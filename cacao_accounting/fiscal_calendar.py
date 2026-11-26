# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Shared calendar rules for fiscal-year ranges and accounting periods."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from cacao_accounting.i18n import _

MAX_FISCAL_YEAR_PERIODS = 12


def add_months(original_date: date, months: int) -> date:
    """Return a date shifted by calendar months, clamping to the target month's last day."""
    month_offset = original_date.month - 1 + months
    year = original_date.year + month_offset // 12
    month = month_offset % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(original_date.day, last_day))


def max_fiscal_year_end(start: date) -> date:
    """Return the last day before the twelve-month anniversary of the start date."""
    return add_months(start, MAX_FISCAL_YEAR_PERIODS) - timedelta(days=1)


def validate_fiscal_year_range(start: date, end: date) -> None:
    """Reject reversed ranges and fiscal years that would require more than twelve periods."""
    if start > end:
        raise ValueError(_("La fecha de inicio del año fiscal debe ser anterior a la fecha de fin."))
    if end > max_fiscal_year_end(start):
        raise ValueError(_("El año fiscal no puede superar 12 meses."))
