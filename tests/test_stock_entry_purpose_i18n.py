# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos\u00e9 Moreno Reyes

"""#1875: StockEntry muestra etiquetas traducibles de prop\u00f3sito."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.database import StockEntry, database


def _stock_entry(purpose: str) -> StockEntry:
    entry = StockEntry(
        company="cacao",
        purpose=purpose,
        posting_date=date(2026, 5, 15),
        transaction_currency="NIO",
        base_currency="NIO",
        document_no=f"SE-{uuid4().hex[:8]}",
    )
    database.session.add(entry)
    database.session.commit()
    return entry


def test_stock_entry_list_muestra_etiqueta_no_codigo(app, authenticated_client):
    with app.app_context():
        entry = _stock_entry("material_receipt")
        entry_id = entry.id
    client = authenticated_client("admin")
    response = client.get("/inventory/stock-entry/list")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f"/inventory/stock-entry/{entry_id}" in body
    assert "material_receipt" not in body
    assert "Recepci\u00f3n de Material" in body


def test_stock_entry_detail_muestra_etiqueta_no_codigo(app, authenticated_client):
    with app.app_context():
        entry = _stock_entry("adjustment_negative")
        entry_id = entry.id
    client = authenticated_client("admin")
    response = client.get(f"/inventory/stock-entry/{entry_id}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "adjustment_negative" not in body
    assert "Ajuste Negativo" in body
