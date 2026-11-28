# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

"""#1461: la fecha de pago destino se normaliza antes de persistir."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Party, PaymentEntry, SalesInvoice, database
from cacao_accounting.document_flow.service import create_target_document


def test_create_target_document_payment_accepts_iso_posting_date(entorno_contable):
    with entorno_contable.app.app_context():
        customer_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
        invoice = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"V-ISO-{uuid4().hex[:8]}",
            document_type="sales_invoice",
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
        database.session.commit()

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": "2026-05-16",
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer_id,
                "currency": "NIO",
                "base_currency": "NIO",
                "exchange_rate": "1",
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": invoice.id,
                        "allocated_amount": "100",
                    }
                ],
            },
            commit=True,
        )

        payment = database.session.get(PaymentEntry, result["target_id"])
        assert payment is not None
        assert str(payment.posting_date) == "2026-05-16"
