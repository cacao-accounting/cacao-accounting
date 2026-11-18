# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Smoke de modo Desktop para las rutas con alcance de compañía.

En Desktop solo existe SQLite y una compañía; las guardas de módulo y de
alcance no deben romper los listados tocados por los lotes de Fase 1.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database


@pytest.fixture
def desktop_app():
    """Create a desktop-mode app with one company and an admin user."""
    suffix = uuid4().hex[:6]
    company = f"d{suffix}"
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="inventory", default=True, enabled=True),
                Modules(module="cash", default=True, enabled=True),
                Entity(
                    code=company,
                    name="Escritorio",
                    company_name=f"Compañía Escritorio {suffix}",
                    tax_id=f"TAX-D-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id=f"desktop-admin-{suffix}",
                    user=f"desktop-admin-{suffix}",
                    name="Administrador Escritorio",
                    password=b"unused",
                    active=True,
                    company=company,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
        user_id = f"desktop-admin-{suffix}"

    yield app, user_id

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the seeded desktop admin."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_desktop_mode_serves_scoped_lists(desktop_app):
    """Desktop keeps serving the module lists after the company-scope guards."""
    app, user_id = desktop_app
    client = _authenticated_client(app, user_id)

    for path in (
        "/inventory/item/list",
        "/inventory/stock-entry/list",
        "/cash_management/bank-transaction/list",
        "/cash_management/petty-cash/list",
    ):
        assert client.get(path).status_code == 200, path


def test_desktop_mode_user_selector_returns_the_local_directory(desktop_app):
    """Desktop user selector has no Cloud grants and still resolves the local user."""
    app, user_id = desktop_app
    client = _authenticated_client(app, user_id)

    response = client.get("/api/search-select?doctype=user")

    assert response.status_code == 200
    assert user_id in {option["value"] for option in response.get_json()["results"]}
