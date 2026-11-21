# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1864: rechaza decimales inválidos en las líneas dinámicas de inventario."""

from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import NamingSeries, StockEntry, database
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company


@pytest.mark.parametrize(
    ("purpose", "field", "value"),
    [
        ("material_receipt", "qty_0", "abc"),
        ("material_receipt", "rate_0", "NaN"),
        ("stock_reconciliation", "counted_qty_0", "Infinity"),
        ("stock_reconciliation", "target_valuation_rate_0", "NaN"),
        ("stock_reconciliation", "target_stock_value_0", "abc"),
        ("adjustment_positive", "amount_0", "Infinity"),
    ],
)
def test_stock_entry_decimal_fields_return_validation_and_rollback(
    app, entorno_contable, authenticated_client, purpose, field, value
):
    """Cada parser dinámico controlado revierte también la cabecera ya insertada."""
    marker = f"DECIMAL-STOCK-{uuid4().hex[:8]}"
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["stock_entry"])
        database.session.commit()
        series_id = database.session.execute(
            database.select(NamingSeries.id).filter_by(entity_type="stock_entry", company="cacao")
        ).scalar_one()

    path = {
        "material_receipt": "/inventory/stock-entry/material-receipt/new",
        "stock_reconciliation": "/inventory/stock-entry/reconciliation/new",
        "adjustment_positive": "/inventory/stock-entry/adjustment-positive/new",
    }[purpose]
    form_data = {
        "purpose": purpose,
        "company": "cacao",
        "naming_series": series_id,
        "posting_date": "2026-05-15",
        "transaction_currency": "NIO",
        "to_warehouse": "BOD01",
        "warehouse_0": "BOD01",
        "item_code_0": "ART01",
        "qty_0": "0" if field == "amount_0" else "1",
        "rate_0": "1",
        "amount_0": "0",
        "counted_qty_0": "1",
        "target_valuation_rate_0": "1",
        "target_stock_value_0": "1",
        "uom_0": "UND",
        "remarks": marker,
    }
    form_data[field] = value
    if purpose == "stock_reconciliation":
        form_data["counted_qty_0"] = form_data.get("counted_qty_0", "1")

    response = authenticated_client().post(path, data=form_data)

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(StockEntry).filter_by(remarks=marker)).scalar_one_or_none() is None
