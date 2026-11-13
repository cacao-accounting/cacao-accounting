# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El tipo de dimensión respeta la casilla de vigencia.

Escenario de negocio (issue #2003): un checkbox desmarcado no se envía; la
ruta aplicaba True por defecto y no permitía crear un tipo inactivo desde la
interfaz.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, DimensionType, Entity, Modules, User, database


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


@pytest.mark.parametrize(("enviar", "esperado"), [(False, False), (True, True)])
def test_la_casilla_define_el_estado_persistido(enviar, esperado):
    """Sin is_active persiste inactivo; con la casilla, activo."""
    application = _crear_app()
    try:
        client = _cliente(application)
        datos = {"action": "create_type", "name": "Centro de costos"}
        if enviar:
            datos["is_active"] = "on"

        respuesta = client.post("/settings/dimensions", data=datos)

        assert respuesta.status_code == 302
        with application.app_context():
            tipo = database.session.execute(database.select(DimensionType)).scalar_one()
            assert tipo.is_active is esperado
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
