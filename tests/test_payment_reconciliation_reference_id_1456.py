# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Jose Moreno Reyes

"""#1456: la conciliacion acepta reference_id del esquema de importacion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.api.line_import import (
    LineImportSchemaRegistry,
    _validate_import_row,
    _validate_payment_reconciliation_row,
)
from cacao_accounting.database import Party, PaymentEntry, SalesInvoice, database


def _escenario(app) -> dict:
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(code=f"REF-{suffix}", name="Cliente ref", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SI-{suffix}",
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
            payment_type="receive",
            posting_date=date(2026, 5, 15),
            paid_amount=Decimal("100"),
            received_amount=Decimal("100"),
            currency="NIO",
            party_type="customer",
            party_id=cliente.id,
            docstatus=1,
            document_no=f"PE-{suffix}",
        )
        database.session.add_all([factura, pago])
        database.session.commit()
        return {"payment": pago.id, "reference": factura.id, "party": cliente.id}


def test_payment_reconciliation_import_accepts_reference_id(entorno_contable_aislado):
    ids = _escenario(entorno_contable_aislado.app)
    row = {
        "payment_id": ids["payment"],
        "reference_type": "sales_invoice",
        "reference_id": ids["reference"],
        "allocated_amount": "100",
    }
    errors: list[dict] = []
    with entorno_contable_aislado.app.app_context():
        _validate_payment_reconciliation_row(row, 1, "cacao", errors, party_type="customer", party_id=ids["party"])

    assert errors == []


def test_import_row_accepts_reference_id_without_materialized_open_item(entorno_contable_aislado):
    """La ruta real de importación no exige un ARAPOpenItem previo."""
    app = entorno_contable_aislado.app
    ids = _escenario(app)
    row = {
        "payment_id": ids["payment"],
        "reference_type": "sales_invoice",
        "reference_id": ids["reference"],
        "allocated_amount": "100",
    }
    schema = LineImportSchemaRegistry.get_schema("payment_reconciliation")
    assert schema is not None

    with app.app_context():
        errors, validated = _validate_import_row(
            row=row,
            row_no=1,
            schema=schema,
            doctype="payment_reconciliation",
            company_id="cacao",
            party_type="customer",
            party_id=ids["party"],
            allocation_date=date(2026, 5, 15),
        )

    assert errors == []
    assert validated["payment_id"] == ids["payment"]
    assert validated["reference_type"] == "sales_invoice"
    assert validated["reference_id"] == ids["reference"]
