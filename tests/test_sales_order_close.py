"""Tests for sales order close lifecycle."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CacaoConfig,
    Currency,
    DeliveryNote,
    DeliveryNoteItem,
    Entity,
    Item,
    Modules,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    UOM,
    User,
    database,
)
from cacao_accounting.document_flow import create_document_relation
from cacao_accounting.ventas.services import (
    sales_order_is_ready_to_close,
    sales_order_line_closure_reasons,
)


@pytest.fixture()
def sales_close_app():
    """Create an isolated schema for sales order close tests."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "sales-close-test-secret",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                CacaoConfig(key="SETUP_COMPLETE", value="True"),
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO", enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Modules(module="sales", default=True, enabled=True),
                Modules(module="inventory", default=True, enabled=True),
                Modules(module="accounting", default=True, enabled=True),
                UOM(code="UN", name="Unidad", is_active=True),
                Item(code="ITEM-001", name="Test Item", item_type="goods", default_uom="UN", is_active=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()


def _create_customer_and_order():
    """Persist a minimal customer and sales order fixture."""
    customer = Party(code="CUST-001", name="Customer Test", tax_id="J-001", is_customer=True, is_active=True)
    order = SalesOrder(
        company="cacao",
        customer_name=customer.name,
        transaction_currency="NIO",
        grand_total=Decimal("1000"),
        posting_date=date(2026, 8, 26),
        document_no="SO-001",
        docstatus=1,
        status="open",
    )
    database.session.add_all([customer, order])
    database.session.flush()
    order.customer_id = customer.id
    item = SalesOrderItem(
        sales_order_id=order.id,
        item_code="ITEM-001",
        qty=Decimal("10"),
        rate=Decimal("100"),
        amount=Decimal("1000"),
    )
    database.session.add(item)
    database.session.commit()
    return customer, order, item


def test_sales_order_default_status_is_open(sales_close_app):
    """A new sales order defaults to open status."""
    customer, order, item = _create_customer_and_order()
    assert order.status == "open"


def test_sales_order_is_ready_to_close_returns_false_when_no_children(sales_close_app):
    """An order with no deliveries or invoices is not ready to close."""
    customer, order, item = _create_customer_and_order()
    assert sales_order_is_ready_to_close(order) is False


def test_sales_order_is_ready_to_close_returns_true_when_all_delivered(sales_close_app):
    """An order is ready to close when all lines have approved delivery notes."""
    customer, order, item = _create_customer_and_order()
    dn = DeliveryNote(
        company="cacao",
        customer_id=customer.id,
        customer_name=customer.name,
        transaction_currency="NIO",
        grand_total=Decimal("1000"),
        posting_date=date(2026, 8, 26),
        docstatus=1,
    )
    database.session.add(dn)
    database.session.flush()
    dn_item = DeliveryNoteItem(
        delivery_note_id=dn.id,
        item_code="ITEM-001",
        qty=Decimal("10"),
        rate=Decimal("100"),
        amount=Decimal("1000"),
    )
    database.session.add(dn_item)
    database.session.flush()
    create_document_relation(
        source_type="sales_order",
        source_id=order.id,
        source_item_id=item.id,
        target_type="delivery_note",
        target_id=dn.id,
        target_item_id=dn_item.id,
        qty=Decimal("10"),
    )
    database.session.commit()
    assert sales_order_is_ready_to_close(order) is True


def test_sales_order_line_closure_reasons_with_delivery(sales_close_app):
    """Closure reasons include delivery note references."""
    customer, order, item = _create_customer_and_order()
    dn = DeliveryNote(
        company="cacao",
        customer_id=customer.id,
        customer_name=customer.name,
        transaction_currency="NIO",
        grand_total=Decimal("1000"),
        posting_date=date(2026, 8, 26),
        docstatus=1,
    )
    database.session.add(dn)
    database.session.flush()
    dn_item = DeliveryNoteItem(
        delivery_note_id=dn.id,
        item_code="ITEM-001",
        qty=Decimal("10"),
        rate=Decimal("100"),
        amount=Decimal("1000"),
    )
    database.session.add(dn_item)
    database.session.flush()
    create_document_relation(
        source_type="sales_order",
        source_id=order.id,
        source_item_id=item.id,
        target_type="delivery_note",
        target_id=dn.id,
        target_item_id=dn_item.id,
        qty=Decimal("10"),
    )
    database.session.commit()
    reasons = sales_order_line_closure_reasons(order)
    assert item.id in reasons
    assert "Nota de Entrega" in reasons[item.id]


def test_sales_order_line_closure_reasons_with_invoice(sales_close_app):
    """Closure reasons include sales invoice references."""
    customer, order, item = _create_customer_and_order()
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        customer_name=customer.name,
        transaction_currency="NIO",
        grand_total=Decimal("1000"),
        posting_date=date(2026, 8, 26),
        docstatus=1,
    )
    database.session.add(invoice)
    database.session.flush()
    inv_item = SalesInvoiceItem(
        sales_invoice_id=invoice.id,
        item_code="ITEM-001",
        qty=Decimal("10"),
        rate=Decimal("100"),
        amount=Decimal("1000"),
    )
    database.session.add(inv_item)
    database.session.flush()
    create_document_relation(
        source_type="sales_order",
        source_id=order.id,
        source_item_id=item.id,
        target_type="sales_invoice",
        target_id=invoice.id,
        target_item_id=inv_item.id,
        qty=Decimal("10"),
    )
    database.session.commit()
    reasons = sales_order_line_closure_reasons(order)
    assert item.id in reasons
    assert "Factura de Venta" in reasons[item.id]
