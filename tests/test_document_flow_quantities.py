# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contrato de cantidades del flujo documental.

Escenario de negocio (issue #966): una empresa compra 2 cajas (BOX) de un
artículo cuya unidad base son unidades (EA), con factor 1 BOX = 10 EA. El
pedido registra 20 EA como cantidad base. Se recibe media caja (5 EA) y el
pedido debe seguir parcialmente recibido con 15 EA pendientes, aunque no exista
una fila de ``DocumentLineFlowState`` cacheada.

La regresión protege el invariante: total, consumo y pendiente se comparan en
la misma unidad (UOM base del artículo). Mezclar la cantidad comercial (2 BOX)
con el consumo base (5 EA) haría desaparecer el pendiente y marcaría el pedido
como completado con 15 unidades aún por recibir.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DocumentRelation,
    Entity,
    Item,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    UOM,
    database,
)
from cacao_accounting.document_flow.service import get_document_flow_items, pending_qty
from cacao_accounting.document_flow.status import calculate_document_status

FECHA = date(2026, 10, 20)


@pytest.fixture
def flujo_compra():
    """Pedido de 2 BOX (20 EA) con media caja recibida (5 EA)."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                UOM(code="BOX", name="Caja"),
                UOM(code="EA", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add(
            Item(
                code="CAFE-GRANO",
                name="Café en grano",
                item_type="goods",
                is_stock_item=False,
                default_uom="EA",
            )
        )
        database.session.flush()

        pedido = PurchaseOrder(company="cacao", posting_date=FECHA, docstatus=1, supplier_name="Finca La Esperanza")
        recepcion = PurchaseReceipt(company="cacao", posting_date=FECHA, docstatus=1, supplier_name="Finca La Esperanza")
        database.session.add_all([pedido, recepcion])
        database.session.flush()

        linea_pedido = PurchaseOrderItem(
            purchase_order_id=pedido.id,
            item_code="CAFE-GRANO",
            item_name="Café en grano",
            qty=Decimal("2"),
            uom="BOX",
            qty_in_base_uom=Decimal("20"),
            rate=Decimal("50"),
            amount=Decimal("100"),
        )
        linea_recepcion = PurchaseReceiptItem(
            purchase_receipt_id=recepcion.id,
            item_code="CAFE-GRANO",
            item_name="Café en grano",
            qty=Decimal("0.5"),
            uom="BOX",
            qty_in_base_uom=Decimal("5"),
            rate=Decimal("50"),
            amount=Decimal("25"),
        )
        database.session.add_all([linea_pedido, linea_recepcion])
        database.session.flush()

        database.session.add(
            DocumentRelation(
                source_type="purchase_order",
                source_id=pedido.id,
                source_item_id=linea_pedido.id,
                target_type="purchase_receipt",
                target_id=recepcion.id,
                target_item_id=linea_recepcion.id,
                company="cacao",
                qty=Decimal("0.5"),
                qty_in_base_uom=Decimal("5"),
                uom="BOX",
                rate=Decimal("50"),
                amount=Decimal("25"),
                relation_type="receipt",
                status="active",
            )
        )
        database.session.commit()
        ids = {"pedido": pedido.id, "linea_pedido": linea_pedido.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_pedido_parcialmente_recibido_conserva_el_pendiente_en_uom_base(flujo_compra):
    """#966: 2 BOX pedidas y 0.5 BOX recibidas dejan 15 EA pendientes, no cero."""
    application, ids = flujo_compra
    with application.app_context():
        estado = calculate_document_status("purchase_order", ids["pedido"])
        pendiente = pending_qty("purchase_order", ids["pedido"], ids["linea_pedido"], "purchase_receipt")

    assert pendiente == Decimal("15")
    assert estado.code == "partially_received"
    assert estado.badge_class == "text-bg-primary"


def test_lineas_pendientes_para_recepcion_expresan_cantidad_base(flujo_compra):
    """El selector de recepción anuncia 15 EA disponibles, no 1.5 BOX ni 2 BOX."""
    application, ids = flujo_compra
    with application.app_context():
        items = get_document_flow_items("purchase_receipt", [f"purchase_order:{ids['pedido']}"])

    assert len(items) == 1
    assert Decimal(str(items[0]["pending_qty_in_base_uom"])) == Decimal("15")
    assert Decimal(str(items[0]["pending_qty"])) == Decimal("1.5")
    assert Decimal(str(items[0]["source_qty_in_base_uom"])) == Decimal("20")


def test_recepcion_completa_pasa_a_pendiente_facturar(flujo_compra):
    """Control de negocio: con las 20 EA recibidas el pedido queda por facturar."""
    application, ids = flujo_compra
    with application.app_context():
        from cacao_accounting.database import PurchaseReceipt as Recepcion

        segunda = Recepcion(company="cacao", posting_date=FECHA, docstatus=1, supplier_name="Finca La Esperanza")
        database.session.add(segunda)
        database.session.flush()
        linea = PurchaseReceiptItem(
            purchase_receipt_id=segunda.id,
            item_code="CAFE-GRANO",
            item_name="Café en grano",
            qty=Decimal("1.5"),
            uom="BOX",
            qty_in_base_uom=Decimal("15"),
            rate=Decimal("50"),
            amount=Decimal("75"),
        )
        database.session.add(linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_order",
                source_id=ids["pedido"],
                source_item_id=ids["linea_pedido"],
                target_type="purchase_receipt",
                target_id=segunda.id,
                target_item_id=linea.id,
                company="cacao",
                qty=Decimal("1.5"),
                qty_in_base_uom=Decimal("15"),
                uom="BOX",
                rate=Decimal("50"),
                amount=Decimal("75"),
                relation_type="receipt",
                status="active",
            )
        )
        database.session.commit()

        estado = calculate_document_status("purchase_order", ids["pedido"])
        pendiente = pending_qty("purchase_order", ids["pedido"], ids["linea_pedido"], "purchase_receipt")

    assert pendiente == Decimal("0")
    assert estado.code == "pending_billing"
