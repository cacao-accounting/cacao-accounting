# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2203/#2204: las macros de formulario deben tener consumidores reales.

`transaction_form_js` solo asignaba `globalThis.transactionFormConfig` y no se
invocaba. El resto de macros sí se usa en formularios de compras, ventas,
inventario y caja chica; esta prueba evita reintroducir macros muertas.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"
MACROS = RAIZ / "templates" / "transaction_form_macros.html"
PATRON_MACRO = re.compile(r"{%\s*macro\s+([a-zA-Z_][a-zA-Z0-9_]*)")
PATRON_CONSUMIDOR = re.compile(r"(?:tf_macros|macros)\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")


def _macros_definidas() -> set[str]:
    """Devuelve los nombres de macro definidos en el archivo compartido."""
    return set(PATRON_MACRO.findall(MACROS.read_text(encoding="utf-8")))


def _macros_consumidas() -> set[str]:
    """Devuelve los nombres de macro invocados desde el resto de plantillas."""
    consumidas: set[str] = set()
    for plantilla in RAIZ.rglob("*.html"):
        if plantilla == MACROS:
            continue
        consumidas.update(PATRON_CONSUMIDOR.findall(plantilla.read_text(encoding="utf-8", errors="ignore")))
    return consumidas


def test_toda_macro_compartida_tiene_consumidor():
    """Una macro nueva sin invocaciones rompe la suite en lugar de quedar muerta."""
    definidas = _macros_definidas()

    assert "transaction_form_header" in definidas
    assert "transaction_grid" in definidas
    assert "logistics_section" in definidas
    assert "smart_select" in definidas
    assert definidas - _macros_consumidas() == set()


def test_transaction_form_js_y_su_config_global_estan_retirados():
    """La macro superseded no vuelve a introducir `transactionFormConfig`."""
    fuente = MACROS.read_text(encoding="utf-8")

    assert "transaction_form_js" not in fuente
    assert "transactionFormConfig" not in fuente
    for plantilla in RAIZ.rglob("*"):
        if not plantilla.is_file() or plantilla.suffix not in {".html", ".py", ".js"}:
            continue
        if "node_modules" in plantilla.parts or "build" in plantilla.parts:
            continue
        assert "transactionFormConfig" not in plantilla.read_text(encoding="utf-8", errors="ignore")
