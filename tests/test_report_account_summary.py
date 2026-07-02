# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests for Account Summary Report."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    Entity,
    GLEntry,
    Modules,
    User,
    database,
)
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    get_account_summary_report,
)


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
        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="accounting", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


def test_get_account_summary_report(app_ctx):
    # 1. Setup
    book = Book(entity="cacao", code="FISC", name="Fiscal", status="activo", is_primary=True, currency="NIO")
    period = AccountingPeriod(
        entity="cacao",
        name="2026-05",
        enabled=True,
        is_closed=False,
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
    )
    acct1 = Accounts(entity="cacao", code="1.01", name="Caja", active=True, enabled=True, classification="Activo")
    acct2 = Accounts(entity="cacao", code="4.01", name="Ingresos", active=True, enabled=True, classification="Ingreso")
    database.session.add_all([book, period, acct1, acct2])
    database.session.commit()

    # 2. Add some entries
    # Opening balance (before period)
    entry_opening = GLEntry(
        company="cacao",
        ledger_id=book.id,
        account_id=acct1.id,
        account_code=acct1.code,
        posting_date=date(2026, 4, 30),
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
        is_cancelled=False,
        is_fiscal_year_closing=False,
        voucher_type="journal_entry",
        voucher_id="OPEN-001",
    )
    # Movement within period
    entry_movement1 = GLEntry(
        company="cacao",
        ledger_id=book.id,
        account_id=acct1.id,
        account_code=acct1.code,
        posting_date=date(2026, 5, 10),
        debit=Decimal("50.00"),
        credit=Decimal("0.00"),
        is_cancelled=False,
        is_fiscal_year_closing=False,
        voucher_type="journal_entry",
        voucher_id="MOV-001",
    )
    entry_movement2 = GLEntry(
        company="cacao",
        ledger_id=book.id,
        account_id=acct1.id,
        account_code=acct1.code,
        posting_date=date(2026, 5, 15),
        debit=Decimal("0.00"),
        credit=Decimal("30.00"),
        is_cancelled=False,
        is_fiscal_year_closing=False,
        voucher_type="journal_entry",
        voucher_id="MOV-002",
    )
    database.session.add_all([entry_opening, entry_movement1, entry_movement2])
    database.session.commit()

    # 3. Call service
    filters = FinancialReportFilters(
        company="cacao",
        ledger="FISC",
        accounting_period="2026-05",
    )
    report = get_account_summary_report(filters)

    # 4. Assertions
    assert len(report.rows) == 1
    row = report.rows[0].values
    assert row["account_code"] == "1.01"
    assert row["opening_balance"] == Decimal("100.00")
    assert row["debit"] == Decimal("50.00")
    assert row["credit"] == Decimal("30.00")
    assert row["ending_balance"] == Decimal("120.00")
    assert row["movement_count"] == 2
    assert row["first_movement"] == date(2026, 5, 10)
    assert row["last_movement"] == date(2026, 5, 15)

    assert report.totals["opening_balance"] == Decimal("100.00")
    assert report.totals["debit"] == Decimal("50.00")
    assert report.totals["credit"] == Decimal("30.00")
    assert report.totals["ending_balance"] == Decimal("120.00")
