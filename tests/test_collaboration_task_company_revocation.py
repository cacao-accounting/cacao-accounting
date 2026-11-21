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
from cacao_accounting import collaboration_service
from cacao_accounting.collaboration_service import (
    CollaborationError,
    open_task_count,
    update_task_status,
)
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
        sales_module = database.session.execute(database.select(Modules.id).filter_by(module="sales")).scalar_one()
        inventory_module = database.session.execute(database.select(Modules.id).filter_by(module="inventory")).scalar_one()
        sales_role = Roles(name=f"task-sales-{suffix}", note="Consulta de ventas")
        inventory_role = Roles(name=f"task-inventory-{suffix}", note="Consulta de inventario")
        database.session.add_all([sales_role, inventory_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=sales_role.id, module_id=sales_module, access=True, view=True),
                RolesAccess(rol_id=inventory_role.id, module_id=inventory_module, access=True, view=True),
                RolesUser(user_id=assignee, role_id=sales_role.id, active=True),
                RolesUser(user_id=assignee, role_id=inventory_role.id, active=True),
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
    assert ids["none"] not in body
    assert ids["beta"] not in body

    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        assert open_task_count(ids["assignee"]) == 1


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
    assert ids["none"] not in body

    filtered = client.get(f"/tasks/my?company={ids['company_alpha']}")
    assert filtered.status_code == 200
    filtered_body = filtered.get_data(as_text=True)
    assert ids["alpha"] not in filtered_body
    assert ids["none"] not in filtered_body

    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        assert open_task_count(ids["assignee"]) == 0


def test_revoking_module_role_hides_document_tasks(task_revocation_scenario):
    """Losing the document module hides its tasks even with company access (#1595)."""
    app, ids = task_revocation_scenario
    with app.app_context():
        database.session.execute(database.delete(RolesUser).filter_by(user_id=ids["assignee"]))
        database.session.commit()
    client = _authenticated_client(app, ids["assignee"])

    response = client.get("/tasks/my")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha"] not in body
    assert ids["beta"] not in body
    assert ids["none"] not in body

    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        assert open_task_count(ids["assignee"]) == 0


def test_task_filters_do_not_reintroduce_revoked_tasks(task_revocation_scenario):
    """Los filtros de la bandeja tampoco devuelven tareas fuera de alcance (#1572).

    El scoping se aplica antes de los filtros opcionales; probar `status`,
    `priority` y `company` evita que una combinación de query string vuelva a
    exponer el título o la referencia de una tarea revocada.
    """
    app, ids = task_revocation_scenario
    _revoke_alpha_access(app, ids["assignee"])
    client = _authenticated_client(app, ids["assignee"])

    for query in (
        "status=open",
        "priority=normal",
        f"company={ids['company_alpha']}&status=open",
    ):
        response = client.get(f"/tasks/my?{query}")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ids["alpha"] not in body
        assert ids["beta"] not in body

    filtered_company = client.get(f"/tasks/my?company={ids['company_alpha']}")
    assert ids["none"] not in filtered_company.get_data(as_text=True)


def test_task_with_a_document_from_another_company_is_hidden(task_revocation_scenario):
    """A mismatched polymorphic task cannot expose the other company document."""
    app, ids = task_revocation_scenario
    title = "Tarea inconsistente de otra compañía"
    with app.app_context():
        from cacao_accounting.database import DeliveryNote

        beta = database.session.execute(database.select(DeliveryNote).filter_by(company=ids["company_beta"])).scalar_one()
        database.session.add(
            DocumentTask(
                document_type="delivery_note",
                document_id=beta.id,
                document_no=beta.document_no,
                company=ids["company_alpha"],
                title=title,
                assigned_by=ids["assignee"],
                assigned_to=ids["assignee"],
            )
        )
        database.session.commit()

    client = _authenticated_client(app, ids["assignee"])
    body = client.get("/tasks/my").get_data(as_text=True)

    assert title not in body
    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        assert open_task_count(ids["assignee"]) == 1


def test_task_with_unresolvable_document_cannot_change_status(task_revocation_scenario):
    """Una tarea cuyo documento no se puede validar no puede mutar de estado."""
    app, ids = task_revocation_scenario
    with app.app_context():
        task = DocumentTask(
            document_type="delivery_note",
            document_id="01MISSING0000000000000000",
            document_no="DN-HUERFANA",
            company=ids["company_alpha"],
            title="Tarea huérfana",
            assigned_by=ids["assignee"],
            assigned_to=ids["assignee"],
        )
        database.session.add(task)
        database.session.commit()
        task_id = task.id

    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        with pytest.raises(CollaborationError) as error:
            update_task_status(task_id, "completed", ids["assignee"])
        assert error.value.status_code == 404

    with app.app_context():
        assert database.session.get(DocumentTask, task_id).status == "open"


def test_open_task_count_resolves_documents_in_bulk(task_revocation_scenario, monkeypatch):
    """El badge no consulta cada documento con `get_document` (#N2)."""
    app, ids = task_revocation_scenario

    def fail_per_row(*_args, **_kwargs):
        raise AssertionError("open_task_count no debe resolver documentos fila a fila")

    monkeypatch.setattr(collaboration_service, "get_document", fail_per_row)

    with app.test_request_context("/tasks/my"):
        from flask_login import login_user

        login_user(database.session.get(User, ids["assignee"]))
        assert open_task_count(ids["assignee"]) == 1
