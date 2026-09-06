# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regression coverage for physical purchase returns and supplier credit notes.

Refs: #816, #817.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.posting import cancel_document, submit_document
from cacao_accounting.database import (
    GLEntry,
    PurchaseCreditNoteAllocation,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseInvoiceReceiptAllocation,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseReceiptReturnAllocation,
    PurchaseReconciliation,
    DocumentRelation,
    LandedCostAllocation,
    PurchaseMatchingConfig,
    PaymentEntry,
    StockBin,
    StockLedgerEntry,
    database,
)
from cacao_accounting.document_flow.payment import apply_advance_to_invoice, compute_outstanding_amount
from cacao_accounting.compras import _persist_purchase_reversal_relation, _validate_purchase_reversal_of
from cacao_accounting.compras.purchase_reconciliation_service import (
    get_purchase_order_status_report,
    get_purchase_reconciliation_pending,
)
from cacao_accounting.document_flow import create_document_relation
from cacao_accounting.document_flow.service import get_source_items
from cacao_accounting.document_flow.repository import get_line_flow_state


@pytest.fixture()
def app_ctx():
    """Create the complete S2P master-data fixture used by posting tests."""
    from tests.test_s2p_full_lifecycle import _setup_base_data

    app = create_app({**configuracion, "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        _setup_base_data()
        yield
        database.session.remove()
        database.drop_all()


def _create_purchase_order(order_id: str, *, qty: Decimal) -> PurchaseOrder:
    """Build the purchase-order leg required by the configured three-way match."""
    order = PurchaseOrder(
        id=order_id,
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=1,
        grand_total=qty,
        transaction_currency="NIO",
    )
    item = PurchaseOrderItem(
        id=f"{order_id}-ITEM",
        purchase_order_id=order_id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=qty,
        uom="UND",
        qty_in_base_uom=qty,
        rate=Decimal("1"),
        amount=qty,
    )
    database.session.add_all([order, item])
    database.session.commit()
    return order


def _create_receipt(
    receipt_id: str,
    *,
    qty: Decimal,
    purchase_order_id: str | None = None,
    docstatus: int = 0,
    is_return: bool = False,
    reversal_of: str | None = None,
):
    """Build a receipt line for the regression scenario."""
    receipt = PurchaseReceipt(
        id=receipt_id,
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=docstatus,
        is_return=is_return,
        reversal_of=reversal_of,
        purchase_order_id=purchase_order_id,
        grand_total=qty,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    item = PurchaseReceiptItem(
        id=f"{receipt_id}-ITEM",
        purchase_receipt_id=receipt_id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=qty,
        qty_in_base_uom=qty,
        uom="UND",
        rate=Decimal("1"),
        amount=qty,
        warehouse="ALM-MAIN",
        valuation_rate=Decimal("1"),
    )
    database.session.add_all([receipt, item])
    database.session.commit()
    return receipt, item


def _link_receipt_to_order(order: PurchaseOrder, receipt: PurchaseReceipt, receipt_item: PurchaseReceiptItem) -> None:
    """Create the positive PO relation used to derive net receipt consumption."""
    order_item = database.session.execute(
        database.select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == order.id)
    ).scalar_one()
    create_document_relation(
        source_type="purchase_order",
        source_id=order.id,
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id=receipt.id,
        target_item_id=receipt_item.id,
        qty=receipt_item.qty,
        uom=receipt_item.uom,
        rate=receipt_item.rate,
        amount=receipt_item.amount,
    )
    database.session.commit()


def _create_invoice(
    invoice_id: str, receipt_id: str, *, qty: Decimal, purchase_order_id: str | None = None, docstatus: int = 0
):
    """Build a supplier invoice linked to a receipt line."""
    invoice = PurchaseInvoice(
        id=invoice_id,
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=docstatus,
        document_type="purchase_invoice",
        purchase_receipt_id=receipt_id,
        purchase_order_id=purchase_order_id,
        grand_total=qty,
        outstanding_amount=qty,
        base_outstanding_amount=qty,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    item = PurchaseInvoiceItem(
        id=f"{invoice_id}-ITEM",
        purchase_invoice_id=invoice_id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=qty,
        uom="UND",
        rate=Decimal("1"),
        amount=qty,
    )
    database.session.add_all([invoice, item])
    database.session.commit()
    return invoice, item


def test_partial_return_of_reconciled_receipt_cancels_only_its_own_evidence(app_ctx):
    """A partial physical return must not cancel the original invoice match (Refs: #816)."""
    order = _create_purchase_order("PO-816", qty=Decimal("100"))
    receipt, receipt_item = _create_receipt("PREC-816-ORIGINAL", qty=Decimal("100"), purchase_order_id=order.id)
    submit_document(receipt)
    database.session.commit()

    invoice, invoice_item = _create_invoice("PINV-816", receipt.id, qty=Decimal("100"), purchase_order_id=order.id)
    submit_document(invoice)
    database.session.commit()

    original_allocation = database.session.execute(
        database.select(PurchaseInvoiceReceiptAllocation).where(
            PurchaseInvoiceReceiptAllocation.receipt_item_id == receipt_item.id,
            PurchaseInvoiceReceiptAllocation.invoice_item_id == invoice_item.id,
        )
    ).scalar_one()
    reconciliation = database.session.execute(
        database.select(PurchaseReconciliation).where(PurchaseReconciliation.purchase_invoice_id == invoice.id)
    ).scalar_one()
    assert original_allocation.status == "active"
    assert reconciliation.status == "reconciled"

    returned, returned_item = _create_receipt("PREC-816-RETURN", qty=Decimal("10"), is_return=True, reversal_of=receipt.id)
    submit_document(returned)
    database.session.commit()

    return_allocation = database.session.execute(
        database.select(PurchaseReceiptReturnAllocation).where(
            PurchaseReceiptReturnAllocation.return_receipt_item_id == returned_item.id
        )
    ).scalar_one()
    assert return_allocation.qty_in_base_uom == Decimal("10")
    assert compute_outstanding_amount(invoice) == Decimal("100")

    cancel_document(returned, reason="Devolución física de prueba", actor_user_id="user-manager")
    database.session.commit()

    database.session.refresh(invoice)
    database.session.refresh(reconciliation)
    database.session.refresh(original_allocation)
    assert returned.docstatus == 2
    assert return_allocation.status == "cancelled"
    assert original_allocation.status == "active"
    assert reconciliation.status == "reconciled"
    assert invoice.outstanding_amount == Decimal("100")

    original_stock = (
        database.session.execute(
            database.select(StockLedgerEntry).where(
                StockLedgerEntry.voucher_type == "purchase_receipt", StockLedgerEntry.voucher_id == receipt.id
            )
        )
        .scalars()
        .all()
    )
    return_stock = (
        database.session.execute(
            database.select(StockLedgerEntry).where(
                StockLedgerEntry.voucher_type == "purchase_receipt", StockLedgerEntry.voucher_id == returned.id
            )
        )
        .scalars()
        .all()
    )
    assert len(original_stock) == 1
    assert original_stock[0].is_cancelled is False
    assert len(return_stock) == 2
    assert sum(movement.qty_change for movement in return_stock) == Decimal("0")
    assert sum(movement.is_reversal for movement in return_stock) == 1

    original_gl = (
        database.session.execute(
            database.select(GLEntry).where(GLEntry.voucher_type == "purchase_receipt", GLEntry.voucher_id == receipt.id)
        )
        .scalars()
        .all()
    )
    assert original_gl
    assert all(entry.is_cancelled is False for entry in original_gl)

    stock_bin = database.session.execute(
        database.select(StockBin).where(StockBin.item_code == "ITEM-S2P-01", StockBin.warehouse == "ALM-MAIN")
    ).scalar_one()
    assert stock_bin.actual_qty == Decimal("100")


def test_physical_return_keeps_ap_outstanding_until_explicit_credit_note(app_ctx):
    """A physical return affects stock; only its explicit AP note reduces outstanding (Refs: #817)."""
    order = _create_purchase_order("PO-817", qty=Decimal("100"))
    receipt, _ = _create_receipt("PREC-817-ORIGINAL", qty=Decimal("100"), purchase_order_id=order.id)
    submit_document(receipt)
    database.session.commit()
    invoice, _ = _create_invoice("PINV-817", receipt.id, qty=Decimal("100"), purchase_order_id=order.id)
    submit_document(invoice)
    database.session.commit()

    returned, returned_item = _create_receipt("PREC-817-RETURN", qty=Decimal("20"), is_return=True, reversal_of=receipt.id)
    submit_document(returned)
    database.session.commit()
    assert compute_outstanding_amount(invoice) == Decimal("100")
    assert invoice.outstanding_amount == Decimal("100")

    credit_note = PurchaseInvoice(
        id="PINV-817-CN",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=0,
        document_type="purchase_credit_note",
        credit_note_type="physical_return",
        purchase_receipt_id=returned.id,
        reversal_of=invoice.id,
        is_return=True,
        grand_total=Decimal("20"),
        outstanding_amount=Decimal("20"),
        base_outstanding_amount=Decimal("20"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    credit_item = PurchaseInvoiceItem(
        id="PINV-817-CN-ITEM",
        purchase_invoice_id=credit_note.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("20"),
        uom="UND",
        rate=Decimal("1"),
        amount=Decimal("20"),
    )
    database.session.add_all([credit_note, credit_item])
    database.session.commit()

    submit_document(credit_note)
    _persist_purchase_reversal_relation(credit_note)
    database.session.commit()

    database.session.refresh(invoice)
    allocation = database.session.execute(
        database.select(PurchaseCreditNoteAllocation).where(PurchaseCreditNoteAllocation.credit_note_item_id == credit_item.id)
    ).scalar_one()
    assert allocation.return_receipt_item_id == returned_item.id
    assert allocation.allocation_type == "physical_return"
    assert allocation.status == "active"
    assert compute_outstanding_amount(invoice) == Decimal("80")
    assert invoice.outstanding_amount == Decimal("80")


def test_partial_return_reduces_uninvoiced_grni_without_exposing_return_as_pending(app_ctx):
    """A physical return reduces only the original receipt's pending GRNI (Refs: #816)."""
    order = _create_purchase_order("PO-816-GRNI", qty=Decimal("100"))
    receipt, receipt_item = _create_receipt("PREC-816-GRNI", qty=Decimal("100"), purchase_order_id=order.id)
    submit_document(receipt)
    database.session.commit()

    returned, returned_item = _create_receipt(
        "PREC-816-GRNI-RETURN", qty=Decimal("10"), is_return=True, reversal_of=receipt.id
    )
    submit_document(returned)
    database.session.commit()

    pending = get_purchase_reconciliation_pending("cacao")
    original_rows = [row for row in pending if row.purchase_receipt_item_id == receipt_item.id]
    return_rows = [row for row in pending if row.purchase_receipt_item_id == returned_item.id]
    assert len(original_rows) == 1
    assert original_rows[0].pending_qty == Decimal("90")
    assert original_rows[0].pending_amount == Decimal("90")
    assert return_rows == []


def test_return_reopens_po_for_subsequent_receipt_without_negative_relation(app_ctx):
    """An active return makes the net PO receipt balance available again (Refs: #816)."""
    order = _create_purchase_order("PO-816-REOPEN", qty=Decimal("100"))
    receipt, receipt_item = _create_receipt("PREC-816-REOPEN-ORIGINAL", qty=Decimal("100"), purchase_order_id=order.id)
    _link_receipt_to_order(order, receipt, receipt_item)
    submit_document(receipt)
    database.session.commit()

    return_receipt, return_item = _create_receipt(
        "PREC-816-REOPEN-RETURN", qty=Decimal("10"), is_return=True, reversal_of=receipt.id
    )
    submit_document(return_receipt)
    database.session.commit()

    order_item = database.session.get(PurchaseOrderItem, f"{order.id}-ITEM")
    database.session.refresh(order_item)
    assert order_item.received_qty == Decimal("90")
    available = get_source_items("purchase_order", order.id, "purchase_receipt")
    assert Decimal(available[0]["pending_qty"]) == Decimal("10")
    state = get_line_flow_state("purchase_order", order.id, order_item.id, "purchase_receipt")
    assert state is not None
    assert state.processed_qty == Decimal("90")
    assert state.pending_qty == Decimal("10")
    assert state.line_status == "partial"

    replacement, replacement_item = _create_receipt("PREC-816-REOPEN-RECEIPT", qty=Decimal("10"), purchase_order_id=order.id)
    _link_receipt_to_order(order, replacement, replacement_item)
    submit_document(replacement)
    database.session.commit()

    database.session.refresh(order_item)
    assert order_item.received_qty == Decimal("100")
    assert get_source_items("purchase_order", order.id, "purchase_receipt") == []
    state = get_line_flow_state("purchase_order", order.id, order_item.id, "purchase_receipt")
    assert state is not None
    assert state.processed_qty == Decimal("100")
    assert state.pending_qty == Decimal("0")
    assert state.line_status == "complete"
    return_relations = (
        database.session.execute(
            database.select(DocumentRelation).where(
                DocumentRelation.source_type == "purchase_order",
                DocumentRelation.source_id == order.id,
                DocumentRelation.target_id == return_receipt.id,
            )
        )
        .scalars()
        .all()
    )
    assert return_relations == []
    original_relation = database.session.execute(
        database.select(DocumentRelation).where(
            DocumentRelation.source_type == "purchase_order",
            DocumentRelation.source_id == order.id,
            DocumentRelation.target_id == receipt.id,
            DocumentRelation.target_item_id == receipt_item.id,
        )
    ).scalar_one()
    assert original_relation.qty_in_base_uom == Decimal("100")
    assert return_item.qty_in_base_uom == Decimal("10")


def test_cancelling_return_restores_po_received_cache_and_line_state(app_ctx):
    """Cancelling a return restores the gross receipt balance (Refs: #816)."""
    order = _create_purchase_order("PO-816-CANCEL", qty=Decimal("100"))
    receipt, receipt_item = _create_receipt("PREC-816-CANCEL-ORIGINAL", qty=Decimal("100"), purchase_order_id=order.id)
    _link_receipt_to_order(order, receipt, receipt_item)
    submit_document(receipt)
    database.session.commit()

    returned, _ = _create_receipt("PREC-816-CANCEL-RETURN", qty=Decimal("10"), is_return=True, reversal_of=receipt.id)
    submit_document(returned)
    database.session.commit()
    order_item = database.session.get(PurchaseOrderItem, f"{order.id}-ITEM")
    database.session.refresh(order_item)
    assert order_item.received_qty == Decimal("90")

    cancel_document(returned, reason="Reapertura de prueba", actor_user_id="user-manager")
    database.session.commit()

    database.session.refresh(order_item)
    assert returned.docstatus == 2
    assert order_item.received_qty == Decimal("100")
    assert get_source_items("purchase_order", order.id, "purchase_receipt") == []


def test_po_receipt_invoice_return_and_replacement_receipt_preserve_invoice_link(app_ctx):
    """The full return/replacement chain reopens and closes the PO without double billing."""
    order = _create_purchase_order("PO-816-FULL-CHAIN", qty=Decimal("100"))
    original, original_item = _create_receipt("PREC-816-FULL-ORIGINAL", qty=Decimal("100"), purchase_order_id=order.id)
    _link_receipt_to_order(order, original, original_item)
    submit_document(original)
    database.session.commit()

    invoice, invoice_item = _create_invoice("PINV-816-FULL", original.id, qty=Decimal("100"), purchase_order_id=order.id)
    create_document_relation(
        source_type="purchase_receipt",
        source_id=original.id,
        source_item_id=original_item.id,
        target_type="purchase_invoice",
        target_id=invoice.id,
        target_item_id=invoice_item.id,
        qty=invoice_item.qty,
        uom=invoice_item.uom,
        rate=invoice_item.rate,
        amount=invoice_item.amount,
    )
    submit_document(invoice)
    database.session.commit()
    original_allocations = (
        database.session.execute(
            database.select(PurchaseInvoiceReceiptAllocation).where(
                PurchaseInvoiceReceiptAllocation.invoice_item_id == invoice_item.id,
                PurchaseInvoiceReceiptAllocation.status == "active",
            )
        )
        .scalars()
        .all()
    )
    assert sum((row.qty_in_base_uom for row in original_allocations), Decimal("0")) == Decimal("100")

    returned, _ = _create_receipt("PREC-816-FULL-RETURN", qty=Decimal("10"), is_return=True, reversal_of=original.id)
    submit_document(returned)
    database.session.commit()

    order_item = database.session.get(PurchaseOrderItem, f"{order.id}-ITEM")
    database.session.refresh(order_item)
    status = get_purchase_order_status_report("cacao")[0]
    assert order_item.received_qty == Decimal("90")
    assert order_item.billed_qty == Decimal("100")
    assert status["receipt_status"] == "Parcial"
    assert status["billing_status"] == "Completado"

    replacement, replacement_item = _create_receipt("PREC-816-FULL-REPLACEMENT", qty=Decimal("10"), purchase_order_id=order.id)
    _link_receipt_to_order(order, replacement, replacement_item)
    submit_document(replacement)
    database.session.commit()

    database.session.refresh(order_item)
    database.session.refresh(invoice)
    final_allocations = (
        database.session.execute(
            database.select(PurchaseInvoiceReceiptAllocation).where(
                PurchaseInvoiceReceiptAllocation.invoice_item_id == invoice_item.id,
                PurchaseInvoiceReceiptAllocation.status == "active",
            )
        )
        .scalars()
        .all()
    )
    assert order_item.received_qty == Decimal("100")
    assert get_source_items("purchase_order", order.id, "purchase_receipt") == []
    assert sum((row.qty_in_base_uom for row in final_allocations), Decimal("0")) == Decimal("100")
    assert compute_outstanding_amount(invoice) == Decimal("100")


def test_invoice_total_before_full_receipt_then_return_and_final_delivery(app_ctx):
    """A 2-way invoice for the PO total survives a return and later full delivery."""
    matching_config = PurchaseMatchingConfig(company="cacao", matching_type="2-way", require_purchase_order=True)
    database.session.add(matching_config)
    database.session.flush()
    matching_config.matching_type = "2-way"
    order = _create_purchase_order("PO-816-2WAY-CHAIN", qty=Decimal("100"))
    first_receipt, first_item = _create_receipt("PREC-816-2WAY-FIRST", qty=Decimal("80"), purchase_order_id=order.id)
    _link_receipt_to_order(order, first_receipt, first_item)
    submit_document(first_receipt)
    database.session.commit()

    invoice, invoice_item = _create_invoice("PINV-816-2WAY-TOTAL", None, qty=Decimal("100"), purchase_order_id=order.id)
    order_item = database.session.get(PurchaseOrderItem, f"{order.id}-ITEM")
    create_document_relation(
        source_type="purchase_order",
        source_id=order.id,
        source_item_id=order_item.id,
        target_type="purchase_invoice",
        target_id=invoice.id,
        target_item_id=invoice_item.id,
        qty=invoice_item.qty,
        uom=invoice_item.uom,
        rate=invoice_item.rate,
        amount=invoice_item.amount,
    )
    database.session.commit()
    submit_document(invoice)
    database.session.commit()

    returned, _ = _create_receipt("PREC-816-2WAY-RETURN", qty=Decimal("10"), is_return=True, reversal_of=first_receipt.id)
    submit_document(returned)
    database.session.commit()
    order_item = database.session.get(PurchaseOrderItem, f"{order.id}-ITEM")
    database.session.refresh(order_item)
    assert order_item.received_qty == Decimal("70")
    assert order_item.billed_qty == Decimal("100")

    final_receipt, final_item = _create_receipt("PREC-816-2WAY-FINAL", qty=Decimal("30"), purchase_order_id=order.id)
    _link_receipt_to_order(order, final_receipt, final_item)
    submit_document(final_receipt)
    database.session.commit()

    database.session.refresh(order_item)
    database.session.refresh(invoice)
    allocations = (
        database.session.execute(
            database.select(PurchaseInvoiceReceiptAllocation).where(
                PurchaseInvoiceReceiptAllocation.invoice_item_id == invoice_item.id,
                PurchaseInvoiceReceiptAllocation.status == "active",
            )
        )
        .scalars()
        .all()
    )
    assert order_item.received_qty == Decimal("100")
    assert get_source_items("purchase_order", order.id, "purchase_receipt") == []
    assert sum((row.qty_in_base_uom for row in allocations), Decimal("0")) == Decimal("100")
    assert compute_outstanding_amount(invoice) == Decimal("100")


def test_late_invoice_is_allocated_before_physical_return_credit_note(app_ctx):
    """An invoice dated after its receipt remains eligible for explicit physical-return matching."""
    order = _create_purchase_order("PO-817-LATE", qty=Decimal("10"))
    receipt, receipt_item = _create_receipt("PREC-817-LATE-RECEIPT", qty=Decimal("10"), purchase_order_id=order.id)
    _link_receipt_to_order(order, receipt, receipt_item)
    receipt.posting_date = date.today() - timedelta(days=1)
    database.session.commit()
    submit_document(receipt)
    database.session.commit()

    invoice, invoice_item = _create_invoice("PINV-817-LATE", receipt.id, qty=Decimal("10"), purchase_order_id=order.id)
    invoice.posting_date = date.today()
    submit_document(invoice)
    database.session.commit()
    allocation = database.session.execute(
        database.select(PurchaseInvoiceReceiptAllocation).where(
            PurchaseInvoiceReceiptAllocation.invoice_item_id == invoice_item.id,
            PurchaseInvoiceReceiptAllocation.status == "active",
        )
    ).scalar_one()
    assert allocation.qty_in_base_uom == Decimal("10")

    returned, returned_item = _create_receipt("PREC-817-LATE-RETURN", qty=Decimal("2"), is_return=True, reversal_of=receipt.id)
    submit_document(returned)
    database.session.commit()
    credit_note = PurchaseInvoice(
        id="PINV-817-LATE-CN",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_credit_note",
        credit_note_type="physical_return",
        purchase_receipt_id=returned.id,
        reversal_of=invoice.id,
        is_return=True,
        grand_total=Decimal("2"),
        outstanding_amount=Decimal("2"),
        base_outstanding_amount=Decimal("2"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    credit_item = PurchaseInvoiceItem(
        id="PINV-817-LATE-CN-ITEM",
        purchase_invoice_id=credit_note.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("2"),
        uom="UND",
        rate=Decimal("1"),
        amount=Decimal("2"),
    )
    database.session.add_all([credit_note, credit_item])
    database.session.flush()
    from cacao_accounting.compras.purchase_reconciliation_service import create_purchase_credit_note_allocations

    allocations = create_purchase_credit_note_allocations(credit_note.id)
    assert allocations[0].return_receipt_item_id == returned_item.id


def test_supplier_advance_invoice_application_then_partial_return(app_ctx):
    """Advance -> invoice settlement -> receipt -> return keeps AP and stock evidence coherent."""
    matching_config = PurchaseMatchingConfig(company="cacao", matching_type="2-way", require_purchase_order=True)
    database.session.add(matching_config)
    order = _create_purchase_order("PO-817-ADVANCE", qty=Decimal("100"))
    advance = PaymentEntry(
        id="PAY-817-ADVANCE",
        company="cacao",
        party_type="supplier",
        party_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=1,
        payment_type="pay",
        currency="NIO",
        paid_amount=Decimal("100"),
        is_advance=True,
    )
    database.session.add(advance)
    database.session.commit()

    invoice, invoice_item = _create_invoice("PINV-817-ADVANCE", None, qty=Decimal("100"), purchase_order_id=order.id)
    order_item = database.session.get(PurchaseOrderItem, f"{order.id}-ITEM")
    create_document_relation(
        source_type="purchase_order",
        source_id=order.id,
        source_item_id=order_item.id,
        target_type="purchase_invoice",
        target_id=invoice.id,
        target_item_id=invoice_item.id,
        qty=invoice_item.qty,
        uom=invoice_item.uom,
        rate=invoice_item.rate,
        amount=invoice_item.amount,
    )
    database.session.commit()
    submit_document(invoice)
    database.session.commit()

    application = apply_advance_to_invoice(advance.id, invoice.id, Decimal("100"), date.today())
    database.session.commit()
    database.session.refresh(invoice)
    assert application.reference_id == invoice.id
    assert compute_outstanding_amount(invoice) == Decimal("0")

    receipt, receipt_item = _create_receipt("PREC-817-ADVANCE-RECEIPT", qty=Decimal("100"), purchase_order_id=order.id)
    _link_receipt_to_order(order, receipt, receipt_item)
    submit_document(receipt)
    database.session.commit()
    invoice_allocation = database.session.execute(
        database.select(PurchaseInvoiceReceiptAllocation).where(
            PurchaseInvoiceReceiptAllocation.invoice_item_id == invoice_item.id,
            PurchaseInvoiceReceiptAllocation.status == "active",
        )
    ).scalar_one()
    assert invoice_allocation.qty_in_base_uom == Decimal("100")

    returned, _ = _create_receipt("PREC-817-ADVANCE-RETURN", qty=Decimal("20"), is_return=True, reversal_of=receipt.id)
    submit_document(returned)
    database.session.commit()
    database.session.refresh(invoice)
    assert compute_outstanding_amount(invoice) == Decimal("0")
    assert compute_outstanding_amount(returned, signed=True) == Decimal("-20")

    _validate_purchase_reversal_of(
        invoice.id,
        invoice.supplier_id,
        invoice.company,
        note_amount=Decimal("20"),
        document_type="purchase_credit_note",
        posting_date=date.today(),
    )
    credit_note = PurchaseInvoice(
        id="PINV-817-ADVANCE-CN",
        company="cacao",
        supplier_id="SUP-S2P-01",
        posting_date=date.today(),
        docstatus=1,
        document_type="purchase_credit_note",
        credit_note_type="physical_return",
        purchase_receipt_id=returned.id,
        reversal_of=invoice.id,
        is_return=True,
        grand_total=Decimal("20"),
        outstanding_amount=Decimal("20"),
        base_outstanding_amount=Decimal("20"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    credit_item = PurchaseInvoiceItem(
        id="PINV-817-ADVANCE-CN-ITEM",
        purchase_invoice_id=credit_note.id,
        item_code="ITEM-S2P-01",
        item_name="Laptop Pro",
        qty=Decimal("20"),
        uom="UND",
        rate=Decimal("1"),
        amount=Decimal("20"),
    )
    database.session.add_all([credit_note, credit_item])
    database.session.flush()
    from cacao_accounting.compras.purchase_reconciliation_service import create_purchase_credit_note_allocations

    assert create_purchase_credit_note_allocations(credit_note.id)[0].return_receipt_item_id is not None
    _persist_purchase_reversal_relation(credit_note)
    database.session.commit()
    assert compute_outstanding_amount(invoice) == Decimal("0")


def test_purchase_return_reverses_capitalized_landed_cost(app_ctx):
    """A return values inventory at receipt cost plus capitalized landed cost (Refs: #816)."""
    receipt, receipt_item = _create_receipt("PREC-816-LC", qty=Decimal("10"))
    submit_document(receipt)
    database.session.add(
        LandedCostAllocation(
            company="cacao",
            document_type="purchase_receipt",
            document_id=receipt.id,
            document_line_id=receipt_item.id,
            item_code=receipt_item.item_code,
            warehouse=receipt_item.warehouse,
            posting_date=date.today(),
            base_amount=Decimal("50"),
            allocated_amount=Decimal("50"),
            final_inventory_cost=Decimal("60"),
            unit_inventory_cost=Decimal("6"),
        )
    )
    database.session.commit()

    returned, _ = _create_receipt("PREC-816-LC-RETURN", qty=Decimal("2"), is_return=True, reversal_of=receipt.id)
    submit_document(returned)
    database.session.commit()

    movements = (
        database.session.execute(
            database.select(StockLedgerEntry).where(
                StockLedgerEntry.voucher_type == "purchase_receipt", StockLedgerEntry.voucher_id == returned.id
            )
        )
        .scalars()
        .all()
    )
    assert movements[0].stock_value_difference == Decimal("-12.0000")
    inventory_entries = (
        database.session.execute(
            database.select(GLEntry).where(GLEntry.voucher_type == "purchase_receipt", GLEntry.voucher_id == returned.id)
        )
        .scalars()
        .all()
    )
    assert sum((entry.credit for entry in inventory_entries), Decimal("0")) == Decimal("12.0000")


def test_full_return_reopens_entire_po_and_removes_grni_pending(app_ctx):
    """A full physical return reopens the complete PO quantity and clears GRNI."""
    order = _create_purchase_order("PO-816-FULL-RETURN", qty=Decimal("100"))
    receipt, receipt_item = _create_receipt("PREC-816-FULL-RETURN-ORIGINAL", qty=Decimal("100"), purchase_order_id=order.id)
    _link_receipt_to_order(order, receipt, receipt_item)
    submit_document(receipt)
    database.session.commit()

    returned, returned_item = _create_receipt(
        "PREC-816-FULL-RETURN-NOTE", qty=Decimal("100"), is_return=True, reversal_of=receipt.id
    )
    submit_document(returned)
    database.session.commit()

    order_item = database.session.get(PurchaseOrderItem, f"{order.id}-ITEM")
    database.session.refresh(order_item)
    assert order_item.received_qty == Decimal("0")
    assert Decimal(get_source_items("purchase_order", order.id, "purchase_receipt")[0]["pending_qty"]) == Decimal("100")
    assert get_purchase_reconciliation_pending("cacao") == []
    allocation = database.session.execute(
        database.select(PurchaseReceiptReturnAllocation).where(
            PurchaseReceiptReturnAllocation.return_receipt_item_id == returned_item.id
        )
    ).scalar_one()
    assert allocation.qty_in_base_uom == Decimal("100")


def test_return_cannot_exceed_unreturned_source_quantity(app_ctx):
    """A return greater than the active source balance is rejected."""
    receipt, _ = _create_receipt("PREC-816-OVERRETURN-ORIGINAL", qty=Decimal("10"))
    submit_document(receipt)
    database.session.commit()
    returned, _ = _create_receipt("PREC-816-OVERRETURN-RETURN", qty=Decimal("11"), is_return=True, reversal_of=receipt.id)
    with pytest.raises(ValueError, match="excede"):
        submit_document(returned)
    database.session.rollback()
