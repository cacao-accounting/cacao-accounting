# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1951: un rechazo del pronóstico conserva los datos enviados."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import inspect

from cacao_accounting.database import CashForecast, FiscalYear, database


def test_rechazo_conserva_datos_y_no_persiste_duplicado(app, authenticated_client, entorno_contable):
    """Una versión duplicada vuelve con los valores y selección enviados."""
    version = f"Q3-{uuid4().hex[:8]}"
    fiscal_year_id = inspect(entorno_contable.fiscal_year).identity[0]
    with app.app_context():
        fiscal_year = database.session.get(FiscalYear, fiscal_year_id)
        assert fiscal_year is not None
        existing = CashForecast(
            version=version,
            description="Versión previa",
            fiscal_year_id=fiscal_year_id,
            company="cacao",
            periodicity="monthly",
            status="Draft",
        )
        database.session.add(existing)
        database.session.commit()
        existing_id = existing.id
    datos = {
        "company": "cacao",
        "fiscal_year_id": fiscal_year_id,
        "version": version,
        "description": "Escenario pesimista",
        "periodicity": "weekly",
    }

    try:
        respuesta = authenticated_client("admin").post("/cash_management/cash-forecast/new", data=datos)

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert f'value="{version}"' in html
        assert "Escenario pesimista" in html
        assert f'value="{fiscal_year_id}" selected' in html
        assert 'value="weekly" selected' in html
        with app.app_context():
            matches = (
                database.session.execute(
                    database.select(CashForecast).filter_by(company="cacao", fiscal_year_id=fiscal_year_id, version=version)
                )
                .scalars()
                .all()
            )
            assert len(matches) == 1
    finally:
        with app.app_context():
            existing = database.session.get(CashForecast, existing_id)
            if existing is not None:
                database.session.delete(existing)
                database.session.commit()
