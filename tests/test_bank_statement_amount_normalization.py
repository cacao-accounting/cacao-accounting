# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1030: los importes bancarios ambiguos se rechazan, no se reinterpretan.

``1.000`` puede ser mil (convención europea) o uno con tres decimales; leerlo
mal corrompe el extracto por un factor de 1000. La regresión cubre los
formatos inequívocos, los ambiguos y la celda de solo espacios, que debe
tratarse como ausente y no como un decimal vacío.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pytest

from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

conversion = BankStatementAdapter._optional_amount


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1.000,00", Decimal("1000.00")),
        ("1,234.56", Decimal("1234.56")),
        ("1,234,567.89", Decimal("1234567.89")),
        ("1.234.567,89", Decimal("1234567.89")),
        ("1234.56", Decimal("1234.56")),
        ("-1,234.56", Decimal("-1234.56")),
    ],
)
def test_importe_inequivoco_se_interpreta(texto, esperado):
    """Los formatos con agrupación correcta conservan su valor exacto."""
    assert conversion(texto) == esperado


@pytest.mark.parametrize("texto", ["1.000", "1,000", "12,34.56", "1.234,56.78", "1,23.45"])
def test_importe_ambiguo_se_rechaza(texto):
    """Un separador sin agrupación válida no se elimina en silencio."""
    with pytest.raises(InvalidOperation):
        conversion(texto)


@pytest.mark.parametrize("texto", [None, "", "   ", "\t"])
def test_celda_vacia_se_normaliza_a_ausente(texto):
    """Una celda vacía o de solo espacios representa un lado sin importe."""
    assert conversion(texto) is None


def test_importe_cero_se_normaliza_a_ausente():
    """Un cero no registra movimiento bancario en ese lado."""
    assert conversion("0,00") is None
