# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1638: el estado y el detalle reflejan una anulación pendiente."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.database import ApprovalRequest, SalesInvoice, User, database
from cacao_accounting.document_flow.status import calculate_document_status, document_status_payload


def _factura_pendiente() -> tuple[str, str]:
    sufijo = uuid4().hex[:6]
    usuario = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
    factura = SalesInvoice(
        company="cacao",
        posting_date=date(2026, 5, 15),
        document_type="sales_debit_note",
        docstatus=1,
        status="open",
        customer_name="Cliente 1638",
        document_no=f"ND-{sufijo}",
    )
    database.session.add(factura)
    database.session.flush()
    solicitud = ApprovalRequest(
        document_type="cancel_sales_debit_note",
        document_id=factura.id,
        company_id="cacao",
        requested_by=usuario.id,
        current_level=1,
        required_level=1,
        status="Pending Cancellation",
        cancellation_date=date(2026, 5, 15),
        cancellation_reason="Anulación solicitada",
    )
    database.session.add(solicitud)
    database.session.commit()
    return factura.id, solicitud.id


def test_estado_calculado_reconoce_la_solicitud_cancel(app, entorno_contable):
    """La fila cancel_<doctype> gobierna el estado visible del documento original."""
    del entorno_contable
    with app.app_context():
        factura_id, solicitud_id = _factura_pendiente()
        try:
            factura = database.session.get(SalesInvoice, factura_id)
            estado = calculate_document_status("sales_debit_note", factura)
            payload = document_status_payload("sales_debit_note", factura_id)

            assert estado.code == "pending_cancellation"
            assert estado.label == "Anulación Pendiente"
            assert payload["code"] == "pending_cancellation"
        finally:
            database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.id == solicitud_id))
            database.session.execute(database.delete(SalesInvoice).where(SalesInvoice.id == factura_id))
            database.session.commit()


def test_detalle_muestra_el_badge_y_oculta_anular(app, authenticated_client, entorno_contable):
    """Con la anulación pendiente no se ofrece otra acción de anulación."""
    del entorno_contable
    with app.app_context():
        factura_id, solicitud_id = _factura_pendiente()

    try:
        response = authenticated_client("admin").get(f"/sales/sales-invoice/{factura_id}")

        assert response.status_code == 200
        cuerpo = response.get_data(as_text=True)
        assert "Anulación Pendiente" in cuerpo
        assert f"/sales/sales-invoice/{factura_id}/cancel" not in cuerpo
    finally:
        with app.app_context():
            database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.id == solicitud_id))
            database.session.execute(database.delete(SalesInvoice).where(SalesInvoice.id == factura_id))
            database.session.commit()
