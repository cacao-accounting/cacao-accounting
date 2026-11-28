# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2115: el detalle de venta muestra el tipo documental real."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Party, SalesInvoice, database

FECHA = date(2026, 5, 15)


@pytest.mark.parametrize(
    ("document_type", "label"),
    [
        ("sales_invoice", "Factura de Venta"),
        ("sales_credit_note", "Nota de Crédito de Venta"),
        ("sales_debit_note", "Nota de Débito de Venta"),
        ("sales_return", "Devolución de Venta"),
    ],
)
def test_detalle_muestra_la_etiqueta_del_tipo(app, entorno_contable, authenticated_client, document_type, label):
    """Cada tipo de SalesInvoice usa su título localizado, no siempre «Factura»."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"TIPO-{document_type}-{suffix}",
            document_type=document_type,
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("10"),
        )
        database.session.add(factura)
        database.session.commit()
        factura_id = factura.id

    response = authenticated_client().get(f"/sales/sales-invoice/{factura_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert label in html
