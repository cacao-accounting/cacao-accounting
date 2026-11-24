# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1617: duplicar factura/entrega conserva descuentos y relaciones de línea."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Currency,
    DeliveryNote,
    DeliveryNoteItem,
    DocumentRelation,
    Entity,
    Item,
    Modules,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    UOM,
    User,
    database,
)
from cacao_accounting.document_flow.validation import require_line_relations
from cacao_accounting.ventas.services import _validate_sales_invoice_line_amounts


@pytest.fixture
def sales_duplicate_scene():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
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
                Modules(module="sales", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J-1617",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Item(
                    code="ART01",
                    name="Artículo de prueba",
                    item_type="goods",
                    is_stock_item=False,
                    default_uom="UND",
                ),
                User(
                    id="admin-1617",
                    user="admin-1617",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity="cacao",
                name="Mayo 2026",
                enabled=True,
                is_closed=False,
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
            )
        )
        database.session.flush()
        orden = SalesOrder(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            customer_name="Cliente 1617",
            document_no="OV-1617",
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(orden)
        database.session.flush()
        orden_linea = SalesOrderItem(
            sales_order_id=orden.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("2"),
            uom="UND",
            qty_in_base_uom=Decimal("2"),
            rate=Decimal("100"),
            amount=Decimal("200"),
        )
        database.session.add(orden_linea)
        database.session.flush()

        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            document_type="sales_invoice",
            docstatus=1,
            status="open",
            customer_name="Cliente 1617",
            document_no="FV-1617",
            sales_order_id=orden.id,
            transaction_currency="NIO",
            base_currency="NIO",
            total=Decimal("90"),
            grand_total=Decimal("90"),
            outstanding_amount=Decimal("90"),
            base_total=Decimal("90"),
            base_grand_total=Decimal("90"),
            base_outstanding_amount=Decimal("90"),
        )
        database.session.add(factura)
        database.session.flush()
        factura_linea = SalesInvoiceItem(
            sales_invoice_id=factura.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("1"),
            uom="UND",
            qty_in_base_uom=Decimal("1"),
            rate=Decimal("100"),
            amount=Decimal("90"),
            discount_percentage=Decimal("10"),
            discount_amount=Decimal("10"),
        )
        database.session.add(factura_linea)
        database.session.flush()

        entrega = DeliveryNote(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            customer_name="Cliente 1617",
            document_no="NE-1617",
            sales_order_id=orden.id,
            transaction_currency="NIO",
            base_currency="NIO",
            total=Decimal("180"),
            grand_total=Decimal("180"),
        )
        database.session.add(entrega)
        database.session.flush()
        entrega_linea = DeliveryNoteItem(
            delivery_note_id=entrega.id,
            item_code="ART01",
            item_name="Artículo de prueba",
            qty=Decimal("2"),
            uom="UND",
            qty_in_base_uom=Decimal("2"),
            rate=Decimal("100"),
            amount=Decimal("180"),
            discount_percentage=Decimal("10"),
            discount_amount=Decimal("20"),
        )
        database.session.add(entrega_linea)
        database.session.flush()
        database.session.add_all(
            [
                DocumentRelation(
                    source_type="sales_order",
                    source_id=orden.id,
                    source_item_id=orden_linea.id,
                    target_type="sales_invoice",
                    target_id=factura.id,
                    target_item_id=factura_linea.id,
                    company="cacao",
                    qty=Decimal("1"),
                    qty_in_base_uom=Decimal("1"),
                    uom="UND",
                    rate=Decimal("100"),
                    amount=Decimal("90"),
                    relation_type="billing",
                    status="active",
                ),
                DocumentRelation(
                    source_type="sales_order",
                    source_id=orden.id,
                    source_item_id=orden_linea.id,
                    target_type="delivery_note",
                    target_id=entrega.id,
                    target_item_id=entrega_linea.id,
                    company="cacao",
                    qty=Decimal("2"),
                    qty_in_base_uom=Decimal("2"),
                    uom="UND",
                    rate=Decimal("100"),
                    amount=Decimal("180"),
                    relation_type="delivery",
                    status="active",
                ),
            ]
        )
        database.session.commit()
        ids = {
            "order": orden.id,
            "invoice": factura.id,
            "delivery": entrega.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _client(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin-1617"
        session["_fresh"] = True
    return client


def test_duplicar_factura_copia_relacion_y_descuento(sales_duplicate_scene):
    """La factura duplicada conserva la relación de la orden y su descuento."""
    application, ids = sales_duplicate_scene
    respuesta = _client(application).post(f"/sales/sales-invoice/{ids['invoice']}/duplicate")
    assert respuesta.status_code == 302

    with application.app_context():
        duplicada = database.session.execute(
            database.select(SalesInvoice).where(SalesInvoice.id != ids["invoice"])
        ).scalar_one()
        linea = database.session.execute(
            database.select(SalesInvoiceItem).filter_by(sales_invoice_id=duplicada.id)
        ).scalar_one()
        relaciones = (
            database.session.execute(
                database.select(DocumentRelation).filter_by(
                    target_type="sales_invoice", target_id=duplicada.id, status="active"
                )
            )
            .scalars()
            .all()
        )

        assert linea.discount_percentage == Decimal("10.0000")
        assert linea.discount_amount == Decimal("10.0000")
        assert len(relaciones) == 1
        assert relaciones[0].source_id == ids["order"]
        require_line_relations(
            target_type="sales_invoice",
            target_id=duplicada.id,
            source_type="sales_order",
            source_id=ids["order"],
            items=[linea],
        )
        _validate_sales_invoice_line_amounts(duplicada, [linea])


def test_duplicar_entrega_copia_relacion_y_descuento(sales_duplicate_scene):
    """La nota de entrega duplicada conserva descuentos y relación de línea."""
    application, ids = sales_duplicate_scene
    respuesta = _client(application).post(f"/sales/delivery-note/{ids['delivery']}/duplicate")
    assert respuesta.status_code == 302

    with application.app_context():
        duplicada = database.session.execute(
            database.select(DeliveryNote).where(DeliveryNote.id != ids["delivery"])
        ).scalar_one()
        linea = database.session.execute(
            database.select(DeliveryNoteItem).filter_by(delivery_note_id=duplicada.id)
        ).scalar_one()
        relaciones = (
            database.session.execute(
                database.select(DocumentRelation).filter_by(
                    target_type="delivery_note", target_id=duplicada.id, status="active"
                )
            )
            .scalars()
            .all()
        )

        assert linea.discount_percentage == Decimal("10.0000")
        assert linea.discount_amount == Decimal("20.0000")
        assert len(relaciones) == 1
        assert relaciones[0].source_id == ids["order"]
        require_line_relations(
            target_type="delivery_note",
            target_id=duplicada.id,
            source_type="sales_order",
            source_id=ids["order"],
            items=[linea],
        )
        _validate_sales_invoice_line_amounts(duplicada, [linea])
