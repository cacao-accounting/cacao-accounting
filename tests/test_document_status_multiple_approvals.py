# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1613: varias solicitudes de aprobación no rompen el estado documental."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.database import ApprovalRequest, User, database
from cacao_accounting.document_flow.status import calculate_document_status


def test_estado_usa_la_solicitud_pendiente_entre_varias(app):
    """Una solicitud rechazada anterior no provoca MultipleResultsFound."""
    sufijo = uuid4().hex[:8]
    documento = SimpleNamespace(
        id=f"DOC-{sufijo}",
        company="cacao",
        docstatus=1,
        grand_total=0,
        document_type="sales_invoice",
    )
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        database.session.add_all(
            [
                ApprovalRequest(
                    document_type="sales_invoice",
                    document_id=documento.id,
                    company_id="cacao",
                    requested_by=admin.id,
                    current_level=1,
                    required_level=1,
                    status="Rejected",
                ),
                ApprovalRequest(
                    document_type="sales_invoice",
                    document_id=documento.id,
                    company_id="cacao",
                    requested_by=admin.id,
                    current_level=1,
                    required_level=1,
                    status="Pending Approval",
                ),
            ]
        )
        database.session.commit()

        estado = calculate_document_status("sales_invoice", documento)

        assert estado.code == "pending_approval"
        assert estado.label == "Pendiente de Aprobación"

        database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.document_id == documento.id))
        database.session.commit()
