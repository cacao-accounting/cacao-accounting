# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las altas contables no persisten campos que WTForms haya rechazado."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Entity, Project, Unit, database
from cacao_accounting.database.helpers import check_hierarchy_cycle

MENSAJE_PADRE_INEXISTENTE = "El registro padre seleccionado no existe."
MENSAJE_PADRE_AJENO = "Los registros de una jerarquía deben pertenecer a la misma compañía."
MENSAJE_CONFLICTO_GENERICO = (
    "No se pudo guardar porque los datos entran en conflicto " + "con otro registro. Revise el código y las referencias."
)


@pytest.fixture
def accounting_catalog_cleanup(app):
    """Registra códigos creados por las pruebas y elimina sus filas al finalizar."""
    created = {"unit": [], "project": [], "entity": []}
    yield created
    with app.app_context():
        for model, codes in ((Project, created["project"]), (Unit, created["unit"])):
            for code in codes:
                record = database.session.execute(database.select(model).filter_by(code=code)).scalar_one_or_none()
                if record is not None:
                    database.session.delete(record)
        database.session.commit()
        for code in created["entity"]:
            record = database.session.execute(database.select(Entity).filter_by(code=code)).scalar_one_or_none()
            if record is not None:
                database.session.delete(record)
        database.session.commit()


@pytest.fixture
def padres_otra_compania(app, accounting_catalog_cleanup):
    """Crea padres de otra compañía para comprobar el aislamiento jerárquico."""
    sufijo = uuid4().hex[:8].upper()
    codigo_entidad = f"OTR{sufijo}"
    codigo_unidad = f"U{sufijo}"
    codigo_proyecto = f"P{sufijo}"
    accounting_catalog_cleanup["unit"].append(codigo_unidad)
    accounting_catalog_cleanup["project"].append(codigo_proyecto)
    accounting_catalog_cleanup["entity"].append(codigo_entidad)
    with app.app_context():
        entidad = Entity(
            code=codigo_entidad,
            name=f"Otra compañía {sufijo}",
            company_name=f"Otra compañía {sufijo}",
            tax_id=f"J{sufijo}",
            currency="NIO",
            enabled=True,
        )
        database.session.add(entidad)
        database.session.flush()
        unidad = Unit(code=codigo_unidad, name="Unidad ajena", entity=codigo_entidad, enabled=True)
        proyecto = Project(code=codigo_proyecto, name="Proyecto ajeno", entity=codigo_entidad, enabled=True)
        database.session.add_all([unidad, proyecto])
        database.session.commit()
        ids = {"unit": unidad.id, "project": proyecto.id}
    yield ids


def test_unit_create_rejects_missing_required_fields(app, authenticated_client):
    """An invalid unit POST does not persist empty code or name values."""
    response = authenticated_client().post(
        "/accounting/unit/new",
        data={"id": "", "nombre": "", "entidad": "cacao"},
    )

    assert response.status_code == 200
    assert 'class="alert alert-danger' in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(database.select(Unit).filter_by(code="")).scalar_one_or_none() is None


def test_unit_create_valid_post_persists_row(app, authenticated_client, accounting_catalog_cleanup):
    """A valid unit POST stores the code, name, and company."""
    code = f"U{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["unit"].append(code)

    response = authenticated_client().post(
        "/accounting/unit/new",
        data={"id": code, "nombre": "Unidad válida", "entidad": "cacao", "habilitado": "on"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/accounting/unit/list")
    with app.app_context():
        unit = database.session.execute(database.select(Unit).filter_by(code=code)).scalar_one()
        assert unit.name == "Unidad válida"
        assert unit.entity == "cacao"


def test_unit_create_rejects_missing_parent(app, authenticated_client, accounting_catalog_cleanup):
    """A unit with a non-existent parent is rejected before persisting."""
    code = f"U{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["unit"].append(code)

    response = authenticated_client().post(
        "/accounting/unit/new",
        data={
            "id": code,
            "nombre": "Unidad con padre inválido",
            "entidad": "cacao",
            "parent_id": "parent-does-not-exist",
            "habilitado": "on",
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MENSAJE_PADRE_INEXISTENTE in cuerpo
    assert MENSAJE_CONFLICTO_GENERICO not in cuerpo
    with app.app_context():
        assert database.session.execute(database.select(Unit).filter_by(code=code)).scalar_one_or_none() is None


def test_unit_edit_rejects_missing_parent(app, authenticated_client, accounting_catalog_cleanup):
    """Editing a unit cannot leave an orphan parent in SQLite."""
    code = f"U{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["unit"].append(code)
    with app.app_context():
        database.session.add(Unit(code=code, name="Unidad sin padre", entity="cacao", enabled=True))
        database.session.commit()
        unit_id = database.session.execute(database.select(Unit.id).filter_by(code=code)).scalar_one()

    response = authenticated_client().post(
        f"/accounting/unit/{unit_id}/edit",
        data={
            "id": code,
            "nombre": "Unidad sin padre",
            "entidad": "cacao",
            "parent_id": "parent-does-not-exist",
            "habilitado": "on",
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MENSAJE_PADRE_INEXISTENTE in cuerpo
    assert MENSAJE_CONFLICTO_GENERICO not in cuerpo
    with app.app_context():
        unit = database.session.execute(database.select(Unit).filter_by(code=code)).scalar_one()
        assert unit.parent_id is None


def test_project_create_rejects_missing_parent(app, authenticated_client, accounting_catalog_cleanup):
    """A project with a non-existent parent is rejected before persisting."""
    code = f"P{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["project"].append(code)

    response = authenticated_client().post(
        "/accounting/project/new",
        data={
            "id": code,
            "nombre": "Proyecto con padre inválido",
            "entidad": "cacao",
            "parent_id": "parent-does-not-exist",
            "presupuesto": "10",
            "status": "open",
            "habilitado": "on",
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MENSAJE_PADRE_INEXISTENTE in cuerpo
    assert MENSAJE_CONFLICTO_GENERICO not in cuerpo
    with app.app_context():
        assert database.session.execute(database.select(Project).filter_by(code=code)).scalar_one_or_none() is None


def test_unit_create_rejects_parent_from_another_company(
    app, authenticated_client, accounting_catalog_cleanup, padres_otra_compania
):
    """Una unidad de cacao no puede usar como padre una unidad ajena."""
    code = f"U{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["unit"].append(code)

    response = authenticated_client().post(
        "/accounting/unit/new",
        data={
            "id": code,
            "nombre": "Unidad con padre ajeno",
            "entidad": "cacao",
            "parent_id": padres_otra_compania["unit"],
            "habilitado": "on",
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MENSAJE_PADRE_AJENO in cuerpo
    assert MENSAJE_CONFLICTO_GENERICO not in cuerpo
    with app.app_context():
        assert database.session.execute(database.select(Unit).filter_by(code=code)).scalar_one_or_none() is None


def test_unit_edit_rejects_parent_from_another_company(
    app, authenticated_client, accounting_catalog_cleanup, padres_otra_compania
):
    """Editar una unidad no permite adoptar un padre de otra compañía."""
    code = f"U{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["unit"].append(code)
    with app.app_context():
        database.session.add(Unit(code=code, name="Unidad local", entity="cacao", enabled=True))
        database.session.commit()
        unit_id = database.session.execute(database.select(Unit.id).filter_by(code=code)).scalar_one()

    response = authenticated_client().post(
        f"/accounting/unit/{unit_id}/edit",
        data={
            "id": code,
            "nombre": "Unidad local",
            "entidad": "cacao",
            "parent_id": padres_otra_compania["unit"],
            "habilitado": "on",
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MENSAJE_PADRE_AJENO in cuerpo
    assert MENSAJE_CONFLICTO_GENERICO not in cuerpo
    with app.app_context():
        unidad = database.session.execute(database.select(Unit).filter_by(code=code)).scalar_one()
        assert unidad.parent_id is None


def test_project_create_rejects_parent_from_another_company(
    app, authenticated_client, accounting_catalog_cleanup, padres_otra_compania
):
    """Un proyecto de cacao no puede usar como padre un proyecto ajeno."""
    code = f"P{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["project"].append(code)

    response = authenticated_client().post(
        "/accounting/project/new",
        data={
            "id": code,
            "nombre": "Proyecto con padre ajeno",
            "entidad": "cacao",
            "parent_id": padres_otra_compania["project"],
            "presupuesto": "10",
            "status": "open",
            "habilitado": "on",
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert MENSAJE_PADRE_AJENO in cuerpo
    assert MENSAJE_CONFLICTO_GENERICO not in cuerpo
    with app.app_context():
        assert database.session.execute(database.select(Project).filter_by(code=code)).scalar_one_or_none() is None


def test_project_create_rejects_invalid_budget_without_defaulting_to_zero(app, authenticated_client):
    """An unparsable budget keeps the project form invalid and creates no project."""
    code = "INVALID-BUDGET-TEST"

    response = authenticated_client().post(
        "/accounting/project/new",
        data={
            "id": code,
            "nombre": "Proyecto de prueba",
            "entidad": "cacao",
            "presupuesto": "abc",
            "status": "open",
        },
    )

    assert response.status_code == 200
    assert 'class="alert alert-danger' in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.execute(database.select(Project).filter_by(code=code)).scalar_one_or_none() is None


def test_project_create_persists_valid_budget(app, authenticated_client, accounting_catalog_cleanup):
    """A valid project POST stores the exact budget instead of defaulting to zero."""
    code = f"P{uuid4().hex[:6].upper()}"
    accounting_catalog_cleanup["project"].append(code)

    response = authenticated_client().post(
        "/accounting/project/new",
        data={
            "id": code,
            "nombre": "Proyecto válido",
            "entidad": "cacao",
            "presupuesto": "123.45",
            "status": "open",
            "habilitado": "on",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/accounting/project/list")
    with app.app_context():
        project = database.session.execute(database.select(Project).filter_by(code=code)).scalar_one()
        assert project.name == "Proyecto válido"
        assert project.budget == Decimal("123.45")
        assert project.budget_currency_code == "NIO"


@pytest.fixture
def proyecto_con_padre_local(app, accounting_catalog_cleanup):
    """Proyecto con padre válido de la misma compañía para probar ediciones rechazadas."""
    sufijo = uuid4().hex[:8].upper()
    codigo_padre = f"PP{sufijo}"
    codigo_hijo = f"PH{sufijo}"
    accounting_catalog_cleanup["project"].extend([codigo_hijo, codigo_padre])
    with app.app_context():
        padre = Project(code=codigo_padre, name="Proyecto padre local", entity="cacao", enabled=True)
        database.session.add(padre)
        database.session.flush()
        hijo = Project(
            code=codigo_hijo,
            name="Proyecto hijo local",
            entity="cacao",
            enabled=True,
            parent_id=padre.id,
        )
        database.session.add(hijo)
        database.session.commit()
        ids = {"hijo": hijo.id, "padre": padre.id, "ruta_padre": padre.path}
    return ids


@pytest.mark.parametrize("modelo", [Unit, Project])
def test_check_hierarchy_cycle_rechaza_padre_inexistente_con_error_especifico(app, modelo):
    """La guarda aplicacional falla por su propio motivo, sin depender de la FK."""
    with app.app_context():
        with pytest.raises(ValueError, match=MENSAJE_PADRE_INEXISTENTE):
            check_hierarchy_cycle(modelo, None, "padre-inexistente-sin-fk", entity="cacao")


@pytest.mark.parametrize(("modelo", "clave"), [(Unit, "unit"), (Project, "project")])
def test_check_hierarchy_cycle_rechaza_padre_ajeno_con_error_especifico(app, padres_otra_compania, modelo, clave):
    """La misma guarda distingue el padre de otra compañía de un conflicto de base."""
    with app.app_context():
        with pytest.raises(ValueError, match=MENSAJE_PADRE_AJENO):
            check_hierarchy_cycle(modelo, None, padres_otra_compania[clave], entity="cacao")


@pytest.mark.parametrize(
    ("clave_origen", "mensaje"),
    [
        pytest.param(None, MENSAJE_PADRE_INEXISTENTE, id="inexistente"),
        pytest.param("project", MENSAJE_PADRE_AJENO, id="ajeno"),
    ],
)
def test_project_edit_rejects_invalid_parent_and_preserves_existing_parent(
    app,
    authenticated_client,
    proyecto_con_padre_local,
    padres_otra_compania,
    clave_origen,
    mensaje,
):
    """Editar un proyecto no puede reemplazar su padre válido por una referencia inválida."""
    ids = proyecto_con_padre_local
    padre_invalido = "parent-does-not-exist" if clave_origen is None else padres_otra_compania[clave_origen]

    respuesta = authenticated_client().post(
        f"/accounting/project/{ids['hijo']}/edit",
        data={
            "id": ids["hijo"],
            "nombre": "Proyecto hijo local",
            "entidad": "cacao",
            "parent_id": padre_invalido,
            "presupuesto": "10",
            "status": "open",
            "habilitado": "on",
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    assert mensaje in cuerpo
    assert MENSAJE_CONFLICTO_GENERICO not in cuerpo
    with app.app_context():
        hijo = database.session.get(Project, ids["hijo"])
        padre = database.session.get(Project, ids["padre"])
        assert hijo.parent_id == ids["padre"]
        assert padre.path == ids["ruta_padre"]
