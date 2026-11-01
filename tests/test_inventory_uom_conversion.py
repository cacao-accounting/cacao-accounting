# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Conversiones de UOM por artículo: guardas de factor.

Escenario de negocio (issue #1034): una conversión directa con factor
cero anula la cantidad (qty × 0 = 0) y un factor negativo invierte el
signo del saldo; un registro migrado por API con factor inválido no
debe permitir salidas sin respaldo de stock. La guarda de la inversa
debe aplicar también a la directa y a los factores no positivos.
"""

from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

CAJA = "CAJA-12"
CAJA_POR_UNIDADES = Decimal("12")
CANTIDAD = Decimal("5")


@pytest.fixture
def almacen_conversiones():
    """Aplicación con artículo y conversiones directas e inversas sembradas."""
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
        from cacao_accounting.database import Entity, Item, UOM

        database.session.add_all(
            [
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
                Item(
                    code="CHOCOLATE-100G",
                    name="Chocolate 100g",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="UND",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _conversion_factor(application, desde: str, hacia: str, factor: Decimal) -> None:
    """Siembra la conversión directa que registra el operador o la migración."""
    from cacao_accounting.database import ItemUOMConversion, database

    with application.app_context():
        database.session.add(
            ItemUOMConversion(
                item_code="CHOCOLATE-100G",
                from_uom=desde,
                to_uom=hacia,
                conversion_factor=factor,
            )
        )
        database.session.commit()


def _convertir(application, cantidad: Decimal, desde: str, hacia: str):
    with application.app_context():
        from cacao_accounting.inventario.service import convert_item_qty

        return convert_item_qty("CHOCOLATE-100G", cantidad, desde, hacia)


def test_conversión_directa_con_factor_cero_se_rechaza(almacen_conversiones):
    """Regresión del issue: qty × 0 no silencia la cantidad en salida."""
    application = almacen_conversiones
    _conversion_factor(application, CAJA, "UND", Decimal("0"))
    with pytest.raises(Exception) as excinfo:
        _convertir(application, CANTIDAD, CAJA, "UND")
    assert "factor positivo" in str(excinfo.value)


def test_conversión_directa_con_factor_negativo_se_rechaza(almacen_conversiones):
    """Un factor negativo invierte el signo del saldo requisitados."""
    application = almacen_conversiones
    _conversion_factor(application, CAJA, "UND", Decimal("-12"))
    with pytest.raises(Exception) as excinfo:
        _convertir(application, CANTIDAD, CAJA, "UND")
    assert "factor positivo" in str(excinfo.value)


def test_conversión_inversa_con_factor_cero_y_negativo_se_rechazan(almacen_conversiones):
    """La guardia histórica de la inversa sigue aplicando y se extiende a negativos."""
    application = almacen_conversiones
    _conversion_factor(application, "UND", CAJA, Decimal("0"))
    with pytest.raises(Exception) as excinfo:
        _convertir(application, CANTIDAD, CAJA, "UND")
    assert "factor positivo" in str(excinfo.value)

    _actualizar_factor(application, "UND", CAJA, Decimal("-12"))
    with pytest.raises(Exception) as excinfo:
        _convertir(application, CANTIDAD, CAJA, "UND")
    assert "factor positivo" in str(excinfo.value)


def _actualizar_factor(application, desde: str, hacia: str, factor: Decimal) -> None:
    """Corrige en sitio el factor de una conversión (operación admitida por proveedor/Migración)."""
    from cacao_accounting.database import database, ItemUOMConversion

    with application.app_context():
        registro = database.session.execute(
            database.select(ItemUOMConversion).filter_by(item_code="CHOCOLATE-100G", from_uom=desde, to_uom=hacia)
        ).scalar_one()
        registro.conversion_factor = factor
        database.session.commit()


def test_conversiones_positivas_directa_e_inversa_operan(almacen_conversiones):
    """Control positivo de negocio: caja a 12 unidades y viceversa."""
    application = almacen_conversiones
    _conversion_factor(application, CAJA, "UND", CAJA_POR_UNIDADES)
    assert _convertir(application, Decimal("2"), CAJA, "UND") == Decimal("24")
    assert _convertir(application, Decimal("24"), "UND", CAJA) == Decimal("2")
