# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Montos de caja y conciliación se validan en la frontera.

Escenario de negocio:
- #1972: NaN en conciliación bancaria escapaba como InvalidOperation/500.
- #1984: float_amount no numérico en caja chica producía HTTP 500.
"""

from __future__ import annotations

import importlib

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, PettyCashAccount, User, database


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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "abc"])
def test_conciliacion_rechaza_montos_no_finitos(valor):
    """#1972: el parser devuelve error de formulario, no InvalidOperation."""
    routes = importlib.import_module("cacao_accounting.bancos.routes")
    application = _crear_app()
    try:
        with application.test_request_context(
            "/cash_management/bank-reconciliation/apply",
            method="POST",
            data={"amount_txn": valor, "difference_txn": "0", "target_txn": "payment_entry:pay-1"},
        ):
            match, difference, error = routes._parse_reconciliation_item_from_form("txn")

            assert match is None and difference is None
            assert error is not None and "número" in error
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_caja_chica_rechaza_monto_no_numerico():
    """#1984: float_amount inválido vuelve al formulario sin persistir."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/petty-cash/new",
            data={"company": "cacao", "name": "Caja principal", "float_amount": "abc"},
        )

        assert respuesta.status_code == 200
        assert "debe ser un número válido" in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(PettyCashAccount)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
