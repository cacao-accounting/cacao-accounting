# SPDX-License-Identifier: Apache-2.0

"""Regression tests for cash forecast redirect validation."""

from cacao_accounting.bancos.cash_forecast import _safe_next_url


def test_safe_next_url_rejects_external_redirect_normalization_bypasses():
    """Reject encoded or backslash-based paths normalized externally by browsers."""
    assert _safe_next_url("/\\evil.com") is None
    assert _safe_next_url("/%2F%2Fevil.com") is None
    assert _safe_next_url("https://evil.com/account") is None


def test_safe_next_url_accepts_internal_path():
    """Keep valid internal paths available for returning to the forecast page."""
    assert _safe_next_url("/cash_management/cash-forecast/123?tab=entries") == (
        "/cash_management/cash-forecast/123?tab=entries"
    )
