# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2198: el selector de compañías acepta el filtro `company` con su ACL.

``GET /api/search-select?doctype=company&company=<código>`` debe devolver la
compañía solicitada cuando el usuario tiene acceso y rechazarla con 403 cuando
no lo tiene, en lugar de responder 400 por un filtro declarado no permitido.
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


@pytest.fixture
def search_select_company_scenario():
    """Create two companies and readers scoped to one of them."""
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
                    id=f"alpha-reader-{suffix}",
                    user=f"alpha-reader-{suffix}",
                    name="Lector Alfa",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        role = Roles(name=f"company-reader-{suffix}", note="Consulta de compañías")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=f"alpha-reader-{suffix}", role_id=role.id, active=True),
                UserCompanyAccess(user_id=f"alpha-reader-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"admin-{suffix}", company_code=company_alpha),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "alpha_reader": f"alpha-reader-{suffix}",
            "admin": f"admin-{suffix}",
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


def test_company_search_accepts_authorized_company_filter(search_select_company_scenario):
    """An authorized explicit company is filtered, not rejected as invalid."""
    app, ids = search_select_company_scenario
    client = _authenticated_client(app, ids["alpha_reader"])

    response = client.get(f"/api/search-select?doctype=company&company={ids['company_alpha']}")

    assert response.status_code == 200
    values = {option["value"] for option in response.get_json()["results"]}
    assert values == {ids["company_alpha"]}


def test_company_search_rejects_foreign_company_filter(search_select_company_scenario):
    """A foreign company keeps the 403 from the ACL layer."""
    app, ids = search_select_company_scenario
    client = _authenticated_client(app, ids["alpha_reader"])

    response = client.get(f"/api/search-select?doctype=company&company={ids['company_beta']}")

    assert response.status_code == 403


def test_company_search_rejects_unknown_company_filter(search_select_company_scenario):
    """An unknown company is also refused by the ACL layer."""
    app, ids = search_select_company_scenario
    client = _authenticated_client(app, ids["alpha_reader"])

    response = client.get("/api/search-select?doctype=company&company=NO-SUCH-COMPANY")

    assert response.status_code == 403


def test_company_search_without_filter_stays_scoped(search_select_company_scenario):
    """The unfiltered catalog still returns only authorized companies."""
    app, ids = search_select_company_scenario
    client = _authenticated_client(app, ids["alpha_reader"])

    response = client.get("/api/search-select?doctype=company")

    assert response.status_code == 200
    values = {option["value"] for option in response.get_json()["results"]}
    assert values == {ids["company_alpha"]}


def test_company_search_admin_respects_cloud_grants(search_select_company_scenario):
    """En Cloud el administrador también se limita a sus concesiones explícitas."""
    app, ids = search_select_company_scenario
    client = _authenticated_client(app, ids["admin"])

    granted = client.get(f"/api/search-select?doctype=company&company={ids['company_alpha']}")
    assert granted.status_code == 200
    assert {option["value"] for option in granted.get_json()["results"]} == {ids["company_alpha"]}

    denied = client.get(f"/api/search-select?doctype=company&company={ids['company_beta']}")
    assert denied.status_code == 403
