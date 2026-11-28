# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1950: los formularios administrativos envían token CSRF.

Con la protección global activa, los tres formularios de configuración deben
renderizar el token, aceptar el POST con token válido y rechazar el envío sin
token antes de ejecutar la vista.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Roles,
    RolesUser,
    Tax,
    TaxTemplate,
    TaxTemplateItem,
    User,
    database,
)

PATRON_TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def admin_csrf_scenario():
    """App con CSRF activo, administrador y catálogos fiscales mínimos."""
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
    user_id = f"admin-csrf-{suffix}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao SA", tax_id="J-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        role = Roles(name=f"admin-{suffix}", note="Administrador")
        database.session.add(role)
        database.session.flush()
        database.session.add(
            User(
                id=user_id,
                user=f"admin_{suffix}",
                name="Admin CSRF",
                password=b"unused",
                classification="admin",
                active=True,
                company="cacao",
            )
        )
        database.session.flush()
        database.session.add(RolesUser(user_id=user_id, role_id=role.id, active=True))
        tax = Tax(name=f"IVA {suffix}", rate="15", tax_type="percentage", is_active=True)
        template = TaxTemplate(name=f"Plantilla {suffix}", company="cacao", template_type="selling", is_active=True)
        database.session.add_all([tax, template])
        database.session.commit()
        ids = {"tax": tax.id, "template": template.id, "suffix": suffix}
    yield application, user_id, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _cliente(application, user_id: str):  # noqa: ANN001 - fixture helper
    """Cliente HTTP autenticado como el administrador del escenario."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _formulario_de(html: str, campo: str) -> str:
    """Devuelve el formulario que contiene el campo indicado."""
    posicion = html.index(f'name="{campo}"')
    inicio = html.rindex("<form", 0, posicion)
    fin = html.index("</form>", posicion)
    return html[inicio:fin]


def _token(client, ruta: str, campo: str) -> str:
    """Extrae el token CSRF del formulario que contiene ``campo``."""
    response = client.get(ruta)
    assert response.status_code == 200
    formulario = _formulario_de(response.get_data(as_text=True), campo)
    match = PATRON_TOKEN.search(formulario)
    assert match is not None, f"{ruta} no renderiza csrf_token en el formulario de {campo}"
    return match.group(1)


def test_validacion_externa_renderiza_token(admin_csrf_scenario):
    """La configuración de validación externa expone el token."""
    application, user_id, _ = admin_csrf_scenario

    assert _token(_cliente(application, user_id), "/settings/external-document-validation", "base_url")


def test_plantillas_de_impuesto_renderizan_token(admin_csrf_scenario):
    """El alta de plantillas fiscales expone el token."""
    application, user_id, _ = admin_csrf_scenario

    assert _token(_cliente(application, user_id), "/settings/tax-templates", "template_type")


def test_items_de_plantilla_renderizan_token(admin_csrf_scenario):
    """Las líneas de plantilla fiscal exponen el token."""
    application, user_id, ids = admin_csrf_scenario

    assert _token(_cliente(application, user_id), f"/settings/tax-templates/{ids['template']}/items", "calculation_base")


def test_plantilla_fiscal_persiste_con_token_valido(admin_csrf_scenario):
    """El POST con token crea la plantilla; sin token responde 400."""
    application, user_id, ids = admin_csrf_scenario
    client = _cliente(application, user_id)
    token = _token(client, "/settings/tax-templates", "template_type")

    sin_token = client.post("/settings/tax-templates", data={"name": "Sin token"})
    assert sin_token.status_code == 400

    con_token = client.post(
        "/settings/tax-templates",
        data={
            "csrf_token": token,
            "name": f"Nueva plantilla {ids['suffix']}",
            "company": "cacao",
            "template_type": "selling",
        },
    )
    assert con_token.status_code == 302
    with application.app_context():
        nombres = database.session.execute(database.select(TaxTemplate.name)).scalars().all()
        assert f"Nueva plantilla {ids['suffix']}" in nombres


def test_linea_fiscal_persiste_con_token_valido(admin_csrf_scenario):
    """El POST con token agrega la línea; sin token responde 400."""
    application, user_id, ids = admin_csrf_scenario
    client = _cliente(application, user_id)
    ruta = f"/settings/tax-templates/{ids['template']}/items"
    token = _token(client, ruta, "calculation_base")

    sin_token = client.post(ruta, data={"tax_id": ids["tax"], "sequence": "10"})
    assert sin_token.status_code == 400

    con_token = client.post(
        ruta,
        data={
            "csrf_token": token,
            "tax_id": ids["tax"],
            "sequence": "10",
            "calculation_base": "net_document",
            "behavior": "additive",
        },
    )
    assert con_token.status_code == 302
    with application.app_context():
        template = database.session.get(TaxTemplate, ids["template"])
        assert template is not None
        assert (
            database.session.execute(
                database.select(TaxTemplateItem.id).filter_by(tax_template_id=ids["template"])
            ).scalar_one_or_none()
            is not None
        )


def test_validacion_externa_persiste_con_token_valido(admin_csrf_scenario):
    """El POST de validación externa exige token y persiste la configuración."""
    from cacao_accounting.printing.settings import external_validation_base_url, external_validation_enabled

    application, user_id, _ = admin_csrf_scenario
    client = _cliente(application, user_id)
    ruta = "/settings/external-document-validation"
    token = _token(client, ruta, "base_url")

    sin_token = client.post(ruta, data={"enabled": "on", "base_url": "https://validacion.example"})
    assert sin_token.status_code == 400

    con_token = client.post(
        ruta,
        data={"csrf_token": token, "enabled": "on", "base_url": "https://validacion.example"},
    )
    assert con_token.status_code == 302
    with application.app_context():
        assert external_validation_enabled() is True
        assert external_validation_base_url() == "https://validacion.example"
