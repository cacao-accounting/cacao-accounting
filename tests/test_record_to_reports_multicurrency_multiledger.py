"""End-to-end evidence for multi-currency, multi-ledger record-to-reports."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Book


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
        Bank,
        BankAccount,
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

    sale, sale_return = (
        invoice(SalesInvoice, "customer_id", "CUSTOMER-SEMANTIC", Decimal("10")),
        invoice(SalesInvoice, "customer_id", "CUSTOMER-SEMANTIC", Decimal("2"), True),
    )
    purchase, purchase_return = (
        invoice(PurchaseInvoice, "supplier_id", "SUPPLIER-SEMANTIC", Decimal("20")),
        invoice(PurchaseInvoice, "supplier_id", "SUPPLIER-SEMANTIC", Decimal("5"), True),
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

    assert sum(row["amount"] for row in sales) == Decimal("8")
    assert sum(row["quantity"] for row in sales) == Decimal("0")
    assert sum(row["base_amount"] for row in sales) == Decimal("288")
    assert sum(row["amount"] for row in purchases) == Decimal("15")
    assert sum(row["quantity"] for row in purchases) == Decimal("1")
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
            transaction_currency="USD",
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


def test_cash_forecast_skips_only_an_invoice_without_a_conversion_rate():
    """One incomplete foreign invoice cannot suppress other cash projections."""
    from types import SimpleNamespace

    from cacao_accounting.bancos.cash_forecast_service import _sum_invoice_amount

    invoices = [
        SimpleNamespace(
            posting_date=date(2026, 8, 1),
            outstanding_amount=Decimal("10"),
            base_outstanding_amount=None,
            transaction_currency="USD",
            exchange_rate=None,
            is_return=False,
        ),
        SimpleNamespace(
            posting_date=date(2026, 8, 2),
            outstanding_amount=Decimal("5"),
            base_outstanding_amount=Decimal("180"),
            transaction_currency="USD",
            exchange_rate=Decimal("36"),
            is_return=False,
        ),
    ]

    assert _sum_invoice_amount(invoices, date(2026, 8, 1), date(2026, 8, 31)) == Decimal("180")


def test_semantic_reports_multicurrency(app_ctx):
    """Verify that semantic AR/AP datasets correctly project currency, base_amount, and base_outstanding_amount."""
    from cacao_accounting.database import (
        PurchaseInvoice,
        PurchaseInvoiceItem,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )
    from cacao_accounting.reportes.semantic import (
        get_payables_analysis,
        get_receivables_analysis,
    )

    def make_sales_invoice(amount, currency, rate):
        invoice = SalesInvoice(
            company="r2r",
            posting_date=date(2026, 8, 1),
            customer_id="CUSTOMER-SEMANTIC",
            transaction_currency=currency,
            base_currency="NIO",
            exchange_rate=rate,
            grand_total=amount,
            base_grand_total=amount * rate,
            outstanding_amount=amount,
            base_outstanding_amount=amount * rate,
            is_return=False,
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code="ITEM-SEMANTIC",
                qty=1,
                amount=amount,
                base_amount=amount * rate,
            )
        )
        return invoice

    def make_purchase_invoice(amount, currency, rate):
        invoice = PurchaseInvoice(
            company="r2r",
            posting_date=date(2026, 8, 1),
            supplier_id="SUPPLIER-SEMANTIC",
            transaction_currency=currency,
            base_currency="NIO",
            exchange_rate=rate,
            grand_total=amount,
            base_grand_total=amount * rate,
            outstanding_amount=amount,
            base_outstanding_amount=amount * rate,
            is_return=False,
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code="ITEM-SEMANTIC",
                qty=1,
                amount=amount,
                base_amount=amount * rate,
            )
        )
        return invoice

    # Clear previous documents for clean assertion
    database.session.execute(database.delete(SalesInvoiceItem))
    database.session.execute(database.delete(SalesInvoice))
    database.session.execute(database.delete(PurchaseInvoiceItem))
    database.session.execute(database.delete(PurchaseInvoice))
    database.session.commit()

    # Sales Invoices: 10 USD (base NIO 360) and 100 NIO (base NIO 100)
    make_sales_invoice(Decimal("10"), "USD", Decimal("36"))
    make_sales_invoice(Decimal("100"), "NIO", Decimal("1"))
    database.session.commit()

    receivables = get_receivables_analysis(company="r2r")
    assert len(receivables) == 2

    # Check first invoice (USD 10)
    row_usd = [r for r in receivables if r["currency"] == "USD"][0]
    assert row_usd["amount"] == Decimal("10")
    assert row_usd["outstanding_amount"] == Decimal("10")
    assert row_usd["base_amount"] == Decimal("360")
    assert row_usd["base_outstanding_amount"] == Decimal("360")

    # Check second invoice (NIO 100)
    row_nio = [r for r in receivables if r["currency"] == "NIO"][0]
    assert row_nio["amount"] == Decimal("100")
    assert row_nio["outstanding_amount"] == Decimal("100")
    assert row_nio["base_amount"] == Decimal("100")
    assert row_nio["base_outstanding_amount"] == Decimal("100")

    # Purchase Invoices: 10 USD (base NIO 360) and 100 NIO (base NIO 100)
    make_purchase_invoice(Decimal("10"), "USD", Decimal("36"))
    make_purchase_invoice(Decimal("100"), "NIO", Decimal("1"))
    database.session.commit()

    payables = get_payables_analysis(company="r2r")
    assert len(payables) == 2

    # Check first invoice (USD 10)
    row_p_usd = [r for r in payables if r["currency"] == "USD"][0]
    assert row_p_usd["amount"] == Decimal("10")
    assert row_p_usd["outstanding_amount"] == Decimal("10")
    assert row_p_usd["base_amount"] == Decimal("360")
    assert row_p_usd["base_outstanding_amount"] == Decimal("360")

    # Check second invoice (NIO 100)
    row_p_nio = [r for r in payables if r["currency"] == "NIO"][0]
    assert row_p_nio["amount"] == Decimal("100")
    assert row_p_nio["outstanding_amount"] == Decimal("100")
    assert row_p_nio["base_amount"] == Decimal("100")
    assert row_p_nio["base_outstanding_amount"] == Decimal("100")


def test_r2r_multi_currency_journal_entry_all_reports(app_ctx):
    """Post manual journal entries in GBP to NIO/EUR/USD books and verify reports."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Book,
        Currency,
        ExchangeRate,
        ComprobanteContable,
        ComprobanteContableDetalle,
        GLEntry,
        database,
    )
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        get_balance_sheet_report,
        get_income_statement_report,
        get_trial_balance_report,
        get_account_summary_report,
    )

    currencies = [Currency(code=code, name=code, decimals=2, active=True) for code in ("NIO", "USD", "EUR", "GBP")]
    local_book = Book(entity="r2r", code="R2RLOC", name="Local", currency="NIO", status="activo", is_primary=True)
    ifrs_book = Book(entity="r2r", code="R2REUR", name="IFRS", currency="EUR", status="activo")
    us_gaap_book = Book(entity="r2r", code="R2RUSD", name="USGAAP", currency="USD", status="activo")

    receivable = Accounts(entity="r2r", code="AR-JE", name="Receivable JE", active=True, enabled=True, classification="asset")
    income = Accounts(
        entity="r2r",
        code="INC-JE",
        name="Income JE",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )

    database.session.add_all([*currencies, local_book, ifrs_book, us_gaap_book, receivable, income])
    database.session.flush()

    database.session.add_all(
        [
            ExchangeRate(origin="GBP", destination="NIO", rate=Decimal("50"), date=date(2026, 8, 7)),
            ExchangeRate(origin="GBP", destination="EUR", rate=Decimal("1.2"), date=date(2026, 8, 7)),
            ExchangeRate(origin="GBP", destination="USD", rate=Decimal("1.3"), date=date(2026, 8, 7)),
        ]
    )
    database.session.flush()

    journal = ComprobanteContable(
        entity="r2r",
        date=date(2026, 8, 7),
        transaction_currency="GBP",
        memo="Manual multi-currency JE",
    )
    database.session.add(journal)
    database.session.flush()

    database.session.add_all(
        [
            ComprobanteContableDetalle(
                entity="r2r",
                account=receivable.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("10.00"),
                memo="Dr Receivable",
                third_type="customer",
                third_code="CUST-JE",
            ),
            ComprobanteContableDetalle(
                entity="r2r",
                account=income.code,
                date=journal.date,
                transaction="journal_entry",
                transaction_id=journal.id,
                value=Decimal("-10.00"),
                memo="Cr Income",
            ),
        ]
    )
    database.session.commit()

    post_document_to_gl(journal)
    database.session.commit()

    entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=journal.id)).scalars().all()
    assert len(entries) == 6

    expected_rates = {
        local_book.id: ("NIO", Decimal("50"), Decimal("500")),
        ifrs_book.id: ("EUR", Decimal("1.2"), Decimal("12")),
        us_gaap_book.id: ("USD", Decimal("1.3"), Decimal("13")),
    }

    for ledger_id, (currency, rate, amount) in expected_rates.items():
        book_entries = [entry for entry in entries if entry.ledger_id == ledger_id]
        assert len(book_entries) == 2
        assert {entry.company_currency for entry in book_entries} == {currency}
        assert {entry.account_currency for entry in book_entries} == {"GBP"}
        assert {entry.exchange_rate for entry in book_entries} == {rate}
        assert sum(entry.debit for entry in book_entries) == amount
        assert sum(entry.credit for entry in book_entries) == amount
        assert sum(entry.debit_in_account_currency or 0 for entry in book_entries) == Decimal("10")
        assert sum(entry.credit_in_account_currency or 0 for entry in book_entries) == Decimal("10")

    report_checks = [
        ("R2RLOC", "NIO", Decimal("500")),
        ("R2REUR", "EUR", Decimal("12")),
        ("R2RUSD", "USD", Decimal("13")),
    ]

    for ledger_code, currency, expected_amount in report_checks:
        filters = FinancialReportFilters(company="r2r", ledger=ledger_code)

        tb = get_trial_balance_report(filters)
        assert tb.ledger_currency == currency
        assert tb.totals["debit"] == expected_amount
        assert tb.totals["credit"] == expected_amount
        assert tb.totals["difference"] == 0

        income_stmt = get_income_statement_report(filters)
        assert income_stmt.totals["income"] == expected_amount
        assert income_stmt.totals["net_profit"] == expected_amount

        bs = get_balance_sheet_report(filters)
        assert bs.totals["assets"] == expected_amount
        assert bs.totals["period_profit"] == expected_amount
        assert bs.totals["difference"] == 0

        summary_rpt = get_account_summary_report(filters)
        assert summary_rpt.ledger_currency == currency
        assert summary_rpt.totals["debit"] == expected_amount
        assert summary_rpt.totals["credit"] == expected_amount
        assert summary_rpt.totals["difference"] == 0


def test_r2r_purchase_flow_reconciliation_multicurrency(app_ctx):
    """Post USD purchase invoice & returns into NIO/EUR/USD books.

    Verify reconciliation & operational reports.
    """
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        Book,
        CompanyDefaultAccount,
        Currency,
        ExchangeRate,
        PartyAccount,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        database,
    )
    from cacao_accounting.reportes.services import (
        OperationalReportFilters,
        ReconciliationFilters,
        get_reconciliation_matrix,
        get_purchases_by_supplier,
        get_purchases_by_item,
        get_ar_ap_subledger,
        SubledgerFilters,
    )

    currencies = [Currency(code=code, name=code, decimals=2, active=True) for code in ("NIO", "USD", "EUR")]
    local_book = Book(entity="r2r", code="R2RLOC", name="Local", currency="NIO", status="activo", is_primary=True)
    ifrs_book = Book(entity="r2r", code="R2REUR", name="IFRS", currency="EUR", status="activo")
    us_gaap_book = Book(entity="r2r", code="R2RUSD", name="USGAAP", currency="USD", status="activo")

    payable = Accounts(entity="r2r", code="AP-R2R", name="Payable", active=True, enabled=True, classification="liability")
    expense = Accounts(
        entity="r2r",
        code="EXP-R2R",
        name="Expense",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    bank_account_gl = Accounts(
        entity="r2r", code="BANK-R2R-P", name="Bank P", active=True, enabled=True, classification="asset", account_type="bank"
    )
    exchange_gain = Accounts(
        entity="r2r",
        code="FXG-R2R-P",
        name="Exchange gain P",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    bank = Bank(name="R2R Bank P")
    database.session.add_all(
        [*currencies, local_book, ifrs_book, us_gaap_book, payable, expense, bank_account_gl, exchange_gain, bank]
    )
    database.session.flush()

    bank_account = BankAccount(
        bank_id=bank.id,
        company="r2r",
        account_name="USD account P",
        currency="USD",
        gl_account_id=bank_account_gl.id,
    )
    database.session.add_all(
        [
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 8, 7)),
            ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.9"), date=date(2026, 8, 7)),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("37"), date=date(2026, 8, 8)),
            ExchangeRate(origin="USD", destination="EUR", rate=Decimal("0.95"), date=date(2026, 8, 8)),
            PartyAccount(party_id="SUPP-R2R", company="r2r", payable_account_id=payable.id),
            CompanyDefaultAccount(
                company="r2r",
                default_payable=payable.id,
                default_bank=bank_account_gl.id,
                default_expense=expense.id,
                exchange_gain_account_id=exchange_gain.id,
            ),
            bank_account,
        ]
    )
    database.session.flush()

    invoice = PurchaseInvoice(
        company="r2r",
        posting_date=date(2026, 8, 7),
        supplier_id="SUPP-R2R",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("3600"),
        base_grand_total=Decimal("3600"),
        outstanding_amount=Decimal("100"),
        base_outstanding_amount=Decimal("3600"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-P",
            item_name="Purchased Item",
            qty=Decimal("1"),
            rate=Decimal("100"),
            amount=Decimal("100"),
            base_amount=Decimal("3600"),
            expense_account_id=expense.id,
        )
    )

    return_invoice = PurchaseInvoice(
        company="r2r",
        posting_date=date(2026, 8, 7),
        supplier_id="SUPP-R2R",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
        is_return=True,
        total=Decimal("20"),
        grand_total=Decimal("20"),
        base_total=Decimal("720"),
        base_grand_total=Decimal("720"),
        outstanding_amount=Decimal("20"),
        base_outstanding_amount=Decimal("720"),
    )
    database.session.add(return_invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=return_invoice.id,
            item_code="ITEM-P",
            item_name="Purchased Item",
            qty=Decimal("0.2"),
            rate=Decimal("100"),
            amount=Decimal("20"),
            base_amount=Decimal("720"),
            expense_account_id=expense.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    post_document_to_gl(return_invoice)
    database.session.commit()

    sub_filters = SubledgerFilters(company="r2r", party_type="supplier", as_of_date=date(2026, 8, 7))
    subledger = get_ar_ap_subledger(sub_filters)
    assert subledger.totals["outstanding_amount"] == Decimal("2880")

    op_filters = OperationalReportFilters(company="r2r", date_from=date(2026, 8, 7), date_to=date(2026, 8, 7))
    by_supp = get_purchases_by_supplier(op_filters)
    by_item = get_purchases_by_item(op_filters)

    assert by_supp.totals["amount"] == Decimal("2880")
    assert by_item.totals["qty"] == Decimal("0.8")
    assert by_item.totals["amount"] == Decimal("2880")

    for ledger_code, currency, expected_sub_amount, expected_gl_amount, expected_diff, expected_status in (
        ("R2RLOC", "NIO", Decimal("-2880"), Decimal("-2880"), Decimal("0"), "reconciled"),
        ("R2REUR", "EUR", Decimal("-2880"), Decimal("-72"), Decimal("-2808"), "difference"),
        ("R2RUSD", "USD", Decimal("-80"), Decimal("-80"), Decimal("0"), "reconciled"),
    ):
        recon_filters = ReconciliationFilters(company="r2r", ledger=ledger_code, as_of_date=date(2026, 8, 7))
        # EUR ledger has no NIO->EUR or EUR->NIO exchange rate: the subledger
        # in company currency (NIO) cannot be converted to the ledger currency
        # (EUR), so the matrix must fail in a controlled way instead of
        # reporting a false difference.
        if currency == "EUR":
            with pytest.raises(ValueError, match="tipo de cambio"):
                get_reconciliation_matrix(recon_filters)
            continue

        matrix = get_reconciliation_matrix(recon_filters)

        ap_row = next(row for row in matrix.rows if row.values["area"] == "AP")
        assert ap_row.values["subledger_amount"] == expected_sub_amount
        assert ap_row.values["gl_control_amount"] == expected_gl_amount
        assert ap_row.values["difference"] == expected_diff
        assert ap_row.values["status"] == expected_status


def test_semantic_reports_fallback_to_company_currency(app_ctx):
    """Use the entity currency when local invoices omit currency fields."""
    from cacao_accounting.database import PurchaseInvoice, SalesInvoice, database
    from cacao_accounting.reportes.semantic import get_payables_analysis, get_receivables_analysis

    database.session.add_all(
        [
            SalesInvoice(
                company="r2r",
                posting_date=date(2026, 8, 1),
                customer_id="CUSTOMER-LOCAL",
                grand_total=Decimal("50"),
                outstanding_amount=Decimal("50"),
                docstatus=1,
            ),
            PurchaseInvoice(
                company="r2r",
                posting_date=date(2026, 8, 1),
                supplier_id="SUPPLIER-LOCAL",
                grand_total=Decimal("75"),
                outstanding_amount=Decimal("75"),
                docstatus=1,
            ),
        ]
    )
    database.session.commit()

    receivable = get_receivables_analysis(company="r2r")[0]
    payable = get_payables_analysis(company="r2r")[0]

    assert receivable["currency"] == "NIO"
    assert receivable["base_amount"] == Decimal("50")
    assert payable["currency"] == "NIO"
    assert payable["base_amount"] == Decimal("75")


def test_settlement_analysis_excludes_cancelled_payments(app_ctx):
    """Cancelled payments must not remain in the settlement semantic dataset."""
    from cacao_accounting.database import PaymentEntry, PaymentReference, database
    from cacao_accounting.reportes.semantic import get_settlement_analysis

    active_payment = PaymentEntry(
        company="r2r",
        posting_date=date(2026, 8, 1),
        payment_type="receive",
        received_amount=Decimal("100"),
        docstatus=1,
    )
    cancelled_payment = PaymentEntry(
        company="r2r",
        posting_date=date(2026, 8, 2),
        payment_type="receive",
        received_amount=Decimal("200"),
        docstatus=2,
    )
    database.session.add_all([active_payment, cancelled_payment])
    database.session.flush()
    database.session.add_all(
        [
            PaymentReference(
                payment_id=active_payment.id,
                reference_type="sales_invoice",
                reference_id="INV-ACTIVE",
                company="r2r",
                allocated_amount=Decimal("100"),
                allocation_date=active_payment.posting_date,
            ),
            PaymentReference(
                payment_id=cancelled_payment.id,
                reference_type="sales_invoice",
                reference_id="INV-CANCELLED",
                company="r2r",
                allocated_amount=Decimal("200"),
                allocation_date=cancelled_payment.posting_date,
            ),
        ]
    )
    database.session.commit()

    rows = get_settlement_analysis(company="r2r")

    assert [row["amount"] for row in rows] == [Decimal("100")]


def test_r2r_multi_company_isolation_all_ledgers(app_ctx):
    """Assert strict multi-tenant entity isolation across GL, AR, AP, and Kardex ledgers."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        Entity,
        GLEntry,
        Item,
        ItemAccount,
        PartyAccount,
        PurchaseInvoice,
        SalesInvoice,
        SalesInvoiceItem,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        Warehouse,
        database,
    )
    from cacao_accounting.reportes.semantic import (
        get_payables_analysis,
        get_receivables_analysis,
    )
    from cacao_accounting.reportes.services import SubledgerFilters, get_ar_ap_subledger

    # Setup Company B
    database.session.add(Book(code="R2R-BASE", name="Base A", entity="r2r", currency="NIO", is_primary=True, status="activo"))
    comp_b = Entity(code="r2r-b", name="R2R Corp B", company_name="R2R Corp B", tax_id="R2R-B-1", currency="NIO")
    database.session.add(comp_b)
    database.session.flush()
    database.session.add(
        Book(code="R2R-BBASE", name="Base B", entity="r2r-b", currency="NIO", is_primary=True, status="activo")
    )

    # Accounts for Company A ("r2r") and Company B ("r2r-b")
    ar_a = Accounts(entity="r2r", code="AR-A", name="AR A", active=True, enabled=True, classification="asset")
    ar_b = Accounts(entity="r2r-b", code="AR-B", name="AR B", active=True, enabled=True, classification="asset")
    inc_a = Accounts(
        entity="r2r", code="INC-A", name="Inc A", active=True, enabled=True, classification="income", account_type="income"
    )
    inc_b = Accounts(
        entity="r2r-b", code="INC-B", name="Inc B", active=True, enabled=True, classification="income", account_type="income"
    )
    inv_a = Accounts(entity="r2r", code="INV-A", name="Inv A", active=True, enabled=True, classification="asset")
    inv_b = Accounts(entity="r2r-b", code="INV-B", name="Inv B", active=True, enabled=True, classification="asset")
    exp_a = Accounts(
        entity="r2r", code="EXP-A", name="Exp A", active=True, enabled=True, classification="expense", account_type="expense"
    )
    exp_b = Accounts(
        entity="r2r-b", code="EXP-B", name="Exp B", active=True, enabled=True, classification="expense", account_type="expense"
    )

    database.session.add_all([ar_a, ar_b, inc_a, inc_b, inv_a, inv_b, exp_a, exp_b])
    database.session.flush()

    database.session.add_all(
        [
            CompanyDefaultAccount(
                company="r2r", default_receivable=ar_a.id, default_income=inc_a.id, default_expense=exp_a.id
            ),
            CompanyDefaultAccount(
                company="r2r-b", default_receivable=ar_b.id, default_income=inc_b.id, default_expense=exp_b.id
            ),
            PartyAccount(party_id="CUST-ISO-A", company="r2r", receivable_account_id=ar_a.id),
            PartyAccount(party_id="CUST-ISO-B", company="r2r-b", receivable_account_id=ar_b.id),
        ]
    )

    from cacao_accounting.database import WarehouseCompanyAccount

    wh_a = Warehouse(code="WH-A", name="Warehouse A", company="r2r", is_active=True)
    wh_b = Warehouse(code="WH-B", name="Warehouse B", company="r2r-b", is_active=True)
    item_a = Item(code="ITEM-ISO-A", name="Item ISO A", item_type="product", is_stock_item=True, default_uom="PZA")
    item_b = Item(code="ITEM-ISO-B", name="Item ISO B", item_type="product", is_stock_item=True, default_uom="PZA")

    database.session.add_all([wh_a, wh_b, item_a, item_b])
    database.session.flush()

    database.session.add_all(
        [
            WarehouseCompanyAccount(warehouse_code="WH-A", company="r2r", inventory_account_id=inv_a.id),
            WarehouseCompanyAccount(warehouse_code="WH-B", company="r2r-b", inventory_account_id=inv_b.id),
        ]
    )
    database.session.flush()

    database.session.add_all(
        [
            ItemAccount(item_code="ITEM-ISO-A", company="r2r", income_account_id=inc_a.id, expense_account_id=exp_a.id),
            ItemAccount(item_code="ITEM-ISO-B", company="r2r-b", income_account_id=inc_b.id, expense_account_id=exp_b.id),
        ]
    )
    database.session.commit()

    # Sales Invoice in Company A
    inv_doc_a = SalesInvoice(
        company="r2r",
        posting_date=date(2026, 8, 10),
        customer_id="CUST-ISO-A",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        total=Decimal("500"),
        grand_total=Decimal("500"),
        outstanding_amount=Decimal("500"),
    )
    database.session.add(inv_doc_a)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=inv_doc_a.id, item_code="ITEM-ISO-A", qty=1, rate=500, amount=500, income_account_id=inc_a.id
        )
    )

    # Sales Invoice in Company B
    inv_doc_b = SalesInvoice(
        company="r2r-b",
        posting_date=date(2026, 8, 10),
        customer_id="CUST-ISO-B",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        total=Decimal("1200"),
        grand_total=Decimal("1200"),
        outstanding_amount=Decimal("1200"),
    )
    database.session.add(inv_doc_b)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=inv_doc_b.id, item_code="ITEM-ISO-B", qty=2, rate=600, amount=1200, income_account_id=inc_b.id
        )
    )
    database.session.commit()

    post_document_to_gl(inv_doc_a)
    post_document_to_gl(inv_doc_b)
    database.session.commit()

    # Purchase invoices in both companies must remain isolated in AP reports.
    purchase_a = PurchaseInvoice(
        company="r2r",
        posting_date=date(2026, 8, 10),
        supplier_id="SUPP-ISO-A",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
        total=Decimal("700"),
        grand_total=Decimal("700"),
        outstanding_amount=Decimal("700"),
    )
    purchase_b = PurchaseInvoice(
        company="r2r-b",
        posting_date=date(2026, 8, 10),
        supplier_id="SUPP-ISO-B",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=1,
        total=Decimal("900"),
        grand_total=Decimal("900"),
        outstanding_amount=Decimal("900"),
    )
    database.session.add_all([purchase_a, purchase_b])
    database.session.commit()

    # Stock Entry in Company A
    se_a = StockEntry(
        company="r2r", posting_date=date(2026, 8, 10), purpose="material_receipt", docstatus=1, to_warehouse="WH-A"
    )
    database.session.add(se_a)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=se_a.id,
            item_code="ITEM-ISO-A",
            target_warehouse="WH-A",
            qty=10,
            uom="PZA",
            valuation_rate=50,
            amount=500,
        )
    )

    # Stock Entry in Company B
    se_b = StockEntry(
        company="r2r-b", posting_date=date(2026, 8, 10), purpose="material_receipt", docstatus=1, to_warehouse="WH-B"
    )
    database.session.add(se_b)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=se_b.id,
            item_code="ITEM-ISO-B",
            target_warehouse="WH-B",
            qty=20,
            uom="PZA",
            valuation_rate=100,
            amount=2000,
        )
    )
    database.session.commit()

    post_document_to_gl(se_a)
    post_document_to_gl(se_b)
    database.session.commit()

    # Assert GL Entry Isolation
    gl_a = database.session.execute(database.select(GLEntry).filter_by(company="r2r")).scalars().all()
    gl_b = database.session.execute(database.select(GLEntry).filter_by(company="r2r-b")).scalars().all()

    assert all(e.company == "r2r" for e in gl_a)
    assert all(e.company == "r2r-b" for e in gl_b)
    assert sum(e.debit for e in gl_a if e.account_id == ar_a.id) == Decimal("500")
    assert sum(e.debit for e in gl_b if e.account_id == ar_b.id) == Decimal("1200")

    # Assert Subledger Isolation (AR / Semantic)
    ar_analysis_a = get_receivables_analysis(company="r2r")
    ar_analysis_b = get_receivables_analysis(company="r2r-b")

    assert [row["customer_code"] for row in ar_analysis_a if row["customer_code"] == "CUST-ISO-A"] == ["CUST-ISO-A"]
    assert [row["customer_code"] for row in ar_analysis_a if row["customer_code"] == "CUST-ISO-B"] == []
    assert [row["customer_code"] for row in ar_analysis_b if row["customer_code"] == "CUST-ISO-B"] == ["CUST-ISO-B"]
    assert [row["customer_code"] for row in ar_analysis_b if row["customer_code"] == "CUST-ISO-A"] == []

    ap_analysis_a = get_payables_analysis(company="r2r")
    ap_analysis_b = get_payables_analysis(company="r2r-b")
    assert [row["supplier_code"] for row in ap_analysis_a] == ["SUPP-ISO-A"]
    assert [row["supplier_code"] for row in ap_analysis_b] == ["SUPP-ISO-B"]

    ap_subledger_a = get_ar_ap_subledger(SubledgerFilters(company="r2r", party_type="supplier"))
    ap_subledger_b = get_ar_ap_subledger(SubledgerFilters(company="r2r-b", party_type="supplier"))
    assert ap_subledger_a.totals["outstanding_amount"] == Decimal("700")
    assert ap_subledger_b.totals["outstanding_amount"] == Decimal("900")

    # Assert Kardex / Stock Bin / Stock Ledger Isolation
    sle_a = database.session.execute(database.select(StockLedgerEntry).filter_by(company="r2r")).scalars().all()
    sle_b = database.session.execute(database.select(StockLedgerEntry).filter_by(company="r2r-b")).scalars().all()

    assert all(sle.company == "r2r" and sle.item_code == "ITEM-ISO-A" for sle in sle_a)
    assert all(sle.company == "r2r-b" and sle.item_code == "ITEM-ISO-B" for sle in sle_b)

    bin_a = database.session.execute(database.select(StockBin).filter_by(company="r2r")).scalars().all()
    bin_b = database.session.execute(database.select(StockBin).filter_by(company="r2r-b")).scalars().all()

    assert len(bin_a) == 1 and bin_a[0].actual_qty == Decimal("10")
    assert len(bin_b) == 1 and bin_b[0].actual_qty == Decimal("20")


def test_r2r_append_only_cancellation_lifecycle(app_ctx):
    """Verify that cancellations strictly execute via append-only reversals without hard row deletions."""
    from cacao_accounting.contabilidad.posting import cancel_document, post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        Item,
        ItemAccount,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    database.session.add(
        Book(code="R2R-CANC", name="R2R Cancellation", entity="r2r", currency="NIO", is_primary=True, status="activo")
    )

    ar = Accounts(entity="r2r", code="AR-CANC", name="AR Canc", active=True, enabled=True, classification="asset")
    inc = Accounts(
        entity="r2r",
        code="INC-CANC",
        name="Inc Canc",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    inv = Accounts(entity="r2r", code="INV-CANC", name="Inv Canc", active=True, enabled=True, classification="asset")
    bank_gl = Accounts(
        entity="r2r", code="BNK-CANC", name="Bank Canc", active=True, enabled=True, classification="asset", account_type="bank"
    )
    adj = Accounts(
        entity="r2r",
        code="ADJ-CANC",
        name="Adj Canc",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )

    database.session.add_all([ar, inc, inv, bank_gl, adj])
    database.session.flush()

    database.session.add_all(
        [
            CompanyDefaultAccount(
                company="r2r",
                default_receivable=ar.id,
                default_income=inc.id,
                default_bank=bank_gl.id,
                default_expense=adj.id,
                inventory_adjustment_account_id=adj.id,
            ),
            PartyAccount(party_id="CUST-CANC", company="r2r", receivable_account_id=ar.id),
        ]
    )

    wh = Warehouse(code="WH-CANC", name="WH Canc", company="r2r", is_active=True)
    item = Item(code="ITEM-CANC", name="Item Canc", item_type="product", is_stock_item=True, default_uom="PZA")
    database.session.add_all([wh, item])
    database.session.flush()

    database.session.add_all(
        [
            WarehouseCompanyAccount(warehouse_code="WH-CANC", company="r2r", inventory_account_id=inv.id),
            ItemAccount(item_code="ITEM-CANC", company="r2r", income_account_id=inc.id),
        ]
    )
    database.session.commit()

    # 1. Post and cancel Sales Invoice
    invoice = SalesInvoice(
        company="r2r",
        posting_date=date(2026, 8, 12),
        customer_id="CUST-CANC",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        total=Decimal("800"),
        grand_total=Decimal("800"),
        outstanding_amount=Decimal("800"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id, item_code="ITEM-CANC", qty=1, rate=800, amount=800, income_account_id=inc.id
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    entries_before = database.session.execute(database.select(GLEntry).filter_by(voucher_id=invoice.id)).scalars().all()
    assert len(entries_before) == 2
    assert all(not e.is_cancelled and not e.is_reversal for e in entries_before)

    # Cancel Sales Invoice
    cancel_document(invoice)
    database.session.commit()

    assert invoice.docstatus == 2
    all_entries = database.session.execute(database.select(GLEntry).filter_by(voucher_id=invoice.id)).scalars().all()
    assert len(all_entries) == 4  # 2 original + 2 append-only reversals

    cancelled_originals = [e for e in all_entries if e.is_cancelled]
    reversals = [e for e in all_entries if e.is_reversal]

    assert len(cancelled_originals) == 2
    assert len(reversals) == 2

    # Verify debit/credit swap in reversals
    orig_ar = next(e for e in cancelled_originals if e.account_id == ar.id)
    rev_ar = next(e for e in reversals if e.account_id == ar.id)
    assert orig_ar.debit == Decimal("800") and orig_ar.credit == Decimal("0")
    assert rev_ar.credit == Decimal("800") and rev_ar.debit == Decimal("0")
    assert rev_ar.reversal_of == orig_ar.id

    # 2. Post and cancel Stock Entry
    se = StockEntry(
        company="r2r", posting_date=date(2026, 8, 12), purpose="material_receipt", docstatus=1, to_warehouse="WH-CANC"
    )
    database.session.add(se)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=se.id,
            item_code="ITEM-CANC",
            target_warehouse="WH-CANC",
            qty=50,
            uom="PZA",
            valuation_rate=20,
            amount=2500,
        )
    )
    database.session.commit()

    post_document_to_gl(se)
    database.session.commit()

    bin_row = database.session.execute(database.select(StockBin).filter_by(company="r2r", item_code="ITEM-CANC")).scalar_one()
    assert bin_row.actual_qty == Decimal("50")

    sles_before = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=se.id)).scalars().all()
    assert len(sles_before) == 1
    assert sles_before[0].qty_change == Decimal("50")

    # Cancel Stock Entry
    cancel_document(se)
    database.session.commit()

    assert se.docstatus == 2
    all_sles = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=se.id)).scalars().all()
    assert len(all_sles) == 2  # 1 original cancelled + 1 reversal entry

    orig_sle = next(sle for sle in all_sles if sle.is_cancelled)
    rev_sle = next(sle for sle in all_sles if not sle.is_cancelled)

    assert orig_sle.qty_change == Decimal("50")
    assert rev_sle.qty_change == Decimal("-50")

    # Verify StockBin was adjusted back to zero via append-only ledger entries without row deletion
    bin_row_after = database.session.execute(
        database.select(StockBin).filter_by(company="r2r", item_code="ITEM-CANC")
    ).scalar_one()
    assert bin_row_after.actual_qty == Decimal("0")


def test_r2r_subledger_to_gl_reconciliation_multi_currency(app_ctx):
    """Assert exact mathematical agreement between subledger totals, reconciliation matrix, and GL control accounts."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Book,
        CompanyDefaultAccount,
        ExchangeRate,
        GLEntry,
        PartyAccount,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )
    from cacao_accounting.reportes.services import (
        ReconciliationFilters,
        SubledgerFilters,
        get_ar_ap_subledger,
        get_reconciliation_matrix,
    )

    ar = Accounts(entity="r2r", code="AR-REC", name="AR Rec", active=True, enabled=True, classification="asset")
    ap = Accounts(entity="r2r", code="AP-REC", name="AP Rec", active=True, enabled=True, classification="liability")
    inc = Accounts(
        entity="r2r", code="INC-REC", name="Inc Rec", active=True, enabled=True, classification="income", account_type="income"
    )
    exp = Accounts(
        entity="r2r",
        code="EXP-REC",
        name="Exp Rec",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )

    primary_book = Book(entity="r2r", code="R2RLOC", name="Local", currency="NIO", status="activo", is_primary=True)
    database.session.add_all([primary_book, ar, ap, inc, exp])
    database.session.flush()

    database.session.add_all(
        [
            CompanyDefaultAccount(
                company="r2r", default_receivable=ar.id, default_payable=ap.id, default_income=inc.id, default_expense=exp.id
            ),
            PartyAccount(party_id="CUST-REC", company="r2r", receivable_account_id=ar.id),
            PartyAccount(party_id="SUPP-REC", company="r2r", payable_account_id=ap.id),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 8, 15)),
        ]
    )
    database.session.commit()

    # Post USD Sales Invoice ($100 = NIO 3600)
    si = SalesInvoice(
        company="r2r",
        posting_date=date(2026, 8, 15),
        customer_id="CUST-REC",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("3600"),
        base_grand_total=Decimal("3600"),
        outstanding_amount=Decimal("100"),
        base_outstanding_amount=Decimal("3600"),
    )
    database.session.add(si)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=si.id,
            item_code="ITEM-REC",
            qty=1,
            rate=100,
            amount=100,
            base_amount=3600,
            income_account_id=inc.id,
        )
    )

    # Post USD Purchase Invoice ($200 = NIO 7200)
    pi = PurchaseInvoice(
        company="r2r",
        posting_date=date(2026, 8, 15),
        supplier_id="SUPP-REC",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36"),
        docstatus=1,
        total=Decimal("200"),
        grand_total=Decimal("200"),
        base_total=Decimal("7200"),
        base_grand_total=Decimal("7200"),
        outstanding_amount=Decimal("200"),
        base_outstanding_amount=Decimal("7200"),
    )
    database.session.add(pi)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=pi.id,
            item_code="ITEM-REC",
            qty=1,
            rate=200,
            amount=200,
            base_amount=7200,
            expense_account_id=exp.id,
        )
    )
    database.session.commit()

    post_document_to_gl(si)
    post_document_to_gl(pi)
    database.session.commit()

    # 1. Check Subledgers
    ar_sub = get_ar_ap_subledger(SubledgerFilters(company="r2r", party_type="customer", as_of_date=date(2026, 8, 15)))
    ap_sub = get_ar_ap_subledger(SubledgerFilters(company="r2r", party_type="supplier", as_of_date=date(2026, 8, 15)))

    assert ar_sub.totals["outstanding_amount"] == Decimal("3600")
    assert ap_sub.totals["outstanding_amount"] == Decimal("7200")

    # 2. Reconcile with GL Control Accounts
    gl_ar_balance = database.session.execute(
        database.select(database.func.sum(GLEntry.debit - GLEntry.credit)).filter_by(company="r2r", account_id=ar.id)
    ).scalar() or Decimal("0")

    gl_ap_balance = database.session.execute(
        database.select(database.func.sum(GLEntry.credit - GLEntry.debit)).filter_by(company="r2r", account_id=ap.id)
    ).scalar() or Decimal("0")

    assert ar_sub.totals["outstanding_amount"] == gl_ar_balance
    assert ap_sub.totals["outstanding_amount"] == gl_ap_balance

    # 3. Check Reconciliation Matrix Report
    primary_book = database.session.execute(database.select(Book).filter_by(entity="r2r", is_primary=True)).scalars().first()
    matrix = get_reconciliation_matrix(
        ReconciliationFilters(company="r2r", ledger=primary_book.code if primary_book else None, as_of_date=date(2026, 8, 15))
    )

    ar_row = next(row for row in matrix.rows if row.values["area"] == "AR")
    ap_row = next(row for row in matrix.rows if row.values["area"] == "AP")

    assert ar_row.values["subledger_amount"] == Decimal("3600")
    assert ar_row.values["gl_control_amount"] == Decimal("3600")
    assert ar_row.values["status"] == "reconciled"

    assert ap_row.values["subledger_amount"] == Decimal("-7200")
    assert ap_row.values["gl_control_amount"] == Decimal("-7200")
    assert ap_row.values["status"] == "reconciled"


def test_r2r_kardex_inventory_valuation_and_moving_average(app_ctx):
    """Verify StockBin, StockLedgerEntry, and StockValuationLayer moving average calculations and GL synchronization."""
    from cacao_accounting.contabilidad.posting import post_delivery_note, post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        DeliveryNote,
        DeliveryNoteItem,
        GLEntry,
        Item,
        ItemAccount,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    database.session.add(
        Book(code="R2R-KARD", name="R2R Kardex", entity="r2r", currency="NIO", is_primary=True, status="activo")
    )

    inv_acc = Accounts(entity="r2r", code="INV-KARD", name="Inv Kardex", active=True, enabled=True, classification="asset")
    cogs_acc = Accounts(
        entity="r2r",
        code="COGS-KARD",
        name="COGS Kardex",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    adj_acc = Accounts(
        entity="r2r",
        code="ADJ-KARD",
        name="Adj Kardex",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )

    database.session.add_all([inv_acc, cogs_acc, adj_acc])
    database.session.flush()

    database.session.add_all(
        [
            CompanyDefaultAccount(
                company="r2r", default_expense=adj_acc.id, inventory_adjustment_account_id=adj_acc.id, default_cogs=cogs_acc.id
            ),
        ]
    )

    wh = Warehouse(code="WH-KARD", name="WH Kardex", company="r2r", is_active=True)
    item = Item(code="ITEM-KARD", name="Item Kardex", item_type="product", is_stock_item=True, default_uom="PZA")
    database.session.add_all([wh, item])
    database.session.flush()

    database.session.add_all(
        [
            WarehouseCompanyAccount(warehouse_code="WH-KARD", company="r2r", inventory_account_id=inv_acc.id),
            ItemAccount(item_code="ITEM-KARD", company="r2r", expense_account_id=cogs_acc.id),
        ]
    )
    database.session.commit()

    # 1. Receipt 1: 10 units @ 100 NIO = 1000 NIO
    se1 = StockEntry(
        company="r2r", posting_date=date(2026, 8, 16), purpose="material_receipt", docstatus=1, to_warehouse="WH-KARD"
    )
    database.session.add(se1)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=se1.id,
            item_code="ITEM-KARD",
            target_warehouse="WH-KARD",
            qty=10,
            uom="PZA",
            valuation_rate=100,
            amount=1000,
        )
    )
    database.session.commit()

    post_document_to_gl(se1)
    database.session.commit()

    bin1 = database.session.execute(database.select(StockBin).filter_by(company="r2r", item_code="ITEM-KARD")).scalar_one()
    assert bin1.actual_qty == Decimal("10")
    assert bin1.stock_value == Decimal("1000")
    assert bin1.valuation_rate == Decimal("100")

    # 2. Receipt 2: 10 units @ 200 NIO = 2000 NIO (Total stock = 20 units, Total value = 3000 NIO, Avg rate = 150 NIO)
    se2 = StockEntry(
        company="r2r", posting_date=date(2026, 8, 17), purpose="material_receipt", docstatus=1, to_warehouse="WH-KARD"
    )
    database.session.add(se2)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=se2.id,
            item_code="ITEM-KARD",
            target_warehouse="WH-KARD",
            qty=10,
            uom="PZA",
            valuation_rate=200,
            amount=2000,
        )
    )
    database.session.commit()

    post_document_to_gl(se2)
    database.session.commit()

    bin2 = database.session.execute(database.select(StockBin).filter_by(company="r2r", item_code="ITEM-KARD")).scalar_one()
    assert bin2.actual_qty == Decimal("20")
    assert bin2.stock_value == Decimal("3000")
    assert bin2.valuation_rate == Decimal("150")

    # 3. Delivery Note: 5 units delivered. Expected COGS = 5 * 150 = 750 NIO.
    dn = DeliveryNote(company="r2r", posting_date=date(2026, 8, 18), docstatus=1)
    database.session.add(dn)
    database.session.flush()
    dn_item = DeliveryNoteItem(
        delivery_note_id=dn.id, item_code="ITEM-KARD", warehouse="WH-KARD", qty=5, uom="PZA", rate=250, amount=1250
    )
    database.session.add(dn_item)
    database.session.commit()

    post_delivery_note(dn)
    database.session.commit()

    bin3 = database.session.execute(database.select(StockBin).filter_by(company="r2r", item_code="ITEM-KARD")).scalar_one()
    assert bin3.actual_qty == Decimal("15")
    assert bin3.stock_value == Decimal("2250")
    assert bin3.valuation_rate == Decimal("150")

    # Verify Stock Ledger Entry for Delivery
    sle_dn = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=dn.id)).scalar_one()
    assert sle_dn.qty_change == Decimal("-5")
    assert sle_dn.valuation_rate == Decimal("150")
    assert sle_dn.stock_value_difference == Decimal("-750")

    # Verify GL Entries for Delivery Note (Dr COGS 750, Cr Inventory 750)
    dn_gls = database.session.execute(database.select(GLEntry).filter_by(voucher_id=dn.id)).scalars().all()
    assert len(dn_gls) == 2
    cogs_gl = next(g for g in dn_gls if g.account_id == cogs_acc.id)
    inv_gl = next(g for g in dn_gls if g.account_id == inv_acc.id)

    assert cogs_gl.debit == Decimal("750") and cogs_gl.credit == Decimal("0")
    assert inv_gl.credit == Decimal("750") and inv_gl.debit == Decimal("0")
