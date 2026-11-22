# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1405: el endpoint de flujo documental crea pagos con origen solo por línea.

El pago destino no declara ``source_document_type`` en la cabecera; la
autorización se resuelve por cada factura de ``lines``. La regresión cubre el
POST HTTP real, la persistencia del pago y la denegación sin permiso de caja.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.database import (
    DocumentRelation,
    Party,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    database,
)
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

FECHA = date(2026, 5, 15)


def _factura_cliente() -> SalesInvoice:
    """Crea una factura de venta aprobada con saldo abierto."""
    with database.session.no_autoflush:
        customer_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
    invoice = SalesInvoice(
        company="cacao",
        posting_date=FECHA,
        docstatus=1,
        document_no="FAC-PAGO-1405",
        customer_id=customer_id,
        customer_name="Cliente Principal SA",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        grand_total=Decimal("100"),
        total=Decimal("100"),
        outstanding_amount=Decimal("100"),
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _payload(invoice_id: str, customer_id: str) -> dict:
    """Payload de pago destino sin origen en la cabecera."""
    return {
        "target_document_type": "payment_entry",
        "company": "cacao",
        "posting_date": FECHA.isoformat(),
        "payment_type": "receive",
        "party_type": "customer",
        "party_id": customer_id,
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


def test_create_target_persiste_pago_con_origen_por_linea(app, entorno_contable, authenticated_client):
    """Un usuario con permiso de caja crea el pago desde la factura de la línea."""
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["payment_entry"])
        invoice = _factura_cliente()
        invoice_id = invoice.id
        customer_id = invoice.customer_id
        database.session.commit()

    client = authenticated_client("admin")
    response = client.post("/api/document-flow/create-target", json=_payload(invoice_id, customer_id))

    assert response.status_code == 201, response.get_data(as_text=True)
    payment_id = response.get_json()["target_id"]
    with app.app_context():
        payment = database.session.get(PaymentEntry, payment_id)
        reference = database.session.execute(database.select(PaymentReference).filter_by(payment_id=payment_id)).scalar_one()
        relation = database.session.execute(
            database.select(DocumentRelation).filter_by(
                source_id=invoice_id,
                target_id=payment_id,
            )
        ).scalar_one_or_none()
        assert payment is not None
        assert payment.company == "cacao"
        assert payment.party_id == customer_id
        assert reference.reference_id == invoice_id
        assert reference.allocated_amount == Decimal("40")
        assert relation is not None


def test_create_target_rechaza_pago_sin_permiso_de_caja(app, entorno_contable, authenticated_client):
    """Sin permiso de crear en caja el endpoint no persiste el pago."""
    with app.app_context():
        ensure_default_naming_series_for_company("cacao", ["payment_entry"])
        invoice = _factura_cliente()
        invoice_id = invoice.id
        customer_id = invoice.customer_id
        database.session.commit()
        payments_before = database.session.execute(database.select(PaymentEntry.id)).scalars().all()

    client = authenticated_client("other_company")
    response = client.post("/api/document-flow/create-target", json=_payload(invoice_id, customer_id))

    assert response.status_code == 403
    with app.app_context():
        payments_after = database.session.execute(database.select(PaymentEntry.id)).scalars().all()
        assert payments_after == payments_before
