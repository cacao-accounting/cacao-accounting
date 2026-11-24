# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1964: el catálogo anunciado como inglés no filtra nombres en español.

`base_en.csv` se importa directamente a `Accounts.name`, así que sus nombres
son datos visibles y no pasan por gettext. La regresión exige que conserve la
estructura del catálogo base y que sus nombres sean ingleses, salvo nombres
propios o términos internacionales idénticos en ambos idiomas.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

CATALOGOS = Path(__file__).resolve().parents[1] / "cacao_accounting" / "contabilidad" / "ctas" / "catalogos"
IDENTICOS_PERMITIDOS = {"INATEC", "Internet"}
PALABRAS_ESPANOLAS = re.compile(
    r"\b(de|del|y|por|para|en|las|los|cuentas|otros|otras|gastos|ingresos|"
    r"proveedores|clientes|activos|pasivos|efectivo|anticipos|impuestos|pagos|cobros|"
    r"estimación|estimacion|incobrables|deterioro)\b",
    re.IGNORECASE,
)
ACENTOS_ESPANOLES = re.compile(r"[áéíóúüñ]", re.IGNORECASE)


def _catalogo(nombre: str) -> dict[str, dict[str, str]]:
    """Carga un catálogo indexado por código contable."""
    with (CATALOGOS / nombre).open(encoding="utf-8", newline="") as archivo:
        return {fila["codigo"]: fila for fila in csv.DictReader(archivo)}


def test_base_en_conserva_la_estructura_de_base_es():
    """Códigos, jerarquía y clasificación coinciden con el catálogo español."""
    ingles = _catalogo("base_en.csv")
    espanol = _catalogo("base_es.csv")

    assert len(ingles) == 217
    assert set(ingles) == set(espanol)
    for codigo, fila in ingles.items():
        referencia = espanol[codigo]
        for campo in ("padre", "grupo", "rubro", "tipo", "account_type"):
            assert fila[campo] == referencia[campo], f"{codigo}: {campo} difiere del catálogo base"


def test_base_en_no_reutiliza_nombres_en_espanol():
    """Ningún nombre queda en español salvo los términos internacionales."""
    ingles = _catalogo("base_en.csv")
    espanol = _catalogo("base_es.csv")

    identicos = {codigo for codigo, fila in ingles.items() if fila["nombre"] == espanol[codigo]["nombre"]}
    assert identicos <= {codigo for codigo, fila in ingles.items() if fila["nombre"] in IDENTICOS_PERMITIDOS}

    con_espanol = {codigo: fila["nombre"] for codigo, fila in ingles.items() if PALABRAS_ESPANOLAS.search(fila["nombre"])}
    assert con_espanol == {}

    con_acentos = {codigo: fila["nombre"] for codigo, fila in ingles.items() if ACENTOS_ESPANOLES.search(fila["nombre"])}
    assert con_acentos == {}, "El catálogo inglés conserva palabras acentuadas en español"
