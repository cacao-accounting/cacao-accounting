# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1304: una referencia de pago sin DocumentRelation no altera el saldo.

DocumentRelation es el vínculo canónico del subledger; una fila huérfana
no representa una aplicación efectiva.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.database import (
    DocumentRelation,
    Party,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    database,
)
from cacao_accounting.document_flow.payment import compute_outstanding_amount

FECHA = date(2026, 5, 15)


def _invoice() -> str:
    """Crea una factura de venta publicada por 100."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer_id,
        document_type="sales_invoice",
        document_no="FAC-1304",
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
    return str(invoice.id)


def _reference(invoice_id: str) -> PaymentReference:
    """Crea pago aprobado y su referencia, aún sin relación documental."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id=customer_id,
        posting_date=FECHA,
        received_amount=Decimal("40"),
        paid_amount=Decimal("40"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        document_no="PAY-1304",
    )
    database.session.add(payment)
    database.session.flush()
    reference = PaymentReference(
        payment_id=payment.id,
        reference_type="sales_invoice",
        reference_id=invoice_id,
        reference_document_no="FAC-1304",
        reference_date=FECHA,
        allocated_amount=Decimal("40"),
        payment_amount=Decimal("40"),
        party_type="customer",
        party_id=customer_id,
        company="cacao",
        currency="NIO",
    )
    database.session.add(reference)
    database.session.flush()
    return reference


def test_referencia_huerfana_no_reduce_el_saldo(entorno_contable_aislado):
    """Sin relación activa el saldo permanece en 100."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id = _invoice()
        _reference(invoice_id)
        database.session.commit()
        invoice = database.session.get(SalesInvoice, invoice_id)

        assert compute_outstanding_amount(invoice, as_of_date=FECHA) == Decimal("100")


def test_relacion_activa_es_la_unica_que_descuenta(entorno_contable_aislado):
    """Al crear la relación canónica el saldo baja a 60."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id = _invoice()
        reference = _reference(invoice_id)
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id=invoice_id,
                target_type="payment_entry",
                target_id=str(reference.payment_id),
                target_item_id=str(reference.id),
                company="cacao",
                qty=Decimal("40"),
                amount=Decimal("40"),
                relation_type="payment_allocation",
                status="active",
            )
        )
        database.session.commit()
        invoice = database.session.get(SalesInvoice, invoice_id)

        assert compute_outstanding_amount(invoice, as_of_date=FECHA) == Decimal("60")
