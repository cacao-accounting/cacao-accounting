# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2141.4: el listado expone todas las comparativas de una solicitud."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
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


def test_crear_comparativo_con_quoting_invalido_no_produce_500(app, entorno_contable, authenticated_client):
    """#2141.5: un ValueError de creación se muestra como flash, no como 500."""
    from cacao_accounting.compras import routes as compras_routes

    suffix = uuid4().hex[:6]
    with app.app_context():
        from cacao_accounting.database import DocumentRelation

        request = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-VAL-{suffix}",
            requested_by="admin",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SC-VAL-{suffix}",
            supplier_name=f"Proveedor Val {suffix}",
            transaction_currency="NIO",
        )
        database.session.add_all([request, quotation])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                target_type="supplier_quotation",
                target_id=quotation.id,
                company="cacao",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                relation_type="quotation",
                status="active",
            )
        )
        database.session.commit()
        request_id = request.id
        quotation_id = quotation.id

    def _boom(*_args, **_kwargs):
        raise ValueError("Cotización no válida para el comparativo")

    monkeypatch_target = compras_routes.create_purchase_request_comparison
    compras_routes.create_purchase_request_comparison = _boom
    try:
        response = authenticated_client().post(
            f"/buying/request-for-quotation/comparison/purchase-request/{request_id}",
            data={"supplier_quotation_ids": quotation_id},
        )
    finally:
        compras_routes.create_purchase_request_comparison = monkeypatch_target

    assert response.status_code in (200, 302)
    if response.status_code == 200:
        assert "Cotización no válida" in response.get_data(as_text=True)
    with app.app_context():
        from cacao_accounting.database import PurchaseRequestComparison

        assert (
            database.session.execute(
                database.select(PurchaseRequestComparison).filter_by(purchase_request_id=request_id)
            ).scalar_one_or_none()
            is None
        )


def test_listado_muestra_total_con_moneda(app, entorno_contable, authenticated_client):
    """#2141.6: el listado muestra el total con su moneda, no un número crudo."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        request = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-MON-{suffix}",
            requested_by="admin",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            transaction_currency="NIO",
            grand_total=Decimal("1250"),
        )
        database.session.add(request)
        database.session.commit()

    body = authenticated_client().get("/buying/request-for-quotation/comparison").get_data(as_text=True)

    assert f"REQ-MON-{suffix}" in body
    assert "NIO 1,250.00" in body


def test_ordenes_canceladas_no_aparecen_como_candidatas(app, entorno_contable, authenticated_client):
    """#2141.7: una cotización cancelada no se ofrece como participante."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        from cacao_accounting.database import DocumentRelation

        request = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-CAN-{suffix}",
            requested_by="admin",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=2,
            document_no=f"SC-CAN-{suffix}",
            supplier_name=f"Proveedor Cancelado {suffix}",
            transaction_currency="NIO",
        )
        database.session.add_all([request, quotation])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                target_type="supplier_quotation",
                target_id=quotation.id,
                company="cacao",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                relation_type="quotation",
                status="active",
            )
        )
        database.session.commit()
        request_id = request.id

    body = (
        authenticated_client()
        .get(f"/buying/request-for-quotation/comparison/purchase-request/{request_id}")
        .get_data(as_text=True)
    )
    assert f"Proveedor Cancelado {suffix}" not in body
