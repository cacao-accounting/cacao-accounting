"""#1767/#2231: el sistema no debe quedar sin administradores activos."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.admin.services import (
    _lock_last_admin_users,
    _would_leave_no_admin,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import Modules, Roles, RolesUser, User, database

WORKERS = 2


@pytest.fixture
def last_admin_app(tmp_path):
    suffix = uuid4().hex[:8]
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'last-admin.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"timeout": 30}},
        }
    )
    ids = {}
    with app.app_context():
        database.create_all()
        database.session.add(Modules(module="admin", default=False, enabled=True))
        admin_role = Roles(name=f"admin-{suffix}", note="admin")
        database.session.add(admin_role)
        database.session.flush()
        for label in ("a", "b"):
            user_id = f"admin-{label}-{suffix}"
            user = User(
                id=user_id,
                user=user_id,
                name=f"Admin {label}",
                password=b"unused",
                active=True,
                classification="admin",
            )
            database.session.add(user)
            database.session.flush()
            database.session.add(RolesUser(user_id=user_id, role_id=admin_role.id, active=True))
            ids[label] = user_id
        ids["admin_role"] = admin_role.id
        database.session.commit()

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _active_admin_total(app) -> int:
    from sqlalchemy import func, or_, select

    with app.app_context():
        admin_role = database.session.execute(select(Roles.id).where(Roles.name.like("admin-%"))).scalars().first()
        conds = [User.classification == "admin"]
        if admin_role:
            conds.append(
                User.id.in_(select(RolesUser.user_id).where(RolesUser.role_id == admin_role, RolesUser.active.is_(True)))
            )
        return int(
            database.session.execute(select(func.count(User.id)).where(User.active.is_(True), or_(*conds))).scalar() or 0
        )


def test_rejects_deactivating_the_only_active_admin(last_admin_app):
    app, ids = last_admin_app
    with app.app_context():
        # Leave only admin "a" as active admin.
        user_b = database.session.get(User, ids["b"])
        user_b.active = False
        database.session.commit()

        user_a = database.session.get(User, ids["a"])
        _lock_last_admin_users(user_a.id)
        assert _would_leave_no_admin(user_a, active=False, classification=user_a.classification) is True
        database.session.rollback()

    assert _active_admin_total(app) == 1


def test_rejects_removing_last_admin_role_assignment(last_admin_app):
    app, ids = last_admin_app
    with app.app_context():
        user_b = database.session.get(User, ids["b"])
        user_b.classification = "system"
        database.session.execute(
            database.update(RolesUser)
            .where(RolesUser.user_id == ids["b"], RolesUser.role_id == ids["admin_role"])
            .values(active=False)
        )
        database.session.commit()

        user_a = database.session.get(User, ids["a"])
        _lock_last_admin_users(user_a.id)
        remaining_roles = set()
        assert (
            _would_leave_no_admin(
                user_a,
                active=True,
                classification="system",
                role_ids=remaining_roles,
            )
            is True
        )
        database.session.rollback()

    assert _active_admin_total(app) == 1


def test_concurrent_demotions_cannot_remove_all_admins(last_admin_app):
    app, ids = last_admin_app
    barrier = Barrier(WORKERS)

    def demote(user_key: str) -> str:
        with app.app_context():
            barrier.wait()
            user_id = ids[user_key]
            _lock_last_admin_users(user_id)
            user = database.session.get(User, user_id)
            if _would_leave_no_admin(user, active=True, classification="system", role_ids=set()):
                database.session.rollback()
                return "rejected"
            user.classification = "system"
            database.session.execute(
                database.update(RolesUser)
                .where(RolesUser.user_id == user_id, RolesUser.role_id == ids["admin_role"])
                .values(active=False)
            )
            database.session.commit()
            return "ok"

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(demote, ["a", "b"]))

    assert sorted(results) == ["ok", "rejected"]
    assert _active_admin_total(app) == 1
