# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2056: el pedido de venta exige el rol cliente al informar un tercero.

El alta, la edición y la duplicación deben rechazar un Party que solo sea
proveedor, sin persistir ni mutar el documento.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import Party, SalesRequest, database


@pytest.fixture
def proveedor_sin_rol_cliente(app, entorno_contable):
    """Tercero activo que no tiene el rol cliente."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        proveedor = Party(
            code=f"PRV-2056-{sufijo}",
            name=f"Proveedor {sufijo}",
            is_supplier=True,
            is_customer=False,
            is_active=True,
        )
        database.session.add(proveedor)
        database.session.commit()
        proveedor_id = proveedor.id
    yield proveedor_id
    with app.app_context():
        database.session.execute(database.delete(SalesRequest).where(SalesRequest.customer_id == proveedor_id))
        database.session.execute(database.delete(Party).where(Party.id == proveedor_id))
        database.session.commit()


def test_alta_rechaza_tercero_que_no_es_cliente(app, authenticated_client, proveedor_sin_rol_cliente):
    """El alta no persiste el pedido con un proveedor como cliente."""
    response = authenticated_client("admin").post(
        "/sales/sales-request/new",
        data={
            "company": "cacao",
            "posting_date": "2026-05-15",
            "currency": "NIO",
            "customer_id": proveedor_sin_rol_cliente,
        },
    )

    assert response.status_code == 200
    assert "no está habilitado como cliente" in response.get_data(as_text=True)
    with app.app_context():
        assert (
            database.session.execute(
                database.select(SalesRequest).filter_by(customer_id=proveedor_sin_rol_cliente)
            ).scalar_one_or_none()
            is None
        )


def test_duplicar_rechaza_tercero_que_perdio_el_rol_cliente(app, authenticated_client, proveedor_sin_rol_cliente):
    """Duplicar un borrador no reintroduce un cliente que ya no tiene el rol."""
    with app.app_context():
        origen = SalesRequest(
            company="cacao",
            customer_id=proveedor_sin_rol_cliente,
            customer_name="Proveedor histórico",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=1,
            posting_date=date(2026, 5, 15),
            docstatus=0,
        )
        database.session.add(origen)
        database.session.commit()
        origen_id = origen.id

    response = authenticated_client("admin").post(
        f"/sales/sales-request/{origen_id}/duplicate",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "no está habilitado como cliente" in response.get_data(as_text=True)
    with app.app_context():
        pedidos = (
            database.session.execute(database.select(SalesRequest).filter_by(customer_id=proveedor_sin_rol_cliente))
            .scalars()
            .all()
        )
        assert [pedido.id for pedido in pedidos] == [origen_id]
