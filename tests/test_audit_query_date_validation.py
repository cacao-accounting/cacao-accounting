# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1969: los query tools validan fechas y rangos como parámetros."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.handlers import audit_trail


def _contexto():
    return SimpleNamespace(user_id="u1", company_ids=("cacao",))


def test_fecha_imposible_es_error_de_parametro(app, monkeypatch):
    """Una fecha inválida no escapa como ValueError."""
    monkeypatch.setattr(audit_trail, "validate_permission", lambda *a, **k: None)
    with app.app_context():
        with pytest.raises(QueryToolError) as exc:
            audit_trail.get_user_activity_summary.handler(context=_contexto(), company_id="cacao", date_from="2026-02-31")

    assert exc.value.code == ErrorCode.INVALID_PARAMETER


def test_rango_invertido_es_error_de_parametro(app, monkeypatch):
    """date_from posterior a date_to se rechaza antes de consultar."""
    monkeypatch.setattr(audit_trail, "validate_permission", lambda *a, **k: None)
    with app.app_context():
        with pytest.raises(QueryToolError) as exc:
            audit_trail.get_user_activity_summary.handler(
                context=_contexto(), company_id="cacao", date_from="2026-12-31", date_to="2026-01-01"
            )

    assert exc.value.code == ErrorCode.INVALID_PARAMETER


@pytest.mark.parametrize(
    ("modulo", "funcion", "kwargs"),
    [
        ("analytics", "get_kpi_snapshot_tool", {"date_from": "2026-02-31", "date_to": "2026-03-01"}),
        ("advanced", "get_banking_balance_summary", {"as_of_date": "2026-02-31"}),
        ("operational", "search_payments", {"date_from": "2026-02-31"}),
        ("receivables", "get_receivables_aging", {"as_of_date": "2026-02-31"}),
        ("payables", "get_payables_aging", {"as_of_date": "2026-02-31"}),
        ("treasury", "get_maturity_schedule_handler", {"as_of_date": "2026-02-31"}),
    ],
)
def test_los_handlers_restantes_traducen_la_fecha_invalida(app, monkeypatch, modulo, funcion, kwargs):
    """Todos los consumidores devuelven INVALID_PARAMETER en lugar de ValueError."""
    modulo_obj = importlib.import_module(f"cacao_accounting.query_tools.handlers.{modulo}")
    monkeypatch.setattr(modulo_obj, "validate_permission", lambda *a, **k: None)

    with app.app_context():
        with pytest.raises(QueryToolError) as exc:
            getattr(modulo_obj, funcion).handler(context=_contexto(), company_id="cacao", **kwargs)

    assert exc.value.code == ErrorCode.INVALID_PARAMETER
    assert "ISO 8601" in exc.value.message


@pytest.mark.parametrize(
    ("funcion", "kwargs"),
    [
        ("get_kpi_snapshot_tool", {"date_from": "2026-12-31", "date_to": "2026-01-01"}),
        ("get_trend_tool", {"metric": "income", "date_from": "2026-12-31", "date_to": "2026-01-01"}),
        (
            "get_concentration_tool",
            {"dimension": "customer", "date_from": "2026-12-31", "date_to": "2026-01-01"},
        ),
        (
            "compare_periods_tool",
            {
                "metric": "income",
                "base_date_from": "2026-12-31",
                "base_date_to": "2026-01-01",
                "compare_date_from": "2026-01-01",
                "compare_date_to": "2026-12-31",
            },
        ),
    ],
)
def test_analytics_rechaza_rango_invertido(app, monkeypatch, funcion, kwargs):
    """Un rango invertido es INVALID_PARAMETER, no una respuesta vacía."""
    modulo_obj = importlib.import_module("cacao_accounting.query_tools.handlers.analytics")
    monkeypatch.setattr(modulo_obj, "validate_permission", lambda *a, **k: None)

    with app.app_context():
        with pytest.raises(QueryToolError) as exc:
            getattr(modulo_obj, funcion).handler(context=_contexto(), company_id="cacao", **kwargs)

    assert exc.value.code == ErrorCode.INVALID_PARAMETER
    assert "fecha inicial" in exc.value.message
