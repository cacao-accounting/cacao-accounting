# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las altas contables no persisten campos que WTForms haya rechazado."""

from __future__ import annotations

from cacao_accounting.database import Project, Unit, database


def test_unit_create_rejects_missing_required_fields(app, authenticated_client):
    """An invalid unit POST does not persist empty code or name values."""
    response = authenticated_client().post(
        "/accounting/unit/new",
        data={"id": "", "nombre": "", "entidad": "cacao"},
    )

    assert response.status_code == 200
    with app.app_context():
        assert database.session.execute(database.select(Unit).filter_by(code="")).scalar_one_or_none() is None


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
    with app.app_context():
        assert database.session.execute(database.select(Project).filter_by(code=code)).scalar_one_or_none() is None
