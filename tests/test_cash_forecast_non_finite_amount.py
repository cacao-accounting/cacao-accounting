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
from cacao_accounting.database import CashForecastEntry, database

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

    assert totals == (Decimal("25"), Decimal("0"))
