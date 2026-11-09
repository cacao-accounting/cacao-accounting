# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El catálogo base_en usa nombres coherentes en inglés.

Escenario de negocio (issue #1964): base_en.csv se anunciaba como inglés pero
conservaba nombres en español e híbridos, que luego se copiaban a Accounts.name.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

CATALOG_DIR = Path("cacao_accounting/contabilidad/ctas/catalogos")
SPANISH_MARKERS = re.compile(
    r"\b(de|del|la|las|los|el|y|por|para|en|con|sin|Impuesto|Cuentas|Gastos|Ingresos|"
    r"Activos?|Pasivos?|Precio|Banco|Caja|Saldo|Pago|Cobro|Venta|Compra|Recargo)\b",
    re.IGNORECASE,
)


def _rows(name: str) -> list[list[str]]:
    with (CATALOG_DIR / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh))


def test_base_en_no_conserva_nombres_espanoles_ni_hibridos():
    """#1964: ningún nombre del catálogo inglés contiene marcadores españoles."""
    rows = _rows("base_en.csv")
    assert len(rows) == 218
    pendientes = [(row[0], row[1]) for row in rows[1:] if SPANISH_MARKERS.search(row[1])]
    assert pendientes == []


def test_base_en_conserva_estructura_del_catalogo():
    """#1964: códigos, jerarquía y clasificación no cambian al traducir."""
    en = _rows("base_en.csv")
    es = _rows("base_es.csv")
    assert len(en) == len(es)
    for english, spanish in zip(en[1:], es[1:]):
        assert english[0] == spanish[0]
        assert english[2:] == spanish[2:]


def test_base_en_tiene_las_traducciones_esperadas():
    """#1964: los términos clave quedan en inglés contable."""
    rows = {row[0]: row[1] for row in _rows("base_en.csv")[1:]}
    assert rows["1"] == "Assets"
    assert rows["11.01.001"] == "Cash"
    assert rows["12.01"] == "Property, Plant and Equipment"
    assert rows["12.01.003"] == "Plant, Installations and Industrial Machinery"
    assert rows["21.02.003"] == "Customer Deposits"
    assert rows["22.01"] == "Long-term Loans Payable"
    assert rows["52.03.002"] == "Fines, Late Fees and Value Maintenance"
    assert rows["52.04.005"] == "Other Financial Expenses"


def test_base_en_json_apunta_a_cuentas_existentes():
    """#1964: los mapeos predeterminados siguen resolviendo al catálogo."""
    codes = {row[0] for row in _rows("base_en.csv")[1:]}
    mapping = json.loads((CATALOG_DIR / "base_en.json").read_text(encoding="utf-8"))
    assert mapping["catalog"] == "base_en.csv"
    for key, code in mapping["default_accounts"].items():
        if code:
            assert code in codes, f"{key} apunta a {code}, ausente del catálogo"
