# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1621: una solicitud convertida en orden deja de mostrarse abierta."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import SalesOrderItem, SalesRequest, SalesRequestItem, database
from cacao_accounting.document_flow.service import create_target_document
from cacao_accounting.document_flow.status import calculate_document_status


def test_solicitud_consumida_por_orden_directa_queda_completada(app, entorno_contable):
    """El flujo directo sales_request -> sales_order gobierna el estado."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        solicitud = SalesRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            customer_name="Cliente 1621",
            document_no=f"SR-{sufijo}",
        )
        database.session.add(solicitud)
        database.session.flush()
        linea = SalesRequestItem(
            sales_request_id=solicitud.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("50"),
            uom="UND",
            qty_in_base_uom=Decimal("50"),
            rate=Decimal("10"),
            amount=Decimal("500"),
        )
        database.session.add(linea)
        database.session.commit()
        solicitud_id, linea_id = solicitud.id, linea.id

    try:
        with app.app_context():
            inicial = calculate_document_status("sales_request", database.session.get(SalesRequest, solicitud_id))
            assert inicial.code == "open"
            resultado = create_target_document(
                {
                    "target_document_type": "sales_order",
                    "company": "cacao",
                    "posting_date": "2026-05-15",
                    "lines": [
                        {
                            "source_document_type": "sales_request",
                            "source_document_id": solicitud_id,
                            "source_row_id": linea_id,
                            "qty": "50",
                        }
                    ],
                },
                commit=False,
            )
            estado = calculate_document_status("sales_request", database.session.get(SalesRequest, solicitud_id))
            assert database.session.get(SalesOrderItem, resultado["lines"][0]["target_item_id"]).qty == Decimal("50")
            assert estado.code == "completed"
            assert estado.label == "Completado"
            database.session.rollback()
    finally:
        with app.app_context():
            database.session.execute(database.delete(SalesRequestItem).where(SalesRequestItem.id == linea_id))
            database.session.execute(database.delete(SalesRequest).where(SalesRequest.id == solicitud_id))
            database.session.commit()
