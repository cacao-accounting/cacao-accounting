# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1222: cancelling a commercial purchase credit note releases its line allocation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import cancel_document, submit_document
from cacao_accounting.database import (
    ARAPLedgerEntry,
    Accounts,
    GLEntry,
    Item,
    Party,
    PurchaseCreditNoteAllocation,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    UOM,
    User,
    database,
)
from cacao_accounting.internal_control_service import audit_actor


def _create_purchase_document(
    *,
    actor: User,
    supplier: Party,
    item: Item,
    uom: UOM,
    expense_account: Accounts,
    amount: Decimal,
    document_no: str,
    is_credit_note: bool,
    source_invoice_id: str | None = None,
) -> PurchaseInvoice:
    """Create and post one invoice or commercial credit note without matching sources."""
    document = PurchaseInvoice(
        company="cacao",
        posting_date=date(2026, 5, 20) if is_credit_note else date(2026, 5, 10),
        document_no=document_no,
        document_type="purchase_credit_note" if is_credit_note else "purchase_invoice",
        credit_note_type="commercial_adjustment" if is_credit_note else None,
        is_return=is_credit_note,
        reversal_of=source_invoice_id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(document)
    database.session.flush()
    database.session.add(
        PurchaseInvoiceItem(
            purchase_invoice_id=document.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom=uom.code,
            rate=amount,
            amount=amount,
            base_amount=amount,
            expense_account_id=expense_account.id,
        )
    )
    database.session.commit()
    with audit_actor(actor.id, actor.name), approved_execution(document, actor.id):
        submit_document(document)
    database.session.commit()
    return document


def test_cancelled_commercial_credit_note_releases_source_line_capacity(entorno_contable_aislado):
    """A cancelled note keeps its evidence but no longer consumes invoice capacity."""
    app = entorno_contable_aislado.app
    with app.app_context():
        actor = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        supplier = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(database.select(UOM).filter_by(code="UND")).scalar_one()
        expense = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="5201")).scalar_one()

        source_invoice = _create_purchase_document(
            actor=actor,
            supplier=supplier,
            item=item,
            uom=uom,
            expense_account=expense,
            amount=Decimal("100"),
            document_no=f"PI-CN-{uuid4().hex[:8]}",
            is_credit_note=False,
        )
        first_note = _create_purchase_document(
            actor=actor,
            supplier=supplier,
            item=item,
            uom=uom,
            expense_account=expense,
            amount=Decimal("80"),
            document_no=f"CN-CANCEL-{uuid4().hex[:8]}",
            is_credit_note=True,
            source_invoice_id=source_invoice.id,
        )
        first_allocation = database.session.execute(
            database.select(PurchaseCreditNoteAllocation).where(
                PurchaseCreditNoteAllocation.credit_note_item_id.in_(
                    database.select(PurchaseInvoiceItem.id).where(PurchaseInvoiceItem.purchase_invoice_id == first_note.id)
                )
            )
        ).scalar_one()
        assert first_allocation.status == "active"
        ap_before = (
            database.session.execute(database.select(ARAPLedgerEntry).where(ARAPLedgerEntry.document_id == first_note.id))
            .scalars()
            .all()
        )
        gl_before = database.session.execute(database.select(GLEntry).filter_by(voucher_id=first_note.id)).scalars().all()
        assert ap_before and gl_before

        with audit_actor(actor.id, actor.name), approved_execution(first_note, actor.id):
            cancel_document(
                first_note,
                reason="Anular nota comercial de prueba",
                actor_user_id=actor.id,
                cancellation_date=first_note.posting_date,
            )
        database.session.commit()

        database.session.expire_all()
        cancelled_allocation = database.session.get(PurchaseCreditNoteAllocation, first_allocation.id)
        assert cancelled_allocation is not None
        assert cancelled_allocation.status == "cancelled"
        assert database.session.get(PurchaseInvoice, first_note.id).docstatus == 2
        note_ap_entries = (
            database.session.execute(database.select(ARAPLedgerEntry).where(ARAPLedgerEntry.document_id == first_note.id))
            .scalars()
            .all()
        )
        assert len(note_ap_entries) > len(ap_before)
        assert len(note_ap_entries) >= 2
        assert {entry.posting_date for entry in note_ap_entries} == {first_note.posting_date}
        assert sum((entry.document_amount for entry in note_ap_entries), Decimal("0")) == Decimal("0")
        note_gl_entries = (
            database.session.execute(database.select(GLEntry).filter_by(voucher_id=first_note.id)).scalars().all()
        )
        assert len(note_gl_entries) > len(gl_before)
        assert {entry.posting_date for entry in note_gl_entries} == {first_note.posting_date}
        by_ledger: dict[str, tuple[Decimal, Decimal]] = {}
        for entry in note_gl_entries:
            debit, credit = by_ledger.get(entry.ledger_id, (Decimal("0"), Decimal("0")))
            by_ledger[entry.ledger_id] = (debit + Decimal(entry.debit), credit + Decimal(entry.credit))
        assert by_ledger and all(debit == credit for debit, credit in by_ledger.values())

        next_note = _create_purchase_document(
            actor=actor,
            supplier=supplier,
            item=item,
            uom=uom,
            expense_account=expense,
            amount=Decimal("30"),
            document_no=f"CN-NEXT-{uuid4().hex[:8]}",
            is_credit_note=True,
            source_invoice_id=source_invoice.id,
        )
        next_allocation = database.session.execute(
            database.select(PurchaseCreditNoteAllocation).where(
                PurchaseCreditNoteAllocation.credit_note_item_id.in_(
                    database.select(PurchaseInvoiceItem.id).where(PurchaseInvoiceItem.purchase_invoice_id == next_note.id)
                )
            )
        ).scalar_one()
        assert next_allocation.status == "active"
        assert next_allocation.amount == Decimal("30")
