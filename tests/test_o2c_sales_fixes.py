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
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    SalesMatchingConfig,
    SalesOrder,
    SalesOrderItem,
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
