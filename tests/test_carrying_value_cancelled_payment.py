# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1310: el valor en libros excluye pagos cancelados y sus reversas.

Una referencia append-only de un pago cancelado no debe sumar su reversión
activa al valor contable de la factura.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.accounting_engine.document_builders import _document_carrying_value_in_ledger
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.contabilidad.posting_service import cancel_document, submit_document
from cacao_accounting.database import (
    ARAPLedgerEntry,
    Accounts,
    Book,
    DocumentRelation,
    GLEntry,
    Item,
    Party,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    SalesInvoiceItem,
    User,
    UOM,
    database,
)
from cacao_accounting.document_flow.service import create_target_document, revert_relations_for_target
from cacao_accounting.internal_control_service import audit_actor

FECHA = date(2026, 5, 15)


def _seed_invoice() -> tuple[str, str, str, str]:
    """Crea factura AR de 100 con su GL y devuelve ids del escenario."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    receivable_id = str(database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="1105")).scalar_one())
    book = database.session.execute(select(Book).where(Book.entity == "cacao", Book.is_primary.is_(True))).scalar_one()
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer_id,
        document_type="sales_invoice",
        document_no="FAC-1310",
        posting_date=FECHA,
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        GLEntry(
            company="cacao",
            ledger_id=book.id,
            account_id=receivable_id,
            debit=Decimal("100"),
            credit=Decimal("0"),
            is_cancelled=False,
            is_reversal=False,
            party_type="customer",
            party_id=customer_id,
            posting_date=FECHA,
            voucher_type="sales_invoice",
            voucher_id=str(invoice.id),
            document_no="FAC-1310",
        )
    )
    database.session.flush()
    return str(invoice.id), customer_id, receivable_id, str(book.id)


def _payment(
    invoice_id: str,
    customer_id: str,
    receivable_id: str,
    book_id: str,
    *,
    cancelled: bool,
) -> str:
    """Crea un pago de 50 aplicado a la factura, activo o cancelado."""
    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id=customer_id,
        posting_date=FECHA,
        received_amount=Decimal("50"),
        paid_amount=Decimal("50"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=2 if cancelled else 1,
        document_no="PAY-1310-C" if cancelled else "PAY-1310-A",
    )
    database.session.add(payment)
    database.session.flush()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=invoice_id,
        allocated_amount=Decimal("50"),
        payment_amount=Decimal("50"),
        company="cacao",
        party_type="customer",
        party_id=customer_id,
    )
    database.session.add(reference)
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="sales_invoice",
            source_id=invoice_id,
            target_type="payment_entry",
            target_id=str(payment.id),
            target_item_id=str(reference.id),
            company="cacao",
            qty=Decimal("50"),
            amount=Decimal("50"),
            relation_type="payment_allocation",
            status="active",
        )
    )
    database.session.add(
        GLEntry(
            company="cacao",
            ledger_id=book_id,
            account_id=receivable_id,
            debit=Decimal("0"),
            credit=Decimal("50"),
            is_cancelled=cancelled,
            is_reversal=False,
            party_type="customer",
            party_id=customer_id,
            posting_date=FECHA,
            voucher_type="payment_entry",
            voucher_id=str(payment.id),
            document_no=payment.document_no,
        )
    )
    if cancelled:
        database.session.add(
            GLEntry(
                company="cacao",
                ledger_id=book_id,
                account_id=receivable_id,
                debit=Decimal("50"),
                credit=Decimal("0"),
                is_cancelled=False,
                is_reversal=True,
                party_type="customer",
                party_id=customer_id,
                posting_date=FECHA,
                voucher_type="payment_entry",
                voucher_id=str(payment.id),
                document_no=payment.document_no,
            )
        )
    database.session.commit()
    return str(payment.id)


def _carrying(invoice_id: str, receivable_id: str, book_id: str) -> Decimal | None:
    """Ejecuta el helper de valor en libros para la factura."""
    return _document_carrying_value_in_ledger(
        company="cacao",
        document_type="sales_invoice",
        document_id=invoice_id,
        exclude_payment_id="",
        party_account_id=receivable_id,
        ledger_id=book_id,
        receivable=True,
        as_of_date=None,
    )


def test_pago_activo_reduce_el_valor_en_libros(entorno_contable_aislado):
    """Un pago vigente de 50 deja el valor contable en 50."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, customer_id, receivable_id, book_id = _seed_invoice()
        _payment(invoice_id, customer_id, receivable_id, book_id, cancelled=False)
        database.session.commit()

        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("50.0000")


def test_pago_cancelado_no_suma_su_reversa(entorno_contable_aislado):
    """Cancelar el pago restaura 100 y no duplica la reversión activa."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, customer_id, receivable_id, book_id = _seed_invoice()
        _payment(invoice_id, customer_id, receivable_id, book_id, cancelled=True)
        database.session.commit()

        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("100.0000")


def _postear_factura_y_pago(application) -> tuple[str, str, str, str]:
    """Postea una factura AR de 100 y un pago parcial real de 40."""
    with application.app_context():
        customer = database.session.execute(select(Party).filter_by(code="CLI001")).scalar_one()
        actor = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        item = database.session.execute(select(Item).filter_by(code="ART01")).scalar_one()
        uom = database.session.execute(select(UOM).filter_by(code="UND")).scalar_one()
        income = database.session.execute(select(Accounts).filter_by(entity="cacao", code="4101")).scalar_one()
        invoice = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            document_date=FECHA,
            document_no=f"FAC-1310-REAL-{uuid4().hex[:8]}",
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
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=uom.code,
                rate=Decimal("100"),
                amount=Decimal("100"),
                base_amount=Decimal("100"),
                income_account_id=income.id,
            )
        )
        database.session.flush()
        with audit_actor(actor.id, actor.name), approved_execution(invoice, actor.id):
            submit_document(invoice)
        database.session.commit()
        invoice_id = str(invoice.id)

        resultado = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": FECHA,
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer.id,
                "currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": invoice_id,
                        "allocated_amount": "40",
                    }
                ],
            }
        )
        payment = database.session.get(PaymentEntry, resultado["target_id"])
        assert payment is not None
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            submit_document(payment)
        database.session.commit()
        receivable_id = str(database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="1105")).scalar_one())
        book_id = str(
            database.session.execute(select(Book.id).where(Book.entity == "cacao", Book.is_primary.is_(True))).scalar_one()
        )
        return invoice_id, str(payment.id), receivable_id, book_id


def test_cancelacion_real_restaura_valor_y_concilia_subledger(entorno_contable_aislado):
    """El flujo real deja factura en 100, pago en cero y evidencia append-only."""
    app = entorno_contable_aislado.app
    invoice_id, payment_id, receivable_id, book_id = _postear_factura_y_pago(app)
    with app.app_context():
        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("60.0000")
        assert ARAPLedgerEntry.document_balance("sales_invoice", invoice_id) == Decimal("60.0000")
        assert ARAPLedgerEntry.document_balance("payment_entry", payment_id) == Decimal("0.0000")
        actor = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        payment = database.session.get(PaymentEntry, payment_id)
        original_gl_ids = set(
            database.session.execute(
                select(GLEntry.id).filter_by(voucher_type="payment_entry", voucher_id=payment_id)
            ).scalars()
        )
        with audit_actor(actor.id, actor.name), approved_execution(payment, actor.id):
            cancel_document(
                payment,
                reason="Regresión de valor en libros",
                actor_user_id=actor.id,
                cancellation_date=FECHA,
            )
        database.session.commit()
        database.session.expire_all()

        invoice = database.session.get(SalesInvoice, invoice_id)
        payment = database.session.get(PaymentEntry, payment_id)
        assert invoice is not None and payment is not None
        assert payment.docstatus == 2
        assert invoice.outstanding_amount == Decimal("100")
        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("100.0000")
        assert ARAPLedgerEntry.document_balance("sales_invoice", invoice_id) == Decimal("100.0000")
        assert ARAPLedgerEntry.document_balance("payment_entry", payment_id) == Decimal("0.0000")
        assert database.session.execute(select(PaymentReference.id).filter_by(payment_id=payment_id)).scalar_one_or_none()
        relation = database.session.execute(
            select(DocumentRelation).filter_by(target_type="payment_entry", target_id=payment_id, status="reverted")
        ).scalar_one()
        assert relation.reversal_reason == "payment_cancelled"
        assert relation.reversed_at is not None
        original_gl = database.session.execute(select(GLEntry).where(GLEntry.id.in_(original_gl_ids))).scalars().all()
        assert original_gl and all(row.is_cancelled for row in original_gl)
        reversals = (
            database.session.execute(
                select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment_id, is_reversal=True)
            )
            .scalars()
            .all()
        )
        assert {str(row.reversal_of) for row in reversals} == {str(row.id) for row in original_gl}


def test_relacion_revertida_no_sigue_reduciendo_el_valor_en_libros(entorno_contable_aislado):
    """Una aplicación sin relación activa no reduce el valor contable de la factura."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, customer_id, receivable_id, book_id = _seed_invoice()
        payment_id = _payment(invoice_id, customer_id, receivable_id, book_id, cancelled=False)
        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("50.0000")

        assert revert_relations_for_target("payment_entry", payment_id, reason="payment_cancelled") == 1
        database.session.commit()

        assert _carrying(invoice_id, receivable_id, book_id) == Decimal("100.0000")
