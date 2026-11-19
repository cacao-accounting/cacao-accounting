# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2113: la cancelación toma el lock documental antes de revisar hijas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import SalesRequest, User, database
from cacao_accounting.ventas import routes as ventas_routes


def test_cancelacion_bloquea_el_documento_antes_de_revisar_relaciones(
    app, entorno_contable, authenticated_client, monkeypatch
):
    """El lock compartido serializa la cancelación con nuevas relaciones."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        pedido = SalesRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SR-LOCK-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(pedido)
        database.session.commit()
        request_id = pedido.id

    llamadas: list[tuple[str, str]] = []
    original = ventas_routes.lock_document_flow_document

    def tracking(document_type: str, document_id: str) -> None:
        llamadas.append((document_type, document_id))
        original(document_type, document_id)

    monkeypatch.setattr(ventas_routes, "lock_document_flow_document", tracking)
    respuesta = authenticated_client().post(f"/sales/sales-request/{request_id}/cancel")

    assert respuesta.status_code == 302
    assert ("sales_request", request_id) in llamadas


def test_aprobacion_de_cancelacion_bloquea_antes_de_validar(app, entorno_contable, monkeypatch):
    """La vía de aprobación adquiere el lock antes de revisar hijas."""
    from types import SimpleNamespace

    from cacao_accounting.approval_engine import ApprovalEngine
    from cacao_accounting.database import SalesOrder

    suffix = uuid4().hex[:8]
    with app.app_context():
        orden = SalesOrder(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SO-APR-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(orden)
        database.session.commit()
        orden_id = orden.id
        usuario_id = database.session.execute(database.select(User.id).filter_by(user="admin")).scalar_one()
        usuario = SimpleNamespace(id=str(usuario_id), name="Admin")

    orden_llamadas: list[str] = []
    monkeypatch.setattr(
        "cacao_accounting.document_flow.lock_document_flow_document",
        lambda *_args, **_kwargs: orden_llamadas.append("lock"),
    )
    monkeypatch.setattr(
        ApprovalEngine,
        "_validate_final_cancellation",
        staticmethod(lambda *_args, **_kwargs: orden_llamadas.append("validate")),
    )
    monkeypatch.setattr(
        ApprovalEngine,
        "_execute_cancel",
        staticmethod(lambda *_args, **_kwargs: orden_llamadas.append("execute")),
    )

    solicitud = SimpleNamespace(
        document_type="cancel_sales_order",
        document_id=orden_id,
        cancellation_reason="Prueba",
        cancellation_date=date(2026, 5, 15),
        created_at=None,
    )
    with app.app_context(), app.test_request_context("/"):
        orden_actual = database.session.get(SalesOrder, orden_id)
        ApprovalEngine._finalize_approval(solicitud, orden_actual, usuario)

    assert orden_llamadas == ["lock", "validate", "execute"]
