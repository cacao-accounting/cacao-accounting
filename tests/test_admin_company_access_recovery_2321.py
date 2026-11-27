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
        app.config["MODO_ESCRITORIO"] = True


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
