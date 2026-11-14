# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La impresión de un tipo de documento desconocido falla de forma controlada.

Escenario operativo: un usuario abre un enlace de impresión con un tipo de
documento que no existe en el registro (por ejemplo, un enlace viejo o un
``document_type`` escrito a mano). El sistema debe responder 404, no 500, y
debe dejar constancia del intento fallido en la bitácora de impresión.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintJobLog, PrintTemplate


def _last_print_job(app, document_type: str) -> PrintJobLog | None:
    """Devuelve el último trabajo de impresión registrado para el tipo dado."""
    with app.app_context():
        return (
            database.session.execute(
                database.select(PrintJobLog).where(PrintJobLog.document_type == document_type).order_by(PrintJobLog.id.desc())
            )
            .scalars()
            .first()
        )


def test_preview_de_tipo_no_registrado_responde_404_y_registra_fallo(app, authenticated_client):
    """La vista previa de un tipo desconocido es un 404 y queda auditada."""
    client = authenticated_client("admin")

    response = client.get("/print/not-registered/audit-document/preview")

    assert response.status_code == 404
    job = _last_print_job(app, "not-registered")
    assert job is not None
    assert job.success is False
    assert job.output_format == "html_preview"
    assert "no registrado" in (job.error_message or "").lower()


def test_pdf_de_tipo_no_registrado_responde_404_y_registra_fallo(app, authenticated_client):
    """La descarga PDF de un tipo desconocido también es un 404 auditado."""
    client = authenticated_client("admin")

    response = client.get("/print/not-registered/audit-document/pdf")

    assert response.status_code == 404
    job = _last_print_job(app, "not-registered")
    assert job is not None
    assert job.success is False
    assert job.output_format == "pdf"
    assert "no registrado" in (job.error_message or "").lower()


def test_create_template_does_not_persist_unregistered_document_type(app, authenticated_client):
    """Un POST manipulado no debe dejar un borrador que nunca se pueda publicar."""
    client = authenticated_client("admin")
    code = f"invalid-document-type-{uuid4().hex}"

    response = client.post(
        "/admin/print-templates/new",
        data={
            "document_type": "not-registered-audit",
            "code": code,
            "name": "Invalid template type",
            "template_body": "<html><body>Safe sample</body></html>",
            "stylesheet_body": "",
            "paper_size": "letter",
            "orientation": "portrait",
        },
    )

    assert response.status_code == 200
    with app.app_context():
        persisted = database.session.execute(select(PrintTemplate).filter_by(code=code)).scalar_one_or_none()
        assert persisted is None
