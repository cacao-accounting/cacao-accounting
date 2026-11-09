# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La cola de correo conserva evidencia aunque falle el commit posterior.

Escenario de negocio (issue #1958): la fila EmailQueue se confirmaba después
del SMTP; un fallo de commit tras la aceptación del correo eliminaba la
trazabilidad y permitía reenvíos ciegos.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.api import _send_document_emails
from cacao_accounting.config import configuracion
from cacao_accounting.database import EmailQueue, database


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
    return application


def _cola(application):
    return database.session.execute(database.select(EmailQueue).order_by(EmailQueue.recipient)).scalars().all()


def test_la_fila_sobrevive_al_rollback_posterior(monkeypatch):
    """Tras enviar y hacer rollback, la fila sent sigue persistida."""
    application = _crear_app()
    try:
        enviados: list[str] = []
        monkeypatch.setattr(
            "cacao_accounting.messaging.email.send_email",
            lambda **kwargs: enviados.append(kwargs["to_email"]),
        )
        with application.app_context():
            _send_document_emails("sales_invoice", "INV-1", ["ok@example.com"], "Asunto", "Cuerpo")
            database.session.rollback()

            filas = _cola(application)
            assert enviados == ["ok@example.com"]
            assert len(filas) == 1
            assert filas[0].status == "sent"
            assert filas[0].document_id == "INV-1"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_envio_parcial_persiste_cada_resultado(monkeypatch):
    """Un destinatario fallido no oculta el estado del que sí se envió."""
    application = _crear_app()
    try:

        def _envio(**kwargs):
            if kwargs["to_email"] == "fail@example.com":
                raise RuntimeError("SMTP rechazó el destinatario")

        monkeypatch.setattr("cacao_accounting.messaging.email.send_email", _envio)
        with application.app_context():
            enviados, errores = _send_document_emails(
                "sales_invoice",
                "INV-2",
                ["ok@example.com", "fail@example.com"],
                "Asunto",
                "Cuerpo",
            )
            database.session.rollback()

            filas = {fila.recipient: fila.status for fila in _cola(application)}
            assert enviados == ["ok@example.com"]
            assert len(errores) == 1
            assert filas == {"ok@example.com": "sent", "fail@example.com": "failed"}
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_si_falla_el_commit_posterior_queda_evidencia_pendiente(monkeypatch):
    """La fila pre-confirmada sobrevive al fallo del commit de estado."""
    application = _crear_app()
    try:
        monkeypatch.setattr("cacao_accounting.messaging.email.send_email", lambda **kwargs: None)
        with application.app_context():
            commit_real = database.session.commit
            llamadas = {"n": 0}

            def _commit_falla_despues_del_primero():
                llamadas["n"] += 1
                if llamadas["n"] == 2:
                    raise RuntimeError("fallo de commit posterior")
                commit_real()

            monkeypatch.setattr(database.session, "commit", _commit_falla_despues_del_primero)
            try:
                _send_document_emails("sales_invoice", "INV-3", ["ok@example.com"], "Asunto", "Cuerpo")
            except RuntimeError:
                pass
            finally:
                database.session.rollback()
                monkeypatch.setattr(database.session, "commit", commit_real)

            filas = _cola(application)
            assert len(filas) == 1
            assert filas[0].status == "pending"
            assert filas[0].document_id == "INV-3"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
