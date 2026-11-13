# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Desactivar un usuario invalida su sesión Flask-Login vigente.

Escenario de negocio (issue #1732): el flujo administrativo revocaba el JWT
pero no las sesiones web. El user loader recargaba al usuario por ID sin mirar
``active`` y la sesión seguía accediendo a rutas protegidas.
"""

from __future__ import annotations

import pytest
from flask_login import login_user
from sqlalchemy.pool import StaticPool
from werkzeug.exceptions import Forbidden

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.auth.permisos import Permisos
from cacao_accounting.database import Currency, Entity, Modules, User, database

CONTRASENA = "sesion-desactivada-2026"


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "deactivated-session-secret",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                    id="operador",
                    user="operador",
                    name="Operador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="system",
                ),
            ]
        )
        database.session.commit()
    return application


def test_la_sesion_deja_de_autenticar_al_desactivar():
    """La cookie existente pierde acceso cuando el usuario queda inactivo."""
    application = _crear_app()
    try:
        client = application.test_client()
        login = client.post(
            "/login",
            data={"usuario": "operador", "acceso": CONTRASENA},
            follow_redirects=True,
        )
        assert login.status_code == 200
        assert client.get("/auth/profile").status_code == 200

        with application.app_context():
            usuario = database.session.execute(database.select(User).filter_by(id="operador")).scalar_one()
            usuario.active = False
            database.session.commit()

        respuesta = client.get("/auth/profile")

        assert respuesta.status_code == 302
        assert "/login" in respuesta.headers["Location"]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_user_loader_ignora_usuarios_inactivos():
    """La recarga de sesión devuelve None cuando active es False."""
    from cacao_accounting.auth import cargar_sesion

    application = _crear_app()
    try:
        with application.app_context():
            usuario = database.session.execute(database.select(User).filter_by(id="operador")).scalar_one()
            usuario.active = False
            database.session.commit()

            assert cargar_sesion("operador") is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_usuario_con_active_null_no_recibe_permisos():
    """A nullable active flag must fail closed in the shared permission resolver."""
    application = _crear_app()
    try:
        with application.app_context():
            usuario = database.session.get(User, "operador")
            modulo = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one()
            assert usuario is not None
            usuario.active = None
            usuario.classification = "admin"
            database.session.commit()

            permisos = Permisos(modulo=modulo.id, usuario=usuario.id)
            assert permisos.administrador is False
            assert permisos.autorizado is False
            assert permisos.access is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_guardia_admin_rechaza_active_null():
    """The admin guard must require explicit active=True, even after login."""
    from cacao_accounting.admin.services import _require_system_admin

    application = _crear_app()
    try:
        with application.test_request_context("/settings/users"):
            with application.app_context():
                usuario = database.session.get(User, "operador")
                assert usuario is not None
                usuario.active = None
                usuario.classification = "admin"
                database.session.commit()
                assert login_user(usuario)

                with pytest.raises(Forbidden):
                    _require_system_admin()
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
