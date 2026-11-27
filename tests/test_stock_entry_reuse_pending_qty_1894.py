# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""#1894: reuso stock_entry->stock_entry precarga solo cantidad pendiente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Item,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    StockEntry,
    StockEntryItem,
    UOM,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def stock_entry_reuse_scenario():
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
    suffix = uuid4().hex[:6]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Modules(module="inventory", default=False, enabled=True),
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
        database.session.add_all(
            [
                Item(
                    code=f"ITEM-{suffix}",
                    name="Articulo",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="EA",
                ),
                User(
                    id=f"inv-{suffix}",
                    user=f"inv-{suffix}",
                    name="Inventario",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        inv_mod = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        role = Roles(name=f"inv-{suffix}", note="inv")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=inv_mod, access=True, view=True),
                RolesUser(user_id=f"inv-{suffix}", role_id=role.id, active=True),
                UserCompanyAccess(user_id=f"inv-{suffix}", company_code="alpha"),
            ]
        )

        source = StockEntry(
            company="alpha",
            document_no=f"SE-SRC-{suffix}",
            posting_date=date(2026, 5, 10),
            docstatus=1,
            purpose="Material Receipt",
        )
        database.session.add(source)
        database.session.flush()
        source_item = StockEntryItem(
            stock_entry_id=source.id,
            item_code=f"ITEM-{suffix}",
            qty=Decimal("10"),
            uom="EA",
            qty_in_base_uom=Decimal("10"),
        )
        database.session.add(source_item)
        database.session.flush()

        target = StockEntry(
            company="alpha",
            document_no=f"SE-TGT-{suffix}",
            posting_date=date(2026, 5, 11),
            docstatus=1,
            purpose="Material Receipt",
        )
        database.session.add(target)
        database.session.flush()
        target_item = StockEntryItem(
            stock_entry_id=target.id,
            item_code=f"ITEM-{suffix}",
            qty=Decimal("4"),
            uom="EA",
            qty_in_base_uom=Decimal("4"),
        )
        database.session.add(target_item)
        database.session.flush()

        database.session.add(
            DocumentRelation(
                source_type="stock_entry",
                source_id=source.id,
                source_item_id=source_item.id,
                target_type="stock_entry",
                target_id=target.id,
                target_item_id=target_item.id,
                relation_type="reuse",
                qty=Decimal("4"),
                qty_in_base_uom=Decimal("4"),
                company="alpha",
            )
        )
        database.session.commit()
        ids = {"source": source.id, "user": f"inv-{suffix}"}
    yield app, ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_stock_entry_reuse_api_returns_pending_qty(stock_entry_reuse_scenario):
    app, ids = stock_entry_reuse_scenario
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = ids["user"]
        session["_fresh"] = True

    resp = client.get(f"/api/inventory/stock-entry/{ids['source']}/items")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert Decimal(str(item["qty"])) == Decimal("6")
    assert Decimal(str(item["pending_qty"])) == Decimal("6")
    assert Decimal(str(item["source_qty"])) == Decimal("10")
    assert Decimal(str(item["consumed_qty"])) == Decimal("4")
