"""End-to-end evidence for multi-currency, multi-ledger record-to-reports."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Create an isolated accounting database for the R2R scenario."""
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
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(Entity(code="r2r", name="R2R", company_name="R2R", tax_id="R2R-1", currency="NIO"))
        database.session.commit()
        yield app


def test_foreign_invoice_reaches_reports_in_each_book_currency(app_ctx):
    """Post one USD invoice into NIO/EUR books and reconcile their reports."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Book,
        Currency,
        ExchangeRate,
        GLEntry,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        get_balance_sheet_report,
        get_income_statement_report,
        get_trial_balance_report,
    )

    currencies = [Currency(code=code, name=code, decimals=2, active=True) for code in ("NIO", "USD", "EUR")]
    local_book = Book(entity="r2r", code="R2RLOC", name="Local", currency="NIO", status="activo", is_primary=True)
    ifrs_book = Book(entity="r2r", code="R2REUR", name="IFRS", currency="EUR", status="activo")
    receivable = Accounts(entity="r2r", code="AR-R2R", name="Receivable", active=True, enabled=True, classification="asset")
    income = Accounts(
        entity="r2r",
        code="INC-R2R",
        name="Income",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([*currencies, local_book, ifrs_book, receivable, income])
    database.session.flush()
    database.session.add_all(
        [
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 8, 7)),
            ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.9"), date=date(2026, 8, 7)),
            PartyAccount(party_id="CUST-R2R", company="r2r", receivable_account_id=receivable.id),
        ]
    )
    invoice = SalesInvoice(
        company="r2r",
        posting_date=date(2026, 8, 7),
        customer_id="CUST-R2R",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
        total=Decimal("10"),
        grand_total=Decimal("10"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="SERVICE-R2R",
            item_name="Service",
            qty=Decimal("1"),
            rate=Decimal("10"),
            amount=Decimal("10"),
            income_account_id=income.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=invoice.id)).scalars().all()
    assert len(entries) == 4
    expected = {local_book.id: ("NIO", Decimal("36"), Decimal("360")), ifrs_book.id: ("EUR", Decimal("0.9"), Decimal("9"))}
    for ledger_id, (currency, rate, amount) in expected.items():
        book_entries = [entry for entry in entries if entry.ledger_id == ledger_id]
        assert len(book_entries) == 2
        assert {entry.company_currency for entry in book_entries} == {currency}
        assert {entry.account_currency for entry in book_entries} == {"USD"}
        assert {entry.exchange_rate for entry in book_entries} == {rate}
        assert sum(entry.debit for entry in book_entries) == amount
        assert sum(entry.credit for entry in book_entries) == amount
        assert sum(entry.debit_in_account_currency or 0 for entry in book_entries) == Decimal("10")
        assert sum(entry.credit_in_account_currency or 0 for entry in book_entries) == Decimal("10")

    for ledger_code, currency, amount in (("R2RLOC", "NIO", Decimal("360")), ("R2REUR", "EUR", Decimal("9"))):
        filters = FinancialReportFilters(company="r2r", ledger=ledger_code)
        trial_balance = get_trial_balance_report(filters)
        income_statement = get_income_statement_report(filters)
        balance_sheet = get_balance_sheet_report(filters)
        assert trial_balance.ledger_currency == currency
        assert trial_balance.totals["debit"] == amount
        assert trial_balance.totals["credit"] == amount
        assert trial_balance.totals["difference"] == 0
        assert income_statement.totals["income"] == amount
        assert income_statement.totals["net_profit"] == amount
        assert balance_sheet.totals["assets"] == amount
        assert balance_sheet.totals["period_profit"] == amount
        assert balance_sheet.totals["difference"] == 0
