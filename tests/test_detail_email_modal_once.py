# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2201: el detalle de documento renderiza una sola vez el modal de correo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import SalesInvoice, SalesInvoiceItem, database


def test_detalle_de_factura_no_duplica_el_modal_de_correo(app, entorno_contable, authenticated_client, monkeypatch):
    """Las acciones inline y el menú comparten botones, pero el modal es único."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        invoice = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"INV-EMAIL-{suffix}",
            document_type="sales_invoice",
            customer_name="Cliente correo",
            transaction_currency="NIO",
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.add(
            SalesInvoiceItem(
                sales_invoice_id=invoice.id,
                item_code="ART01",
                item_name="Artículo",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("50"),
                amount=Decimal("50"),
            )
        )
        database.session.commit()
        invoice_id = invoice.id

    monkeypatch.setitem(app.jinja_env.globals, "can_send_transaction_emails", lambda: True)
    app.jinja_env.cache.clear()

    response = authenticated_client().get(f"/sales/sales-invoice/{invoice_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count('id="emailNotificationModal"') == 1
    assert html.count('id="emailNotificationModalLabel"') == 1
    assert 'data-action-source=".ca-detail-actions-inline"' in html
