# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El formulario de reposición es solo de alta.

Escenario de negocio (issue #2034): la plantilla conservaba título, campos
precargados y ramas de edición que ningún caller podía activar; la única ruta
que la renderiza crea solicitudes y no pasa ``reposicion`` ni ``attached_ids``.
Se retira la rama sin consumidor.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Modules, User, database


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
                Modules(module="cash", default=False, enabled=True),
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
                ),
            ]
        )
        database.session.commit()
    return application


def test_el_formulario_solo_ofrece_alta():
    """No queda rastro del modo edición sin caller."""
    application = _crear_app()
    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.get("/cash_management/petty-cash-replenishment/new")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "Nueva reposición de Caja Chica" in html
        assert "Editar reposición de Caja Chica" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
