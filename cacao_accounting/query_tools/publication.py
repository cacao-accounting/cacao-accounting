"""Shared publication policy for read-only query tools.

Plugins are transport adapters; authorization and exposure metadata belong to
the accounting query layer so MCP, AI and future connectors cannot drift.
"""

from __future__ import annotations

from typing import Any

# External scopes are intentionally coarser than internal permissions. A
# service credential receives the internal report permission only after the
# external scope has been normalized here.
EXTERNAL_SCOPE_PERMISSIONS: dict[str, frozenset[str]] = {
    "companies.read": frozenset({"companies.read"}),
    "accounting.read": frozenset({"accounting.read", "accounting.reports.read"}),
    "receivables.read": frozenset({"receivables.read", "receivables.reports.read"}),
    "payables.read": frozenset({"payables.read", "payables.reports.read"}),
    "banking.read": frozenset({"banking.read", "banking.reports.read"}),
    "documents.read": frozenset({"documents.read", "documents.reports.read"}),
    "audit.read": frozenset({"audit.read", "audit.reports.read"}),
    "inventory.read": frozenset({"inventory.read", "inventory.reports.read"}),
}

TOOL_EXTERNAL_SCOPES: dict[str, str] = {
    "companies.list": "companies.read",
    "accounting_periods.list": "accounting.read",
    "accounts.search": "accounting.read",
    "accounting.get_trial_balance": "accounting.read",
    "accounting.get_general_ledger": "accounting.read",
    "receivables.get_aging": "receivables.read",
    "receivables.get_open_documents": "receivables.read",
    "payables.get_aging": "payables.read",
    "payables.get_open_documents": "payables.read",
    "banking.get_accounts": "banking.read",
    "banking.get_transactions": "banking.read",
    "documents.get_flow": "documents.read",
    "audit.get_document_timeline": "audit.read",
    "accounting.get_income_statement": "accounting.read",
    "accounting.get_balance_sheet": "accounting.read",
    "accounting.get_account_summary": "accounting.read",
    "sales.get_by_customer": "receivables.read",
    "sales.get_by_item": "receivables.read",
    "sales.get_gross_margin": "receivables.read",
    "purchases.get_by_supplier": "payables.read",
    "purchases.get_by_item": "payables.read",
    "inventory.get_stock_balance": "inventory.read",
    "inventory.get_valuation": "inventory.read",
    "inventory.get_kardex": "inventory.read",
    "inventory.get_existence": "inventory.read",
    "inventory.get_batches": "inventory.read",
    "inventory.get_serials": "inventory.read",
    "inventory.get_negative_stock": "inventory.read",
    "inventory.get_slow_moving_items": "inventory.read",
    "inventory.get_turnover": "inventory.read",
    "banking.get_balance_summary": "banking.read",
    "banking.get_reconciliation_status": "banking.read",
    "banking.get_unreconciled_transactions": "banking.read",
    "receivables.get_subledger": "receivables.read",
    "payables.get_subledger": "payables.read",
    "payments.search": "banking.read",
    "payments.get_unapplied": "banking.read",
    "payments.get_applications": "banking.read",
    "documents.search_relations": "documents.read",
    "audit.search_events": "audit.read",
    "audit.get_user_activity_summary": "audit.read",
    "accounting.get_revaluations": "accounting.read",
    "analytics.get_kpi_snapshot": "accounting.read",
    "analytics.compare_periods": "accounting.read",
    "analytics.get_trend": "accounting.read",
    "analytics.get_concentration": "accounting.read",
    "ledgers.list": "accounting.read",
    "parties.search": "documents.read",
    "items.search": "inventory.read",
    "warehouses.list": "inventory.read",
    "bank_accounts.search": "banking.read",
    "currencies.list": "accounting.read",
    "treasury.forecasts.list": "banking.read",
    "treasury.get_cash_forecast": "banking.read",
    "treasury.compare_forecasts": "banking.read",
}


def permissions_for_scopes(scopes: set[str] | list[str]) -> set[str]:
    """Expand external read scopes into the internal query permissions."""
    permissions: set[str] = set()
    for scope in scopes:
        permissions.update(EXTERNAL_SCOPE_PERMISSIONS.get(scope, ()))
    return permissions


def published_tool_scope(tool_name: str) -> str | None:
    return TOOL_EXTERNAL_SCOPES.get(tool_name)


def is_published_read_tool(tool: Any, name: str | None = None) -> bool:
    """Defence in depth: only immutable read-only tools can be published."""
    tool_name = name or getattr(tool, "name", None)
    return bool(tool.read_only is not False and tool_name in TOOL_EXTERNAL_SCOPES)
