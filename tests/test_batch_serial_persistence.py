# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Tests para issue #720: persistencia de batch_id y serial_no en documentos de compra/venta.

Valida que los campos batch_id y serial_no se lean correctamente del formulario
y se persistan en los modelos PurchaseReceiptItem, PurchaseInvoiceItem,
DeliveryNoteItem y SalesInvoiceItem.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Batch,
    Currency,
    DeliveryNote,
    DeliveryNoteItem,
    Item,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    SalesInvoice,
    SalesInvoiceItem,
    StockEntry,
    StockEntryItem,
    Warehouse,
    Entity,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


@pytest.fixture()
def app_ctx():
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        _setup_test_data()
        yield app


def _setup_test_data():
    """Crea datos de prueba: warehouse, batch y items controlados."""
    currency = database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none()
    if currency is None:
        database.session.add(Currency(code="NIO", name="Cordoba", decimals=2, active=True))
    company = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one_or_none()
    if company is None:
        company = Entity(
            code="cacao",
            name="Cacao",
            company_name="Cacao",
            tax_id="CACAO-TEST",
            currency="NIO",
            enabled=True,
        )
        database.session.add(company)
    else:
        company.currency = "NIO"
    warehouse = Warehouse(code="WH-TEST", name="Warehouse Test", company="cacao", is_active=True)
    existing_warehouse = database.session.execute(database.select(Warehouse).filter_by(code="WH-TEST")).scalar_one_or_none()
    if not existing_warehouse:
        database.session.add(warehouse)

    item_batch = Item(
        code="ITEM-BATCH",
        name="Item con lote",
        item_type="goods",
        is_stock_item=True,
        has_batch=True,
        default_uom="UND",
    )
    item_serial = Item(
        code="ITEM-SERIAL",
        name="Item con serie",
        item_type="goods",
        is_stock_item=True,
        has_serial_no=True,
        default_uom="UND",
    )
    for item in [item_batch, item_serial]:
        existing = database.session.execute(database.select(Item).filter_by(code=item.code)).scalar_one_or_none()
        if not existing:
            database.session.add(item)

    batch = Batch(item_code="ITEM-BATCH", batch_no="LOT-001")
    existing_batch = database.session.execute(
        database.select(Batch).filter_by(item_code="ITEM-BATCH", batch_no="LOT-001")
    ).scalar_one_or_none()
    if not existing_batch:
        database.session.add(batch)

    database.session.commit()


def _login(client):
    return client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)


class TestPurchaseReceiptBatchSerial:
    """Tests para persistencia de batch_id y serial_no en PurchaseReceiptItem."""

    def test_purchase_receipt_persists_batch_id(self, app_ctx):
        """PurchaseReceiptItem debe guardar batch_id del formulario."""
        client = app_ctx.test_client()
        _login(client)
        response = client.post(
            "/buying/purchase-receipt/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-BATCH",
                "qty_0": "5",
                "uom_0": "UND",
                "rate_0": "10",
                "amount_0": "50",
                "warehouse_0": "WH-TEST",
                "batch_id_0": "LOT-001",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        receipt = (
            database.session.execute(database.select(PurchaseReceipt).order_by(PurchaseReceipt.created.desc()))
            .scalars()
            .first()
        )
        assert receipt is not None

        item = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id))
            .scalars()
            .first()
        )
        assert item is not None
        assert item.batch_id == "LOT-001"

    def test_purchase_receipt_persists_serial_no(self, app_ctx):
        """PurchaseReceiptItem debe guardar serial_no del formulario."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/buying/purchase-receipt/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-SERIAL",
                "qty_0": "1",
                "uom_0": "UND",
                "rate_0": "100",
                "amount_0": "100",
                "warehouse_0": "WH-TEST",
                "serial_no_0": "SN-001",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        receipt = (
            database.session.execute(database.select(PurchaseReceipt).order_by(PurchaseReceipt.created.desc()))
            .scalars()
            .first()
        )
        assert receipt is not None

        item = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id))
            .scalars()
            .first()
        )
        assert item is not None
        assert item.serial_no == "SN-001"

    def test_purchase_receipt_null_batch_when_empty(self, app_ctx):
        """PurchaseReceiptItem batch_id debe ser None cuando no se envía."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/buying/purchase-receipt/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-BATCH",
                "qty_0": "1",
                "uom_0": "UND",
                "rate_0": "10",
                "amount_0": "10",
                "warehouse_0": "WH-TEST",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        receipt = (
            database.session.execute(database.select(PurchaseReceipt).order_by(PurchaseReceipt.created.desc()))
            .scalars()
            .first()
        )
        item = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id))
            .scalars()
            .first()
        )
        assert item.batch_id is None


class TestPurchaseInvoiceBatchSerial:
    """Tests para persistencia de batch_id y serial_no en PurchaseInvoiceItem."""

    def test_purchase_invoice_persists_batch_id(self, app_ctx):
        """PurchaseInvoiceItem debe guardar batch_id del formulario."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/buying/purchase-invoice/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-BATCH",
                "qty_0": "3",
                "uom_0": "UND",
                "rate_0": "20",
                "amount_0": "60",
                "batch_id_0": "LOT-001",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        invoice = (
            database.session.execute(database.select(PurchaseInvoice).order_by(PurchaseInvoice.created.desc()))
            .scalars()
            .first()
        )
        assert invoice is not None

        item = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert item is not None
        assert item.batch_id == "LOT-001"

    def test_purchase_invoice_persists_serial_no(self, app_ctx):
        """PurchaseInvoiceItem debe guardar serial_no del formulario."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/buying/purchase-invoice/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-SERIAL",
                "qty_0": "1",
                "uom_0": "UND",
                "rate_0": "100",
                "amount_0": "100",
                "serial_no_0": "SN-002",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        invoice = (
            database.session.execute(database.select(PurchaseInvoice).order_by(PurchaseInvoice.created.desc()))
            .scalars()
            .first()
        )
        assert invoice is not None

        item = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert item is not None
        assert item.serial_no == "SN-002"


class TestDeliveryNoteBatchSerial:
    """Tests para persistencia de batch_id y serial_no en DeliveryNoteItem."""

    def test_delivery_note_persists_batch_id(self, app_ctx):
        """DeliveryNoteItem debe guardar batch_id del formulario."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/sales/delivery-note/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-BATCH",
                "qty_0": "2",
                "uom_0": "UND",
                "rate_0": "15",
                "amount_0": "30",
                "warehouse_0": "WH-TEST",
                "batch_id_0": "LOT-001",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        note = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()
        assert note is not None

        item = (
            database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=note.id)).scalars().first()
        )
        assert item is not None
        assert item.batch_id == "LOT-001"

    def test_delivery_note_persists_serial_no(self, app_ctx):
        """DeliveryNoteItem debe guardar serial_no del formulario."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/sales/delivery-note/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-SERIAL",
                "qty_0": "1",
                "uom_0": "UND",
                "rate_0": "100",
                "amount_0": "100",
                "warehouse_0": "WH-TEST",
                "serial_no_0": "SN-003",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        note = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()
        assert note is not None

        item = (
            database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=note.id)).scalars().first()
        )
        assert item is not None
        assert item.serial_no == "SN-003"


class TestSalesInvoiceBatchSerial:
    """Tests para persistencia de batch_id y serial_no en SalesInvoiceItem."""

    def test_sales_invoice_persists_batch_id(self, app_ctx):
        """SalesInvoiceItem debe guardar batch_id del formulario."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/sales/sales-invoice/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-BATCH",
                "qty_0": "4",
                "uom_0": "UND",
                "rate_0": "25",
                "amount_0": "100",
                "warehouse_0": "WH-TEST",
                "batch_id_0": "LOT-001",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        invoice = (
            database.session.execute(database.select(SalesInvoice).order_by(SalesInvoice.created.desc())).scalars().first()
        )
        assert invoice is not None

        item = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert item is not None
        assert item.batch_id == "LOT-001"

    def test_sales_invoice_persists_serial_no(self, app_ctx):
        """SalesInvoiceItem debe guardar serial_no del formulario."""
        client = app_ctx.test_client()
        _login(client)

        response = client.post(
            "/sales/sales-invoice/new",
            data={
                "company": "cacao",
                "transaction_currency": "NIO",
                "posting_date": date.today().isoformat(),
                "item_code_0": "ITEM-SERIAL",
                "qty_0": "1",
                "uom_0": "UND",
                "rate_0": "200",
                "amount_0": "200",
                "warehouse_0": "WH-TEST",
                "serial_no_0": "SN-004",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        invoice = (
            database.session.execute(database.select(SalesInvoice).order_by(SalesInvoice.created.desc())).scalars().first()
        )
        assert invoice is not None

        item = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert item is not None
        assert item.serial_no == "SN-004"


class TestStockEntryBatchSerial:
    """Tests para lote/serie en movimientos directos de inventario."""

    def test_material_receipt_persists_batch(self, app_ctx):
        """Un movimiento directo conserva el lote seleccionado en su línea."""
        from cacao_accounting.inventario.services import _save_stock_entry_item

        client = app_ctx.test_client()
        _login(client)
        response = client.get("/inventory/stock-entry/new")
        assert response.status_code == 200
        assert b'"enableBatchSerial": true' in response.data
        assert b'"has_batch": true' in response.data

        entry = StockEntry(
            purpose="material_receipt",
            company="cacao",
            posting_date=date.today(),
            to_warehouse="WH-TEST",
        )
        database.session.add(entry)
        database.session.flush()
        with app_ctx.test_request_context(
            "/inventory/stock-entry/new",
            method="POST",
            data={
                "item_code_0": "ITEM-BATCH",
                "qty_0": "5",
                "uom_0": "UND",
                "rate_0": "10",
                "amount_0": "50",
                "batch_id_0": "LOT-001",
            },
        ):
            _save_stock_entry_item(entry, 0, "ITEM-BATCH")

        line = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entry.id)).scalar_one()
        assert line.batch_id == "LOT-001"
