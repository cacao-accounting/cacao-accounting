# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1469: la ruta HTTP de conciliación rechaza importes no finitos sin 500."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from cacao_accounting.database import (
    ARAPLedgerEntry,
    DocumentRelation,
    Party,
    PaymentEntry,
    PaymentReference,
    Reconciliation,
    SalesInvoice,
    User,
    database,
)
from cacao_accounting.document_flow.payment import compute_payment_unallocated_amount

FECHA = date(2026, 5, 15)
PATH = "/cash_management/payment-reconciliation"


def _escenario() -> tuple[str, str, str]:
    """Siembra una cuenta por cobrar y un pago recibido con apertura AR real."""
    customer_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    invoice = SalesInvoice(
        company="cacao",
        posting_date=FECHA,
        document_no="SI-1469-HTTP",
        document_type="sales_invoice",
        customer_id=customer_id,
        customer_name="Cliente 1469",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        grand_total=Decimal("100"),
        outstanding_amount=Decimal("100"),
        docstatus=1,
    )
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
        document_no="PAY-1469-HTTP",
        docstatus=1,
    )
    database.session.add_all([invoice, payment])
    database.session.flush()
    database.session.add_all(
        [
            ARAPLedgerEntry(
                company="cacao",
                ledger_type="AR",
                party_type="customer",
                party_id=customer_id,
                document_type="sales_invoice",
                document_id=invoice.id,
                document_no=invoice.document_no,
                posting_date=FECHA,
                event_type="opening",
                currency="NIO",
                document_amount=Decimal("100"),
            ),
            ARAPLedgerEntry(
                company="cacao",
                ledger_type="AR",
                party_type="customer",
                party_id=customer_id,
                document_type="payment_entry",
                document_id=payment.id,
                document_no=payment.document_no,
                posting_date=FECHA,
                event_type="opening",
                currency="NIO",
                document_amount=Decimal("-100"),
            ),
        ]
    )
    database.session.commit()
    return str(invoice.id), str(payment.id), customer_id


def _cliente(app):
    """Cliente autenticado sobre la base aislada del escenario."""
    client = app.test_client()
    with app.app_context():
        admin_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def _payload(invoice_id: str, payment_id: str, customer_id: str, amount: str) -> dict:
    """Construye el formulario JSON que consume la ruta de conciliación."""
    return {
        "company": "cacao",
        "party_type": "customer",
        "party_id": customer_id,
        "allocation_date": FECHA.isoformat(),
        "lines": [
            {
                "payment_id": payment_id,
                "reference_type": "sales_invoice",
                "reference_id": invoice_id,
                "allocated_amount": amount,
            }
        ],
    }


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
def test_ruta_rechaza_no_finitos_sin_500_ni_persistencia(entorno_contable_aislado, amount: str):
    """NaN e infinitos se devuelven como validación y revierten toda la fila."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, payment_id, customer_id = _escenario()

    response = _cliente(app).post(
        PATH, data={"payment_reconciliation_payload": json.dumps(_payload(invoice_id, payment_id, customer_id, amount))}
    )

    assert response.status_code == 200
    assert "número finito" in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(select(Reconciliation)).scalars().all() == []
        assert database.session.execute(select(PaymentReference)).scalars().all() == []
        assert (
            database.session.execute(select(ARAPLedgerEntry).where(ARAPLedgerEntry.event_type == "allocation")).scalars().all()
            == []
        )
        invoice = database.session.get(SalesInvoice, invoice_id)
        payment = database.session.get(PaymentEntry, payment_id)
        assert invoice is not None and invoice.outstanding_amount == Decimal("100")
        assert payment is not None and compute_payment_unallocated_amount(payment) == Decimal("100")


def test_ruta_acepta_decimal_finito_y_actualiza_saldos(entorno_contable_aislado):
    """Un importe finito completa la conciliación y deja evidencia canónica."""
    app = entorno_contable_aislado.app
    with app.app_context():
        invoice_id, payment_id, customer_id = _escenario()

    response = _cliente(app).post(
        PATH,
        data={"payment_reconciliation_payload": json.dumps(_payload(invoice_id, payment_id, customer_id, "25.00"))},
    )

    assert response.status_code == 302
    with app.app_context():
        reconciliacion = database.session.execute(select(Reconciliation)).scalar_one()
        referencia = database.session.execute(select(PaymentReference)).scalar_one()
        assert referencia.payment_id == payment_id
        assert referencia.reference_id == invoice_id
        assert referencia.allocated_amount == Decimal("25")
        relacion = database.session.execute(
            select(DocumentRelation).filter_by(
                target_type="payment_entry",
                target_id=payment_id,
                target_item_id=referencia.id,
                source_type="sales_invoice",
                source_id=invoice_id,
                status="active",
            )
        ).scalar_one()
        assert relacion.company == "cacao"
        assert database.session.execute(select(Reconciliation).filter_by(id=reconciliacion.id)).scalar_one() is not None
        invoice = database.session.get(SalesInvoice, invoice_id)
        payment = database.session.get(PaymentEntry, payment_id)
        assert invoice is not None and invoice.outstanding_amount == Decimal("75")
        assert payment is not None and compute_payment_unallocated_amount(payment) == Decimal("75")
