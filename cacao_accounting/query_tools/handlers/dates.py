# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación compartida de fechas ISO en los query tools (#1969)."""

from __future__ import annotations

from datetime import date

from cacao_accounting.i18n import _l
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError

INVALID_DATE_MESSAGE = _l("La fecha debe usar el formato ISO 8601 (AAAA-MM-DD).")


def parse_iso_date(value: str | None, *, required: bool = False) -> date | None:
    """Convierte una fecha ISO del schema o falla como error de parámetro."""
    if not value:
        if required:
            raise QueryToolError(code=ErrorCode.INVALID_PARAMETER, message=INVALID_DATE_MESSAGE)
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise QueryToolError(code=ErrorCode.INVALID_PARAMETER, message=INVALID_DATE_MESSAGE) from None
