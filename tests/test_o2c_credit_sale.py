"""Caso O2C de venta a crédito, abono parcial y anulación del cobro."""

from datetime import date
from decimal import Decimal
from importlib import import_module
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import PostingError, cancel_document, submit_document
from cacao_accounting.database import (
    ARAPLedgerEntry,
    ARAPOpenItem,
    DocumentTransition,
    DeliveryNote,
    GLEntry,
    Accounts,
    Item,
    PaymentEntry,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    User,
    UOM,
    database,
)
from cacao_accounting.document_flow.service import create_target_document
from cacao_accounting.internal_control_service import audit_actor
from cacao_accounting.ventas.services import _cancel_linked_delivery_note


def test_venta_credito_abono_parcial_y_anulacion_conservan_evidencia(entorno_contable):
    """Anular el abono restaura cartera sin borrar movimientos contables."""
    with entorno_contable.app.app_context():
        suffix = uuid4().hex[:10]
        company_code = "cacao"
        customer = database.session.execute(select(Party).where(Party.code == "CLI001")).scalar_one()
        actor = database.session.execute(select(User).where(User.user == "admin")).scalar_one()
        item = database.session.execute(select(Item).where(Item.code == "ART01")).scalar_one()
        uom = database.session.execute(select(UOM).where(UOM.code == "UND")).scalar_one()
        income_account = database.session.execute(select(Accounts).where(Accounts.code == "4101")).scalar_one()
        invoice = SalesInvoice(
            company=company_code,
            posting_date=date(2026, 5, 15),
            document_date=date(2026, 5, 15),
            document_no=f"V-{suffix}",
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("100"),
            base_total=Decimal("100"),
            grand_total=Decimal("100"),
            base_grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
            base_outstanding_amount=Decimal("100"),
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom=uom.code,
                rate=Decimal("50"),
                amount=Decimal("100"),
                base_amount=Decimal("100"),
                income_account_id=income_account.id,
            )
        )
        database.session.flush()
        with audit_actor(actor.id, actor.name), approved_execution(invoice, actor.id):
            submit_document(invoice)
        database.session.commit()

        payment_result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": company_code,
                "posting_date": "2026-05-20",
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer.id,
                "currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": invoice.id,
                        "allocated_amount": "40",
                    }
                ],
            }
        )
        payment = database.session.get(PaymentEntry, payment_result["target_id"])
        assert payment is not None
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            submit_document(payment)
        database.session.commit()

        open_item = database.session.execute(
            select(ARAPOpenItem).where(
                ARAPOpenItem.document_type == "sales_invoice",
                ARAPOpenItem.document_id == invoice.id,
            )
        ).scalar_one()
        assert Decimal(str(open_item.unallocated_amount)) == Decimal("60")

        invoice_gl_before = database.session.execute(
            select(func.count(GLEntry.id)).where(
                GLEntry.voucher_id == invoice.id,
                GLEntry.is_cancelled.is_(False),
            )
        ).scalar_one()
        payment_gl_before = database.session.execute(
            select(func.count(GLEntry.id)).where(
                GLEntry.voucher_id == payment.id,
            )
        ).scalar_one()
        arap_events_before = database.session.execute(
            select(func.count(ARAPLedgerEntry.id)).where(
                ARAPLedgerEntry.document_id == invoice.id,
            )
        ).scalar_one()
        payment_arap_events_before = database.session.execute(
            select(func.count(ARAPLedgerEntry.id)).where(ARAPLedgerEntry.document_id == payment.id)
        ).scalar_one()
        payment_transitions_before = database.session.execute(
            select(func.count(DocumentTransition.id)).where(
                DocumentTransition.source_id == payment.id,
                DocumentTransition.transition_type == "cancellation",
            )
        ).scalar_one()

        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            with pytest.raises(PostingError, match="debe coincidir con la fecha de contabilización del documento"):
                cancel_document(
                    payment,
                    reason="Abono registrado por error",
                    actor_user_id=actor.id,
                    cancellation_date=date(2026, 5, 21),
                )
        database.session.expire_all()
        payment = database.session.get(PaymentEntry, payment.id)
        assert payment is not None and payment.docstatus == 1
        assert (
            database.session.execute(
                select(func.count(ARAPLedgerEntry.id)).where(ARAPLedgerEntry.document_id == invoice.id)
            ).scalar_one()
            == arap_events_before
        )
        invoice_open_item = database.session.execute(
            select(ARAPOpenItem).where(
                ARAPOpenItem.document_type == "sales_invoice",
                ARAPOpenItem.document_id == invoice.id,
            )
        ).scalar_one()
        assert Decimal(str(invoice_open_item.unallocated_amount)) == Decimal("60")
        assert (
            database.session.execute(select(func.count(GLEntry.id)).where(GLEntry.voucher_id == payment.id)).scalar_one()
            == payment_gl_before
        )
        assert (
            database.session.execute(
                select(func.count(ARAPLedgerEntry.id)).where(ARAPLedgerEntry.document_id == payment.id)
            ).scalar_one()
            == payment_arap_events_before
        )
        assert (
            database.session.execute(
                select(func.count(DocumentTransition.id)).where(
                    DocumentTransition.source_id == payment.id,
                    DocumentTransition.transition_type == "cancellation",
                )
            ).scalar_one()
            == payment_transitions_before
        )

        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            cancel_document(
                payment,
                reason="Abono registrado por error",
                actor_user_id=actor.id,
                cancellation_date=date(2026, 5, 20),
            )
        database.session.commit()
        database.session.expire_all()

        invoice = database.session.get(SalesInvoice, invoice.id)
        payment = database.session.get(PaymentEntry, payment.id)
        open_item = database.session.execute(
            select(ARAPOpenItem).where(
                ARAPOpenItem.document_type == "sales_invoice",
                ARAPOpenItem.document_id == invoice.id,
            )
        ).scalar_one()
        assert invoice is not None and payment is not None
        assert invoice.docstatus == 1
        assert payment.docstatus == 2
        assert Decimal(str(invoice.outstanding_amount)) == Decimal("100")
        assert Decimal(str(invoice.base_outstanding_amount)) == Decimal("100")
        assert Decimal(str(open_item.unallocated_amount)) == Decimal("100")
        assert database.session.execute(
            select(func.sum(ARAPLedgerEntry.document_amount)).where(
                ARAPLedgerEntry.document_type == "sales_invoice",
                ARAPLedgerEntry.document_id == invoice.id,
            )
        ).scalar_one() == Decimal("100.0000")
        assert (
            database.session.execute(
                select(func.count(GLEntry.id)).where(
                    GLEntry.voucher_id == invoice.id,
                    GLEntry.is_cancelled.is_(False),
                )
            ).scalar_one()
            == invoice_gl_before
        )
        assert (
            database.session.execute(
                select(func.count(GLEntry.id)).where(
                    GLEntry.voucher_id == payment.id,
                )
            ).scalar_one()
            > payment_gl_before
        )
        assert (
            database.session.execute(
                select(func.count(GLEntry.id)).where(
                    GLEntry.voucher_id == payment.id,
                    GLEntry.is_reversal.is_(True),
                    GLEntry.reversal_of.is_not(None),
                )
            ).scalar_one()
            == payment_gl_before
        )
        assert (
            database.session.execute(
                select(func.count(ARAPLedgerEntry.id)).where(
                    ARAPLedgerEntry.document_id == invoice.id,
                )
            ).scalar_one()
            > arap_events_before
        )


def test_anular_factura_usa_fecha_de_contabilizacion_de_nota_vinculada(entorno_contable, monkeypatch):
    """La nota de entrega vinculada conserva su propia fecha de anulación."""
    with entorno_contable.app.app_context():
        delivery_date = date(2026, 5, 10)
        invoice_date = date(2026, 5, 15)
        delivery_note = DeliveryNote(company="cacao", posting_date=delivery_date, docstatus=1)
        database.session.add(delivery_note)
        database.session.flush()
        invoice = SalesInvoice(
            company="cacao",
            posting_date=invoice_date,
            delivery_note_id=delivery_note.id,
            update_inventory=True,
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.flush()
        actor_id = database.session.execute(select(User.id).where(User.user == "admin")).scalar_one()

        cancellation_calls = []
        sales_services = import_module("cacao_accounting.ventas.services")
        monkeypatch.setattr(
            sales_services,
            "cancel_document",
            lambda document, **kwargs: cancellation_calls.append((document, kwargs)),
        )
        monkeypatch.setattr(sales_services, "_restore_reservation_for_delivery_note", lambda document: None)
        monkeypatch.setattr(sales_services, "log_cancel", lambda document: None)

        with entorno_contable.app.test_request_context():
            _cancel_linked_delivery_note(
                invoice,
                reason="Factura cancelada",
                actor_user_id=actor_id,
            )

        assert invoice.posting_date != delivery_note.posting_date
        assert len(cancellation_calls) == 1
        cancelled_document, cancellation_kwargs = cancellation_calls[0]
        assert cancelled_document.id == delivery_note.id
        assert cancellation_kwargs["cancellation_date"] == delivery_date


def test_reembolso_de_nota_credito_anulado_restaura_saldo_abierto(entorno_contable):
    """Anular un reembolso vuelve a abrir la nota de crédito en AR/AP y su caché."""
    with entorno_contable.app.app_context():
        customer = database.session.execute(select(Party).where(Party.code == "CLI001")).scalar_one()
        actor = database.session.execute(select(User).where(User.user == "admin")).scalar_one()
        item = database.session.execute(select(Item).where(Item.code == "ART01")).scalar_one()
        uom = database.session.execute(select(UOM).where(UOM.code == "UND")).scalar_one()
        income_account = database.session.execute(select(Accounts).where(Accounts.code == "4101")).scalar_one()
        credit_note = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_date=date(2026, 5, 15),
            document_no=f"NC-{uuid4().hex[:10]}",
            document_type="sales_credit_note",
            is_return=True,
            customer_id=customer.id,
            customer_name=customer.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("40"),
            base_total=Decimal("40"),
            grand_total=Decimal("40"),
            base_grand_total=Decimal("40"),
            outstanding_amount=Decimal("40"),
            base_outstanding_amount=Decimal("40"),
        )
        database.session.add(credit_note)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=credit_note.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("40"),
                amount=Decimal("40"),
                base_amount=Decimal("40"),
                income_account_id=income_account.id,
            )
        )
        database.session.flush()
        with audit_actor(actor.id, actor.name), approved_execution(credit_note, actor.id):
            submit_document(credit_note)
        database.session.commit()

        refund_result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": "2026-05-20",
                "payment_type": "pay",
                "party_type": "customer",
                "party_id": customer.id,
                "currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {
                        "source_document_type": "sales_credit_note",
                        "source_document_id": credit_note.id,
                        "allocated_amount": "20",
                    }
                ],
            }
        )
        refund = database.session.get(PaymentEntry, refund_result["target_id"])
        assert refund is not None
        with audit_actor(actor.id, actor.name), approved_execution(refund, actor.id):
            submit_document(refund)
        database.session.commit()

        open_item = database.session.execute(
            select(ARAPOpenItem).where(
                ARAPOpenItem.document_type == "sales_credit_note",
                ARAPOpenItem.document_id == credit_note.id,
            )
        ).scalar_one()
        assert Decimal(str(open_item.unallocated_amount)) == Decimal("20")
        with audit_actor(actor.id, actor.name), approved_execution(refund, actor.id):
            cancel_document(
                refund,
                reason="Reembolso registrado por error",
                actor_user_id=actor.id,
                cancellation_date=date(2026, 5, 20),
            )
        database.session.commit()
        database.session.expire_all()

        credit_note = database.session.get(SalesInvoice, credit_note.id)
        open_item = database.session.execute(
            select(ARAPOpenItem).where(
                ARAPOpenItem.document_type == "sales_credit_note",
                ARAPOpenItem.document_id == credit_note.id,
            )
        ).scalar_one()
        assert Decimal(str(credit_note.outstanding_amount)) == Decimal("40")
        assert Decimal(str(open_item.unallocated_amount)) == Decimal("40")
