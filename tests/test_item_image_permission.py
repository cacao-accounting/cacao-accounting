# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1301: las imágenes de artículos exigen permiso de Inventario.

La imagen pertenece al artículo global y se comparte entre compañías, por lo
que la lectura exige `inventory.consultar` y las mutaciones `inventory.editar`.
Un usuario sin permiso no alcanza el recurso aunque conozca el código.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    UOM,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def item_image_permission_scenario():
    """Create a shared item and inventory users with and without permissions."""
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
    company = f"c{suffix}"
    item_code = f"IMG-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code=company,
                    name="Compañía",
                    company_name=f"Compañía {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(UOM(code="EA", name="Each", is_active=True))
        database.session.flush()
        database.session.add_all(
            [
                Item(code=item_code, name="Artículo con imagen", item_type="goods", is_stock_item=True, default_uom="EA"),
                User(
                    id=f"access-only-{suffix}",
                    user=f"access-only-{suffix}",
                    name="Solo acceso",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
                User(
                    id=f"viewer-{suffix}",
                    user=f"viewer-{suffix}",
                    name="Consulta de inventario",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
                User(
                    id=f"editor-{suffix}",
                    user=f"editor-{suffix}",
                    name="Edición de inventario",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
            ]
        )
        database.session.flush()
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        access_role = Roles(name=f"image-access-{suffix}", note="Solo acceso")
        viewer_role = Roles(name=f"image-view-{suffix}", note="Consulta de inventario")
        editor_role = Roles(name=f"image-edit-{suffix}", note="Edición de inventario")
        database.session.add_all([access_role, viewer_role, editor_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=access_role.id, module_id=module_id, access=True),
                RolesAccess(rol_id=viewer_role.id, module_id=module_id, access=True, view=True),
                RolesAccess(rol_id=editor_role.id, module_id=module_id, access=True, view=True, edit=True),
                RolesUser(user_id=f"access-only-{suffix}", role_id=access_role.id, active=True),
                RolesUser(user_id=f"viewer-{suffix}", role_id=viewer_role.id, active=True),
                RolesUser(user_id=f"editor-{suffix}", role_id=editor_role.id, active=True),
                UserCompanyAccess(user_id=f"access-only-{suffix}", company_code=company),
                UserCompanyAccess(user_id=f"viewer-{suffix}", company_code=company),
                UserCompanyAccess(user_id=f"editor-{suffix}", company_code=company),
            ]
        )
        database.session.commit()
        ids = {
            "company": company,
            "item_code": item_code,
            "access_only": f"access-only-{suffix}",
            "viewer": f"viewer-{suffix}",
            "editor": f"editor-{suffix}",
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


def test_item_image_read_requires_inventory_view(item_image_permission_scenario):
    """Access without view cannot read the image nor learn whether it exists."""
    app, ids = item_image_permission_scenario
    client = _authenticated_client(app, ids["access_only"])

    response = client.get(f"/api/inventory/items/{ids['item_code']}/image")

    assert response.status_code == 403


def test_item_image_mutations_require_inventory_edit(item_image_permission_scenario):
    """Access-only and read-only users cannot upload or delete images."""
    app, ids = item_image_permission_scenario
    access_only = _authenticated_client(app, ids["access_only"])
    viewer = _authenticated_client(app, ids["viewer"])
    path = f"/api/inventory/items/{ids['item_code']}/image"

    assert access_only.post(path).status_code == 403
    assert access_only.post(f"{path}/delete").status_code == 403
    assert viewer.post(path).status_code == 403
    assert viewer.post(f"{path}/delete").status_code == 403


def test_item_image_editor_passes_the_permission_guard(item_image_permission_scenario):
    """An editor reaches the image service; the missing file is not an ACL error."""
    app, ids = item_image_permission_scenario
    client = _authenticated_client(app, ids["editor"])
    path = f"/api/inventory/items/{ids['item_code']}/image"

    upload = client.post(path)
    delete = client.post(f"{path}/delete")

    assert upload.status_code != 403
    assert delete.status_code != 403


def test_item_image_reader_passes_the_read_guard(item_image_permission_scenario):
    """A reader reaches the image lookup and receives 404 when there is no file."""
    app, ids = item_image_permission_scenario
    client = _authenticated_client(app, ids["viewer"])

    response = client.get(f"/api/inventory/items/{ids['item_code']}/image")

    assert response.status_code == 404
