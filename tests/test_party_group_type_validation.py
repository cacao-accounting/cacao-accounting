# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Party group writers accept only customer and supplier roles."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.database import Modules, PartyGroup, User, database


@pytest.fixture(name="party_group_admin", autouse=True)
def party_group_admin_fixture(app):
    """Enable the admin module and return a logged in system administrator id."""
    with app.app_context():
        admin_module = database.session.execute(select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if admin_module is None:
            database.session.add(Modules(module="admin", default=False, enabled=True))
        else:
            admin_module.enabled = True
        database.session.commit()
        return database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()


@pytest.mark.parametrize("path", ["/settings/party-groups", "/settings/party-groups/placeholder/edit"])
def test_group_create_or_edit_rejects_unknown_type_without_persisting(app, authenticated_client, path):
    """Invalid group types cannot create an orphan or mutate an existing group."""
    client = authenticated_client("admin")
    group_name = f"Validation group {uuid4().hex[:8]}"
    if "placeholder" in path:
        with app.app_context():
            group = PartyGroup(group_type="customer", name=group_name, description="original", is_active=True)
            database.session.add(group)
            database.session.commit()
            path = f"/settings/party-groups/{group.id}/edit"
            group_id = group.id
    else:
        group_id = None

    response = client.post(path, data={"group_type": "legacy_type", "name": "Mutated group", "is_active": "on"})

    assert response.status_code == 200
    assert "debe ser cliente o proveedor" in response.get_data(as_text=True)
    with app.app_context():
        if group_id is None:
            assert database.session.execute(select(PartyGroup).filter_by(name="Mutated group")).scalar_one_or_none() is None
        else:
            group = database.session.get(PartyGroup, group_id)
            assert (group.group_type, group.name, group.description, group.is_active) == (
                "customer",
                group_name,
                "original",
                True,
            )


@pytest.mark.parametrize("group_type", ["customer", "supplier"])
@pytest.mark.parametrize("edit", [False, True])
def test_group_create_and_edit_accept_supported_types(app, authenticated_client, group_type, edit):
    """Both supported role types remain available to create and edit."""
    client = authenticated_client("admin")
    name = f"Supported group {uuid4().hex[:8]}"
    path = "/settings/party-groups"
    if edit:
        with app.app_context():
            group = PartyGroup(group_type="customer", name=name, description="old", is_active=True)
            database.session.add(group)
            database.session.commit()
            path = f"{path}/{group.id}/edit"
            group_id = group.id
    else:
        group_id = None

    response = client.post(path, data={"group_type": group_type, "name": name, "is_active": "on"})

    assert response.status_code == 302
    with app.app_context():
        group = (
            database.session.get(PartyGroup, group_id)
            if group_id
            else database.session.execute(select(PartyGroup).filter_by(group_type=group_type, name=name)).scalar_one()
        )
        assert group.group_type == group_type
        assert group.name == name
