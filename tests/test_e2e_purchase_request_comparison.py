"""Prueba end-to-end del flujo de comparativo de ofertas por solicitud de compra."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    DocumentRelation,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonLine,
    PurchaseRequestItem,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    User,
    database,
)


@pytest.fixture()
def e2e_app():
    """Create an isolated application with an administrator for HTTP tests."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "comparison-e2e-key",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Modules(module="purchases", default=True, enabled=True))
        database.session.add(
            User(
                id="USER-E2E-ADMIN",
                user="e2e-admin",
                password=proteger_passwd("e2e-password"),
                active=True,
                classification="admin",
            )
        )
        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def _seed_request_with_multiple_rfqs() -> tuple[PurchaseRequest, list[SupplierQuotation]]:
    """Create one request, two RFQs, two supplier offers, and three request lines."""
    entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="E2E-TAX", currency="NIO")
    uom = UOM(code="UND", name="Unidad")
    items = [
        Item(code=f"E2E-ITEM-{index}", name=f"Producto E2E {index}", item_type="goods", is_stock_item=True, default_uom="UND")
        for index in range(1, 4)
    ]
    request_record = PurchaseRequest(
        id="PREQ-E2E-001",
        document_no="cacao-PREQ-E2E-001",
        company="cacao",
        posting_date=date(2026, 8, 15),
        docstatus=1,
    )
    request_items = [
        PurchaseRequestItem(
            id=f"PREQI-E2E-{index}",
            purchase_request_id=request_record.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal(str(index)),
            uom="UND",
        )
        for index, item in enumerate(items, start=1)
    ]
    rfqs = [
        PurchaseQuotation(
            id=f"RFQ-E2E-{index}",
            document_no=f"cacao-RFQ-E2E-0000{index}",
            company="cacao",
            posting_date=date(2026, 8, 15),
            docstatus=1,
        )
        for index in range(1, 3)
    ]
    parties = [
        Party(id=f"PARTY-E2E-{index}", code=f"SUP-E2E-{index}", name=f"Proveedor E2E {index}", is_supplier=True)
        for index in range(1, 3)
    ]
    offers = [
        SupplierQuotation(
            id=f"SQ-E2E-{index}",
            document_no=f"cacao-SPQ-E2E-0000{index}",
            company="cacao",
            supplier_id=parties[index - 1].id,
            supplier_name=parties[index - 1].name,
            purchase_quotation_id=rfqs[index - 1].id,
            posting_date=date(2026, 8, 15),
            docstatus=1,
        )
        for index in range(1, 3)
    ]
    rates = ([Decimal("10"), Decimal("20"), Decimal("30")], [Decimal("12"), Decimal("15"), Decimal("25")])
    offer_items = [
        SupplierQuotationItem(
            id=f"SQI-E2E-{offer_index}-{line_index}",
            supplier_quotation_id=offer.id,
            item_code=item.code,
            item_name=item.name,
            qty=request_item.qty,
            uom="UND",
            rate=rates[offer_index - 1][line_index - 1],
            amount=request_item.qty * rates[offer_index - 1][line_index - 1],
        )
        for offer_index, offer in enumerate(offers, start=1)
        for line_index, (item, request_item) in enumerate(zip(items, request_items), start=1)
    ]
    database.session.add_all([entity, uom, *items, request_record, *request_items, *rfqs, *parties, *offers, *offer_items])
    database.session.flush()
    database.session.add_all(
        [
            DocumentRelation(
                source_type="purchase_request",
                source_id=request_record.id,
                target_type="purchase_quotation",
                target_id=rfq.id,
                qty=Decimal("1"),
                relation_type="quotation",
                status="active",
            )
            for rfq in rfqs
        ]
        + [
            DocumentRelation(
                source_type="purchase_quotation",
                source_id=offer.purchase_quotation_id,
                target_type="supplier_quotation",
                target_id=offer.id,
                qty=Decimal("1"),
                relation_type="quotation",
                status="active",
            )
            for offer in offers
        ]
    )
    database.session.commit()
    return request_record, offers


def test_purchase_request_to_placed_purchase_orders_over_http(e2e_app):
    """Exercise the complete request, comparison, authorization, and order flow."""
    with e2e_app.app_context():
        request_record, offers = _seed_request_with_multiple_rfqs()
        request_items = list(
            database.session.execute(
                database.select(PurchaseRequestItem)
                .where(PurchaseRequestItem.purchase_request_id == request_record.id)
                .order_by(PurchaseRequestItem.id)
            )
            .scalars()
            .all()
        )

        with e2e_app.test_client() as client:
            login = client.post("/login", data={"usuario": "e2e-admin", "acceso": "e2e-password"})
            assert login.status_code in {302, 303}

            listing = client.get("/buying/request-for-quotation/comparison")
            assert listing.status_code == 200
            assert request_record.document_no.encode() in listing.data
            assert b"Nueva comparativa" in listing.data

            selection = client.get(f"/buying/request-for-quotation/comparison/purchase-request/{request_record.id}")
            assert selection.status_code == 200
            assert offers[0].document_no.encode() in selection.data
            assert offers[1].document_no.encode() in selection.data

            created = client.post(
                f"/buying/request-for-quotation/comparison/purchase-request/{request_record.id}",
                data={"supplier_quotation_ids": [offer.id for offer in offers]},
            )
            assert created.status_code in {302, 303}
            comparison = database.session.execute(
                database.select(PurchaseRequestComparison).filter_by(purchase_request_id=request_record.id)
            ).scalar_one()

            detail = client.get(f"/buying/request-for-quotation/comparison/{comparison.id}")
            assert detail.status_code == 200
            assert b"Recomendado" in detail.data
            assert b"Guardar borrador" in detail.data
            assert b"Autorizar y finalizar" in detail.data

            draft = client.post(
                f"/buying/request-for-quotation/comparison/{comparison.id}/draft",
                data={
                    f"selection_{request_items[0].id}": offers[0].id,
                    f"selection_{request_items[1].id}": offers[0].id,
                    f"selection_{request_items[2].id}": offers[1].id,
                    f"override_reason_{request_items[1].id}": "Condición comercial preferida",
                },
            )
            assert draft.status_code in {302, 303}
            database.session.expire_all()
            comparison = database.session.get(PurchaseRequestComparison, comparison.id)
            assert comparison.status == "pending_authorization"
            saved_lines = (
                database.session.execute(
                    database.select(PurchaseRequestComparisonLine)
                    .where(PurchaseRequestComparisonLine.comparison_id == comparison.id)
                    .order_by(PurchaseRequestComparisonLine.id)
                )
                .scalars()
                .all()
            )
            assert len(saved_lines) == 3
            assert saved_lines[1].manual_override is True
            assert saved_lines[1].override_reason == "Condición comercial preferida"

            finalized = client.post(
                f"/buying/request-for-quotation/comparison/{comparison.id}/finalize",
                data={
                    f"selection_{request_items[0].id}": offers[0].id,
                    f"selection_{request_items[1].id}": offers[0].id,
                    f"selection_{request_items[2].id}": offers[1].id,
                    f"override_reason_{request_items[1].id}": "Condición comercial preferida",
                },
            )
            assert finalized.status_code in {302, 303}
            database.session.expire_all()
            comparison = database.session.get(PurchaseRequestComparison, comparison.id)
            assert comparison.status == "finalized"
            assert comparison.authorized_by == "USER-E2E-ADMIN"
            authorized_lines = (
                database.session.execute(
                    database.select(PurchaseRequestComparisonLine).where(
                        PurchaseRequestComparisonLine.comparison_id == comparison.id
                    )
                )
                .scalars()
                .all()
            )
            assert all(line.authorized_by == "USER-E2E-ADMIN" for line in authorized_lines)

            placed = client.post(f"/buying/request-for-quotation/comparison/{comparison.id}/place-purchase-orders")
            assert placed.status_code in {302, 303}
            database.session.expire_all()
            comparison = database.session.get(PurchaseRequestComparison, comparison.id)
            assert comparison.status == "used"
            orders = (
                database.session.execute(
                    database.select(PurchaseOrder)
                    .where(PurchaseOrder.purchase_request_comparison_id == comparison.id)
                    .order_by(PurchaseOrder.supplier_id)
                )
                .scalars()
                .all()
            )
            assert len(orders) == 2
            assert {order.supplier_name for order in orders} == {"Proveedor E2E 1", "Proveedor E2E 2"}
            assert (
                sum(
                    database.session.query(PurchaseOrderItem).filter_by(purchase_order_id=order.id).count() for order in orders
                )
                == 3
            )
            assert all(order.docstatus == 0 and order.document_no for order in orders)
            relations = (
                database.session.execute(
                    database.select(DocumentRelation).where(
                        DocumentRelation.target_type == "purchase_order",
                        DocumentRelation.target_id.in_([order.id for order in orders]),
                    )
                )
                .scalars()
                .all()
            )
            assert {relation.source_type for relation in relations} == {"purchase_request", "supplier_quotation"}

            final_detail = client.get(f"/buying/request-for-quotation/comparison/{comparison.id}")
            assert final_detail.status_code == 200
            assert b"ya fueron generadas" in final_detail.data
