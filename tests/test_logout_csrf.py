# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El cierre de sesión exige POST y token CSRF.

Escenario de negocio (issue #2153): el cierre de sesión se exponía como enlace
GET. Un sitio externo podía forzar la navegación y cerrar la sesión de la
víctima sin su intención. La interfaz ahora envía un formulario POST con token.
"""

from __future__ import annotations

import re

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, User, database

CONTRASENA = "logout-csrf-2026"


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
            "WTF_CSRF_ENABLED": True,
            "TESTING": True,
            "SECRET_KEY": "logout-csrf-secret",
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
    return application


def _autenticar(client, application) -> None:
    with application.app_context():
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True


def test_logout_rechaza_get():
    """La ruta ya no acepta navegación GET."""
    application = _crear_app()
    try:
        client = application.test_client()
        _autenticar(client, application)

        respuesta = client.get("/logout")

        assert respuesta.status_code == 405
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_logout_sin_token_csrf_es_rechazado():
    """Un POST externo sin token no cierra la sesión."""
    application = _crear_app()
    try:
        client = application.test_client()
        _autenticar(client, application)

        respuesta = client.post("/logout")

        assert respuesta.status_code == 400
        with client.session_transaction() as session:
            assert session.get("_user_id") == "admin"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_logout_con_token_csrf_cierra_la_sesion():
    """El formulario legítimo con token sí finaliza la sesión."""
    application = _crear_app()
    try:
        client = application.test_client()
        html = client.get("/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
        _autenticar(client, application)

        respuesta = client.post("/logout", data={"csrf_token": token})

        assert respuesta.status_code == 302
        assert respuesta.headers["Location"].endswith("/login")
        with client.session_transaction() as session:
            assert session.get("_user_id") is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
