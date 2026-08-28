# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para correcciones de issues ventas (O2C) y flujo documental."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Book,
    CompanyParty,
    DocumentRelation,
    ExchangeRate,
    Item,
    ItemPrice,
    Party,
    PriceList,
    SalesInvoice,
    SalesInvoiceItem,
    SalesMatchingConfig,
    SalesOrder,
    SalesOrderItem,
    database,
    Warehouse,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.document_flow import DocumentFlowError


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

        books = database.session.execute(database.select(Book).filter_by(entity="cacao")).scalars().all()
        book_codes = [b.code for b in books]
        if "USD_BOOK" not in book_codes:
            database.session.add(Book(code="USD_BOOK", name="Dólares", entity="cacao", currency="USD", status="activo"))
        today = date.today()
        for r in (ExchangeRate(origin="USD", destination="NIO", rate=Decimal("36.5"), date=today),):
            exists = (
                database.session.execute(
                    database.select(ExchangeRate).filter_by(origin=r.origin, destination=r.destination, date=r.date)
                )
                .scalars()
                .first()
            )
            if not exists:
                database.session.add(r)
        database.session.commit()
        yield app


def _ensure_item(code="ART-O2C"):
    item = database.session.get(Item, code)
    if not item:
        item = Item(code=code, name="Articulo O2C", item_type="goods", is_stock_item=True, default_uom="UND")
        database.session.add(item)
        database.session.flush()
    return item


def _ensure_customer(code, name):
    customer = database.session.execute(database.select(Party).filter_by(code=code)).scalar_one_or_none()
    if not customer:
        customer = Party(code=code, name=name, is_customer=True, is_active=True)
        database.session.add(customer)
        database.session.flush()
    if not database.session.execute(
        database.select(CompanyParty).filter_by(party_id=customer.id, company="cacao")
    ).scalar_one_or_none():
        database.session.add(CompanyParty(party_id=customer.id, company="cacao", is_active=True))
        database.session.commit()
    return customer


def test_sales_order_new_handles_unexpected_error(app_ctx):
    from cacao_accounting.ventas import _handle_sales_order_new_post

    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)
    customer = _ensure_customer("CUST-O2C10", "Cliente O2C10")

    def boom(*args, **kwargs):
        raise ValueError("Error inesperado simulado")

    with patch("cacao_accounting.ventas._save_sales_order_items", boom):
        with app_ctx.test_request_context(
            "/sales/sales-order/new",
            method="POST",
            data={
                "company": "cacao",
                "customer_id": customer.id,
                "posting_date": date.today().isoformat(),
                "item_code_0": "ART-O2C",
                "qty_0": "1",
                "rate_0": "10",
                "amount_0": "10",
            },
        ):
            # No debe propagar la excepcion (500); debe capturarla y retornar None.
            result = _handle_sales_order_new_post(None, None)
    assert result is None


def test_sales_invoice_form_exposes_company_warehouses(app_ctx):
    """La factura de venta muestra la bodega por línea para crear la DN correcta."""
    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    warehouse = database.session.execute(database.select(Warehouse).filter_by(company="cacao")).scalars().first()
    assert warehouse is not None
    response = client.get("/sales/sales-invoice/new?company=cacao")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '"field": "warehouse"' in html
    assert warehouse.code in html


def test_sales_document_totals_convert_transaction_currency(app_ctx):
    """Los documentos comerciales conservan la moneda transaccional y su base funcional."""
    from cacao_accounting.ventas import _sales_base_amount, _set_sales_document_totals

    order = SalesOrder(
        company="cacao",
        posting_date=date.today(),
        transaction_currency="USD",
    )
    _set_sales_document_totals(order, Decimal("100"))
    expected_rate = (
        database.session.execute(database.select(ExchangeRate).filter_by(origin="USD", destination="NIO", date=date.today()))
        .scalar_one()
        .rate
    )

    assert order.base_currency == "NIO"
    assert order.exchange_rate == expected_rate
    assert order.base_total == (Decimal("100") * expected_rate).quantize(Decimal("0.0001"))
    assert _sales_base_amount(order, Decimal("100")) == order.base_total


def test_sales_order_items_reject_duplicate_item_codes(app_ctx):
    """Una misma referencia no puede ocupar dos líneas del mismo documento."""
    from cacao_accounting.ventas import _save_sales_order_items

    order = SalesOrder(company="cacao", posting_date=date.today(), docstatus=0)
    database.session.add(order)
    database.session.flush()
    item = _ensure_item("ART-O2C-DUP")
    price_list = PriceList(name="Default O2C Duplicate", company="cacao", is_selling=True, is_default=True, is_active=True)
    database.session.add(price_list)
    database.session.flush()
    database.session.add(ItemPrice(item_code=item.code, price_list_id=price_list.id, uom="UND", price=Decimal("10")))
    database.session.commit()

    with app_ctx.test_request_context(
        "/sales/sales-order/new",
        method="POST",
        data={
            "item_code_0": "ART-O2C-DUP",
            "qty_0": "1",
            "rate_0": "10",
            "amount_0": "10",
            "item_code_1": "ART-O2C-DUP",
            "qty_1": "2",
            "rate_1": "10",
            "amount_1": "20",
        },
    ):
        with pytest.raises(DocumentFlowError, match="no puede repetirse"):
            _save_sales_order_items(order.id)
    database.session.rollback()


def test_flow_source_line_is_loaded_with_a_submission_lock(app_ctx):
    """La validación O2C obtiene la línea fuente mediante el helper de lock."""
    from cacao_accounting.database import SalesOrder, SalesOrderItem, database
    from cacao_accounting.ventas.services import _lock_flow_source_item

    order = SalesOrder(company="cacao", posting_date=date.today(), docstatus=1)
    database.session.add(order)
    database.session.flush()
    item = SalesOrderItem(sales_order_id=order.id, item_code="ART-O2C-LOCK", qty=Decimal("1"), rate=Decimal("1"))
    database.session.add(item)
    database.session.flush()

    locked = _lock_flow_source_item(SalesOrderItem, item.id)

    assert locked is item


O2C_BILLING_SCENARIOS = [
    (10, 4, "12"),
    (10, 10, "12"),
    (25, 7, "8.50"),
    (25, 25, "8.50"),
    (1, 1, "100"),
    (100, 33, "2.75"),
    (100, 99, "2.75"),
    (12, 5, "36.40"),
    (12, 12, "36.40"),
    (7, 3, "19.99"),
    (7, 6, "19.99"),
    (50, 1, "0.25"),
    (50, 49, "0.25"),
    (3, 2, "1250"),
    (3, 3, "1250"),
]


@pytest.mark.full
@pytest.mark.parametrize("ordered_qty, billed_qty, rate_raw", O2C_BILLING_SCENARIOS)
def test_o2c_sales_order_to_invoice_relation_manual_balances(app_ctx, ordered_qty, billed_qty, rate_raw):
    """Verifica cantidades pendientes y valor facturado en quince ciclos O2C.

    La expectativa es independiente del servicio: pendiente = orden - factura
    y valor facturado = factura x tarifa. Cada caso usa una orden y factura
    aprobadas, crea la relación documental y consulta el estado resultante.
    """
    from cacao_accounting.document_flow import create_document_relation
    from cacao_accounting.document_flow.repository import consumed_qty_for_source
    from cacao_accounting.document_flow.service import get_source_items, pending_qty

    item = _ensure_item(f"ART-O2C-FULL-{ordered_qty}-{billed_qty}")
    customer = _ensure_customer(f"CUST-O2C-FULL-{ordered_qty}-{billed_qty}", "Cliente O2C full")
    rate = Decimal(rate_raw)
    order = SalesOrder(
        company="cacao",
        customer_id=customer.id,
        posting_date=date(2026, 8, 1),
        docstatus=1,
        grand_total=Decimal(ordered_qty) * rate,
    )
    database.session.add(order)
    database.session.flush()
    order_item = SalesOrderItem(
        sales_order_id=order.id,
        item_code=item.code,
        qty=Decimal(ordered_qty),
        uom="UND",
        rate=rate,
        amount=Decimal(ordered_qty) * rate,
    )
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date(2026, 8, 2),
        docstatus=1,
        grand_total=Decimal(billed_qty) * rate,
    )
    database.session.add_all([order_item, invoice])
    database.session.flush()
    invoice_item = SalesInvoiceItem(
        sales_invoice_id=invoice.id,
        item_code=item.code,
        qty=Decimal(billed_qty),
        uom="UND",
        rate=rate,
        amount=Decimal(billed_qty) * rate,
    )
    database.session.add(invoice_item)
    database.session.flush()
    create_document_relation(
        source_type="sales_order",
        source_id=order.id,
        source_item_id=order_item.id,
        target_type="sales_invoice",
        target_id=invoice.id,
        target_item_id=invoice_item.id,
        qty=Decimal(billed_qty),
        uom="UND",
        rate=rate,
        amount=Decimal(billed_qty) * rate,
    )
    database.session.commit()

    source_rows = get_source_items("sales_order", order.id, "sales_invoice")
    expected_pending = Decimal(ordered_qty - billed_qty)
    assert consumed_qty_for_source("sales_order", order.id, order_item.id, "sales_invoice") == Decimal(billed_qty)
    assert pending_qty("sales_order", order.id, order_item.id, "sales_invoice") == expected_pending
    relation = database.session.execute(
        database.select(DocumentRelation).filter_by(source_id=order.id, target_id=invoice.id)
    ).scalar_one()
    assert relation.qty == Decimal(billed_qty)
    if expected_pending:
        assert Decimal(source_rows[0]["source_qty"]) == Decimal(ordered_qty)
        assert Decimal(source_rows[0]["consumed_qty"]) == Decimal(billed_qty)
        assert Decimal(source_rows[0]["pending_qty"]) == expected_pending
        assert Decimal(str(source_rows[0]["amount"])) == expected_pending * rate
    else:
        assert source_rows == []


def test_validate_invoice_prices_warns_without_raising(app_ctx):
    from cacao_accounting.ventas import _validate_invoice_prices_against_source

    _ensure_item("ART-O2C06")
    customer = _ensure_customer("CUST-O2C06", "Cliente O2C06")

    so = SalesOrder(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=1)
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(sales_order_id=so.id, item_code="ART-O2C06", qty=Decimal("1"), rate=Decimal("100"))
    database.session.add(so_item)
    database.session.flush()

    si = SalesInvoice(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=0)
    database.session.add(si)
    database.session.flush()
    si_item = SalesInvoiceItem(sales_invoice_id=si.id, item_code="ART-O2C06", qty=Decimal("1"), rate=Decimal("110"))
    database.session.add(si_item)
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="sales_order",
            source_id=so.id,
            source_item_id=so_item.id,
            target_type="sales_invoice",
            target_id=si.id,
            target_item_id=si_item.id,
            qty=Decimal("1"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.add(
        SalesMatchingConfig(company="cacao", allow_price_difference=False, price_tolerance_value=Decimal("0"))
    )
    database.session.commit()

    warnings = _validate_invoice_prices_against_source(si, raise_on_violation=False)
    assert len(warnings) == 1

    with pytest.raises(ValueError):
        _validate_invoice_prices_against_source(si, raise_on_violation=True)


def test_sales_invoice_requires_sales_order_when_configured(app_ctx):
    """La configuración de matching debe bloquear facturas manuales sin OV."""
    from cacao_accounting.ventas import _validate_sales_order_requirement

    customer = _ensure_customer("CUST-O2C-REQUIRE-OV", "Cliente requiere OV")
    database.session.add(SalesMatchingConfig(company="cacao", require_sales_order=True))
    invoice = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        document_type="sales_invoice",
        is_return=False,
        docstatus=0,
    )
    database.session.add(invoice)
    database.session.commit()

    with pytest.raises(ValueError, match="Orden de Venta"):
        _validate_sales_order_requirement(invoice)


def test_edit_invoice_rejects_reversal_of_on_customer_change(app_ctx):
    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)
    customer_a = _ensure_customer("CUST-O2C18A", "Cliente O2C18A")
    customer_b = _ensure_customer("CUST-O2C18B", "Cliente O2C18B")

    source = SalesInvoice(
        customer_id=customer_a.id, company="cacao", posting_date=date.today(), docstatus=1, document_type="sales_invoice"
    )
    database.session.add(source)
    database.session.flush()
    from cacao_accounting.document_identifiers import assign_document_identifier

    assign_document_identifier(
        document=source, entity_type="sales_invoice", posting_date_raw=date.today(), naming_series_id=None
    )

    invoice = SalesInvoice(
        customer_id=customer_a.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=0,
        document_type="sales_credit_note",
        reversal_of=source.id,
    )
    database.session.add(invoice)
    database.session.flush()
    assign_document_identifier(
        document=invoice, entity_type="sales_credit_note", posting_date_raw=date.today(), naming_series_id=None
    )
    database.session.add(
        SalesInvoiceItem(sales_invoice_id=invoice.id, item_code="ART-O2C18", qty=Decimal("1"), rate=Decimal("10"))
    )
    database.session.commit()

    response = client.post(
        f"/sales/sales-invoice/{invoice.id}/edit",
        data={
            "company": "cacao",
            "customer_id": customer_b.id,
            "posting_date": date.today().isoformat(),
            "item_code_0": "ART-O2C18",
            "qty_0": "1",
            "rate_0": "10",
            "amount_0": "10",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    database.session.refresh(invoice)
    assert invoice.customer_id == customer_a.id


def test_credit_note_cannot_exceed_cumulative_source_balance(app_ctx):
    """Una nota de credito nueva respeta pagos y notas anteriores acumuladas."""
    from cacao_accounting.ventas import _validate_reversal_of

    customer = _ensure_customer("CUST-O2C-CAP", "Cliente limite NC")
    source = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="sales_invoice",
        grand_total=Decimal("100"),
    )
    previous_note = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="sales_credit_note",
        grand_total=Decimal("60"),
        reversal_of=None,
    )
    database.session.add_all([source, previous_note])
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="sales_invoice",
            source_id=source.id,
            target_type="sales_credit_note",
            target_id=previous_note.id,
            qty=Decimal("1"),
            amount=Decimal("60"),
            relation_type="reference",
            status="active",
        )
    )
    database.session.commit()

    with pytest.raises(ValueError, match="excede el saldo pendiente"):
        _validate_reversal_of(
            source.id,
            customer.id,
            "cacao",
            note_amount=Decimal("41"),
            document_type="sales_credit_note",
            posting_date=date.today(),
        )

    _validate_reversal_of(
        source.id,
        customer.id,
        "cacao",
        note_amount=Decimal("40"),
        document_type="sales_credit_note",
        posting_date=date.today(),
    )


def test_credit_note_limit_uses_current_outstanding_not_backdated_balance(app_ctx):
    """A backdated credit note cannot ignore a payment applied after its posting date."""
    from cacao_accounting.ventas.services import _validate_reversal_of

    customer = _ensure_customer("CUST-O2C-CURRENT-OUT", "Cliente saldo actual")
    source = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date(2026, 1, 1),
        docstatus=1,
        document_type="sales_invoice",
        grand_total=Decimal("100"),
    )
    database.session.add(source)
    database.session.commit()

    with patch("cacao_accounting.document_flow.payment.compute_outstanding_amount", return_value=Decimal("0")) as outstanding:
        with pytest.raises(ValueError, match="excede el saldo pendiente"):
            _validate_reversal_of(
                source.id,
                customer.id,
                "cacao",
                note_amount=Decimal("100"),
                document_type="sales_credit_note",
                posting_date=date(2026, 2, 15),
            )

    outstanding.assert_called_once_with(source)


def test_create_document_relation_rejects_cancelled_source(app_ctx):
    from cacao_accounting.document_flow.service import create_document_relation
    from cacao_accounting.document_flow import DocumentFlowError

    _ensure_item("ART-O2C13")
    customer = _ensure_customer("CUST-O2C13", "Cliente O2C13")

    so = SalesOrder(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=2)
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(sales_order_id=so.id, item_code="ART-O2C13", qty=Decimal("5"), rate=Decimal("10"))
    database.session.add(so_item)

    si = SalesInvoice(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=0)
    database.session.add(si)
    database.session.flush()
    si_item = SalesInvoiceItem(sales_invoice_id=si.id, item_code="ART-O2C13", qty=Decimal("2"), rate=Decimal("10"))
    database.session.add(si_item)
    database.session.add(
        DocumentRelation(
            source_type="sales_order",
            source_id=so.id,
            source_item_id=so_item.id,
            target_type="sales_invoice",
            target_id=si.id,
            target_item_id=si_item.id,
            qty=Decimal("2"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    with pytest.raises(DocumentFlowError):
        create_document_relation(
            source_type="sales_order",
            source_id=so.id,
            source_item_id=so_item.id,
            target_type="sales_invoice",
            target_id=si.id,
            target_item_id=si_item.id,
            qty=Decimal("1"),
        )


def test_over_delivery_validation(app_ctx):
    from cacao_accounting.database import DeliveryNote, DeliveryNoteItem
    from cacao_accounting.ventas import _validate_delivery_quantities_against_so

    _ensure_item("ART-RESERVE")
    customer = _ensure_customer("CUST-O2C25", "Cliente O2C25")

    # 1. Crear y aprobar una Orden de Venta por 10 unidades.
    so = SalesOrder(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=1)
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(sales_order_id=so.id, item_code="ART-RESERVE", qty=Decimal("10"), rate=Decimal("5"))
    database.session.add(so_item)
    database.session.flush()

    # 2. Crear una Nota de Entrega asociada a esta Orden de Venta por 12 unidades (invalida).
    dn = DeliveryNote(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=0)
    database.session.add(dn)
    database.session.flush()
    dn_item = DeliveryNoteItem(delivery_note_id=dn.id, item_code="ART-RESERVE", qty=Decimal("12"), rate=Decimal("5"))
    database.session.add(dn_item)
    database.session.flush()

    # Create document relation between SO item and DN item
    database.session.add(
        DocumentRelation(
            source_type="sales_order",
            source_id=so.id,
            source_item_id=so_item.id,
            target_type="delivery_note",
            target_id=dn.id,
            target_item_id=dn_item.id,
            qty=Decimal("12"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    # 3. Intentar aprobar la Nota de Entrega (debe lanzar ValueError por sobre-entrega)
    with pytest.raises(ValueError) as excinfo:
        _validate_delivery_quantities_against_so(dn.id)
    assert "Sobre-entrega" in str(excinfo.value)

    # Now let's change the DN quantity to 10 (valid) and check it passes
    dn_item.qty = Decimal("10")
    # Also need to update the DocumentRelation qty to 10
    rel = database.session.execute(
        database.select(DocumentRelation).filter_by(
            target_type="delivery_note",
            target_id=dn.id,
            target_item_id=dn_item.id,
        )
    ).scalar_one()
    rel.qty = Decimal("10")
    rel.qty_in_base_uom = Decimal("10")
    database.session.commit()

    # This should not raise any exceptions
    _validate_delivery_quantities_against_so(dn.id)


def test_over_billing_validation(app_ctx):
    from cacao_accounting.database import DeliveryNote, DeliveryNoteItem
    from cacao_accounting.ventas import _validate_sales_invoice_quantities

    _ensure_item("ART-RESERVE")
    customer = _ensure_customer("CUST-O2C26", "Cliente O2C26")

    # Flow 1: Direct sales order billing over-billing
    so = SalesOrder(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=1)
    database.session.add(so)
    database.session.flush()
    so_item = SalesOrderItem(sales_order_id=so.id, item_code="ART-RESERVE", qty=Decimal("10"), rate=Decimal("5"))
    database.session.add(so_item)
    database.session.flush()

    si1 = SalesInvoice(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=0)
    database.session.add(si1)
    database.session.flush()
    si1_item = SalesInvoiceItem(sales_invoice_id=si1.id, item_code="ART-RESERVE", qty=Decimal("11"), rate=Decimal("5"))
    database.session.add(si1_item)
    database.session.flush()

    database.session.add(
        DocumentRelation(
            source_type="sales_order",
            source_id=so.id,
            source_item_id=so_item.id,
            target_type="sales_invoice",
            target_id=si1.id,
            target_item_id=si1_item.id,
            qty=Decimal("11"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    with pytest.raises(ValueError) as excinfo:
        _validate_sales_invoice_quantities(si1.id)
    assert "Sobre-facturación" in str(excinfo.value)

    # Flow 2: Delivery Note billing over-billing
    dn = DeliveryNote(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=1)
    database.session.add(dn)
    database.session.flush()
    dn_item = DeliveryNoteItem(delivery_note_id=dn.id, item_code="ART-RESERVE", qty=Decimal("5"), rate=Decimal("5"))
    database.session.add(dn_item)
    database.session.flush()

    si2 = SalesInvoice(customer_id=customer.id, company="cacao", posting_date=date.today(), docstatus=0)
    database.session.add(si2)
    database.session.flush()
    si2_item = SalesInvoiceItem(sales_invoice_id=si2.id, item_code="ART-RESERVE", qty=Decimal("7"), rate=Decimal("5"))
    database.session.add(si2_item)
    database.session.flush()

    database.session.add(
        DocumentRelation(
            source_type="delivery_note",
            source_id=dn.id,
            source_item_id=dn_item.id,
            target_type="sales_invoice",
            target_id=si2.id,
            target_item_id=si2_item.id,
            qty=Decimal("7"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    with pytest.raises(ValueError) as excinfo:
        _validate_sales_invoice_quantities(si2.id)
    assert "Sobre-facturación" in str(excinfo.value)

    # Flow 3: a credit note created directly from an invoice must also respect
    # the quantity invoiced by the source line.
    source_invoice = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=1,
        document_type="sales_invoice",
        grand_total=Decimal("100"),
    )
    database.session.add(source_invoice)
    database.session.flush()
    source_invoice_item = SalesInvoiceItem(
        sales_invoice_id=source_invoice.id,
        item_code="ART-RESERVE",
        qty=Decimal("1"),
        rate=Decimal("100"),
    )
    credit_note = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        docstatus=0,
        document_type="sales_credit_note",
        is_return=True,
        reversal_of=source_invoice.id,
        grand_total=Decimal("50"),
    )
    database.session.add_all([source_invoice_item, credit_note])
    database.session.flush()
    credit_note_item = SalesInvoiceItem(
        sales_invoice_id=credit_note.id,
        item_code="ART-RESERVE",
        qty=Decimal("50"),
        rate=Decimal("1"),
    )
    database.session.add(credit_note_item)
    database.session.flush()
    database.session.add(
        DocumentRelation(
            source_type="sales_invoice",
            source_id=source_invoice.id,
            source_item_id=source_invoice_item.id,
            target_type="sales_invoice",
            target_id=credit_note.id,
            target_item_id=credit_note_item.id,
            qty=Decimal("50"),
            relation_type="fulfillment",
            status="active",
        )
    )
    database.session.commit()

    with pytest.raises(ValueError) as excinfo:
        _validate_sales_invoice_quantities(credit_note.id)
    assert "Sobre-facturación" in str(excinfo.value)
