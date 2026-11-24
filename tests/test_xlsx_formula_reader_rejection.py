# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1623: el lector XLSX rechaza fórmulas aunque exista un valor en caché."""

from __future__ import annotations

import shutil
from zipfile import ZipFile

import openpyxl

from cacao_accounting.imports.adapters.customer import CustomerAdapter
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


def test_reader_expone_la_formula_y_no_el_valor_cacheado(tmp_path):
    """data_only=False conserva la fórmula para que la validación la rechace."""
    ruta = _xlsx_con_formula_cacheada(tmp_path)
    cacheado = openpyxl.load_workbook(ruta, data_only=True).active["A2"].value
    assert cacheado == 999

    libro = XLSXReader().read(str(ruta))

    assert libro.rows[0][0] == "=SUM(1,1)"
    fila = dict(zip(libro.columns, libro.rows[0]))
    errores = CustomerAdapter().validate_row(fila)
    assert any("Fórmula detectada" in error for error in errores)
