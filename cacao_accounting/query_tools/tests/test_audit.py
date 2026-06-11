from __future__ import annotations

from cacao_accounting.query_tools.audit import (
    ALLOWED_QUERY_ACTIONS,
    serialize_parameters,
)


def test_serialize_parameters_sanitizes_keys():
    params = {
        "company_id": "EMP001",
        "api_key": "sk-secret123",
        "password": "mypassword",
        "token": "abc123",
        "date_from": "2026-01-01",
    }
    sanitized = serialize_parameters(params)
    assert sanitized["company_id"] == "EMP001"
    assert sanitized["api_key"] == "***"
    assert sanitized["password"] == "***"
    assert sanitized["token"] == "***"
    assert sanitized["date_from"] == "2026-01-01"


def test_serialize_parameters_nested():
    params = {
        "company_id": "EMP001",
        "nested": {
            "api_key": "secret",
            "value": 42,
        },
    }
    sanitized = serialize_parameters(params)
    assert sanitized["nested"]["api_key"] == "***"
    assert sanitized["nested"]["value"] == 42


def test_valid_actions():
    assert "query_tool.executed" in ALLOWED_QUERY_ACTIONS
    assert "query_tool.denied" in ALLOWED_QUERY_ACTIONS
    assert "query_tool.failed" in ALLOWED_QUERY_ACTIONS
    assert "query_tool.rate_limited" in ALLOWED_QUERY_ACTIONS


def test_serialize_parameters_empty():
    assert serialize_parameters({}) == {}
