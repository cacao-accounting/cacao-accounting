# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1778: no se elimina un centro de costos con hijos.

El borrado debe rechazarse antes de dejar referencias `parent` colgantes;
el hijo conserva su jerarquía y puede seguir editándose.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import CostCenter, database


@pytest.fixture
def cost_center_hierarchy(app):
    """Create a group center with one child and clean them afterwards."""
    suffix = uuid4().hex[:6]
    group_code = f"GRP{suffix}".upper()[:10]
    child_code = f"CHI{suffix}".upper()[:10]
    with app.app_context():
        group = CostCenter(
            entity="cacao",
            code=group_code,
            name="Grupo de costos",
            group=True,
            active=True,
            enabled=True,
        )
        child = CostCenter(
            entity="cacao",
            code=child_code,
            name="Centro hijo",
            parent=group_code,
            active=True,
            enabled=True,
        )
        database.session.add_all([group, child])
        database.session.commit()
        ids = {"group": group.id, "group_code": group_code, "child_id": child.id, "child_code": child_code}

    yield ids

    with app.app_context():
        for center_id in (ids["child_id"], ids["group"]):
            center = database.session.get(CostCenter, center_id)
            if center is not None:
                database.session.delete(center)
        database.session.commit()


def test_deleting_a_parent_center_is_rejected_and_children_survive(app, authenticated_client, cost_center_hierarchy):
    """The parent deletion is blocked and the child keeps its parent code."""
    ids = cost_center_hierarchy
    client = authenticated_client()

    response = client.post(f"/accounting/costs_center/{ids['group']}/delete")

    assert response.status_code == 302
    with app.app_context():
        group = database.session.get(CostCenter, ids["group"])
        child = database.session.get(CostCenter, ids["child_id"])
        assert group is not None
        assert child is not None
        assert child.parent == ids["group_code"]


def test_deleting_a_childless_center_still_works(app, authenticated_client, cost_center_hierarchy):
    """A leaf without dependencies can still be removed."""
    ids = cost_center_hierarchy
    client = authenticated_client()

    response = client.post(f"/accounting/costs_center/{ids['child_id']}/delete")

    assert response.status_code == 302
    with app.app_context():
        assert database.session.get(CostCenter, ids["child_id"]) is None
        assert database.session.get(CostCenter, ids["group"]) is not None
