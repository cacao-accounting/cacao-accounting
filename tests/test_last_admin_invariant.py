"""#1767/#2231: el sistema no debe quedar sin administradores activos."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from cacao_accounting import create_app
from cacao_accounting.admin import services
from cacao_accounting.admin.services import (
    _acquire_last_admin_lock,
    _commit_last_admin_transition,
    _lock_last_admin_users,
    _would_leave_no_admin,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import Modules, Roles, RolesUser, User, database

WORKERS = 2

pytestmark = pytest.mark.database

LAST_ADMIN_MESSAGE = "El sistema debe conservar al menos un administrador activo."


def _database_uri(tmp_path) -> str:
    """Usa SQLite temporal o el motor externo dedicado de CI."""
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        return f"sqlite:///{tmp_path / 'last-admin.sqlite'}"
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    return uri


def _engine_options() -> dict[str, object]:
    """Ajusta el pool para concurrencia real o el timeout de SQLite."""
    if str(configuracion["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite"):
        return {"connect_args": {"timeout": 30}}
    return {"pool_size": 4, "max_overflow": 0}


def _crear_app(tmp_path):
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": _database_uri(tmp_path),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SQLALCHEMY_ENGINE_OPTIONS": _engine_options(),
        }
    )


@pytest.fixture
def last_admin_app(tmp_path, isolated_admin_registry):
    """Dos administradores por clasificación en la base dedicada de la prueba."""
    app = _crear_app(tmp_path)
    suffix = uuid4().hex[:8]
    ids = {}
    with isolated_admin_registry(app):
        with app.app_context():
            database.create_all()
            if database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none() is None:
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
            database.session.execute(database.delete(RolesUser).where(RolesUser.user_id.in_([ids["a"], ids["b"]])))
            database.session.execute(database.delete(User).where(User.id.in_([ids["a"], ids["b"]])))
            database.session.execute(database.delete(Roles).where(Roles.id == ids["admin_role"]))
            database.session.commit()
            database.session.remove()
            database.engine.dispose()


@pytest.fixture
def single_admin_app(tmp_path, request, isolated_admin_registry):
    """Escenario con un único administrador y sin otros privilegiados."""
    parametros = getattr(request, "param", {})
    classification = parametros.get("classification", "admin")
    with_role = parametros.get("with_role", False)
    app = _crear_app(tmp_path)
    suffix = uuid4().hex[:8]
    user_id = f"sole-{suffix}"
    username = f"sole-{suffix}"
    with isolated_admin_registry(app):
        with app.app_context():
            database.create_all()
            modulo_admin = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
            if modulo_admin is None:
                database.session.add(Modules(module="admin", default=False, enabled=True))
            else:
                modulo_admin.enabled = True
            database.session.add(
                User(
                    id=user_id,
                    user=username,
                    name="Administrador único",
                    password=b"unused",
                    active=True,
                    classification=classification,
                )
            )
            if with_role:
                admin_role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one_or_none()
                if admin_role is None:
                    admin_role = Roles(name="admin", note="admin")
                    database.session.add(admin_role)
                    database.session.flush()
                database.session.add(RolesUser(user_id=user_id, role_id=admin_role.id, active=True))
            database.session.commit()
        yield app, user_id, username


def _authenticated(app, user_id: str):
    """Cliente HTTP autenticado como el usuario indicado."""
    with app.app_context():
        auth_version = database.session.get(User, user_id).auth_version
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


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


@pytest.mark.parametrize("single_admin_app", [{}], indirect=True)
def test_toggle_http_rechaza_desactivar_al_ultimo_admin(single_admin_app):
    """POST real al listado: el último administrador no puede desactivarse."""
    app, user_id, _ = single_admin_app
    client = _authenticated(app, user_id)

    response = client.post(
        "/settings/users",
        data={"user_id": user_id, "action": "toggle"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert LAST_ADMIN_MESSAGE in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.get(User, user_id).active is True


@pytest.mark.parametrize("single_admin_app", [{}], indirect=True)
def test_edicion_http_rechaza_desclasificar_al_ultimo_admin(single_admin_app):
    """POST real a la edición: el último administrador conserva su clasificación."""
    app, user_id, username = single_admin_app
    client = _authenticated(app, user_id)

    response = client.post(
        f"/settings/users/{user_id}/edit",
        data={"usuario": username, "classification": "system", "active": "y"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert LAST_ADMIN_MESSAGE in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.get(User, user_id).classification == "admin"


@pytest.mark.parametrize("single_admin_app", [{"classification": "system", "with_role": True}], indirect=True)
def test_roles_http_rechaza_retirar_el_rol_admin_al_ultimo_admin(single_admin_app):
    """POST real a roles: un administrador por rol no puede quedarse sin él."""
    app, user_id, _ = single_admin_app
    client = _authenticated(app, user_id)

    response = client.post(f"/settings/users/{user_id}/roles", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert LAST_ADMIN_MESSAGE in response.get_data(as_text=True)
    with app.app_context():
        admin_role = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one()
        assignment = database.session.execute(
            database.select(RolesUser).filter_by(user_id=user_id, role_id=admin_role.id)
        ).scalar_one()
        assert assignment.active is True


def test_lock_deadlock_se_trata_como_rechazo(last_admin_app, monkeypatch):
    """Un deadlock al adquirir el bloqueo revierte y no responde 500."""
    app, _ = last_admin_app

    def deadlock(*_args, **_kwargs):
        raise OperationalError("SELECT FOR UPDATE", {}, Exception("deadlock detected"))

    monkeypatch.setattr(services, "_lock_last_admin_users", deadlock)

    with app.app_context():
        assert _acquire_last_admin_lock("cualquiera") is False


def test_commit_deadlock_se_trata_como_rechazo(last_admin_app, monkeypatch):
    """Un deadlock al confirmar revierte y no responde 500."""
    app, _ = last_admin_app

    def deadlock(*_args, **_kwargs):
        raise OperationalError("COMMIT", {}, Exception("deadlock detected"))

    monkeypatch.setattr(database.session, "commit", deadlock)

    with app.app_context():
        assert _commit_last_admin_transition() is False
