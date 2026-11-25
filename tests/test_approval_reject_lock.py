# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2076: rechazo y aprobación serializan la solicitud."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.database import ApprovalAction, ApprovalRequest, User, database


def _solicitud(app):
    """Crea un documento y su solicitud pendiente con un aprobador real."""
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
        return documento, solicitud.id, SimpleNamespace(id=admin.id)


def test_un_segundo_rechazo_observa_la_solicitud_ya_rechazada(app, entorno_contable, monkeypatch):
    """La segunda operación falla y no registra una acción duplicada."""
    documento, solicitud_id, admin_user = _solicitud(app)
    monkeypatch.setattr(ApprovalEngine, "is_enabled", classmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "can_approve", staticmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "_get_user_rules", classmethod(lambda *_args, **_kwargs: []))

    with app.app_context():
        ApprovalEngine.reject(documento, admin_user, "Primer rechazo")
        database.session.commit()
        first = database.session.get(ApprovalRequest, solicitud_id)
        assert first.status == "Rejected"

        with pytest.raises(ValueError, match="No existe ninguna solicitud|no está pendiente"):
            ApprovalEngine.reject(documento, admin_user, "Segundo rechazo")

        assert database.session.get(ApprovalRequest, solicitud_id).status == "Rejected"
        acciones = (
            database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=solicitud_id))
            .scalars()
            .all()
        )
        assert len(acciones) == 1
        assert acciones[0].comments == "Primer rechazo"


def test_un_rechazo_no_revive_al_aprobar(app, entorno_contable, monkeypatch):
    """Aprobar tras un rechazo no crea solicitud ni publica el documento."""
    del entorno_contable
    documento, solicitud_id, admin_user = _solicitud(app)
    regla = SimpleNamespace(id=None, role_id=None, max_amount=None, approval_level=1)
    monkeypatch.setattr(ApprovalEngine, "is_enabled", classmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "can_approve", staticmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "_get_user_rules", classmethod(lambda *_args, **_kwargs: [regla]))
    monkeypatch.setattr(ApprovalEngine, "_find_applicable_rule", staticmethod(lambda *_args, **_kwargs: regla))
    monkeypatch.setattr(ApprovalEngine, "_lock_document", classmethod(lambda *_args, **_kwargs: None))
    publicado: list[str] = []

    def no_publicar(cls, req, document, user):
        publicado.append(req.document_id)
        return True

    monkeypatch.setattr(ApprovalEngine, "_finalize_approval", classmethod(no_publicar))

    with app.app_context():
        ApprovalEngine.reject(documento, admin_user, "Rechazo confirmado")
        database.session.commit()

        with pytest.raises(ValueError, match="fue rechazada"):
            ApprovalEngine.approve(documento, admin_user, "Aprobación tardía")

        solicitudes = (
            database.session.execute(database.select(ApprovalRequest).where(ApprovalRequest.document_id == documento.id))
            .scalars()
            .all()
        )
        assert [item.id for item in solicitudes] == [solicitud_id]
        assert solicitudes[0].status == "Rejected"
        acciones = (
            database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=solicitud_id))
            .scalars()
            .all()
        )
        assert len(acciones) == 1
        assert acciones[0].action == "reject"
        assert publicado == []
