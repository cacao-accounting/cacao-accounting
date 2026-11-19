# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2098: la aprobación de recepción bloquea la orden de compra."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.compras import routes as compras_routes
from cacao_accounting.database import PurchaseOrder, PurchaseReceipt, database

FECHA = date(2026, 5, 15)


def test_submit_bloquea_la_orden_antes_de_validar_cantidades(app, entorno_contable, authenticated_client, monkeypatch):
    """Dos recepciones contra la misma OC se serializan por el lock documental."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        orden = PurchaseOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"PO-LOCK-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(orden)
        database.session.flush()
        recepcion = PurchaseReceipt(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no=f"PR-LOCK-{suffix}",
            purchase_order_id=orden.id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(recepcion)
        database.session.commit()
        orden_id = orden.id
        recepcion_id = recepcion.id

    llamadas: list[tuple[str, str]] = []
    original = compras_routes.lock_document_flow_document

    def tracking(document_type: str, document_id: str) -> None:
        llamadas.append((document_type, document_id))
        original(document_type, document_id)

    monkeypatch.setattr(compras_routes, "lock_document_flow_document", tracking)
    respuesta = authenticated_client().post(f"/buying/purchase-receipt/{recepcion_id}/submit")

    assert respuesta.status_code == 302
    assert ("purchase_order", orden_id) in llamadas
