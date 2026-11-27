# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Manual cash projections reject and exclude non-finite amounts (#1500)."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from cacao_accounting.bancos.cash_forecast_service import _compute_manual_projections
from cacao_accounting.database import CashForecast, CashForecastEntry, database

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="El pronóstico de caja no aplica en modo escritorio.",
)


def _create_forecast(client) -> str:
    """Create a draft cash forecast through its HTTP route."""
    response = client.post(
        "/cash_management/cash-forecast/new",
        data={
            "company": "cacao",
            "version": f"finite-{uuid4().hex[:8]}",
            "description": "Montos finitos",
            "fiscal_year_id": "FY2026",
            "periodicity": "monthly",
        },
    )
    assert response.status_code in (302, 303)
    return urlsplit(response.headers["Location"]).path.rsplit("/", 1)[-1]


def _entry_payload(amount: str) -> dict[str, str]:
    """Build a valid manual projection payload except for its requested amount."""
    return {
        "type": "Income",
        "concept": "Cobro proyectado",
        "currency": "NIO",
        "amount": amount,
        "estimated_date": "2026-12-15",
        "notes": "",
    }


@pytest.mark.usefixtures("entorno_contable")
def test_manual_projection_add_and_edit_reject_infinity_without_mutation(app, authenticated_client):
    """Both HTTP writers reject Infinity and an invalid edit preserves the original amount."""
    client = authenticated_client()
    forecast_id = _create_forecast(client)

    added = client.post(
        f"/cash_management/cash-forecast/{forecast_id}/entry/add",
        data=_entry_payload("Infinity"),
    )
    assert added.status_code == 302
    with app.app_context():
        assert (
            not database.session.execute(database.select(CashForecastEntry).filter_by(forecast_id=forecast_id)).scalars().all()
        )

    client.post(
        f"/cash_management/cash-forecast/{forecast_id}/entry/add",
        data=_entry_payload("125.50"),
    )
    with app.app_context():
        entry = database.session.execute(database.select(CashForecastEntry).filter_by(forecast_id=forecast_id)).scalar_one()
        entry_id = entry.id
        original_amount = entry.amount
        assert original_amount == Decimal("125.50")

    edited = client.post(
        f"/cash_management/cash-forecast/{forecast_id}/entry/{entry_id}/edit",
        data=_entry_payload("Infinity"),
    )
    assert edited.status_code == 302
    with app.app_context():
        assert database.session.get(CashForecastEntry, entry_id).amount == original_amount


def test_manual_projection_calculation_skips_legacy_non_finite_amounts():
    """A legacy non-finite row cannot contaminate otherwise valid forecast totals."""
    entries = [
        CashForecastEntry(
            type="Income",
            currency="NIO",
            amount=Decimal("Infinity"),
            estimated_date=date(2026, 12, 15),
        ),
        CashForecastEntry(
            type="Income",
            currency="NIO",
            amount=Decimal("25"),
            estimated_date=date(2026, 12, 15),
        ),
    ]

    totals = _compute_manual_projections(
        entries,
        date(2026, 12, 1),
        date(2026, 12, 31),
        "Projected",
        date(2026, 12, 15),
        "NIO",
    )

    assert totals == (Decimal("25"), Decimal("0"), [])


def test_manual_projection_reports_missing_exchange_rate_without_losing_entry(monkeypatch):
    """A projection without FX remains visible as incomplete and is excluded from converted totals."""
    from cacao_accounting.bancos import cash_forecast_service

    missing_rate_entry = CashForecastEntry(
        id="missing-rate",
        type="Income",
        concept="Venta en USD",
        currency="USD",
        amount=Decimal("50"),
        estimated_date=date(2026, 12, 15),
    )
    valid_entry = CashForecastEntry(
        id="valid",
        type="Expense",
        concept="Pago en NIO",
        currency="NIO",
        amount=Decimal("20"),
        estimated_date=date(2026, 12, 18),
    )

    def convert(amount, currency, _company_currency, _target_date):
        if currency == "USD":
            raise cash_forecast_service.CashForecastConversionError("missing rate")
        return amount

    monkeypatch.setattr(cash_forecast_service, "get_base_amount", convert)
    inflow, outflow, incomplete = _compute_manual_projections(
        [missing_rate_entry, valid_entry],
        date(2026, 12, 1),
        date(2026, 12, 31),
        "Projected",
        date(2026, 11, 30),
        "NIO",
    )

    assert (inflow, outflow) == (Decimal("0"), Decimal("20"))
    assert incomplete == [
        {
            "id": "missing-rate",
            "concept": "Venta en USD",
            "type": "Income",
            "amount": Decimal("50"),
            "currency": "USD",
            "estimated_date": date(2026, 12, 15),
        }
    ]


@pytest.mark.usefixtures("entorno_contable")
def test_cash_forecast_detail_marks_and_lists_projection_without_exchange_rate(app, authenticated_client, monkeypatch):
    """The forecast detail warns that balances are partial and preserves original amount details."""
    from cacao_accounting.bancos import cash_forecast_service

    client = authenticated_client()
    forecast_id = _create_forecast(client)
    with app.app_context():
        forecast = database.session.get(CashForecast, forecast_id)
        entry = CashForecastEntry(
            forecast_id=forecast.id,
            type="Income",
            concept="Venta pendiente USD",
            currency="USD",
            amount=Decimal("75.25"),
            estimated_date=date(2026, 12, 15),
        )
        database.session.add(entry)
        database.session.commit()

    monkeypatch.setattr(cash_forecast_service, "_lookup_exchange_rate", lambda *_args: None)
    response = client.get(f"/cash_management/cash-forecast/{forecast_id}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Matriz incompleta" in page
    assert "no deben interpretarse como completos" in page
    assert "Venta pendiente USD" in page
    assert "75.25" in page
    assert "USD" in page
    assert "15/12/2026" in page
    with app.app_context():
        saved_entry = database.session.execute(
            database.select(CashForecastEntry).filter_by(forecast_id=forecast_id)
        ).scalar_one()
        assert saved_entry.amount == Decimal("75.25")
        assert saved_entry.currency == "USD"
