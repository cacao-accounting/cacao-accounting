# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cotización, entrega y factura solo aceptan artículos vendibles.

Escenario de negocio (issue #2124): a diferencia de solicitud y orden, los
tres guardadores restantes no comprobaban ``Item.is_active`` ni
``Item.is_sale_item``. Un POST manual podía crear y contabilizar una venta con
un artículo deshabilitado o inactivo.
"""

from __future__ import annotations

from datetime import date

import pytest
from flask_login import login_user
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DeliveryNote,
    Entity,
    Item,
    Modules,
    SalesInvoice,
    SalesQuotation,
    UOM,
    User,
    Warehouse,
    database,
)
from cacao_accounting.ventas.services import (
    _save_delivery_note_items,
    _save_sales_invoice_items,
    _save_sales_quotation_items,
)

FECHA = date(2026, 10, 15)


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
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.add_all(
            [
                UOM(code="Unidad", name="Unidad"),
                Warehouse(code="ALM-1", name="Almacén", company="cacao"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
                Item(
                    code="SALE-1",
                    name="Vendible",
                    item_type="goods",
                    is_stock_item=False,
                    is_sale_item=True,
                    is_active=True,
                    default_uom="Unidad",
                ),
                Item(
                    code="NO-SALE",
                    name="No vendible",
                    item_type="goods",
                    is_stock_item=False,
                    is_sale_item=False,
                    is_active=True,
                    default_uom="Unidad",
                ),
                Item(
                    code="INACTIVE",
                    name="Inactivo",
                    item_type="goods",
                    is_stock_item=False,
                    is_sale_item=True,
                    is_active=False,
                    default_uom="Unidad",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        cotizacion = SalesQuotation(company="cacao", posting_date=FECHA, docstatus=0, transaction_currency="NIO")
        entrega = DeliveryNote(company="cacao", posting_date=FECHA, docstatus=0, transaction_currency="NIO")
        factura = SalesInvoice(company="cacao", posting_date=FECHA, docstatus=0, transaction_currency="NIO")
        database.session.add_all([cotizacion, entrega, factura])
        database.session.commit()
        ids = {"cotizacion": cotizacion.id, "entrega": entrega.id, "factura": factura.id}
    return application, ids


def _datos(item_code: str) -> dict[str, str]:
    return {
        "item_code_0": item_code,
        "item_name_0": "Línea",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "Unidad",
        "warehouse": "ALM-1",
    }


def _casos(ids: dict[str, str]):
    return (
        (_save_sales_quotation_items, ids["cotizacion"]),
        (_save_delivery_note_items, ids["entrega"]),
        (_save_sales_invoice_items, ids["factura"]),
    )


@pytest.mark.parametrize("item_code", ["NO-SALE", "INACTIVE"])
def test_las_tres_lineas_rechazan_articulos_no_vendibles(item_code):
    """La elegibilidad comercial se valida antes de persistir cualquier línea."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            admin = database.session.get(User, "admin")
            for guardar, documento_id in _casos(ids):
                with application.test_request_context("/", method="POST", data=_datos(item_code)):
                    login_user(admin)
                    with pytest.raises(ValueError, match="no está habilitado para venta"):
                        guardar(documento_id)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_las_tres_lineas_aceptan_un_articulo_vendible():
    """El control positivo conserva el alta normal de líneas."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            admin = database.session.get(User, "admin")
            for guardar, documento_id in _casos(ids):
                with application.test_request_context("/", method="POST", data=_datos("SALE-1")):
                    login_user(admin)
                    total_qty, total = guardar(documento_id)
                assert total_qty == 1
                assert total == 10
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
