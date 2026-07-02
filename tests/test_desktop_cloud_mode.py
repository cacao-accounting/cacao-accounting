# SPDX-License-Identifier: Apache-2.0
"""Tests for desktop restrictions and cloud collaboration."""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AuditTrail,
    ComprobanteContable,
    DocumentTask,
    Entity,
    Modules,
    User,
    database,
)


@pytest.fixture()
def app_ctx():
    """Create an isolated app with the minimal collaboration fixtures."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "desktop-cloud-tests",
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        _seed_base_data()
        yield app
        database.session.remove()
        database.drop_all()


def _seed_base_data() -> None:
    database.session.add_all(
        [
            Entity(
                id="entity-id",
                code="cacao",
                name="Cacao",
                company_name="Cacao",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
            ),
            Modules(id="module-accounting", module="accounting", default=True, enabled=True),
            Modules(id="module-admin", module="admin", default=True, enabled=True),
            User(id="admin-id", user="admin", name="Admin", password=b"x", classification="admin", active=True),
            User(
                id="assignee-id",
                user="assignee",
                name="Assignee",
                password=b"x",
                classification="user",
                active=True,
            ),
            User(
                id="inactive-id",
                user="inactive",
                name="Inactive",
                password=b"x",
                classification="user",
                active=False,
            ),
            ComprobanteContable(
                id="journal-id",
                entity="cacao",
                user_id="admin-id",
                date=date(2026, 5, 24),
                memo="Comprobante de prueba",
                document_no="CC-001",
                status="draft",
            ),
        ]
    )
    database.session.commit()


def _login(client, user_id: str = "admin-id") -> None:
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def test_desktop_mode_rejects_collaboration_endpoints(app_ctx) -> None:
    """Desktop mode rejects document comments and task pages."""
    app_ctx.config["MODO_ESCRITORIO"] = True
    client = app_ctx.test_client()
    _login(client)

    response = client.post(
        "/api/documents/journal_entry/journal-id/comments",
        json={"comment": "Comentario no permitido"},
    )
    assert response.status_code == 403

    response = client.get("/tasks/my")
    assert response.status_code == 403


def test_desktop_mode_blocks_second_user(app_ctx) -> None:
    """Desktop installations cannot create another user once one exists."""
    app_ctx.config["MODO_ESCRITORIO"] = True
    client = app_ctx.test_client()
    _login(client)

    response = client.post("/settings/users/new", data={"usuario": "nuevo"})

    assert response.status_code == 403


def test_single_entity_blocks_second_company_but_not_users(app_ctx, monkeypatch) -> None:
    """Explicit single-entity mode blocks companies without blocking users."""
    from cacao_accounting.setup.service import create_company

    app_ctx.config["MODO_ESCRITORIO"] = False
    monkeypatch.setenv("CACAO_ACCOUNTING_FORCE_SINGLE_ENTITY", "true")

    with pytest.raises(ValueError):
        create_company(
            {
                "id": "segunda",
                "nombre": "Segunda",
                "razon_social": "Segunda SA",
                "identificacion": "J0002",
                "moneda": "NIO",
            }
        )

    client = app_ctx.test_client()
    _login(client)
    response = client.get("/settings/users/new")
    assert response.status_code == 200


def test_cloud_comment_and_task_flow_records_audit_trail(app_ctx) -> None:
    """Cloud collaboration creates comments, tasks, status changes, and audit entries."""
    client = app_ctx.test_client()
    _login(client)

    comment_response = client.post(
        "/api/documents/journal_entry/journal-id/comments",
        json={"comment": "Revisar soporte adjunto"},
    )
    assert comment_response.status_code == 201

    inactive_response = client.post(
        "/api/documents/journal_entry/journal-id/tasks",
        json={"title": "No asignar", "assigned_to": "inactive-id"},
    )
    assert inactive_response.status_code == 400

    task_response = client.post(
        "/api/documents/journal_entry/journal-id/tasks",
        json={
            "title": "Validar comprobante",
            "description": "Confirmar que los soportes coinciden.",
            "assigned_to": "admin-id",
            "priority": "high",
            "due_date": "2026-05-31",
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.get_json()["id"]

    task = database.session.get(DocumentTask, task_id)
    assert task is not None
    assert task.status == "open"
    assert task.priority == "high"

    list_response = client.get("/tasks/my?status=open")
    assert list_response.status_code == 200
    assert "Validar comprobante" in list_response.get_data(as_text=True)

    for status in ("in_progress", "completed", "cancelled"):
        status_response = client.post(f"/api/tasks/{task_id}/status", json={"status": status})
        assert status_response.status_code == 200
        assert status_response.get_json()["status"] == status

    actions = [
        row.action
        for row in database.session.execute(database.select(AuditTrail).where(AuditTrail.document_id == "journal-id"))
        .scalars()
        .all()
    ]
    assert "commented" in actions
    assert "task_created" in actions
    assert "task_status_changed" in actions
    assert "task_completed" in actions
    assert "task_cancelled" in actions
