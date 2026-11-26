# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1741: tarifas negativas no se guardan ni se exponen como precio utilizable."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.database import Item, ItemPrice, Modules, PriceList, UOM, database
from cacao_accounting.setup.repository import create_default_price_lists
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


@pytest.fixture
def item_price_reference_scenario(app, entorno_contable):
    """Prepara referencias activas y una tarifa aislada con SQLite FK activas."""
    del entorno_contable
    suffix = uuid4().hex[:8]
    item_code = f"REF-1764-{suffix}"
    uom_code = f"UOM-{suffix}"
    price_list_id: str | None = None
    try:
        with app.app_context():
            uom = UOM(code=uom_code, name=f"Unidad {suffix}", is_active=True)
            item = Item(
                code=item_code,
                name=f"Artículo {suffix}",
                item_type="service",
                is_stock_item=False,
                is_sale_item=True,
                is_purchase_item=False,
                default_uom=uom_code,
                is_active=True,
            )
            database.session.add(uom)
            database.session.flush()
            database.session.add(item)
            database.session.commit()
        price_list_id = _create_price_list(app)
        with app.app_context():
            item_price = ItemPrice(
                item_code=item_code,
                price_list_id=price_list_id,
                uom=uom_code,
                price=Decimal("10"),
                min_qty=Decimal("0"),
            )
            database.session.add(item_price)
            database.session.commit()
            item_price_id = item_price.id
            assert database.session.execute(database.text("PRAGMA foreign_keys")).scalar_one() == 1
        yield SimpleNamespace(
            suffix=suffix,
            item_code=item_code,
            uom_code=uom_code,
            price_list_id=price_list_id,
            item_price_id=item_price_id,
        )
    finally:
        with app.app_context():
            database.session.rollback()
            if price_list_id is not None:
                precios = (
                    database.session.execute(database.select(ItemPrice).filter_by(price_list_id=price_list_id)).scalars().all()
                )
                for precio in precios:
                    database.session.delete(precio)
            item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one_or_none()
            if item is not None:
                database.session.delete(item)
            uom = database.session.execute(database.select(UOM).filter_by(code=uom_code)).scalar_one_or_none()
            if uom is not None:
                database.session.delete(uom)
            if price_list_id is not None:
                price_list = database.session.get(PriceList, price_list_id)
                if price_list is not None:
                    database.session.delete(price_list)
            database.session.commit()


def _remove_item_price_reference(app, scenario, reference: str) -> None:
    """Simula una fila legada huérfana y reactiva FK antes del POST HTTP."""
    with app.app_context():
        database.session.remove()
        code = scenario.item_code if reference == "item" else scenario.uom_code
        table = "item" if reference == "item" else "uom"
        with database.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 0
            try:
                connection.exec_driver_sql(f"DELETE FROM {table} WHERE code = ?", (code,))
            finally:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert database.session.execute(database.text("PRAGMA foreign_keys")).scalar_one() == 1


def _item_price_snapshot(app, item_price_id: str) -> dict[str, object]:
    """Obtiene todas las columnas persistidas para comprobar ausencia de mutación."""
    with app.app_context():
        database.session.expire_all()
        item_price = database.session.get(ItemPrice, item_price_id)
        assert item_price is not None
        return {column.key: getattr(item_price, column.key) for column in ItemPrice.__table__.columns}


_REFERENCE_CASES = (
    ("item", "missing", "missing_item"),
    ("item", "inactive", "inactive_item"),
    ("uom", "missing", "missing_uom"),
    ("uom", "inactive", "inactive_uom"),
)
_REFERENCE_MESSAGES = {
    "missing_item": ("El artículo seleccionado no existe.", "The selected item does not exist."),
    "inactive_item": ("El artículo seleccionado no está activo.", "The selected item is not active."),
    "missing_uom": ("La unidad de medida seleccionada no existe.", "The selected unit of measure does not exist."),
    "inactive_uom": ("La unidad de medida seleccionada no está activa.", "The selected unit of measure is not active."),
}


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


def test_lista_de_precios_omite_tarifas_legacy_negativas(app, authenticated_client, entorno_contable):
    """#1741: crear una lista no genera precios desde tarifas negativas heredadas."""
    from cacao_accounting.database import Item, ItemPrice, database

    with app.app_context():
        item = Item(
            code="NEG-1741",
            name="Negativo",
            item_type="service",
            is_stock_item=False,
            is_sale_item=True,
            is_purchase_item=False,
            default_uom="UND",
            standard_rate=Decimal("-5"),
        )
        database.session.add(item)
        database.session.commit()

    respuesta = authenticated_client("admin").post(
        "/settings/price-lists",
        data={"name": "Lista 1741", "company": "cacao", "currency": "NIO", "is_selling": "y"},
    )

    assert respuesta.status_code in {200, 302}
    with app.app_context():
        precios = database.session.execute(database.select(ItemPrice).filter_by(item_code="NEG-1741")).scalars().all()
        assert precios == []


def test_seed_omite_tarifa_estandar_legacy_negativa(app, entorno_contable):
    """El seed no debe regenerar precios de venta negativos desde artículos legacy."""
    with app.app_context():
        item = Item(
            code="SEED-NEG-1741",
            name="Negativo heredado",
            item_type="service",
            is_stock_item=False,
            is_sale_item=True,
            is_purchase_item=False,
            default_uom="UND",
            standard_rate=Decimal("-5"),
        )
        database.session.add(item)
        database.session.flush()

        create_default_price_lists("cacao", "NIO")

        prices = database.session.execute(database.select(ItemPrice).filter_by(item_code="SEED-NEG-1741")).scalars().all()
        assert prices == []
        database.session.rollback()


def _assert_item_price_redirect_message(response, messages: tuple[str, ...]) -> None:
    """Verifica redirección controlada y mensaje visible tras seguir el POST."""
    assert response.status_code == 200
    assert response.history[0].status_code == 302
    html = response.get_data(as_text=True)
    assert any(message in html for message in messages)


@pytest.mark.parametrize(("reference", "state", "message_key"), _REFERENCE_CASES)
def test_item_price_creation_rejects_unavailable_references_without_persisting(
    app, authenticated_client, item_price_reference_scenario, reference, state, message_key
):
    """El alta HTTP rechaza Item o UOM inexistentes/inactivos sin crear tarifas."""
    scenario = item_price_reference_scenario
    data = {
        "price_list_id": scenario.price_list_id,
        "item_code": scenario.item_code,
        "uom": scenario.uom_code,
        "price": "12.50",
        "min_qty": "0",
    }
    with app.app_context():
        if state == "inactive":
            model = Item if reference == "item" else UOM
            code = scenario.item_code if reference == "item" else scenario.uom_code
            registro = database.session.execute(database.select(model).filter_by(code=code)).scalar_one_or_none()
            assert registro is not None
            registro.is_active = False
            database.session.commit()
        else:
            campo = "item_code" if reference == "item" else "uom"
            data[campo] = f"MISSING-{reference}-{scenario.suffix}"
        antes = database.session.execute(
            database.select(database.func.count()).select_from(ItemPrice).filter_by(price_list_id=scenario.price_list_id)
        ).scalar_one()

    respuesta = authenticated_client().post("/settings/item-prices", data=data, follow_redirects=True)

    _assert_item_price_redirect_message(respuesta, _REFERENCE_MESSAGES[message_key])
    with app.app_context():
        despues = database.session.execute(
            database.select(database.func.count()).select_from(ItemPrice).filter_by(price_list_id=scenario.price_list_id)
        ).scalar_one()
    assert despues == antes


@pytest.mark.parametrize(("reference", "state", "message_key"), _REFERENCE_CASES)
def test_item_price_update_rejects_unavailable_references_without_mutating(
    app, authenticated_client, item_price_reference_scenario, reference, state, message_key
):
    """La edición HTTP rechaza referencias heredadas inválidas y conserva la tarifa."""
    scenario = item_price_reference_scenario
    with app.app_context():
        if state == "inactive":
            model = Item if reference == "item" else UOM
            code = scenario.item_code if reference == "item" else scenario.uom_code
            registro = database.session.execute(database.select(model).filter_by(code=code)).scalar_one_or_none()
            assert registro is not None
            registro.is_active = False
            database.session.commit()
        else:
            _remove_item_price_reference(app, scenario, reference)
    antes = _item_price_snapshot(app, scenario.item_price_id)

    respuesta = authenticated_client().post(
        f"/settings/item-prices/{scenario.item_price_id}",
        data={"price": "18.75", "min_qty": "2", "valid_from": "2026-05-01", "valid_upto": "2026-05-31"},
        follow_redirects=True,
    )

    _assert_item_price_redirect_message(respuesta, _REFERENCE_MESSAGES[message_key])
    assert _item_price_snapshot(app, scenario.item_price_id) == antes


@pytest.mark.parametrize("empty_uom", [False, True])
def test_item_price_creation_accepts_active_references_and_optional_uom(
    app, authenticated_client, item_price_reference_scenario, empty_uom
):
    """El control válido acepta referencias activas y una UOM vacía opcional."""
    scenario = item_price_reference_scenario
    respuesta = authenticated_client().post(
        "/settings/item-prices",
        data={
            "price_list_id": scenario.price_list_id,
            "item_code": scenario.item_code,
            "uom": "" if empty_uom else scenario.uom_code,
            "price": "12.3456",
            "min_qty": "1.5",
        },
    )

    assert respuesta.status_code == 302
    with app.app_context():
        database.session.expire_all()
        creado = database.session.execute(
            database.select(ItemPrice).filter_by(
                item_code=scenario.item_code,
                price_list_id=scenario.price_list_id,
                price=Decimal("12.3456"),
            )
        ).scalar_one()
        assert creado.uom == (None if empty_uom else scenario.uom_code)
        assert creado.min_qty == Decimal("1.5")


@pytest.mark.parametrize("empty_uom", [False, True])
def test_item_price_update_accepts_active_references_and_optional_uom(
    app, authenticated_client, item_price_reference_scenario, empty_uom
):
    """La edición válida conserva una UOM activa o vacía y aplica todos los campos."""
    scenario = item_price_reference_scenario
    with app.app_context():
        item_price = database.session.get(ItemPrice, scenario.item_price_id)
        assert item_price is not None
        if empty_uom:
            item_price.uom = None
        database.session.commit()

    respuesta = authenticated_client().post(
        f"/settings/item-prices/{scenario.item_price_id}",
        data={
            "price": "18.7500",
            "min_qty": "2.5",
            "valid_from": "2026-05-01",
            "valid_upto": "2026-05-31",
        },
    )

    assert respuesta.status_code == 302
    with app.app_context():
        database.session.expire_all()
        item_price = database.session.get(ItemPrice, scenario.item_price_id)
        assert item_price is not None
        assert item_price.uom == (None if empty_uom else scenario.uom_code)
        assert item_price.price == Decimal("18.7500")
        assert item_price.min_qty == Decimal("2.5")
        assert item_price.valid_from == date(2026, 5, 1)
        assert item_price.valid_upto == date(2026, 5, 31)
