# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2073: la conciliación valida el subtipo real del documento."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.api.line_import import _get_payment_reconciliation_reference
from cacao_accounting.database import Party, SalesInvoice, database
from cacao_accounting.document_flow.payment import _get_reference_document
from cacao_accounting.document_flow.service import DocumentFlowError


def _factura(app) -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = Party(code=f"SUB-{suffix}", name="Cliente subtipo", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SUB-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("100"),
        )
        database.session.add(factura)
        database.session.commit()
        return str(factura.id), str(cliente.id)


def test_prevalidacion_rechaza_alias_de_nota_sobre_factura(app, entorno_contable):
    """Enviar sales_debit_note para una factura ordinaria falla en validación."""
    factura_id, _cliente_id = _factura(app)
    errors: list[dict] = []

    with app.app_context():
        reference, reference_type = _get_payment_reconciliation_reference(
            {"reference_type": "sales_debit_note", "reference_id": factura_id},
            "cacao",
            1,
            errors,
        )

    assert reference is None
    assert reference_type == "sales_debit_note"
    assert any("subtipo" in str(error.get("message", "")).lower() for error in errors)


def test_post_rechaza_alias_de_nota_sobre_factura(app, entorno_contable):
    """El servicio final aplica la misma regla de subtipo."""
    factura_id, cliente_id = _factura(app)

    with app.app_context(), pytest.raises(DocumentFlowError, match="subtipo"):
        _get_reference_document("sales_debit_note", factura_id, "cacao", "customer", cliente_id)
