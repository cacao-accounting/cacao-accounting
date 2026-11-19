# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2094: la creación de órdenes bloquea el comparativo."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.compras import purchase_request_comparison_service as comparison_service
from cacao_accounting.database import PurchaseRequest, PurchaseRequestComparison, database


def test_crear_ordenes_bloquea_el_comparativo(app, entorno_contable, monkeypatch):
    """Dos solicitudes no pueden pasar el estado y crear órdenes duplicadas."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        request = PurchaseRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"PR-{suffix}",
        )
        database.session.add(request)
        database.session.flush()
        comparison = PurchaseRequestComparison(
            company="cacao",
            status="draft",
            purchase_request_id=request.id,
        )
        database.session.add(comparison)
        database.session.commit()
        comparison_id = comparison.id
        comparison_obj = comparison

    llamadas: list[tuple[str, str]] = []
    original = comparison_service.lock_document_flow_document

    def tracking(document_type: str, document_id: str) -> None:
        llamadas.append((document_type, document_id))
        original(document_type, document_id)

    monkeypatch.setattr(comparison_service, "lock_document_flow_document", tracking)
    with app.app_context():
        with pytest.raises(ValueError):
            comparison_service.create_purchase_orders_from_comparison(comparison_obj)

    assert ("purchase_request_comparison", comparison_id) in llamadas
