# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2353: posting completo concurrente del mismo serial en PostgreSQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from test_purchase_receipt_return_cancel_postgresql import _drop, _isolated_url, _seed

from cacao_accounting import create_app
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting_service import post_stock_entry
from cacao_accounting.database import (
    GLEntry,
    Item,
    Modules,
    SerialNumber,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.internal_control_service import audit_actor

pytestmark = pytest.mark.database


def test_posting_concurrente_del_mismo_serial():
    """Solo una salida completa deja Stock Ledger y GL; la otra revierte."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2353-posting",
                "WTF_CSRF_ENABLED": False,
                "MODO_ESCRITORIO": False,
            }
        )
        _seed(app)
        suffix = uuid4().hex[:6].upper()
        serial_no = f"SER-{suffix}"
        with app.app_context():
            admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            admin_id = str(admin.id)
            item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
            item.allow_negative_stock = True
            item.has_serial_no = True
            for module in ("inventory", "accounting"):
                if database.session.execute(database.select(Modules).filter_by(module=module)).scalar_one_or_none() is None:
                    database.session.add(Modules(module=module, default=False, enabled=True))
            database.session.add(UserCompanyAccess(user_id=admin_id, company_code="cacao"))
            database.session.add(
                SerialNumber(item_code="ART01", serial_no=serial_no, serial_status="available", warehouse="BOD01")
            )
            database.session.add(
                StockBin(
                    company="cacao",
                    item_code="ART01",
                    warehouse="BOD01",
                    actual_qty=Decimal("10"),
                    reserved_qty=Decimal("0"),
                )
            )
            entries = []
            for index in (1, 2):
                entry = StockEntry(
                    purpose="material_issue",
                    company="cacao",
                    posting_date=date(2026, 5, 12),
                    from_warehouse="BOD01",
                    document_no=f"SE-{suffix}-{index}",
                    transaction_currency="NIO",
                    base_currency="NIO",
                    total_amount=Decimal("10"),
                    docstatus=1,
                )
                database.session.add(entry)
                database.session.flush()
                database.session.add(
                    StockEntryItem(
                        stock_entry_id=entry.id,
                        item_code="ART01",
                        source_warehouse="BOD01",
                        qty=Decimal("1"),
                        uom="UND",
                        qty_in_base_uom=Decimal("1"),
                        basic_rate=Decimal("10"),
                        amount=Decimal("10"),
                        serial_no=serial_no,
                    )
                )
                entries.append(entry.id)
            database.session.commit()
            database.session.remove()

        barrier = Barrier(2, timeout=30)

        def post(entry_id: str) -> str:
            with app.app_context():
                try:
                    barrier.wait(timeout=10)
                    entry = database.session.get(StockEntry, entry_id)
                    with audit_actor(admin_id, "Admin"), approved_execution(entry, admin_id):
                        post_stock_entry(entry, ledger_code="FISCAL")
                    database.session.commit()
                    return "posted"
                except Exception:
                    database.session.rollback()
                    return "rejected"
                finally:
                    database.session.remove()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(post, entries))
        assert sorted(results) == ["posted", "rejected"], results

        with app.app_context():
            serial = database.session.execute(database.select(SerialNumber).filter_by(serial_no=serial_no)).scalar_one()
            assert serial.serial_status == "delivered"
            stock_rows = (
                database.session.execute(database.select(StockLedgerEntry).where(StockLedgerEntry.voucher_id.in_(entries)))
                .scalars()
                .all()
            )
            gl_rows = (
                database.session.execute(
                    database.select(GLEntry).where(GLEntry.voucher_id.in_(entries), GLEntry.is_cancelled.is_(False))
                )
                .scalars()
                .all()
            )
            assert len({row.voucher_id for row in stock_rows}) == 1
            assert len({row.voucher_id for row in gl_rows}) == 1
            # El perdedor no puede reintentar después del rollback.
            rejected_id = entries[results.index("rejected")]
            entry = database.session.get(StockEntry, rejected_id)
            with audit_actor(admin_id, "Admin"), approved_execution(entry, admin_id):
                try:
                    post_stock_entry(entry, ledger_code="FISCAL")
                    database.session.commit()
                except Exception:
                    database.session.rollback()
            stock_after = (
                database.session.execute(database.select(StockLedgerEntry).where(StockLedgerEntry.voucher_id.in_(entries)))
                .scalars()
                .all()
            )
            gl_after = (
                database.session.execute(
                    database.select(GLEntry).where(GLEntry.voucher_id.in_(entries), GLEntry.is_cancelled.is_(False))
                )
                .scalars()
                .all()
            )
            assert len({row.voucher_id for row in stock_after}) == 1
            assert len({row.voucher_id for row in gl_after}) == 1
            database.session.remove()
    finally:
        _drop(url, name)
