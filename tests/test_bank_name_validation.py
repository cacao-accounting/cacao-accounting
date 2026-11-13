# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El alta de banco muestra el error de nombre obligatorio.

Escenario de negocio (issue #2029): un nombre vacío o de espacios no persistía
pero el formulario reaparecía sin explicación; ahora el error de WTForms se
renderiza con mensaje traducible.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, Currency, Entity, Modules, User, database


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


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


@pytest.mark.parametrize("nombre", ["", "   "])
def test_muestra_el_error_de_nombre_obligatorio(nombre):
    """El formulario rechazado explica el error y no persiste el banco."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/cash_management/bank/new", data={"name": nombre})

        assert respuesta.status_code == 200
        assert "Este campo es obligatorio." in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(Bank)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
