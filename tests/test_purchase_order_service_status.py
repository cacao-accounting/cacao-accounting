# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1592: una orden de servicios no exige recepción física."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.database import (
    DocumentRelation,
    Item,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    database,
)
from cacao_accounting.document_flow.status import calculate_document_status


@pytest.fixture
def servicio(entorno_contable_aislado):
    """Agrega un artículo de servicio al escenario contable aislado."""
    with entorno_contable_aislado.app.app_context():
        database.session.add(
            Item(
                code="SRV-1592",
                name="Servicio de consultoría",
                item_type="service",
                is_stock_item=False,
                is_purchase_item=True,
                default_uom="UND",
            )
        )
        database.session.commit()
    return entorno_contable_aislado


def _crear_orden(entorno, item_code: str, cantidad: str) -> str:
    with entorno.app.app_context():
        orden = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 15), docstatus=1, status="open")
        database.session.add(orden)
        database.session.flush()
        database.session.add(
            PurchaseOrderItem(
                purchase_order_id=orden.id,
                item_code=item_code,
                item_name=item_code,
                qty=Decimal(cantidad),
                uom="UND",
                qty_in_base_uom=Decimal(cantidad),
                rate=Decimal("100"),
                amount=Decimal(cantidad) * Decimal("100"),
            )
        )
        database.session.commit()
        return orden.id


def _facturar_orden(entorno, orden_id: str, item_code: str, cantidad: str) -> None:
    with entorno.app.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        linea = database.session.execute(database.select(PurchaseOrderItem).filter_by(purchase_order_id=orden_id)).scalar_one()
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 16),
            docstatus=1,
            grand_total=Decimal(cantidad) * Decimal("100"),
            base_grand_total=Decimal(cantidad) * Decimal("100"),
        )
        database.session.add(factura)
        database.session.flush()
        linea_factura = PurchaseInvoiceItem(
            purchase_invoice_id=factura.id,
            item_code=item_code,
            item_name=item_code,
            qty=Decimal(cantidad),
            uom="UND",
            qty_in_base_uom=Decimal(cantidad),
            rate=Decimal("100"),
            amount=Decimal(cantidad) * Decimal("100"),
        )
        database.session.add(linea_factura)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                company="cacao",
                source_type="purchase_order",
                source_id=orden.id,
                source_item_id=linea.id,
                target_type="purchase_invoice",
                target_id=factura.id,
                target_item_id=linea_factura.id,
                qty=Decimal(cantidad),
                qty_in_base_uom=Decimal(cantidad),
                uom="UND",
                rate=Decimal("100"),
                amount=Decimal(cantidad) * Decimal("100"),
                relation_type="billing",
                status="active",
            )
        )
        database.session.commit()


def test_orden_de_servicio_facturada_queda_completada(servicio):
    """Sin líneas de inventario, la facturación directa cierra la orden."""
    orden_id = _crear_orden(servicio, "SRV-1592", "3")
    _facturar_orden(servicio, orden_id, "SRV-1592", "3")

    with servicio.app.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        estado = calculate_document_status("purchase_order", orden)

    assert estado.code == "completed"


def test_orden_con_inventario_sigue_pendiente_de_recepcion(servicio):
    """Una línea de inventario conserva el control de recepción física."""
    orden_id = _crear_orden(servicio, "ART01", "3")

    with servicio.app.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        estado = calculate_document_status("purchase_order", orden)

    assert estado.code == "pending_receipt"


def test_orden_de_servicio_sin_factura_no_pide_recepcion(servicio):
    """Sin líneas de inventario la orden queda abierta, no pendiente de recibir."""
    orden_id = _crear_orden(servicio, "SRV-1592", "3")

    with servicio.app.app_context():
        orden = database.session.get(PurchaseOrder, orden_id)
        estado = calculate_document_status("purchase_order", orden)

    assert estado.code == "pending_billing"
