# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de reserva de inventario en Ordenes de Venta (O2C-03)."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    Item,
    ItemAccount,
    SalesOrder,
    SalesOrderItem,
    SalesInvoice,
    SalesInvoiceItem,
    StockBin,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    Warehouse,
    WarehouseCompanyAccount,
    Accounts,
    CompanyDefaultAccount,
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
        _seed_data()
        yield app


def _seed_data():
    item = database.session.get(Item, "ART-RESERVE")
    if not item:
        item = Item(
            code="ART-RESERVE",
            name="Articulo Reserva",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
        )
        database.session.add(item)

    warehouse = database.session.get(Warehouse, "WH-RESERVE")
    if not warehouse:
        warehouse = Warehouse(code="WH-RESERVE", name="Bodega Reserva", company="cacao")
        database.session.add(warehouse)

    database.session.flush()

    inv_ac = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="INV-RES")).scalar_one_or_none()
    if not inv_ac:
        inv_ac = Accounts(
            entity="cacao",
            code="INV-RES",
            name="Inventario Reserva",
            active=True,
            enabled=True,
            classification="asset",
            account_type="inventory",
        )
        database.session.add(inv_ac)

    exp_ac = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="EXP-RES")).scalar_one_or_none()
    if not exp_ac:
        exp_ac = Accounts(
            entity="cacao",
            code="EXP-RES",
            name="Gasto Reserva",
            active=True,
            enabled=True,
            classification="expense",
            account_type="expense",
        )
        database.session.add(exp_ac)

    database.session.flush()

    if not database.session.execute(
        database.select(ItemAccount).filter_by(item_code="ART-RESERVE", company="cacao")
    ).scalar_one_or_none():
        database.session.add(ItemAccount(item_code="ART-RESERVE", company="cacao"))

    company_def = database.session.execute(
        database.select(CompanyDefaultAccount).filter_by(company="cacao")
    ).scalar_one_or_none()
    if not company_def:
        company_def = CompanyDefaultAccount(company="cacao", default_expense=exp_ac.id)
        database.session.add(company_def)

    if not database.session.execute(
        database.select(WarehouseCompanyAccount).filter_by(warehouse_code="WH-RESERVE", company="cacao")
    ).scalar_one_or_none():
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code="WH-RESERVE", company="cacao", inventory_account_id=inv_ac.id, is_active=True
            )
        )

    database.session.flush()

    if not database.session.execute(
        database.select(StockBin).filter_by(item_code="ART-RESERVE", warehouse="WH-RESERVE")
    ).scalar_one_or_none():
        database.session.add(
            StockBin(
                company="cacao",
                item_code="ART-RESERVE",
                warehouse="WH-RESERVE",
                actual_qty=Decimal("20"),
                reserved_qty=Decimal("0"),
                valuation_rate=Decimal("10.00"),
                stock_value=Decimal("200.00"),
            )
        )
        database.session.flush()

    if not database.session.execute(
        database.select(StockLedgerEntry).filter_by(voucher_id="seed-reserve")
    ).scalar_one_or_none():
        database.session.add(
            StockLedgerEntry(
                posting_date=date(2026, 6, 1),
                item_code="ART-RESERVE",
                warehouse="WH-RESERVE",
                company="cacao",
                qty_change=Decimal("20"),
                qty_after_transaction=Decimal("20"),
                valuation_rate=Decimal("10.00"),
                stock_value_difference=Decimal("200.00"),
                stock_value=Decimal("200.00"),
                voucher_type="seed",
                voucher_id="seed-reserve",
            )
        )
        database.session.flush()

    if not database.session.execute(
        database.select(StockValuationLayer).filter_by(voucher_id="seed-reserve")
    ).scalar_one_or_none():
        database.session.add(
            StockValuationLayer(
                item_code="ART-RESERVE",
                warehouse="WH-RESERVE",
                company="cacao",
                qty=Decimal("20"),
                rate=Decimal("10.00"),
                stock_value_difference=Decimal("200.00"),
                remaining_qty=Decimal("20"),
                remaining_stock_value=Decimal("200.00"),
                voucher_type="seed",
                voucher_id="seed-reserve",
                posting_date=date(2026, 6, 1),
            )
        )
    database.session.commit()


def _make_so(
    so_id: str,
    qty: Decimal,
    warehouse: str = "WH-RESERVE",
    company: str = "cacao",
    docstatus: int = 0,
) -> SalesOrder:
    so = SalesOrder(id=so_id, company=company, posting_date=date(2026, 6, 15), docstatus=docstatus, customer_id="CUST-RESERVE")
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(
        sales_order_id=so.id,
        item_code="ART-RESERVE",
        item_name="Articulo Reserva",
        qty=qty,
        uom="UND",
        rate=Decimal("15.00"),
        amount=qty * Decimal("15.00"),
        warehouse=warehouse,
    )
    database.session.add(so_item)
    database.session.commit()
    return so


def _make_dn(
    dn_id: str,
    qty: Decimal,
    warehouse: str = "WH-RESERVE",
    sales_order_id: str | None = None,
    company: str = "cacao",
    docstatus: int = 0,
) -> DeliveryNote:
    dn = DeliveryNote(
        id=dn_id,
        company=company,
        posting_date=date(2026, 6, 16),
        customer_id="CUST-RESERVE",
        docstatus=docstatus,
        sales_order_id=sales_order_id,
    )
    database.session.add(dn)
    database.session.flush()
    dn_item = DeliveryNoteItem(
        delivery_note_id=dn.id,
        item_code="ART-RESERVE",
        item_name="Articulo Reserva",
        qty=qty,
        uom="UND",
        rate=Decimal("15.00"),
        amount=qty * Decimal("15.00"),
        warehouse=warehouse,
    )
    database.session.add(dn_item)
    database.session.commit()
    return dn


def _get_bin() -> StockBin:
    return database.session.execute(
        database.select(StockBin).filter_by(item_code="ART-RESERVE", warehouse="WH-RESERVE")
    ).scalar_one()


class TestReservaOrdenVenta:
    """Pruebas de reserva al aprobar/cancelar Orden de Venta."""

    def test_so_submit_reserva_stock(self, app_ctx):
        so = _make_so("SO-RES-01", Decimal("5"))
        client = app_ctx.test_client()
        login(client)

        response = client.post("/sales/sales-order/SO-RES-01/submit", follow_redirects=True)
        assert response.status_code == 200

        database.session.refresh(so)
        assert so.docstatus == 1

        bin_row = _get_bin()
        assert bin_row.actual_qty == Decimal("20")
        assert bin_row.reserved_qty == Decimal("5")

    def test_so_submit_rechaza_stock_insuficiente(self, app_ctx):
        so = _make_so("SO-RES-02", Decimal("25"))
        client = app_ctx.test_client()
        login(client)

        response = client.post("/sales/sales-order/SO-RES-02/submit", follow_redirects=True)
        assert response.status_code == 200

        database.session.refresh(so)
        assert so.docstatus == 0

        bin_row = _get_bin()
        assert bin_row.reserved_qty == Decimal("0")

    def test_so_submit_rechaza_cuando_ya_hay_reserva(self, app_ctx):
        _make_so("SO-RES-03A", Decimal("15"))
        client = app_ctx.test_client()
        login(client)

        response = client.post("/sales/sales-order/SO-RES-03A/submit", follow_redirects=True)
        assert response.status_code == 200

        bin_row = _get_bin()
        assert bin_row.reserved_qty == Decimal("15")

        so2 = _make_so("SO-RES-03B", Decimal("10"))
        response2 = client.post("/sales/sales-order/SO-RES-03B/submit", follow_redirects=True)
        assert response2.status_code == 200

        database.session.refresh(so2)
        assert so2.docstatus == 0

        bin_row2 = _get_bin()
        assert bin_row2.reserved_qty == Decimal("15")

    def test_so_cancel_libera_reserva(self, app_ctx):
        so = _make_so("SO-RES-04", Decimal("8"), docstatus=1)
        database.session.refresh(so)
        bin_row = _get_bin()
        bin_row.reserved_qty = Decimal("8")
        database.session.commit()

        client = app_ctx.test_client()
        login(client)

        response = client.post("/sales/sales-order/SO-RES-04/cancel", follow_redirects=True)
        assert response.status_code == 200

        database.session.refresh(so)
        assert so.docstatus == 2

        bin_row2 = _get_bin()
        assert bin_row2.reserved_qty == Decimal("0")


class TestReservaNotaEntrega:
    """Pruebas de liberacion/restauracion de reserva al aprobar/cancelar Nota de Entrega."""

    def test_dn_submit_libera_reserva(self, app_ctx):
        so = _make_so("SO-RES-DN-01", Decimal("10"), docstatus=1)
        bin_row = _get_bin()
        bin_row.reserved_qty = Decimal("10")
        database.session.commit()

        dn = _make_dn("DN-RES-01", Decimal("6"), sales_order_id=so.id)

        client = app_ctx.test_client()
        login(client)

        response = client.post("/sales/delivery-note/DN-RES-01/submit", follow_redirects=True)
        assert response.status_code == 200

        bin_row2 = _get_bin()
        assert bin_row2.actual_qty == Decimal("14")
        assert bin_row2.reserved_qty == Decimal("4")

    def test_dn_submit_sin_so_no_libera_reserva(self, app_ctx):
        so = _make_so("SO-RES-DN-02", Decimal("5"), docstatus=1)
        bin_row = _get_bin()
        bin_row.reserved_qty = Decimal("5")
        database.session.commit()

        dn = _make_dn("DN-RES-02", Decimal("3"), sales_order_id=None)
        client = app_ctx.test_client()
        login(client)

        response = client.post("/sales/delivery-note/DN-RES-02/submit", follow_redirects=True)
        assert response.status_code == 200

        bin_row2 = _get_bin()
        assert bin_row2.reserved_qty == Decimal("5")

    def test_dn_cancel_restaura_reserva(self, app_ctx):
        so = _make_so("SO-RES-DN-03", Decimal("10"), docstatus=1)
        bin_row = _get_bin()
        bin_row.reserved_qty = Decimal("10")
        database.session.commit()

        dn = _make_dn("DN-RES-03", Decimal("4"), sales_order_id=so.id, docstatus=0)
        client = app_ctx.test_client()
        login(client)

        submit_resp = client.post("/sales/delivery-note/DN-RES-03/submit", follow_redirects=True)
        assert submit_resp.status_code == 200
        database.session.refresh(dn)
        assert dn.docstatus == 1

        bin_row2 = _get_bin()
        assert bin_row2.actual_qty == Decimal("16")
        assert bin_row2.reserved_qty == Decimal("6")

        cancel_resp = client.post("/sales/delivery-note/DN-RES-03/cancel", follow_redirects=True)
        assert cancel_resp.status_code == 200

        database.session.refresh(dn)
        assert dn.docstatus == 2

        bin_row3 = _get_bin()
        assert bin_row3.actual_qty == Decimal("20")
        assert bin_row3.reserved_qty == Decimal("10")


def test_rebuild_stock_bins_preserva_reserved_qty(app_ctx):
    from cacao_accounting.inventario.service import rebuild_stock_bins

    bin_row = _get_bin()
    bin_row.reserved_qty = Decimal("7")
    database.session.commit()

    result = rebuild_stock_bins(company="cacao", item_code="ART-RESERVE", warehouse="WH-RESERVE")
    assert result.rebuilt_bins >= 1

    database.session.refresh(bin_row)
    assert bin_row.actual_qty == Decimal("20")
    assert bin_row.reserved_qty == Decimal("7")


def login(client, username="cacao", password="cacao"):
    client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def test_release_reservation_is_idempotent(app_ctx):
    from cacao_accounting.ventas import _release_reservation_for_delivery_note
    from cacao_accounting.document_identifiers import assign_document_identifier

    bin_row = (
        database.session.execute(
            database.select(StockBin).filter_by(item_code="ART-RESERVE", warehouse="WH-RESERVE")
        )
        .scalar_one_or_none()
    )
    assert bin_row is not None
    bin_row.reserved_qty = Decimal("10")
    database.session.flush()

    dn = DeliveryNote(
        customer_id="CUST-RES",
        company="cacao",
        posting_date=date.today(),
        sales_order_id="SO-RES",
        docstatus=1,
    )
    database.session.add(dn)
    database.session.flush()
    assign_document_identifier(
        document=dn, entity_type="delivery_note", posting_date_raw=date.today(), naming_series_id=None
    )
    database.session.add(
        DeliveryNoteItem(delivery_note_id=dn.id, item_code="ART-RESERVE", qty=Decimal("3"), warehouse="WH-RESERVE")
    )
    database.session.commit()

    _release_reservation_for_delivery_note(dn)
    database.session.commit()
    database.session.refresh(bin_row)
    assert bin_row.reserved_qty == Decimal("7")
    _release_reservation_for_delivery_note(dn)
    database.session.commit()
    database.session.refresh(bin_row)
    assert bin_row.reserved_qty == Decimal("7")
