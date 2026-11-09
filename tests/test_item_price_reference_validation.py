# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El catálogo de precios valida artículo y unidad de medida.

Escenario de negocio (issue #1764): el alta y la edición insertaban códigos de
texto libre; con FKs activas el motor devolvía HTTP 500 y sin ellas quedaba una
tarifa huérfana.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    ItemPrice,
    Modules,
    PriceList,
    UOM,
    User,
    database,
)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                UOM(code="UND", name="Unidad", is_active=True),
                UOM(code="OFF", name="Unidad inactiva", is_active=False),
                Item(code="ART-1", name="Artículo", item_type="goods", default_uom="UND", is_active=True),
                Item(code="ART-OFF", name="Artículo inactivo", item_type="goods", default_uom="UND", is_active=False),
                PriceList(
                    name="Ventas",
                    company="cacao",
                    currency="NIO",
                    is_selling=True,
                    is_active=True,
                ),
            ]
        )
        database.session.commit()
        price_list_id = database.session.execute(database.select(PriceList)).scalar_one().id
    return application, price_list_id


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _formulario(price_list_id: str, **overrides) -> dict[str, str]:
    datos = {
        "price_list_id": price_list_id,
        "item_code": "ART-1",
        "uom": "UND",
        "price": "10",
        "min_qty": "0",
    }
    datos.update(overrides)
    return datos


@pytest.mark.parametrize(
    ("item_code", "uom", "mensaje"),
    [
        ("NO-EXISTE", "UND", "El artículo seleccionado no existe."),
        ("ART-OFF", "UND", "El artículo seleccionado no está activo."),
        ("ART-1", "NO-UOM", "La unidad de medida seleccionada no existe."),
        ("ART-1", "OFF", "La unidad de medida seleccionada no está activa."),
    ],
)
def test_rechaza_referencias_invalidas(item_code, uom, mensaje):
    """#1764: artículo/UOM inexistente o inactivo no crea la tarifa."""
    application, price_list_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/item-prices", data=_formulario(price_list_id, item_code=item_code, uom=uom))

        assert respuesta.status_code == 302
        with application.app_context():
            assert database.session.execute(database.select(ItemPrice)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_crea_una_tarifa_con_referencias_vigentes():
    """#1764: la combinación válida sigue persistiendo el precio."""
    application, price_list_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/item-prices", data=_formulario(price_list_id))

        assert respuesta.status_code == 302
        with application.app_context():
            tarifa = database.session.execute(database.select(ItemPrice)).scalar_one()
            assert tarifa.item_code == "ART-1"
            assert tarifa.uom == "UND"
            assert tarifa.price == Decimal("10.0000")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_edicion_revalida_la_referencia():
    """#1764: si el artículo se desactiva, la edición no sobrescribe."""
    application, price_list_id = _crear_app()
    try:
        with application.app_context():
            item_price = ItemPrice(
                item_code="ART-1",
                price_list_id=price_list_id,
                uom="UND",
                price=Decimal("10"),
                min_qty=Decimal("0"),
            )
            database.session.add(item_price)
            item = database.session.execute(database.select(Item).filter_by(code="ART-1")).scalar_one()
            item.is_active = False
            database.session.commit()
            item_price_id = item_price.id

        client = _cliente(application)
        respuesta = client.post(f"/settings/item-prices/{item_price_id}", data={"price": "99", "min_qty": "0"})

        assert respuesta.status_code == 302
        with application.app_context():
            tarifa = database.session.get(ItemPrice, item_price_id)
            assert tarifa is not None and tarifa.price == Decimal("10.0000")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
