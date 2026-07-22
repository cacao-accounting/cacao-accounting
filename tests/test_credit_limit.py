# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moore Reyes

"""Pruebas para validación de límites de crédito y bloqueo de facturas vencidas (O2C-23)."""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Book,
    CompanyParty,
    PaymentTerms,
    Item,
    Party,
    SalesInvoice,
    SalesOrder,
    SalesOrderItem,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.ventas import _validate_credit_limit_and_overdue


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
    cp = database.session.execute(
        database.select(CompanyParty).filter_by(party_id=customer.id, company="cacao")
    ).scalar_one_or_none()
    if not cp:
        cp = CompanyParty(party_id=customer.id, company="cacao", is_active=True)
        database.session.add(cp)
        database.session.commit()
    return customer, cp


def test_credit_limit_validation(app_ctx):
    customer, cp = _ensure_customer("CUST-LIMIT-1", "Cliente con Limite")

    # scenario 1: no limit
    cp.credit_limit = None
    database.session.commit()
    # Should not raise exception
    _validate_credit_limit_and_overdue("cacao", customer.id, Decimal("5000"))

    # scenario 2: within limit
    cp.credit_limit = Decimal("1000")
    database.session.commit()
    # 500 is within 1000
    _validate_credit_limit_and_overdue("cacao", customer.id, Decimal("500"))

    # scenario 3: exceeds limit
    with pytest.raises(ValueError) as excinfo:
        _validate_credit_limit_and_overdue("cacao", customer.id, Decimal("1001"))
    assert "límite de crédito" in str(excinfo.value).lower()


def test_block_overdue_validation(app_ctx):
    customer, cp = _ensure_customer("CUST-OVERDUE-1", "Cliente Overdue")
    _ensure_item("ART-O2C")

    # Set payment terms to 10 days
    terms = PaymentTerms(name="10 Dias", due_days=10, is_active=True)
    database.session.add(terms)
    database.session.flush()
    cp.payment_terms_id = terms.id
    cp.block_overdue = True
    database.session.commit()

    # Add a posted sales invoice from 15 days ago (outstanding > 0, so it is overdue)
    past_date = date.today() - timedelta(days=15)
    invoice = SalesInvoice(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=past_date,
        docstatus=1,
        grand_total=Decimal("100"),
        outstanding_amount=Decimal("100"),
        base_outstanding_amount=Decimal("100"),
    )
    database.session.add(invoice)
    database.session.flush()
    database.session.commit()

    # Should raise ValueError since invoice is overdue and block_overdue is True
    with pytest.raises(ValueError) as excinfo:
        _validate_credit_limit_and_overdue("cacao", customer.id, Decimal("10"))
    assert "facturas vencidas" in str(excinfo.value).lower()

    # If block_overdue is False, it should not raise ValueError
    cp.block_overdue = False
    database.session.commit()
    _validate_credit_limit_and_overdue("cacao", customer.id, Decimal("10"))


def test_route_submit_credit_limit_blocks(app_ctx):
    client = app_ctx.test_client()
    client.post("/login", data={"usuario": "cacao", "acceso": "cacao"}, follow_redirects=True)
    customer, cp = _ensure_customer("CUST-SUBMIT-LIMIT", "Cliente Submit Limit")
    _ensure_item("ART-O2C")

    # Set a tight credit limit
    cp.credit_limit = Decimal("50")
    database.session.commit()

    # Create Sales Order of 100 (which exceeds 50)
    so = SalesOrder(
        customer_id=customer.id,
        customer_name=customer.name,
        company="cacao",
        posting_date=date.today(),
        docstatus=0,
        grand_total=Decimal("100"),
    )
    database.session.add(so)
    database.session.flush()
    database.session.add(
        SalesOrderItem(sales_order_id=so.id, item_code="ART-O2C", qty=Decimal("10"), rate=Decimal("10"), amount=Decimal("100"))
    )
    database.session.commit()

    # Try to submit the sales order via POST route
    response = client.post(f"/sales/sales-order/{so.id}/submit", follow_redirects=True)
    assert response.status_code == 200
    # The submission should fail and keep the document in draft (docstatus=0)
    database.session.refresh(so)
    assert so.docstatus == 0


def test_skip_credit_limit_on_return(app_ctx):
    customer, cp = _ensure_customer("CUST-RETURN-LIMIT", "Cliente Return Limit")

    cp.credit_limit = Decimal("50")
    database.session.commit()

    # Even though -100 is passed, or if the document is a return, it should not raise an error
    _validate_credit_limit_and_overdue("cacao", customer.id, Decimal("-100"))
