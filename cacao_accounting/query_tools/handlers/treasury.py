"""Read-only access to the upstream cash forecast service."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from cacao_accounting.bancos.cash_forecast_service import get_cash_forecast_matrix, get_forecast_comparison
from cacao_accounting.database import CashForecast, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import PaginatedResult, paginate
from cacao_accounting.query_tools.permissions import validate_permission


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    return value


def _verify_forecast(context: QueryContext, company_id: str, forecast_id: str) -> CashForecast:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    forecast = database.session.get(CashForecast, forecast_id)
    if forecast is None or forecast.company != company_id:
        raise ValueError("Pronóstico no encontrado para la compañía autorizada")
    return forecast


_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "page": {"type": "integer", "minimum": 1, "default": 1},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
    },
    "required": ["company_id"],
}


@query_tool(
    "treasury.forecasts.list",
    "Lista versiones de pronósticos de caja de una compañía.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema=_LIST_SCHEMA,
)
def list_cash_forecasts(
    *, context: QueryContext, company_id: str, page: int = 1, page_size: int = 50
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    current, size = paginate(page, page_size)
    query = database.select(CashForecast).where(CashForecast.company == company_id)
    total = database.session.execute(database.select(database.func.count()).select_from(query.subquery())).scalar() or 0
    rows = database.session.execute(
        query.order_by(CashForecast.created.desc()).offset((current - 1) * size).limit(size)
    ).scalars()
    items = [
        {
            "id": row.id,
            "version": row.version,
            "description": row.description,
            "fiscal_year_id": row.fiscal_year_id,
            "periodicity": row.periodicity,
            "approved": bool(row.approved_at),
        }
        for row in rows
    ]
    result = PaginatedResult(page=current, page_size=size, total_items=total, items=items).to_dict()
    result["provenance"] = {"company_id": company_id, "completeness": {"truncated": result["page"]["has_more"]}}
    return result


_FORECAST_SCHEMA = {
    "type": "object",
    "properties": {"company_id": {"type": "string"}, "forecast_id": {"type": "string"}},
    "required": ["company_id", "forecast_id"],
}


@query_tool(
    "treasury.get_cash_forecast",
    "Obtiene el pronóstico de caja por períodos, sin modificarlo.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema=_FORECAST_SCHEMA,
)
def get_cash_forecast(
    *, context: QueryContext, company_id: str, forecast_id: str
) -> dict[str, Any]:
    _verify_forecast(context, company_id, forecast_id)
    items = _json(get_cash_forecast_matrix(company_id, forecast_id))
    return {
        "items": items,
        "summary": {"periods": len(items)},
        "provenance": {"company_id": company_id, "filters": {"forecast_id": forecast_id}, "complete": True},
    }


@query_tool(
    "treasury.compare_forecasts",
    "Compara dos versiones de pronóstico de caja de una misma compañía.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "base_forecast_id": {"type": "string"},
            "compare_forecast_id": {"type": "string"},
        },
        "required": ["company_id", "base_forecast_id", "compare_forecast_id"],
    },
)
def compare_cash_forecasts(
    *, context: QueryContext, company_id: str, base_forecast_id: str, compare_forecast_id: str
) -> dict[str, Any]:
    _verify_forecast(context, company_id, base_forecast_id)
    _verify_forecast(context, company_id, compare_forecast_id)
    items = _json(get_forecast_comparison(company_id, base_forecast_id, compare_forecast_id))
    return {
        "items": items,
        "summary": {"periods": len(items)},
        "provenance": {
            "company_id": company_id,
            "filters": {"base_forecast_id": base_forecast_id, "compare_forecast_id": compare_forecast_id},
            "complete": True,
        },
    }
