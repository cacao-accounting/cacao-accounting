# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alineación del acceso al portal con la clasificación del usuario.

Escenario de negocio: un usuario con rol ``customer`` pero clasificación
``user`` no es elegible para el portal. El login no debe enviarlo a una pantalla
que el guard rechazará; solo ``classification="customer"`` redirige al portal.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Party, User, database

CONTRASENA = "portal-alineacion-2026"


@pytest.fixture
def portal_usuarios():
    """Usuario con rol customer/clasificación user y usuario de portal real."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        cliente = Party(code="CLI-1", name="Cliente", is_customer=True)
        database.session.add(cliente)
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id="rol_solo",
                    user="rol_solo",
                    name="Rol Customer",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="user",
                    party_id=cliente.id,
                    company="cacao",
                ),
                User(
                    id="portal",
                    user="portal",
                    name="Portal Customer",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="customer",
                    party_id=cliente.id,
                    company="cacao",
                ),
            ]
        )
        database.session.commit()
        crea_roles_predeterminados()
        asigna_rol_a_usuario("rol_solo", "customer")
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(client, usuario: str):
    return client.post(
        "/login",
        data={"usuario": usuario, "acceso": CONTRASENA},
        follow_redirects=False,
    )


def test_rol_customer_sin_clasificacion_no_va_al_portal(portal_usuarios):
    """El login no redirige al portal si la clasificación no es customer."""
    client = portal_usuarios.test_client()

    response = _login(client, "rol_solo")

    assert response.status_code == 302
    assert "/portal/customer" not in response.headers["Location"]
    assert client.get("/portal/customer").status_code == 403


def test_clasificacion_customer_si_va_al_portal(portal_usuarios):
    """Control positivo: classification=customer conserva el portal."""
    client = portal_usuarios.test_client()

    response = _login(client, "portal")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/portal/customer")
