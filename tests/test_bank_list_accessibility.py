# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El nombre accesible de la navegación de bancos se traduce.

Escenario de negocio (issue #2027): el landmark usaba el literal inglés
``aria-label="breadcrumb"``; con locale español el lector de pantalla seguía
anunciando ese texto.
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
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                    company="cacao",
                ),
            ]
        )
        database.session.commit()
    return application


def test_el_listado_usa_un_nombre_accesible_traducible():
    """El HTML ya no publica el literal inglés."""
    application = _crear_app()
    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.get("/cash_management/bank/list")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert 'aria-label="Ruta de navegación"' in html
        assert 'aria-label="breadcrumb"' not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
