# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1055: las fechas XLS respetan el sistema de fechas del libro.

Los libros guardados con el sistema de 1904 usan un epoch distinto al de
1899-12-30. Interpretar un serial de 1904 con el epoch fijo desplaza la fecha
1462 días, por lo que el lector debe convertir las celdas de fecha con el
``datemode`` real del libro antes de entregarlas al importador.

No hay un escritor .xls entre las dependencias del proyecto, así que la
integración del lector se verifica con un libro BIFF mínimo simulado y con el
helper oficial de xlrd; el cálculo del serial usa la propia librería.
"""

from __future__ import annotations

from datetime import datetime

import pytest
import xlrd
from xlrd.xldate import xldate_from_date_tuple

from cacao_accounting.imports.readers import xls_reader
from cacao_accounting.imports.utils.dates import parse_import_date

FECHA = (2026, 5, 15)
FECHA_ESPERADA = datetime(2026, 5, 15)


class _LibroFalso:
    """Libro mínimo con el contrato que consume el lector."""

    def __init__(self, datemode: int):
        self.datemode = datemode
        self.released = False

    def sheet_by_index(self, _index: int):
        return _HojaFalsa(self.datemode)

    def release_resources(self) -> None:
        self.released = True


class _HojaFalsa:
    nrows = 2
    ncols = 2

    def __init__(self, datemode: int):
        self._filas = [
            ("fecha", "monto"),
            (xldate_from_date_tuple(FECHA, datemode), 100),
        ]

    def cell_value(self, row: int, col: int):
        return self._filas[row][col]

    def cell_type(self, row: int, col: int) -> int:
        if row == 0:
            return xlrd.XL_CELL_TEXT
        return xlrd.XL_CELL_DATE if col == 0 else xlrd.XL_CELL_NUMBER


@pytest.mark.parametrize("datemode", [0, 1], ids=["1900", "1904"])
def test_celda_de_fecha_usa_el_epoch_del_libro(datemode):
    """El mismo día se convierte correctamente en ambos sistemas de fecha."""
    libro = _LibroFalso(datemode)

    assert xls_reader._cell_value(libro, xlrd.XL_CELL_DATE, xldate_from_date_tuple(FECHA, datemode)) == FECHA_ESPERADA


def test_celda_numerica_conserva_su_valor():
    """Una celda que no es fecha no se convierte ni se altera."""
    libro = _LibroFalso(1)

    assert xls_reader._cell_value(libro, xlrd.XL_CELL_NUMBER, 100) == 100


@pytest.mark.parametrize("datemode", [0, 1], ids=["1900", "1904"])
def test_lector_aplica_datemode_al_leer_filas(tmp_path, monkeypatch, datemode):
    """`read` entrega la fecha convertida y no el serial crudo del libro."""
    archivo = tmp_path / "extracto.xls"
    archivo.write_bytes(b"biff-simulado")
    libro = _LibroFalso(datemode)

    monkeypatch.setattr(xls_reader, "_preflight_legacy_xls", lambda _path: True)
    monkeypatch.setattr(xls_reader.xlrd, "open_workbook", lambda *_a, **_k: libro)

    resultado = xls_reader.XLSReader().read(str(archivo))

    assert resultado.columns == ["fecha", "monto"]
    assert resultado.rows == [["2026-05-15", "100"]]
    assert parse_import_date(resultado.rows[0][0]) == FECHA_ESPERADA.date()
    assert libro.released is True
