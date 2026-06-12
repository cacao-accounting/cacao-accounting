from __future__ import annotations

from typing import Any

from cacao_accounting.audit_trail_service import get_document_timeline
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
    validate_permission(
        context,
        required_permission="audit.reports.read",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    entries = get_document_timeline(document_type, document_id)

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
