# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Login and portal guards use the same Cloud eligibility rules."""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.auth.roles import asigna_rol_a_usuario, crea_roles_predeterminados
from cacao_accounting.config import configuracion
from cacao_accounting.database import CompanyParty, Currency, Entity, Party, User, database

CONTRASENA = "portal-alineacion-2026"


@pytest.fixture
def portal_usuarios():
    """Cloud con perfiles elegibles y no elegibles para ambos portales."""
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
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
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
        cliente = Party(code="CLI-1920", name="Cliente", is_customer=True, is_active=True)
        proveedor = Party(code="PRV-1920", name="Proveedor", is_supplier=True, is_active=True)
        database.session.add_all([cliente, proveedor])
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="cacao", party_id=cliente.id, is_active=True),
                CompanyParty(company="cacao", party_id=proveedor.id, is_active=True),
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
                    id="portal_cliente",
                    user="portal_cliente",
                    name="Portal Customer",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="customer",
                    party_id=cliente.id,
                    company="cacao",
                ),
                User(
                    id="portal_sin_asociacion",
                    user="portal_sin_asociacion",
                    name="Portal sin asociación",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="customer",
                ),
                User(
                    id="portal_proveedor",
                    user="portal_proveedor",
                    name="Portal Supplier",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="supplier",
                    party_id=proveedor.id,
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
    """Autentica un perfil sin seguir su redirección."""
    return client.post(
        "/login",
        data={"usuario": usuario, "acceso": CONTRASENA},
        follow_redirects=False,
    )


def test_rol_customer_sin_clasificacion_no_va_al_portal(portal_usuarios):
    """El rol customer sin classification customer no recibe acceso."""
    client = portal_usuarios.test_client()

    response = _login(client, "rol_solo")

    assert response.status_code == 302
    assert "/portal/customer" not in response.headers["Location"]
    assert client.get("/portal/customer").status_code == 403


def test_customer_elegible_accede_al_portal(portal_usuarios):
    """El perfil customer con asociaciones activas conserva el acceso."""
    client = portal_usuarios.test_client()

    response = _login(client, "portal_cliente")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/portal/customer")
    assert client.get("/portal/customer").status_code == 200


def test_customer_sin_asociaciones_no_va_al_portal(portal_usuarios):
    """Classification customer sin party/company no recibe redirect al portal."""
    client = portal_usuarios.test_client()

    response = _login(client, "portal_sin_asociacion")

    assert response.status_code == 302
    assert "/portal/customer" not in response.headers["Location"]
    assert client.get("/portal/customer").status_code == 403


def test_supplier_elegible_accede_al_portal(portal_usuarios):
    """El proveedor válido se redirige al portal y pasa su guard."""
    client = portal_usuarios.test_client()

    response = _login(client, "portal_proveedor")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/portal/supplier")
    assert client.get("/portal/supplier").status_code == 200


def test_portal_respeta_idioma_del_usuario(portal_usuarios):
    """El HTML del portal declara el idioma configurado, no un es fijo."""
    with portal_usuarios.app_context():
        usuario = database.session.execute(database.select(User).filter_by(user="portal_cliente")).scalar_one()
        usuario.language = "en"
        database.session.commit()
    client = portal_usuarios.test_client()
    _login(client, "portal_cliente")

    html = client.get("/portal/customer").get_data(as_text=True)

    assert '<html lang="en">' in html
    assert '<html lang="es">' not in html


def test_desktop_login_no_redirige_y_el_guard_rechaza_el_portal():
    """En Desktop el login y el guard mantienen al portal deshabilitado."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
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
        cliente = Party(code="CLI-DESKTOP", name="Cliente", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        database.session.add(
            User(
                id="desktop_portal",
                user="desktop_portal",
                name="Portal Desktop",
                password=proteger_passwd(CONTRASENA),
                active=True,
                classification="customer",
                party_id=cliente.id,
                company="cacao",
            )
        )
        database.session.commit()

    client = application.test_client()
    response = _login(client, "desktop_portal")

    assert response.status_code == 302
    assert "/portal" not in response.headers["Location"]
    portal_response = client.get("/portal/customer")
    assert portal_response.status_code != 200
    assert "/portal/customer" not in portal_response.headers.get("Location", "")
    with application.app_context():
        database.session.remove()
        database.engine.dispose()
