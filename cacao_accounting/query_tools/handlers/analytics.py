# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Read-only composite analytics with a closed metric/dimension vocabulary."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.handlers.advanced import _json_value
from cacao_accounting.query_tools.handlers.dates import parse_iso_date
from cacao_accounting.query_tools.permissions import validate_permission

from cacao_accounting.reportes.analytics import (
    ALLOWED_DIMENSIONS,
    ALLOWED_METRICS,
    compare_periods,
    get_concentration,
    get_kpi_snapshot,
    get_trend,
)
from cacao_accounting.i18n import _, _l

_PERM_ACCOUNTING_REPORTS_READ = "accounting.reports.read"


def _date(value: str) -> date:
    return cast(date, parse_iso_date(value, required=True))


def _date_range(context: QueryContext, date_from: str, date_to: str) -> tuple[date, date]:
    """Parsea y valida que el rango no esté invertido."""
    start = _date(date_from)
    end = _date(date_to)
    if start > end:
        raise QueryToolError(
            code=ErrorCode.INVALID_PARAMETER,
            message=_("La fecha inicial no puede ser posterior a la fecha final."),
            request_id=getattr(context, "request_id", None),
        )
    return start, end


def _json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return _json_value(value)


def _validate(context: QueryContext, company_id: str) -> None:
    validate_permission(context, _PERM_ACCOUNTING_REPORTS_READ, "accounting", company_id)


def _envelope(payload: dict[str, Any], company_id: str, **filters: Any) -> dict[str, Any]:
    payload["provenance"] = {
        "company_id": company_id,
        "filters": {key: value for key, value in filters.items() if value is not None},
        "complete": bool(payload.get("complete", True)),
    }
    return payload


_PERIOD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
    },
    "required": ["company_id", "date_from", "date_to"],
}


@query_tool(
    "analytics.get_kpi_snapshot",
    _l("Obtiene un snapshot ejecutivo determinista de liquidez, cartera, inventario y resultado."),
    required_module="accounting",
    required_permission=_PERM_ACCOUNTING_REPORTS_READ,
    parameters_schema=_PERIOD_SCHEMA,
)
def get_kpi_snapshot_tool(*, context: QueryContext, company_id: str, date_from: str, date_to: str) -> dict[str, Any]:
    _validate(context, company_id)
    start, end = _date_range(context, date_from, date_to)
    return _envelope(
        _json(get_kpi_snapshot(company_id, start, end)),
        company_id,
        date_from=date_from,
        date_to=date_to,
    )


@query_tool(
    "analytics.compare_periods",
    _l("Compara una métrica permitida entre dos períodos sin descargar movimientos."),
    required_module="accounting",
    required_permission=_PERM_ACCOUNTING_REPORTS_READ,
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "metric": {"type": "string", "enum": sorted(ALLOWED_METRICS)},
            "base_date_from": {"type": "string", "format": "date"},
            "base_date_to": {"type": "string", "format": "date"},
            "compare_date_from": {"type": "string", "format": "date"},
            "compare_date_to": {"type": "string", "format": "date"},
        },
        "required": ["company_id", "metric", "base_date_from", "base_date_to", "compare_date_from", "compare_date_to"],
    },
)
def compare_periods_tool(
    *,
    context: QueryContext,
    company_id: str,
    metric: str,
    base_date_from: str,
    base_date_to: str,
    compare_date_from: str,
    compare_date_to: str,
) -> dict[str, Any]:
    _validate(context, company_id)
    base_start, base_end = _date_range(context, base_date_from, base_date_to)
    compare_start, compare_end = _date_range(context, compare_date_from, compare_date_to)
    return _envelope(
        _json(
            compare_periods(
                company_id,
                metric,
                base_start,
                base_end,
                compare_start,
                compare_end,
            )
        ),
        company_id,
        metric=metric,
        base_date_from=base_date_from,
        base_date_to=base_date_to,
        compare_date_from=compare_date_from,
        compare_date_to=compare_date_to,
    )


@query_tool(
    "analytics.get_trend",
    _l("Obtiene una tendencia mensual de una métrica permitida."),
    required_module="accounting",
    required_permission=_PERM_ACCOUNTING_REPORTS_READ,
    parameters_schema={
        **_PERIOD_SCHEMA,
        "properties": {**_PERIOD_SCHEMA["properties"], "metric": {"type": "string", "enum": sorted(ALLOWED_METRICS)}},
        "required": ["company_id", "metric", "date_from", "date_to"],
    },
)
def get_trend_tool(*, context: QueryContext, company_id: str, metric: str, date_from: str, date_to: str) -> dict[str, Any]:
    _validate(context, company_id)
    start, end = _date_range(context, date_from, date_to)
    return _envelope(
        {"items": _json(get_trend(company_id, metric, start, end)), "complete": True},
        company_id,
        metric=metric,
        date_from=date_from,
        date_to=date_to,
    )


@query_tool(
    "analytics.get_concentration",
    _l("Obtiene concentración por cliente, proveedor o artículo con un límite explícito."),
    required_module="accounting",
    required_permission=_PERM_ACCOUNTING_REPORTS_READ,
    parameters_schema={
        **_PERIOD_SCHEMA,
        "properties": {
            **_PERIOD_SCHEMA["properties"],
            "dimension": {"type": "string", "enum": sorted(ALLOWED_DIMENSIONS)},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
        },
        "required": ["company_id", "dimension", "date_from", "date_to"],
    },
)
def get_concentration_tool(
    *, context: QueryContext, company_id: str, dimension: str, date_from: str, date_to: str, limit: int = 10
) -> dict[str, Any]:
    _validate(context, company_id)
    start, end = _date_range(context, date_from, date_to)
    return _envelope(
        {"items": _json(get_concentration(company_id, dimension, start, end, limit)), "complete": True},
        company_id,
        dimension=dimension,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
