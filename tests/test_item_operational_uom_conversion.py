# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1737: las UOM de compra/venta requieren conversión configurada.

Un artículo con `purchase_uom`/`sale_uom` distinta de la base y sin fila de
conversión se persistía igual, y luego los flujos de compra/venta no podían
normalizar la cantidad a la UOM base.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, UOM, database
from cacao_accounting.inventario.service import (
    InventoryServiceError,
    ItemParams,
    ItemUOMRow,
    create_item_with_uoms,
)

FECHA = date(2026, 5, 15)


@pytest.fixture
def item_uom_scenario():
    """Compañía con UOM base EA y alternativa BOX."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
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
                UOM(code="EA", name="Unidad", is_active=True),
                UOM(code="BOX", name="Caja", is_active=True),
            ]
        )
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _params(**overrides) -> ItemParams:
    values = {
        "name": "Artículo UOM",
        "item_type": "goods",
        "is_stock_item": True,
        "default_uom": "EA",
    }
    values.update(overrides)
    return ItemParams(**values)


def test_creacion_rechaza_uom_compra_sin_conversion(item_uom_scenario):
    """Una purchase_uom distinta de la base sin conversión se rechaza."""
    with item_uom_scenario.app_context():
        with pytest.raises(InventoryServiceError, match="requiere una conversión"):
            create_item_with_uoms(_params(purchase_uom="BOX", uom_rows=[]))


def test_creacion_rechaza_uom_venta_sin_conversion(item_uom_scenario):
    """Una sale_uom distinta de la base sin conversión se rechaza."""
    with item_uom_scenario.app_context():
        with pytest.raises(InventoryServiceError, match="requiere una conversión"):
            create_item_with_uoms(_params(sale_uom="BOX", uom_rows=[]))


def test_creacion_acepta_uom_compra_con_conversion(item_uom_scenario):
    """Control positivo: con conversión configurada el artículo se crea."""
    with item_uom_scenario.app_context():
        item = create_item_with_uoms(
            _params(purchase_uom="BOX", sale_uom="BOX", uom_rows=[ItemUOMRow(uom_code="BOX", conversion_factor=Decimal("12"))])
        )
        assert item.purchase_uom == "BOX"
        assert item.sale_uom == "BOX"


def test_creacion_acepta_uom_compra_igual_a_base(item_uom_scenario):
    """Control positivo: usar la UOM base no requiere conversión."""
    with item_uom_scenario.app_context():
        item = create_item_with_uoms(_params(purchase_uom="EA", sale_uom="EA"))
        assert item.code
