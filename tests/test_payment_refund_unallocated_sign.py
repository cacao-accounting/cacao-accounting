# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1143: el remanente de un reembolso se orienta con el signo del pago.

Una apertura normal abre en negativo y un reembolso en positivo; el saldo
no aplicado debe ser positivo en ambos casos para que la conciliación
pueda asignarlo.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.contabilidad.arap_allocation import list_open_items
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


def _party_id(code: str) -> str:
    """Devuelve el tercero del escenario contable."""
    return str(database.session.execute(select(Party.id).filter_by(code=code)).scalar_one())


def _payment(payment_type: str, party_type: str, amount: Decimal) -> PaymentEntry:
    """Crea un pago aprobado con su apertura canónica orientada."""
    party_id = _party_id("CLI001" if party_type == "customer" else "PRV001")
    payment = PaymentEntry(
        company="cacao",
        payment_type=payment_type,
        party_type=party_type,
        party_id=party_id,
        posting_date=FECHA,
        paid_amount=amount,
        received_amount=amount,
        currency="NIO",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        docstatus=1,
        document_no=f"PAY-1143-{payment_type}-{party_type}",
    )
    database.session.add(payment)
    database.session.flush()
    normal = (payment_type == "receive") == (party_type == "customer")
    sign = Decimal("-1") if normal else Decimal("1")
    database.session.add(
        ARAPLedgerEntry(
            company="cacao",
            ledger_type="AR" if party_type == "customer" else "AP",
            party_type=party_type,
            party_id=party_id,
            document_type="payment_entry",
            document_id=str(payment.id),
            document_no=payment.document_no,
            posting_date=FECHA,
            event_type="opening",
            currency="NIO",
            document_amount=sign * amount,
        )
    )
    database.session.flush()
    return payment


@pytest.mark.parametrize(
    ("payment_type", "party_type"),
    [
        ("pay", "supplier"),
        ("receive", "customer"),
        ("receive", "supplier"),
        ("pay", "customer"),
    ],
)
def test_remanente_positivo_en_pagos_y_reembolsos(entorno_contable_aislado, payment_type, party_type):
    """Las cuatro direcciones exponen el mismo remanente de 100."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment = _payment(payment_type, party_type, Decimal("100"))

        assert compute_payment_unallocated_amount(payment) == Decimal("100")

        open_items = list_open_items(company="cacao", party_type=party_type, party_id=payment.party_id)
        assert [item.outstanding for item in open_items if item.document_id == str(payment.id)] == [Decimal("100")]


def test_reembolso_descuenta_referencias_pendientes(entorno_contable_aislado):
    """Un reembolso con 40 pendientes conserva 60 disponibles."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment = _payment("receive", "supplier", Decimal("100"))
        reference = PaymentReference(
            payment_id=payment.id,
            reference_type="purchase_credit_note",
            reference_id="CN-1143",
            allocated_amount=Decimal("40"),
            payment_amount=Decimal("40"),
            party_type="supplier",
            party_id=payment.party_id,
            company="cacao",
        )
        database.session.add(reference)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_credit_note",
                source_id="CN-1143",
                target_type="payment_entry",
                target_id=str(payment.id),
                target_item_id=str(reference.id),
                company="cacao",
                qty=Decimal("40"),
                amount=Decimal("40"),
                relation_type="payment_allocation",
                status="active",
            )
        )

        assert compute_payment_unallocated_amount(payment) == Decimal("60")


def test_reembolso_cancelado_no_tiene_remanente(entorno_contable_aislado):
    """Un reembolso cancelado conserva el contrato de saldo cero."""
    app = entorno_contable_aislado.app
    with app.app_context():
        payment = _payment("receive", "supplier", Decimal("100"))
        payment.docstatus = 2
        database.session.flush()

        assert compute_payment_unallocated_amount(payment) == Decimal("0")


def test_reembolso_de_proveedor_se_aplica_a_nota_de_credito(entorno_contable_aislado):
    """El reembolso conserva 100 disponibles y la conciliación puede asignarlos."""
    from cacao_accounting.database import PurchaseInvoice
    from cacao_accounting.document_flow.payment import apply_payment_reconciliation

    app = entorno_contable_aislado.app
    with app.app_context():
        payment = _payment("receive", "supplier", Decimal("100"))
        note = PurchaseInvoice(
            company="cacao",
            supplier_id=payment.party_id,
            supplier_name="Proveedor Principal SA",
            document_type="purchase_credit_note",
            document_no="CN-1143",
            posting_date=FECHA,
            docstatus=1,
            is_return=True,
            total=Decimal("100"),
            grand_total=Decimal("100"),
            base_total=Decimal("100"),
            base_grand_total=Decimal("100"),
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(note)
        database.session.flush()
        database.session.add(
            ARAPLedgerEntry(
                company="cacao",
                ledger_type="AP",
                party_type="supplier",
                party_id=payment.party_id,
                document_type="purchase_credit_note",
                document_id=str(note.id),
                document_no="CN-1143",
                posting_date=FECHA,
                event_type="opening",
                currency="NIO",
                document_amount=Decimal("-100"),
            )
        )
        database.session.commit()

        apply_payment_reconciliation(
            company="cacao",
            party_type="supplier",
            party_id=payment.party_id,
            allocation_date=FECHA,
            lines=[
                {
                    "payment_id": payment.id,
                    "flow_source_type": "purchase_credit_note",
                    "reference_id": note.id,
                    "allocated_amount": "100",
                    "payment_amount": "100",
                }
            ],
        )
        database.session.commit()

        assert compute_payment_unallocated_amount(payment) == Decimal("0")
        assert (
            database.session.execute(
                select(PaymentReference.id).filter_by(payment_id=payment.id, reference_id=note.id)
            ).scalar_one_or_none()
            is not None
        )
