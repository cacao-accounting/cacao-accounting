# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import pytest
from datetime import date
from decimal import Decimal
from cacao_accounting import create_app
from cacao_accounting.database import (
    database, Entity, FiscalYear, Accounts, GLEntry, ComprobanteContable,
    CompanyDefaultAccount, User, Roles, RolesUser, AccountingPeriod, Book
)
from cacao_accounting.contabilidad.fiscal_year_closing import (
    create_fiscal_year_closing_voucher,
    reverse_fiscal_year_closing,
    FiscalYearClosingError
)
from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal, cancel_submitted_journal

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
        entity = Entity(
            code="CMP",
            company_name="Test Company",
            tax_id="123",
            currency="USD",
            enabled=True
        )
        database.session.add(entity)

        # Setup Admin User
        user = User(id="admin_user", user="admin", name="Admin", password=b"123", classification="admin", active=True)
        database.session.add(user)

        # Setup Accounts
        income_acc = Accounts(entity="CMP", code="41.01", name="Income", classification="income", group=False, active=True)
        expense_acc = Accounts(entity="CMP", code="51.01", name="Expense", classification="expense", group=False, active=True)
        equity_acc = Accounts(entity="CMP", code="33.02", name="Retained Earnings", classification="equity", account_type="retained_earnings", group=False, active=True)
        cash_acc = Accounts(entity="CMP", code="11.01", name="Cash", classification="activo", group=False, active=True)

        database.session.add_all([income_acc, expense_acc, equity_acc, cash_acc])
        database.session.flush()

        # Setup Book
        book = Book(
            code="GEN",
            name="General Ledger",
            entity="CMP",
            is_primary=True,
            currency="USD"
        )
        database.session.add(book)

        # Setup Defaults
        defaults = CompanyDefaultAccount(company="CMP", retained_earnings_account_id=equity_acc.id)
        database.session.add(defaults)

        # Setup Fiscal Year
        fy = FiscalYear(
            entity="CMP",
            name="2024",
            year_start_date=date(2024, 1, 1),
            year_end_date=date(2024, 12, 31),
            is_closed=False
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
            is_closed=False
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
            "equity_acc_code": equity_acc.code
        }

def test_fiscal_year_closing_cycle(app, setup_data):
    with app.app_context():
        # 1. Create movements
        payload1 = {
            "company": "CMP", "posting_date": "2024-12-15",
            "lines": [
                {"account": setup_data["cash_acc_code"], "debit": "100", "credit": "0"},
                {"account": setup_data["income_acc_code"], "debit": "0", "credit": "100"},
            ]
        }
        j1 = create_journal_draft(payload1, setup_data["admin_user_id"])
        submit_journal(j1.id)

        fy = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        fy.is_closed = True
        database.session.commit()

        # 2. Create Closing Voucher (Draft)
        closing_journal = create_fiscal_year_closing_voucher("CMP", setup_data["fiscal_year_id"], setup_data["admin_user_id"])
        assert closing_journal.status == "draft"
        assert closing_journal.is_fiscal_year_closing is True

        fy = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        assert fy.financial_closed is False # Still draft

        # 3. Submit Closing Voucher
        submit_journal(closing_journal.id)
        assert closing_journal.status == "submitted"

        fy = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        assert fy.financial_closed is True
        assert fy.closing_voucher_id == closing_journal.id

        # 4. Cancel Closing Voucher
        cancel_submitted_journal(closing_journal.id, user_id=setup_data["admin_user_id"])
        assert closing_journal.status == "cancelled"

        fy = database.session.get(FiscalYear, setup_data["fiscal_year_id"])
        assert fy.financial_closed is False
        assert fy.closing_voucher_id is None
