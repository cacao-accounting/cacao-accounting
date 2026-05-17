"""Tests for persisted fiscal rules and admin CRUD."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from flask import Flask

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
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
