# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2141.4: el listado expone todas las comparativas de una solicitud."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.database import (
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    SupplierQuotation,
    database,
)


def test_listado_muestra_todas_las_comparativas(app, entorno_contable, authenticated_client):
    """No se oculta una comparativa anterior de la misma solicitud."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        request = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-{suffix}",
            requested_by="admin",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        database.session.add(request)
        database.session.flush()
        first = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=request.id,
            document_no=f"CMP-A-{suffix}",
            posting_date=date(2026, 5, 15),
            status="finalized",
        )
        second = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=request.id,
            document_no=f"CMP-B-{suffix}",
            posting_date=date(2026, 5, 16),
            status="used",
        )
        database.session.add_all([first, second])
        database.session.commit()
        first_id, second_id = first.id, second.id

    response = authenticated_client().get("/buying/request-for-quotation/comparison")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert first_id in html
    assert second_id in html
    assert html.count("Ver comparativo") >= 2
    assert "NIO" in html


def test_detalle_renderiza_el_comparativo_de_solicitud(app, entorno_contable, authenticated_client):
    """La ruta de detalle conserva el flujo activo de comparación de solicitudes."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        request = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-DET-{suffix}",
            requested_by="admin",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        database.session.add(request)
        database.session.flush()
        comparison = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=request.id,
            document_no=f"CMP-DET-{suffix}",
            posting_date=date(2026, 5, 15),
            status="finalized",
        )
        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SC-DET-{suffix}",
            supplier_name=f"Proveedor Detalle {suffix}",
            transaction_currency="NIO",
        )
        database.session.add_all([comparison, quotation])
        database.session.flush()
        database.session.add(
            PurchaseRequestComparisonOffer(
                comparison_id=comparison.id,
                supplier_quotation_id=quotation.id,
            )
        )
        database.session.commit()
        comparison_id = comparison.id
        document_no = comparison.document_no

    response = authenticated_client().get(f"/buying/request-for-quotation/comparison/{comparison_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert document_no in body
    assert f"Proveedor Detalle {suffix}" in body


def test_listado_no_ofrece_filtro_de_estado_inoperante(app, entorno_contable, authenticated_client):
    """El comparativo de solicitudes no muestra un filtro de estado sin efecto (#2141)."""
    response = authenticated_client().get("/buying/request-for-quotation/comparison")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="list-status"' not in body
    assert 'name="status"' not in body
