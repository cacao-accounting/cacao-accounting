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
