# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1329: la bandeja y el badge pierden tareas al revocar la compañía.

Una tarea asignada deja de mostrarse en `/tasks/my` y en el contador cuando el
usuario pierde acceso a la compañía del documento. Las tareas sin compañía se
conservan, y el filtro explícito por compañía tampoco amplía el alcance.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.collaboration_service import open_task_count
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
def task_revocation_scenario():
    """Create alpha and beta tasks plus a company-less task for one assignee."""
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
    assignee = f"assignee-{suffix}"
    assigner = f"assigner-{suffix}"
    titles = {
        "alpha": f"Tarea Alfa {suffix}",
        "beta": f"Tarea Beta {suffix}",
        "none": f"Tarea Sin Compañía {suffix}",
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
                User(
                    id=assignee,
                    user=assignee,
                    name="Asignado",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
                User(
                    id=assigner,
                    user=assigner,
                    name="Asignador",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                ),
            ]
        )
        database.session.flush()
        alpha_note = DeliveryNote(
            company=company_alpha,
            document_no=f"DN-A-{suffix}",
            customer_name="Cliente Alfa",
            posting_date=date(2026, 5, 10),
        )
        beta_note = DeliveryNote(
            company=company_beta,
            document_no=f"DN-B-{suffix}",
            customer_name="Cliente Beta",
            posting_date=date(2026, 5, 11),
        )
        database.session.add_all([alpha_note, beta_note])
        database.session.flush()
        database.session.add_all(
            [
                DocumentTask(
                    document_type="delivery_note",
                    document_id=alpha_note.id,
                    document_no=alpha_note.document_no,
                    company=company_alpha,
                    title=titles["alpha"],
                    assigned_by=assigner,
                    assigned_to=assignee,
                ),
                DocumentTask(
                    document_type="delivery_note",
                    document_id=beta_note.id,
                    document_no=beta_note.document_no,
                    company=company_beta,
                    title=titles["beta"],
                    assigned_by=assigner,
                    assigned_to=assignee,
                ),
                DocumentTask(
                    document_type="delivery_note",
                    document_id=alpha_note.id,
                    document_no=alpha_note.document_no,
                    company=None,
                    title=titles["none"],
                    assigned_by=assigner,
                    assigned_to=assignee,
                ),
            ]
        )
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        role = Roles(name=f"task-reader-{suffix}", note="Consulta de ventas")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=assignee, role_id=role.id, active=True),
                UserCompanyAccess(user_id=assignee, company_code=company_alpha),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "assignee": assignee,
            **titles,
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


def _revoke_alpha_access(app, user_id: str) -> None:
    """Remove the user's explicit grant for the alpha company."""
    with app.app_context():
        database.session.execute(database.delete(UserCompanyAccess).filter_by(user_id=user_id))
        database.session.commit()


def test_inbox_and_badge_count_only_tasks_in_authorized_companies(task_revocation_scenario):
    """Before revocation the assignee sees alpha and company-less tasks only."""
    app, ids = task_revocation_scenario
    client = _authenticated_client(app, ids["assignee"])

    response = client.get("/tasks/my")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha"] in body
    assert ids["none"] in body
    assert ids["beta"] not in body

    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        assert open_task_count(ids["assignee"]) == 2


def test_revoking_company_access_removes_inbox_and_badge_entries(task_revocation_scenario):
    """After losing alpha, its task disappears from the inbox, filter and badge."""
    app, ids = task_revocation_scenario
    _revoke_alpha_access(app, ids["assignee"])
    client = _authenticated_client(app, ids["assignee"])

    response = client.get("/tasks/my")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha"] not in body
    assert ids["beta"] not in body
    assert ids["none"] in body

    filtered = client.get(f"/tasks/my?company={ids['company_alpha']}")
    assert filtered.status_code == 200
    filtered_body = filtered.get_data(as_text=True)
    assert ids["alpha"] not in filtered_body
    assert ids["none"] not in filtered_body

    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        assert open_task_count(ids["assignee"]) == 1
