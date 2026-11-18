# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1640: la edición de precios ignora vínculos de rol desactivados.

`is_sales_price_editor` debe conceder acceso solo con una asignación activa al
rol de gerente de ventas, o a un administrador.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Roles, RolesUser, User, database
from cacao_accounting.ventas.services import is_sales_price_editor


@pytest.fixture
def price_editor_scenario():
    """Create users with active, revoked and unrelated sales roles."""
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
                User(
                    id=f"active-{suffix}",
                    user=f"active-{suffix}",
                    name="Gerente activo",
                    password=b"unused",
                    active=True,
                    classification="user",
                ),
                User(
                    id=f"revoked-{suffix}",
                    user=f"revoked-{suffix}",
                    name="Gerente revocado",
                    password=b"unused",
                    active=True,
                    classification="user",
                ),
                User(
                    id=f"other-{suffix}",
                    user=f"other-{suffix}",
                    name="Otro rol",
                    password=b"unused",
                    active=True,
                    classification="user",
                ),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        sales_role = Roles(name=f"sales_manager-{suffix}", note="Gerente de Ventas")
        other_role = Roles(name=f"accountant-{suffix}", note="Contador")
        database.session.add_all([sales_role, other_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesUser(user_id=f"active-{suffix}", role_id=sales_role.id, active=True),
                RolesUser(user_id=f"revoked-{suffix}", role_id=sales_role.id, active=False),
                RolesUser(user_id=f"other-{suffix}", role_id=other_role.id, active=True),
            ]
        )
        database.session.commit()
        ids = {
            "active": f"active-{suffix}",
            "revoked": f"revoked-{suffix}",
            "other": f"other-{suffix}",
            "admin": f"admin-{suffix}",
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_active_sales_manager_can_edit_prices(price_editor_scenario):
    """An active sales-manager assignment grants price editing."""
    app, ids = price_editor_scenario

    with app.app_context():
        assert is_sales_price_editor(ids["active"]) is True


def test_revoked_sales_manager_cannot_edit_prices(price_editor_scenario):
    """A revoked assignment loses price editing (#1640)."""
    app, ids = price_editor_scenario

    with app.app_context():
        assert is_sales_price_editor(ids["revoked"]) is False


def test_unrelated_role_and_admin_behavior(price_editor_scenario):
    """Other roles are denied and the administrator keeps the bypass."""
    app, ids = price_editor_scenario

    with app.app_context():
        assert is_sales_price_editor(ids["other"]) is False
        assert is_sales_price_editor(ids["admin"]) is True
        assert is_sales_price_editor(None) is False
