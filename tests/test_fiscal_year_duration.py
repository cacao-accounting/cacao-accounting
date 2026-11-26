# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1954: los años fiscales aceptan hasta doce períodos, también años cortos."""

from __future__ import annotations

import calendar
from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import Entity, FiscalYear, database
from cacao_accounting.setup.repository import _generate_fiscal_period_ranges, create_default_fiscal_year


def test_generates_six_complete_months_for_short_fiscal_year():
    """A shorter company fiscal year produces only its six full periods."""
    start = date(2026, 1, 1)
    end = date(2026, 6, 30)

    ranges = _generate_fiscal_period_ranges(start, end)

    assert ranges == [(date(2026, month, 1), date(2026, month, calendar.monthrange(2026, month)[1])) for month in range(1, 7)]


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


def test_fiscal_year_form_allows_a_six_month_year(app, authenticated_client, entorno_contable):
    """The CRUD preserves the approved option to use a shorter fiscal year."""
    del entorno_contable
    name = f"FY-SHORT-{uuid4().hex[:8]}"

    response = authenticated_client("admin").post(
        "/accounting/fiscal_year/new",
        data={
            "id": name,
            "entidad": "cacao",
            "inicio": "2026-01-01",
            "fin": "2026-06-30",
        },
    )

    try:
        assert response.status_code == 302
        with app.app_context():
            fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(name=name)).scalar_one()
            assert fiscal_year.year_start_date == date(2026, 1, 1)
            assert fiscal_year.year_end_date == date(2026, 6, 30)
    finally:
        with app.app_context():
            database.session.execute(database.delete(FiscalYear).where(FiscalYear.name == name))
            database.session.commit()
