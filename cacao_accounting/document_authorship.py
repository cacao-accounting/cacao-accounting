# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Resolve document authorship from persisted documents and approval evidence."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from sqlalchemy import or_, select

from cacao_accounting.database import ApprovalAction, ApprovalRequest, AuditTrail, User, database
from cacao_accounting.document_flow.registry import DOCUMENT_TYPES, normalize_doctype
from cacao_accounting.reportes.services import PaginatedReport, ReportRow
from cacao_accounting.runtime_mode import is_cloud_mode

AUTHOR_COLUMNS = ("created_by", "created_at", "approved_by", "approved_at", "modified_by", "modified_at")


def _empty_authorship() -> dict[str, Any]:
    """Return missing evidence explicitly, without inventing an actor."""
    return dict.fromkeys(AUTHOR_COLUMNS)


def _document_values(document: Any) -> dict[str, Any]:
    """Read persisted creator and last editor, excluding derived actor guesses."""
    return {
        **_empty_authorship(),
        "created_by": getattr(document, "created_by", None),
        "created_at": getattr(document, "created", None),
        "modified_by": getattr(document, "modified_by", None),
        "modified_at": getattr(document, "modified", None) if getattr(document, "modified_by", None) else None,
    }


def _load_documents(company: str, keys: set[tuple[str, str]]) -> tuple[dict, dict]:
    """Batch load each document type, scoped before resolving display numbers."""
    grouped: dict[str, set[str]] = defaultdict(set)
    for kind, identifier in keys:
        grouped[kind].add(identifier)
    documents: dict[tuple[str, str], dict[str, Any]] = {}
    aliases: dict[tuple[str, str], tuple[str, str]] = {}
    for kind, identifiers in grouped.items():
        spec = DOCUMENT_TYPES.get(kind)
        if spec is None:
            continue
        model = spec.header_model
        company_column = getattr(model, "company", None)
        if company_column is None:
            company_column = getattr(model, "entity", None)
        if company_column is None:
            continue
        condition = model.id.in_(identifiers)
        if hasattr(model, "document_no"):
            condition = or_(condition, model.document_no.in_(identifiers))
        for document in database.session.scalars(select(model).where(company_column == company, condition)):
            key = (kind, str(document.id))
            documents[key] = _document_values(document)
            aliases[key] = key
            number = getattr(document, "document_no", None)
            if number:
                aliases[(kind, str(number))] = key
    return documents, aliases


def _apply_events(company: str, documents: dict) -> None:
    """Fill creator/editor from actual events and approval from explicit evidence."""
    ids = {key[1] for key in documents}
    if not ids:
        return
    events = database.session.scalars(
        select(AuditTrail)
        .where(AuditTrail.company == company, AuditTrail.document_id.in_(ids))
        .order_by(AuditTrail.timestamp, AuditTrail.id)
    )
    fields = {
        "created": ("created_by", "created_at"),
        "updated": ("modified_by", "modified_at"),
        "approved": ("approved_by", "approved_at"),
    }
    for event in events:
        key = (normalize_doctype(event.document_type), str(event.document_id))
        if key not in documents or event.action not in fields:
            continue
        actor_field, time_field = fields[event.action]
        if event.action == "created" and documents[key][actor_field]:
            continue
        documents[key][actor_field] = event.actor_name or event.actor_user_id
        documents[key][time_field] = event.timestamp
    approvals = database.session.execute(
        select(ApprovalRequest, ApprovalAction)
        .join(ApprovalAction, ApprovalAction.approval_request_id == ApprovalRequest.id)
        .where(
            ApprovalRequest.company_id == company,
            ApprovalRequest.document_id.in_(ids),
            ApprovalRequest.status == "Approved",
            ApprovalAction.action == "approve",
        )
        .order_by(ApprovalAction.created_at, ApprovalAction.id)
    )
    for request, action in approvals:
        key = (normalize_doctype(request.document_type), str(request.document_id))
        if key in documents:
            documents[key]["approved_by"] = action.approved_by
            documents[key]["approved_at"] = action.created_at


def _review_documents(company: str, keys: set[tuple[str, str]], documents: dict, aliases: dict) -> None:
    """Resolve proposal creators when a review precedes the actual business record."""
    kinds = {"bank_reconciliation", "monthly_close", "period_reopen"}
    ids = {identifier for kind, identifier in keys if kind in kinds}
    if not ids:
        return
    requests = database.session.scalars(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.company_id == company,
            ApprovalRequest.document_type.in_(kinds),
            ApprovalRequest.document_id.in_(ids),
        )
        .order_by(ApprovalRequest.created_at, ApprovalRequest.id)
    )
    for request in requests:
        key = (request.document_type, str(request.document_id))
        if key in documents:
            continue
        documents[key] = {**_empty_authorship(), "created_by": request.requested_by, "created_at": request.created_at}
        aliases[key] = key


def batch_authorship(company: str, keys: set[tuple[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Resolve a company-scoped batch without a query for every ledger line."""
    if not is_cloud_mode() or not keys:
        return {}
    normalized = {(normalize_doctype(kind), identifier) for kind, identifier in keys}
    documents, aliases = _load_documents(company, normalized)
    _review_documents(company, normalized, documents, aliases)
    _apply_events(company, documents)
    actors = {values[field] for values in documents.values() for field in AUTHOR_COLUMNS[::2] if values[field]}
    names = {
        str(user.id): user.name or user.user for user in database.session.scalars(select(User).where(User.id.in_(actors)))
    }
    for values in documents.values():
        for field in AUTHOR_COLUMNS[::2]:
            values[field] = names.get(values[field], values[field])
    return {key: documents[target] for key, target in aliases.items()}


def document_authorship(document_type: str, document: Any) -> dict[str, Any]:
    """Resolve authorship for an already authorized document detail view."""
    company = getattr(document, "company", None) or getattr(document, "entity", None)
    key = (normalize_doctype(document_type), str(document.id))
    return batch_authorship(str(company), {key}).get(key, _empty_authorship())


def _row_key(values: dict[str, Any]) -> tuple[str, str] | None:
    """Identify individual transaction rows, leaving aggregate reports alone."""
    kind = values.get("voucher_type") or values.get("document_type")
    identifier = values.get("voucher_id") or values.get("document_id") or values.get("document_no")
    if not kind or not identifier:
        return None
    return normalize_doctype(str(kind)), str(identifier)


def report_authorship(report: PaginatedReport, company: str, show_users: bool) -> PaginatedReport:
    """Toggle user columns for transaction reports and their exports."""
    if not is_cloud_mode():
        return report
    keys = {key for row in report.rows if (key := _row_key(row.values))}
    if not keys:
        return report
    evidence = batch_authorship(company, keys) if show_users else {}
    columns = [column for column in report.columns or [] if column not in AUTHOR_COLUMNS]
    if show_users:
        columns.extend(AUTHOR_COLUMNS)
    rows = []
    for row in report.rows:
        values = {name: value for name, value in row.values.items() if name not in AUTHOR_COLUMNS}
        if show_users:
            row_key = _row_key(row.values)
            values.update(evidence.get(row_key, _empty_authorship()) if row_key else _empty_authorship())
        rows.append(ReportRow(values=values))
    return replace(report, rows=rows, columns=columns)
