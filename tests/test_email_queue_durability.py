# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1958: la cola de correo conserva evidencia si falla la entrega o el commit."""

from __future__ import annotations

from types import SimpleNamespace

from cacao_accounting.api import _send_document_emails
from cacao_accounting.database import EmailQueue, database


def _cola() -> list[EmailQueue]:
    return database.session.execute(database.select(EmailQueue).order_by(EmailQueue.recipient)).scalars().all()


def test_fallo_de_entrega_conserva_la_fila_reintentable(app, monkeypatch):
    """La fila queda durable antes de SMTP y sobrevive al fallo de entrega."""
    monkeypatch.setattr(
        "cacao_accounting.messaging.email.deliver_email_queue_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("SMTP caído")),
        raising=False,
    )
    with app.app_context():
        sent, newly, errors = _send_document_emails("sales_invoice", "INV-1", ["uno@example.com"], "Asunto", "Cuerpo")

        filas = _cola()
        assert len(filas) == 1
        assert filas[0].status == "pending"
        assert filas[0].attempts == 1
        assert sent == [] and newly == [] and errors


def test_entrega_parcial_registra_cada_destinatario(app, monkeypatch):
    """Un destinatario aceptado y otro fallido dejan estados independientes."""
    estado = {"uno@example.com": True, "dos@example.com": False}
    llamadas: list[str] = []

    def deliver(queue_id: str, retry: bool = False):
        item = database.session.get(EmailQueue, queue_id)
        llamadas.append(item.recipient)
        if estado[item.recipient]:
            item.status = "sent"
            database.session.commit()
            return SimpleNamespace(status="sent"), True
        raise RuntimeError("rebotado")

    monkeypatch.setattr("cacao_accounting.messaging.email.deliver_email_queue_item", deliver, raising=False)

    with app.app_context():
        sent, newly, errors = _send_document_emails(
            "sales_invoice", "INV-2", ["uno@example.com", "dos@example.com"], "Asunto", "Cuerpo"
        )

        filas = {fila.recipient: fila for fila in _cola()}
        assert llamadas == ["uno@example.com", "dos@example.com"]
        assert sent == ["uno@example.com"]
        assert newly == ["uno@example.com"]
        assert len(errors) == 1
        assert filas["uno@example.com"].status == "sent"
        assert filas["dos@example.com"].status == "pending"
