# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#911: en Cloud la compañía de reportes es obligatoria y sin fallback.

Los dashboards envían la compañía activa en todos sus enlaces; una petición
sin compañía no asume la compañía predeterminada ni la única autorizada, y una
compañía ajena se rechaza por permisos.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from flask_login import login_user
from werkzeug.exceptions import HTTPException

from cacao_accounting import create_app
from cacao_accounting.company_context import ACTIVE_COMPANY_COOKIE
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
from cacao_accounting.decorators import resolve_required_company
from cacao_accounting.reportes.helpers import _resolve_company

DASHBOARDS = ("/accounting/", "/sales/", "/buying/", "/inventory/", "/cash_management/")


@pytest.fixture
def report_company_scenario():
    """Create two companies and users scoped to both or only beta."""
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
                *[
                    Modules(module=name, default=False, enabled=True)
                    for name in ("accounting", "sales", "purchases", "inventory", "cash")
                ],
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
                    code="beta",
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                User(
                    id=f"analista-{suffix}",
                    user=f"analista-{suffix}",
                    name="Analista",
                    password=b"unused",
                    active=True,
                    company="alpha",
                ),
                User(
                    id=f"solo-beta-{suffix}",
                    user=f"solo-beta-{suffix}",
                    name="Solo Beta",
                    password=b"unused",
                    active=True,
                    company="beta",
                ),
            ]
        )
        database.session.flush()
        modules = {
            module: database.session.execute(database.select(Modules.id).filter_by(module=module)).scalar_one()
            for module in ("accounting", "sales", "purchases", "inventory", "cash")
        }
        roles = {}
        for module, module_id in modules.items():
            role = Roles(name=f"reports-{module}-{suffix}", note=f"Consulta de {module}")
            database.session.add(role)
            database.session.flush()
            database.session.add(
                RolesAccess(
                    rol_id=role.id,
                    module_id=module_id,
                    access=True,
                    view=True,
                    report=True,
                )
            )
            roles[module] = role.id
        analyst = f"analista-{suffix}"
        solo_beta = f"solo-beta-{suffix}"
        for module_role in roles.values():
            database.session.add(RolesUser(user_id=analyst, role_id=module_role, active=True))
            database.session.add(RolesUser(user_id=solo_beta, role_id=module_role, active=True))
        database.session.add_all(
            [
                UserCompanyAccess(user_id=analyst, company_code="alpha"),
                UserCompanyAccess(user_id=analyst, company_code="beta"),
                UserCompanyAccess(user_id=solo_beta, company_code="beta"),
            ]
        )
        database.session.commit()
        ids = {"analyst": analyst, "solo_beta": solo_beta}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(app, user_id: str):
    """Open a request context with the requested user logged in."""
    user = database.session.get(User, user_id)
    login_user(user, remember=False, force=True)


def _abort_code(callable_) -> int:
    """Return the HTTP status raised by an aborting callable."""
    with pytest.raises(HTTPException) as excinfo:
        callable_()
    return int(excinfo.value.code)


def test_cloud_requires_company_even_with_a_single_authorized_company(report_company_scenario):
    """One authorized company is not a reason to assume it in Cloud."""
    app, ids = report_company_scenario

    with app.test_request_context("/"):
        _login(app, ids["solo_beta"])
        assert _abort_code(lambda: resolve_required_company(None, "accounting")) == 400


def test_cloud_requires_company_with_several_authorized_companies(report_company_scenario):
    """A multi-company user must name the company explicitly."""
    app, ids = report_company_scenario

    with app.test_request_context("/"):
        _login(app, ids["analyst"])
        assert _abort_code(lambda: resolve_required_company(None, "accounting")) == 400
        assert resolve_required_company("beta", "accounting") == "beta"


def test_desktop_resolves_the_single_authorized_company(report_company_scenario):
    """Desktop keeps its single-company navigation."""
    app, ids = report_company_scenario

    app.config["MODO_ESCRITORIO"] = True
    try:
        with app.test_request_context("/"):
            _login(app, ids["solo_beta"])
            assert resolve_required_company(None, "accounting") == "beta"
    finally:
        app.config["MODO_ESCRITORIO"] = False


def test_desktop_without_a_single_company_fails_closed(report_company_scenario):
    """Desktop with several grants still demands an explicit company."""
    app, ids = report_company_scenario

    app.config["MODO_ESCRITORIO"] = True
    try:
        with app.test_request_context("/"):
            _login(app, ids["analyst"])
            assert _abort_code(lambda: resolve_required_company(None, "accounting")) == 400
    finally:
        app.config["MODO_ESCRITORIO"] = False


def test_unknown_company_does_not_fall_back_to_the_default_company(report_company_scenario):
    """A typo returns 400 instead of silently reading the default company."""
    app, ids = report_company_scenario

    with app.test_request_context("/"):
        _login(app, ids["analyst"])
        assert _abort_code(lambda: _resolve_company("missing", "accounting")) == 400


def test_company_without_access_is_rejected_without_default_fallback(report_company_scenario):
    """A user without alpha never reads alpha, even if alpha is the default."""
    app, ids = report_company_scenario

    with app.test_request_context("/"):
        _login(app, ids["solo_beta"])
        assert _abort_code(lambda: _resolve_company("alpha", "accounting")) == 403
        assert _resolve_company("beta", "accounting") == "beta"


@pytest.mark.parametrize("path", DASHBOARDS)
def test_dashboard_report_links_carry_the_active_company(report_company_scenario, path):
    """Every dashboard link includes the active company selected in the cookie."""
    app, ids = report_company_scenario
    app.config["MODO_ESCRITORIO"] = False
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = ids["analyst"]
        session["_fresh"] = True
    client.set_cookie(ACTIVE_COMPANY_COOKIE, "beta", domain="localhost")

    response = client.get(path)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "company=beta" in body
    assert "company=alpha" not in body
    if path == "/buying/":
        # Las conciliaciones de compras también resuelven compañía obligatoria.
        assert "/buying/purchase-reconciliation/panel?company=beta" in body
        assert "/buying/purchase-reconciliation?company=beta" in body
