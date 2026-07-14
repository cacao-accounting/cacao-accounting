# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO", enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                Modules(module="purchasing", default=True, enabled=True),
                Modules(module="sales", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


def test_stock_entry_draft_audit_capture(app_ctx):
    from cacao_accounting.database import StockEntry, StockEntryItem, database
    from cacao_accounting.inventario import _capture_stock_entry_state
    from cacao_accounting.audit_trail_service import _format_timeline_value

    # 1. Create a draft StockEntry with items
    se = StockEntry(
        id="SE-001",
        purpose="material_receipt",
        company="cacao",
        posting_date=date(2026, 7, 10),
        remarks="Draft entry",
    )
    database.session.add(se)
    database.session.commit()

    sei = StockEntryItem(
        stock_entry_id="SE-001",
        item_code="ITEM-HIGH-COST",
        qty=Decimal("100"),
        uom="Pza",
        basic_rate=Decimal("50.00"),
        amount=Decimal("5000.00"),
    )
    database.session.add(sei)
    database.session.commit()

    # 2. Capture stock entry state before update
    before_state = _capture_stock_entry_state(se)
    assert "items" in before_state
    assert len(before_state["items"]) == 1
    assert before_state["items"][0]["item_code"] == "ITEM-HIGH-COST"
    assert Decimal(str(before_state["items"][0]["qty"])) == Decimal("100")

    # 3. Simulate change in items (qty changes from 100 to 80)
    after_state = {
        "purpose": "material_receipt",
        "company": "cacao",
        "posting_date": "2026-07-10",
        "remarks": "Draft entry",
        "items": [
            {
                "item_code": "ITEM-HIGH-COST",
                "qty": Decimal("80"),
                "uom": "Pza",
                "basic_rate": Decimal("50.00"),
                "amount": Decimal("4000.00"),
            }
        ],
    }

    # 4. Format values and check difference
    before_formatted = _format_timeline_value(before_state["items"])
    after_formatted = _format_timeline_value(after_state["items"])

    assert "100" in before_formatted
    assert "ITEM-HIGH-COST" in before_formatted
    assert "80" in after_formatted
    assert "ITEM-HIGH-COST" in after_formatted


def test_purchase_document_draft_audit_capture(app_ctx):
    from cacao_accounting.database import PurchaseOrder, PurchaseOrderItem, database
    from cacao_accounting.compras import _capture_purchase_state
    from cacao_accounting.audit_trail_service import _format_timeline_value

    po = PurchaseOrder(
        id="PO-001",
        company="cacao",
        posting_date=date(2026, 7, 10),
        remarks="Draft purchase order",
    )
    database.session.add(po)
    database.session.commit()

    poi = PurchaseOrderItem(
        purchase_order_id="PO-001",
        item_code="ITEM-PO",
        qty=Decimal("10"),
        uom="Box",
        rate=Decimal("100.00"),
        amount=Decimal("1000.00"),
    )
    database.session.add(poi)
    database.session.commit()

    before_state = _capture_purchase_state(po)
    assert "items" in before_state
    assert len(before_state["items"]) == 1
    assert before_state["items"][0]["item_code"] == "ITEM-PO"
    assert Decimal(str(before_state["items"][0]["qty"])) == Decimal("10")

    formatted = _format_timeline_value(before_state["items"])
    assert "10 Box de ITEM-PO a 100" in formatted


def test_sales_document_draft_audit_capture(app_ctx):
    from cacao_accounting.database import SalesOrder, SalesOrderItem, database
    from cacao_accounting.ventas import _capture_sales_state
    from cacao_accounting.audit_trail_service import _format_timeline_value

    so = SalesOrder(
        id="SO-001",
        company="cacao",
        posting_date=date(2026, 7, 10),
        remarks="Draft sales order",
    )
    database.session.add(so)
    database.session.commit()

    soi = SalesOrderItem(
        sales_order_id="SO-001",
        item_code="ITEM-SO",
        qty=Decimal("5"),
        uom="Unit",
        rate=Decimal("20.00"),
        amount=Decimal("100.00"),
    )
    database.session.add(soi)
    database.session.commit()

    before_state = _capture_sales_state(so)
    assert "items" in before_state
    assert len(before_state["items"]) == 1
    assert before_state["items"][0]["item_code"] == "ITEM-SO"
    assert Decimal(str(before_state["items"][0]["qty"])) == Decimal("5")

    formatted = _format_timeline_value(before_state["items"])
    assert "5 Unit de ITEM-SO a 20" in formatted


def test_format_document_timeline_with_items_changes(app_ctx):
    from cacao_accounting.audit_trail_service import format_document_timeline, log_update
    from cacao_accounting.database import StockEntry, database

    se = StockEntry(
        id="SE-002",
        purpose="material_receipt",
        company="cacao",
        posting_date=date(2026, 7, 10),
    )
    database.session.add(se)
    database.session.commit()

    before_state = {
        "purpose": "material_receipt",
        "company": "cacao",
        "items": [
            {
                "item_code": "ITEM-A",
                "qty": Decimal("100"),
                "uom": "Pza",
                "basic_rate": Decimal("1.5"),
                "amount": Decimal("150"),
            }
        ],
    }

    after_state = {
        "purpose": "material_receipt",
        "company": "cacao",
        "items": [
            {"item_code": "ITEM-A", "qty": Decimal("80"), "uom": "Pza", "basic_rate": Decimal("1.5"), "amount": Decimal("120")}
        ],
    }

    log_update(se, before=before_state, after=after_state)
    database.session.commit()

    timeline = format_document_timeline("StockEntry", "SE-002")
    assert len(timeline) == 1
    changes = timeline[0]["changes"]
    assert len(changes) == 1
    assert changes[0]["field"] == "items"
    assert changes[0]["before"] == "100 Pza de ITEM-A a 1.5 (Total: 150)"
    assert changes[0]["after"] == "80 Pza de ITEM-A a 1.5 (Total: 120)"
