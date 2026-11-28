# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1169: el listado de cierres fiscales respeta la compañía autorizada.

Años fiscales y selector de entidades se limitan al alcance de Contabilidad; un
filtro explícito de otra compañía responde 403.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    FiscalYear,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

LIST_PATH = "/accounting/fiscal_year_closing/list"


@pytest.fixture
def closing_scope_scenario():
    """Create fiscal years in two companies and a reader for one."""
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
    alpha_year = f"FA{suffix}"[:10]
    beta_year = f"FB{suffix}"[:10]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code=company_alpha,
                    name=f"Alfa {suffix}",
                    company_name=f"Alfa SA {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code=company_beta,
                    name=f"Beta {suffix}",
                    company_name=f"Beta SA {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                FiscalYear(
                    id=alpha_year,
                    entity=company_alpha,
                    name="2026",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
                ),
                FiscalYear(
                    id=beta_year,
                    entity=company_beta,
                    name="2026",
                    year_start_date=date(2026, 1, 1),
                    year_end_date=date(2026, 12, 31),
                    is_closed=False,
                ),
                User(
                    id=f"reader-{suffix}",
                    user=f"reader-{suffix}",
                    name="Contabilidad",
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
        role = Roles(name=f"closing-reader-{suffix}", note="Consulta contable")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=f"reader-{suffix}", role_id=role.id, active=True),
                UserCompanyAccess(user_id=f"reader-{suffix}", company_code=company_alpha),
                UserCompanyAccess(user_id=f"admin-{suffix}", company_code=company_alpha),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "alpha_year": alpha_year,
            "beta_year": beta_year,
            "alpha_name": f"Alfa {suffix}",
            "beta_name": f"Beta {suffix}",
            "reader": f"reader-{suffix}",
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


def test_closing_list_and_selector_only_show_authorized_company(closing_scope_scenario):
    """The listing and its company selector hide the foreign fiscal year."""
    app, ids = closing_scope_scenario
    client = _authenticated_client(app, ids["reader"])

    response = client.get(LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_year"] in body
    assert ids["beta_year"] not in body
    assert ids["alpha_name"] in body
    assert ids["beta_name"] not in body


def test_closing_list_rejects_foreign_company_filter(closing_scope_scenario):
    """An explicit company outside the grant is refused."""
    app, ids = closing_scope_scenario
    client = _authenticated_client(app, ids["reader"])

    response = client.get(f"{LIST_PATH}?company={ids['company_beta']}")

    assert response.status_code == 403
    assert ids["beta_year"] not in response.get_data(as_text=True)


def test_closing_list_admin_keeps_global_scope(closing_scope_scenario):
    """An administrator keeps both companies."""
    app, ids = closing_scope_scenario
    client = _authenticated_client(app, ids["admin"])

    response = client.get(LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_year"] in body
    assert ids["beta_year"] in body
