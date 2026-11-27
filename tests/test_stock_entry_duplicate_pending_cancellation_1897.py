# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""#1897: no duplicar StockEntry con anulaci?n pendiente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask_login import login_user
from werkzeug.exceptions import Conflict

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalRequest,
    Currency,
    Entity,
    Item,
    Modules,
    StockEntry,
    StockEntryItem,
    UOM,
    User,
    database,
)
from cacao_accounting.inventario.routes import inventario_entrada_duplicar


@pytest.fixture
def duplicate_pending_scenario(monkeypatch):
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
        from cacao_accounting.database import AccountingPeriod, FiscalYear

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
        fy = FiscalYear(
            entity="alpha",
            name="FY2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(fy)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                fiscal_year_id=fy.id,
                entity="alpha",
                name="2026-05",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                is_closed=False,
                enabled=True,
            )
        )
        database.session.flush()
        database.session.add(
            Item(code=f"ITEM-{suffix}", name="Articulo", item_type="goods", is_stock_item=True, default_uom="EA")
        )
        admin = User(id=f"inv-{suffix}", user=f"inv-{suffix}", name="Inv", password=b"unused", active=True)
        database.session.add(admin)
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
                item_code=f"ITEM-{suffix}",
                qty=Decimal("1"),
                uom="EA",
                qty_in_base_uom=Decimal("1"),
            )
        )
        database.session.commit()

        from cacao_accounting.inventario import routes as inv_routes

        monkeypatch.setattr(inv_routes, "exige_acceso_compania", lambda *a, **k: None)
        yield app, {"entry": entry.id, "user": admin.id}

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_duplicate_blocked_when_cancel_pending(duplicate_pending_scenario):
    app, ids = duplicate_pending_scenario
    with app.app_context():
        database.session.add(
            ApprovalRequest(
                document_type="cancel_stock_entry",
                document_id=ids["entry"],
                status="Pending Cancellation",
                company_id="alpha",
                requested_by=ids["user"],
            )
        )
        database.session.commit()

    with app.test_request_context(f"/inventory/stock-entry/{ids['entry']}/duplicate", method="POST"):
        login_user(database.session.get(User, ids["user"]))
        with pytest.raises(Conflict):
            inventario_entrada_duplicar(ids["entry"])

    with app.app_context():
        count = database.session.execute(database.select(StockEntry).filter_by(company="alpha")).scalars().all()
        assert len(count) == 1


def test_duplicate_allowed_after_cancel_rejected(duplicate_pending_scenario):
    app, ids = duplicate_pending_scenario
    with app.app_context():
        database.session.add(
            ApprovalRequest(
                document_type="cancel_stock_entry",
                document_id=ids["entry"],
                status="Rejected",
                company_id="alpha",
                requested_by=ids["user"],
            )
        )
        database.session.commit()

    with app.test_request_context(f"/inventory/stock-entry/{ids['entry']}/duplicate", method="POST"):
        login_user(database.session.get(User, ids["user"]))
        resp = inventario_entrada_duplicar(ids["entry"])
        assert resp.status_code in (302, 303)

    with app.app_context():
        entries = database.session.execute(database.select(StockEntry).filter_by(company="alpha")).scalars().all()
        assert len(entries) == 2
