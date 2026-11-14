"""Company ownership remains consistent across unit and project hierarchies."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting.database import Project, Unit, database


@pytest.fixture
def hierarchy_company_scenario(app, reference_users):
    """Create local and foreign parents plus editable children in two companies."""
    suffix = uuid4().hex[:6].upper()
    codes = {
        "unit_local": f"UL{suffix}",
        "unit_foreign": f"UF{suffix}",
        "unit_child": f"UC{suffix}",
        "project_local": f"PL{suffix}",
        "project_foreign": f"PF{suffix}",
        "project_child": f"PC{suffix}",
    }
    with app.app_context():
        records = [
            Unit(code=codes["unit_local"], name="Unidad local", entity="cacao", enabled=True),
            Unit(code=codes["unit_foreign"], name="Unidad extranjera", entity="alpha", enabled=True),
            Unit(code=codes["unit_child"], name="Unidad hija", entity="cacao", enabled=True),
            Project(code=codes["project_local"], name="Proyecto local", entity="cacao", enabled=True),
            Project(code=codes["project_foreign"], name="Proyecto extranjero", entity="alpha", enabled=True),
            Project(code=codes["project_child"], name="Proyecto hijo", entity="cacao", enabled=True),
        ]
        database.session.add_all(records)
        database.session.flush()
        records[2].parent_id = records[0].id
        records[5].parent_id = records[3].id
        database.session.flush()
        ids = {
            "unit_local": database.session.execute(database.select(Unit.id).filter_by(code=codes["unit_local"])).scalar_one(),
            "unit_foreign": database.session.execute(
                database.select(Unit.id).filter_by(code=codes["unit_foreign"])
            ).scalar_one(),
            "unit_child": database.session.execute(database.select(Unit.id).filter_by(code=codes["unit_child"])).scalar_one(),
            "project_local": database.session.execute(
                database.select(Project.id).filter_by(code=codes["project_local"])
            ).scalar_one(),
            "project_foreign": database.session.execute(
                database.select(Project.id).filter_by(code=codes["project_foreign"])
            ).scalar_one(),
            "project_child": database.session.execute(
                database.select(Project.id).filter_by(code=codes["project_child"])
            ).scalar_one(),
        }
        database.session.commit()

    yield app, codes, ids

    with app.app_context():
        for model, keys in (
            (Unit, ("unit_child", "unit_local", "unit_foreign")),
            (Project, ("project_child", "project_local", "project_foreign")),
        ):
            for key in keys:
                record = database.session.execute(database.select(model).filter_by(code=codes[key])).scalar_one_or_none()
                if record is not None:
                    database.session.delete(record)
        database.session.commit()


@pytest.mark.parametrize(
    ("node_type", "model", "parent_key", "path"),
    [
        ("unit", Unit, "unit_foreign", "/accounting/hierarchy/unit/parents"),
        ("project", Project, "project_foreign", "/accounting/hierarchy/project/parents"),
    ],
)
def test_parent_selector_only_returns_nodes_of_selected_company(
    authenticated_client, hierarchy_company_scenario, node_type, model, parent_key, path
):
    """The parent-options endpoint excludes foreign company records and retains local choices."""
    _app, codes, ids = hierarchy_company_scenario

    response = authenticated_client().get(f"{path}?entity=cacao&action=crear")

    assert response.status_code == 200
    options = response.get_json()
    option_ids = {option["value"] for option in options}
    local_key = f"{node_type}_local"
    assert ids[local_key] in option_ids
    assert ids[parent_key] not in option_ids
    assert all(codes[f"{node_type}_foreign"] not in option["label"] for option in options)


@pytest.mark.parametrize(
    ("path", "child_key", "parent_key"),
    [
        ("/accounting/hierarchy/unit/parents", "unit_child", "unit_foreign"),
        ("/accounting/hierarchy/project/parents", "project_child", "project_foreign"),
    ],
)
def test_parent_selector_ignores_exclusion_id_from_previous_company(
    authenticated_client, hierarchy_company_scenario, path, child_key, parent_key
):
    """Changing a leaf company still loads parent choices for the destination company."""
    _app, _codes, ids = hierarchy_company_scenario

    response = authenticated_client().get(f"{path}?entity=alpha&action=editar&exclude_id={ids[child_key]}")

    assert response.status_code == 200
    options = response.get_json()
    assert ids[parent_key] in {option["value"] for option in options}
    assert all(option["value"] != ids[child_key] for option in options)


@pytest.mark.parametrize(
    ("node_type", "path", "parent_key", "code_key", "child_code", "name"),
    [
        ("unit", "/accounting/unit/new", "unit_foreign", "unit_child", "U-NEW", "Unidad nueva"),
        ("project", "/accounting/project/new", "project_foreign", "project_child", "P-NEW", "Proyecto nuevo"),
    ],
)
def test_create_rejects_parent_from_another_company(
    authenticated_client, hierarchy_company_scenario, node_type, path, parent_key, code_key, child_code, name
):
    """A forged parent ID cannot create a cross-company unit or project."""
    app, _codes, ids = hierarchy_company_scenario
    data = {
        "id": child_code,
        "nombre": name,
        "entidad": "cacao",
        "parent_id": ids[parent_key],
        "habilitado": "on",
        "status": "open",
    }

    response = authenticated_client().post(path, data=data)

    assert response.status_code == 200
    with app.app_context():
        model = Unit if node_type == "unit" else Project
        assert database.session.execute(database.select(model).filter_by(code=child_code)).scalar_one_or_none() is None


@pytest.mark.parametrize(
    ("node_type", "path", "parent_key", "child_key", "name"),
    [
        ("unit", "/accounting/unit", "unit_foreign", "unit_child", "Cambio rechazado"),
        ("project", "/accounting/project", "project_foreign", "project_child", "Cambio rechazado"),
    ],
)
def test_edit_rejects_foreign_parent_without_mutating_existing_node(
    authenticated_client, hierarchy_company_scenario, node_type, path, parent_key, child_key, name
):
    """An invalid reparent attempt keeps the child company, parent, and name unchanged."""
    app, codes, ids = hierarchy_company_scenario
    data = {
        "id": codes[child_key],
        "nombre": name,
        "entidad": "cacao",
        "parent_id": ids[parent_key],
        "habilitado": "on",
        "status": "open",
    }

    response = authenticated_client().post(f"{path}/{codes[child_key]}/edit", data=data)

    assert response.status_code == 200
    with app.app_context():
        model = Unit if node_type == "unit" else Project
        child = database.session.execute(database.select(model).filter_by(code=codes[child_key])).scalar_one()
        assert child.entity == "cacao"
        assert child.parent_id == ids[f"{node_type}_local"]
        assert child.name == ("Unidad hija" if node_type == "unit" else "Proyecto hijo")


@pytest.mark.parametrize(
    ("node_type", "path", "parent_key", "child_key"),
    [
        ("unit", "/accounting/unit", "unit_local", "unit_child"),
        ("project", "/accounting/project", "project_local", "project_child"),
    ],
)
def test_parent_cannot_change_company_while_children_remain(
    authenticated_client, hierarchy_company_scenario, node_type, path, parent_key, child_key
):
    """Changing a parent company cannot leave its existing child in another company."""
    app, codes, _ids = hierarchy_company_scenario
    data = {
        "id": codes[parent_key],
        "nombre": "Padre conservado",
        "entidad": "alpha",
        "parent_id": "",
        "habilitado": "on",
        "status": "open",
    }

    response = authenticated_client().post(f"{path}/{codes[parent_key]}/edit", data=data)

    assert response.status_code == 200
    with app.app_context():
        model = Unit if node_type == "unit" else Project
        parent = database.session.execute(database.select(model).filter_by(code=codes[parent_key])).scalar_one()
        child = database.session.execute(database.select(model).filter_by(code=codes[child_key])).scalar_one()
        assert parent.entity == "cacao"
        assert parent.name == ("Unidad local" if node_type == "unit" else "Proyecto local")
        assert child.entity == "cacao"
        assert child.parent_id == parent.id


@pytest.mark.parametrize(
    ("node_type", "path", "child_key", "parent_key"),
    [
        ("unit", "/accounting/unit", "unit_child", "unit_foreign"),
        ("project", "/accounting/project", "project_child", "project_foreign"),
    ],
)
def test_leaf_can_move_company_and_use_destination_parent(
    authenticated_client, hierarchy_company_scenario, node_type, path, child_key, parent_key
):
    """A leaf remains editable when moved to a company and parent it can access."""
    app, codes, ids = hierarchy_company_scenario
    data = {
        "id": codes[child_key],
        "nombre": "Hijo trasladado",
        "entidad": "alpha",
        "parent_id": ids[parent_key],
        "habilitado": "on",
        "status": "open",
    }

    response = authenticated_client().post(f"{path}/{codes[child_key]}/edit", data=data)

    assert response.status_code == 302
    with app.app_context():
        model = Unit if node_type == "unit" else Project
        child = database.session.execute(database.select(model).filter_by(code=codes[child_key])).scalar_one()
        assert child.entity == "alpha"
        assert child.name == "Hijo trasladado"
        assert child.parent_id == ids[parent_key]


@pytest.mark.parametrize(
    ("model", "parent_key"),
    [(Unit, "unit_foreign"), (Project, "project_foreign")],
)
def test_database_constraint_rejects_cross_company_parent(hierarchy_company_scenario, model, parent_key):
    """Composite parent foreign keys reject bypassed cross-company writes."""
    _app, codes, ids = hierarchy_company_scenario
    child = model(code=f"X{uuid4().hex[:7].upper()}", name="Hijo inválido", entity="cacao", parent_id=ids[parent_key])

    with pytest.raises(IntegrityError):
        database.session.add(child)
        database.session.flush()

    database.session.rollback()
