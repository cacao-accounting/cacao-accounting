# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1865: editar la cabecera no puede borrar evidencia de un StockEntry vinculado.

El guard rechazaba cualquier edición cuando existía una ``DocumentRelation``,
incluidas las que solo cambian cabecera. La regresión exige que una edición de
cabecera con líneas y cantidades idénticas se guarde, y que cualquier cambio de
línea, cantidad o almacén se rechace sin mutar la evidencia.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import get_flashed_messages

from cacao_accounting.database import DocumentRelation, StockEntry, StockEntryItem, database
from cacao_accounting.inventario import services as inventory_services


def _seed_linked_entry(app, relation_status: str = "active") -> dict[str, str]:
    """Crea un movimiento con una línea y una relación documental activa."""
    suffix = uuid4().hex[:10]
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
            item_code="ART01",
            source_warehouse=None,
            target_warehouse=None,
            qty=Decimal("2"),
            uom="UND",
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
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("20"),
            relation_type="purchase_receipt_to_stock_entry",
            status=relation_status,
        )
        database.session.add(relation)
        database.session.commit()
        return {"entry": entry.id, "line": line.id, "relation": relation.id}


def _post_edit(app, monkeypatch, entry_id: str, form_data: dict[str, str]):
    """Ejecuta el handler de edición con las dependencias externas neutralizadas."""
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_company", lambda _value, _action: "cacao")
    monkeypatch.setattr(inventory_services, "_validate_stock_entry_dimensions", lambda *_args: None)
    with app.test_request_context("/inventory/stock-entry/test/edit", method="POST", data=form_data):
        response = inventory_services._handle_stock_entry_edit_post(database.session.get(StockEntry, entry_id))
        return response, list(get_flashed_messages())


def _header_form(**extra: str) -> dict[str, str]:
    """Formulario con las líneas persistidas sin cambios."""
    form = {
        "purpose": "material_receipt",
        "company": "cacao",
        "posting_date": "2026-05-16",
        "transaction_currency": "NIO",
        "remarks": "Edited header",
        "item_code_0": "ART01",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }
    form.update(extra)
    return form


@pytest.mark.parametrize("relation_status", ["active", "closed"])
@pytest.mark.parametrize("edit", ["change_quantity", "remove_line", "change_warehouse"])
def test_linked_stock_entry_rejects_line_edit_without_mutating_evidence(
    app, entorno_contable, monkeypatch, relation_status, edit
):
    """Cambiar líneas, cantidades o almacenes revierte todo sin perder evidencia."""
    ids = _seed_linked_entry(app, relation_status)
    form_data = _header_form()
    if edit == "change_quantity":
        form_data.update({"qty_0": "3", "amount_0": "30"})
    elif edit == "remove_line":
        form_data.pop("item_code_0")
    else:
        form_data["from_warehouse"] = "BOD01"

    response, messages = _post_edit(app, monkeypatch, ids["entry"], form_data)

    assert response is None
    assert any("inmutables" in message for message in messages)
    with app.app_context():
        saved_entry = database.session.get(StockEntry, ids["entry"])
        saved_line = database.session.get(StockEntryItem, ids["line"])
        saved_relation = database.session.get(DocumentRelation, ids["relation"])
        assert saved_entry is not None and saved_entry.remarks == "Original header"
        assert saved_entry.posting_date == date(2026, 5, 15)
        assert saved_entry.from_warehouse != "BOD01"
        assert saved_line is not None
        assert (saved_line.item_code, saved_line.qty, saved_line.uom, saved_line.amount) == (
            "ART01",
            Decimal("2.000000000"),
            "UND",
            Decimal("20.0000"),
        )
        assert saved_relation is not None
        assert (saved_relation.status, saved_relation.qty, saved_relation.target_item_id) == (
            relation_status,
            Decimal("2.000000000"),
            ids["line"],
        )


def test_linked_stock_entry_allows_header_only_edit(app, entorno_contable, monkeypatch):
    """Cambiar solo campos de cabecera conserva la relación y no borra líneas."""
    ids = _seed_linked_entry(app, "active")

    response, messages = _post_edit(app, monkeypatch, ids["entry"], _header_form())

    assert response is not None
    assert not any("inmutables" in message for message in messages)
    with app.app_context():
        saved_entry = database.session.get(StockEntry, ids["entry"])
        saved_line = database.session.get(StockEntryItem, ids["line"])
        saved_relation = database.session.get(DocumentRelation, ids["relation"])
        assert saved_entry is not None
        assert (saved_entry.remarks, saved_entry.posting_date) == ("Edited header", date(2026, 5, 16))
        assert saved_line is not None and saved_line.qty == Decimal("2.000000000")
        assert saved_relation is not None and saved_relation.qty == Decimal("2.000000000")
