from __future__ import annotations

from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError


def test_error_code_values():
    assert ErrorCode.PERMISSION_DENIED.value == "permission_denied"
    assert ErrorCode.COMPANY_ACCESS_DENIED.value == "company_access_denied"
    assert ErrorCode.TOOL_NOT_FOUND.value == "tool_not_found"
    assert ErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_query_tool_error_to_dict():
    error = QueryToolError(
        code=ErrorCode.PERMISSION_DENIED,
        message="No tiene permisos.",
        request_id="req-123",
    )
    d = error.to_dict()
    assert d["error"]["code"] == "permission_denied"
    assert d["error"]["message"] == "No tiene permisos."
    assert d["error"]["request_id"] == "req-123"


def test_query_tool_error_without_request_id():
    error = QueryToolError(
        code=ErrorCode.INTERNAL_ERROR,
        message="Error interno.",
    )
    d = error.to_dict()
    assert "request_id" not in d["error"]
