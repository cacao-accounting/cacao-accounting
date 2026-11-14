# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión #2057: cantidades no positivas se rechazan sin persistir el pedido de venta."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

import cacao_accounting
from cacao_accounting.database import Party, SalesRequest, SalesRequestItem, database

FECHA = date(2026, 5, 15)
MENSAJE_CANTIDAD = "debe ser mayor a cero"
RUTA_NUEVO_PEDIDO = "/sales/sales-request/new"


def _datos_formulario(entorno_contable, qty: str, marcador: str) -> dict[str, str]:
    """Construye el POST de alta con una única línea cuya cantidad es la indicada."""
    with entorno_contable.app.app_context():
        cliente_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": cliente_id,
        "remarks": marcador,
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": qty,
        "rate_0": "10",
        "uom_0": "UND",
    }


def _pedidos_con_marcador(entorno_contable, marcador: str) -> int:
    """Cuenta pedidos de venta persistidos con el marcador único de la prueba."""
    with entorno_contable.app.app_context():
        return database.session.execute(
            select(func.count()).select_from(SalesRequest).where(SalesRequest.remarks == marcador)
        ).scalar_one()


def _lineas_de_pedidos_con_marcador(entorno_contable, marcador: str) -> int:
    """Cuenta líneas de venta asociadas a pedidos marcados con el identificador único."""
    with entorno_contable.app.app_context():
        return database.session.execute(
            select(func.count())
            .select_from(SalesRequestItem)
            .join(SalesRequest, SalesRequestItem.sales_request_id == SalesRequest.id)
            .where(SalesRequest.remarks == marcador)
        ).scalar_one()


@pytest.mark.parametrize("qty", ["0", "-1", "-0.5"], ids=["cero", "negativo_entero", "negativo_decimal"])
def test_pedido_con_cantidad_no_positiva_responde_formulario_y_no_persiste(entorno_contable, authenticated_client, qty):
    """qty <= 0 devuelve el formulario con flash de error y no persiste pedido ni líneas (#2057)."""
    marcador = f"QTY-INVALIDA-{uuid4().hex[:10]}"
    formulario = _datos_formulario(entorno_contable, qty, marcador)

    respuesta = authenticated_client().post(RUTA_NUEVO_PEDIDO, data=formulario)

    assert respuesta.status_code == 200, "El POST debe re-renderizar el formulario con un error controlado, nunca 500."
    assert MENSAJE_CANTIDAD in respuesta.get_data(as_text=True)
    assert _pedidos_con_marcador(entorno_contable, marcador) == 0, "El pedido con cantidad inválida no debe persistirse."
    assert _lineas_de_pedidos_con_marcador(entorno_contable, marcador) == 0, "No debe persistirse ninguna línea del pedido."


def test_pedido_con_cantidad_positiva_se_persiste(entorno_contable, authenticated_client):
    """Control positivo: qty=1 crea el pedido con su línea y redirige al detalle (#2057)."""
    app = entorno_contable.app
    marcador = f"QTY-VALIDA-{uuid4().hex[:10]}"
    formulario = _datos_formulario(entorno_contable, "1", marcador)

    respuesta = authenticated_client().post(RUTA_NUEVO_PEDIDO, data=formulario)

    assert respuesta.status_code == 302
    with app.app_context():
        pedido = database.session.execute(select(SalesRequest).where(SalesRequest.remarks == marcador)).scalar_one()
        assert pedido is not None
        linea = database.session.execute(
            select(SalesRequestItem).where(SalesRequestItem.sales_request_id == pedido.id)
        ).scalar_one()
        assert linea is not None
        assert linea.item_code == "ART01"
        assert Decimal(str(linea.qty)) == Decimal("1")


def test_plantilla_del_formulario_exige_cantidad_minima_positiva():
    """La macro del formulario declara min="0.0001" en el campo de cantidad (defensa en cliente)."""
    plantilla = Path(cacao_accounting.__file__).parent / "templates" / "transaction_form_macros.html"
    contenido = plantilla.read_text(encoding="utf-8")
    posicion = contenido.index("column.field === 'qty'")
    segmento_cantidad = contenido[posicion : posicion + 400]
    assert ":name=\"'qty_' + index\"" in segmento_cantidad
    assert 'min="0.0001"' in segmento_cantidad
