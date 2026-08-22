"""Regression coverage for gross-margin GL report consistency."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import AccountingPeriod, Accounts, Book, Entity, FiscalYear, GLEntry, database
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    OperationalReportFilters,
    get_balance_sheet_report,
    get_gross_margin,
)


def test_gross_margin_ignores_closing_entries_and_normalizes_plural_classifications() -> None:
    """Keep operational income and COGS when a fiscal closing is in the selected period."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        entity = Entity(code="margin", name="Margin", company_name="Margin", tax_id="MARGIN", currency="NIO")
        book = Book(entity="margin", code="MARGIN", name="Margin", currency="NIO", is_primary=True, default=True)
        income = Accounts(entity="margin", code="4.01", name="Ventas", active=True, enabled=True, classification="Ingresos")
        cost = Accounts(entity="margin", code="5.01", name="Costo", active=True, enabled=True, classification="Costos")
        database.session.add_all([entity, book, income, cost])
        database.session.flush()
        database.session.add_all(
            [
                GLEntry(
                    posting_date=date(2026, 12, 30),
                    company="margin",
                    ledger_id=book.id,
                    account_id=income.id,
                    account_code=income.code,
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    voucher_type="invoice",
                    voucher_id="invoice-1",
                ),
                GLEntry(
                    posting_date=date(2026, 12, 30),
                    company="margin",
                    ledger_id=book.id,
                    account_id=cost.id,
                    account_code=cost.code,
                    debit=Decimal("40"),
                    credit=Decimal("0"),
                    voucher_type="invoice",
                    voucher_id="invoice-1",
                ),
                GLEntry(
                    posting_date=date(2026, 12, 31),
                    company="margin",
                    ledger_id=book.id,
                    account_id=income.id,
                    account_code=income.code,
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    voucher_type="closing",
                    voucher_id="closing-1",
                    is_fiscal_year_closing=True,
                ),
                GLEntry(
                    posting_date=date(2026, 12, 31),
                    company="margin",
                    ledger_id=book.id,
                    account_id=cost.id,
                    account_code=cost.code,
                    debit=Decimal("0"),
                    credit=Decimal("40"),
                    voucher_type="closing",
                    voucher_id="closing-1",
                    is_fiscal_year_closing=True,
                ),
            ]
        )
        database.session.commit()

        report = get_gross_margin(
            OperationalReportFilters(company="margin", date_from=date(2026, 1, 1), date_to=date(2026, 12, 31))
        )

        assert report.totals == {
            "income": Decimal("100"),
            "cogs": Decimal("40"),
            "gross_margin": Decimal("60"),
        }


def test_balance_sheet_capitalizes_unclosed_prior_year_profit() -> None:
    """Present prior unclosed P&L balances as retained earnings in the new fiscal year."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(
            Entity(code="retained", name="Retained", company_name="Retained", tax_id="RETAINED", currency="NIO")
        )
        book = Book(entity="retained", code="RETAINED", name="Retained", currency="NIO", is_primary=True, default=True)
        income = Accounts(entity="retained", code="4.01", name="Ventas", active=True, enabled=True, classification="Ingresos")
        expense = Accounts(entity="retained", code="5.01", name="Gastos", active=True, enabled=True, classification="Gastos")
        cash = Accounts(entity="retained", code="1.01", name="Caja", active=True, enabled=True, classification="Activo")
        previous_year = FiscalYear(
            entity="retained", name="2025", year_start_date=date(2025, 1, 1), year_end_date=date(2025, 12, 31)
        )
        current_year = FiscalYear(
            entity="retained", name="2026", year_start_date=date(2026, 1, 1), year_end_date=date(2026, 12, 31)
        )
        database.session.add_all([book, income, expense, cash, previous_year, current_year])
        database.session.flush()
        current_period = AccountingPeriod(
            entity="retained",
            fiscal_year_id=current_year.id,
            name="2026-01",
            enabled=True,
            start=date(2026, 1, 1),
            end=date(2026, 1, 31),
        )
        database.session.add(current_period)
        database.session.add_all(
            [
                GLEntry(
                    posting_date=date(2025, 12, 20),
                    company="retained",
                    ledger_id=book.id,
                    account_id=cash.id,
                    account_code=cash.code,
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    voucher_type="invoice",
                    voucher_id="invoice-1",
                ),
                GLEntry(
                    posting_date=date(2025, 12, 20),
                    company="retained",
                    ledger_id=book.id,
                    account_id=income.id,
                    account_code=income.code,
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    voucher_type="invoice",
                    voucher_id="invoice-1",
                ),
                GLEntry(
                    posting_date=date(2025, 12, 21),
                    company="retained",
                    ledger_id=book.id,
                    account_id=expense.id,
                    account_code=expense.code,
                    debit=Decimal("30"),
                    credit=Decimal("0"),
                    voucher_type="expense",
                    voucher_id="expense-1",
                ),
                GLEntry(
                    posting_date=date(2025, 12, 21),
                    company="retained",
                    ledger_id=book.id,
                    account_id=cash.id,
                    account_code=cash.code,
                    debit=Decimal("0"),
                    credit=Decimal("30"),
                    voucher_type="expense",
                    voucher_id="expense-1",
                ),
            ]
        )
        database.session.commit()

        report = get_balance_sheet_report(
            FinancialReportFilters(company="retained", ledger="RETAINED", accounting_period="2026-01")
        )

        assert report.totals["assets"] == Decimal("70")
        assert report.totals["equity"] == Decimal("70")
        assert report.totals["period_profit"] == Decimal("0")
        assert report.totals["difference"] == Decimal("0")


def test_balance_sheet_without_fiscal_period_excludes_both_sides_of_closing_entry() -> None:
    """Avoid counting closing retained earnings and the same period profit together."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Entity(code="closing", name="Closing", company_name="Closing", tax_id="CLOSING", currency="NIO"))
        book = Book(entity="closing", code="CLOSING", name="Closing", currency="NIO", is_primary=True, default=True)
        cash = Accounts(entity="closing", code="1.01", name="Caja", active=True, enabled=True, classification="Activo")
        income = Accounts(entity="closing", code="4.01", name="Ventas", active=True, enabled=True, classification="Ingresos")
        equity = Accounts(
            entity="closing", code="3.01", name="Resultado acumulado", active=True, enabled=True, classification="Patrimonio"
        )
        database.session.add_all([book, cash, income, equity])
        database.session.flush()
        database.session.add_all(
            [
                GLEntry(
                    posting_date=date(2026, 12, 30),
                    company="closing",
                    ledger_id=book.id,
                    account_id=cash.id,
                    account_code=cash.code,
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    voucher_type="invoice",
                    voucher_id="invoice-1",
                ),
                GLEntry(
                    posting_date=date(2026, 12, 30),
                    company="closing",
                    ledger_id=book.id,
                    account_id=income.id,
                    account_code=income.code,
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    voucher_type="invoice",
                    voucher_id="invoice-1",
                ),
                GLEntry(
                    posting_date=date(2026, 12, 31),
                    company="closing",
                    ledger_id=book.id,
                    account_id=income.id,
                    account_code=income.code,
                    debit=Decimal("100"),
                    credit=Decimal("0"),
                    voucher_type="closing",
                    voucher_id="closing-1",
                    is_fiscal_year_closing=True,
                ),
                GLEntry(
                    posting_date=date(2026, 12, 31),
                    company="closing",
                    ledger_id=book.id,
                    account_id=equity.id,
                    account_code=equity.code,
                    debit=Decimal("0"),
                    credit=Decimal("100"),
                    voucher_type="closing",
                    voucher_id="closing-1",
                    is_fiscal_year_closing=True,
                ),
            ]
        )
        database.session.commit()

        report = get_balance_sheet_report(FinancialReportFilters(company="closing", ledger="CLOSING"))

        assert report.totals["equity"] == Decimal("100")
        assert report.totals["difference"] == Decimal("0")
