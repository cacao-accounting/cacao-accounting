"""Handlers de consultas de pista de auditoría de documentos."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func

from cacao_accounting.audit_trail_service import get_document_timeline
from cacao_accounting.database import AuditTrail, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import (
    PaginatedResult,
    paginate,
)
from cacao_accounting.query_tools.permissions import validate_permission


@query_tool(
    name="audit.get_document_timeline",
    description="Obtiene la auditoría de un documento específico.",
    required_permission="audit.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "document_type": {"type": "string"},
            "document_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id", "document_type", "document_id"],
    },
)
def get_document_timeline_handler(
    *,
    context: QueryContext,
    company_id: str,
    document_type: str,
    document_id: str,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Obtiene la línea de tiempo de auditoría de un documento específico."""
    validate_permission(
        context,
        required_permission="audit.reports.read",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    entries = get_document_timeline(document_type, document_id, company_id)

    start = (_page - 1) * _page_size
    end = start + _page_size
    page_entries = entries[start:end]

    items = [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "action": e.action,
            "actor_user_id": e.actor_user_id,
            "actor_name": e.actor_name,
            "comment": e.comment,
            "ip_address": e.ip_address,
            "document_type": e.document_type,
            "document_id": e.document_id,
            "document_no": e.document_no,
        }
        for e in page_entries
    ]

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=len(entries),
        items=items,
    )
    return result.to_dict()


@query_tool(
    name="audit.get_user_activity_summary",
    description="Resume eventos de auditoría por usuario y acción, sin exponer payloads internos.",
    required_permission="audit.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "actor_user_id": {"type": "string"},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
        "required": ["company_id"],
    },
)
def get_user_activity_summary(
    *,
    context: QueryContext,
    company_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    actor_user_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "audit.reports.read", "audit", company_id)
    current_page, size = paginate(page, page_size)
    query = database.select(
        AuditTrail.actor_user_id,
        AuditTrail.actor_name,
        AuditTrail.action,
        AuditTrail.document_type,
        func.count(AuditTrail.id).label("event_count"),
    ).where(AuditTrail.company == company_id)
    if date_from:
        query = query.where(AuditTrail.timestamp >= date.fromisoformat(date_from))
    if date_to:
        query = query.where(AuditTrail.timestamp < date.fromisoformat(date_to) + timedelta(days=1))
    if actor_user_id:
        query = query.where(AuditTrail.actor_user_id == actor_user_id)
    query = query.group_by(AuditTrail.actor_user_id, AuditTrail.actor_name, AuditTrail.action, AuditTrail.document_type)
    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = database.session.execute(
        query.order_by(func.count(AuditTrail.id).desc()).offset((current_page - 1) * size).limit(size)
    ).all()
    return {
        "page": {"number": current_page, "size": size, "total_items": total, "has_more": current_page * size < total},
        "items": [
            {
                "actor_user_id": row.actor_user_id,
                "actor_name": row.actor_name,
                "action": row.action,
                "document_type": row.document_type,
                "event_count": row.event_count,
            }
            for row in rows
        ],
        "provenance": {
            "company_id": company_id,
            "filters": {"date_from": date_from, "date_to": date_to, "actor_user_id": actor_user_id},
            "completeness": {"truncated": current_page * size < total, "returned_items": len(rows), "total_items": total},
        },
    }
