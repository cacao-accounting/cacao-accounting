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


def test_purchase_order_adapter_rejects_non_finite_quantity_and_price(non_finite_scenario):
    """The purchase-order importer does not persist NaN or Infinity lines."""
    from cacao_accounting.imports.adapters.purchase_order import PurchaseOrderAdapter

    app = non_finite_scenario
    row = {"document_ref": "PO-1", "fecha": "2026-05-10", "proveedor": "SUP-1", "producto": "ITEM-1"}
    with app.app_context():
        errors_qty = PurchaseOrderAdapter().validate_document([{**row, "cantidad": "NaN", "precio_unitario": "1"}])
        errors_price = PurchaseOrderAdapter().validate_document([{**row, "cantidad": "1", "precio_unitario": "Infinity"}])

    assert any("finito" in error for error in errors_qty)
    assert any("finito" in error for error in errors_price)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_purchase_order_adapter_rejects_non_finite_exchange_rate(non_finite_scenario, value):
    """An imported purchase order cannot carry a non-finite exchange rate."""
    from cacao_accounting.imports.adapters.purchase_order import PurchaseOrderAdapter

    app = non_finite_scenario
    row = {
        "document_ref": "PO-1",
        "fecha": "2026-05-10",
        "proveedor": "SUP-1",
        "producto": "ITEM-1",
        "cantidad": "1",
        "precio_unitario": "1",
        "moneda": "USD",
        "tipo_cambio": value,
    }
    with app.app_context():
        with pytest.raises(ValueError):
            PurchaseOrderAdapter._currency_and_rate(row, "alpha", date(2026, 5, 10))


def test_cash_forecast_adapter_rejects_non_finite_amount(non_finite_scenario):
    """Cash forecast rows and documents reject non-finite amounts."""
    from cacao_accounting.imports.adapters.cash_forecast_entry import CashForecastEntryAdapter

    app = non_finite_scenario
    adapter = CashForecastEntryAdapter()
    row = {
        "forecast_id": "FC-1",
        "type": "Income",
        "concept": "Venta",
        "currency": "NIO",
        "amount": "NaN",
        "estimated_date": "2026-05-10",
    }
    with app.app_context():
        errors = adapter.validate_row(row)
        with pytest.raises(ValueError):
            adapter.build_document([{**row, "amount": "Infinity"}], {"company_id": "alpha"})

    assert any("finito" in error for error in errors)
