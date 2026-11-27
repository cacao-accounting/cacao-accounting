# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1400/#1401: contrato del lector XLSX de importación de líneas.

Un ZIP válido que no sea OOXML debe rechazarse con un 400 accionable y un
libro con más de una hoja de líneas no puede importarse parcialmente en
silencio.
"""

import io
import json
import zipfile

import openpyxl

from cacao_accounting.api import line_import
from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry

_HEADERS = ["Cuenta", "Descripción", "Debe", "Haber"]


def _xlsx_bytes(sheet_titles: tuple[str, ...] = ("Lines",)) -> bytes:
    """Construye un XLSX en memoria con las hojas indicadas."""
    workbook = openpyxl.Workbook()
    workbook.active.title = sheet_titles[0]
    workbook.active.append(_HEADERS)
    workbook.active.append(["1101", "Caja", "100", "0"])
    for title in sheet_titles[1:]:
        sheet = workbook.create_sheet(title)
        sheet.append(_HEADERS)
        sheet.append(["1102", "Banco", "0", "100"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def _fake_zip_bytes() -> bytes:
    """Construye un ZIP válido que no contiene partes OOXML."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("not-an-xlsx.txt", "contenido")
    return buffer.getvalue()


def test_archivo_zip_que_no_es_ooxml_se_rechaza(tmp_path):
    """El guard estructural exige las partes obligatorias del libro."""
    path = tmp_path / "falso.xlsx"
    path.write_bytes(_fake_zip_bytes())

    safe, reason = line_import._xlsx_archive_is_safe(str(path))

    assert safe is False
    assert reason and "dañado" in reason


def test_archivo_xlsx_valido_sigue_aceptado(tmp_path):
    """La validación estructural no rechaza un libro OOXML real."""
    path = tmp_path / "valido.xlsx"
    path.write_bytes(_xlsx_bytes())

    safe, reason = line_import._xlsx_archive_is_safe(str(path))

    assert safe is True
    assert reason is None


def test_endpoint_rechaza_zip_que_no_es_ooxml(authenticated_client):
    """La ruta responde 400, no 500, ante un ZIP que no es un libro."""
    client = authenticated_client("admin")

    response = client.post(
        "/api/line-import/parse-xlsx",
        data={"doctype": "journal_entry", "file": (io.BytesIO(_fake_zip_bytes()), "falso.xlsx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["valid"] is False
    assert payload["errors"][0]["field"] == "file"


def test_varias_hojas_de_lineas_se_rechazan(tmp_path):
    """Dos hojas candidatas no se resuelven tomando la primera."""
    path = tmp_path / "ambigua.xlsx"
    path.write_bytes(_xlsx_bytes(("Lines", "Lineas")))
    schema = LineImportSchemaRegistry.get_schema("journal_entry")

    rows, errors = line_import._xlsx_rows(str(path), schema)

    assert not rows
    assert errors and errors[0]["field"] == "sheet"


def test_endpoint_rechaza_varias_hojas_de_lineas(authenticated_client):
    """El endpoint informa la ambigüedad de hojas sin importar filas parciales."""
    client = authenticated_client("admin")

    response = client.post(
        "/api/line-import/parse-xlsx",
        data={"doctype": "journal_entry", "file": (io.BytesIO(_xlsx_bytes(("Lines", "Lineas"))), "ambigua.xlsx")},
        content_type="multipart/form-data",
    )

    payload = json.loads(response.get_data(as_text=True))
    assert payload["valid"] is False
    assert payload["rows"] == []
    assert payload["errors"][0]["field"] == "sheet"
