from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.reportes import analytics
from cacao_accounting.query_tools import TOOL_EXTERNAL_SCOPES, load_query_tools, registry


def test_metric_vocabulary_is_closed(monkeypatch):
    with pytest.raises(ValueError, match="Métrica no permitida"):
        analytics.metric_value("EMP001", "sql", date(2026, 1, 1), date(2026, 1, 31))
    monkeypatch.setattr(analytics, "metric_value", lambda *args: Decimal("10"))
    result = analytics.compare_periods(
        "EMP001", "sales", date(2026, 1, 1), date(2026, 1, 31), date(2025, 1, 1), date(2025, 1, 31)
    )
    assert result["variance"] == Decimal("0")


def test_trend_uses_monthly_buckets(monkeypatch):
    monkeypatch.setattr(analytics, "metric_value", lambda *args: Decimal("1"))
    rows = analytics.get_trend("EMP001", "sales", date(2026, 1, 15), date(2026, 3, 2))
    assert [row["period"] for row in rows] == ["2026-01", "2026-02", "2026-03"]
    assert rows[0]["date_from"] == date(2026, 1, 15)
    assert rows[-1]["date_to"] == date(2026, 3, 2)


def test_discovery_and_composite_tools_are_published():
    load_query_tools()
    expected = {
        "ledgers.list",
        "parties.search",
        "items.search",
        "warehouses.list",
        "bank_accounts.search",
        "currencies.list",
        "analytics.get_kpi_snapshot",
        "analytics.compare_periods",
        "analytics.get_trend",
        "analytics.get_concentration",
        "treasury.forecasts.list",
        "treasury.get_cash_forecast",
        "treasury.compare_forecasts",
        "banking.get_reconciliation_status",
        "banking.get_unreconciled_transactions",
        "inventory.get_negative_stock",
        "inventory.get_slow_moving_items",
        "inventory.get_turnover",
        "audit.get_user_activity_summary",
        "documents.get_details",
        "documents.get_lines",
        "documents.get_status",
        "documents.get_related_documents",
        "accounting.get_account_movement_detail",
        "accounting.get_budget_variance",
    }
    assert expected.issubset(TOOL_EXTERNAL_SCOPES)
    assert expected.issubset(registry.list_tools())
