# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2111: el snapshot de ventas registra cambios de update_inventory."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import AuditTrail, Party, SalesInvoice, SalesInvoiceItem, database

FECHA = date(2026, 5, 15)


def test_edicion_registra_cambio_de_update_inventory(app, entorno_contable, authenticated_client):
    """Activar el inventario deja evidencia antes/después en la bitácora."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        factura = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no=f"FI-INV-{suffix}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            update_inventory=False,
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
                rate=Decimal("10"),
                amount=Decimal("10"),
            )
        )
        database.session.commit()
        factura_id = factura.id
        cliente_id = cliente.id

    respuesta = authenticated_client().post(
        f"/sales/sales-invoice/{factura_id}/edit",
        data={
            "company": "cacao",
            "posting_date": FECHA.isoformat(),
            "customer_id": cliente_id,
            "update_inventory": "on",
            "item_code_0": "ART01",
            "item_name_0": "Articulo Comercial",
            "qty_0": "1",
            "rate_0": "10",
            "uom_0": "UND",
        },
    )
    assert respuesta.status_code == 302

    with app.app_context():
        auditoria = database.session.execute(
            database.select(AuditTrail)
            .filter_by(document_type="sales_invoice", document_id=factura_id, action="updated")
            .order_by(AuditTrail.timestamp.desc(), AuditTrail.id.desc())
            .limit(1)
        ).scalar_one()
        cambios = json.loads(auditoria.changes_json)
        assert cambios["update_inventory"]["before"] is False
        assert cambios["update_inventory"]["after"] is True
