"""Regression coverage for gross-margin GL report consistency."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Book, Entity, GLEntry, database
from cacao_accounting.reportes.services import OperationalReportFilters, get_gross_margin


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
