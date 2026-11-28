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


def _fiscal_year_id(app, name: str, entity: str = "cacao") -> str | None:
    """Devuelve el ID del año fiscal propio de la prueba, acotado por compañía."""
    with app.app_context():
        return database.session.execute(
            database.select(FiscalYear.id).filter_by(name=name, entity=entity)
        ).scalar_one_or_none()


def _cleanup_fiscal_year(app, fiscal_year_id: str) -> None:
    """Delete the test fiscal year and its periods by the captured identity."""
    with app.app_context():
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.fiscal_year_id == fiscal_year_id))
        database.session.execute(database.delete(FiscalYear).where(FiscalYear.id == fiscal_year_id))
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
        identificador = _fiscal_year_id(app, name)
        if identificador:
            _cleanup_fiscal_year(app, identificador)


@pytest.mark.parametrize("end_month", (3, 6))
def test_fiscal_year_form_allows_short_years(app, authenticated_client, entorno_contable, end_month):
    """The CRUD accepts the approved three- and six-month fiscal years."""
    del entorno_contable
    name = f"FY-SHORT-{uuid4().hex[:8]}"
    start = date(2097, 1, 1)
    end = date(2097, end_month, calendar.monthrange(2097, end_month)[1])

    try:
        response = authenticated_client("admin").post(
            "/accounting/fiscal_year/new",
            data={
                "id": name,
                "entidad": "cacao",
                "inicio": start.isoformat(),
                "fin": end.isoformat(),
            },
        )
        assert response.status_code == 302, response.get_data(as_text=True)[-1200:]
        with app.app_context():
            fiscal_year = database.session.execute(database.select(FiscalYear).filter_by(name=name)).scalar_one()
            assert fiscal_year.year_start_date == start
            assert fiscal_year.year_end_date == end
    finally:
        identificador = _fiscal_year_id(app, name)
        if identificador:
            _cleanup_fiscal_year(app, identificador)


def test_setup_persists_three_complete_accounting_periods(entorno_contable_aislado):
    """Company setup creates three monthly periods in an isolated database."""
    application = entorno_contable_aislado.app
    with application.app_context():
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


def test_setup_convive_con_un_anio_homonimo_de_otra_compania(entorno_contable_aislado):
    """Un año 2098 de otra compañía no se reutiliza ni se modifica."""
    application = entorno_contable_aislado.app
    with application.app_context():
        sufijo = uuid4().hex[:6]
        otra = Entity(
            code="OTRA",
            company_name=f"Compañía ajena {sufijo}",
            tax_id=f"TAX-{sufijo}",
            currency="NIO",
            enabled=True,
            status="activo",
        )
        database.session.add(otra)
        database.session.flush()
        ajeno = FiscalYear(
            entity="OTRA",
            name="2098",
            year_start_date=date(2098, 1, 1),
            year_end_date=date(2098, 12, 31),
            is_closed=False,
        )
        database.session.add(ajeno)
        database.session.flush()
        periodo_ajeno = AccountingPeriod(
            entity="OTRA",
            fiscal_year_id=ajeno.id,
            name="2098-01",
            start=date(2098, 1, 1),
            end=date(2098, 1, 31),
        )
        database.session.add(periodo_ajeno)
        database.session.commit()
        ajeno_id = ajeno.id
        periodo_ajeno_id = periodo_ajeno.id

        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        propio = create_default_fiscal_year(
            entity,
            year_start_date=date(2098, 1, 1),
            year_end_date=date(2098, 3, 31),
        )
        create_default_accounting_period(entity, propio)
        database.session.commit()

        assert propio.id != ajeno_id
        assert propio.entity == "cacao"
        propios = (
            database.session.execute(database.select(AccountingPeriod.id).filter_by(fiscal_year_id=propio.id)).scalars().all()
        )
        assert len(propios) == 3
        assert periodo_ajeno_id not in propios

        year_ajeno = database.session.get(FiscalYear, ajeno_id)
        assert year_ajeno is not None and year_ajeno.year_end_date == date(2098, 12, 31)
        assert database.session.get(AccountingPeriod, periodo_ajeno_id) is not None


def test_cleanup_por_identidad_no_borra_un_anio_homonimo(entorno_contable_aislado):
    """El cleanup de la prueba elimina solo el año que creó, aunque comparta nombre."""
    application = entorno_contable_aislado.app
    with application.app_context():
        sufijo = uuid4().hex[:6]
        database.session.add(
            Entity(
                code="OTRA",
                company_name=f"Compañía ajena {sufijo}",
                tax_id=f"TAX-{sufijo}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        ajeno = FiscalYear(
            entity="OTRA",
            name="2098",
            year_start_date=date(2098, 1, 1),
            year_end_date=date(2098, 12, 31),
            is_closed=False,
        )
        database.session.add(ajeno)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity="OTRA",
                fiscal_year_id=ajeno.id,
                name="2098-01",
                start=date(2098, 1, 1),
                end=date(2098, 1, 31),
            )
        )
        entity = database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one()
        propio = create_default_fiscal_year(
            entity,
            year_start_date=date(2098, 1, 1),
            year_end_date=date(2098, 3, 31),
        )
        create_default_accounting_period(entity, propio)
        database.session.commit()
        ajeno_id = ajeno.id
        propio_id = propio.id

    _cleanup_fiscal_year(application, propio_id)

    with application.app_context():
        assert database.session.get(FiscalYear, propio_id) is None
        assert (
            database.session.execute(database.select(AccountingPeriod).filter_by(fiscal_year_id=propio_id)).scalars().all()
            == []
        )
        assert database.session.get(FiscalYear, ajeno_id) is not None
        assert (
            database.session.execute(database.select(AccountingPeriod).filter_by(fiscal_year_id=ajeno_id)).scalar_one_or_none()
            is not None
        )
