# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2076: rechazo y aprobación serializan la solicitud."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.database import ApprovalRequest, User, database


def test_rechazo_bloquea_la_solicitud_y_revalida_estado(app, entorno_contable, monkeypatch):
    """El rechazo usa el mismo lock que la aprobación antes de transicionar."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        documento = SimpleNamespace(id=f"DOC-{suffix}", company="cacao", document_type="sales_invoice")
        solicitud = ApprovalRequest(
            document_type="sales_invoice",
            document_id=documento.id,
            company_id="cacao",
            requested_by=admin.id,
            current_level=1,
            required_level=1,
            status="Pending Approval",
        )
        database.session.add(solicitud)
        database.session.commit()
        solicitud_id = solicitud.id
        admin_user = SimpleNamespace(id=admin.id)

    llamadas: list[bool] = []
    original = ApprovalEngine._pending_request.__func__

    def tracking(cls, document, *, lock=False):
        llamadas.append(lock)
        return original(cls, document, lock=lock)

    monkeypatch.setattr(ApprovalEngine, "_pending_request", classmethod(tracking))
    monkeypatch.setattr(ApprovalEngine, "can_approve", staticmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "_get_user_rules", classmethod(lambda *_args, **_kwargs: []))

    with app.app_context():
        ApprovalEngine.reject(documento, admin_user, "Rechazo de prueba")
        database.session.commit()
        actual = database.session.get(ApprovalRequest, solicitud_id)
        assert actual.status == "Rejected"

    assert True in llamadas
