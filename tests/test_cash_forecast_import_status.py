# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1049: la importación no modifica pronósticos de caja no borrador.

El estado se valida al revisar las filas y otra vez justo antes de persistir,
de modo que una aprobación concurrente tampoco permite agregar entradas.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

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
from cacao_accounting.imports.adapters.cash_forecast_entry import CashForecastEntryAdapter


@pytest.fixture
def forecast_status_scenario():
    """Create a draft and an approved forecast for one company."""
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
        draft = CashForecast(
            company="alpha",
            version=f"Draft-{suffix}",
            fiscal_year_id=year.id,
            periodicity="monthly",
            status="Draft",
        )
        approved = CashForecast(
            company="alpha",
            version=f"Approved-{suffix}",
            fiscal_year_id=year.id,
            periodicity="monthly",
            status="Approved",
        )
        database.session.add_all([draft, approved])
        database.session.commit()
        ids = {"draft": draft.id, "approved": approved.id}

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _row(forecast_id: str) -> dict:
    """Build one valid import row for a forecast."""
    return {
        "forecast_id": forecast_id,
        "type": "Income",
        "concept": "Venta proyectada",
        "currency": "NIO",
        "amount": "150",
        "estimated_date": "2026-05-10",
        "notes": "",
    }


def _entries(app, forecast_id: str) -> list[CashForecastEntry]:
    """Read persisted entries for one forecast."""
    with app.app_context():
        return list(
            database.session.execute(database.select(CashForecastEntry).filter_by(forecast_id=forecast_id)).scalars().all()
        )


def test_approved_forecast_is_rejected_at_row_validation(forecast_status_scenario):
    """A non-draft forecast reports a validation error before executing."""
    app, ids = forecast_status_scenario
    adapter = CashForecastEntryAdapter()

    with app.app_context():
        errors = adapter.validate_row(_row(ids["approved"]))
        document_errors = adapter.validate_document([_row(ids["approved"])], {"company_id": "alpha"})
        assert adapter.validate_row(_row(ids["draft"])) == []

    assert any("Borrador" in error for error in errors)
    assert any("Borrador" in error for error in document_errors)


def test_persist_rechecks_status_and_does_not_write(forecast_status_scenario):
    """An approval after validation still blocks the persistence."""
    app, ids = forecast_status_scenario
    adapter = CashForecastEntryAdapter()

    with app.app_context():
        draft_document = adapter.build_document([_row(ids["draft"])], {"company_id": "alpha"})
        adapter.persist_document(draft_document)
        database.session.commit()

        approved_document = adapter.build_document([_row(ids["approved"])], {"company_id": "alpha"})
        with pytest.raises(ValueError):
            adapter.persist_document(approved_document)
        database.session.rollback()

        forecast = database.session.get(CashForecast, ids["draft"])
        forecast.status = "Approved"
        database.session.commit()
        late_document = adapter.build_document([_row(ids["draft"])], {"company_id": "alpha"})
        with pytest.raises(ValueError):
            adapter.persist_document(late_document)
        database.session.rollback()

    assert len(_entries(app, ids["draft"])) == 1
    assert _entries(app, ids["approved"]) == []
