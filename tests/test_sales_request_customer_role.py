# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión #2056: el rol de cliente (Party.is_customer) es obligatorio en el pedido de venta."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from cacao_accounting.database import Party, SalesRequest, SalesRequestItem, database

FECHA = date(2026, 5, 15)
MENSAJE_NO_CLIENTE = "no está habilitado como cliente"
RUTA_NUEVO_PEDIDO = "/sales/sales-request/new"


def _crear_proveedor_solo(entorno_contable) -> str:
    """Crea un tercero proveedor que no tiene el rol de cliente, con código único."""
    with entorno_contable.app.app_context():
        proveedor = Party(
            code=f"PRV-NC-{uuid4().hex[:10]}",
            name="Proveedor Sin Rol Cliente",
            is_supplier=True,
            is_customer=False,
        )
        database.session.add(proveedor)
        database.session.commit()
        return proveedor.id


def _id_cliente_principal(entorno_contable) -> str:
    """Devuelve el identificador del cliente CLI001 sembrado por el entorno."""
    with entorno_contable.app.app_context():
        return database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id


def _datos_formulario(cliente_id: str, marcador: str) -> dict[str, str]:
    """Construye el POST de alta de pedido con una línea válida y el cliente indicado."""
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": cliente_id,
        "remarks": marcador,
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
    }


def _pedidos_con_marcador(entorno_contable, marcador: str) -> int:
    """Cuenta pedidos de venta persistidos con el marcador único de la prueba."""
    with entorno_contable.app.app_context():
        return database.session.execute(
            select(func.count()).select_from(SalesRequest).where(SalesRequest.remarks == marcador)
        ).scalar_one()


def test_alta_con_tercero_proveedor_rechazada_y_no_persiste(entorno_contable, authenticated_client):
    """Un Party sin is_customer produce error controlado en el alta y no persiste el pedido (#2056)."""
    proveedor = _crear_proveedor_solo(entorno_contable)
    marcador = f"ROL-CLIENTE-RECHAZADO-{uuid4().hex[:10]}"

    respuesta = authenticated_client().post(RUTA_NUEVO_PEDIDO, data=_datos_formulario(proveedor, marcador))

    assert respuesta.status_code == 200, "El alta con un no-cliente debe re-renderizar el formulario con error, nunca 500."
    assert MENSAJE_NO_CLIENTE in respuesta.get_data(as_text=True)
    assert _pedidos_con_marcador(entorno_contable, marcador) == 0, "El pedido con cliente inválido no debe persistirse."


def test_alta_con_cliente_valido_se_persiste(entorno_contable, authenticated_client):
    """Control positivo: CLI001 tiene el rol de cliente y el pedido se crea (#2056)."""
    app = entorno_contable.app
    cliente_id = _id_cliente_principal(entorno_contable)
    marcador = f"ROL-CLIENTE-ACEPTADO-{uuid4().hex[:10]}"

    respuesta = authenticated_client().post(RUTA_NUEVO_PEDIDO, data=_datos_formulario(cliente_id, marcador))

    assert respuesta.status_code == 302
    with app.app_context():
        pedido = database.session.execute(select(SalesRequest).where(SalesRequest.remarks == marcador)).scalar_one()
        assert pedido is not None
        assert pedido.customer_id == cliente_id
        assert pedido.customer_name == "Cliente Principal SA"


def _crear_borrador_con_cliente(entorno_contable, cliente_id: str, marcador: str) -> tuple[str, str]:
    """Crea un pedido borrador con línea y devuelve (pedido, línea)."""
    with entorno_contable.app.app_context():
        pedido = SalesRequest(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            customer_id=cliente_id,
            customer_name="Cliente Principal SA",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            remarks=marcador,
        )
        database.session.add(pedido)
        database.session.flush()
        linea = SalesRequestItem(
            sales_request_id=pedido.id,
            item_code="ART01",
            item_name="Articulo Comercial",
            qty=Decimal("3"),
            qty_in_base_uom=Decimal("3"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("30"),
        )
        database.session.add(linea)
        database.session.commit()
        return pedido.id, linea.id


def test_edicion_con_tercero_proveedor_rechazada_y_conserva_cliente(entorno_contable, authenticated_client):
    """#2056: editar no permite sustituir el cliente por un proveedor."""
    cliente_id = _id_cliente_principal(entorno_contable)
    proveedor_id = _crear_proveedor_solo(entorno_contable)
    marcador = f"EDIT-{uuid4().hex[:6]}"
    pedido_id, _linea = _crear_borrador_con_cliente(entorno_contable, cliente_id, marcador)

    respuesta = authenticated_client("admin").post(
        f"/sales/sales-request/{pedido_id}/edit",
        data=_datos_formulario(proveedor_id, marcador),
    )

    assert respuesta.status_code != 500
    with entorno_contable.app.app_context():
        pedido = database.session.get(SalesRequest, pedido_id)
        assert pedido is not None
        assert pedido.customer_id == cliente_id
