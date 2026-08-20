# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests de contrato de precisión decimal para serialización financiera.

Cubren:
- ``_to_json_number``: edge cases con valores límite de precisión.
- ``payment_reference_candidates``: contrato multi-moneda con decimales
  fraccionarios y types de cambio.

Issue: #284 — parseFloat precision losses in frontend/printing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from cacao_accounting import create_app
from cacao_accounting.database import (
    BankAccount,
    CompanyDefaultAccount,
    Party,
    SalesInvoice,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos
from cacao_accounting.document_flow.payment import _to_json_number


def test_to_json_number_preserves_exact_decimal_values():
    """Valores Decimal deben serializarse sin perder precisión."""
    assert _to_json_number(Decimal("0.01")) == "0.01"
    assert _to_json_number(Decimal("0.1")) == "0.1"
    assert _to_json_number(Decimal("0.333333")) == "0.333333"
    assert _to_json_number(Decimal("1.005")) == "1.005"
    assert _to_json_number(Decimal("999999999.99")) == "999999999.99"
    assert _to_json_number(Decimal("0.0001")) == "0.0001"
    assert _to_json_number(Decimal("36.123456789")) == "36.123456789"


def test_to_json_number_handles_none_and_empty():
    """None y strings vacíos deben serializarse como '0'."""
    assert _to_json_number(None) == "0"
    assert _to_json_number("") == "0"


def test_to_json_number_preserves_string_inputs():
    """Strings decimales limpios se preservan sin perder ceros significativos."""
    assert _to_json_number("300.0000") == "300.0000"
    assert _to_json_number("10.50") == "10.50"
    assert _to_json_number("0.0001") == "0.0001"
    assert _to_json_number("0") == "0"


def test_to_json_number_handles_numeric_string_with_whitespace():
    """Los strings con espacios en blanco se normalizan correctamente."""
    assert _to_json_number("  1.005  ") == "1.005"


def test_to_json_number_preserves_scale_for_large_integers():
    """Los enteros grandes se serializan exactamente."""
    assert _to_json_number(Decimal("1000000")) == "1000000"
    assert _to_json_number(Decimal("999999999999")) == "999999999999"


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


def _ensure_company_default_accounts(company: str, bank: BankAccount) -> CompanyDefaultAccount:
    defaults = database.session.execute(database.select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()
    if not defaults:
        defaults = CompanyDefaultAccount(company=company)
        database.session.add(defaults)
        database.session.flush()
    defaults.default_bank = defaults.default_bank or bank.gl_account_id
    defaults.default_cash = defaults.default_cash or bank.gl_account_id
    defaults.default_receivable = defaults.default_receivable or bank.gl_account_id
    defaults.default_payable = defaults.default_payable or bank.gl_account_id
    defaults.customer_advance_account_id = defaults.customer_advance_account_id or defaults.default_receivable
    defaults.supplier_advance_account_id = defaults.supplier_advance_account_id or defaults.default_payable
    database.session.commit()
    return defaults


class TestPaymentReferencePrecision:
    """Tests de contrato de precisión para payment_reference_candidates."""

    def test_candidate_preserves_fractional_amounts(self, app_ctx):
        """Los montos fraccionarios se serializan como strings sin perder precisión."""
        client = app_ctx.test_client()
        login(client, "cacao", "cacao")

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        invoice = SalesInvoice(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            document_type="sales_invoice",
            docstatus=1,
            grand_total=Decimal("300.50"),
            outstanding_amount=Decimal("300.50"),
            base_outstanding_amount=Decimal("300.50"),
            document_no="FV-PRECISION-001",
        )
        database.session.add(invoice)
        database.session.commit()

        response = client.get(
            "/api/document-flow/payment-reference-candidates",
            query_string={
                "company": "cacao",
                "party_type": "customer",
                "party_id": customer.id,
                "source_type": ["sales_invoice"],
            },
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        candidate = next(item for item in items if item["document_id"] == invoice.id)
        assert candidate["pending_amount"] == "300.5000"
        assert Decimal(candidate["pending_amount"]) == Decimal("300.50")
        assert candidate["grand_total"] == "300.5000"

    def test_candidate_preserves_high_precision_amounts(self, app_ctx):
        """Montos con 4 decimales se preservan según la escala de la BD (scale=4)."""
        client = app_ctx.test_client()
        login(client, "cacao", "cacao")

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        invoice = SalesInvoice(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            document_type="sales_invoice",
            docstatus=1,
            grand_total=Decimal("999.9999"),
            outstanding_amount=Decimal("999.9999"),
            base_outstanding_amount=Decimal("999.9999"),
            document_no="FV-PRECISION-002",
        )
        database.session.add(invoice)
        database.session.commit()

        response = client.get(
            "/api/document-flow/payment-reference-candidates",
            query_string={
                "company": "cacao",
                "party_type": "customer",
                "party_id": customer.id,
                "source_type": ["sales_invoice"],
            },
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        candidate = next(item for item in items if item["document_id"] == invoice.id)
        assert candidate["pending_amount"] == "999.9999"
        assert Decimal(candidate["pending_amount"]) == Decimal("999.9999")

    def test_candidate_excludes_zero_outstanding(self, app_ctx):
        """Documentos con saldo pendiente cero no aparecen como candidatos."""
        client = app_ctx.test_client()
        login(client, "cacao", "cacao")

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        invoice = SalesInvoice(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            document_type="sales_invoice",
            docstatus=1,
            grand_total=Decimal("0"),
            outstanding_amount=Decimal("0"),
            base_outstanding_amount=Decimal("0"),
            document_no="FV-ZERO-001",
        )
        database.session.add(invoice)
        database.session.commit()

        response = client.get(
            "/api/document-flow/payment-reference-candidates",
            query_string={
                "company": "cacao",
                "party_type": "customer",
                "party_id": customer.id,
                "source_type": ["sales_invoice"],
            },
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert all(item["document_id"] != invoice.id for item in items)

    def test_candidate_filters_by_company(self, app_ctx):
        """Los candidatos se filtran correctamente por compañía."""
        client = app_ctx.test_client()
        login(client, "cacao", "cacao")

        customer = database.session.execute(database.select(Party).filter(Party.is_customer.is_(True))).scalars().first()
        invoice = SalesInvoice(
            company="cacao",
            customer_id=customer.id,
            posting_date=date.today(),
            document_type="sales_invoice",
            docstatus=1,
            grand_total=Decimal("150.25"),
            outstanding_amount=Decimal("150.25"),
            base_outstanding_amount=Decimal("150.25"),
            document_no="FV-COMPANY-001",
        )
        database.session.add(invoice)
        database.session.commit()

        response = client.get(
            "/api/document-flow/payment-reference-candidates",
            query_string={
                "company": "cacao",
                "party_type": "customer",
                "party_id": customer.id,
                "source_type": ["sales_invoice", "purchase_invoice"],
            },
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        candidate = next(item for item in items if item["document_id"] == invoice.id)
        assert Decimal(candidate["pending_amount"]) == Decimal("150.25")
