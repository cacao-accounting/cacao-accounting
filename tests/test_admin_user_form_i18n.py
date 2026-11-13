# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los botones del formulario de usuario respetan el idioma.

Escenario de negocio (issue #2022): las rutas pasaban «Nuevo Usuario» y
«Actualizar Usuario» como literales sin gettext; con locale inglés el botón
seguía en español.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database


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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    language="en",
                ),
            ]
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_los_botones_de_usuario_se_traducen_al_ingles():
    """Alta y edición usan los msgid traducidos, no literales."""
    application = _crear_app()
    try:
        client = _cliente(application)

        alta = client.get("/settings/users/new")
        edicion = client.get("/settings/users/admin/edit")

        assert alta.status_code == 200
        assert "Nuevo Usuario" not in alta.get_data(as_text=True)
        assert "New User" in alta.get_data(as_text=True)
        assert edicion.status_code == 200
        assert "Actualizar Usuario" not in edicion.get_data(as_text=True)
        assert "Update User" in edicion.get_data(as_text=True)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
