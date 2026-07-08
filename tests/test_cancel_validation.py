# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de validacion de cancelacion de ordenes con hijos activos (S2P-04)."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    SalesOrder,
    SalesOrderItem,
    DeliveryNote,
    DeliveryNoteItem,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.document_flow import create_document_relation


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.datos.dev import master_data

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        master_data()
        database.session.commit()
        yield app


def login(client, username, password):
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def test_purchase_order_cancel_blocked_with_active_receipt(app_ctx):
    """Cancelar OC falla si tiene recepciones activas vinculadas."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    order = PurchaseOrder(
        id="PO-CANCEL-01",
        company="cacao",
        posting_date=date(2026, 5, 1),
        docstatus=1,
        grand_total=Decimal("50"),
    )
    order_item = PurchaseOrderItem(
        purchase_order_id="PO-CANCEL-01",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("50"),
    )
    receipt = PurchaseReceipt(
        id="PR-CANCEL-01",
        company="cacao",
        posting_date=date(2026, 5, 2),
        docstatus=1,
    )
    receipt_item = PurchaseReceiptItem(
        purchase_receipt_id="PR-CANCEL-01",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )
    database.session.add_all([order, order_item, receipt, receipt_item])
    database.session.flush()

    create_document_relation(
        source_type="purchase_order",
        source_id="PO-CANCEL-01",
        source_item_id=order_item.id,
        target_type="purchase_receipt",
        target_id="PR-CANCEL-01",
        target_item_id=receipt_item.id,
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )
    database.session.commit()

    response = client.post("/buying/purchase-order/PO-CANCEL-01/cancel", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(order)
    assert order.docstatus == 1, "La OC no deberia cancelarse porque tiene recepciones activas"


def test_purchase_order_cancel_allowed_without_children(app_ctx):
    """Cancelar OC funciona cuando no tiene hijos activos."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    order = PurchaseOrder(
        id="PO-CANCEL-02",
        company="cacao",
        posting_date=date(2026, 5, 1),
        docstatus=1,
        grand_total=Decimal("50"),
    )
    database.session.add(order)
    database.session.commit()

    response = client.post("/buying/purchase-order/PO-CANCEL-02/cancel", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(order)
    assert order.docstatus == 2, "La OC deberia cancelarse porque no tiene hijos activos"


def test_sales_order_cancel_blocked_with_active_delivery_note(app_ctx):
    """Cancelar OV falla si tiene notas de entrega activas vinculadas."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    order = SalesOrder(
        id="SO-CANCEL-01",
        company="cacao",
        posting_date=date(2026, 5, 1),
        docstatus=1,
        grand_total=Decimal("50"),
    )
    order_item = SalesOrderItem(
        sales_order_id="SO-CANCEL-01",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("50"),
    )
    dn = DeliveryNote(
        id="DN-CANCEL-01",
        company="cacao",
        posting_date=date(2026, 5, 2),
        docstatus=1,
    )
    dn_item = DeliveryNoteItem(
        delivery_note_id="DN-CANCEL-01",
        item_code="ART-001",
        item_name="Chocolate",
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )
    database.session.add_all([order, order_item, dn, dn_item])
    database.session.flush()

    create_document_relation(
        source_type="sales_order",
        source_id="SO-CANCEL-01",
        source_item_id=order_item.id,
        target_type="delivery_note",
        target_id="DN-CANCEL-01",
        target_item_id=dn_item.id,
        qty=Decimal("5"),
        uom="UND",
        rate=Decimal("5"),
        amount=Decimal("25"),
    )
    database.session.commit()

    response = client.post("/sales/sales-order/SO-CANCEL-01/cancel", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(order)
    assert order.docstatus == 1, "La OV no deberia cancelarse porque tiene notas de entrega activas"


def test_sales_order_cancel_allowed_without_children(app_ctx):
    """Cancelar OV funciona cuando no tiene hijos activos."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    order = SalesOrder(
        id="SO-CANCEL-02",
        company="cacao",
        posting_date=date(2026, 5, 1),
        docstatus=1,
        grand_total=Decimal("50"),
    )
    database.session.add(order)
    database.session.commit()

    response = client.post("/sales/sales-order/SO-CANCEL-02/cancel", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(order)
    assert order.docstatus == 2, "La OV deberia cancelarse porque no tiene hijos activos"
