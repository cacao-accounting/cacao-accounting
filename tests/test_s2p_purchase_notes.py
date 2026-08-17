# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""S2P Purchase Credit and Debit Notes flows tests."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Party,
    CompanyParty,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    DocumentRelation,
    User,
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


def test_purchase_credit_note_exceeds_source_balance(app_ctx):
    """Verifies that a purchase credit note cannot exceed the outstanding balance of its source."""
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
    with pytest.raises(ValueError, match="excede el saldo pendiente"):
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

    def fake_cancel(doc):
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
        mock_cancel.assert_called_once_with(credit_note)
        database.session.commit()

        # Verify relation reverted and outstanding restored
        assert compute_outstanding_amount(source_invoice) == Decimal("600.00")
        assert source_invoice.outstanding_amount == Decimal("600.00")
