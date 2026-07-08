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
        from cacao_accounting.database import Entity, database

        database.create_all()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao",
                tax_id="J0001",
                currency="NIO",
            )
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
    from cacao_accounting.database import PaymentReference, PurchaseInvoice, SalesInvoice, database

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
    database.session.add_all(
        [
            PaymentReference(
                payment_id="PAY-001",
                reference_type="purchase_invoice",
                reference_id=purchase_invoice.id,
                total_amount=Decimal("100.00"),
                outstanding_amount=Decimal("100.00"),
                allocated_amount=Decimal("30.00"),
                allocation_date=date(2026, 5, 4),
            ),
            PaymentReference(
                payment_id="PAY-002",
                reference_type="sales_invoice",
                reference_id=sales_invoice.id,
                total_amount=Decimal("150.00"),
                outstanding_amount=Decimal("150.00"),
                allocated_amount=Decimal("50.00"),
                allocation_date=date(2026, 5, 4),
            ),
        ]
    )
    database.session.commit()

    assert compute_outstanding_amount(purchase_invoice) == Decimal("70.00")
    assert compute_outstanding_amount(sales_invoice) == Decimal("100.00")


def test_compute_outstanding_amount_as_of_date_filters_allocations(app_ctx):
    from cacao_accounting.document_flow.service import compute_outstanding_amount
    from cacao_accounting.database import PaymentReference, SalesInvoice, database

    invoice = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 4),
        customer_id="CUST-TEMP",
        total=Decimal("200.00"),
        grand_total=Decimal("200.00"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add_all(
        [
            PaymentReference(
                payment_id="PAY-001",
                reference_type="sales_invoice",
                reference_id=invoice.id,
                total_amount=Decimal("200.00"),
                outstanding_amount=Decimal("200.00"),
                allocated_amount=Decimal("50.00"),
                allocation_date=date(2026, 5, 1),
            ),
            PaymentReference(
                payment_id="PAY-002",
                reference_type="sales_invoice",
                reference_id=invoice.id,
                total_amount=Decimal("200.00"),
                outstanding_amount=Decimal("150.00"),
                allocated_amount=Decimal("25.00"),
                allocation_date=date(2026, 5, 10),
            ),
        ]
    )
    database.session.commit()

    assert compute_outstanding_amount(invoice, as_of_date=date(2026, 5, 4)) == Decimal("150.00")
    assert compute_outstanding_amount(invoice, as_of_date=date(2026, 5, 10)) == Decimal("125.00")


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
    payment = PaymentEntry(company="cacao", posting_date=date(2026, 5, 5), payment_type="receive")
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
                payment_discount_account_id=discount_account.id,
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
        CompanyDefaultAccount,
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
    database.session.add_all([inventory_account, bridge_account])
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
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
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
    assert len(gl_entries) == 2
    assert sum(line.debit for line in gl_entries) == sum(line.credit for line in gl_entries)
    assert len(stock_entries) == 1
    assert stock_entries[0].qty_change == Decimal("3.000000000")
    assert bin_row.actual_qty == Decimal("3.000000000")
    assert len(valuation_layers) == 1


def test_stock_transfer_creates_stock_ledger_without_gl(app_ctx):
    from cacao_accounting.contabilidad.posting import post_document_to_gl
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

    entries = post_document_to_gl(entry)
    database.session.commit()

    stock_entries = (
        database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id))
        .scalars()
        .all()
    )
    assert entries == []
    assert len(stock_entries) == 2
    assert sorted(line.qty_change for line in stock_entries) == [Decimal("-2.000000000"), Decimal("2.000000000")]


def test_stock_transfer_preserves_valuation_cost_from_source(app_ctx):
    """INV-01: Verifica que transferencia entre bodegas use el costo real FIFO/MA,
    no la tasa ingresada por el usuario."""
    from cacao_accounting.contabilidad.posting import post_document_to_gl
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
        database.session.execute(
            database.select(StockLedgerEntry).filter_by(voucher_type="stock_entry", voucher_id=entry.id)
        )
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
            CompanyDefaultAccount(company="cacao", bridge_account_id=inv_account.id, inventory_adjustment_account_id=inv_account.id),
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
    from cacao_accounting.document_flow.service import refresh_outstanding_amount_cache, _update_document_outstanding
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
