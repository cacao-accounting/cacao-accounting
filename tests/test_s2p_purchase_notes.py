# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""S2P Purchase Credit and Debit Notes flows tests."""

from datetime import date
from decimal import Decimal
import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Party,
    CompanyParty,
    PurchaseInvoice,
)
from cacao_accounting.document_flow.payment import compute_outstanding_amount, refresh_outstanding_amount_cache
from cacao_accounting.compras import (
    _validate_purchase_reversal_of,
    _persist_purchase_reversal_relation,
)


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
        database.session.add(CompanyParty(company="cacao", party_id=code, is_active=True))
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
