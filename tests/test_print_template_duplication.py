# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1929: duplicar y crear plantillas no terminan en 500 por colisión de código."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import User, database
from cacao_accounting.printing.models import PrintTemplate


@pytest.fixture
def plantillas(app):
    """Plantilla de sistema duplicable y administrador autenticado."""
    from cacao_accounting.database import Roles, RolesUser

    sufijo = uuid4().hex[:6]
    with app.app_context():
        rol = database.session.execute(database.select(Roles).filter_by(name="admin")).scalars().first()
        if rol is None:
            rol = Roles(name="admin", note="Administrador")
            database.session.add(rol)
            database.session.flush()
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
    yield template_id, codigo, tipo, f"admin-print-{sufijo}"


def _cliente(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_duplicar_dos_veces_no_colisiona(app, plantillas):
    """La segunda duplicación usa un código nuevo."""
    template_id, _codigo, _tipo, user_id = plantillas
    client = _cliente(app, user_id)

    primera = client.post(f"/admin/print-templates/{template_id}/duplicate")
    segunda = client.post(f"/admin/print-templates/{template_id}/duplicate")

    assert primera.status_code in {301, 302, 303}
    assert segunda.status_code in {301, 302, 303}
    with app.app_context():
        codigos = [fila.code for fila in database.session.execute(database.select(PrintTemplate)).scalars()]
        assert len(codigos) == len(set(codigos))


def test_crear_con_codigo_repetido_es_error_controlado(app, plantillas):
    """Repetir el código en la misma compañía y tipo no produce 500."""
    _template_id, codigo, tipo, user_id = plantillas
    client = _cliente(app, user_id)

    payload = {
        "document_type": tipo,
        "code": codigo,
        "name": "Repetida",
        "template_body": "<p>Otro</p>",
    }
    response = client.post("/admin/print-templates/new", data=payload)

    assert response.status_code != 500
