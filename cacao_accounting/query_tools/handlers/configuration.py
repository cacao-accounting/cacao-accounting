"""Read-only, redacted configuration discovery for administrators."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from cacao_accounting.database import CacaoConfig, User, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import PaginatedResult, paginate
from cacao_accounting.query_tools.permissions import validate_permission

_ALLOWED_PREFIXES = ("cacao_ai_", "cacao_mcp_", "cacao_reporting_", "budget_control_")
_SENSITIVE_MARKERS = ("key", "token", "secret", "password", "credential")


def _is_admin(context: QueryContext) -> bool:
    if context.is_service_principal:
        return True
    user = database.session.execute(database.select(User).where(User.id == context.user_id)).scalars().first()
    return bool(user and str(user.classification or "").lower() in {"admin", "administrator"})


@query_tool(
    "admin.configuration.list",
    "Lista configuración permitida con valores sensibles siempre redactados.",
    required_permission="admin.config.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "query": {"type": "string", "maxLength": 100},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 200, "default": 100},
        },
        "required": ["company_id"],
    },
)
def list_admin_configuration(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "admin.config.read", None, company_id)
    if not _is_admin(context):
        return {
            "items": [],
            "page": {"number": 1, "size": page_size, "total_items": 0, "has_more": False},
            "provenance": {"company_id": company_id},
        }
    current, size = paginate(page, page_size)
    statement = database.select(CacaoConfig).where(or_(*[CacaoConfig.key.startswith(prefix) for prefix in _ALLOWED_PREFIXES]))
    if query:
        statement = statement.where(CacaoConfig.key.ilike(f"%{query}%"))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(CacaoConfig.key).offset((current - 1) * size).limit(size)).scalars()
    items = []
    for row in rows:
        sensitive = any(marker in row.key.lower() for marker in _SENSITIVE_MARKERS)
        items.append({"key": row.key, "value": "[REDACTED]" if sensitive else row.value, "sensitive": sensitive})
    return {
        **PaginatedResult(page=current, page_size=size, total_items=total, items=items).to_dict(),
        "provenance": {"company_id": company_id, "filters": {"query": query}, "redacted": True},
    }
