# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1741: tarifas negativas no se guardan ni se exponen como precio utilizable."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import ItemPrice, Modules, PriceList, database
from cacao_accounting.tax_pricing_service import resolve_item_price_record


def _create_price_list(app) -> str:
    """Crea una lista activa exclusiva de la prueba y devuelve su ID."""
    with app.app_context():
        admin_module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if admin_module is None:
            admin_module = Modules(module="admin", default=False, enabled=True)
            database.session.add(admin_module)
        admin_module.enabled = True
        price_list = PriceList(
            name=f"Lista {uuid4().hex[:8]}",
            company="cacao",
            currency="NIO",
            is_selling=True,
            is_active=True,
        )
        database.session.add(price_list)
        database.session.commit()
        return str(price_list.id)


def test_item_price_endpoint_rejects_negative_price_without_persisting(app, entorno_contable, authenticated_client):
    """Un POST administrativo negativo produce validación y no crea la tarifa."""
    price_list_id = _create_price_list(app)
    response = authenticated_client().post(
        "/settings/item-prices",
        data={
            "price_list_id": price_list_id,
            "item_code": "ART01",
            "uom": "UND",
            "price": "-2.50",
            "min_qty": "0",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        assert (
            database.session.execute(database.select(ItemPrice).filter_by(price_list_id=price_list_id)).scalars().all() == []
        )
        price_list = database.session.get(PriceList, price_list_id)
        database.session.delete(price_list)
        database.session.commit()


def test_existing_negative_price_is_not_returned_for_use(app, entorno_contable):
    """Un registro legado inválido no llega al resolvedor del precio de venta."""
    price_list_id = _create_price_list(app)
    with app.app_context():
        item_price = ItemPrice(
            item_code="ART01",
            price_list_id=price_list_id,
            uom="UND",
            price=Decimal("-2.50"),
            min_qty=Decimal("0"),
        )
        database.session.add(item_price)
        database.session.commit()

        resolved = resolve_item_price_record("ART01", price_list_id, Decimal("1"), "UND", date(2026, 5, 15))
        assert resolved is None

        database.session.delete(item_price)
        database.session.delete(database.session.get(PriceList, price_list_id))
        database.session.commit()
