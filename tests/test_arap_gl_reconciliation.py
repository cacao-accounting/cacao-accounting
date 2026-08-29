"""Unit tests for continuous AR/AP-to-GL reconciliation."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.contabilidad.arap_gl_reconciliation import (
    ARAPGLReconciliationError,
    ARAPGLReconciliationKey,
    compare_arap_gl_totals,
    enforce_arap_gl_policy,
    resolve_arap_gl_policy,
)


def _key(*, ledger: str = "BOOK-NIO", party: str = "PARTY-1", currency: str = "NIO", kind: str = "AR"):
    """Build one stable matrix key."""
    return ARAPGLReconciliationKey("cacao", ledger, kind, "customer" if kind == "AR" else "supplier", party, currency)


def test_balanced_matrix_returns_structured_positive_result():
    """Equal subledger and GL totals reconcile without policy effects."""
    key = _key()
    result = compare_arap_gl_totals(
        company="cacao",
        as_of_date=date(2026, 8, 29),
        subledger_totals={key: Decimal("125.00")},
        gl_totals={key: Decimal("125.00")},
        mode="strict",
        tolerance=Decimal("0.01"),
    )

    assert result.is_balanced is True
    assert result.blocked is False
    assert result.differences == ()
    assert result.lines[0].difference == Decimal("0.00")


def test_strict_drift_raises_with_structured_result():
    """Strict mode exposes the complete drift and blocks the transaction."""
    key = _key()
    result = compare_arap_gl_totals(
        company="cacao",
        as_of_date=date(2026, 8, 29),
        subledger_totals={key: Decimal("100")},
        gl_totals={key: Decimal("99.98")},
        mode="strict",
        tolerance=Decimal("0.01"),
    )

    with pytest.raises(ARAPGLReconciliationError) as error:
        enforce_arap_gl_policy(result)

    assert error.value.result is result
    assert result.blocked is True
    assert result.differences[0].difference == Decimal("0.02")


def test_tolerance_includes_boundary_difference():
    """A difference equal to tolerance is balanced."""
    key = _key()
    result = compare_arap_gl_totals(
        company="cacao",
        as_of_date=date(2026, 8, 29),
        subledger_totals={key: Decimal("100.00")},
        gl_totals={key: Decimal("99.99")},
        tolerance=Decimal("0.01"),
    )

    assert result.is_balanced is True


def test_matrix_retains_company_book_party_currency_and_zero_sided_rows():
    """The union matrix reports independent drift for every required dimension."""
    nio_ar = _key()
    usd_ap = _key(ledger="BOOK-USD", party="SUP-2", currency="USD", kind="AP")
    result = compare_arap_gl_totals(
        company="cacao",
        as_of_date=date(2026, 8, 29),
        subledger_totals={nio_ar: Decimal("10"), usd_ap: Decimal("20")},
        gl_totals={nio_ar: Decimal("10")},
        mode="log",
        tolerance=Decimal("0"),
    )

    assert len(result.lines) == 2
    assert result.differences[0].key == usd_ap
    assert result.differences[0].gl_amount == Decimal("0")
    assert "libro=BOOK-USD" in result.message
    assert "moneda=USD" in result.message


def test_warn_and_log_modes_report_without_blocking(caplog):
    """Non-strict policies preserve the transaction while surfacing drift."""
    key = _key()
    warn_result = compare_arap_gl_totals(
        company="cacao",
        as_of_date=date(2026, 8, 29),
        subledger_totals={key: Decimal("2")},
        gl_totals={},
        mode="warn",
        tolerance=Decimal("0"),
    )
    with pytest.warns(RuntimeWarning, match="Diferencias AR/AP"):
        enforce_arap_gl_policy(warn_result)

    log_result = compare_arap_gl_totals(
        company="cacao",
        as_of_date=date(2026, 8, 29),
        subledger_totals={key: Decimal("2")},
        gl_totals={},
        mode="log",
        tolerance=Decimal("0"),
    )
    enforce_arap_gl_policy(log_result)

    assert log_result.blocked is False
    assert "Diferencias AR/AP" in caplog.text


@pytest.mark.parametrize("mode", ["strict", "warn", "log"])
def test_policy_accepts_supported_modes(mode):
    """All documented policy modes normalize consistently."""
    assert resolve_arap_gl_policy(mode=mode, tolerance="0.005") == (mode, Decimal("0.005"))


@pytest.mark.parametrize("mode,tolerance", [("ignore", "0.01"), ("strict", "-0.01"), ("strict", "NaN")])
def test_policy_rejects_invalid_configuration(mode, tolerance):
    """Invalid policy cannot silently weaken reconciliation."""
    with pytest.raises(ValueError):
        resolve_arap_gl_policy(mode=mode, tolerance=tolerance)
