# SPDX-License-Identifier: Apache-2.0
"""Regresión para el issue #781: sales_return reduce el outstanding de la factura origen."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Accounts,
    Book,
    CompanyParty,
    DocumentRelation,
    Item,
    Party,
    SalesInvoice,
    SalesInvoiceItem,
    Warehouse,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


@pytest.fixture()
def app_ctx():
    """Crea un contexto de aplicación aislado en memoria."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key_sales_return_781",
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
        for book in books:
            if book.is_primary and book.status is None:
                book.status = "activo"
        database.session.commit()
        yield app


def _ensure_item(code="ITEM-SR781", warehouse="WH-MAIN"):
    """Crea el artículo y la bodega mínima para emitir facturas."""
    wh = database.session.get(Warehouse, warehouse)
    if not wh:
        wh = Warehouse(code=warehouse, name="Almacén Principal SR781", company="cacao")
        database.session.add(wh)
        database.session.flush()
    inv_account = (
        database.session.execute(database.select(Accounts).filter_by(entity="cacao", account_type="inventory"))
        .scalars()
        .first()
    )
    if (
        inv_account
        and not database.session.execute(
            database.select(WarehouseCompanyAccount).filter_by(warehouse_code=warehouse, company="cacao")
        ).scalar_one_or_none()
    ):
        database.session.add(
            WarehouseCompanyAccount(
                warehouse_code=warehouse,
                company="cacao",
                inventory_account_id=inv_account.id,
                is_active=True,
            )
        )
        database.session.flush()
    item = database.session.get(Item, code)
    if not item:
        item = Item(
            code=code,
            name=f"Artículo {code}",
            item_type="goods",
            is_stock_item=True,
            default_uom="UND",
            default_warehouse_id=warehouse,
        )
        database.session.add(item)
        database.session.flush()
    return item


def _ensure_customer(code="CUST-SR781", name="Cliente SR781"):
    """Crea el cliente y su vínculo con la compañía cacao."""
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


def _create_invoice(customer, item, *, amount, document_type="sales_invoice", reversal_of=None):
    """Crea una factura/nota/devolución en borrador con una línea."""
    invoice = SalesInvoice(
        customer_id=customer.id,
        company="cacao",
        posting_date=date.today(),
        document_type=document_type,
        reversal_of=reversal_of,
        is_return=document_type in ("sales_credit_note", "sales_return"),
        transaction_currency="NIO",
        base_currency="NIO",
        total=Decimal(str(amount)),
        grand_total=Decimal(str(amount)),
        docstatus=0,
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code=item.code,
            qty=Decimal("1"),
            rate=Decimal(str(amount)),
            amount=Decimal(str(amount)),
        )
    )
    database.session.commit()
    return invoice


def test_sales_return_reduces_original_outstanding(app_ctx):
    """Reproduce el issue #781: factura 1000 + devolución 200 deja saldo 800."""
    from cacao_accounting.document_flow.payment import compute_outstanding_amount

    customer = _ensure_customer()
    item = _ensure_item()
    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    invoice = _create_invoice(customer, item, amount="1000", document_type="sales_invoice")
    assert client.post(f"/sales/sales-invoice/{invoice.id}/submit", follow_redirects=True).status_code == 200
    database.session.refresh(invoice)
    assert invoice.docstatus == 1
    assert compute_outstanding_amount(invoice) == Decimal("1000")

    sales_return = _create_invoice(customer, item, amount="200", document_type="sales_return", reversal_of=invoice.id)
    assert client.post(f"/sales/sales-invoice/{sales_return.id}/submit", follow_redirects=True).status_code == 200
    database.session.refresh(sales_return)
    assert sales_return.docstatus == 1

    relation = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                source_type="sales_invoice",
                source_id=invoice.id,
                target_type="sales_return",
                target_id=sales_return.id,
            )
        )
        .scalars()
        .first()
    )
    assert relation is not None
    assert relation.status == "active"

    database.session.refresh(invoice)
    assert compute_outstanding_amount(invoice) == Decimal("800")


def test_sales_return_combines_with_credit_note_without_double_count(app_ctx):
    """Una devolución y una nota de crédito reducen el saldo de forma aditiva."""
    from cacao_accounting.document_flow.payment import compute_outstanding_amount

    customer = _ensure_customer("CUST-SR781-B", "Cliente SR781 B")
    item = _ensure_item("ITEM-SR781-B")
    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)

    invoice = _create_invoice(customer, item, amount="1000", document_type="sales_invoice")
    assert client.post(f"/sales/sales-invoice/{invoice.id}/submit", follow_redirects=True).status_code == 200

    credit_note = _create_invoice(customer, item, amount="400", document_type="sales_credit_note", reversal_of=invoice.id)
    assert client.post(f"/sales/sales-invoice/{credit_note.id}/submit", follow_redirects=True).status_code == 200
    assert compute_outstanding_amount(invoice) == Decimal("600")

    sales_return = _create_invoice(customer, item, amount="100", document_type="sales_return", reversal_of=invoice.id)
    assert client.post(f"/sales/sales-invoice/{sales_return.id}/submit", follow_redirects=True).status_code == 200
    assert compute_outstanding_amount(invoice) == Decimal("500")


def test_sales_reversal_source_supports_sales_return(app_ctx):
    """La vía UI resuelve la factura origen también para sales_return."""
    from cacao_accounting.ventas.services import _sales_reversal_source

    with app_ctx.test_request_context("/ventas/factura", method="POST", data={"from_invoice": "INV-1", "from_return": ""}):
        assert _sales_reversal_source("sales_return") == "INV-1"
        assert _sales_reversal_source("sales_credit_note") == "INV-1"
        assert _sales_reversal_source("sales_invoice") is None
