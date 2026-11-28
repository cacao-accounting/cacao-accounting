# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1467: solo el asignado o el creador cambian el estado de una tarea.

El acceso de consulta al documento no concede gestión de tareas. Un lector
ajeno recibe 403 y la tarea conserva su estado; el asignado y el asignador
mantienen el ciclo de vida.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
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

TASK_STATUS_URL = "/api/tasks/{task_id}/status"


@pytest.fixture
def task_status_scenario():
    """Create a task assigned to one reader with an unrelated third reader."""
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
    company = f"c{suffix}"
    assignee = f"assignee-{suffix}"
    assigner = f"assigner-{suffix}"
    viewer = f"viewer-{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code=company,
                    name="Cacao",
                    company_name=f"Compañía Cacao {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id=assignee,
                    user=assignee,
                    name="Asignado",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
                User(
                    id=assigner,
                    user=assigner,
                    name="Asignador",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
                User(
                    id=viewer,
                    user=viewer,
                    name="Lector ajeno",
                    password=b"unused",
                    active=True,
                    company=company,
                ),
            ]
        )
        database.session.flush()
        note = DeliveryNote(
            company=company,
            document_no=f"DN-{suffix}",
            customer_name="Cliente Cacao",
            posting_date=date(2026, 5, 10),
        )
        database.session.add(note)
        database.session.flush()
        task = DocumentTask(
            document_type="delivery_note",
            document_id=note.id,
            document_no=note.document_no,
            company=company,
            title=f"Revisar entrega {suffix}",
            assigned_by=assigner,
            assigned_to=assignee,
            status="open",
        )
        database.session.add(task)
        inventory_module = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        inventory_role = Roles(name=f"task-viewer-{suffix}", note="Consulta de inventario")
        database.session.add(inventory_role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=inventory_role.id, module_id=inventory_module, access=True, view=True),
                RolesUser(user_id=assignee, role_id=inventory_role.id, active=True),
                RolesUser(user_id=assigner, role_id=inventory_role.id, active=True),
                RolesUser(user_id=viewer, role_id=inventory_role.id, active=True),
                UserCompanyAccess(user_id=assignee, company_code=company),
                UserCompanyAccess(user_id=assigner, company_code=company),
                UserCompanyAccess(user_id=viewer, company_code=company),
            ]
        )
        database.session.commit()
        ids = {
            "assignee": assignee,
            "assigner": assigner,
            "viewer": viewer,
            "task": task.id,
            "title": task.title,
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


def _task_status(app, task_id: str) -> str:
    """Read the persisted status of the task."""
    with app.app_context():
        task = database.session.get(DocumentTask, task_id)
        assert task is not None
        return task.status


def test_reader_with_document_access_cannot_change_foreign_task(task_status_scenario):
    """A non-assigned reader gets 403 and the task keeps its state."""
    app, ids = task_status_scenario
    client = _authenticated_client(app, ids["viewer"])

    response = client.post(TASK_STATUS_URL.format(task_id=ids["task"]), json={"status": "completed"})

    assert response.status_code == 403
    assert _task_status(app, ids["task"]) == "open"


def test_assignee_can_complete_the_task(task_status_scenario):
    """The assigned user keeps the task lifecycle."""
    app, ids = task_status_scenario
    client = _authenticated_client(app, ids["assignee"])

    response = client.post(TASK_STATUS_URL.format(task_id=ids["task"]), json={"status": "completed"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "completed"
    assert _task_status(app, ids["task"]) == "completed"


def test_assigner_can_reopen_the_task(task_status_scenario):
    """The user who created the assignment can also move the status."""
    app, ids = task_status_scenario
    client = _authenticated_client(app, ids["viewer"])
    assert client.post(TASK_STATUS_URL.format(task_id=ids["task"]), json={"status": "in_progress"}).status_code == 403

    assigner_client = _authenticated_client(app, ids["assigner"])
    response = assigner_client.post(TASK_STATUS_URL.format(task_id=ids["task"]), json={"status": "in_progress"})

    assert response.status_code == 200
    assert _task_status(app, ids["task"]) == "in_progress"


def test_inbox_post_also_rejects_a_foreign_reader(task_status_scenario):
    """The HTML inbox honors the same ownership rule as the JSON endpoint."""
    app, ids = task_status_scenario
    client = _authenticated_client(app, ids["viewer"])

    response = client.post("/tasks/my", data={"task_id": ids["task"], "status": "cancelled"})

    assert response.status_code == 403
    assert _task_status(app, ids["task"]) == "open"
