"""Pruebas de cierre de solicitudes de compra con comparativos y órdenes directas.

Cubre el issue #731: una solicitud mixta (líneas por comparativo y líneas por
asignación directa sin comparativo) debe poder cerrarse dejando motivo por línea
en la bitácora de auditoría.
"""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.audit_trail_service import format_document_timeline, get_document_timeline, log_create
from cacao_accounting.compras.purchase_request_comparison_service import (
    purchase_request_comparison_is_closed,
    purchase_request_direct_order_item_ids,
    purchase_request_is_ready_to_close,
    purchase_request_line_closure_reasons,
)
from cacao_accounting.database import (
    AuditTrail,
    DocumentRelation,
    Entity,
    Modules,
    PurchaseOrder,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonLine,
    PurchaseRequestItem,
    SupplierQuotation,
    User,
    database,
)


@pytest.fixture()
def app_ctx():
    """Provide an isolated application database."""
    app = create_app({**configuracion, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        database.create_all()
        database.session.add(Modules(module="purchases", default=True, enabled=True))
        database.session.flush()
        yield app
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def http_app():
    """Create an isolated application with an administrator for HTTP tests."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "purchase-request-close-key",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Modules(module="purchases", default=True, enabled=True))
        database.session.add(
            User(
                id="USER-CLOSE-ADMIN",
                user="close-admin",
                password=proteger_passwd("close-password"),
                active=True,
                classification="admin",
            )
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def _seed_mixed_request() -> PurchaseRequest:
    """Seed one request: line 1 by finalized comparison, line 2 by direct order."""
    entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
    request = PurchaseRequest(
        id="PREQ-MIXED-01",
        document_no="cacao-PREQ-MIXED-01",
        company="cacao",
        posting_date=date(2026, 8, 15),
        docstatus=1,
    )
    compared_item = PurchaseRequestItem(
        id="PREQI-MIXED-1",
        purchase_request_id=request.id,
        item_code="ITEM-A",
        item_name="Producto A",
        qty=Decimal("5"),
        uom="UND",
    )
    direct_item = PurchaseRequestItem(
        id="PREQI-MIXED-2",
        purchase_request_id=request.id,
        item_code="ITEM-B",
        item_name="Producto B",
        qty=Decimal("3"),
        uom="UND",
    )
    comparison = PurchaseRequestComparison(
        id="PRC-MIXED-01",
        document_no="cacao-CMP-MIXED-01",
        company="cacao",
        purchase_request_id=request.id,
        status="finalized",
    )
    offer = SupplierQuotation(id="SQ-MIXED-1", document_no="cacao-SPQ-MIXED-01", company="cacao", docstatus=1)
    order = PurchaseOrder(
        id="PO-MIXED-01",
        document_no="cacao-OC-MIXED-01",
        company="cacao",
        supplier_name="Proveedor Directo",
        posting_date=date(2026, 8, 16),
        docstatus=1,
    )
    database.session.add_all([entity, request, compared_item, direct_item, comparison, offer, order])
    database.session.flush()
    database.session.add_all(
        [
            PurchaseRequestComparisonLine(
                comparison_id=comparison.id,
                purchase_request_item_id=compared_item.id,
                selected_supplier_quotation_id=offer.id,
            ),
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                source_item_id=direct_item.id,
                target_type="purchase_order",
                target_id=order.id,
                qty=Decimal("3"),
                relation_type="order",
                status="active",
            ),
        ]
    )
    database.session.commit()
    return request


def test_mixed_request_ready_to_close_with_comparison_and_direct_order(app_ctx):
    """A mixed request closes even though comparisons do not cover every line."""
    with app_ctx.app_context():
        request = _seed_mixed_request()

        assert not purchase_request_comparison_is_closed(request)
        assert purchase_request_is_ready_to_close(request)

        reasons = purchase_request_line_closure_reasons(request)
        assert set(reasons) == {"PREQI-MIXED-1", "PREQI-MIXED-2"}
        assert "cacao-CMP-MIXED-01" in reasons["PREQI-MIXED-1"]
        assert "cacao-OC-MIXED-01" in reasons["PREQI-MIXED-2"]
        assert "sin comparativo" in reasons["PREQI-MIXED-2"]


def test_direct_order_coverage_requires_active_relation_to_approved_order(app_ctx):
    """Draft or reverted orders do not close a request line."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        request = PurchaseRequest(id="PREQ-DIRECT-01", company="cacao", docstatus=1)
        item = PurchaseRequestItem(
            id="PREQI-DIRECT-1", purchase_request_id=request.id, item_code="ITEM-C", qty=Decimal("1"), uom="UND"
        )
        order = PurchaseOrder(id="PO-DIRECT-01", company="cacao", docstatus=0)
        database.session.add_all([entity, request, item, order])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                source_item_id=item.id,
                target_type="purchase_order",
                target_id=order.id,
                qty=Decimal("1"),
                relation_type="order",
                status="active",
            )
        )
        database.session.commit()

        assert not purchase_request_direct_order_item_ids(request)
        assert not purchase_request_is_ready_to_close(request)

        order.docstatus = 1
        database.session.commit()
        assert purchase_request_direct_order_item_ids(request) == {"PREQI-DIRECT-1"}
        assert purchase_request_is_ready_to_close(request)

        order.docstatus = 2
        relation = database.session.query(DocumentRelation).one()
        relation.status = "reverted"
        database.session.commit()
        assert not purchase_request_direct_order_item_ids(request)
        assert not purchase_request_is_ready_to_close(request)


def test_mixed_purchase_request_closes_over_http_with_per_line_audit(http_app):
    """Closing a mixed request registers the closure reason of every line."""
    with http_app.app_context():
        request = _seed_mixed_request()

        with http_app.test_client() as client:
            login = client.post("/login", data={"usuario": "close-admin", "acceso": "close-password"})
            assert login.status_code in {302, 303}

            detail = client.get(f"/buying/purchase-request/{request.id}")
            assert detail.status_code == 200
            assert b"Cerrar" in detail.data

            closed = client.post(f"/buying/purchase-request/{request.id}/close")
            assert closed.status_code in {302, 303}
            database.session.expire_all()
            assert database.session.get(PurchaseRequest, request.id).status == "closed"

            closure_entries = (
                database.session.query(AuditTrail)
                .filter_by(document_type="purchase_request", document_id=request.id, action="closed")
                .all()
            )
            assert len(closure_entries) == 2
            comments = " | ".join(entry.comment or "" for entry in closure_entries)
            assert "ITEM-A" in comments and "cacao-CMP-MIXED-01" in comments
            assert "ITEM-B" in comments and "cacao-OC-MIXED-01" in comments

            timeline_comments = [
                event["event"].comment
                for event in format_document_timeline("purchase_request", request.id)
                if event["event"].action == "closed"
            ]
            assert len(timeline_comments) == 2


def test_unclosable_purchase_request_rejects_close_over_http(http_app):
    """A request with an uncovered line cannot be closed from the route."""
    with http_app.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        request = PurchaseRequest(id="PREQ-OPEN-01", document_no="cacao-PREQ-OPEN-01", company="cacao", docstatus=1)
        item = PurchaseRequestItem(
            id="PREQI-OPEN-1", purchase_request_id=request.id, item_code="ITEM-D", qty=Decimal("1"), uom="UND"
        )
        database.session.add_all([entity, request, item])
        database.session.commit()

        with http_app.test_client() as client:
            login = client.post("/login", data={"usuario": "close-admin", "acceso": "close-password"})
            assert login.status_code in {302, 303}

            rejected = client.post(f"/buying/purchase-request/{request.id}/close", follow_redirects=True)
            assert rejected.status_code == 200
            assert "órdenes de compra activas".encode() in rejected.data
            database.session.expire_all()
            assert database.session.get(PurchaseRequest, request.id).status == "open"


def test_audit_trail_stores_snake_case_document_type(app_ctx):
    """DocBase documents are audited under their snake_case document type."""
    with app_ctx.app_context():
        request = PurchaseRequest(id="PREQ-AUDIT-01", company="cacao", docstatus=1)
        database.session.add(request)
        database.session.flush()
        log_create(request)
        database.session.commit()

        assert len(get_document_timeline("purchase_request", request.id)) == 1
