# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las altas contables no persisten campos que WTForms haya rechazado."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Project, Unit, database


@pytest.fixture
def accounting_catalog_cleanup(app):
    """Registra códigos creados por las pruebas y elimina sus filas al finalizar."""
    created = {"unit": [], "project": []}
    yield created
    with app.app_context():
        for model, codes in ((Project, created["project"]), (Unit, created["unit"])):
            for code in codes:
                record = database.session.execute(database.select(model).filter_by(code=code)).scalar_one_or_none()
                if record is not None:
                    database.session.delete(record)
        database.session.commit()


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
