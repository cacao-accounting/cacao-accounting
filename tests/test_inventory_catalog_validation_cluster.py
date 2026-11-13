# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación de catálogos y seriales de inventario.

Escenario de negocio (paraguas #1717):
- #1736: UOM y bodega persistían aunque WTForms fallara.
- #1747: los selectores de UOM de compra/venta no tenían choices.
- #1829: un serial de otro artículo terminaba en IntegrityError.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    SerialNumber,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.inventario.service import InventoryServiceError, update_serial_state, validate_batch_serial


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
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                UOM(code="EA", name="Unidad", is_active=True),
                UOM(code="BOX", name="Caja", is_active=True),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Item(
                    code="A",
                    name="Artículo A",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="EA",
                    has_serial_no=True,
                ),
                Item(
                    code="B",
                    name="Artículo B",
                    item_type="goods",
                    is_stock_item=True,
                    default_uom="EA",
                    has_serial_no=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            SerialNumber(item_code="A", serial_no="SN-1", serial_status="available"),
        )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_uom_no_persiste_si_el_formulario_falla():
    """#1736: código/nombre vacíos no crean una UOM."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/inventory/uom/new", data={"code": "", "name": ""})

        assert respuesta.status_code == 200
        with application.app_context():
            assert database.session.execute(database.select(UOM).filter_by(code="")).scalar_one_or_none() is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_bodega_no_persiste_si_el_formulario_falla():
    """#1736: el mismo guard aplica al alta de bodega."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/inventory/warehouse/new", data={"code": "", "name": ""})

        assert respuesta.status_code == 200
        with application.app_context():
            assert database.session.execute(database.select(Warehouse)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_articulo_guarda_las_uom_comerciales():
    """#1747: compra y venta aceptan las UOM del catálogo."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/inventory/item/new",
            data={
                "name": "Artículo comercial",
                "item_type": "goods",
                "is_stock_item": "on",
                "is_purchase_item": "on",
                "is_sale_item": "on",
                "default_uom": "EA",
                "purchase_uom": "BOX",
                "sale_uom": "BOX",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            item = database.session.execute(database.select(Item).filter_by(name="Artículo comercial")).scalar_one()
            assert item.default_uom == "EA"
            assert item.purchase_uom == "BOX"
            assert item.sale_uom == "BOX"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_serial_de_otro_articulo_se_rechaza_en_validacion():
    """#1829: la validación usa la unicidad global del serial."""
    application = _crear_app()
    try:
        with application.app_context():
            linea = SimpleNamespace(item_code="B", serial_no="SN-1", qty_in_base_uom=None, qty=1)
            with pytest.raises(InventoryServiceError, match="otro artículo"):
                validate_batch_serial(linea, outgoing=False)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_serial_de_otro_articulo_se_rechaza_al_actualizar():
    """#1829: la actualización tampoco intenta insertar un duplicado global."""
    application = _crear_app()
    try:
        with application.app_context():
            linea = SimpleNamespace(item_code="B", serial_no="SN-1")
            with pytest.raises(InventoryServiceError, match="otro artículo"):
                update_serial_state(linea, outgoing=False, warehouse="WH-1")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
