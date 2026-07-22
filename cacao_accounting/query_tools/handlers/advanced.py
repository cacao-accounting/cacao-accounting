"""Read-only analytical query tools backed by the reporting services."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Callable

from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.permissions import validate_permission
from cacao_accounting.reportes.services import (
    BankingFilters,
    FinancialReportFilters,
    KardexFilters,
    OperationalReportFilters,
    SubledgerFilters,
    get_account_summary_report,
    get_account_movement_detail,
    get_budget_variance,
    get_balance_sheet_report,
    get_gross_margin,
    get_income_statement_report,
    get_inventory_valuation,
    get_negative_stock,
    get_reorder_alerts,
    get_slow_moving_items,
    get_inventory_turnover,
    get_kardex,
    get_inventory_existence as get_inventory_existence_report,
    get_bank_balance_summary,
    get_unreconciled_bank_transactions,
    get_reconciliation_report,
    get_ar_ap_subledger,
    get_batch_report,
    get_serial_report,
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


def _filter_payload(filters: Any) -> dict[str, Any]:
    values = getattr(filters, "__dict__", {})
    return {key: _json_value(value) for key, value in values.items() if value is not None}


def _report_result(report: Any, company_id: str | None = None, filters: Any = None) -> dict[str, Any]:
    page_number = getattr(filters, "page", None) or report.page or 1
    requested_size = getattr(filters, "page_size", None)
    page_size = requested_size or report.page_size or len(report.rows)
    total_items = report.total_rows or len(report.rows)
    rows = report.rows
    if requested_size:
        start = (page_number - 1) * page_size
        rows = report.rows[start : start + page_size]
    has_more = page_number * page_size < total_items
    return {
        "items": [{key: _json_value(value) for key, value in row.values.items()} for row in rows],
        "summary": {key: _json_value(value) for key, value in report.totals.items()},
        "page": {
            "number": page_number,
            "size": page_size,
            "total_items": total_items,
            "has_more": has_more,
        },
        "currency": report.ledger_currency,
        "columns": report.columns or [],
        "provenance": {
            "company_id": company_id,
            "filters": _filter_payload(filters) if filters is not None else {},
            "currency": report.ledger_currency,
            "completeness": {"truncated": has_more, "returned_items": len(rows), "total_items": total_items},
        },
    }


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _aging_result(report: Any) -> dict[str, Any]:
    return {
        "items": [{key: _json_value(value) for key, value in row.values.items()} for row in report.rows],
        "summary": {key: _json_value(value) for key, value in report.totals.items()},
        "page": {"number": 1, "size": len(report.rows), "total_items": len(report.rows), "has_more": False},
    }


def _financial(
    context: QueryContext,
    company_id: str,
    ledger_id: str | None,
    accounting_period: str | None,
    page: int = 1,
    page_size: int = 100,
) -> FinancialReportFilters:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    return FinancialReportFilters(
        company=company_id,
        ledger=ledger_id,
        accounting_period=accounting_period,
        page=page,
        page_size=page_size,
    )


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
        "page": {"type": "integer", "minimum": 1, "default": 1},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
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
    *,
    context: QueryContext,
    company_id: str,
    ledger_id: str | None = None,
    accounting_period: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    filters = _financial(context, company_id, ledger_id, accounting_period, page, page_size)
    return _report_result(get_income_statement_report(filters), company_id, filters)


@query_tool(
    "accounting.get_balance_sheet",
    "Obtiene el balance general por clasificación.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_FINANCIAL_SCHEMA,
)
def get_balance_sheet(
    *,
    context: QueryContext,
    company_id: str,
    ledger_id: str | None = None,
    accounting_period: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    filters = _financial(context, company_id, ledger_id, accounting_period, page, page_size)
    return _report_result(get_balance_sheet_report(filters), company_id, filters)


@query_tool(
    "accounting.get_account_summary",
    "Obtiene el resumen de movimientos por cuenta.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_FINANCIAL_SCHEMA,
)
def get_account_summary(
    *,
    context: QueryContext,
    company_id: str,
    ledger_id: str | None = None,
    accounting_period: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    filters = _financial(context, company_id, ledger_id, accounting_period, page, page_size)
    return _report_result(get_account_summary_report(filters), company_id, filters)


@query_tool(
    "accounting.get_account_movement_detail",
    "Obtiene el detalle de asientos de una cuenta con saldo acumulado opcional.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        **_FINANCIAL_SCHEMA,
        "properties": {
            **_FINANCIAL_SCHEMA["properties"],
            "account_code": {"type": "string"},
            "voucher_type": {"type": "string"},
            "party_type": {"type": "string", "enum": ["customer", "supplier"]},
            "party_id": {"type": "string"},
            "include_running_balance": {"type": "boolean", "default": False},
        },
    },
)
def get_account_movement_detail_handler(
    *,
    context: QueryContext,
    company_id: str,
    ledger_id: str | None = None,
    accounting_period: str | None = None,
    account_code: str | None = None,
    voucher_type: str | None = None,
    party_type: str | None = None,
    party_id: str | None = None,
    include_running_balance: bool = False,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    filters = FinancialReportFilters(
        company=company_id,
        ledger=ledger_id,
        accounting_period=accounting_period,
        account_code=account_code,
        voucher_type=voucher_type,
        party_type=party_type,
        party_id=party_id,
        include_running_balance=include_running_balance,
        page=page,
        page_size=page_size,
    )
    return _report_result(get_account_movement_detail(filters), company_id, filters)


@query_tool(
    "accounting.get_budget_variance",
    "Compara presupuesto aprobado contra ejecución real por cuenta y período.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        **_FINANCIAL_SCHEMA,
        "properties": {**_FINANCIAL_SCHEMA["properties"], "budget_code": {"type": "string"}},
        "required": ["company_id", "accounting_period"],
    },
)
def get_budget_variance_handler(
    *,
    context: QueryContext,
    company_id: str,
    ledger_id: str | None = None,
    accounting_period: str,
    budget_code: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    filters = FinancialReportFilters(
        company=company_id,
        ledger=ledger_id,
        accounting_period=accounting_period,
        budget_code=budget_code,
        page=page,
        page_size=page_size,
    )
    return _report_result(get_budget_variance(filters), company_id, filters)


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
            "bank_account_id": {"type": "string"},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
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
        page: int = 1,
        page_size: int = 100,
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
            page=page,
            page_size=page_size,
        )
        return _report_result(service(filters), company_id, filters)


_register_operational(
    "sales.get_by_customer", "Agrega ventas por cliente.", "receivables.reports.read", "sales", get_sales_by_customer
)


_INVENTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "item_code": {"type": "string"},
        "warehouse": {"type": "string"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
        "page": {"type": "integer", "minimum": 1, "default": 1},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
    },
    "required": ["company_id"],
}


def _inventory_query(
    context: QueryContext,
    company_id: str,
    service: Callable[..., Any],
    item_code: str | None = None,
    warehouse: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "inventory.reports.read", "inventory", company_id)
    filters = KardexFilters(
        company=company_id,
        item_code=item_code,
        warehouse=warehouse,
        date_from=_date(date_from),
        date_to=_date(date_to),
        page=page,
        page_size=page_size,
    )
    return _report_result(service(filters), company_id, filters)


@query_tool(
    "inventory.get_kardex",
    "Consulta movimientos de inventario por artículo y almacén.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_INVENTORY_SCHEMA,
)
def get_inventory_kardex(
    *,
    context: QueryContext,
    company_id: str,
    item_code: str | None = None,
    warehouse: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    return _inventory_query(context, company_id, get_kardex, item_code, warehouse, date_from, date_to, page, page_size)


@query_tool(
    "inventory.get_existence",
    "Obtiene existencia histórica o actual de inventario.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_INVENTORY_SCHEMA,
)
def get_inventory_existence(
    *,
    context: QueryContext,
    company_id: str,
    item_code: str | None = None,
    warehouse: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    return _inventory_query(
        context, company_id, get_inventory_existence_report, item_code, warehouse, date_from, date_to, page, page_size
    )


def _inventory_operational(
    context: QueryContext,
    company_id: str,
    service: Callable[..., Any],
    item_code: str | None,
    warehouse: str | None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "inventory.reports.read", "inventory", company_id)
    filters = OperationalReportFilters(
        company=company_id, item_code=item_code, warehouse=warehouse, page=page, page_size=page_size
    )
    return _report_result(service(filters), company_id, filters)


@query_tool(
    "inventory.get_batches",
    "Lista lotes de inventario.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_INVENTORY_SCHEMA,
)
def get_inventory_batches(
    *,
    context: QueryContext,
    company_id: str,
    item_code: str | None = None,
    warehouse: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    return _inventory_operational(context, company_id, get_batch_report, item_code, warehouse, page, page_size)


@query_tool(
    "inventory.get_serials",
    "Lista números de serie de inventario.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_INVENTORY_SCHEMA,
)
def get_inventory_serials(
    *,
    context: QueryContext,
    company_id: str,
    item_code: str | None = None,
    warehouse: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    return _inventory_operational(context, company_id, get_serial_report, item_code, warehouse, page, page_size)


@query_tool(
    "inventory.get_negative_stock",
    "Detecta existencias negativas por artículo y almacén.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_operational_schema(),
)
def get_inventory_negative_stock(
    *,
    context: QueryContext,
    company_id: str,
    item_code: str | None = None,
    warehouse: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    filters = _operational(
        context,
        company_id,
        "inventory.reports.read",
        "inventory",
        None,
        None,
        item_code=item_code,
        warehouse=warehouse,
        page=page,
        page_size=page_size,
    )
    return _report_result(get_negative_stock(filters), company_id, filters)


@query_tool(
    "inventory.get_reorder_alerts",
    "Detecta artículos por debajo del mínimo o punto de reorden configurado.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_operational_schema(),
)
def get_inventory_reorder_alerts(
    *,
    context: QueryContext,
    company_id: str,
    item_code: str | None = None,
    warehouse: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    filters = _operational(
        context,
        company_id,
        "inventory.reports.read",
        "inventory",
        None,
        None,
        item_code=item_code,
        warehouse=warehouse,
        page=page,
        page_size=page_size,
    )
    return _report_result(get_reorder_alerts(filters), company_id, filters)


@query_tool(
    "inventory.get_slow_moving_items",
    "Lista inventario con existencias y sin salidas durante un umbral.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema={
        **_operational_schema(),
        "properties": {
            **_operational_schema()["properties"],
            "inactivity_days": {"type": "integer", "minimum": 1, "maximum": 3650},
        },
    },
)
def get_inventory_slow_moving_items(
    *,
    context: QueryContext,
    company_id: str,
    date_to: str | None = None,
    item_code: str | None = None,
    warehouse: str | None = None,
    inactivity_days: int = 90,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    filters = _operational(
        context,
        company_id,
        "inventory.reports.read",
        "inventory",
        None,
        date_to,
        item_code=item_code,
        warehouse=warehouse,
        page=page,
        page_size=page_size,
    )
    return _report_result(get_slow_moving_items(filters, inactivity_days), company_id, filters)


@query_tool(
    "inventory.get_turnover",
    "Calcula rotación de inventario por artículo y almacén.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema={
        **_operational_schema(),
        "required": ["company_id", "date_from", "date_to"],
    },
)
def get_inventory_turnover_report(
    *,
    context: QueryContext,
    company_id: str,
    date_from: str,
    date_to: str,
    item_code: str | None = None,
    warehouse: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    filters = _operational(
        context,
        company_id,
        "inventory.reports.read",
        "inventory",
        date_from,
        date_to,
        item_code=item_code,
        warehouse=warehouse,
        page=page,
        page_size=page_size,
    )
    return _report_result(get_inventory_turnover(filters), company_id, filters)


@query_tool(
    "banking.get_balance_summary",
    "Obtiene saldos bancarios consolidados.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema=_operational_schema(),
)
def get_banking_balance_summary(
    *,
    context: QueryContext,
    company_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    bank_account_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    filters = BankingFilters(
        company=company_id,
        bank_account_id=bank_account_id,
        date_from=_date(date_from),
        date_to=_date(date_to),
        page=page,
        page_size=page_size,
    )
    report = get_bank_balance_summary(filters)
    return _report_result(report, company_id, filters)


@query_tool(
    "banking.get_reconciliation_status",
    "Obtiene el estado de conciliaciones bancarias y pendientes de compras.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "as_of_date": {"type": "string", "format": "date"},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
        "required": ["company_id"],
    },
)
def get_banking_reconciliation_status(
    *,
    context: QueryContext,
    company_id: str,
    as_of_date: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    report = get_reconciliation_report(company_id, _date(as_of_date))
    filters = SimpleNamespace(as_of_date=as_of_date, page=page, page_size=page_size)
    return _report_result(report, company_id, filters)


@query_tool(
    "banking.get_unreconciled_transactions",
    "Lista movimientos de extracto pendientes de conciliación.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema=_operational_schema(),
)
def get_banking_unreconciled_transactions(
    *,
    context: QueryContext,
    company_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    bank_account_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    filters = BankingFilters(
        company=company_id,
        bank_account_id=bank_account_id,
        date_from=_date(date_from),
        date_to=_date(date_to),
        page=page,
        page_size=page_size,
    )
    return _report_result(get_unreconciled_bank_transactions(filters), company_id, filters)


_SUBLEDGER_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "party_type": {"type": "string", "enum": ["customer", "supplier"]},
        "party_id": {"type": "string"},
        "as_of_date": {"type": "string", "format": "date"},
        "page": {"type": "integer", "minimum": 1, "default": 1},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
    },
    "required": ["company_id", "party_type"],
}


def _subledger(
    context: QueryContext,
    company_id: str,
    party_type: str,
    party_id: str | None,
    as_of_date: str | None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    permission = "receivables.reports.read" if party_type == "customer" else "payables.reports.read"
    module = "sales" if party_type == "customer" else "purchases"
    validate_permission(context, permission, module, company_id)
    filters = SubledgerFilters(
        company=company_id,
        party_type=party_type,
        party_id=party_id,
        as_of_date=_date(as_of_date),
        page=page,
        page_size=page_size,
    )
    return _report_result(get_ar_ap_subledger(filters), company_id, filters)


@query_tool(
    "receivables.get_subledger",
    "Obtiene el subledger detallado de clientes.",
    required_module="sales",
    required_permission="receivables.reports.read",
    parameters_schema=_SUBLEDGER_SCHEMA,
)
def get_receivables_subledger(
    *,
    context: QueryContext,
    company_id: str,
    party_type: str = "customer",
    party_id: str | None = None,
    as_of_date: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    return _subledger(context, company_id, "customer", party_id, as_of_date, page, page_size)


@query_tool(
    "payables.get_subledger",
    "Obtiene el subledger detallado de proveedores.",
    required_module="purchases",
    required_permission="payables.reports.read",
    parameters_schema=_SUBLEDGER_SCHEMA,
)
def get_payables_subledger(
    *,
    context: QueryContext,
    company_id: str,
    party_type: str = "supplier",
    party_id: str | None = None,
    as_of_date: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    return _subledger(context, company_id, "supplier", party_id, as_of_date, page, page_size)


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
