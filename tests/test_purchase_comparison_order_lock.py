# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2094: la creación de órdenes bloquea el comparativo."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.compras import purchase_request_comparison_service as comparison_service
from cacao_accounting.database import Currency, Entity, PurchaseRequest, PurchaseRequestComparison, database


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


def test_la_instancia_obsoleta_no_omite_la_revalidacion(tmp_path):
    """Tras el lock se relee el estado, no la foto previa del llamador."""
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'comparison-lock.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    suffix = uuid4().hex[:8]
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J-CACAO",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        request = PurchaseRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"PR-STALE-{suffix}",
        )
        database.session.add(request)
        database.session.flush()
        comparison = PurchaseRequestComparison(
            company="cacao",
            status="finalized",
            purchase_request_id=request.id,
        )
        database.session.add(comparison)
        database.session.commit()
        comparison_id = comparison.id
        database.session.expunge(comparison)
        database.session.rollback()
        with database.engine.begin() as connection:
            connection.execute(
                database.text("UPDATE purchase_request_comparison SET status = 'used' WHERE id = :id"),
                {"id": comparison_id},
            )

        with pytest.raises(ValueError, match="finalizado"):
            comparison_service.create_purchase_orders_from_comparison(comparison)
        database.session.remove()
        database.engine.dispose()
