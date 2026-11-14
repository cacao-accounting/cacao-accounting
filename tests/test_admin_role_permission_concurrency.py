# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Concurrent role-permission replacements must keep one complete matrix."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Modules, Roles, RolesAccess, User, database

pytestmark = pytest.mark.database


@pytest.fixture
def role_permission_app(tmp_path):
    """Create an isolated SQLite database or use an opt-in external test database."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'role-permissions.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")

    engine_options = {**configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}), "pool_size": 4, "max_overflow": 0}
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": engine_options,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        suffix = uuid4().hex[:8]
        user = User(
            user=f"permission-admin-{suffix}",
            name="Administrador de permisos",
            password=b"business-test",
            classification="admin",
            active=True,
        )
        role = Roles(name=f"Role permissions {suffix}", note="Concurrent business test")
        module = Modules(module=f"permission-test-{suffix}", default=False, enabled=True)
        admin_module = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        created_admin_module = admin_module is None
        admin_module_was_enabled = admin_module.enabled if admin_module is not None else None
        if admin_module is None:
            admin_module = Modules(module="admin", default=False, enabled=True)
            database.session.add(admin_module)
        else:
            admin_module.enabled = True
        database.session.add_all([user, role, module])
        database.session.commit()
        user_id, role_id, module_id = str(user.id), role.id, module.id
        admin_module_id = admin_module.id

    yield app, user_id, role_id, module_id

    with app.app_context():
        database.session.execute(database.delete(RolesAccess).where(RolesAccess.rol_id == role_id))
        database.session.execute(database.delete(Roles).where(Roles.id == role_id))
        database.session.execute(database.delete(Modules).where(Modules.id == module_id))
        database.session.execute(database.delete(User).where(User.id == user_id))
        if created_admin_module:
            database.session.execute(database.delete(Modules).where(Modules.id == admin_module_id))
        elif admin_module_was_enabled is not None:
            database.session.execute(
                database.update(Modules).where(Modules.id == admin_module_id).values(enabled=admin_module_was_enabled)
            )
        database.session.commit()
        database.session.remove()
        database.engine.dispose()


def test_concurrent_admin_saves_leave_one_complete_role_permission_matrix(role_permission_app):
    """Two full replacements may leave either submitted matrix, never their union."""
    app, user_id, role_id, module_id = role_permission_app
    start_requests = Barrier(2)

    def save_permission(action: str) -> int:
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = user_id
            session["_fresh"] = True
        start_requests.wait(timeout=10)
        response = client.post(
            f"/settings/roles/{role_id}/permissions",
            data={f"perm_{module_id}_{action}": "on"},
            follow_redirects=False,
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(save_permission, ("access", "view")))

    assert responses == [302, 302]
    with app.app_context():
        permissions = (
            database.session.execute(
                database.select(RolesAccess).where(
                    RolesAccess.rol_id == role_id,
                    RolesAccess.module_id == module_id,
                )
            )
            .scalars()
            .all()
        )

    assert len(permissions) == 1
    assert (permissions[0].access, permissions[0].view) in {(True, False), (False, True)}
