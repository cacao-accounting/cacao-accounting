# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1639: las lineas creadas por el flujo conservan la cantidad base."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import SalesOrderItem, SalesRequest, SalesRequestItem, database
from cacao_accounting.document_flow.service import create_target_document


def test_documento_destino_copia_qty_in_base_uom(app, entorno_contable):
    """Una orden creada desde un pedido puede usarse luego como origen."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        pedido = SalesRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            customer_name="Cliente 1639",
            document_no=f"SR-{sufijo}",
        )
        database.session.add(pedido)
        database.session.flush()
        linea = SalesRequestItem(
            sales_request_id=pedido.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("10"),
            uom="UND",
            qty_in_base_uom=Decimal("10"),
            rate=Decimal("5"),
            amount=Decimal("50"),
        )
        database.session.add(linea)
        database.session.commit()
        pedido_id, linea_id = pedido.id, linea.id

    try:
        with app.app_context():
            resultado = create_target_document(
                {
                    "target_document_type": "sales_order",
                    "company": "cacao",
                    "posting_date": "2026-05-15",
                    "lines": [
                        {
                            "source_document_type": "sales_request",
                            "source_document_id": pedido_id,
                            "source_row_id": linea_id,
                            "qty": "10",
                        }
                    ],
                },
                commit=False,
            )
            destino = database.session.get(SalesOrderItem, resultado["lines"][0]["target_item_id"])
            assert destino.qty_in_base_uom == Decimal("10")
            assert destino.qty == Decimal("10")
            database.session.rollback()
    finally:
        with app.app_context():
            database.session.execute(database.delete(SalesRequestItem).where(SalesRequestItem.id == linea_id))
            database.session.execute(database.delete(SalesRequest).where(SalesRequest.id == pedido_id))
            database.session.commit()
