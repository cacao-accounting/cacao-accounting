# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1600: el dashboard exige la acción de consulta del módulo.

Un rol con `access=True` y `view=False` no recibe datos del dashboard, ni
siquiera para una compañía a la que tiene concesión explícita. Un rol con
consulta sí recibe la sección de Contabilidad.
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

DASHBOARD_PATH = "/api/dashboard/data"


@pytest.fixture
def dashboard_permission_scenario():
    """Create an access-only and a read-only accounting user."""
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
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        access_role = Roles(name=f"dashboard-access-{suffix}", note="Solo acceso")
        viewer_role = Roles(name=f"dashboard-view-{suffix}", note="Consulta contable")
        database.session.add_all([access_role, viewer_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=access_role.id, module_id=module_id, access=True),
                RolesAccess(rol_id=viewer_role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=f"access-only-{suffix}", role_id=access_role.id, active=True),
                RolesUser(user_id=f"viewer-{suffix}", role_id=viewer_role.id, active=True),
                UserCompanyAccess(user_id=f"access-only-{suffix}", company_code=company),
                UserCompanyAccess(user_id=f"viewer-{suffix}", company_code=company),
            ]
        )
        database.session.commit()
        ids = {
            "company": company,
            "access_only": f"access-only-{suffix}",
            "viewer": f"viewer-{suffix}",
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


def test_dashboard_rejects_access_without_view_permission(dashboard_permission_scenario):
    """Access without view cannot read dashboard KPIs for a granted company."""
    app, ids = dashboard_permission_scenario
    client = _authenticated_client(app, ids["access_only"])

    response = client.get(f"{DASHBOARD_PATH}?company={ids['company']}")

    assert response.status_code == 403
    assert "kpis" not in response.get_data(as_text=True)


def test_dashboard_exposes_accounting_section_with_view_permission(dashboard_permission_scenario):
    """A reader sees the accounting section and hides other modules."""
    app, ids = dashboard_permission_scenario
    client = _authenticated_client(app, ids["viewer"])

    response = client.get(f"{DASHBOARD_PATH}?company={ids['company']}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["sections"]["accounting"]["visible"] is True
    assert payload["sections"]["accounting"]["badge"] != "Oculto por permisos"
    assert payload["sections"]["banks"]["visible"] is False
    assert payload["sections"]["purchases"]["visible"] is False
    assert payload["sections"]["inventory"]["visible"] is False
    assert payload["sections"]["sales"]["visible"] is False
