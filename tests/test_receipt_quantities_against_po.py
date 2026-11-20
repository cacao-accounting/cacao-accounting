# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2098: la validación de recepciones serializa contra la OC y sus líneas."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.compras.services import _validate_receipt_quantities_against_po
from cacao_accounting.database import (
    DocumentRelation,
    Item,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    Warehouse,
    database,
)

FECHA = date(2026, 5, 15)


def _relacion(purchase_order_id: str, po_item_id: str, receipt_id: str, receipt_item_id: str, qty: Decimal) -> None:
    """Crea la relación activa de una recepción sobre una línea de OC."""
    database.session.add(
        DocumentRelation(
            source_type="purchase_order",
            source_id=purchase_order_id,
            source_item_id=po_item_id,
            target_type="purchase_receipt",
            target_id=receipt_id,
            target_item_id=receipt_item_id,
            qty=qty,
            qty_in_base_uom=qty,
            uom="UND2098",
            relation_type="receives",
            status="active",
        )
    )


def test_validacion_rechaza_recepciones_que_superan_la_ordenada(app):
    """Dos recepciones aprobadas que suman más que la línea ordenada son rechazadas (#2098)."""
    with app.app_context():
        database.session.add(UOM(code="UND2098", name="Unidad 2098"))
        database.session.flush()
        database.session.add(Warehouse(code="BOD-2098", name="Bodega 2098", company="cacao"))
        database.session.flush()
        database.session.add(
            Item(code="ART-2098", name="Articulo 2098", item_type="goods", is_stock_item=True, default_uom="UND2098")
        )
        database.session.flush()
        database.session.add(Party(code="SUP-2098", name="Proveedor 2098", is_supplier=True))
        database.session.flush()
        supplier = database.session.execute(database.select(Party).filter_by(is_supplier=True)).scalars().first()
        purchase_order = PurchaseOrder(
            company="cacao", document_no="PO-2098", posting_date=FECHA, docstatus=1, supplier_id=supplier.id
        )
        database.session.add(purchase_order)
        database.session.flush()
        po_item = PurchaseOrderItem(
            purchase_order_id=purchase_order.id,
            item_code="ART-2098",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="UND2098",
        )
        database.session.add(po_item)
        database.session.flush()
        receipt_a = PurchaseReceipt(
            company="cacao",
            document_no="PR-2098A",
            purchase_order_id=purchase_order.id,
            supplier_id=supplier.id,
            posting_date=FECHA,
            docstatus=1,
        )
        receipt_b = PurchaseReceipt(
            company="cacao",
            document_no="PR-2098B",
            purchase_order_id=purchase_order.id,
            supplier_id=supplier.id,
            posting_date=FECHA,
            docstatus=1,
        )
        database.session.add_all([receipt_a, receipt_b])
        database.session.flush()
        receipt_item_a = PurchaseReceiptItem(
            purchase_receipt_id=receipt_a.id,
            item_code="ART-2098",
            qty=Decimal("6"),
            qty_in_base_uom=Decimal("6"),
            uom="UND2098",
        )
        receipt_item_b = PurchaseReceiptItem(
            purchase_receipt_id=receipt_b.id,
            item_code="ART-2098",
            qty=Decimal("6"),
            qty_in_base_uom=Decimal("6"),
            uom="UND2098",
        )
        database.session.add_all([receipt_item_a, receipt_item_b])
        database.session.flush()
        _relacion(purchase_order.id, po_item.id, receipt_a.id, receipt_item_a.id, Decimal("6"))
        _relacion(purchase_order.id, po_item.id, receipt_b.id, receipt_item_b.id, Decimal("6"))
        database.session.commit()

        with pytest.raises(ValueError, match="Sobre-recepción"):
            _validate_receipt_quantities_against_po(receipt_b.id)
