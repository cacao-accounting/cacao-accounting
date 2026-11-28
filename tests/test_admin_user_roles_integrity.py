# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1682/#2006: asignaciones de rol únicas y reemplazo serializado.

El reemplazo conserva las filas revocadas con `active=False`, no permite
duplicados por usuario/rol y serializa a los administradores concurrentes.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.auth.roles import asigna_rol_a_usuario, replace_user_roles
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Modules,
    Roles,
    RolesUser,
    User,
    database,
)

WORKERS = 2


@pytest.fixture
def roles_integrity_scenario(tmp_path):
    """Create an admin, a target user and three roles on file SQLite."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'roles-integrity.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"timeout": 30}},
        }
    )
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    classification="admin",
                ),
                User(
                    id=f"target-{suffix}",
                    user=f"target-{suffix}",
                    name="Usuario Objetivo",
                    password=b"unused",
                    active=True,
                ),
            ]
        )
        database.session.flush()
        roles = {}
        for name in ("role_a", "role_b", "role_c"):
            role = Roles(name=f"{name}-{suffix}", note=name)
            database.session.add(role)
            database.session.flush()
            roles[name] = role.id
        database.session.commit()
        ids = {
            "admin": f"admin-{suffix}",
            "target": f"target-{suffix}",
            "target_user": f"target-{suffix}",
            "roles": roles,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _assignments(app, user_id: str) -> dict[str, RolesUser]:
    """Return current assignments keyed by role id."""
    with app.app_context():
        rows = database.session.execute(database.select(RolesUser).filter_by(user_id=user_id)).scalars().all()
        return {row.role_id: row for row in rows}


def _active_roles(app, user_id: str) -> set[str]:
    """Return the active role ids for a user."""
    return {role_id for role_id, row in _assignments(app, user_id).items() if row.active}


def test_schema_rejects_duplicate_user_role_pairs(roles_integrity_scenario):
    """The database cannot store the same role twice for one user."""
    app, ids = roles_integrity_scenario
    role_id = ids["roles"]["role_a"]

    with app.app_context():
        database.session.add(RolesUser(user_id=ids["target"], role_id=role_id, active=True))
        database.session.flush()
        database.session.add(RolesUser(user_id=ids["target"], role_id=role_id, active=False))
        with pytest.raises(IntegrityError):
            database.session.flush()
        database.session.rollback()


def test_replace_roles_revokes_in_place_without_deleting(roles_integrity_scenario):
    """Removed roles keep their row and only change the active flag."""
    app, ids = roles_integrity_scenario
    roles = ids["roles"]

    with app.app_context():
        replace_user_roles(ids["target"], {roles["role_a"], roles["role_b"]})
        database.session.commit()
        before = {role_id: row.id for role_id, row in _assignments(app, ids["target"]).items()}
        replace_user_roles(ids["target"], {roles["role_b"], roles["role_c"]})
        database.session.commit()

    after = _assignments(app, ids["target"])
    assert set(after) == {roles["role_a"], roles["role_b"], roles["role_c"]}
    assert after[roles["role_a"]].active is False
    assert after[roles["role_b"]].active is True
    assert after[roles["role_c"]].active is True
    assert after[roles["role_a"]].id == before[roles["role_a"]]


def test_assign_role_reactivates_a_revoked_assignment(roles_integrity_scenario):
    """Reassigning an existing role reactivates it instead of duplicating."""
    app, ids = roles_integrity_scenario
    role_id = ids["roles"]["role_a"]

    with app.app_context():
        database.session.add(RolesUser(user_id=ids["target"], role_id=role_id, active=False))
        database.session.commit()
        role_name = database.session.get(Roles, role_id).name
        asigna_rol_a_usuario(ids["target_user"], role_name)

    assignments = _assignments(app, ids["target"])
    assert len(assignments) == 1
    assert assignments[role_id].active is True


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_admin_route_replaces_roles_without_server_error(roles_integrity_scenario):
    """The HTTP form can retain, revoke and change existing assignments."""
    app, ids = roles_integrity_scenario
    roles = ids["roles"]
    client = _authenticated_client(app, ids["admin"])
    path = f"/settings/users/{ids['target']}/roles"

    retained = client.post(path, data={"roles": [roles["role_a"], roles["role_b"]]})
    assert retained.status_code == 302
    assert _active_roles(app, ids["target"]) == {roles["role_a"], roles["role_b"]}

    changed = client.post(path, data={"roles": [roles["role_b"]]})
    assert changed.status_code == 302
    assert _active_roles(app, ids["target"]) == {roles["role_b"]}

    revoked = client.post(path, data={})
    assert revoked.status_code == 302
    assert _active_roles(app, ids["target"]) == set()
    assert set(_assignments(app, ids["target"])) == {roles["role_a"], roles["role_b"]}


def test_concurrent_replacements_do_not_mix_permissions(roles_integrity_scenario):
    """Two administrators settle on one complete selection, never a mix."""
    app, ids = roles_integrity_scenario
    roles = ids["roles"]
    barrier = Barrier(WORKERS)

    def replace(selected: set[str]) -> None:
        barrier.wait(timeout=20)
        with app.app_context():
            try:
                replace_user_roles(ids["target"], selected)
                database.session.commit()
            finally:
                database.session.remove()

    selections = [{roles["role_a"]}, {roles["role_b"]}]
    with ThreadPoolExecutor(max_workers=WORKERS) as workers:
        list(workers.map(replace, selections))

    active = _active_roles(app, ids["target"])
    assert active in selections
    assert len(_assignments(app, ids["target"])) == WORKERS
