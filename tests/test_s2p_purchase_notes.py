# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""S2P Purchase Credit and Debit Notes flows tests."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Party,
    CompanyParty,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseInvoiceReceiptAllocation,
    PurchaseCreditNoteAllocation,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReceiptReturnAllocation,
    Item,
    DocumentRelation,
    User,
    Entity,
    Currency,
)
from cacao_accounting.document_flow.payment import compute_outstanding_amount, refresh_outstanding_amount_cache
from cacao_accounting.compras import (
    _has_active_purchase_reversal_notes,
    _validate_purchase_reversal_of,
    _persist_purchase_reversal_relation,
)
from cacao_accounting.approval_engine import ApprovalEngine


@pytest.fixture
def app_ctx():
    """Application context fixture."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Cordobas", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="S2P-NOTES", currency="NIO"),
            ]
        )
        database.session.commit()
        yield
        database.session.remove()
        database.drop_all()


def _ensure_supplier(code, name):
    """Utility helper to ensure a supplier exists in testing DB."""
    supplier = database.session.get(Party, code)
    if not supplier:
        supplier = Party(id=code, code=code, name=name, is_supplier=True, is_active=True)
        database.session.add(supplier)
        database.session.add(
            CompanyParty(
                company="cacao",
                party_id=code,
                is_active=True,
                allow_purchase_invoice_without_receipt=True,
                allow_purchase_invoice_without_order=True,
            )
        )
        database.session.commit()
    return supplier


def _ensure_purchase_item(code="ITEM-S2P-ALLOC"):
    """Create the stock item used by allocation tests."""
    item = database.session.get(Item, code)
    if item is None:
        item = Item(
            code=code,
            name="Artículo S2P",
            item_type="goods",
            default_uom="UND",
            is_stock_item=True,
            is_purchase_item=True,
        )
        database.session.add(item)
        database.session.flush()
    return item


def test_purchase_credit_note_reduces_outstanding_balance(app_ctx):
    """Verifies that submitting a purchase credit note reduces the origin invoice's outstanding amount."""
    supplier = _ensure_supplier("SUPLR-AP-NOTE-1", "Proveedor AP Note 1")

    # Create and submit a source purchase invoice
    source_invoice = PurchaseInvoice(
        id="PINV-ORIG-001",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("1000.00"),
        outstanding_amount=Decimal("1000.00"),
        base_outstanding_amount=Decimal("1000.00"),
    )
    database.session.add(source_invoice)
    database.session.flush()

    # Create a draft purchase credit note referencing PINV-ORIG-001
    credit_note = PurchaseInvoice(
        id="PINV-CN-001",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=0,
        document_type="purchase_credit_note",
        grand_total=Decimal("400.00"),
        outstanding_amount=Decimal("400.00"),
        reversal_of="PINV-ORIG-001",
        is_return=True,
    )
    database.session.add(credit_note)
    database.session.commit()

    # Validate draft
    _validate_purchase_reversal_of(
        reversal_of=credit_note.reversal_of,
        supplier_id=credit_note.supplier_id,
        company=credit_note.company,
        note_amount=credit_note.grand_total,
        document_type=credit_note.document_type,
        posting_date=credit_note.posting_date,
    )

    # Approve/Submit the credit note and check outstanding
    credit_note.docstatus = 1
    _persist_purchase_reversal_relation(credit_note)
    database.session.commit()

    # The outstanding amount on the source invoice should have been reduced to 600.00
    assert compute_outstanding_amount(source_invoice) == Decimal("600.00")
    assert source_invoice.outstanding_amount == Decimal("600.00")


def test_purchase_return_invoice_route_is_removed(app_ctx):
    """Physical returns are receipts and cannot be created as AP invoices (Refs: #816, #817)."""
    from cacao_accounting.compras.services import _purchase_invoice_document_type

    with pytest.raises(ValueError, match="devoluciones físicas"):
        _purchase_invoice_document_type({}, "purchase_return")


def test_purchase_note_from_reconciled_invoice_skips_upstream_receipt_matching(app_ctx):
    """Una nota desde factura no exige repetir el matching contra la recepción."""
    from flask import current_app

    from cacao_accounting.compras.services import _create_purchase_invoice_from_request

    supplier = _ensure_supplier("SUPLR-AP-NOTE-RECEIPT", "Proveedor AP Note Receipt")
    receipt = PurchaseReceipt(
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(receipt)
    database.session.flush()
    source_invoice = PurchaseInvoice(
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        purchase_receipt_id=receipt.id,
        grand_total=Decimal("100"),
        outstanding_amount=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(source_invoice)
    database.session.commit()

    def save_note_items(invoice_id):
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=invoice_id,
                item_code="ITEM-NOTE-RECEIPT",
                qty=Decimal("1"),
                rate=Decimal("10"),
                amount=Decimal("10"),
            )
        )
        database.session.flush()
        return Decimal("1"), Decimal("10")

    with current_app.test_request_context(
        "/buying/purchase-invoice/new",
        method="POST",
        data={
            "company": "cacao",
            "supplier_id": supplier.id,
            "posting_date": date.today().isoformat(),
            "from_invoice": source_invoice.id,
            "item_code_0": "ITEM-NOTE-RECEIPT",
            "qty_0": "1",
            "rate_0": "10",
            "amount_0": "10",
        },
    ):
        with patch.multiple(
            "cacao_accounting.compras.services",
            exige_acceso_compania=lambda *args, **kwargs: None,
            _validate_supplier_company_membership=lambda *args, **kwargs: None,
            _validate_supplier_invoice_flags=lambda *args, **kwargs: None,
            _validate_duplicate_supplier_invoice=lambda *args, **kwargs: None,
            _validate_purchase_reversal_of=lambda *args, **kwargs: None,
            _validate_purchase_source_link=Mock(side_effect=AssertionError("no debe revalidar la recepción")),
            _save_purchase_invoice_items=save_note_items,
            _purchase_exchange_rate=lambda *args, **kwargs: Decimal("1"),
            company_currency=lambda *args, **kwargs: "NIO",
            calculate_document_total_with_taxes=lambda *args, **kwargs: Decimal("10"),
            persist_document_fiscal_snapshot=lambda *args, **kwargs: None,
            assign_document_identifier=lambda *args, **kwargs: None,
            log_create=lambda *args, **kwargs: None,
        ):
            result = _create_purchase_invoice_from_request()

    assert result is not None
    note = (
        database.session.execute(
            database.select(PurchaseInvoice)
            .where(PurchaseInvoice.document_type == "purchase_credit_note")
            .order_by(PurchaseInvoice.created.desc())
        )
        .scalars()
        .first()
    )
    assert note is not None
    assert note.purchase_receipt_id == receipt.id


def test_invoice_before_receipt_creates_idempotent_line_allocation(app_ctx):
    """Refs: #816, #817 - invoice-before-receipt is settled by durable line evidence."""
    from cacao_accounting.compras.purchase_reconciliation_service import allocate_purchase_invoice_receipt_lines

    supplier = _ensure_supplier("SUPLR-ALLOC-1", "Proveedor Allocation")
    item = _ensure_purchase_item()
    receipt = PurchaseReceipt(
        id="PREC-ALLOC-1",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date(2026, 5, 10),
        docstatus=1,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    invoice = PurchaseInvoice(
        id="PINV-ALLOC-1",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date(2026, 5, 1),
        docstatus=1,
        document_type="purchase_invoice",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add_all([receipt, invoice])
    database.session.flush()
    receipt_item = PurchaseReceiptItem(
        id="PREC-ALLOC-ITEM-1",
        purchase_receipt_id=receipt.id,
        item_code=item.code,
        qty=Decimal("2"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("20"),
    )
    invoice_item = PurchaseInvoiceItem(
        id="PINV-ALLOC-ITEM-1",
        purchase_invoice_id=invoice.id,
        item_code=item.code,
        qty=Decimal("2"),
        uom="UND",
        rate=Decimal("12"),
        amount=Decimal("24"),
    )
    database.session.add_all([receipt_item, invoice_item])
    database.session.commit()

    first = allocate_purchase_invoice_receipt_lines(receipt.id, invoice.id)
    second = allocate_purchase_invoice_receipt_lines(receipt.id, invoice.id)

    assert len(first) == 1
    assert second == []
    allocation = database.session.get(PurchaseInvoiceReceiptAllocation, first[0].id)
    assert allocation is not None
    assert allocation.qty_in_base_uom == Decimal("2")
    assert allocation.receipt_amount == Decimal("20")
    assert allocation.invoice_amount == Decimal("24")
    assert allocation.price_variance_base == Decimal("4")


def test_physical_return_and_credit_note_require_separate_audit_allocations(app_ctx):
    """Refs: #816, #817 - physical return and AP credit note remain separate."""
    from cacao_accounting.compras.purchase_reconciliation_service import (
        allocate_purchase_invoice_receipt_lines,
        create_purchase_credit_note_allocations,
        create_purchase_receipt_return_allocations,
    )

    supplier = _ensure_supplier("SUPLR-ALLOC-2", "Proveedor Return Allocation")
    item = _ensure_purchase_item("ITEM-S2P-RETURN")
    original = PurchaseReceipt(
        id="PREC-RETURN-1",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date(2026, 5, 10),
        docstatus=1,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    invoice = PurchaseInvoice(
        id="PINV-RETURN-1",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date(2026, 5, 10),
        docstatus=1,
        document_type="purchase_invoice",
        purchase_receipt_id=original.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        grand_total=Decimal("100"),
    )
    database.session.add_all([original, invoice])
    database.session.flush()
    original_item = PurchaseReceiptItem(
        id="PREC-RETURN-ITEM-1",
        purchase_receipt_id=original.id,
        item_code=item.code,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("100"),
    )
    invoice_item = PurchaseInvoiceItem(
        id="PINV-RETURN-ITEM-1",
        purchase_invoice_id=invoice.id,
        item_code=item.code,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("100"),
    )
    database.session.add_all([original_item, invoice_item])
    database.session.commit()
    allocate_purchase_invoice_receipt_lines(original.id, invoice.id)

    returned = PurchaseReceipt(
        id="PREC-RETURN-2",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date(2026, 5, 11),
        docstatus=1,
        is_return=True,
        reversal_of=original.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(returned)
    database.session.flush()
    returned_item = PurchaseReceiptItem(
        id="PREC-RETURN-ITEM-2",
        purchase_receipt_id=returned.id,
        item_code=item.code,
        qty=Decimal("2"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("20"),
    )
    database.session.add(returned_item)
    database.session.commit()
    return_allocations = create_purchase_receipt_return_allocations(returned.id)
    assert len(return_allocations) == 1

    credit_note = PurchaseInvoice(
        id="PINV-RETURN-CN-1",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date(2026, 5, 11),
        docstatus=1,
        document_type="purchase_credit_note",
        credit_note_type="physical_return",
        purchase_receipt_id=returned.id,
        reversal_of=invoice.id,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(credit_note)
    database.session.flush()
    credit_item = PurchaseInvoiceItem(
        id="PINV-RETURN-CN-ITEM-1",
        purchase_invoice_id=credit_note.id,
        item_code=item.code,
        qty=Decimal("2"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("20"),
    )
    database.session.add(credit_item)
    database.session.commit()

    credit_allocations = create_purchase_credit_note_allocations(credit_note.id)
    assert len(credit_allocations) == 1
    assert credit_allocations[0].allocation_type == "physical_return"
    assert credit_allocations[0].return_receipt_item_id == returned_item.id
    assert database.session.query(PurchaseCreditNoteAllocation).count() == 1
    assert database.session.query(PurchaseReceiptReturnAllocation).count() == 1


@pytest.mark.parametrize("document_type", ["purchase_credit_note", "purchase_debit_note"])
def test_purchase_adjustment_note_never_reconciles_receipt(app_ctx, document_type):
    """Una nota de crédito o débito ajusta AP y no debe consumir una recepción."""
    from cacao_accounting.compras.purchase_reconciliation_service import get_purchase_reconciliation_pending
    from cacao_accounting.contabilidad.posting_service import _record_purchase_reconciliation

    receipt = PurchaseReceipt(
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        transaction_currency="NIO",
        base_currency="NIO",
    )
    database.session.add(receipt)
    database.session.flush()
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id=receipt.id,
        item_code="ITEM-NOTE-ADJUSTMENT",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("100"),
    )
    database.session.add(receipt_item)
    database.session.commit()
    pending_before = get_purchase_reconciliation_pending("cacao")

    note = SimpleNamespace(
        is_return=False,
        document_type=document_type,
        purchase_receipt_id=receipt.id,
        purchase_order_id=None,
    )

    with patch("cacao_accounting.compras.purchase_reconciliation_service.reconcile_purchase_invoice") as reconcile:
        _record_purchase_reconciliation(note, Decimal("10"))

    reconcile.assert_not_called()
    pending_after = get_purchase_reconciliation_pending("cacao")
    assert [(row.pending_qty, row.pending_amount) for row in pending_after] == [
        (row.pending_qty, row.pending_amount) for row in pending_before
    ]


def test_purchase_invoice_still_reconciles_receipt():
    """Una factura normal vinculada a recepción conserva el matching automático."""
    from cacao_accounting.contabilidad.posting_service import _record_purchase_reconciliation

    invoice = SimpleNamespace(
        id="invoice-id",
        is_return=False,
        document_type="purchase_invoice",
        purchase_receipt_id="receipt-id",
        purchase_order_id=None,
        company="cacao",
    )

    with (
        patch("cacao_accounting.compras.purchase_reconciliation_service.get_matching_config") as get_config,
        patch("cacao_accounting.compras.purchase_reconciliation_service.reconcile_purchase_invoice") as reconcile,
        patch("cacao_accounting.contabilidad.posting_service._validate_purchase_receipt_for_reconciliation"),
    ):
        get_config.return_value.auto_reconcile = True
        _record_purchase_reconciliation(invoice, Decimal("10"))

    reconcile.assert_called_once_with("invoice-id")


def test_purchase_credit_note_exceeds_source_balance(app_ctx):
    """A purchase credit note cannot exceed the source invoice's credit capacity."""
    supplier = _ensure_supplier("SUPLR-AP-NOTE-2", "Proveedor AP Note 2")

    source_invoice = PurchaseInvoice(
        id="PINV-ORIG-002",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("500.00"),
        outstanding_amount=Decimal("500.00"),
        base_outstanding_amount=Decimal("500.00"),
    )
    database.session.add(source_invoice)
    database.session.commit()

    # Credit note for 600 should raise an exception
    with pytest.raises(ValueError, match="excede el credito disponible"):
        _validate_purchase_reversal_of(
            reversal_of="PINV-ORIG-002",
            supplier_id=supplier.id,
            company="cacao",
            note_amount=Decimal("600.00"),
            document_type="purchase_credit_note",
            posting_date=date.today(),
        )

    # Credit note for 500 should be allowed
    _validate_purchase_reversal_of(
        reversal_of="PINV-ORIG-002",
        supplier_id=supplier.id,
        company="cacao",
        note_amount=Decimal("500.00"),
        document_type="purchase_credit_note",
        posting_date=date.today(),
    )


def test_purchase_credit_note_after_payment_uses_invoice_capacity(app_ctx):
    """A paid invoice can still receive a credit note up to its original total."""
    supplier = _ensure_supplier("SUPLR-AP-NOTE-CURRENT", "Proveedor saldo actual")
    source_invoice = PurchaseInvoice(
        id="PINV-ORIG-CURRENT",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date(2026, 1, 1),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("100.00"),
    )
    database.session.add(source_invoice)
    database.session.commit()

    with patch("cacao_accounting.document_flow.payment.compute_outstanding_amount", return_value=Decimal("0")) as outstanding:
        _validate_purchase_reversal_of(
            reversal_of=source_invoice.id,
            supplier_id=supplier.id,
            company="cacao",
            note_amount=Decimal("100.00"),
            document_type="purchase_credit_note",
            posting_date=date(2026, 2, 15),
        )

    outstanding.assert_not_called()


def test_purchase_invoice_cannot_cancel_with_active_reversal_note(app_ctx):
    """Una factura con NC/NDto activa no puede quedar como origen cancelado."""
    supplier = _ensure_supplier("SUPLR-AP-NOTE-CANCEL", "Proveedor AP Note Cancel")
    source = PurchaseInvoice(
        id="PINV-ORIG-CANCEL",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("500"),
    )
    note = PurchaseInvoice(
        id="PINV-CN-CANCEL",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_credit_note",
        reversal_of=source.id,
        grand_total=Decimal("100"),
    )
    database.session.add_all([source, note])
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="purchase_invoice",
            source_id=source.id,
            target_type="purchase_credit_note",
            target_id=note.id,
            relation_type="invoice_reversal",
            company="cacao",
            qty=Decimal("1"),
            amount=Decimal("100"),
            status="active",
        )
    )
    database.session.flush()

    assert _has_active_purchase_reversal_notes(source.id) is True
    note.docstatus = 2
    database.session.flush()
    assert _has_active_purchase_reversal_notes(source.id) is False


def test_purchase_debit_note_revalidates_source_party_and_company(app_ctx):
    """Debit notes must keep the same supplier and company as their source invoice."""
    supplier = _ensure_supplier("SUPLR-AP-NOTE-DEBIT", "Proveedor AP Debit")
    source_invoice = PurchaseInvoice(
        id="PINV-ORIG-DEBIT",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("500.00"),
        outstanding_amount=Decimal("500.00"),
        base_outstanding_amount=Decimal("500.00"),
    )
    database.session.add(source_invoice)
    database.session.commit()

    with pytest.raises(ValueError, match="mismo proveedor"):
        _validate_purchase_reversal_of(
            reversal_of=source_invoice.id,
            supplier_id="OTHER-SUPPLIER",
            company="cacao",
            note_amount=Decimal("100.00"),
            document_type="purchase_debit_note",
            posting_date=date.today(),
        )


def test_cancel_purchase_credit_note_restores_outstanding(app_ctx):
    """Verifies that cancelling a purchase credit note restores the origin invoice's outstanding amount."""
    supplier = _ensure_supplier("SUPLR-AP-NOTE-3", "Proveedor AP Note 3")

    source_invoice = PurchaseInvoice(
        id="PINV-ORIG-003",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("800.00"),
        outstanding_amount=Decimal("800.00"),
        base_outstanding_amount=Decimal("800.00"),
    )
    credit_note = PurchaseInvoice(
        id="PINV-CN-003",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_credit_note",
        grand_total=Decimal("300.00"),
        outstanding_amount=Decimal("300.00"),
        reversal_of="PINV-ORIG-003",
        is_return=True,
    )
    database.session.add_all([source_invoice, credit_note])
    database.session.flush()

    # Create active relation
    _persist_purchase_reversal_relation(credit_note)
    database.session.commit()

    # Check outstanding has decreased to 500.00
    assert compute_outstanding_amount(source_invoice) == Decimal("500.00")
    assert source_invoice.outstanding_amount == Decimal("500.00")

    # Cancel the credit note
    from cacao_accounting.document_flow import revert_relations_for_target, refresh_source_caches_for_target

    credit_note.docstatus = 2
    target_type = credit_note.document_type or "purchase_invoice"
    revert_relations_for_target(target_type, credit_note.id)
    refresh_source_caches_for_target(target_type, credit_note.id)

    # Trigger cache update on cancellation
    if credit_note.reversal_of:
        source = database.session.get(PurchaseInvoice, credit_note.reversal_of)
        if source:
            refresh_outstanding_amount_cache(source)
    database.session.commit()

    # Outstanding should be restored to 800.00
    assert compute_outstanding_amount(source_invoice) == Decimal("800.00")
    assert source_invoice.outstanding_amount == Decimal("800.00")


def test_approval_engine_execute_submit_and_cancel_purchase_credit_note(app_ctx):
    """Verifies that ApprovalEngine execute submit and cancel successfully trigger S2P note workflows."""
    supplier = _ensure_supplier("SUPLR-AP-NOTE-AE", "Proveedor AP Note AE")
    user = User(id="user-ae", user="user-ae", name="User AE", password=b"x", classification="admin", active=True)
    database.session.add(user)
    database.session.commit()

    source_invoice = PurchaseInvoice(
        id="PINV-ORIG-AE",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_invoice",
        grand_total=Decimal("600.00"),
        outstanding_amount=Decimal("600.00"),
        base_outstanding_amount=Decimal("600.00"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    credit_note = PurchaseInvoice(
        id="PINV-CN-AE",
        supplier_id=supplier.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=0,
        document_type="purchase_credit_note",
        grand_total=Decimal("200.00"),
        outstanding_amount=Decimal("200.00"),
        reversal_of="PINV-ORIG-AE",
        is_return=True,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add_all([source_invoice, credit_note])
    database.session.flush()

    item_src = PurchaseInvoiceItem(
        purchase_invoice_id=source_invoice.id,
        item_code="ITEM-AE-1",
        qty=Decimal("1"),
        rate=Decimal("600.00"),
        amount=Decimal("600.00"),
    )
    item_cn = PurchaseInvoiceItem(
        purchase_invoice_id=credit_note.id,
        item_code="ITEM-AE-2",
        qty=Decimal("1"),
        rate=Decimal("200.00"),
        amount=Decimal("200.00"),
    )
    database.session.add_all([item_src, item_cn])
    database.session.commit()

    def fake_submit(doc):
        doc.docstatus = 1

    def fake_cancel(doc, **kwargs):
        doc.docstatus = 2

    with (
        patch("cacao_accounting.contabilidad.posting.submit_document", side_effect=fake_submit) as mock_submit,
        patch("cacao_accounting.contabilidad.posting.cancel_document", side_effect=fake_cancel) as mock_cancel,
    ):

        # ApprovalEngine._execute_submit
        ApprovalEngine._execute_submit("purchase_invoice", credit_note, user)
        mock_submit.assert_called_once_with(credit_note)
        database.session.commit()

        # Verify relation persisted and outstanding reduced
        assert compute_outstanding_amount(source_invoice) == Decimal("400.00")
        assert source_invoice.outstanding_amount == Decimal("400.00")

        # ApprovalEngine._execute_cancel
        ApprovalEngine._execute_cancel("purchase_invoice", credit_note, user)
        mock_cancel.assert_called_once()
        cancel_args, cancel_kwargs = mock_cancel.call_args
        assert cancel_args == (credit_note,)
        assert cancel_kwargs["actor_user_id"] == user.id
        database.session.commit()

        # Verify relation reverted and outstanding restored
        assert compute_outstanding_amount(source_invoice) == Decimal("600.00")
        assert source_invoice.outstanding_amount == Decimal("600.00")


def test_purchase_invoice_source_helpers_cover_receipt_and_relations(app_ctx, monkeypatch):
    """A receipt source creates a normal invoice; only invoice sources create notes."""
    from cacao_accounting.compras import services as compras_module
    from flask import current_app

    receipt = SimpleNamespace(id="REC-HELPER", purchase_order_id=None)
    source_invoice = SimpleNamespace(id="PINV-HELPER", purchase_order_id="PO-HELPER", purchase_receipt_id="REC-HELPER")
    monkeypatch.setattr(compras_module.database.session, "get", lambda model, identifier: receipt)
    monkeypatch.setattr(compras_module, "_purchase_invoice_sources", lambda source_ids: (None, receipt, None))
    with current_app.test_request_context("/buying/purchase-invoice/new", method="POST", data={"from_receipt": receipt.id}):
        invoice_context = compras_module._purchase_invoice_source_context()
    assert invoice_context["document_type"] == "purchase_invoice"
    assert invoice_context["from_receipt"] == receipt.id

    monkeypatch.setattr(compras_module, "_purchase_invoice_sources", lambda source_ids: (None, None, source_invoice))
    with current_app.test_request_context(
        "/buying/purchase-invoice/new", method="POST", data={"from_invoice": source_invoice.id}
    ):
        credit_context = compras_module._purchase_invoice_source_context()
    assert credit_context["document_type"] == "purchase_credit_note"
    assert credit_context["from_order"] == source_invoice.purchase_order_id
    assert credit_context["from_receipt"] == source_invoice.purchase_receipt_id

    calls = []
    monkeypatch.setattr(compras_module, "_validate_purchase_source_link", lambda *args: calls.append(args))
    invoice = SimpleNamespace(document_type="purchase_invoice", purchase_receipt_id="REC-1", purchase_order_id="PO-1")
    compras_module._validate_purchase_invoice_source(invoice, [])
    assert calls[-1][1:3] == ("purchase_receipt", "REC-1")
    invoice.purchase_receipt_id = None
    compras_module._validate_purchase_invoice_source(invoice, [])
    assert calls[-1][1:3] == ("purchase_order", "PO-1")
    invoice.document_type = "purchase_credit_note"
    compras_module._validate_purchase_invoice_source(invoice, [])
    assert len(calls) == 2


def test_purchase_invoice_creation_reports_validation_error(app_ctx, monkeypatch):
    """Invoice creation rolls back and reports expected validation failures."""
    from cacao_accounting.compras import services as compras_module
    from flask import current_app

    errors = []
    monkeypatch.setattr(
        compras_module, "_purchase_invoice_creation_context", lambda: (_ for _ in ()).throw(ValueError("invalid"))
    )
    monkeypatch.setattr(compras_module.database.session, "rollback", lambda: None)
    monkeypatch.setattr(compras_module, "flash_error", lambda error: errors.append(error))
    with current_app.test_request_context("/buying/purchase-invoice/new", method="POST"):
        assert compras_module._create_purchase_invoice_from_request() is None
    assert str(errors[0]) == "invalid"
