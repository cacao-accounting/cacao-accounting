from __future__ import annotations

import pytest

from cacao_accounting.query_tools.decorators import QueryTool, query_tool
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.registry import Registry, registry


def test_registry_singleton():
    assert isinstance(registry, Registry)


def test_register_tool():
    r = Registry()
    tool = QueryTool(
        name="test.tool",
        description="A test tool",
        read_only=True,
    )
    r.register(tool)
    assert r.get("test.tool") == tool


def test_register_duplicate_name():
    r = Registry()
    tool1 = QueryTool(name="test.dup", description="First", read_only=True)
    tool2 = QueryTool(name="test.dup", description="Second", read_only=True)
    r.register(tool1)
    with pytest.raises(ValueError, match="already registered"):
        r.register(tool2)


def test_get_nonexistent_tool():
    with pytest.raises(QueryToolError) as exc:
        registry.get("nonexistent.tool")
    assert exc.value.code == ErrorCode.TOOL_NOT_FOUND


def test_list_tools_returns_dict():
    r = Registry()
    tool = QueryTool(name="test.list_me", description="List me", read_only=True)
    r.register(tool)
    tools = r.list_tools()
    assert isinstance(tools, dict)
    assert "test.list_me" in tools


def test_get_tools_for_permissions_filters():
    r = Registry()
    t1 = QueryTool(
        name="test.p1",
        description="Needs p1",
        required_permission="p1",
        read_only=True,
    )
    t2 = QueryTool(
        name="test.p2",
        description="Needs p2",
        required_permission="p2",
        read_only=True,
    )
    t3 = QueryTool(
        name="test.no_perm",
        description="No perm needed",
        read_only=True,
    )
    r.register(t1)
    r.register(t2)
    r.register(t3)

    result = r.get_tools_for_permissions({"p1"})
    names = [t["name"] for t in result]
    assert "test.p1" in names
    assert "test.p2" not in names
    assert "test.no_perm" in names


def test_get_count():
    r = Registry()
    assert r.get_count() == 0
    r.register(QueryTool(name="test.c1", description="C1", read_only=True))
    assert r.get_count() == 1
    r.register(QueryTool(name="test.c2", description="C2", read_only=True))
    assert r.get_count() == 2
