# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1050: la importación de pronósticos exige montos positivos.

La edición manual rechaza importes <= 0; la importación debe aplicar la misma
regla al validar y al persistir.
"""

from __future__ import annotations

import csv
from datetime import date
from uuid import uuid4

import pytest
from openpyxl import Workbook

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CashForecast,
    CashForecastEntry,
    Currency,
    Entity,
    FiscalYear,
    database,
)
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.adapters.cash_forecast_entry import CashForecastEntryAdapter
from cacao_accounting.imports.services.import_service import ImportService


@pytest.fixture
def forecast_amount_scenario():
    """Create one draft forecast for the company."""
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
    suffix = uuid4().hex[:6]

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-{suffix}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        year = FiscalYear(
            entity="alpha",
            name=f"FY-{suffix}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        database.session.add(year)
        database.session.flush()
        forecast = CashForecast(
            company="alpha",
            version=f"Draft-{suffix}",
            fiscal_year_id=year.id,
            periodicity="monthly",
            status="Draft",
        )
        database.session.add(forecast)
        database.session.commit()
        ids = {"forecast": forecast.id}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _row(forecast_id: str, amount: str) -> dict:
    """Build one import row with the requested amount."""
    return {
        "forecast_id": forecast_id,
        "type": "Income",
        "concept": "Venta proyectada",
        "currency": "NIO",
        "amount": amount,
        "estimated_date": "2026-05-10",
        "notes": "",
    }


def _write_forecast_rows(path, source_format: str, rows: list[list[object]]) -> None:
    """Write forecast rows in the selected supported import format."""
    headers = CashForecastEntryAdapter.columns
    if source_format == "csv":
        with path.open("w", encoding="utf-8", newline="") as source_file:
            writer = csv.writer(source_file)
            writer.writerow(headers)
            writer.writerows(rows)
        return

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


@pytest.mark.parametrize("amount", ["0", "-0.01", "-100"])
def test_non_positive_amounts_are_rejected_in_validation(forecast_amount_scenario, amount):
    """Zero and negative amounts report a validation error."""
    app, ids = forecast_amount_scenario
    adapter = CashForecastEntryAdapter()

    with app.app_context():
        errors = adapter.validate_row(_row(ids["forecast"], amount))
        with pytest.raises(ValueError):
            adapter.build_document([_row(ids["forecast"], amount)], {"company_id": "alpha"})

    assert any("mayor que cero" in error for error in errors)


@pytest.mark.parametrize("amount", [0, -1, 0.0, -1.0])
def test_numeric_spreadsheet_amounts_are_rejected(forecast_amount_scenario, amount):
    """Las celdas numéricas de XLS/XLSX no eluden la regla de importe positivo."""
    app, ids = forecast_amount_scenario
    adapter = CashForecastEntryAdapter()
    row = _row(ids["forecast"], amount)

    with app.app_context():
        errors = adapter.validate_row(row)
        with pytest.raises(ValueError, match="mayor que cero"):
            adapter.build_document([row], {"company_id": "alpha"})

    assert any("mayor que cero" in error for error in errors)


def test_csv_negative_amount_with_leading_space_is_rejected(forecast_amount_scenario):
    """Un signo con espacio inicial no evade la validación compartida del adaptador."""
    app, ids = forecast_amount_scenario
    adapter = CashForecastEntryAdapter()
    row = _row(ids["forecast"], " -100")

    with app.app_context():
        errors = adapter.validate_row(row)
        with pytest.raises(ValueError, match="mayor que cero"):
            adapter.build_document([row], {"company_id": "alpha"})

    assert any("mayor que cero" in error for error in errors)


def test_persist_rechecks_positive_amount_before_inserting(forecast_amount_scenario):
    """A manually built document cannot bypass the amount rule."""
    app, ids = forecast_amount_scenario
    adapter = CashForecastEntryAdapter()

    with app.app_context():
        adapter.persist_document(
            [
                {
                    "forecast_id": ids["forecast"],
                    "type": "Income",
                    "concept": "Venta",
                    "currency": "NIO",
                    "amount": 50,
                    "estimated_date": date(2026, 5, 10),
                    "notes": "",
                    "company_id": "alpha",
                }
            ]
        )
        database.session.commit()
        with pytest.raises(ValueError):
            adapter.persist_document(
                [
                    {
                        "forecast_id": ids["forecast"],
                        "type": "Income",
                        "concept": "Venta",
                        "currency": "NIO",
                        "amount": -50,
                        "estimated_date": date(2026, 5, 10),
                        "notes": "",
                        "company_id": "alpha",
                    }
                ]
            )
        database.session.rollback()
        entries = (
            database.session.execute(database.select(CashForecastEntry).filter_by(forecast_id=ids["forecast"])).scalars().all()
        )

    assert len(entries) == 1
    assert entries[0].amount == 50


@pytest.mark.parametrize(
    ("source_format", "entry_type", "invalid_amount"),
    [
        ("csv", "Income", "-100"),
        ("csv", "Expense", "0"),
        ("xlsx", "Income", -100),
        ("xlsx", "Expense", 0),
    ],
)
def test_invalid_amount_blocks_whole_forecast_import_batch(
    forecast_amount_scenario, tmp_path, source_format, entry_type, invalid_amount
):
    """CSV and XLSX batches reject non-positive Income and Expense rows before persistence."""
    app, ids = forecast_amount_scenario
    path = tmp_path / f"forecast-entries.{source_format}"
    rows = [
        [ids["forecast"], entry_type, "Importe válido", "NIO", 25 if source_format == "xlsx" else "25", "2026-05-10", ""],
        [ids["forecast"], entry_type, "Importe inválido", "NIO", invalid_amount, "2026-05-11", ""],
    ]
    _write_forecast_rows(path, source_format, rows)

    with app.app_context():
        batch = ImportBatch(
            company_id="alpha",
            record_type="cash_forecast_entry",
            source_format=source_format,
            source_filename=path.name,
            source_path=str(path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()

        assert ImportService().validate(batch.id)
        database.session.refresh(batch)
        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        entries = (
            database.session.execute(database.select(CashForecastEntry).filter_by(forecast_id=ids["forecast"])).scalars().all()
        )

        assert batch.import_status == 2
        assert any(error.error_type == "ROW_VALIDATION" for error in errors)
        assert entries == []
