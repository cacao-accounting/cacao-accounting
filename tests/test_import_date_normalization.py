# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1055: fechas de Excel normalizadas antes de validar.

XLSX entrega `datetime` y XLS seriales numéricos; los adaptadores deben
convertirlos a `date` sin rechazarlos ni dejarlos llegar a la ejecución.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.imports.adapters.journal_entry import JournalEntryAdapter
from cacao_accounting.imports.adapters.transaction_documents import (
    TransactionDocumentAdapter,
    TransactionImportConfig,
)
from cacao_accounting.imports.utils.dates import parse_import_date

EXCEL_SERIAL = 46152  # 2026-05-10 con el sistema de fechas de Excel


@pytest.fixture
def date_import_scenario():
    """Create a company for period and currency checks."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {uuid4().hex[:6]}",
                    tax_id=f"TAX-{uuid4().hex[:6]}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.commit()

    yield app

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.mark.parametrize(
    "value",
    [
        date(2026, 5, 10),
        datetime(2026, 5, 10, 0, 0),
        "2026-05-10",
        "2026-05-10 00:00:00",
        EXCEL_SERIAL,
        float(EXCEL_SERIAL),
    ],
)
def test_parse_import_date_normalizes_supported_representations(value):
    """All reader representations resolve to the same date."""
    assert parse_import_date(value) == date(2026, 5, 10)


@pytest.mark.parametrize("value", [None, "", "no-es-fecha", 0, -1, "NaN"])
def test_parse_import_date_rejects_invalid_values(value):
    """Invalid or non-positive serials fail with a controlled error."""
    with pytest.raises(ValueError):
        parse_import_date(value)


def test_transaction_validation_accepts_an_excel_datetime(date_import_scenario):
    """An XLSX datetime is not reported as a malformed ISO date."""
    app = date_import_scenario
    adapter = TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_request",
            header_model=object,
            item_model=object,
            parent_field="purchase_request_id",
        )
    )

    with app.app_context():
        errors = adapter.validate_document(
            [
                {
                    "document_ref": "PR-1",
                    "fecha": datetime(2026, 5, 10, 0, 0),
                    "producto": "ITEM-1",
                    "cantidad": "1",
                    "precio_unitario": "5",
                }
            ],
            {"company_id": "alpha"},
        )

    assert not any("fecha válida" in error for error in errors)


def test_journal_period_validation_accepts_an_excel_datetime(date_import_scenario):
    """The journal prevalidation parses the datetime instead of ignoring it."""
    app = date_import_scenario
    adapter = JournalEntryAdapter()

    with app.app_context():
        errors = adapter._validate_period(
            [{"document_ref": "JE-1", "fecha": datetime(2026, 5, 10, 0, 0)}],
            {"company_id": "alpha"},
        )

    assert errors
    assert not any("formato válido" in error for error in errors)


def test_bank_statement_build_accepts_datetime_and_serial():
    """The bank adapter returns the same date for datetime and serial cells."""
    adapter = BankStatementAdapter()
    base_row = {
        "bank_account_id": "BA-1",
        "reference_number": "REF",
        "description": "",
        "deposit": "10",
        "withdrawal": None,
    }

    datetime_document = adapter.build_document(
        [{**base_row, "posting_date": datetime(2026, 5, 10, 0, 0)}],
        {"company_id": "alpha"},
    )
    serial_document = adapter.build_document(
        [{**base_row, "posting_date": EXCEL_SERIAL}],
        {"company_id": "alpha"},
    )

    assert datetime_document[0]["posting_date"] == date(2026, 5, 10)
    assert serial_document[0]["posting_date"] == date(2026, 5, 10)


def test_out_of_range_excel_serial_is_a_validation_error():
    """A huge numeric cell becomes ValueError, not OverflowError (#1055)."""
    with pytest.raises(ValueError):
        parse_import_date(20261030)


def test_transaction_document_reports_a_huge_numeric_date(date_import_scenario):
    """A large YYYYMMDD-like number is a row error, not an uncaught exception."""
    app = date_import_scenario
    adapter = TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_request",
            header_model=object,
            item_model=object,
            parent_field="purchase_request_id",
        )
    )
    with app.app_context():
        errors = adapter.validate_document(
            [
                {
                    "document_ref": "PR-1",
                    "fecha": 20261030,
                    "producto": "ITEM-1",
                    "cantidad": "1",
                    "precio_unitario": "5",
                }
            ],
            {"company_id": "alpha"},
        )

    assert any("fecha válida" in error for error in errors)
