# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2098: la aprobación de recepción bloquea la orden de compra."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.compras import services as compras_services
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
    original = compras_services.lock_document_flow_document

    def tracking(document_type: str, document_id: str) -> None:
        llamadas.append((document_type, document_id))
        original(document_type, document_id)

    monkeypatch.setattr(compras_services, "lock_document_flow_document", tracking)
    respuesta = authenticated_client().post(f"/buying/purchase-receipt/{recepcion_id}/submit")

    assert respuesta.status_code == 302
    assert ("purchase_order", orden_id) in llamadas


def test_validacion_final_de_aprobacion_bloquea_la_orden(app, monkeypatch):
    """El camino de aprobación también serializa contra la orden de compra."""
    from types import SimpleNamespace

    from cacao_accounting.approval_engine import ApprovalEngine

    llamadas: list[tuple[str, str]] = []
    monkeypatch.setattr(
        compras_services,
        "lock_document_flow_document",
        lambda document_type, document_id: llamadas.append((document_type, document_id)),
    )
    monkeypatch.setattr(compras_services, "_validate_receipt_quantities_against_po", lambda _id: None)
    monkeypatch.setattr("cacao_accounting.document_flow.validation.validate_submit_prerequisites", lambda *_a, **_k: None)
    monkeypatch.setattr("cacao_accounting.document_flow.validate_currency_contract", lambda *_a, **_k: None)
    import importlib

    inventario_service = importlib.import_module("cacao_accounting.inventario.service")
    monkeypatch.setattr(inventario_service, "validate_batch_serial_draft", lambda *_a, **_k: None)
    documento = SimpleNamespace(id="REC-APROBACION", purchase_order_id="PO-APROBACION", is_return=False)

    with app.app_context():
        ApprovalEngine._validate_final_submission("purchase_receipt", documento)

    assert ("purchase_order", "PO-APROBACION") in llamadas
