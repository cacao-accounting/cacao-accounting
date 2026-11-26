# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1958: la cola conserva evidencia con el servicio real de entrega.

Cada caso ejecuta ``deliver_email_queue_item`` sin sustituirlo y solo frena el
transporte SMTP: así se observa el estado real de la fila después del fallo. La
lectura de verificación se hace en una sesión nueva, porque una fila que solo
vive en el identity map no es evidencia.
"""

from __future__ import annotations

import smtplib
from typing import Any
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.api import _send_document_emails
from cacao_accounting.config import configuracion
from cacao_accounting.database import EmailQueue, database


@pytest.fixture
def cola_app(tmp_path, monkeypatch):
    """App cloud con SMTP configurado hacia un transporte que no abre red."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'cola-correo.sqlite'}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "cola-correo-test-secret",
        }
    )
    monkeypatch.setenv("CACAO_SMTP_SERVER", "smtp.invalid.test")
    monkeypatch.setenv("CACAO_SMTP_PORT", "587")
    monkeypatch.setenv("CACAO_SMTP_FROM_EMAIL", "no-reply@cacao.invalid")
    with application.app_context():
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _transporte(registrados: list[str], rechazos: set[str]) -> Any:
    """Clase ``smtplib.SMTP`` falsa que captura aceptaciones y simula rechazos."""

    class _TransporteFalso:
        def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
            self.host = host
            self.port = port

        def ehlo(self) -> None:
            return None

        def starttls(self, context: Any = None) -> None:
            return None

        def login(self, user: str, password: str) -> None:
            return None

        def sendmail(self, from_email: str, to_addrs: list[str], message: str) -> None:
            destinatario = to_addrs[0]
            if destinatario in rechazos:
                raise smtplib.SMTPSenderRefused(550, "usuario desconocido", from_email)
            registrados.append(destinatario)

        def quit(self) -> None:
            return None

    return _TransporteFalso


def _filas_nueva_sesion(application: Any) -> dict[str, EmailQueue]:
    """Relee la cola desde una sesión limpia, sin identidad en caché."""
    database.session.remove()
    with application.app_context():
        filas = database.session.execute(database.select(EmailQueue).order_by(EmailQueue.recipient)).scalars().all()
        return {fila.recipient: fila for fila in filas}


def test_entrega_exitosa_sobrevive_al_rollback(cola_app, monkeypatch):
    """La fila confirmada no depende de la sesión que la escribió."""
    enviados: list[str] = []
    monkeypatch.setattr(smtplib, "SMTP", _transporte(enviados, set()))

    with cola_app.app_context():
        documento = f"INV-OK-{uuid4().hex[:6]}"
        sent, newly, errors = _send_document_emails("sales_invoice", documento, ["ok@example.com"], "Asunto", "Cuerpo")
        database.session.rollback()

    filas = _filas_nueva_sesion(cola_app)
    assert enviados == ["ok@example.com"]
    assert sent == newly == ["ok@example.com"] and errors == []
    assert len(filas) == 1
    assert filas["ok@example.com"].status == "sent"
    assert filas["ok@example.com"].sent_at is not None
    assert filas["ok@example.com"].document_id == documento


def test_fallo_de_smtp_conserva_la_fila_reintentable(cola_app, monkeypatch):
    """Un rechazo del servidor deja evidencia fallida, no una fila perdida."""
    enviados: list[str] = []
    monkeypatch.setattr(smtplib, "SMTP", _transporte(enviados, {"malo@example.com"}))

    with cola_app.app_context():
        _send_document_emails("sales_invoice", "INV-FAIL", ["malo@example.com"], "Asunto", "Cuerpo")

    filas = _filas_nueva_sesion(cola_app)
    assert enviados == []
    assert len(filas) == 1
    assert filas["malo@example.com"].status == "failed"
    assert filas["malo@example.com"].sent_at is None
    assert "550" in (filas["malo@example.com"].error_message or "")


def test_fallo_del_commit_posterior_conserva_evidencia_no_confirmada(cola_app, monkeypatch):
    """Si SMTP aceptó pero el commit de estado falla, la fila queda reconciliable."""
    enviados: list[str] = []
    monkeypatch.setattr(smtplib, "SMTP", _transporte(enviados, set()))
    commit_real = database.session.commit
    llamadas = {"n": 0}

    def _commit_falla_en_el_segundo() -> None:
        """Rompe solo el commit que confirma el envío; el de la fila previa pasa."""
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("fallo de commit posterior")
        commit_real()

    monkeypatch.setattr(database.session, "commit", _commit_falla_en_el_segundo)
    try:
        with cola_app.app_context():
            _send_document_emails("sales_invoice", "INV-COMMIT", ["ok@example.com"], "Asunto", "Cuerpo")
    finally:
        monkeypatch.setattr(database.session, "commit", commit_real)
        database.session.rollback()

    filas = _filas_nueva_sesion(cola_app)
    assert llamadas["n"] >= 2, "el commit de confirmación nunca se intentó: la prueba no discrimina"
    assert len(enviados) == 1, "SMTP aceptó el mensaje antes del fallo"
    assert len(filas) == 1
    fila = filas["ok@example.com"]
    assert fila.status != "sent", "no puede afirmarse un envío cuyo commit falló"
    assert fila.sent_at is None
    assert fila.document_id == "INV-COMMIT"
    assert fila.status in {"pending", "failed"}, "debe quedar visible para conciliar"


def test_entrega_parcial_registra_cada_destinatario(cola_app, monkeypatch):
    """El fallo de un destinatario no borra el estado del que sí se envió."""
    enviados: list[str] = []
    monkeypatch.setattr(smtplib, "SMTP", _transporte(enviados, {"mal@example.com"}))

    with cola_app.app_context():
        sent, newly, errors = _send_document_emails(
            "sales_invoice", "INV-PARC", ["ok@example.com", "mal@example.com"], "Asunto", "Cuerpo"
        )

    filas = _filas_nueva_sesion(cola_app)
    assert enviados == ["ok@example.com"]
    assert sent == newly == ["ok@example.com"]
    assert len(errors) == 1
    assert {correo: fila.status for correo, fila in filas.items()} == {
        "ok@example.com": "sent",
        "mal@example.com": "failed",
    }
