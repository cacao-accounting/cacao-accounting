# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1929: duplicar y crear plantillas no terminan en 500 por colisión de código."""

from __future__ import annotations

from uuid import uuid4

import pytest

from sqlalchemy import select

from cacao_accounting.database import Roles, RolesUser, User, database
from cacao_accounting.printing.models import PrintTemplate


@pytest.fixture
def plantillas(app):
    """Plantilla de sistema duplicable y administrador autenticado."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        rol = database.session.execute(database.select(Roles).filter_by(name="admin")).scalars().first()
        rol_creado = rol is None
        if rol is None:
            rol = Roles(name="admin", note="Administrador")
            database.session.add(rol)
            database.session.flush()
        role_id = rol.id
        database.session.add(
            User(
                id=f"admin-print-{sufijo}",
                user=f"admin-print-{sufijo}",
                name="Admin Print",
                password=b"unused",
                active=True,
                classification="admin",
            )
        )
        database.session.flush()
        database.session.add(RolesUser(user_id=f"admin-print-{sufijo}", role_id=rol.id, active=True))
        plantilla = PrintTemplate(
            company_code="cacao",
            document_type="sales_invoice",
            code=f"BASE-{sufijo}",
            name="Plantilla base",
            template_body="<p>Documento</p>",
            paper_size="letter",
            orientation="portrait",
            status="draft",
            is_system=False,
        )
        database.session.add(plantilla)
        database.session.commit()
        template_id = plantilla.id
        codigo = plantilla.code
        tipo = plantilla.document_type
        company = plantilla.company_code
    user_id = f"admin-print-{sufijo}"
    yield template_id, codigo, tipo, user_id

    with app.app_context():
        templates = database.session.execute(
            select(PrintTemplate).filter_by(company_code=company, document_type=tipo)
        ).scalars()
        for template in templates:
            if template.code == codigo or template.code.startswith(f"{codigo}_copy"):
                database.session.delete(template)
        assignments = database.session.execute(select(RolesUser).filter_by(user_id=user_id)).scalars()
        for assignment in assignments:
            database.session.delete(assignment)
        user = database.session.get(User, user_id)
        if user is not None:
            database.session.delete(user)
        if rol_creado:
            role = database.session.get(Roles, role_id)
            if role is not None:
                database.session.delete(role)
        database.session.commit()


def _cliente(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_duplicar_dos_veces_no_colisiona(app, plantillas):
    """La segunda duplicación usa un código nuevo."""
    template_id, codigo, tipo, user_id = plantillas
    client = _cliente(app, user_id)

    primera = client.post(f"/admin/print-templates/{template_id}/duplicate")
    segunda = client.post(f"/admin/print-templates/{template_id}/duplicate")

    assert primera.status_code in {301, 302, 303}
    assert segunda.status_code in {301, 302, 303}
    with app.app_context():
        copias = (
            database.session.execute(
                select(PrintTemplate)
                .filter_by(company_code="cacao", document_type=tipo)
                .where(PrintTemplate.code.in_([f"{codigo}_copy", f"{codigo}_copy_2"]))
            )
            .scalars()
            .all()
        )
        assert {fila.code for fila in copias} == {f"{codigo}_copy", f"{codigo}_copy_2"}
        assert all(fila.status == "draft" and not fila.is_default for fila in copias)


def test_crear_con_codigo_repetido_es_error_controlado(app, plantillas):
    """Repetir el código en la misma compañía y tipo no produce 500."""
    _template_id, codigo, tipo, user_id = plantillas
    client = _cliente(app, user_id)
    with app.app_context():
        count_before = len(
            database.session.execute(select(PrintTemplate).filter_by(company_code="cacao", document_type=tipo, code=codigo))
            .scalars()
            .all()
        )

    payload = {
        "document_type": tipo,
        "company_code": "cacao",
        "code": codigo,
        "name": "Repetida",
        "template_body": "<p>Otro</p>",
    }
    response = client.post("/admin/print-templates/new", data=payload)

    assert response.status_code == 200
    assert "Ya existe una plantilla con ese" in response.get_data(as_text=True)
    with app.app_context():
        count_after = len(
            database.session.execute(select(PrintTemplate).filter_by(company_code="cacao", document_type=tipo, code=codigo))
            .scalars()
            .all()
        )
    assert count_after == count_before == 1
