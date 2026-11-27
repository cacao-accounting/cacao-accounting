# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1625: los parsers ODS de tasas y presupuesto funcionan con odfpy."""

from __future__ import annotations

import io

import pytest
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P

from cacao_accounting.contabilidad.budget_import_service import BudgetImportService
from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportService
from cacao_accounting.imports.readers.limits import ImportReadLimitError


def _ods_bytes(rows: list[list[str]], repeat_first_data_cell: bool = False, repeat_count: int = 2) -> bytes:
    documento = OpenDocumentSpreadsheet()
    tabla = Table(name="Datos")
    for row_index, values in enumerate(rows):
        fila = TableRow()
        for cell_index, value in enumerate(values):
            repetir = repeat_first_data_cell and row_index == 1 and cell_index == 0
            atributos = {"valuetype": "string"}
            if repetir:
                atributos["numbercolumnsrepeated"] = str(repeat_count)
            celda = TableCell(**atributos)
            celda.addElement(P(text=str(value)))
            fila.addElement(celda)
        tabla.addElement(fila)
    documento.spreadsheet.addElement(tabla)
    salida = io.BytesIO()
    documento.save(salida)
    return salida.getvalue()


def test_tasas_parsea_ods_real():
    """El parser de tasas no invoca getAttributeNS y conserva la fila."""
    contenido = _ods_bytes(
        [
            ["Moneda Origen", "Moneda Destino", "Fecha", "Tasa"],
            ["USD", "NIO", "2026-05-15", "36.5"],
        ]
    )

    filas = ExchangeRateImportService()._parse_ods(contenido)

    assert filas == [{"Moneda Origen": "USD", "Moneda Destino": "NIO", "Fecha": "2026-05-15", "Tasa": "36.5"}]


def test_presupuesto_parsea_ods_real():
    """El parser de presupuesto procesa celdas y encabezados ODS."""
    contenido = _ods_bytes(
        [
            ["Cuenta", "Centro de Costo", "Mayo 2026"],
            ["1101", "ADM", "10"],
        ]
    )

    filas = BudgetImportService()._parse_ods(contenido)

    assert filas == [{"Cuenta": "1101", "Centro de Costo": "ADM", "Mayo 2026": "10"}]


def test_presupuesto_parsea_celdas_repetidas_ods():
    """La repetición de columnas usa getAttribute y replica el valor."""
    contenido = _ods_bytes(
        [
            ["Cuenta", "Descripción", "Mayo 2026"],
            ["1101", "Caja", "10"],
        ],
        repeat_first_data_cell=True,
    )

    filas = BudgetImportService()._parse_ods(contenido)

    assert filas and filas[0]["Cuenta"] == "1101"
    assert filas[0]["Descripción"] == "1101"


def test_presupuesto_rechaza_columnas_repetidas_excesivas():
    """Una repetición ODS enorme falla antes de expandir la fila (#1373)."""
    contenido = _ods_bytes(
        [
            ["Cuenta", "Descripción", "Mayo 2026"],
            ["1101", "Caja", "10"],
        ],
        repeat_first_data_cell=True,
        repeat_count=100_000,
    )

    with pytest.raises(ImportReadLimitError):
        BudgetImportService()._parse_ods(contenido)


def test_tasas_rechaza_columnas_repetidas_excesivas():
    """El parser de tasas aplica el mismo límite de expansión (#1373)."""
    contenido = _ods_bytes(
        [
            ["Moneda Origen", "Moneda Destino", "Fecha", "Tasa"],
            ["USD", "NIO", "2026-05-15", "36.5"],
        ],
        repeat_first_data_cell=True,
        repeat_count=100_000,
    )

    with pytest.raises(ImportReadLimitError):
        ExchangeRateImportService()._parse_ods(contenido)


def _ods_typed_bytes() -> bytes:
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableCell, TableRow
    from odf.text import P

    doc = OpenDocumentSpreadsheet()
    t = Table(name="T")
    r1 = TableRow()
    for h in ["Moneda Origen", "Moneda Destino", "Fecha", "Tasa"]:
        c = TableCell(valuetype="string")
        c.addElement(P(text=h))
        r1.addElement(c)
    t.addElement(r1)
    r2 = TableRow()
    for v in ["USD", "NIO"]:
        c = TableCell(valuetype="string")
        c.addElement(P(text=v))
        r2.addElement(c)
    r2.addElement(TableCell(valuetype="date", datevalue="2026-05-15"))
    r2.addElement(TableCell(valuetype="float", value="36.5"))
    t.addElement(r2)
    doc.spreadsheet.addElement(t)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def test_tasas_parsea_ods_tipos_office_value():
    """#1625 QA: lee celdas tipadas sin text:p."""
    filas = ExchangeRateImportService()._parse_ods(_ods_typed_bytes())
    assert filas == [{"Moneda Origen": "USD", "Moneda Destino": "NIO", "Fecha": "2026-05-15", "Tasa": "36.5"}]
