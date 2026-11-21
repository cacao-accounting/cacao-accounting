# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2090: el importe de caja chica admite los decimales de su moneda."""

from __future__ import annotations

from pathlib import Path

PLANTILLA = (
    Path(__file__).resolve().parents[1]
    / "cacao_accounting"
    / "bancos"
    / "templates"
    / "bancos"
    / "caja_chica_gasto_nuevo.html"
)


def test_importe_no_impone_dos_decimales():
    """`step=any` evita que el navegador rechace 1.001 en monedas de 3 decimales."""
    fuente = PLANTILLA.read_text(encoding="utf-8")

    assert 'name="amount"' in fuente
    assert 'step="any"' in fuente
    assert 'step="0.01"' not in fuente
