# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1887: los selectores de cuentas resuelven la compañía actual de la fila.

Una cadena escalar en ``filters`` queda congelada al crear el componente; el
selector de cuentas debe usar una función, igual que el de centro de costo, para
seguir la compañía que el usuario elige en la fila.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "cacao_accounting"
    / "inventario"
    / "templates"
    / "inventario"
    / "articulo_nuevo.html"
)
FILTRO_ACTUAL = "company: function () { return row.company; }"


def test_los_selectores_de_cuentas_usan_la_compania_actual():
    """Ningún selector de cuenta conserva el snapshot escalar de company."""
    texto = TEMPLATE.read_text(encoding="utf-8")

    assert "company: row.company" not in texto
    bloques = re.findall(r'doctype: "account",.*?requiredFilters', texto, re.DOTALL)
    assert len(bloques) == 4
    for bloque in bloques:
        assert FILTRO_ACTUAL in bloque


def test_el_selector_de_centro_de_costo_mantiene_el_mismo_contrato():
    """El control ya correcto sigue resolviendo la compañía de la fila."""
    texto = TEMPLATE.read_text(encoding="utf-8")

    assert FILTRO_ACTUAL in texto
    assert texto.count(FILTRO_ACTUAL) == 5
