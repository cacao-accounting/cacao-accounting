from dataclasses import dataclass
from decimal import Decimal

from cacao_accounting.query_tools.handlers.advanced import _report_result


@dataclass
class _Row:
    values: dict


@dataclass
class _Report:
    rows: list
    totals: dict
    page: int = 1
    page_size: int = 0
    total_rows: int = 0
    columns: list | None = None
    ledger_currency: str | None = "USD"


def test_advanced_result_has_provenance_and_bounded_page():
    report = _Report(
        rows=[_Row({"account": str(index), "amount": Decimal(index)}) for index in range(5)],
        totals={"amount": Decimal("10")},
        total_rows=5,
    )
    result = _report_result(report, "EMP001", type("Filters", (), {"page": 2, "page_size": 2})())

    assert [row["account"] for row in result["items"]] == ["2", "3"]
    assert result["page"] == {"number": 2, "size": 2, "total_items": 5, "has_more": True}
    assert result["provenance"]["company_id"] == "EMP001"
    assert result["provenance"]["completeness"]["returned_items"] == 2
