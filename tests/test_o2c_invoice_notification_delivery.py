"""Business regression for concurrent invoice notification delivery."""

from __future__ import annotations

import os
from importlib import import_module
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4

import pytest


from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditTrail, Currency, EmailQueue, Entity, Party, SalesInvoice, User, database
from cacao_accounting.messaging.email import retry_email_queue_item


pytestmark = pytest.mark.database


@pytest.fixture
def invoice_email_app(tmp_path):
    """Create Cloud-mode storage for one posted invoice and its notification."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'invoice-notification.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        suffix = uuid4().hex[:9]
        currency_code = f"C{suffix}"
        company_code = f"M{suffix}"
        actor_id = f"mail-{suffix}"
        customer_code = f"MAIL-{suffix}"
        database.create_all()
        database.session.add(Currency(code=currency_code, name="Córdoba", decimals=2, active=True, default=True))
        company = Entity(
            code=company_code,
            name=f"Empresa de notificación {suffix}",
            company_name=f"Empresa de notificación {suffix} SA",
            tax_id=customer_code,
            currency=currency_code,
            enabled=True,
            status="default",
        )
        customer = Party(code=customer_code, name="Cliente de prueba", is_customer=True)
        user = User(
            id=actor_id,
            user=actor_id,
            name="Agente de notificaciones",
            password=b"unused-test-password",
            active=True,
            company=company_code,
        )
        database.session.add_all([company, customer, user])
        database.session.flush()
        invoice = SalesInvoice(
            company=company.code,
            customer_id=customer.id,
            customer_name=customer.name,
            document_no=f"INV-MAIL-{suffix}",
            docstatus=1,
            transaction_currency=currency_code,
            base_currency=currency_code,
            exchange_rate=1,
            total=100,
            grand_total=100,
            base_grand_total=100,
            outstanding_amount=100,
            base_outstanding_amount=100,
        )
        database.session.add(invoice)
        database.session.commit()
        invoice_id = invoice.id
        user_id = user.id

    yield application, invoice_id, user_id

    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_invoice_request_succeeds_when_retry_delivers_first(invoice_email_app, monkeypatch):
    """The initial O2C request reports success when a retry wins the queue row."""
    application, invoice_id, user_id = invoice_email_app
    api_module = import_module("cacao_accounting.api")
    email_module = import_module("cacao_accounting.messaging.email")

    monkeypatch.setattr(email_module, "can_send_transaction_emails", lambda: True)
    monkeypatch.setattr(
        api_module,
        "_require_document_send_access",
        lambda _document_type, document_id: database.session.get(SalesInvoice, document_id),
    )

    initial_reached_delivery = Event()
    allow_initial_delivery = Event()
    send_lock = Lock()
    delivered_messages: list[dict[str, object]] = []
    original_delivery = email_module.deliver_email_queue_item

    def deliver_with_retry_interleaving(queue_id: str, *, retry: bool):
        if not retry:
            initial_reached_delivery.set()
            assert allow_initial_delivery.wait(timeout=10)
        return original_delivery(queue_id, retry=retry)

    def fake_smtp(**message):
        with send_lock:
            delivered_messages.append(message)

    monkeypatch.setattr(email_module, "deliver_email_queue_item", deliver_with_retry_interleaving)
    monkeypatch.setattr(email_module, "send_email", fake_smtp)

    def send_invoice_notification():
        with application.test_client() as client:
            with client.session_transaction() as session:
                session["_user_id"] = user_id
                session["_auth_version"] = 0
                session["_fresh"] = True
            response = client.post(
                f"/api/documents/sales_invoice/{invoice_id}/email",
                json={"recipient": "cliente@example.com", "subject": "Factura INV-MAIL-001"},
            )
            return response.status_code, response.get_json()

    with ThreadPoolExecutor(max_workers=1) as executor:
        initial_request = executor.submit(send_invoice_notification)
        assert initial_reached_delivery.wait(timeout=10)
        with application.app_context():
            queued_email = database.session.execute(
                database.select(EmailQueue).filter_by(document_id=invoice_id, recipient="cliente@example.com")
            ).scalar_one()
            queue_id = queued_email.id
            retry_email_queue_item(queue_id)
        allow_initial_delivery.set()
        status_code, response = initial_request.result(timeout=10)

    with application.app_context():
        database.session.expire_all()
        queued_email = database.session.get(EmailQueue, queue_id)
        audit_events = (
            database.session.execute(
                database.select(AuditTrail).where(
                    AuditTrail.action == "email_sent",
                    AuditTrail.document_id == invoice_id,
                )
            )
            .scalars()
            .all()
        )

        assert status_code == 200
        assert response["success"] is True
        assert response["sent_count"] == 1
        assert len(delivered_messages) == 1
        assert queued_email is not None and queued_email.status == "sent"
        assert queued_email.attempts == 2
        assert len(audit_events) == 1
