# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1641: `/info` ignora vínculos de administrador revocados.

La página de desarrollo usa la misma regla de vigencia que el resto de los
permisos: solo un vínculo activo o la clasificación `admin` conceden acceso.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Roles, RolesUser, User, database

INFO_URLS = ("/info", "/dev")


@pytest.fixture
def dev_info_scenario():
    """Create one system user with a revocable admin link and one admin user."""
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
                User(
                    id=f"system-{suffix}",
                    user=f"system-{suffix}",
                    name="Usuario de sistema",
                    password=b"unused",
                    active=True,
                    classification="system",
                ),
                User(
                    id=f"admin-{suffix}",
                    user=f"admin-{suffix}",
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    classification="admin",
                ),
                User(
                    id=f"plain-{suffix}",
                    user=f"plain-{suffix}",
                    name="Usuario sin rol",
                    password=b"unused",
                    active=True,
                    classification="system",
                ),
            ]
        )
        database.session.flush()
        admin_role = Roles(name="admin", note="Administración del sistema")
        database.session.add(admin_role)
        database.session.flush()
        database.session.add(RolesUser(user_id=f"system-{suffix}", role_id=admin_role.id, active=False))
        database.session.commit()
        ids = {
            "system": f"system-{suffix}",
            "admin": f"admin-{suffix}",
            "plain": f"plain-{suffix}",
            "admin_role": admin_role.id,
        }

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


@pytest.mark.parametrize("path", INFO_URLS)
def test_revoked_admin_link_is_denied(dev_info_scenario, path):
    """An inactive admin link does not grant the development page."""
    app, ids = dev_info_scenario
    client = _authenticated_client(app, ids["system"])

    assert client.get(path).status_code == 403


@pytest.mark.parametrize("path", INFO_URLS)
def test_active_admin_link_is_allowed(dev_info_scenario, path):
    """Reactivating the link restores the documented access."""
    app, ids = dev_info_scenario
    with app.app_context():
        link = database.session.execute(
            database.select(RolesUser).filter_by(user_id=ids["system"], role_id=ids["admin_role"])
        ).scalar_one()
        link.active = True
        database.session.commit()
    client = _authenticated_client(app, ids["system"])

    assert client.get(path).status_code == 200


def test_admin_classification_is_allowed_without_a_role(dev_info_scenario):
    """The system administrator classification keeps working as before."""
    app, ids = dev_info_scenario
    client = _authenticated_client(app, ids["admin"])

    assert client.get("/info").status_code == 200


def test_user_without_admin_credentials_is_denied(dev_info_scenario):
    """A system user without the admin role or classification is denied."""
    app, ids = dev_info_scenario
    client = _authenticated_client(app, ids["plain"])

    assert client.get("/info").status_code == 403
