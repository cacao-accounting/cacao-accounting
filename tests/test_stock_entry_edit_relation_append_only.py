# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""A linked stock entry cannot rewrite or remove its document-flow evidence."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import get_flashed_messages

from cacao_accounting.database import DocumentRelation, StockEntry, StockEntryItem, database
from cacao_accounting.inventario import services as inventory_services


@pytest.mark.parametrize("relation_status", ["active", "closed"])
@pytest.mark.parametrize("edit", ["change_quantity", "remove_line"])
def test_linked_stock_entry_rejects_edit_without_mutating_evidence(app, entorno_contable, monkeypatch, relation_status, edit):
    """Editing a linked movement rolls back instead of deleting relation history."""
    suffix = uuid4().hex[:10]
    item_code = "ART01"
    uom = "UND"
    with app.app_context():
        entry = StockEntry(
            company="cacao",
            purpose="material_receipt",
            posting_date=date(2026, 5, 15),
            transaction_currency="NIO",
            base_currency="NIO",
            remarks="Original header",
        )
        database.session.add(entry)
        database.session.flush()
        line = StockEntryItem(
            stock_entry_id=entry.id,
            item_code=item_code,
            source_warehouse=None,
            target_warehouse=None,
            qty=Decimal("2"),
            uom=uom,
            qty_in_base_uom=Decimal("2"),
            basic_rate=Decimal("10"),
            amount=Decimal("20"),
        )
        database.session.add(line)
        database.session.flush()
        relation = DocumentRelation(
            source_type="purchase_receipt",
            source_id=f"receipt-{suffix}",
            source_item_id=f"receipt-line-{suffix}",
            target_type="stock_entry",
            target_id=entry.id,
            target_item_id=line.id,
            company="cacao",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom=uom,
            rate=Decimal("10"),
            amount=Decimal("20"),
            relation_type="purchase_receipt_to_stock_entry",
            status=relation_status,
        )
        database.session.add(relation)
        database.session.commit()
        entry_id, line_id, relation_id = entry.id, line.id, relation.id

    monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_dimensions", lambda *_args: None)
    line_fields = (
        {
            "item_code_0": item_code,
            "qty_0": "3",
            "uom_0": uom,
            "rate_0": "10",
            "amount_0": "30",
        }
        if edit == "change_quantity"
        else {}
    )
    form_data = {
        "purpose": "material_receipt",
        "company": "cacao",
        "posting_date": "2026-05-16",
        "transaction_currency": "NIO",
        "remarks": "Edited header",
        **line_fields,
    }

    with app.test_request_context("/inventory/stock-entry/test/edit", method="POST", data=form_data):
        response = inventory_services._handle_stock_entry_edit_post(database.session.get(StockEntry, entry_id))
        assert response is None
        assert any("inmutables" in message for message in get_flashed_messages())

    with app.app_context():
        saved_entry = database.session.get(StockEntry, entry_id)
        saved_line = database.session.get(StockEntryItem, line_id)
        saved_relation = database.session.get(DocumentRelation, relation_id)
        assert saved_entry is not None and saved_entry.remarks == "Original header"
        assert saved_entry.posting_date == date(2026, 5, 15)
        assert saved_line is not None
        assert (saved_line.item_code, saved_line.qty, saved_line.uom, saved_line.amount) == (
            item_code,
            Decimal("2.000000000"),
            uom,
            Decimal("20.0000"),
        )
        assert saved_relation is not None
        assert (saved_relation.status, saved_relation.qty, saved_relation.target_item_id) == (
            relation_status,
            Decimal("2.000000000"),
            line_id,
        )
