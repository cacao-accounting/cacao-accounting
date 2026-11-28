# SPDX-License-Identifier: Apache-2.0
"""#1505: el importador activo rechaza importes negativos sin importacion parcial."""

from __future__ import annotations

import pytest
from flask_babel import force_locale

from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter


def test_validate_row_rejects_negative_deposit_and_withdrawal(app):
    with app.app_context():
        adapter = BankStatementAdapter()
        errs = adapter.validate_row(
            {
                "bank_account_id": "ba1",
                "posting_date": "2026-11-01",
                "deposit": "-100.00",
                "withdrawal": "50.00",
            }
        )
        assert any("negativo" in str(e).lower() for e in errs)
        errs = adapter.validate_row(
            {
                "bank_account_id": "ba1",
                "posting_date": "2026-11-01",
                "deposit": "100.00",
                "withdrawal": "-50.00",
            }
        )
        assert any("negativo" in str(e).lower() for e in errs)


def test_build_document_rejects_negative_amounts_no_partial_import(app):
    with app.app_context():
        adapter = BankStatementAdapter()
        with pytest.raises(ValueError, match="negativo"):
            adapter.build_document(
                [
                    {
                        "bank_account_id": "ba1",
                        "posting_date": "2026-11-01",
                        "deposit": "100.00",
                        "withdrawal": "-50.00",
                    }
                ],
                {"company_id": "E1"},
            )


@pytest.mark.parametrize("field", ["deposit", "withdrawal"])
def test_build_document_persists_translated_negative_amount_error(app, field: str):
    """El error de construcción conserva el msgid traducido y no importa la fila."""
    row = {
        "bank_account_id": "ba1",
        "posting_date": "2026-11-01",
        "deposit": "100.00",
        "withdrawal": "50.00",
    }
    row[field] = "-1.00"
    with app.app_context(), force_locale("en"):
        with pytest.raises(ValueError) as error:
            BankStatementAdapter().build_document([row], {"company_id": "E1"})
    assert str(error.value) == f"The bank amount in column '{field}' cannot be negative."
