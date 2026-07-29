"""Shared publication policy for read-only query tools.

Plugins are transport adapters; authorization and exposure metadata belong to
the accounting query layer so MCP, AI and future connectors cannot drift.
"""

from __future__ import annotations

from typing import Any

# Scope string constants — deduplicated for SonarCloud S1192.
_SCOPE_ADMIN_CONFIG_READ = "admin.config.read"
_SCOPE_COMPANIES_READ = "companies.read"
_SCOPE_ACCOUNTING_READ = "accounting.read"
_SCOPE_ACCOUNTING_REPORTS_READ = "accounting.reports.read"
_SCOPE_RECEIVABLES_READ = "receivables.read"
_SCOPE_RECEIVABLES_REPORTS_READ = "receivables.reports.read"
_SCOPE_PAYABLES_READ = "payables.read"
_SCOPE_PAYABLES_REPORTS_READ = "payables.reports.read"
_SCOPE_BANKING_READ = "banking.read"
_SCOPE_BANKING_REPORTS_READ = "banking.reports.read"
_SCOPE_DOCUMENTS_READ = "documents.read"
_SCOPE_DOCUMENTS_REPORTS_READ = "documents.reports.read"
_SCOPE_AUDIT_READ = "audit.read"
_SCOPE_AUDIT_REPORTS_READ = "audit.reports.read"
_SCOPE_INVENTORY_READ = "inventory.read"
_SCOPE_INVENTORY_REPORTS_READ = "inventory.reports.read"
_SCOPE_ADMIN_READ = "admin.read"

# External scopes are intentionally coarser than internal permissions. A
# service credential receives the internal report permission only after the
# external scope has been normalized here.
EXTERNAL_SCOPE_PERMISSIONS: dict[str, frozenset[str]] = {
    _SCOPE_ADMIN_READ: frozenset({_SCOPE_ADMIN_CONFIG_READ}),
    _SCOPE_COMPANIES_READ: frozenset({_SCOPE_COMPANIES_READ}),
    _SCOPE_ACCOUNTING_READ: frozenset({_SCOPE_ACCOUNTING_READ, _SCOPE_ACCOUNTING_REPORTS_READ}),
    _SCOPE_RECEIVABLES_READ: frozenset({_SCOPE_RECEIVABLES_READ, _SCOPE_RECEIVABLES_REPORTS_READ}),
    _SCOPE_PAYABLES_READ: frozenset({_SCOPE_PAYABLES_READ, _SCOPE_PAYABLES_REPORTS_READ}),
    _SCOPE_BANKING_READ: frozenset({_SCOPE_BANKING_READ, _SCOPE_BANKING_REPORTS_READ}),
    _SCOPE_DOCUMENTS_READ: frozenset({_SCOPE_DOCUMENTS_READ, _SCOPE_DOCUMENTS_REPORTS_READ}),
    _SCOPE_AUDIT_READ: frozenset({_SCOPE_AUDIT_READ, _SCOPE_AUDIT_REPORTS_READ}),
    _SCOPE_INVENTORY_READ: frozenset({_SCOPE_INVENTORY_READ, _SCOPE_INVENTORY_REPORTS_READ}),
}

TOOL_EXTERNAL_SCOPES: dict[str, str] = {
    "companies.list": _SCOPE_COMPANIES_READ,
    "accounting_periods.list": _SCOPE_ACCOUNTING_READ,
    "accounts.search": _SCOPE_ACCOUNTING_READ,
    "accounting.get_trial_balance": _SCOPE_ACCOUNTING_READ,
    "accounting.get_general_ledger": _SCOPE_ACCOUNTING_READ,
    "receivables.get_aging": _SCOPE_RECEIVABLES_READ,
    "receivables.get_open_documents": _SCOPE_RECEIVABLES_READ,
    "payables.get_aging": _SCOPE_PAYABLES_READ,
    "payables.get_open_documents": _SCOPE_PAYABLES_READ,
    "banking.get_accounts": _SCOPE_BANKING_READ,
    "banking.get_transactions": _SCOPE_BANKING_READ,
    "documents.get_flow": _SCOPE_DOCUMENTS_READ,
    "documents.get_details": _SCOPE_DOCUMENTS_READ,
    "documents.get_lines": _SCOPE_DOCUMENTS_READ,
    "documents.get_status": _SCOPE_DOCUMENTS_READ,
    "documents.get_related_documents": _SCOPE_DOCUMENTS_READ,
    "audit.get_document_timeline": _SCOPE_AUDIT_READ,
    "accounting.get_income_statement": _SCOPE_ACCOUNTING_READ,
    "accounting.get_balance_sheet": _SCOPE_ACCOUNTING_READ,
    "accounting.get_account_summary": _SCOPE_ACCOUNTING_READ,
    "accounting.get_account_movement_detail": _SCOPE_ACCOUNTING_READ,
    "accounting.get_budget_variance": _SCOPE_ACCOUNTING_READ,
    "sales.get_by_customer": _SCOPE_RECEIVABLES_READ,
    "sales.get_by_item": _SCOPE_RECEIVABLES_READ,
    "sales.get_gross_margin": _SCOPE_RECEIVABLES_READ,
    "purchases.get_by_supplier": _SCOPE_PAYABLES_READ,
    "purchases.get_by_item": _SCOPE_PAYABLES_READ,
    "inventory.get_stock_balance": _SCOPE_INVENTORY_READ,
    "inventory.get_valuation": _SCOPE_INVENTORY_READ,
    "inventory.get_kardex": _SCOPE_INVENTORY_READ,
    "inventory.get_existence": _SCOPE_INVENTORY_READ,
    "inventory.get_batches": _SCOPE_INVENTORY_READ,
    "inventory.get_serials": _SCOPE_INVENTORY_READ,
    "inventory.get_negative_stock": _SCOPE_INVENTORY_READ,
    "inventory.get_reorder_alerts": _SCOPE_INVENTORY_READ,
    "inventory.get_transfers": _SCOPE_INVENTORY_READ,
    "inventory.get_slow_moving_items": _SCOPE_INVENTORY_READ,
    "inventory.get_turnover": _SCOPE_INVENTORY_READ,
    "banking.get_balance_summary": _SCOPE_BANKING_READ,
    "banking.get_reconciliation_status": _SCOPE_BANKING_READ,
    "banking.get_unreconciled_transactions": _SCOPE_BANKING_READ,
    "receivables.get_subledger": _SCOPE_RECEIVABLES_READ,
    "payables.get_subledger": _SCOPE_PAYABLES_READ,
    "payments.search": _SCOPE_BANKING_READ,
    "payments.get_unapplied": _SCOPE_BANKING_READ,
    "payments.get_applications": _SCOPE_BANKING_READ,
    "documents.search_relations": _SCOPE_DOCUMENTS_READ,
    "audit.search_events": _SCOPE_AUDIT_READ,
    "audit.get_user_activity_summary": _SCOPE_AUDIT_READ,
    "accounting.get_revaluations": _SCOPE_ACCOUNTING_READ,
    "analytics.get_kpi_snapshot": _SCOPE_ACCOUNTING_READ,
    "analytics.compare_periods": _SCOPE_ACCOUNTING_READ,
    "analytics.get_trend": _SCOPE_ACCOUNTING_READ,
    "analytics.get_concentration": _SCOPE_ACCOUNTING_READ,
    "ledgers.list": _SCOPE_ACCOUNTING_READ,
    "parties.search": _SCOPE_DOCUMENTS_READ,
    "items.search": _SCOPE_INVENTORY_READ,
    "warehouses.list": _SCOPE_INVENTORY_READ,
    "bank_accounts.search": _SCOPE_BANKING_READ,
    "currencies.list": _SCOPE_ACCOUNTING_READ,
    "dimensions.list": _SCOPE_ACCOUNTING_READ,
    "dimension_values.search": _SCOPE_ACCOUNTING_READ,
    "cost_centers.list": _SCOPE_ACCOUNTING_READ,
    "uoms.list": _SCOPE_INVENTORY_READ,
    "treasury.forecasts.list": _SCOPE_BANKING_READ,
    "treasury.get_cash_forecast": _SCOPE_BANKING_READ,
    "treasury.compare_forecasts": _SCOPE_BANKING_READ,
    "treasury.get_maturity_schedule": _SCOPE_BANKING_READ,
    "admin.configuration.list": _SCOPE_ADMIN_READ,
}


def permissions_for_scopes(scopes: set[str] | list[str]) -> set[str]:
    """Expand external read scopes into the internal query permissions."""
    permissions: set[str] = set()
    for scope in scopes:
        permissions.update(EXTERNAL_SCOPE_PERMISSIONS.get(scope, ()))
    return permissions


def published_tool_scope(tool_name: str) -> str | None:
    """Return the external scope assigned to a published tool."""
    return TOOL_EXTERNAL_SCOPES.get(tool_name)


def is_published_read_tool(tool: Any, name: str | None = None) -> bool:
    """Defence in depth: only immutable read-only tools can be published."""
    tool_name = name or getattr(tool, "name", None)
    return bool(tool.read_only is not False and tool_name in TOOL_EXTERNAL_SCOPES)
