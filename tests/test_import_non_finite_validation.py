# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#950: la importación rechaza números no finitos como error de validación.

`NaN` e `Infinity` no deben escapar como excepción HTTP ni persistirse como
importes; el adaptador devuelve errores accionables por fila.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos.statement_service import BankStatementError, _decimal_value
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.imports.adapters.transaction_documents import (
    TransactionDocumentAdapter,
    TransactionImportConfig,
)


@pytest.fixture
def non_finite_scenario():
    """Create a company with a functional currency."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {uuid4().hex[:6]}",
                    tax_id=f"TAX-{uuid4().hex[:6]}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()

    yield app

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _transaction_adapter() -> TransactionDocumentAdapter:
    """Build the generic transaction adapter used by Compras and Ventas."""
    return TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_request",
            header_model=object,
            item_model=object,
            parent_field="purchase_request_id",
        )
    )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_transaction_amounts_reject_non_finite_values(non_finite_scenario, value):
    """Cantidad and precio no finitos return row errors, not exceptions."""
    app = non_finite_scenario

    with app.app_context():
        errors = _transaction_adapter().validate_row({"document_ref": "PR-1", "cantidad": value, "precio_unitario": value})

    assert any("'cantidad'" in error for error in errors)
    assert any("'precio_unitario'" in error for error in errors)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_transaction_exchange_rate_rejects_non_finite_values(non_finite_scenario, value):
    """The explicit rate must be finite before any amount is calculated."""
    app = non_finite_scenario

    with app.app_context():
        with pytest.raises(ValueError):
            _transaction_adapter()._currency_and_rate(
                {"moneda": "USD", "tipo_cambio": value},
                None,
                "alpha",
                date(2026, 5, 10),
            )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_bank_row_amounts_reject_non_finite_values(non_finite_scenario, value):
    """The bank statement adapter reports the invalid amount by column."""
    app = non_finite_scenario

    with app.app_context():
        errors = BankStatementAdapter().validate_row(
            {"bank_account_id": "BA-1", "posting_date": "2026-05-10", "deposit": value}
        )

    assert any("Monto bancario inválido en columna 'deposit'" in error for error in errors)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_statement_service_rejects_non_finite_decimals(value):
    """The statement parser rejects a non-finite Decimal before persisting."""
    with pytest.raises(BankStatementError):
        _decimal_value(value)
