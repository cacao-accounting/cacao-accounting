# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Reusable helpers for simple list filters."""

from __future__ import annotations

from typing import Any

from flask import request
from sqlalchemy import Select, or_
from sqlalchemy.orm.attributes import InstrumentedAttribute

DOCSTATUS_FILTERS: dict[str, int] = {
    "draft": 0,
    "submitted": 1,
    "cancelled": 2,
}


def apply_list_filters(
    query: Select[Any],
    model: type[Any],
    search_fields: tuple[InstrumentedAttribute[Any], ...],
    *,
    include_status: bool = True,
) -> Select[Any]:
    """Apply common search and document status filters to a query."""
    search = (request.args.get("search") or "").strip()
    if search and search_fields:
        pattern = f"%{search}%"
        query = query.filter(or_(*(field.ilike(pattern) for field in search_fields)))

    status = (request.args.get("status") or "").strip()
    if include_status and status in DOCSTATUS_FILTERS:
        if hasattr(model, "docstatus"):
            query = query.filter(model.docstatus == DOCSTATUS_FILTERS[status])
        elif hasattr(model, "status"):
            query = query.filter(model.status == status)

    return query
