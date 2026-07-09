# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations
import json
from datetime import date
from decimal import Decimal

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import (
    Accounts,
    database,
    Party,
    BankAccount,
    ExternalCounter,
    CompanyDefaultAccount,
    SalesInvoice,
    SalesInvoiceItem,
    PurchaseInvoice,
    PurchaseOrder,
    PaymentEntry,
    PaymentReference,
    DocumentRelation,
    GLEntry,
    SalesOrder,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.search_select import search_select


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


def _payment_gl_entries(payment_id: str) -> list[GLEntry]:
    return (
        database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=payment_id))
        .scalars()
        .all()
    )


def _first_account_id(company: str, account_type: str) -> str | None:
    account = (
        database.session.execute(
            database.select(Accounts).filter_by(entity=company, account_type=account_type).order_by(Accounts.code.asc())
        )
        .scalars()
        .first()
    )
    return account.id if account else None


def _ensure_company_default_accounts(company: str, bank: BankAccount) -> CompanyDefaultAccount:
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()
    if not defaults:
        defaults = CompanyDefaultAccount(company=company)
        database.session.add(defaults)
        database.session.flush()
    defaults.default_bank = defaults.default_bank or bank.gl_account_id or _first_account_id(company, "bank")
    defaults.default_cash = defaults.default_cash or _first_account_id(company, "cash") or defaults.default_bank
    defaults.default_receivable = defaults.default_receivable or _first_account_id(company, "receivable")
    defaults.default_payable = defaults.default_payable or _first_account_id(company, "payable")
    defaults.customer_advance_account_id = defaults.customer_advance_account_id or defaults.default_payable
    defaults.supplier_advance_account_id = defaults.supplier_advance_account_id or defaults.default_receivable
    defaults.payment_discount_account_id = defaults.payment_discount_account_id or _first_account_id(company, "expense")
    defaults.exchange_gain_account_id = defaults.exchange_gain_account_id or _first_account_id(company, "income")
    defaults.exchange_loss_account_id = defaults.exchange_loss_account_id or _first_account_id(company, "expense")
    defaults.unrealized_exchange_gain_account_id = (
        defaults.unrealized_exchange_gain_account_id or defaults.exchange_gain_account_id
    )
    defaults.unrealized_exchange_loss_account_id = (
        defaults.unrealized_exchange_loss_account_id or defaults.exchange_loss_account_id
    )
    database.session.commit()
    return defaults


def test_payment_to_single_invoice(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    # 1. Create a submitted Sales Invoice
    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    si = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=1000,
        outstanding_amount=1000,
        base_outstanding_amount=1000,
    )
    database.session.add(si)
    database.session.flush()
    sii = SalesInvoiceItem(sales_invoice_id=si.id, item_code="ART-001", qty=1, rate=1000, amount=1000)
    database.session.add(sii)
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    # 2. Create Payment Entry via JSON payload
    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "reference_no": "REF-001",
        "reference_date": date.today().isoformat(),
        "mode_of_payment": "transfer",
        "lines": [
            {
                "reference_type": "sales_invoice",
                "reference_id": si.id,
                "allocated_amount": 1000,
                "discount_amount": 0,
                "gain_loss_amount": 0,
                "notes": "Test note",
            }
        ],
    }

    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Pago registrado correctamente" in response.data

    # 3. Verify database
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    assert pe.paid_amount in (0, None)  # received_amount should be set
    assert pe.received_amount == 1000
    assert pe.reference_no == "REF-001"
    assert pe.mode_of_payment == "transfer"

    ref = database.session.execute(database.select(PaymentReference).filter_by(payment_id=pe.id)).scalars().first()
    assert ref.reference_id == si.id
    assert ref.allocated_amount == 1000
    assert ref.notes == "Test note"

    database.session.refresh(si)
    assert si.outstanding_amount == 0


def test_payment_over_application_blocking(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    si = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=2000,
        outstanding_amount=2000,
    )
    database.session.add(si)
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    # Try to apply 1200 to a 1000 payment (invoice has 2000 outstanding, so it's not a reference-level overflow)
    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_invoice", "reference_id": si.id, "allocated_amount": 1200}],
    }

    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True
    )
    # The backend validation should catch this
    # decode data to check content
    content = response.data.decode("utf-8")
    assert "El monto aplicado no puede ser mayor al monto total del pago" in content


def test_payment_line_cannot_exceed_individual_outstanding(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=1000,
        outstanding_amount=100,
        base_outstanding_amount=100,
    )
    database.session.add(invoice)
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 500}],
    }
    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True
    )
    assert b"Pago registrado correctamente" not in response.data
    assert "saldo pendiente" in response.data.decode("utf-8").lower()


def test_payment_with_discount_and_gain_loss(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    si = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=1000,
        outstanding_amount=1000,
    )
    database.session.add(si)
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 950,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [
            {
                "reference_type": "sales_invoice",
                "reference_id": si.id,
                "allocated_amount": 950,
                "discount_amount": 50,
                "gain_loss_amount": 0,
            }
        ],
    }

    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True
    )
    assert b"Pago registrado correctamente" in response.data

    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    ref = database.session.execute(database.select(PaymentReference).filter_by(payment_id=pe.id)).scalars().first()
    assert ref.discount_amount == 50


def test_unallocated_payment(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    # Payment with NO lines (unallocated / advance)
    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 500,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [],
    }

    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True
    )
    assert b"Pago registrado correctamente" in response.data

    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    assert pe.received_amount == 500
    from cacao_accounting.document_flow.service import compute_payment_unallocated_amount

    assert compute_payment_unallocated_amount(pe) == 500

    refs = database.session.execute(database.select(PaymentReference).filter_by(payment_id=pe.id)).scalars().all()
    assert len(refs) == 0


def test_unallocated_payment_excludes_reverted_references(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=1000,
        outstanding_amount=1000,
        base_outstanding_amount=1000,
    )
    database.session.add(invoice)
    database.session.commit()

    payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 600}],
    }
    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payload)}, follow_redirects=True
    )
    assert b"Pago registrado correctamente" in response.data
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()

    from cacao_accounting.document_flow.service import compute_payment_unallocated_amount, revert_relations_for_target

    assert compute_payment_unallocated_amount(pe) == 400
    revert_relations_for_target("payment_entry", pe.id, reason="test_only")
    database.session.commit()
    assert compute_payment_unallocated_amount(pe) == 1000


def test_unallocated_payment_uses_cash_consumed_formula(app_ctx):
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
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payload)}, follow_redirects=True
    )
    assert b"Pago registrado correctamente" in response.data
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()

    from cacao_accounting.document_flow.service import compute_payment_unallocated_amount

    assert compute_payment_unallocated_amount(pe) == 0


def test_partial_allocation_no_discount(app_ctx):
    """Verifica que un pago parcial sin descuento reporta el saldo correcto.

    paid_amount = 1000, allocated_amount = 700, discount = 0 → unallocated = 300.
    """
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

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": supplier.id,
        "party_type": "supplier",
        "lines": [
            {
                "reference_type": "purchase_invoice",
                "reference_id": invoice.id,
                "allocated_amount": 700,
                "discount_amount": 0,
                "gain_loss_amount": 0,
            }
        ],
    }
    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payload)}, follow_redirects=True
    )
    assert b"Pago registrado correctamente" in response.data
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()

    from cacao_accounting.document_flow.service import compute_payment_unallocated_amount

    assert compute_payment_unallocated_amount(pe) == 300


def test_payment_to_multiple_invoices(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    si1 = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=300,
        outstanding_amount=300,
    )
    si2 = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=400,
        outstanding_amount=400,
    )
    si3 = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=300,
        outstanding_amount=300,
    )
    database.session.add_all([si1, si2, si3])
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [
            {"reference_type": "sales_invoice", "reference_id": si1.id, "allocated_amount": 300},
            {"reference_type": "sales_invoice", "reference_id": si2.id, "allocated_amount": 400},
            {"reference_type": "sales_invoice", "reference_id": si3.id, "allocated_amount": 300},
        ],
    }

    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True
    )
    assert b"Pago registrado correctamente" in response.data

    database.session.refresh(si1)
    database.session.refresh(si2)
    database.session.refresh(si3)
    from cacao_accounting.document_flow.service import compute_outstanding_amount

    assert compute_outstanding_amount(si1) == 0
    assert compute_outstanding_amount(si2) == 0
    assert compute_outstanding_amount(si3) == 0


def test_multiple_payments_to_single_invoice(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    si = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=1000,
        outstanding_amount=1000,
    )
    database.session.add(si)
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    # First payment: 250
    p1 = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 250,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_invoice", "reference_id": si.id, "allocated_amount": 250}],
    }
    client.post("/cash_management/payment/new", data={"payment_payload": json.dumps(p1)}, follow_redirects=True)

    from cacao_accounting.document_flow.service import compute_outstanding_amount

    database.session.refresh(si)
    assert compute_outstanding_amount(si) == 750

    # Second payment: 300
    p2 = p1.copy()
    p2["paid_amount"] = 300
    p2["lines"] = [{"reference_type": "sales_invoice", "reference_id": si.id, "allocated_amount": 300}]
    client.post("/cash_management/payment/new", data={"payment_payload": json.dumps(p2)}, follow_redirects=True)

    database.session.refresh(si)
    assert compute_outstanding_amount(si) == 450

    # Third payment: 450
    p3 = p1.copy()
    p3["paid_amount"] = 450
    p3["lines"] = [{"reference_type": "sales_invoice", "reference_id": si.id, "allocated_amount": 450}]
    response = client.post("/cash_management/payment/new", data={"payment_payload": json.dumps(p3)}, follow_redirects=True)
    assert b"Pago registrado correctamente" in response.data
    database.session.refresh(si)
    assert compute_outstanding_amount(si) == 0


def test_payment_cancellation_and_balance_restoration(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    si = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=1000,
        outstanding_amount=1000,
    )
    database.session.add(si)
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_invoice", "reference_id": si.id, "allocated_amount": 1000}],
    }

    client.post("/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True)
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()

    from cacao_accounting.document_flow.service import compute_outstanding_amount

    database.session.refresh(si)
    assert compute_outstanding_amount(si) == 0

    # Submit the payment (required to cancel)
    client.post(f"/cash_management/payment/{pe.id}/submit", follow_redirects=True)
    database.session.refresh(pe)
    assert pe.docstatus == 1

    # Cancel the payment
    client.post(f"/cash_management/payment/{pe.id}/cancel", follow_redirects=True)

    database.session.refresh(pe)
    assert pe.docstatus == 2
    database.session.refresh(si)
    assert compute_outstanding_amount(si) == 1000
    active_relations = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="payment_entry", target_id=pe.id, status="active")
        )
        .scalars()
        .all()
    )
    assert len(active_relations) == 0
    reversed_relations = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(target_type="payment_entry", target_id=pe.id, status="reverted")
        )
        .scalars()
        .all()
    )
    assert len(reversed_relations) >= 1
    reversal_entries = (
        database.session.execute(
            database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=pe.id, is_reversal=True)
        )
        .scalars()
        .all()
    )
    assert len(reversal_entries) >= 1


def test_order_reference_requires_advance_mode(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    order = SalesOrder(company="cacao", customer_id=customer.id, posting_date=date.today(), docstatus=1, grand_total=1000)
    database.session.add(order)
    database.session.commit()

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_order", "reference_id": order.id, "allocated_amount": 1000}],
    }
    response = client.post(
        "/cash_management/payment/new", data={"payment_payload": json.dumps(payload)}, follow_redirects=True
    )
    assert b"flujo de anticipo" in response.data


def test_accounting_entries_for_customer_collection(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    defaults = _ensure_company_default_accounts("cacao", bank)

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [],  # Unallocated to keep it simple
    }

    client.post("/cash_management/payment/new", data={"payment_payload": json.dumps(payment_payload)}, follow_redirects=True)
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()

    # Submit to generate GL
    response = client.post(f"/cash_management/payment/{pe.id}/submit", follow_redirects=True)
    assert b"Pago aprobado" in response.data
    database.session.refresh(pe)
    assert pe.docstatus == 1

    entries = _payment_gl_entries(pe.id)
    assert len(entries) >= 2
    account_ids = {entry.account_id for entry in entries}
    accounts = database.session.execute(database.select(Accounts).where(Accounts.id.in_(account_ids))).scalars().all()
    assert any(account.account_type in {"bank", "cash"} for account in accounts)
    assert defaults.customer_advance_account_id in account_ids

    # Debits should equal credits
    total_debit = sum(e.debit for e in entries if e.ledger_id == entries[0].ledger_id)
    total_credit = sum(e.credit for e in entries if e.ledger_id == entries[0].ledger_id)
    assert total_debit == total_credit == 1000


@pytest.mark.parametrize(
    "party_type,payment_type,reference_type,document_type,expected_party_account_type",
    [
        ("supplier", "pay", "purchase_invoice", "purchase_invoice", "payable"),
        ("customer", "pay", "sales_credit_note", "sales_credit_note", "payable"),
        ("supplier", "receive", "purchase_credit_note", "purchase_credit_note", "receivable"),
        ("supplier", "pay", "purchase_debit_note", "purchase_debit_note", "payable"),
        ("customer", "receive", "sales_debit_note", "sales_debit_note", "receivable"),
    ],
)
def test_accounting_entries_for_payment_variants(
    app_ctx, party_type, payment_type, reference_type, document_type, expected_party_account_type
):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    if party_type == "supplier":
        party_filter = Party.is_supplier.is_(True)
    else:
        party_filter = Party.is_customer.is_(True)
    party = database.session.execute(database.select(Party).filter(party_filter)).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    _ensure_company_default_accounts("cacao", bank)
    if party_type == "supplier":
        doc = PurchaseInvoice(
            company="cacao",
            supplier_id=party.id,
            posting_date=date.today(),
            document_type=document_type,
            docstatus=1,
            grand_total=1000,
            outstanding_amount=1000,
            base_outstanding_amount=1000,
        )
    else:
        doc = SalesInvoice(
            company="cacao",
            customer_id=party.id,
            posting_date=date.today(),
            document_type=document_type,
            docstatus=1,
            grand_total=1000,
            outstanding_amount=1000,
            base_outstanding_amount=1000,
        )
    database.session.add(doc)
    database.session.commit()

    payment_payload = {
        "payment_type": payment_type,
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 1000,
        "party_id": party.id,
        "party_type": party_type,
        "lines": [{"reference_type": reference_type, "reference_id": doc.id, "allocated_amount": 1000}],
    }

    create_response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in create_response.data
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    submit_response = client.post(f"/cash_management/payment/{pe.id}/submit", follow_redirects=True)
    assert b"Pago aprobado" in submit_response.data
    entries = _payment_gl_entries(pe.id)
    assert len(entries) >= 2
    account_ids = {entry.account_id for entry in entries}
    accounts = database.session.execute(database.select(Accounts).where(Accounts.id.in_(account_ids))).scalars().all()
    assert any(account.account_type in {"bank", "cash"} for account in accounts)
    party_line_account_ids = {entry.account_id for entry in entries if entry.party_id == party.id and entry.account_id}
    party_accounts = (
        database.session.execute(database.select(Accounts).where(Accounts.id.in_(party_line_account_ids))).scalars().all()
        if party_line_account_ids
        else []
    )
    assert any(account.account_type == expected_party_account_type for account in party_accounts)
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)


def test_supplier_discount_is_persisted_on_reference(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    defaults = _ensure_company_default_accounts("cacao", bank)
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

    payment_payload = {
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
            }
        ],
    }
    create_response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in create_response.data
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    reference = database.session.execute(database.select(PaymentReference).filter_by(payment_id=pe.id)).scalars().first()
    assert reference is not None
    assert reference.discount_amount == 100
    assert defaults.payment_discount_account_id is not None


def test_accounting_entries_with_gain_loss_adjustment(app_ctx):
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    defaults = _ensure_company_default_accounts("cacao", bank)
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=1000,
        outstanding_amount=1000,
        base_outstanding_amount=1000,
    )
    database.session.add(invoice)
    database.session.commit()

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 950,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [
            {
                "reference_type": "sales_invoice",
                "reference_id": invoice.id,
                "allocated_amount": 1000,
                "discount_amount": 0,
                "gain_loss_amount": 50,
            }
        ],
    }
    create_response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in create_response.data
    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    submit_response = client.post(f"/cash_management/payment/{pe.id}/submit", follow_redirects=True)
    assert b"Pago aprobado" in submit_response.data
    entries = _payment_gl_entries(pe.id)
    assert len(entries) >= 2
    exchange_lines = [entry for entry in entries if "Exchange Difference" in (entry.remarks or "")]
    if exchange_lines:
        expected_accounts = {defaults.exchange_gain_account_id, defaults.exchange_loss_account_id}
        assert all(entry.account_id in expected_accounts for entry in exchange_lines)
        assert any(entry.account_id in expected_accounts for entry in exchange_lines)
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)


def test_advance_payment_from_purchase_order(app_ctx):
    """Anticipo a proveedor desde orden: no debe afectar AR/AP de factura."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    defaults = _ensure_company_default_accounts("cacao", bank)

    order = PurchaseOrder(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=500,
    )
    database.session.add(order)
    database.session.commit()

    payment_payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 500,
        "party_id": supplier.id,
        "party_type": "supplier",
        "advance_mode": True,
        "lines": [
            {
                "reference_type": "purchase_order",
                "reference_id": order.id,
                "allocated_amount": 500,
            }
        ],
    }

    create_response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in create_response.data

    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    assert pe is not None
    reference = database.session.execute(database.select(PaymentReference).filter_by(payment_id=pe.id)).scalars().first()
    assert reference is not None
    assert reference.reference_type == "purchase_order"
    assert reference.flow_source_type == "purchase_order"
    assert reference.reference_document_no == (order.document_no or order.id)
    assert reference.company == "cacao"
    assert reference.party_type == "supplier"
    assert reference.party_id == supplier.id
    relation = (
        database.session.execute(
            database.select(DocumentRelation).filter_by(
                source_type="purchase_order",
                source_id=order.id,
                target_type="payment_entry",
                target_id=pe.id,
                target_item_id=reference.id,
                status="active",
            )
        )
        .scalars()
        .first()
    )
    assert relation is not None

    from cacao_accounting.document_flow.service import compute_payment_unallocated_amount

    assert compute_payment_unallocated_amount(pe) == 500

    submit_response = client.post(f"/cash_management/payment/{pe.id}/submit", follow_redirects=True)
    assert b"Pago aprobado" in submit_response.data

    database.session.refresh(pe)
    assert pe.docstatus == 1

    # GL entries should exist and balance
    entries = _payment_gl_entries(pe.id)
    assert len(entries) >= 2
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)

    # Advance/bridge account must be used — bank account should NOT be the only account
    account_ids = {entry.account_id for entry in entries}
    bank_gl_account = bank.gl_account_id if bank else None
    assert any(aid != bank_gl_account for aid in account_ids)
    assert defaults.supplier_advance_account_id in account_ids


def test_advance_payment_from_sales_order(app_ctx):
    """Anticipo de cliente desde orden de venta: usa cuenta puente."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    defaults = _ensure_company_default_accounts("cacao", bank)

    order = SalesOrder(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=800,
    )
    database.session.add(order)
    database.session.commit()

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 800,
        "party_id": customer.id,
        "party_type": "customer",
        "advance_mode": True,
        "lines": [
            {
                "reference_type": "sales_order",
                "reference_id": order.id,
                "allocated_amount": 800,
            }
        ],
    }

    create_response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in create_response.data

    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    reference = database.session.execute(database.select(PaymentReference).filter_by(payment_id=pe.id)).scalars().first()
    assert reference is not None
    assert reference.reference_type == "sales_order"
    assert reference.flow_source_type == "sales_order"
    assert reference.party_type == "customer"
    assert reference.party_id == customer.id

    from cacao_accounting.document_flow.service import compute_payment_unallocated_amount

    assert compute_payment_unallocated_amount(pe) == 800
    submit_response = client.post(f"/cash_management/payment/{pe.id}/submit", follow_redirects=True)
    assert b"Pago aprobado" in submit_response.data

    database.session.refresh(pe)
    assert pe.docstatus == 1

    entries = _payment_gl_entries(pe.id)
    assert len(entries) >= 2
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)

    account_ids = {entry.account_id for entry in entries}
    bank_gl_account = bank.gl_account_id if bank else None
    assert any(aid != bank_gl_account for aid in account_ids)
    assert defaults.customer_advance_account_id in account_ids


def test_payment_from_purchase_order_prefills_reference_line(app_ctx):
    """La acción Crear desde orden abre pago con línea de anticipo trazable."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    order = PurchaseOrder(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=375,
        document_no="PO-PREFILL-001",
    )
    database.session.add(order)
    database.session.commit()

    response = client.get(f"/cash_management/payment/new?from_purchase_order={order.id}")

    assert response.status_code == 200
    assert b"purchase_order" in response.data
    assert b"PO-PREFILL-001" in response.data
    assert b"payment-reference-candidates" in response.data


def test_payment_source_rows_preserve_order_and_skip_missing(app_ctx):
    """Las filas de origen conservan el orden y omiten documentos faltantes."""
    from cacao_accounting.bancos import _payment_source_rows
    from cacao_accounting.database import Party, PurchaseInvoice, SalesOrder, database

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    purchase_invoice = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=1,
        grand_total=100,
        document_no="PI-SRC-001",
    )
    sales_order = SalesOrder(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        docstatus=1,
        grand_total=200,
        document_no="SO-SRC-001",
    )
    database.session.add_all([purchase_invoice, sales_order])
    database.session.commit()

    with app_ctx.test_request_context("/cash_management/payment/new"):
        rows = _payment_source_rows(
            [purchase_invoice.id, "missing-invoice"],
            [],
            [],
            [sales_order.id],
            [],
            [],
            [],
            [],
        )

    assert [row["reference_type"] for row in rows] == ["purchase_invoice", "sales_order"]
    assert [row["document"].id for row in rows] == [purchase_invoice.id, sales_order.id]


def test_payment_source_rows_filters_note_document_types(app_ctx):
    """Las notas solo entran si su tipo documental coincide con el esperado."""
    from cacao_accounting.bancos import _payment_source_rows
    from cacao_accounting.database import Party, PurchaseInvoice, SalesInvoice, database

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    purchase_credit_note = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_credit_note",
        docstatus=1,
        grand_total=100,
        document_no="PCN-SRC-001",
    )
    purchase_invoice = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=1,
        grand_total=50,
        document_no="PI-SRC-002",
    )
    sales_credit_note = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_credit_note",
        docstatus=1,
        grand_total=80,
        document_no="SCN-SRC-001",
    )
    wrong_sales_note = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=40,
        document_no="SI-SRC-IGNORED",
    )
    database.session.add_all([purchase_credit_note, purchase_invoice, sales_credit_note, wrong_sales_note])
    database.session.commit()

    with app_ctx.test_request_context("/cash_management/payment/new"):
        rows = _payment_source_rows(
            [],
            [],
            [],
            [],
            [purchase_credit_note.id, purchase_invoice.id],
            [],
            [sales_credit_note.id, wrong_sales_note.id],
            [],
        )

    assert [row["reference_type"] for row in rows] == ["purchase_invoice", "sales_invoice"]
    assert [row["flow_source_type"] for row in rows] == ["purchase_credit_note", "sales_credit_note"]


def test_payment_reference_candidates_endpoint_filters_by_party_and_company(app_ctx):
    """El endpoint de candidatos devuelve documentos pendientes del mismo tercero."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    other_customer = Party(
        id="candidate_other_customer", code="CANDIDATE_OTHER", is_customer=True, name="Cliente Candidatos Otro"
    )
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=300,
        outstanding_amount=300,
        base_outstanding_amount=300,
        document_no="FV-CAND-001",
    )
    other_invoice = SalesInvoice(
        company="cacao",
        customer_id=other_customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=500,
        outstanding_amount=500,
        base_outstanding_amount=500,
        document_no="FV-CAND-OTHER",
    )
    database.session.add_all([other_customer, invoice, other_invoice])
    database.session.commit()

    response = client.get(
        "/api/document-flow/payment-reference-candidates",
        query_string={
            "company": "cacao",
            "party_type": "customer",
            "party_id": customer.id,
            "source_type": ["sales_invoice", "sales_credit_note"],
        },
    )

    assert response.status_code == 200
    items = response.get_json()["items"]
    assert any(item["reference_id"] == invoice.id for item in items)
    assert all(item["reference_id"] != other_invoice.id for item in items)
    candidate = next(item for item in items if item["reference_id"] == invoice.id)
    assert candidate["reference_type"] == "sales_invoice"
    assert candidate["flow_source_type"] == "sales_invoice"
    assert candidate["pending_amount"] == 300.0


def test_payment_reference_snapshot_is_persisted(app_ctx):
    """Las referencias guardan snapshot minimo para auditoria futura."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    _ensure_company_default_accounts("cacao", bank)
    invoice = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=1,
        grand_total=450,
        outstanding_amount=450,
        base_outstanding_amount=450,
        document_no="PI-SNAPSHOT-001",
    )
    database.session.add(invoice)
    database.session.commit()

    payment_payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "currency": "NIO",
        "posting_date": date.today().isoformat(),
        "paid_amount": 200,
        "party_id": supplier.id,
        "party_type": "supplier",
        "lines": [{"reference_type": "purchase_invoice", "reference_id": invoice.id, "allocated_amount": 200}],
    }
    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )

    assert b"Pago registrado correctamente" in response.data
    reference = database.session.execute(database.select(PaymentReference)).scalars().first()
    assert reference.flow_source_type == "purchase_invoice"
    assert reference.reference_document_no == "PI-SNAPSHOT-001"
    assert reference.reference_date == invoice.posting_date
    assert reference.party_type == "supplier"
    assert reference.party_id == supplier.id
    assert reference.company == "cacao"
    assert reference.currency == "NIO"
    assert reference.outstanding_amount == 450
    assert reference.outstanding_amount_after == 250
    assert reference.exchange_rate == 1


def test_payment_requires_party_for_manual_pay_receive(app_ctx):
    """Pagos y cobros manuales requieren tercero explícito."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 100,
        "party_type": "customer",
        "party_id": "",
        "lines": [],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )

    assert b"Pago registrado correctamente" not in response.data
    assert "tercero".encode() in response.data.lower()


def test_payment_to_draft_document_blocked(app_ctx):
    """No se debe poder pagar un documento en borrador (docstatus=0)."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    _ensure_company_default_accounts("cacao", bank)

    draft_invoice = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=0,  # draft
        grand_total=300,
        outstanding_amount=300,
        base_outstanding_amount=300,
    )
    database.session.add(draft_invoice)
    database.session.commit()

    payment_payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 300,
        "party_id": supplier.id,
        "party_type": "supplier",
        "lines": [{"reference_type": "purchase_invoice", "reference_id": draft_invoice.id, "allocated_amount": 300}],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    # Should fail because document is in draft
    assert b"Pago registrado correctamente" not in response.data


def test_payment_to_cancelled_document_blocked(app_ctx):
    """No se debe poder pagar un documento cancelado (docstatus=2)."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    _ensure_company_default_accounts("cacao", bank)

    cancelled_invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=2,  # cancelled
        grand_total=200,
        outstanding_amount=200,
        base_outstanding_amount=200,
    )
    database.session.add(cancelled_invoice)
    database.session.commit()

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 200,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_invoice", "reference_id": cancelled_invoice.id, "allocated_amount": 200}],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" not in response.data


def test_payment_company_mismatch_blocked(app_ctx):
    """No se debe poder aplicar un pago a un documento de otra compañía."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    _ensure_company_default_accounts("cacao", bank)

    # Invoice belonging to a different company
    other_invoice = PurchaseInvoice(
        company="oth",  # different company
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=1,
        grand_total=400,
        outstanding_amount=400,
        base_outstanding_amount=400,
    )
    database.session.add(other_invoice)
    database.session.commit()

    payment_payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 400,
        "party_id": supplier.id,
        "party_type": "supplier",
        "lines": [{"reference_type": "purchase_invoice", "reference_id": other_invoice.id, "allocated_amount": 400}],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" not in response.data


def test_payment_party_mismatch_blocked(app_ctx):
    """No se debe poder aplicar un pago a un documento de otro tercero."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    parties = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().all()
    assert len(parties) >= 1
    supplier_a = parties[0]
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    _ensure_company_default_accounts("cacao", bank)

    # Create a second supplier if only one exists
    supplier_b_id = "other_supplier_id"
    supplier_b = database.session.get(Party, supplier_b_id)
    if not supplier_b:
        supplier_b = Party(id=supplier_b_id, code="OTHER_SUPPLIER", is_supplier=True, name="Otro Proveedor")
        database.session.add(supplier_b)
        database.session.commit()

    # Invoice belonging to supplier_b
    invoice_b = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier_b.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=1,
        grand_total=250,
        outstanding_amount=250,
        base_outstanding_amount=250,
    )
    database.session.add(invoice_b)
    database.session.commit()

    # Payment from supplier_a but referencing supplier_b's invoice
    payment_payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 250,
        "party_id": supplier_a.id,
        "party_type": "supplier",
        "lines": [{"reference_type": "purchase_invoice", "reference_id": invoice_b.id, "allocated_amount": 250}],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" not in response.data


def test_payment_detail_view_shows_references(app_ctx):
    """El detalle del pago muestra la tabla de referencias aplicadas."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    _ensure_company_default_accounts("cacao", bank)

    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=600,
        outstanding_amount=600,
        base_outstanding_amount=600,
    )
    database.session.add(invoice)
    database.session.commit()

    payment_payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 600,
        "party_id": customer.id,
        "party_type": "customer",
        "lines": [{"reference_type": "sales_invoice", "reference_id": invoice.id, "allocated_amount": 600}],
    }

    client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payment_payload)},
        follow_redirects=True,
    )

    pe = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()

    detail_response = client.get(f"/cash_management/payment/{pe.id}")
    assert detail_response.status_code == 200
    # The detail view should render references section
    assert b"Referencias del Pago" in detail_response.data or b"pago.html" in detail_response.data


def test_payment_new_form_uses_smart_select_header_flow(app_ctx):
    """El formulario nuevo usa smart-select para el encabezado operativo."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    response = client.get("/cash_management/payment/new")
    html = response.data.decode("utf-8")

    assert response.status_code == 200
    assert 'doctype: "company"' in html
    assert 'doctype: "bank_account"' in html
    assert 'doctype: "mode_of_payment"' in html
    assert 'doctype: "naming_series"' in html
    assert 'doctype: "party_type"' in html
    assert 'filters: { party_type: { selector: "#party_type_val" } }' in html
    assert "preload: true" in html
    assert 'x-show="isCheckPayment()"' in html
    assert "Número de cheque a emitir" in html
    assert 'x-model="header.external_number" readonly' in html
    assert 'x-model="header.exchange_rate"' not in html
    assert "Tipo de cambio" not in html


def test_mode_of_payment_static_search_select_options(app_ctx):
    """Forma de pago se expone como catálogo estático precargable."""
    payload = search_select("mode_of_payment", "", {}, limit=10)

    values = {item["value"] for item in payload["results"]}
    labels = {item["display_name"] for item in payload["results"]}
    assert {"transfer", "check", "cash"}.issubset(values)
    assert {"Transferencia", "Cheque", "Efectivo"}.issubset(labels)


def test_bank_account_search_select_exposes_payment_metadata(app_ctx):
    """La cuenta bancaria devuelve moneda y defaults de numeración para el formulario."""
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    payload = search_select("bank_account", "", {"company": ["cacao"], "is_active": ["True"]}, limit=10)
    row = next(item for item in payload["results"] if item["value"] == bank.id)

    assert row["currency"] == bank.currency
    assert row["default_naming_series_id"] == bank.default_naming_series_id
    assert row["default_external_counter_id"] == bank.default_external_counter_id
    assert row["default_external_number"]


def test_payment_ignores_exchange_rate_and_external_counter_for_transfer(app_ctx):
    """Transferencia no debe consumir chequera ni aceptar tasa editable del formulario."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    assert bank.default_external_counter_id

    payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 125,
        "party_id": customer.id,
        "party_type": "customer",
        "currency": "USD-IGNORED",
        "exchange_rate": "99.99",
        "mode_of_payment": "transfer",
        "external_counter_id": bank.default_external_counter_id,
        "external_number": "SHOULD-NOT-PERSIST",
        "lines": [],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )

    assert b"Pago registrado correctamente" in response.data
    payment = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    assert payment.currency == bank.currency
    assert payment.transaction_currency == bank.currency
    assert payment.exchange_rate == Decimal("1")
    assert payment.external_counter_id is None
    assert payment.external_number is None


def test_payment_uses_default_external_counter_for_check(app_ctx):
    """Cheque usa la chequera default de la cuenta bancaria cuando no se envía una explícita."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    counter = database.session.get(ExternalCounter, bank.default_external_counter_id)
    assert counter is not None

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 125,
        "party_id": supplier.id,
        "party_type": "supplier",
        "mode_of_payment": "check",
        "lines": [],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )

    assert b"Pago registrado correctamente" in response.data
    payment = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    assert payment.mode_of_payment == "check"
    assert payment.external_counter_id == counter.id
    assert payment.external_number


def test_payment_detail_view_matches_payment_header_changes(app_ctx):
    """El detalle muestra moneda, forma de pago y tipo de cambio gestionado por backend."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 75,
        "party_id": customer.id,
        "party_type": "customer",
        "mode_of_payment": "transfer",
        "lines": [],
    }
    client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    payment = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()

    response = client.get(f"/cash_management/payment/{payment.id}")
    html = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "Registro de Pago" in html
    assert "Forma de pago" in html
    assert "transfer" in html
    assert "Cuenta bancaria" in html
    assert "Gestionado por backend/libros activos" in html


def _open_payment(
    *,
    party: Party,
    payment_type: str,
    amount: Decimal,
    document_no: str,
) -> PaymentEntry:
    """Crea un pago aprobado sin referencias para pruebas de conciliacion masiva."""
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    party_type_value = "customer" if party.is_customer else "supplier"
    payment = PaymentEntry(
        company="cacao",
        posting_date=date.today(),
        payment_type=payment_type,
        party_type=party_type_value,
        party_id=party.id,
        party_name=party.name,
        bank_account_id=bank.id,
        currency=bank.currency or "NIO",
        paid_amount=amount if payment_type == "pay" else None,
        received_amount=amount if payment_type == "receive" else None,
        docstatus=1,
        document_no=document_no,
    )
    database.session.add(payment)
    database.session.flush()
    return payment


def test_mass_payment_reconciliation_applies_customer_payment_to_multiple_sales_invoices(app_ctx):
    """La conciliacion masiva aplica un cobro abierto contra varias facturas AR."""
    from cacao_accounting.document_flow.service import (
        apply_payment_reconciliation,
        compute_payment_unallocated_amount,
    )

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    payment = _open_payment(party=customer, payment_type="receive", amount=Decimal("500.00"), document_no="PAY-AR-001")
    invoices = [
        SalesInvoice(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            document_type="sales_invoice",
            docstatus=1,
            grand_total=amount,
            outstanding_amount=amount,
            base_outstanding_amount=amount,
            document_no=document_no,
        )
        for amount, document_no in ((Decimal("300.00"), "SI-MASS-001"), (Decimal("200.00"), "SI-MASS-002"))
    ]
    database.session.add_all(invoices)
    database.session.commit()

    reconciliation = apply_payment_reconciliation(
        company="cacao",
        party_type="customer",
        party_id=customer.id,
        allocation_date=date.today(),
        lines=[
            {
                "payment_id": payment.id,
                "reference_type": "sales_invoice",
                "reference_id": invoices[0].id,
                "allocated_amount": "300.00",
            },
            {
                "payment_id": payment.id,
                "reference_type": "sales_invoice",
                "reference_id": invoices[1].id,
                "allocated_amount": "200.00",
            },
        ],
    )
    database.session.commit()

    assert reconciliation.recon_type == "AR"
    assert compute_payment_unallocated_amount(payment) == Decimal("0")
    assert [invoice.outstanding_amount for invoice in invoices] == [Decimal("0.0000"), Decimal("0.0000")]
    assert database.session.execute(database.select(PaymentReference)).scalars().all()
    relations = (
        database.session.execute(database.select(DocumentRelation).filter_by(target_type="payment_entry")).scalars().all()
    )
    assert len(relations) == 2


def test_mass_payment_reconciliation_applies_supplier_payment_to_purchase_invoices(app_ctx):
    """La conciliacion masiva aplica un pago abierto contra facturas AP."""
    from cacao_accounting.document_flow.service import apply_payment_reconciliation, compute_payment_unallocated_amount

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    payment = _open_payment(party=supplier, payment_type="pay", amount=Decimal("600.00"), document_no="PAY-AP-001")
    invoices = [
        PurchaseInvoice(
            company="cacao",
            supplier_id=supplier.id,
            posting_date=date.today(),
            document_type="purchase_invoice",
            docstatus=1,
            grand_total=amount,
            outstanding_amount=amount,
            base_outstanding_amount=amount,
            document_no=document_no,
        )
        for amount, document_no in ((Decimal("250.00"), "PI-MASS-001"), (Decimal("350.00"), "PI-MASS-002"))
    ]
    database.session.add_all(invoices)
    database.session.commit()

    reconciliation = apply_payment_reconciliation(
        company="cacao",
        party_type="supplier",
        party_id=supplier.id,
        allocation_date=date.today(),
        lines=[
            {
                "payment_id": payment.id,
                "reference_type": "purchase_invoice",
                "reference_id": invoice.id,
                "allocated_amount": str(invoice.grand_total),
            }
            for invoice in invoices
        ],
    )
    database.session.commit()

    assert reconciliation.recon_type == "AP"
    assert compute_payment_unallocated_amount(payment) == Decimal("0")
    assert [invoice.outstanding_amount for invoice in invoices] == [Decimal("0.0000"), Decimal("0.0000")]


def test_mass_payment_reconciliation_rejects_overapplication_and_party_mismatch(app_ctx):
    """La aplicacion masiva bloquea saldos excedidos y documentos de otro tercero."""
    from cacao_accounting.document_flow.service import DocumentFlowError, apply_payment_reconciliation

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    other_customer = Party(
        id="customer_mass_mismatch", code="MASS_MISMATCH", is_customer=True, name="Cliente distinto conciliacion"
    )
    payment = _open_payment(party=customer, payment_type="receive", amount=Decimal("100.00"), document_no="PAY-ERR-001")
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=Decimal("150.00"),
        outstanding_amount=Decimal("150.00"),
        base_outstanding_amount=Decimal("150.00"),
    )
    other_invoice = SalesInvoice(
        company="cacao",
        customer_id=other_customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=Decimal("50.00"),
        outstanding_amount=Decimal("50.00"),
        base_outstanding_amount=Decimal("50.00"),
    )
    database.session.add_all([other_customer, invoice, other_invoice])
    database.session.commit()

    with pytest.raises(DocumentFlowError, match="excede el saldo disponible"):
        apply_payment_reconciliation(
            company="cacao",
            party_type="customer",
            party_id=customer.id,
            allocation_date=date.today(),
            lines=[
                {
                    "payment_id": payment.id,
                    "reference_type": "sales_invoice",
                    "reference_id": invoice.id,
                    "allocated_amount": "120.00",
                }
            ],
        )
    database.session.rollback()

    with pytest.raises(DocumentFlowError, match="no coincide con el tercero"):
        apply_payment_reconciliation(
            company="cacao",
            party_type="customer",
            party_id=customer.id,
            allocation_date=date.today(),
            lines=[
                {
                    "payment_id": payment.id,
                    "reference_type": "sales_invoice",
                    "reference_id": other_invoice.id,
                    "allocated_amount": "50.00",
                }
            ],
        )


def test_payment_reconciliation_screen_menu_and_candidates_endpoint_render(app_ctx):
    """La pantalla administrativa y su endpoint JSON quedan visibles en Caja y Bancos."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    payment = _open_payment(party=customer, payment_type="receive", amount=Decimal("80.00"), document_no="PAY-UI-001")
    invoice = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=Decimal("80.00"),
        outstanding_amount=Decimal("80.00"),
        base_outstanding_amount=Decimal("80.00"),
        document_no="SI-UI-001",
    )
    database.session.add(invoice)
    database.session.commit()

    menu_response = client.get("/cash_management/")
    screen_response = client.get("/cash_management/payment-reconciliation")
    api_response = client.get(
        "/api/document-flow/payment-reconciliation-candidates",
        query_string={"company": "cacao", "party_type": "customer", "party_id": customer.id},
    )

    assert menu_response.status_code == 200
    assert b"Conciliaci\xc3\xb3n Facturas/Pagos" in menu_response.data
    assert screen_response.status_code == 200
    assert b"payment-reconciliation-screen" in screen_response.data
    assert api_response.status_code == 200
    payload = api_response.get_json()
    assert any(row["payment_id"] == payment.id for row in payload["payments"])
    assert any(row["reference_id"] == invoice.id for row in payload["documents"])


def test_stock_reconciliation_screen_exposes_global_accounting_dimension_fields(app_ctx):
    """La conciliacion de inventario expone cuenta de diferencia y dimensiones globales."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    response = client.get("/inventory/stock-entry/reconciliation/new")
    warehouse_response = client.get("/inventory/warehouse/new")

    assert response.status_code == 200
    assert b"Cuenta de diferencia" in response.data
    assert b"Centro de costos" in response.data
    assert b"Unidad de negocio" in response.data
    assert b"Proyecto" in response.data
    assert warehouse_response.status_code == 200
    assert b"Cuenta de inventario" in warehouse_response.data


def test_payment_auto_populates_exchange_rate_same_currency(app_ctx):
    """Pago en misma moneda de la compania debe tener exchange_rate=1."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="NIO")).scalars().first()

    payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 500,
        "party_id": customer.id,
        "party_type": "customer",
        "mode_of_payment": "transfer",
        "lines": [],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in response.data
    payment = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    assert payment.exchange_rate == Decimal("1")
    assert payment.currency == "NIO"
    assert payment.base_paid_amount == Decimal("500.0000") or payment.base_received_amount == Decimal("500.0000")


def test_payment_auto_populates_exchange_rate_different_currency(app_ctx):
    """Pago en USD (moneda distinta a NIO de la compania) debe auto-poblar exchange_rate."""
    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="USD")).scalars().first()
    assert bank is not None, "Se necesita una cuenta bancaria en USD en los datos de prueba"

    payload = {
        "payment_type": "receive",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 100,
        "party_id": customer.id,
        "party_type": "customer",
        "mode_of_payment": "transfer",
        "lines": [],
    }

    response = client.post(
        "/cash_management/payment/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert b"Pago registrado correctamente" in response.data
    payment = database.session.execute(database.select(PaymentEntry).order_by(PaymentEntry.created.desc())).scalars().first()
    assert payment.exchange_rate is not None
    assert payment.exchange_rate != Decimal("0")
    assert payment.transaction_currency == "USD"
    assert payment.currency == "USD"


def test_payment_reference_loads_with_row_lock(app_ctx):
    """Verifica que _load_payment_reference_document usa FOR UPDATE (no debe romper flujo normal)."""
    from cacao_accounting.database import PurchaseInvoice

    client = app_ctx.test_client()
    login(client, "cacao", "cacao")

    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    invoice = (
        database.session.execute(
            database.select(PurchaseInvoice)
            .filter_by(company="cacao", docstatus=1)
            .filter(PurchaseInvoice.supplier_id.isnot(None))
        )
        .scalars()
        .first()
    )
    if not invoice:
        invoice = PurchaseInvoice(
            id="PI-LOCK-TEST",
            company="cacao",
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            posting_date=date.today(),
            grand_total=Decimal("1000"),
            outstanding_amount=Decimal("1000"),
            docstatus=1,
        )
        database.session.add(invoice)
        database.session.flush()
        database.session.commit()

    payload = {
        "payment_type": "pay",
        "company": "cacao",
        "bank_account_id": bank.id,
        "posting_date": date.today().isoformat(),
        "paid_amount": 100,
        "party_id": supplier.id,
        "party_type": "supplier",
        "mode_of_payment": "transfer",
        "lines": [
            {
                "reference_type": "purchase_invoice",
                "reference_id": invoice.id,
                "reference_doctype": "purchase_invoice",
                "allocated_amount": 100,
                "discount_amount": 0,
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

    ref = (
        database.session.execute(database.select(PaymentReference).order_by(PaymentReference.created.desc())).scalars().first()
    )
    assert ref is not None
    assert ref.allocated_amount == Decimal("100")

    database.session.refresh(invoice)
    assert invoice.outstanding_amount == Decimal("900")
