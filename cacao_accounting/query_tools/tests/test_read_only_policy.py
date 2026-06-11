from __future__ import annotations

import pytest

from cacao_accounting.query_tools.decorators import QueryTool, query_tool


def test_tool_default_is_read_only():
    tool = QueryTool(
        name="test.default_read_only",
        description="Should default to read_only=True",
    )
    assert tool.read_only is True


def test_tool_must_be_read_only():
    from cacao_accounting.query_tools.registry import Registry

    r = Registry()
    tool = QueryTool(
        name="test.not_read_only",
        description="Should fail",
        read_only=False,
    )
    with pytest.raises(ValueError, match="read_only"):
        r.register(tool)


def test_query_tool_decorator_sets_read_only():
    @query_tool(
        name="test.decorator_read_only",
        description="Decorated tool",
    )
    def my_handler(*, context, **kwargs):
        return {"data": "test"}

    assert my_handler.read_only is True


def test_registry_rejects_non_read_only():
    from cacao_accounting.query_tools.registry import Registry

    r = Registry()
    tool = QueryTool(
        name="test.write_tool_via_registry",
        description="Should be rejected by registry",
        read_only=False,
    )
    with pytest.raises(ValueError, match="read_only"):
        r.register(tool)
