# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2096: duplicar conserva descripción y bodega de las líneas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    PurchaseRequest,
    PurchaseRequestItem,
    SalesRequest,
    SalesRequestItem,
    database,
)

FECHA = date(2026, 5, 15)


def _linea_request(company: str, suffix: str) -> PurchaseRequest:
    origen = PurchaseRequest(
        company=company,
        posting_date=FECHA,
        docstatus=1,
        document_no=f"PR-DUP-{suffix}",
        remarks=f"PR-DUP-{suffix}",
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(origen)
    database.session.flush()
    database.session.add(
        PurchaseRequestItem(
            purchase_request_id=origen.id,
            item_code="ART01",
            item_name="Articulo Comercial",
            description="Especificación de compra",
            warehouse="BOD01",
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("10"),
        )
    )
    return origen


def test_duplicar_solicitud_compra_conserva_descripcion_y_bodega(app, entorno_contable, authenticated_client):
    suffix = uuid4().hex[:8]
    with app.app_context():
        origen = _linea_request("cacao", suffix)
        database.session.commit()
        origen_id = origen.id

    respuesta = authenticated_client().post(f"/buying/purchase-request/{origen_id}/duplicate")
    assert respuesta.status_code == 302

    with app.app_context():
        copia = database.session.execute(
            database.select(PurchaseRequest).filter_by(remarks=f"PR-DUP-{suffix}", docstatus=0)
        ).scalar_one()
        linea = database.session.execute(
            database.select(PurchaseRequestItem).filter_by(purchase_request_id=copia.id)
        ).scalar_one()
        assert linea.description == "Especificación de compra"
        assert linea.warehouse == "BOD01"


def test_duplicar_pedido_venta_conserva_descripcion_y_bodega(app, entorno_contable, authenticated_client):
    suffix = uuid4().hex[:8]
    with app.app_context():
        origen = SalesRequest(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            document_no=f"SR-DUP-{suffix}",
            remarks=f"SR-DUP-{suffix}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(origen)
        database.session.flush()
        database.session.add(
            SalesRequestItem(
                sales_request_id=origen.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                description="Especificación de venta",
                warehouse="BOD01",
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal("10"),
            )
        )
        database.session.commit()
        origen_id = origen.id

    respuesta = authenticated_client().post(f"/sales/sales-request/{origen_id}/duplicate")
    assert respuesta.status_code == 302

    with app.app_context():
        copia = database.session.execute(
            database.select(SalesRequest).filter_by(remarks=f"SR-DUP-{suffix}", docstatus=0)
        ).scalar_one()
        linea = database.session.execute(database.select(SalesRequestItem).filter_by(sales_request_id=copia.id)).scalar_one()
        assert linea.description == "Especificación de venta"
        assert linea.warehouse == "BOD01"
