# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1327: cada catálogo del selector exige el permiso de su módulo dueño.

Tener acceso a Compras o Ventas en una compañía no habilita los catálogos de
Contabilidad o Caja. Además, cuando se repite el parámetro `company`, se valida
el permiso del módulo para cada compañía, no solo para la primera.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
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


@pytest.fixture
def selector_module_scenario():
    """Create accounting and purchases readers with two granted companies."""
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
    company_alpha = f"a{suffix}"
    company_beta = f"b{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code=company_alpha,
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=company_beta,
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                User(
                    id=f"purchases-only-{suffix}",
                    user=f"purchases-only-{suffix}",
                    name="Compras",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=f"accounting-reader-{suffix}",
                    user=f"accounting-reader-{suffix}",
                    name="Contabilidad",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Accounts(
                    entity=company_alpha,
                    code=f"1100{suffix}",
                    name="Cuenta Alfa",
                    classification="asset",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity=company_beta,
                    code=f"1200{suffix}",
                    name="Cuenta Beta",
                    classification="asset",
                    active=True,
                    enabled=True,
                    group=False,
                ),
            ]
        )
        database.session.flush()
        purchases_module = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        accounting_module = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        purchases_role = Roles(name=f"purchases-only-{suffix}", note="Compras")
        accounting_role = Roles(name=f"accounting-reader-{suffix}", note="Contabilidad")
        database.session.add_all([purchases_role, accounting_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=purchases_role.id, module_id=purchases_module, access=True, view=True),
                RolesAccess(rol_id=accounting_role.id, module_id=accounting_module, access=True, view=True),
                RolesUser(user_id=f"purchases-only-{suffix}", role_id=purchases_role.id, active=True),
                RolesUser(user_id=f"accounting-reader-{suffix}", role_id=accounting_role.id, active=True),
                UserCompanyAccess(user_id=f"purchases-only-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"purchases-only-{suffix}", company_code=company_beta),
                UserCompanyAccess(user_id=f"accounting-reader-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"accounting-reader-{suffix}", company_code=company_beta),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_alpha_id": str(
                database.session.execute(database.select(Entity.id).filter_by(code=company_alpha)).scalar_one()
            ),
            "company_beta": company_beta,
            "alpha_account": f"1100{suffix}",
            "beta_account": f"1200{suffix}",
            "purchases_only": f"purchases-only-{suffix}",
            "accounting_reader": f"accounting-reader-{suffix}",
        }

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


def test_selector_rejects_account_catalog_without_accounting_permission(selector_module_scenario):
    """A purchases reader cannot read the accounting catalogue."""
    app, ids = selector_module_scenario
    client = _authenticated_client(app, ids["purchases_only"])

    response = client.get(f"/api/search-select?doctype=account&company={ids['company_alpha']}")

    assert response.status_code == 403
    assert ids["alpha_account"] not in response.get_data(as_text=True)


def test_selector_rejects_bank_catalog_without_cash_permission(selector_module_scenario):
    """A purchases reader cannot read the cash catalogue either."""
    app, ids = selector_module_scenario
    client = _authenticated_client(app, ids["purchases_only"])

    response = client.get(f"/api/search-select?doctype=bank_account&company={ids['company_alpha']}")

    assert response.status_code == 403


def test_selector_accepts_account_catalog_with_accounting_permission(selector_module_scenario):
    """An accounting reader receives the accounts of the requested company."""
    app, ids = selector_module_scenario
    client = _authenticated_client(app, ids["accounting_reader"])

    response = client.get(f"/api/search-select?doctype=account&company={ids['company_alpha']}")

    assert response.status_code == 200
    labels = " ".join(option["label"] for option in response.get_json()["results"])
    assert ids["alpha_account"] in labels
    assert ids["beta_account"] not in labels


def test_selector_validates_every_repeated_company_for_module_permission(selector_module_scenario, monkeypatch):
    """With repeated `company`, the module permission of each value is required."""
    import importlib

    api_module = importlib.import_module("cacao_accounting.api")

    app, ids = selector_module_scenario
    client = _authenticated_client(app, ids["accounting_reader"])
    monkeypatch.setattr(
        api_module,
        "_puede_consultar_modulo_compania",
        lambda module, company: company == ids["company_alpha"],
    )

    response = client.get(
        "/api/search-select?doctype=account" f"&company={ids['company_alpha']}&company={ids['company_beta']}"
    )

    assert response.status_code == 403


def test_selector_accepts_company_ulid_for_module_permission(selector_module_scenario):
    """El filtro por ULID de compañía no se rechaza si el usuario está autorizado."""
    app, ids = selector_module_scenario
    client = _authenticated_client(app, ids["accounting_reader"])

    response = client.get(f"/api/search-select?doctype=account&company={ids['company_alpha_id']}")

    assert response.status_code == 200
    labels = " ".join(option["label"] for option in response.get_json()["results"])
    assert ids["alpha_account"] in labels
