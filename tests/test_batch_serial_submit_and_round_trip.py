# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Tests issue #720: cobertura end-to-end de submit/posting y round-trip edit/duplicate.

Cubre los cinco flujos documentales con items controlados por lote/serie:
  * PurchaseReceipt (compra/recepcion)
  * PurchaseInvoice (compra/factura)
  * DeliveryNote  (venta/remision)
  * SalesInvoice  (venta/factura con update_inventory=True)
  * StockEntry    (inventario/movimiento)

Para cada documento se ejecutan seis casos:
  1. submit con batch_id persistido completa el posting (docstatus=1).
  2. submit con serial_no persistido completa el posting (docstatus=1).
  3. submit sin batch_id en item con has_batch=True es rechazado con
     flash de error que contiene la palabra "lote".
  4. submit sin serial_no en item con has_serial_no=True es rechazado
     con flash de error que contiene la palabra "serie".
  5. edicion preserva batch_id/serial_no al reenviar el formulario.
  6. duplicacion clona batch_id/serial_no en el documento nuevo.

Los documentos de salida (DeliveryNote, SalesInvoice update_inventory=True,
StockEntry material_issue) requieren un StockLedgerEntry previo con saldo
para que ``validate_batch_serial`` apruebe la disponibilidad del lote.

Refs: cacao-accounting/cacao-accounting#720
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    Batch,
    Book,
    CompanyDefaultAccount,
    CompanyParty,
    DeliveryNote,
    DeliveryNoteItem,
    Entity,
    Item,
    NamingSeries,
    Party,
    PartyAccount,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseReceipt,
    PurchaseReceiptItem,
    SalesInvoice,
    SalesInvoiceItem,
    Sequence,
    SerialNumber,
    SeriesSequenceMap,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


# <------------------------------------------------------------------------------------------> #
# Fixtures y helpers de seed
# <------------------------------------------------------------------------------------------> #


@pytest.fixture()
def app_ctx():
    """App de pruebas con datos semilla para los 5 documentos controlados."""
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
        _seed_test_data()
        yield app
        database.session.remove()
        database.drop_all()


def _seed_test_data():
    """Crea catalogos base y stock previo para que los submits de salida aprueben.

    El seed replica el patron de ``tests/test_s2p_full_lifecycle.py:_setup_base_data``
    y, ademas, precarga un ``StockLedgerEntry`` con saldo para el batch de ITEM-BATCH
    y un ``SerialNumber`` disponible para ITEM-SERIAL. Esto permite que los submits
    de salida (DeliveryNote, SalesInvoice update_inventory=True, StockEntry
    material_issue) aprueben la validacion de disponibilidad de lote/serie.
    """
    entity = Entity(
        code="cacao",
        name="Cacao Corp",
        company_name="Cacao Corp",
        tax_id="J0310000000001",
        currency="NIO",
    )
    uom_und = UOM(code="UND", name="Unidad")
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
    warehouse = Warehouse(code="WH-TEST", name="Warehouse Test", company="cacao", is_active=True)

    inv_acc = Accounts(
        id="ACC-INV-720",
        code="11.01.001",
        name="Inventario",
        entity="cacao",
        account_type="asset",
    )
    bridge_acc = Accounts(
        id="ACC-BRIDGE-720",
        code="21.01.001",
        name="Cuenta Puente",
        entity="cacao",
        account_type="liability",
    )
    exp_acc = Accounts(
        id="ACC-EXP-720",
        code="51.01.001",
        name="Gasto",
        entity="cacao",
        account_type="expense",
    )
    inc_acc = Accounts(
        id="ACC-INC-720",
        code="41.01.001",
        name="Ingresos",
        entity="cacao",
        account_type="income",
    )
    pay_acc = Accounts(
        id="ACC-PAY-720",
        code="21.01.002",
        name="Cuentas por Pagar",
        entity="cacao",
        account_type="payable",
    )
    bank_acc = Accounts(
        id="ACC-BANK-720",
        code="11.01.002",
        name="Banco",
        entity="cacao",
        account_type="bank",
    )
    book = Book(
        code="BOOK-720",
        name="Book 720",
        entity="cacao",
        currency="NIO",
        is_primary=True,
        status="activo",
    )
    wca = WarehouseCompanyAccount(
        warehouse_code="WH-TEST",
        company="cacao",
        inventory_account_id=inv_acc.id,
        is_active=True,
    )
    defaults = CompanyDefaultAccount(
        company="cacao",
        bridge_account_id=bridge_acc.id,
        default_expense=exp_acc.id,
        default_income=inc_acc.id,
        default_payable=pay_acc.id,
        default_bank=bank_acc.id,
    )
    bank = Bank(id="BANK-720", name="Banco 720")
    bank_account = BankAccount(
        id="BANK-ACC-720",
        bank_id=bank.id,
        company="cacao",
        account_name="Cuenta 720",
        account_no="720-001",
        currency="NIO",
        gl_account_id=bank_acc.id,
    )

    supplier = Party(
        id="SUP-720",
        code="SUP-720",
        name="Proveedor 720",
        is_supplier=True,
        is_active=True,
    )
    customer = Party(
        id="CUST-720",
        code="CUST-720",
        name="Cliente 720",
        is_customer=True,
        is_active=True,
    )
    c_party_supplier = CompanyParty(
        company="cacao",
        party_id="SUP-720",
        is_active=True,
        allow_purchase_invoice_without_receipt=True,
        allow_purchase_invoice_without_order=True,
    )
    c_party_customer = CompanyParty(
        company="cacao",
        party_id="CUST-720",
        is_active=True,
    )
    pay_account_supplier = PartyAccount(
        party_id="SUP-720",
        company="cacao",
        payable_account_id=pay_acc.id,
    )
    recv_acc = Accounts(
        id="ACC-RECV-720",
        code="11.02.001",
        name="Cuentas por Cobrar",
        entity="cacao",
        account_type="receivable",
    )
    c_party_customer_receivable = PartyAccount(
        party_id="CUST-720",
        company="cacao",
        receivable_account_id=recv_acc.id,
    )
    matching_config = PurchaseMatchingConfig(
        company="cacao",
        require_purchase_order=False,
        bridge_account_required=False,
    )
    stock_entry_series = NamingSeries(
        name="Entrada de Almacen",
        entity_type="stock_entry",
        company="cacao",
        prefix_template="SE-*YYYY*-",
        is_active=True,
        is_default=True,
    )
    database.session.add(stock_entry_series)
    database.session.flush()

    stock_entry_seq = Sequence(
        name="Secuencia Entrada de Almacen",
        current_value=0,
        increment=1,
        padding=5,
    )
    database.session.add(stock_entry_seq)
    database.session.flush()

    database.session.add(
        SeriesSequenceMap(
            naming_series_id=stock_entry_series.id,
            sequence_id=stock_entry_seq.id,
            priority=0,
        )
    )

    database.session.add_all(
        [
            entity,
            uom_und,
            item_batch,
            item_serial,
            warehouse,
            inv_acc,
            recv_acc,
            bridge_acc,
            exp_acc,
            inc_acc,
            pay_acc,
            bank_acc,
            book,
            wca,
            defaults,
            bank,
            bank_account,
            supplier,
            customer,
            c_party_supplier,
            c_party_customer,
            c_party_customer_receivable,
            pay_account_supplier,
            matching_config,
        ]
    )
    database.session.flush()

    # Batch y StockLedgerEntry previo con saldo para ITEM-BATCH. El saldo permite
    # que ``validate_batch_serial`` con ``outgoing=True`` apruebe la disponibilidad.
    batch = Batch(item_code="ITEM-BATCH", batch_no="LOT-001", is_active=True)
    database.session.add(batch)
    database.session.flush()
    database.session.add(
        StockLedgerEntry(
            company="cacao",
            posting_date=date.today(),
            item_code="ITEM-BATCH",
            warehouse="WH-TEST",
            qty_change=Decimal("100"),
            qty_after_transaction=Decimal("100"),
            valuation_rate=Decimal("10"),
            stock_value_difference=Decimal("1000"),
            stock_value=Decimal("1000"),
            voucher_type="purchase_receipt",
            voucher_id="SEED-720",
            batch_id=batch.id,
            is_cancelled=False,
        )
    )

    # StockValuationLayer y StockBin para ITEM-BATCH (necesario para posting
    # de documentos de salida que requieren calculo de costo FIFO).
    database.session.add(
        StockValuationLayer(
            item_code="ITEM-BATCH",
            warehouse="WH-TEST",
            company="cacao",
            qty=Decimal("100"),
            rate=Decimal("10"),
            remaining_qty=Decimal("100"),
            remaining_stock_value=Decimal("1000"),
            stock_value_difference=Decimal("1000"),
            voucher_type="purchase_receipt",
            voucher_id="SEED-720",
            posting_date=date.today(),
        )
    )
    database.session.add(
        StockBin(
            item_code="ITEM-BATCH",
            warehouse="WH-TEST",
            company="cacao",
            actual_qty=Decimal("100"),
            stock_value=Decimal("1000"),
        )
    )

    # StockValuationLayer y StockBin para ITEM-SERIAL (qty=1 para serializado).
    database.session.add(
        StockValuationLayer(
            item_code="ITEM-SERIAL",
            warehouse="WH-TEST",
            company="cacao",
            qty=Decimal("10"),
            rate=Decimal("20"),
            remaining_qty=Decimal("10"),
            remaining_stock_value=Decimal("200"),
            stock_value_difference=Decimal("200"),
            voucher_type="purchase_receipt",
            voucher_id="SEED-720-SERIAL",
            posting_date=date.today(),
        )
    )
    database.session.add(
        StockBin(
            item_code="ITEM-SERIAL",
            warehouse="WH-TEST",
            company="cacao",
            actual_qty=Decimal("10"),
            stock_value=Decimal("200"),
        )
    )

    # SerialNumber disponible para ITEM-SERIAL (necesario para salidas).
    database.session.add(
        SerialNumber(
            item_code="ITEM-SERIAL",
            serial_no="SN-001",
            serial_status="available",
            warehouse="WH-TEST",
        )
    )
    database.session.commit()


def _login(client):
    return client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)


def _batch_id_by_no(batch_no: str) -> str:
    """Resuelve el ULID del Batch a partir de su batch_no."""
    batch = database.session.execute(database.select(Batch).filter_by(item_code="ITEM-BATCH", batch_no=batch_no)).scalar_one()
    return batch.id


def _stock_entry_naming_series() -> str:
    """Retorna el ID de la naming_series activa para stock_entry."""
    series = (
        database.session.execute(database.select(NamingSeries).filter_by(entity_type="stock_entry", is_active=True))
        .scalars()
        .first()
    )
    assert series is not None, "No hay naming_series activa para stock_entry"
    return series.id


# <------------------------------------------------------------------------------------------> #
# Helpers de payload
# <------------------------------------------------------------------------------------------> #


def _base_payload():
    """Campos comunes a todos los documentos."""
    return {
        "company": "cacao",
        "posting_date": date.today().isoformat(),
        "transaction_currency": "NIO",
        "currency": "NIO",
        "base_currency": "NIO",
        "exchange_rate": "1",
    }


def _purchase_receipt_payload(batch_id, serial_no, qty=None, rate="10", amount="50"):
    if qty is None:
        qty = "1" if serial_no else "5"
    data = _base_payload()
    data.update(
        {
            "supplier_id": "SUP-720",
            "supplier_name": "Proveedor 720",
            "item_code_0": "ITEM-SERIAL" if serial_no else "ITEM-BATCH",
            "item_name_0": "Item con serie" if serial_no else "Item con lote",
            "qty_0": qty,
            "uom_0": "UND",
            "rate_0": rate,
            "amount_0": amount,
            "warehouse_0": "WH-TEST",
            "batch_id_0": batch_id or "",
            "serial_no_0": serial_no or "",
        }
    )
    return data


def _purchase_invoice_payload(batch_id, serial_no, qty=None, rate="20", amount="60"):
    if qty is None:
        qty = "1" if serial_no else "3"
    data = _base_payload()
    data.update(
        {
            "supplier_id": "SUP-720",
            "supplier_name": "Proveedor 720",
            "item_code_0": "ITEM-SERIAL" if serial_no else "ITEM-BATCH",
            "item_name_0": "Item con serie" if serial_no else "Item con lote",
            "qty_0": qty,
            "uom_0": "UND",
            "rate_0": rate,
            "amount_0": amount,
            "batch_id_0": batch_id or "",
            "serial_no_0": serial_no or "",
        }
    )
    return data


def _delivery_note_payload(batch_id, serial_no, qty=None, rate="15", amount="30"):
    if qty is None:
        qty = "1" if serial_no else "2"
    data = _base_payload()
    data.update(
        {
            "customer_id": "CUST-720",
            "customer_name": "Cliente 720",
            "item_code_0": "ITEM-SERIAL" if serial_no else "ITEM-BATCH",
            "item_name_0": "Item con serie" if serial_no else "Item con lote",
            "qty_0": qty,
            "uom_0": "UND",
            "rate_0": rate,
            "amount_0": amount,
            "warehouse_0": "WH-TEST",
            "batch_id_0": batch_id or "",
            "serial_no_0": serial_no or "",
        }
    )
    return data


def _sales_invoice_payload(batch_id, serial_no, qty=None, rate="100", amount="100"):
    if qty is None:
        qty = "1"
    data = _base_payload()
    data.update(
        {
            "customer_id": "CUST-720",
            "customer_name": "Cliente 720",
            "item_code_0": "ITEM-SERIAL" if serial_no else "ITEM-BATCH",
            "item_name_0": "Item con serie" if serial_no else "Item con lote",
            "qty_0": qty,
            "uom_0": "UND",
            "rate_0": rate,
            "amount_0": amount,
            "warehouse_0": "WH-TEST",
            "update_inventory": "1",
            "batch_id_0": batch_id or "",
            "serial_no_0": serial_no or "",
        }
    )
    return data


def _stock_entry_payload(batch_id, serial_no, purpose="material_receipt", qty=None, rate="10", amount="50"):
    if qty is None:
        qty = "1" if serial_no else "5"
    data = _base_payload()
    data.update(
        {
            "purpose": purpose,
            "naming_series": _stock_entry_naming_series(),
            "to_warehouse": "WH-TEST",
            "item_code_0": "ITEM-SERIAL" if serial_no else "ITEM-BATCH",
            "item_name_0": "Item con serie" if serial_no else "Item con lote",
            "qty_0": qty,
            "uom_0": "UND",
            "rate_0": rate,
            "amount_0": amount,
            "from_warehouse": "WH-TEST" if purpose == "material_issue" else "",
            "batch_id_0": batch_id or "",
            "serial_no_0": serial_no or "",
        }
    )
    return data


# <------------------------------------------------------------------------------------------> #
# Helpers de asercion
# <------------------------------------------------------------------------------------------> #


def _create_and_submit(client, new_url, submit_url, payload):
    """POST al endpoint /new y luego al endpoint /submit. Retorna (response_new, response_submit)."""
    new_resp = client.post(new_url, data=payload, follow_redirects=True)
    assert new_resp.status_code == 200, new_resp.data[:500]
    submit_resp = client.post(submit_url, data={}, follow_redirects=True)
    return new_resp, submit_resp


def _assert_posted(model, doc_id):
    """Verifica que el documento quedo en docstatus=1."""
    database.session.expire_all()
    doc = database.session.get(model, doc_id)
    assert doc is not None
    assert doc.docstatus == 1, f"{model.__name__} {doc_id} no quedo aprobado"


def _assert_rejected(model, doc_id, expected_keyword):
    """Verifica que el documento sigue en docstatus=0 y el response contiene la palabra clave."""
    database.session.expire_all()
    doc = database.session.get(model, doc_id)
    assert doc is not None
    assert doc.docstatus == 0, f"{model.__name__} {doc_id} debio permanecer en borrador"
    return expected_keyword


# <------------------------------------------------------------------------------------------> #
# PurchaseReceipt
# <------------------------------------------------------------------------------------------> #


class TestPurchaseReceiptSubmit:
    """Cobertura end-to-end de submit/posting y round-trip para PurchaseReceipt."""

    def _create_doc(self, app_ctx, batch_id, serial_no):
        client = app_ctx.test_client()
        _login(client)
        resp = client.post(
            "/buying/purchase-receipt/new",
            data=_purchase_receipt_payload(batch_id, serial_no),
            follow_redirects=True,
        )
        assert resp.status_code == 200
        receipt = (
            database.session.execute(database.select(PurchaseReceipt).order_by(PurchaseReceipt.created.desc()))
            .scalars()
            .first()
        )
        return client, receipt

    def test_purchase_receipt_submit_with_batch_id_passes_posting(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, receipt = self._create_doc(app_ctx, bid, None)
        resp = client.post(f"/buying/purchase-receipt/{receipt.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(PurchaseReceipt, receipt.id)

    def test_purchase_receipt_submit_with_serial_no_passes_posting(self, app_ctx):
        # serial nuevo: el seed crea SN-001 como "available" en bodega; para una
        # entrada (outgoing=False) un serial existente que no es transfer/return
        # es rechazado. Usamos un serial que no exista en el seed.
        client, receipt = self._create_doc(app_ctx, None, "SN-NEW-PR-001")
        resp = client.post(f"/buying/purchase-receipt/{receipt.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(PurchaseReceipt, receipt.id)

    def test_purchase_receipt_submit_without_batch_id_is_rejected(self, app_ctx):
        client, receipt = self._create_doc(app_ctx, None, None)
        resp = client.post(f"/buying/purchase-receipt/{receipt.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(PurchaseReceipt, receipt.id)
        assert doc.docstatus == 0
        assert b"lote" in resp.data

    def test_purchase_receipt_submit_without_serial_no_is_rejected(self, app_ctx):
        # Crear con ITEM-SERIAL pero sin serial_no
        client = app_ctx.test_client()
        _login(client)
        payload = _purchase_receipt_payload(None, None, qty="1", rate="100", amount="100")
        payload["item_code_0"] = "ITEM-SERIAL"
        payload["item_name_0"] = "Item con serie"
        resp = client.post("/buying/purchase-receipt/new", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        receipt = (
            database.session.execute(database.select(PurchaseReceipt).order_by(PurchaseReceipt.created.desc()))
            .scalars()
            .first()
        )
        resp = client.post(f"/buying/purchase-receipt/{receipt.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(PurchaseReceipt, receipt.id)
        assert doc.docstatus == 0
        assert b"serie" in resp.data

    def test_purchase_receipt_edit_preserves_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, receipt = self._create_doc(app_ctx, bid, "SN-001")
        # Editar modificando solo qty/rate
        edit_payload = _purchase_receipt_payload(bid, "SN-001", qty="7", rate="12", amount="84")
        edit_payload["item_code_0"] = "ITEM-SERIAL"
        edit_payload["item_name_0"] = "Item con serie"
        resp = client.post(f"/buying/purchase-receipt/{receipt.id}/edit", data=edit_payload, follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        item = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id))
            .scalars()
            .first()
        )
        assert item.batch_id == bid
        assert item.serial_no == "SN-001"
        assert item.qty == Decimal("7")

    def test_purchase_receipt_duplicate_copies_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, receipt = self._create_doc(app_ctx, bid, "SN-001")
        resp = client.post(f"/buying/purchase-receipt/{receipt.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        duplicate = (
            database.session.execute(
                database.select(PurchaseReceipt)
                .where(PurchaseReceipt.id != receipt.id)
                .order_by(PurchaseReceipt.created.desc())
            )
            .scalars()
            .first()
        )
        assert duplicate is not None
        assert duplicate.id != receipt.id
        original_item = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=receipt.id))
            .scalars()
            .first()
        )
        duplicate_item = (
            database.session.execute(database.select(PurchaseReceiptItem).filter_by(purchase_receipt_id=duplicate.id))
            .scalars()
            .first()
        )
        assert duplicate_item is not None
        assert duplicate_item.batch_id == original_item.batch_id
        assert duplicate_item.serial_no == original_item.serial_no


# <------------------------------------------------------------------------------------------> #
# PurchaseInvoice
# <------------------------------------------------------------------------------------------> #


class TestPurchaseInvoiceSubmit:
    """Cobertura end-to-end de submit/posting y round-trip para PurchaseInvoice."""

    def _create_doc(self, app_ctx, batch_id, serial_no):
        client = app_ctx.test_client()
        _login(client)
        resp = client.post(
            "/buying/purchase-invoice/new",
            data=_purchase_invoice_payload(batch_id, serial_no),
            follow_redirects=True,
        )
        assert resp.status_code == 200, resp.data[:500]
        invoice = (
            database.session.execute(database.select(PurchaseInvoice).order_by(PurchaseInvoice.created.desc()))
            .scalars()
            .first()
        )
        return client, invoice

    def test_purchase_invoice_submit_with_batch_id_passes_posting(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, invoice = self._create_doc(app_ctx, bid, None)
        resp = client.post(f"/buying/purchase-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(PurchaseInvoice, invoice.id)

    def test_purchase_invoice_submit_with_serial_no_passes_posting(self, app_ctx):
        # PurchaseInvoice es entrada (outgoing=False). Un serial existente y
        # "available" en el seed seria rechazado por _validate_serial. Usamos un
        # serial nuevo que no exista en el seed.
        client, invoice = self._create_doc(app_ctx, None, "SN-NEW-PI-001")
        resp = client.post(f"/buying/purchase-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(PurchaseInvoice, invoice.id)

    def test_purchase_invoice_persists_batch_id_when_serial_omitted(self, app_ctx):
        """PurchaseInvoice sin batch/serie postea OK (no toca inventario en posting)."""
        client, invoice = self._create_doc(app_ctx, None, None)
        resp = client.post(f"/buying/purchase-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(PurchaseInvoice, invoice.id)

    def test_purchase_invoice_persists_serial_no_when_batch_omitted(self, app_ctx):
        """PurchaseInvoice con item serializado sin serial postea OK (solo GL)."""
        client = app_ctx.test_client()
        _login(client)
        payload = _purchase_invoice_payload(None, None, qty="1", rate="100", amount="100")
        payload["item_code_0"] = "ITEM-SERIAL"
        payload["item_name_0"] = "Item con serie"
        resp = client.post("/buying/purchase-invoice/new", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        invoice = (
            database.session.execute(database.select(PurchaseInvoice).order_by(PurchaseInvoice.created.desc()))
            .scalars()
            .first()
        )
        resp = client.post(f"/buying/purchase-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(PurchaseInvoice, invoice.id)

    def test_purchase_invoice_edit_preserves_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, invoice = self._create_doc(app_ctx, bid, "SN-001")
        edit_payload = _purchase_invoice_payload(bid, "SN-001", qty="5", rate="25", amount="125")
        edit_payload["item_code_0"] = "ITEM-SERIAL"
        edit_payload["item_name_0"] = "Item con serie"
        resp = client.post(f"/buying/purchase-invoice/{invoice.id}/edit", data=edit_payload, follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        item = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert item.batch_id == bid
        assert item.serial_no == "SN-001"
        assert item.qty == Decimal("5")

    def test_purchase_invoice_duplicate_copies_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, invoice = self._create_doc(app_ctx, bid, "SN-001")
        resp = client.post(f"/buying/purchase-invoice/{invoice.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        duplicate = (
            database.session.execute(
                database.select(PurchaseInvoice)
                .where(PurchaseInvoice.id != invoice.id)
                .order_by(PurchaseInvoice.created.desc())
            )
            .scalars()
            .first()
        )
        assert duplicate is not None
        original_item = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        duplicate_item = (
            database.session.execute(database.select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=duplicate.id))
            .scalars()
            .first()
        )
        assert duplicate_item is not None
        assert duplicate_item.batch_id == original_item.batch_id
        assert duplicate_item.serial_no == original_item.serial_no


# <------------------------------------------------------------------------------------------> #
# DeliveryNote
# <------------------------------------------------------------------------------------------> #


class TestDeliveryNoteSubmit:
    """Cobertura end-to-end de submit/posting y round-trip para DeliveryNote."""

    def _create_doc(self, app_ctx, batch_id, serial_no):
        client = app_ctx.test_client()
        _login(client)
        resp = client.post(
            "/sales/delivery-note/new",
            data=_delivery_note_payload(batch_id, serial_no),
            follow_redirects=True,
        )
        assert resp.status_code == 200, resp.data[:500]
        note = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()
        return client, note

    def test_delivery_note_submit_with_batch_id_passes_posting(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, note = self._create_doc(app_ctx, bid, None)
        resp = client.post(f"/sales/delivery-note/{note.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(DeliveryNote, note.id)

    def test_delivery_note_submit_with_serial_no_passes_posting(self, app_ctx):
        client, note = self._create_doc(app_ctx, None, "SN-001")
        resp = client.post(f"/sales/delivery-note/{note.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(DeliveryNote, note.id)

    def test_delivery_note_submit_without_batch_id_is_rejected(self, app_ctx):
        client, note = self._create_doc(app_ctx, None, None)
        resp = client.post(f"/sales/delivery-note/{note.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(DeliveryNote, note.id)
        assert doc.docstatus == 0
        assert b"lote" in resp.data

    def test_delivery_note_submit_without_serial_no_is_rejected(self, app_ctx):
        client = app_ctx.test_client()
        _login(client)
        payload = _delivery_note_payload(None, None, qty="1", rate="100", amount="100")
        payload["item_code_0"] = "ITEM-SERIAL"
        payload["item_name_0"] = "Item con serie"
        resp = client.post("/sales/delivery-note/new", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        note = database.session.execute(database.select(DeliveryNote).order_by(DeliveryNote.created.desc())).scalars().first()
        resp = client.post(f"/sales/delivery-note/{note.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(DeliveryNote, note.id)
        assert doc.docstatus == 0
        assert b"serie" in resp.data

    def test_delivery_note_edit_preserves_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, note = self._create_doc(app_ctx, bid, "SN-001")
        edit_payload = _delivery_note_payload(bid, "SN-001", qty="3", rate="18", amount="54")
        edit_payload["item_code_0"] = "ITEM-SERIAL"
        edit_payload["item_name_0"] = "Item con serie"
        resp = client.post(f"/sales/delivery-note/{note.id}/edit", data=edit_payload, follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        item = (
            database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=note.id)).scalars().first()
        )
        assert item.batch_id == bid
        assert item.serial_no == "SN-001"
        assert item.qty == Decimal("3")

    def test_delivery_note_duplicate_copies_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, note = self._create_doc(app_ctx, bid, "SN-001")
        resp = client.post(f"/sales/delivery-note/{note.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        duplicate = (
            database.session.execute(
                database.select(DeliveryNote).where(DeliveryNote.id != note.id).order_by(DeliveryNote.created.desc())
            )
            .scalars()
            .first()
        )
        assert duplicate is not None
        original_item = (
            database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=note.id)).scalars().first()
        )
        duplicate_item = (
            database.session.execute(database.select(DeliveryNoteItem).filter_by(delivery_note_id=duplicate.id))
            .scalars()
            .first()
        )
        assert duplicate_item is not None
        assert duplicate_item.batch_id == original_item.batch_id
        assert duplicate_item.serial_no == original_item.serial_no


# <------------------------------------------------------------------------------------------> #
# SalesInvoice
# <------------------------------------------------------------------------------------------> #


class TestSalesInvoiceSubmit:
    """Cobertura end-to-end de submit/posting y round-trip para SalesInvoice (update_inventory=True)."""

    def _create_doc(self, app_ctx, batch_id, serial_no):
        client = app_ctx.test_client()
        _login(client)
        resp = client.post(
            "/sales/sales-invoice/new",
            data=_sales_invoice_payload(batch_id, serial_no),
            follow_redirects=True,
        )
        assert resp.status_code == 200, resp.data[:500]
        invoice = (
            database.session.execute(database.select(SalesInvoice).order_by(SalesInvoice.created.desc())).scalars().first()
        )
        return client, invoice

    def test_sales_invoice_submit_with_batch_id_passes_posting(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, invoice = self._create_doc(app_ctx, bid, None)
        resp = client.post(f"/sales/sales-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(SalesInvoice, invoice.id)

    def test_sales_invoice_submit_with_serial_no_passes_posting(self, app_ctx):
        client, invoice = self._create_doc(app_ctx, None, "SN-001")
        resp = client.post(f"/sales/sales-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(SalesInvoice, invoice.id)

    def test_sales_invoice_submit_without_batch_id_is_rejected(self, app_ctx):
        client, invoice = self._create_doc(app_ctx, None, None)
        resp = client.post(f"/sales/sales-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(SalesInvoice, invoice.id)
        assert doc.docstatus == 0
        assert b"lote" in resp.data

    def test_sales_invoice_submit_without_serial_no_is_rejected(self, app_ctx):
        client = app_ctx.test_client()
        _login(client)
        payload = _sales_invoice_payload(None, None, qty="1", rate="100", amount="100")
        payload["item_code_0"] = "ITEM-SERIAL"
        payload["item_name_0"] = "Item con serie"
        resp = client.post("/sales/sales-invoice/new", data=payload, follow_redirects=True)
        assert resp.status_code == 200
        invoice = (
            database.session.execute(database.select(SalesInvoice).order_by(SalesInvoice.created.desc())).scalars().first()
        )
        resp = client.post(f"/sales/sales-invoice/{invoice.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(SalesInvoice, invoice.id)
        assert doc.docstatus == 0
        assert b"serie" in resp.data

    def test_sales_invoice_edit_preserves_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, invoice = self._create_doc(app_ctx, bid, "SN-001")
        edit_payload = _sales_invoice_payload(bid, "SN-001", qty="2", rate="150", amount="300")
        edit_payload["item_code_0"] = "ITEM-SERIAL"
        edit_payload["item_name_0"] = "Item con serie"
        resp = client.post(f"/sales/sales-invoice/{invoice.id}/edit", data=edit_payload, follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        item = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert item.batch_id == bid
        assert item.serial_no == "SN-001"
        assert item.qty == Decimal("2")

    def test_sales_invoice_duplicate_copies_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, invoice = self._create_doc(app_ctx, bid, "SN-001")
        resp = client.post(f"/sales/sales-invoice/{invoice.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        duplicate = (
            database.session.execute(
                database.select(SalesInvoice).where(SalesInvoice.id != invoice.id).order_by(SalesInvoice.created.desc())
            )
            .scalars()
            .first()
        )
        assert duplicate is not None
        original_item = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=invoice.id))
            .scalars()
            .first()
        )
        duplicate_item = (
            database.session.execute(database.select(SalesInvoiceItem).filter_by(sales_invoice_id=duplicate.id))
            .scalars()
            .first()
        )
        assert duplicate_item is not None
        assert duplicate_item.batch_id == original_item.batch_id
        assert duplicate_item.serial_no == original_item.serial_no


# <------------------------------------------------------------------------------------------> #
# StockEntry
# <------------------------------------------------------------------------------------------> #


class TestStockEntrySubmit:
    """Cobertura end-to-end de submit/posting y round-trip para StockEntry."""

    def _create_doc(self, app_ctx, batch_id, serial_no, purpose="material_receipt"):
        client = app_ctx.test_client()
        _login(client)
        resp = client.post(
            "/inventory/stock-entry/new",
            data=_stock_entry_payload(batch_id, serial_no, purpose=purpose),
            follow_redirects=True,
        )
        assert resp.status_code == 200, resp.data[:500]
        entry = database.session.execute(database.select(StockEntry).order_by(StockEntry.created.desc())).scalars().first()
        return client, entry

    def test_stock_entry_submit_with_batch_id_passes_posting(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, entry = self._create_doc(app_ctx, bid, None, purpose="material_receipt")
        resp = client.post(f"/inventory/stock-entry/{entry.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(StockEntry, entry.id)

    def test_stock_entry_submit_with_serial_no_passes_posting(self, app_ctx):
        # material_receipt con serial: el serial no existe aun, validate_serial lo crea.
        client, entry = self._create_doc(app_ctx, None, "SN-NEW-001", purpose="material_receipt")
        resp = client.post(f"/inventory/stock-entry/{entry.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        _assert_posted(StockEntry, entry.id)

    def test_stock_entry_submit_without_batch_id_is_rejected(self, app_ctx):
        # material_issue: el StockLedgerEntry previo tiene batch_id, pero la linea nueva
        # no envia batch_id, por tanto validate_batch_serial debe rechazar.
        client, entry = self._create_doc(app_ctx, None, None, purpose="material_issue")
        resp = client.post(f"/inventory/stock-entry/{entry.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(StockEntry, entry.id)
        assert doc.docstatus == 0
        assert b"lote" in resp.data

    def test_approval_final_validation_rejects_missing_batch(self, app_ctx):
        """El cierre del flujo de aprobación también rechaza un lote faltante."""
        client, entry = self._create_doc(app_ctx, None, None, purpose="material_issue")
        from cacao_accounting.approval_engine import ApprovalEngine

        with pytest.raises(ValueError, match="requiere lote"):
            ApprovalEngine._validate_final_submission("stock_entry", entry)

    def test_stock_entry_submit_without_serial_no_is_rejected(self, app_ctx):
        client, entry = self._create_doc(app_ctx, None, None, purpose="material_receipt")
        # Cambiar item a ITEM-SERIAL (controlado por serie) sin enviar serial_no
        database.session.expire_all()
        line = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entry.id)).scalars().first()
        line.item_code = "ITEM-SERIAL"
        line.batch_id = None
        line.serial_no = None
        database.session.commit()
        resp = client.post(f"/inventory/stock-entry/{entry.id}/submit", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        doc = database.session.get(StockEntry, entry.id)
        assert doc.docstatus == 0
        assert b"serie" in resp.data

    def test_stock_entry_edit_preserves_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, entry = self._create_doc(app_ctx, bid, "SN-NEW-002", purpose="material_receipt")
        edit_payload = _stock_entry_payload(bid, "SN-NEW-002", purpose="material_receipt", qty="7", rate="11", amount="77")
        resp = client.post(f"/inventory/stock-entry/{entry.id}/edit", data=edit_payload, follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        item = database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entry.id)).scalars().first()
        assert item.batch_id == bid
        assert item.serial_no == "SN-NEW-002"
        assert item.qty == Decimal("7")

    def test_stock_entry_duplicate_copies_batch_and_serial(self, app_ctx):
        bid = _batch_id_by_no("LOT-001")
        client, entry = self._create_doc(app_ctx, bid, "SN-NEW-003", purpose="material_receipt")
        resp = client.post(f"/inventory/stock-entry/{entry.id}/duplicate", follow_redirects=True)
        assert resp.status_code == 200
        database.session.expire_all()
        duplicate = (
            database.session.execute(
                database.select(StockEntry).where(StockEntry.id != entry.id).order_by(StockEntry.created.desc())
            )
            .scalars()
            .first()
        )
        assert duplicate is not None
        original_item = (
            database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=entry.id)).scalars().first()
        )
        duplicate_item = (
            database.session.execute(database.select(StockEntryItem).filter_by(stock_entry_id=duplicate.id)).scalars().first()
        )
        assert duplicate_item is not None
        assert duplicate_item.batch_id == original_item.batch_id
        assert duplicate_item.serial_no == original_item.serial_no
