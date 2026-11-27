# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2308: la compañía propietaria de Unit y Project es inmutable."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.services import _validate_project_edit_form
from cacao_accounting.database import Project, Unit, UserCompanyAccess, database


def test_unit_edit_rechaza_cambio_de_compania(app, entorno_contable, authenticated_client, reference_users):
    """El POST de edición no puede trasladar la unidad a otra compañía."""
    del entorno_contable
    suffix = uuid4().hex[:6].upper()
    code = f"U{suffix}"
    admin_id = str(reference_users["admin"].id)
    with app.app_context():
        access = database.session.execute(
            database.select(UserCompanyAccess).filter_by(user_id=admin_id, company_code="alpha")
        ).scalar_one_or_none()
        if access is None:
            database.session.add(UserCompanyAccess(user_id=admin_id, company_code="alpha"))
        unit = Unit(code=code, name="Unidad inmutable", entity="cacao", enabled=True)
        database.session.add(unit)
        database.session.commit()
        unit_id = unit.id

    response = authenticated_client("admin").post(
        f"/accounting/unit/{unit_id}/edit",
        data={
            "id": code,
            "nombre": "Unidad inmutable",
            "entidad": "alpha",
            "parent_id": "",
            "habilitado": "on",
        },
    )

    assert response.status_code == 200
    assert "no puede cambiarse después de crearla" in response.get_data(as_text=True)
    with app.app_context():
        unit = database.session.get(Unit, unit_id)
        assert unit is not None
        assert unit.entity == "cacao"


def test_project_edit_rechaza_cambio_de_compania(app, entorno_contable):
    """La validación del servicio rechaza cambiar la compañía del proyecto."""
    del entorno_contable
    suffix = uuid4().hex[:6].upper()
    with app.app_context():
        project = Project(
            code=f"P{suffix}",
            name="Proyecto inmutable",
            entity="cacao",
            enabled=True,
            status="open",
        )
        database.session.add(project)
        database.session.commit()
        project_id = project.id

        formulario = SimpleNamespace(capitalizable=SimpleNamespace(data=False))
        with app.test_request_context(
            "/accounting/project/edit",
            method="POST",
            data={"entidad": "alpha", "parent_id": ""},
        ):
            with pytest.raises(ValueError, match="no puede cambiarse después de crearlo"):
                _validate_project_edit_form(formulario, database.session.get(Project, project_id))

        project = database.session.get(Project, project_id)
        assert project is not None
        assert project.entity == "cacao"
