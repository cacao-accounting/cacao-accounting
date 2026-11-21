# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1261: una regla de matching bancario respeta su cuenta configurada.

La ejecución manual debe aplicar la misma regla que el matching automático: una
regla ligada a una cuenta solo corre sobre esa cuenta; las reglas sin cuenta
aplican a toda la compañía.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos.statement_service import BankStatementError, apply_bank_matching_rule
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankMatchingRule,
    Currency,
    Entity,
    Modules,
    User,
    database,
)


@pytest.fixture
def bank_rule_scope_scenario():
    """Create two bank accounts and rules with and without account scope."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="cash", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name=f"Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        bank = Bank(name="Banco")
        database.session.add(bank)
        database.session.flush()
        account_a = BankAccount(bank_id=bank.id, company="alpha", account_name="Cuenta A", account_no="A-1")
        account_b = BankAccount(bank_id=bank.id, company="alpha", account_name="Cuenta B", account_no="B-1")
        account_foreign = BankAccount(bank_id=bank.id, company="beta", account_name="Cuenta Beta", account_no="BE-1")
        database.session.add_all([account_a, account_b, account_foreign])
        database.session.flush()
        scoped_rule = BankMatchingRule(
            company="alpha",
            bank_account_id=account_a.id,
            name="Regla A",
            days_tolerance=7,
            amount_tolerance=Decimal("0"),
            is_active=True,
        )
        company_rule = BankMatchingRule(
            company="alpha",
            bank_account_id=None,
            name="Regla Compañía",
            days_tolerance=7,
            amount_tolerance=Decimal("0"),
            is_active=True,
        )
        database.session.add_all([scoped_rule, company_rule])
        database.session.add(
            User(
                id=f"admin-{suffix}",
                user=f"admin-{suffix}",
                name="Administrador",
                password=b"unused",
                active=True,
                company="alpha",
                classification="admin",
            )
        )
        database.session.commit()
        ids = {
            "account_a": account_a.id,
            "account_b": account_b.id,
            "account_foreign": account_foreign.id,
            "scoped_rule": scoped_rule.id,
            "company_rule": company_rule.id,
            "admin": f"admin-{suffix}",
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the seeded admin."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_service_rejects_rule_scoped_to_another_account(bank_rule_scope_scenario):
    """The service enforces the account rule before querying transactions."""
    app, ids = bank_rule_scope_scenario

    with app.app_context():
        with pytest.raises(BankStatementError):
            apply_bank_matching_rule(ids["scoped_rule"], ids["account_b"], (date(2026, 5, 1), date(2026, 5, 31)))


def test_service_allows_rule_scope_and_company_wide_rule(bank_rule_scope_scenario):
    """The scoped rule runs on its account and the company rule on any account."""
    app, ids = bank_rule_scope_scenario

    with app.app_context():
        scoped = apply_bank_matching_rule(ids["scoped_rule"], ids["account_a"], (date(2026, 5, 1), date(2026, 5, 31)))
        company_wide = apply_bank_matching_rule(ids["company_rule"], ids["account_b"], (date(2026, 5, 1), date(2026, 5, 31)))

    assert scoped.rule_id == ids["scoped_rule"]
    assert company_wide.rule_id == ids["company_rule"]


def test_manual_execution_rejects_another_account(bank_rule_scope_scenario):
    """The manual run shows the scope error instead of evaluating the other account."""
    app, ids = bank_rule_scope_scenario
    client = _authenticated_client(app, ids["admin"])

    response = client.post(
        f"/cash_management/bank-matching-rules/{ids['scoped_rule']}/run",
        data={
            "bank_account_id": ids["account_b"],
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "otra cuenta bancaria" in body
    assert "transacciones evaluadas" not in body


def test_service_rejects_account_from_another_company(bank_rule_scope_scenario):
    """The service itself refuses an account outside the rule's company (QA2 B2)."""
    app, ids = bank_rule_scope_scenario

    with app.app_context():
        with pytest.raises(BankStatementError):
            apply_bank_matching_rule(ids["company_rule"], ids["account_foreign"], (date(2026, 5, 1), date(2026, 5, 31)))
