"""Read-only analytical query tools backed by the reporting services."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Callable

from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.permissions import validate_permission
from cacao_accounting.reportes.services import (
    FinancialReportFilters,
    OperationalReportFilters,
    get_account_summary_report,
    get_balance_sheet_report,
    get_gross_margin,
    get_income_statement_report,
    get_inventory_valuation,
    get_purchases_by_item,
    get_purchases_by_supplier,
    get_sales_by_customer,
    get_sales_by_item,
    get_stock_balance,
)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


def _report_result(report: Any) -> dict[str, Any]:
    return {
        "items": [{key: _json_value(value) for key, value in row.values.items()} for row in report.rows],
        "summary": {key: _json_value(value) for key, value in report.totals.items()},
        "page": {
            "number": report.page or 1,
            "size": report.page_size or len(report.rows),
            "total_items": report.total_rows or len(report.rows),
            "has_more": bool(report.total_rows and report.page_size and report.page * report.page_size < report.total_rows),
        },
        "currency": report.ledger_currency,
        "columns": report.columns or [],
    }


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _financial(
    context: QueryContext, company_id: str, ledger_id: str | None, accounting_period: str | None
) -> FinancialReportFilters:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    return FinancialReportFilters(company=company_id, ledger=ledger_id, accounting_period=accounting_period)


def _operational(
    context: QueryContext,
    company_id: str,
    permission: str,
    module: str,
    date_from: str | None,
    date_to: str | None,
    **kwargs: Any,
) -> OperationalReportFilters:
    validate_permission(context, permission, module, company_id)
    return OperationalReportFilters(company=company_id, date_from=_date(date_from), date_to=_date(date_to), **kwargs)


_FINANCIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "ledger_id": {"type": "string"},
        "accounting_period": {"type": "string"},
    },
    "required": ["company_id"],
}


@query_tool(
    "accounting.get_income_statement",
    "Obtiene el estado de resultados acumulado.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_FINANCIAL_SCHEMA,
)
def get_income_statement(
    *, context: QueryContext, company_id: str, ledger_id: str | None = None, accounting_period: str | None = None
) -> dict[str, Any]:
    return _report_result(get_income_statement_report(_financial(context, company_id, ledger_id, accounting_period)))


@query_tool(
    "accounting.get_balance_sheet",
    "Obtiene el balance general por clasificación.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_FINANCIAL_SCHEMA,
)
def get_balance_sheet(
    *, context: QueryContext, company_id: str, ledger_id: str | None = None, accounting_period: str | None = None
) -> dict[str, Any]:
    return _report_result(get_balance_sheet_report(_financial(context, company_id, ledger_id, accounting_period)))


@query_tool(
    "accounting.get_account_summary",
    "Obtiene el resumen de movimientos por cuenta.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_FINANCIAL_SCHEMA,
)
def get_account_summary(
    *, context: QueryContext, company_id: str, ledger_id: str | None = None, accounting_period: str | None = None
) -> dict[str, Any]:
    return _report_result(get_account_summary_report(_financial(context, company_id, ledger_id, accounting_period)))


def _operational_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "party_id": {"type": "string"},
            "item_code": {"type": "string"},
            "warehouse": {"type": "string"},
        },
        "required": ["company_id"],
    }


def _register_operational(name: str, description: str, permission: str, module: str, service: Callable[..., Any]) -> None:
    @query_tool(
        name, description, required_module=module, required_permission=permission, parameters_schema=_operational_schema()
    )
    def handler(
        *,
        context: QueryContext,
        company_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        party_id: str | None = None,
        item_code: str | None = None,
        warehouse: str | None = None,
    ) -> dict[str, Any]:
        filters = _operational(
            context,
            company_id,
            permission,
            module,
            date_from,
            date_to,
            party_id=party_id,
            item_code=item_code,
            warehouse=warehouse,
        )
        return _report_result(service(filters))


_register_operational(
    "sales.get_by_customer", "Agrega ventas por cliente.", "receivables.reports.read", "sales", get_sales_by_customer
)
_register_operational(
    "sales.get_by_item", "Agrega ventas por artículo.", "receivables.reports.read", "sales", get_sales_by_item
)
_register_operational(
    "sales.get_gross_margin", "Calcula margen bruto de ventas.", "receivables.reports.read", "sales", get_gross_margin
)
_register_operational(
    "purchases.get_by_supplier",
    "Agrega compras por proveedor.",
    "payables.reports.read",
    "purchases",
    get_purchases_by_supplier,
)
_register_operational(
    "purchases.get_by_item", "Agrega compras por artículo.", "payables.reports.read", "purchases", get_purchases_by_item
)
_register_operational(
    "inventory.get_stock_balance",
    "Obtiene existencias actuales por artículo y almacén.",
    "inventory.reports.read",
    "inventory",
    get_stock_balance,
)
_register_operational(
    "inventory.get_valuation",
    "Obtiene valoración de inventario.",
    "inventory.reports.read",
    "inventory",
    get_inventory_valuation,
)
