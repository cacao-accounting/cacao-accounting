# SPDX-License-Identifier: Apache-2.0
"""Pruebas para notificaciones por correo electrónico en transacciones operativas."""

from __future__ import annotations

from unittest import mock

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    AuditTrail,
    CacaoConfig,
    CompanyParty,
    EmailQueue,
    Entity,
    Modules,
    Party,
    PurchaseOrder,
    User,
    database,
)
from cacao_accounting.messaging.email import (
    EmailError,
    can_send_transaction_emails,
    get_document_default_recipient_email,
    get_smtp_setting,
    set_smtp_setting,
)


@pytest.fixture()
def app_ctx():
    """Create an isolated app with database in-memory for transaction email tests."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "transaction_email_test_secret",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()

        from cacao_accounting.auth.helpers import ph

        user = User(
            user="admin_email_user",
            name="Admin Email User",
            password=ph.hash("secretpassword").encode("utf-8"),
            classification="admin",
            active=True,
        )
        database.session.add(user)

        entity = Entity(
            code="EMP1", company_name="Compañía Email Test", name="Compañía Email Test", tax_id="123456789", enabled=True
        )
        database.session.add(entity)

        supplier = Party(
            code="SUPP001",
            name="Proveedor Test SA",
            primary_email="proveedor@test.com",
            is_active=True,
        )
        database.session.add(supplier)
        database.session.flush()

        cp = CompanyParty(company=entity.code, party_id=supplier.id, is_active=True)
        database.session.add(cp)

        po = PurchaseOrder(
            id="PO-EMAIL-001",
            document_no="PO-2026-0001",
            company="EMP1",
            supplier_id=supplier.id,
            supplier_name="Proveedor Test SA",
            docstatus=0,
            status="draft",
        )
        database.session.add(po)

        mod = Modules(module="purchases", default=False, enabled=True)
        database.session.add(mod)
        mod_admin = Modules(module="admin", default=True, enabled=True)
        database.session.add(mod_admin)

        database.session.commit()
        yield app
        database.session.remove()
        database.drop_all()


def test_can_send_transaction_emails_desktop_mode(app_ctx):
    """Verify transaction email logic returns False in desktop mode."""
    with app_ctx.app_context():
        app_ctx.config["MODO_ESCRITORIO"] = True
        try:
            assert can_send_transaction_emails() is False
        finally:
            app_ctx.config["MODO_ESCRITORIO"] = False


def test_can_send_transaction_emails_unconfigured(app_ctx):
    """Verify transaction email logic returns False if SMTP is unconfigured."""
    with app_ctx.app_context():
        database.session.execute(database.delete(CacaoConfig))
        database.session.commit()
        assert can_send_transaction_emails() is False


def test_can_send_transaction_emails_enabled_and_disabled(app_ctx):
    """Verify transaction email logic respects SMTP config and admin toggle."""
    with app_ctx.app_context():
        database.session.execute(database.delete(CacaoConfig))
        set_smtp_setting("smtp_server", "smtp.test.com")
        set_smtp_setting("smtp_from_email", "noreply@test.com")
        set_smtp_setting("disable_transaction_emails", "false")
        database.session.commit()

        assert can_send_transaction_emails() is True

        set_smtp_setting("disable_transaction_emails", "true")
        database.session.commit()

        assert can_send_transaction_emails() is False


def test_get_document_default_recipient_email(app_ctx):
    """Verify supplier email resolution for purchase documents."""
    with app_ctx.app_context():
        email = get_document_default_recipient_email("purchase_order", "PO-EMAIL-001")
        assert email == "proveedor@test.com"

        email_nonexistent = get_document_default_recipient_email("purchase_order", "PO-NONEXISTENT")
        assert email_nonexistent == ""


def test_admin_toggle_transaction_emails_view(app_ctx):
    """Verify admin email settings view saves transaction email disable toggle."""
    with app_ctx.test_client() as client:
        client.post("/login", data={"usuario": "admin_email_user", "acceso": "secretpassword"})

        response = client.post(
            "/settings/email",
            data={
                "smtp_server": "smtp.test.com",
                "smtp_port": "587",
                "smtp_from_email": "noreply@test.com",
                "disable_transaction_emails": "on",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app_ctx.app_context():
            assert get_smtp_setting("disable_transaction_emails") == "true"
            assert can_send_transaction_emails() is False


@mock.patch("cacao_accounting.messaging.email.send_email")
def test_api_document_email_info_and_send_success(mock_send_email, app_ctx):
    """Verify GET email-info and POST email dispatch with queue & audit log on success."""
    with app_ctx.app_context():
        set_smtp_setting("smtp_server", "smtp.test.com")
        set_smtp_setting("smtp_from_email", "noreply@test.com")
        set_smtp_setting("disable_transaction_emails", "false")
        database.session.commit()

    with app_ctx.test_client() as client:
        client.post("/login", data={"usuario": "admin_email_user", "acceso": "secretpassword"})

        # Test email-info
        resp_info = client.get("/api/documents/purchase_order/PO-EMAIL-001/email-info")
        assert resp_info.status_code == 200
        data_info = resp_info.get_json()
        assert data_info["enabled"] is True
        assert data_info["default_recipient"] == "proveedor@test.com"

        # Test send email success
        resp_send = client.post(
            "/api/documents/purchase_order/PO-EMAIL-001/email",
            json={
                "recipients": "proveedor@test.com, adicional@test.com",
                "subject": "Prueba de Orden de Compra",
                "body": "Cuerpo del mensaje de prueba",
            },
        )
        assert resp_send.status_code == 200
        data_send = resp_send.get_json()
        assert data_send["success"] is True
        assert data_send["sent_count"] == 2

        assert mock_send_email.call_count == 2

        # Verify AuditTrail record was created
        with app_ctx.app_context():
            logs = (
                database.session.execute(
                    database.select(AuditTrail).where(
                        AuditTrail.document_id == "PO-EMAIL-001",
                        AuditTrail.action == "email_sent",
                    )
                )
                .scalars()
                .all()
            )
            assert len(logs) == 1
            assert "correo enviado exitosamente a proveedor@test.com, adicional@test.com" in logs[0].comment

            queue_items = (
                database.session.execute(database.select(EmailQueue).where(EmailQueue.document_id == "PO-EMAIL-001"))
                .scalars()
                .all()
            )
            assert len(queue_items) == 2
            assert all(item.status == "sent" for item in queue_items)


@mock.patch("cacao_accounting.messaging.email.send_email", side_effect=EmailError("Fallo de conexión SMTP"))
def test_api_document_email_send_failure_queue_recorded(mock_send_email, app_ctx):
    """Verify that email send failure logs failed status in EmailQueue and creates NO audit log."""
    with app_ctx.app_context():
        set_smtp_setting("smtp_server", "smtp.test.com")
        set_smtp_setting("smtp_from_email", "noreply@test.com")
        set_smtp_setting("disable_transaction_emails", "false")
        database.session.commit()

    with app_ctx.test_client() as client:
        client.post("/login", data={"usuario": "admin_email_user", "acceso": "secretpassword"})

        resp = client.post(
            "/api/documents/purchase_order/PO-EMAIL-001/email",
            json={
                "recipients": "proveedor@test.com",
                "subject": "Asunto Test",
                "body": "Cuerpo Test",
            },
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert "Fallo de conexión SMTP" in data["error"]

        with app_ctx.app_context():
            logs = (
                database.session.execute(
                    database.select(AuditTrail).where(
                        AuditTrail.document_id == "PO-EMAIL-001",
                        AuditTrail.action == "email_sent",
                    )
                )
                .scalars()
                .all()
            )
            assert len(logs) == 0

            queue_items = (
                database.session.execute(database.select(EmailQueue).where(EmailQueue.document_id == "PO-EMAIL-001"))
                .scalars()
                .all()
            )
            assert len(queue_items) == 1
            assert queue_items[0].status == "failed"
            assert "Fallo de conexión SMTP" in queue_items[0].error_message


@mock.patch(
    "cacao_accounting.messaging.email.send_email",
    side_effect=[None, EmailError("Segundo destinatario rechazado")],
)
def test_api_document_email_send_reports_partial_delivery(mock_send_email, app_ctx):
    """Report partial delivery and audit only the recipient that succeeded."""
    with app_ctx.app_context():
        set_smtp_setting("smtp_server", "smtp.test.com")
        set_smtp_setting("smtp_from_email", "noreply@test.com")
        set_smtp_setting("disable_transaction_emails", "false")
        database.session.commit()

    with app_ctx.test_client() as client:
        client.post("/login", data={"usuario": "admin_email_user", "acceso": "secretpassword"})
        response = client.post(
            "/api/documents/purchase_order/PO-EMAIL-001/email",
            json={"recipients": "ok@test.com, failed@test.com", "subject": "Asunto", "body": "Cuerpo"},
        )

    assert response.status_code == 207
    data = response.get_json()
    assert data["success"] is False
    assert data["partial"] is True
    assert data["recipients"] == ["ok@test.com"]
    assert "failed@test.com" in data["errors"][0]

    with app_ctx.app_context():
        logs = database.session.execute(
            database.select(AuditTrail).where(
                AuditTrail.document_id == "PO-EMAIL-001", AuditTrail.action == "email_sent"
            )
        ).scalars().all()
        assert len(logs) == 1
        assert "ok@test.com" in logs[0].comment
        assert "failed@test.com" not in logs[0].comment

        queue_items = database.session.execute(
            database.select(EmailQueue)
            .where(EmailQueue.document_id == "PO-EMAIL-001")
            .order_by(EmailQueue.recipient)
        ).scalars().all()
        assert [(item.recipient, item.status) for item in queue_items] == [
            ("failed@test.com", "failed"),
            ("ok@test.com", "sent"),
        ]


def test_admin_email_log_view_and_retry(app_ctx):
    """Verify admin email log view and retry action for failed queue items."""
    with app_ctx.app_context():
        set_smtp_setting("smtp_server", "smtp.test.com")
        set_smtp_setting("smtp_from_email", "noreply@test.com")

        item = EmailQueue(
            document_type="purchase_order",
            document_id="PO-EMAIL-001",
            recipient="retry@test.com",
            subject="Asunto Reintento",
            body="Cuerpo Reintento",
            status="failed",
            error_message="Error previo",
            attempts=1,
        )
        database.session.add(item)
        database.session.commit()
        queue_id = item.id

    with app_ctx.test_client() as client:
        client.post("/login", data={"usuario": "admin_email_user", "acceso": "secretpassword"})

        resp_log = client.get("/settings/email-log")
        assert resp_log.status_code == 200
        assert b"Bit" in resp_log.data and b"cora de Correos" in resp_log.data
        assert b"retry@test.com" in resp_log.data

        with mock.patch("cacao_accounting.messaging.email.send_email") as mock_send:
            resp_retry = client.post(
                f"/settings/email-log/{queue_id}/retry",
                follow_redirects=True,
            )
            assert resp_retry.status_code == 200
            mock_send.assert_called_once_with(
                to_email="retry@test.com",
                subject="Asunto Reintento",
                body="Cuerpo Reintento",
                is_html=False,
            )

        with app_ctx.app_context():
            updated = database.session.get(EmailQueue, queue_id)
            assert updated.status == "sent"
            assert updated.attempts == 2
            assert updated.error_message is None
