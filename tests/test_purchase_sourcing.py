"""Pruebas unitarias para comparación y adjudicación de ofertas."""

# pylint: disable=redefined-outer-name

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Entity,
    DocumentRelation,
    Item,
    Modules,
    Party,
    PurchaseQuotation,
    PurchaseQuotationAwardItem,
    PurchaseQuotationItem,
    PurchaseNegotiationRound,
    PurchaseOrder,
    PurchaseOrderComparison,
    PurchaseOrderComparisonOrder,
    PurchaseOrderComparisonRound,
    PurchaseOrderComparisonRoundOrder,
    PurchaseRequest,
    Roles,
    RolesUser,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    User,
    database,
)
from cacao_accounting.compras.purchase_sourcing_service import (
    PurchaseSourcingError,
    create_purchase_quotation_award,
    get_purchase_sourcing_config,
    open_negotiation_round,
    set_purchase_sourcing_config,
    submitted_supplier_quotations,
)
from cacao_accounting.compras.purchase_order_comparison_service import (
    comparable_purchase_orders,
    create_purchase_order_comparison,
    current_purchase_order_comparison_round,
    open_purchase_order_comparison_round,
    purchase_orders_for_request,
    purchase_order_comparison_round_orders,
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


def _seed_rfq(offer_count: int = 1):
    """Create an RFQ with one line and submitted supplier offers."""
    entity = Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="T-1", currency="NIO")
    uom = UOM(code="UND", name="Unidad")
    item = Item(code="ITEM-01", name="Producto", item_type="goods", is_stock_item=True, default_uom="UND")
    rfq = PurchaseQuotation(id="RFQ-01", company="cacao", posting_date=date(2026, 1, 1), docstatus=1)
    rfq_item = PurchaseQuotationItem(
        id="RFQI-01",
        purchase_quotation_id=rfq.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("10"),
        uom=uom.code,
        rate=Decimal("0"),
        amount=Decimal("0"),
    )
    database.session.add_all([entity, uom, item, rfq, rfq_item])
    offers = []
    for index in range(offer_count):
        party = Party(code=f"SUP-{index}", name=f"Proveedor {index}", is_supplier=True)
        offer = SupplierQuotation(
            id=f"SQ-{index}",
            company="cacao",
            supplier_id=party.id,
            supplier_name=party.name,
            purchase_quotation_id=rfq.id,
            posting_date=date(2026, 1, 2),
            docstatus=1,
        )
        line = SupplierQuotationItem(
            id=f"SQI-{index}",
            supplier_quotation_id=offer.id,
            item_code=item.code,
            item_name=item.name,
            qty=Decimal("10"),
            uom=uom.code,
            rate=Decimal(str(10 + index)),
            amount=Decimal(str((10 + index) * 10)),
        )
        database.session.add_all([party, offer, line])
        offers.append(offer)
    database.session.flush()
    return rfq, rfq_item, offers


def _manager() -> User:
    """Create a user assigned to the exact manager role."""
    user = User(user="manager", name="Manager", classification="user", password=b"test")
    role = Roles(name="Purchase Manager", note="Gerente de Compras")
    database.session.add_all([user, role])
    database.session.flush()
    database.session.add(RolesUser(user_id=user.id, role_id=role.id, active=True))
    database.session.flush()
    return user


def test_sourcing_config_defaults_to_two_offers_and_is_global(app_ctx):
    """The global sourcing policy defaults safely and can be changed by admin."""
    with app_ctx.app_context():
        assert get_purchase_sourcing_config().minimum_offers == 2
        assert not get_purchase_sourcing_config().require_comparison
        set_purchase_sourcing_config(True, 4)
        database.session.commit()
        config = get_purchase_sourcing_config()
        assert config.require_comparison
        assert config.minimum_offers == 4


def test_single_offer_requires_manager_authorization_and_reason(app_ctx):
    """A single offer is accepted only with manager authorization and evidence."""
    with app_ctx.app_context():
        rfq, item, _ = _seed_rfq()
        manager = _manager()
        set_purchase_sourcing_config(True, 2)
        database.session.commit()

        with pytest.raises(PurchaseSourcingError, match="al menos 2"):
            create_purchase_quotation_award(rfq, {item.id: "SQ-0"}, None)
        with pytest.raises(PurchaseSourcingError, match="justificación"):
            create_purchase_quotation_award(rfq, {item.id: "SQ-0"}, manager.id)

        award = create_purchase_quotation_award(rfq, {item.id: "SQ-0"}, manager.id, "Proveedor único disponible")
        assert award.status == "finalized"
        assert award.authorized_by == manager.id
        assert award.authorization_reason == "Proveedor único disponible"


def test_partial_coverage_can_be_awarded_by_line(app_ctx):
    """Uncovered RFQ lines may remain open while covered lines are awarded."""
    with app_ctx.app_context():
        rfq, item, offers = _seed_rfq(offer_count=2)
        second = PurchaseQuotationItem(
            id="RFQI-02",
            purchase_quotation_id=rfq.id,
            item_code="ITEM-01",
            item_name="Producto",
            qty=Decimal("5"),
            uom="UND",
            rate=Decimal("0"),
            amount=Decimal("0"),
        )
        database.session.add(second)
        database.session.flush()
        award = create_purchase_quotation_award(rfq, {item.id: offers[0].id}, None)
        assert award.id is not None
        awarded_lines = database.session.query(PurchaseQuotationAwardItem).filter_by(award_id=award.id).all()
        assert len(awarded_lines) == 1
        assert awarded_lines[0].item_code == "ITEM-01"


def test_non_recommended_offer_requires_manager_override(app_ctx):
    """Selecting a higher offer requires the manager's documented override."""
    with app_ctx.app_context():
        rfq, item, offers = _seed_rfq(offer_count=2)
        manager = _manager()
        with pytest.raises(PurchaseSourcingError, match="no recomendada"):
            create_purchase_quotation_award(rfq, {item.id: offers[1].id}, None)
        award = create_purchase_quotation_award(rfq, {item.id: offers[1].id}, manager.id, "Proveedor ofrece mejor plazo")
        assert award.authorization_reason == "Proveedor ofrece mejor plazo"
        line = database.session.query(PurchaseQuotationAwardItem).filter_by(award_id=award.id).one()
        assert line.manual_override is True
        assert line.override_reason == "Proveedor ofrece mejor plazo"
        assert award.authorized_by == manager.id


def test_duplicate_rfq_items_match_distinct_supplier_lines(app_ctx):
    """Repeated item codes use the corresponding supplier quotation line."""
    with app_ctx.app_context():
        rfq, item, offers = _seed_rfq(offer_count=2)
        second_rfq_item = PurchaseQuotationItem(
            id="RFQI-02",
            purchase_quotation_id=rfq.id,
            item_code=item.item_code,
            item_name=item.item_name,
            qty=Decimal("5"),
            uom="UND",
            rate=Decimal("0"),
            amount=Decimal("0"),
        )
        database.session.add(second_rfq_item)
        for index, offer in enumerate(offers):
            database.session.add(
                SupplierQuotationItem(
                    id=f"SQI-{index}-02",
                    supplier_quotation_id=offer.id,
                    item_code=item.item_code,
                    item_name=item.item_name,
                    qty=Decimal("5"),
                    uom="UND",
                    rate=Decimal(str(20 + index)),
                    amount=Decimal(str((20 + index) * 5)),
                )
            )
        database.session.flush()
        award = create_purchase_quotation_award(rfq, {"RFQI-01": offers[0].id, "RFQI-02": offers[0].id}, None)
        lines = (
            database.session.query(PurchaseQuotationAwardItem)
            .filter_by(award_id=award.id)
            .order_by(PurchaseQuotationAwardItem.purchase_quotation_item_id)
            .all()
        )
        assert [line.supplier_quotation_item_id for line in lines] == ["SQI-0", "SQI-0-02"]


def test_negotiation_rounds_replace_active_offer_set(app_ctx):
    """Only offers submitted in the active negotiation round are comparable."""
    with app_ctx.app_context():
        rfq, _, offers = _seed_rfq(offer_count=2)
        first_round = open_negotiation_round(rfq.id, None)
        database.session.commit()
        assert first_round.round_number == 1
        assert not submitted_supplier_quotations(rfq.id)

        new_offer = SupplierQuotation(
            id="SQ-NEW",
            company="cacao",
            supplier_name="Proveedor nuevo",
            purchase_quotation_id=rfq.id,
            negotiation_round_id=first_round.id,
            posting_date=date(2026, 1, 3),
            docstatus=1,
        )
        database.session.add(new_offer)
        database.session.flush()
        assert submitted_supplier_quotations(rfq.id) == [new_offer]

        second_round = open_negotiation_round(rfq.id, None)
        database.session.commit()
        assert first_round.status == "closed"
        assert second_round.round_number == 2
        assert not submitted_supplier_quotations(rfq.id)
        assert offers[0].negotiation_round_id is None
        assert database.session.query(PurchaseNegotiationRound).count() == 2


def test_purchase_order_comparison_uses_selected_purchase_orders(app_ctx):
    """A comparison persists a base order and only the selected related orders."""
    with app_ctx.app_context():
        purchase_request = PurchaseRequest(
            id="PREQ-COMP-01",
            company="cacao",
            posting_date=date(2026, 1, 1),
            docstatus=1,
        )
        base = PurchaseOrder(
            id="PO-COMP-BASE",
            company="cacao",
            supplier_name="Proveedor base",
            posting_date=date(2026, 1, 1),
            docstatus=1,
        )
        offer = PurchaseOrder(
            id="PO-COMP-OFFER",
            company="cacao",
            supplier_name="Proveedor oferta",
            posting_date=date(2026, 1, 2),
            docstatus=1,
        )
        unrelated = PurchaseOrder(
            id="PO-COMP-OTHER",
            company="cacao",
            supplier_name="Proveedor no relacionado",
            posting_date=date(2026, 1, 3),
            docstatus=1,
        )
        database.session.add_all([purchase_request, base, offer, unrelated])
        database.session.flush()
        database.session.add_all(
            [
                DocumentRelation(
                    source_type="purchase_request",
                    source_id=purchase_request.id,
                    target_type="purchase_order",
                    target_id=base.id,
                    qty=Decimal("1"),
                    relation_type="fulfillment",
                    status="active",
                ),
                DocumentRelation(
                    source_type="purchase_request",
                    source_id=purchase_request.id,
                    target_type="purchase_order",
                    target_id=offer.id,
                    qty=Decimal("1"),
                    relation_type="fulfillment",
                    status="active",
                ),
            ]
        )
        database.session.flush()

        assert purchase_orders_for_request(purchase_request) == [base, offer]
        assert comparable_purchase_orders(base) == [base, offer]
        comparison = create_purchase_order_comparison(purchase_request, base, [offer.id], "USER-COMP")
        database.session.commit()

        stored_comparison = database.session.get(PurchaseOrderComparison, comparison.id)
        assert stored_comparison.base_purchase_order_id == base.id
        assert stored_comparison.purchase_request_id == purchase_request.id
        participants = database.session.query(PurchaseOrderComparisonOrder).filter_by(comparison_id=comparison.id).all()
        assert {row.purchase_order_id for row in participants} == {base.id, offer.id}
        assert {row.is_base for row in participants} == {True, False}

        first_round = current_purchase_order_comparison_round(comparison.id)
        assert first_round is not None
        assert first_round.round_number == 1
        assert {row.purchase_order_id for row in purchase_order_comparison_round_orders(first_round.id)} == {
            base.id,
            offer.id,
        }

        second_round = open_purchase_order_comparison_round(comparison, purchase_request, [offer.id], "USER-COMP")
        database.session.commit()

        assert first_round.status == "closed"
        assert second_round.round_number == 2
        assert current_purchase_order_comparison_round(comparison.id).id == second_round.id
        assert {row.purchase_order_id for row in purchase_order_comparison_round_orders(second_round.id)} == {
            base.id,
            offer.id,
        }
        assert database.session.query(PurchaseOrderComparisonRound).count() == 2
        assert database.session.query(PurchaseOrderComparisonRoundOrder).count() == 4

        with pytest.raises(ValueError, match="mismo origen"):
            open_purchase_order_comparison_round(comparison, purchase_request, ["PO-COMP-OTHER"], "USER-COMP")
