# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1599: el dashboard no cuenta órdenes completadas como abiertas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.api.dashboard import get_purchases_data
from cacao_accounting.database import (
    DocumentRelation,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    database,
)
from cacao_accounting.document_flow.status import calculate_document_status


def _crear_orden(entorno, cantidad: str, *, recibida: bool) -> str:
    """Crea una orden aprobada y, opcionalmente, su recepción completa."""
    with entorno.app.app_context():
        orden = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 15), docstatus=1, status="open")
        database.session.add(orden)
        database.session.flush()
        linea = PurchaseOrderItem(
            purchase_order_id=orden.id,
            item_code="ART01",
            item_name="Articulo Comercial",
            qty=Decimal(cantidad),
            uom="UND",
            qty_in_base_uom=Decimal(cantidad),
            rate=Decimal("10"),
            amount=Decimal(cantidad) * Decimal("10"),
        )
        database.session.add(linea)
        database.session.flush()
        if recibida:
            recepcion = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 16), docstatus=1)
            database.session.add(recepcion)
            database.session.flush()
            linea_recepcion = PurchaseReceiptItem(
                purchase_receipt_id=recepcion.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal(cantidad),
                uom="UND",
                qty_in_base_uom=Decimal(cantidad),
                rate=Decimal("10"),
                amount=Decimal(cantidad) * Decimal("10"),
            )
            database.session.add(linea_recepcion)
            database.session.flush()
            database.session.add(
                DocumentRelation(
                    company="cacao",
                    source_type="purchase_order",
                    source_id=orden.id,
                    source_item_id=linea.id,
                    target_type="purchase_receipt",
                    target_id=recepcion.id,
                    target_item_id=linea_recepcion.id,
                    qty=Decimal(cantidad),
                    qty_in_base_uom=Decimal(cantidad),
                    uom="UND",
                    rate=Decimal("10"),
                    amount=Decimal(cantidad) * Decimal("10"),
                    relation_type="receives",
                    status="active",
                )
            )
        database.session.commit()
        return orden.id


def test_orden_con_flujo_completado_no_cuenta_como_abierta(entorno_contable_aislado):
    """Una orden recibida por completo deja de sumar en el KPI de abiertas."""
    entorno = entorno_contable_aislado
    completada = _crear_orden(entorno, "10", recibida=True)
    _crear_orden(entorno, "5", recibida=False)

    with entorno.app.app_context():
        orden = database.session.get(PurchaseOrder, completada)
        assert calculate_document_status("purchase_order", orden).code == "completed"

        payload = get_purchases_data("cacao", "NIO", None, None)

    assert payload["kpis"]["open_orders"]["value"] == 1
