# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


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
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"))
        database.session.commit()
        yield app


def test_purchase_reconciliation_line_matching_supports_partial_and_completion(app_ctx):
    from cacao_accounting.compras.purchase_reconciliation_service import (
        get_purchase_reconciliation_pending,
        reconcile_purchase_invoice,
    )
    from cacao_accounting.database import (
        PurchaseReconciliationItem,
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(code="ITEM-GR8", name="Item GR8", item_type="goods", is_stock_item=True, default_uom="EA"),
            Warehouse(code="WH-GR8", name="Bodega GR8", company="cacao"),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-8", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-GR8",
            item_name="Item GR8",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="EA",
            rate=Decimal("5.00"),
            amount=Decimal("50.00"),
            warehouse="WH-GR8",
        )
    )
    invoices = []
    for qty in (Decimal("4"), Decimal("6")):
        invoice = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 2),
            supplier_id="SUPP-8",
            purchase_receipt_id=receipt.id,
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code="ITEM-GR8",
                item_name="Item GR8",
                qty=qty,
                uom="EA",
                rate=Decimal("5.00"),
                amount=qty * Decimal("5.00"),
                warehouse="WH-GR8",
            )
        )
        invoices.append(invoice)
    database.session.commit()

    first = reconcile_purchase_invoice(invoices[0].id)
    assert first.matched_qty == Decimal("4.000000000")
    assert get_purchase_reconciliation_pending("cacao")[0].pending_qty == Decimal("6.000000000")

    second = reconcile_purchase_invoice(invoices[1].id)
    database.session.commit()
    assert second.matched_qty == Decimal("6.000000000")
    assert get_purchase_reconciliation_pending("cacao") == []
    assert database.session.execute(database.select(PurchaseReconciliationItem)).scalars().all()


def test_purchase_reconciliation_rejects_overbilling_and_price_difference(app_ctx):
    from cacao_accounting.compras.purchase_reconciliation_service import reconcile_purchase_invoice
    from cacao_accounting.database import (
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        PurchaseReconciliation,
        PurchaseReconciliationItem,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(code="ITEM-GR9", name="Item GR9", item_type="goods", is_stock_item=True, default_uom="EA"),
            Warehouse(code="WH-GR9", name="Bodega GR9", company="cacao"),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-9", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-GR9",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="EA",
            rate=Decimal("5.00"),
            amount=Decimal("10.00"),
            warehouse="WH-GR9",
        )
    )
    invoice = PurchaseInvoice(
        company="cacao", posting_date=date(2026, 5, 2), supplier_id="SUPP-9", purchase_receipt_id=receipt.id, docstatus=1
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-GR9",
            qty=Decimal("3"),
            uom="EA",
            rate=Decimal("5.00"),
            amount=Decimal("15.00"),
            warehouse="WH-GR9",
        )
    )
    database.session.commit()

    result = reconcile_purchase_invoice(invoice.id)
    database.session.commit()

    reconciliation = database.session.execute(
        database.select(PurchaseReconciliation).filter_by(id=result.reconciliation_id)
    ).scalar_one()
    items = (
        database.session.execute(
            database.select(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=reconciliation.id)
        )
        .scalars()
        .all()
    )

    assert result.matching_result == "MATCH_FAILED"
    assert reconciliation.status == "disputed"
    assert items == []

    valid_invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 3),
        supplier_id="SUPP-9",
        purchase_receipt_id=receipt.id,
        docstatus=1,
    )
    database.session.add(valid_invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=valid_invoice.id,
            item_code="ITEM-GR9",
            qty=Decimal("2"),
            uom="EA",
            rate=Decimal("5.00"),
            amount=Decimal("10.00"),
            warehouse="WH-GR9",
        )
    )
    database.session.commit()

    valid_result = reconcile_purchase_invoice(valid_invoice.id)
    assert valid_result.matching_result == "MATCH_OK"


def test_bank_reconciliation_supports_partial_and_rejects_duplicates(app_ctx):
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationError,
        BankReconciliationMatch,
        BankReconciliationRequest,
        reconcile_bank_items,
    )
    from cacao_accounting.database import Bank, BankAccount, BankTransaction, PaymentEntry, ReconciliationItem, database

    bank = Bank(name="Banco")
    database.session.add(bank)
    database.session.flush()
    bank_account = BankAccount(bank_id=bank.id, company="cacao", account_name="Cuenta")
    database.session.add(bank_account)
    database.session.flush()
    transaction = BankTransaction(bank_account_id=bank_account.id, posting_date=date(2026, 5, 5), deposit=Decimal("100.00"))
    payment_a = PaymentEntry(
        company="cacao", posting_date=date(2026, 5, 5), payment_type="receive", received_amount=Decimal("60.00"), docstatus=1
    )
    payment_b = PaymentEntry(
        company="cacao", posting_date=date(2026, 5, 5), payment_type="receive", received_amount=Decimal("40.00"), docstatus=1
    )
    database.session.add_all([transaction, payment_a, payment_b])
    database.session.commit()

    reconcile_bank_items(
        BankReconciliationRequest(
            company="cacao",
            reconciliation_date=date(2026, 5, 5),
            matches=[
                BankReconciliationMatch(transaction.id, "payment_entry", payment_a.id, Decimal("60.00")),
                BankReconciliationMatch(transaction.id, "payment_entry", payment_b.id, Decimal("40.00")),
            ],
        )
    )
    database.session.commit()

    items = database.session.execute(database.select(ReconciliationItem)).scalars().all()
    assert transaction.is_reconciled is True
    assert sum(item.allocated_amount for item in items) == Decimal("100.00")
    with pytest.raises(BankReconciliationError, match="excede"):
        reconcile_bank_items(
            BankReconciliationRequest(
                company="cacao",
                reconciliation_date=date(2026, 5, 5),
                matches=[BankReconciliationMatch(transaction.id, "payment_entry", payment_a.id, Decimal("1.00"))],
            )
        )


def test_reports_return_subledger_aging_kardex_and_reconciliations(app_ctx):
    from cacao_accounting.database import PaymentReference, SalesInvoice, StockLedgerEntry, database
    from cacao_accounting.reportes.services import (
        AgingFilters,
        KardexFilters,
        SubledgerFilters,
        get_aging_report,
        get_ar_ap_subledger,
        get_kardex,
        get_reconciliation_report,
    )

    invoice = SalesInvoice(company="cacao", posting_date=date(2026, 4, 1), customer_id="CUST-R", grand_total=Decimal("100.00"))
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PaymentReference(
            payment_id="PAY-R",
            reference_type="sales_invoice",
            reference_id=invoice.id,
            allocated_amount=Decimal("25.00"),
            allocation_date=date(2026, 4, 15),
        )
    )
    database.session.add(
        StockLedgerEntry(
            posting_date=date(2026, 5, 1),
            item_code="ITEM-R",
            warehouse="WH-R",
            company="cacao",
            qty_change=Decimal("3"),
            qty_after_transaction=Decimal("3"),
            valuation_rate=Decimal("2.00"),
            stock_value_difference=Decimal("6.00"),
            stock_value=Decimal("6.00"),
            voucher_type="seed",
            voucher_id="seed-r",
        )
    )
    database.session.commit()

    subledger = get_ar_ap_subledger(SubledgerFilters(company="cacao", party_type="customer", as_of_date=date(2026, 5, 5)))
    aging = get_aging_report(AgingFilters(company="cacao", party_type="customer", as_of_date=date(2026, 5, 5)))
    kardex = get_kardex(KardexFilters(company="cacao", item_code="ITEM-R"))
    reconciliations = get_reconciliation_report(company="cacao")

    assert subledger.totals["outstanding_amount"] == Decimal("75.00")
    assert aging.totals["31_60"] == Decimal("75.00")
    assert kardex.totals["incoming_qty"] == Decimal("3.000000000")
    assert reconciliations.totals["bank_reconciled_amount"] == Decimal("0")


def test_financial_reports_framework_uses_gl_and_supports_export(app_ctx):
    from cacao_accounting.database import (
        AccountingPeriod,
        Accounts,
        Book,
        FiscalYear,
        GLEntry,
        Modules,
        User,
        database,
    )
    from cacao_accounting.reportes.services import (
        FinancialReportFilters,
        get_account_movement_detail,
        get_balance_sheet_report,
        get_income_statement_report,
        get_trial_balance_report,
    )

    fiscal_year = FiscalYear(
        entity="cacao",
        name="2026",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
        is_closed=False,
    )
    database.session.add(fiscal_year)
    database.session.flush()
    period_apr = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="2026-04",
        enabled=True,
        is_closed=False,
        start=date(2026, 4, 1),
        end=date(2026, 4, 30),
    )
    period_may = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="2026-05",
        enabled=True,
        is_closed=False,
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
    )
    book = Book(code="FISC", name="Fiscal", entity="cacao", currency="NIO", is_primary=True, default=True)
    accounts = [
        Accounts(entity="cacao", code="1.01.01", name="Caja", active=True, enabled=True, classification="Activo"),
        Accounts(entity="cacao", code="3.01.01", name="Capital", active=True, enabled=True, classification="Patrimonio"),
        Accounts(entity="cacao", code="4.01.01", name="Ventas", active=True, enabled=True, classification="Ingresos"),
        Accounts(entity="cacao", code="5.01.01", name="Gastos", active=True, enabled=True, classification="Gastos"),
    ]
    database.session.add_all([period_apr, period_may, book, *accounts])
    database.session.flush()
    cash, equity, income, expense = accounts

    database.session.add_all(
        [
            GLEntry(
                posting_date=date(2026, 4, 30),
                company="cacao",
                ledger_id=book.id,
                account_id=cash.id,
                account_code=cash.code,
                debit=Decimal("50.00"),
                credit=Decimal("0"),
                voucher_type="journal_entry",
                voucher_id="OPEN-1",
                document_no="cacao-JOU-2026-04-00001",
                accounting_period_id=period_apr.id,
            ),
            GLEntry(
                posting_date=date(2026, 4, 30),
                company="cacao",
                ledger_id=book.id,
                account_id=equity.id,
                account_code=equity.code,
                debit=Decimal("0"),
                credit=Decimal("50.00"),
                voucher_type="journal_entry",
                voucher_id="OPEN-1",
                document_no="cacao-JOU-2026-04-00001",
                accounting_period_id=period_apr.id,
            ),
            GLEntry(
                posting_date=date(2026, 5, 5),
                company="cacao",
                ledger_id=book.id,
                account_id=cash.id,
                account_code=cash.code,
                debit=Decimal("100.00"),
                credit=Decimal("0"),
                voucher_type="sales_invoice",
                voucher_id="SI-1",
                document_no="cacao-JOU-2026-05-00001",
                accounting_period_id=period_may.id,
            ),
            GLEntry(
                posting_date=date(2026, 5, 5),
                company="cacao",
                ledger_id=book.id,
                account_id=income.id,
                account_code=income.code,
                debit=Decimal("0"),
                credit=Decimal("100.00"),
                voucher_type="sales_invoice",
                voucher_id="SI-1",
                document_no="cacao-JOU-2026-05-00001",
                accounting_period_id=period_may.id,
            ),
            GLEntry(
                posting_date=date(2026, 5, 12),
                company="cacao",
                ledger_id=book.id,
                account_id=expense.id,
                account_code=expense.code,
                debit=Decimal("30.00"),
                credit=Decimal("0"),
                voucher_type="journal_entry",
                voucher_id="JE-2",
                document_no="cacao-JOU-2026-05-00002",
                accounting_period_id=period_may.id,
            ),
            GLEntry(
                posting_date=date(2026, 5, 12),
                company="cacao",
                ledger_id=book.id,
                account_id=cash.id,
                account_code=cash.code,
                debit=Decimal("0"),
                credit=Decimal("30.00"),
                voucher_type="journal_entry",
                voucher_id="JE-2",
                document_no="cacao-JOU-2026-05-00002",
                accounting_period_id=period_may.id,
            ),
        ]
    )
    accounting_module = Modules(module="accounting", default=True, enabled=True)
    report_user = User(user="report-user", name="Report User", password=b"x", classification="admin", active=True)
    database.session.add_all([accounting_module, report_user])
    database.session.commit()

    filters = FinancialReportFilters(
        company="cacao",
        ledger="FISC",
        accounting_period="2026-05",
        include_running_balance=True,
        page=1,
        page_size=10,
        voucher_number="2026-05",
    )
    movement = get_account_movement_detail(filters)
    movement_page_two = get_account_movement_detail(
        FinancialReportFilters(
            company="cacao",
            ledger="FISC",
            accounting_period="2026-05",
            account_code="1.01.01",
            include_running_balance=True,
            page=2,
            page_size=1,
            voucher_number="2026-05",
        )
    )
    trial_balance = get_trial_balance_report(
        FinancialReportFilters(company="cacao", ledger="FISC", accounting_period="2026-05")
    )
    income_statement = get_income_statement_report(
        FinancialReportFilters(company="cacao", ledger="FISC", accounting_period="2026-05")
    )
    balance_sheet = get_balance_sheet_report(
        FinancialReportFilters(company="cacao", ledger="FISC", accounting_period="2026-05")
    )

    assert movement.total_rows == 4
    assert movement.totals["difference"] == Decimal("0")
    cash_running_balances = [
        row.values.get("running_balance")
        for row in movement.rows
        if row.values.get("account_code") == "1.01.01" and "running_balance" in row.values
    ]
    assert cash_running_balances == [Decimal("100.0000"), Decimal("70.0000")]
    assert movement_page_two.rows[0].values.get("running_balance") == Decimal("70.0000")
    assert trial_balance.totals["debit"] == Decimal("130.00")
    assert trial_balance.totals["credit"] == Decimal("130.00")
    assert income_statement.totals["net_profit"] == Decimal("70.00")
    assert balance_sheet.totals["difference"] == Decimal("0.00")

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = report_user.id
        session["_fresh"] = True
    response = client.get("/reports/account-movement?company=cacao&ledger=FISC&accounting_period=2026-05&export=csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    html_response = client.get("/reports/account-movement?company=cacao&ledger=FISC&accounting_period=2026-05")
    html = html_response.get_data(as_text=True)
    assert html_response.status_code == 200
    assert 'doctype: "company"' in html
    assert 'doctype: "book"' in html
    assert 'doctype: "accounting_period"' in html
    assert 'doctype: "document_no"' in html
    response_xlsx = client.get("/reports/account-movement?company=cacao&ledger=FISC&accounting_period=2026-05&export=xlsx")
    assert response_xlsx.status_code == 200
    assert response_xlsx.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    workbook = load_workbook(BytesIO(response_xlsx.data))
    assert "Filtros" in workbook.sheetnames
    assert workbook.active.freeze_panes == "A5"
    filters_sheet = workbook["Filtros"]
    filter_rows = [row for row in filters_sheet.iter_rows(min_row=2, max_col=2, values_only=True) if row[0]]
    assert any("Company" in str(row[0]) for row in filter_rows)
    assert any(str(row[1]) == "cacao" for row in filter_rows)


def test_financial_report_view_persistence_and_column_selection(app_ctx):
    from cacao_accounting.database import Modules, User, UserFormPreference, database

    accounting_module = Modules(module="accounting", default=True, enabled=True)
    report_user = User(user="report-view-user", name="Report View User", password=b"x", classification="admin", active=True)
    database.session.add_all([accounting_module, report_user])
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = report_user.id
        session["_fresh"] = True

    response_save = client.get(
        "/reports/account-movement?company=cacao&ledger=FISC&saved_view=vista-mensual&view_action=save&visible_columns=posting_date&visible_columns=account_code"
    )
    assert response_save.status_code == 200
    preference = database.session.execute(
        database.select(UserFormPreference).filter_by(
            user_id=report_user.id,
            form_key="reports.financial.account-movement",
            view_key="vista-mensual",
        )
    ).scalar_one()
    assert "posting_date" in preference.config_json

    response_apply = client.get(
        "/reports/account-movement?company=cacao&ledger=FISC&saved_view=vista-mensual&view_action=apply"
    )
    assert response_apply.status_code == 200
    html = response_apply.get_data(as_text=True)
    assert "vista-mensual" in html
    assert "Reference Type" in html
    assert "Is Reversal" in html
    assert ">reference_type<" not in html
    assert ">is_reversal<" not in html


def test_financial_report_filters_prefill_and_hide_columns_for_summary_reports(app_ctx):
    from cacao_accounting.database import AccountingPeriod, Book, FiscalYear, Modules, User, database

    accounting_module = Modules(module="accounting", default=True, enabled=True)
    report_user = User(
        user="report-filter-user", name="Report Filter User", password=b"x", classification="admin", active=True
    )
    fiscal_year = FiscalYear(
        entity="cacao",
        name="FY-2026",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    database.session.add_all([accounting_module, report_user, fiscal_year])
    database.session.flush()
    database.session.add_all(
        [
            Book(entity="cacao", code="FISC", name="Fiscal", currency="NIO", is_primary=True, default=True),
            AccountingPeriod(
                entity="cacao",
                fiscal_year_id=fiscal_year.id,
                name="2026-05",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                enabled=True,
                is_closed=False,
            ),
        ]
    )
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = report_user.id
        session["_fresh"] = True

    summary_response = client.get("/reports/trial-balance")
    summary_html = summary_response.get_data(as_text=True)
    detail_response = client.get("/reports/account-movement")
    detail_html = detail_response.get_data(as_text=True)

    assert summary_response.status_code == 200
    assert 'initialValue: "FISC"' in summary_html
    assert 'initialValue: "2026-05"' in summary_html
    assert "Columnas visibles" not in summary_html
    assert 'data-bs-target="#saveViewModal">Guardar vista' not in summary_html
    assert 'name="view_action" value="reset">Eliminar vista' not in summary_html
    assert 'x-show="advanced" x-cloak' in summary_html
    assert detail_response.status_code == 200
    assert "Columnas visibles" in detail_html


def test_financial_report_can_group_by_voucher_type_when_column_is_hidden(app_ctx):
    from cacao_accounting.database import Accounts, AccountingPeriod, Book, FiscalYear, GLEntry, Modules, User, database

    accounting_module = Modules(module="accounting", default=True, enabled=True)
    report_user = User(user="report-group-user", name="Report Group User", password=b"x", classification="admin", active=True)
    fiscal_year = FiscalYear(
        entity="cacao",
        name="FY-2026-G",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    book = Book(entity="cacao", code="FISC", name="Fiscal", currency="NIO", is_primary=True, default=True)
    account = Accounts(entity="cacao", code="1.01.99", name="Caja Grupo", active=True, enabled=True)
    offset = Accounts(entity="cacao", code="3.01.99", name="Capital Grupo", active=True, enabled=True)
    database.session.add_all([accounting_module, report_user, fiscal_year, book, account, offset])
    database.session.flush()
    period = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="2026-05",
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        enabled=True,
        is_closed=False,
    )
    database.session.add(period)
    database.session.flush()
    database.session.add_all(
        [
            GLEntry(
                posting_date=date(2026, 5, 8),
                company="cacao",
                ledger_id=book.id,
                accounting_period_id=period.id,
                account_id=account.id,
                account_code=account.code,
                debit=Decimal("10.00"),
                credit=Decimal("0"),
                voucher_type="journal_entry",
                voucher_id="JE-G",
                document_no="JE-G",
            ),
            GLEntry(
                posting_date=date(2026, 5, 8),
                company="cacao",
                ledger_id=book.id,
                accounting_period_id=period.id,
                account_id=offset.id,
                account_code=offset.code,
                debit=Decimal("0"),
                credit=Decimal("10.00"),
                voucher_type="journal_entry",
                voucher_id="JE-G",
                document_no="JE-G",
            ),
        ]
    )
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = report_user.id
        session["_fresh"] = True

    response = client.get(
        "/reports/account-movement?apply_filters=1&company=cacao&ledger=FISC&accounting_period=2026-05"
        "&group_by=voucher_type&visible_columns=posting_date&visible_columns=account_code&visible_columns=debit"
        "&visible_columns=credit"
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Voucher Type: journal_entry" in html
    assert "Subtotal" in html


def test_search_select_party_type_labels_and_party_filter(app_ctx):
    from cacao_accounting.database import CompanyParty, Modules, Party, User, database

    user = User(user="party-filter-user", name="Party Filter User", password=b"x", classification="admin", active=True)
    database.session.add_all(
        [
            Modules(module="accounting", default=True, enabled=True),
            user,
            Party(id="SUPP-F", party_type="supplier", name="Proveedor F", tax_id="SUPP-F", is_active=True),
            Party(id="CUST-F", party_type="customer", name="Cliente F", tax_id="CUST-F", is_active=True),
            CompanyParty(company="cacao", party_id="SUPP-F", is_active=True),
            CompanyParty(company="cacao", party_id="CUST-F", is_active=True),
        ]
    )
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True

    party_type_payload = client.get("/api/search-select?doctype=party_type&q=prove").json
    supplier_payload = client.get("/api/search-select?doctype=party&q=Proveedor&company=cacao&party_type=supplier").json

    assert party_type_payload["results"][0]["value"] == "supplier"
    assert party_type_payload["results"][0]["display_name"] == "Proveedor"
    assert [item["value"] for item in supplier_payload["results"]] == ["SUPP-F"]


def test_trial_balance_uses_tree_presentation_without_level_column(app_ctx):
    from cacao_accounting.database import (
        Accounts,
        AccountingPeriod,
        Book,
        FiscalYear,
        GLEntry,
        Modules,
        User,
        database,
    )

    accounting_module = Modules(module="accounting", default=True, enabled=True)
    report_user = User(user="trial-tree-user", name="Trial Tree User", password=b"x", classification="admin", active=True)
    fiscal_year = FiscalYear(
        entity="cacao",
        name="FY-2026",
        year_start_date=date(2026, 1, 1),
        year_end_date=date(2026, 12, 31),
    )
    book = Book(entity="cacao", code="FISC", name="Fiscal", currency="NIO", is_primary=True, default=True)
    period = AccountingPeriod(
        entity="cacao",
        fiscal_year_id=fiscal_year.id,
        name="2026-05",
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
        enabled=True,
        is_closed=False,
    )
    database.session.add_all([accounting_module, report_user, fiscal_year, book])
    database.session.flush()
    period.fiscal_year_id = fiscal_year.id
    database.session.add(period)
    account_parent = Accounts(
        entity="cacao",
        code="1.01",
        name="Activo Corriente",
        active=True,
        enabled=True,
        account_type="asset",
        classification="activo",
    )
    account_leaf = Accounts(
        entity="cacao",
        code="1.01.001",
        name="Caja",
        active=True,
        enabled=True,
        account_type="cash",
        classification="activo",
    )
    database.session.add_all([account_parent, account_leaf])
    database.session.flush()
    database.session.add_all(
        [
            GLEntry(
                posting_date=date(2026, 5, 1),
                company="cacao",
                ledger_id=book.id,
                accounting_period_id=period.id,
                account_id=account_leaf.id,
                account_code=account_leaf.code,
                debit=Decimal("120.00"),
                credit=Decimal("0"),
                voucher_type="journal_entry",
                voucher_id="TREE-1",
                document_no="TREE-1",
            ),
            GLEntry(
                posting_date=date(2026, 5, 1),
                company="cacao",
                ledger_id=book.id,
                accounting_period_id=period.id,
                account_id=account_leaf.id,
                account_code=account_leaf.code,
                debit=Decimal("0"),
                credit=Decimal("120.00"),
                voucher_type="journal_entry",
                voucher_id="TREE-1",
                document_no="TREE-1",
            ),
        ]
    )
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = report_user.id
        session["_fresh"] = True

    response = client.get("/reports/trial-balance?apply_filters=1&company=cacao&ledger=FISC&accounting_period=2026-05")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Activo Corriente" in html
    assert "Caja" in html
    assert "Level" not in html
    assert "ca-tree-toggle" in html


def test_tax_template_posts_sales_tax_and_price_suggestion(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        GLEntry,
        ItemPrice,
        PartyAccount,
        PriceList,
        SalesInvoice,
        SalesInvoiceItem,
        Tax,
        TaxTemplate,
        TaxTemplateItem,
        database,
    )
    from cacao_accounting.tax_pricing_service import get_item_price, validate_price_tolerance

    receivable = Accounts(entity="cacao", code="AR-T", name="AR", active=True, enabled=True, account_type="receivable")
    income = Accounts(entity="cacao", code="INC-T", name="Ingreso", active=True, enabled=True, account_type="income")
    tax_account = Accounts(entity="cacao", code="TAX-T", name="IVA", active=True, enabled=True, account_type="liability")
    database.session.add_all([receivable, income, tax_account])
    database.session.flush()
    template = TaxTemplate(name="IVA Ventas", company="cacao", template_type="selling")
    tax = Tax(name="IVA 15", rate=Decimal("15.00"), tax_type="percentage", applies_to="sales", account_id=tax_account.id)
    price_list = PriceList(name="Ventas", company="cacao", currency="NIO", is_selling=True)
    database.session.add_all([template, tax, price_list])
    database.session.flush()
    database.session.add_all(
        [
            TaxTemplateItem(tax_template_id=template.id, tax_id=tax.id, sequence=1, behavior="additive"),
            PartyAccount(party_id="CUST-T", company="cacao", receivable_account_id=receivable.id),
            ItemPrice(item_code="ITEM-T", price_list_id=price_list.id, uom="EA", price=Decimal("100.00")),
        ]
    )
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 5),
        customer_id="CUST-T",
        tax_template_id=template.id,
        total=Decimal("100.00"),
        grand_total=Decimal("115.00"),
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    line = SalesInvoiceItem(
        sales_invoice_id=invoice.id,
        item_code="ITEM-T",
        qty=Decimal("1"),
        uom="EA",
        rate=Decimal("100.00"),
        amount=Decimal("100.00"),
        income_account_id=income.id,
    )
    database.session.add(line)
    database.session.commit()

    post_document_to_gl(invoice)
    suggestion = get_item_price("ITEM-T", price_list.id, Decimal("1"), "EA", date(2026, 5, 5))
    line.suggested_rate = suggestion.price
    tolerance = validate_price_tolerance("sales_invoice", line, None)
    entries = database.session.execute(database.select(GLEntry)).scalars().all()

    assert suggestion.price == Decimal("100.0000")
    assert tolerance.allowed is True
    assert sum(entry.debit for entry in entries) == Decimal("115.0000")
    assert sum(entry.credit for entry in entries) == Decimal("115.0000")
    assert any(entry.account_id == tax_account.id and entry.credit == Decimal("15.0000") for entry in entries)


def test_catalog_loader_accepts_spanish_and_english_headers(app_ctx, tmp_path):
    from cacao_accounting.contabilidad.ctas import CatalogoCtas, cargar_catalogos
    from cacao_accounting.database import Accounts, Entity, database

    database.session.add(Entity(code="eng", name="English", company_name="English", tax_id="J-ENG", currency="NIO"))
    database.session.commit()

    english_catalog = tmp_path / "english.csv"
    english_catalog.write_text(
        "code,name,parent,group,classification,type,account_type\n"
        "1,Assets,,true,Asset,,\n"
        "1.01,Bank,1,false,Asset,,bank\n",
        encoding="utf-8",
    )
    cargar_catalogos(CatalogoCtas(file=str(english_catalog), pais=None, idioma="EN"), "eng")
    database.session.commit()

    account = database.session.execute(database.select(Accounts).filter_by(entity="eng", code="1.01")).scalar_one()
    assert account.account_type == "bank"
    assert account.group is False


def test_base_catalog_mapping_covers_required_default_accounts(app_ctx):
    import csv
    import json
    from pathlib import Path

    from cacao_accounting.contabilidad.default_accounts import DEFAULT_ACCOUNT_FIELDS

    catalog_path = Path("cacao_accounting/contabilidad/ctas/catalogos/base_es.csv")
    mapping_path = Path("cacao_accounting/contabilidad/ctas/catalogos/base_es.json")
    rows = list(csv.DictReader(catalog_path.open(encoding="utf-8")))
    codes = {row["codigo"] for row in rows}
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))["default_accounts"]

    assert set(DEFAULT_ACCOUNT_FIELDS) == set(mapping)
    assert all(code in codes for code in mapping.values())
    assert len(codes) == len(rows)

    catalog_path_en = Path("cacao_accounting/contabilidad/ctas/catalogos/base_en.csv")
    mapping_path_en = Path("cacao_accounting/contabilidad/ctas/catalogos/base_en.json")
    rows_en = list(csv.DictReader(catalog_path_en.open(encoding="utf-8")))
    codes_en = {row["codigo"] for row in rows_en}
    mapping_en = json.loads(mapping_path_en.read_text(encoding="utf-8"))["default_accounts"]

    assert set(DEFAULT_ACCOUNT_FIELDS) == set(mapping_en)
    assert all(code in codes_en for code in mapping_en.values())
    assert len(codes_en) == len(rows_en)


def test_setup_with_predefined_catalog_creates_complete_company_defaults(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DEFAULT_ACCOUNT_FIELDS
    from cacao_accounting.database import CompanyDefaultAccount, database
    from cacao_accounting.setup.service import available_catalog_files, finalize_setup

    assert ("base_es.csv", "Predeterminado - ES") in available_catalog_files()
    assert ("base_en.csv", "Default - EN") in available_catalog_files()

    finalize_setup(
        {
            "id": "mapco",
            "razon_social": "Mapping Company",
            "nombre_comercial": "Mapping Company",
            "id_fiscal": "J-MAP",
            "moneda": "NIO",
            "tipo_entidad": "Sociedad Anonima",
        },
        catalogo_tipo="preexistente",
        country="NI",
        idioma="ES",
        catalogo_archivo="base_es.csv",
    )
    database.session.commit()

    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="mapco")).scalar_one()
    assert all(getattr(defaults, field) for field in DEFAULT_ACCOUNT_FIELDS)


def test_setup_with_invalid_catalog_raises_error(app_ctx):
    from cacao_accounting.setup.service import finalize_setup

    with pytest.raises(ValueError, match="catálogo seleccionado.*no está disponible"):
        finalize_setup(
            {
                "id": "mapco",
                "razon_social": "Mapping Company",
                "nombre_comercial": "Mapping Company",
                "id_fiscal": "J-MAP",
                "moneda": "NIO",
                "tipo_entidad": "Sociedad Anonima",
            },
            catalogo_tipo="preexistente",
            country="NI",
            idioma="ES",
            catalogo_archivo="missing_catalog.csv",
        )


def test_setup_with_predefined_catalog_creates_bootstrap_records(app_ctx):
    from datetime import date

    from cacao_accounting.database import (
        AccountingPeriod,
        Book,
        CostCenter,
        Currency,
        Entity,
        FiscalYear,
        NamingSeries,
        database,
    )
    from cacao_accounting.setup.service import finalize_setup

    database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.commit()

    finalize_setup(
        {
            "id": "mapco",
            "razon_social": "Mapping Company",
            "nombre_comercial": "Mapping Company",
            "id_fiscal": "J-MAP",
            "moneda": "NIO",
            "tipo_entidad": "Sociedad Anonima",
        },
        catalogo_tipo="preexistente",
        country="NI",
        idioma="ES",
        catalogo_archivo="base_es.csv",
    )

    entity = database.session.execute(database.select(Entity).filter_by(code="mapco")).scalar_one()
    book = database.session.execute(database.select(Book).filter_by(entity="mapco", code="FISC")).scalar_one()
    cost_center = database.session.execute(database.select(CostCenter).filter_by(entity="mapco", code="MAIN")).scalar_one()
    fiscal_year = database.session.execute(
        database.select(FiscalYear).filter_by(entity="mapco", name=str(date.today().year))
    ).scalar_one()
    period = database.session.execute(
        database.select(AccountingPeriod).filter_by(entity="mapco", name=f"{date.today().year}-01")
    ).scalar_one()
    series = database.session.execute(
        database.select(NamingSeries).filter_by(company="mapco", entity_type="journal_entry")
    ).scalar_one_or_none()

    assert entity is not None
    assert book is not None
    assert cost_center is not None
    assert fiscal_year is not None
    assert period is not None
    assert period.fiscal_year_id == fiscal_year.id
    assert series is not None


def test_example_seed_creates_company_default_accounts(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import DEFAULT_ACCOUNT_FIELDS
    from cacao_accounting.database.helpers import inicia_base_de_datos
    from cacao_accounting.database import CompanyDefaultAccount, database

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
        database.drop_all()
        database.create_all()
        assert inicia_base_de_datos(app=app, user="cacao", passwd="cacao", with_examples=True)

        for company in ("cacao", "dulce", "cafe"):
            defaults = database.session.execute(
                database.select(CompanyDefaultAccount).filter_by(company=company)
            ).scalar_one_or_none()
            assert defaults is not None
            assert all(getattr(defaults, field) for field in DEFAULT_ACCOUNT_FIELDS)


def test_example_seed_creates_company_base_records(app_ctx):
    from cacao_accounting.database import (
        AccountingPeriod,
        Book,
        CostCenter,
        Entity,
        FiscalYear,
        NamingSeries,
        PurchaseMatchingConfig,
        database,
    )
    from cacao_accounting.database.helpers import inicia_base_de_datos

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
        database.drop_all()
        database.create_all()
        assert inicia_base_de_datos(app=app, user="cacao", passwd="cacao", with_examples=True)

        for company in ("cacao", "dulce", "cafe"):
            assert database.session.execute(database.select(Entity).filter_by(code=company)).scalar_one_or_none()
            assert database.session.execute(database.select(Book).filter_by(entity=company, code="FISC")).scalar_one_or_none()
            assert database.session.execute(
                database.select(CostCenter).filter_by(entity=company, code="MAIN")
            ).scalar_one_or_none()
            assert database.session.execute(database.select(FiscalYear).filter_by(entity=company)).scalar_one_or_none()
            assert database.session.execute(database.select(AccountingPeriod).filter_by(entity=company)).scalars().first()
            assert database.session.execute(
                database.select(NamingSeries).filter_by(company=company, entity_type="journal_entry")
            ).scalar_one_or_none()
            assert database.session.execute(
                database.select(PurchaseMatchingConfig).filter_by(company=company)
            ).scalar_one_or_none()


def test_default_account_admin_crud_rejects_incompatible_types(app_ctx):
    from cacao_accounting.database import Accounts, Entity, Modules, User, database

    bank = Accounts(entity="cacao", code="BANK-CRUD", name="Banco", active=True, enabled=True, account_type="bank")
    expense = Accounts(entity="cacao", code="EXP-CRUD", name="Gasto", active=True, enabled=True, account_type="expense")
    admin_user = User(user="admin", name="Admin", password=b"x", classification="admin", active=True)
    admin_module = Modules(module="admin", default=True, enabled=True)
    database.session.add_all([bank, expense, admin_user, admin_module])
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_user.id
        session["_fresh"] = True

    response = client.post(
        "/settings/default-accounts",
        data={"company": "cacao", "default_bank": expense.id, "action": "save"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "debe ser de tipo" in response.get_data(as_text=True)

    response = client.post(
        "/settings/default-accounts",
        data={"company": "cacao", "default_bank": bank.id, "action": "save"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Cuentas predeterminadas guardadas correctamente" in response.get_data(as_text=True)
    assert database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()

    response = client.post(
        "/settings/default-accounts",
        data={"company": "cacao", "action": "delete"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_search_select_account_filters_and_validates_registry(app_ctx):
    from cacao_accounting.database import Accounts, database
    from cacao_accounting.search_select import SearchSelectError, search_select

    bank = Accounts(
        entity="cacao", code="BAN-001", name="Banco Central", active=True, enabled=True, group=False, account_type="bank"
    )
    expense = Accounts(
        entity="cacao", code="EXP-001", name="Banco Gastos", active=True, enabled=True, group=False, account_type="expense"
    )
    disabled = Accounts(
        entity="cacao",
        code="BAN-002",
        name="Banco Deshabilitado",
        active=True,
        enabled=False,
        group=False,
        account_type="bank",
    )
    inactive = Accounts(
        entity="cacao", code="BAN-003", name="Banco Inactivo", active=False, enabled=True, group=False, account_type="bank"
    )
    group = Accounts(
        entity="cacao", code="BAN-004", name="Banco Grupo", active=True, enabled=True, group=True, account_type="bank"
    )
    database.session.add_all([bank, expense, disabled, inactive, group])
    database.session.commit()

    payload = search_select("account", "ban", {"company": ["cacao"], "account_type": ["bank"]}, limit=10)

    assert [item["id"] for item in payload["results"]] == [bank.id]
    assert payload["results"][0]["display_name"] == "BAN-001 - Banco Central"
    assert payload["results"][0]["account_type"] == "bank"

    mixed_types = search_select("account", "ban", {"company": ["cacao"], "account_type": ["bank", "expense"]}, limit=10)
    assert [item["id"] for item in mixed_types["results"]] == [bank.id, expense.id]

    limited = search_select("account", "ban", {"company": ["cacao"], "account_type": ["bank", "expense"]}, limit=1)
    assert len(limited["results"]) == 1
    assert limited["has_more"] is True

    with pytest.raises(SearchSelectError):
        search_select("unknown", "ban", {}, limit=10)

    with pytest.raises(SearchSelectError):
        search_select("account", "ban", {"not_allowed": ["x"]}, limit=10)


def test_search_select_api_requires_login_and_returns_filtered_accounts(app_ctx):
    from cacao_accounting.database import Accounts, User, database

    bank = Accounts(
        entity="cacao", code="BANK-API", name="Banco API", active=True, enabled=True, group=False, account_type="bank"
    )
    expense = Accounts(
        entity="cacao", code="BANK-EXP", name="Gasto Banco", active=True, enabled=True, group=False, account_type="expense"
    )
    user = User(user="api-admin", name="API Admin", password=b"x", classification="admin", active=True)
    database.session.add_all([bank, expense, user])
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True

    response = client.get("/api/search-select?doctype=account&q=BANK&company=cacao&account_type=bank")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["doctype"] == "account"
    assert [item["id"] for item in payload["results"]] == [bank.id]

    response = client.get("/api/search-select?doctype=account&q=BANK&company=cacao&account_type=bank&account_type=expense")
    assert response.status_code == 200
    assert {item["id"] for item in response.get_json()["results"]} == {bank.id, expense.id}

    response = client.get("/api/search-select?doctype=account&q=BANK&company=cacao&bad_filter=x")
    assert response.status_code == 400


def test_default_accounts_view_uses_smart_select_without_rendering_full_account_options(app_ctx):
    from cacao_accounting.contabilidad.default_accounts import upsert_company_default_accounts
    from cacao_accounting.database import Accounts, Modules, User, database

    bank = Accounts(
        entity="cacao", code="BANK-VIEW", name="Banco Vista", active=True, enabled=True, group=False, account_type="bank"
    )
    receivable = Accounts(
        entity="cacao",
        code="AR-VIEW",
        name="Cuenta por Cobrar",
        active=True,
        enabled=True,
        group=False,
        account_type="receivable",
    )
    admin_user = User(user="view-admin", name="View Admin", password=b"x", classification="admin", active=True)
    admin_module = Modules(module="admin", default=True, enabled=True)
    database.session.add_all([bank, receivable, admin_user, admin_module])
    database.session.flush()
    upsert_company_default_accounts("cacao", {"default_bank": bank.id, "default_receivable": receivable.id})
    database.session.commit()

    app_ctx.config["SECRET_KEY"] = "testing"
    client = app_ctx.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_user.id
        session["_fresh"] = True

    response = client.get("/settings/default-accounts?company=cacao")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "x-data='smartSelect({" in html
    assert 'account_type: ["bank"]' in html
    assert "BANK-VIEW - Banco Vista" in html
    assert f'<option value="{bank.id}"' not in html
    assert f'<option value="{receivable.id}"' not in html


def test_manual_journal_allows_bank_and_untyped_accounts(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import Accounts, ComprobanteContable, ComprobanteContableDetalle, GLEntry, database

    bank = Accounts(entity="cacao", code="BANK-M", name="Banco", active=True, enabled=True, account_type="bank")
    free = Accounts(entity="cacao", code="FREE-M", name="Libre", active=True, enabled=True)
    database.session.add_all([bank, free])
    database.session.flush()

    bank_journal = ComprobanteContable(entity="cacao", date=date(2026, 5, 6), memo="Manual banco")
    database.session.add(bank_journal)
    database.session.flush()
    database.session.add_all(
        [
            ComprobanteContableDetalle(
                entity="cacao",
                account=bank.code,
                date=bank_journal.date,
                transaction=bank_journal.__tablename__,
                transaction_id=bank_journal.id,
                value=Decimal("10.00"),
            ),
            ComprobanteContableDetalle(
                entity="cacao",
                account=free.code,
                date=bank_journal.date,
                transaction=bank_journal.__tablename__,
                transaction_id=bank_journal.id,
                value=Decimal("-10.00"),
            ),
        ]
    )
    database.session.commit()

    bank_entries = post_document_to_gl(bank_journal)
    assert len(bank_entries) == 2

    free_journal = ComprobanteContable(entity="cacao", date=date(2026, 5, 6), memo="Manual libre")
    database.session.add(free_journal)
    database.session.flush()
    database.session.add_all(
        [
            ComprobanteContableDetalle(
                entity="cacao",
                account=free.code,
                date=free_journal.date,
                transaction=free_journal.__tablename__,
                transaction_id=free_journal.id,
                value=Decimal("10.00"),
            ),
            ComprobanteContableDetalle(
                entity="cacao",
                account=free.code,
                date=free_journal.date,
                transaction=free_journal.__tablename__,
                transaction_id=free_journal.id,
                value=Decimal("-10.00"),
            ),
        ]
    )
    database.session.commit()

    entries = post_document_to_gl(free_journal)
    assert len(entries) == 2
    assert database.session.execute(database.select(GLEntry)).scalars().all()


def test_sales_tax_uses_default_account_when_tax_has_no_account(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        Tax,
        TaxTemplate,
        TaxTemplateItem,
        database,
    )

    receivable = Accounts(entity="cacao", code="AR-DF", name="AR", active=True, enabled=True, account_type="receivable")
    income = Accounts(entity="cacao", code="INC-DF", name="Ingreso", active=True, enabled=True, account_type="income")
    tax_account = Accounts(entity="cacao", code="TAX-DF", name="IVA", active=True, enabled=True, account_type="tax")
    database.session.add_all([receivable, income, tax_account])
    database.session.flush()
    template = TaxTemplate(name="IVA Default", company="cacao", template_type="selling")
    tax = Tax(name="IVA 15", rate=Decimal("15.00"), tax_type="percentage", applies_to="sales", account_id=None)
    database.session.add_all([template, tax])
    database.session.flush()
    database.session.add_all(
        [
            TaxTemplateItem(tax_template_id=template.id, tax_id=tax.id, sequence=1, behavior="additive"),
            PartyAccount(party_id="CUST-DF", company="cacao", receivable_account_id=receivable.id),
            CompanyDefaultAccount(company="cacao", default_sales_tax_account_id=tax_account.id),
        ]
    )
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 6),
        customer_id="CUST-DF",
        tax_template_id=template.id,
        total=Decimal("100.00"),
        grand_total=Decimal("115.00"),
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-DF",
            qty=Decimal("1"),
            uom="EA",
            rate=Decimal("100.00"),
            amount=Decimal("100.00"),
            income_account_id=income.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    entries = database.session.execute(database.select(GLEntry)).scalars().all()
    assert any(entry.account_id == tax_account.id and entry.credit == Decimal("15.0000") for entry in entries)


def test_inventory_uom_batch_serial_and_rebuild_stock_bins(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Batch,
        CompanyDefaultAccount,
        Item,
        ItemAccount,
        ItemUOMConversion,
        SerialNumber,
        StockBin,
        StockEntry,
        StockEntryItem,
        UOM,
        Warehouse,
        database,
    )
    from cacao_accounting.inventario.service import convert_item_qty, rebuild_stock_bins

    inventory = Accounts(entity="cacao", code="INV-S", name="Inventario", active=True, enabled=True, account_type="asset")
    bridge = Accounts(
        entity="cacao", code="BRIDGE-S", name="Cuenta Puente Compras", active=True, enabled=True, account_type="liability"
    )
    database.session.add_all(
        [
            inventory,
            bridge,
            UOM(code="EA", name="Each"),
            UOM(code="BOX", name="Box"),
            Item(
                code="ITEM-S",
                name="Serial",
                item_type="goods",
                is_stock_item=True,
                has_batch=True,
                has_serial_no=True,
                default_uom="EA",
            ),
            Warehouse(code="WH-S", name="Bodega", company="cacao"),
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            CompanyDefaultAccount(company="cacao", default_inventory=inventory.id, bridge_account_id=bridge.id),
            ItemAccount(item_code="ITEM-S", company="cacao", inventory_account_id=inventory.id),
            ItemUOMConversion(item_code="ITEM-S", from_uom="BOX", to_uom="EA", conversion_factor=Decimal("10")),
            Batch(item_code="ITEM-S", batch_no="B-1"),
        ]
    )
    database.session.flush()
    batch = database.session.execute(database.select(Batch).filter_by(batch_no="B-1")).scalar_one()
    entry = StockEntry(
        company="cacao", posting_date=date(2026, 5, 5), purpose="material_receipt", to_warehouse="WH-S", docstatus=1
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-S",
            target_warehouse="WH-S",
            qty=Decimal("1"),
            uom="EA",
            basic_rate=Decimal("7.00"),
            amount=Decimal("7.00"),
            batch_id=batch.id,
            serial_no="SN-1",
        )
    )
    database.session.commit()

    post_document_to_gl(entry)
    result = rebuild_stock_bins("cacao", item_code="ITEM-S", warehouse="WH-S")
    serial = database.session.execute(database.select(SerialNumber).filter_by(serial_no="SN-1")).scalar_one()
    bin_row = database.session.execute(database.select(StockBin).filter_by(item_code="ITEM-S", warehouse="WH-S")).scalar_one()

    assert convert_item_qty("ITEM-S", Decimal("1"), "BOX", "EA") == Decimal("10")
    assert serial.serial_status == "available"
    assert bin_row.actual_qty == Decimal("1.000000000")
    assert result.rebuilt_bins == 1


def test_bank_statement_import_preview_and_matching_rule(app_ctx):
    from io import StringIO

    from cacao_accounting.bancos.statement_service import apply_bank_matching_rule, import_bank_statement
    from cacao_accounting.database import Bank, BankAccount, BankMatchingRule, BankTransaction, database

    bank = Bank(name="Banco CSV")
    database.session.add(bank)
    database.session.flush()
    account = BankAccount(bank_id=bank.id, company="cacao", account_name="Cuenta CSV", is_active=True)
    database.session.add(account)
    database.session.flush()
    csv_data = "date,reference,description,deposit,withdrawal\n2026-05-05,REF-1,Ingreso,25.00,\n"
    mapping = {
        "date": "date",
        "reference": "reference",
        "description": "description",
        "deposit": "deposit",
        "withdrawal": "withdrawal",
    }

    preview = import_bank_statement(StringIO(csv_data), mapping, account.id, preview=True)
    imported = import_bank_statement(StringIO(csv_data), mapping, account.id, preview=False)
    duplicate = import_bank_statement(StringIO(csv_data), mapping, account.id, preview=True)
    rule = BankMatchingRule(company="cacao", bank_account_id=account.id, name="Referencia", reference_contains="REF")
    database.session.add(rule)
    database.session.commit()
    run = apply_bank_matching_rule(rule.id, account.id, (date(2026, 5, 1), date(2026, 5, 31)))

    assert preview.imported_count == 0
    assert imported.imported_count == 1
    assert duplicate.duplicate_count == 1
    assert database.session.execute(database.select(BankTransaction)).scalars().first()
    assert run.candidates_by_transaction


# ---------------------------------------------------------------------------
# Criterios de aceptacion del Issue: Framework de Conciliacion de Compras
# ---------------------------------------------------------------------------


def test_matching_without_accounting_entries_is_possible(app_ctx):
    """Criterio #1: se puede ejecutar el matching sin generar asientos contables."""
    from cacao_accounting.compras.purchase_reconciliation_service import reconcile_purchase_invoice
    from cacao_accounting.database import (
        GLEntry,
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA-AC1", name="Each AC1"),
            Item(code="ITEM-AC1", name="Item AC1", item_type="goods", is_stock_item=True, default_uom="EA-AC1"),
            Warehouse(code="WH-AC1", name="Bodega AC1", company="cacao"),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-AC1", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-AC1",
            item_name="Item AC1",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA-AC1",
            rate=Decimal("10.00"),
            amount=Decimal("50.00"),
            warehouse="WH-AC1",
        )
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-AC1",
        purchase_receipt_id=receipt.id,
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-AC1",
            item_name="Item AC1",
            qty=Decimal("5"),
            uom="EA-AC1",
            rate=Decimal("10.00"),
            amount=Decimal("50.00"),
            warehouse="WH-AC1",
        )
    )
    database.session.commit()

    # reconcile WITHOUT calling post_document_to_gl — no GL entries should exist
    result = reconcile_purchase_invoice(invoice.id)
    database.session.commit()

    gl_count = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )

    assert result.matching_result == "MATCH_OK"
    assert result.matched_amount == Decimal("50.0000")
    # Matching produced no accounting entries on its own
    assert len(gl_count) == 0


def test_changing_tolerances_does_not_alter_historical_reconciliations(app_ctx):
    """Criterio #2: cambiar tolerancias no altera datos historicos."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        PurchaseMatchingConfig,
        seed_matching_config_for_company,
    )
    from cacao_accounting.database import (
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        PurchaseReconciliation,
        UOM,
        Warehouse,
        database,
    )
    from cacao_accounting.compras.purchase_reconciliation_service import reconcile_purchase_invoice

    # Seed strict config
    seed_matching_config_for_company("cacao")
    database.session.commit()

    database.session.add_all(
        [
            UOM(code="EA-AC2", name="Each AC2"),
            Item(code="ITEM-AC2", name="Item AC2", item_type="goods", is_stock_item=True, default_uom="EA-AC2"),
            Warehouse(code="WH-AC2", name="Bodega AC2", company="cacao"),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-AC2", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-AC2",
            item_name="Item AC2",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom="EA-AC2",
            rate=Decimal("20.00"),
            amount=Decimal("200.00"),
            warehouse="WH-AC2",
        )
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-AC2",
        purchase_receipt_id=receipt.id,
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-AC2",
            item_name="Item AC2",
            qty=Decimal("10"),
            uom="EA-AC2",
            rate=Decimal("20.00"),
            amount=Decimal("200.00"),
            warehouse="WH-AC2",
        )
    )
    database.session.commit()

    reconcile_purchase_invoice(invoice.id)
    database.session.commit()

    # Now change tolerance — should NOT affect the already-created reconciliation
    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    cfg.price_tolerance_value = Decimal("10")  # relax tolerance
    database.session.commit()

    recon = database.session.execute(
        database.select(PurchaseReconciliation).filter_by(purchase_invoice_id=invoice.id)
    ).scalar_one()

    # Historical record is unchanged
    assert recon.matched_amount == Decimal("200.0000")
    assert recon.matching_type == "3-way"


def test_state_reconstruction_from_events(app_ctx):
    """Criterio #3: se pueden reconstruir estados desde eventos."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        reconstruct_reconciliation_state,
        reconcile_purchase_invoice,
    )
    from cacao_accounting.database import (
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA-AC3", name="Each AC3"),
            Item(code="ITEM-AC3", name="Item AC3", item_type="goods", is_stock_item=True, default_uom="EA-AC3"),
            Warehouse(code="WH-AC3", name="Bodega AC3", company="cacao"),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-AC3", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-AC3",
            item_name="Item AC3",
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="EA-AC3",
            rate=Decimal("30.00"),
            amount=Decimal("90.00"),
            warehouse="WH-AC3",
        )
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-AC3",
        purchase_receipt_id=receipt.id,
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-AC3",
            item_name="Item AC3",
            qty=Decimal("3"),
            uom="EA-AC3",
            rate=Decimal("30.00"),
            amount=Decimal("90.00"),
            warehouse="WH-AC3",
        )
    )
    database.session.commit()

    result = reconcile_purchase_invoice(invoice.id)
    database.session.commit()

    # Reconstruct state from event log
    snapshot = reconstruct_reconciliation_state("cacao", result.reconciliation_id)

    assert snapshot.company == "cacao"
    assert snapshot.document_id == result.reconciliation_id
    # At least one event was logged for this reconciliation
    assert len(snapshot.events) >= 1
    # Event log contains a MATCH event
    event_types = [ev["event_type"] for ev in snapshot.events]
    assert any("MATCH" in et for et in event_types)


def test_system_supports_two_way_and_three_way_without_structural_changes(app_ctx):
    """Criterio #4: el sistema soporta 2-way y 3-way sin cambios estructurales."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        MatchingType,
        PurchaseMatchingConfig,
        get_matching_config,
        seed_matching_config_for_company,
    )
    from cacao_accounting.database import database

    seed_matching_config_for_company("cacao")
    database.session.commit()

    # 3-way (default)
    cfg_3way = get_matching_config("cacao")
    assert cfg_3way.matching_type == MatchingType.THREE_WAY

    # Switch to 2-way via config — no structural changes required
    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    cfg.matching_type = MatchingType.TWO_WAY
    database.session.commit()

    cfg_2way = get_matching_config("cacao")
    assert cfg_2way.matching_type == MatchingType.TWO_WAY


def test_two_way_matching_uses_purchase_order_lines_without_receipts(app_ctx):
    """2-way: OC + factura sin recepcion usa lineas de OC y no IDs de recepcion."""
    from sqlalchemy import text

    from cacao_accounting.compras.purchase_reconciliation_service import (
        MatchingType,
        PurchaseMatchingConfig,
        reconcile_purchase_invoice,
        seed_matching_config_for_company,
    )
    from cacao_accounting.database import (
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReconciliation,
        PurchaseReconciliationItem,
        UOM,
        database,
    )

    seed_matching_config_for_company("cacao")
    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    cfg.matching_type = MatchingType.TWO_WAY
    database.session.add_all(
        [
            UOM(code="EA-2W", name="Each 2W"),
            Item(code="ITEM-2W", name="Item 2W", item_type="goods", is_stock_item=False, default_uom="EA-2W"),
        ]
    )
    order = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-2W", docstatus=1)
    database.session.add(order)
    database.session.flush()
    order_item = PurchaseOrderItem(
        purchase_order_id=order.id,
        item_code="ITEM-2W",
        item_name="Item 2W",
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="EA-2W",
        rate=Decimal("10.00"),
        amount=Decimal("50.00"),
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-2W",
        purchase_order_id=order.id,
        docstatus=1,
    )
    database.session.add_all([order_item, invoice])
    database.session.flush()
    invoice_item = PurchaseInvoiceItem(
        purchase_invoice_id=invoice.id,
        item_code="ITEM-2W",
        item_name="Item 2W",
        qty=Decimal("5"),
        uom="EA-2W",
        rate=Decimal("10.00"),
        amount=Decimal("50.00"),
    )
    database.session.add(invoice_item)
    database.session.commit()
    database.session.execute(text("PRAGMA foreign_keys=ON"))

    result = reconcile_purchase_invoice(invoice.id)
    database.session.commit()

    reconciliation = database.session.execute(
        database.select(PurchaseReconciliation).filter_by(id=result.reconciliation_id)
    ).scalar_one()
    reconciliation_item = database.session.execute(
        database.select(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=reconciliation.id)
    ).scalar_one()

    assert result.matching_result == "MATCH_OK"
    assert reconciliation.matching_type == "2-way"
    assert reconciliation.purchase_order_id == order.id
    assert reconciliation.purchase_receipt_id is None
    assert reconciliation_item.purchase_order_item_id == order_item.id
    assert reconciliation_item.purchase_receipt_item_id is None


def test_two_way_matching_aggregates_duplicate_order_and_invoice_lines(app_ctx):
    """2-way evalua cantidades agregadas por producto/UOM antes de crear detalles."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        MatchingType,
        PurchaseMatchingConfig,
        reconcile_purchase_invoice,
        seed_matching_config_for_company,
    )
    from cacao_accounting.database import (
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReconciliationItem,
        UOM,
        database,
    )

    seed_matching_config_for_company("cacao")
    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    cfg.matching_type = MatchingType.TWO_WAY
    database.session.add_all(
        [
            UOM(code="EA-2WA", name="Each 2WA"),
            Item(code="ITEM-2WA", name="Item 2WA", item_type="goods", is_stock_item=False, default_uom="EA-2WA"),
        ]
    )
    order = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-2WA", docstatus=1)
    database.session.add(order)
    database.session.flush()
    order_items = [
        PurchaseOrderItem(
            purchase_order_id=order.id,
            item_code="ITEM-2WA",
            item_name="Item 2WA",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="EA-2WA",
            rate=Decimal("10.00"),
            amount=Decimal("20.00"),
        ),
        PurchaseOrderItem(
            purchase_order_id=order.id,
            item_code="ITEM-2WA",
            item_name="Item 2WA",
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="EA-2WA",
            rate=Decimal("10.00"),
            amount=Decimal("30.00"),
        ),
    ]
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-2WA",
        purchase_order_id=order.id,
        docstatus=1,
    )
    database.session.add_all([*order_items, invoice])
    database.session.flush()
    database.session.add_all(
        [
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code="ITEM-2WA",
                item_name="Item 2WA",
                qty=Decimal("2"),
                uom="EA-2WA",
                rate=Decimal("10.00"),
                amount=Decimal("20.00"),
            ),
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code="ITEM-2WA",
                item_name="Item 2WA",
                qty=Decimal("3"),
                uom="EA-2WA",
                rate=Decimal("10.00"),
                amount=Decimal("30.00"),
            ),
        ]
    )
    database.session.commit()

    result = reconcile_purchase_invoice(invoice.id)
    database.session.commit()
    items = (
        database.session.execute(
            database.select(PurchaseReconciliationItem).filter_by(purchase_reconciliation_id=result.reconciliation_id)
        )
        .scalars()
        .all()
    )

    assert result.matching_result == "MATCH_OK"
    assert result.status == "reconciled"
    assert len(items) == 2
    assert {item.purchase_order_item_id for item in items} == {order_item.id for order_item in order_items}
    assert all(item.purchase_receipt_item_id is None for item in items)


def test_purchase_invoice_posting_auto_reconciles_two_way_po_only_invoice(app_ctx):
    """Posting: una factura PO-only se auto-concilia cuando la compania esta en 2-way."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        MatchingType,
        PurchaseMatchingConfig,
        seed_matching_config_for_company,
    )
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Item,
        PartyAccount,
        PurchaseEconomicEvent,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReconciliation,
        UOM,
        database,
    )

    payable_account = Accounts(
        entity="cacao",
        code="AP-2W",
        name="AP 2W",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    expense_account = Accounts(
        entity="cacao",
        code="EXP-2W",
        name="Gasto 2W",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add_all(
        [
            payable_account,
            expense_account,
            UOM(code="EA-2WP", name="Each 2WP"),
            Item(code="ITEM-2WP", name="Item 2WP", item_type="goods", is_stock_item=False, default_uom="EA-2WP"),
        ]
    )
    database.session.flush()
    database.session.add(PartyAccount(party_id="SUPP-2WP", company="cacao", payable_account_id=payable_account.id))
    seed_matching_config_for_company("cacao")
    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    cfg.matching_type = MatchingType.TWO_WAY

    order = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-2WP", docstatus=1)
    database.session.add(order)
    database.session.flush()
    database.session.add(
        PurchaseOrderItem(
            purchase_order_id=order.id,
            item_code="ITEM-2WP",
            item_name="Item 2WP",
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="EA-2WP",
            rate=Decimal("12.00"),
            amount=Decimal("36.00"),
        )
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-2WP",
        purchase_order_id=order.id,
        docstatus=1,
        total=Decimal("36.00"),
        grand_total=Decimal("36.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-2WP",
            item_name="Item 2WP",
            qty=Decimal("3"),
            uom="EA-2WP",
            rate=Decimal("12.00"),
            amount=Decimal("36.00"),
            expense_account_id=expense_account.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    reconciliation = database.session.execute(
        database.select(PurchaseReconciliation).filter_by(purchase_invoice_id=invoice.id)
    ).scalar_one()
    event_types = [
        event.event_type
        for event in database.session.execute(database.select(PurchaseEconomicEvent).filter_by(company="cacao"))
        .scalars()
        .all()
    ]

    assert reconciliation.matching_type == "2-way"
    assert reconciliation.purchase_receipt_id is None
    assert "INVOICE_RECEIVED" in event_types
    assert "MATCH_COMPLETED" in event_types


def test_cancel_two_way_purchase_invoice_releases_order_quantities(app_ctx):
    """Cancelar una factura 2-way cancela su conciliacion y libera cantidad de OC."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        MatchingType,
        PurchaseMatchingConfig,
        cancel_purchase_reconciliation,
        reconcile_purchase_invoice,
        seed_matching_config_for_company,
    )
    from cacao_accounting.database import (
        Item,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReconciliation,
        UOM,
        database,
    )

    seed_matching_config_for_company("cacao")
    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    cfg.matching_type = MatchingType.TWO_WAY
    database.session.add_all(
        [
            UOM(code="EA-2WC", name="Each 2WC"),
            Item(code="ITEM-2WC", name="Item 2WC", item_type="goods", is_stock_item=False, default_uom="EA-2WC"),
        ]
    )
    order = PurchaseOrder(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-2WC", docstatus=1)
    database.session.add(order)
    database.session.flush()
    database.session.add(
        PurchaseOrderItem(
            purchase_order_id=order.id,
            item_code="ITEM-2WC",
            item_name="Item 2WC",
            qty=Decimal("4"),
            qty_in_base_uom=Decimal("4"),
            uom="EA-2WC",
            rate=Decimal("8.00"),
            amount=Decimal("32.00"),
        )
    )
    first_invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-2WC",
        purchase_order_id=order.id,
        docstatus=1,
    )
    second_invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 3),
        supplier_id="SUPP-2WC",
        purchase_order_id=order.id,
        docstatus=1,
    )
    database.session.add_all([first_invoice, second_invoice])
    database.session.flush()
    for invoice in (first_invoice, second_invoice):
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice.id,
                item_code="ITEM-2WC",
                item_name="Item 2WC",
                qty=Decimal("4"),
                uom="EA-2WC",
                rate=Decimal("8.00"),
                amount=Decimal("32.00"),
            )
        )
    database.session.commit()

    first_result = reconcile_purchase_invoice(first_invoice.id)
    database.session.commit()
    cancel_purchase_reconciliation(first_invoice.id)
    database.session.commit()

    first_reconciliation = database.session.execute(
        database.select(PurchaseReconciliation).filter_by(id=first_result.reconciliation_id)
    ).scalar_one()
    second_result = reconcile_purchase_invoice(second_invoice.id)

    assert first_reconciliation.status == "cancelled"
    assert second_result.matching_result == "MATCH_OK"


def test_bridge_account_is_configurable_not_required_by_default(app_ctx):
    """Criterio #5: la cuenta puente es configurable, no obligatoria."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        PurchaseMatchingConfig,
        seed_matching_config_for_company,
    )
    from cacao_accounting.database import database

    seed_matching_config_for_company("cacao")
    database.session.commit()

    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    # By default it is required (strict mode) but can be set to False
    assert isinstance(cfg.bridge_account_required, bool)

    cfg.bridge_account_required = False
    database.session.commit()

    cfg_relaxed = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    assert cfg_relaxed.bridge_account_required is False


def test_purchase_receipt_posting_allows_missing_bridge_when_not_required(app_ctx):
    """Recepcion mantiene stock ledger sin GL puente cuando la cuenta puente no es requerida."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        PurchaseMatchingConfig,
        seed_matching_config_for_company,
    )
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        GLEntry,
        Item,
        PurchaseReceipt,
        PurchaseReceiptItem,
        StockLedgerEntry,
        UOM,
        Warehouse,
        database,
    )

    seed_matching_config_for_company("cacao")
    cfg = database.session.execute(database.select(PurchaseMatchingConfig).filter_by(company="cacao")).scalar_one()
    cfg.bridge_account_required = False
    database.session.add_all(
        [
            UOM(code="EA-NB", name="Each No Bridge"),
            Item(code="ITEM-NB", name="Item No Bridge", item_type="goods", is_stock_item=True, default_uom="EA-NB"),
            Warehouse(code="WH-NB", name="Bodega No Bridge", company="cacao"),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-NB", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-NB",
            item_name="Item No Bridge",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="EA-NB",
            rate=Decimal("9.00"),
            amount=Decimal("9.00"),
            warehouse="WH-NB",
        )
    )
    database.session.commit()

    entries = post_document_to_gl(receipt)
    database.session.commit()

    stock_movements = database.session.execute(
        database.select(StockLedgerEntry).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id)
    ).scalar_one_or_none()
    gl_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id))
        .scalars()
        .all()
    )

    assert entries == []
    assert stock_movements is not None
    assert gl_entries == []


def test_purchase_reconciliation_panel_groups_two_way_and_three_way(app_ctx):
    """Panel: agrupa conciliaciones 2-way sin recepcion y 3-way con recepcion por OC."""
    from cacao_accounting.compras.purchase_reconciliation_service import get_purchase_reconciliation_panel_groups
    from cacao_accounting.database import PurchaseReconciliation, database

    database.session.add_all(
        [
            PurchaseReconciliation(
                company="cacao",
                purchase_order_id="PO-PANEL",
                purchase_receipt_id=None,
                purchase_invoice_id="PINV-2W",
                matching_type="2-way",
                matched_amount=Decimal("10.00"),
                matched_date=date(2026, 5, 1),
                status="reconciled",
            ),
            PurchaseReconciliation(
                company="cacao",
                purchase_order_id="PO-PANEL",
                purchase_receipt_id="PREC-3W",
                purchase_invoice_id="PINV-3W",
                matching_type="3-way",
                matched_amount=Decimal("20.00"),
                matched_date=date(2026, 5, 2),
                status="partial",
            ),
        ]
    )
    database.session.commit()

    groups = get_purchase_reconciliation_panel_groups("cacao")
    group = next(group for group in groups if group.purchase_order_id == "PO-PANEL")

    assert group.invoice_count == 2
    assert group.receipt_count == 1
    assert group.worst_status == "partial"
    assert {reconciliation.matching_type for reconciliation in group.reconciliations} == {"2-way", "3-way"}


def test_goods_received_cancelled_event_emitted_on_receipt_cancel(app_ctx):
    """Cancelar una recepcion emite GOODS_RECEIVED_CANCELLED y cancela conciliaciones dependientes."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        emit_goods_received_cancelled,
        reconcile_purchase_invoice,
    )
    from cacao_accounting.database import (
        Item,
        PurchaseEconomicEvent,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        PurchaseReconciliation,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA-AC6", name="Each AC6"),
            Item(code="ITEM-AC6", name="Item AC6", item_type="goods", is_stock_item=True, default_uom="EA-AC6"),
            Warehouse(code="WH-AC6", name="Bodega AC6", company="cacao"),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 1), supplier_id="SUPP-AC6", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-AC6",
            item_name="Item AC6",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="EA-AC6",
            rate=Decimal("50.00"),
            amount=Decimal("100.00"),
            warehouse="WH-AC6",
        )
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 2),
        supplier_id="SUPP-AC6",
        purchase_receipt_id=receipt.id,
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-AC6",
            item_name="Item AC6",
            qty=Decimal("2"),
            uom="EA-AC6",
            rate=Decimal("50.00"),
            amount=Decimal("100.00"),
            warehouse="WH-AC6",
        )
    )
    database.session.commit()

    reconcile_purchase_invoice(invoice.id)
    database.session.commit()

    # Cancel the receipt — should also cancel dependent reconciliation and emit event
    emit_goods_received_cancelled(receipt.id, "cacao")
    database.session.commit()

    recon = database.session.execute(
        database.select(PurchaseReconciliation).filter_by(purchase_receipt_id=receipt.id)
    ).scalar_one()
    assert recon.status == "cancelled"

    cancel_event = database.session.execute(
        database.select(PurchaseEconomicEvent).filter_by(
            company="cacao", document_id=receipt.id, event_type="GOODS_RECEIVED_CANCELLED"
        )
    ).scalar_one_or_none()
    assert cancel_event is not None
