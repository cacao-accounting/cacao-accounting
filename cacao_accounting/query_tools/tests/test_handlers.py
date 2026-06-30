# SPDX-License-Identifier: Apache-2.0

"""Integration tests for query tool handlers."""

from __future__ import annotations

import pytest

from cacao_accounting.query_tools import PaginatedResult


@pytest.mark.slow
class TestPaginatedResultIntegration:
    def test_paginated_result_with_items(self):
        items = [{"id": "1", "name": "Test"}]
        result = PaginatedResult(
            page=1,
            page_size=10,
            total_items=1,
            items=items,
        )
        assert result.total_items == 1
        assert len(result.items) == 1
        assert result.has_next_page is False
        assert result.total_pages == 1

    def test_paginated_result_multi_page(self):
        items = [{"id": str(i)} for i in range(10)]
        result = PaginatedResult(
            page=1,
            page_size=10,
            total_items=15,
            items=items,
        )
        assert result.total_pages == 2
        assert result.has_next_page is True

    def test_paginated_result_to_dict_format(self):
        result = PaginatedResult(
            page=2,
            page_size=5,
            total_items=12,
            items=[{"num": i} for i in range(5)],
        )
        d = result.to_dict()
        assert d["page"] == 2
        assert d["page_size"] == 5
        assert d["total_items"] == 12
        assert d["total_pages"] == 3
        assert d["has_next_page"] is True
        assert len(d["items"]) == 5

    def test_paginated_result_empty_items(self):
        result = PaginatedResult(page=1, page_size=10, total_items=0, items=[])
        assert result.total_pages == 1
        assert result.has_next_page is False

    def test_paginated_result_last_page(self):
        items = [{"id": str(i)} for i in range(3)]
        result = PaginatedResult(
            page=2,
            page_size=10,
            total_items=12,
            items=items,
        )
        assert result.total_pages == 2
        assert result.has_next_page is False

    def test_paginated_result_single_page(self):
        items = [{"id": str(i)} for i in range(5)]
        result = PaginatedResult(
            page=1,
            page_size=10,
            total_items=5,
            items=items,
        )
        assert result.total_pages == 1
        assert result.has_next_page is False
