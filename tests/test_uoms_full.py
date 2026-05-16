# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations
import json
import re
from decimal import Decimal
from datetime import date
import pytest
from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Entity,
    Book,
    ExchangeRate,
    Item,
    UOM,
    ItemUOMConversion,
    PurchaseReceipt,
    PurchaseReceiptItem,
    SalesInvoice,
    SalesInvoiceItem,
    DeliveryNote,
    DeliveryNoteItem,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    Party,
    StockBin,
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

        # Add UOMs
        uoms = [
            UOM(code="PKG", name="Paquete"),
            UOM(code="BOX", name="Caja"),
            UOM(code="DZ", name="Docena"),
        ]
        for u in uoms:
            if not database.session.execute(database.select(UOM).filter_by(code=u.code)).scalars().first():
                database.session.add(u)

        # Add Conversions for ART-001 (Chocolate 100g, default UOM is UND)
        # 1 PKG = 10 UND
        # 1 BOX = 50 UND
        # 1 DZ = 12 UND
        conversions = [
            ItemUOMConversion(item_code="ART-001", from_uom="PKG", to_uom="UND", conversion_factor=Decimal("10")),
            ItemUOMConversion(item_code="ART-001", from_uom="BOX", to_uom="UND", conversion_factor=Decimal("50")),
            ItemUOMConversion(item_code="ART-001", from_uom="DZ", to_uom="UND", conversion_factor=Decimal("12")),
        ]
        for c in conversions:
            database.session.add(c)

        database.session.commit()
        yield app


def login(client, username, password):
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def get_error(data):
    if isinstance(data, bytes):
        data = data.decode()
    match = re.search(r'class="alert alert-danger.*?>(.*?)</div>', data, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def assert_no_danger(response, msg=""):
    error = get_error(response.data)
    assert error is None, f"{msg}: {error}"


def test_uom_conversion_cycle(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Buy 2 BOX (Should be 100 UND in inventory)
    supplier = database.session.execute(database.select(Party).filter_by(party_type="supplier")).scalars().first()
    prc_data = {
        "company": "cacao",
        "supplier_id": supplier.id,
        "posting_date": date.today().isoformat(),
        "remarks": "UOM CYCLE TEST",
        "item_code_0": "ART-001",
        "item_name_0": "Chocolate 100g",
        "qty_0": "2",
        "uom_0": "BOX",
        "rate_0": "500",  # 500 per BOX
        "amount_0": "1000",
        "warehouse_0": "PRINCIPAL",
    }
    response = client.post("/buying/purchase-receipt/new", data=prc_data, follow_redirects=True)
    assert response.status_code == 200
    prc = (
        database.session.execute(
            database.select(PurchaseReceipt).filter_by(remarks="UOM CYCLE TEST").order_by(PurchaseReceipt.created.desc())
        )
        .scalars()
        .first()
    )
    assert prc is not None
    response = client.post(f"/buying/purchase-receipt/{prc.id}/submit", follow_redirects=True)
    assert_no_danger(response, "Purchase Receipt Submit")

    from tests.test_e2e_modules import check_ledger_entries

    check_ledger_entries(prc.id)

    # Check Stock Ledger: should show 100 UND
    sle = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=prc.id)).scalars().first()
    assert sle is not None, "Stock Ledger Entry not found"
    assert sle.qty_change == 100
    assert sle.valuation_rate == 10  # 1000 / 100

    # 2. Transfer 1 PKG from PRINCIPAL to SUCURSAL (Should move 10 UND)
    mt_data = {
        "company": "cacao",
        "purpose": "material_transfer",
        "posting_date": date.today().isoformat(),
        "remarks": "UOM TRANSFER TEST",
        "from_warehouse": "PRINCIPAL",
        "to_warehouse": "SUCURSAL",
        "item_code_0": "ART-001",
        "qty_0": "1",
        "uom_0": "PKG",
        "rate_0": "100",
        "amount_0": "100",
    }
    response = client.post("/inventory/stock-entry/new", data=mt_data, follow_redirects=True)
    assert_no_danger(response, "Stock Entry Create")
    mt = (
        database.session.execute(
            database.select(StockEntry).filter_by(remarks="UOM TRANSFER TEST").order_by(StockEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert mt is not None
    response = client.post(f"/inventory/stock-entry/{mt.id}/submit", follow_redirects=True)
    assert_no_danger(response, "Stock Entry Submit")

    # Material Transfer doesn't generate GL entries by default if same company
    # check_ledger_entries(mt.id, expected_books_count=0)

    # Check Stock Ledger for transfer
    sles = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=mt.id)).scalars().all()
    assert len(sles) == 2
    # Verify quantities in base UOM
    qtys = [s.qty_change for s in sles]
    assert Decimal("-10") in qtys
    assert Decimal("10") in qtys

    # 3. Sell 3 DZ from PRINCIPAL (Remaining in PRINCIPAL: 100 - 10 - 36 = 54 UND)
    customer = database.session.execute(database.select(Party).filter_by(party_type="customer")).scalars().first()

    dn_data = {
        "company": "cacao",
        "customer_id": customer.id,
        "posting_date": date.today().isoformat(),
        "remarks": "UOM SALE TEST",
        "item_code_0": "ART-001",
        "qty_0": "3",
        "uom_0": "DZ",
        "rate_0": "150",
        "amount_0": "450",
        "warehouse_0": "PRINCIPAL",
    }
    response = client.post("/sales/delivery-note/new", data=dn_data, follow_redirects=True)
    assert response.status_code == 200
    dn = (
        database.session.execute(
            database.select(DeliveryNote).filter_by(remarks="UOM SALE TEST").order_by(DeliveryNote.created.desc())
        )
        .scalars()
        .first()
    )
    assert dn is not None
    response = client.post(f"/sales/delivery-note/{dn.id}/submit", follow_redirects=True)
    assert_no_danger(response, "Delivery Note Submit")

    check_ledger_entries(dn.id)

    # Check Stock Ledger: should show -36 UND
    sle_dn = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=dn.id)).scalars().first()
    assert sle_dn is not None
    assert sle_dn.qty_change == -36

    # Check final quantity in PRINCIPAL
    bin_p = (
        database.session.execute(database.select(StockBin).filter_by(item_code="ART-001", warehouse="PRINCIPAL"))
        .scalars()
        .first()
    )
    assert bin_p.actual_qty == 54  # 100 - 10 - 36


def test_average_cost(app_ctx):
    from tests.test_e2e_modules import check_ledger_entries

    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Create a new item with Moving Average valuation
    item_avg = Item(
        code="AVG-ITEM",
        name="Average Cost Item",
        item_type="goods",
        is_stock_item=True,
        default_uom="UND",
        valuation_method="moving_average",
    )
    database.session.add(item_avg)
    database.session.commit()

    # 2. Purchase 10 UND at 100 each
    mr1_data = {
        "company": "cacao",
        "purpose": "material_receipt",
        "posting_date": date.today().isoformat(),
        "remarks": "AVG COST TEST 1",
        "to_warehouse": "PRINCIPAL",
        "item_code_0": "AVG-ITEM",
        "item_name_0": "Average Cost Item",
        "qty_0": "10",
        "uom_0": "UND",
        "rate_0": "100",
        "amount_0": "1000",
    }
    response = client.post("/inventory/stock-entry/new", data=mr1_data, follow_redirects=True)
    assert response.status_code == 200
    mr1 = (
        database.session.execute(
            database.select(StockEntry).filter_by(remarks="AVG COST TEST 1").order_by(StockEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert mr1 is not None
    response = client.post(f"/inventory/stock-entry/{mr1.id}/submit", follow_redirects=True)
    assert_no_danger(response, "MR1 Submit")

    check_ledger_entries(mr1.id)

    # Check cost: should be 100
    bin_row = (
        database.session.execute(database.select(StockBin).filter_by(item_code="AVG-ITEM", warehouse="PRINCIPAL"))
        .scalars()
        .first()
    )
    assert bin_row.valuation_rate == 100
    assert bin_row.actual_qty == 10

    # 3. Purchase another 10 UND at 200 each
    mr2_data = {
        "company": "cacao",
        "purpose": "material_receipt",
        "posting_date": date.today().isoformat(),
        "remarks": "AVG COST TEST 2",
        "to_warehouse": "PRINCIPAL",
        "item_code_0": "AVG-ITEM",
        "item_name_0": "Average Cost Item",
        "qty_0": "10",
        "uom_0": "UND",
        "rate_0": "200",
        "amount_0": "2000",
    }
    response = client.post("/inventory/stock-entry/new", data=mr2_data, follow_redirects=True)
    assert_no_danger(response, "MR2 Create")
    mr2 = (
        database.session.execute(
            database.select(StockEntry).filter_by(remarks="AVG COST TEST 2").order_by(StockEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert mr2 is not None
    response = client.post(f"/inventory/stock-entry/{mr2.id}/submit", follow_redirects=True)
    assert_no_danger(response, "MR2 Submit")

    check_ledger_entries(mr2.id)

    # Check average cost: (10*100 + 10*200) / 20 = 3000 / 20 = 150
    database.session.refresh(bin_row)
    assert bin_row.valuation_rate == 150
    assert bin_row.actual_qty == 20

    # 4. Sell 5 UND (Should use 150 as cost)
    dn_data = {
        "company": "cacao",
        "customer_id": database.session.execute(database.select(Party).filter_by(party_type="customer")).scalars().first().id,
        "posting_date": date.today().isoformat(),
        "remarks": "AVG COST SALE",
        "item_code_0": "AVG-ITEM",
        "qty_0": "5",
        "uom_0": "UND",
        "rate_0": "300",
        "amount_0": "1500",
        "warehouse_0": "PRINCIPAL",
    }
    response = client.post("/sales/delivery-note/new", data=dn_data, follow_redirects=True)
    assert response.status_code == 200
    dn = (
        database.session.execute(
            database.select(DeliveryNote).filter_by(remarks="AVG COST SALE").order_by(DeliveryNote.created.desc())
        )
        .scalars()
        .first()
    )
    assert dn is not None
    response = client.post(f"/sales/delivery-note/{dn.id}/submit", follow_redirects=True)
    assert_no_danger(response, "DN Submit")

    check_ledger_entries(dn.id)

    # Check Stock Ledger Entry for Delivery Note
    sle = database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=dn.id)).scalars().first()
    assert sle is not None
    assert sle.valuation_rate == 150
    assert sle.stock_value_difference == -750  # 5 * 150
