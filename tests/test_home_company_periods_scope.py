# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1558: la portada solo serializa períodos de compañías autorizadas.

El HTML inicial no debe contener IDs, nombres ni fechas de períodos de otra
compañía, aunque el selector los filtre en JavaScript.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
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


@pytest.fixture
def home_periods_scenario():
    """Create one accounting period per company and scoped users."""
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
    alpha_period = f"P-ALPHA-{suffix}"
    beta_period = f"P-BETA-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code="alpha",
                    name=f"Alfa {suffix}",
                    company_name=f"Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name=f"Beta {suffix}",
                    company_name=f"Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        alpha_year = FiscalYear(
            id=f"FY-A-{suffix}",
            entity="alpha",
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        beta_year = FiscalYear(
            id=f"FY-B-{suffix}",
            entity="beta",
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add_all([alpha_year, beta_year])
        database.session.flush()
        database.session.add_all(
            [
                AccountingPeriod(
                    id=alpha_period,
                    entity="alpha",
                    fiscal_year_id=alpha_year.id,
                    name="Mayo Alfa",
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                    enabled=True,
                    is_closed=False,
                ),
                AccountingPeriod(
                    id=beta_period,
                    entity="beta",
                    fiscal_year_id=beta_year.id,
                    name="Mayo Beta Secreto",
                    start=date(2026, 5, 1),
                    end=date(2026, 5, 31),
                    enabled=True,
                    is_closed=False,
                ),
                User(
                    id=f"reader-{suffix}",
                    user=f"reader-{suffix}",
                    name="Lectora",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    company="alpha",
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        role = Roles(name=f"home-reader-{suffix}", note="Consulta contable")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=f"reader-{suffix}", role_id=role.id, active=True),
                UserCompanyAccess(user_id=f"reader-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"admin-{suffix}", company_code="alpha"),
                # #1828: el escenario "admin ve todas" exige acceso explícito.
                UserCompanyAccess(user_id=f"admin-{suffix}", company_code="beta"),
            ]
        )
        database.session.commit()
        ids = {
            "alpha_period": alpha_period,
            "beta_period": beta_period,
            "beta_name": "Mayo Beta Secreto",
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


def test_home_omits_periods_from_unauthorized_companies(home_periods_scenario):
    """The home HTML only contains periods of the authorized company."""
    app, ids = home_periods_scenario
    client = _authenticated_client(app, ids["reader"])

    response = client.get("/app")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_period"] in body
    assert ids["beta_period"] not in body
    assert ids["beta_name"] not in body


def test_home_admin_receives_every_enabled_company_period(home_periods_scenario):
    """An administrator keeps the global period list."""
    app, ids = home_periods_scenario
    client = _authenticated_client(app, ids["admin"])

    response = client.get("/app")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_period"] in body
    assert ids["beta_period"] in body
