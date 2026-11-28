# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2123: una devolución no cubre una línea de orden de venta."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    DocumentRelation,
    SalesInvoice,
    SalesOrder,
    SalesOrderItem,
    database,
)
from cacao_accounting.ventas.services import sales_order_is_ready_to_close, sales_order_line_closure_reasons

FECHA = date(2026, 5, 15)


def _relacion_orden_factura(order: SalesOrder, item: SalesOrderItem, invoice: SalesInvoice) -> DocumentRelation:
    return DocumentRelation(
        company="cacao",
        source_type="sales_order",
        source_id=order.id,
        source_item_id=item.id,
        target_type="sales_invoice",
        target_id=invoice.id,
        target_item_id=f"{invoice.id}-1",
        relation_type="fulfillment",
        qty=Decimal("1"),
        qty_in_base_uom=Decimal("1"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("10"),
        status="active",
    )


def test_devolucion_no_cierra_la_orden_y_la_factura_positiva_si(app, entorno_contable):
    """Solo una factura positiva aprobada acredita cumplimiento de la línea."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        order = SalesOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"SO-RET-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(order)
        database.session.flush()
        item = SalesOrderItem(
            sales_order_id=order.id,
            item_code="ART01",
            item_name="Articulo Comercial",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("10"),
        )
        retorno = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"RET-{suffix}",
            document_type="sales_return",
            is_return=True,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add_all([item, retorno])
        database.session.flush()
        database.session.add(_relacion_orden_factura(order, item, retorno))
        database.session.commit()
        item_id = item.id

        assert sales_order_line_closure_reasons(order) == {}
        assert sales_order_is_ready_to_close(order) is False

        positiva = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"FAC-{suffix}",
            document_type="sales_invoice",
            is_return=False,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(positiva)
        database.session.flush()
        database.session.add(_relacion_orden_factura(order, item, positiva))
        database.session.commit()

        razones = sales_order_line_closure_reasons(order)
        assert item_id in razones
        assert "Factura de Venta" in razones[item_id]
        assert sales_order_is_ready_to_close(order) is True
