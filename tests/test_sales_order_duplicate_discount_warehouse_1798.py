# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1798: la orden duplicada conserva descuento y bodega por línea."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect, select

from cacao_accounting.database import Party, SalesOrder, SalesOrderItem, User, database
from cacao_accounting.ventas.services import _source_line_discount

FECHA = date(2026, 5, 15)


def _cliente(app):
    """Autentica al administrador de la aplicación aislada."""
    with app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        admin_id = str(inspect(admin).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def test_orden_duplicada_conserva_descuento_y_bodega(entorno_contable_aislado):
    """El duplicado mantiene el neto comercial y la asignación de fulfillment."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:8]
    with app.app_context():
        customer = database.session.execute(select(Party).filter_by(code="CLI001")).scalar_one()
        order = SalesOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"SO-DUP-1798-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=f"DUP-1798-{suffix}",
        )
        database.session.add(order)
        database.session.flush()
        database.session.add(
            SalesOrderItem(
                sales_order_id=order.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
                amount=Decimal("90"),
                discount_percentage=Decimal("10"),
                discount_amount=Decimal("10"),
                warehouse="BOD01",
            )
        )
        database.session.commit()
        order_id = order.id

    response = _cliente(app).post(f"/sales/sales-order/{order_id}/duplicate")
    assert response.status_code == 302

    with app.app_context():
        duplicate = database.session.execute(
            select(SalesOrder).filter_by(remarks=f"DUP-1798-{suffix}", docstatus=0)
        ).scalar_one()
        line = database.session.execute(select(SalesOrderItem).filter_by(sales_order_id=duplicate.id)).scalar_one()
        assert line.amount == Decimal("90")
        assert line.discount_percentage == Decimal("10")
        assert line.discount_amount == Decimal("10")
        assert line.warehouse == "BOD01"

        with app.test_request_context(
            "/sales/sales-invoice/new",
            method="POST",
            data={
                "source_type_0": "sales_order",
                "source_id_0": duplicate.id,
                "source_item_id_0": line.id,
            },
        ):
            percentage, amount, net = _source_line_discount(0, Decimal("100"))
        assert percentage == Decimal("10")
        assert amount == Decimal("10")
        assert net == Decimal("90")
