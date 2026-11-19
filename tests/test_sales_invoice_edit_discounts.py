# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2112: la edición de factura carga los descuentos de línea."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Party, SalesInvoice, SalesInvoiceItem, database

FECHA = date(2026, 5, 15)


def test_edicion_incluye_descuento_porcentual_y_monto(app, entorno_contable, authenticated_client):
    """La línea inicial conserva descuento y neto antes de recalcular."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no=f"DESC-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(factura)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=factura.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
                discount_percentage=Decimal("10"),
                discount_amount=Decimal("10"),
                amount=Decimal("90"),
            )
        )
        database.session.commit()
        factura_id = factura.id

    response = authenticated_client().get(f"/sales/sales-invoice/{factura_id}/edit")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '"discount_percentage": "10' in html
    assert '"discount_amount": "10' in html
