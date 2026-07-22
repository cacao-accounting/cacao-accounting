"""Handlers de consultas de compañías."""

from __future__ import annotations

from typing import Any

from cacao_accounting.database import Entity, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import (
    PaginatedResult,
    paginate,
)


@query_tool(
    name="companies.list",
    description="Lista las compañías accesibles para el usuario.",
    parameters_schema={
        "type": "object",
        "properties": {
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
    },
    needs_company=False,
)
def list_companies(
    *,
    context: QueryContext,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Lista las compañías accesibles para el usuario."""
    _page, _page_size = paginate(page, page_size)

    query = database.select(Entity)

    if context.allow_all_companies:
        query = query.where(Entity.enabled.is_(True))
    else:
        query = query.where(Entity.code.in_(context.company_ids))

    total = database.session.execute(database.select(database.func.count()).select_from(query.subquery())).scalar() or 0

    rows = (
        database.session.execute(query.order_by(Entity.company_name).offset((_page - 1) * _page_size).limit(_page_size))
        .scalars()
        .all()
    )

    items = [
        {
            "code": e.code,
            "company_name": e.company_name,
            "name": e.name,
            "tax_id": e.tax_id,
            "currency": e.currency,
            "country": e.country,
            "entity_type": e.entity_type,
            "enabled": e.enabled,
        }
        for e in rows
    ]

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()
