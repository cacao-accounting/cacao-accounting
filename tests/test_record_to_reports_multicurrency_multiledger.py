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
        Bank,
        BankAccount,
        Book,
        CompanyDefaultAccount,
        Currency,
        ExchangeRate,
        GLEntry,
        PartyAccount,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        OperationalReportFilters,
        get_balance_sheet_report,
        get_gross_margin,
        get_income_statement_report,
        get_sales_by_customer,
        get_sales_by_item,
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
    bank_account_gl = Accounts(
        entity="r2r", code="BANK-R2R", name="Bank", active=True, enabled=True, classification="asset", account_type="bank"
    )
    exchange_gain = Accounts(
        entity="r2r",
        code="FXG-R2R",
        name="Exchange gain",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    bank = Bank(name="R2R Bank")
    database.session.add_all([*currencies, local_book, ifrs_book, receivable, income, bank_account_gl, exchange_gain, bank])
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="r2r",
        account_name="USD account",
        currency="USD",
        gl_account_id=bank_account_gl.id,
    )
    database.session.add_all(
        [
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 8, 7)),
            ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.9"), date=date(2026, 8, 7)),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("37"), date=date(2026, 8, 8)),
            ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.95"), date=date(2026, 8, 8)),
            PartyAccount(party_id="CUST-R2R", company="r2r", receivable_account_id=receivable.id),
            CompanyDefaultAccount(
                company="r2r",
                default_receivable=receivable.id,
                default_bank=bank_account_gl.id,
                exchange_gain_account_id=exchange_gain.id,
            ),
            bank_account,
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
        base_total=Decimal("360"),
        grand_total=Decimal("10"),
        base_grand_total=Decimal("360"),
        outstanding_amount=Decimal("10"),
        base_outstanding_amount=Decimal("360"),
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
            base_amount=Decimal("360"),
            income_account_id=income.id,
        )
    )
    sales_return = SalesInvoice(
        company="r2r",
        posting_date=date(2026, 8, 7),
        customer_id="CUST-R2R",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
        is_return=True,
        grand_total=Decimal("2"),
        base_grand_total=Decimal("72"),
    )
    draft_invoice = SalesInvoice(
        company="r2r",
        posting_date=date(2026, 8, 7),
        customer_id="CUST-R2R",
        docstatus=0,
        grand_total=Decimal("1000"),
        base_grand_total=Decimal("36000"),
    )
    database.session.add_all([sales_return, draft_invoice])
    database.session.flush()
    database.session.add_all(
        [
            SalesInvoiceItem(
                sales_invoice_id=sales_return.id,
                item_code="SERVICE-R2R",
                qty=Decimal("0.2"),
                amount=Decimal("2"),
                base_amount=Decimal("72"),
            ),
            SalesInvoiceItem(
                sales_invoice_id=draft_invoice.id,
                item_code="SERVICE-R2R",
                qty=Decimal("100"),
                amount=Decimal("1000"),
                base_amount=Decimal("36000"),
            ),
        ]
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    operational_filters = OperationalReportFilters(company="r2r")
    sales_by_customer = get_sales_by_customer(operational_filters)
    sales_by_item = get_sales_by_item(operational_filters)
    gross_margin = get_gross_margin(operational_filters)
    assert sales_by_customer.totals["amount"] == Decimal("288")
    assert sales_by_item.totals["qty"] == Decimal("0.8")
    assert sales_by_item.totals["amount"] == Decimal("288")
    assert gross_margin.totals == {
        "income": Decimal("360"),
        "cogs": Decimal("0"),
        "gross_margin": Decimal("360"),
    }

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

    payment = PaymentEntry(
        company="r2r",
        posting_date=date(2026, 8, 8),
        payment_type="receive",
        party_type="customer",
        party_id="CUST-R2R",
        bank_account_id=bank_account.id,
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("37"),
        received_amount=Decimal("10"),
        base_received_amount=Decimal("370"),
        docstatus=1,
    )
    database.session.add(payment)
    database.session.flush()
    database.session.add(
        PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            total_amount=Decimal("10"),
            outstanding_amount=Decimal("10"),
            allocated_amount=Decimal("10"),
            allocation_date=payment.posting_date,
        )
    )
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    payment_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=payment.id)).scalars().all()
    assert len(payment_entries) == 6
    payment_expected = {
        local_book.id: (Decimal("370"), Decimal("360"), Decimal("10")),
        ifrs_book.id: (Decimal("9.5"), Decimal("9"), Decimal("0.5")),
    }
    for ledger_id, (cash_amount, carrying_amount, gain_amount) in payment_expected.items():
        book_entries = [entry for entry in payment_entries if entry.ledger_id == ledger_id]
        assert sum(entry.debit for entry in book_entries) == sum(entry.credit for entry in book_entries)
        assert any(entry.account_id == bank_account_gl.id and entry.debit == cash_amount for entry in book_entries)
        assert any(entry.account_id == receivable.id and entry.credit == carrying_amount for entry in book_entries)
        assert any(entry.account_id == exchange_gain.id and entry.credit == gain_amount for entry in book_entries)

    for ledger_code, currency, balance, cumulative in (
        ("R2RLOC", "NIO", Decimal("370"), Decimal("730")),
        ("R2REUR", "EUR", Decimal("9.5"), Decimal("18.5")),
    ):
        filters = FinancialReportFilters(company="r2r", ledger=ledger_code)
        trial_balance = get_trial_balance_report(filters)
        income_statement = get_income_statement_report(filters)
        balance_sheet = get_balance_sheet_report(filters)
        assert trial_balance.ledger_currency == currency
        assert trial_balance.totals["debit"] == cumulative
        assert trial_balance.totals["credit"] == cumulative
        assert income_statement.totals["net_profit"] == balance
        assert balance_sheet.totals["assets"] == balance
        assert balance_sheet.totals["period_profit"] == balance
        assert balance_sheet.totals["difference"] == 0


def test_semantic_reports_net_returns_and_expose_base_amount(app_ctx):
    """Semantic datasets must not inflate sales, purchases, or open items with returns."""
    from cacao_accounting.database import (
        PurchaseInvoice,
        PurchaseInvoiceItem,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )
    from cacao_accounting.reportes.semantic import (
        get_payables_analysis,
        get_purchase_analysis,
        get_receivables_analysis,
        get_sales_analysis,
    )

    def invoice(model, party_field, party, amount, is_return=False):
        return model(
            company="r2r",
            posting_date=date(2026, 8, 1),
            **{party_field: party},
            transaction_currency="USD",
            exchange_rate=Decimal("36"),
            grand_total=amount,
            base_grand_total=amount * Decimal("36"),
            outstanding_amount=amount,
            base_outstanding_amount=amount * Decimal("36"),
            is_return=is_return,
            docstatus=1,
        )

    sale, sale_return = invoice(SalesInvoice, "customer_id", "CUSTOMER-SEMANTIC", Decimal("10")), invoice(
        SalesInvoice, "customer_id", "CUSTOMER-SEMANTIC", Decimal("2"), True
    )
    purchase, purchase_return = invoice(PurchaseInvoice, "supplier_id", "SUPPLIER-SEMANTIC", Decimal("20")), invoice(
        PurchaseInvoice, "supplier_id", "SUPPLIER-SEMANTIC", Decimal("5"), True
    )
    database.session.add_all([sale, sale_return, purchase, purchase_return])
    database.session.flush()
    database.session.add_all(
        [
            SalesInvoiceItem(sales_invoice_id=sale.id, item_code="ITEM-SEMANTIC", qty=1, amount=10, base_amount=360),
            SalesInvoiceItem(sales_invoice_id=sale_return.id, item_code="ITEM-SEMANTIC", qty=1, amount=2, base_amount=72),
            PurchaseInvoiceItem(purchase_invoice_id=purchase.id, item_code="ITEM-SEMANTIC", qty=2, amount=20, base_amount=720),
            PurchaseInvoiceItem(
                purchase_invoice_id=purchase_return.id, item_code="ITEM-SEMANTIC", qty=1, amount=5, base_amount=180
            ),
        ]
    )
    database.session.commit()

    sales = get_sales_analysis(company="r2r")
    purchases = get_purchase_analysis(company="r2r")
    receivables = get_receivables_analysis(company="r2r")
    payables = get_payables_analysis(company="r2r")

    assert sum(row["quantity"] for row in sales) == Decimal("0")
    assert sum(row["amount"] for row in sales) == Decimal("8")
    assert sum(row["base_amount"] for row in sales) == Decimal("288")
    assert sum(row["quantity"] for row in purchases) == Decimal("1")
    assert sum(row["amount"] for row in purchases) == Decimal("15")
    assert sum(row["base_amount"] for row in purchases) == Decimal("540")
    assert sum(row["outstanding_amount"] for row in receivables) == Decimal("8")
    assert sum(row["outstanding_amount"] for row in payables) == Decimal("15")


def test_cash_forecast_uses_base_legacy_balance_and_nets_returns():
    """Cash projections must use base balances and subtract credit notes."""
    from types import SimpleNamespace

    from cacao_accounting.bancos.cash_forecast_service import _sum_invoice_amount

    invoices = [
        SimpleNamespace(
            posting_date=date(2026, 8, 1),
            outstanding_amount=Decimal("10"),
            base_outstanding_amount=None,
            exchange_rate=Decimal("36"),
            is_return=False,
        ),
        SimpleNamespace(
            posting_date=date(2026, 8, 2),
            outstanding_amount=Decimal("2"),
            base_outstanding_amount=Decimal("72"),
            exchange_rate=Decimal("36"),
            is_return=True,
        ),
    ]

    assert _sum_invoice_amount(invoices, date(2026, 8, 1), date(2026, 8, 31)) == Decimal("288")
