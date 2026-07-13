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

from datetime import date
from decimal import Decimal

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
    PurchaseOrder,
    PurchaseOrderItem,
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


class TestToJsonNumber:
    """Unit tests for _to_json_number."""

    def test_decimal_value(self):
        from cacao_accounting.document_flow.payment import _to_json_number

        assert _to_json_number(Decimal("123.45")) == 123.45

    def test_none_returns_zero(self):
        from cacao_accounting.document_flow.payment import _to_json_number

        assert _to_json_number(None) == 0.0

    def test_zero(self):
        from cacao_accounting.document_flow.payment import _to_json_number

        assert _to_json_number(Decimal("0")) == 0.0


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
                        "qty": 300,
                    }
                ],
            }
        )
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
        rels = database.session.execute(
            database.select(DocumentRelation).filter_by(
                source_type="sales_invoice",
                source_id=si.id,
                target_type="payment_entry",
                target_id=result["target_id"],
            )
        ).scalars().all()
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
        si = _make_customer_invoice(grand_total=Decimal("500"))
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
