# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1603: el lector XLSX cierra el libro y libera el archivo temporal."""

from __future__ import annotations

import os

import openpyxl
import pytest

from cacao_accounting.api import line_import
from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry


def _crear_xlsx(path, encabezados):
    """Crea un XLSX mínimo con los encabezados indicados."""
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(encabezados)
    if "Cuenta" in encabezados:
        hoja.append(["1101", "Caja", "100", "0"])
    libro.save(path)
    libro.close()


@pytest.fixture
def libros_abiertos(monkeypatch):
    """Registra cada libro abierto por el lector para inspeccionar su cierre."""
    abiertos = []
    original = line_import.load_workbook

    def load_workbook_registrado(*args, **kwargs):
        libro = original(*args, **kwargs)
        abiertos.append(libro)
        return libro

    monkeypatch.setattr(line_import, "load_workbook", load_workbook_registrado)
    return abiertos


def test_cierra_el_libro_tras_leer_un_archivo_valido(tmp_path, libros_abiertos):
    """El descriptor se libera y el temporal se puede borrar en Windows."""
    ruta = tmp_path / "lineas.xlsx"
    _crear_xlsx(ruta, ["Cuenta", "Descripción", "Debe", "Haber"])
    schema = LineImportSchemaRegistry.get_schema("journal_entry")

    filas, errores = line_import._xlsx_rows(str(ruta), schema)

    assert errores == []
    assert filas[0]["account"] == "1101"
    assert len(libros_abiertos) == 1
    assert libros_abiertos[0]._archive.fp is None
    os.unlink(ruta)


def test_cierra_el_libro_cuando_faltan_columnas(tmp_path, libros_abiertos):
    """Una salida temprana por error estructural también cierra el libro."""
    ruta = tmp_path / "incompleto.xlsx"
    _crear_xlsx(ruta, ["Descripción"])
    schema = LineImportSchemaRegistry.get_schema("journal_entry")

    filas, errores = line_import._xlsx_rows(str(ruta), schema)

    assert filas == []
    assert errores
    assert len(libros_abiertos) == 1
    assert libros_abiertos[0]._archive.fp is None
    os.unlink(ruta)
