# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1601: las rutas POST de Contabilidad exigen la acción del módulo.

Un rol con acceso y consulta no puede crear, editar, importar, aprobar,
cerrar ni anular por las rutas administrativas de contabilidad.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    database,
)

WRITE_REQUESTS = (
    ("post", "/accounting/currency/NIO/toggle-active"),
    ("get", "/accounting/exchange/new"),
    ("get", "/accounting/exchange/import"),
    ("get", "/accounting/journal/recurring/new"),
    ("post", "/accounting/journal/recurring/MISSING/approve"),
    ("post", "/accounting/journal/recurring/MISSING/cancel"),
    ("get", "/accounting/naming-series/new"),
    ("get", "/accounting/naming-series/MISSING/edit"),
    ("post", "/accounting/naming-series/MISSING/toggle-default"),
    ("post", "/accounting/naming-series/MISSING/toggle-active"),
    ("get", "/accounting/external-counter/new"),
    ("get", "/accounting/external-counter/MISSING/edit"),
    ("get", "/accounting/external-counter/MISSING/adjust"),
    ("post", "/accounting/external-counter/MISSING/toggle-active"),
    ("post", "/accounting/period-close/monthly/MISSING/project-capitalization"),
    ("post", "/accounting/period-close/monthly/MISSING/close"),
    ("post", "/accounting/exchange-revaluation/MISSING/void"),
    ("get", "/accounting/entity/set_active/MISSING"),
    ("get", "/accounting/journal/new"),
    ("post", "/accounting/period-close/monthly/MISSING/exchange-revaluation"),
    ("get", "/accounting/exchange-revaluation/new"),
    ("post", "/accounting/cash-flow-config"),
    ("get", "/accounting/balance-confirmations/new"),
)

FULL_PERMISSIONS = {
    "access": True,
    "view": True,
    "create": True,
    "edit": True,
    "delete": True,
    "import_": True,
    "approve": True,
    "set_null": True,
    "close": True,
    "request": True,
    "setup": True,
}


@pytest.fixture
def accounting_write_scenario():
    """Create a read-only and a fully-authorized accounting user."""
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
                Modules(module="accounting", default=False, enabled=True),
                User(
                    id=f"reader-{suffix}",
                    user=f"reader-{suffix}",
                    name="Lector",
                    password=b"unused",
                    active=True,
                ),
                User(
                    id=f"editor-{suffix}",
                    user=f"editor-{suffix}",
                    name="Editor",
                    password=b"unused",
                    active=True,
                ),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="accounting")).scalar_one()
        reader_role = Roles(name=f"accounting-reader-{suffix}", note="Consulta")
        editor_role = Roles(name=f"accounting-editor-{suffix}", note="Escritura")
        database.session.add_all([reader_role, editor_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=reader_role.id, module_id=module_id, access=True, view=True),
                RolesAccess(rol_id=editor_role.id, module_id=module_id, **FULL_PERMISSIONS),
                RolesUser(user_id=f"reader-{suffix}", role_id=reader_role.id, active=True),
                RolesUser(user_id=f"editor-{suffix}", role_id=editor_role.id, active=True),
            ]
        )
        database.session.commit()
        ids = {"reader": f"reader-{suffix}", "editor": f"editor-{suffix}"}

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


@pytest.mark.parametrize(("method", "path"), WRITE_REQUESTS)
def test_read_only_role_is_denied_on_accounting_writes(accounting_write_scenario, method, path):
    """Access plus view is not enough for state-changing accounting routes."""
    app, ids = accounting_write_scenario
    client = _authenticated_client(app, ids["reader"])

    response = getattr(client, method)(path)

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path"), WRITE_REQUESTS)
def test_authorized_role_reaches_the_accounting_route(accounting_write_scenario, method, path):
    """The matching action permission opens the route (data may still be missing)."""
    app, ids = accounting_write_scenario
    client = _authenticated_client(app, ids["editor"])

    response = getattr(client, method)(path)

    assert response.status_code != 403
