# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1033: celdas vacías de XLSX/ODS no persisten el literal "None".

Los lectores entregan `None` en celdas vacías; los adaptadores deben
normalizarlo a vacío o al valor por defecto (moneda NIO en pronósticos).
"""

from __future__ import annotations

from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.imports.adapters.cash_forecast_entry import CashForecastEntryAdapter


def test_bank_statement_normalizes_empty_description_and_reference():
    """An empty XLSX cell becomes an empty string, not "None"."""
    documents = BankStatementAdapter().build_document(
        [
            {
                "bank_account_id": "BA-1",
                "posting_date": "2026-05-10",
                "reference_number": None,
                "description": None,
                "deposit": "10",
                "withdrawal": "",
            }
        ],
        {"company_id": "alpha"},
    )

    assert len(documents) == 1
    assert documents[0]["reference_number"] == ""
    assert documents[0]["description"] == ""
    assert documents[0]["bank_account_id"] == "BA-1"


def test_cash_forecast_normalizes_empty_text_cells_and_currency():
    """Empty concept, notes and currency use the documented defaults."""
    documents = CashForecastEntryAdapter().build_document(
        [
            {
                "forecast_id": "FC-1",
                "type": "Income",
                "concept": None,
                "currency": None,
                "amount": "25",
                "estimated_date": "2026-05-10",
                "notes": None,
            }
        ],
        {"company_id": "alpha"},
    )

    assert len(documents) == 1
    assert documents[0]["concept"] == ""
    assert documents[0]["notes"] == ""
    assert documents[0]["currency"] == "NIO"
