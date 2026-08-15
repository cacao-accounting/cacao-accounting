"""Pruebas del comparativo de cotizaciones desde solicitudes de compra."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.document_flow import DocumentFlowError
from cacao_accounting.database import (
    DocumentRelation,
    Entity,
    Modules,
    PurchaseQuotation,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)
from cacao_accounting.compras import _validate_supplier_quotation_header
from cacao_accounting.compras.purchase_request_comparison_service import (
    create_purchase_request_comparison,
    supplier_quotation_comparison_rows,
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


def test_comparison_collects_direct_supplier_quotation_from_request(app_ctx):
    """Direct request-to-offer relations are eligible comparison candidates."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        request = PurchaseRequest(id="PREQ-COMP-DIRECT", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        offer = SupplierQuotation(
            id="SQ-COMP-DIRECT",
            company="cacao",
            supplier_name="Proveedor Directo",
            posting_date=date(2026, 8, 15),
            docstatus=1,
        )
        database.session.add_all([entity, request, offer])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                target_type="supplier_quotation",
                target_id=offer.id,
                qty=Decimal("1"),
                relation_type="quotation",
                status="active",
            )
        )
        database.session.commit()

        assert supplier_quotations_for_request(request) == [offer]


def test_comparison_rows_include_lines_only_present_in_later_offer(app_ctx):
    """The comparison universe is the stable union of every offer's lines."""
    with app_ctx.app_context():
        first = SupplierQuotation(id="SQ-ROWS-1", company="cacao", docstatus=1)
        second = SupplierQuotation(id="SQ-ROWS-2", company="cacao", docstatus=1)
        first_item = SupplierQuotationItem(
            id="SQI-ROWS-1",
            supplier_quotation_id=first.id,
            item_code="ITEM-A",
            qty=Decimal("1"),
            rate=Decimal("10"),
        )
        second_first_item = SupplierQuotationItem(
            id="SQI-ROWS-2",
            supplier_quotation_id=second.id,
            item_code="ITEM-A",
            qty=Decimal("1"),
            rate=Decimal("11"),
        )
        second_only_item = SupplierQuotationItem(
            id="SQI-ROWS-3",
            supplier_quotation_id=second.id,
            item_code="ITEM-B",
            qty=Decimal("2"),
            rate=Decimal("20"),
        )

        rows = supplier_quotation_comparison_rows(
            [first, second],
            {
                first.id: [first_item],
                second.id: [second_first_item, second_only_item],
            },
        )

        assert [row["item"].item_code for row in rows] == ["ITEM-A", "ITEM-B"]
        assert rows[1]["offers"][first.id] is None
        assert rows[1]["offers"][second.id] is second_only_item


def test_supplier_quotation_origin_header_is_immutable(app_ctx, monkeypatch):
    """A supplier quotation cannot change the source RFQ company."""
    import sys

    compras = sys.modules["cacao_accounting.compras"]

    with app_ctx.app_context():
        source = PurchaseQuotation(
            id="RFQ-HEADER-01",
            company="cacao",
            posting_date=date(2026, 8, 15),
            docstatus=1,
        )
        database.session.add(source)
        database.session.commit()
        monkeypatch.setattr(compras, "_require_purchase_document_access", lambda *_args: None)

        with app_ctx.test_request_context(method="POST", data={"company": "other", "currency": "NIO"}):
            with pytest.raises(DocumentFlowError, match="compañía"):
                _validate_supplier_quotation_header(source)
