"""Pruebas del comparativo de cotizaciones desde solicitudes de compra."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    DocumentRelation,
    Entity,
    Modules,
    PurchaseQuotation,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    SupplierQuotation,
    database,
)
from cacao_accounting.compras.purchase_request_comparison_service import (
    create_purchase_request_comparison,
    supplier_quotations_for_request,
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


def test_comparison_collects_supplier_quotations_through_request_rfqs(app_ctx):
    """The request is the root and offers may come through different RFQs."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        request = PurchaseRequest(id="PREQ-COMP-01", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        rfq_one = PurchaseQuotation(id="RFQ-COMP-01", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        rfq_two = PurchaseQuotation(id="RFQ-COMP-02", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        offer_one = SupplierQuotation(
            id="SQ-COMP-01",
            company="cacao",
            supplier_name="Proveedor Uno",
            purchase_quotation_id=rfq_one.id,
            posting_date=date(2026, 8, 15),
            docstatus=1,
        )
        offer_two = SupplierQuotation(
            id="SQ-COMP-02",
            company="cacao",
            supplier_name="Proveedor Dos",
            posting_date=date(2026, 8, 15),
            docstatus=1,
        )
        database.session.add_all([entity, request, rfq_one, rfq_two, offer_one, offer_two])
        database.session.flush()
        database.session.add_all(
            [
                DocumentRelation(
                    source_type="purchase_request",
                    source_id=request.id,
                    target_type="purchase_quotation",
                    target_id=rfq_one.id,
                    qty=Decimal("1"),
                    relation_type="quotation",
                    status="active",
                ),
                DocumentRelation(
                    source_type="purchase_request",
                    source_id=request.id,
                    target_type="purchase_quotation",
                    target_id=rfq_two.id,
                    qty=Decimal("1"),
                    relation_type="quotation",
                    status="active",
                ),
                DocumentRelation(
                    source_type="purchase_quotation",
                    source_id=rfq_two.id,
                    target_type="supplier_quotation",
                    target_id=offer_two.id,
                    qty=Decimal("1"),
                    relation_type="quotation",
                    status="active",
                ),
            ]
        )
        database.session.flush()

        candidates = supplier_quotations_for_request(request)
        assert {offer.id for offer in candidates} == {offer_one.id, offer_two.id}

        comparison = create_purchase_request_comparison(request, [offer_one.id, offer_two.id], "USER-COMP")
        database.session.commit()

        stored = database.session.get(PurchaseRequestComparison, comparison.id)
        assert stored.purchase_request_id == request.id
        participants = database.session.query(PurchaseRequestComparisonOffer).filter_by(comparison_id=comparison.id).all()
        assert {participant.supplier_quotation_id for participant in participants} == {offer_one.id, offer_two.id}
