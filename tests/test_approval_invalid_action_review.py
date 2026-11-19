# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2063: una acción desconocida no rechaza una revisión."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.admin import services as admin_services
from cacao_accounting.database import ApprovalRequest, User, database


def test_accion_invalida_no_rechaza_la_revision(app, entorno_contable, monkeypatch):
    """El handler valida la acción antes de despachar a approve/reject."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        req = ApprovalRequest(
            document_type="bank_reconciliation",
            document_id=f"REC-{suffix}",
            company_id="cacao",
            requested_by=admin.id,
            current_level=1,
            required_level=1,
            status="Pending Approval",
        )
        database.session.add(req)
        database.session.commit()
        req_id = req.id

    mensajes: list[str] = []
    monkeypatch.setattr(admin_services, "flash_error", lambda exc: mensajes.append(str(exc)))
    with app.test_request_context("/", method="POST", data={"request_id": req_id, "action": "bogus"}):
        admin_services._process_pending_approval_post(ApprovalRequest, lambda _tipo: object)

    with app.app_context():
        actual = database.session.get(ApprovalRequest, req_id)
        assert actual.status == "Pending Approval"
    assert mensajes and "no es válida" in mensajes[0]
