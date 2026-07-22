# SPDX-License-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de update_inventory en Factura de Venta (O2C-01)."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Accounts,
    DeliveryNote,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    StockValuationLayer,
    Warehouse,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


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


def _setup_inventory_context(company="cacao"):
    """Configura el contexto de inventario necesario para DN posting."""
    warehouse = database.session.execute(database.select(Warehouse).filter_by(company=company)).scalars().first()
    if not warehouse:
        warehouse = Warehouse(code="BOD-TEST", name="Bodega Test", company=company, is_active=True)
        database.session.add(warehouse)
        database.session.flush()

    item = database.session.execute(database.select(Item).filter_by(is_stock_item=True)).scalars().first()
    if not item:
        item = Item(code="ITEM-INV-001", name="Item Test", item_type="goods", is_stock_item=True, default_uom="UND")
        database.session.add(item)
        database.session.flush()

    cogs_account = (
        database.session.execute(database.select(Accounts).filter_by(entity=company, account_type="cost_of_goods_sold"))
        .scalars()
        .first()
    )
    inventory_account = (
        database.session.execute(database.select(Accounts).filter_by(entity=company, account_type="inventory"))
        .scalars()
        .first()
    )

    return warehouse, item, cogs_account, inventory_account


def _ensure_default_warehouse(item, warehouse):
    """Asigna bodega predeterminada al ítem."""
    item.default_warehouse_id = warehouse.code
    database.session.flush()


def _seed_valuation_layer(item, warehouse, company="cacao", qty=Decimal("100"), rate=Decimal("10")):
    """Crea una capa de valuación para que el posting de DN funcione."""
    layer = StockValuationLayer(
        item_code=item.code,
        warehouse=warehouse.code,
        company=company,
        qty=qty,
        rate=rate,
        remaining_qty=qty,
        remaining_stock_value=qty * rate,
        stock_value_difference=qty * rate,
        voucher_type="purchase_receipt",
        voucher_id="SEED-001",
        posting_date=date(2026, 1, 1),
    )
    database.session.add(layer)
    database.session.flush()


def test_submit_with_update_inventory_creates_delivery_note(app_ctx):
    """Factura con update_inventory=True y sin DN crea DN automáticamente."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()
    _ensure_default_warehouse(item, warehouse)
    _seed_valuation_layer(item, warehouse)

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()

    invoice = SalesInvoice(
        id="SI-INV-01",
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_type="sales_invoice",
        update_inventory=True,
        docstatus=0,
        grand_total=Decimal("500"),
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id="SI-INV-01",
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("50"),
        amount=Decimal("500"),
        warehouse=warehouse.code,
    )
    database.session.add_all([invoice, invoice_item])
    database.session.commit()

    response = client.post("/sales/sales-invoice/SI-INV-01/submit", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(invoice)
    assert invoice.docstatus == 1
    assert invoice.delivery_note_id is not None

    dn = database.session.get(DeliveryNote, invoice.delivery_note_id)
    assert dn is not None
    assert dn.docstatus == 1
    assert dn.customer_id == customer.id


def test_submit_without_update_inventory_does_not_create_dn(app_ctx):
    """Factura con update_inventory=False no crea DN."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()
    _ensure_default_warehouse(item, warehouse)
    _seed_valuation_layer(item, warehouse)

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()

    invoice = SalesInvoice(
        id="SI-INV-02",
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_type="sales_invoice",
        update_inventory=False,
        docstatus=0,
        grand_total=Decimal("500"),
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id="SI-INV-02",
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("50"),
        amount=Decimal("500"),
        warehouse=warehouse.code,
    )
    database.session.add_all([invoice, invoice_item])
    database.session.commit()

    response = client.post("/sales/sales-invoice/SI-INV-02/submit", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(invoice)
    assert invoice.docstatus == 1
    assert invoice.delivery_note_id is None


def test_cancel_with_update_inventory_cancels_linked_dn(app_ctx):
    """Cancelar factura con update_inventory=True cancela la DN vinculada."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()
    _ensure_default_warehouse(item, warehouse)
    _seed_valuation_layer(item, warehouse)

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()

    invoice = SalesInvoice(
        id="SI-INV-03",
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_type="sales_invoice",
        update_inventory=True,
        docstatus=0,
        grand_total=Decimal("500"),
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id="SI-INV-03",
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("50"),
        amount=Decimal("500"),
        warehouse=warehouse.code,
    )
    database.session.add_all([invoice, invoice_item])
    database.session.commit()

    client.post("/sales/sales-invoice/SI-INV-03/submit", follow_redirects=True)
    database.session.refresh(invoice)
    dn_id = invoice.delivery_note_id
    assert dn_id is not None

    response = client.post("/sales/sales-invoice/SI-INV-03/cancel", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(invoice)
    assert invoice.docstatus == 2

    dn = database.session.get(DeliveryNote, dn_id)
    assert dn.docstatus == 2


def test_submit_fails_when_item_has_no_default_warehouse(app_ctx):
    """Factura con update_inventory=True falla si el ítem no tiene bodega."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()
    item.default_warehouse_id = None
    database.session.flush()
    _seed_valuation_layer(item, warehouse)

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()

    invoice = SalesInvoice(
        id="SI-INV-04",
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_type="sales_invoice",
        update_inventory=True,
        docstatus=0,
        grand_total=Decimal("500"),
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id="SI-INV-04",
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("10"),
        uom="UND",
        rate=Decimal("50"),
        amount=Decimal("500"),
    )
    database.session.add_all([invoice, invoice_item])
    database.session.commit()

    response = client.post("/sales/sales-invoice/SI-INV-04/submit", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(invoice)
    assert invoice.docstatus == 0, "La factura no deberia aprobarse si el item no tiene bodega"
