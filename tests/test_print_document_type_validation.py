# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La impresión de un tipo de documento desconocido falla de forma controlada.

Escenario operativo: un usuario abre un enlace de impresión con un tipo de
documento que no existe en el registro (por ejemplo, un enlace viejo o un
``document_type`` escrito a mano). El sistema debe responder 404, no 500, y
debe dejar constancia del intento fallido en la bitácora de impresión.
"""

from __future__ import annotations

from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintJobLog


def _last_print_job(app, document_type: str) -> PrintJobLog:
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
