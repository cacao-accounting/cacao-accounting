# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Coerción y validación de números decimales en fronteras de entrada."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from cacao_accounting.i18n import _


def coerce_decimal(
    value: Any,
    field_name: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
    max_fractional_digits: int | None = None,
) -> Decimal:
    """Convierte una entrada a ``Decimal`` y aplica restricciones declaradas por campo.

    No se impone signo si el caller no lo solicita: descuentos, reversas y
    ajustes pueden tener convenciones distintas según su flujo contable.
    """
    if positive and non_negative:
        raise ValueError("positive and non_negative cannot both be enabled")
    if max_fractional_digits is not None and max_fractional_digits < 0:
        raise ValueError("max_fractional_digits must be non-negative")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(_("El campo %(field)s debe ser un número válido.") % {"field": field_name}) from exc
    if not number.is_finite():
        raise ValueError(_("El campo %(field)s debe ser un número finito.") % {"field": field_name})
    if positive and number <= 0:
        raise ValueError(_("El campo %(field)s debe ser mayor que cero.") % {"field": field_name})
    if non_negative and number < 0:
        raise ValueError(_("El campo %(field)s no puede ser negativo.") % {"field": field_name})
    if max_fractional_digits is not None and _fractional_digits(number) > max_fractional_digits:
        raise ValueError(
            _("El campo %(field)s admite como máximo %(digits)s decimales.")
            % {"field": field_name, "digits": max_fractional_digits}
        )
    return number


def coerce_boolean(value: Any, field_name: str) -> bool:
    """Convierte un booleano o su representación textual aceptada.

    Acepta ``True``/``False`` nativos y las formas textuales inequívocas
    (``true``/``false``, ``1``/``0``, ``yes``/``no``, ``si``/``sí``,
    ``on``/``off``). Un valor desconocido es un error de validación en vez
    de asumirse verdadero.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "si", "sí", "on"}:
        return True
    if normalized in {"false", "0", "no", "off", ""}:
        return False
    raise ValueError(_("El campo %(field)s debe ser un valor booleano válido.") % {"field": field_name})


def _fractional_digits(number: Decimal) -> int:
    """Cuenta los decimales significativos sin redondear ni alterar el valor."""
    digits = number.as_tuple().digits
    exponent = number.as_tuple().exponent
    if not isinstance(exponent, int) or exponent >= 0:
        return 0
    trailing_zeros = 0
    for digit in reversed(digits):
        if digit != 0:
            break
        trailing_zeros += 1
    return max(0, -exponent - trailing_zeros)
