# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1865: la edición de entrada vinculada conserva relaciones documentales."""

from decimal import Decimal

from cacao_accounting.database import (
    DocumentRelation,
    Item,
    StockEntry,
    StockEntryItem,
    UOM,
    database,
)
from cacao_accounting.inventario.services import _handle_stock_entry_edit_post


def test_editar_entrada_vinculada_restringe_y_conserva_relaciones(app):
    """La edición de una entrada con relaciones activas se rechaza sin borrar evidencia (#1865)."""
    with app.app_context():
        database.session.add(UOM(code="UNI-1865", name="Unidad 1865"))
        database.session.flush()
        database.session.add(
            Item(
                code="ART-1865",
                name="Articulo 1865",
                item_type="goods",
                is_stock_item=False,
                default_uom="UNI-1865",
            )
        )
        database.session.flush()
        entry = StockEntry(company="cacao", purpose="material_receipt", remarks="Original")
        database.session.add(entry)
        database.session.flush()
        item = StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ART-1865",
            qty=Decimal("5"),
            uom="UNI-1865",
            qty_in_base_uom=Decimal("5"),
        )
        database.session.add(item)
        database.session.flush()
        relation = DocumentRelation(
            source_type="purchase_receipt",
            source_id="PR-1865",
            source_item_id="PRL-1865",
            target_type="stock_entry",
            target_id=entry.id,
            target_item_id=item.id,
            qty=Decimal("5"),
            relation_type="stock",
            company="cacao",
        )
        database.session.add(relation)
        database.session.commit()
        entry_id = entry.id
        relation_id = relation.id
        item_id = item.id

    with app.test_request_context("/stock-entry/test/edit", method="POST", data={"remarks": "Edicion intentada"}):
        response = _handle_stock_entry_edit_post(entry)

    assert response is None
    with app.app_context():
        persisted = database.session.get(StockEntry, entry_id)
        assert persisted is not None
        assert persisted.remarks == "Original"
        assert database.session.get(DocumentRelation, relation_id) is not None
        assert database.session.get(StockEntryItem, item_id) is not None
