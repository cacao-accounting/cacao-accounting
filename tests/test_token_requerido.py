# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Revocación de acceso al API para usuarios deshabilitados.

Escenario de negocio (issue #1020): con el token JWT persistido en
manejo (vigencia 8 h), el deshabilitamiento del usuario debe cortar el
acceso al API de inmediato, tanto por los controles de instauración
semántica del token como por el gesto de revocación al deshabilitar.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, UserCompanyAccess, database

CONTRASENA = "token-cacao-2026"


def _sembrar_escenario() -> dict[str, str]:
    """Un vendedor interno y el administrador del sistema en modo cloud."""
    database.session.add_all(
        [
            Modules(module="admin", default=False, enabled=True),
            Entity(
                code="cacao",
                name="Cacao Accounting",
                company_name="Cacao Accounting SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            ),
            User(
                id="vendedor",
                user="vendedor",
                name="Vendedor Local",
                password=proteger_passwd(CONTRASENA),
                active=True,
            ),
            UserCompanyAccess(user_id="vendedor", company_code="cacao"),
            User(
                id="admin",
                user="admin",
                name="Administrador",
                password=proteger_passwd(CONTRASENA),
                classification="admin",
                active=True,
            ),
            UserCompanyAccess(user_id="admin", company_code="cacao"),
        ]
    )
    database.session.commit()
    return {"vendedor": "vendedor", "admin": "admin"}


@pytest.fixture
def api_con_usuarios():
    """Aplicación en modo cloud con un usuario interno y el administrador."""
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
        _sembrar_escenario()
    yield application, application.test_client()
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar_sesion(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def _cerrar_sesion(client) -> None:
    """Cierra la sesión para poder autenticar a otro usuario en el mismo cliente."""
    client.post("/logout")


def _token_persistido(application, usuario: str):
    """Devuelve el token JWT emitido durante el login del usuario."""
    with application.app_context():
        from cacao_accounting.database import User as Usuario

        identidad = database.session.execute(database.select(Usuario).filter_by(user=usuario)).scalar_one()
        return identidad.token


def _llamar_api_test(client, token) -> int:
    response = client.get("/api/test", headers={"Authorization": f"Bearer {token}"})
    return response.status_code


def test_el_token_del_usuario_activo_autoriza_el_llamado(api_con_usuarios):
    """Control positivo: el token emitido en el login consume el API."""
    application, client = api_con_usuarios
    _iniciar_sesion(client, "vendedor")
    token = _token_persistido(application, "vendedor")
    assert token is not None
    assert _llamar_api_test(client, token) == 200


def test_token_del_usuario_desactivado_no_autoriza_el_llamado(api_con_usuarios):
    """Vigente pero deshabilitado: el token no debe autorizar el API."""
    application, client = api_con_usuarios
    _iniciar_sesion(client, "vendedor")
    token = _token_persistido(application, "vendedor")
    assert token is not None
    assert _llamar_api_test(client, token) == 200

    with application.app_context():
        from cacao_accounting.database import User as Usuario

        identidad = database.session.execute(database.select(Usuario).filter_by(user="vendedor")).scalar_one()
        identidad.active = False
        database.session.commit()
    assert _llamar_api_test(client, token) == 401


def test_deshabilitar_por_admin_revoca_el_token_persistido(api_con_usuarios):
    """Toggle revokes API and browser credentials across reactivation."""
    application, client = api_con_usuarios
    _iniciar_sesion(client, "vendedor")
    token = _token_persistido(application, "vendedor")
    assert token is not None
    assert _llamar_api_test(client, token) == 200

    _cerrar_sesion(client)
    _iniciar_sesion(client, "admin")
    with application.app_context():
        from cacao_accounting.database import User as Usuario

        identidad = database.session.execute(database.select(Usuario).filter_by(user="vendedor")).scalar_one()
    response = client.post(
        "/settings/users",
        data={"user_id": identidad.id, "action": "toggle"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with application.app_context():
        from cacao_accounting.database import User as Usuario

        deshabilitado = database.session.execute(database.select(Usuario).filter_by(user="vendedor")).scalar_one()
        assert deshabilitado.active is False
        assert deshabilitado.token is None
        assert deshabilitado.auth_version == 1
    assert _llamar_api_test(client, token) == 401

    response = client.post(
        "/settings/users",
        data={"user_id": identidad.id, "action": "toggle"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with application.app_context():
        reactivado = database.session.execute(database.select(Usuario).filter_by(user="vendedor")).scalar_one()
        assert reactivado.active is True
        assert reactivado.auth_version == 2
    assert _llamar_api_test(client, token) == 401


def test_editar_usuario_revoca_jwt_y_sesion_tras_reactivacion(api_con_usuarios):
    """The edit form cannot revive a JWT or browser session after reactivation."""
    application, _ = api_con_usuarios
    browser_client = application.test_client()
    _iniciar_sesion(browser_client, "vendedor")
    token = _token_persistido(application, "vendedor")
    assert token is not None
    assert _llamar_api_test(application.test_client(), token) == 200

    admin_client = application.test_client()
    _iniciar_sesion(admin_client, "admin")

    def editar_usuario(*, active: bool):
        data = {"usuario": "vendedor", "name": "Vendedor Local", "classification": "system"}
        if active:
            data["active"] = "y"
        return admin_client.post("/settings/users/vendedor/edit", data=data)

    assert editar_usuario(active=False).status_code == 302
    with application.app_context():
        usuario = database.session.get(User, "vendedor")
        assert usuario is not None
        assert usuario.active is False
        assert usuario.auth_version == 1
        assert usuario.token is None
    assert _llamar_api_test(application.test_client(), token) == 401
    assert browser_client.get("/auth/profile").status_code == 302

    assert editar_usuario(active=True).status_code == 302
    with application.app_context():
        usuario = database.session.get(User, "vendedor")
        assert usuario is not None
        assert usuario.active is True
        assert usuario.auth_version == 2
    assert _llamar_api_test(application.test_client(), token) == 401
    assert browser_client.get("/auth/profile").status_code == 302

    fresh_client = application.test_client()
    _iniciar_sesion(fresh_client, "vendedor")
    new_token = _token_persistido(application, "vendedor")
    assert new_token is not None and new_token != token
    assert _llamar_api_test(fresh_client, new_token) == 200
