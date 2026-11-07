# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación del esquema contra el motor real configurado en DATABASE_URL.

Solo se ejecuta cuando CHECK_DATABASE=true; el conftest salta estos items en
corridas normales. En CI el job de databases ejecuta ``cacaoctl db reset``
contra cada motor antes de correr ``pytest -m database``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

pytestmark = pytest.mark.database

TABLAS_CRITICAS = [
    "accounts",
    "ar_ap_ledger_entry",
    "book",
    "entity",
    "gl_entry",
    "party",
    "payment_entry",
    "purchase_invoice",
    "sales_invoice",
    "stock_ledger_entry",
    "user",
]


@pytest.fixture(scope="module")
def esquema():
    """App apuntando al motor de DATABASE_URL con el esquema ya inicializado."""
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion

    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with application.app_context():
        from cacao_accounting.database import database

        database.create_all()
        yield application
        database.session.remove()
        database.engine.dispose()


def _inspector(esquema):
    from cacao_accounting.database import database

    return inspect(database.engine)


def test_esquema_materializa_sin_error(esquema):
    """create_all sobre el motor configurado completa sin excepción."""
    assert esquema is not None


@pytest.mark.parametrize("tabla", TABLAS_CRITICAS)
def test_tabla_critica_existe(esquema, tabla):
    """Cada tabla critica del ledger y subledgers existe en el motor real."""
    assert _inspector(esquema).has_table(tabla), f"Tabla {tabla} no existe en el esquema"


def test_gl_entry_columnas_multimoneda(esquema):
    """gl_entry conserva el contrato multimoneda (columnas de moneda y tasa)."""
    columnas = {col["name"] for col in _inspector(esquema).get_columns("gl_entry")}
    requeridas = {
        "debit",
        "credit",
        "debit_in_account_currency",
        "credit_in_account_currency",
        "account_currency",
        "company_currency",
        "exchange_rate",
    }
    assert requeridas.issubset(columnas), f"Faltan columnas: {requeridas - columnas}"


def test_gl_entry_restringe_debito_credito_exclusivos(esquema):
    """El esquema define la restriccion que impide debito y credito a la vez."""
    constraints = _inspector(esquema).get_check_constraints("gl_entry")
    textos = " ".join(str(c.get("sqltext", c.get("text", ""))).lower() for c in constraints)
    assert "debit" in textos and "credit" in textos, "No se encontro la restriccion debito/credito en gl_entry"
