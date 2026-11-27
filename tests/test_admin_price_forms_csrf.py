# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1743: los formularios de listas y tarifas de precio funcionan con CSRF activo."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Item, ItemPrice, Modules, PriceList, database

_UNSET = object()

_INVALID_ITEM_PRICE_VALUES = (
    (
        "price",
        "no-es-numero",
        ("El campo price debe ser un número válido.", "The price field must be a valid number."),
    ),
    (
        "price",
        "NaN",
        ("El campo price debe ser un número finito.", "The price field must be a finite number."),
    ),
    (
        "min_qty",
        "no-es-numero",
        ("El campo min_qty debe ser un número válido.", "The min_qty field must be a valid number."),
    ),
    (
        "min_qty",
        "-Infinity",
        ("El campo min_qty debe ser un número finito.", "The min_qty field must be a finite number."),
    ),
    (
        "valid_from",
        "no-es-fecha",
        ("El campo valid_from debe ser una fecha válida.", "The valid_from field must be a valid date."),
    ),
    (
        "valid_upto",
        "2026-02-30",
        ("El campo valid_upto debe ser una fecha válida.", "The valid_upto field must be a valid date."),
    ),
)


@pytest.fixture
def csrf_state_snapshot(app):
    """Verifica al final de la prueba que CSRF y el módulo admin vuelven al estado previo."""
    previous_csrf = app.config["WTF_CSRF_ENABLED"]
    with app.app_context():
        previous_enabled = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one().enabled
    yield
    assert app.config["WTF_CSRF_ENABLED"] == previous_csrf
    with app.app_context():
        current = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one()
        assert current.enabled == previous_enabled


@pytest.fixture
def csrf_price_forms(app, entorno_contable, authenticated_client, csrf_state_snapshot):
    """Habilita CSRF real y prepara artículos, lista y tarifa de prueba."""
    del entorno_contable, csrf_state_snapshot
    previous_csrf = app.config["WTF_CSRF_ENABLED"]
    module_created = False
    previous_enabled: object = _UNSET
    ids: tuple[str, str, str] | None = None
    try:
        app.config["WTF_CSRF_ENABLED"] = True
        suffix = uuid4().hex[:8]
        item_code = f"CSR-1743-{suffix}"
        with app.app_context():
            admin_module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            module_created = admin_module is None
            previous_enabled = None if module_created else admin_module.enabled
            if module_created:
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
    finally:
        app.config["WTF_CSRF_ENABLED"] = previous_csrf
        with app.app_context():
            database.session.rollback()
            if ids is not None:
                database.session.execute(database.delete(ItemPrice).where(ItemPrice.id == ids[2]))
                database.session.execute(database.delete(PriceList).where(PriceList.id == ids[1]))
                database.session.execute(database.delete(Item).where(Item.code == ids[0]))
            current = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if module_created:
                if current is not None:
                    database.session.delete(current)
            elif current is not None and previous_enabled is not _UNSET:
                current.enabled = previous_enabled
            database.session.commit()


def test_fixture_restaura_estado_si_falla_el_cliente_autenticado(app, entorno_contable):
    """#2284: un fallo de setup no deja CSRF, módulo ni filas de prueba."""
    previous_csrf = app.config["WTF_CSRF_ENABLED"]
    with app.app_context():
        previous_enabled = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one().enabled
        counts = tuple(
            database.session.execute(database.select(database.func.count()).select_from(model)).scalar_one()
            for model in (Item, PriceList, ItemPrice)
        )

    def failing_client(_role):
        raise RuntimeError("fallo de setup")

    generator = csrf_price_forms.__wrapped__(app, entorno_contable, failing_client, object())
    with pytest.raises(RuntimeError, match="fallo de setup"):
        next(generator)

    assert app.config["WTF_CSRF_ENABLED"] == previous_csrf
    with app.app_context():
        assert (
            database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one().enabled
            == previous_enabled
        )
        after = tuple(
            database.session.execute(database.select(database.func.count()).select_from(model)).scalar_one()
            for model in (Item, PriceList, ItemPrice)
        )
    assert after == counts


def _form_token(html: str, action: str | None = None, marker: str | None = None) -> str:
    """Devuelve el token del formulario identificado por ``action`` o ``marker``.

    Seleccionar el formulario de forma explícita evita que el token del encabezado
    enmascare la ausencia del campo oculto en el formulario bajo prueba.
    """
    forms = re.findall(r"<form\b([^>]*)>(.*?)</form>", html, flags=re.DOTALL)
    for attributes, body in forms:
        if action is not None:
            form_action = re.search(r'action="([^"]+)"', attributes)
            if form_action is None or form_action.group(1) != action:
                continue
        if marker is not None and marker not in body:
            continue
        token = re.search(r'name="csrf_token"\s+value="([^"]+)"', body)
        if token is not None:
            return token.group(1)
    pytest.fail(f"No CSRF token found for form action={action!r} marker={marker!r}")


def test_price_list_form_sends_its_own_csrf_token(csrf_price_forms):
    """La alta de listas no puede bloquearse por el guard global de CSRF."""
    app, client, _ids = csrf_price_forms
    page = client.get("/settings/price-lists")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True), marker='name="name"')

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
    token = _form_token(page.get_data(as_text=True), marker='name="item_code"')

    data = {"price_list_id": price_list_id, "item_code": item_code, "price": "12.50", "min_qty": "2"}
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


def _item_price_snapshot(app, item_price_id: str) -> dict[str, object]:
    """Lee una tarifa fresca para detectar mutaciones parciales tras un POST inválido."""
    with app.app_context():
        database.session.expire_all()
        item_price = database.session.get(ItemPrice, item_price_id)
        assert item_price is not None
        return {column.key: getattr(item_price, column.key) for column in ItemPrice.__table__.columns}


@pytest.mark.parametrize(("field", "value", "messages"), _INVALID_ITEM_PRICE_VALUES)
def test_item_price_creation_rejects_invalid_decimal_or_date_without_persisting(csrf_price_forms, field, value, messages):
    """La alta HTTP real informa el campo inválido y no agrega tarifas."""
    app, client, (item_code, price_list_id, _item_price_id) = csrf_price_forms
    page = client.get("/settings/item-prices")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True), marker='name="item_code"')
    data = {
        "price_list_id": price_list_id,
        "item_code": item_code,
        "uom": "UND",
        "price": "12.50",
        "min_qty": "0",
        "valid_from": "2026-05-01",
        "valid_upto": "2026-05-31",
    }
    data[field] = value
    with app.app_context():
        antes = database.session.execute(
            database.select(database.func.count()).select_from(ItemPrice).filter_by(price_list_id=price_list_id)
        ).scalar_one()

    respuesta = client.post(
        "/settings/item-prices",
        data={**data, "csrf_token": token},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert respuesta.history[0].status_code == 302
    html = respuesta.get_data(as_text=True)
    assert any(mensaje in html for mensaje in messages)
    with app.app_context():
        despues = database.session.execute(
            database.select(database.func.count()).select_from(ItemPrice).filter_by(price_list_id=price_list_id)
        ).scalar_one()
    assert despues == antes


_INVALID_QUICK_PRICE_VALUES = tuple(entry for entry in _INVALID_ITEM_PRICE_VALUES if entry[0] == "price")


@pytest.mark.parametrize(("field", "value", "messages"), _INVALID_QUICK_PRICE_VALUES)
def test_item_price_update_rejects_invalid_decimal_without_mutating(csrf_price_forms, field, value, messages):
    """La edición HTTP real no aplica cambios parciales cuando un campo es inválido."""
    app, client, (_item_code, _price_list_id, item_price_id) = csrf_price_forms
    url = f"/settings/item-prices/{item_price_id}"
    page = client.get("/settings/item-prices")
    assert page.status_code == 200
    token = _form_token(page.get_data(as_text=True), url)
    data = {
        "price": "18.75",
        "min_qty": "2",
        "valid_from": "2026-05-01",
        "valid_upto": "2026-05-31",
    }
    data[field] = value
    antes = _item_price_snapshot(app, item_price_id)

    respuesta = client.post(
        url,
        data={**data, "csrf_token": token},
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert respuesta.history[0].status_code == 302
    html = respuesta.get_data(as_text=True)
    assert any(mensaje in html for mensaje in messages)
    assert _item_price_snapshot(app, item_price_id) == antes


def _prepara_tarifa_con_criterios(app, item_price_id):
    """Fija criterios no editables para comprobar que el POST rápido los conserva."""
    with app.app_context():
        item_price = database.session.get(ItemPrice, item_price_id)
        item_price.min_qty = Decimal("5")
        item_price.valid_from = date(2026, 1, 1)
        item_price.valid_upto = date(2026, 12, 31)
        database.session.commit()


def _criterios(app, item_price_id):
    """Lee precio y criterios vigentes de una tarifa."""
    with app.app_context():
        database.session.expire_all()
        item_price = database.session.get(ItemPrice, item_price_id)
        return (item_price.price, item_price.min_qty, item_price.valid_from, item_price.valid_upto)


def test_edicion_rapida_preserva_criterios_ausentes(csrf_price_forms):
    """Si el POST rápido omite cantidad y vigencias, se conservan las persistidas."""
    app, client, (_item_code, _price_list_id, item_price_id) = csrf_price_forms
    _prepara_tarifa_con_criterios(app, item_price_id)
    url = f"/settings/item-prices/{item_price_id}"
    page = client.get("/settings/item-prices")
    token = _form_token(page.get_data(as_text=True), url)

    respuesta = client.post(url, data={"price": "18.75", "expected_price": "10", "csrf_token": token})

    assert respuesta.status_code == 302
    assert _criterios(app, item_price_id) == (Decimal("18.75"), Decimal("5"), date(2026, 1, 1), date(2026, 12, 31))


def test_edicion_rapida_ignora_criterios_obsoletos(csrf_price_forms):
    """Los campos ocultos desfasados no reescriben cantidad ni vigencias."""
    app, client, (_item_code, _price_list_id, item_price_id) = csrf_price_forms
    _prepara_tarifa_con_criterios(app, item_price_id)
    url = f"/settings/item-prices/{item_price_id}"
    page = client.get("/settings/item-prices")
    token = _form_token(page.get_data(as_text=True), url)

    respuesta = client.post(
        url,
        data={
            "price": "20",
            "expected_price": "10",
            "min_qty": "999",
            "valid_from": "2020-01-01",
            "valid_upto": "2020-12-31",
            "csrf_token": token,
        },
    )

    assert respuesta.status_code == 302
    assert _criterios(app, item_price_id) == (Decimal("20"), Decimal("5"), date(2026, 1, 1), date(2026, 12, 31))


def test_edicion_rapida_rechaza_precio_desfasado(csrf_price_forms):
    """Dos formularios abiertos antes del cambio no sobrescriben el precio."""
    app, client, (_item_code, _price_list_id, item_price_id) = csrf_price_forms
    _prepara_tarifa_con_criterios(app, item_price_id)
    url = f"/settings/item-prices/{item_price_id}"
    page = client.get("/settings/item-prices")
    token = _form_token(page.get_data(as_text=True), url)

    primera = client.post(url, data={"price": "18.75", "expected_price": "10", "csrf_token": token})
    segunda = client.post(
        url,
        data={"price": "99", "expected_price": "10", "csrf_token": token},
        follow_redirects=True,
    )

    assert primera.status_code == 302
    assert segunda.status_code == 200
    assert segunda.history[0].status_code == 302
    assert "El precio cambió mientras editaba" in segunda.get_data(as_text=True)
    assert _criterios(app, item_price_id) == (Decimal("18.75"), Decimal("5"), date(2026, 1, 1), date(2026, 12, 31))


def test_edicion_completa_si_actualiza_criterios(csrf_price_forms):
    """El formulario completo conserva su vía explícita para crear tarifas con vigencias."""
    app, client, (item_code, price_list_id, item_price_id) = csrf_price_forms
    page = client.get("/settings/item-prices")
    token = _form_token(page.get_data(as_text=True), marker='name="item_code"')

    respuesta = client.post(
        "/settings/item-prices",
        data={
            "price_list_id": price_list_id,
            "item_code": item_code,
            "uom": "UND",
            "price": "30",
            "min_qty": "7",
            "valid_from": "2026-03-01",
            "valid_upto": "2026-09-30",
            "csrf_token": token,
        },
    )

    assert respuesta.status_code == 302
    try:
        with app.app_context():
            creada = database.session.execute(
                database.select(ItemPrice).where(
                    ItemPrice.item_code == item_code,
                    ItemPrice.price == Decimal("30"),
                    ItemPrice.min_qty == Decimal("7"),
                    ItemPrice.valid_from == date(2026, 3, 1),
                    ItemPrice.valid_upto == date(2026, 9, 30),
                )
            ).scalar_one_or_none()
            assert creada is not None
            assert creada.id != item_price_id
    finally:
        with app.app_context():
            database.session.rollback()
            temporales = (
                database.session.execute(
                    database.select(ItemPrice).where(
                        ItemPrice.price_list_id == price_list_id,
                        ItemPrice.id != item_price_id,
                    )
                )
                .scalars()
                .all()
            )
            for temporal in temporales:
                database.session.delete(temporal)
            database.session.commit()
