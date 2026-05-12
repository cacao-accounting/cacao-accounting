# Copyright 2026
# Licensed under the Apache License, Version 2.0

"""Repositorios de datos para el asistente de configuración inicial."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
import calendar

from cacao_accounting.database import (
    AccountingPeriod,
    Book,
    CacaoConfig,
    CostCenter,
    Entity,
    FiscalYear,
    database,
)

try:
    from flask_babel import gettext as _
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        return value


def get_setup_value(key: str, default: Any = None) -> Any:
    """Recupera un valor de configuración por clave."""
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).first()
    if record:
        return record[0].value
    return default


def set_setup_value(key: str, value: str) -> None:
    """Establece o crea un valor de configuración."""
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).first()
    if record:
        config = record[0]
        config.value = value
    else:
        config = CacaoConfig(key=key, value=value)
        database.session.add(config)


def create_default_entity(data: dict, status: str = "default", default: bool = True) -> Entity:
    """Crea y añade una entidad en la sesión de base de datos."""
    if not data.get("id") or not data.get("razon_social") or not data.get("id_fiscal"):
        raise ValueError("Los datos de la entidad son incompletos.")

    existing_entity = database.session.execute(database.select(Entity).filter_by(code=data["id"])).scalar_one_or_none()
    if existing_entity is not None:
        raise ValueError(f"La entidad con código '{data['id']}' ya existe.")

    entity = Entity(
        code=data.get("id"),
        company_name=data.get("razon_social"),
        name=data.get("nombre_comercial") or data.get("razon_social"),
        tax_id=data.get("id_fiscal"),
        currency=data.get("moneda"),
        country=data.get("pais"),
        entity_type=data.get("tipo_entidad"),
        e_mail=data.get("correo_electronico"),
        web=data.get("web"),
        phone1=data.get("telefono1"),
        phone2=data.get("telefono2"),
        fax=data.get("fax"),
        status=status,
        enabled=True,
        default=default,
    )
    database.session.add(entity)
    return entity


def create_default_book(entity: Entity) -> "Book":
    from cacao_accounting.database import Book

    existing_book = database.session.execute(
        database.select(Book).filter_by(entity=entity.code, code="FISC")
    ).scalar_one_or_none()
    if existing_book is not None:
        return existing_book

    book = Book(
        code="FISC",
        name="Local",
        entity=entity.code,
        currency=entity.currency,
        is_primary=True,
        default=True,
    )
    database.session.add(book)
    return book


def create_default_cost_center(entity: Entity) -> "CostCenter":
    from cacao_accounting.database import CostCenter

    existing_cost_center = database.session.execute(
        database.select(CostCenter).filter_by(entity=entity.code, code="MAIN")
    ).scalar_one_or_none()
    if existing_cost_center is not None:
        return existing_cost_center

    cost_center = CostCenter(
        entity=entity.code,
        code="MAIN",
        name="Principal",
        active=True,
        enabled=True,
        default=True,
        group=False,
    )
    database.session.add(cost_center)
    return cost_center


def _add_months(original_date: date, months: int) -> date:
    year = original_date.year + (original_date.month - 1 + months) // 12
    month = (original_date.month - 1 + months) % 12 + 1
    day = original_date.day
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _generate_fiscal_period_ranges(start: date, end: date) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError("La fecha de inicio del año fiscal debe ser anterior a la fecha de fin.")

    ranges: list[tuple[date, date]] = []
    current_start = start
    for period_index in range(12):
        next_start = _add_months(current_start, 1)
        period_end = min(next_start - timedelta(days=1), end)
        ranges.append((current_start, period_end))
        if period_end == end:
            break
        current_start = next_start

    if ranges and ranges[-1][1] != end:
        ranges[-1] = (ranges[-1][0], end)

    return ranges


def create_default_fiscal_year(
    entity: Entity,
    year_start_date: "date | None" = None,
    year_end_date: "date | None" = None,
    reference_date: "date | None" = None,
) -> "FiscalYear":
    from datetime import date as _date
    from cacao_accounting.database import FiscalYear

    if year_start_date is not None and year_end_date is not None:
        start = year_start_date
        end = year_end_date
    else:
        today = reference_date or _date.today()
        start = _date(today.year, 1, 1)
        end = _date(today.year, 12, 31)

    existing_year = database.session.execute(
        database.select(FiscalYear).filter_by(entity=entity.code, year_start_date=start, year_end_date=end)
    ).scalar_one_or_none()
    if existing_year is not None:
        return existing_year

    fiscal_year = FiscalYear(
        entity=entity.code,
        name=str(start.year) if start.year == end.year else f"{start.year}-{end.year}",
        year_start_date=start,
        year_end_date=end,
        is_closed=False,
    )
    database.session.add(fiscal_year)
    database.session.flush()
    return fiscal_year


def create_default_accounting_period(entity: Entity, fiscal_year: "FiscalYear") -> "AccountingPeriod":
    existing_period = database.session.execute(
        database.select(AccountingPeriod).filter_by(entity=entity.code, fiscal_year_id=fiscal_year.id)
    ).scalar_one_or_none()
    if existing_period is not None:
        return existing_period

    period_ranges = _generate_fiscal_period_ranges(fiscal_year.year_start_date, fiscal_year.year_end_date)
    for index, (start, end) in enumerate(period_ranges, start=1):
        period_name = f"{start:%Y-%m}"
        period = AccountingPeriod(
            entity=entity.code,
            fiscal_year_id=fiscal_year.id,
            name=period_name,
            status="open",
            enabled=True,
            is_closed=False,
            start=start,
            end=end,
        )
        database.session.add(period)

    database.session.flush()
    first_period = (
        database.session.execute(
            database.select(AccountingPeriod)
            .filter_by(entity=entity.code, fiscal_year_id=fiscal_year.id)
            .order_by(AccountingPeriod.start)
        )
        .scalars()
        .first()
    )
    if first_period is None:
        raise ValueError(_("No se pudo crear el período contable inicial."))
    return first_period


def get_default_entity() -> Entity | None:
    """Recupera la entidad predeterminada si existe."""
    return database.session.execute(database.select(Entity).filter_by(status="default")).scalar_one_or_none()
