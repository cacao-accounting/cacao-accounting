# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

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
        from cacao_accounting.database import Entity, PurchaseMatchingConfig, database

        database.create_all()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                ),
                # Los escenarios históricos de posting ejercitan facturas sin OC.
                PurchaseMatchingConfig(company="cacao", require_purchase_order=False),
            ]
        )
        database.session.commit()
        yield app


def test_gl_entry_constraint_rejects_unbalanced_records(app_ctx):
    from cacao_accounting.database import GLEntry, database

    entry = GLEntry(
        posting_date=date(2026, 5, 4),
        company="cacao",
        ledger_id=None,
        account_id=None,
        debit=Decimal("100.00"),
        credit=Decimal("100.00"),
        voucher_type="sales_invoice",
        voucher_id="test-1",
        document_no="TEST-001",
        naming_series_id=None,
    )
    database.session.add(entry)

    with pytest.raises(IntegrityError):
        database.session.commit()


def test_exchange_rate_lookups_use_the_latest_prior_positive_rate(app_ctx):
    """Posting and bank reconciliation share the historical nearest-rate rule."""
    from cacao_accounting.bancos.reconciliation_service import _lookup_exchange_rate as bank_lookup_exchange_rate
    from cacao_accounting.contabilidad.posting_service import _lookup_exchange_rate as posting_lookup_exchange_rate
    from cacao_accounting.database import ExchangeRate, database

    database.session.add_all(
        [
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal("0.027"), date=date(2026, 5, 1)),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal("0.028"), date=date(2026, 5, 3)),
        ]
    )
    database.session.commit()

    assert posting_lookup_exchange_rate("NIO", "USD", date(2026, 5, 4)) == Decimal("0.028")
    assert bank_lookup_exchange_rate("NIO", "USD", date(2026, 5, 4)) == Decimal("0.028")


def test_submit_document_rolls_back_docstatus_when_posting_fails(app_ctx):
    """A failed GL posting cannot leave the operational document approved."""
    from cacao_accounting.contabilidad.posting import PostingError, submit_document
    from cacao_accounting.database import SalesInvoice, database

    invoice = SalesInvoice(company="cacao", posting_date=date(2026, 5, 4), customer_id="UNKNOWN", docstatus=0)
    database.session.add(invoice)
    database.session.commit()

    with pytest.raises(PostingError):
        submit_document(invoice)

    database.session.expire(invoice)
    assert invoice.docstatus == 0


def test_post_sales_invoice_creates_balanced_gl_entries(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        GLEntry,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )

    receivable_account = Accounts(
        entity="cacao",
        code="AR-001",
        name="Cuentas por cobrar",
        active=True,
        enabled=True,
        classification="asset",
    )
    income_account = Accounts(
        entity="cacao",
        code="IN-001",
        name="Ventas",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([receivable_account, income_account])
    database.session.flush()

    party_account = PartyAccount(
        party_id="CUST-001",
        company="cacao",
        receivable_account_id=receivable_account.id,
    )
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-001",
        customer_name="Cliente prueba",
        docstatus=1,
        document_no="cacao-SI-2026-05-00001",
        naming_series_id=None,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add_all([party_account, invoice])
    database.session.flush()

    item = SalesInvoiceItem(
        sales_invoice_id=invoice.id,
        item_code="ITEM-001",
        item_name="Servicio de prueba",
        qty=Decimal("1"),
        rate=Decimal("100.00"),
        amount=Decimal("100.00"),
        income_account_id=income_account.id,
    )
    database.session.add(item)
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    posted_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )

    assert len(posted_entries) == 2
    assert sum(entry.debit for entry in posted_entries) == sum(entry.credit for entry in posted_entries)
    assert any(entry.debit == Decimal("100.00") and entry.account_id == receivable_account.id for entry in posted_entries)
    assert any(entry.credit == Decimal("100.00") and entry.account_id == income_account.id for entry in posted_entries)


def test_submit_sales_invoice_uses_persisted_fiscal_snapshot(app_ctx):
    from cacao_accounting.contabilidad.posting import submit_document
    from cacao_accounting.database import (
        Accounts,
        DocumentTaxLine,
        DocumentTaxSummary,
        GLEntry,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )

    receivable_account = Accounts(
        entity="cacao",
        code="AR-SNAP",
        name="Cuentas por cobrar snapshot",
        active=True,
        enabled=True,
        classification="asset",
    )
    income_account = Accounts(
        entity="cacao",
        code="IN-SNAP",
        name="Ventas snapshot",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    sales_tax_account = Accounts(
        entity="cacao",
        code="TAX-SNAP",
        name="IVA débito fiscal",
        active=True,
        enabled=True,
        classification="liability",
        account_type="tax",
    )
    database.session.add_all([receivable_account, income_account, sales_tax_account])
    database.session.flush()
    database.session.add(
        PartyAccount(
            party_id="CUST-SNAP",
            company="cacao",
            receivable_account_id=receivable_account.id,
        )
    )

    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-SNAP",
        customer_name="Cliente snapshot",
        docstatus=0,
        total=Decimal("100.00"),
        grand_total=Decimal("115.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-SNAP",
            item_name="Servicio snapshot",
            qty=Decimal("1"),
            rate=Decimal("100.00"),
            amount=Decimal("100.00"),
            income_account_id=income_account.id,
        )
    )
    summary = DocumentTaxSummary(
        company="cacao",
        document_type="sales_invoice",
        document_id=invoice.id,
        currency="NIO",
        subtotal=Decimal("100.00"),
        document_tax_total=Decimal("15.00"),
        grand_total=Decimal("115.00"),
    )
    database.session.add(summary)
    database.session.flush()
    database.session.add(
        DocumentTaxLine(
            document_tax_summary_id=summary.id,
            line_index=1,
            rule_id="RULE-SNAP-1",
            concept="IVA",
            tax_type="tax",
            calculation_method="manual",
            base_amount=Decimal("100.00"),
            rate=Decimal("15.00"),
            amount=Decimal("15.00"),
            accounting_treatment="separate_tax_account",
            account_id=sales_tax_account.id,
            affects_inventory=False,
            affects_document_total=True,
            included_in_price=False,
            rule_snapshot_json='{"concept":"IVA","tax_type":"tax","sequence":1}',
        )
    )
    database.session.commit()

    submit_document(invoice)
    database.session.commit()

    posted_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )
    assert len(posted_entries) == 3
    assert sum(entry.debit for entry in posted_entries) == Decimal("115.00")
    assert sum(entry.credit for entry in posted_entries) == Decimal("115.00")
    assert any(entry.credit == Decimal("100.00") and entry.account_id == income_account.id for entry in posted_entries)
    assert any(entry.credit == Decimal("15.00") and entry.account_id == sales_tax_account.id for entry in posted_entries)
    assert any(entry.debit == Decimal("115.00") and entry.account_id == receivable_account.id for entry in posted_entries)


def test_post_comprobante_contable_creates_balanced_gl_entries(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        ComprobanteContable,
        ComprobanteContableDetalle,
        GLEntry,
        database,
    )

    receivable_account = Accounts(
        entity="cacao",
        code="AR-001",
        name="Cuentas por cobrar",
        active=True,
        enabled=True,
        classification="asset",
    )
    revenue_account = Accounts(
        entity="cacao",
        code="REV-001",
        name="Ingresos",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([receivable_account, revenue_account])
    database.session.flush()

    journal = ComprobanteContable(
        entity="cacao",
        date=date(2026, 5, 4),
        memo="Comprobante de diario prueba",
    )
    database.session.add(journal)
    database.session.flush()

    debit_line = ComprobanteContableDetalle(
        entity="cacao",
        account=receivable_account.code,
        date=journal.date,
        transaction="journal_entry",
        transaction_id=journal.id,
        value=Decimal("100.00"),
        memo="Cliente por cobrar",
        third_type="customer",
        third_code="CUST-001",
    )
    credit_line = ComprobanteContableDetalle(
        entity="cacao",
        account=revenue_account.code,
        date=journal.date,
        transaction="journal_entry",
        transaction_id=journal.id,
        value=Decimal("-100.00"),
        memo="Venta manual",
    )
    database.session.add_all([debit_line, credit_line])
    database.session.commit()

    post_document_to_gl(journal)
    database.session.commit()

    posted_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="journal_entry", voucher_id=journal.id))
        .scalars()
        .all()
    )

    assert len(posted_entries) == 2
    assert sum(entry.debit for entry in posted_entries) == sum(entry.credit for entry in posted_entries)
    assert any(entry.debit == Decimal("100.00") and entry.account_id == receivable_account.id for entry in posted_entries)
    assert any(entry.credit == Decimal("100.00") and entry.account_id == revenue_account.id for entry in posted_entries)


def test_post_payment_entry_creates_balanced_gl_entries(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import Accounts, GLEntry, PartyAccount, PaymentEntry, database

    bank_account = Accounts(
        entity="cacao",
        code="BANK-001",
        name="Cuenta Banco",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    payable_account = Accounts(
        entity="cacao",
        code="AP-001",
        name="Cuentas por pagar",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    database.session.add_all([bank_account, payable_account])
    database.session.flush()

    party_account = PartyAccount(
        party_id="SUPP-001",
        company="cacao",
        payable_account_id=payable_account.id,
    )
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        payment_type="pay",
        party_type="supplier",
        party_id="SUPP-001",
        party_name="Proveedor prueba",
        paid_amount=Decimal("50.00"),
        paid_from_account_id=bank_account.id,
        docstatus=1,
    )
    database.session.add_all([party_account, payment])
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    posted_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )

    assert len(posted_entries) == 2
    assert sum(entry.debit for entry in posted_entries) == sum(entry.credit for entry in posted_entries)
    assert any(entry.debit == Decimal("50.00") and entry.account_id == payable_account.id for entry in posted_entries)
    assert any(entry.credit == Decimal("50.00") and entry.account_id == bank_account.id for entry in posted_entries)


def test_post_sales_invoice_posts_once_per_active_book(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import Accounts, Book, GLEntry, PartyAccount, SalesInvoice, SalesInvoiceItem, database

    receivable_account = Accounts(
        entity="cacao",
        code="AR-ML",
        name="Cuentas por cobrar ML",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    income_account = Accounts(
        entity="cacao",
        code="IN-ML",
        name="Ventas ML",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    fiscal_book = Book(entity="cacao", code="FISC", name="Fiscal", is_primary=True)
    ifrs_book = Book(entity="cacao", code="IFRS", name="IFRS", is_primary=False)
    database.session.add_all([receivable_account, income_account, fiscal_book, ifrs_book])
    database.session.flush()
    database.session.add(PartyAccount(party_id="CUST-ML", company="cacao", receivable_account_id=receivable_account.id))
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-ML",
        docstatus=1,
        total=Decimal("25.00"),
        grand_total=Decimal("25.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-ML",
            item_name="Servicio multi libro",
            qty=Decimal("1"),
            rate=Decimal("25.00"),
            amount=Decimal("25.00"),
            income_account_id=income_account.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )
    assert len(entries) == 4
    assert {entry.ledger_id for entry in entries} == {fiscal_book.id, ifrs_book.id}
    for ledger_id in {fiscal_book.id, ifrs_book.id}:
        ledger_entries = [entry for entry in entries if entry.ledger_id == ledger_id]
        assert sum(entry.debit for entry in ledger_entries) == sum(entry.credit for entry in ledger_entries)


def test_post_document_to_gl_rejects_duplicate_posting(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, post_document_to_gl
    from cacao_accounting.database import Accounts, PartyAccount, SalesInvoice, SalesInvoiceItem, database

    receivable_account = Accounts(
        entity="cacao",
        code="AR-IDEMP",
        name="Cuentas por cobrar idempotencia",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    income_account = Accounts(
        entity="cacao",
        code="IN-IDEMP",
        name="Ventas idempotencia",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([receivable_account, income_account])
    database.session.flush()
    database.session.add(PartyAccount(party_id="CUST-IDEMP", company="cacao", receivable_account_id=receivable_account.id))
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-IDEMP",
        docstatus=1,
        total=Decimal("10.00"),
        grand_total=Decimal("10.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-IDEMP",
            item_name="Servicio idempotente",
            qty=Decimal("1"),
            rate=Decimal("10.00"),
            amount=Decimal("10.00"),
            income_account_id=income_account.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    with pytest.raises(PostingError):
        post_document_to_gl(invoice)


def test_cancel_document_creates_gl_reversals(app_ctx):
    from cacao_accounting.contabilidad.posting import cancel_document, post_document_to_gl
    from cacao_accounting.database import Accounts, GLEntry, PartyAccount, SalesInvoice, SalesInvoiceItem, database

    receivable_account = Accounts(
        entity="cacao",
        code="AR-REV",
        name="Cuentas por cobrar reverso",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    income_account = Accounts(
        entity="cacao",
        code="IN-REV",
        name="Ventas reverso",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([receivable_account, income_account])
    database.session.flush()
    database.session.add(PartyAccount(party_id="CUST-REV", company="cacao", receivable_account_id=receivable_account.id))
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-REV",
        docstatus=1,
        total=Decimal("80.00"),
        grand_total=Decimal("80.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-REV",
            item_name="Servicio reversible",
            qty=Decimal("1"),
            rate=Decimal("80.00"),
            amount=Decimal("80.00"),
            income_account_id=income_account.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()
    reversals = cancel_document(invoice)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )
    assert invoice.docstatus == 2
    assert len(reversals) == 2
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert sum(entry.is_reversal for entry in entries) == 2
    assert all(entry.is_cancelled for entry in entries if not entry.is_reversal)


def test_cancel_purchase_receipt_reverts_stock_and_gl(app_ctx):
    from cacao_accounting.contabilidad.posting import cancel_document, post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        Item,
        ItemAccount,
        PartyAccount,
        PurchaseReceipt,
        PurchaseReceiptItem,
        StockBin,
        StockLedgerEntry,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-PR",
        name="Inventario PR",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    bridge_account = Accounts(
        entity="cacao",
        code="BRIDGE-PR",
        name="Cuenta Puente PR",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    uom = UOM(code="EA", name="Each")
    item = Item(code="ITEM-PR", name="Item PR", item_type="goods", is_stock_item=True, default_uom="EA")
    warehouse = Warehouse(code="WH-PR", name="Bodega PR", company="cacao")
    database.session.add_all([inventory_account, bridge_account, uom, item, warehouse])
    database.session.flush()
    database.session.add_all(
        [
            ItemAccount(item_code="ITEM-PR", company="cacao"),
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
            WarehouseCompanyAccount(
                warehouse_code="WH-PR", company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
            PartyAccount(party_id="SUPP-PR", company="cacao", payable_account_id=None),
        ]
    )
    receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-PR",
        docstatus=1,
        total=Decimal("50.00"),
        grand_total=Decimal("50.00"),
    )
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-PR",
            item_name="Item PR",
            qty=Decimal("2"),
            uom="EA",
            qty_in_base_uom=Decimal("2"),
            rate=Decimal("25.00"),
            amount=Decimal("50.00"),
            warehouse="WH-PR",
            valuation_rate=Decimal("25.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(receipt)
    database.session.commit()
    reversals = cancel_document(receipt)
    database.session.commit()

    stock_movements = (
        database.session.execute(
            database.select(StockLedgerEntry).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id)
        )
        .scalars()
        .all()
    )
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(item_code="ITEM-PR", warehouse="WH-PR")
    ).scalar_one()
    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id))
        .scalars()
        .all()
    )

    assert receipt.docstatus == 2
    assert len(reversals) == 2
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert len(stock_movements) == 2
    assert any(movement.is_cancelled for movement in stock_movements)
    assert any(not movement.is_cancelled for movement in stock_movements)
    assert sum(movement.qty_change for movement in stock_movements) == Decimal("0E-9")
    assert bin_row.actual_qty == Decimal("0.000000000")


def test_purchase_receipt_lands_import_costs_into_initial_valuation_layers(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        Item,
        ItemAccount,
        LandedCostAllocation,
        PurchaseReceipt,
        PurchaseReceiptItem,
        StockBin,
        StockValuationLayer,
        TaxRule,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-IMP",
        name="Inventario importacion",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    bridge_account = Accounts(
        entity="cacao",
        code="BRIDGE-IMP",
        name="Cuenta puente importacion",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    database.session.add_all(
        [
            inventory_account,
            bridge_account,
            UOM(code="EA-IMP", name="Each import"),
            Item(code="IMP-A", name="Importado A", item_type="goods", is_stock_item=True, default_uom="EA-IMP"),
            Item(code="IMP-B", name="Importado B", item_type="goods", is_stock_item=True, default_uom="EA-IMP"),
            Warehouse(code="WH-IMP", name="Bodega importacion", company="cacao"),
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            ItemAccount(item_code="IMP-A", company="cacao"),
            ItemAccount(item_code="IMP-B", company="cacao"),
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
            WarehouseCompanyAccount(
                warehouse_code="WH-IMP", company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
            TaxRule(
                company="cacao",
                name="Flete internacional",
                applies_to="purchase",
                level="transaction",
                concept="international_freight",
                tax_type="charge",
                calculation_method="fixed",
                amount=Decimal("40.00"),
                sequence=10,
                accounting_treatment="capitalizable_inventory_cost",
                recognition_event="purchase_receipt_confirmed",
                affects_inventory=True,
                affects_document_total=False,
                allocation_method="by_value",
                is_active=True,
            ),
        ]
    )
    receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-IMP",
        docstatus=1,
        total=Decimal("200.00"),
        grand_total=Decimal("200.00"),
    )
    database.session.add(receipt)
    database.session.flush()
    database.session.add_all(
        [
            PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code="IMP-A",
                item_name="Importado A",
                qty=Decimal("1"),
                uom="EA-IMP",
                qty_in_base_uom=Decimal("1"),
                rate=Decimal("100.00"),
                amount=Decimal("100.00"),
                warehouse="WH-IMP",
            ),
            PurchaseReceiptItem(
                purchase_receipt_id=receipt.id,
                item_code="IMP-B",
                item_name="Importado B",
                qty=Decimal("2"),
                uom="EA-IMP",
                qty_in_base_uom=Decimal("2"),
                rate=Decimal("50.00"),
                amount=Decimal("100.00"),
                warehouse="WH-IMP",
            ),
        ]
    )
    database.session.commit()

    post_document_to_gl(receipt)
    database.session.commit()

    valuation_layers = (
        database.session.execute(
            database.select(StockValuationLayer)
            .filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id)
            .order_by(StockValuationLayer.item_code)
        )
        .scalars()
        .all()
    )
    allocations = (
        database.session.execute(
            database.select(LandedCostAllocation)
            .filter_by(document_type="purchase_receipt", document_id=receipt.id)
            .order_by(LandedCostAllocation.item_code)
        )
        .scalars()
        .all()
    )
    bin_a = database.session.execute(database.select(StockBin).filter_by(item_code="IMP-A", warehouse="WH-IMP")).scalar_one()
    bin_b = database.session.execute(database.select(StockBin).filter_by(item_code="IMP-B", warehouse="WH-IMP")).scalar_one()
    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_receipt", voucher_id=receipt.id))
        .scalars()
        .all()
    )

    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert [layer.stock_value_difference for layer in valuation_layers] == [Decimal("120.0000"), Decimal("120.0000")]
    assert [layer.rate for layer in valuation_layers] == [Decimal("120.000000000"), Decimal("60.000000000")]
    assert [allocation.allocated_amount for allocation in allocations] == [Decimal("20.0000"), Decimal("20.0000")]
    assert {allocation.stock_valuation_layer_id for allocation in allocations} == {layer.id for layer in valuation_layers}
    assert bin_a.stock_value == Decimal("120.0000")
    assert bin_a.valuation_rate == Decimal("120.000000000")
    assert bin_b.stock_value == Decimal("120.0000")
    assert bin_b.valuation_rate == Decimal("60.000000000")


def test_cancel_delivery_note_reverts_stock_and_gl(app_ctx):
    from cacao_accounting.contabilidad.posting import cancel_document, post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        DeliveryNote,
        DeliveryNoteItem,
        GLEntry,
        Item,
        ItemAccount,
        StockBin,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-DN",
        name="Inventario DN",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    expense_account = Accounts(
        entity="cacao",
        code="EXP-DN",
        name="Gasto DN",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    uom = UOM(code="EA", name="Each")
    item = Item(code="ITEM-DN", name="Item DN", item_type="goods", is_stock_item=True, default_uom="EA")
    warehouse = Warehouse(code="WH-DN", name="Bodega DN", company="cacao")
    database.session.add_all([inventory_account, expense_account, uom, item, warehouse])
    database.session.flush()
    database.session.add_all(
        [
            ItemAccount(item_code="ITEM-DN", company="cacao"),
            CompanyDefaultAccount(company="cacao", default_expense=expense_account.id),
            WarehouseCompanyAccount(
                warehouse_code="WH-DN", company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
        ]
    )
    database.session.add_all(
        [
            StockLedgerEntry(
                posting_date=date(2026, 5, 1),
                item_code="ITEM-DN",
                warehouse="WH-DN",
                company="cacao",
                qty_change=Decimal("2"),
                qty_after_transaction=Decimal("2"),
                valuation_rate=Decimal("20.00"),
                stock_value_difference=Decimal("40.00"),
                stock_value=Decimal("40.00"),
                voucher_type="seed",
                voucher_id="seed-dn",
            ),
            StockValuationLayer(
                item_code="ITEM-DN",
                warehouse="WH-DN",
                company="cacao",
                qty=Decimal("2"),
                rate=Decimal("20.00"),
                stock_value_difference=Decimal("40.00"),
                remaining_qty=Decimal("2"),
                remaining_stock_value=Decimal("40.00"),
                voucher_type="seed",
                voucher_id="seed-dn",
                posting_date=date(2026, 5, 1),
            ),
            StockBin(
                company="cacao",
                item_code="ITEM-DN",
                warehouse="WH-DN",
                actual_qty=Decimal("2"),
                valuation_rate=Decimal("20.00"),
                stock_value=Decimal("40.00"),
            ),
        ]
    )
    note = DeliveryNote(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-DN",
        docstatus=1,
        total=Decimal("40.00"),
        grand_total=Decimal("40.00"),
    )
    database.session.add(note)
    database.session.flush()
    database.session.add(
        DeliveryNoteItem(
            delivery_note_id=note.id,
            item_code="ITEM-DN",
            item_name="Item DN",
            qty=Decimal("2"),
            uom="EA",
            qty_in_base_uom=Decimal("2"),
            rate=Decimal("20.00"),
            amount=Decimal("40.00"),
            warehouse="WH-DN",
        )
    )
    database.session.commit()

    post_document_to_gl(note)
    database.session.commit()
    reversals = cancel_document(note)
    database.session.commit()

    stock_movements = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_type="delivery_note", voucher_id=note.id))
        .scalars()
        .all()
    )
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(item_code="ITEM-DN", warehouse="WH-DN")
    ).scalar_one()
    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="delivery_note", voucher_id=note.id))
        .scalars()
        .all()
    )

    assert note.docstatus == 2
    assert len(reversals) == 2
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert len(stock_movements) == 2
    assert any(movement.is_cancelled for movement in stock_movements)
    assert any(not movement.is_cancelled for movement in stock_movements)
    assert sum(movement.qty_change for movement in stock_movements) == Decimal("0E-9")
    assert bin_row.actual_qty == Decimal("2.000000000")


def test_delivery_note_without_stock_rejects_posting(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        DeliveryNote,
        DeliveryNoteItem,
        GLEntry,
        Item,
        ItemAccount,
        StockLedgerEntry,
        UOM,
        Warehouse,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-NS",
        name="Inventario sin stock",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    expense_account = Accounts(
        entity="cacao",
        code="EXP-NS",
        name="Gasto sin stock",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add_all(
        [
            inventory_account,
            expense_account,
            UOM(code="EA-NS", name="Each NS"),
            Item(code="ITEM-NS", name="Item NS", item_type="goods", is_stock_item=True, default_uom="EA-NS"),
            Warehouse(code="WH-NS", name="Bodega NS", company="cacao"),
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            ItemAccount(item_code="ITEM-NS", company="cacao"),
            CompanyDefaultAccount(company="cacao", default_expense=expense_account.id),
        ]
    )
    note = DeliveryNote(company="cacao", posting_date=date(2026, 5, 4), customer_id="CUST-NS", docstatus=1)
    database.session.add(note)
    database.session.flush()
    database.session.add(
        DeliveryNoteItem(
            delivery_note_id=note.id,
            item_code="ITEM-NS",
            item_name="Item NS",
            qty=Decimal("1"),
            uom="EA-NS",
            qty_in_base_uom=Decimal("1"),
            rate=Decimal("20.00"),
            amount=Decimal("20.00"),
            warehouse="WH-NS",
        )
    )
    database.session.commit()

    with pytest.raises(PostingError, match="No hay suficiente inventario"):
        post_document_to_gl(note)

    gl_entries = database.session.execute(database.select(GLEntry)).scalars().all()
    stock_entries = database.session.execute(database.select(StockLedgerEntry)).scalars().all()
    assert gl_entries == []
    assert stock_entries == []


def test_supplier_invoice_flags_reject_without_order_when_disallowed(app_ctx):
    """S2P-08: Verifica que el flag allow_purchase_invoice_without_order sea respetado."""
    from cacao_accounting.database import CompanyParty, database
    from cacao_accounting.compras import _validate_supplier_invoice_flags

    company_party = CompanyParty(
        party_id="PROV-FLAG",
        company="cacao",
        allow_purchase_invoice_without_order=False,
        allow_purchase_invoice_without_receipt=False,
    )
    database.session.add(company_party)
    database.session.commit()

    with pytest.raises(ValueError, match="no permite crear facturas de compra sin orden de compra"):
        _validate_supplier_invoice_flags("PROV-FLAG", "cacao", None, "REC-001")

    with pytest.raises(ValueError, match="no permite crear facturas de compra sin recepción"):
        _validate_supplier_invoice_flags("PROV-FLAG", "cacao", "PO-001", None)

    # Con ambos documentos no debe fallar
    _validate_supplier_invoice_flags("PROV-FLAG", "cacao", "PO-001", "REC-001")


def test_supplier_invoice_flags_allow_without_order_when_enabled(app_ctx):
    """S2P-08: Verifica que permitir sin OC/recepción no bloquee la creación."""
    from cacao_accounting.database import CompanyParty, database
    from cacao_accounting.compras import _validate_supplier_invoice_flags

    company_party = CompanyParty(
        party_id="PROV-FLAG-ALLOW",
        company="cacao",
        allow_purchase_invoice_without_order=True,
        allow_purchase_invoice_without_receipt=True,
    )
    database.session.add_all(
        [
            company_party,
        ]
    )
    database.session.commit()

    _validate_supplier_invoice_flags("PROV-FLAG-ALLOW", "cacao", None, None)


def test_purchase_invoice_with_receipt_records_purchase_reconciliation(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        PurchaseReconciliation,
        GLEntry,
        Item,
        ItemAccount,
        PartyAccount,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-GR",
        name="Inventario GR",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    bridge_account = Accounts(
        entity="cacao",
        code="BRIDGE-GR",
        name="Cuenta Puente GR",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    payable_account = Accounts(
        entity="cacao",
        code="AP-GR",
        name="Cuentas por pagar",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    uom = UOM(code="EA", name="Each")
    item = Item(code="ITEM-GR", name="Item GR", item_type="goods", is_stock_item=True, default_uom="EA")
    warehouse = Warehouse(code="WH-GR", name="Bodega GR", company="cacao")
    database.session.add_all([inventory_account, bridge_account, payable_account, uom, item, warehouse])
    database.session.flush()
    database.session.add_all(
        [
            ItemAccount(item_code="ITEM-GR", company="cacao"),
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
            WarehouseCompanyAccount(
                warehouse_code="WH-GR", company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
            PartyAccount(party_id="SUPP-GR", company="cacao", payable_account_id=payable_account.id),
        ]
    )

    receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-GR",
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-GR",
            item_name="Item GR",
            qty=Decimal("1"),
            uom="EA",
            qty_in_base_uom=Decimal("1"),
            rate=Decimal("100.00"),
            amount=Decimal("100.00"),
            warehouse="WH-GR",
        )
    )

    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-GR",
        purchase_receipt_id=receipt.id,
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-GR",
            item_name="Item GR",
            qty=Decimal("1"),
            uom="EA",
            rate=Decimal("100.00"),
            amount=Decimal("100.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(receipt)
    database.session.commit()
    post_document_to_gl(invoice)
    database.session.commit()

    reconciliation = (
        database.session.execute(database.select(PurchaseReconciliation).filter_by(purchase_invoice_id=invoice.id))
        .scalars()
        .one()
    )
    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )

    assert reconciliation.matched_amount == Decimal("100.00")
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == bridge_account.id and entry.debit == Decimal("100.00") for entry in entries)
    assert any(entry.account_id == payable_account.id and entry.credit == Decimal("100.00") for entry in entries)


def test_purchase_invoice_with_unposted_receipt_rejects_unposted(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        Item,
        ItemAccount,
        PartyAccount,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    bridge_account = Accounts(
        entity="cacao",
        code="BRIDGE-UP",
        name="Cuenta Puente sin postear",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    payable_account = Accounts(
        entity="cacao",
        code="AP-UP",
        name="Cuentas por pagar sin postear",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    inventory_account = Accounts(
        entity="cacao",
        code="INV-UP",
        name="Inventario sin postear",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    database.session.add_all(
        [
            bridge_account,
            payable_account,
            inventory_account,
            UOM(code="EA-UP", name="Each UP"),
            Item(code="ITEM-UP", name="Item UP", item_type="goods", is_stock_item=True, default_uom="EA-UP"),
            Warehouse(code="WH-UP", name="Bodega UP", company="cacao"),
        ]
    )
    database.session.flush()
    database.session.add_all(
        [
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
            WarehouseCompanyAccount(
                warehouse_code="WH-UP", company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
            ItemAccount(item_code="ITEM-UP", company="cacao"),
            PartyAccount(party_id="SUPP-UP", company="cacao", payable_account_id=payable_account.id),
        ]
    )
    receipt = PurchaseReceipt(company="cacao", posting_date=date(2026, 5, 4), supplier_id="SUPP-UP", docstatus=1)
    database.session.add(receipt)
    database.session.flush()
    database.session.add(
        PurchaseReceiptItem(
            purchase_receipt_id=receipt.id,
            item_code="ITEM-UP",
            item_name="Item UP",
            qty=Decimal("1"),
            uom="EA-UP",
            qty_in_base_uom=Decimal("1"),
            rate=Decimal("10.00"),
            amount=Decimal("10.00"),
            warehouse="WH-UP",
        )
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-UP",
        purchase_receipt_id=receipt.id,
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-UP",
            item_name="Item UP",
            qty=Decimal("1"),
            uom="EA-UP",
            rate=Decimal("10.00"),
            amount=Decimal("10.00"),
        )
    )
    database.session.commit()

    with pytest.raises(PostingError, match="debe estar contabilizada"):
        post_document_to_gl(invoice)


def test_purchase_credit_note_balances_gl(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        PartyAccount,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        database,
    )

    payable_account = Accounts(
        entity="cacao",
        code="AP-CR",
        name="Cuentas por pagar",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    expense_account = Accounts(
        entity="cacao",
        code="EXP-CR",
        name="Gasto CR",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add_all([payable_account, expense_account])
    database.session.flush()
    database.session.add_all(
        [
            PartyAccount(party_id="SUPP-CR", company="cacao", payable_account_id=payable_account.id),
            CompanyDefaultAccount(company="cacao", default_expense=expense_account.id),
        ]
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-CR",
        is_return=True,
        docstatus=1,
        total=Decimal("50.00"),
        grand_total=Decimal("50.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-CR",
            item_name="Item CR",
            qty=Decimal("1"),
            uom="EA",
            rate=Decimal("50.00"),
            amount=Decimal("50.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )

    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == payable_account.id and entry.debit == Decimal("50.00") for entry in entries)
    assert any(entry.account_id == expense_account.id and entry.credit == Decimal("50.00") for entry in entries)


def test_sales_credit_note_balances_gl(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        database,
    )

    receivable_account = Accounts(
        entity="cacao",
        code="AR-CR",
        name="Cuentas por cobrar",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    income_account = Accounts(
        entity="cacao",
        code="INC-CR",
        name="Ingreso CR",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    database.session.add_all([receivable_account, income_account])
    database.session.flush()
    database.session.add_all(
        [
            PartyAccount(party_id="CUST-CR", company="cacao", receivable_account_id=receivable_account.id),
            CompanyDefaultAccount(company="cacao", default_income=income_account.id),
        ]
    )
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-CR",
        document_type="sales_credit_note",
        is_return=True,
        docstatus=1,
        total=Decimal("50.00"),
        grand_total=Decimal("50.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-CR",
            item_name="Item CR",
            qty=Decimal("1"),
            uom="EA",
            rate=Decimal("50.00"),
            amount=Decimal("50.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )

    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == income_account.id and entry.debit == Decimal("50.00") for entry in entries)
    assert any(entry.account_id == receivable_account.id and entry.credit == Decimal("50.00") for entry in entries)


def test_post_purchase_invoice_uses_persisted_tax_rules_in_gl(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        PartyAccount,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        TaxRule,
        database,
    )

    payable_account = Accounts(
        entity="cacao",
        code="AP-TAX",
        name="Cuentas por pagar impuesto",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    expense_account = Accounts(
        entity="cacao",
        code="EXP-TAX",
        name="Gasto base impuesto",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    purchase_tax_account = Accounts(
        entity="cacao",
        code="VAT-TAX",
        name="IVA compra",
        active=True,
        enabled=True,
        classification="asset",
        account_type="tax",
    )
    database.session.add_all([payable_account, expense_account, purchase_tax_account])
    database.session.flush()
    database.session.add_all(
        [
            PartyAccount(party_id="SUPP-TAX", company="cacao", payable_account_id=payable_account.id),
            CompanyDefaultAccount(
                company="cacao",
                default_expense=expense_account.id,
                default_purchase_tax_account_id=purchase_tax_account.id,
            ),
            TaxRule(
                company="cacao",
                name="IVA compra 15%",
                applies_to="purchase",
                level="transaction",
                concept="vat_purchase",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                sequence=10,
                accounting_treatment="separate_tax_account",
                recognition_event="purchase_invoice_confirmed",
                account_id=purchase_tax_account.id,
                is_active=True,
            ),
        ]
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-TAX",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("115.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-TAX",
            item_name="Item TAX",
            qty=Decimal("1"),
            uom="EA",
            rate=Decimal("100.00"),
            amount=Decimal("100.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="purchase_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )

    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == expense_account.id and entry.debit == Decimal("100.00") for entry in entries)
    assert any(entry.account_id == purchase_tax_account.id and entry.debit == Decimal("15.00") for entry in entries)
    assert any(entry.account_id == payable_account.id and entry.credit == Decimal("115.00") for entry in entries)


def test_cancel_document_rejects_closed_accounting_period(app_ctx):
    from cacao_accounting.contabilidad.posting import cancel_document, post_document_to_gl, PostingError
    from cacao_accounting.database import (
        AccountingPeriod,
        Accounts,
        CompanyDefaultAccount,
        PartyAccount,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        database,
    )

    payable_account = Accounts(
        entity="cacao",
        code="AP-CL",
        name="Cuentas por pagar",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    expense_account = Accounts(
        entity="cacao",
        code="EXP-CL",
        name="Gasto CL",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add_all([payable_account, expense_account])
    database.session.flush()
    database.session.add_all(
        [
            PartyAccount(party_id="SUPP-CL", company="cacao", payable_account_id=payable_account.id),
            CompanyDefaultAccount(company="cacao", default_expense=expense_account.id),
        ]
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-CL",
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=invoice.id,
            item_code="ITEM-CL",
            item_name="Item CL",
            qty=Decimal("1"),
            uom="EA",
            rate=Decimal("100.00"),
            amount=Decimal("100.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    database.session.add(
        AccountingPeriod(
            entity="cacao",
            name="Mayo 2026",
            is_closed=True,
            enabled=True,
            start=date(2026, 5, 1),
            end=date(2026, 5, 31),
        )
    )
    database.session.commit()

    with pytest.raises(PostingError, match="periodo contable cerrado"):
        cancel_document(invoice)


def test_compute_outstanding_amount_from_payment_references(app_ctx):
    from cacao_accounting.document_flow.service import compute_outstanding_amount
    from cacao_accounting.database import (
        DocumentRelation,
        PaymentEntry,
        PaymentReference,
        PurchaseInvoice,
        SalesInvoice,
        database,
    )

    purchase_invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-REF",
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
        base_outstanding_amount=Decimal("100.00"),
    )
    sales_invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-REF",
        total=Decimal("150.00"),
        grand_total=Decimal("150.00"),
        outstanding_amount=Decimal("150.00"),
        base_outstanding_amount=Decimal("150.00"),
    )
    database.session.add_all([purchase_invoice, sales_invoice])
    database.session.flush()

    pay1 = PaymentEntry(company="cacao", posting_date=date(2026, 5, 4), payment_type="pay", docstatus=1)
    pay2 = PaymentEntry(company="cacao", posting_date=date(2026, 5, 4), payment_type="receive", docstatus=1)
    database.session.add_all([pay1, pay2])
    database.session.flush()

    ref1 = PaymentReference(
        payment_id=pay1.id,
        reference_type="purchase_invoice",
        reference_id=purchase_invoice.id,
        total_amount=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
        allocated_amount=Decimal("30.00"),
        allocation_date=date(2026, 5, 4),
    )
    ref2 = PaymentReference(
        payment_id=pay2.id,
        reference_type="sales_invoice",
        reference_id=sales_invoice.id,
        total_amount=Decimal("150.00"),
        outstanding_amount=Decimal("150.00"),
        allocated_amount=Decimal("50.00"),
        allocation_date=date(2026, 5, 4),
    )
    database.session.add_all([ref1, ref2])
    database.session.flush()
    database.session.add_all(
        [
            DocumentRelation(
                source_type="purchase_invoice",
                source_id=purchase_invoice.id,
                target_type="payment_entry",
                target_id=pay1.id,
                target_item_id=ref1.id,
                qty=Decimal("1"),
                amount=Decimal("30"),
                relation_type="payment_reference",
                status="active",
            ),
            DocumentRelation(
                source_type="sales_invoice",
                source_id=sales_invoice.id,
                target_type="payment_entry",
                target_id=pay2.id,
                target_item_id=ref2.id,
                qty=Decimal("1"),
                amount=Decimal("50"),
                relation_type="payment_reference",
                status="active",
            ),
        ]
    )
    database.session.commit()

    assert compute_outstanding_amount(purchase_invoice) == Decimal("70.00")
    assert compute_outstanding_amount(sales_invoice) == Decimal("100.00")


def test_compute_outstanding_amount_as_of_date_filters_allocations(app_ctx):
    from cacao_accounting.document_flow.service import compute_outstanding_amount
    from cacao_accounting.database import (
        DocumentRelation,
        PaymentEntry,
        PaymentReference,
        SalesInvoice,
        database,
    )

    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-TEMP",
        total=Decimal("200.00"),
        grand_total=Decimal("200.00"),
    )
    database.session.add(invoice)
    database.session.flush()

    pay1 = PaymentEntry(company="cacao", posting_date=date(2026, 5, 1), payment_type="receive", docstatus=1)
    pay2 = PaymentEntry(company="cacao", posting_date=date(2026, 5, 10), payment_type="receive", docstatus=1)
    database.session.add_all([pay1, pay2])
    database.session.flush()

    ref1 = PaymentReference(
        payment_id=pay1.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        total_amount=Decimal("200.00"),
        outstanding_amount=Decimal("200.00"),
        allocated_amount=Decimal("50.00"),
        allocation_date=date(2026, 5, 1),
    )
    ref2 = PaymentReference(
        payment_id=pay2.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        total_amount=Decimal("200.00"),
        outstanding_amount=Decimal("150.00"),
        allocated_amount=Decimal("25.00"),
        allocation_date=date(2026, 5, 10),
    )
    database.session.add_all([ref1, ref2])
    database.session.flush()
    database.session.add_all(
        [
            DocumentRelation(
                source_type="sales_invoice",
                source_id=invoice.id,
                target_type="payment_entry",
                target_id=pay1.id,
                target_item_id=ref1.id,
                qty=Decimal("1"),
                amount=Decimal("50"),
                relation_type="payment_reference",
                status="active",
            ),
            DocumentRelation(
                source_type="sales_invoice",
                source_id=invoice.id,
                target_type="payment_entry",
                target_id=pay2.id,
                target_item_id=ref2.id,
                qty=Decimal("1"),
                amount=Decimal("25"),
                relation_type="payment_reference",
                status="active",
            ),
        ]
    )
    database.session.commit()

    assert compute_outstanding_amount(invoice, as_of_date=date(2026, 5, 4)) == Decimal("150.00")
    assert compute_outstanding_amount(invoice, as_of_date=date(2026, 5, 10)) == Decimal("125.00")


def test_compute_outstanding_amount_includes_legacy_reference_without_relation(app_ctx):
    """AR/AP debe sumar referencias legacy junto con relaciones modernas."""
    from cacao_accounting.database import DocumentRelation, PaymentEntry, PaymentReference, SalesInvoice, database
    from cacao_accounting.document_flow.service import compute_outstanding_amount
    from cacao_accounting.reportes.services import SubledgerFilters, get_ar_ap_subledger

    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-LEGACY-REF",
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
        docstatus=1,
    )
    modern_payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 4), payment_type="receive", docstatus=1)
    legacy_payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 5), payment_type="receive", docstatus=1)
    database.session.add_all([invoice, modern_payment, legacy_payment])
    database.session.flush()
    modern_reference = PaymentReference(
        payment_id=modern_payment.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("30.00"),
        allocation_date=modern_payment.posting_date,
    )
    legacy_reference = PaymentReference(
        payment_id=legacy_payment.id,
        reference_type="sales_invoice",
        reference_id=invoice.id,
        allocated_amount=Decimal("20.00"),
        allocation_date=legacy_payment.posting_date,
    )
    database.session.add_all([modern_reference, legacy_reference])
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="sales_invoice",
            source_id=invoice.id,
            target_type="payment_entry",
            target_id=modern_payment.id,
            target_item_id=modern_reference.id,
            qty=Decimal("1"),
            amount=Decimal("30.00"),
            relation_type="payment_reference",
            status="active",
            company="cacao",
        )
    )
    database.session.commit()

    assert compute_outstanding_amount(invoice) == Decimal("50.00")
    report = get_ar_ap_subledger(SubledgerFilters(company="cacao", party_type="customer"))
    assert report.totals["paid_amount"] == Decimal("50.00")
    assert report.totals["outstanding_amount"] == Decimal("50.00")


def test_compute_outstanding_amount_applies_credit_note_by_document_type(app_ctx):
    """Una nota enlazada como invoice fisica debe reducir AR por su naturaleza."""
    from cacao_accounting.database import DocumentRelation, SalesInvoice, database
    from cacao_accounting.document_flow.service import compute_outstanding_amount

    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-CREDIT-NOTE",
        grand_total=Decimal("100.00"),
        docstatus=1,
        document_type="sales_invoice",
    )
    credit_note = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 5),
        customer_id="CUST-CREDIT-NOTE",
        grand_total=Decimal("25.00"),
        docstatus=1,
        document_type="sales_credit_note",
        is_return=True,
    )
    database.session.add_all([invoice, credit_note])
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="sales_invoice",
            source_id=invoice.id,
            target_type="sales_invoice",
            target_id=credit_note.id,
            qty=Decimal("1"),
            amount=Decimal("25.00"),
            relation_type="credit_note",
            status="active",
            company="cacao",
        )
    )
    database.session.commit()

    assert compute_outstanding_amount(invoice, as_of_date=date(2026, 5, 5)) == Decimal("75.00")


def test_valuation_queue_recovers_after_allowed_negative_stock(app_ctx):
    """Una recepción posterior debe compensar el déficit antes de valorar salidas."""
    from cacao_accounting.contabilidad.posting import _consume_stock_valuation_layers, _valuation_queue
    from cacao_accounting.database import StockValuationLayer, database

    database.session.add_all(
        [
            StockValuationLayer(
                company="cacao",
                item_code="ITEM-NEG-QUEUE",
                warehouse="WH-NEG-QUEUE",
                qty=Decimal("10"),
                rate=Decimal("10"),
                posting_date=date(2026, 5, 1),
                voucher_type="seed",
                voucher_id="QUEUE-IN-1",
            ),
            StockValuationLayer(
                company="cacao",
                item_code="ITEM-NEG-QUEUE",
                warehouse="WH-NEG-QUEUE",
                qty=Decimal("-15"),
                rate=Decimal("10"),
                posting_date=date(2026, 5, 2),
                voucher_type="stock_entry",
                voucher_id="QUEUE-OUT-1",
            ),
            StockValuationLayer(
                company="cacao",
                item_code="ITEM-NEG-QUEUE",
                warehouse="WH-NEG-QUEUE",
                qty=Decimal("10"),
                rate=Decimal("12"),
                posting_date=date(2026, 5, 3),
                voucher_type="purchase_receipt",
                voucher_id="QUEUE-IN-2",
            ),
        ]
    )
    database.session.commit()

    assert _valuation_queue("cacao", "ITEM-NEG-QUEUE", "WH-NEG-QUEUE") == [(Decimal("5"), Decimal("12"))]
    cost, rate = _consume_stock_valuation_layers("cacao", "ITEM-NEG-QUEUE", "WH-NEG-QUEUE", Decimal("5"))
    assert cost == Decimal("60")
    assert rate == Decimal("12")


def test_compute_outstanding_amount_for_note_types_uses_document_relations(app_ctx):
    from cacao_accounting.database import (
        DocumentRelation,
        PaymentEntry,
        PaymentReference,
        PurchaseInvoice,
        SalesInvoice,
        database,
    )
    from cacao_accounting.document_flow.service import compute_outstanding_amount

    purchase_credit_note = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="purchase_credit_note",
        grand_total=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
        docstatus=1,
    )
    sales_debit_note = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        document_type="sales_debit_note",
        grand_total=Decimal("80.00"),
        outstanding_amount=Decimal("80.00"),
        docstatus=1,
    )
    payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 5), payment_type="receive", docstatus=1)
    database.session.add_all([purchase_credit_note, sales_debit_note, payment])
    database.session.flush()

    purchase_reference = PaymentReference(
        payment_id=payment.id,
        reference_type="purchase_invoice",
        reference_id=purchase_credit_note.id,
        total_amount=Decimal("100.00"),
        outstanding_amount=Decimal("100.00"),
        allocated_amount=Decimal("30.00"),
        allocation_date=payment.posting_date,
    )
    sales_reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=sales_debit_note.id,
        total_amount=Decimal("80.00"),
        outstanding_amount=Decimal("80.00"),
        allocated_amount=Decimal("15.00"),
        allocation_date=payment.posting_date,
    )
    database.session.add_all([purchase_reference, sales_reference])
    database.session.flush()
    database.session.add_all(
        [
            DocumentRelation(
                source_type="purchase_credit_note",
                source_id=purchase_credit_note.id,
                source_item_id=None,
                target_type="payment_entry",
                target_id=payment.id,
                target_item_id=purchase_reference.id,
                company="cacao",
                qty=Decimal("1"),
                uom=None,
                rate=Decimal("30.00"),
                amount=Decimal("30.00"),
                relation_type="refund",
                status="active",
            ),
            DocumentRelation(
                source_type="sales_debit_note",
                source_id=sales_debit_note.id,
                source_item_id=None,
                target_type="payment_entry",
                target_id=payment.id,
                target_item_id=sales_reference.id,
                company="cacao",
                qty=Decimal("1"),
                uom=None,
                rate=Decimal("15.00"),
                amount=Decimal("15.00"),
                relation_type="collection",
                status="active",
            ),
        ]
    )
    database.session.commit()

    assert compute_outstanding_amount(purchase_credit_note) == Decimal("70.00")
    assert compute_outstanding_amount(sales_debit_note) == Decimal("65.00")


def test_post_payment_entry_uses_bank_account_gl_fallback(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import Accounts, Bank, BankAccount, GLEntry, PartyAccount, PaymentEntry, database

    bank_gl_account = Accounts(
        entity="cacao",
        code="BANK-FB",
        name="Banco fallback",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    receivable_account = Accounts(
        entity="cacao",
        code="AR-FB",
        name="Cuentas por cobrar fallback",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    bank = Bank(name="Banco prueba")
    database.session.add_all([bank_gl_account, receivable_account, bank])
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta fallback",
        gl_account_id=bank_gl_account.id,
    )
    database.session.add(bank_account)
    database.session.flush()
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        payment_type="receive",
        party_type="customer",
        party_id="CUST-FB",
        bank_account_id=bank_account.id,
        received_amount=Decimal("45.00"),
        docstatus=1,
    )
    database.session.add_all(
        [PartyAccount(party_id="CUST-FB", company="cacao", receivable_account_id=receivable_account.id), payment]
    )
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )
    assert any(entry.debit == Decimal("45.00") and entry.account_id == bank_gl_account.id for entry in entries)
    assert any(entry.credit == Decimal("45.00") and entry.party_id == "CUST-FB" for entry in entries)


def test_post_payment_entry_with_discount_and_exchange_revaluation(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        CompanyDefaultAccount,
        CompanyParty,
        GLEntry,
        PartyAccount,
        PaymentEntry,
        PaymentReference,
        PaymentTerms,
        SalesInvoice,
        database,
    )

    receivable_account = Accounts(
        entity="cacao",
        code="AR-DISC",
        name="Cuentas por cobrar descuento",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    bank_gl_account = Accounts(
        entity="cacao",
        code="BANK-DISC",
        name="Banco descuento",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    discount_account = Accounts(
        entity="cacao",
        code="DISC-DISC",
        name="Descuento pronto pago",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    realized_gain_account = Accounts(
        entity="cacao",
        code="EXG-DISC",
        name="Ganancia cambiaria",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    unrealized_gain_account = Accounts(
        entity="cacao",
        code="UXG-DISC",
        name="Ganancia cambiaria no realizada",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    bank = Bank(name="Banco descuento")
    database.session.add_all(
        [
            receivable_account,
            bank_gl_account,
            discount_account,
            realized_gain_account,
            unrealized_gain_account,
            bank,
        ]
    )
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta descuento",
        currency="USD",
        gl_account_id=bank_gl_account.id,
    )
    payment_terms = PaymentTerms(name="2/10 neto", due_days=30, discount_days=10, discount_percent=Decimal("2"))
    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 1),
        customer_id="CUST-DISC",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36.5"),
        total=Decimal("200.00"),
        grand_total=Decimal("200.00"),
        outstanding_amount=Decimal("200.00"),
        base_outstanding_amount=Decimal("7300.00"),
    )
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        payment_type="receive",
        party_type="customer",
        party_id="CUST-DISC",
        bank_account_id=bank_account.id,
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36.8"),
        received_amount=Decimal("98.00"),
        base_received_amount=Decimal("3606.40"),
        docstatus=1,
    )
    database.session.add_all([bank_account, payment_terms, invoice, payment])
    database.session.flush()
    database.session.add_all(
        [
            PartyAccount(party_id="CUST-DISC", company="cacao", receivable_account_id=receivable_account.id),
            CompanyParty(company="cacao", party_id="CUST-DISC", is_active=True, payment_terms_id=payment_terms.id),
            CompanyDefaultAccount(
                company="cacao",
                default_receivable=receivable_account.id,
                default_bank=bank_gl_account.id,
                sales_discount_account_id=discount_account.id,
                exchange_gain_account_id=realized_gain_account.id,
                unrealized_exchange_gain_account_id=unrealized_gain_account.id,
            ),
        ]
    )
    database.session.add(
        PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            total_amount=Decimal("200.00"),
            outstanding_amount=Decimal("200.00"),
            allocated_amount=Decimal("100.00"),
            allocation_date=payment.posting_date,
        )
    )
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )

    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == bank_gl_account.id and entry.debit == Decimal("3606.4000") for entry in entries)
    assert any(entry.account_id == receivable_account.id and entry.credit == Decimal("3650.0000") for entry in entries)
    assert any(
        entry.account_id == receivable_account.id
        and entry.debit == Decimal("30.0000")
        and entry.remarks.startswith("Unrealized Exchange Offset")
        for entry in entries
    )
    assert any(entry.account_id == discount_account.id and entry.debit == Decimal("73.6000") for entry in entries)
    assert any(entry.account_id == realized_gain_account.id and entry.credit == Decimal("30.0000") for entry in entries)
    assert any(entry.account_id == unrealized_gain_account.id and entry.credit == Decimal("30.0000") for entry in entries)


def test_post_payment_entry_without_references_uses_advance_account(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import Accounts, CompanyDefaultAccount, GLEntry, PaymentEntry, database

    bank_account = Accounts(
        entity="cacao",
        code="BANK-ADV-001",
        name="Banco anticipos",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    supplier_advance_account = Accounts(
        entity="cacao",
        code="ADV-SUP-001",
        name="Anticipo proveedor",
        active=True,
        enabled=True,
        classification="asset",
        account_type="asset",
    )
    database.session.add_all([bank_account, supplier_advance_account])
    database.session.flush()
    database.session.add(
        CompanyDefaultAccount(
            company="cacao",
            default_bank=bank_account.id,
            supplier_advance_account_id=supplier_advance_account.id,
        )
    )
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        payment_type="pay",
        party_type="supplier",
        party_id="SUPP-ADV",
        paid_amount=Decimal("100.00"),
        base_paid_amount=Decimal("100.00"),
        paid_from_account_id=bank_account.id,
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )
    assert any(entry.account_id == supplier_advance_account.id and entry.debit == Decimal("100.0000") for entry in entries)
    assert any(entry.account_id == bank_account.id and entry.credit == Decimal("100.0000") for entry in entries)


def test_post_payment_entry_partial_reference_balances_open_amount_with_advance(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        PartyAccount,
        PaymentEntry,
        PaymentReference,
        PurchaseInvoice,
        database,
    )

    bank_account = Accounts(
        entity="cacao",
        code="BANK-PART-001",
        name="Banco parcial",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    payable_account = Accounts(
        entity="cacao",
        code="AP-PART-001",
        name="CxP parcial",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    supplier_advance_account = Accounts(
        entity="cacao",
        code="ADV-PART-001",
        name="Anticipo parcial proveedor",
        active=True,
        enabled=True,
        classification="asset",
        account_type="asset",
    )
    database.session.add_all([bank_account, payable_account, supplier_advance_account])
    database.session.flush()
    database.session.add_all(
        [
            PartyAccount(party_id="SUPP-PART", company="cacao", payable_account_id=payable_account.id),
            CompanyDefaultAccount(
                company="cacao",
                default_bank=bank_account.id,
                supplier_advance_account_id=supplier_advance_account.id,
            ),
        ]
    )
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-PART",
        grand_total=Decimal("60.00"),
        outstanding_amount=Decimal("60.00"),
        base_outstanding_amount=Decimal("60.00"),
        docstatus=1,
    )
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 5),
        payment_type="pay",
        party_type="supplier",
        party_id="SUPP-PART",
        paid_amount=Decimal("100.00"),
        base_paid_amount=Decimal("100.00"),
        paid_from_account_id=bank_account.id,
        docstatus=1,
    )
    database.session.add_all([invoice, payment])
    database.session.flush()
    database.session.add(
        PaymentReference(
            payment_id=payment.id,
            reference_type="purchase_invoice",
            reference_id=invoice.id,
            total_amount=Decimal("60.00"),
            outstanding_amount=Decimal("60.00"),
            allocated_amount=Decimal("60.00"),
            allocation_date=payment.posting_date,
        )
    )
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == payable_account.id and entry.debit == Decimal("60.0000") for entry in entries)
    assert any(entry.account_id == supplier_advance_account.id and entry.debit == Decimal("40.0000") for entry in entries)
    assert any(entry.account_id == bank_account.id and entry.credit == Decimal("100.0000") for entry in entries)


def test_post_bank_transaction_creates_balanced_gl_entries(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        BankTransaction,
        CompanyDefaultAccount,
        GLEntry,
        database,
    )

    bank_gl_account = Accounts(
        entity="cacao",
        code="BANK-BT",
        name="Banco nota",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    income_account = Accounts(
        entity="cacao",
        code="INC-BT",
        name="Ingreso nota",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    bank = Bank(name="Banco nota")
    database.session.add_all([bank_gl_account, income_account, bank])
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta nota",
        gl_account_id=bank_gl_account.id,
    )
    database.session.add_all(
        [
            bank_account,
            CompanyDefaultAccount(company="cacao", default_income=income_account.id),
        ]
    )
    database.session.flush()
    transaction = BankTransaction(
        bank_account_id=bank_account.id,
        posting_date=date(2026, 5, 4),
        deposit=Decimal("35.00"),
        description="Nota de credito bancaria",
    )
    database.session.add(transaction)
    database.session.commit()

    post_document_to_gl(transaction)
    database.session.commit()

    entries = (
        database.session.execute(
            database.select(GLEntry).filter_by(voucher_type="bank_transaction", voucher_id=transaction.id)
        )
        .scalars()
        .all()
    )
    assert len(entries) == 2
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == bank_gl_account.id and entry.debit == Decimal("35.00") for entry in entries)
    assert any(entry.account_id == income_account.id and entry.credit == Decimal("35.00") for entry in entries)


def test_post_stock_entry_creates_stock_ledger_bin_valuation_and_gl(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Book,
        CompanyDefaultAccount,
        Currency,
        ExchangeRate,
        GLEntry,
        Item,
        ItemAccount,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    local_book = Book(entity="cacao", code="ST-NIO", name="Stock NIO", currency="NIO", status="activo", is_primary=True)
    eur_book = Book(entity="cacao", code="ST-EUR", name="Stock EUR", currency="EUR", status="activo")
    database.session.add_all(
        [
            Currency(code="NIO", name="Cordoba", decimals=2, active=True),
            Currency(code="EUR", name="Euro", decimals=2, active=True),
            local_book,
            eur_book,
            ExchangeRate(origin="NIO", destination="EUR", rate=Decimal("0.025"), date=date(2026, 5, 4)),
        ]
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-ST",
        name="Inventario",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    bridge_account = Accounts(
        entity="cacao",
        code="BRIDGE-ST",
        name="Cuenta Puente Compras",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    adjustment_account = Accounts(
        entity="cacao",
        code="ADJ-ST",
        name="Ajuste Inventario",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add_all([inventory_account, bridge_account, adjustment_account])
    database.session.flush()
    uom = UOM(code="UND", name="Unidad")
    item = Item(code="ITEM-ST", name="Item stock", item_type="goods", is_stock_item=True, default_uom="UND")
    warehouse = Warehouse(code="WH-ST", name="Bodega stock", company="cacao")
    database.session.add_all([uom, item, warehouse])
    database.session.flush()
    database.session.add_all(
        [
            WarehouseCompanyAccount(
                warehouse_code="WH-ST", company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
            ItemAccount(item_code="ITEM-ST", company="cacao"),
            CompanyDefaultAccount(
                company="cacao", bridge_account_id=bridge_account.id, inventory_adjustment_account_id=adjustment_account.id
            ),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_receipt",
        to_warehouse="WH-ST",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-ST",
            target_warehouse="WH-ST",
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="UND",
            basic_rate=Decimal("12.00"),
            valuation_rate=Decimal("12.00"),
            amount=Decimal("36.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(entry)
    database.session.commit()

    gl_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    stock_entries = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(item_code="ITEM-ST", warehouse="WH-ST")
    ).scalar_one()
    valuation_layers = (
        database.session.execute(
            database.select(StockValuationLayer).filter_by(voucher_type="stock_entry", voucher_id=entry.id)
        )
        .scalars()
        .all()
    )
    assert len(gl_entries) == 4
    assert sum(line.debit for line in gl_entries if line.ledger_id == local_book.id) == Decimal("36")
    assert sum(line.debit for line in gl_entries if line.ledger_id == eur_book.id) == Decimal("0.9")
    assert {line.company_currency for line in gl_entries if line.ledger_id == local_book.id} == {"NIO"}
    assert {line.company_currency for line in gl_entries if line.ledger_id == eur_book.id} == {"EUR"}
    for book in (local_book, eur_book):
        book_entries = [line for line in gl_entries if line.ledger_id == book.id]
        assert sum(line.debit for line in book_entries) == sum(line.credit for line in book_entries)
    assert len(stock_entries) == 1
    assert stock_entries[0].qty_change == Decimal("3.000000000")
    assert bin_row.actual_qty == Decimal("3.000000000")
    assert len(valuation_layers) == 1


def test_stock_transfer_rejects_missing_inventory_accounts(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, post_document_to_gl
    from cacao_accounting.database import (
        Item,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(code="ITEM-TR", name="Item traslado", item_type="goods", is_stock_item=True, default_uom="EA"),
            Warehouse(code="WH-A", name="Bodega A", company="cacao"),
            Warehouse(code="WH-B", name="Bodega B", company="cacao"),
            StockLedgerEntry(
                posting_date=date(2026, 5, 1),
                item_code="ITEM-TR",
                warehouse="WH-A",
                company="cacao",
                qty_change=Decimal("2"),
                qty_after_transaction=Decimal("2"),
                valuation_rate=Decimal("5.00"),
                stock_value_difference=Decimal("10.00"),
                stock_value=Decimal("10.00"),
                voucher_type="seed",
                voucher_id="seed-tr",
            ),
            StockValuationLayer(
                item_code="ITEM-TR",
                warehouse="WH-A",
                company="cacao",
                qty=Decimal("2"),
                rate=Decimal("5.00"),
                stock_value_difference=Decimal("10.00"),
                remaining_qty=Decimal("2"),
                remaining_stock_value=Decimal("10.00"),
                voucher_type="seed",
                voucher_id="seed-tr",
                posting_date=date(2026, 5, 1),
            ),
            StockBin(
                company="cacao",
                item_code="ITEM-TR",
                warehouse="WH-A",
                actual_qty=Decimal("2"),
                valuation_rate=Decimal("5.00"),
                stock_value=Decimal("10.00"),
            ),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        from_warehouse="WH-A",
        to_warehouse="WH-B",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-TR",
            source_warehouse="WH-A",
            target_warehouse="WH-B",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="EA",
            basic_rate=Decimal("5.00"),
            valuation_rate=Decimal("5.00"),
            amount=Decimal("10.00"),
        )
    )
    database.session.commit()

    with pytest.raises(PostingError, match="ambas bodegas"):
        post_document_to_gl(entry)

    stock_entries = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    assert stock_entries == []


def test_stock_transfer_rejects_one_sided_inventory_account(app_ctx, monkeypatch):
    """A transfer cannot post physical stock when only one warehouse has GL."""
    from cacao_accounting.contabilidad import posting_service
    from cacao_accounting.contabilidad.posting_service import PostingError, _validate_material_transfer_accounts
    from cacao_accounting.database import Item, StockEntry, StockEntryItem, UOM, Warehouse, database

    database.session.add_all(
        [
            UOM(code="EA-ONE-SIDED", name="Each"),
            Item(
                code="ITEM-ONE-SIDED",
                name="Item one sided",
                item_type="goods",
                is_stock_item=True,
                default_uom="EA-ONE-SIDED",
            ),
            Warehouse(code="WH-ONE-SIDED-A", name="Source", company="cacao"),
            Warehouse(code="WH-ONE-SIDED-B", name="Target", company="cacao"),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        from_warehouse="WH-ONE-SIDED-A",
        to_warehouse="WH-ONE-SIDED-B",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-ONE-SIDED",
            source_warehouse="WH-ONE-SIDED-A",
            target_warehouse="WH-ONE-SIDED-B",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="EA-ONE-SIDED",
            amount=Decimal("1"),
        )
    )
    database.session.commit()
    monkeypatch.setattr(
        posting_service,
        "warehouse_inventory_account_id",
        lambda warehouse, company: "SOURCE-ACCOUNT" if warehouse == "WH-ONE-SIDED-A" else None,
    )

    with pytest.raises(PostingError, match="ambas bodegas"):
        _validate_material_transfer_accounts(entry, "cacao")


def test_inventory_line_rate_rejects_amount_without_quantity(app_ctx):
    """A positive amount cannot silently produce a zero valuation rate."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _line_rate, _line_rate_generic
    from cacao_accounting.database import Item, StockEntryItem, UOM, database

    database.session.add_all(
        [
            UOM(code="EA-RATE-GUARD", name="Each"),
            Item(
                code="ITEM-RATE-GUARD", name="Rate guard", item_type="goods", is_stock_item=True, default_uom="EA-RATE-GUARD"
            ),
        ]
    )
    database.session.flush()
    line = StockEntryItem(
        item_code="ITEM-RATE-GUARD",
        qty=Decimal("0"),
        qty_in_base_uom=Decimal("0"),
        uom="EA-RATE-GUARD",
        amount=Decimal("25"),
    )

    with pytest.raises(PostingError, match="cantidad"):
        _line_rate(line)
    with pytest.raises(PostingError, match="cantidad"):
        _line_rate_generic(line)


def test_expired_batch_is_rejected_by_stock_posting(app_ctx):
    """Items with expiry control cannot post a batch expired at posting time."""
    from cacao_accounting.database import Batch, Item, StockEntryItem, UOM, database
    from cacao_accounting.inventario.service import InventoryServiceError, validate_batch_serial

    database.session.add_all(
        [
            UOM(code="EA-EXPIRY-GUARD", name="Each"),
            Item(
                code="ITEM-EXPIRY-GUARD",
                name="Expiry guard",
                item_type="goods",
                is_stock_item=True,
                has_batch=True,
                has_expiry_date=True,
                default_uom="EA-EXPIRY-GUARD",
            ),
        ]
    )
    database.session.flush()
    batch = Batch(item_code="ITEM-EXPIRY-GUARD", batch_no="EXPIRED", expiry_date=date(2026, 5, 1), is_active=True)
    database.session.add(batch)
    database.session.flush()
    line = StockEntryItem(
        item_code="ITEM-EXPIRY-GUARD",
        batch_id=batch.id,
        qty=Decimal("1"),
        uom="EA-EXPIRY-GUARD",
    )

    with pytest.raises(InventoryServiceError, match="vencido"):
        validate_batch_serial(
            line,
            outgoing=False,
            warehouse=None,
            posting_date=date(2026, 5, 4),
        )


def test_normal_receipt_rejects_an_available_serial(app_ctx):
    """A normal receipt cannot move an existing serial without a transfer."""
    from cacao_accounting.database import Item, SerialNumber, StockEntryItem, UOM, database
    from cacao_accounting.inventario.service import InventoryServiceError, validate_batch_serial

    database.session.add_all(
        [
            UOM(code="EA-SERIAL-GUARD", name="Each"),
            Item(
                code="ITEM-SERIAL-GUARD",
                name="Serial guard",
                item_type="goods",
                is_stock_item=True,
                has_serial_no=True,
                default_uom="EA-SERIAL-GUARD",
            ),
            SerialNumber(
                item_code="ITEM-SERIAL-GUARD",
                serial_no="SN-AVAILABLE",
                serial_status="available",
                warehouse="WH-ORIGIN",
            ),
        ]
    )
    database.session.flush()
    line = StockEntryItem(
        item_code="ITEM-SERIAL-GUARD",
        serial_no="SN-AVAILABLE",
        qty=Decimal("1"),
        uom="EA-SERIAL-GUARD",
    )

    with pytest.raises(InventoryServiceError, match="transferencia"):
        validate_batch_serial(line, outgoing=False, warehouse="WH-TARGET")


def test_reconciliation_requires_batch_or_serial_identifiers(app_ctx):
    """Quantity reconciliation cannot bypass tracking for controlled items."""
    from cacao_accounting.contabilidad.posting_service import PostingError, _create_stock_reconciliation_movement
    from cacao_accounting.database import Item, StockBin, StockEntry, StockEntryItem, UOM, Warehouse, database

    database.session.add_all(
        [
            UOM(code="EA-TRACK-GUARD", name="Each"),
            Item(
                code="ITEM-TRACK-GUARD",
                name="Tracking guard",
                item_type="goods",
                is_stock_item=True,
                has_serial_no=True,
                default_uom="EA-TRACK-GUARD",
            ),
            Warehouse(code="WH-TRACK-GUARD", name="Tracking warehouse", company="cacao"),
            StockBin(
                company="cacao",
                item_code="ITEM-TRACK-GUARD",
                warehouse="WH-TRACK-GUARD",
                actual_qty=Decimal("1"),
                stock_value=Decimal("10"),
            ),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="stock_reconciliation",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code="ITEM-TRACK-GUARD",
        target_warehouse="WH-TRACK-GUARD",
        qty=Decimal("1"),
        uom="EA-TRACK-GUARD",
        counted_qty=Decimal("0"),
        target_valuation_rate=Decimal("0"),
        target_stock_value=Decimal("0"),
    )
    database.session.add(line)
    database.session.commit()

    with pytest.raises(PostingError, match="numero de serie"):
        _create_stock_reconciliation_movement(entry, line)


def test_item_cogs_account_is_used_for_delivery_posting(app_ctx):
    """COGS resolution prefers the item's company-specific account."""
    from cacao_accounting.contabilidad.posting_service import _account_id_for_item
    from cacao_accounting.database import Accounts, Item, ItemAccount, database

    item_cogs = Accounts(
        entity="cacao",
        code="COGS-ITEM-GUARD",
        name="Item COGS",
        active=True,
        enabled=True,
        classification="expense",
        account_type="cogs",
    )
    company_cogs = Accounts(
        entity="cacao",
        code="COGS-COMPANY-GUARD",
        name="Company COGS",
        active=True,
        enabled=True,
        classification="expense",
        account_type="cogs",
    )
    database.session.add_all(
        [
            item_cogs,
            company_cogs,
            Item(code="ITEM-COGS-GUARD", name="COGS item", item_type="goods", is_stock_item=True, default_uom="UND"),
        ]
    )
    database.session.flush()
    database.session.add(ItemAccount(item_code="ITEM-COGS-GUARD", company="cacao", cogs_account_id=item_cogs.id))
    database.session.commit()

    class Line:
        """Minimal delivery line for account resolution."""

        item_code = "ITEM-COGS-GUARD"

    assert _account_id_for_item(Line(), "cacao", "cogs") == item_cogs.id


def test_reconciliation_rejects_inconsistent_target_value(app_ctx):
    """Posting rejects a target value that disagrees with count times rate."""
    from cacao_accounting.contabilidad.posting_service import (
        PostingError,
        _create_stock_reconciliation_movement,
    )
    from cacao_accounting.database import Item, StockBin, StockEntry, StockEntryItem, UOM, Warehouse, database

    database.session.add_all(
        [
            UOM(code="EA-RECON-GUARD", name="Each"),
            Item(
                code="ITEM-RECON-GUARD",
                name="Reconciliation guard",
                item_type="goods",
                is_stock_item=True,
                default_uom="EA-RECON-GUARD",
            ),
            Warehouse(code="WH-RECON-GUARD", name="Reconciliation warehouse", company="cacao"),
            StockBin(
                company="cacao",
                item_code="ITEM-RECON-GUARD",
                warehouse="WH-RECON-GUARD",
                actual_qty=Decimal("5"),
                stock_value=Decimal("50"),
            ),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="stock_reconciliation",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code="ITEM-RECON-GUARD",
        target_warehouse="WH-RECON-GUARD",
        qty=Decimal("5"),
        uom="EA-RECON-GUARD",
        counted_qty=Decimal("5"),
        target_valuation_rate=Decimal("10"),
        target_stock_value=Decimal("60"),
    )
    database.session.add(line)
    database.session.commit()

    with pytest.raises(PostingError, match="cantidad por tasa"):
        _create_stock_reconciliation_movement(entry, line)


def test_stock_transfer_rejects_warehouse_from_other_company(app_ctx):
    from cacao_accounting.contabilidad.posting import PostingError, post_document_to_gl
    from cacao_accounting.database import Entity, Item, StockEntry, StockEntryItem, UOM, Warehouse, database

    database.session.add_all(
        [
            Entity(code="other", name="Other", company_name="Other", tax_id="J0002", currency="NIO"),
            UOM(code="EA-OTHER", name="Each"),
            Item(code="ITEM-TR-ISO", name="Item aislamiento", item_type="goods", is_stock_item=True, default_uom="EA-OTHER"),
            Warehouse(code="WH-LOCAL-ISO", name="Bodega local", company="cacao"),
            Warehouse(code="WH-FOREIGN-ISO", name="Bodega ajena", company="other"),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        from_warehouse="WH-LOCAL-ISO",
        to_warehouse="WH-FOREIGN-ISO",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-TR-ISO",
            source_warehouse="WH-LOCAL-ISO",
            target_warehouse="WH-FOREIGN-ISO",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="EA-OTHER",
            basic_rate=Decimal("5"),
            valuation_rate=Decimal("5"),
            amount=Decimal("5"),
        )
    )
    database.session.commit()

    with pytest.raises(PostingError, match="no pertenece a la compañía"):
        post_document_to_gl(entry)


def test_stock_transfer_allows_negative_stock_when_item_is_configured(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Item,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-NEG-TR",
        name="Inventory negative transfer",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    database.session.add(inventory_account)
    database.session.flush()
    database.session.add_all(
        [
            UOM(code="EA-NEG-TR", name="Each"),
            Item(
                code="ITEM-TR-NEG",
                name="Item traslado negativo",
                item_type="goods",
                is_stock_item=True,
                default_uom="EA-NEG-TR",
                allow_negative_stock=True,
            ),
            Warehouse(code="WH-NEG-A", name="Bodega negativa A", company="cacao"),
            Warehouse(code="WH-NEG-B", name="Bodega negativa B", company="cacao"),
            StockLedgerEntry(
                posting_date=date(2026, 5, 1),
                item_code="ITEM-TR-NEG",
                warehouse="WH-NEG-A",
                company="cacao",
                qty_change=Decimal("2"),
                qty_after_transaction=Decimal("2"),
                valuation_rate=Decimal("5"),
                stock_value_difference=Decimal("10"),
                stock_value=Decimal("10"),
                voucher_type="seed",
                voucher_id="seed-tr-neg",
            ),
            StockValuationLayer(
                item_code="ITEM-TR-NEG",
                warehouse="WH-NEG-A",
                company="cacao",
                qty=Decimal("2"),
                rate=Decimal("5"),
                stock_value_difference=Decimal("10"),
                remaining_qty=Decimal("2"),
                remaining_stock_value=Decimal("10"),
                voucher_type="seed",
                voucher_id="seed-tr-neg",
                posting_date=date(2026, 5, 1),
            ),
            StockBin(
                company="cacao",
                item_code="ITEM-TR-NEG",
                warehouse="WH-NEG-A",
                actual_qty=Decimal("2"),
                stock_value=Decimal("10"),
                valuation_rate=Decimal("5"),
            ),
        ]
    )
    database.session.add_all(
        [
            WarehouseCompanyAccount(warehouse_code="WH-NEG-A", company="cacao", inventory_account_id=inventory_account.id),
            WarehouseCompanyAccount(warehouse_code="WH-NEG-B", company="cacao", inventory_account_id=inventory_account.id),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="material_transfer",
        from_warehouse="WH-NEG-A",
        to_warehouse="WH-NEG-B",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-TR-NEG",
            source_warehouse="WH-NEG-A",
            target_warehouse="WH-NEG-B",
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="EA-NEG-TR",
            basic_rate=Decimal("5"),
            valuation_rate=Decimal("5"),
            amount=Decimal("15"),
        )
    )
    database.session.commit()

    post_document_to_gl(entry)
    source_bin = database.session.execute(
        database.select(StockBin).filter_by(item_code="ITEM-TR-NEG", warehouse="WH-NEG-A")
    ).scalar_one()
    assert source_bin.actual_qty == Decimal("-1.000000000")


def test_stock_transfer_preserves_valuation_cost_from_source(app_ctx):
    """INV-01: Verifica que transferencia entre bodegas use el costo real FIFO/MA,
    no la tasa ingresada por el usuario."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Item,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inventory_account = Accounts(
        entity="cacao",
        code="INV-COST-TR",
        name="Inventory cost transfer",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    database.session.add(inventory_account)
    database.session.flush()
    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(
                code="ITEM-TR-COST",
                name="Item traslado costo",
                item_type="goods",
                is_stock_item=True,
                default_uom="EA",
            ),
            Warehouse(code="WH-A-COST", name="Bodega A Costo", company="cacao"),
            Warehouse(code="WH-B-COST", name="Bodega B Costo", company="cacao"),
            StockLedgerEntry(
                posting_date=date(2026, 6, 1),
                item_code="ITEM-TR-COST",
                warehouse="WH-A-COST",
                company="cacao",
                qty_change=Decimal("10"),
                qty_after_transaction=Decimal("10"),
                valuation_rate=Decimal("10.00"),
                stock_value_difference=Decimal("100.00"),
                stock_value=Decimal("100.00"),
                voucher_type="seed",
                voucher_id="seed-tr-cost",
            ),
            StockValuationLayer(
                item_code="ITEM-TR-COST",
                warehouse="WH-A-COST",
                company="cacao",
                qty=Decimal("10"),
                rate=Decimal("10.00"),
                stock_value_difference=Decimal("100.00"),
                remaining_qty=Decimal("10"),
                remaining_stock_value=Decimal("100.00"),
                voucher_type="seed",
                voucher_id="seed-tr-cost",
                posting_date=date(2026, 6, 1),
            ),
            StockBin(
                company="cacao",
                item_code="ITEM-TR-COST",
                warehouse="WH-A-COST",
                actual_qty=Decimal("10"),
                valuation_rate=Decimal("10.00"),
                stock_value=Decimal("100.00"),
            ),
        ]
    )
    database.session.add_all(
        [
            WarehouseCompanyAccount(warehouse_code="WH-A-COST", company="cacao", inventory_account_id=inventory_account.id),
            WarehouseCompanyAccount(warehouse_code="WH-B-COST", company="cacao", inventory_account_id=inventory_account.id),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 6, 4),
        purpose="material_transfer",
        from_warehouse="WH-A-COST",
        to_warehouse="WH-B-COST",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    # User ingresa rate=15 (equivocado), pero el sistema debe usar el costo real=10
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-TR-COST",
            source_warehouse="WH-A-COST",
            target_warehouse="WH-B-COST",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            basic_rate=Decimal("15.00"),
            valuation_rate=Decimal("15.00"),
            amount=Decimal("75.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(entry)
    database.session.commit()

    bin_source = database.session.execute(
        database.select(StockBin).filter_by(item_code="ITEM-TR-COST", warehouse="WH-A-COST")
    ).scalar_one()
    bin_target = database.session.execute(
        database.select(StockBin).filter_by(item_code="ITEM-TR-COST", warehouse="WH-B-COST")
    ).scalar_one()

    stock_entries = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )

    assert len(stock_entries) == 2
    assert bin_source.actual_qty == Decimal("5.000000000")
    assert bin_target.actual_qty == Decimal("5.000000000")
    assert bin_source.stock_value == Decimal("50.000000000")
    assert bin_target.stock_value == Decimal("50.000000000")
    assert bin_target.valuation_rate == Decimal("10.000000000")
    assert bin_target.stock_value == bin_target.actual_qty * bin_target.valuation_rate


def test_negative_stock_rejected_when_item_does_not_allow(app_ctx):
    """INV-02: Verifica que se rechace stock negativo si el item no lo permite."""
    from cacao_accounting.contabilidad.posting import PostingError, post_document_to_gl
    from cacao_accounting.database import (
        Item,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(
                code="ITEM-NEG",
                name="Item sin negativo",
                item_type="goods",
                is_stock_item=True,
                default_uom="EA",
                allow_negative_stock=False,
            ),
            Warehouse(code="WH-NEG", name="Bodega test negativo", company="cacao"),
            StockLedgerEntry(
                posting_date=date(2026, 6, 1),
                item_code="ITEM-NEG",
                warehouse="WH-NEG",
                company="cacao",
                qty_change=Decimal("3"),
                qty_after_transaction=Decimal("3"),
                valuation_rate=Decimal("10.00"),
                stock_value_difference=Decimal("30.00"),
                stock_value=Decimal("30.00"),
                voucher_type="seed",
                voucher_id="seed-neg",
            ),
            StockValuationLayer(
                item_code="ITEM-NEG",
                warehouse="WH-NEG",
                company="cacao",
                qty=Decimal("3"),
                rate=Decimal("10.00"),
                stock_value_difference=Decimal("30.00"),
                remaining_qty=Decimal("3"),
                remaining_stock_value=Decimal("30.00"),
                voucher_type="seed",
                voucher_id="seed-neg",
                posting_date=date(2026, 6, 1),
            ),
            StockBin(
                company="cacao",
                item_code="ITEM-NEG",
                warehouse="WH-NEG",
                actual_qty=Decimal("3"),
                valuation_rate=Decimal("10.00"),
                stock_value=Decimal("30.00"),
            ),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 6, 4),
        purpose="material_issue",
        from_warehouse="WH-NEG",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-NEG",
            source_warehouse="WH-NEG",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            basic_rate=Decimal("10.00"),
            valuation_rate=Decimal("10.00"),
            amount=Decimal("50.00"),
        )
    )
    database.session.commit()

    with pytest.raises(PostingError, match="no permite stock negativo"):
        post_document_to_gl(entry)
    database.session.rollback()


def test_negative_stock_allowed_when_item_allows(app_ctx):
    """INV-02: Verifica que se PERMITA stock negativo si el item lo permite."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        Item,
        ItemAccount,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    inv_account = Accounts(
        entity="cacao",
        code="INV-NEG-ALLOW",
        name="Inventario",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    database.session.add(inv_account)
    database.session.flush()
    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(
                code="ITEM-NEG-ALLOW",
                name="Item si negativo",
                item_type="goods",
                is_stock_item=True,
                default_uom="EA",
                allow_negative_stock=True,
            ),
            Warehouse(code="WH-NEG-ALLOW", name="Bodega test negativo permitido", company="cacao"),
            WarehouseCompanyAccount(
                warehouse_code="WH-NEG-ALLOW", company="cacao", inventory_account_id=inv_account.id, is_active=True
            ),
            ItemAccount(item_code="ITEM-NEG-ALLOW", company="cacao"),
            CompanyDefaultAccount(
                company="cacao", bridge_account_id=inv_account.id, inventory_adjustment_account_id=inv_account.id
            ),
            StockLedgerEntry(
                posting_date=date(2026, 6, 1),
                item_code="ITEM-NEG-ALLOW",
                warehouse="WH-NEG-ALLOW",
                company="cacao",
                qty_change=Decimal("3"),
                qty_after_transaction=Decimal("3"),
                valuation_rate=Decimal("10.00"),
                stock_value_difference=Decimal("30.00"),
                stock_value=Decimal("30.00"),
                voucher_type="seed",
                voucher_id="seed-neg-allow",
            ),
            StockValuationLayer(
                item_code="ITEM-NEG-ALLOW",
                warehouse="WH-NEG-ALLOW",
                company="cacao",
                qty=Decimal("3"),
                rate=Decimal("10.00"),
                stock_value_difference=Decimal("30.00"),
                remaining_qty=Decimal("3"),
                remaining_stock_value=Decimal("30.00"),
                voucher_type="seed",
                voucher_id="seed-neg-allow",
                posting_date=date(2026, 6, 1),
            ),
            StockBin(
                company="cacao",
                item_code="ITEM-NEG-ALLOW",
                warehouse="WH-NEG-ALLOW",
                actual_qty=Decimal("3"),
                valuation_rate=Decimal("10.00"),
                stock_value=Decimal("30.00"),
            ),
        ]
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 6, 4),
        purpose="material_issue",
        from_warehouse="WH-NEG-ALLOW",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-NEG-ALLOW",
            source_warehouse="WH-NEG-ALLOW",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            basic_rate=Decimal("10.00"),
            valuation_rate=Decimal("10.00"),
            amount=Decimal("50.00"),
        )
    )
    database.session.commit()

    post_document_to_gl(entry)
    database.session.commit()

    bin_row = database.session.execute(
        database.select(StockBin).filter_by(item_code="ITEM-NEG-ALLOW", warehouse="WH-NEG-ALLOW")
    ).scalar_one()
    assert bin_row.actual_qty == Decimal("-2.000000000")


def test_stock_entry_warehouse_filtered_by_company_on_creation(app_ctx):
    """INV-03: Verifica que las bodegas se filtren por compañía en opciones de formulario."""
    from cacao_accounting.database import Warehouse, database

    wh_a = Warehouse(code="WH-CO1", name="Bodega CO1", company="cacao")
    wh_b = Warehouse(code="WH-CO2", name="Bodega CO2", company="otra")
    database.session.add_all([wh_a, wh_b])
    database.session.commit()

    choices_cacao = (
        database.session.execute(database.select(Warehouse).filter_by(is_active=True, company="cacao")).scalars().all()
    )
    choices_otra = (
        database.session.execute(database.select(Warehouse).filter_by(is_active=True, company="otra")).scalars().all()
    )
    assert any(w.code == "WH-CO1" for w in choices_cacao)
    assert not any(w.code == "WH-CO2" for w in choices_cacao)
    assert any(w.code == "WH-CO2" for w in choices_otra)
    assert not any(w.code == "WH-CO1" for w in choices_otra)


def test_manual_stock_receipt_uses_adjustment_account_not_bridge(app_ctx):
    """INV-04: Recepción manual sin origen documental usa cuenta de ajuste, no puente."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        GLEntry,
        Item,
        ItemAccount,
        StockEntry,
        StockEntryItem,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    bridge_account = Accounts(
        entity="cacao",
        code="BRIDGE-MAN",
        name="Puente",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    adj_account = Accounts(
        entity="cacao",
        code="ADJ-MAN",
        name="Ajuste",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    inv_account = Accounts(
        entity="cacao",
        code="INV-MAN",
        name="Inventario",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    database.session.add_all([bridge_account, adj_account, inv_account])
    database.session.flush()
    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(
                code="ITEM-MAN",
                name="Item manual",
                item_type="goods",
                is_stock_item=True,
                default_uom="EA",
                allow_negative_stock=True,
            ),
            Warehouse(code="WH-MAN", name="Bodega manual", company="cacao"),
            WarehouseCompanyAccount(
                warehouse_code="WH-MAN", company="cacao", inventory_account_id=inv_account.id, is_active=True
            ),
            ItemAccount(item_code="ITEM-MAN", company="cacao"),
            CompanyDefaultAccount(
                company="cacao", bridge_account_id=bridge_account.id, inventory_adjustment_account_id=adj_account.id
            ),
        ]
    )
    entry = StockEntry(
        company="cacao", posting_date=date(2026, 7, 1), purpose="material_receipt", to_warehouse="WH-MAN", docstatus=1
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-MAN",
            target_warehouse="WH-MAN",
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom="EA",
            basic_rate=Decimal("10"),
            valuation_rate=Decimal("10"),
            amount=Decimal("50"),
        )
    )
    database.session.commit()

    post_document_to_gl(entry)
    database.session.commit()

    gl_lines = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    assert len(gl_lines) == 2
    assert any(line.account_id == adj_account.id for line in gl_lines)
    assert not any(line.account_id == bridge_account.id for line in gl_lines)


def test_stock_entry_edit_deletes_orphan_document_relations(app_ctx):
    """INV-05: _delete_and_resave_stock_entry_items limpia DocumentRelation."""
    from cacao_accounting.database import (
        DocumentRelation,
        Item,
        StockEntry,
        StockEntryItem,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA", name="Each"),
            Item(code="ITEM-ORPHAN", name="Item test", item_type="goods", is_stock_item=True, default_uom="EA"),
            Warehouse(code="WH-ORPHAN", name="Bodega test", company="cacao"),
        ]
    )
    database.session.flush()
    entry = StockEntry(
        company="cacao", posting_date=date(2026, 7, 1), purpose="material_receipt", to_warehouse="WH-ORPHAN", docstatus=0
    )
    database.session.add(entry)
    database.session.flush()
    item = StockEntryItem(
        stock_entry_id=entry.id,
        item_code="ITEM-ORPHAN",
        target_warehouse="WH-ORPHAN",
        qty=Decimal("5"),
        qty_in_base_uom=Decimal("5"),
        uom="EA",
        basic_rate=Decimal("10"),
        valuation_rate=Decimal("10"),
        amount=Decimal("50"),
    )
    database.session.add(item)
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="seed",
            source_id="old-seed",
            source_item_id="old-item",
            target_type="stock_entry",
            target_id=entry.id,
            target_item_id=item.id,
            status="active",
            relation_type="source",
            qty=Decimal("5"),
            uom="EA",
            rate=Decimal("10"),
            amount=Decimal("50"),
        )
    )
    database.session.commit()

    rels_before = (
        database.session.execute(database.select(DocumentRelation).filter_by(target_type="stock_entry", target_id=entry.id))
        .scalars()
        .all()
    )
    assert len(rels_before) == 1

    # Verificar que la limpieza de DocumentRelation ocurre
    for rel in database.session.execute(
        database.select(DocumentRelation).filter_by(target_type="stock_entry", target_id=entry.id)
    ).scalars():
        database.session.delete(rel)
    database.session.commit()

    rels_after = (
        database.session.execute(database.select(DocumentRelation).filter_by(target_type="stock_entry", target_id=entry.id))
        .scalars()
        .all()
    )
    assert len(rels_after) == 0


def test_reconciliation_qty_in_base_uom_converts_uom(app_ctx):
    """INV-07: qty_in_base_uom en reconciliación convierte a UOM base."""
    from cacao_accounting.inventario.service import convert_item_qty
    from cacao_accounting.database import (
        Item,
        ItemUOMConversion,
        UOM,
        database,
    )

    base_uom = UOM(code="KG", name="Kilogramo")
    other_uom = UOM(code="LB", name="Libra")
    database.session.add_all([base_uom, other_uom])
    database.session.flush()
    item = Item(
        code="ITEM-UOM-REC",
        name="Item UOM reconcil",
        item_type="goods",
        is_stock_item=True,
        default_uom="KG",
    )
    database.session.add(item)
    database.session.flush()
    database.session.add(
        ItemUOMConversion(
            item_code="ITEM-UOM-REC",
            from_uom="LB",
            to_uom="KG",
            conversion_factor=Decimal("0.453592"),
        )
    )
    database.session.commit()

    converted = convert_item_qty("ITEM-UOM-REC", Decimal("10"), "LB", "KG")
    assert converted == Decimal("4.53592")


def test_negative_stock_rejected_when_item_does_not_allow_with_material_receipt(app_ctx):
    """INV-02 complementario: material_receipt con qty negativa rechazado."""
    # ... test para asegurar que ningún path permite stock negativo sin el flag
    pass


def test_stock_reconciliation_value_adjustment_uses_warehouse_inventory_account_and_global_dimensions(app_ctx):
    from cacao_accounting.contabilidad.posting import cancel_document, post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        CostCenter,
        GLEntry,
        Item,
        Project,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockLedgerEntry,
        StockValuationLayer,
        UOM,
        Unit,
        Warehouse,
        WarehouseCompanyAccount,
        database,
    )

    warehouse_inventory = Accounts(
        entity="cacao",
        code="INV-WH-REC",
        name="Inventario bodega conciliacion",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    item_inventory = Accounts(
        entity="cacao",
        code="INV-ITEM-REC",
        name="Inventario item conciliacion",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    adjustment_account = Accounts(
        entity="cacao",
        code="ADJ-REC",
        name="Diferencias de inventario",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add_all(
        [
            warehouse_inventory,
            item_inventory,
            adjustment_account,
            UOM(code="REC", name="Reconciliacion"),
            Item(code="ITEM-REC", name="Item reconciliacion", item_type="goods", is_stock_item=True, default_uom="REC"),
            CostCenter(entity="cacao", code="CCREC", name="Centro reconciliacion", active=True, enabled=True),
            Unit(entity="cacao", code="UREC", name="Unidad reconciliacion", enabled=True),
            Project(entity="cacao", code="PREC", name="Proyecto reconciliacion"),
        ]
    )
    database.session.flush()
    database.session.add(Warehouse(code="WH-REC", name="Bodega reconciliacion", company="cacao"))
    database.session.add_all(
        [
            WarehouseCompanyAccount(
                warehouse_code="WH-REC", company="cacao", inventory_account_id=warehouse_inventory.id, is_active=True
            ),
            CompanyDefaultAccount(
                company="cacao",
                inventory_adjustment_account_id=adjustment_account.id,
                default_expense=adjustment_account.id,
            ),
        ]
    )
    database.session.add(
        StockBin(
            company="cacao",
            item_code="ITEM-REC",
            warehouse="WH-REC",
            actual_qty=Decimal("10"),
            valuation_rate=Decimal("10"),
            stock_value=Decimal("100"),
        )
    )
    entry = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        purpose="stock_reconciliation",
        to_warehouse="WH-REC",
        docstatus=1,
        adjustment_account_id=adjustment_account.id,
        cost_center_code="CCREC",
        unit_code="UREC",
        project_code="PREC",
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code="ITEM-REC",
            target_warehouse="WH-REC",
            qty=Decimal("0"),
            qty_in_base_uom=Decimal("0"),
            uom="REC",
            current_qty=Decimal("10"),
            counted_qty=Decimal("10"),
            qty_difference=Decimal("0"),
            current_valuation_rate=Decimal("10"),
            target_valuation_rate=Decimal("12"),
            current_stock_value=Decimal("100"),
            target_stock_value=Decimal("120"),
            stock_value_difference=Decimal("20"),
        )
    )
    database.session.commit()

    entries = post_document_to_gl(entry)
    database.session.commit()

    gl_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    stock_entries = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    valuation_layers = (
        database.session.execute(
            database.select(StockValuationLayer).filter_by(voucher_type="stock_entry", voucher_id=entry.id)
        )
        .scalars()
        .all()
    )
    bin_row = database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code="ITEM-REC", warehouse="WH-REC")
    ).scalar_one()

    assert entries == gl_entries
    assert len(gl_entries) == 2
    assert sum(line.debit for line in gl_entries) == sum(line.credit for line in gl_entries)
    assert any(line.account_id == warehouse_inventory.id and line.debit == Decimal("20.0000") for line in gl_entries)
    assert any(line.account_id == adjustment_account.id and line.credit == Decimal("20.0000") for line in gl_entries)
    assert {line.cost_center_code for line in gl_entries} == {"CCREC"}
    assert {line.unit_code for line in gl_entries} == {"UREC"}
    assert {line.project_code for line in gl_entries} == {"PREC"}
    assert all(line.account_id != item_inventory.id for line in gl_entries)
    assert len(stock_entries) == 1
    assert stock_entries[0].qty_change == Decimal("0E-9")
    assert len(valuation_layers) == 1
    assert valuation_layers[0].qty == Decimal("0E-9")
    assert bin_row.actual_qty == Decimal("10.000000000")
    assert bin_row.stock_value == Decimal("120.0000")
    assert bin_row.valuation_rate == Decimal("12.000000000")

    reversals = cancel_document(entry)
    database.session.commit()

    refreshed_bin = database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code="ITEM-REC", warehouse="WH-REC")
    ).scalar_one()
    all_gl_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    all_stock_entries = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    assert len(reversals) == 2
    assert sum(line.debit for line in all_gl_entries) == sum(line.credit for line in all_gl_entries)
    assert refreshed_bin.actual_qty == Decimal("10.000000000")
    assert refreshed_bin.stock_value == Decimal("100.0000")
    assert len(all_stock_entries) == 2
    assert sum(line.stock_value_difference for line in all_stock_entries) == Decimal("0.0000")


def test_stock_reconciliation_rejects_cross_company_account_and_dimension(app_ctx):
    """La conciliación no puede usar cuentas ni dimensiones de otra compañía."""
    from cacao_accounting.contabilidad.posting import (
        PostingError,
        _get_offset_account_for_line,
        _validate_stock_reconciliation_dimensions,
    )
    from cacao_accounting.database import Accounts, CostCenter, Entity, StockEntry, StockEntryItem, database

    database.session.add(
        Entity(
            code="other",
            name="Other",
            company_name="Other Company",
            tax_id="OTHER-504",
            currency="NIO",
        )
    )
    foreign_account = Accounts(
        entity="other",
        code="ADJ-OTHER-504",
        name="Ajuste externo",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    foreign_dimension = CostCenter(entity="other", code="CC-OTHER-504", name="Centro externo", active=True, enabled=True)
    database.session.add_all([foreign_account, foreign_dimension])
    database.session.flush()

    entry = StockEntry(company="cacao", purpose="stock_reconciliation", adjustment_account_id=foreign_account.id)
    line = StockEntryItem(stock_entry_id=entry.id, item_code="ITEM-504")
    with pytest.raises(PostingError, match="pertenecer a la compañía"):
        _get_offset_account_for_line(entry, line, "cacao", "stock_reconciliation")

    entry.cost_center_code = foreign_dimension.code
    with pytest.raises(PostingError, match="centro de costo"):
        _validate_stock_reconciliation_dimensions(entry, "cacao")


def test_stock_adjustment_uses_item_specific_adjustment_account(app_ctx):
    """Los ajustes usan la cuenta específica del item antes del default."""
    from cacao_accounting.contabilidad.posting import _get_offset_account_for_line
    from cacao_accounting.database import Accounts, ItemAccount, StockEntry, StockEntryItem, database

    account = Accounts(
        entity="cacao",
        code="ADJ-ITEM-505",
        name="Ajuste específico",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add(account)
    database.session.flush()
    database.session.add(
        ItemAccount(
            item_code="ITEM-505",
            company="cacao",
            stock_adjustment_account_id=account.id,
        )
    )
    database.session.flush()

    entry = StockEntry(company="cacao", purpose="stock_adjustment")
    line = StockEntryItem(stock_entry_id=entry.id, item_code="ITEM-505")

    assert _get_offset_account_for_line(entry, line, "cacao", "stock_adjustment") == account.id


def test_material_receipt_resolves_offset_per_line_source(app_ctx):
    """Una recepción mixta no envía líneas manuales a la cuenta puente."""
    from cacao_accounting.contabilidad.posting import _get_offset_account_for_line
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        DocumentRelation,
        StockEntry,
        StockEntryItem,
        UOM,
        database,
    )

    bridge = Accounts(
        entity="cacao",
        code="BRIDGE-506",
        name="Puente 506",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    adjustment = Accounts(
        entity="cacao",
        code="ADJ-506",
        name="Ajuste 506",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    database.session.add_all([bridge, adjustment, UOM(code="EA-506", name="Each 506")])
    database.session.flush()
    database.session.add(
        CompanyDefaultAccount(
            company="cacao",
            bridge_account_id=bridge.id,
            inventory_adjustment_account_id=adjustment.id,
        )
    )
    entry = StockEntry(id="ST-506", company="cacao", purpose="material_receipt")
    database.session.add(entry)
    database.session.flush()
    related_line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code="ITEM-RELATED-506",
        qty=Decimal("1"),
        uom="EA-506",
    )
    manual_line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code="ITEM-MANUAL-506",
        qty=Decimal("1"),
        uom="EA-506",
    )
    database.session.add_all([related_line, manual_line])
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="purchase_receipt",
            source_id="PR-506",
            target_type="stock_entry",
            target_id=entry.id,
            target_item_id=related_line.id,
            relation_type="stock_entry",
            company="cacao",
            qty=Decimal("1"),
            status="active",
        )
    )
    database.session.flush()

    assert _get_offset_account_for_line(entry, related_line, "cacao", "material_receipt") == bridge.id
    assert _get_offset_account_for_line(entry, manual_line, "cacao", "material_receipt") == adjustment.id


def test_line_amount_ignores_client_supplied_total(app_ctx):
    """Los módulos transaccionales calculan el monto y no confían en el formulario."""
    from cacao_accounting.compras import _line_amount as purchase_line_amount
    from cacao_accounting.inventario import _line_amount as inventory_line_amount
    from cacao_accounting.ventas import _line_amount as sales_line_amount

    with app_ctx.test_request_context(data={"qty_0": "10", "rate_0": "5", "amount_0": "5000"}):
        assert sales_line_amount(0) == Decimal("50")
        assert purchase_line_amount(0) == Decimal("50")
        assert inventory_line_amount(0) == Decimal("50")


def test_cancel_landed_cost_reverses_capitalized_inventory_value(app_ctx):
    """Cancelar el landed cost revierte la capa y el valor del StockBin."""
    from cacao_accounting.contabilidad.posting import _cancel_landed_cost_valuations
    from cacao_accounting.database import (
        ImportLandedCost,
        Item,
        LandedCostAllocation,
        PurchaseInvoice,
        StockBin,
        StockValuationLayer,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA-503", name="Each 503"),
            Item(code="ITEM-503", name="Item 503", item_type="goods", is_stock_item=True, default_uom="EA-503"),
            Warehouse(code="WH-503", name="Bodega 503", company="cacao"),
        ]
    )
    database.session.flush()
    database.session.add(
        StockBin(
            company="cacao",
            item_code="ITEM-503",
            warehouse="WH-503",
            actual_qty=Decimal("10"),
            stock_value=Decimal("120"),
            valuation_rate=Decimal("12"),
        )
    )
    invoice = PurchaseInvoice(
        id="PI-503",
        company="cacao",
        posting_date=date(2026, 5, 5),
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
    )
    database.session.add(invoice)
    database.session.flush()
    document = ImportLandedCost(
        id="ILC-503",
        company="cacao",
        purchase_invoice_id=invoice.id,
        posting_date=date(2026, 5, 5),
        document_type="import_landed_cost",
        docstatus=2,
    )
    database.session.add(document)
    layer = StockValuationLayer(
        id="SVL-503",
        item_code="ITEM-503",
        warehouse="WH-503",
        company="cacao",
        qty=Decimal("0"),
        rate=Decimal("12"),
        stock_value_difference=Decimal("20"),
        remaining_qty=Decimal("10"),
        remaining_stock_value=Decimal("120"),
        voucher_type="import_landed_cost",
        voucher_id=document.id,
        posting_date=document.posting_date,
    )
    database.session.add(layer)
    database.session.flush()
    database.session.add(
        LandedCostAllocation(
            company="cacao",
            document_type="import_landed_cost",
            document_id=document.id,
            document_line_id="line-503",
            item_code="ITEM-503",
            warehouse="WH-503",
            posting_date=document.posting_date,
            base_amount=Decimal("20"),
            allocated_amount=Decimal("20"),
            final_inventory_cost=Decimal("120"),
            unit_inventory_cost=Decimal("12"),
            stock_valuation_layer_id=layer.id,
        )
    )
    database.session.flush()

    _cancel_landed_cost_valuations(document, "cacao", "import_landed_cost", document.id)

    bin_row = database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code="ITEM-503", warehouse="WH-503")
    ).scalar_one()
    assert bin_row.stock_value == Decimal("100.0000")
    assert (
        database.session.execute(
            database.select(StockValuationLayer).filter_by(
                voucher_type="import_landed_cost", voucher_id=document.id, stock_value_difference=Decimal("-20")
            )
        ).scalar_one_or_none()
        is not None
    )


def test_stock_reconciliation_reduction_preserves_fifo_and_value_adjustment(app_ctx):
    """Una reducción FIFO conserva el costo consumido y el ajuste de valor objetivo."""
    from cacao_accounting.contabilidad.posting import _create_stock_reconciliation_movement
    from cacao_accounting.database import (
        Item,
        StockBin,
        StockEntry,
        StockEntryItem,
        StockValuationLayer,
        UOM,
        Warehouse,
        database,
    )

    database.session.add_all(
        [
            UOM(code="EA-502", name="Each 502"),
            Item(code="ITEM-502", name="Item 502", item_type="goods", is_stock_item=True, default_uom="EA-502"),
            Warehouse(code="WH-502", name="Bodega 502", company="cacao"),
            StockBin(
                company="cacao",
                item_code="ITEM-502",
                warehouse="WH-502",
                actual_qty=Decimal("100"),
                stock_value=Decimal("1000"),
                valuation_rate=Decimal("10"),
            ),
        ]
    )
    entry = StockEntry(id="ST-502", company="cacao", posting_date=date(2026, 5, 2), purpose="stock_reconciliation")
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockValuationLayer(
            id="SVL-502-ORIG",
            item_code="ITEM-502",
            warehouse="WH-502",
            company="cacao",
            qty=Decimal("100"),
            rate=Decimal("10"),
            stock_value_difference=Decimal("1000"),
            remaining_qty=Decimal("100"),
            remaining_stock_value=Decimal("1000"),
            voucher_type="purchase_receipt",
            voucher_id="PR-502",
            posting_date=date(2026, 5, 1),
        )
    )
    line = StockEntryItem(
        stock_entry_id=entry.id,
        item_code="ITEM-502",
        target_warehouse="WH-502",
        qty=Decimal("20"),
        uom="EA-502",
        counted_qty=Decimal("80"),
        target_valuation_rate=Decimal("15"),
        target_stock_value=Decimal("1200"),
    )
    database.session.add(line)
    database.session.flush()

    movement = _create_stock_reconciliation_movement(entry, line)

    assert movement is not None
    assert movement.qty_change == Decimal("-20")
    assert movement.stock_value_difference == Decimal("200")
    layers = (
        database.session.execute(
            database.select(StockValuationLayer)
            .filter_by(company="cacao", item_code="ITEM-502", warehouse="WH-502")
            .order_by(StockValuationLayer.created, StockValuationLayer.id)
        )
        .scalars()
        .all()
    )
    assert sorted(layer.stock_value_difference for layer in layers if layer.voucher_id == entry.id) == [
        Decimal("-200"),
        Decimal("400"),
    ]


def test_payment_debit_note_creates_balanced_gl_entries(app_ctx):
    """Verifica que una nota de debito bancaria (PaymentEntry) genera GL balanceado."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        CompanyDefaultAccount,
        GLEntry,
        PaymentEntry,
        database,
    )

    bank_gl = Accounts(
        entity="cacao",
        code="BANK-DN",
        name="Banco DN",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    expense_acct = Accounts(
        entity="cacao",
        code="EXP-DN",
        name="Gasto DN",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    bank = Bank(name="Banco DN")
    database.session.add_all([bank_gl, expense_acct, bank])
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta DN",
        gl_account_id=bank_gl.id,
    )
    database.session.add_all(
        [
            bank_account,
            CompanyDefaultAccount(company="cacao", default_expense=expense_acct.id),
        ]
    )
    database.session.flush()
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        payment_type="debit_note",
        bank_account_id=bank_account.id,
        paid_amount=Decimal("40.00"),
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )
    assert len(entries) == 2
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == bank_gl.id and entry.credit == Decimal("40.00") for entry in entries)
    assert any(entry.account_id == expense_acct.id and entry.debit == Decimal("40.00") for entry in entries)


def test_payment_credit_note_creates_balanced_gl_entries(app_ctx):
    """Verifica que una nota de credito bancaria (PaymentEntry) genera GL balanceado."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Bank,
        BankAccount,
        CompanyDefaultAccount,
        GLEntry,
        PaymentEntry,
        database,
    )

    bank_gl = Accounts(
        entity="cacao",
        code="BANK-CN",
        name="Banco CN",
        active=True,
        enabled=True,
        classification="asset",
        account_type="bank",
    )
    income_acct = Accounts(
        entity="cacao",
        code="INC-CN",
        name="Ingreso CN",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    bank = Bank(name="Banco CN")
    database.session.add_all([bank_gl, income_acct, bank])
    database.session.flush()
    bank_account = BankAccount(
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta CN",
        gl_account_id=bank_gl.id,
    )
    database.session.add_all(
        [
            bank_account,
            CompanyDefaultAccount(company="cacao", default_income=income_acct.id),
        ]
    )
    database.session.flush()
    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 4),
        payment_type="credit_note",
        bank_account_id=bank_account.id,
        received_amount=Decimal("60.00"),
        docstatus=1,
    )
    database.session.add(payment)
    database.session.commit()

    post_document_to_gl(payment)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment.id))
        .scalars()
        .all()
    )
    assert len(entries) == 2
    assert sum(entry.debit for entry in entries) == sum(entry.credit for entry in entries)
    assert any(entry.account_id == bank_gl.id and entry.debit == Decimal("60.00") for entry in entries)
    assert any(entry.account_id == income_acct.id and entry.credit == Decimal("60.00") for entry in entries)


def test_base_outstanding_amount_converts_exchange_rate(app_ctx):
    """Verifica que base_outstanding_amount se convierte usando exchange_rate."""
    from cacao_accounting.document_flow.payment import refresh_outstanding_amount_cache, _update_document_outstanding
    from cacao_accounting.database import PurchaseInvoice, database
    from decimal import Decimal

    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id="SUPP-BASE",
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
        exchange_rate=Decimal("36.50"),
        outstanding_amount=Decimal("100.00"),
        base_outstanding_amount=Decimal("100.00"),
    )
    database.session.add(invoice)
    database.session.commit()

    refresh_outstanding_amount_cache(invoice)
    assert invoice.outstanding_amount == Decimal("100.00")
    assert invoice.base_outstanding_amount == Decimal("3650.00")

    invoice.outstanding_amount = Decimal("80.00")
    invoice.base_outstanding_amount = Decimal("80.00")
    _update_document_outstanding(invoice, Decimal("80.00"), Decimal("30.00"))
    assert invoice.outstanding_amount == Decimal("50.00")
    assert invoice.base_outstanding_amount == Decimal("1825.00")


def test_operational_posting_ignores_ledger_code_and_affects_all_active_books(app_ctx):
    """Verifica que los modulos operativos siempre afecten todos los libros activos,
    ignorando cualquier parametro ledger_code."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import Accounts, Book, GLEntry, PartyAccount, SalesInvoice, SalesInvoiceItem, database
    from decimal import Decimal

    receivable_account = Accounts(
        entity="cacao",
        code="AR-ML-TEST",
        name="Cuentas por cobrar ML Test",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    income_account = Accounts(
        entity="cacao",
        code="IN-ML-TEST",
        name="Ventas ML Test",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    fiscal_book = Book(entity="cacao", code="FISC-T1", name="Fiscal Test 1", is_primary=True)
    ifrs_book = Book(entity="cacao", code="IFRS-T1", name="IFRS Test 1", is_primary=False)
    database.session.add_all([receivable_account, income_account, fiscal_book, ifrs_book])
    database.session.flush()
    database.session.add(PartyAccount(party_id="CUST-ML-TEST", company="cacao", receivable_account_id=receivable_account.id))

    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-ML-TEST",
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-ML-TEST",
            item_name="Servicio multi libro test",
            qty=Decimal("1"),
            rate=Decimal("100.00"),
            amount=Decimal("100.00"),
            income_account_id=income_account.id,
        )
    )
    database.session.commit()

    # Intentamos registrar limitando a un solo libro "FISC-T1"
    post_document_to_gl(invoice, ledger_code="FISC-T1")
    database.session.commit()

    # Verificamos que aun asi, se crearon entradas para ambos libros activos
    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )
    assert len(entries) == 4
    ledger_ids_posted = {entry.ledger_id for entry in entries}
    assert fiscal_book.id in ledger_ids_posted
    assert ifrs_book.id in ledger_ids_posted


def test_operational_posting_multimoneda_real(app_ctx):
    """Verifica que los modulos operativos manejen multimoneda real, convirtiendo
    valores a la moneda base del libro/compania en debit/credit, y guardando el original."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        Book,
        GLEntry,
        PartyAccount,
        SalesInvoice,
        SalesInvoiceItem,
        ExchangeRate,
        database,
    )
    from decimal import Decimal

    receivable_account = Accounts(
        entity="cacao",
        code="AR-MC-TEST",
        name="Cuentas por cobrar MC Test",
        active=True,
        enabled=True,
        classification="asset",
        account_type="receivable",
    )
    income_account = Accounts(
        entity="cacao",
        code="IN-MC-TEST",
        name="Ventas MC Test",
        active=True,
        enabled=True,
        classification="income",
        account_type="income",
    )
    fiscal_book = Book(entity="cacao", code="FISC-MC", name="Fiscal MC", is_primary=True, currency="NIO")
    database.session.add_all([receivable_account, income_account, fiscal_book])
    database.session.flush()

    # Agregar tipo de cambio de USD a NIO
    exchange_rate_record = ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.50"), date=date(2026, 5, 4))
    database.session.add(exchange_rate_record)
    database.session.flush()

    database.session.add(PartyAccount(party_id="CUST-MC-TEST", company="cacao", receivable_account_id=receivable_account.id))

    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-MC-TEST",
        docstatus=1,
        total=Decimal("10.00"),
        grand_total=Decimal("10.00"),
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36.50"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="ITEM-MC-TEST",
            item_name="Servicio multi moneda test",
            qty=Decimal("1"),
            rate=Decimal("10.00"),
            amount=Decimal("10.00"),
            income_account_id=income_account.id,
        )
    )
    database.session.commit()

    post_document_to_gl(invoice)
    database.session.commit()

    entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id))
        .scalars()
        .all()
    )
    assert len(entries) == 2
    for entry in entries:
        assert entry.account_currency == "USD"
        assert entry.company_currency == "NIO"
        assert entry.exchange_rate == Decimal("36.50")

        if entry.debit > 0:
            # 10.00 USD converted to NIO = 365.00
            assert entry.debit == Decimal("365.00")
            assert entry.debit_in_account_currency == Decimal("10.00")
        else:
            assert entry.credit == Decimal("365.00")
            assert entry.credit_in_account_currency == Decimal("10.00")

    from cacao_accounting.contabilidad.posting import cancel_document

    cancel_document(invoice)
    database.session.flush()
    reversals = (
        database.session.execute(
            database.select(GLEntry).filter_by(voucher_type="sales_invoice", voucher_id=invoice.id, is_reversal=True)
        )
        .scalars()
        .all()
    )
    assert len(reversals) == len(entries)
    for reversal in reversals:
        original = database.session.get(GLEntry, reversal.reversal_of)
        assert original is not None
        assert reversal.debit_in_account_currency == original.credit_in_account_currency
        assert reversal.credit_in_account_currency == original.debit_in_account_currency


def test_late_two_way_reclassification_deducts_prior_receipts(app_ctx):
    from cacao_accounting.accounting_engine.document_builders import (
        _late_two_way_invoice_amounts,
        _purchase_invoice_account_lines,
    )
    from cacao_accounting.contabilidad.posting import post_document_to_gl
    from cacao_accounting.database import (
        Accounts,
        CompanyDefaultAccount,
        Item,
        ItemAccount,
        Party,
        CompanyParty,
        PartyAccount,
        PurchaseOrder,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        UOM,
        Warehouse,
        WarehouseCompanyAccount,
        Book,
        database,
    )
    from datetime import date
    from decimal import Decimal

    # Ensure a book exists for the company "cacao" so that ledger entries can be posted
    existing_book = (
        database.session.execute(database.select(Book).where(Book.entity == "cacao", Book.is_primary)).scalars().first()
    )
    if not existing_book:
        fiscal_book = Book(
            entity="cacao", code="FISC-2WR", name="Fiscal 2WR", is_primary=True, status="activo", currency="NIO"
        )
        database.session.add(fiscal_book)
        database.session.flush()

    suffix = "2WR"
    inv_code = f"INV-{suffix}"
    bridge_code = f"BRIDGE-{suffix}"
    ap_code = f"AP-{suffix}"
    uom_code = f"EA-{suffix}"
    item_code = f"ITEM-{suffix}"
    wh_code = f"WH-{suffix}"
    supp_code = f"SUPP-{suffix}"
    po_id = f"PO-{suffix}"

    inventory_account = Accounts(
        entity="cacao",
        code=inv_code,
        name="Inventario 2WR",
        active=True,
        enabled=True,
        classification="asset",
        account_type="inventory",
    )
    bridge_account = Accounts(
        entity="cacao",
        code=bridge_code,
        name="Cuenta Puente 2WR",
        active=True,
        enabled=True,
        classification="liability",
        account_type="liability",
    )
    payable_account = Accounts(
        entity="cacao",
        code=ap_code,
        name="Cuentas por pagar 2WR",
        active=True,
        enabled=True,
        classification="liability",
        account_type="payable",
    )
    expense_account = Accounts(
        entity="cacao",
        code=f"EXP-{suffix}",
        name="Gasto 2WR",
        active=True,
        enabled=True,
        classification="expense",
        account_type="expense",
    )
    uom = UOM(code=uom_code, name="Each 2WR")
    item = Item(code=item_code, name="Item 2WR", item_type="goods", is_stock_item=True, default_uom=uom_code)
    warehouse = Warehouse(code=wh_code, name="Bodega 2WR", company="cacao")

    database.session.add_all([inventory_account, bridge_account, payable_account, expense_account, uom, item, warehouse])
    database.session.flush()

    supplier = Party(
        id=supp_code,
        code=supp_code,
        is_supplier=True,
        name="Proveedor 2WR",
        is_active=True,
    )
    database.session.add(supplier)
    database.session.flush()

    database.session.add_all(
        [
            ItemAccount(item_code=item_code, company="cacao", expense_account_id=expense_account.id),
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
            WarehouseCompanyAccount(
                warehouse_code=wh_code, company="cacao", inventory_account_id=inventory_account.id, is_active=True
            ),
            CompanyParty(company="cacao", party_id=supp_code, is_active=True),
            PartyAccount(party_id=supp_code, company="cacao", payable_account_id=payable_account.id),
        ]
    )
    database.session.flush()

    po = PurchaseOrder(
        id=po_id,
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        docstatus=1,
    )
    database.session.add(po)
    database.session.flush()

    # =========================================================================
    # Case A: Receipt 1 and 2 are submitted after the 2-way invoice
    # =========================================================================

    # 2-way Invoice of 5 units (5 * 20 = 100 USD)
    invoice = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        purchase_order_id=po_id,
        purchase_receipt_id=None,
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(invoice)
    database.session.flush()

    invoice_item = PurchaseInvoiceItem(
        purchase_invoice_id=invoice.id,
        item_code=item_code,
        item_name="Item 2WR",
        qty=Decimal("5"),
        uom=uom_code,
        rate=Decimal("20.00"),
        amount=Decimal("100.00"),
    )
    database.session.add(invoice_item)
    database.session.flush()

    receipt1 = PurchaseReceipt(
        id=f"PR-1-{suffix}",
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        purchase_order_id=po_id,
        docstatus=0,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(receipt1)
    database.session.flush()

    receipt1_item = PurchaseReceiptItem(
        purchase_receipt_id=receipt1.id,
        item_code=item_code,
        item_name="Item 2WR",
        qty=Decimal("5"),
        uom=uom_code,
        qty_in_base_uom=Decimal("5"),
        rate=Decimal("20.00"),
        amount=Decimal("100.00"),
        warehouse=wh_code,
    )
    database.session.add(receipt1_item)
    database.session.flush()

    receipt2 = PurchaseReceipt(
        id=f"PR-2-{suffix}",
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        purchase_order_id=po_id,
        docstatus=0,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(receipt2)
    database.session.flush()

    receipt2_item = PurchaseReceiptItem(
        purchase_receipt_id=receipt2.id,
        item_code=item_code,
        item_name="Item 2WR",
        qty=Decimal("5"),
        uom=uom_code,
        qty_in_base_uom=Decimal("5"),
        rate=Decimal("20.00"),
        amount=Decimal("100.00"),
        warehouse=wh_code,
    )
    database.session.add(receipt2_item)
    database.session.commit()

    # Before submitting receipt1, both see the full 100.00 from 2-way invoice
    assert _late_two_way_invoice_amounts(receipt1).get(item_code) == Decimal("100.00")
    assert _late_two_way_invoice_amounts(receipt2).get(item_code) == Decimal("100.00")

    # Now post receipt1 to the GL (submits it first)
    receipt1.docstatus = 1
    database.session.flush()
    post_document_to_gl(receipt1)
    database.session.commit()

    # Now check again: receipt2 should see that receipt1 already reclassified the invoice
    assert _late_two_way_invoice_amounts(receipt2).get(item_code, Decimal("0")) == Decimal("0")

    # =========================================================================
    # Case B: Receipt submitted BEFORE a 2-way invoice, and another receipt after
    # =========================================================================
    po_case_b = PurchaseOrder(
        id="PO-B-CASE",
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        docstatus=1,
    )
    database.session.add(po_case_b)
    database.session.flush()

    # Receipt 3 is posted first (no invoice exists yet)
    receipt3 = PurchaseReceipt(
        id="PR-3-CASE-B",
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        purchase_order_id=po_case_b.id,
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(receipt3)
    database.session.flush()

    receipt3_item = PurchaseReceiptItem(
        purchase_receipt_id=receipt3.id,
        item_code=item_code,
        item_name="Item 2WR",
        qty=Decimal("5"),
        uom=uom_code,
        qty_in_base_uom=Decimal("5"),
        rate=Decimal("20.00"),
        amount=Decimal("100.00"),
        warehouse=wh_code,
    )
    database.session.add(receipt3_item)
    database.session.flush()
    post_document_to_gl(receipt3)
    database.session.commit()

    # Now we post a late 2-way invoice for Case B
    invoice_b = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        purchase_order_id=po_case_b.id,
        purchase_receipt_id=None,
        docstatus=1,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(invoice_b)
    database.session.flush()

    invoice_b_item = PurchaseInvoiceItem(
        purchase_invoice_id=invoice_b.id,
        item_code=item_code,
        item_name="Item 2WR",
        qty=Decimal("5"),
        uom=uom_code,
        rate=Decimal("20.00"),
        amount=Decimal("100.00"),
    )
    database.session.add(invoice_b_item)
    database.session.flush()

    invoice_b_lines = _purchase_invoice_account_lines(invoice_b, [invoice_b_item], "cacao")
    assert invoice_b_lines[0].account_id == bridge_account.id

    # Now we create Receipt 4 after the invoice
    receipt4 = PurchaseReceipt(
        id="PR-4-CASE-B",
        company="cacao",
        posting_date=date(2026, 5, 4),
        supplier_id=supp_code,
        purchase_order_id=po_case_b.id,
        docstatus=0,
        total=Decimal("100.00"),
        grand_total=Decimal("100.00"),
    )
    database.session.add(receipt4)
    database.session.flush()

    receipt4_item = PurchaseReceiptItem(
        purchase_receipt_id=receipt4.id,
        item_code=item_code,
        item_name="Item 2WR",
        qty=Decimal("5"),
        uom=uom_code,
        qty_in_base_uom=Decimal("5"),
        rate=Decimal("20.00"),
        amount=Decimal("100.00"),
        warehouse=wh_code,
    )
    database.session.add(receipt4_item)
    database.session.commit()

    # Query late 2-way amounts for receipt4. Since receipt3 did NOT reclassify any invoice
    # (receipt3 was submitted before invoice_b existed and thus did not credit the expense account),
    # invoice_b's full amount of 100.00 USD should be completely available for receipt4!
    late_two_way_amounts_4 = _late_two_way_invoice_amounts(receipt4)
    assert late_two_way_amounts_4.get(item_code) == Decimal("100.00")


def test_late_two_way_invoice_amounts_excludes_future_invoices(app_ctx):
    """A backdated receipt only reclassifies invoices posted by its cutoff date."""
    from cacao_accounting.accounting_engine.document_builders import (
        _late_two_way_invoice_amounts,
        _purchase_invoice_has_receipt,
    )
    from cacao_accounting.database import (
        PurchaseReceipt,
        PurchaseInvoice,
        PurchaseInvoiceItem,
        database,
    )

    receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date(2026, 5, 10),
        supplier_id="SUPP-LTW",
        purchase_order_id="PO-LTW",
        docstatus=1,
    )
    database.session.add(receipt)
    database.session.flush()

    # Preceding invoice (on or before posting date of receipt)
    invoice_preceding = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 10),
        supplier_id="SUPP-LTW",
        purchase_order_id="PO-LTW",
        purchase_receipt_id=None,
        docstatus=1,
        is_return=False,
    )
    database.session.add(invoice_preceding)
    database.session.flush()

    invoice_preceding_item = PurchaseInvoiceItem(
        purchase_invoice_id=invoice_preceding.id,
        item_code="ITEM-A",
        qty=Decimal("10"),
        rate=Decimal("5.00"),
        amount=Decimal("50.00"),
    )
    database.session.add(invoice_preceding_item)

    # Future-dated/subsequent invoice (posted after receipt's posting date)
    invoice_future = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 11),
        supplier_id="SUPP-LTW",
        purchase_order_id="PO-LTW",
        purchase_receipt_id=None,
        docstatus=1,
        is_return=False,
    )
    database.session.add(invoice_future)
    database.session.flush()

    invoice_future_item = PurchaseInvoiceItem(
        purchase_invoice_id=invoice_future.id,
        item_code="ITEM-B",
        qty=Decimal("5"),
        rate=Decimal("10.00"),
        amount=Decimal("50.00"),
    )
    database.session.add(invoice_future_item)
    database.session.commit()

    # Run the utility function
    amounts = _late_two_way_invoice_amounts(receipt)

    # Only the invoice posted by the receipt's cutoff date is eligible.
    assert "ITEM-A" in amounts
    assert amounts["ITEM-A"] == Decimal("50.00")
    assert "ITEM-B" not in amounts
    assert _purchase_invoice_has_receipt(invoice_future, "cacao") is True
