# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos\u00e9 Moreno Reyes

"""#1870: shortcuts y edici\u00f3n de StockEntry conservan t\u00edtulo del prop\u00f3sito."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.database import StockEntry, database


def test_shortcut_material_receipt_muestra_titulo_especifico(app, authenticated_client):
    client = authenticated_client("admin")
    response = client.get("/inventory/stock-entry/material-receipt/new")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Nueva Recepci\u00f3n de Material" in body
    assert "Nueva Entrada de Almac\u00e9n - " not in body


def test_shortcut_inventory_issue_muestra_titulo_especifico(app, authenticated_client):
    client = authenticated_client("admin")
    response = client.get("/inventory/stock-entry/inventory-issue/new")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Nuevo Ajuste Negativo de Inventario" in body


def test_edicion_conciliacion_usa_titulo_editar(app, authenticated_client):
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose="stock_reconciliation",
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            document_no=f"SR-{uuid4().hex[:8]}",
            docstatus=0,
        )
        database.session.add(entry)
        database.session.commit()
        entry_id = entry.id
    client = authenticated_client("admin")
    response = client.get(f"/inventory/stock-entry/{entry_id}/edit")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Editar Conciliaci\u00f3n de Inventario" in body
    assert "Nueva Conciliaci\u00f3n de Inventario - " not in body
