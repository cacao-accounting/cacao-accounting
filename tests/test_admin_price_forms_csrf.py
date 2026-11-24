# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1743: los formularios de listas y tarifas de precio funcionan con CSRF activo."""

from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Item, ItemPrice, Modules, PriceList, database


@pytest.fixture
def csrf_price_forms(app, entorno_contable, authenticated_client):
    """Habilita CSRF real y prepara artículos, lista y tarifa de prueba."""
    previous_csrf = app.config["WTF_CSRF_ENABLED"]
    app.config["WTF_CSRF_ENABLED"] = True
    suffix = uuid4().hex[:8]
    item_code = f"CSR-1743-{suffix}"
    with app.app_context():
        admin_module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if admin_module is None:
            admin_module = Modules(module="admin", default=False, enabled=True)
            database.session.add(admin_module)
        admin_module.enabled = True
        item = Item(
            code=item_code,
            name=f"Artículo CSRF {suffix}",
            item_type="service",
            is_stock_item=False,
            is_sale_item=True,
            is_purchase_item=False,
            default_uom="UND",
            standard_rate=Decimal("10"),
        )
        price_list = PriceList(
            name=f"Lista CSRF {suffix}",
            company="cacao",
            currency="NIO",
            is_selling=True,
            is_active=True,
        )
        database.session.add_all([item, price_list])
        database.session.flush()
        item_price = ItemPrice(
            item_code=item_code,
            price_list_id=price_list.id,
            price=Decimal("10"),
            min_qty=Decimal("0"),
        )
        database.session.add(item_price)
        database.session.commit()
        ids = (item_code, price_list.id, item_price.id)
    client = authenticated_client("admin")
    yield app, client, ids
    with app.app_context():
        database.session.execute(database.delete(ItemPrice).where(ItemPrice.id == ids[2]))
        database.session.execute(database.delete(PriceList).where(PriceList.id == ids[1]))
        database.session.execute(database.delete(Item).where(Item.code == ids[0]))
        database.session.commit()
    app.config["WTF_CSRF_ENABLED"] = previous_csrf


def _form_token(html: str, action: str | None = None) -> str:
    """Devuelve el token del formulario que apunta a ``action``."""
    forms = re.findall(r"<form\b([^>]*)>(.*?)</form>", html, flags=re.DOTALL)
    for attributes, body in forms:
        if action is not None:
            form_action = re.search(r'action="([^"]+)"', attributes)
            if form_action is None or form_action.group(1) != action:
                continue
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
        if token is not None:
            return token.group(1)
    pytest.fail(f"No CSRF token found for form action {action!r}")


def test_price_list_form_sends_its_own_csrf_token(csrf_price_forms):
    """La alta de listas no puede bloquearse por el guard global de CSRF."""
    app, client, _ids = csrf_price_forms
    page = client.get("/settings/price-lists")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True))

    without_token = client.post(
        "/settings/price-lists",
        data={"name": "Lista CSRF rechazada", "company": "cacao", "currency": "NIO", "is_selling": "y"},
    )
    assert without_token.status_code == 400

    accepted = client.post(
        "/settings/price-lists",
        data={
            "name": "Lista CSRF aceptada",
            "company": "cacao",
            "currency": "NIO",
            "is_selling": "y",
            "csrf_token": token,
        },
    )
    assert accepted.status_code == 302
    with app.app_context():
        database.session.expire_all()
        created = database.session.execute(
            database.select(PriceList).filter_by(name="Lista CSRF aceptada")
        ).scalar_one_or_none()
        assert created is not None
        database.session.delete(created)
        database.session.commit()


def test_item_price_creation_form_sends_its_own_csrf_token(csrf_price_forms):
    """La alta de tarifas completa la transición con CSRF habilitado."""
    app, client, ids = csrf_price_forms
    item_code, price_list_id, _item_price_id = ids
    page = client.get("/settings/item-prices")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True))

    data = {"price_list_id": price_list_id, "item_code": item_code, "price": "12.50", "min_qty": "0"}
    assert client.post("/settings/item-prices", data=data).status_code == 400

    accepted = client.post("/settings/item-prices", data={**data, "csrf_token": token})
    assert accepted.status_code == 302
    with app.app_context():
        database.session.expire_all()
        created = database.session.execute(
            database.select(ItemPrice).where(
                ItemPrice.item_code == item_code,
                ItemPrice.price_list_id == price_list_id,
                ItemPrice.price == Decimal("12.50"),
            )
        ).scalar_one_or_none()
        assert created is not None
        database.session.delete(created)
        database.session.commit()


def test_item_price_update_form_sends_its_own_csrf_token(csrf_price_forms):
    """La edición de tarifas usa el token del formulario de esa fila."""
    app, client, ids = csrf_price_forms
    _item_code, _price_list_id, item_price_id = ids
    url = f"/settings/item-prices/{item_price_id}"
    page = client.get("/settings/item-prices")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True), url)

    data = {"price": "18.75", "min_qty": "0"}
    assert client.post(url, data=data).status_code == 400

    accepted = client.post(url, data={**data, "csrf_token": token})
    assert accepted.status_code == 302
    with app.app_context():
        database.session.expire_all()
        item_price = database.session.get(ItemPrice, item_price_id)
        assert item_price is not None
        assert item_price.price == Decimal("18.75")
