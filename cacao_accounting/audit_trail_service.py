"""Servicio centralizado y reusable de bitácora de auditoría (append-only)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from flask import has_request_context, request
from flask_login import current_user

from cacao_accounting.database import AuditTrail, database

ALLOWED_ACTIONS = {
    "created",
    "updated",
    "submitted",
    "approved",
    "cancelled",
    "rejected",
    "reversed",
    "reversal_draft_created",
    "imported",
    "reconciled",
    "closed",
    "commented",
    "delete_attempted",
    "task_created",
    "task_completed",
    "task_cancelled",
    "task_status_changed",
}


class AuditTrailServiceError(ValueError):
    """Error de validación para bitácora de auditoría."""


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _snapshot_model(document: Any, exclude_fields: set[str] | None = None) -> dict[str, Any]:
    exclude_fields = exclude_fields or set()
    table = getattr(document, "__table__", None)
    if table is None:
        return {}
    return {
        str(column.name): getattr(document, column.name) for column in table.columns if str(column.name) not in exclude_fields
    }


def _normalize_document(document: Any, exclude_fields: set[str] | None = None) -> dict[str, Any]:
    if is_dataclass(document):
        raw = asdict(cast(Any, document))
    elif isinstance(document, Mapping):
        raw = dict(document)
    elif hasattr(document, "__table__"):
        raw = _snapshot_model(document, exclude_fields=exclude_fields)
    else:
        raw = {}
    return raw


def _current_actor() -> tuple[str | None, str | None]:
    try:
        if current_user and current_user.is_authenticated:
            actor_id = str(current_user.id)
            actor_name = (getattr(current_user, "name", "") or "").strip() or str(
                getattr(current_user, "user", "") or actor_id
            )
            return actor_id, actor_name
    except Exception:
        return None, None
    return None, None


def _doc_info(document: Any) -> tuple[str, str, str | None, str | None]:
    doc = _normalize_document(document)
    document_id = str(doc.get("id") or "")
    if not document_id:
        raise AuditTrailServiceError("El documento debe incluir id para registrar auditoría.")
    document_type = str(
        doc.get("document_type") or doc.get("voucher_type") or doc.get("transaction") or document.__class__.__name__
    )
    document_no = doc.get("document_no") or doc.get("serie") or doc.get("name")
    company = doc.get("company") or doc.get("entity")
    return document_type, document_id, str(document_no) if document_no else None, str(company) if company else None


def _compute_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before.keys()) | set(after.keys())):
        if before.get(key) != after.get(key):
            changes[key] = {"before": before.get(key), "after": after.get(key)}
    return changes


def _log(
    action: str,
    document: Any,
    before: Any = None,
    after: Any = None,
    comment: str | None = None,
    exclude_fields: set[str] | None = None,
) -> AuditTrail:
    if action not in ALLOWED_ACTIONS:
        raise AuditTrailServiceError(f"Acción de auditoría no permitida: {action}")
    document_type, document_id, document_no, company = _doc_info(document)
    actor_user_id, actor_name = _current_actor()
    before_map = _normalize_document(before, exclude_fields=exclude_fields) if before is not None else None
    after_map = _normalize_document(after, exclude_fields=exclude_fields) if after is not None else None
    changes = _compute_changes(before_map, after_map) if before_map is not None and after_map is not None else None

    entry = AuditTrail(
        document_type=document_type,
        document_id=document_id,
        document_no=document_no,
        company=company,
        action=action,
        actor_user_id=actor_user_id,
        actor_name=actor_name,
        before_json=json.dumps(before_map, default=_json_default, ensure_ascii=False) if before_map else None,
        after_json=json.dumps(after_map, default=_json_default, ensure_ascii=False) if after_map else None,
        changes_json=json.dumps(changes, default=_json_default, ensure_ascii=False) if changes else None,
        comment=comment,
        source_module=getattr(document, "__module__", None),
        ip_address=request.remote_addr if has_request_context() else None,
        user_agent=request.user_agent.string if has_request_context() and request.user_agent else None,
    )
    database.session.add(entry)
    return entry


def log_create(document: Any) -> AuditTrail:
    """Log that a document was created."""
    return _log("created", document, after=document)


def log_update(document: Any, before: Any, after: Any) -> AuditTrail:
    """Log that a document was updated with before and after snapshots."""
    return _log("updated", document, before=before, after=after)


def log_submit(document: Any) -> AuditTrail:
    """Log that a document was submitted."""
    return _log("submitted", document, after=document)


def log_approve(document: Any) -> AuditTrail:
    """Log that a document was approved."""
    return _log("approved", document, after=document)


def log_cancel(document: Any) -> AuditTrail:
    """Log that a document was cancelled."""
    return _log("cancelled", document, after=document)


def log_reverse(document: Any) -> AuditTrail:
    """Log that a document was reversed."""
    return _log("reversed", document, after=document)


def log_reject(document: Any) -> AuditTrail:
    """Log that a document was rejected."""
    return _log("rejected", document, after=document)


def log_reversal_draft_created(document: Any) -> AuditTrail:
    """Log that a reversal draft was created from a document."""
    return _log("reversal_draft_created", document, after=document)


def log_delete_attempt(document: Any) -> AuditTrail:
    """Log an attempted document deletion."""
    return _log("delete_attempted", document, after=document)


def log_comment(document: Any, comment: str) -> AuditTrail:
    """Log a user comment on a document."""
    return _log("commented", document, after=document, comment=comment)


def log_task_event(document: Any, action: str, comment: str) -> AuditTrail:
    """Log a lightweight task event against a document."""
    return _log(action, document, after=document, comment=comment)


def get_document_timeline(document_type: str, document_id: str) -> list[AuditTrail]:
    """Devuelve historial cronológico ascendente de un documento."""
    return list(
        database.session.execute(
            database.select(AuditTrail)
            .where(AuditTrail.document_type == document_type)
            .where(AuditTrail.document_id == document_id)
            .order_by(AuditTrail.timestamp.asc(), AuditTrail.id.asc())
        )
        .scalars()
        .all()
    )


_NOISE_FIELDS: frozenset[str] = frozenset(
    {
        "updated_at",
        "modified_at",
        "last_seen",
        "last_modified",
        "last_updated",
        "modification_date",
    }
)


def _timeline_skip_fields(exclude_fields: set[str] | None = None) -> frozenset[str]:
    """Return the set of fields that should be hidden from the timeline diff."""
    return _NOISE_FIELDS | frozenset(exclude_fields or set())


def _parse_timeline_changes(changes_json: str | None) -> dict[str, dict[str, Any]]:
    """Parse a timeline diff payload, falling back to an empty mapping."""
    if not changes_json:
        return {}
    try:
        parsed = json.loads(changes_json)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _format_timeline_value(value: Any) -> str:
    """Format a timeline value for display."""
    return "-" if value in (None, "") else str(value)


def _format_timeline_changes(
    changes_map: dict[str, dict[str, Any]],
    skip_fields: frozenset[str],
) -> list[dict[str, str]]:
    """Build the rendered change rows for one audit trail event."""
    return [
        {
            "field": field,
            "before": _format_timeline_value(change.get("before")),
            "after": _format_timeline_value(change.get("after")),
        }
        for field, change in changes_map.items()
        if field not in skip_fields
    ]


def _format_timeline_event(event: AuditTrail, skip_fields: frozenset[str]) -> dict[str, Any]:
    """Format one audit trail entry for template rendering."""
    changes_map = _parse_timeline_changes(event.changes_json)
    return {"event": event, "changes": _format_timeline_changes(changes_map, skip_fields)}


def format_document_timeline(
    document_type: str,
    document_id: str,
    exclude_fields: set[str] | None = None,
) -> list[dict]:
    """Devuelve historial formateado para render homogéneo en plantillas.

    Los campos en ``_NOISE_FIELDS`` se omiten siempre del diff.
    Campos adicionales se pueden excluir vía ``exclude_fields``.
    """
    skip = _timeline_skip_fields(exclude_fields)
    return [_format_timeline_event(event, skip) for event in get_document_timeline(document_type, document_id)]
