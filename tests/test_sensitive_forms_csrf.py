# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1761: los cuatro formularios POST sensibles renderizan token CSRF.

Con la protección global activa, el cierre fiscal, el comparativo real vs.
presupuesto, el toggle de contadores externos y las plantillas de impresión
deben exponer el token y rechazar un POST sin él antes de ejecutar la vista.
"""

from __future__ import annotations

import re
from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    ExternalCounter,
    FiscalYear,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    database,
)

PATRON_TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def escenario_csrf():
    """App con CSRF activo, administrador con rol y datos mínimos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": True,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]
    user_id = f"csrf-{suffix}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Modules(module="admin", default=False, enabled=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        admin_role = Roles(name="admin", note="Administrador")
        accounting = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one()
        database.session.add(admin_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=admin_role.id,
                    module_id=accounting.id,
                    access=True,
                    view=True,
                    report=True,
                    edit=True,
                    create=True,
                ),
                User(
                    id=user_id,
                    user=f"admin_{suffix}",
                    name="Admin CSRF",
                    password=b"unused",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(RolesUser(user_id=user_id, role_id=admin_role.id, active=True))
        fiscal_year = FiscalYear(
            id=f"FY-{suffix}",
            entity="cacao",
            name=f"Ejercicio {suffix}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        counter = ExternalCounter(company="cacao", name=f"Contador {suffix}", last_used=1, is_active=True)
        database.session.add_all([fiscal_year, counter])
        database.session.commit()
        ids = {"counter": counter.id, "fiscal_year": fiscal_year.id}
    yield application, user_id, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _cliente(application, user_id: str):
    """Cliente autenticado como el administrador del escenario."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _formulario_con(html: str, aguja: str) -> str:
    """Devuelve el formulario que contiene la aguja indicada."""
    posicion = html.index(aguja)
    inicio = html.rindex("<form", 0, posicion)
    fin = html.index("</form>", posicion)
    return html[inicio:fin]


@pytest.mark.parametrize(
    ("ruta_get", "aguja", "ruta_post", "datos"),
    [
        (
            "/accounting/fiscal_year_closing/new",
            'name="fiscal_year_id"',
            "/accounting/fiscal_year_closing/new",
            {"company": "cacao"},
        ),
        (
            "/accounting/presupuestos/report/real-vs-budget",
            'name="granularity"',
            "/accounting/presupuestos/report/real-vs-budget",
            {"company": "cacao"},
        ),
        (
            "/admin/print-templates/new",
            'name="template_body"',
            "/admin/print-templates/new",
            {"document_type": "sales_invoice", "code": "X", "name": "X"},
        ),
    ],
)
def test_formularios_sensibles_renderizan_y_exigen_csrf(escenario_csrf, ruta_get, aguja, ruta_post, datos):
    """El formulario expone el token y un POST sin token responde 400."""
    application, user_id, _ = escenario_csrf
    client = _cliente(application, user_id)

    response = client.get(ruta_get)
    assert response.status_code == 200
    formulario = _formulario_con(response.get_data(as_text=True), aguja)
    assert PATRON_TOKEN.search(formulario) is not None

    assert client.post(ruta_post, data=datos).status_code == 400


def test_toggle_de_contador_externo_renderiza_y_exige_csrf(escenario_csrf):
    """El formulario de toggle del contador incluye token y rechaza POST sin él."""
    application, user_id, ids = escenario_csrf
    client = _cliente(application, user_id)
    ruta = f"/accounting/external-counter/{ids['counter']}/toggle-active"

    response = client.get("/accounting/external-counter/list")
    assert response.status_code == 200
    formulario = _formulario_con(response.get_data(as_text=True), ruta)
    assert PATRON_TOKEN.search(formulario) is not None

    assert client.post(ruta).status_code == 400


def _token(cliente, ruta_get: str, aguja: str) -> str:
    """Extrae el token del formulario que contiene la aguja."""
    html = cliente.get(ruta_get).get_data(as_text=True)
    return PATRON_TOKEN.search(_formulario_con(html, aguja)).group(1)


def test_toggle_de_contador_con_token_cambia_el_estado(escenario_csrf):
    """Con el token del formulario el toggle ejecuta la transición."""
    application, user_id, ids = escenario_csrf
    client = _cliente(application, user_id)
    ruta = f"/accounting/external-counter/{ids['counter']}/toggle-active"
    token = _token(client, "/accounting/external-counter/list", ruta)

    response = client.post(ruta, data={"csrf_token": token})

    assert response.status_code == 302
    with application.app_context():
        assert database.session.get(ExternalCounter, ids["counter"]).is_active is False


def test_plantilla_de_impresion_con_token_se_crea_y_edita(escenario_csrf):
    """El alta y la edición de plantilla persisten con un token válido."""
    from cacao_accounting.printing.models import PrintTemplate

    application, user_id, _ = escenario_csrf
    client = _cliente(application, user_id)
    codigo = f"CSRF-{uuid4().hex[:6]}"
    token = _token(client, "/admin/print-templates/new", 'name="template_body"')

    creada = client.post(
        "/admin/print-templates/new",
        data={
            "csrf_token": token,
            "document_type": "sales_invoice",
            "code": codigo,
            "name": "Plantilla CSRF",
            "template_body": "<p>Documento</p>",
        },
    )
    assert creada.status_code == 302

    with application.app_context():
        plantilla = database.session.execute(database.select(PrintTemplate).filter_by(code=codigo)).scalar_one()
        template_id = plantilla.id

    edicion = f"/admin/print-templates/{template_id}/edit"
    token_edicion = _token(client, edicion, 'name="template_body"')
    actualizada = client.post(
        edicion,
        data={
            "csrf_token": token_edicion,
            "document_type": "sales_invoice",
            "code": codigo,
            "name": "Plantilla CSRF editada",
            "template_body": "<p>Documento editado</p>",
        },
    )
    assert actualizada.status_code in (200, 302)
    with application.app_context():
        assert database.session.get(PrintTemplate, template_id).name == "Plantilla CSRF editada"


@pytest.mark.parametrize(
    ("ruta", "datos"),
    [
        ("/accounting/fiscal_year_closing/new", {"company": "cacao", "fiscal_year_id": "FY"}),
        ("/accounting/presupuestos/report/real-vs-budget", {"company": "cacao", "granularity": "month"}),
    ],
)
def test_cierre_y_reporte_aceptan_el_token_del_formulario(escenario_csrf, ruta, datos):
    """El token del propio formulario supera CSRF y llega a la vista."""
    application, user_id, ids = escenario_csrf
    client = _cliente(application, user_id)
    aguja = 'name="fiscal_year_id"' if "fiscal" in ruta else 'name="granularity"'
    datos = {**datos, "csrf_token": _token(client, ruta, aguja)}
    if "fiscal" in ruta:
        datos["fiscal_year_id"] = ids["fiscal_year"]

    respuesta = client.post(ruta, data=datos)
    assert respuesta.status_code != 400
    assert "CSRF" not in respuesta.get_data(as_text=True)
