# SPDX-License-Identifier: Apache-2.0
"""#1820: cancelaci?n/cierre tard?o no debe consumir reservas ajenas."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.database import SalesOrder, SalesOrderItem, StockBin, database
from cacao_accounting.ventas.services import (
    _release_reservation_for_closed_sales_order,
    _release_reservation_for_sales_order,
)


def _seed_two_orders(app):
    with app.app_context():
        db = database
        # reuse existing company/item/warehouse seeded by entorno fixtures where possible
        company = "cacao"
        # minimal stock bin
        bin_row = db.session.execute(
            db.select(StockBin).filter_by(company=company, item_code="ITM1820", warehouse="WH1820")
        ).scalar_one_or_none()
        if bin_row is None:
            from cacao_accounting.database import Item, UOM, Warehouse

            if db.session.execute(db.select(UOM).filter_by(code="U1820")).scalar_one_or_none() is None:
                db.session.add(UOM(code="U1820", name="U1820"))
            if db.session.get(Item, "ITM1820") is None:
                db.session.add(
                    Item(code="ITM1820", name="Item 1820", item_type="goods", is_stock_item=True, default_uom="U1820")
                )
            if db.session.execute(db.select(Warehouse).filter_by(code="WH1820")).scalar_one_or_none() is None:
                db.session.add(Warehouse(code="WH1820", name="WH1820", company=company))
            db.session.flush()
            bin_row = StockBin(
                company=company, item_code="ITM1820", warehouse="WH1820", actual_qty=Decimal("20"), reserved_qty=Decimal("15")
            )
            db.session.add(bin_row)
        bin_row.reserved_qty = Decimal("15")
        so_a = SalesOrder(
            company=company,
            customer_id=None,
            status="open",
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=1,
        )
        so_b = SalesOrder(
            company=company,
            customer_id=None,
            status="open",
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=1,
        )
        db.session.add_all([so_a, so_b])
        db.session.flush()
        db.session.add_all(
            [
                SalesOrderItem(
                    sales_order_id=so_a.id,
                    item_code="ITM1820",
                    warehouse="WH1820",
                    qty=Decimal("10"),
                    qty_in_base_uom=Decimal("10"),
                ),
                SalesOrderItem(
                    sales_order_id=so_b.id,
                    item_code="ITM1820",
                    warehouse="WH1820",
                    qty=Decimal("5"),
                    qty_in_base_uom=Decimal("5"),
                ),
            ]
        )
        db.session.commit()
        return so_a.id, so_b.id


def test_release_is_idempotent_for_closed_order(app, entorno_contable):
    del entorno_contable
    so_a, _so_b = _seed_two_orders(app)
    with app.app_context():
        so = database.session.get(SalesOrder, so_a)
        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITM1820", warehouse="WH1820")
        ).scalar_one()
        _release_reservation_for_closed_sales_order(so)
        so.status = "closed"
        database.session.commit()
        before = Decimal(str(bin_row.reserved_qty))
        _release_reservation_for_sales_order(database.session.get(SalesOrder, so_a))
        database.session.commit()
        bin_row = database.session.execute(
            database.select(StockBin).filter_by(company="cacao", item_code="ITM1820", warehouse="WH1820")
        ).scalar_one()
        assert Decimal(str(bin_row.reserved_qty)) == before
