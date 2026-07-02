"""Tests for persisted fiscal rules and admin CRUD."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from flask import Flask

from cacao_accounting import create_app
from cacao_accounting.accounting_engine.document_builders import _build_payment_context, _document_tax_rules
from cacao_accounting.config import configuracion
from cacao_accounting.fiscal_persistence_service import (
    build_tax_rule_contexts_from_snapshot,
    load_document_fiscal_lines,
    persist_document_fiscal_snapshot,
)
from cacao_accounting.fiscal_preview_service import fiscal_preview, get_fiscal_document_profile
from cacao_accounting.tax_rule_service import build_tax_rule_contexts


@pytest.fixture()
def app_ctx() -> Iterator[Flask]:
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-tax-rules-secret",
        }
    )
    with app.app_context():
        from cacao_accounting.database import CacaoConfig, Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                CacaoConfig(key="SETUP_COMPLETE", value="True"),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="US Dollar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="admin", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


@pytest.fixture()
def client(app_ctx: Flask):
    return app_ctx.test_client()


def _login_admin(client) -> None:
    from cacao_accounting.database import User

    admin = User.query.filter_by(user="admin").first()
    assert admin is not None
    with client.session_transaction() as session:
        session["_user_id"] = admin.id
        session["_fresh"] = True


def test_admin_tax_rule_crud(client) -> None:
    """The admin module should create, edit and delete fiscal rules."""
    from cacao_accounting.database import TaxRule, database

    _login_admin(client)

    response = client.post(
        "/settings/tax-rules",
        data={
            "name": "IVA Venta",
            "company": "cacao",
            "concept": "IVA",
            "applies_to": "sales",
            "level": "transaction",
            "tax_type": "tax",
            "calculation_method": "percentage",
            "rate": "15",
            "amount": "0",
            "base_mode": "goods",
            "include_concepts": "goods",
            "exclude_concepts": "",
            "sequence": "10",
            "accounting_treatment": "separate_tax_account",
            "recognition_event": "invoice",
            "currency": "USD",
            "country": "NI",
            "affects_document_total": "on",
            "is_active": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    created_rule = database.session.execute(database.select(TaxRule)).scalar_one()
    assert created_rule.name == "IVA Venta"
    assert created_rule.include_concepts == "goods"

    response = client.post(
        f"/settings/tax-rules/{created_rule.id}/edit",
        data={
            "name": "IVA Venta Actualizado",
            "company": "cacao",
            "concept": "IVA",
            "applies_to": "sales",
            "level": "transaction",
            "tax_type": "tax",
            "calculation_method": "percentage",
            "rate": "13",
            "amount": "0",
            "base_mode": "goods",
            "include_concepts": "goods, ISC",
            "exclude_concepts": "",
            "sequence": "20",
            "accounting_treatment": "separate_tax_account",
            "recognition_event": "invoice",
            "currency": "USD",
            "country": "NI",
            "affects_document_total": "on",
            "participates_in_next_base": "on",
            "is_active": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    database.session.refresh(created_rule)
    assert created_rule.name == "IVA Venta Actualizado"
    assert created_rule.sequence == 20
    assert created_rule.participates_in_next_base is True

    response = client.post(f"/settings/tax-rules/{created_rule.id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert database.session.get(TaxRule, created_rule.id) is None


def test_tax_rule_service_builds_contexts_from_db(app_ctx: Flask) -> None:
    """Persisted fiscal rules should be converted into engine contexts."""
    from cacao_accounting.database import TaxRule, database

    database.session.add(
        TaxRule(
            company="cacao",
            name="DAI Importación",
            applies_to="purchase",
            level="transaction",
            concept="DAI",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("5"),
            amount=Decimal("0"),
            base_mode="accumulated",
            include_concepts="goods, Flete",
            sequence=5,
            accounting_treatment="capitalizable_inventory_cost",
            recognition_event="purchase_invoice_confirmed",
            currency="USD",
            valid_from=date(2026, 1, 1),
            is_active=True,
        )
    )
    database.session.commit()

    contexts = build_tax_rule_contexts(
        company="cacao",
        applies_to="purchase",
        currency="USD",
        at_date=date(2026, 5, 1),
        recognition_event="purchase_invoice_confirmed",
    )

    assert len(contexts) == 1
    assert contexts[0].concept == "DAI"
    assert contexts[0].include_concepts == ["goods", "Flete"]
    assert contexts[0].accounting_treatment == "capitalizable_inventory_cost"


def test_fiscal_preview_reuses_canonical_rules_after_recalculation(app_ctx: Flask) -> None:
    """Repeated previews must not degrade cascaded persisted rule metadata."""
    from cacao_accounting.database import TaxRule, database

    database.session.add_all(
        [
            TaxRule(
                company="cacao",
                name="DAI Importación",
                applies_to="purchase",
                level="transaction",
                concept="DAI",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("5"),
                amount=Decimal("0"),
                base_mode="goods",
                sequence=10,
                accounting_treatment="capitalizable_inventory_cost",
                recognition_event="purchase_invoice_confirmed",
                currency="USD",
                valid_from=date(2026, 1, 1),
                is_active=True,
                participates_in_next_base=True,
            ),
            TaxRule(
                company="cacao",
                name="IVA Importación",
                applies_to="purchase",
                level="transaction",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                amount=Decimal("0"),
                base_mode="accumulated",
                include_concepts="goods, DAI",
                sequence=20,
                accounting_treatment="separate_tax_account",
                recognition_event="purchase_invoice_confirmed",
                currency="USD",
                valid_from=date(2026, 1, 1),
                is_active=True,
            ),
        ]
    )
    database.session.commit()
    payload = {
        "document_type": "purchase_invoice",
        "company": "cacao",
        "currency": "USD",
        "posting_date": "2026-05-19",
        "party_type": "supplier",
        "party_id": "SUPP-DEMO",
        "lines": [{"uid": "L-1", "item_code": "ITEM-1", "item_name": "Item 1", "qty": 1, "rate": 100, "amount": 100}],
    }

    first_preview = fiscal_preview(payload)
    second_preview = fiscal_preview({**payload, "tax_lines": first_preview["tax_lines"]})

    assert [line["concept"] for line in second_preview["tax_lines"]] == ["DAI", "IVA"]
    assert second_preview["tax_lines"][1]["base_amount"] == "105.00"
    assert second_preview["tax_lines"][1]["amount"] == "15.75"


def test_fiscal_preview_appends_manual_charges_to_canonical_rules(app_ctx: Flask) -> None:
    """Manual fiscal lines from the form should coexist with configured rules."""
    from cacao_accounting.database import TaxRule, database

    database.session.add(
        TaxRule(
            company="cacao",
            name="IVA Compra",
            applies_to="purchase",
            level="transaction",
            concept="IVA",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("15"),
            amount=Decimal("0"),
            base_mode="goods",
            sequence=10,
            accounting_treatment="separate_tax_account",
            recognition_event="purchase_invoice_confirmed",
            currency="USD",
            valid_from=date(2026, 1, 1),
            is_active=True,
        )
    )
    database.session.commit()

    preview = fiscal_preview(
        {
            "document_type": "purchase_invoice",
            "company": "cacao",
            "currency": "USD",
            "posting_date": "2026-05-19",
            "party_type": "supplier",
            "party_id": "SUPP-DEMO",
            "lines": [{"uid": "L-1", "item_code": "ITEM-1", "item_name": "Item 1", "qty": 1, "rate": 100, "amount": 100}],
            "tax_lines": [
                {
                    "source_rule_id": "MANUAL-FREIGHT",
                    "manual": True,
                    "concept": "Flete",
                    "type": "charge",
                    "calculation_method": "manual",
                    "amount": "12.50",
                    "accounting_treatment": "capitalizable_inventory_cost",
                    "allocation_method": "by_value",
                    "affects_document_total": True,
                }
            ],
        }
    )

    assert [line["concept"] for line in preview["tax_lines"]] == ["IVA", "Flete"]
    assert preview["tax_lines"][1]["manual"] is True
    assert preview["tax_lines"][1]["allocation_method"] == "by_value"
    assert preview["summary"]["document_tax_total"] == "27.50"
    assert preview["summary"]["capitalizable_tax_total"] == "12.50"


def test_receive_payment_profile_uses_collection_event(app_ctx: Flask) -> None:
    """Normal incoming payments must resolve to the collection fiscal profile."""
    profile = get_fiscal_document_profile("payment_entry", "receive")

    assert profile.document_type == "payment_entry"
    assert profile.applies_to == "sales"
    assert profile.recognition_event == "collection_confirmed"


def test_document_tax_snapshot_is_persisted_and_loaded_for_invoice(app_ctx: Flask) -> None:
    """Persisted fiscal lines must be loaded as immutable rules for invoice posting."""
    from cacao_accounting.database import PurchaseInvoice, database

    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 1), document_type="purchase_invoice", docstatus=0)
    database.session.add(invoice)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="purchase_invoice",
        document_id=invoice.id,
        currency="USD",
        tax_lines=[
            {
                "source_rule_id": "RULE-SNAPSHOT-001",
                "concept": "IVA",
                "type": "tax",
                "base_amount": "100.00",
                "rate": "15",
                "amount": "15.00",
                "accounting_treatment": "separate_tax_account",
                "account_id": "",
                "affects_inventory": False,
                "included_in_price": False,
                "notes": "snapshot line",
            }
        ],
        tax_summary={"subtotal": "100.00", "document_tax_total": "15.00", "grand_total": "115.00"},
    )
    rules = _document_tax_rules(
        invoice,
        [],
        company="cacao",
        applies_to="purchase",
        event_type="purchase_invoice_confirmed",
    )
    assert len(rules) == 1
    assert rules[0].calculation_method == "manual"
    assert rules[0].amount == Decimal("15.00")
    assert rules[0].concept == "IVA"
    persisted_lines = load_document_fiscal_lines("purchase_invoice", invoice.id)
    assert persisted_lines[0].account_id is None


def test_payment_context_uses_persisted_fiscal_snapshot(app_ctx: Flask) -> None:
    """Payment posting context must consume persisted fiscal payload instead of recalculating."""
    from cacao_accounting.database import PaymentEntry, database

    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 1),
        payment_type="pay",
        paid_amount=Decimal("120.00"),
        base_paid_amount=Decimal("120.00"),
        party_type="supplier",
        party_id="",
        docstatus=0,
    )
    database.session.add(payment)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="payment_entry",
        document_id=payment.id,
        currency="USD",
        tax_lines=[
            {
                "source_rule_id": "RULE-WHT-001",
                "concept": "RETENCION",
                "type": "withholding",
                "base_amount": "120.00",
                "rate": "2",
                "amount": "2.40",
                "accounting_treatment": "separate_tax_account",
                "account_id": None,
                "affects_inventory": False,
                "affects_document_total": True,
                "included_in_price": False,
            }
        ],
        tax_summary={"subtotal": "120.00", "document_tax_total": "2.40", "grand_total": "122.40"},
    )
    context = _build_payment_context(payment)
    assert context is not None
    assert len(context.tax_rules) == 1
    assert context.tax_rules[0].calculation_method == "manual"
    assert context.tax_rules[0].amount == Decimal("2.40")
    loaded_lines = build_tax_rule_contexts_from_snapshot(
        document_type="payment_entry",
        document_id=payment.id,
        recognition_event="payment_confirmed",
    )
    assert len(loaded_lines) == 1
