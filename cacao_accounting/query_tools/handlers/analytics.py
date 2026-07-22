"""Read-only composite analytics with a closed metric/dimension vocabulary."""

from __future__ import annotations

from datetime import date
from typing import Any

from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.handlers.advanced import _json_value
from cacao_accounting.query_tools.permissions import validate_permission
from cacao_accounting.reportes.analytics import (
    ALLOWED_DIMENSIONS,
    ALLOWED_METRICS,
    compare_periods,
    get_concentration,
    get_kpi_snapshot,
    get_trend,
)


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    return _json_value(value)


def _validate(context: QueryContext, company_id: str) -> None:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)


_PERIOD_SCHEMA = {
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
    "Obtiene un snapshot ejecutivo determinista de liquidez, cartera, inventario y resultado.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_PERIOD_SCHEMA,
)
def get_kpi_snapshot_tool(*, context: QueryContext, company_id: str, date_from: str, date_to: str) -> dict[str, Any]:
    _validate(context, company_id)
    return _json(get_kpi_snapshot(company_id, _date(date_from), _date(date_to)))


@query_tool(
    "analytics.compare_periods",
    "Compara una métrica permitida entre dos períodos sin descargar movimientos.",
    required_module="accounting",
    required_permission="accounting.reports.read",
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
    return _json(
        compare_periods(
            company_id,
            metric,
            _date(base_date_from),
            _date(base_date_to),
            _date(compare_date_from),
            _date(compare_date_to),
        )
    )


@query_tool(
    "analytics.get_trend",
    "Obtiene una tendencia mensual de una métrica permitida.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        **_PERIOD_SCHEMA,
        "properties": {**_PERIOD_SCHEMA["properties"], "metric": {"type": "string", "enum": sorted(ALLOWED_METRICS)}},
        "required": ["company_id", "metric", "date_from", "date_to"],
    },
)
def get_trend_tool(*, context: QueryContext, company_id: str, metric: str, date_from: str, date_to: str) -> dict[str, Any]:
    _validate(context, company_id)
    return {"items": _json(get_trend(company_id, metric, _date(date_from), _date(date_to))), "complete": True}


@query_tool(
    "analytics.get_concentration",
    "Obtiene concentración por cliente, proveedor o artículo con un límite explícito.",
    required_module="accounting",
    required_permission="accounting.reports.read",
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
    return {
        "items": _json(get_concentration(company_id, dimension, _date(date_from), _date(date_to), limit)),
        "complete": True,
    }
