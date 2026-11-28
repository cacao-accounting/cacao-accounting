# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1404: una referencia revertida no reduce el saldo disponible del pago.

La rama con saldo AR/AP del pago debe mirar el estado de DocumentRelation,
igual que la rama sin ledger.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.database import (
    ARAPLedgerEntry,
    DocumentRelation,
    Party,
    PaymentEntry,
    PaymentReference,
    database,
)
from cacao_accounting.document_flow.payment import compute_payment_unallocated_amount

FECHA = date(2026, 5, 15)


def _payment() -> tuple[str, str]:
    """Crea un pago aprobado de 100 con apertura AR/AP negativa."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    payment = PaymentEntry(
        company="cacao",
        payment_type="receive",
        party_type="customer",
        party_id=customer_id,
        posting_date=FECHA,
        received_amount=Decimal("100"),
        paid_amount=Decimal("100"),
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        document_no="PAY-1404",
    )
    database.session.add(payment)
    database.session.flush()
    database.session.add(
        ARAPLedgerEntry(
            company="cacao",
            ledger_type="AR",
            party_type="customer",
            party_id=customer_id,
            document_type="payment_entry",
            document_id=str(payment.id),
            document_no="PAY-1404",
            posting_date=FECHA,
            event_type="payment",
            currency="NIO",
            document_amount=Decimal("-100"),
        )
    )
    database.session.flush()
    return str(payment.id), customer_id


def _reference(payment_id: str, customer_id: str, status: str | None) -> None:
    """Añade una referencia de 30 y opcionalmente su relación documental."""
    reference = PaymentReference(
        payment_id=payment_id,
        reference_type="sales_invoice",
        reference_id="INV-1404",
        allocated_amount=Decimal("30"),
        payment_amount=Decimal("30"),
        party_type="customer",
        party_id=customer_id,
        company="cacao",
        currency="NIO",
    )
    database.session.add(reference)
    database.session.flush()
    if status is not None:
        database.session.add(
            DocumentRelation(
                source_type="sales_invoice",
                source_id="INV-1404",
                target_type="payment_entry",
                target_id=payment_id,
                target_item_id=str(reference.id),
                company="cacao",
                qty=Decimal("30"),
                amount=Decimal("30"),
                relation_type="payment_allocation",
                status=status,
            )
        )
    database.session.commit()


def test_referencia_revertida_no_consume_el_pago(entorno_contable_aislado):
    """Con la relación revertida el pago conserva los 100 disponibles."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment_id, customer_id = _payment()
        _reference(payment_id, customer_id, "reverted")
        payment = database.session.get(PaymentEntry, payment_id)

        assert compute_payment_unallocated_amount(payment) == Decimal("100")


def test_referencia_activa_consume_el_pago(entorno_contable_aislado):
    """Con relación activa el remanente baja a 70."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment_id, customer_id = _payment()
        _reference(payment_id, customer_id, "active")
        payment = database.session.get(PaymentEntry, payment_id)

        assert compute_payment_unallocated_amount(payment) == Decimal("70")


def test_referencia_legacy_sin_relacion_conserva_su_consumo(entorno_contable_aislado):
    """Una fila previa sin DocumentRelation mantiene el contrato anterior."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment_id, customer_id = _payment()
        _reference(payment_id, customer_id, None)
        payment = database.session.get(PaymentEntry, payment_id)

        assert compute_payment_unallocated_amount(payment) == Decimal("70")
