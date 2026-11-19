# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2122: la exposición descuenta facturas enlazadas solo por línea."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import DocumentRelation, Party, SalesInvoice, SalesOrder, database
from cacao_accounting.ventas.services import _approved_customer_order_exposure

FECHA = date(2026, 5, 15)


def _documentos(app) -> tuple[str, str, str]:
    """Crea una orden y una factura del mismo cliente con importes conocidos."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(
            code=f"EXP-{suffix}",
            name=f"Cliente exposición {suffix}",
            is_customer=True,
            is_active=True,
        )
        database.session.add(cliente)
        database.session.flush()
        order = SalesOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"SO-EXP-{suffix}",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("300"),
            base_total=Decimal("300"),
            status="open",
        )
        invoice = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"SI-EXP-{suffix}",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            document_type="sales_invoice",
            is_return=False,
            grand_total=Decimal("100"),
            base_total=Decimal("100"),
        )
        database.session.add_all([order, invoice])
        database.session.commit()
        return str(cliente.id), str(order.id), str(invoice.id)


def _relacion(app, order_id: str, invoice_id: str, amount: str) -> None:
    with app.app_context():
        database.session.add(
            DocumentRelation(
                company="cacao",
                source_type="sales_order",
                source_id=order_id,
                source_item_id=f"{order_id}-item",
                target_type="sales_invoice",
                target_id=invoice_id,
                target_item_id=f"{invoice_id}-item",
                relation_type="fulfillment",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal(amount),
                amount=Decimal(amount),
                status="active",
            )
        )
        database.session.commit()


def test_factura_solo_por_relacion_de_linea_descuenta_la_exposicion(app, entorno_contable):
    """Sin vínculo de cabecera, la relación por línea evita duplicar la exposición."""
    cliente_id, order_id, invoice_id = _documentos(app)
    with app.app_context():
        assert _approved_customer_order_exposure("cacao", cliente_id) == Decimal("300")

    _relacion(app, order_id, invoice_id, "100")

    with app.app_context():
        assert _approved_customer_order_exposure("cacao", cliente_id) == Decimal("200")


def test_la_relacion_parcial_descuenta_solo_su_importe(app, entorno_contable):
    """El importe atribuible es el de la relación, no el total de la factura."""
    cliente_id, order_id, invoice_id = _documentos(app)
    _relacion(app, order_id, invoice_id, "40")

    with app.app_context():
        assert _approved_customer_order_exposure("cacao", cliente_id) == Decimal("260")
