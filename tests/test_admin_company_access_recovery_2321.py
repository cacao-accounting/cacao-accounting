# SPDX-License-Identifier: Apache-2.0
"""#2321: recuperaci?n de acceso a compa??as para administradores en Cloud."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import Entity, Modules, Roles, RolesUser, User, UserCompanyAccess, database


@pytest.fixture
def cloud_admin_access_app(app):
    with app.app_context():
        previous_mode_present = "MODO_ESCRITORIO" in app.config
        previous_mode = app.config.get("MODO_ESCRITORIO")
        app.config["MODO_ESCRITORIO"] = False
        for module in ("admin", "accounting"):
            row = database.session.execute(select(Modules).filter_by(module=module)).scalar_one_or_none()
            if row is None:
                database.session.add(Modules(module=module, default=False, enabled=True))
            else:
                row.enabled = True
        database.session.commit()
    yield app
    with app.app_context():
        if previous_mode_present:
            app.config["MODO_ESCRITORIO"] = previous_mode
        else:
            app.config.pop("MODO_ESCRITORIO", None)


def _mk_company(app, suffix: str) -> str:
    with app.app_context():
        code = f"C{suffix}{uuid4().hex[:4]}".upper()[:10]
        database.session.add(
            Entity(code=code, name=code, company_name=code, tax_id=f"T{code}", currency="NIO", enabled=True, status="activo")
        )
        database.session.commit()
        return code


def _mk_admin(app, suffix: str, *, company_codes: list[str]) -> str:
    with app.app_context():
        uid = f"adm2321-{suffix}-{uuid4().hex[:6]}"
        user = User(id=uid, user=uid, name="Admin", active=True, classification="admin")
        user.password = proteger_passwd("Admin123!Test")
        database.session.add(user)
        database.session.flush()
        admin_role = database.session.execute(select(Roles).filter_by(name="admin")).scalar_one()
        database.session.add(RolesUser(user_id=uid, role_id=admin_role.id, active=True))
        for code in company_codes:
            database.session.add(UserCompanyAccess(user_id=uid, company_code=code))
        database.session.commit()
        return uid


def _login(client, username: str, password: str = "Admin123!Test"):
    return client.post("/login", data={"usuario": username, "clave": password}, follow_redirects=True)


def test_blocks_revoking_last_recoverable_admin_for_company(cloud_admin_access_app, authenticated_client):
    app = cloud_admin_access_app
    company = _mk_company(app, "L")
    target = _mk_admin(app, "last", company_codes=[company])

    # authenticated_client("admin") is system admin; ensure it does NOT have access to this company
    with app.app_context():
        database.session.execute(
            database.delete(UserCompanyAccess).where(
                UserCompanyAccess.user_id == database.session.execute(select(User.id).filter_by(user="admin")).scalar_one(),
                UserCompanyAccess.company_code == company,
            )
        )
        database.session.commit()

    client = authenticated_client("admin")
    resp = client.post(f"/settings/users/{target}/companies", data={"companies": []}, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "administrador" in body.lower()

    with app.app_context():
        rows = database.session.execute(select(UserCompanyAccess.company_code).filter_by(user_id=target)).scalars().all()
        assert company in rows


def test_system_admin_with_company_access_can_reassign_and_recover(cloud_admin_access_app, authenticated_client):
    app = cloud_admin_access_app
    company = _mk_company(app, "R")
    target = _mk_admin(app, "rec", company_codes=[company])

    client = authenticated_client("admin")
    # give system admin access to company so recovery path is authorized
    with app.app_context():
        admin_id = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        exists = database.session.execute(
            select(UserCompanyAccess).filter_by(user_id=admin_id, company_code=company)
        ).scalar_one_or_none()
        if not exists:
            database.session.add(UserCompanyAccess(user_id=admin_id, company_code=company))
            database.session.commit()

    resp = client.post(f"/settings/users/{target}/companies", data={"companies": []}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        rows = database.session.execute(select(UserCompanyAccess.company_code).filter_by(user_id=target)).scalars().all()
        assert company not in rows

    # recover: assign back
    resp = client.post(f"/settings/users/{target}/companies", data={"companies": [company]}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        rows = database.session.execute(select(UserCompanyAccess.company_code).filter_by(user_id=target)).scalars().all()
        assert company in rows


def test_non_admin_cannot_change_company_assignments(cloud_admin_access_app):
    app = cloud_admin_access_app
    company = _mk_company(app, "N")
    target = _mk_admin(app, "tgt", company_codes=[company])

    with app.app_context():
        uid = f"usr2321-{uuid4().hex[:8]}"
        user = User(id=uid, user=uid, name="User", active=True, classification="user")
        user.password = proteger_passwd("User123!Test")
        database.session.add(user)
        database.session.commit()

    client = app.test_client()
    _login(client, uid, "User123!Test")
    resp = client.post(f"/settings/users/{target}/companies", data={"companies": []}, follow_redirects=False)
    assert resp.status_code in (302, 403)

    with app.app_context():
        rows = database.session.execute(select(UserCompanyAccess.company_code).filter_by(user_id=target)).scalars().all()
        assert company in rows


def test_revocaciones_concurrentes_conservan_un_admin_recuperable(tmp_path, monkeypatch):
    """#2321: dos admins no pueden revocar a la vez el último acceso de la compañía."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, BrokenBarrierError

    from cacao_accounting import create_app
    from cacao_accounting.admin import services as admin_services
    from cacao_accounting.config import configuracion
    from cacao_accounting.database import Currency

    database_uri = f"sqlite:///{tmp_path / 'admin-access-2321.sqlite'}"
    settings = {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "TESTING": True,
        "MODO_ESCRITORIO": False,
    }
    writer = create_app(settings)
    reader = create_app(settings)
    company = f"A{uuid4().hex[:7].upper()}"
    admin_ids = [f"adm2321-a-{uuid4().hex[:6]}", f"adm2321-b-{uuid4().hex[:6]}"]
    with writer.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code=company,
                name=company,
                company_name=company,
                tax_id=f"T{company}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        admin_role = Roles(name="admin", note="Administrador")
        database.session.add(admin_role)
        database.session.flush()
        for uid in admin_ids:
            user = User(id=uid, user=uid, name="Admin", active=True, classification="admin")
            user.password = proteger_passwd("Admin123!Test")
            database.session.add(user)
            database.session.flush()
            database.session.add(RolesUser(user_id=uid, role_id=admin_role.id, active=True))
            database.session.add(UserCompanyAccess(user_id=uid, company_code=company))
        database.session.commit()

    barrier = Barrier(2)
    choose_barrier = Barrier(2)
    original_check = admin_services._company_has_recoverable_admin

    def _synchronized_check(company_code: str, *, exclude_user_id: str | None = None) -> bool:
        try:
            choose_barrier.wait(timeout=0.2)
        except BrokenBarrierError:
            pass
        return original_check(company_code, exclude_user_id=exclude_user_id)

    monkeypatch.setattr(admin_services, "_company_has_recoverable_admin", _synchronized_check)

    def _revoke(app, user_id: str) -> str:
        with app.app_context():
            barrier.wait(timeout=10)
            try:
                admin_services.replace_user_company_access(user_id, set())
            except ValueError:
                database.session.rollback()
                return "rejected"
            return "revoked"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_revoke, writer, admin_ids[0]),
            executor.submit(_revoke, reader, admin_ids[1]),
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(results) == ["rejected", "revoked"]
    with writer.app_context():
        database.session.expire_all()
        remaining = database.session.execute(select(UserCompanyAccess.user_id).filter_by(company_code=company)).scalars().all()
        assert len(remaining) == 1
        assert remaining[0] in admin_ids
        database.session.remove()
        database.engine.dispose()
    with reader.app_context():
        database.session.remove()
        database.engine.dispose()
