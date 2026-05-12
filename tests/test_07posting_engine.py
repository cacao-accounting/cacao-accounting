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
        transaction=journal.__tablename__,
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
        transaction=journal.__tablename__,
        transaction_id=journal.id,
        value=Decimal("-100.00"),
        memo="Venta manual",
    )
    database.session.add_all([debit_line, credit_line])
    database.session.commit()

    post_document_to_gl(journal)
    database.session.commit()

    posted_entries = (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type=journal.__tablename__, voucher_id=journal.id))
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
            ItemAccount(item_code="ITEM-PR", company="cacao", inventory_account_id=inventory_account.id),
            CompanyDefaultAccount(
                company="cacao", bridge_account_id=bridge_account.id, default_inventory=inventory_account.id
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
    assert all(not movement.is_cancelled for movement in stock_movements)
    assert sum(movement.qty_change for movement in stock_movements) == Decimal("0E-9")
    assert bin_row.actual_qty == Decimal("0.000000000")


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
            ItemAccount(item_code="ITEM-DN", company="cacao", inventory_account_id=inventory_account.id),
            CompanyDefaultAccount(company="cacao", default_inventory=inventory_account.id, default_expense=expense_account.id),
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
    assert all(not movement.is_cancelled for movement in stock_movements)
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
            ItemAccount(item_code="ITEM-NS", company="cacao", inventory_account_id=inventory_account.id),
            CompanyDefaultAccount(company="cacao", default_inventory=inventory_account.id, default_expense=expense_account.id),
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
            ItemAccount(item_code="ITEM-GR", company="cacao", inventory_account_id=inventory_account.id),
            CompanyDefaultAccount(company="cacao", bridge_account_id=bridge_account.id),
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
            ItemAccount(item_code="ITEM-UP", company="cacao", inventory_account_id=inventory_account.id),
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
    uom = UOM(code="UND", name="Unidad")
    item = Item(code="ITEM-ST", name="Item stock", item_type="goods", is_stock_item=True, default_uom="UND")
    warehouse = Warehouse(code="WH-ST", name="Bodega stock", company="cacao")
    database.session.add_all([inventory_account, bridge_account, uom, item, warehouse])
    database.session.flush()
    database.session.add_all(
        [
            ItemAccount(item_code="ITEM-ST", company="cacao", inventory_account_id=inventory_account.id),
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
