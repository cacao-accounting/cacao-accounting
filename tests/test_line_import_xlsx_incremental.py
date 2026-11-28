# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1206/#1373: el lector XLSX de líneas consume filas de forma acotada.

Una hoja con dimensión inflada o con muchas filas reales no debe
materializarse completa antes de aplicar los límites de filas y columnas.
"""

import io

import openpyxl

# pylint: disable=protected-access
from cacao_accounting.api import line_import
from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry

_HEADERS = ["Cuenta", "Descripción", "Debe", "Haber"]


class _Cell:  # pylint: disable=too-few-public-methods
    """Celda mínima compatible con el lector canónico."""

    def __init__(self, value):
        """Conserva el valor y simula una celda sin fórmula."""
        self.value = value
        self.data_type = "n"


class _Worksheet:  # pylint: disable=too-few-public-methods
    """Hoja controlada que cuenta las filas efectivamente consumidas."""

    title = "Lines"

    def __init__(self, rows):
        """Registra las filas que el lector podrá iterar."""
        self._rows = rows
        self.consumed = 0
        self.reset_called = False

    def reset_dimensions(self):
        """Registra que el lector descarta la dimensión declarada."""
        self.reset_called = True

    def iter_rows(self):
        """Genera las filas de prueba contando cada consumo."""
        for row in self._rows:
            self.consumed += 1
            yield tuple(_Cell(value) for value in row)


class _Workbook:  # pylint: disable=too-few-public-methods
    """Libro mínimo con una única hoja."""

    def __init__(self, worksheet):
        """Expone la hoja como única hoja del libro."""
        self.worksheets = [worksheet]


def _read(rows):
    """Ejecuta el lector productivo sobre una hoja controlada."""
    worksheet = _Worksheet(rows)
    schema = LineImportSchemaRegistry.get_schema("journal_entry")
    result, errors = line_import._read_xlsx_workbook(_Workbook(worksheet), schema)
    return worksheet, result, errors


def test_lector_deja_de_consumir_al_llegar_al_limite():
    """Con más de 500 líneas solo se consumen las necesarias para rechazar."""
    rows = [_HEADERS] + [["1101", f"Fila {index}", "1", "0"] for index in range(1450)]

    worksheet, result, errors = _read(rows)

    assert len(result) == 500
    assert any("500 líneas" in error["message"] for error in errors)
    assert worksheet.consumed <= 502


def test_lector_descarta_la_dimension_declarada():
    """La dimensión de la hoja no se usa para iterar filas inexistentes."""
    rows = [_HEADERS, ["1101", "Caja", "100", "0"], ["1102", "Banco", "0", "100"]]

    worksheet, result, errors = _read(rows)

    assert worksheet.reset_called is True
    assert not errors
    assert [row["account"] for row in result] == ["1101", "1102"]
    assert worksheet.consumed == 3


def test_lector_rechaza_columnas_antes_de_consumir_datos():
    """Un encabezado de más de 100 columnas falla sin iterar las filas."""
    rows = [_HEADERS + [f"C{index}" for index in range(97)]]
    worksheet = _Worksheet(rows)
    schema = LineImportSchemaRegistry.get_schema("journal_entry")

    result, errors = line_import._read_xlsx_workbook(_Workbook(worksheet), schema)

    assert not result
    assert any("demasiadas columnas" in error["message"] for error in errors)
    assert worksheet.consumed == 1


def test_lector_reporta_columna_sin_encabezado_con_datos():
    """La columna sin encabezado se detecta durante la lectura incremental."""
    rows = [_HEADERS + [""], ["1101", "Caja", "100", "0", "dato"]]

    _worksheet, result, errors = _read(rows)

    assert any(error["field"] == "column_5" for error in errors)
    assert result[0]["account"] == "1101"


def test_endpoint_limita_filas_reales(authenticated_client):
    """La ruta devuelve 500 filas y error de límite sin materializar el resto."""
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Lines"
    worksheet.append(_HEADERS)
    for index in range(650):
        worksheet.append(["1101", f"Fila {index}", "1", "0"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()

    client = authenticated_client("admin")
    response = client.post(
        "/api/line-import/parse-xlsx",
        data={"doctype": "journal_entry", "file": (io.BytesIO(buffer.getvalue()), "filas.xlsx")},
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert payload["valid"] is False
    assert payload["rows"] == []
    assert any("500 líneas" in error["message"] for error in payload["errors"])
