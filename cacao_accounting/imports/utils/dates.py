# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Normalización de fechas provenientes de hojas de cálculo.

XLSX/ODS entregan `datetime` y XLS entrega números seriales; los adaptadores
necesitan un `date` antes de validar el período o construir el documento
(#1055).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

_EXCEL_EPOCH = date(1899, 12, 30)


def parse_import_date(value: Any, *, field: str = "fecha") -> date:
    """Convierte fecha, datetime, ISO o serial Excel en `date`.

    Raises:
        ValueError: si el valor no es una fecha utilizable.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        raise ValueError(f"{field} debe ser una fecha válida.")
    if isinstance(value, (int, float, Decimal)):
        serial = Decimal(str(value))
        if not serial.is_finite() or serial <= 0:
            raise ValueError(f"{field} debe ser una fecha válida.")
        try:
            return _EXCEL_EPOCH + timedelta(days=int(serial))
        except (OverflowError, ValueError) as exc:
            raise ValueError(f"{field} debe ser una fecha válida.") from exc
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{field} debe ser una fecha válida.")
        try:
            return date.fromisoformat(text)
        except ValueError:
            try:
                return datetime.fromisoformat(text).date()
            except ValueError as exc:
                raise ValueError(f"{field} debe ser una fecha válida.") from exc
    raise ValueError(f"{field} debe ser una fecha válida.")
