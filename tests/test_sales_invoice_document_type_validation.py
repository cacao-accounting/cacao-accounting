# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Regresión #1225: ventas rechaza subtipos de factura desconocidos."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import SalesInvoice, database
from cacao_accounting.document_flow.validation import (
    SALES_INVOICE_DOCUMENT_TYPES,
    validate_sales_invoice_document_type,
    validate_submit_prerequisites,
)


@pytest.mark.parametrize("document_type", sorted(SALES_INVOICE_DOCUMENT_TYPES))
def test_acepta_subtipos_registrados_en_ventas(document_type):
    """El allowlist conserva factura, notas de crédito/débito y devolución."""
    validate_sales_invoice_document_type(document_type)


def test_post_de_creacion_rechaza_subtipo_desconocido_sin_persistir(entorno_contable, authenticated_client):
    """Un POST inválido se rechaza antes de insertar el encabezado."""
    app = entorno_contable.app
    marker = f"TIPO-INVALIDO-{uuid4().hex}"
    response = authenticated_client().post(
        "/sales/sales-invoice/new",
        data={"document_type": "unknown_type", "remarks": marker},
    )

    assert response.status_code == 302
    with app.app_context():
        documents = database.session.execute(select(SalesInvoice.id).where(SalesInvoice.remarks == marker)).all()
    assert documents == []


def test_aprobacion_rechaza_subtipo_desconocido_persistido(entorno_contable, authenticated_client):
    """Un borrador legado con subtipo desconocido no pasa la validación pre-submit."""
    app = entorno_contable.app
    with app.app_context():
        invoice = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_type="unknown_type",
        )
        database.session.add(invoice)
        database.session.commit()
        invoice_id = invoice.id

        with pytest.raises(ValueError, match="tipo de documento de venta no es válido"):
            validate_submit_prerequisites(invoice, items=[])

    response = authenticated_client().post(f"/sales/sales-invoice/{invoice_id}/submit")
    assert response.status_code == 302
    with app.app_context():
        persisted = database.session.get(SalesInvoice, invoice_id)
        assert persisted is not None
        assert persisted.docstatus == 0
