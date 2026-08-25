# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import pytest
from datetime import date
from decimal import Decimal

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Entity,
    FiscalYear,
    Accounts,
    CompanyDefaultAccount,
    Modules,
    User,
    AccountingPeriod,
    Book,
    Currency,
    ExchangeRate,
    GLEntry,
)
from cacao_accounting.contabilidad.fiscal_year_closing import (
    _build_closing_voucher_payload,
    create_fiscal_year_closing_voucher,
)
from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal, cancel_submitted_journal


def test_closing_payload_omits_zero_net_retained_earnings_line(app):
    """Un libro con resultado neto cero no genera una línea sin importe."""
    fiscal_year = type("FiscalYearStub", (), {"name": "2024", "id": "FY2024", "year_end_date": date(2024, 12, 31)})()
    payload = _build_closing_voucher_payload(
        company="CMP",
        fiscal_year=fiscal_year,
        balances=[
            {"book": "GEN", "account_code": "41.01", "cost_center": None, "unit": None, "project": None, "balance": "500"},
            {"book": "GEN", "account_code": "51.01", "cost_center": None, "unit": None, "project": None, "balance": "-500"},
        ],
        retained_earnings_code="33.02",
    )

    assert len(payload["lines"]) == 2
    assert all(line["account"] != "33.02" for line in payload["lines"])


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture
def setup_data(app):
    with app.app_context():
        # Setup Entity
        entity = Entity(code="CMP", company_name="Test Company", tax_id="123", currency="USD", enabled=True)
        database.session.add(entity)

        # Setup Modules & Admin User
        database.session.add(Modules(module="accounting", default=True, enabled=True))
        user = User(id="admin_user", user="admin", name="Admin", password=b"123", classification="admin", active=True)
        database.session.add(user)

        # Setup Accounts
        income_acc = Accounts(entity="CMP", code="41.01", name="Income", classification="income", group=False, active=True)
        expense_acc = Accounts(entity="CMP", code="51.01", name="Expense", classification="expense", group=False, active=True)
        equity_acc = Accounts(
            entity="CMP",
            code="33.02",
            name="Retained Earnings",
            classification="equity",
            account_type="retained_earnings",
            group=False,
            active=True,
        )
        cash_acc = Accounts(entity="CMP", code="11.01", name="Cash", classification="activo", group=False, active=True)

        database.session.add_all([income_acc, expense_acc, equity_acc, cash_acc])
        database.session.flush()

        database.session.add_all(
            [
                Currency(code="USD", name="US Dollar", decimals=2, active=True),
                Currency(code="EUR", name="Euro", decimals=2, active=True),
            ]
        )

        # Setup Books
        book = Book(code="GEN", name="General Ledger", entity="CMP", is_primary=True, currency="USD", status="activo")
        eur_book = Book(code="EUR", name="EUR Ledger", entity="CMP", is_primary=False, currency="EUR", status="activo")
        database.session.add_all([book, eur_book])
        database.session.add(ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.90"), date=date(2024, 12, 15)))

        # Setup Defaults
        defaults = CompanyDefaultAccount(company="CMP", retained_earnings_account_id=equity_acc.id)
        database.session.add(defaults)

        # Setup Fiscal Year
        fy = FiscalYear(
            entity="CMP", name="2024", year_start_date=date(2024, 1, 1), year_end_date=date(2024, 12, 31), is_closed=False
        )
        database.session.add(fy)
        database.session.flush()

        # Setup Accounting Period
        period = AccountingPeriod(
            entity="CMP",
            fiscal_year_id=fy.id,
            name="2024-12",
            start=date(2024, 12, 1),
            end=date(2024, 12, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period)

        database.session.commit()
        return {
            "entity": "CMP",
            "fiscal_year_id": fy.id,
            "admin_user_id": user.id,
            "income_acc_code": income_acc.code,
            "expense_acc_code": expense_acc.code,
            "cash_acc_code": cash_acc.code,
            "equity_acc_code": equity_acc.code,
        }


def test_fiscal_year_closing_cycle(app, setup_data):
    with app.app_context():
        # 1. Create movements
        payload1 = {
            "company": "CMP",
            "posting_date": "2024-12-15",
            "transaction_currency": "USD",
            "exchange_rate": "1",
            "lines": [
                {"account": setup_data["cash_acc_code"], "debit": "100", "credit": "0"},
                {"account": setup_data["income_acc_code"], "debit": "0", "credit": "100"},
            ],
        }
        j1 = create_journal_draft(payload1, setup_data["admin_user_id"])
        submit_journal(j1.id)

        fy = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        fy.is_closed = True
        database.session.commit()

        with pytest.raises(Exception, match="período.*abierto"):
            create_fiscal_year_closing_voucher("CMP", setup_data["fiscal_year_id"], setup_data["admin_user_id"])

        period = database.session.execute(
            database.select(AccountingPeriod).filter_by(fiscal_year_id=setup_data["fiscal_year_id"])
        ).scalar_one()
        period.is_closed = True
        # A closed period may remain enabled for reporting and lookup.  Its
        # closed state, not the administrative enabled flag, governs fiscal
        # year closing eligibility.
        period.enabled = True
        database.session.commit()

        # 2. Create Closing Voucher (auto-submitted)
        closing_journal = create_fiscal_year_closing_voucher("CMP", setup_data["fiscal_year_id"], setup_data["admin_user_id"])
        assert closing_journal.status == "submitted"
        assert closing_journal.is_fiscal_year_closing is True

        books = {book.code: book for book in database.session.execute(database.select(Book)).scalars().all()}
        closing_entries = (
            database.session.execute(
                database.select(GLEntry).filter_by(voucher_id=closing_journal.id, is_fiscal_year_closing=True)
            )
            .scalars()
            .all()
        )
        income_by_book = {
            code: next(entry for entry in closing_entries if entry.ledger_id == book.id and entry.account_code == "41.01")
            for code, book in books.items()
        }
        assert income_by_book["GEN"].debit == Decimal("100.0000")
        assert income_by_book["EUR"].debit == Decimal("90.0000")

        fy = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        assert fy.financial_closed is True
        assert fy.closing_voucher_id == closing_journal.id

        # 3. Cancel Closing Voucher
        cancel_submitted_journal(closing_journal.id, user_id=setup_data["admin_user_id"])
        assert closing_journal.status == "cancelled"

        fy = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        assert fy.financial_closed is False
        assert fy.closing_voucher_id is None


def test_multiannual_balance_sheet_balanced(app, setup_data):
    from cacao_accounting.reportes.services import get_balance_sheet_report, FinancialReportFilters

    with app.app_context():
        # Setup another equity/capital account
        capital_acc = Accounts(
            entity="CMP",
            code="31.01",
            name="Capital",
            classification="equity",
            group=False,
            active=True,
        )
        database.session.add(capital_acc)

        # Setup 2025 fiscal year and period
        fy2025 = FiscalYear(
            entity="CMP",
            name="2025",
            year_start_date=date(2025, 1, 1),
            year_end_date=date(2025, 12, 31),
            is_closed=False,
        )
        database.session.add(fy2025)
        database.session.flush()

        period2025 = AccountingPeriod(
            entity="CMP",
            fiscal_year_id=fy2025.id,
            name="2025-01",
            start=date(2025, 1, 1),
            end=date(2025, 1, 31),
            enabled=True,
            is_closed=False,
        )
        database.session.add(period2025)
        database.session.commit()

        # Post transactions in 2024 (period 2024-12):
        # 1. Income of 1000
        payload1 = {
            "company": "CMP",
            "posting_date": "2024-12-15",
            "transaction_currency": "USD",
            "exchange_rate": "1",
            "lines": [
                {"account": setup_data["cash_acc_code"], "debit": "1000", "credit": "0"},
                {"account": setup_data["income_acc_code"], "debit": "0", "credit": "1000"},
            ],
        }
        j1 = create_journal_draft(payload1, setup_data["admin_user_id"])
        submit_journal(j1.id)

        # 2. Expense of 600
        payload2 = {
            "company": "CMP",
            "posting_date": "2024-12-15",
            "transaction_currency": "USD",
            "exchange_rate": "1",
            "lines": [
                {"account": setup_data["expense_acc_code"], "debit": "600", "credit": "0"},
                {"account": setup_data["cash_acc_code"], "debit": "0", "credit": "600"},
            ],
        }
        j2 = create_journal_draft(payload2, setup_data["admin_user_id"])
        submit_journal(j2.id)

        # 3. Capital of 100
        payload3 = {
            "company": "CMP",
            "posting_date": "2024-12-15",
            "transaction_currency": "USD",
            "exchange_rate": "1",
            "lines": [
                {"account": setup_data["cash_acc_code"], "debit": "100", "credit": "0"},
                {"account": capital_acc.code, "debit": "0", "credit": "100"},
            ],
        }
        j3 = create_journal_draft(payload3, setup_data["admin_user_id"])
        submit_journal(j3.id)

        # Close 2024 fiscal year
        fy2024 = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        fy2024.is_closed = True
        period2024 = database.session.execute(
            database.select(AccountingPeriod).filter_by(fiscal_year_id=setup_data["fiscal_year_id"])
        ).scalar_one()
        period2024.is_closed = True
        period2024.enabled = False
        database.session.commit()

        # Create Fiscal Year Closing for 2024
        closing_journal = create_fiscal_year_closing_voucher("CMP", setup_data["fiscal_year_id"], setup_data["admin_user_id"])
        assert closing_journal.status == "submitted"

        # Get Balance Sheet Report for 2025-01 (should be multiannual and perfectly balanced)
        report_filters = FinancialReportFilters(
            company="CMP",
            ledger="GEN",
            accounting_period="2025-01",
        )
        report = get_balance_sheet_report(report_filters)

        # Expected:
        # assets = 500 (1000 - 600 + 100)
        # liabilities = 0
        # equity = 500 (capital 100 + retained earnings 400)
        # difference = 0
        assert report.totals["assets"] == Decimal("500.00")
        assert report.totals["liabilities"] == Decimal("0.00")
        assert report.totals["equity"] == Decimal("500.00")
        assert report.totals["difference"] == Decimal("0.00")
