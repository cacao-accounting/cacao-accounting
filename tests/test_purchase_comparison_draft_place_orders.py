# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1605: un comparativo en borrador responde con error controlado, no 500."""

from __future__ import annotations

from datetime import date

from cacao_accounting.database import PurchaseOrder, PurchaseRequest, PurchaseRequestComparison, database


def test_colocar_ordenes_desde_comparativo_en_borrador_no_falla(app, authenticated_client, entorno_contable):
    """El ValueError del servicio se traduce en redirect y rollback."""
    del entorno_contable
    with app.app_context():
        solicitud = PurchaseRequest(company="cacao", posting_date=date(2026, 5, 15), docstatus=1, status="open")
        database.session.add(solicitud)
        database.session.flush()
        comparativo = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=solicitud.id,
            posting_date=date(2026, 5, 15),
            status="draft",
        )
        database.session.add(comparativo)
        database.session.commit()
        comparativo_id = comparativo.id
        solicitud_id = solicitud.id

    try:
        response = authenticated_client("admin").post(
            f"/buying/request-for-quotation/comparison/{comparativo_id}/place-purchase-orders"
        )

        assert response.status_code == 302
        with app.app_context():
            assert (
                database.session.execute(
                    database.select(PurchaseOrder).filter_by(purchase_request_comparison_id=comparativo_id)
                ).scalar_one_or_none()
                is None
            )
    finally:
        with app.app_context():
            database.session.execute(
                database.delete(PurchaseRequestComparison).where(PurchaseRequestComparison.id == comparativo_id)
            )
            database.session.execute(database.delete(PurchaseRequest).where(PurchaseRequest.id == solicitud_id))
            database.session.commit()
