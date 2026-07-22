from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.reportes import analytics


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
