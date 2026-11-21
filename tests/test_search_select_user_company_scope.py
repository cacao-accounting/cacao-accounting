# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1321: el catálogo de usuarios no revela cuentas fuera de la compañía.

``/api/search-select?doctype=user`` debe limitarse a los usuarios que
pertenecen o tienen acceso explícito a las compañías del solicitante. El
listado administrativo de usuarios del sistema conserva su guarda de
administrador.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, UserCompanyAccess, database


@pytest.fixture
def user_catalog_scenario():
    """Create users in two companies plus an inactive and a grant-less user."""
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
    names = {
        "requester": f"requester-{suffix}",
        "alpha_coworker": f"alpha-coworker-{suffix}",
        "alpha_cross": f"alpha-cross-{suffix}",
        "alpha_inactive": f"alpha-inactive-{suffix}",
        "beta_only": f"beta-only-{suffix}",
        "no_grants": f"no-grants-{suffix}",
    }

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
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
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id=names["requester"],
                    user=names["requester"],
                    name="Solicitante",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=names["alpha_coworker"],
                    user=names["alpha_coworker"],
                    name="Compañero Alfa",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=names["alpha_cross"],
                    user=names["alpha_cross"],
                    name="Cruzado Alfa",
                    password=b"unused",
                    active=True,
                    company=company_beta,
                ),
                User(
                    id=names["alpha_inactive"],
                    user=names["alpha_inactive"],
                    name="Inactivo Alfa",
                    password=b"unused",
                    active=False,
                    company=company_alpha,
                ),
                User(
                    id=names["beta_only"],
                    user=names["beta_only"],
                    name="Solo Beta",
                    password=b"unused",
                    active=True,
                    company=company_beta,
                ),
                User(
                    id=names["no_grants"],
                    user=names["no_grants"],
                    name="Sin Compañías",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id=names["requester"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["alpha_coworker"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["alpha_cross"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["alpha_inactive"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["beta_only"], company_code=company_beta),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            **names,
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


def test_user_catalog_lists_only_authorized_company_members(user_catalog_scenario):
    """Active users outside the requester's company scope stay hidden."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["requester"])

    response = client.get("/api/search-select?doctype=user")

    assert response.status_code == 200
    values = {option["value"] for option in response.get_json()["results"]}
    assert values == {ids["requester"], ids["alpha_coworker"], ids["alpha_cross"], ids["no_grants"]}
    assert ids["beta_only"] not in values
    assert ids["alpha_inactive"] not in values


def test_user_catalog_hides_foreign_user_even_with_search_term(user_catalog_scenario):
    """A targeted search for a foreign user returns no row."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["requester"])

    response = client.get(f"/api/search-select?doctype=user&q={ids['beta_only']}")

    assert response.status_code == 200
    assert response.get_json()["results"] == []


def test_user_catalog_includes_company_member_with_search_term(user_catalog_scenario):
    """A member of the authorized company is found by name."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["requester"])

    response = client.get(f"/api/search-select?doctype=user&q={ids['alpha_coworker']}")

    assert response.status_code == 200
    values = {option["value"] for option in response.get_json()["results"]}
    assert values == {ids["alpha_coworker"]}


def test_user_catalog_rejects_foreign_company_filter(user_catalog_scenario):
    """An explicit company outside the grant is refused by the ACL layer."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["requester"])

    response = client.get(f"/api/search-select?doctype=user&company={ids['company_beta']}")

    assert response.status_code == 403


def test_user_catalog_is_empty_without_company_grants(user_catalog_scenario):
    """A user without company grants receives no directory rows."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["no_grants"])

    response = client.get("/api/search-select?doctype=user")

    assert response.status_code == 200
    assert response.get_json()["results"] == []


def test_user_catalog_inactive_flag_keeps_company_scope(user_catalog_scenario):
    """Asking for inactive users does not widen the company scope."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["requester"])

    response = client.get("/api/search-select?doctype=user&active_only=false")

    assert response.status_code == 200
    values = {option["value"] for option in response.get_json()["results"]}
    assert ids["alpha_inactive"] in values
    assert ids["beta_only"] not in values


def test_admin_user_list_keeps_system_admin_guard(user_catalog_scenario):
    """The administrative user listing still requires the system admin role."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["requester"])

    response = client.get("/settings/users")

    assert response.status_code == 403


def test_user_catalog_company_filter_returns_only_that_company(user_catalog_scenario):
    """El filtro explícito devuelve solo usuarios vinculados a la compañía pedida."""
    app, ids = user_catalog_scenario
    client = _authenticated_client(app, ids["requester"])

    response = client.get(f"/api/search-select?doctype=user&company={ids['company_alpha']}")

    assert response.status_code == 200
    values = {option["value"] for option in response.get_json()["results"]}
    assert values == {ids["requester"], ids["alpha_coworker"], ids["alpha_cross"], ids["no_grants"]}
    assert ids["beta_only"] not in values
