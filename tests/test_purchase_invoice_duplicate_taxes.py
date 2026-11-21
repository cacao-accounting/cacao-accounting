# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2099: duplicar factura de compra recalcula el bruto con impuestos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.compras import routes as compras_routes
from cacao_accounting.database import Party, PurchaseInvoice, PurchaseInvoiceItem, database

FECHA = date(2026, 5, 15)


def test_duplicado_recalcula_el_total_fiscal(app, entorno_contable, authenticated_client, monkeypatch):
    """El borrador duplicado no conserva el subtotal como grand_total."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        proveedor = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        origen = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PI-DUP-{suffix}",
            document_type="purchase_invoice",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=f"PI-DUP-{suffix}",
            grand_total=Decimal("115"),
        )
        database.session.add(origen)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=origen.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
                amount=Decimal("100"),
            )
        )
        database.session.commit()
        origen_id = origen.id

    monkeypatch.setattr(
        compras_routes,
        "calculate_document_total_with_taxes",
        lambda _document, subtotal, _items: subtotal * Decimal("1.15"),
    )
    respuesta = authenticated_client().post(f"/buying/purchase-invoice/{origen_id}/duplicate")

    assert respuesta.status_code == 302
    with app.app_context():
        copia = database.session.execute(
            database.select(PurchaseInvoice).filter_by(remarks=f"PI-DUP-{suffix}", docstatus=0)
        ).scalar_one()
        assert copia.total == Decimal("100")
        assert copia.grand_total == Decimal("115.00")
        assert copia.outstanding_amount == Decimal("115.00")
