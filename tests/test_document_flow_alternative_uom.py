# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2274: la cantidad base convertida se conserva a lo largo del flujo documental."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    DocumentRelation,
    ItemUOMConversion,
    SalesOrder,
    SalesOrderItem,
    SalesRequest,
    SalesRequestItem,
    UOM,
    database,
)
from cacao_accounting.document_flow.service import DocumentFlowError, create_target_document


def _pedido(sufijo: str, uom: str, qty: Decimal, base_qty: Decimal) -> tuple[str, str]:
    """Crea un pedido aprobado con una línea en la UOM indicada."""
    pedido = SalesRequest(
        company="cacao",
        posting_date=date(2026, 5, 15),
        docstatus=1,
        status="open",
        customer_name="Cliente 2274",
        document_no=f"SR-{sufijo}",
    )
    database.session.add(pedido)
    database.session.flush()
    linea = SalesRequestItem(
        sales_request_id=pedido.id,
        item_code="ART01",
        item_name="Artículo de prueba",
        qty=qty,
        uom=uom,
        qty_in_base_uom=base_qty,
        rate=Decimal("5"),
        amount=qty * Decimal("5"),
    )
    database.session.add(linea)
    database.session.commit()
    return pedido.id, linea.id


def test_conversion_alternativa_se_conserva_en_linea_relacion_y_siguiente_flujo(entorno_contable_aislado):
    """Dos cajas equivalen a 24 unidades en el pedido, la orden y la entrega."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        database.session.add(UOM(code="CAJA", name="Caja", is_active=True))
        database.session.flush()
        database.session.add(
            ItemUOMConversion(item_code="ART01", from_uom="CAJA", to_uom="UND", conversion_factor=Decimal("12"))
        )
        pedido_id, linea_id = _pedido(sufijo, "CAJA", Decimal("2"), Decimal("24"))

        orden = create_target_document(
            {
                "target_document_type": "sales_order",
                "company": "cacao",
                "posting_date": "2026-05-15",
                "lines": [
                    {
                        "source_document_type": "sales_request",
                        "source_document_id": pedido_id,
                        "source_row_id": linea_id,
                        "qty": "2",
                    }
                ],
            },
            commit=False,
        )
        item_orden = database.session.get(SalesOrderItem, orden["lines"][0]["target_item_id"])
        assert item_orden.qty == Decimal("2")
        assert item_orden.uom == "CAJA"
        assert item_orden.qty_in_base_uom == Decimal("24")
        relacion_orden = database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="sales_order", target_id=orden["target_id"])
        ).scalar_one()
        assert relacion_orden.qty == Decimal("2")
        assert relacion_orden.uom == "CAJA"
        assert relacion_orden.qty_in_base_uom == Decimal("24")

        orden_aprobada = database.session.get(SalesOrder, orden["target_id"])
        orden_aprobada.docstatus = 1
        database.session.commit()

        entrega = create_target_document(
            {
                "target_document_type": "delivery_note",
                "company": "cacao",
                "posting_date": "2026-05-16",
                "lines": [
                    {
                        "source_document_type": "sales_order",
                        "source_document_id": orden["target_id"],
                        "source_row_id": item_orden.id,
                        "qty": "2",
                    }
                ],
            },
            commit=False,
        )
        item_entrega = database.session.get(DeliveryNoteItem, entrega["lines"][0]["target_item_id"])
        assert item_entrega.qty_in_base_uom == Decimal("24")
        relacion_entrega = database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="delivery_note", target_id=entrega["target_id"])
        ).scalar_one()
        assert relacion_entrega.qty_in_base_uom == Decimal("24")
        assert database.session.execute(database.select(DeliveryNote.id).filter_by(id=entrega["target_id"])).scalar_one()


def test_conversion_ausente_rechaza_todo_el_documento_sin_escrituras(entorno_contable_aislado):
    """Una línea sin conversión impide que se persista el resto del destino."""
    app = entorno_contable_aislado.app
    sufijo = uuid4().hex[:6]
    with app.app_context():
        database.session.add(UOM(code="CAJON", name="Cajón", is_active=True))
        database.session.flush()
        pedido_id, linea_valida_id = _pedido(f"{sufijo}-a", "UND", Decimal("1"), Decimal("1"))
        pedido2 = SalesRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            customer_name="Cliente 2274",
            document_no=f"SR-{sufijo}-b",
        )
        database.session.add(pedido2)
        database.session.flush()
        linea_invalida = SalesRequestItem(
            sales_request_id=pedido2.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            uom="CAJON",
            qty_in_base_uom=Decimal("1"),
            rate=Decimal("5"),
            amount=Decimal("5"),
        )
        database.session.add(linea_invalida)
        database.session.commit()

        with pytest.raises(DocumentFlowError, match="No se pudo convertir"):
            create_target_document(
                {
                    "target_document_type": "sales_order",
                    "company": "cacao",
                    "posting_date": "2026-05-15",
                    "lines": [
                        {
                            "source_document_type": "sales_request",
                            "source_document_id": pedido_id,
                            "source_row_id": linea_valida_id,
                            "qty": "1",
                        },
                        {
                            "source_document_type": "sales_request",
                            "source_document_id": pedido2.id,
                            "source_row_id": linea_invalida.id,
                            "qty": "1",
                        },
                    ],
                },
                commit=True,
            )
        database.session.rollback()

        assert database.session.execute(database.select(SalesOrder.id).limit(1)).scalar_one_or_none() is None
        assert database.session.execute(database.select(SalesOrderItem.id).limit(1)).scalar_one_or_none() is None
        assert database.session.execute(database.select(DocumentRelation.id).limit(1)).scalar_one_or_none() is None
