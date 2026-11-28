# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1104: los candidatos de conciliación exigen permiso de Caja.

El endpoint expone IDs, tercero y saldos de pagos; además del módulo comercial
del tercero, debe exigir consulta de Caja en la compañía solicitada.
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

PATH = "/api/document-flow/payment-reconciliation-candidates"


@pytest.fixture
def candidates_scope_scenario():
    """Create sales readers with and without cash permission."""
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
                Modules(module="sales", default=True, enabled=True),
                Modules(module="cash", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name=f"Alpha {suffix}",
                    tax_id=f"TAX-A-{suffix}",
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
        database.session.add_all(
            [
                User(
                    id=f"sales-{suffix}",
                    user=f"sales-{suffix}",
                    name="Ventas",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"sales-cash-{suffix}",
                    user=f"sales-cash-{suffix}",
                    name="Ventas y Caja",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        cash_module = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        sales_role = Roles(name=f"cand-sales-{suffix}", note="Ventas")
        cash_role = Roles(name=f"cand-cash-{suffix}", note="Caja")
        database.session.add_all([sales_role, cash_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesAccess(rol_id=cash_role.id, module_id=cash_module, access=True, view=True),
                RolesUser(user_id=f"sales-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"sales-cash-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"sales-cash-{suffix}", role_id=cash_role.id, active=True),
                UserCompanyAccess(user_id=f"sales-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"sales-cash-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {"sales": f"sales-{suffix}", "sales_cash": f"sales-cash-{suffix}"}

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


def test_candidates_reject_sales_reader_without_cash(candidates_scope_scenario):
    """Sales permission alone cannot read payment balances."""
    app, ids = candidates_scope_scenario
    client = _authenticated_client(app, ids["sales"])

    response = client.get(f"{PATH}?company=alpha&party_type=customer")

    assert response.status_code == 403


def test_candidates_accept_reader_with_sales_and_cash(candidates_scope_scenario):
    """Sales plus cash keeps the candidates endpoint available."""
    app, ids = candidates_scope_scenario
    client = _authenticated_client(app, ids["sales_cash"])

    response = client.get(f"{PATH}?company=alpha&party_type=customer")

    assert response.status_code == 200
    assert response.get_json() == {"documents": [], "payments": []}


def test_candidates_reject_company_outside_scope(candidates_scope_scenario):
    """An explicit company outside the cash scope is refused."""
    app, ids = candidates_scope_scenario
    client = _authenticated_client(app, ids["sales_cash"])

    response = client.get(f"{PATH}?company=beta&party_type=customer")

    assert response.status_code == 403
