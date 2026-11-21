# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1598: el selector de tareas solo ofrece destinatarios elegibles.

El panel de colaboración de un documento debe listar únicamente usuarios con
acceso a la compañía del documento y permiso de consulta en su módulo. El
backend conserva la validación al crear la tarea.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from flask_login import login_user

from cacao_accounting import create_app, collaboration_active_users
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    DeliveryNote,
    DocumentTask,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def collaboration_scope_scenario():
    """Create a delivery note in alpha and candidate users in both companies."""
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
    company_alpha = f"a{suffix}"
    company_beta = f"b{suffix}"
    names = {
        "viewer": f"viewer-{suffix}",
        "alpha_sales": f"alpha-sales-{suffix}",
        "alpha_inventory": f"alpha-inventory-{suffix}",
        "alpha_no_module": f"alpha-no-module-{suffix}",
        "beta_sales": f"beta-sales-{suffix}",
    }

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="sales", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code=company_alpha,
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=company_beta,
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                User(id=user_id, user=user_id, name=user_id, password=b"unused", active=True, company=company_alpha)
                for user_id in names.values()
            ]
        )
        database.session.flush()
        note = DeliveryNote(
            company=company_alpha,
            document_no=f"DN-{suffix}",
            customer_name="Cliente Alfa",
            posting_date=date(2026, 5, 10),
        )
        database.session.add(note)
        database.session.flush()

        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        inventory_module = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        sales_role = Roles(name=f"sales-reader-{suffix}", note="Consulta de ventas")
        inventory_role = Roles(name=f"inventory-reader-{suffix}", note="Consulta de inventario")
        database.session.add_all([sales_role, inventory_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesAccess(rol_id=inventory_role.id, module_id=inventory_module, access=True, view=True),
                RolesUser(user_id=names["viewer"], role_id=sales_role.id, active=True),
                RolesUser(user_id=names["viewer"], role_id=inventory_role.id, active=True),
                RolesUser(user_id=names["alpha_sales"], role_id=sales_role.id, active=True),
                RolesUser(user_id=names["alpha_inventory"], role_id=inventory_role.id, active=True),
                RolesUser(user_id=names["beta_sales"], role_id=sales_role.id, active=True),
                UserCompanyAccess(user_id=names["viewer"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["alpha_sales"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["alpha_inventory"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["alpha_no_module"], company_code=company_alpha),
                UserCompanyAccess(user_id=names["beta_sales"], company_code=company_beta),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "note_id": note.id,
            "note_no": note.document_no,
            **names,
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


def test_task_selector_only_lists_company_and_module_recipients(collaboration_scope_scenario):
    """The rendered selector hides users from other companies or without sales."""
    app, ids = collaboration_scope_scenario
    client = _authenticated_client(app, ids["viewer"])

    response = client.get(f"/sales/delivery-note/{ids['note_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_inventory"] in body
    assert ids["viewer"] in body
    assert ids["beta_sales"] not in body
    assert ids["alpha_sales"] not in body
    assert ids["alpha_no_module"] not in body


def test_collaboration_active_users_scopes_to_document_company(collaboration_scope_scenario):
    """The helper returns only readers of the document's module in its company."""
    app, ids = collaboration_scope_scenario

    with app.test_request_context("/"):
        login_user(database.session.get(User, ids["viewer"]))
        users = collaboration_active_users("delivery_note", ids["company_alpha"])

    assert [user.user for user in users] == [ids["alpha_inventory"], ids["viewer"]]


def test_collaboration_active_users_rejects_company_outside_scope(collaboration_scope_scenario):
    """A company outside the viewer's grants yields an empty selector."""
    app, ids = collaboration_scope_scenario

    with app.test_request_context("/"):
        login_user(database.session.get(User, ids["viewer"]))
        assert collaboration_active_users("delivery_note", ids["company_beta"]) == []


def test_task_creation_rejects_ineligible_recipient(collaboration_scope_scenario):
    """The backend still refuses a recipient without the document company/module."""
    app, ids = collaboration_scope_scenario
    client = _authenticated_client(app, ids["viewer"])
    path = f"/api/documents/delivery_note/{ids['note_id']}/tasks"

    denied = client.post(path, json={"title": "Revisar entrega", "assigned_to": ids["beta_sales"]})
    assert denied.status_code == 403
    with app.app_context():
        assert database.session.execute(database.select(DocumentTask)).scalars().all() == []

    allowed = client.post(path, json={"title": "Revisar entrega", "assigned_to": ids["alpha_inventory"]})
    assert allowed.status_code == 201
    with app.app_context():
        tasks = database.session.execute(database.select(DocumentTask)).scalars().all()
        assert [task.assigned_to for task in tasks] == [ids["alpha_inventory"]]
