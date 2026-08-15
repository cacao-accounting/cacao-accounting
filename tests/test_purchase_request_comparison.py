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
    PurchaseRequestItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Party,
    SupplierQuotation,
    SupplierQuotationItem,
    Item,
    UOM,
    database,
)
from cacao_accounting.compras import _validate_supplier_quotation_header
from cacao_accounting.compras.purchase_request_comparison_service import (
    comparison_recommendations,
    create_purchase_orders_from_comparison,
    create_purchase_request_comparison,
    finalize_purchase_request_comparison,
    save_purchase_request_comparison_draft,
    supplier_quotation_comparison_rows,
    supplier_quotations_for_comparison,
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
        assert stored.document_no.startswith("cacao-CMP-")
        assert stored.naming_series_id is not None
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


def test_comparison_rows_identity_ignores_quoted_quantity(app_ctx):
    """Quantity is coverage, not identity: same item aligns across offers."""
    with app_ctx.app_context():
        first = SupplierQuotation(id="SQ-ROWS-3", company="cacao", docstatus=1)
        second = SupplierQuotation(id="SQ-ROWS-4", company="cacao", docstatus=1)
        first_item = SupplierQuotationItem(
            id="SQI-ROWS-4",
            supplier_quotation_id=first.id,
            item_code="ITEM-A",
            uom="UND",
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            rate=Decimal("10"),
        )
        second_item = SupplierQuotationItem(
            id="SQI-ROWS-5",
            supplier_quotation_id=second.id,
            item_code="ITEM-A",
            uom="UND",
            qty=Decimal("20"),
            qty_in_base_uom=Decimal("20"),
            rate=Decimal("11"),
        )

        rows = supplier_quotation_comparison_rows(
            [first, second],
            {first.id: [first_item], second.id: [second_item]},
        )

        assert len(rows) == 1
        assert rows[0]["offers"][first.id] is first_item
        assert rows[0]["offers"][second.id] is second_item


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


def test_comparison_excludes_cancelled_or_cross_company_offers(app_ctx):
    """Cancelled and cross-company offers are not current comparison participants."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        other_entity = Entity(code="other", name="Other", company_name="Other", tax_id="T-2", currency="NIO")
        request = PurchaseRequest(id="REQ-STATE", company="cacao", docstatus=1)
        comparison = PurchaseRequestComparison(id="PRC-STATE-01", company="cacao", purchase_request_id=request.id)
        current = SupplierQuotation(id="SQ-STATE-1", company="cacao", docstatus=1)
        cancelled = SupplierQuotation(id="SQ-STATE-2", company="cacao", docstatus=2)
        cross_company = SupplierQuotation(id="SQ-STATE-3", company="other", docstatus=1)
        database.session.add_all([entity, other_entity, request, comparison, current, cancelled, cross_company])
        database.session.flush()
        database.session.add_all(
            [
                PurchaseRequestComparisonOffer(comparison_id=comparison.id, supplier_quotation_id=current.id),
                PurchaseRequestComparisonOffer(comparison_id=comparison.id, supplier_quotation_id=cancelled.id),
                PurchaseRequestComparisonOffer(comparison_id=comparison.id, supplier_quotation_id=cross_company.id),
            ]
        )
        database.session.commit()

        assert supplier_quotations_for_comparison(comparison.id) == [current]


def test_comparison_recommends_by_line_and_groups_purchase_orders(app_ctx):
    """The comparison selects the lowest price per line and groups orders by supplier."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        uom = UOM(code="UND", name="Unidad")
        item_one = Item(code="ITEM-COMP-1", name="Producto 1", item_type="goods", is_stock_item=True, default_uom="UND")
        item_two = Item(code="ITEM-COMP-2", name="Producto 2", item_type="goods", is_stock_item=True, default_uom="UND")
        supplier = Party(id="PARTY-AWARD-1", code="SUP-AWARD-1", name="Proveedor Uno", is_supplier=True)
        request = PurchaseRequest(id="PREQ-AWARD", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        request_item_one = PurchaseRequestItem(
            id="PREQI-AWARD-1",
            purchase_request_id=request.id,
            item_code=item_one.code,
            item_name=item_one.name,
            qty=Decimal("10"),
            uom="UND",
        )
        request_item_two = PurchaseRequestItem(
            id="PREQI-AWARD-2",
            purchase_request_id=request.id,
            item_code=item_two.code,
            item_name=item_two.name,
            qty=Decimal("5"),
            uom="UND",
        )
        offer_one = SupplierQuotation(
            id="SQ-AWARD-1", company="cacao", supplier_id=supplier.id, supplier_name=supplier.name, docstatus=1
        )
        offer_two = SupplierQuotation(
            id="SQ-AWARD-2", company="cacao", supplier_id=supplier.id, supplier_name=supplier.name, docstatus=1
        )
        lines = [
            SupplierQuotationItem(
                id="SQAI-1",
                supplier_quotation_id=offer_one.id,
                item_code=item_one.code,
                qty=10,
                uom="UND",
                rate=10,
                amount=100,
            ),
            SupplierQuotationItem(
                id="SQAI-2", supplier_quotation_id=offer_one.id, item_code=item_two.code, qty=5, uom="UND", rate=20, amount=100
            ),
            SupplierQuotationItem(
                id="SQAI-3",
                supplier_quotation_id=offer_two.id,
                item_code=item_one.code,
                qty=10,
                uom="UND",
                rate=12,
                amount=120,
            ),
            SupplierQuotationItem(
                id="SQAI-4", supplier_quotation_id=offer_two.id, item_code=item_two.code, qty=5, uom="UND", rate=15, amount=75
            ),
        ]
        database.session.add_all(
            [
                entity,
                uom,
                item_one,
                item_two,
                supplier,
                request,
                request_item_one,
                request_item_two,
                offer_one,
                offer_two,
                *lines,
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                DocumentRelation(
                    source_type="purchase_request",
                    source_id=request.id,
                    target_type="supplier_quotation",
                    target_id=offer_one.id,
                    qty=15,
                    relation_type="quotation",
                    status="active",
                ),
                DocumentRelation(
                    source_type="purchase_request",
                    source_id=request.id,
                    target_type="supplier_quotation",
                    target_id=offer_two.id,
                    qty=15,
                    relation_type="quotation",
                    status="active",
                ),
            ]
        )
        database.session.flush()

        comparison = create_purchase_request_comparison(request, [offer_one.id, offer_two.id], "USER-COMP")
        rows = comparison_recommendations(comparison)
        assert [row["recommended"]["offer"].id for row in rows] == [offer_one.id, offer_two.id]

        save_purchase_request_comparison_draft(
            comparison,
            {request_item_one.id: offer_one.id, request_item_two.id: offer_one.id},
            {request_item_two.id: "Preferencia comercial"},
            "USER-COMP",
        )
        assert comparison.status == "pending_authorization"
        with pytest.raises(ValueError, match="Gerente"):
            finalize_purchase_request_comparison(comparison, "USER-COMP", False)

        finalize_purchase_request_comparison(comparison, "MANAGER", True)
        assert comparison.status == "finalized"
        orders = create_purchase_orders_from_comparison(comparison)
        assert len(orders) == 1
        assert orders[0].supplier_name == "Proveedor Uno"
        assert database.session.query(PurchaseOrderItem).filter_by(purchase_order_id=orders[0].id).count() == 2
        assert database.session.query(PurchaseOrder).filter_by(purchase_request_comparison_id=comparison.id).count() == 1


def test_comparison_matches_request_lines_by_commercial_identity_not_occurrence(app_ctx):
    """Same item in different UOM are distinct lines and do not cross-match by position."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        uom = UOM(code="UND", name="Unidad")
        item = Item(code="ITEM-MULTIUOM", name="Producto multi UOM", item_type="goods", is_stock_item=True, default_uom="UND")
        supplier = Party(id="PARTY-MULTIUOM-1", code="SUP-MULTIUOM-1", name="Proveedor Multi UOM", is_supplier=True)
        request = PurchaseRequest(id="PREQ-MULTIUOM", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        request_line_und = PurchaseRequestItem(
            id="PREQI-MULTIUOM-UND",
            purchase_request_id=request.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
            warehouse="WH-A",
        )
        request_line_caja = PurchaseRequestItem(
            id="PREQI-MULTIUOM-CAJA",
            purchase_request_id=request.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("2"),
            uom="CAJA",
            qty_in_base_uom=Decimal("20"),
            warehouse="WH-A",
        )
        offer = SupplierQuotation(
            id="SQ-MULTIUOM", company="cacao", supplier_id=supplier.id, supplier_name=supplier.name, docstatus=1
        )
        lines = [
            SupplierQuotationItem(
                id="SQAI-MULTIUOM-UND",
                supplier_quotation_id=offer.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("10"),
                uom="UND",
                qty_in_base_uom=Decimal("10"),
                warehouse="WH-A",
                rate=Decimal("10"),
                amount=Decimal("100"),
            ),
            SupplierQuotationItem(
                id="SQAI-MULTIUOM-CAJA",
                supplier_quotation_id=offer.id,
                item_code=item.code,
                item_name=item.name,
                qty=Decimal("2"),
                uom="CAJA",
                qty_in_base_uom=Decimal("20"),
                warehouse="WH-A",
                rate=Decimal("5"),
                amount=Decimal("10"),
            ),
        ]
        database.session.add_all([entity, uom, item, supplier, request, request_line_und, request_line_caja, offer, *lines])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                target_type="supplier_quotation",
                target_id=offer.id,
                qty=Decimal("12"),
                relation_type="quotation",
                status="active",
            )
        )
        database.session.flush()

        comparison = create_purchase_request_comparison(request, [offer.id], "USER-COMP")
        rows = comparison_recommendations(comparison)
        by_item = {row["item"].id: row for row in rows}
        assert by_item[request_line_und.id]["recommended"]["line"].id == "SQAI-MULTIUOM-UND"
        assert by_item[request_line_caja.id]["recommended"]["line"].id == "SQAI-MULTIUOM-CAJA"


def test_comparison_coverage_compares_base_uom_quantities(app_ctx):
    """An offer must cover the request quantity after UOM conversion."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        uom = UOM(code="UND", name="Unidad")
        item = Item(code="ITEM-COVER", name="Producto cobertura", item_type="goods", is_stock_item=True, default_uom="UND")
        supplier = Party(id="PARTY-COVER-1", code="SUP-COVER-1", name="Proveedor Cobertura", is_supplier=True)
        request = PurchaseRequest(id="PREQ-COVER", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        request_item = PurchaseRequestItem(
            id="PREQI-COVER-1",
            purchase_request_id=request.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("1"),
            uom="UND",
            qty_in_base_uom=Decimal("12"),
        )
        offer = SupplierQuotation(
            id="SQ-COVER", company="cacao", supplier_id=supplier.id, supplier_name=supplier.name, docstatus=1
        )
        short_line = SupplierQuotationItem(
            id="SQAI-COVER-SHORT",
            supplier_quotation_id=offer.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
            rate=Decimal("10"),
            amount=Decimal("50"),
        )
        covering_line = SupplierQuotationItem(
            id="SQAI-COVER-OK",
            supplier_quotation_id=offer.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("20"),
            uom="UND",
            qty_in_base_uom=Decimal("20"),
            rate=Decimal("8"),
            amount=Decimal("160"),
        )
        database.session.add_all([entity, uom, item, supplier, request, request_item, offer, short_line, covering_line])
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
        database.session.flush()

        comparison = create_purchase_request_comparison(request, [offer.id], "USER-COMP")
        rows = comparison_recommendations(comparison)
        assert rows[0]["recommended"]["line"].id == "SQAI-COVER-OK"


def test_comparison_orders_apply_exchange_rate_to_base_total(app_ctx):
    """Orders derived from a comparison compute base totals with the transaction exchange rate."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        uom = UOM(code="UND", name="Unidad")
        item = Item(code="ITEM-TC", name="Producto tipo de cambio", item_type="goods", is_stock_item=True, default_uom="UND")
        supplier = Party(id="PARTY-TC-1", code="SUP-TC-1", name="Proveedor TC", is_supplier=True)
        request = PurchaseRequest(id="PREQ-TC", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        request_item = PurchaseRequestItem(
            id="PREQI-TC-1",
            purchase_request_id=request.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
        )
        offer = SupplierQuotation(
            id="SQ-TC",
            company="cacao",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            transaction_currency="USD",
            docstatus=1,
        )
        offer_item = SupplierQuotationItem(
            id="SQAI-TC-1",
            supplier_quotation_id=offer.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
            rate=Decimal("2"),
            amount=Decimal("20"),
        )
        from cacao_accounting.database import ExchangeRate

        database.session.add_all(
            [
                entity,
                uom,
                item,
                supplier,
                request,
                request_item,
                offer,
                offer_item,
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36"), date=date(2026, 8, 15)),
            ]
        )
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                target_type="supplier_quotation",
                target_id=offer.id,
                qty=Decimal("10"),
                relation_type="quotation",
                status="active",
            )
        )
        database.session.flush()

        comparison = create_purchase_request_comparison(request, [offer.id], "USER-COMP")
        save_purchase_request_comparison_draft(comparison, {request_item.id: offer.id}, {}, "USER-COMP")
        finalize_purchase_request_comparison(comparison, "MANAGER", True)
        orders = create_purchase_orders_from_comparison(comparison)
        assert orders[0].transaction_currency == "USD"
        assert orders[0].base_currency == "NIO"
        assert orders[0].exchange_rate == Decimal("36")
        assert orders[0].base_total == Decimal("720")


def test_comparison_rejects_cancelled_offer_when_placing_orders(app_ctx):
    """A quotation cancelled after finalization must not be turned into an order."""
    with app_ctx.app_context():
        entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
        uom = UOM(code="UND", name="Unidad")
        item = Item(code="ITEM-CANCEL", name="Producto cancelado", item_type="goods", is_stock_item=True, default_uom="UND")
        supplier = Party(id="PARTY-CANCEL-1", code="SUP-CANCEL-1", name="Proveedor Cancelado", is_supplier=True)
        request = PurchaseRequest(id="PREQ-CANCEL", company="cacao", posting_date=date(2026, 8, 15), docstatus=1)
        request_item = PurchaseRequestItem(
            id="PREQI-CANCEL-1",
            purchase_request_id=request.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
        )
        offer = SupplierQuotation(
            id="SQ-CANCEL", company="cacao", supplier_id=supplier.id, supplier_name=supplier.name, docstatus=1
        )
        offer_item = SupplierQuotationItem(
            id="SQAI-CANCEL-1",
            supplier_quotation_id=offer.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
            rate=Decimal("2"),
            amount=Decimal("20"),
        )
        database.session.add_all([entity, uom, item, supplier, request, request_item, offer, offer_item])
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=request.id,
                target_type="supplier_quotation",
                target_id=offer.id,
                qty=Decimal("10"),
                relation_type="quotation",
                status="active",
            )
        )
        database.session.flush()

        comparison = create_purchase_request_comparison(request, [offer.id], "USER-COMP")
        save_purchase_request_comparison_draft(comparison, {request_item.id: offer.id}, {}, "USER-COMP")
        finalize_purchase_request_comparison(comparison, "MANAGER", True)
        offer.docstatus = 2
        database.session.flush()
        with pytest.raises(ValueError, match="aprobada"):
            create_purchase_orders_from_comparison(comparison)
