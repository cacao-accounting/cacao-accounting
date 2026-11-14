# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión #2126: edición O2C sin líneas responde controlado y conserva las líneas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    Party,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    database,
)

FECHA = date(2026, 5, 15)
MENSAJE_SIN_LINEAS = "El documento requiere al menos una línea."


@dataclass(frozen=True)
class EspecificacionEdicion:
    """Describe un documento O2C editable y su ruta de edición."""

    documento: str
    modelo: type
    lineas: type
    clave_foranea: str
    ruta_edicion: str
    con_bodega: bool = False


ESPECIFICACIONES = [
    pytest.param(
        EspecificacionEdicion(
            documento="pedido de venta",
            modelo=SalesRequest,
            lineas=SalesRequestItem,
            clave_foranea="sales_request_id",
            ruta_edicion="/sales/sales-request/{id}/edit",
        ),
        id="sales_request",
    ),
    pytest.param(
        EspecificacionEdicion(
            documento="orden de venta",
            modelo=SalesOrder,
            lineas=SalesOrderItem,
            clave_foranea="sales_order_id",
            ruta_edicion="/sales/sales-order/{id}/edit",
            con_bodega=True,
        ),
        id="sales_order",
    ),
    pytest.param(
        EspecificacionEdicion(
            documento="cotización de venta",
            modelo=SalesQuotation,
            lineas=SalesQuotationItem,
            clave_foranea="sales_quotation_id",
            ruta_edicion="/sales/sales-quotation/{id}/edit",
        ),
        id="sales_quotation",
    ),
    pytest.param(
        EspecificacionEdicion(
            documento="nota de entrega",
            modelo=DeliveryNote,
            lineas=DeliveryNoteItem,
            clave_foranea="delivery_note_id",
            ruta_edicion="/sales/delivery-note/{id}/edit",
            con_bodega=True,
        ),
        id="delivery_note",
    ),
]


def _crear_borrador_con_linea(entorno_contable, especificacion: EspecificacionEdicion, marcador: str) -> tuple[str, str]:
    """Crea un borrador editable con una línea válida y devuelve (documento, línea)."""
    with entorno_contable.app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        documento = especificacion.modelo(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=marcador,
        )
        database.session.add(documento)
        database.session.flush()
        datos_linea = {
            especificacion.clave_foranea: documento.id,
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


@pytest.mark.parametrize("especificacion", ESPECIFICACIONES)
def test_edicion_sin_lineas_responde_controlado_y_conserva_lineas(entorno_contable, authenticated_client, especificacion):
    """El POST de edición sin líneas responde con flash y rollback, nunca 500, y no borra las líneas (#2126)."""
    app = entorno_contable.app
    marcador = f"EDIT-SIN-LINEAS-{uuid4().hex[:10]}"
    documento_id, linea_id = _crear_borrador_con_linea(entorno_contable, especificacion, marcador)

    with app.app_context():
        cliente_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id

    cliente = authenticated_client()
    respuesta = cliente.post(
        especificacion.ruta_edicion.format(id=documento_id),
        data={
            "company": "cacao",
            "posting_date": FECHA.isoformat(),
            "customer_id": cliente_id,
            "remarks": marcador,
        },
    )
    assert respuesta.status_code == 302, "El handler de edición debe capturar el error y redirigir, no romper."

    confirmacion = cliente.get(respuesta.headers["Location"])
    assert confirmacion.status_code == 200
    assert MENSAJE_SIN_LINEAS in confirmacion.get_data(as_text=True)

    with app.app_context():
        linea = database.session.get(especificacion.lineas, linea_id)
        assert linea is not None, "El rollback debe restaurar la línea original eliminada durante la edición."
        assert linea.item_code == "ART01"
        assert Decimal(str(linea.qty)) == Decimal("2")
        assert Decimal(str(linea.amount)) == Decimal("20")
