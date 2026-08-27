# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Períodos contables completos como fuente de verdad para filtros transaccionales y contables.

Todo documento o reporte debe acotarse a un rango contiguo de períodos
contables completos (e.g. ``01-2026`` a ``03-2026``). ``AccountingPeriod`` es
la única fuente de verdad para las fechas de inicio y fin: el backend resuelve
``period_start`` y ``period_end`` desde los registros del período (incluyendo
períodos de ajuste que no coincidan con meses calendario) y rechaza rangos
manuales que no correspondan exactamente al período seleccionado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from flask import abort
from sqlalchemy import select

from cacao_accounting.database import AccountingPeriod, database

try:  # pragma: no cover - fallback defensivo para contextos sin Flask-Babel inicializado.
    from flask_babel import gettext as _babel_gettext
except ImportError:  # pragma: no cover

    def _(value: str) -> str:
        return value

else:

    def _(value: str) -> str:
        try:
            return _babel_gettext(value)
        except (KeyError, RuntimeError):
            return value


_DATE_OVERRIDE_PARAMS = ("date_from", "date_to", "as_of_date")

_INVALID_PERIOD_MESSAGE = _("Período contable inválido o perteneciente a otra compañía.")
_INVERTED_RANGE_MESSAGE = _("El período inicial no puede ser posterior al período final.")
_PARTIAL_RANGE_MESSAGE = _("No se permiten rangos parciales: use períodos contables completos.")


@dataclass(frozen=True)
class PeriodRange:
    """Rango contiguo de períodos contables completos acotado por sus extremos.

    ``period_start`` es el primer día del período inicial y ``period_end`` el
    último día del período final; ambos límites se aplican de forma inclusiva.
    """

    from_id: str
    to_id: str
    from_name: str
    to_name: str
    period_start: date
    period_end: date
    from_period: AccountingPeriod
    to_period: AccountingPeriod

    @property
    def single_period(self) -> bool:
        """Verdadero cuando el rango abarca exactamente un período."""
        return self.from_id == self.to_id

    @property
    def label(self) -> str:
        """Etiqueta de presentación del rango (e.g. ``01-2026 – 03-2026``)."""
        if self.single_period:
            return self.from_name
        return f"{self.from_name} – {self.to_name}"


def list_periods_for_company(company: str) -> list[AccountingPeriod]:
    """Devuelve los períodos de la compañía en orden cronológico de inicio."""
    return list(
        database.session.execute(
            select(AccountingPeriod)
            .where(AccountingPeriod.entity == company)
            .order_by(AccountingPeriod.start.asc(), AccountingPeriod.end.asc())
        ).scalars()
    )


def current_period_for_company(company: str, target_date: date | None = None) -> AccountingPeriod | None:
    """Devuelve el período habilitado que contiene la fecha objetivo o el más reciente."""
    effective_date = target_date or date.today()
    period = (
        database.session.execute(
            select(AccountingPeriod)
            .where(
                AccountingPeriod.entity == company,
                AccountingPeriod.enabled.is_(True),
                AccountingPeriod.start <= effective_date,
                AccountingPeriod.end >= effective_date,
            )
            .order_by(AccountingPeriod.start.desc())
        )
        .scalars()
        .first()
    )
    if period is not None:
        return period
    return (
        database.session.execute(
            select(AccountingPeriod)
            .where(AccountingPeriod.entity == company, AccountingPeriod.enabled.is_(True))
            .order_by(AccountingPeriod.start.desc())
        )
        .scalars()
        .first()
    )


def resolve_period(company: str, period_id: str) -> AccountingPeriod | None:
    """Resuelve un período validando que el identificador pertenezca a la compañía."""
    normalized = period_id.strip()
    if not normalized:
        return None
    period = database.session.execute(select(AccountingPeriod).where(AccountingPeriod.id == normalized)).scalar_one_or_none()
    if period is None or period.entity != company:
        return None
    return period


def resolve_period_range(
    company: str,
    period_from: str | None,
    period_to: str | None,
    *,
    default_to_current: bool = True,
    target_date: date | None = None,
) -> PeriodRange | None:
    """Resuelve un rango contiguo de períodos validado contra la compañía.

    - Sin identificadores y con ``default_to_current`` se devuelve el rango de
      un solo período para el período actual de la compañía (la fecha objetivo
      se usa solo para elegir el período actual en pruebas).
    - Con un solo extremo el rango se reduce a ese único período.
    - Valida que ambos extremos pertenezcan a la compañía y rechaza rangos
      invertidos (inicio posterior al final).
    """
    from_id = (period_from or "").strip()
    to_id = (period_to or "").strip()
    if not from_id and not to_id:
        if not default_to_current:
            return None
        current = current_period_for_company(company, target_date=target_date)
        if current is None:
            return None
        from_id = str(current.id)
        to_id = from_id
    elif from_id and not to_id:
        to_id = from_id
    elif not from_id and to_id:
        from_id = to_id

    from_period = resolve_period(company, from_id)
    to_period = resolve_period(company, to_id)
    if from_period is None or to_period is None:
        abort(400, description=_INVALID_PERIOD_MESSAGE)
    if from_period.start > to_period.start:
        abort(400, description=_INVERTED_RANGE_MESSAGE)
    return PeriodRange(
        from_id=str(from_period.id),
        to_id=str(to_period.id),
        from_name=from_period.name,
        to_name=to_period.name,
        period_start=from_period.start,
        period_end=to_period.end,
        from_period=from_period,
        to_period=to_period,
    )


def reject_manual_date_overrides(overrides: Mapping[str, Any], period_range: PeriodRange) -> None:
    """Rechaza rangos manuales que no correspondan exactamente al período seleccionado.

    El navegador no calcula fechas: cuando se filtra por períodos contables
    completos, cualquier ``date_from``, ``date_to`` o ``as_of_date`` enviado
    debe coincidir con los límites resueltos desde ``AccountingPeriod``.
    """
    for param in _DATE_OVERRIDE_PARAMS:
        raw = overrides.get(param)
        if not raw:
            continue
        provided = _safe_date(raw)
        if provided is None:
            continue
        if param == "date_from":
            expected = period_range.period_start
        else:
            expected = period_range.period_end
        if provided != expected:
            abort(400, description=_PARTIAL_RANGE_MESSAGE)


def _safe_date(value: object) -> date | None:
    """Convierte un valor a fecha solo si tiene formato ISO válido."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None
