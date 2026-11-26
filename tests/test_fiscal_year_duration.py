# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1954: los años fiscales aceptan hasta doce períodos, también años cortos."""

from __future__ import annotations

import calendar
from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import AccountingPeriod, Entity, FiscalYear, database
from cacao_accounting.setup.repository import (
    _generate_fiscal_period_ranges,
    create_default_accounting_period,
    create_default_fiscal_year,
)


def _cleanup_fiscal_year(app, name: str) -> None:
    """Delete a test fiscal year and its periods, including rows left by a failing assertion."""
    with app.app_context():
        fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(name=name)).scalar_one_or_none()
        if fiscal_year is None:
            return
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == fiscal_year.id))
        database.session.delete(fiscal_year)
        database.session.commit()


@pytest.mark.parametrize("end_month", (3, 6))
def test_generates_complete_months_for_short_fiscal_year(end_month):
    """Three- and six-month fiscal years produce only their complete periods."""
    start = date(2026, 1, 1)
    end = date(2026, end_month, calendar.monthrange(2026, end_month)[1])

    ranges = _generate_fiscal_period_ranges(start, end)

    expected_ranges = [
        (date(2026, month, 1), date(2026, month, calendar.monthrange(2026, month)[1])) for month in range(1, end_month + 1)
    ]
    assert ranges == expected_ranges


def test_accepts_twelve_periods_without_extending_the_final_period():
    """The twelfth period ends at its normal boundary rather than absorbing extra dates."""
    ranges = _generate_fiscal_period_ranges(date(2025, 1, 31), date(2026, 1, 30))

    assert len(ranges) == 12
    assert ranges[-1] == (date(2025, 12, 31), date(2026, 1, 30))


def test_rejects_range_that_would_create_a_thirteenth_period():
    """A range beyond its twelve-month anniversary is invalid."""
    with pytest.raises(ValueError, match="12 meses"):
        _generate_fiscal_period_ranges(date(2025, 1, 31), date(2026, 1, 31))


def test_setup_does_not_persist_an_overlong_fiscal_year(app, entorno_contable):
    """Company setup rejects a long range before inserting its FiscalYear."""
    del entorno_contable
    with app.app_context():
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        with pytest.raises(ValueError, match="12 meses"):
            create_default_fiscal_year(
                entity,
                year_start_date=date(2025, 1, 1),
                year_end_date=date(2026, 6, 30),
            )

        assert (
            database.session.execute(
                database.select(FiscalYear).filter_by(
                    entity="cacao",
                    year_start_date=date(2025, 1, 1),
                    year_end_date=date(2026, 6, 30),
                )
            )
            .scalars()
            .all()
            == []
        )


def test_fiscal_year_form_rejects_overlong_range_without_persistence(app, authenticated_client, entorno_contable):
    """The accounting CRUD reports the rule and does not save an overlong range."""
    del entorno_contable
    name = f"FY-OVERLONG-{uuid4().hex[:8]}"

    try:
        response = authenticated_client("admin").post(
            "/accounting/fiscal_year/new",
            data={
                "id": name,
                "entidad": "cacao",
                "inicio": "2025-01-01",
                "fin": "2026-06-30",
            },
        )

        assert response.status_code == 200
        assert "12 meses" in response.get_data(as_text=True)
        with app.app_context():
            assert database.session.execute(database.select(FiscalYear).filter_by(name=name)).scalars().all() == []
    finally:
        _cleanup_fiscal_year(app, name)


@pytest.mark.parametrize("end_month", (3, 6))
def test_fiscal_year_form_allows_short_years(app, authenticated_client, entorno_contable, end_month):
    """The CRUD accepts the approved three- and six-month fiscal years."""
    del entorno_contable
    name = f"FY-SHORT-{uuid4().hex[:8]}"
    end = date(2026, end_month, calendar.monthrange(2026, end_month)[1])

    try:
        response = authenticated_client("admin").post(
            "/accounting/fiscal_year/new",
            data={
                "id": name,
                "entidad": "cacao",
                "inicio": "2026-01-01",
                "fin": end.isoformat(),
            },
        )
        assert response.status_code == 302
        with app.app_context():
            fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(name=name)).scalar_one()
            assert fiscal_year.year_start_date == date(2026, 1, 1)
            assert fiscal_year.year_end_date == end
    finally:
        _cleanup_fiscal_year(app, name)


def test_setup_persists_three_complete_accounting_periods(app, entorno_contable):
    """Company setup creates three monthly periods for an approved short fiscal year."""
    del entorno_contable
    fiscal_year_name = "2098"
    try:
        with app.app_context():
            entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
            fiscal_year = create_default_fiscal_year(
                entity,
                year_start_date=date(2098, 1, 1),
                year_end_date=date(2098, 3, 31),
            )
            create_default_accounting_period(entity, fiscal_year)
            periods = database.session.execute(
                database.select(AccountingPeriod.start, AccountingPeriod.end)
                .filter_by(fiscal_year_id=fiscal_year.id)
                .order_by(AccountingPeriod.start)
            ).all()
            assert periods == [
                (date(2098, 1, 1), date(2098, 1, 31)),
                (date(2098, 2, 1), date(2098, 2, 28)),
                (date(2098, 3, 1), date(2098, 3, 31)),
            ]
            database.session.commit()
    finally:
        _cleanup_fiscal_year(app, fiscal_year_name)
