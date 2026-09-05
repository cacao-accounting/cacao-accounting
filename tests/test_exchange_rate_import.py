# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Pruebas del servicio de importación de tasas de cambio."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Crea una aplicacion Flask aislada para pruebas."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import Currency, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Currency(code="USD", name="Dollar", decimals=2, active=True),
                Currency(code="NIO", name="Cordoba", decimals=2, active=True, default=True),
            ]
        )
        database.session.commit()
        yield app


class TestParseDate:
    """Pruebas del parser de fechas."""

    def test_iso_format(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("2027-01-01") == date(2027, 1, 1)

    def test_iso_format_with_time(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("2027-01-01 00:00:00") == date(2027, 1, 1)

    def test_iso_format_with_time_no_seconds(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("2027-01-01 12:30") == date(2027, 1, 1)

    def test_dmy_dash_format(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("01-01-2027") == date(2027, 1, 1)

    def test_dmy_dash_format_with_time(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("01-01-2027 00:00:00") == date(2027, 1, 1)

    def test_dmy_slash_format(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("01/01/2027") == date(2027, 1, 1)

    def test_dmy_slash_format_with_time(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("01/01/2027 14:30:00") == date(2027, 1, 1)

    def test_mdy_slash_format(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("01/01/2027") == date(2027, 1, 1)

    def test_datetime_object(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date(datetime(2027, 1, 1, 12, 30)) == date(2027, 1, 1)

    def test_date_object(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date(date(2027, 1, 1)) == date(2027, 1, 1)

    def test_invalid_date(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("not-a-date") is None

    def test_empty_string(self):
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        assert ExchangeRateImportService._parse_date("") is None


class TestImportRates:
    """Pruebas de importación de tasas de cambio."""

    def test_import_with_iso_datetime_format(self, app_ctx):
        """Verifica que fechas en formato ISO con hora se importan correctamente."""
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        csv_content = "Moneda Base,Moneda Destino,Fecha,Tipo de Cambio\nNIO,USD,2027-01-01 00:00:00,36.6243\n"
        svc = ExchangeRateImportService()
        result = svc.import_rates("test.csv", csv_content.encode("utf-8-sig"))

        assert result["inserted"] == 1
        assert result["errors"] == []

    def test_import_with_various_date_formats(self, app_ctx):
        """Verifica que múltiples formatos de fecha se manejan correctamente."""
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        csv_content = (
            "Moneda Base,Moneda Destino,Fecha,Tipo de Cambio\n"
            "NIO,USD,2027-01-01 00:00:00,36.6243\n"
            "NIO,USD,01-02-2027,36.7000\n"
            "NIO,USD,01/03/2027,36.8000\n"
        )
        svc = ExchangeRateImportService()
        result = svc.import_rates("test.csv", csv_content.encode("utf-8-sig"))

        assert result["inserted"] == 3
        assert result["errors"] == []

    def test_import_skips_invalid_dates(self, app_ctx):
        """Verifica que filas con fechas inválidas se reportan como errores."""
        from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService

        csv_content = (
            "Moneda Base,Moneda Destino,Fecha,Tipo de Cambio\n" "NIO,USD,2027-01-01,36.6243\n" "NIO,USD,invalid-date,36.7000\n"
        )
        svc = ExchangeRateImportService()
        result = svc.import_rates("test.csv", csv_content.encode("utf-8-sig"))

        assert result["inserted"] == 1
        assert len(result["errors"]) == 1
        assert "invalid-date" in result["errors"][0]
