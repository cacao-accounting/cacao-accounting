# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tokens CSRF en formularios administrativos y contables.

Escenario de negocio: con CSRFProtect activo, los formularios de cierre fiscal,
comparativo real vs. presupuesto, contadores externos y plantillas de impresión
deben enviar un token válido; de lo contrario el navegador recibe 400 y el
flujo no puede ejecutarse.
"""

from __future__ import annotations

import re

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, ExternalCounter, Modules, User, database

CONTRASENA = "csrf-formularios-2026"


@pytest.fixture
def formularios_csrf():
    """Cloud con módulos contables, usuario admin y un contador externo."""
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
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="admin", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
                ExternalCounter(
                    company="cacao",
                    name="Contador fiscal",
                    counter_type="fiscal",
                    is_active=True,
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        asigna_rol_a_usuario("admin", "admin")
        database.session.commit()
        contador_id = database.session.execute(database.select(ExternalCounter)).scalar_one().id
    yield application, contador_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    pagina = client.get("/login")
    token = re.search(r'csrf_token[^>]*value="([^"]+)"', pagina.get_data(as_text=True))
    assert token is not None
    response = client.post(
        "/login",
        data={"usuario": "admin", "acceso": CONTRASENA, "csrf_token": token.group(1)},
        follow_redirects=True,
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "ruta",
    [
        "/accounting/fiscal_year_closing/new",
        "/accounting/presupuestos/report/real-vs-budget",
        "/accounting/external-counter/list",
        "/admin/print-templates/new",
    ],
)
def test_formularios_incluyen_csrf(formularios_csrf, ruta):
    """Cada formulario renderiza el campo csrf_token."""
    application, _ = formularios_csrf
    client = application.test_client()
    _iniciar(client)

    response = client.get(ruta)

    assert response.status_code == 200
    assert 'name="csrf_token"' in response.get_data(as_text=True)


def test_post_sin_token_es_rechazado(formularios_csrf):
    """CSRFProtect sigue activo y rechaza un POST sin token."""
    application, contador_id = formularios_csrf
    client = application.test_client()
    _iniciar(client)

    for ruta in (
        "/accounting/fiscal_year_closing/new",
        "/accounting/presupuestos/report/real-vs-budget",
        f"/accounting/external-counter/{contador_id}/toggle-active",
        "/admin/print-templates/new",
    ):
        response = client.post(ruta, data={})
        assert response.status_code == 400
