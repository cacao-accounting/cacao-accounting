from __future__ import annotations

import pytest

from cacao_accounting.query_tools.decorators import QueryTool
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
    with pytest.raises(ValueError, match="ya está registrada"):
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


def test_query_tool_lazy_description_localization():
    from flask_babel import force_locale
    from cacao_accounting import create_app
    from cacao_accounting.i18n import _l
    from cacao_accounting.query_tools import load_query_tools

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_key",
            "MODO_ESCRITORIO": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        load_query_tools()
        r = Registry()
        tool = QueryTool(
            name="test.accounting_periods",
            description=_l("Lista los períodos contables de una compañía."),
            read_only=True,
        )
        r.register(tool)

        # Confirm description is stored lazily and not as a plain static str
        assert type(tool.description).__name__ == "LazyString"

        # Materialization in default locale (Spanish)
        schema_es = r._tool_to_schema(tool)
        assert schema_es["description"] == "Lista los períodos contables de una compañía."

        # Materialization in English locale
        with force_locale("en"):
            schema_en = r._tool_to_schema(tool)
            assert schema_en["description"] == "Lists accounting periods for a company."


def test_all_registered_tools_have_lazy_descriptions():
    from cacao_accounting import create_app
    from cacao_accounting.query_tools import load_query_tools

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_key",
            "MODO_ESCRITORIO": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        load_query_tools()
        tools = registry.list_tools()
        assert len(tools) > 0
        for name, tool in tools.items():
            assert type(tool.description).__name__ == "LazyString", f"Tool '{name}' description is not LazyString"
