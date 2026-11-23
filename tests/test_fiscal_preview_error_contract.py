# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Functional regression tests for invalid fiscal preview responses (#1943)."""

from __future__ import annotations

from importlib import import_module

api_module = import_module("cacao_accounting.api")


def test_endpoint_reports_engine_errors_as_unprocessable(authenticated_client, monkeypatch):
    """A partial calculation with engine errors is never returned as a successful preview."""
    engine_result = {
        "errors": ["Circular dependency detected in tax rules."],
        "tax_lines": [],
        "summary": {"subtotal": "100", "grand_total": "100"},
    }
    monkeypatch.setattr(api_module, "fiscal_preview", lambda _payload: engine_result)

    response = authenticated_client().post(
        "/api/fiscal/preview",
        json={"document_type": "sales_invoice", "company": "cacao", "subtotal": "100"},
    )

    assert response.status_code == 422
    assert response.get_json() == engine_result
