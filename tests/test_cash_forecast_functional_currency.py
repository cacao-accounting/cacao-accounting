# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1324: el pronóstico de caja no asume NIO sin moneda funcional.

Si la compañía no tiene moneda configurada (o está inactiva), la matriz
debe detenerse con un error de configuración en lugar de convertir a NIO.
"""

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.bancos.cash_forecast_service import (
    CashForecastConversionError,
    _resolve_company_currency,
    get_cash_forecast_matrix,
)
from cacao_accounting.database import (
    CashForecast,
    Currency,
    Entity,
    FiscalYear,
    database,
)


def _company(currency: str | None) -> str:
    """Crea una compañía con la moneda funcional indicada."""
    suffix = uuid4().hex[:6]
    code = f"S{suffix}"
    database.session.add(
        Entity(
            code=code,
            name=f"Compañía {suffix}",
            company_name=f"Compañía {suffix} SA",
            tax_id=f"TAX-{suffix}",
            currency=currency,
            enabled=True,
        )
    )
    database.session.commit()
    return code


def test_compania_configurada_conserva_su_moneda(entorno_contable_aislado):
    """La compañía del escenario resuelve NIO sin cambios."""
    app = entorno_contable_aislado.app
    with app.app_context():
        assert _resolve_company_currency("cacao") == "NIO"


def test_compania_sin_moneda_falla(entorno_contable_aislado):
    """Sin moneda funcional no se inventa NIO."""
    app = entorno_contable_aislado.app
    with app.app_context():
        company = _company(None)

        with pytest.raises(CashForecastConversionError, match="moneda funcional configurada"):
            _resolve_company_currency(company)


def test_compania_con_moneda_inactiva_falla(entorno_contable_aislado):
    """Una moneda funcional inactiva tampoco se usa."""
    app = entorno_contable_aislado.app
    with app.app_context():
        database.session.add(Currency(code="ZZZ", name="Moneda inactiva", decimals=2, active=False, default=False))
        database.session.commit()
        company = _company("ZZZ")

        with pytest.raises(CashForecastConversionError, match="no esta activa"):
            _resolve_company_currency(company)


def test_matriz_no_presenta_saldos_en_moneda_asumida(entorno_contable_aislado):
    """La matriz falla antes de convertir saldos si falta la moneda funcional."""
    app = entorno_contable_aislado.app
    with app.app_context():
        company = _company(None)
        fiscal_year = FiscalYear(
            entity=company,
            name=f"FY-{uuid4().hex[:6]}",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(fiscal_year)
        database.session.flush()
        forecast = CashForecast(
            company=company,
            version=f"Draft-{uuid4().hex[:6]}",
            fiscal_year_id=fiscal_year.id,
            periodicity="monthly",
            status="Draft",
        )
        database.session.add(forecast)
        database.session.commit()

        with pytest.raises(CashForecastConversionError):
            get_cash_forecast_matrix(company, forecast.id, today_date=date(2026, 5, 15))
