# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Un hash de contraseña ilegible no rompe el login.

Escenario de negocio (issue #1965): si la fila del usuario contiene bytes que
no son un hash Argon2 válido (corrupción, migración o dato legacy), el intento
de login propagaba ``InvalidHashError`` y respondía 500 en lugar de rechazar
la credencial de forma controlada.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth.helpers import autenticar_usuario
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, User, database


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
            "SECRET_KEY": "invalid-hash-secret",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
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
                    id="legacy",
                    user="legacy",
                    name="Usuario Legacy",
                    password=b"bad",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
    return application


def test_autenticar_rechaza_un_hash_invalido():
    """La verificación directa devuelve None en lugar de propagar la excepción."""
    application = _crear_app()
    try:
        with application.app_context():
            assert autenticar_usuario("legacy", "cualquier-clave") is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_login_web_responde_sin_500():
    """El endpoint presenta credenciales inválidas sin romper la petición."""
    application = _crear_app()
    try:
        client = application.test_client()
        respuesta = client.post(
            "/login",
            data={"usuario": "legacy", "acceso": "cualquier-clave"},
            follow_redirects=True,
        )

        assert respuesta.status_code == 200
        with client.session_transaction() as session:
            assert session.get("_user_id") is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
