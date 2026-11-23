# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2019: la escala del Decimal no altera el payload firmado."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting.printing.validation import _json_value


@pytest.mark.parametrize(
    ("escala_corta", "escala_larga"),
    [
        ("125.50", "125.5000"),
        ("0.10", "0.100000"),
        ("1000", "1000.00"),
        ("7.1234", "7.12340000"),
    ],
)
def test_la_misma_cantidad_produce_el_mismo_texto(escala_corta: str, escala_larga: str):
    """Releer de Numeric(20,4) no cambia el valor canónico."""
    assert _json_value(Decimal(escala_corta)) == _json_value(Decimal(escala_larga))


@pytest.mark.parametrize("cero", ["0", "0.0", "0.0000", "-0.00"])
def test_cero_tiene_una_sola_forma(cero: str):
    """Todas las representaciones de cero colapsan al mismo token."""
    assert _json_value(Decimal(cero)) == "0"
