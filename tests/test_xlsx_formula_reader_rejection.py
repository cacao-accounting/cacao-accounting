# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1623: el lector XLSX rechaza fórmulas aunque exista un valor en caché."""

from __future__ import annotations

import shutil
from zipfile import ZipFile

import openpyxl

from cacao_accounting.imports.readers.xlsx_reader import XLSXReader


def _xlsx_con_formula_cacheada(tmp_path):
    ruta = tmp_path / "formula.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["nombre"])
    hoja.append(["=SUM(1,1)"])
    libro.save(ruta)

    temporal = tmp_path / "formula-cache.xlsx"
    with ZipFile(ruta) as origen, ZipFile(temporal, "w") as destino:
        for item in origen.infolist():
            data = origen.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b"<f>SUM(1,1)</f>", b"<f>SUM(1,1)</f><v>999</v>")
            destino.writestr(item, data)
    shutil.move(temporal, ruta)
    return ruta


def test_reader_rechaza_formula_con_cache(tmp_path):
    """#1623: la fórmula no se aplana a su valor en caché."""
    ruta = _xlsx_con_formula_cacheada(tmp_path)
    cacheado = openpyxl.load_workbook(ruta, data_only=True).active["A2"].value
    assert cacheado == 999

    try:
        XLSXReader().read(str(ruta))
    except ValueError as exc:
        assert "fórmulas" in str(exc).lower() or "formulas" in str(exc).lower()
    else:
        raise AssertionError("Se esperaba rechazo de fórmula")


def test_reader_rechaza_array_formula(tmp_path):
    """#1623 QA: rechaza ArrayFormula sin depender de string '='."""
    from openpyxl.worksheet.formula import ArrayFormula

    ruta = tmp_path / "array.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["nombre"])
    ws["A2"] = ArrayFormula(ref="A2", text="1+1")
    wb.save(ruta)

    try:
        XLSXReader().read(str(ruta))
    except ValueError as exc:
        assert "fórmulas" in str(exc).lower() or "formulas" in str(exc).lower()
    else:
        raise AssertionError("Se esperaba rechazo de ArrayFormula")
