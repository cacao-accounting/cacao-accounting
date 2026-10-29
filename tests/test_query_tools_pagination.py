# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from __future__ import annotations

import pytest

from cacao_accounting.query_tools.pagination import (
    MAX_PAGE_SIZE,
    PaginatedResult,
    paginate,
)
from cacao_accounting.query_tools.errors import QueryToolError


def test_paginate_defaults():
    page, page_size = paginate()
    assert page == 1
    assert page_size == 100


def test_paginate_custom():
    page, page_size = paginate(page=2, page_size=50)
    assert page == 2
    assert page_size == 50


def test_paginate_clamps_negative():
    page, page_size = paginate(page=0, page_size=0)
    assert page == 1
    assert page_size == 100


def test_paginate_rejects_excessive_page_size():
    with pytest.raises(QueryToolError) as exc:
        paginate(page_size=MAX_PAGE_SIZE + 1)
    assert "500" in exc.value.message


def test_paginated_result_properties():
    result = PaginatedResult(page=1, page_size=10, total_items=25, items=list(range(10)))
    assert result.total_pages == 3
    assert result.has_next_page is True

    result2 = PaginatedResult(page=3, page_size=10, total_items=25, items=list(range(5)))
    assert result2.total_pages == 3
    assert result2.has_next_page is False


def test_paginated_result_to_dict():
    result = PaginatedResult(page=1, page_size=10, total_items=25, items=[1, 2, 3])
    d = result.to_dict()
    assert d["page"] == 1
    assert d["page_size"] == 10
    assert d["total_items"] == 25
    assert d["total_pages"] == 3
    assert d["has_next_page"] is True
    assert d["items"] == [1, 2, 3]


def test_paginated_result_zero_items():
    result = PaginatedResult(page=1, page_size=100, total_items=0, items=[])
    assert result.total_pages == 1
    assert result.has_next_page is False


def test_paginated_result_single_page():
    result = PaginatedResult(page=1, page_size=100, total_items=50, items=list(range(50)))
    assert result.total_pages == 1
    assert result.has_next_page is False


def test_with_provenance_uses_paginated_contract() -> None:
    """La provenance se calcula desde los metadatos de PaginatedResult."""
    from cacao_accounting.query_tools.handlers.operational import _with_provenance
    from cacao_accounting.query_tools.pagination import PaginatedResult

    empty = _with_provenance(PaginatedResult(page=1, page_size=2, total_items=0, items=[]).to_dict(), "c1")
    assert empty["provenance"]["completeness"] == {
        "page": 1,
        "page_size": 2,
        "truncated": False,
        "returned_items": 0,
        "total_items": 0,
    }
    first = _with_provenance(PaginatedResult(page=1, page_size=2, total_items=3, items=[1, 2]).to_dict(), "c1", x=None)
    assert first["provenance"]["completeness"]["truncated"] is True
    assert first["provenance"]["completeness"]["total_items"] == 3
    assert first["provenance"]["filters"] == {}
    last = _with_provenance(PaginatedResult(page=2, page_size=2, total_items=3, items=[3]).to_dict(), "c1")
    assert last["provenance"]["completeness"]["truncated"] is False
    assert last["provenance"]["completeness"]["returned_items"] == 1


def test_discovery_result_uses_paginated_contract() -> None:
    """La procedencia de discovery refleja si hay una página siguiente."""
    from cacao_accounting.query_tools.handlers.discovery import _result

    first = _result(1, 2, [{"id": "a"}, {"id": "b"}], 3, "c1")
    last = _result(2, 2, [{"id": "c"}], 3, "c1")

    assert first["provenance"]["completeness"]["truncated"] is True
    assert last["provenance"]["completeness"]["truncated"] is False
