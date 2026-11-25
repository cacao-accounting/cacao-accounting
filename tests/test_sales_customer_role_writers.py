# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2056: los writers de O2C exigen un cliente vigente en la compañía del documento."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    CompanyParty,
    DeliveryNote,
    DeliveryNoteItem,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    User,
    database,
)

FECHA = date(2026, 5, 15)
MENSAJE_ROL = "no está habilitado como cliente"
MENSAJE_COMPANIA = "no está habilitado para la compañía seleccionada"


@dataclass(frozen=True)
class EspecificacionWriter:
    """Describe un writer O2C y sus rutas HTTP reales."""

    documento: str
    modelo: Any
    lineas: Any
    clave_linea: str
    ruta_alta: str
    ruta_edicion: str
    ruta_duplicacion: str
    con_bodega: bool = False
    estado_alta_rechazada: int = 200
    mensaje_alta_en_flash: bool = False


ESPECIFICACIONES = [
    pytest.param(
        EspecificacionWriter(
            documento="pedido de venta",
            modelo=SalesRequest,
            lineas=SalesRequestItem,
            clave_linea="sales_request_id",
            ruta_alta="/sales/sales-request/new",
            ruta_edicion="/sales/sales-request/{id}/edit",
            ruta_duplicacion="/sales/sales-request/{id}/duplicate",
        ),
        id="sales_request",
    ),
    pytest.param(
        EspecificacionWriter(
            documento="cotización de venta",
            modelo=SalesQuotation,
            lineas=SalesQuotationItem,
            clave_linea="sales_quotation_id",
            ruta_alta="/sales/quotation/new",
            ruta_edicion="/sales/sales-quotation/{id}/edit",
            ruta_duplicacion="/sales/sales-quotation/{id}/duplicate",
        ),
        id="sales_quotation",
    ),
    pytest.param(
        EspecificacionWriter(
            documento="orden de venta",
            modelo=SalesOrder,
            lineas=SalesOrderItem,
            clave_linea="sales_order_id",
            ruta_alta="/sales/sales-order/new",
            ruta_edicion="/sales/sales-order/{id}/edit",
            ruta_duplicacion="/sales/sales-order/{id}/duplicate",
            con_bodega=True,
        ),
        id="sales_order",
    ),
    pytest.param(
        EspecificacionWriter(
            documento="factura de venta",
            modelo=SalesInvoice,
            lineas=SalesInvoiceItem,
            clave_linea="sales_invoice_id",
            ruta_alta="/sales/sales-invoice/new",
            ruta_edicion="/sales/sales-invoice/{id}/edit",
            ruta_duplicacion="/sales/sales-invoice/{id}/duplicate",
            estado_alta_rechazada=302,
            mensaje_alta_en_flash=True,
        ),
        id="sales_invoice",
    ),
    pytest.param(
        EspecificacionWriter(
            documento="nota de entrega",
            modelo=DeliveryNote,
            lineas=DeliveryNoteItem,
            clave_linea="delivery_note_id",
            ruta_alta="/sales/delivery-note/new",
            ruta_edicion="/sales/delivery-note/{id}/edit",
            ruta_duplicacion="/sales/delivery-note/{id}/duplicate",
            con_bodega=True,
        ),
        id="delivery_note",
    ),
]


def _cliente_http(application):
    """Devuelve un cliente autenticado como administrador para la app indicada."""
    with application.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        user_id = str(admin.id)
        auth_version = admin.auth_version
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


@pytest.fixture
def terceros(entorno_contable_aislado):
    """Siembra un proveedor válido, un cliente inactivo y un cliente sin vínculo."""
    application = entorno_contable_aislado.app
    sufijo = uuid4().hex[:8]
    with application.app_context():
        proveedor = Party(
            code=f"PRV-2056-{sufijo}",
            name=f"Proveedor {sufijo}",
            is_supplier=True,
            is_customer=False,
            is_active=True,
        )
        inactivo = Party(
            code=f"CLI-INA-{sufijo}",
            name=f"Cliente inactivo {sufijo}",
            is_customer=True,
            is_active=False,
        )
        sin_vinculo = Party(
            code=f"CLI-SIN-{sufijo}",
            name=f"Cliente sin vínculo {sufijo}",
            is_customer=True,
            is_active=True,
        )
        database.session.add_all([proveedor, inactivo, sin_vinculo])
        database.session.flush()
        database.session.add(CompanyParty(company="cacao", party_id=proveedor.id, is_active=True))
        database.session.add(CompanyParty(company="cacao", party_id=inactivo.id, is_active=True))
        database.session.commit()
        return {
            "proveedor": proveedor.id,
            "inactivo": inactivo.id,
            "sin_vinculo": sin_vinculo.id,
        }


def _crear_borrador(entorno, especificacion: EspecificacionWriter, customer_id: str, marcador: str) -> tuple[str, str]:
    """Crea un borrador con una línea para ejercer edición o duplicación."""
    with entorno.app.app_context():
        documento = especificacion.modelo(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            customer_id=customer_id,
            customer_name="Tercero histórico",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=marcador,
        )
        database.session.add(documento)
        database.session.flush()
        datos_linea = {
            especificacion.clave_linea: documento.id,
            "item_code": "ART01",
            "item_name": "Articulo Comercial",
            "qty": Decimal("2"),
            "qty_in_base_uom": Decimal("2"),
            "uom": "UND",
            "rate": Decimal("10"),
            "amount": Decimal("20"),
        }
        if especificacion.con_bodega:
            datos_linea["warehouse"] = "BOD01"
        linea = especificacion.lineas(**datos_linea)
        database.session.add(linea)
        database.session.commit()
        return documento.id, linea.id


def _mensajes(cliente) -> str:
    """Devuelve los mensajes flash pendientes del cliente indicado."""
    with cliente.session_transaction() as sesion:
        return " ".join(str(mensaje) for _, mensaje in sesion.get("_flashes", []))


@pytest.mark.parametrize("especificacion", ESPECIFICACIONES)
def test_alta_rechaza_proveedor(entorno_contable_aislado, terceros, especificacion):
    """Ningún writer persiste un documento cuyo cliente es solo proveedor."""
    marcador = f"ALTA-{uuid4().hex[:10]}"
    cliente = _cliente_http(entorno_contable_aislado.app)
    datos = {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": terceros["proveedor"],
        "remarks": marcador,
    }
    if especificacion.con_bodega:
        datos["warehouse"] = "BOD01"

    respuesta = cliente.post(especificacion.ruta_alta, data=datos)

    assert respuesta.status_code == especificacion.estado_alta_rechazada
    cuerpo = _mensajes(cliente) if especificacion.mensaje_alta_en_flash else respuesta.get_data(as_text=True)
    assert MENSAJE_ROL in cuerpo
    with entorno_contable_aislado.app.app_context():
        assert (
            database.session.execute(
                database.select(especificacion.modelo).filter_by(customer_id=terceros["proveedor"])
            ).scalar_one_or_none()
            is None
        )


@pytest.mark.parametrize("clave, mensaje", [("inactivo", MENSAJE_ROL), ("sin_vinculo", MENSAJE_COMPANIA)])
def test_alta_rechaza_cliente_no_vigente(entorno_contable_aislado, terceros, clave, mensaje):
    """La política exige cliente activo y vinculado a la compañía del documento."""
    cliente = _cliente_http(entorno_contable_aislado.app)
    respuesta = cliente.post(
        "/sales/sales-request/new",
        data={
            "company": "cacao",
            "currency": "NIO",
            "posting_date": FECHA.isoformat(),
            "customer_id": terceros[clave],
        },
    )

    assert respuesta.status_code == 200
    assert mensaje in respuesta.get_data(as_text=True)
    with entorno_contable_aislado.app.app_context():
        assert (
            database.session.execute(database.select(SalesRequest).filter_by(customer_id=terceros[clave])).scalar_one_or_none()
            is None
        )


@pytest.mark.parametrize("especificacion", ESPECIFICACIONES)
def test_edicion_rechaza_proveedor_y_conserva_documento(entorno_contable_aislado, terceros, especificacion):
    """Editar con un proveedor no muta la cabecera ni borra las líneas originales."""
    marcador = f"EDICION-{uuid4().hex[:10]}"
    documento_id, item_code = _crear_borrador(entorno_contable_aislado, especificacion, terceros["proveedor"], marcador)
    cliente = _cliente_http(entorno_contable_aislado.app)

    respuesta = cliente.post(
        especificacion.ruta_edicion.format(id=documento_id),
        data={
            "company": "cacao",
            "posting_date": "2026-05-16",
            "customer_id": terceros["proveedor"],
            "remarks": marcador,
        },
    )

    assert respuesta.status_code == 302
    assert MENSAJE_ROL in _mensajes(cliente)
    with entorno_contable_aislado.app.app_context():
        documento = database.session.get(especificacion.modelo, documento_id)
        assert documento.customer_name == "Tercero histórico"
        assert documento.posting_date == FECHA
        assert database.session.get(especificacion.lineas, item_code) is not None


@pytest.mark.parametrize("especificacion", ESPECIFICACIONES)
def test_duplicacion_rechaza_proveedor(entorno_contable_aislado, terceros, especificacion):
    """Duplicar un borrador no reintroduce un cliente que ya no tiene el rol."""
    marcador = f"DUPLICAR-{uuid4().hex[:10]}"
    documento_id, _item_code = _crear_borrador(entorno_contable_aislado, especificacion, terceros["proveedor"], marcador)
    cliente = _cliente_http(entorno_contable_aislado.app)

    respuesta = cliente.post(especificacion.ruta_duplicacion.format(id=documento_id))

    assert respuesta.status_code == 302
    assert MENSAJE_ROL in _mensajes(cliente)
    with entorno_contable_aislado.app.app_context():
        documentos = (
            database.session.execute(database.select(especificacion.modelo).filter_by(customer_id=terceros["proveedor"]))
            .scalars()
            .all()
        )
        assert [documento.id for documento in documentos] == [documento_id]
