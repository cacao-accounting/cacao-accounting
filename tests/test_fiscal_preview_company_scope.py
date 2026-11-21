# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#997: el preview fiscal autoriza la compañía del perfil resuelto.

Los alias de cobro y pago comparten perfiles con `payment_entry`; el control
debe aplicarse antes de calcular y nunca omitirse por un alias no mapeado.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

PREVIEW_URL = "/api/fiscal/preview"


@pytest.fixture
def fiscal_preview_scope_scenario():
    """Create a cash user scoped to alpha and a foreign company."""
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
                Modules(module="cash", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="other",
                    name="Otra",
                    company_name=f"Compañía Otra {suffix}",
                    tax_id=f"TAX-O-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            User(
                id=f"cashier-{suffix}",
                user=f"cashier-{suffix}",
                name="Cajero",
                password=b"unused",
                active=True,
                company="alpha",
            )
        )
        database.session.flush()
        cash_module = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        cash_role = Roles(name=f"preview-cash-{suffix}", note="Consulta de caja")
        database.session.add(cash_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=cash_role.id, module_id=cash_module, access=True, view=True),
                RolesUser(user_id=f"cashier-{suffix}", role_id=cash_role.id, active=True),
                UserCompanyAccess(user_id=f"cashier-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {"cashier": f"cashier-{suffix}"}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _payload(document_type: str, company: str, **extra) -> dict:
    """Build a minimal fiscal preview payload for the requested company."""
    return {
        "document_type": document_type,
        "company": company,
        "posting_date": "2026-05-10",
        "currency": "NIO",
        "lines": [{"quantity": 1, "unit_price": 100}],
        **extra,
    }


def test_collection_entry_alias_denies_foreign_company(fiscal_preview_scope_scenario):
    """The cobro alias cannot preview another company's fiscal rules (#997)."""
    app, ids = fiscal_preview_scope_scenario
    client = _authenticated_client(app, ids["cashier"])

    response = client.post(PREVIEW_URL, json=_payload("collection_entry", "other"))

    assert response.status_code == 403


def test_payment_entry_alias_resolves_collection_profile(fiscal_preview_scope_scenario):
    """`payment_entry` + receive resolves to the collection profile policy."""
    app, ids = fiscal_preview_scope_scenario
    client = _authenticated_client(app, ids["cashier"])

    response = client.post(PREVIEW_URL, json=_payload("payment_entry", "other", payment_type="receive"))

    assert response.status_code == 403


@pytest.mark.parametrize("document_type", ["bank_debit_note", "bank_credit_note", "bank_transfer"])
def test_bank_aliases_deny_foreign_company(fiscal_preview_scope_scenario, document_type):
    """Every banking alias keeps the cash-module company check."""
    app, ids = fiscal_preview_scope_scenario
    client = _authenticated_client(app, ids["cashier"])

    response = client.post(PREVIEW_URL, json=_payload(document_type, "other"))

    assert response.status_code == 403


def test_authorized_company_reaches_the_fiscal_calculation(fiscal_preview_scope_scenario):
    """The cash user is not blocked for its own company."""
    app, ids = fiscal_preview_scope_scenario
    client = _authenticated_client(app, ids["cashier"])

    response = client.post(PREVIEW_URL, json=_payload("collection_entry", "alpha"))

    assert response.status_code != 403


def test_every_fiscal_profile_has_an_explicit_company_policy():
    """Un perfil nuevo no puede quedar bloqueado por el fail-closed (QA2 B14)."""
    from cacao_accounting.api import (
        _FISCAL_PREVIEW_MODULES,
        _FISCAL_PREVIEW_SHARED_MODULES,
    )
    from cacao_accounting.fiscal_preview_service import _FISCAL_MATRIX

    policies = set(_FISCAL_PREVIEW_MODULES) | set(_FISCAL_PREVIEW_SHARED_MODULES)

    assert set(_FISCAL_MATRIX) <= policies
