# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Bank matching tolerances must be finite, integral where needed, and non-negative."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos.reconciliation_service import (
    BankReconciliationError,
    _candidate_tolerances,
    _resolve_rule_tolerances,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import BankMatchingRule, Currency, Entity, Modules, User, UserCompanyAccess, database


@pytest.fixture(name="matching_tolerance_app")
def matching_tolerance_app_fixture():
    """Create an isolated cloud company with an authenticated cash administrator."""
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
    user_id = f"admin-{suffix}"
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
                User(
                    id=user_id,
                    user=user_id,
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    company="alpha",
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=user_id, company_code="alpha"))
        database.session.commit()

    yield app, user_id

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _admin_client(app, user_id: str):
    """Return an HTTP client authenticated as the seeded administrator."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("days_tolerance", "-3"),
        ("days_tolerance", "not-an-integer"),
        ("amount_tolerance", "-10"),
        ("amount_tolerance", "Infinity"),
    ],
)
def test_rule_creation_rejects_invalid_tolerances_without_persisting(matching_tolerance_app, field, value):
    """Invalid tolerance inputs receive a controlled redirect and do not create a rule."""
    app, user_id = matching_tolerance_app
    client = _admin_client(app, user_id)
    name = f"Invalid tolerance {uuid4().hex[:6]}"

    response = client.post(
        "/cash_management/bank-matching-rules",
        data={
            "company": "alpha",
            "name": name,
            "days_tolerance": "7",
            "amount_tolerance": "0",
            field: value,
            "is_active": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(BankMatchingRule).filter_by(name=name)).scalar_one_or_none() is None


@pytest.mark.parametrize(
    ("days_tolerance", "amount_tolerance"),
    [(-2, Decimal("0")), (7, Decimal("-1")), (7, Decimal("Infinity"))],
)
def test_rule_resolution_rejects_invalid_persisted_tolerances(matching_tolerance_app, days_tolerance, amount_tolerance):
    """An invalid legacy rule cannot become a silent or unlimited matching rule."""
    app, _user_id = matching_tolerance_app
    with app.app_context():
        database.session.add(
            BankMatchingRule(
                company="alpha",
                name=f"Legacy invalid {uuid4().hex[:6]}",
                days_tolerance=days_tolerance,
                amount_tolerance=amount_tolerance,
                is_active=True,
            )
        )
        database.session.commit()

        with pytest.raises(BankReconciliationError, match="tolerancias inválidas"):
            _resolve_rule_tolerances(SimpleNamespace(bank_account_id=None), "alpha")


@pytest.mark.parametrize(
    ("days_tolerance", "amount_tolerance"),
    [(-1, Decimal("0")), (7, Decimal("-1")), (7, Decimal("Infinity"))],
)
def test_candidate_resolution_rejects_invalid_explicit_tolerances(days_tolerance, amount_tolerance):
    """Explicit service arguments cannot bypass the configured-rule validation."""
    with pytest.raises(BankReconciliationError, match="tolerancias inválidas"):
        _candidate_tolerances(SimpleNamespace(), "alpha", days_tolerance, amount_tolerance)


@pytest.mark.parametrize(
    ("days_tolerance", "amount_tolerance"),
    [(20000, Decimal("0")), (7, Decimal("1e20")), (7, Decimal("99999999999999999"))],
)
def test_candidate_resolution_rejects_unrepresentable_tolerances(days_tolerance, amount_tolerance):
    """#1688: valores fuera del rango de Integer/Numeric(20,4) se rechazan."""
    with pytest.raises(BankReconciliationError, match="tolerancias inválidas"):
        _candidate_tolerances(SimpleNamespace(), "alpha", days_tolerance, amount_tolerance)


def test_candidate_resolution_accepts_representable_tolerances():
    """Control positivo: valores dentro del rango son aceptados."""
    days, amount = _candidate_tolerances(SimpleNamespace(), "alpha", 30, Decimal("10.5000"))
    assert days == 30
    assert amount == Decimal("10.5000")
