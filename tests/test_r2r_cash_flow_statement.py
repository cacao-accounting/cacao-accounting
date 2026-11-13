# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Cash-flow reports reconcile indirect movements with posted cash evidence."""

from datetime import date
from decimal import Decimal
import os
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    Book,
    CashFlowAccountMapping,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    database,
)
from cacao_accounting.reportes.cash_flow import get_cash_flow_statement
from cacao_accounting.reportes.services import FinancialReportFilters

pytestmark = pytest.mark.database


@pytest.fixture
def cash_flow_business_case(tmp_path):
    """Persist opening cash, operating activity, and an investing purchase."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if configured_uri.startswith("sqlite"):
        configured_uri = f"sqlite:///{tmp_path / 'cash-flow-business.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configured_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    suffix = uuid4().hex[:6].upper()
    company_code = f"CF{suffix}"
    currency_code = f"C{suffix}"
    ledger_code = f"L{suffix}"
    account_codes = {
        name: f"{code}{suffix}"
        for name, code in {
            "cash": "11",
            "income": "41",
            "expense": "52",
            "asset": "15",
            "equity": "31",
        }.items()
    }

    with app.app_context():
        database.create_all()
        currency = Currency(code=currency_code, name=f"Moneda EFE {suffix}", decimals=2, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Empresa EFE {suffix}",
            company_name=f"Empresa EFE {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency_code,
            enabled=True,
            status="activo",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        book = Book(
            entity=company_code,
            code=ledger_code,
            name=f"Libro EFE {suffix}",
            status="activo",
            currency=currency_code,
            default=True,
            is_primary=True,
        )
        fiscal_year = FiscalYear(
            entity=company_code,
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        accounts = {
            "cash": Accounts(
                entity=company_code,
                code=account_codes["cash"],
                name="Caja operativa",
                group=False,
                active=True,
                enabled=True,
                classification="asset",
                account_type="cash",
                currency=currency_code,
            ),
            "income": Accounts(
                entity=company_code,
                code=account_codes["income"],
                name="Ventas de contado",
                group=False,
                active=True,
                enabled=True,
                classification="income",
                account_type="income",
                currency=currency_code,
            ),
            "expense": Accounts(
                entity=company_code,
                code=account_codes["expense"],
                name="Gastos operativos",
                group=False,
                active=True,
                enabled=True,
                classification="expense",
                account_type="expense",
                currency=currency_code,
            ),
            "asset": Accounts(
                entity=company_code,
                code=account_codes["asset"],
                name="Equipo de operación",
                group=False,
                active=True,
                enabled=True,
                classification="asset",
                account_type="fixed_asset",
                currency=currency_code,
            ),
            "equity": Accounts(
                entity=company_code,
                code=account_codes["equity"],
                name="Patrimonio de apertura",
                group=False,
                active=True,
                enabled=True,
                classification="equity",
                account_type="equity",
                currency=currency_code,
            ),
        }
        database.session.add_all([book, fiscal_year, *accounts.values()])
        database.session.flush()
        period = AccountingPeriod(
            entity=company_code,
            fiscal_year_id=fiscal_year.id,
            name="Mayo 2026",
            status="open",
            enabled=True,
            is_closed=False,
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
        )
        database.session.add(period)
        database.session.flush()
        database.session.add_all(
            [
                CashFlowAccountMapping(company=company_code, account_id=accounts["cash"].id, flow_section="cash"),
                CashFlowAccountMapping(company=company_code, account_id=accounts["asset"].id, flow_section="investing"),
            ]
        )
        postings = [
            ("cash", date(2026, 4, 30), Decimal("50"), Decimal("0"), "opening-cash"),
            ("equity", date(2026, 4, 30), Decimal("0"), Decimal("50"), "opening-cash"),
            ("cash", date(2026, 5, 15), Decimal("100"), Decimal("0"), "cash-sale"),
            ("income", date(2026, 5, 15), Decimal("0"), Decimal("100"), "cash-sale"),
            ("expense", date(2026, 5, 20), Decimal("20"), Decimal("0"), "operating-expense"),
            ("cash", date(2026, 5, 20), Decimal("0"), Decimal("20"), "operating-expense"),
            ("asset", date(2026, 5, 25), Decimal("10"), Decimal("0"), "equipment-purchase"),
            ("cash", date(2026, 5, 25), Decimal("0"), Decimal("10"), "equipment-purchase"),
        ]
        for account_name, posting_date, debit, credit, voucher_id in postings:
            account = accounts[account_name]
            database.session.add(
                GLEntry(
                    company=company_code,
                    ledger_id=book.id,
                    account_id=account.id,
                    account_code=account.code,
                    account_currency=currency_code,
                    company_currency=currency_code,
                    exchange_rate=Decimal("1"),
                    posting_date=posting_date,
                    debit=debit,
                    credit=credit,
                    voucher_type="journal_entry",
                    voucher_id=f"{voucher_id}-{suffix}",
                    fiscal_year_id=fiscal_year.id,
                    accounting_period_id=period.id if posting_date.month == 5 else None,
                )
            )
        database.session.commit()
        filters = FinancialReportFilters(
            company=company_code,
            ledger=ledger_code,
            accounting_period=period.id,
        )

    yield app, company_code, currency_code, filters

    with app.app_context():
        database.session.remove()
        database.session.execute(database.delete(GLEntry).where(GLEntry.company == company_code))
        database.session.execute(database.delete(CashFlowAccountMapping).where(CashFlowAccountMapping.company == company_code))
        database.session.execute(database.delete(Accounts).where(Accounts.entity == company_code))
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.entity == company_code))
        database.session.execute(database.delete(FiscalYear).where(FiscalYear.entity == company_code))
        database.session.execute(database.delete(Book).where(Book.entity == company_code))
        database.session.execute(database.delete(Entity).where(Entity.code == company_code))
        database.session.execute(database.delete(Currency).where(Currency.code == currency_code))
        database.session.commit()
        database.session.remove()
        database.engine.dispose()


def test_cash_flow_statement_reconciles_opening_operating_and_investing_activity(cash_flow_business_case):
    """Indirect cash movement equals the posted net change across a real period."""
    app, company_code, currency_code, filters = cash_flow_business_case
    assert filters.company == company_code
    with app.app_context():
        report = get_cash_flow_statement(filters)

    assert report.ledger_currency == currency_code
    assert report.totals["net_profit"] == Decimal("80.0000")
    assert report.totals["investing"] == Decimal("-10.0000")
    assert report.totals["net_change_cash"] == Decimal("70.0000")
    assert report.totals["cash_opening"] == Decimal("50.0000")
    assert report.totals["cash_closing"] == Decimal("120.0000")
    assert report.totals["difference"] == Decimal("0.0000")
