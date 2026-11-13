# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Business regressions for retrying invoice notifications."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.api import _send_document_emails
from cacao_accounting.database import AuditTrail, Currency, EmailQueue, Entity, Party, SalesInvoice, database
from cacao_accounting.messaging.email import EmailError, retry_email_queue_item


@pytest.fixture
def cloud_app(tmp_path):
    """Create an isolated Cloud-mode application for a real invoice notification."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'invoice-email.sqlite'}"
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
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _create_posted_invoice(company_id: str) -> SalesInvoice:
    """Create an invoice with a real customer, company, and currency context."""
    currency_code = f"N{company_id[:9]}"
    database.session.add(Currency(code=currency_code, name="Córdoba", decimals=2, active=True, default=True))
    company_code = f"E{company_id[:9]}"
    database.session.add(
        Entity(
            code=company_code,
            name=f"Empresa de notificación {company_id}",
            company_name=f"Empresa de notificación {company_id} SA",
            tax_id=f"TAX-{company_id}",
            currency=currency_code,
            enabled=True,
            status="default",
        )
    )
    customer = Party(code=f"C-{company_id}", name=f"Cliente {company_id}", is_customer=True)
    database.session.add(customer)
    database.session.flush()
    invoice = SalesInvoice(
        company=company_code,
        customer_id=customer.id,
        customer_name=customer.name,
        document_no=f"INV-{company_id}",
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
    return invoice


def _send_invoice_notice(invoice: SalesInvoice, *, is_html: bool = False) -> EmailQueue:
    """Create a queue row through the same writer used by the invoice API."""
    recipients = [f"customer-{invoice.company}@example.com"]
    sent, _newly_sent, errors = _send_document_emails(
        "sales_invoice",
        invoice.id,
        recipients,
        "Factura disponible",
        "<p>La factura está disponible.</p>" if is_html else "La factura está disponible.",
        is_html=is_html,
    )
    assert len(sent) + len(errors) == 1
    return database.session.execute(
        database.select(EmailQueue).filter_by(document_id=invoice.id, recipient=recipients[0])
    ).scalar_one()


def test_concurrent_invoice_email_retry_delivers_once(cloud_app, monkeypatch):
    """Two admins retrying one failed invoice notice produce one delivery."""
    email_module = __import__("cacao_accounting.messaging.email", fromlist=["send_email"])
    with cloud_app.app_context():
        invoice = _create_posted_invoice(uuid4().hex[:9])

        def smtp_rejects(**_message):
            raise RuntimeError("SMTP rechazó la notificación")

        monkeypatch.setattr(email_module, "send_email", smtp_rejects)
        queued_email = _send_invoice_notice(invoice)
        assert queued_email.status == "failed"
        queue_id = queued_email.id

    first_send_started = Event()
    second_send_started = Event()
    release_first_send = Event()
    send_lock = Lock()
    sends: list[dict[str, object]] = []

    def send(**message):
        with send_lock:
            sends.append(message)
            send_count = len(sends)
        if send_count == 1:
            first_send_started.set()
            assert release_first_send.wait(timeout=10)
        else:
            second_send_started.set()

    monkeypatch.setattr(email_module, "send_email", send)

    def retry(*, second: bool = False) -> bool:
        with cloud_app.app_context():
            if second:
                try:
                    retry_email_queue_item(queue_id)
                    return True
                except EmailError:
                    return False
            retry_email_queue_item(queue_id)
            return True

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(retry)
        assert first_send_started.wait(timeout=10)
        second = workers.submit(retry, second=True)
        try:
            assert not second_send_started.wait(timeout=0.5)
        finally:
            release_first_send.set()
        results = [first.result(timeout=10), second.result(timeout=10)]

    with cloud_app.app_context():
        database.session.expire_all()
        queued_email = database.session.get(EmailQueue, queue_id)
        assert queued_email is not None
        assert results.count(True) == 1
        assert results.count(False) == 1
        assert len(sends) == 1
        assert queued_email.status == "sent"
        assert queued_email.attempts == 2
        assert queued_email.error_message is None
        audit_events = (
            database.session.execute(
                database.select(AuditTrail).where(
                    AuditTrail.action == "email_sent",
                    AuditTrail.document_id == queued_email.document_id,
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_events) == 1


def test_retry_waits_for_initial_invoice_delivery(cloud_app, monkeypatch):
    """A retry cannot duplicate a notification while the invoice API sends it."""
    email_module = __import__("cacao_accounting.messaging.email", fromlist=["send_email"])
    with cloud_app.app_context():
        invoice = _create_posted_invoice(uuid4().hex[:9])
        invoice_id = invoice.id
        invoice_company = invoice.company

    initial_send_started = Event()
    retry_send_started = Event()
    release_initial_send = Event()
    send_lock = Lock()
    sends: list[dict[str, object]] = []

    def send(**message):
        with send_lock:
            sends.append(message)
            send_count = len(sends)
        if send_count == 1:
            initial_send_started.set()
            assert release_initial_send.wait(timeout=10)
        else:
            retry_send_started.set()

    monkeypatch.setattr(email_module, "send_email", send)

    def send_initial_notice() -> tuple[list[str], list[str], list[str]]:
        with cloud_app.app_context():
            return _send_document_emails(
                "sales_invoice",
                invoice_id,
                [f"customer-{invoice_company}@example.com"],
                "Factura disponible",
                "La factura está disponible.",
            )

    def retry(queue_id: str) -> bool:
        with cloud_app.app_context():
            try:
                retry_email_queue_item(queue_id)
                return True
            except EmailError:
                return False

    with ThreadPoolExecutor(max_workers=2) as workers:
        initial = workers.submit(send_initial_notice)
        assert initial_send_started.wait(timeout=10), initial.result(timeout=1)
        with cloud_app.app_context():
            queued_email = database.session.execute(database.select(EmailQueue).filter_by(document_id=invoice_id)).scalar_one()
            queue_id = queued_email.id
        retrying = workers.submit(retry, queue_id)
        try:
            assert not retry_send_started.wait(timeout=0.5)
        finally:
            release_initial_send.set()
        sent, newly_sent, errors = initial.result(timeout=10)
        retry_result = retrying.result(timeout=10)

    with cloud_app.app_context():
        database.session.expire_all()
        queued_email = database.session.get(EmailQueue, queue_id)
        assert queued_email is not None
        assert sent == [queued_email.recipient]
        assert newly_sent == [queued_email.recipient]
        assert errors == []
        assert retry_result is False
        assert len(sends) == 1
        assert queued_email.status == "sent"
        assert queued_email.attempts == 1


def test_initial_invoice_request_reports_success_when_retry_wins(cloud_app, monkeypatch):
    """An admin retry that wins the pending row race still counts as sent."""
    email_module = __import__("cacao_accounting.messaging.email", fromlist=["send_email"])
    api_module = __import__("cacao_accounting.api", fromlist=["api_document_send_email"])
    with cloud_app.app_context():
        invoice = _create_posted_invoice(uuid4().hex[:9])
        invoice_id = invoice.id
        invoice_company = invoice.company

    initial_delivery_paused = Event()
    release_initial_delivery = Event()
    delivered_messages: list[dict[str, object]] = []
    actual_delivery = email_module.deliver_email_queue_item

    def pause_initial_delivery(queue_id: str, *, retry: bool):
        if not retry:
            initial_delivery_paused.set()
            assert release_initial_delivery.wait(timeout=10)
        return actual_delivery(queue_id, retry=retry)

    monkeypatch.setattr(email_module, "deliver_email_queue_item", pause_initial_delivery)
    monkeypatch.setattr(email_module, "send_email", lambda **message: delivered_messages.append(message))

    def send_initial_notice():
        with cloud_app.app_context():
            return _send_document_emails(
                "sales_invoice",
                invoice_id,
                [f"customer-{invoice_company}@example.com"],
                "Factura disponible",
                "La factura está disponible.",
            )

    with ThreadPoolExecutor(max_workers=1) as workers:
        initial = workers.submit(send_initial_notice)
        assert initial_delivery_paused.wait(timeout=10)
        with cloud_app.app_context():
            queued_email = database.session.execute(database.select(EmailQueue).filter_by(document_id=invoice_id)).scalar_one()
            queue_id = queued_email.id
            retry_email_queue_item(queue_id)
        release_initial_delivery.set()
        delivery_result = initial.result(timeout=10)

    assert delivery_result[0] == [f"customer-{invoice_company}@example.com"]
    assert delivery_result[1] == []
    assert delivery_result[2] == []
    assert len(delivered_messages) == 1
    with cloud_app.app_context():
        queued_email = database.session.get(EmailQueue, queue_id)
        assert queued_email is not None
        assert queued_email.status == "sent"
        assert queued_email.attempts == 2
        retry_audits = (
            database.session.execute(
                database.select(AuditTrail).where(
                    AuditTrail.action == "email_sent",
                    AuditTrail.document_id == invoice_id,
                )
            )
            .scalars()
            .all()
        )
        assert len(retry_audits) == 1

    monkeypatch.setattr(email_module, "can_send_transaction_emails", lambda: True)
    monkeypatch.setattr(api_module, "_require_document_send_access", lambda *_args: object())
    monkeypatch.setattr(api_module, "_send_document_emails", lambda *_args: delivery_result)
    with cloud_app.test_request_context(
        f"/api/documents/sales_invoice/{invoice_id}/email",
        method="POST",
        json={"recipients": [f"customer-{invoice_company}@example.com"]},
    ):
        response = api_module.api_document_send_email.__wrapped__("sales_invoice", invoice_id)

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_sent_invoice_notification_is_not_delivered_again(cloud_app, monkeypatch):
    """A repeated admin request cannot resend a terminal invoice notification."""
    email_module = __import__("cacao_accounting.messaging.email", fromlist=["send_email"])

    def unexpected_send(**_message):
        pytest.fail("Una notificación sent no debe volver a llegar al transporte.")

    monkeypatch.setattr(email_module, "send_email", unexpected_send)
    with cloud_app.app_context():
        invoice = _create_posted_invoice(uuid4().hex[:9])
        monkeypatch.setattr(email_module, "send_email", lambda **_message: None)
        queued_email = _send_invoice_notice(invoice)
        assert queued_email.status == "sent"
        queue_id = queued_email.id
        monkeypatch.setattr(email_module, "send_email", unexpected_send)
        with pytest.raises(EmailError, match="pendientes o fallidos"):
            retry_email_queue_item(queue_id)
        database.session.expire_all()
        queued_email = database.session.get(EmailQueue, queue_id)
        assert queued_email is not None
        assert queued_email.status == "sent"
        assert queued_email.attempts == 1


def test_uncertain_html_delivery_stays_retryable_after_commit_failure(cloud_app, monkeypatch):
    """A failed local commit leaves an HTML notice retryable under policy B."""
    email_module = __import__("cacao_accounting.messaging.email", fromlist=["send_email"])
    sent_formats: list[bool] = []

    with cloud_app.app_context():
        invoice = _create_posted_invoice(uuid4().hex[:9])

        def smtp_rejects(**_message):
            raise RuntimeError("SMTP rechazó la notificación")

        monkeypatch.setattr(email_module, "send_email", smtp_rejects)
        queued_email = _send_invoice_notice(invoice, is_html=True)
        assert queued_email.status == "failed"
        assert queued_email.is_html is True
        queue_id = queued_email.id
        monkeypatch.setattr(email_module, "send_email", lambda **message: sent_formats.append(bool(message["is_html"])))
        commit_real = database.session.commit
        commit_calls = 0

        def fail_once_after_delivery():
            nonlocal commit_calls
            commit_calls += 1
            if commit_calls == 1:
                raise RuntimeError("fallo de confirmación local")
            commit_real()

        monkeypatch.setattr(database.session, "commit", fail_once_after_delivery)
        with pytest.raises(EmailError, match="fallo de confirmación local"):
            retry_email_queue_item(queue_id)
        monkeypatch.setattr(database.session, "commit", commit_real)

        database.session.expire_all()
        queued_email = database.session.get(EmailQueue, queue_id)
        assert queued_email is not None
        assert queued_email.status == "failed"
        assert queued_email.attempts == 2
        assert "fallo de confirmación local" in queued_email.error_message

        retry_email_queue_item(queue_id)
        assert sent_formats == [True, True]
        database.session.expire_all()
        queued_email = database.session.get(EmailQueue, queue_id)
        assert queued_email is not None
        assert queued_email.status == "sent"
        assert queued_email.attempts == 3
        assert queued_email.error_message is None
