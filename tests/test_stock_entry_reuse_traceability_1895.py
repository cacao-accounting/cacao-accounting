# SPDX-License-Identifier: Apache-2.0

"""#1895: reuso StockEntry preserva trazabilidad batch/serial/expiry en payload."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Batch,
    Currency,
    Entity,
    Item,
    StockEntry,
    StockEntryItem,
    UOM,
    database,
)
from cacao_accounting.document_flow.service import get_source_items


@pytest.fixture
def traceability_app():
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
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.engine.dispose()


def test_get_source_items_includes_batch_serial_expiry(traceability_app):
    app = traceability_app
    suffix = uuid4().hex[:6]
    with app.app_context():
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="EA", name="Each", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(Item(code=f"IT-{suffix}", name="Item", item_type="goods", is_stock_item=True, default_uom="EA"))
        database.session.flush()
        batch = Batch(batch_no=f"B-{suffix}", item_code=f"IT-{suffix}", is_active=True)
        database.session.add(batch)
        database.session.flush()
        entry = StockEntry(
            company="alpha",
            document_no=f"SE-{suffix}",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            purpose="material_receipt",
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=f"IT-{suffix}",
                qty=Decimal("5"),
                uom="EA",
                qty_in_base_uom=Decimal("5"),
                batch_id=batch.id,
                serial_no="SN-001",
                expiry_date=date(2027, 1, 31),
            )
        )
        database.session.commit()

        items = get_source_items("stock_entry", entry.id, "stock_entry")
        assert len(items) == 1
        row = items[0]
        assert row["batch_id"] == batch.id
        assert row["serial_no"] == "SN-001"
        assert row["expiry_date"] == "2027-01-31"
