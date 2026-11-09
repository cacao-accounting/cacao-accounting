# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El alta de lista de precios valida compañía y moneda.

Escenario de negocio (issue #2010): el formulario aceptaba referencias libres;
con FK activas, una compañía o moneda inexistente producía HTTP 500 durante
el flush.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    PriceList,
    User,
    database,
)


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
                Modules(module="sales", default=False, enabled=True),
                Entity(
                    code="CACAO",
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


@pytest.mark.parametrize(
    ("company", "currency", "mensaje"),
    [
        ("NOPE", "NIO", "La compañía seleccionada no existe."),
        ("CACAO", "NOPE", "La moneda seleccionada no existe o no está activa."),
    ],
)
def test_rechaza_referencias_inexistentes_sin_500(company, currency, mensaje):
    """La respuesta es controlada y no persiste la lista."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/price-lists",
            data={
                "name": "Lista inválida",
                "company": company,
                "currency": currency,
                "is_selling": "1",
                "is_active": "1",
            },
            follow_redirects=True,
        )

        assert respuesta.status_code == 200
        assert mensaje in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(PriceList)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_acepta_referencias_existentes():
    """El control positivo conserva el alta normal."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/price-lists",
            data={
                "name": "Lista válida",
                "company": "CACAO",
                "currency": "NIO",
                "is_selling": "1",
                "is_active": "1",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            lista = database.session.execute(database.select(PriceList)).scalar_one()
            assert lista.name == "Lista válida"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
