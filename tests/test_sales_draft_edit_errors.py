# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Una edición inválida no termina en HTTP 500.

Escenario de negocio (issue #2126): los handlers de edición eliminaban las
líneas y llamaban al guardador sin capturar DocumentFlowError. Un POST sin
líneas producía 500; con rollback explícito debe volver al documento y
conservar las líneas originales.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    Entity,
    Item,
    Modules,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    UOM,
    User,
    database,
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
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="Unidad", name="Unidad"),
                Item(
                    code="ART-1",
                    name="Artículo",
                    item_type="goods",
                    is_stock_item=False,
                    is_sale_item=True,
                    is_active=True,
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
        solicitud = SalesRequest(company="cacao", posting_date=FECHA, docstatus=0, transaction_currency="NIO")
        orden = SalesOrder(company="cacao", posting_date=FECHA, docstatus=0, transaction_currency="NIO")
        cotizacion = SalesQuotation(company="cacao", posting_date=FECHA, docstatus=0, transaction_currency="NIO")
        entrega = DeliveryNote(company="cacao", posting_date=FECHA, docstatus=0, transaction_currency="NIO")
        database.session.add_all([solicitud, orden, cotizacion, entrega])
        database.session.flush()
        database.session.add_all(
            [
                SalesRequestItem(sales_request_id=solicitud.id, item_code="ART-1", qty=1, rate=10, amount=10, uom="Unidad"),
                SalesOrderItem(sales_order_id=orden.id, item_code="ART-1", qty=1, rate=10, amount=10, uom="Unidad"),
                SalesQuotationItem(
                    sales_quotation_id=cotizacion.id, item_code="ART-1", qty=1, rate=10, amount=10, uom="Unidad"
                ),
                DeliveryNoteItem(
                    delivery_note_id=entrega.id,
                    item_code="ART-1",
                    qty=1,
                    rate=10,
                    amount=10,
                    uom="Unidad",
                    warehouse="ALM-1",
                ),
            ]
        )
        database.session.commit()
        ids = {
            "solicitud": solicitud.id,
            "orden": orden.id,
            "cotizacion": cotizacion.id,
            "entrega": entrega.id,
        }
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _conteos(application) -> tuple[int, int, int, int]:
    return (
        len(database.session.execute(database.select(SalesRequestItem)).scalars().all()),
        len(database.session.execute(database.select(SalesOrderItem)).scalars().all()),
        len(database.session.execute(database.select(SalesQuotationItem)).scalars().all()),
        len(database.session.execute(database.select(DeliveryNoteItem)).scalars().all()),
    )


def test_las_cuatro_ediciones_rechazan_sin_lineas_sin_500():
    """El error de dominio redirige y el rollback conserva las líneas."""
    application, ids = _crear_app()
    rutas = (
        f"/sales/sales-request/{ids['solicitud']}/edit",
        f"/sales/sales-order/{ids['orden']}/edit",
        f"/sales/sales-quotation/{ids['cotizacion']}/edit",
        f"/sales/delivery-note/{ids['entrega']}/edit",
    )
    try:
        client = _cliente(application)
        for ruta in rutas:
            respuesta = client.post(ruta, data={"company": "cacao", "posting_date": FECHA.isoformat()})
            assert respuesta.status_code == 302, ruta
            with client.session_transaction() as session:
                flashes = session.get("_flashes", [])
            assert any("al menos una línea" in mensaje for _categoria, mensaje in flashes), ruta

        with application.app_context():
            assert _conteos(application) == (1, 1, 1, 1)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
