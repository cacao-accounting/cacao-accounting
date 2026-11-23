# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1822: editar una factura de compra refresca su moneda base."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    CompanyParty,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    database,
)


@pytest.fixture
def factura_con_base_obsoleta(app, entorno_contable):
    """Factura borrador cuya base monetaria quedó desalineada de la compañía."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        configuracion = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if configuracion is None:
            configuracion = PurchaseMatchingConfig(
                company="cacao",
                matching_type="2-way",
                require_purchase_order=False,
                bridge_account_required=False,
                auto_reconcile=False,
            )
            database.session.add(configuracion)
        else:
            configuracion.require_purchase_order = False
        proveedor = Party(
            code=f"PRV-BASE-{sufijo}",
            name=f"Proveedor base {sufijo}",
            is_supplier=True,
        )
        database.session.add(proveedor)
        database.session.flush()
        database.session.add(
            CompanyParty(
                company="cacao",
                party_id=proveedor.id,
                is_active=True,
                allow_purchase_invoice_without_order=True,
                allow_purchase_invoice_without_receipt=True,
            )
        )
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"FI-BASE-{sufijo}",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            document_type="purchase_invoice",
            transaction_currency="NIO",
            base_currency="USD",
            exchange_rate=Decimal("1"),
        )
        database.session.add(factura)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=factura.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("2"),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal("20"),
            )
        )
        database.session.commit()
        ids = {
            "factura": factura.id,
            "proveedor": proveedor.id,
            "sufijo": sufijo,
        }
    yield ids


def test_editar_factura_refresca_base_currency_desde_la_compania(app, authenticated_client, factura_con_base_obsoleta):
    """Un snapshot de base monetaria obsoleto no sobrevive a la edición."""
    ids = factura_con_base_obsoleta
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        f"/buying/purchase-invoice/{ids['factura']}/edit",
        data={
            "supplier_id": ids["proveedor"],
            "company": "cacao",
            "posting_date": "2026-05-15",
            "transaction_currency": "NIO",
            "supplier_invoice_no": f"FAC-{ids['sufijo']}",
            "item_code_0": "ART01",
            "item_name_0": "Articulo Comercial",
            "qty_0": "2",
            "uom_0": "UND",
            "rate_0": "10",
            "amount_0": "20",
        },
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    with app.app_context():
        factura = database.session.get(PurchaseInvoice, ids["factura"])
        assert factura.base_currency == "NIO"
        assert factura.exchange_rate == Decimal("1")
        assert factura.base_grand_total == factura.grand_total
