# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2011: una asignación de ventas revocada no conserva las listas de precios.

La gestión de precios exige un rol de ventas vigente además de la compañía.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from flask_login import login_user

from cacao_accounting import create_app
from cacao_accounting.admin.routes import _can_access_price_list_company
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    PriceList,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

PATH = "/settings/price-lists"


@pytest.fixture
def price_list_role_scenario():
    """Create active, revoked and unrelated users for a company."""
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
                Currency(code="USD", name="Dólar inactivo", decimals=2, active=False, default=False),
                Modules(module="admin", default=True, enabled=True),
                Modules(module="sales", default=True, enabled=True),
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
                    id=f"active-{suffix}",
                    user=f"active-{suffix}",
                    name="Gerente activo",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"revoked-{suffix}",
                    user=f"revoked-{suffix}",
                    name="Gerente revocado",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"member-{suffix}",
                    user=f"member-{suffix}",
                    name="Sin ventas",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
            ]
        )
        database.session.flush()
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        sales_role = Roles(name=f"sales_manager-{suffix}", note="Gerente de Ventas")
        database.session.add(sales_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True, edit=True),
                RolesUser(user_id=f"active-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"revoked-{suffix}", role_id=sales_role.id, active=False),
                UserCompanyAccess(user_id=f"active-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"revoked-{suffix}", company_code="alpha"),
                UserCompanyAccess(user_id=f"member-{suffix}", company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "active": f"active-{suffix}",
            "revoked": f"revoked-{suffix}",
            "member": f"member-{suffix}",
            "name": f"Lista Revocada {suffix}",
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


def test_active_sales_manager_can_open_price_lists(price_list_role_scenario):
    """An active sales manager keeps access to the price list screen."""
    app, ids = price_list_role_scenario
    client = _authenticated_client(app, ids["active"])

    assert client.get(PATH).status_code == 200


def test_revoked_sales_manager_cannot_open_or_write_price_lists(price_list_role_scenario):
    """A revoked sales-manager assignment loses listing and creation."""
    app, ids = price_list_role_scenario
    client = _authenticated_client(app, ids["revoked"])

    assert client.get(PATH).status_code == 403
    response = client.post(
        PATH,
        data={
            "name": ids["name"],
            "company": "alpha",
            "currency": "NIO",
            "is_selling": "y",
            "is_active": "y",
        },
    )
    assert response.status_code == 403
    with app.app_context():
        assert database.session.execute(database.select(PriceList).filter_by(name=ids["name"])).scalar_one_or_none() is None


def test_company_member_without_sales_role_cannot_manage_price_lists(price_list_role_scenario):
    """Company membership alone does not grant price-list management."""
    app, ids = price_list_role_scenario
    client = _authenticated_client(app, ids["member"])

    assert client.get(PATH).status_code == 403


def test_active_sales_manager_can_create_price_list(price_list_role_scenario):
    """The active manager persists a price list for its company."""
    app, ids = price_list_role_scenario
    client = _authenticated_client(app, ids["active"])

    response = client.post(
        PATH,
        data={
            "name": ids["name"],
            "company": "alpha",
            "currency": "NIO",
            "is_selling": "y",
            "is_active": "y",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        assert (
            database.session.execute(database.select(PriceList).filter_by(name=ids["name"])).scalar_one_or_none() is not None
        )


@pytest.mark.parametrize("company", ["beta", ""])
def test_active_sales_manager_cannot_create_outside_alpha(price_list_role_scenario, company):
    """El POST hacia otra compañía o una lista global se rechaza antes de guardar."""
    app, ids = price_list_role_scenario
    client = _authenticated_client(app, ids["active"])
    nombre = f"Fuera de alcance {uuid4().hex[:8]}"

    response = client.post(
        PATH,
        data={
            "name": nombre,
            "company": company,
            "currency": "NIO",
            "is_selling": "y",
            "is_active": "y",
        },
    )

    assert response.status_code == 403
    with app.app_context():
        assert database.session.execute(database.select(PriceList).filter_by(name=nombre)).scalar_one_or_none() is None


def test_price_list_rejects_inactive_currency(price_list_role_scenario):
    """Una moneda inactiva no se persiste como lista de precios."""
    app, ids = price_list_role_scenario
    client = _authenticated_client(app, ids["active"])
    nombre = f"Moneda inactiva {uuid4().hex[:8]}"

    response = client.post(
        PATH,
        data={
            "name": nombre,
            "company": "alpha",
            "currency": "USD",
            "is_selling": "y",
            "is_active": "y",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "La moneda seleccionada no existe o no está activa." in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(database.select(PriceList).filter_by(name=nombre)).scalar_one_or_none() is None


def test_company_membership_alone_is_not_enough_for_price_list_scope(price_list_role_scenario):
    """`_can_access_price_list_company` requires an active sales permission, not just the grant."""
    app, ids = price_list_role_scenario
    price_list = PriceList(name="Lista Alfa", company="alpha", currency="NIO")

    with app.test_request_context("/"):
        login_user(database.session.get(User, ids["member"]))
        assert _can_access_price_list_company(price_list) is False

    with app.test_request_context("/"):
        login_user(database.session.get(User, ids["active"]))
        assert _can_access_price_list_company(price_list) is True
