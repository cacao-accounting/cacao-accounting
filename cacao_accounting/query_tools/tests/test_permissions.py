from __future__ import annotations

import pytest

from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import QueryToolError


def test_query_context_defaults():
    ctx = QueryContext(user_id="user123")
    assert ctx.user_id == "user123"
    assert ctx.company_ids == []
    assert ctx.permissions == set()
    assert ctx.source == "test"


def test_query_context_with_values():
    ctx = QueryContext(
        user_id="user456",
        company_ids=["EMP001", "EMP002"],
        permissions={"accounting.read", "companies.read"},
        source="mcp",
        source_client="claude",
    )
    assert ctx.user_id == "user456"
    assert "EMP001" in ctx.company_ids
    assert "accounting.read" in ctx.permissions
    assert ctx.source == "mcp"


def test_permission_validation_error():
    from cacao_accounting.query_tools.permissions import validate_permission

    ctx = QueryContext(user_id="user1", permissions=set())
    with pytest.raises(QueryToolError) as exc:
        validate_permission(ctx, required_permission="accounting.reports.read")
    assert "permisos" in exc.value.message.lower()


def test_permission_validation_passes():
    from cacao_accounting.query_tools.permissions import validate_permission

    ctx = QueryContext(
        user_id="user1",
        permissions={"accounting.reports.read"},
    )
    # Should not raise for missing company/module (no company_id provided)
    validate_permission(ctx, required_permission="accounting.reports.read")
