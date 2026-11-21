# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2074: la preconciliación valida el tipo de pago."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.api.line_import import _validate_payment_reconciliation_row
from cacao_accounting.database import Party, PaymentEntry, SalesInvoice, database


def test_prevalidacion_rechaza_pago_pay_contra_factura_venta(app, entorno_contable):
    """Un pago `pay` no puede aplicarse a una cuenta por cobrar."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(code=f"TIPO-{suffix}", name="Cliente tipo", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"TIPO-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("100"),
            outstanding_amount=Decimal("100"),
        )
        pago = PaymentEntry(
            company="cacao",
            payment_type="pay",
            posting_date=date(2026, 5, 15),
            paid_amount=Decimal("10"),
            received_amount=Decimal("0"),
            currency="NIO",
            party_type="customer",
            party_id=cliente.id,
            docstatus=1,
            document_no=f"PAY-{suffix}",
        )
        database.session.add_all([factura, pago])
        database.session.commit()
        factura_id, pago_id, cliente_id = factura.id, pago.id, cliente.id

    errors: list[dict] = []
    _validate_payment_reconciliation_row(
        {
            "payment_id": pago_id,
            "reference_type": "sales_invoice",
            "reference_id": factura_id,
            "allocated_amount": "10",
        },
        1,
        "cacao",
        errors,
        party_type="customer",
        party_id=cliente_id,
    )

    assert any(
        error.get("field") == "payment_id"
        and error.get("message") == "El tipo de pago no coincide con el documento de referencia."
        for error in errors
    )
