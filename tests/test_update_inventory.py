# SPDX-License-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de update_inventory en Factura de Venta (O2C-01)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Accounts,
    DeliveryNote,
    DeliveryNoteItem,
    ExchangeRate,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    StockEntry,
    StockEntryItem,
    StockValuationLayer,
    StockLedgerEntry,
    Warehouse,
    StockBin,
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
        database.session.add_all(
            [
                ExchangeRate(origin="NIO", destination="USD", rate=Decimal("0.0273224044"), date=date(2026, 5, 1)),
                ExchangeRate(origin="NIO", destination="EUR", rate=Decimal("0.0245"), date=date(2026, 5, 1)),
                ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.5"), date=date(2026, 5, 1)),
            ]
        )
        database.session.commit()
        yield app


def login(client, username, password):
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def _setup_inventory_context(company="cacao"):
    """Configura el contexto de inventario necesario para DN posting."""
    from cacao_accounting.database import Entity

    entity = database.session.execute(database.select(Entity).filter_by(code=company)).scalars().first()
    if entity:
        entity.valuation_method = "fifo"
        database.session.flush()

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

    bin_record = StockBin(
        item_code=item.code,
        warehouse=warehouse.code,
        company=company,
        actual_qty=qty,
        stock_value=qty * rate,
    )
    database.session.add(bin_record)
    database.session.flush()


def test_submit_with_update_inventory_creates_delivery_note(app_ctx):
    """Factura con update_inventory=True y sin DN crea DN automáticamente."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    warehouse, item, _cogs_account, _inventory_account = _setup_inventory_context()
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
        transaction_currency="NIO",
        base_currency="NIO",
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


def test_auto_delivery_note_copies_invoice_currency_context(app_ctx):
    """La DN automática conserva la moneda y la tasa de la factura."""
    from cacao_accounting.ventas.services import _create_delivery_note_from_invoice

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()
    _ensure_default_warehouse(item, warehouse)
    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    invoice = SalesInvoice(
        id="SI-INV-FX-DN",
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_type="sales_invoice",
        transaction_currency="USD",
        base_currency="NIO",
        exchange_rate=Decimal("36.5"),
        docstatus=0,
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id=invoice.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("1"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("10"),
        warehouse=warehouse.code,
    )
    database.session.add_all([invoice, invoice_item])
    database.session.flush()

    with (
        patch("cacao_accounting.ventas.services.submit_document"),
        patch("cacao_accounting.ventas.services._release_reservation_for_delivery_note"),
    ):
        delivery_note = _create_delivery_note_from_invoice(invoice)

    assert delivery_note.transaction_currency == "USD"
    assert delivery_note.base_currency == "NIO"
    assert delivery_note.exchange_rate == Decimal("36.5")


def test_auto_delivery_note_rejects_default_warehouse_from_another_company(app_ctx):
    """An invoice cannot use an item's default warehouse from another company."""
    from cacao_accounting.contabilidad.posting import PostingError
    from cacao_accounting.ventas.services import _create_delivery_note_from_invoice

    warehouse, item, _cogs_account, _inventory_account = _setup_inventory_context()
    warehouse.company = "cafe"
    database.session.add(warehouse)
    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    invoice = SalesInvoice(
        id="SI-INV-FOREIGN-WH",
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_type="sales_invoice",
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=0,
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id=invoice.id,
        item_code=item.code,
        item_name=item.name,
        qty=Decimal("1"),
        uom="UND",
        rate=Decimal("10"),
        amount=Decimal("10"),
    )
    item.default_warehouse_id = warehouse.code
    database.session.add_all([invoice, invoice_item])
    database.session.flush()

    with pytest.raises(PostingError, match="no pertenece a la compañía"):
        _create_delivery_note_from_invoice(invoice)


def test_sales_delivery_return_restores_historical_inventory_cost(app_ctx):
    """A sales return restores the original delivery cost, not the sales price."""
    from cacao_accounting.contabilidad.posting_service import (
        _create_delivery_note_gl_entries,
        _create_stock_ledger_for_document,
    )

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()
    original = DeliveryNote(company="cacao", posting_date=date(2026, 5, 1), docstatus=1)
    database.session.add(original)
    database.session.flush()
    database.session.add(
        StockLedgerEntry(
            posting_date=original.posting_date,
            item_code=item.code,
            warehouse=warehouse.code,
            company="cacao",
            qty_change=Decimal("-1"),
            qty_after_transaction=Decimal("0"),
            valuation_rate=Decimal("60"),
            stock_value_difference=Decimal("-60"),
            stock_value=Decimal("0"),
            voucher_type="delivery_note",
            voucher_id=original.id,
        )
    )
    returned = DeliveryNote(
        company="cacao",
        posting_date=date(2026, 5, 2),
        transaction_currency="NIO",
        base_currency="NIO",
        is_return=True,
        reversal_of=original.id,
        docstatus=1,
    )
    database.session.add(returned)
    database.session.flush()
    line = DeliveryNoteItem(
        delivery_note_id=returned.id,
        item_code=item.code,
        qty=Decimal("1"),
        uom=item.default_uom,
        rate=Decimal("100"),
        amount=Decimal("100"),
        warehouse=warehouse.code,
    )
    database.session.add(line)
    database.session.flush()

    movement = _create_stock_ledger_for_document(returned, Decimal("1"), Decimal("100"), warehouse.code, line)

    assert movement.valuation_rate == Decimal("60")
    assert movement.stock_value_difference == Decimal("60.0000")
    assert line._inventory_cost_amount == Decimal("60.0000")
    gl_entries = _create_delivery_note_gl_entries(returned, "cacao", None)
    assert any(entry.account_id == inventory_account.id and entry.debit == Decimal("60.0000") for entry in gl_entries)
    assert any(entry.account_id == cogs_account.id and entry.credit == Decimal("60.0000") for entry in gl_entries)


def test_delivery_return_fifo_multilayer_cost(app_ctx):
    """Partial return values at source layer rates, not averaged cost.

    Scenario (Refs: #833):
      Receipt layers: 5 @ 8 and 5 @ 12.
      Delivery of 10: FIFO consumes 5@8 + 5@12, aggregated cost 100, avg 10.
      Partial return of 5: should value at 40 (first 5 @ 8), not 50 (avg 10).
    """
    import json

    from cacao_accounting.contabilidad.posting_service import (
        _create_delivery_note_gl_entries,
        _create_stock_ledger_for_document,
    )

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()

    layer1 = StockValuationLayer(
        item_code=item.code,
        warehouse=warehouse.code,
        company="cacao",
        qty=Decimal("5"),
        rate=Decimal("8"),
        remaining_qty=Decimal("0"),
        remaining_stock_value=Decimal("0"),
        stock_value_difference=Decimal("40"),
        voucher_type="purchase_receipt",
        voucher_id="SEED-L1",
        posting_date=date(2026, 1, 1),
    )
    layer2 = StockValuationLayer(
        item_code=item.code,
        warehouse=warehouse.code,
        company="cacao",
        qty=Decimal("5"),
        rate=Decimal("12"),
        remaining_qty=Decimal("0"),
        remaining_stock_value=Decimal("0"),
        stock_value_difference=Decimal("60"),
        voucher_type="purchase_receipt",
        voucher_id="SEED-L2",
        posting_date=date(2026, 1, 2),
    )
    database.session.add_all([layer1, layer2])
    database.session.flush()

    original = DeliveryNote(company="cacao", posting_date=date(2026, 5, 1), docstatus=1)
    database.session.add(original)
    database.session.flush()

    database.session.add(
        StockLedgerEntry(
            posting_date=original.posting_date,
            item_code=item.code,
            warehouse=warehouse.code,
            company="cacao",
            qty_change=Decimal("-10"),
            qty_after_transaction=Decimal("0"),
            valuation_rate=Decimal("10"),
            stock_value_difference=Decimal("-100"),
            stock_value=Decimal("0"),
            voucher_type="delivery_note",
            voucher_id=original.id,
        )
    )
    database.session.add(
        StockValuationLayer(
            item_code=item.code,
            warehouse=warehouse.code,
            company="cacao",
            qty=Decimal("-10"),
            rate=Decimal("10"),
            stock_value_difference=Decimal("-100"),
            remaining_qty=Decimal("0"),
            remaining_stock_value=Decimal("0"),
            voucher_type="delivery_note",
            voucher_id=original.id,
            posting_date=date(2026, 5, 1),
            source_layer_id=layer1.id,
            consumed_layers=json.dumps(
                [
                    {"layer_id": layer1.id, "qty": "5", "rate": "8"},
                    {"layer_id": layer2.id, "qty": "5", "rate": "12"},
                ]
            ),
        )
    )
    database.session.flush()

    returned = DeliveryNote(
        company="cacao",
        posting_date=date(2026, 5, 2),
        transaction_currency="NIO",
        base_currency="NIO",
        is_return=True,
        reversal_of=original.id,
        docstatus=1,
    )
    database.session.add(returned)
    database.session.flush()
    line = DeliveryNoteItem(
        delivery_note_id=returned.id,
        item_code=item.code,
        qty=Decimal("5"),
        uom=item.default_uom,
        rate=Decimal("100"),
        amount=Decimal("500"),
        warehouse=warehouse.code,
    )
    database.session.add(line)
    database.session.flush()

    movement = _create_stock_ledger_for_document(returned, Decimal("5"), Decimal("40"), warehouse.code, line)

    assert movement.valuation_rate == Decimal("8.0000"), f"Expected rate 8, got {movement.valuation_rate}"
    assert movement.stock_value_difference == Decimal("40.0000"), f"Expected value 40, got {movement.stock_value_difference}"
    assert line._inventory_cost_amount == Decimal("40.0000"), f"Expected cost 40, got {line._inventory_cost_amount}"

    gl_entries = _create_delivery_note_gl_entries(returned, "cacao", None)
    assert any(
        entry.account_id == inventory_account.id and entry.debit == Decimal("40.0000") for entry in gl_entries
    ), f"Inventory debit 40 not found in GL: {[(e.account_id, e.debit, e.credit) for e in gl_entries]}"
    assert any(
        entry.account_id == cogs_account.id and entry.credit == Decimal("40.0000") for entry in gl_entries
    ), f"COGS credit 40 not found in GL: {[(e.account_id, e.debit, e.credit) for e in gl_entries]}"


def test_delivery_return_fifo_multilayer_cost_end_to_end_posting(app_ctx):
    """Full-flow test: outgoing delivery note posting automatically persists consumed_layers

    Scenario:
      1. Post 2 incoming receipts/stock entries (5 @ 8 and 5 @ 12).
      2. Submit outgoing DeliveryNote for 10 units via submit_document.
      3. Verify outgoing StockValuationLayer has consumed_layers saved automatically in DB.
      4. Submit partial DeliveryNote return for 5 units.
      5. Verify return cost is 40 (5 @ 8) and GL entries reflect 40.
    """
    import json
    from cacao_accounting.contabilidad.posting_service import submit_document

    warehouse, item, cogs_account, inventory_account = _setup_inventory_context()

    database.session.add_all(
        [
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal("0.0273224044"), date=date(2026, 5, 2)),
            ExchangeRate(origin="NIO", destination="EUR", rate=Decimal("0.0245"), date=date(2026, 5, 2)),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.5"), date=date(2026, 5, 2)),
            ExchangeRate(origin="NIO", destination="USD", rate=Decimal("0.0273224044"), date=date(2026, 5, 3)),
            ExchangeRate(origin="NIO", destination="EUR", rate=Decimal("0.0245"), date=date(2026, 5, 3)),
            ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.5"), date=date(2026, 5, 3)),
        ]
    )
    database.session.flush()

    # Step 1: Add two incoming stock entries
    entry1 = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 1),
        purpose="material_receipt",
        to_warehouse=warehouse.code,
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=0,
    )
    database.session.add(entry1)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry1.id,
            item_code=item.code,
            target_warehouse=warehouse.code,
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom=item.default_uom,
            basic_rate=Decimal("8"),
            valuation_rate=Decimal("8"),
            amount=Decimal("40"),
        )
    )
    submit_document(entry1)

    entry2 = StockEntry(
        company="cacao",
        posting_date=date(2026, 5, 1),
        purpose="material_receipt",
        to_warehouse=warehouse.code,
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=0,
    )
    database.session.add(entry2)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry2.id,
            item_code=item.code,
            target_warehouse=warehouse.code,
            qty=Decimal("5"),
            qty_in_base_uom=Decimal("5"),
            uom=item.default_uom,
            basic_rate=Decimal("12"),
            valuation_rate=Decimal("12"),
            amount=Decimal("60"),
        )
    )
    submit_document(entry2)

    # Step 2: Submit an outgoing DeliveryNote for 10 units
    outgoing_dn = DeliveryNote(
        company="cacao",
        posting_date=date(2026, 5, 2),
        transaction_currency="NIO",
        base_currency="NIO",
        docstatus=0,
    )
    database.session.add(outgoing_dn)
    database.session.flush()
    database.session.add(
        DeliveryNoteItem(
            delivery_note_id=outgoing_dn.id,
            item_code=item.code,
            qty=Decimal("10"),
            uom=item.default_uom,
            rate=Decimal("100"),
            amount=Decimal("1000"),
            warehouse=warehouse.code,
        )
    )
    submit_document(outgoing_dn)

    # Step 3: Verify StockValuationLayer for outgoing_dn has consumed_layers persisted
    outgoing_svl = (
        database.session.execute(
            database.select(StockValuationLayer).filter_by(
                company="cacao",
                voucher_type="delivery_note",
                voucher_id=outgoing_dn.id,
                item_code=item.code,
                warehouse=warehouse.code,
            )
        )
        .scalars()
        .first()
    )
    assert outgoing_svl is not None, "Outgoing StockValuationLayer not found"
    assert outgoing_svl.consumed_layers is not None, "consumed_layers was not persisted on outgoing StockValuationLayer"

    parsed_consumed = json.loads(outgoing_svl.consumed_layers)
    assert len(parsed_consumed) == 2, f"Expected 2 consumed layers, got {parsed_consumed}"
    assert Decimal(parsed_consumed[0]["qty"]) == Decimal("5")
    assert Decimal(parsed_consumed[0]["rate"]) == Decimal("8")
    assert Decimal(parsed_consumed[1]["qty"]) == Decimal("5")
    assert Decimal(parsed_consumed[1]["rate"]) == Decimal("12")

    # Step 4: Submit a partial DeliveryNote return for 5 units
    return_dn = DeliveryNote(
        company="cacao",
        posting_date=date(2026, 5, 3),
        transaction_currency="NIO",
        base_currency="NIO",
        is_return=True,
        reversal_of=outgoing_dn.id,
        docstatus=0,
    )
    database.session.add(return_dn)
    database.session.flush()
    database.session.add(
        DeliveryNoteItem(
            delivery_note_id=return_dn.id,
            item_code=item.code,
            qty=Decimal("5"),
            uom=item.default_uom,
            rate=Decimal("100"),
            amount=Decimal("500"),
            warehouse=warehouse.code,
        )
    )
    gl_entries = submit_document(return_dn)

    # Step 5: Verify return layer cost is 40 and GL entries reflect 40
    return_svl = (
        database.session.execute(
            database.select(StockValuationLayer).filter_by(
                company="cacao",
                voucher_type="delivery_note",
                voucher_id=return_dn.id,
                item_code=item.code,
                warehouse=warehouse.code,
            )
        )
        .scalars()
        .first()
    )
    assert return_svl is not None, "Return StockValuationLayer not found"
    assert return_svl.stock_value_difference == Decimal("40.0000"), (
        f"Expected return stock value diff 40, got {return_svl.stock_value_difference}"
    )
    assert return_svl.rate == Decimal("8.0000"), f"Expected return rate 8, got {return_svl.rate}"

    assert any(
        entry.account_id == inventory_account.id and entry.debit == Decimal("40.0000") for entry in gl_entries
    ), f"Inventory debit 40 not found in GL: {[(e.account_id, e.debit, e.credit) for e in gl_entries]}"
    assert any(
        entry.account_id == cogs_account.id and entry.credit == Decimal("40.0000") for entry in gl_entries
    ), f"COGS credit 40 not found in GL: {[(e.account_id, e.debit, e.credit) for e in gl_entries]}"


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
        transaction_currency="NIO",
        base_currency="NIO",
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


def test_sales_debit_note_never_creates_delivery_note_from_update_inventory_flag(app_ctx):
    """A financial debit note must not create stock evidence even if the flag is tampered on."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    warehouse, item, _cogs_account, _inventory_account = _setup_inventory_context()
    _ensure_default_warehouse(item, warehouse)
    _seed_valuation_layer(item, warehouse)
    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()

    invoice = SalesInvoice(
        id="SI-DEBIT-NO-STOCK",
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date(2026, 5, 1),
        document_type="sales_debit_note",
        transaction_currency="NIO",
        base_currency="NIO",
        update_inventory=True,
        docstatus=0,
        grand_total=Decimal("500"),
    )
    invoice_item = SalesInvoiceItem(
        sales_invoice_id=invoice.id,
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

    response = client.post(f"/sales/sales-invoice/{invoice.id}/submit", follow_redirects=True)
    assert response.status_code == 200

    database.session.refresh(invoice)
    assert invoice.docstatus == 1
    assert invoice.delivery_note_id is None
    assert (
        database.session.execute(
            database.select(StockLedgerEntry).filter_by(voucher_type="delivery_note", voucher_id=invoice.id)
        )
        .scalars()
        .all()
        == []
    )


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
        transaction_currency="NIO",
        base_currency="NIO",
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

    response = client.post(
        "/sales/sales-invoice/SI-INV-03/cancel", data={"reason": "cancelacion por prueba"}, follow_redirects=True
    )
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
