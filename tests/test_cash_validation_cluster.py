# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1083: el pronóstico de caja solo admite períodos semanales o mensuales."""

from __future__ import annotations

import os
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from cacao_accounting.bancos.cash_forecast_service import generate_periods
from cacao_accounting.database import CashForecast, FiscalYear, database

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="El pronóstico de caja no aplica en modo escritorio.",
)


@pytest.mark.parametrize("periodicity", ["annual", "daily", "desconocida"])
def test_generate_periods_rechaza_periodicidad_no_soportada(app, entorno_contable, periodicity):
    """El servicio no interpreta una periodicidad inválida como semanal."""
    with app.app_context():
        fiscal_year = database.session.get(FiscalYear, inspect(entorno_contable.fiscal_year).identity[0])
        assert fiscal_year is not None

        with pytest.raises(ValueError, match="La periodicidad debe ser semanal o mensual"):
            generate_periods(fiscal_year, periodicity)


@pytest.mark.parametrize(
    ("periodicity", "cantidad", "primer_fin"),
    [
        ("weekly", 53, date(2026, 1, 7)),
        ("monthly", 12, date(2026, 1, 31)),
    ],
)
def test_generate_periods_cubre_el_anio_con_periodicidad_valida(app, entorno_contable, periodicity, cantidad, primer_fin):
    """Los períodos válidos son contiguos y cubren todo el año fiscal."""
    with app.app_context():
        fiscal_year = database.session.get(FiscalYear, inspect(entorno_contable.fiscal_year).identity[0])
        assert fiscal_year is not None

        periodos = generate_periods(fiscal_year, periodicity)

        assert len(periodos) == cantidad
        assert periodos[0]["start_date"] == date(2026, 1, 1)
        assert periodos[0]["end_date"] == primer_fin
        assert periodos[-1]["start_date"] <= periodos[-1]["end_date"] == date(2026, 12, 31)
        assert all(
            periodo_actual["end_date"] + timedelta(days=1) == periodo_siguiente["start_date"]
            for periodo_actual, periodo_siguiente in zip(periodos, periodos[1:], strict=False)
        )


@pytest.mark.parametrize("periodicity", ["annual", "daily", "desconocida"])
def test_post_con_periodicidad_invalida_muestra_error_y_no_crea_pronostico(
    app, authenticated_client, entorno_contable, periodicity
):
    """El controlador rechaza el valor antes de persistir y conserva el formulario."""
    version = f"invalida-{periodicity}-{uuid4().hex[:8]}"
    fiscal_year_id = inspect(entorno_contable.fiscal_year).identity[0]
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        "/cash_management/cash-forecast/new",
        data={
            "company": "cacao",
            "fiscal_year_id": fiscal_year_id,
            "version": version,
            "description": "Periodicidad manipulada",
            "periodicity": periodicity,
        },
    )

    assert respuesta.status_code == 200
    html = respuesta.get_data(as_text=True)
    assert "La periodicidad debe ser semanal o mensual." in html
    assert f'value="{version}"' in html
    with app.app_context():
        assert (
            database.session.execute(
                database.select(CashForecast).filter_by(company="cacao", fiscal_year_id=fiscal_year_id, version=version)
            ).scalar_one_or_none()
            is None
        )


@pytest.mark.parametrize("periodicity", ["weekly", "monthly"])
def test_post_con_periodicidad_valida_crea_pronostico(app, authenticated_client, entorno_contable, periodicity):
    """Las dos periodicidades soportadas siguen creando pronósticos en borrador."""
    version = f"valida-{periodicity}-{uuid4().hex[:8]}"
    fiscal_year_id = inspect(entorno_contable.fiscal_year).identity[0]
    cliente = authenticated_client("admin")

    respuesta = cliente.post(
        "/cash_management/cash-forecast/new",
        data={
            "company": "cacao",
            "fiscal_year_id": fiscal_year_id,
            "version": version,
            "description": "Escenario válido",
            "periodicity": periodicity,
        },
    )

    assert respuesta.status_code == 302
    with app.app_context():
        pronostico = database.session.execute(
            database.select(CashForecast).filter_by(company="cacao", fiscal_year_id=fiscal_year_id, version=version)
        ).scalar_one()
        assert pronostico.periodicity == periodicity
        assert pronostico.status == "Draft"
        database.session.delete(pronostico)
        database.session.commit()
