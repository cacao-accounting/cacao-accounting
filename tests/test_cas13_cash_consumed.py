"""Tests for CAS-13: _cash_consumed=0 bypasses balance check when discount >= allocated."""

import json
from datetime import date
from decimal import Decimal

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import database, Party, BankAccount, PurchaseInvoice
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


def _make_supplier_invoice(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")
    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    invoice = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=1,
        grand_total=1000,
        outstanding_amount=1000,
        base_outstanding_amount=1000,
    )
    database.session.add(invoice)
    database.session.commit()
    return client, supplier, bank, invoice


def test_cas13_discount_exceeds_allocated_rejected(app_ctx):
    """CAS-13: discount >= allocated must be rejected."""
    client, supplier, bank, invoice = _make_supplier_invoice(app_ctx)

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 900,
        "party_id": supplier.id,
        "party_type": "supplier",
        "lines": [
            {
                "reference_type": "purchase_invoice",
                "reference_id": invoice.id,
                "allocated_amount": 100,
                "discount_amount": 150,
                "gain_loss_amount": 0,
            }
        ],
    }
    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert b"error" in response.data.lower() or b"descuento" in response.data.lower() or response.status_code in (400, 409)


def test_cas13_discount_equals_allocated_rejected(app_ctx):
    """CAS-13: discount == allocated must be rejected (consumed=0 bypass)."""
    client, supplier, bank, invoice = _make_supplier_invoice(app_ctx)

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 900,
        "party_id": supplier.id,
        "party_type": "supplier",
        "lines": [
            {
                "reference_type": "purchase_invoice",
                "reference_id": invoice.id,
                "allocated_amount": 100,
                "discount_amount": 100,
                "gain_loss_amount": 0,
            }
        ],
    }
    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert b"error" in response.data.lower() or b"descuento" in response.data.lower() or response.status_code in (400, 409)


def test_cas13_valid_discount_below_allocated_accepted(app_ctx):
    """Normal case: discount < allocated should be accepted."""
    client, supplier, bank, invoice = _make_supplier_invoice(app_ctx)

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 900,
        "party_id": supplier.id,
        "party_type": "supplier",
        "lines": [
            {
                "reference_type": "purchase_invoice",
                "reference_id": invoice.id,
                "allocated_amount": 1000,
                "discount_amount": 100,
                "gain_loss_amount": 0,
            }
        ],
    }
    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in response.data


def test_cas13_unit_cash_consumed():
    """Unit test: _cash_consumed returns correct values."""
    from cacao_accounting.document_flow.payment import _cash_consumed

    assert _cash_consumed(Decimal("100"), Decimal("30"), Decimal("0")) == Decimal("70")
    assert _cash_consumed(Decimal("100"), Decimal("0"), Decimal("0")) == Decimal("100")
    assert _cash_consumed(Decimal("100"), Decimal("100"), Decimal("0")) == Decimal("0")
    assert _cash_consumed(Decimal("100"), Decimal("80"), Decimal("30")) == Decimal("0")
