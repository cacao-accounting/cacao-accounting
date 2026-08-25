# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests exhaustivos para document_flow/payment.py.

Cobertura de funciones no testeadas:
- _create_payment_target y cluster de funciones auxiliares
- assign_payment_identifier
- _validate_payment_currency_match (rama de mismatch)
- _check_duplicate_application (rama de duplicado)
- _payment_order_allocated (ordenes como fuente)
- Funciones helper puras: _payment_candidate_physical_type, _payment_candidate_date,
  _payment_candidate_party, _cash_consumed, _payment_type_matches_source, etc.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import (
    database,
    Party,
    BankAccount,
    SalesInvoice,
    SalesInvoiceItem,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PaymentEntry,
    PaymentReference,
    DocumentRelation,
    CompanyDefaultAccount,
    SalesOrder,
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
        yield app


def login(client, username, password):
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def test_duplicate_payment_warning_covers_receipts(app_ctx):
    """Un cobro repetido debe generar la advertencia preventiva de duplicidad."""
    from flask import get_flashed_messages

    from cacao_accounting.bancos import _warn_duplicate_payment

    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    existing = PaymentEntry(
        company="cacao",
        party_id=customer.id,
        party_type="customer",
        payment_type="receive",
        received_amount=Decimal("500"),
        currency="NIO",
        posting_date=date(2026, 8, 17),
        docstatus=1,
    )
    candidate = PaymentEntry(
        id="PAY-DUP-RECEIVE",
        company="cacao",
        party_id=customer.id,
        party_type="customer",
        payment_type="receive",
        received_amount=Decimal("500"),
        currency="NIO",
        posting_date=date(2026, 8, 18),
        docstatus=0,
    )
    database.session.add_all([existing, candidate])
    database.session.flush()

    with app_ctx.test_request_context():
        _warn_duplicate_payment(candidate)
        messages = get_flashed_messages(with_categories=True)

    assert any(category == "warning" for category, _message in messages)


def test_invoice_outstanding_ignores_base_currency_cache(monkeypatch):
    """El saldo aplicable no debe mezclar moneda transaccional y moneda base."""
    bancos_module = import_module("cacao_accounting.bancos.services")

    invoice = SimpleNamespace(outstanding_amount=Decimal("100"), base_outstanding_amount=Decimal("1"))
    monkeypatch.setattr(bancos_module, "compute_outstanding_amount", lambda _invoice: Decimal("100"))
    monkeypatch.setattr(bancos_module, "refresh_outstanding_amount_cache", lambda _invoice: Decimal("100"))

    assert bancos_module._invoice_outstanding(invoice) == Decimal("100")


def _first_account_id(company: str, account_type: str) -> str | None:
    from cacao_accounting.database import Accounts

    account = (
        database.session.execute(
            database.select(Accounts).filter_by(entity=company, account_type=account_type).order_by(Accounts.code.asc())
        )
        .scalars()
        .first()
    )
    return account.id if account else None


def _ensure_company_default_accounts(company: str, bank: BankAccount) -> CompanyDefaultAccount:
    if not bank.gl_account_id:
        bank.gl_account_id = _first_account_id(company, "bank")
        database.session.flush()
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
    defaults.sales_discount_account_id = defaults.sales_discount_account_id or _first_account_id(company, "expense")
    defaults.purchase_discount_account_id = defaults.purchase_discount_account_id or _first_account_id(company, "income")
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


def _make_customer_invoice(*, grand_total: Decimal = Decimal("1000")) -> SalesInvoice:
    customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
    si = SalesInvoice(
        company="cacao",
        customer_id=customer.id,
        posting_date=date.today(),
        document_type="sales_invoice",
        docstatus=1,
        grand_total=grand_total,
        outstanding_amount=grand_total,
        base_outstanding_amount=grand_total,
    )
    database.session.add(si)
    database.session.flush()
    sii = SalesInvoiceItem(sales_invoice_id=si.id, item_code="ART-001", qty=1, rate=grand_total, amount=grand_total)
    database.session.add(sii)
    database.session.commit()
    return si


def _make_supplier_invoice(*, grand_total: Decimal = Decimal("1000")) -> PurchaseInvoice:
    supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
    pi = PurchaseInvoice(
        company="cacao",
        supplier_id=supplier.id,
        posting_date=date.today(),
        document_type="purchase_invoice",
        docstatus=1,
        grand_total=grand_total,
        outstanding_amount=grand_total,
        base_outstanding_amount=grand_total,
    )
    database.session.add(pi)
    database.session.flush()
    pii = PurchaseInvoiceItem(purchase_invoice_id=pi.id, item_code="ART-001", qty=1, rate=grand_total, amount=grand_total)
    database.session.add(pii)
    database.session.commit()
    return pi


def _make_open_payment(
    *,
    party: Party,
    payment_type: str,
    amount: Decimal,
    document_no: str = "PAY-TEST-001",
    currency: str = "NIO",
) -> PaymentEntry:
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
        currency=currency,
        paid_amount=amount if payment_type == "pay" else None,
        received_amount=amount if payment_type == "receive" else None,
        docstatus=1,
        document_no=document_no,
    )
    database.session.add(payment)
    database.session.flush()
    return payment


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestPaymentCandidateHelpers:
    """Unit tests for pure helper functions in payment.py."""

    def test_payment_candidate_physical_type_purchase_credit_note(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_physical_type

        assert _payment_candidate_physical_type("purchase_credit_note") == "purchase_invoice"

    def test_payment_candidate_physical_type_purchase_debit_note(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_physical_type

        assert _payment_candidate_physical_type("purchase_debit_note") == "purchase_invoice"

    def test_payment_candidate_physical_type_sales_credit_note(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_physical_type

        assert _payment_candidate_physical_type("sales_credit_note") == "sales_invoice"

    def test_payment_candidate_physical_type_sales_debit_note(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_physical_type

        assert _payment_candidate_physical_type("sales_debit_note") == "sales_invoice"

    def test_payment_candidate_physical_type_passthrough(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_physical_type

        assert _payment_candidate_physical_type("sales_invoice") == "sales_invoice"
        assert _payment_candidate_physical_type("purchase_invoice") == "purchase_invoice"

    def test_payment_candidate_date_prefers_posting_date(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_date

        class FakeDoc:
            posting_date = date(2026, 1, 15)
            bill_date = date(2026, 2, 1)

        assert _payment_candidate_date(FakeDoc()) == date(2026, 1, 15)

    def test_payment_candidate_date_falls_back_to_bill_date(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_date

        class FakeDoc:
            posting_date = None
            bill_date = date(2026, 3, 10)

        assert _payment_candidate_date(FakeDoc()) == date(2026, 3, 10)

    def test_payment_candidate_date_returns_none_when_no_dates(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_date

        class FakeDoc:
            posting_date = None
            bill_date = None
            transaction_date = None
            due_date = None

        assert _payment_candidate_date(FakeDoc()) is None

    def test_payment_candidate_party_purchase(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_party

        class FakeDoc:
            supplier_id = "SUP-001"

        party_type, party_id = _payment_candidate_party(FakeDoc(), "purchase_invoice")
        assert party_type == "supplier"
        assert party_id == "SUP-001"

    def test_payment_candidate_party_sales(self):
        from cacao_accounting.document_flow.payment import _payment_candidate_party

        class FakeDoc:
            customer_id = "CUST-001"

        party_type, party_id = _payment_candidate_party(FakeDoc(), "sales_invoice")
        assert party_type == "customer"
        assert party_id == "CUST-001"

    def test_payment_type_matches_source_valid(self):
        from cacao_accounting.document_flow.payment import _payment_type_matches_source

        assert _payment_type_matches_source("pay", "purchase_invoice") is True
        assert _payment_type_matches_source("receive", "sales_invoice") is True
        assert _payment_type_matches_source("receive", "purchase_credit_note") is True
        assert _payment_type_matches_source("pay", "sales_credit_note") is True

    def test_payment_type_matches_source_invalid(self):
        from cacao_accounting.document_flow.payment import _payment_type_matches_source

        assert _payment_type_matches_source("receive", "purchase_invoice") is False
        assert _payment_type_matches_source("pay", "sales_invoice") is False

    def test_payment_type_matches_source_unknown_type_returns_true(self):
        from cacao_accounting.document_flow.payment import _payment_type_matches_source

        assert _payment_type_matches_source("pay", "unknown_type") is True


class TestCashConsumed:
    """Direct unit tests for _cash_consumed."""

    def test_basic_consumed(self):
        from cacao_accounting.document_flow.payment import _cash_consumed

        assert _cash_consumed(Decimal("100"), Decimal("0"), Decimal("0")) == Decimal("100")

    def test_with_discount(self):
        from cacao_accounting.document_flow.payment import _cash_consumed

        assert _cash_consumed(Decimal("100"), Decimal("30"), Decimal("0")) == Decimal("70")

    def test_with_gain_loss(self):
        from cacao_accounting.document_flow.payment import _cash_consumed

        assert _cash_consumed(Decimal("100"), Decimal("0"), Decimal("20")) == Decimal("80")

    def test_discount_plus_gain_loss_exceeds_allocated(self):
        from cacao_accounting.document_flow.payment import _cash_consumed

        assert _cash_consumed(Decimal("100"), Decimal("80"), Decimal("30")) == Decimal("0")

    def test_zero_allocated(self):
        from cacao_accounting.document_flow.payment import _cash_consumed

        assert _cash_consumed(Decimal("0"), Decimal("0"), Decimal("0")) == Decimal("0")


def test_payment_reference_totals_reject_a_one_cent_overallocation():
    """Payment references cannot accumulate a tolerated cent above cash paid."""
    from cacao_accounting.bancos.services import _validate_payment_reference_totals

    with pytest.raises(ValueError, match="monto aplicado"):
        _validate_payment_reference_totals(
            Decimal("100.00"),
            {"allocated": Decimal("100.01"), "discount": Decimal("0"), "gain_loss": Decimal("0")},
        )


class TestToJsonNumber:
    """Unit tests for _to_json_number."""

    def test_decimal_value(self):
        from cacao_accounting.document_flow.payment import _to_json_number

        assert _to_json_number(Decimal("123.45")) == "123.45"

    def test_none_returns_zero(self):
        from cacao_accounting.document_flow.payment import _to_json_number

        assert _to_json_number(None) == "0"

    def test_zero(self):
        from cacao_accounting.document_flow.payment import _to_json_number

        assert _to_json_number(Decimal("0")) == "0"


class TestDocumentExchangeRate:
    """Unit tests for _document_exchange_rate."""

    def test_with_exchange_rate(self):
        from cacao_accounting.document_flow.payment import _document_exchange_rate

        class FakeDoc:
            exchange_rate = Decimal("35.5")

        assert _document_exchange_rate(FakeDoc()) == Decimal("35.5")

    def test_without_exchange_rate(self):
        from cacao_accounting.document_flow.payment import _document_exchange_rate

        class FakeDoc:
            exchange_rate = None

        assert _document_exchange_rate(FakeDoc()) == Decimal("1")


class TestBaseAmount:
    """Unit tests for _base_amount."""

    def test_conversion(self):
        from cacao_accounting.document_flow.payment import _base_amount

        class FakeDoc:
            exchange_rate = Decimal("35")

        assert _base_amount(Decimal("100"), FakeDoc()) == Decimal("3500")

    def test_no_exchange_rate(self):
        from cacao_accounting.document_flow.payment import _base_amount

        class FakeDoc:
            exchange_rate = None

        assert _base_amount(Decimal("100"), FakeDoc()) == Decimal("100")


# ---------------------------------------------------------------------------
# _payment_reference_model
# ---------------------------------------------------------------------------


class TestPaymentReferenceModel:
    """Unit tests for _payment_reference_model."""

    def test_purchase_types_return_purchase_invoice(self):
        from cacao_accounting.document_flow.payment import _payment_reference_model
        from cacao_accounting.database import PurchaseInvoice

        assert _payment_reference_model("purchase_invoice") is PurchaseInvoice
        assert _payment_reference_model("purchase_credit_note") is PurchaseInvoice
        assert _payment_reference_model("purchase_debit_note") is PurchaseInvoice

    def test_sales_types_return_sales_invoice(self):
        from cacao_accounting.document_flow.payment import _payment_reference_model
        from cacao_accounting.database import SalesInvoice

        assert _payment_reference_model("sales_invoice") is SalesInvoice
        assert _payment_reference_model("sales_credit_note") is SalesInvoice
        assert _payment_reference_model("sales_debit_note") is SalesInvoice

    def test_unknown_type_raises(self):
        from cacao_accounting.document_flow.payment import _payment_reference_model

        with pytest.raises(ValueError, match="Tipo de referencia invalido"):
            _payment_reference_model("unknown_type")


# ---------------------------------------------------------------------------
# _candidate_source_types
# ---------------------------------------------------------------------------


class TestCandidateSourceTypes:
    """Unit tests for _candidate_source_types."""

    def test_supplier(self):
        from cacao_accounting.document_flow.payment import _candidate_source_types

        result = _candidate_source_types("supplier")
        assert "purchase_invoice" in result
        assert "purchase_debit_note" in result
        assert "purchase_credit_note" in result

    def test_customer(self):
        from cacao_accounting.document_flow.payment import _candidate_source_types

        result = _candidate_source_types("customer")
        assert "sales_invoice" in result
        assert "sales_debit_note" in result
        assert "sales_credit_note" in result


# ---------------------------------------------------------------------------
# _should_include_orders
# ---------------------------------------------------------------------------


class TestShouldIncludeOrders:
    """Unit tests for _should_include_orders."""

    def test_order_type_with_flag_true(self):
        from cacao_accounting.document_flow.payment import _should_include_orders

        assert _should_include_orders("purchase_order", True) is True
        assert _should_include_orders("sales_order", True) is True

    def test_order_type_with_flag_false(self):
        from cacao_accounting.document_flow.payment import _should_include_orders

        assert _should_include_orders("purchase_order", False) is False
        assert _should_include_orders("sales_order", False) is False

    def test_non_order_type_always_included(self):
        from cacao_accounting.document_flow.payment import _should_include_orders

        assert _should_include_orders("sales_invoice", False) is True
        assert _should_include_orders("purchase_invoice", True) is True


# ---------------------------------------------------------------------------
# _filter_candidates_by_currency
# ---------------------------------------------------------------------------


class TestFilterCandidatesByCurrency:
    """Unit tests for _filter_candidates_by_currency."""

    def test_no_filter(self):
        from cacao_accounting.document_flow.payment import _filter_candidates_by_currency

        docs = [{"currency": "USD"}, {"currency": "NIO"}]
        assert _filter_candidates_by_currency(docs, None) == docs

    def test_filter_by_usd(self):
        from cacao_accounting.document_flow.payment import _filter_candidates_by_currency

        docs = [{"currency": "USD"}, {"currency": "NIO"}, {"currency": ""}]
        result = _filter_candidates_by_currency(docs, "USD")
        assert len(result) == 2
        assert all(d["currency"] in {"USD", ""} for d in result)


# ---------------------------------------------------------------------------
# Integration tests: payment_reference_candidates
# ---------------------------------------------------------------------------


class TestPaymentReferenceCandidates:
    """Tests for payment_reference_candidates public function."""

    def test_requires_company_party_type_party_id(self):
        from cacao_accounting.document_flow.payment import payment_reference_candidates

        with pytest.raises(ValueError, match="compania"):
            payment_reference_candidates(company="", party_type="customer", party_id="X", source_types=["sales_invoice"])

    def test_supplier_does_not_return_sales_docs(self, app_ctx):
        from cacao_accounting.document_flow.payment import payment_reference_candidates

        supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
        si = _make_customer_invoice()
        results = payment_reference_candidates(
            company="cacao",
            party_type="supplier",
            party_id=supplier.id,
            source_types=["sales_invoice", "purchase_invoice"],
        )
        assert all(r["document_id"] != si.id for r in results)

    def test_order_candidates_when_flag_enabled(self, app_ctx):
        from cacao_accounting.document_flow.payment import payment_reference_candidates

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        so = SalesOrder(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            docstatus=1,
            grand_total=500,
        )
        database.session.add(so)
        database.session.commit()

        results = payment_reference_candidates(
            company="cacao",
            party_type="customer",
            party_id=customer.id,
            source_types=["sales_order"],
            include_orders=True,
        )
        assert any(r["document_id"] == so.id for r in results)

    def test_order_candidates_excluded_by_default(self, app_ctx):
        from cacao_accounting.document_flow.payment import payment_reference_candidates

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        so = SalesOrder(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            docstatus=1,
            grand_total=500,
        )
        database.session.add(so)
        database.session.commit()

        results = payment_reference_candidates(
            company="cacao",
            party_type="customer",
            party_id=customer.id,
            source_types=["sales_order"],
        )
        assert all(r["document_id"] != so.id for r in results)


# ---------------------------------------------------------------------------
# _payment_order_allocated
# ---------------------------------------------------------------------------


class TestPaymentOrderAllocated:
    """Tests for _payment_order_allocated (order source types)."""

    def test_order_with_no_allocations(self, app_ctx):
        from cacao_accounting.document_flow.payment import _payment_order_allocated

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        so = SalesOrder(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            docstatus=1,
            grand_total=500,
        )
        database.session.add(so)
        database.session.commit()

        result = _payment_order_allocated("sales_order", so.id)
        assert result == Decimal("0")

    def test_order_with_existing_allocation(self, app_ctx):
        from cacao_accounting.document_flow.payment import _payment_order_allocated

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        so = SalesOrder(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            docstatus=1,
            grand_total=500,
        )
        database.session.add(so)
        database.session.flush()

        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="receive",
            party_type="customer",
            party_id=customer.id,
            party_name=customer.name,
            bank_account_id=bank.id,
            currency="NIO",
            received_amount=200,
            docstatus=1,
        )
        database.session.add(payment)
        database.session.flush()

        ref = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_order",
            reference_id=so.id,
            allocated_amount=200,
            allocation_date=date.today(),
        )
        database.session.add(ref)
        database.session.flush()

        rel = DocumentRelation(
            source_type="sales_order",
            source_id=so.id,
            target_type="payment_entry",
            target_id=payment.id,
            target_item_id=ref.id,
            qty=Decimal("1"),
            amount=200,
            relation_type="payment_reference",
            status="active",
        )
        database.session.add(rel)
        database.session.commit()

        result = _payment_order_allocated("sales_order", so.id)
        assert result == Decimal("200")
        assert _payment_order_allocated("sales_order", so.id, company="other") == Decimal("0")


# ---------------------------------------------------------------------------
# Currency mismatch validation
# ---------------------------------------------------------------------------


class TestValidatePaymentCurrencyMatch:
    """Tests for _validate_payment_currency_match."""

    def test_same_currency_passes(self):
        from cacao_accounting.document_flow.payment import _validate_payment_currency_match

        class FakePayment:
            currency = "NIO"

        class FakeDoc:
            currency = "NIO"

        _validate_payment_currency_match(FakePayment(), FakeDoc())

    def test_different_currency_raises(self):
        from cacao_accounting.document_flow.payment import _validate_payment_currency_match

        class FakePayment:
            currency = "USD"

        class FakeDoc:
            currency = "NIO"

        with pytest.raises(ValueError, match="moneda del pago"):
            _validate_payment_currency_match(FakePayment(), FakeDoc())

    def test_no_payment_currency_passes(self):
        from cacao_accounting.document_flow.payment import _validate_payment_currency_match

        class FakePayment:
            currency = None

        class FakeDoc:
            currency = "NIO"

        _validate_payment_currency_match(FakePayment(), FakeDoc())


# ---------------------------------------------------------------------------
# Duplicate application validation
# ---------------------------------------------------------------------------


class TestCheckDuplicateApplication:
    """Tests for _check_duplicate_application."""

    def test_no_duplicate_passes(self, app_ctx):
        from cacao_accounting.document_flow.payment import _check_duplicate_application

        si = _make_customer_invoice()
        _check_duplicate_application("fake-payment-id", "sales_invoice", si.id)

    def test_duplicate_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _check_duplicate_application

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        si = _make_customer_invoice()

        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="receive",
            party_type="customer",
            party_id=customer.id,
            party_name=customer.name,
            bank_account_id=bank.id,
            currency="NIO",
            received_amount=1000,
            docstatus=1,
        )
        database.session.add(payment)
        database.session.flush()

        ref = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=si.id,
            allocated_amount=500,
            allocation_date=date.today(),
        )
        database.session.add(ref)
        database.session.flush()

        rel = DocumentRelation(
            source_type="sales_invoice",
            source_id=si.id,
            target_type="payment_entry",
            target_id=payment.id,
            target_item_id=ref.id,
            qty=Decimal("1"),
            amount=500,
            relation_type="payment_reference",
            status="active",
        )
        database.session.add(rel)
        database.session.commit()

        with pytest.raises(ValueError, match="ya esta aplicado"):
            _check_duplicate_application(payment.id, "sales_invoice", si.id)


# ---------------------------------------------------------------------------
# _validate_and_get_outstanding
# ---------------------------------------------------------------------------


class TestValidateAndGetOutstanding:
    """Tests for _validate_and_get_outstanding."""

    def test_no_outstanding_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_and_get_outstanding

        si = _make_customer_invoice(grand_total=Decimal("100"))
        si.grand_total = Decimal("0")
        database.session.commit()

        with pytest.raises(ValueError, match="saldo pendiente"):
            _validate_and_get_outstanding(si, Decimal("100"), date.today())

    def test_allocation_exceeds_outstanding_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_and_get_outstanding

        si = _make_customer_invoice(grand_total=Decimal("100"))

        with pytest.raises(ValueError, match="excede el saldo"):
            _validate_and_get_outstanding(si, Decimal("200"), date.today())


# ---------------------------------------------------------------------------
# _validate_payment
# ---------------------------------------------------------------------------


class TestValidatePayment:
    """Tests for _validate_payment."""

    def test_missing_payment_raises(self):
        from cacao_accounting.document_flow.payment import _validate_payment

        with pytest.raises(ValueError, match="existir y estar aprobado"):
            _validate_payment(None, "cacao", "customer", "X", "sales_invoice")

    def test_wrong_company_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_payment

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        payment = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("100"))

        with pytest.raises(ValueError, match="compania o tercero"):
            _validate_payment(payment, "other_company", "customer", customer.id, "sales_invoice")

    def test_wrong_payment_type_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_payment

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        payment = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("100"))

        with pytest.raises(ValueError, match="tipo de pago no corresponde"):
            _validate_payment(payment, "cacao", "customer", customer.id, "purchase_invoice")


# ---------------------------------------------------------------------------
# _validate_advance_allocation
# ---------------------------------------------------------------------------


class TestValidateAdvanceAllocation:
    """Tests for _validate_advance_allocation."""

    def test_reverted_advance_references_do_not_consume_payment_balance(self, app_ctx):
        """Only active relations count when calculating an advance remainder."""
        from cacao_accounting.database import DocumentRelation, PaymentReference
        from cacao_accounting.document_flow.payment import _advance_allocated_amount

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        payment = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("500"))
        active = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id="ACTIVE",
            allocated_amount=Decimal("100"),
        )
        reverted = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id="REVERTED",
            allocated_amount=Decimal("200"),
        )
        database.session.add_all([active, reverted])
        database.session.flush()
        database.session.add_all(
            [
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id="ACTIVE",
                    target_type="payment_entry",
                    target_id=payment.id,
                    target_item_id=active.id,
                    qty=Decimal("1"),
                    relation_type="payment_reference",
                    status="active",
                ),
                DocumentRelation(
                    source_type="sales_invoice",
                    source_id="REVERTED",
                    target_type="payment_entry",
                    target_id=payment.id,
                    target_item_id=reverted.id,
                    qty=Decimal("1"),
                    relation_type="payment_reference",
                    status="reverted",
                ),
            ]
        )
        database.session.flush()

        assert _advance_allocated_amount(payment.id) == Decimal("100")

    def test_company_mismatch_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_advance_allocation

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        payment = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("500"))

        class FakeInvoice:
            company = "other_company"

        with pytest.raises(ValueError, match="companias distintas"):
            _validate_advance_allocation(payment, FakeInvoice(), customer.id, Decimal("100"), date.today())

    def test_party_mismatch_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_advance_allocation

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        payment = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("500"))
        payment.party_id = "OTHER-PARTY"

        class FakeInvoice:
            company = "cacao"

        with pytest.raises(ValueError, match="otro tercero"):
            _validate_advance_allocation(payment, FakeInvoice(), customer.id, Decimal("100"), date.today())

    def test_amount_zero_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_advance_allocation

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        payment = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("500"))

        class FakeInvoice:
            company = "cacao"

        with pytest.raises(ValueError, match="mayor que cero"):
            _validate_advance_allocation(payment, FakeInvoice(), customer.id, Decimal("0"), date.today())

    def test_amount_exceeds_payment_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _validate_advance_allocation

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        payment = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("100"))

        class FakeInvoice:
            company = "cacao"

        with pytest.raises(ValueError, match="remanente del anticipo"):
            _validate_advance_allocation(payment, FakeInvoice(), customer.id, Decimal("200"), date.today())


# ---------------------------------------------------------------------------
# _validate_payment_target_allocation
# ---------------------------------------------------------------------------


class TestValidatePaymentTargetAllocation:
    """Tests for _validate_payment_target_allocation."""

    def test_zero_raises(self):
        from cacao_accounting.document_flow.payment import _validate_payment_target_allocation

        with pytest.raises(ValueError, match="mayor que cero"):
            _validate_payment_target_allocation(Decimal("0"), Decimal("100"))

    def test_exceeds_outstanding_raises(self):
        from cacao_accounting.document_flow.payment import _validate_payment_target_allocation

        with pytest.raises(ValueError, match="excede el saldo"):
            _validate_payment_target_allocation(Decimal("200"), Decimal("100"))

    def test_valid_passes(self):
        from cacao_accounting.document_flow.payment import _validate_payment_target_allocation

        _validate_payment_target_allocation(Decimal("50"), Decimal("100"))


# ---------------------------------------------------------------------------
# _update_document_outstanding
# ---------------------------------------------------------------------------


class TestUpdateDocumentOutstanding:
    """Tests for _update_document_outstanding."""

    def test_updates_attributes(self):
        from cacao_accounting.document_flow.payment import _update_document_outstanding

        class FakeDoc:
            outstanding_amount = Decimal("1000")
            base_outstanding_amount = Decimal("1000")
            exchange_rate = None

        doc = FakeDoc()
        _update_document_outstanding(doc, Decimal("1000"), Decimal("400"))
        assert doc.outstanding_amount == Decimal("600")
        assert doc.base_outstanding_amount == Decimal("600")

    def test_with_exchange_rate(self):
        from cacao_accounting.document_flow.payment import _update_document_outstanding

        class FakeDoc:
            outstanding_amount = Decimal("1000")
            base_outstanding_amount = Decimal("35000")
            exchange_rate = Decimal("35")

        doc = FakeDoc()
        _update_document_outstanding(doc, Decimal("1000"), Decimal("300"))
        assert doc.outstanding_amount == Decimal("700")
        assert doc.base_outstanding_amount == Decimal("24500")


# ---------------------------------------------------------------------------
# _load_advance_invoice
# ---------------------------------------------------------------------------


class TestLoadAdvanceInvoice:
    """Tests for _load_advance_invoice."""

    def test_nonexistent_raises(self, app_ctx):
        from cacao_accounting.document_flow.payment import _load_advance_invoice

        with pytest.raises(ValueError, match="no existe"):
            _load_advance_invoice("NONEXISTENT-ID")

    def test_sales_invoice_found(self, app_ctx):
        from cacao_accounting.document_flow.payment import _load_advance_invoice

        si = _make_customer_invoice()
        invoice, ref_type, party_id = _load_advance_invoice(si.id)
        assert ref_type == "sales_invoice"
        assert invoice.id == si.id

    def test_purchase_invoice_found(self, app_ctx):
        from cacao_accounting.document_flow.payment import _load_advance_invoice

        pi = _make_supplier_invoice()
        invoice, ref_type, party_id = _load_advance_invoice(pi.id)
        assert ref_type == "purchase_invoice"
        assert invoice.id == pi.id


# ---------------------------------------------------------------------------
# Payment target creation (via create_target_document)
# ---------------------------------------------------------------------------


class TestCreatePaymentTarget:
    """Tests for _create_payment_target (dispatched via create_target_document)."""

    def test_internal_transfer_target_resolves_both_bank_gl_accounts(self, app_ctx):
        """El target documental conserva la cuenta GL de cada pata bancaria."""
        from cacao_accounting.document_flow.payment import _build_payment_target_payment

        bank_accounts = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().all()
        eligible = [account for account in bank_accounts if account.gl_account_id]
        if len(eligible) < 2:
            pytest.skip("La fixture requiere dos cuentas bancarias con cuenta GL configurada.")

        source, target = eligible[:2]
        payment = _build_payment_target_payment(
            "cacao",
            {
                "payment_type": "internal_transfer",
                "bank_account_id": source.id,
                "target_bank_account_id": target.id,
                "posting_date": date.today(),
            },
        )

        assert payment.paid_from_account_id == source.gl_account_id
        assert payment.paid_to_account_id == target.gl_account_id

    def test_create_payment_from_sales_invoice(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("500"))

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": date.today(),
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer.id,
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": si.id,
                        "qty": 500,
                    }
                ],
            }
        )
        assert result["target_type"] == "payment_entry"
        assert result["document_no"] is not None

        payment = database.session.get(PaymentEntry, result["target_id"])
        assert payment is not None
        assert payment.received_amount == Decimal("500")
        assert payment.docstatus == 0

    def test_create_payment_rejects_cross_currency_invoice(self, app_ctx):
        """El target payment no descuenta nominales de monedas distintas."""
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("1000"))
        si.transaction_currency = "EUR"
        database.session.commit()

        with pytest.raises(ValueError, match="moneda"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "cacao",
                    "posting_date": date.today(),
                    "payment_type": "receive",
                    "party_type": "customer",
                    "party_id": customer.id,
                    "currency": "USD",
                    "lines": [{"source_document_type": "sales_invoice", "source_document_id": si.id, "qty": 1000}],
                }
            )

    def test_create_payment_rejects_unapproved_invoice(self, app_ctx):
        """Un target payment no debe aplicar saldo de una factura en borrador."""
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("1000"))
        si.docstatus = 0
        database.session.commit()

        with pytest.raises(ValueError, match="aprobada"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "cacao",
                    "posting_date": date.today(),
                    "payment_type": "receive",
                    "party_type": "customer",
                    "party_id": customer.id,
                    "lines": [{"source_document_type": "sales_invoice", "source_document_id": si.id, "qty": 1000}],
                }
            )

    def test_create_payment_rejects_invoice_from_another_party(self, app_ctx):
        """Un target payment no debe aplicar facturas de otro cliente."""
        from cacao_accounting.document_flow.service import create_target_document

        customers = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().all()
        if len(customers) < 2:
            pytest.skip("La base de pruebas requiere dos clientes")
        si = _make_customer_invoice(grand_total=Decimal("1000"))

        with pytest.raises(ValueError, match="tercero"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "cacao",
                    "posting_date": date.today(),
                    "payment_type": "receive",
                    "party_type": "customer",
                    "party_id": customers[1].id if customers[0].id == si.customer_id else customers[0].id,
                    "lines": [{"source_document_type": "sales_invoice", "source_document_id": si.id, "qty": 1000}],
                }
            )

    def test_create_payment_infers_currency_from_first_invoice(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("1000"))
        si.transaction_currency = "EUR"
        database.session.commit()

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": date.today(),
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer.id,
                "lines": [{"source_document_type": "sales_invoice", "source_document_id": si.id, "qty": 1000}],
            }
        )
        payment = database.session.get(PaymentEntry, result["target_id"])
        assert payment.currency == "EUR"
        assert payment.transaction_currency == "EUR"

    @pytest.mark.parametrize(
        ("payment_type", "factory", "amount_field", "base_amount_field"),
        [
            ("receive", _make_customer_invoice, "received_amount", "base_received_amount"),
            ("pay", _make_supplier_invoice, "paid_amount", "base_paid_amount"),
        ],
    )
    def test_create_payment_persists_foreign_currency_base_amounts(
        self, app_ctx, payment_type, factory, amount_field, base_amount_field
    ):
        """Los pagos destino conservan moneda transaccional y total base convertido."""
        from cacao_accounting.document_flow.service import create_target_document

        invoice = factory(grand_total=Decimal("100"))
        invoice.transaction_currency = "USD"
        database.session.commit()

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": date.today(),
                "payment_type": payment_type,
                "party_type": "customer" if payment_type == "receive" else "supplier",
                "party_id": invoice.customer_id if payment_type == "receive" else invoice.supplier_id,
                "currency": "USD",
                "base_currency": "NIO",
                "exchange_rate": "36",
                "lines": [{"source_document_type": invoice.document_type, "source_document_id": invoice.id, "qty": 100}],
            }
        )

        payment = database.session.get(PaymentEntry, result["target_id"])
        assert payment.transaction_currency == "USD"
        assert getattr(payment, amount_field) == Decimal("100")
        assert getattr(payment, base_amount_field) == Decimal("3600")

    def test_create_payment_from_purchase_invoice(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
        pi = _make_supplier_invoice(grand_total=Decimal("300"))

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": date.today(),
                "payment_type": "pay",
                "party_type": "supplier",
                "party_id": supplier.id,
                "lines": [
                    {
                        "source_document_type": "purchase_invoice",
                        "source_document_id": pi.id,
                        "qty": 300,
                    }
                ],
            }
        )
        assert result["target_type"] == "payment_entry"
        payment = database.session.get(PaymentEntry, result["target_id"])
        assert payment.paid_amount == Decimal("300")

    def test_create_payment_duplicate_invoice_rejected(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("500"))

        with pytest.raises(ValueError, match="repetir la misma factura"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "cacao",
                    "posting_date": date.today(),
                    "payment_type": "receive",
                    "party_type": "customer",
                    "party_id": customer.id,
                    "lines": [
                        {
                            "source_document_type": "sales_invoice",
                            "source_document_id": si.id,
                            "qty": 250,
                        },
                        {
                            "source_document_type": "sales_invoice",
                            "source_document_id": si.id,
                            "qty": 250,
                        },
                    ],
                }
            )

    def test_create_payment_missing_lines_rejected(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        with pytest.raises(ValueError, match="lineas"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "cacao",
                    "posting_date": date.today(),
                    "lines": [],
                }
            )

    def test_create_payment_zero_amount_rejected(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("500"))

        with pytest.raises(ValueError, match="mayor que cero"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "cacao",
                    "posting_date": date.today(),
                    "payment_type": "receive",
                    "party_type": "customer",
                    "party_id": customer.id,
                    "lines": [
                        {
                            "source_document_type": "sales_invoice",
                            "source_document_id": si.id,
                            "qty": 0,
                        }
                    ],
                }
            )

    def test_create_payment_exceeds_outstanding_rejected(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("100"))

        with pytest.raises(ValueError, match="excede el saldo"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "cacao",
                    "posting_date": date.today(),
                    "payment_type": "receive",
                    "party_type": "customer",
                    "party_id": customer.id,
                    "lines": [
                        {
                            "source_document_type": "sales_invoice",
                            "source_document_id": si.id,
                            "qty": 200,
                        }
                    ],
                }
            )

    def test_create_payment_company_mismatch_rejected(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("500"))

        with pytest.raises(ValueError, match="companias incompatibles"):
            create_target_document(
                {
                    "target_document_type": "payment_entry",
                    "company": "other_company",
                    "posting_date": date.today(),
                    "payment_type": "receive",
                    "party_type": "customer",
                    "party_id": customer.id,
                    "lines": [
                        {
                            "source_document_type": "sales_invoice",
                            "source_document_id": si.id,
                            "qty": 500,
                        }
                    ],
                }
            )

    def test_create_payment_updates_outstanding(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document
        from cacao_accounting.document_flow.payment import compute_outstanding_amount

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("500"))

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": date.today(),
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer.id,
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": si.id,
                        "qty": 300,
                    }
                ],
            }
        )
        payment = database.session.get(PaymentEntry, result["target_id"])
        payment.docstatus = 1
        database.session.flush()
        remaining = compute_outstanding_amount(si)
        assert remaining == Decimal("200")

    def test_create_payment_creates_document_relation(self, app_ctx):
        from cacao_accounting.document_flow.service import create_target_document

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        si = _make_customer_invoice(grand_total=Decimal("500"))

        result = create_target_document(
            {
                "target_document_type": "payment_entry",
                "company": "cacao",
                "posting_date": date.today(),
                "payment_type": "receive",
                "party_type": "customer",
                "party_id": customer.id,
                "lines": [
                    {
                        "source_document_type": "sales_invoice",
                        "source_document_id": si.id,
                        "qty": 500,
                    }
                ],
            }
        )
        rels = (
            database.session.execute(
                database.select(DocumentRelation).filter_by(
                    source_type="sales_invoice",
                    source_id=si.id,
                    target_type="payment_entry",
                    target_id=result["target_id"],
                )
            )
            .scalars()
            .all()
        )
        assert len(rels) == 1
        assert rels[0].status == "active"


# ---------------------------------------------------------------------------
# payment_reconciliation_candidates
# ---------------------------------------------------------------------------


class TestPaymentReconciliationCandidates:
    """Tests for payment_reconciliation_candidates."""

    def test_requires_company(self):
        from cacao_accounting.document_flow.payment import payment_reconciliation_candidates

        with pytest.raises(ValueError, match="compania"):
            payment_reconciliation_candidates(company="", party_type="customer")

    def test_returns_payments_and_documents(self, app_ctx):
        from cacao_accounting.document_flow.payment import payment_reconciliation_candidates

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        _make_customer_invoice(grand_total=Decimal("500"))
        _make_open_payment(party=customer, payment_type="receive", amount=Decimal("300"))

        result = payment_reconciliation_candidates(
            company="cacao",
            party_type="customer",
            party_id=customer.id,
        )
        assert "payments" in result
        assert "documents" in result
        assert len(result["payments"]) >= 1
        assert len(result["documents"]) >= 1


# ---------------------------------------------------------------------------
# refresh_outstanding_amount_cache
# ---------------------------------------------------------------------------


class TestRefreshOutstandingAmountCache:
    """Tests for refresh_outstanding_amount_cache."""

    def test_syncs_cache_field(self, app_ctx):
        from cacao_accounting.document_flow.payment import refresh_outstanding_amount_cache

        si = _make_customer_invoice(grand_total=Decimal("500"))
        si.outstanding_amount = Decimal("999")
        si.base_outstanding_amount = Decimal("999")
        database.session.flush()

        result = refresh_outstanding_amount_cache(si)
        assert result == Decimal("500")
        assert si.outstanding_amount == Decimal("500")


# ---------------------------------------------------------------------------
# _compute_cash_consumed_from_reference
# ---------------------------------------------------------------------------


class TestComputeCashConsumedFromReference:
    """Tests for _compute_cash_consumed_from_reference."""

    def test_order_type_returns_zero(self):
        from cacao_accounting.document_flow.payment import _compute_cash_consumed_from_reference

        consumed, status = _compute_cash_consumed_from_reference(
            "ref-1", "sales_order", "sales_order", Decimal("100"), Decimal("0"), Decimal("0"), "active"
        )
        assert consumed == Decimal("0")
        assert status is None

    def test_normal_reference(self):
        from cacao_accounting.document_flow.payment import _compute_cash_consumed_from_reference

        consumed, status = _compute_cash_consumed_from_reference(
            "ref-1", "sales_invoice", "sales_invoice", Decimal("100"), Decimal("10"), Decimal("5"), "active"
        )
        assert consumed == Decimal("85")
        assert status == "active"

    def test_negative_consumed_clamps_to_zero(self):
        from cacao_accounting.document_flow.payment import _compute_cash_consumed_from_reference

        consumed, status = _compute_cash_consumed_from_reference(
            "ref-1", "sales_invoice", "sales_invoice", Decimal("50"), Decimal("30"), Decimal("30"), "active"
        )
        assert consumed == Decimal("0")


# ---------------------------------------------------------------------------
# apply_advance_to_invoice - party_type casing
# ---------------------------------------------------------------------------


class TestApplyAdvancePartyTypeCasing:
    """PaymentReference.party_type must use lowercase ('customer'/'supplier')
    to be consistent with the rest of the codebase.  Capitalised values
    ('Customer'/'Supplier') break case-sensitive comparisons downstream."""

    def test_sales_advance_party_type_is_lowercase_customer(self, app_ctx):
        """Applying an advance to a SalesInvoice stores party_type='customer'."""
        from cacao_accounting.document_flow.payment import apply_advance_to_invoice

        si = _make_customer_invoice(grand_total=Decimal("500"))
        payment = _make_open_payment(
            party=database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first(),
            payment_type="receive",
            amount=Decimal("200"),
        )

        reference = apply_advance_to_invoice(payment.id, si.id, Decimal("100"), date.today())

        assert reference.party_type == "customer", f"Expected lowercase 'customer', got '{reference.party_type}'"

    def test_purchase_advance_party_type_is_lowercase_supplier(self, app_ctx):
        """Applying an advance to a PurchaseInvoice stores party_type='supplier'."""
        from cacao_accounting.document_flow.payment import apply_advance_to_invoice

        pi = _make_supplier_invoice(grand_total=Decimal("800"))
        payment = _make_open_payment(
            party=database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first(),
            payment_type="pay",
            amount=Decimal("300"),
        )

        reference = apply_advance_to_invoice(payment.id, pi.id, Decimal("150"), date.today())

        assert reference.party_type == "supplier", f"Expected lowercase 'supplier', got '{reference.party_type}'"

    def test_advance_cannot_be_applied_to_a_draft_invoice(self, app_ctx):
        """Advance applications require an approved invoice as well as an approved payment."""
        from cacao_accounting.document_flow.payment import apply_advance_to_invoice

        invoice = _make_customer_invoice(grand_total=Decimal("500"))
        invoice.docstatus = 0
        database.session.commit()
        payment = _make_open_payment(
            party=database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first(),
            payment_type="receive",
            amount=Decimal("200"),
        )

        with pytest.raises(ValueError, match="factura debe estar aprobada"):
            apply_advance_to_invoice(payment.id, invoice.id, Decimal("100"), date.today())

    def test_advance_cannot_overapply_an_invoice_with_a_later_payment(self, app_ctx):
        """Una aplicación retrofechada debe respetar el saldo vigente de la factura."""
        from cacao_accounting.document_flow.payment import apply_advance_to_invoice, compute_outstanding_amount
        from cacao_accounting.document_flow.service import create_document_relation

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        invoice = _make_customer_invoice(grand_total=Decimal("100"))
        invoice.posting_date = date.today() - timedelta(days=3)
        advance = _make_open_payment(party=customer, payment_type="receive", amount=Decimal("100"))
        advance.posting_date = date.today() - timedelta(days=2)
        later_payment = _make_open_payment(
            party=customer,
            payment_type="receive",
            amount=Decimal("100"),
            document_no="PAY-LATER-001",
        )
        later_payment.posting_date = date.today()
        later_reference = PaymentReference(
            payment_id=later_payment.id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
            allocated_amount=Decimal("100"),
            allocation_date=date.today(),
            company="cacao",
        )
        database.session.add(later_reference)
        database.session.flush()
        create_document_relation(
            source_type="sales_invoice",
            source_id=invoice.id,
            source_item_id=None,
            target_type="payment_entry",
            target_id=later_payment.id,
            target_item_id=later_reference.id,
            qty=Decimal("1"),
            rate=Decimal("100"),
            amount=Decimal("100"),
        )
        database.session.flush()

        assert compute_outstanding_amount(invoice) == Decimal("0")
        with pytest.raises(ValueError, match="saldo pendiente vigente"):
            apply_advance_to_invoice(advance.id, invoice.id, Decimal("100"), date.today() - timedelta(days=1))
        assert (
            database.session.execute(database.select(PaymentReference).filter_by(payment_id=advance.id)).scalars().all() == []
        )


# ---------------------------------------------------------------------------
# Exhaustive Bank Management Tests (Customer/Supplier payments, Advances,
# Deposits, Withdrawals, Debit Notes, Credit Notes, Transfers, FX, Reconciliation)
# ---------------------------------------------------------------------------


class TestBankManagementExhaustive:
    """Exhaustive tests for bank management and posting engine integration."""

    def test_customer_payment_excess_split_to_advance_account(self, app_ctx):
        """A customer payment exceeding invoice allocation splits the excess into customer_advance_account_id."""
        from cacao_accounting.contabilidad.posting import _create_payment_receive_entries, _document_contexts
        from cacao_accounting.database import BankAccount, Party, PaymentEntry, PaymentReference

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        defaults = _ensure_company_default_accounts("cacao", bank)

        si = _make_customer_invoice(grand_total=Decimal("700"))

        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="receive",
            party_type="customer",
            party_id=customer.id,
            party_name=customer.name,
            bank_account_id=bank.id,
            currency="NIO",
            received_amount=Decimal("1000"),
            docstatus=1,
            document_no="PAY-REC-EXCESS-01",
        )
        database.session.add(payment)
        database.session.flush()

        ref = PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id=si.id,
            allocated_amount=Decimal("700"),
            allocation_date=date.today(),
        )
        database.session.add(ref)
        database.session.commit()

        context = _document_contexts(payment)[0]
        entries = _create_payment_receive_entries(context, payment, "cacao", Decimal("1000"))
        assert len(entries) == 3

        debit_entry = [e for e in entries if e.debit > 0][0]
        assert debit_entry.debit_in_account_currency == Decimal("1000")
        assert debit_entry.account_id == bank.gl_account_id
        assert debit_entry.party_type is None
        assert debit_entry.party_id is None

        credits = [e for e in entries if e.credit > 0]
        assert len(credits) == 2
        rec_credit = [e for e in credits if e.account_id == defaults.default_receivable][0]
        assert rec_credit.credit_in_account_currency == Decimal("700")

        adv_credit = [e for e in credits if e.account_id == defaults.customer_advance_account_id][0]
        assert adv_credit.credit_in_account_currency == Decimal("300")

    def test_customer_advance_bank_entry_has_no_party_dimension(self, app_ctx):
        """A receipt without allocations keeps the customer off the bank line."""
        from cacao_accounting.contabilidad.posting import _create_payment_receive_entries, _document_contexts
        from cacao_accounting.database import BankAccount, Party, PaymentEntry

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        _ensure_company_default_accounts("cacao", bank)
        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="receive",
            party_type="customer",
            party_id=customer.id,
            party_name=customer.name,
            bank_account_id=bank.id,
            currency="NIO",
            received_amount=Decimal("100"),
            docstatus=1,
            document_no="PAY-REC-ADVANCE-01",
        )
        database.session.add(payment)
        database.session.commit()

        entries = _create_payment_receive_entries(_document_contexts(payment)[0], payment, "cacao", Decimal("100"))
        bank_entry = next(entry for entry in entries if entry.account_id == bank.gl_account_id)

        assert bank_entry.party_type is None
        assert bank_entry.party_id is None

    def test_normal_payment_entries_keep_party_off_bank_side(self, app_ctx):
        """The shared payment helper only assigns the party to the subledger side."""
        from cacao_accounting.contabilidad.posting import _document_contexts, _normal_entries_for_amount
        from cacao_accounting.database import BankAccount, Party, PaymentEntry

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        defaults = _ensure_company_default_accounts("cacao", bank)
        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="pay",
            party_type="customer",
            party_id=customer.id,
            bank_account_id=bank.id,
            currency="NIO",
            paid_amount=Decimal("100"),
            docstatus=1,
            document_no="PAY-BANK-PARTY-01",
        )
        database.session.add(payment)
        database.session.commit()

        entries = _normal_entries_for_amount(
            context=_document_contexts(payment)[0],
            debit_account_id=defaults.default_receivable,
            credit_account_id=bank.gl_account_id,
            amount=Decimal("100"),
            party_type="customer",
            party_id=customer.id,
            credit_bank_account_id=bank.id,
        )

        party_entry = next(entry for entry in entries if entry.account_id == defaults.default_receivable)
        bank_entry = next(entry for entry in entries if entry.account_id == bank.gl_account_id)
        assert party_entry.party_id == customer.id
        assert bank_entry.party_type is None
        assert bank_entry.party_id is None

    def test_supplier_payment_excess_requires_advance_account(self, app_ctx):
        """A partially allocated supplier payment cannot drop its advance portion."""
        import pytest

        from cacao_accounting.contabilidad.posting import PostingError, _create_payment_pay_entries, _document_contexts
        from cacao_accounting.database import BankAccount, Party, PaymentEntry, PaymentReference

        supplier = database.session.execute(database.select(Party).filter(Party.is_supplier.is_(True))).scalars().first()
        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        defaults = _ensure_company_default_accounts("cacao", bank)
        defaults.supplier_advance_account_id = None
        invoice = _make_supplier_invoice(grand_total=Decimal("700"))
        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="pay",
            party_type="supplier",
            party_id=supplier.id,
            party_name=supplier.name,
            bank_account_id=bank.id,
            currency="NIO",
            paid_amount=Decimal("1000"),
            docstatus=1,
            document_no="PAY-SUPPLIER-EXCESS-01",
        )
        database.session.add(payment)
        database.session.flush()
        database.session.add(
            PaymentReference(
                payment_id=payment.id,
                reference_type="purchase_invoice",
                reference_id=invoice.id,
                allocated_amount=Decimal("700"),
                allocation_date=date.today(),
            )
        )
        database.session.commit()

        with pytest.raises(PostingError, match="anticipo de proveedor"):
            _create_payment_pay_entries(_document_contexts(payment)[0], payment, "cacao", Decimal("1000"))

    def test_bank_debit_note_uses_custom_paid_to_account(self, app_ctx):
        """A bank debit note uses paid_to_account_id when specified."""
        from cacao_accounting.contabilidad.posting import post_payment_entry
        from cacao_accounting.database import BankAccount, Accounts, PaymentEntry
        from cacao_accounting.ledger_queries import primary_ledger_id

        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        _ensure_company_default_accounts("cacao", bank)

        custom_expense = (
            database.session.execute(
                database.select(Accounts).filter_by(entity="cacao", account_type="expense").order_by(Accounts.code.desc())
            )
            .scalars()
            .first()
        )

        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="debit_note",
            bank_account_id=bank.id,
            paid_to_account_id=custom_expense.id,
            currency="NIO",
            paid_amount=Decimal("150"),
            docstatus=1,
            document_no="PAY-DN-CUSTOM-01",
        )
        database.session.add(payment)
        database.session.commit()

        entries = post_payment_entry(payment)
        primary_id = primary_ledger_id("cacao")
        primary_entries = [e for e in entries if e.ledger_id == primary_id] if primary_id else entries
        assert len(primary_entries) == 2
        debit_entry = [e for e in primary_entries if e.debit > 0][0]
        assert debit_entry.account_id == custom_expense.id
        assert debit_entry.debit_in_account_currency == Decimal("150")

    def test_bank_credit_note_uses_custom_paid_from_account(self, app_ctx):
        """A bank credit note uses paid_from_account_id when specified."""
        from cacao_accounting.contabilidad.posting import post_payment_entry
        from cacao_accounting.database import BankAccount, Accounts, PaymentEntry
        from cacao_accounting.ledger_queries import primary_ledger_id

        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        _ensure_company_default_accounts("cacao", bank)

        custom_income = (
            database.session.execute(
                database.select(Accounts).filter_by(entity="cacao", account_type="income").order_by(Accounts.code.desc())
            )
            .scalars()
            .first()
        )

        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="credit_note",
            bank_account_id=bank.id,
            paid_from_account_id=custom_income.id,
            currency="NIO",
            received_amount=Decimal("250"),
            docstatus=1,
            document_no="PAY-CN-CUSTOM-01",
        )
        database.session.add(payment)
        database.session.commit()

        entries = post_payment_entry(payment)
        primary_id = primary_ledger_id("cacao")
        primary_entries = [e for e in entries if e.ledger_id == primary_id] if primary_id else entries
        assert len(primary_entries) == 2
        credit_entry = [e for e in primary_entries if e.credit > 0][0]
        assert credit_entry.account_id == custom_income.id
        assert credit_entry.credit_in_account_currency == Decimal("250")

    def test_internal_transfer_multi_currency_with_fx_difference(self, app_ctx):
        """Internal transfer between accounts in different currencies generates FX gain/loss entries."""
        from cacao_accounting.contabilidad.posting import post_payment_entry
        from cacao_accounting.database import BankAccount, Bank, Accounts, ExchangeRate, PaymentEntry
        from cacao_accounting.ledger_queries import primary_ledger_id

        bank_entity = database.session.execute(database.select(Bank)).scalars().first()
        bank1 = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        _ensure_company_default_accounts("cacao", bank1)

        usd_account = (
            database.session.execute(
                database.select(Accounts).filter_by(entity="cacao", account_type="bank").order_by(Accounts.code.desc())
            )
            .scalars()
            .first()
        )
        bank2 = BankAccount(
            bank_id=bank_entity.id,
            company="cacao",
            account_name="Cuenta USD Test",
            account_no="USD-9999",
            currency="USD",
            gl_account_id=usd_account.id,
        )
        database.session.add(bank2)

        existing_rate = (
            database.session.execute(
                database.select(ExchangeRate).filter_by(origin="USD", destination="NIO", date=date.today())
            )
            .scalars()
            .first()
        )
        if existing_rate:
            existing_rate.rate = Decimal("36.50")
        else:
            rate = ExchangeRate(
                origin="USD",
                destination="NIO",
                date=date.today(),
                rate=Decimal("36.50"),
            )
            database.session.add(rate)
        database.session.commit()

        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="internal_transfer",
            bank_account_id=bank2.id,
            target_bank_account_id=bank1.id,
            paid_from_account_id=bank2.gl_account_id,
            paid_to_account_id=bank1.gl_account_id,
            currency="USD",
            paid_amount=Decimal("100"),
            received_amount=Decimal("3600"),
            docstatus=1,
            document_no="PAY-TRF-FX-01",
        )
        database.session.add(payment)
        database.session.commit()

        entries = post_payment_entry(payment)
        primary_id = primary_ledger_id("cacao")
        primary_entries = [e for e in entries if e.ledger_id == primary_id] if primary_id else entries
        assert len(primary_entries) == 3
        target_debit = [e for e in primary_entries if e.account_id == bank1.gl_account_id and e.debit > 0][0]
        assert target_debit.debit_in_account_currency == Decimal("3600")

        source_credit = [e for e in primary_entries if e.account_id == bank2.gl_account_id and e.credit > 0][0]
        assert source_credit.credit_in_account_currency == Decimal("100")

    def test_internal_transfer_multi_currency_unbalanced_rejected(self, app_ctx):
        """Internal transfer with internally unbalanced amounts in foreign currency is rejected."""
        from cacao_accounting.contabilidad.posting import post_payment_entry, PostingError
        from cacao_accounting.database import BankAccount, Bank, Accounts, ExchangeRate, PaymentEntry

        bank_entity = database.session.execute(database.select(Bank)).scalars().first()
        bank1 = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        _ensure_company_default_accounts("cacao", bank1)

        usd_account1 = (
            database.session.execute(
                database.select(Accounts).filter_by(entity="cacao", account_type="bank").order_by(Accounts.code.asc())
            )
            .scalars()
            .first()
        )
        usd_account2 = (
            database.session.execute(
                database.select(Accounts).filter_by(entity="cacao", account_type="bank").order_by(Accounts.code.desc())
            )
            .scalars()
            .first()
        )
        bank_usd1 = BankAccount(
            bank_id=bank_entity.id,
            company="cacao",
            account_name="Cuenta USD Out",
            account_no="USD-100",
            currency="USD",
            gl_account_id=usd_account1.id,
        )
        bank_usd2 = BankAccount(
            bank_id=bank_entity.id,
            company="cacao",
            account_name="Cuenta USD In",
            account_no="USD-200",
            currency="USD",
            gl_account_id=usd_account2.id,
        )
        database.session.add_all([bank_usd1, bank_usd2])

        existing_rate = (
            database.session.execute(
                database.select(ExchangeRate).filter_by(origin="USD", destination="NIO", date=date.today())
            )
            .scalars()
            .first()
        )
        if existing_rate:
            existing_rate.rate = Decimal("36.50")
        else:
            rate = ExchangeRate(
                origin="USD",
                destination="NIO",
                date=date.today(),
                rate=Decimal("36.50"),
            )
            database.session.add(rate)
        database.session.commit()

        # Unbalanced USD transfer: 100 USD paid from bank_usd1, 90 USD received into bank_usd2
        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="internal_transfer",
            bank_account_id=bank_usd1.id,
            target_bank_account_id=bank_usd2.id,
            paid_from_account_id=bank_usd1.gl_account_id,
            paid_to_account_id=bank_usd2.gl_account_id,
            currency="USD",
            paid_amount=Decimal("100"),
            received_amount=Decimal("90"),
            docstatus=1,
            document_no="PAY-TRF-UNBAL-01",
        )
        database.session.add(payment)
        database.session.commit()

        with pytest.raises(PostingError, match="Las entradas GL no balancean en moneda de transaccion"):
            post_payment_entry(payment)

    def test_bank_reconciliation_and_difference_journal(self, app_ctx):
        """Bank reconciliation candidates search, matching, and bank difference adjustment."""
        from cacao_accounting.bancos.reconciliation_service import (
            BankReconciliationMatch,
            BankReconciliationRequest,
            find_bank_reconciliation_candidates,
            reconcile_bank_items,
        )
        from cacao_accounting.bancos.statement_service import create_bank_difference_journal
        from cacao_accounting.database import BankAccount, BankTransaction, CompanyDefaultAccount, Party, PaymentEntry

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
        _ensure_company_default_accounts("cacao", bank)

        payment = PaymentEntry(
            company="cacao",
            posting_date=date.today(),
            payment_type="receive",
            party_type="customer",
            party_id=customer.id,
            party_name=customer.name,
            bank_account_id=bank.id,
            currency="NIO",
            received_amount=Decimal("500"),
            docstatus=1,
            document_no="PAY-REC-RECON-01",
        )
        database.session.add(payment)

        bt = BankTransaction(
            bank_account_id=bank.id,
            posting_date=date.today(),
            reference_number="REC-001",
            description="Depósito cliente",
            deposit=Decimal("500"),
        )
        database.session.add(bt)
        database.session.commit()

        candidates = find_bank_reconciliation_candidates(bt.id)
        assert len(candidates) >= 1
        assert any(c.reference_id == payment.id for c in candidates)

        reconciliation = reconcile_bank_items(
            BankReconciliationRequest(
                company="cacao",
                reconciliation_date=date.today(),
                matches=[
                    BankReconciliationMatch(
                        bank_transaction_id=bt.id,
                        target_type="payment_entry",
                        target_id=payment.id,
                        allocated_amount=Decimal("500"),
                    )
                ],
            )
        )
        assert reconciliation.id is not None
        assert bt.is_reconciled is True

        defaults = (
            database.session.execute(database.select(CompanyDefaultAccount).filter_by(company="cacao")).scalars().first()
        )
        defaults.bank_difference_account_id = defaults.default_expense
        database.session.commit()

        journal = create_bank_difference_journal(reconciliation.id, Decimal("10"), transaction_id=bt.id)
        assert journal is not None
        assert journal.entity == "cacao"
