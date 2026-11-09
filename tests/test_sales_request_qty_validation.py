# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Cantidad no positiva en líneas de venta.

Escenario de negocio (issue #2057): el formulario permitía enviar ``qty=0`` y
la constraint ``ck_sri_qty_positive`` se violaba en el ``flush``. El usuario
recibía un HTTP 500 en lugar de un error de validación traducible, y el
documento no debía persistirse parcialmente. La misma invariante aplica a las
cinco líneas de venta con constraint de cantidad positiva; el backend debe
rechazarlas antes de tocar la base.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DeliveryNote,
    Entity,
    Item,
    Modules,
    Party,
    SalesInvoice,
    SalesOrder,
    SalesQuotation,
    SalesRequest,
    SalesRequestItem,
    UOM,
    User,
    database,
)

FECHA = date(2026, 10, 15)


@pytest.fixture
def ventas_desktop():
    """App Desktop con un artículo vendible y un cliente."""
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
        cliente = Party(code="CLI-1", name="Cliente Uno", is_customer=True)
        database.session.add_all(
            [
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
                Modules(module="sales", default=False, enabled=True),
                UOM(code="Unidad", name="Unidad"),
                Item(
                    code="ART-1",
                    name="Artículo vendible",
                    item_type="goods",
                    is_stock_item=False,
                    is_sale_item=True,
                    default_uom="Unidad",
                ),
                cliente,
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
        database.session.commit()
        yield application, {"cliente": cliente.id}
        database.session.remove()
        database.engine.dispose()


def _cliente_autenticado(application) -> object:
    """Cliente HTTP con sesión iniciada como el administrador de escritorio."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _payload(cliente_id: str, qty: str) -> dict[str, str]:
    return {
        "company": "cacao",
        "customer_id": cliente_id,
        "posting_date": FECHA.isoformat(),
        "transaction_currency": "NIO",
        "item_code_0": "ART-1",
        "item_name_0": "Artículo vendible",
        "qty_0": qty,
        "rate_0": "10",
        "uom_0": "Unidad",
    }


@pytest.mark.parametrize("qty", ["0", "-1", "-0.0001"])
def test_rechaza_cantidad_no_positiva_sin_error_500(ventas_desktop, qty):
    """Una cantidad no positiva se rechaza con error de formulario y sin persistir."""
    application, ids = ventas_desktop
    client = _cliente_autenticado(application)

    response = client.post("/sales/sales-request/new", data=_payload(ids["cliente"], qty))

    assert response.status_code == 200
    assert "mayor a cero" in response.get_data(as_text=True)
    with application.app_context():
        assert database.session.execute(database.select(SalesRequest)).scalars().all() == []
        assert database.session.execute(database.select(SalesRequestItem)).scalars().all() == []


def test_acepta_cantidad_positiva(ventas_desktop):
    """El control positivo conserva el alta normal del pedido."""
    application, ids = ventas_desktop
    client = _cliente_autenticado(application)

    response = client.post("/sales/sales-request/new", data=_payload(ids["cliente"], "2"))

    assert response.status_code == 302
    with application.app_context():
        pedidos = database.session.execute(database.select(SalesRequest)).scalars().all()
        assert len(pedidos) == 1
        lineas = database.session.execute(database.select(SalesRequestItem)).scalars().all()
        assert len(lineas) == 1
        assert lineas[0].qty == 2
        assert lineas[0].amount == 20


def test_las_demas_lineas_de_venta_rechazan_cantidad_cero(ventas_desktop):
    """La invariante se aplica a orden, cotización, nota de entrega y factura."""
    from cacao_accounting.ventas.services import (
        _save_delivery_note_items,
        _save_sales_invoice_items,
        _save_sales_order_items,
        _save_sales_quotation_items,
    )

    application, ids = ventas_desktop
    with application.app_context():
        documento = {
            SalesOrder: ("sales_order_id", "SO-1"),
            SalesQuotation: ("sales_quotation_id", "SQ-1"),
            DeliveryNote: ("delivery_note_id", "DN-1"),
            SalesInvoice: ("sales_invoice_id", "INV-1"),
        }
        creados = {}
        for modelo, (_, numero) in documento.items():
            registro = modelo(company="cacao", posting_date=FECHA, docstatus=0, document_no=numero)
            database.session.add(registro)
            database.session.flush()
            creados[modelo] = registro.id
        database.session.commit()

        datos = {
            "item_code_0": "ART-1",
            "item_name_0": "Artículo vendible",
            "qty_0": "0",
            "rate_0": "10",
            "uom_0": "Unidad",
            "warehouse": "ALM-1",
        }
        casos = (
            (_save_sales_order_items, creados[SalesOrder]),
            (_save_sales_quotation_items, creados[SalesQuotation]),
            (_save_delivery_note_items, creados[DeliveryNote]),
            (_save_sales_invoice_items, creados[SalesInvoice]),
        )
        for guardar, identificador in casos:
            with application.test_request_context("/", method="POST", data=datos):
                with pytest.raises(Exception) as error:
                    guardar(identificador)
                assert getattr(error.value, "status_code", 400) == 400
                assert "mayor a cero" in str(error.value)
