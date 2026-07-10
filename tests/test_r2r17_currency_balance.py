"""Tests for R2R-17: balance validation in transaction currency."""

from decimal import Decimal

import pytest
from cacao_accounting.contabilidad.posting import _assert_entries_balance, PostingError
from cacao_accounting.database import GLEntry


def _make_entry(**kwargs):
    defaults = {
        "ledger_id": "GL",
        "account_id": "ACC",
        "debit": Decimal("0"),
        "credit": Decimal("0"),
        "debit_in_account_currency": None,
        "credit_in_account_currency": None,
        "account_currency": None,
    }
    defaults.update(kwargs)
    return GLEntry(**defaults)


def test_r2r17_balanced_company_currency():
    entries = [
        _make_entry(debit=Decimal("100"), credit=Decimal("0")),
        _make_entry(debit=Decimal("0"), credit=Decimal("100")),
    ]
    _assert_entries_balance(entries)


def test_r2r17_unbalanced_company_currency():
    entries = [
        _make_entry(debit=Decimal("100"), credit=Decimal("0")),
        _make_entry(debit=Decimal("0"), credit=Decimal("99")),
    ]
    with pytest.raises(PostingError, match="no balancean por libro"):
        _assert_entries_balance(entries)


def test_r2r17_balanced_transaction_currency():
    entries = [
        _make_entry(
            debit=Decimal("100"),
            credit=Decimal("0"),
            debit_in_account_currency=Decimal("100"),
            credit_in_account_currency=Decimal("0"),
            account_currency="USD",
        ),
        _make_entry(
            debit=Decimal("0"),
            credit=Decimal("100"),
            debit_in_account_currency=Decimal("0"),
            credit_in_account_currency=Decimal("100"),
            account_currency="USD",
        ),
    ]
    _assert_entries_balance(entries)


def test_r2r17_unbalanced_transaction_currency():
    entries = [
        _make_entry(
            debit=Decimal("100"),
            credit=Decimal("0"),
            debit_in_account_currency=Decimal("100"),
            credit_in_account_currency=Decimal("0"),
            account_currency="USD",
        ),
        _make_entry(
            debit=Decimal("0"),
            credit=Decimal("100"),
            debit_in_account_currency=Decimal("0"),
            credit_in_account_currency=Decimal("90"),
            account_currency="USD",
        ),
    ]
    with pytest.raises(PostingError, match="moneda de transaccion"):
        _assert_entries_balance(entries)


def test_r2r17_null_currency_skipped():
    entries = [
        _make_entry(
            debit=Decimal("100"),
            credit=Decimal("0"),
            debit_in_account_currency=None,
            credit_in_account_currency=None,
            account_currency=None,
        ),
        _make_entry(
            debit=Decimal("0"),
            credit=Decimal("100"),
            debit_in_account_currency=None,
            credit_in_account_currency=None,
            account_currency=None,
        ),
    ]
    _assert_entries_balance(entries)
