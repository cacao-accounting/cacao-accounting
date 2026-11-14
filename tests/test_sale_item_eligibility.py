# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión #2124: los artículos deben estar activos y habilitados para venta en todo el O2C."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    database,
)

FECHA = date(2026, 5, 15)
MENSAJE_NO_VENDIBLE = "no está habilitado para venta"


@dataclass(frozen=True)
class EspecificacionAlta:
    """Describe el alta manual de un documento O2C desde su formulario."""

    documento: str
    ruta: str
    lineas: type
    clave_foranea: str
    cabecera: type
    datos_extra: dict[str, str]

    @property
    def redirige_al_fallar(self) -> bool:
        """La factura redirige al detalle revertido en lugar de re-renderizar el formulario."""
        return self.documento == "factura de venta"


ESPECIFICACIONES = [
    pytest.param(
        EspecificacionAlta(
            documento="pedido de venta",
            ruta="/sales/sales-request/new",
            lineas=SalesRequestItem,
            clave_foranea="sales_request_id",
            cabecera=SalesRequest,
            datos_extra={},
        ),
        id="sales_request",
    ),
    pytest.param(
        EspecificacionAlta(
            documento="orden de venta",
            ruta="/sales/sales-order/new",
            lineas=SalesOrderItem,
            clave_foranea="sales_order_id",
            cabecera=SalesOrder,
            datos_extra={"warehouse": "BOD01"},
        ),
        id="sales_order",
    ),
    pytest.param(
        EspecificacionAlta(
            documento="cotización de venta",
            ruta="/sales/quotation/new",
            lineas=SalesQuotationItem,
            clave_foranea="sales_quotation_id",
            cabecera=SalesQuotation,
            datos_extra={},
        ),
        id="sales_quotation",
    ),
    pytest.param(
        EspecificacionAlta(
            documento="nota de entrega",
            ruta="/sales/delivery-note/new",
            lineas=DeliveryNoteItem,
            clave_foranea="delivery_note_id",
            cabecera=DeliveryNote,
            datos_extra={"from_warehouse": "BOD01"},
        ),
        id="delivery_note",
    ),
    pytest.param(
        EspecificacionAlta(
            documento="factura de venta",
            ruta="/sales/sales-invoice/new",
            lineas=SalesInvoiceItem,
            clave_foranea="sales_invoice_id",
            cabecera=SalesInvoice,
            datos_extra={},
        ),
        id="sales_invoice",
    ),
]


def _datos_formulario(entorno_contable, especificacion: EspecificacionAlta, item_code: str, marcador: str) -> dict[str, str]:
    """Construye el POST de alta manual con una única línea del artículo indicado."""
    with entorno_contable.app.app_context():
        cliente_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
    datos: dict[str, str] = {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": cliente_id,
        "remarks": marcador,
        "item_code_0": item_code,
        "item_name_0": "Linea de prueba",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
    }
    datos.update(especificacion.datos_extra)
    return datos


def _crear_item_no_vendible(entorno_contable, *, activo: bool, vendible: bool) -> str:
    """Crea un artículo con código único y devuelve su código."""
    with entorno_contable.app.app_context():
        item = Item(
            code=f"NOVTA-{uuid4().hex[:10]}",
            name="Articulo no vendible",
            item_type="goods",
            is_stock_item=False,
            default_uom="UND",
            is_active=activo,
            is_sale_item=vendible,
        )
        database.session.add(item)
        database.session.commit()
        return item.code


def _flash_del_cliente(cliente) -> str:
    """Devuelve los mensajes flash pendientes en la sesión del cliente indicado."""
    with cliente.session_transaction() as sesion:
        mensajes = " ".join(str(mensaje) for _, mensaje in sesion.get("_flashes", []))
        sesion["_flashes"] = []
    return mensajes


@pytest.mark.parametrize("especificacion", ESPECIFICACIONES)
@pytest.mark.parametrize("vendible,activo", [(False, True), (True, False)], ids=["sin_rol_venta", "inactivo"])
def test_alta_manual_rechaza_articulo_no_vendible(entorno_contable, authenticated_client, especificacion, vendible, activo):
    """Un artículo inactivo o sin rol de venta produce error controlado y no persiste el documento (#2124)."""
    app = entorno_contable.app
    codigo_item = _crear_item_no_vendible(entorno_contable, activo=activo, vendible=vendible)
    marcador = f"ALTA-RECHAZADA-{uuid4().hex[:10]}"
    formulario = _datos_formulario(entorno_contable, especificacion, codigo_item, marcador)

    cliente = authenticated_client()
    respuesta = cliente.post(especificacion.ruta, data=formulario)

    if especificacion.redirige_al_fallar:
        assert respuesta.status_code == 302, "La factura debe responder con una redirección controlada, nunca 500."
        # El flash queda pendiente porque el destino redirigido ya no existe; se lee de la sesión.
        mensaje_flash = _flash_del_cliente(cliente)
    else:
        assert respuesta.status_code == 200, "El alta manual debe responder con el formulario y un error controlado."
        # El re-render consume el flash y lo pinta en el cuerpo de la respuesta.
        mensaje_flash = respuesta.get_data(as_text=True)
    assert MENSAJE_NO_VENDIBLE in mensaje_flash, "El error debe informar que el artículo no está habilitado para venta."

    with app.app_context():
        documentos = database.session.execute(
            select(func.count()).select_from(especificacion.cabecera).where(especificacion.cabecera.remarks == marcador)
        ).scalar_one()
        lineas = database.session.execute(
            select(func.count()).select_from(especificacion.lineas).where(especificacion.lineas.item_code == codigo_item)
        ).scalar_one()
    assert documentos == 0, "Ningún documento debe persistirse cuando el artículo no es vendible."
    assert lineas == 0, "Ninguna línea debe persistirse cuando el artículo no es vendible."


@pytest.mark.parametrize("especificacion", ESPECIFICACIONES)
def test_alta_manual_acepta_articulo_vendible_y_activo(entorno_contable, authenticated_client, especificacion):
    """Control positivo: un artículo vendible y activo permite crear el documento (#2124)."""
    app = entorno_contable.app
    marcador = f"ALTA-ACEPTADA-{uuid4().hex[:10]}"
    formulario = _datos_formulario(entorno_contable, especificacion, "ART01", marcador)

    respuesta = authenticated_client().post(especificacion.ruta, data=formulario)

    assert respuesta.status_code == 302, "El control positivo debe crear el documento y redirigir a su detalle."
    with app.app_context():
        documento = database.session.execute(
            select(especificacion.cabecera).where(especificacion.cabecera.remarks == marcador)
        ).scalar_one()
        assert documento is not None
        linea = database.session.execute(
            select(especificacion.lineas).where(getattr(especificacion.lineas, especificacion.clave_foranea) == documento.id)
        ).scalar_one()
        assert linea is not None
        assert linea.item_code == "ART01"
        assert Decimal(str(linea.qty)) == Decimal("1")
