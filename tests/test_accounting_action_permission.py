# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1601: crear una moneda exige el permiso de acción, no solo acceso.

Un rol con `access=True` y `create=False` no puede persistir una moneda; el
`POST /accounting/currency/new` debe responder 403 sin mutar el catálogo.
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

CURRENCY_NEW_PATH = "/accounting/currency/new"


@pytest.fixture
def accounting_action_scenario():
    """Create accounting users with access-only, view and create permissions."""
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
    company = f"c{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(
                    code=company,
                    name="Compañía",
                    company_name=f"Compañía {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id=f"access-only-{suffix}",
                    user=f"access-only-{suffix}",
                    name="Solo acceso",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
                User(
                    id=f"viewer-{suffix}",
                    user=f"viewer-{suffix}",
                    name="Consulta contable",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
                User(
                    id=f"creator-{suffix}",
                    user=f"creator-{suffix}",
                    name="Alta contable",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        access_role = Roles(name=f"access-only-{suffix}", note="Solo acceso")
        viewer_role = Roles(name=f"viewer-{suffix}", note="Consulta contable")
        creator_role = Roles(name=f"creator-{suffix}", note="Alta contable")
        database.session.add_all([access_role, viewer_role, creator_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=access_role.id, module_id=module_id, access=True),
                RolesAccess(rol_id=viewer_role.id, module_id=module_id, access=True, view=True),
                RolesAccess(rol_id=creator_role.id, module_id=module_id, access=True, view=True, create=True),
                RolesUser(user_id=f"access-only-{suffix}", role_id=access_role.id, active=True),
                RolesUser(user_id=f"viewer-{suffix}", role_id=viewer_role.id, active=True),
                RolesUser(user_id=f"creator-{suffix}", role_id=creator_role.id, active=True),
                UserCompanyAccess(user_id=f"access-only-{suffix}", company_code=company),
                UserCompanyAccess(user_id=f"viewer-{suffix}", company_code=company),
                UserCompanyAccess(user_id=f"creator-{suffix}", company_code=company),
            ]
        )
        database.session.commit()
        ids = {
            "company": company,
            "access_only": f"access-only-{suffix}",
            "viewer": f"viewer-{suffix}",
            "creator": f"creator-{suffix}",
            "currency_code": f"TST-{suffix}",
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


def test_currency_creation_requires_create_permission(accounting_action_scenario):
    """Access without create cannot persist a currency."""
    app, ids = accounting_action_scenario
    client = _authenticated_client(app, ids["access_only"])

    response = client.post(
        CURRENCY_NEW_PATH,
        data={"code": ids["currency_code"], "name": "Moneda No Autorizada", "decimals": "2"},
    )

    assert response.status_code == 403
    with app.app_context():
        assert (
            database.session.execute(database.select(Currency).filter_by(code=ids["currency_code"])).scalar_one_or_none()
            is None
        )


def test_currency_creation_rejects_read_only_role(accounting_action_scenario):
    """View without create is still denied and does not mutate."""
    app, ids = accounting_action_scenario
    client = _authenticated_client(app, ids["viewer"])

    response = client.post(
        CURRENCY_NEW_PATH,
        data={"code": ids["currency_code"], "name": "Moneda de Lectura", "decimals": "2"},
    )

    assert response.status_code == 403
    with app.app_context():
        assert (
            database.session.execute(database.select(Currency).filter_by(code=ids["currency_code"])).scalar_one_or_none()
            is None
        )


def test_currency_creation_works_with_create_permission(accounting_action_scenario):
    """A role with create keeps the normal flow."""
    app, ids = accounting_action_scenario
    client = _authenticated_client(app, ids["creator"])

    response = client.post(
        CURRENCY_NEW_PATH,
        data={"code": ids["currency_code"], "name": "Moneda Autorizada", "decimals": "2"},
    )

    assert response.status_code == 302
    with app.app_context():
        assert (
            database.session.execute(database.select(Currency).filter_by(code=ids["currency_code"])).scalar_one_or_none()
            is not None
        )
