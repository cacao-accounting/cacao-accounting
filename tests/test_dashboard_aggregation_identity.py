# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1619/#1620: los KPI del dashboard respetan la identidad del tercero y el ítem."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.api.dashboard import get_inventory_data, _top_customers
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Party,
    SalesInvoice,
    StockBin,
    UOM,
    Warehouse,
    database,
)


@pytest.fixture
def dashboard_aggregation_app():
    """Create an isolated company with two same-name customers and multi-warehouse stock."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:8]
    company = f"d{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code=company,
                    name="Compañía Dashboard",
                    company_name=f"Compañía Dashboard {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()

        first_customer = Party(code=f"C1-{suffix}", name="Acme SA", is_customer=True)
        second_customer = Party(code=f"C2-{suffix}", name="Acme SA", is_customer=True)
        database.session.add_all([first_customer, second_customer])
        database.session.flush()
        first_customer_id = first_customer.id
        second_customer_id = second_customer.id

        database.session.add_all(
            [
                SalesInvoice(
                    company=company,
                    posting_date=date(2026, 5, 15),
                    document_no=f"V1-{suffix}",
                    docstatus=1,
                    customer_id=first_customer.id,
                    customer_name=first_customer.name,
                    transaction_currency="NIO",
                    base_currency="NIO",
                    exchange_rate=Decimal("1"),
                    grand_total=Decimal("100"),
                    total=Decimal("100"),
                    outstanding_amount=Decimal("100"),
                ),
                SalesInvoice(
                    company=company,
                    posting_date=date(2026, 5, 16),
                    document_no=f"V2-{suffix}",
                    docstatus=1,
                    customer_id=second_customer.id,
                    customer_name=second_customer.name,
                    transaction_currency="NIO",
                    base_currency="NIO",
                    exchange_rate=Decimal("1"),
                    grand_total=Decimal("50"),
                    total=Decimal("50"),
                    outstanding_amount=Decimal("50"),
                ),
            ]
        )

        first_item = Item(
            code=f"ITEM-A-{suffix}",
            name="Artículo con dos bodegas",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
        )
        second_item = Item(
            code=f"ITEM-B-{suffix}",
            name="Artículo sin existencia",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
        )
        first_warehouse = Warehouse(code=f"W1-{suffix}", name="Bodega Norte", company=company)
        second_warehouse = Warehouse(code=f"W2-{suffix}", name="Bodega Sur", company=company)
        database.session.add_all([first_item, second_item, first_warehouse, second_warehouse])
        database.session.flush()

        database.session.add_all(
            [
                StockBin(
                    company=company,
                    item_code=first_item.code,
                    warehouse=first_warehouse.code,
                    actual_qty=Decimal("3"),
                    stock_value=Decimal("30"),
                ),
                StockBin(
                    company=company,
                    item_code=first_item.code,
                    warehouse=second_warehouse.code,
                    actual_qty=Decimal("2"),
                    stock_value=Decimal("20"),
                ),
                StockBin(
                    company=company,
                    item_code=second_item.code,
                    warehouse=first_warehouse.code,
                    actual_qty=Decimal("0"),
                    stock_value=Decimal("0"),
                ),
            ]
        )
        database.session.commit()

    yield app, company, first_customer_id, second_customer_id

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_top_customers_keeps_same_name_parties_separate(dashboard_aggregation_app):
    """Two customers with the same visible name remain distinct aggregation rows."""
    app, company, first_customer_id, second_customer_id = dashboard_aggregation_app

    with app.app_context():
        rows = _top_customers(company, None, None, "NIO")

    assert len(rows) == 2
    assert {row["customer_id"] for row in rows} == {first_customer_id, second_customer_id}
    assert {Decimal(row["total"]) for row in rows} == {Decimal("100"), Decimal("50")}
    assert all(row["name"] == "Acme SA" for row in rows)


def test_inventory_stocked_items_counts_distinct_item_codes(dashboard_aggregation_app):
    """An item stocked in two warehouses counts once in the items-with-stock KPI."""
    app, company, _first_customer_id, _second_customer_id = dashboard_aggregation_app

    with app.app_context():
        payload = get_inventory_data(company, "NIO", None, None)

    assert payload["kpis"]["stocked_items"]["value"] == 1
    assert len(payload["tables"]["lowest_stock_items"]) == 3
