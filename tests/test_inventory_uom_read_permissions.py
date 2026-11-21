# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1926: global UOM catalog reads require inventory consultation permission."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Modules, Roles, RolesAccess, RolesUser, UOM, User, database


@pytest.fixture
def uom_permission_scenario():
    """Provide a UOM, a reader, and a user with module access but no read permission."""
    application = create_app(
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
    reader_id = f"uom-reader-{suffix}"
    denied_id = f"uom-no-view-{suffix}"
    uom_code = f"EA{suffix}"

    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="inventory", default=False, enabled=True),
                User(id=reader_id, user=reader_id, name="Lector UOM", password=b"unused", active=True),
                User(id=denied_id, user=denied_id, name="Sin consulta UOM", password=b"unused", active=True),
                UOM(code=uom_code, name="Unidad de prueba", is_active=True),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        reader_role = Roles(name=f"uom-reader-role-{suffix}", note="Consulta inventario")
        denied_role = Roles(name=f"uom-no-view-role-{suffix}", note="Acceso sin consulta")
        database.session.add_all([reader_role, denied_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=reader_role.id, module_id=module_id, access=True, view=True),
                RolesAccess(rol_id=denied_role.id, module_id=module_id, access=True),
                RolesUser(user_id=reader_id, role_id=reader_role.id, active=True),
                RolesUser(user_id=denied_id, role_id=denied_role.id, active=True),
            ]
        )
        database.session.commit()

    yield application, {"reader": reader_id, "denied": denied_id, "uom": uom_code}

    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(application, user_id: str):
    """Authenticate a test client as a seeded inventory user."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


@pytest.mark.parametrize("path_kind", ["list", "detail"])
def test_uom_reads_require_inventory_consultation(uom_permission_scenario, path_kind):
    """A user with module access but no consulta cannot read either catalog view."""
    application, ids = uom_permission_scenario
    client = _authenticated_client(application, ids["denied"])
    path = "/inventory/uom/list" if path_kind == "list" else f"/inventory/uom/{ids['uom']}"

    response = client.get(path)

    assert response.status_code == 403


def test_uom_reader_can_open_global_list_and_detail(uom_permission_scenario):
    """Authorized readers retain access to both global UOM catalog surfaces."""
    application, ids = uom_permission_scenario
    client = _authenticated_client(application, ids["reader"])

    listing = client.get("/inventory/uom/list")
    detail = client.get(f"/inventory/uom/{ids['uom']}")

    assert listing.status_code == 200
    assert ids["uom"] in listing.get_data(as_text=True)
    assert detail.status_code == 200
    assert "Unidad de prueba" in detail.get_data(as_text=True)
