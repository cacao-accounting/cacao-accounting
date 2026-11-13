# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación de claves foráneas SQLite en conexiones de la aplicación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import CashForecast, CashForecastEntry, Currency, Entity, FiscalYear, database


@pytest.fixture
def sqlite_app(tmp_path):
    """Crea una aplicación SQLite aislada sin hooks específicos de tests."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'foreign_keys.db'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 2, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "sqlite-foreign-key-test-secret",
        }
    )
    with application.app_context():
        database.create_all()
        database.session.remove()
        database.engine.dispose()
        yield application
        database.session.remove()
        database.engine.dispose()


def test_sqlite_foreign_keys_enabled_on_each_new_connection(sqlite_app):
    """Cada conexión física recibe el pragma antes de usarse."""
    with sqlite_app.app_context():
        first = database.engine.connect()
        second = database.engine.connect()
        try:
            assert first.connection.driver_connection is not second.connection.driver_connection
            assert first.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert second.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        finally:
            first.close()
            second.close()


def test_sqlite_rejects_invalid_foreign_key_and_has_no_orphans(sqlite_app):
    """Una moneda inexistente falla y el rollback conserva integridad referencial."""
    with sqlite_app.app_context():
        currency = Currency(code="NIO", name="Córdoba", active=True, default=True)
        entity = Entity(code="cacao", company_name="Cacao SA", tax_id="J0001", currency="NIO", enabled=True)
        fiscal_year = FiscalYear(
            entity="cacao",
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
        )
        database.session.add_all([currency, entity, fiscal_year])
        database.session.flush()
        forecast = CashForecast(
            fiscal_year_id=fiscal_year.id,
            company="cacao",
            version="base",
            periodicity="monthly",
        )
        database.session.add(forecast)
        database.session.flush()
        database.session.add(
            CashForecastEntry(
                forecast_id=forecast.id,
                type="Income",
                concept="Referencia inválida",
                currency="ZZZ_INVALID",
                amount=Decimal("10"),
                estimated_date=date(2026, 1, 31),
            )
        )

        with pytest.raises(IntegrityError):
            database.session.flush()
        database.session.rollback()

        with database.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
