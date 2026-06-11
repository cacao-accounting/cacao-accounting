from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from cacao_accounting.database import AuditTrail, database
from cacao_accounting.logs import log
from cacao_accounting.query_tools.context import QueryContext

ALLOWED_QUERY_ACTIONS = frozenset({
    "query_tool.executed",
    "query_tool.denied",
    "query_tool.failed",
    "query_tool.rate_limited",
})


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def serialize_parameters(params: dict[str, Any]) -> dict[str, Any]:
    sanitized = {}
    for key, value in params.items():
        if key.lower() in {"api_key", "api_key", "password", "secret", "token", "access_token"}:
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = serialize_parameters(value)
        else:
            sanitized[key] = _serialize_value(value)
    return sanitized


def log_query_tool_event(
    *,
    action: str,
    context: QueryContext,
    tool_name: str,
    parameters: dict[str, Any] | None = None,
    status: str = "success",
    duration_ms: float | None = None,
    result_count: int | None = None,
    error_code: str | None = None,
) -> None:
    if action not in ALLOWED_QUERY_ACTIONS:
        raise ValueError(f"Acción de auditoría no permitida: {action}")

    entry = AuditTrail(
        document_type="query_tool",
        document_id=tool_name,
        document_no=None,
        company=parameters.get("company_id") if parameters else None,
        action=action,
        actor_user_id=context.user_id,
        actor_name=context.user_id,
        before_json=None,
        after_json=json.dumps(
            serialize_parameters(parameters or {}),
            default=str,
            ensure_ascii=False,
        ),
        changes_json=None,
        comment=json.dumps(
            {
                "source": context.source,
                "source_client": context.source_client,
                "status": status,
                "duration_ms": duration_ms,
                "result_count": result_count,
                "error_code": error_code,
            },
            default=str,
            ensure_ascii=False,
        ),
        source_module=f"query_tools.{tool_name}",
        ip_address=context.ip_address,
        user_agent=context.user_agent,
    )
    database.session.add(entry)
