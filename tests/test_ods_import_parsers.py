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


def _typed_cell(value_type: str, text: str | None = None, **attributes):
    """Crea una celda tipada con texto visible opcional."""
    celda = TableCell(valuetype=value_type, **attributes)
    if text is not None:
        celda.addElement(P(text=text))
    return celda


def _ods_bytes_with(
    headers: list[str],
    data_rows: list[tuple[int, list[TableCell]]],
) -> bytes:
    """Construye un ODS con la repetición de fila declarada por cada grupo."""
    documento = OpenDocumentSpreadsheet()
    tabla = Table(name="Datos")
    fila_encabezado = TableRow()
    for header in headers:
        fila_encabezado.addElement(_typed_cell("string", header))
    tabla.addElement(fila_encabezado)
    for repeat, cells in data_rows:
        fila = TableRow()
        if repeat != 1:
            fila.setAttribute("numberrowsrepeated", str(repeat))
        for cell in cells:
            fila.addElement(cell)
        tabla.addElement(fila)
    documento.spreadsheet.addElement(tabla)
    salida = io.BytesIO()
    documento.save(salida)
    return salida.getvalue()


def test_tasas_expande_filas_repetidas():
    """Un ODS que comprime filas iguales importa todas las filas lógicas."""
    contenido = _ods_bytes_with(
        ["Moneda Origen", "Moneda Destino", "Fecha", "Tasa"],
        [
            (
                2,
                [
                    _typed_cell("string", "USD"),
                    _typed_cell("string", "NIO"),
                    _typed_cell("date", "2026-05-15", datevalue="2026-05-15"),
                    _typed_cell("float", "36.5", value="36.5"),
                ],
            ),
        ],
    )

    filas = ExchangeRateImportService()._parse_ods(contenido)

    assert len(filas) == 2
    assert all(fila["Fecha"] == "2026-05-15" and fila["Tasa"] == "36.5" for fila in filas)


def test_presupuesto_expande_filas_repetidas():
    """El presupuesto no pierde filas comprimidas por numberrowsrepeated."""
    contenido = _ods_bytes_with(
        ["Cuenta", "Centro de Costo", "Mayo 2026"],
        [
            (
                3,
                [
                    _typed_cell("string", "1101"),
                    _typed_cell("string", "ADM"),
                    _typed_cell("float", "10", value="10"),
                ],
            ),
        ],
    )

    filas = BudgetImportService()._parse_ods(contenido)

    assert len(filas) == 3
    assert all(fila == {"Cuenta": "1101", "Centro de Costo": "ADM", "Mayo 2026": "10"} for fila in filas)


def test_tasas_prioriza_el_valor_tipado_sobre_el_texto_visible():
    """La fecha y la tasa usan value/date-value, no la presentación local."""
    contenido = _ods_bytes_with(
        ["Moneda Origen", "Moneda Destino", "Fecha", "Tasa"],
        [
            (
                1,
                [
                    _typed_cell("string", "USD"),
                    _typed_cell("string", "NIO"),
                    _typed_cell("date", "15/05/2026", datevalue="2026-05-15"),
                    _typed_cell("float", "36,5", value="36.5"),
                ],
            ),
        ],
    )

    filas = ExchangeRateImportService()._parse_ods(contenido)

    assert filas == [{"Moneda Origen": "USD", "Moneda Destino": "NIO", "Fecha": "2026-05-15", "Tasa": "36.5"}]


def test_presupuesto_prioriza_el_valor_tipado_sobre_el_texto_visible():
    """El importe presupuestado usa el valor canónico y no el formato local."""
    contenido = _ods_bytes_with(
        ["Cuenta", "Centro de Costo", "Mayo 2026"],
        [
            (
                1,
                [
                    _typed_cell("string", "1101"),
                    _typed_cell("string", "ADM"),
                    _typed_cell("float", "1.500,00", value="1500"),
                ],
            ),
        ],
    )

    filas = BudgetImportService()._parse_ods(contenido)

    assert filas[0]["Mayo 2026"] == "1500"


def test_tasas_usa_el_texto_si_el_valor_tipado_es_invalido():
    """Un date-value inválido no se impone sobre el texto visible."""
    contenido = _ods_bytes_with(
        ["Moneda Origen", "Moneda Destino", "Fecha", "Tasa"],
        [
            (
                1,
                [
                    _typed_cell("string", "USD"),
                    _typed_cell("string", "NIO"),
                    _typed_cell("date", "15/05/2026", datevalue="no-es-fecha"),
                    _typed_cell("float", "36.5", value="36.5"),
                ],
            ),
        ],
    )

    filas = ExchangeRateImportService()._parse_ods(contenido)

    assert filas[0]["Fecha"] == "15/05/2026"


def test_tasas_rechaza_filas_repetidas_excesivas():
    """Una repetición de filas enorme falla antes de materializarla."""
    contenido = _ods_bytes_with(
        ["Moneda Origen", "Moneda Destino", "Fecha", "Tasa"],
        [
            (
                100_001,
                [
                    _typed_cell("string", "USD"),
                    _typed_cell("string", "NIO"),
                    _typed_cell("date", "2026-05-15", datevalue="2026-05-15"),
                    _typed_cell("float", "36.5", value="36.5"),
                ],
            ),
        ],
    )

    with pytest.raises(ImportReadLimitError):
        ExchangeRateImportService()._parse_ods(contenido)


def test_presupuesto_rechaza_filas_repetidas_excesivas():
    """El presupuesto aplica el mismo límite de filas repetidas."""
    contenido = _ods_bytes_with(
        ["Cuenta", "Centro de Costo", "Mayo 2026"],
        [
            (
                100_001,
                [
                    _typed_cell("string", "1101"),
                    _typed_cell("string", "ADM"),
                    _typed_cell("float", "10", value="10"),
                ],
            ),
        ],
    )

    with pytest.raises(ImportReadLimitError):
        BudgetImportService()._parse_ods(contenido)
