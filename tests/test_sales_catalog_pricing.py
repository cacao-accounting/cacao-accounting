"""Regression tests for customer-specific sales catalog pricing. Refs: #744."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    CompanyParty,
    Entity,
    Item,
    ItemPrice,
    Party,
    PriceList,
    Roles,
    RolesUser,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.setup.repository import create_default_price_lists
from cacao_accounting.ventas.services import (
    _save_sales_order_items,
    _save_sales_quotation_items,
    _source_line_rate,
    resolve_sales_catalog_price,
    validate_sales_quotation_expiry,
)


@pytest.fixture()
def app_ctx():
    """Create an isolated sales catalog with the standard master data."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        from cacao_accounting.datos.dev import master_data

        master_data()
        database.session.commit()
        yield app


def _customer_and_item() -> tuple[Party, Item]:
    """Return active customer and sale item from the test master data."""
    customer = database.session.execute(database.select(Party).where(Party.is_customer.is_(True))).scalars().first()
    item = database.session.execute(database.select(Item).where(Item.is_sale_item.is_(True))).scalars().first()
    assert customer is not None
    assert item is not None
    return customer, item


def test_customer_list_overrides_company_default_and_observes_quantity_break(app_ctx):
    """A single list can serve a customer while another remains the fallback."""
    with app_ctx.app_context():
        customer, item = _customer_and_item()
        default = PriceList(name="Default", company="cacao", is_selling=True, is_default=True, is_active=True)
        wholesale = PriceList(name="Mayoristas", company="cacao", is_selling=True, is_active=True)
        database.session.add_all([default, wholesale])
        database.session.flush()
        database.session.add_all(
            [
                ItemPrice(item_code=item.code, price_list_id=default.id, uom=item.default_uom, price=Decimal("100")),
                ItemPrice(item_code=item.code, price_list_id=wholesale.id, uom=item.default_uom, price=Decimal("90")),
                ItemPrice(
                    item_code=item.code,
                    price_list_id=wholesale.id,
                    uom=item.default_uom,
                    min_qty=Decimal("10"),
                    price=Decimal("80"),
                ),
            ]
        )
        company_party = database.session.execute(
            database.select(CompanyParty).where(CompanyParty.company == "cacao", CompanyParty.party_id == customer.id)
        ).scalar_one_or_none()
        if company_party is None:
            company_party = CompanyParty(company="cacao", party_id=customer.id)
            database.session.add(company_party)
        company_party.default_price_list_id = wholesale.id
        database.session.commit()

        regular = resolve_sales_catalog_price("cacao", customer.id, item.code, Decimal("1"), item.default_uom, date.today())
        bulk = resolve_sales_catalog_price("cacao", customer.id, item.code, Decimal("10"), item.default_uom, date.today())

        assert regular is not None and regular[0] == Decimal("90") and regular[1].id == wholesale.id
        assert bulk is not None and bulk[0] == Decimal("80") and bulk[1].id == wholesale.id


def test_sales_catalog_api_returns_effective_customer_price(app_ctx):
    """The transaction grid API exposes the same price resolver as posting."""
    with app_ctx.app_context():
        customer, item = _customer_and_item()
        price_list = PriceList(name="Distribuidores", company="cacao", is_selling=True, is_default=True, is_active=True)
        database.session.add(price_list)
        database.session.flush()
        database.session.add(ItemPrice(item_code=item.code, price_list_id=price_list.id, price=Decimal("55")))
        database.session.commit()
        customer_id, item_code = customer.id, item.code

    with app_ctx.test_client() as client:
        client.post("/login", data={"usuario": "cacao", "acceso": "cacao"})
        response = client.get(
            "/api/sales/catalog-price",
            query_string={"company": "cacao", "customer_id": customer_id, "item_code": item_code, "qty": "1"},
        )

    assert response.status_code == 200
    assert response.get_json()["price"] == "55.0000"
    assert response.get_json()["price_list_name"] == "Distribuidores"


def test_quotation_rate_is_a_snapshot_when_the_catalog_changes(app_ctx):
    """A quotation retains its agreed price even after the catalog is corrected."""
    with app_ctx.app_context():
        customer, item = _customer_and_item()
        price_list = PriceList(name="Default", company="cacao", is_selling=True, is_default=True, is_active=True)
        database.session.add(price_list)
        database.session.flush()
        item_price = ItemPrice(item_code=item.code, price_list_id=price_list.id, price=Decimal("100"))
        quotation = SalesQuotation(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=1)
        database.session.add_all([item_price, quotation])
        database.session.flush()
        database.session.add(
            SalesQuotationItem(
                sales_quotation_id=quotation.id,
                item_code=item.code,
                qty=Decimal("2"),
                uom=item.default_uom,
                rate=Decimal("100"),
                amount=Decimal("200"),
            )
        )
        database.session.commit()

        item_price.price = Decimal("125")
        database.session.commit()
        saved_line = database.session.execute(
            database.select(SalesQuotationItem).where(SalesQuotationItem.sales_quotation_id == quotation.id)
        ).scalar_one()

        assert saved_line.rate == Decimal("100")
        current = resolve_sales_catalog_price("cacao", customer.id, item.code, Decimal("2"), item.default_uom, date.today())
        assert current is not None and current[0] == Decimal("125")


def test_source_line_rate_is_derived_on_the_server(app_ctx):
    """A forged price in a document-flow POST cannot change the source snapshot."""
    with app_ctx.app_context():
        customer, item = _customer_and_item()
        quotation = SalesQuotation(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=1)
        database.session.add(quotation)
        database.session.flush()
        source_line = SalesQuotationItem(
            sales_quotation_id=quotation.id,
            item_code=item.code,
            qty=Decimal("1"),
            uom=item.default_uom,
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.add(source_line)
        database.session.commit()

        with app_ctx.test_request_context(
            "/sales-order/new",
            method="POST",
            data={
                "source_type_0": "sales_quotation",
                "source_id_0": quotation.id,
                "source_item_id_0": source_line.id,
                "rate_0": "1",
            },
        ):
            assert _source_line_rate(0, Decimal("1")) == Decimal("100")


def test_sales_order_persists_source_rate_not_forged_form_rate(app_ctx):
    """Document-flow persistence retains the quotation snapshot on a forged POST."""
    with app_ctx.app_context():
        customer, item = _customer_and_item()
        quotation = SalesQuotation(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=1)
        order = SalesOrder(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=0)
        database.session.add_all([quotation, order])
        database.session.flush()
        source_line = SalesQuotationItem(
            sales_quotation_id=quotation.id,
            item_code=item.code,
            qty=Decimal("1"),
            uom=item.default_uom,
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.add(source_line)
        database.session.commit()

        with app_ctx.test_request_context(
            "/sales-order/new",
            method="POST",
            data={
                "item_code_0": item.code,
                "item_name_0": item.name,
                "qty_0": "1",
                "uom_0": item.default_uom,
                "rate_0": "1",
                "source_type_0": "sales_quotation",
                "source_id_0": quotation.id,
                "source_item_id_0": source_line.id,
            },
        ):
            _save_sales_order_items(order.id)
        saved_line = database.session.execute(
            database.select(SalesOrderItem).where(SalesOrderItem.sales_order_id == order.id)
        ).scalar_one()

        assert saved_line.rate == Decimal("100")
        assert saved_line.amount == Decimal("100")


def test_sales_quotation_discount_is_persisted_and_reduces_total(app_ctx):
    """Line percentage discounts are calculated server-side and included in totals."""
    with app_ctx.app_context():
        customer, item = _customer_and_item()
        price_list = PriceList(name="Default", company="cacao", is_selling=True, is_default=True, is_active=True)
        database.session.add(price_list)
        database.session.flush()
        database.session.add(ItemPrice(item_code=item.code, price_list_id=price_list.id, price=Decimal("100")))
        quotation = SalesQuotation(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=0)
        database.session.add(quotation)
        database.session.flush()
        with app_ctx.test_request_context(
            "/quotation/new",
            method="POST",
            data={"item_code_0": item.code, "qty_0": "2", "rate_0": "100", "discount_percentage_0": "15"},
        ):
            _save_sales_quotation_items(quotation.id)
        line = database.session.execute(database.select(SalesQuotationItem)).scalar_one()
        assert line.discount_percentage == Decimal("15")
        assert line.discount_amount == Decimal("30.0000")
        assert line.amount == Decimal("170.0000")


def test_partial_conversion_prorates_source_discount(app_ctx):
    """A partial source conversion does not apply the full source discount twice."""
    with app_ctx.app_context():
        customer, item = _customer_and_item()
        quotation = SalesQuotation(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=1)
        order = SalesOrder(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=0)
        database.session.add_all([quotation, order])
        database.session.flush()
        source = SalesQuotationItem(
            sales_quotation_id=quotation.id,
            item_code=item.code,
            qty=10,
            rate=100,
            amount=900,
            discount_percentage=10,
            discount_amount=100,
        )
        database.session.add(source)
        database.session.commit()
        with app_ctx.test_request_context(
            "/sales-order/new",
            method="POST",
            data={
                "item_code_0": item.code,
                "qty_0": "5",
                "rate_0": "100",
                "source_type_0": "sales_quotation",
                "source_id_0": quotation.id,
                "source_item_id_0": source.id,
            },
        ):
            _save_sales_order_items(order.id)
        line = database.session.execute(database.select(SalesOrderItem)).scalar_one()
        assert line.discount_amount == Decimal("50.0000")
        assert line.amount == Decimal("450.0000")


def test_quotation_expiry_is_inclusive(app_ctx):
    """Conversion on valid_until succeeds while a later date is rejected."""
    with app_ctx.app_context():
        quotation = SalesQuotation(valid_until=date(2026, 8, 27))
        validate_sales_quotation_expiry(quotation, date(2026, 8, 27))
        with pytest.raises(ValueError, match="vencida"):
            validate_sales_quotation_expiry(quotation, date(2026, 8, 28))


def test_sales_manager_cannot_manage_other_company_price_lists(app_ctx):
    """Company grants confine a sales manager's price-list administration."""
    with app_ctx.app_context():
        sales_role = database.session.execute(database.select(Roles).where(Roles.name == "sales_manager")).scalar_one()
        manager = User(id="PRICE-MANAGER", user="price-manager", password=b"test", active=True)
        other_company = Entity(
            code="price2", name="Café", company_name="Café", tax_id="J-PRICE-CAFE", currency="NIO", enabled=True
        )
        local_list = PriceList(name="Cacao", company="cacao", is_selling=True, is_active=True)
        foreign_list = PriceList(name="Café", company="price2", is_selling=True, is_active=True)
        database.session.add_all(
            [
                manager,
                other_company,
                local_list,
                foreign_list,
                RolesUser(user_id=manager.id, role_id=sales_role.id, active=True),
                UserCompanyAccess(user_id=manager.id, company_code="cacao"),
            ]
        )
        database.session.flush()
        foreign_price = ItemPrice(item_code=_customer_and_item()[1].code, price_list_id=foreign_list.id, price=Decimal("10"))
        database.session.add(foreign_price)
        database.session.commit()
        foreign_list_id, foreign_price_id = foreign_list.id, foreign_price.id

    with app_ctx.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = "PRICE-MANAGER"
            session["_fresh"] = True
        listing = client.get("/settings/price-lists")
        create = client.post(
            "/settings/item-prices", data={"item_code": "ART-TEST", "price_list_id": foreign_list_id, "price": "1"}
        )
        update = client.post(f"/settings/item-prices/{foreign_price_id}", data={"price": "1"})

    assert listing.status_code == 200
    assert b"Cacao" in listing.data and "Café".encode() not in listing.data
    assert create.status_code == 403
    assert update.status_code == 403


def test_setup_default_sales_list_seeds_standard_item_prices(app_ctx):
    """Setup makes a new company's default selling list usable immediately."""
    with app_ctx.app_context():
        _customer, existing_item = _customer_and_item()
        item = Item(
            code="PRICE-SETUP-TEST",
            name="Precio Setup",
            item_type="goods",
            default_uom=existing_item.default_uom,
            is_sale_item=True,
            standard_rate=Decimal("77"),
        )
        database.session.add(item)
        database.session.flush()
        create_default_price_lists("cacao", "NIO")
        database.session.flush()
        default_list = (
            database.session.execute(
                database.select(PriceList).where(
                    PriceList.company == "cacao", PriceList.is_default.is_(True), PriceList.is_selling.is_(True)
                )
            )
            .scalars()
            .first()
        )
        assert default_list is not None
        seeded = database.session.execute(
            database.select(ItemPrice).where(ItemPrice.price_list_id == default_list.id, ItemPrice.item_code == item.code)
        ).scalar_one_or_none()

        assert seeded is not None and seeded.price == Decimal("77")
