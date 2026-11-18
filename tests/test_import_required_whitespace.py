# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1052: los campos requeridos solo con espacios cuentan como faltantes.

Las celdas XLSX/ODS pueden contener espacios; el adaptador debe rechazar la
fila antes de persistir una cuenta sin código, nombre ni clasificación útiles.
"""

from __future__ import annotations

from cacao_accounting.imports.adapters.chart_of_accounts import ChartOfAccountsAdapter


def test_whitespace_only_required_fields_are_rejected():
    """Spaces in every required column produce the missing-column errors."""
    adapter = ChartOfAccountsAdapter()

    errors = adapter.validate_row({"codigo": " ", "nombre": "   ", "clasificacion": "\t"})

    assert any("codigo" in error for error in errors)
    assert any("nombre" in error for error in errors)
    assert any("clasificacion" in error for error in errors)


def test_mixed_missing_and_whitespace_fields_are_rejected():
    """None, empty and whitespace values share the same validation."""
    adapter = ChartOfAccountsAdapter()

    errors = adapter.validate_row({"codigo": None, "nombre": "", "clasificacion": "  "})

    assert len(errors) == 3


def test_valid_required_fields_still_pass():
    """A fully populated row has no missing-column errors."""
    adapter = ChartOfAccountsAdapter()

    assert adapter.validate_row({"codigo": "1101", "nombre": "Caja", "clasificacion": "activo"}) == []
