# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2063/#1017: una acción desconocida no rechaza una revisión."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.admin import services as admin_services
from cacao_accounting.database import ApprovalAction, ApprovalRequest, User, database


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


def test_post_de_revision_con_accion_invalida_no_muta_estado_ni_auditoria(entorno_contable_aislado):
    """#1017: el endpoint rechaza el payload inválido sin crear acción de revisión."""
    application = entorno_contable_aislado.app
    with application.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        req = ApprovalRequest(
            document_type="bank_reconciliation",
            document_id="RECON-INVALID-ACTION",
            company_id="cacao",
            requested_by=admin.id,
            current_level=1,
            required_level=1,
            status="Pending Approval",
        )
        database.session.add(req)
        database.session.commit()
        req_id = req.id
        user_id = str(admin.id)
        auth_version = admin.auth_version

    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    try:
        response = client.post("/me/pending-approvals", data={"request_id": req_id, "action": "typo"})

        assert response.status_code == 302
        with application.app_context():
            persisted = database.session.get(ApprovalRequest, req_id)
            actions = (
                database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=req_id)).scalars().all()
            )
            assert persisted is not None and persisted.status == "Pending Approval"
            assert actions == []
    finally:
        with application.app_context():
            database.session.execute(database.delete(ApprovalAction).where(ApprovalAction.approval_request_id == req_id))
            database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.id == req_id))
            database.session.commit()
