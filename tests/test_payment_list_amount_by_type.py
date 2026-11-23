# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1949: el listado muestra el importe según el tipo de pago."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cacao_accounting.database import PaymentEntry, database


def test_cobro_muestra_received_amount(app, authenticated_client, entorno_contable):
    """Un cobro (receive) no muestra paid_amount en cero."""
    with app.app_context():
        database.session.add_all(
            [
                PaymentEntry(
                    company="cacao",
                    payment_type="receive",
                    posting_date=date(2026, 5, 15),
                    paid_amount=Decimal("0"),
                    received_amount=Decimal("321.00"),
                    transaction_currency="NIO",
                    party_name="Cliente cobro",
                    document_no="REC-1949",
                ),
                PaymentEntry(
                    company="cacao",
                    payment_type="pay",
                    posting_date=date(2026, 5, 15),
                    paid_amount=Decimal("654.00"),
                    received_amount=Decimal("0"),
                    transaction_currency="NIO",
                    party_name="Proveedor pago",
                    document_no="PAG-1949",
                ),
            ]
        )
        database.session.commit()

    html = authenticated_client("admin").get("/cash_management/payment/list").get_data(as_text=True)

    assert "321.00" in html
    assert "654.00" in html
