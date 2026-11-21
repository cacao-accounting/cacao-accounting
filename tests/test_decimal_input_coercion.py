# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contrato compartido de coerción decimal en fronteras de entrada."""

from decimal import Decimal

import pytest

from cacao_accounting.numbers import coerce_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.2300", Decimal("1.2300")),
        (Decimal("-1.25"), Decimal("-1.25")),
        (123, Decimal("123")),
        ("1e2", Decimal("1E+2")),
    ],
)
def test_coerce_decimal_preserves_finite_values_and_default_sign(value, expected):
    """La coerción exacta no redondea ni impone una política global de signo."""
    assert coerce_decimal(value, "importe") == expected


@pytest.mark.parametrize("value", ["abc", None, object()])
def test_coerce_decimal_rejects_values_that_cannot_be_parsed(value):
    """Entradas no numéricas se convierten a errores de validación controlados."""
    with pytest.raises(ValueError, match="número válido"):
        coerce_decimal(value, "importe")


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_coerce_decimal_rejects_non_finite_values(value):
    """Los decimales no finitos se rechazan antes de comparaciones aritméticas."""
    with pytest.raises(ValueError, match="número finito"):
        coerce_decimal(value, "importe")


@pytest.mark.parametrize("value", ["0", "-0.01"])
def test_coerce_decimal_enforces_strictly_positive_fields(value):
    """Los campos que declaran positividad rechazan cero y negativos."""
    with pytest.raises(ValueError, match="mayor que cero"):
        coerce_decimal(value, "cantidad", positive=True)


def test_coerce_decimal_allows_zero_but_rejects_negative_non_negative_fields():
    """Los campos no negativos conservan cero sin admitir signos negativos."""
    assert coerce_decimal("0", "tolerancia", non_negative=True) == Decimal("0")
    with pytest.raises(ValueError, match="no puede ser negativo"):
        coerce_decimal("-0.01", "tolerancia", non_negative=True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1.2345", Decimal("1.2345")), ("1.23000", Decimal("1.23000")), ("1E+3", Decimal("1E+3"))],
)
def test_coerce_decimal_accepts_values_representable_at_scale(value, expected):
    """La escala elimina ceros no significativos y acepta enteros exactos."""
    assert coerce_decimal(value, "monto", max_fractional_digits=4) == expected


def test_coerce_decimal_rejects_significant_digits_beyond_storage_scale():
    """La entrada no se redondea silenciosamente a la escala de persistencia."""
    with pytest.raises(ValueError, match="máximo 4 decimales"):
        coerce_decimal("1.23456", "monto", max_fractional_digits=4)


def test_coerce_decimal_rejects_conflicting_or_invalid_constraints():
    """La configuración accidental de restricciones falla antes de coercionar."""
    with pytest.raises(ValueError, match="both be enabled"):
        coerce_decimal("1", "importe", positive=True, non_negative=True)
    with pytest.raises(ValueError, match="must be non-negative"):
        coerce_decimal("1", "importe", max_fractional_digits=-1)
