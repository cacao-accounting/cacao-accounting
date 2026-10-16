# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Independent Cloud reviews using the existing approval evidence and RBAC."""

from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Any
from collections.abc import Iterator

from flask_login import current_user

from cacao_accounting.database import ApprovalAction, ApprovalRequest, AuditTrail, User, database
from cacao_accounting.i18n import _

REVIEW_TYPES = frozenset({"bank_reconciliation", "monthly_close", "period_reopen", "config_change"})
_OPERATION_SCOPE = {
    "bank_reconciliation": ("cash", "edit"),
    "config_change": ("admin", "edit"),
    "monthly_close": ("accounting", "close"),
    "period_reopen": ("accounting", "close"),
}
_execution: ContextVar[Any] = ContextVar("control_review_execution", default=None)


def _operation_actor(kind: str, company: str, actor_id: str | None) -> Any:
    """Enforce permanent backend scope and operation permissions, independently of four eyes."""
    from cacao_accounting.approval_policy import authorized

    actor_id = actor_id or getattr(current_user, "id", None)
    actor = database.session.get(User, actor_id) if actor_id else None
    module, action = _OPERATION_SCOPE.get(kind, ("accounting", "close"))
    if actor is None or not authorized(actor, company, module, action):
        raise ValueError(_("No tiene autorización para preparar esta operación."))
    return actor


def _digest(value: Any) -> str:
    """Hash a canonical snapshot without depending on JSON insertion order."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _event(req: Any, action: str, actor: Any, after: Any = None) -> None:
    """Persist explicit actors, preparation snapshots and review outcomes atomically."""
    database.session.add(
        AuditTrail(
            document_type=req.document_type,
            document_id=req.document_id,
            company=req.company_id,
            actor_user_id=actor.id,
            actor_name=actor.name or actor.user,
            action=action,
            after_json=json.dumps(after or req.review_payload, default=str),
            source_module="control_review",
        )
    )


def _preparation_policy(actor: Any, preparer_ids: tuple, module: str) -> dict:
    """Keep every identified preparer's rank in the independent review evidence."""
    from cacao_accounting.approval_policy import module_rank

    ids = sorted({str(actor.id), *(str(value) for value in preparer_ids if value)})
    preparers = []
    for identifier in ids:
        user = database.session.get(User, identifier)
        rank = module_rank(user, module) if user is not None else None
        if user is None or rank is None:
            raise ValueError(_("Los preparadores necesitan un nivel de aprobación configurado."))
        preparers.append({"user_id": user.id, "rank": rank})
    return {
        "requires_independent": True,
        "module": module,
        "preparers": preparers,
    }


def require_review(
    kind: str, identifier: str, company: str, actor_id: str | None, payload: dict, preparer_ids: tuple = ()
) -> Any:
    """Return a pending proposal, or allow execution through a validated review context."""
    from cacao_accounting.approval_engine import ApprovalEngine
    from cacao_accounting.runtime_mode import is_desktop_mode

    if is_desktop_mode():
        return None
    actor = _operation_actor(kind, company, actor_id)

    execution = _execution.get()
    if execution is not None:
        if (execution.document_type, execution.document_id, execution.company_id) != (kind, identifier, company):
            raise ValueError(_("La revisión no corresponde a esta operación."))
        if _digest(payload) != _digest(execution.review_payload):
            raise ValueError(_("La operación cambió después de solicitar la revisión."))
        return None
    req = database.session.execute(
        database.select(ApprovalRequest)
        .filter_by(document_type=kind, document_id=identifier, company_id=company, status="Pending Approval")
        .with_for_update()
    ).scalar_one_or_none()
    if req is None and (not ApprovalEngine.requires_different_approver(company) or not ApprovalEngine.is_enabled(company)):
        return None
    module = _OPERATION_SCOPE.get(kind, ("accounting", "close"))[0]
    policy = _preparation_policy(actor, preparer_ids, module)
    if req is not None:
        if _digest(req.review_payload) == _digest(payload):
            return req
        from cacao_accounting.internal_control_service import approval_request_transition

        with approval_request_transition(req):
            req.status = "Invalidated"
            _event(req, "rejected", actor, {"reason": "changed_proposal"})
            database.session.flush()
    req = ApprovalRequest(
        document_type=kind,
        document_id=identifier,
        company_id=company,
        requested_by=actor.id,
        current_level=1,
        required_level=1,
        status="Pending Approval",
        review_payload=payload,
        policy_snapshot=policy,
    )
    database.session.add(req)
    database.session.flush()
    _event(req, "approval_requested", actor)
    return req


def review_is_allowed(req: Any, user: Any) -> bool:
    """Use the shared independent approval policy for nonmonetary reviews."""
    from cacao_accounting.approval_policy import authorized, permits_independent_approval
    from cacao_accounting.runtime_mode import is_desktop_mode

    return bool(
        not is_desktop_mode()
        and req.document_type in REVIEW_TYPES
        and req.status == "Pending Approval"
        and permits_independent_approval(req.policy_snapshot or {}, user, req.company_id)
        and authorized(
            user,
            req.company_id,
            req.policy_snapshot["module"],
            _OPERATION_SCOPE.get(req.document_type, ("", "close"))[1],
        )
    )


@contextmanager
def reviewed_bank_difference(journal: Any, transaction_id: str, amount: Decimal, actor_id: str) -> Iterator[None]:
    """Authorize only a derived journal explicitly covered by the active approved proposal."""
    from cacao_accounting.approval_engine import approved_execution

    req = _execution.get()
    if req is None:
        yield
        return
    differences = req.review_payload.get("differences", [])
    covered = any(identifier == transaction_id and abs(Decimal(value)) == abs(amount) for identifier, value in differences)
    journal_company = getattr(journal, "company", None) or getattr(journal, "entity", None)
    if req.document_type != "bank_reconciliation" or not covered or journal_company != req.company_id:
        raise ValueError(_("La revisión no corresponde a esta operación."))
    with approved_execution(journal, actor_id):
        yield


def _execute(req: Any, user: Any) -> Any:
    """Apply the reviewed proposal through the same business services and validators."""
    payload = req.review_payload
    if req.document_type == "config_change":
        from cacao_accounting.matching_config_service import update_matching_config

        return update_matching_config(
            payload["model"], req.company_id, payload["after"], actor_id=str(user.id), expected_before=payload["before"]
        )
    if req.document_type == "monthly_close":
        from cacao_accounting.contabilidad.services import finalize_monthly_close

        return finalize_monthly_close(req.document_id, str(user.id), commit=False)
    if req.document_type == "period_reopen":
        from cacao_accounting.contabilidad.services import reopen_accounting_period

        return reopen_accounting_period(req.document_id, str(user.id), payload["reason"], commit=False)
    from cacao_accounting.bancos.reconciliation_service import (
        BankReconciliationMatch,
        BankReconciliationRequest,
        reconcile_bank_items,
    )
    from cacao_accounting.bancos.services import _post_bank_difference_adjustment
    from cacao_accounting.database import BankTransaction

    matches = [
        BankReconciliationMatch(**{**item, "allocated_amount": Decimal(item["allocated_amount"])})
        for item in payload["matches"]
    ]
    result = reconcile_bank_items(
        BankReconciliationRequest(req.company_id, date.fromisoformat(payload["date"]), matches),
        actor_id=str(user.id),
        differences=payload.get("differences", []),
    )
    for transaction_id, amount in payload.get("differences", []):
        transaction = database.session.get(BankTransaction, transaction_id, with_for_update=True)
        if transaction is None:
            raise ValueError(_("La transacción bancaria no existe."))
        _post_bank_difference_adjustment(result.id, transaction, Decimal(amount), user_id=str(user.id))
    return result


def approve_review(req: Any, user: Any, comments: str | None = None) -> Any:
    """Approve and execute once, without committing outside the caller transaction."""
    req = database.session.get(ApprovalRequest, req.id, with_for_update=True, populate_existing=True)
    if req is None or not review_is_allowed(req, user):
        raise ValueError(_("No tiene autorización para revisar esta operación."))
    token = _execution.set(req)
    try:
        from cacao_accounting.internal_control_service import audit_actor

        with audit_actor(str(user.id), str(user.name or user.user or user.id)):
            result = _execute(req, user)
    finally:
        _execution.reset(token)
    from cacao_accounting.internal_control_service import approval_request_transition

    with approval_request_transition(req):
        req.status = "Approved"
        database.session.add(
            ApprovalAction(approval_request_id=req.id, approved_by=user.id, action="approve", level=1, comments=comments)
        )
        _event(req, "approved", user, {"result_id": result.id, "prepared_by": req.requested_by})
        database.session.flush()
    return result


def reject_review(req: Any, user: Any, comments: str | None = None) -> None:
    """Reject a proposal without changing accounting or bank records."""
    req = database.session.get(ApprovalRequest, req.id, with_for_update=True, populate_existing=True)
    if req is None or not review_is_allowed(req, user):
        raise ValueError(_("No tiene autorización para revisar esta operación."))
    from cacao_accounting.internal_control_service import approval_request_transition

    with approval_request_transition(req):
        req.status = "Rejected"
        database.session.add(
            ApprovalAction(approval_request_id=req.id, approved_by=user.id, action="reject", level=1, comments=comments)
        )
        _event(req, "rejected", user)
        database.session.flush()


def review_pending_info(req: Any, user: Any) -> dict | None:
    """Represent a review in the existing pending approval inbox."""
    if not review_is_allowed(req, user):
        return None
    labels = {
        "bank_reconciliation": _("Conciliación bancaria"),
        "monthly_close": _("Cierre mensual"),
        "period_reopen": _("Reapertura de período"),
        "config_change": _("Cambio de configuración de matching"),
    }
    from flask import url_for

    endpoints = {
        "monthly_close": ("contabilidad.ver_cierre_mensual", {"identifier": req.document_id}),
        "period_reopen": ("contabilidad.accounting_period_edit", {"period_id": req.document_id}),
        "bank_reconciliation": ("bancos.bancos_conciliacion_bancaria", {"company": req.company_id}),
        "config_change": (
            ("admin.config_conciliacion_ventas", {})
            if (req.review_payload or {}).get("model") == "sales"
            else ("admin.config_conciliacion_compras", {})
        ),
    }
    document_id = (
        f"{(req.review_payload or {}).get('model', 'config')}:{req.company_id}"
        if req.document_type == "config_change"
        else req.document_id
    )
    endpoint = endpoints[req.document_type]
    requester = database.session.get(User, req.requested_by)
    return {
        "request": req,
        "document": req,
        "label": labels[req.document_type],
        "detail_url": url_for(endpoint[0], _external=False, **endpoint[1]),
        "requester_name": requester.name or requester.user if requester else req.requested_by,
        "amount": Decimal("0"),
        "doc_no": document_id,
        "review_payload": req.review_payload,
    }


def period_review_payload(period: Any, reason: str | None = None) -> dict:
    """Fingerprint the accounting evidence so preparation cannot outlive financial changes."""
    from cacao_accounting.database import GLEntry

    rows = (
        database.session.execute(
            database.select(GLEntry)
            .where(
                GLEntry.company == period.entity,
                GLEntry.posting_date >= period.start,
                GLEntry.posting_date <= period.end,
            )
            .order_by(GLEntry.id)
        )
        .scalars()
        .all()
    )
    evidence = [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]
    return {
        "period_id": period.id,
        "start": str(period.start),
        "end": str(period.end),
        "closed": period.is_closed,
        "ledger_hash": _digest(evidence),
        "reason": reason,
    }
