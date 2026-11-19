# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2185: las proyecciones manuales pertenecen al año fiscal del pronóstico."""

from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from cacao_accounting.database import CashForecast, CashForecastEntry, database

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="El pronóstico de caja no aplica en modo escritorio.",
)


def _crear_pronostico(cliente) -> str:
    """Crea un pronóstico borrador por la ruta real y devuelve su id."""
    respuesta = cliente.post(
        "/cash_management/cash-forecast/new",
        data={
            "company": "cacao",
            "version": f"fy-{uuid4().hex[:8]}",
            "description": "Alcance fiscal",
            "fiscal_year_id": "FY2026",
            "periodicity": "monthly",
        },
    )
    assert respuesta.status_code in (302, 303)
    return urlsplit(respuesta.headers["Location"]).path.rsplit("/", 1)[-1]


def _datos_entrada(fecha: str) -> dict[str, str]:
    return {
        "type": "Income",
        "concept": "Cobro proyectado",
        "currency": "NIO",
        "amount": "100",
        "estimated_date": fecha,
        "notes": "",
    }


def _entradas(app, forecast_id: str) -> list[CashForecastEntry]:
    with app.app_context():
        return list(
            database.session.execute(database.select(CashForecastEntry).filter_by(forecast_id=forecast_id)).scalars().all()
        )


def test_alta_y_edicion_rechazan_fechas_fuera_del_anio_fiscal(app, authenticated_client, entorno_contable):
    """La fecha estimada debe caer dentro del año fiscal; el rechazo no persiste."""
    cliente = authenticated_client()
    forecast_id = _crear_pronostico(cliente)

    rechazo = cliente.post(
        f"/cash_management/cash-forecast/{forecast_id}/entry/add",
        data=_datos_entrada("2027-01-01"),
    )
    assert rechazo.status_code == 302
    seguimiento = cliente.get(rechazo.headers["Location"])
    assert "dentro del año fiscal" in seguimiento.get_data(as_text=True)
    assert _entradas(app, forecast_id) == []

    valida = cliente.post(
        f"/cash_management/cash-forecast/{forecast_id}/entry/add",
        data=_datos_entrada("2026-12-31"),
    )
    assert valida.status_code == 302
    entradas = _entradas(app, forecast_id)
    assert len(entradas) == 1
    entry_id = entradas[0].id

    edicion = cliente.post(
        f"/cash_management/cash-forecast/{forecast_id}/entry/{entry_id}/edit",
        data=_datos_entrada("2027-01-02"),
    )
    assert edicion.status_code == 302
    with app.app_context():
        entry = database.session.get(CashForecastEntry, entry_id)
        assert entry.estimated_date == date(2026, 12, 31)


def test_el_detalle_reporta_historicos_fuera_del_anio_fiscal(app, authenticated_client, entorno_contable):
    """Un registro histórico inconsistente se avisa sin cambiar su fecha."""
    cliente = authenticated_client()
    forecast_id = _crear_pronostico(cliente)
    with app.app_context():
        forecast = database.session.get(CashForecast, forecast_id)
        historico = CashForecastEntry(
            forecast_id=forecast.id,
            type="Income",
            concept="Histórico fuera de rango",
            currency="NIO",
            amount=100,
            estimated_date=date(2027, 3, 1),
        )
        database.session.add(historico)
        database.session.commit()
        entry_id = historico.id

    detalle = cliente.get(f"/cash_management/cash-forecast/{forecast_id}")

    assert detalle.status_code == 200
    assert "proyecciones fuera del año fiscal" in detalle.get_data(as_text=True)
    with app.app_context():
        entry = database.session.get(CashForecastEntry, entry_id)
        assert entry.estimated_date == date(2027, 3, 1)
