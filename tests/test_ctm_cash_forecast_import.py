"""Cash forecast imports must preserve valid currency references."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError


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


pytestmark = pytest.mark.database


@pytest.fixture
def forecast_import_app(tmp_path):
    """Use an isolated SQLite database or an explicitly enabled external engine."""
    database_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if database_uri.startswith("sqlite"):
        database_uri = f"sqlite:///{tmp_path / 'cash-forecast-import.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")

    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 2, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with application.app_context():
        database.create_all()

    yield application

    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_cash_forecast_import_rejects_unknown_currency_without_orphan(forecast_import_app):
    """A real forecast entry import cannot persist an unknown currency."""
    with forecast_import_app.app_context():
        suffix = uuid4().hex[:8]
        currency_code = f"C{suffix}"
        company_code = f"M{suffix}"
        database.session.add(Currency(code=currency_code, name="Moneda de pronóstico", decimals=2, active=True, default=False))
        company = Entity(
            code=company_code,
            name=f"Empresa de pronóstico {suffix}",
            company_name=f"Empresa de pronóstico {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency_code,
            enabled=True,
            status="default",
        )
        database.session.add(company)
        database.session.flush()

        fiscal_year = FiscalYear(
            entity=company.code,
            name=f"FY-{suffix}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        database.session.add(fiscal_year)
        database.session.flush()
        forecast = CashForecast(
            fiscal_year_id=fiscal_year.id,
            company=company.code,
            version="base",
            periodicity="monthly",
        )
        database.session.add(forecast)
        database.session.flush()

        adapter = CashForecastEntryAdapter()
        valid_row = {
            "forecast_id": forecast.id,
            "type": "Income",
            "concept": "Cobros previstos de clientes",
            "currency": currency_code,
            "amount": "1250.00",
            "estimated_date": "2026-02-28",
        }
        context = {"company_id": company.code, "created_by": None}
        assert adapter.validate_row(valid_row) == []
        assert adapter.validate_document([valid_row], context) == []
        adapter.persist_document(adapter.build_document([valid_row], context))
        database.session.commit()

        imported_entry = database.session.execute(
            database.select(CashForecastEntry).filter_by(forecast_id=forecast.id)
        ).scalar_one()
        assert imported_entry.amount == Decimal("1250.0000")
        assert imported_entry.currency == currency_code

        invalid_row = {
            **valid_row,
            "concept": "Cobro con moneda inexistente",
            "currency": f"X{suffix}",
        }
        assert adapter.validate_row(invalid_row) == []
        adapter.persist_document(adapter.build_document([invalid_row], context))
        with pytest.raises(DBAPIError):
            database.session.flush()
        database.session.rollback()

        entries = (
            database.session.execute(database.select(CashForecastEntry).filter_by(forecast_id=forecast.id)).scalars().all()
        )
        assert [(entry.concept, entry.currency, entry.amount) for entry in entries] == [
            ("Cobros previstos de clientes", currency_code, Decimal("1250.0000"))
        ]

        database.session.remove()
        if database.engine.dialect.name == "sqlite":
            first = database.engine.connect()
            second = database.engine.connect()
            try:
                assert first.connection.driver_connection is not second.connection.driver_connection
                assert first.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
                assert second.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
                assert first.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            finally:
                first.close()
                second.close()
