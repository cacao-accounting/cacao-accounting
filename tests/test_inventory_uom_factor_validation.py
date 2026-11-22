# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1072/#1174: los factores y resultados de conversión UOM deben ser finitos.

El escenario reproduce la frontera real del formulario de artículo:
``parse_item_uom_rows`` construye el factor y ``create_item_with_uoms`` lo
persiste. Un ``Infinity`` superaba la comparación con cero y un ``NaN``
propagaba ``decimal.InvalidOperation`` fuera de la validación controlada.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

ITEM = "ITEM-UOM-FINITO"
CAJA = "CAJA-12"


@pytest.fixture
def catalogo_uom():
    """Aplicación aislada con artículo, moneda y unidades de medida."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        from cacao_accounting.database import Currency, Entity, Item, UOM

        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="UND", name="Unidad", is_active=True),
                UOM(code=CAJA, name="Caja de 12", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code=ITEM,
                name="Artículo con conversión",
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
            )
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _item_params(factor: Decimal):
    """Construye los parámetros reales del alta de artículo con una conversión."""
    from cacao_accounting.inventario.service import ItemParams, ItemUOMRow

    return ItemParams(
        name="Artículo inválido",
        item_type="goods",
        is_stock_item=True,
        default_uom="UND",
        uom_rows=[ItemUOMRow(uom_code=CAJA, conversion_factor=factor)],
    )


@pytest.mark.parametrize("factor", [Decimal("Infinity"), Decimal("-Infinity"), Decimal("NaN")])
def test_validacion_rechaza_factor_no_finito(catalogo_uom, factor):
    """La validación de filas rechaza cualquier factor no finito con error controlado."""
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.inventario.service import (
            InventoryServiceError,
            ItemUOMRow,
            validate_item_uom_rows,
        )

        with pytest.raises(InventoryServiceError):
            validate_item_uom_rows("UND", [ItemUOMRow(uom_code=CAJA, conversion_factor=factor)])


@pytest.mark.parametrize("texto", ["Infinity", "-Infinity", "NaN", "0.0000000001"])
def test_parseo_rechaza_factor_no_finito_o_no_representable(catalogo_uom, texto):
    """El formulario no convierte factores no finitos o no representables en filas."""
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.inventario.service import InventoryServiceError, parse_item_uom_rows

        with pytest.raises(InventoryServiceError):
            parse_item_uom_rows({"uom_code": [CAJA], "uom_conversion_factor": [texto]})


@pytest.mark.parametrize("factor", [Decimal("Infinity"), Decimal("NaN"), Decimal("0.0000000001")])
def test_alta_de_articulo_no_persiste_factor_no_valido(catalogo_uom, factor):
    """The item writer rejects invalid factors without leaving item or conversion rows."""
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.database import Item, ItemUOMConversion
        from cacao_accounting.inventario.service import InventoryServiceError, create_item_with_uoms

        with pytest.raises(InventoryServiceError):
            create_item_with_uoms(_item_params(factor), code="ITEM-UOM-INVALIDO")
        database.session.rollback()

        assert database.session.get(Item, "ITEM-UOM-INVALIDO") is None
        assert (
            database.session.execute(
                database.select(ItemUOMConversion).filter_by(item_code="ITEM-UOM-INVALIDO")
            ).scalar_one_or_none()
            is None
        )


def test_conversion_persistida_no_finita_falla_de_forma_controlada(catalogo_uom):
    """Un factor Infinity ya guardado no produce una cantidad infinita silenciosa."""
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.database import ItemUOMConversion
        from cacao_accounting.inventario.service import InventoryServiceError, convert_item_qty

        database.session.add(
            ItemUOMConversion(item_code=ITEM, from_uom=CAJA, to_uom="UND", conversion_factor=Decimal("Infinity"))
        )
        database.session.commit()

        with pytest.raises(InventoryServiceError):
            convert_item_qty(ITEM, Decimal("1"), CAJA, "UND")


def test_conversion_finita_directa_e_inversa_operan(catalogo_uom):
    """Control positivo: la guarda nueva no altera conversiones válidas."""
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.database import ItemUOMConversion
        from cacao_accounting.inventario.service import convert_item_qty, item_qty_in_base_uom

        database.session.add(ItemUOMConversion(item_code=ITEM, from_uom=CAJA, to_uom="UND", conversion_factor=Decimal("12")))
        database.session.commit()

        assert convert_item_qty(ITEM, Decimal("2"), CAJA, "UND") == Decimal("24")
        assert convert_item_qty(ITEM, Decimal("24"), "UND", CAJA) == Decimal("2")
        assert item_qty_in_base_uom(ITEM, Decimal("3"), CAJA) == Decimal("36")


@pytest.mark.parametrize("factor", [Decimal("0"), Decimal("-12"), Decimal("0.0000000001")])
def test_validacion_rechaza_factor_cero_negativo_o_no_representable(catalogo_uom, factor):
    """Zero, negative, or rounded-to-zero factors cannot be stored as conversions."""
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.inventario.service import (
            InventoryServiceError,
            ItemUOMRow,
            validate_item_uom_rows,
        )

        with pytest.raises(InventoryServiceError):
            validate_item_uom_rows("UND", [ItemUOMRow(uom_code=CAJA, conversion_factor=factor)])


@pytest.mark.parametrize("factor", [Decimal("0"), Decimal("-12")])
def test_conversion_persistida_cero_o_negativa_falla_en_ambas_direcciones(catalogo_uom, factor):
    """#1034: la guarda cubre la conversión directa y la inversa por igual.

    La fila se inserta directamente para simular datos heredados o de API que
    eludieron el alta; leerla no debe producir cantidades anuladas ni con signo
    invertido en ninguna de las dos direcciones.
    """
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.database import ItemUOMConversion
        from cacao_accounting.inventario.service import InventoryServiceError, convert_item_qty

        database.session.add(ItemUOMConversion(item_code=ITEM, from_uom=CAJA, to_uom="UND", conversion_factor=factor))
        database.session.commit()

        with pytest.raises(InventoryServiceError):
            convert_item_qty(ITEM, Decimal("2"), CAJA, "UND")
        with pytest.raises(InventoryServiceError):
            convert_item_qty(ITEM, Decimal("24"), "UND", CAJA)


@pytest.mark.parametrize("factor", [Decimal("0.000000001"), Decimal("99999999999.999999999")])
def test_factor_en_limites_de_precision_puede_validarse(catalogo_uom, factor):
    """Finite positive factors representable by Numeric(20, 9) remain accepted."""
    application = catalogo_uom
    with application.app_context():
        from cacao_accounting.inventario.service import ItemUOMRow, validate_item_uom_rows

        validate_item_uom_rows("UND", [ItemUOMRow(uom_code=CAJA, conversion_factor=factor)])
