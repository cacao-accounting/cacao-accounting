# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos XLS."""

from typing import Any
from io import StringIO
from pathlib import Path

import xlrd
from xlrd import biffh, compdoc
from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable
from cacao_accounting.imports.readers.limits import (
    MAX_IMPORT_CELLS,
    MAX_IMPORT_COLUMNS,
    MAX_IMPORT_ROWS,
    MAX_IMPORT_SHEETS,
    ImportReadLimitError,
    ReadBudget,
    validate_file_size,
)


class XLSReader(BaseReader):
    """Lee archivos XLS usando xlrd."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee un archivo XLS y devuelve una NormalizedTable."""
        validate_file_size(file_path)
        _preflight_legacy_xls(file_path)
        wb = xlrd.open_workbook(file_path, on_demand=True)
        try:
            _validate_sheet_extent(wb)
            ws = wb.sheet_by_index(0)
            if ws.nrows == 0:
                return NormalizedTable(source_format="xls")
            if ws.nrows - 1 > MAX_IMPORT_ROWS or ws.ncols > MAX_IMPORT_COLUMNS:
                raise ImportReadLimitError()

            budget = ReadBudget()
            budget.consume_header(ws.ncols)
            columns = [str(ws.cell_value(0, col)) for col in range(ws.ncols)]
            rows = []
            for row_idx in range(1, ws.nrows):
                row = [ws.cell_value(row_idx, col) for col in range(ws.ncols)]
                budget.consume_row(len(row))
                rows.append(row)

            return NormalizedTable(columns=columns, rows=rows, source_format="xls")
        finally:
            wb.release_resources()


def _validate_sheet_extent(workbook: Any) -> None:
    """Escanea registros BIFF antes de que xlrd materialice la primera hoja."""
    positions = getattr(workbook, "_sh_abs_posn", None)
    memory = getattr(workbook, "mem", None)
    if not positions or memory is None:
        raise ImportReadLimitError()

    extent = _scan_biff_extent(memory, positions[0], workbook.base + workbook.stream_len)
    extent.validate()


def _preflight_legacy_xls(file_path: str) -> None:
    """Prevalida BIFF2–4 antes de xlrd, que carga esas hojas eager."""
    source = Path(file_path).read_bytes()
    memory, base, stream_length = _workbook_stream(source)
    stream_end = base + stream_length
    if base + 4 > stream_end:
        return
    record, data, position = _read_biff_record(memory, base, stream_end)
    if record not in biffh.bofcodes or record >> 8 == 0x08:
        return
    version = record >> 8
    stream_type = biffh.unpack("<H", data[2:4])[0]
    if version == 0x04 and stream_type == biffh.XL_WORKBOOK_GLOBALS_4W:
        _preflight_biff4w(memory, position, stream_end)
    elif version in (0x00, 0x02, 0x04) and stream_type == biffh.XL_WORKSHEET:
        _scan_biff_extent(memory, base, stream_end).validate()


def _workbook_stream(source: bytes) -> tuple[Any, int, int]:
    """Localiza el stream BIFF dentro de un contenedor OLE o devuelve el archivo."""
    if source[:8] != compdoc.SIGNATURE:
        return source, 0, len(source)
    document = compdoc.CompDoc(source, logfile=StringIO())
    for name in ("Workbook", "Book"):
        memory, base, length = document.locate_named_stream(name)
        if memory:
            return memory, base, length
    raise xlrd.XLRDError("Can't find workbook stream in OLE compound document")


def _preflight_biff4w(memory: Any, position: int, stream_end: int) -> None:
    """Prevalida cada substream de BIFF4W que xlrd cargaría durante open_workbook."""
    total_cells = 0
    total_data_rows = 0
    sheet_count = 0
    while position + 4 <= stream_end:
        record, data, record_end = _read_biff_record(memory, position, stream_end)
        if record == biffh.XL_EOF:
            return
        if record == biffh.XL_SHEETHDR:
            if len(data) < 4:
                raise ImportReadLimitError()
            sheet_length = biffh.unpack("<i", data[:4])[0]
            sheet_end = record_end + sheet_length
            if sheet_length <= 0 or sheet_end > stream_end:
                raise ImportReadLimitError()
            extent = _scan_biff_extent(memory, record_end, sheet_end)
            total_cells += extent.validate()
            total_data_rows += max(0, extent.max_row)
            sheet_count += 1
            if total_cells > MAX_IMPORT_CELLS or total_data_rows > MAX_IMPORT_ROWS or sheet_count > MAX_IMPORT_SHEETS:
                raise ImportReadLimitError()
            position = sheet_end
        else:
            position = record_end


def _scan_biff_extent(memory: Any, position: int, stream_end: int) -> "_BIFFExtent":
    """Escanea una hoja hasta EOF y rechaza streams BIFF truncados."""
    extent = _BIFFExtent()
    while position + 4 <= stream_end:
        record, data, position = _read_biff_record(memory, position, stream_end)
        if not extent.consume(record, data):
            return extent
    raise ImportReadLimitError()


_CELL_RECORDS = {
    biffh.XL_NUMBER,
    biffh.XL_LABELSST,
    biffh.XL_LABEL,
    biffh.XL_RSTRING,
    biffh.XL_RK,
    biffh.XL_FORMULA,
    biffh.XL_FORMULA3,
    biffh.XL_FORMULA4,
    biffh.XL_BOOLERR,
    biffh.XL_BLANK,
    biffh.XL_INTEGER,
    biffh.XL_NUMBER_B2,
    biffh.XL_LABEL_B2,
    biffh.XL_BOOLERR_B2,
}


class _BIFFExtent:
    """Calcula la matriz máxima descrita por registros de la primera hoja."""

    def __init__(self) -> None:
        """Inicia coordenadas y estado de substreams BIFF."""
        self.max_row = -1
        self.max_column = -1
        self.sheet_started = False
        self.embedded_stream = False

    def consume(self, record: int, data: bytes) -> bool:
        """Procesa un registro y devuelve si el escaneo de hoja debe continuar."""
        if record == biffh.XL_EOF:
            if self.embedded_stream:
                self.embedded_stream = False
                return True
            return False
        if record in biffh.bofcodes:
            self.embedded_stream = self.sheet_started
            self.sheet_started = True
        if not self.embedded_stream:
            self._include_record(record, data)
        return True

    def validate(self) -> int:
        """Rechaza coordenadas BIFF sobre límites y devuelve celdas materializadas."""
        if self.max_row >= MAX_IMPORT_ROWS + 1 or self.max_column + 1 > MAX_IMPORT_COLUMNS:
            raise ImportReadLimitError()
        if self.max_row >= 0 and (self.max_row + 1) * (self.max_column + 1) > MAX_IMPORT_CELLS:
            raise ImportReadLimitError()
        if self.max_row < 0:
            return 0
        return (self.max_row + 1) * (self.max_column + 1)

    def _include_record(self, record: int, data: bytes) -> None:
        """Actualiza los extremos desde celdas, rangos o celdas múltiples."""
        if record in _CELL_RECORDS:
            row, column = biffh.unpack("<HH", data[:4])
            self.max_row = max(self.max_row, row)
            self.max_column = max(self.max_column, column)
        elif record in (biffh.XL_MULRK, biffh.XL_MULBLANK):
            self._include_multiple_cells(data)
        elif record == biffh.XL_MERGEDCELLS:
            self.max_row, self.max_column = _merged_extent(data, self.max_row, self.max_column)

    def _include_multiple_cells(self, data: bytes) -> None:
        """Actualiza los extremos de una fila BIFF con varias celdas contiguas."""
        row, first_column = biffh.unpack("<HH", data[:4])
        last_column = biffh.unpack("<H", data[-2:])[0]
        if last_column < first_column:
            raise ImportReadLimitError()
        self.max_row = max(self.max_row, row)
        self.max_column = max(self.max_column, last_column)


def _read_biff_record(memory: Any, position: int, stream_end: int) -> tuple[int, bytes, int]:
    """Lee una cabecera BIFF y comprueba que el payload no rebase el stream."""
    record, length = biffh.unpack("<HH", memory[position : position + 4])
    payload_start = position + 4
    record_end = payload_start + length
    if record_end > stream_end:
        raise ImportReadLimitError()
    return record, memory[payload_start:record_end], record_end


def _merged_extent(data: bytes, max_row: int, max_column: int) -> tuple[int, int]:
    """Incluye rangos combinados, que también amplían la matriz de xlrd."""
    if len(data) < 2:
        raise ImportReadLimitError()
    ranges = biffh.unpack("<H", data[:2])[0]
    if len(data) != 2 + ranges * 8:
        raise ImportReadLimitError()
    for offset in range(2, len(data), 8):
        first_row, last_row, first_column, last_column = biffh.unpack("<HHHH", data[offset : offset + 8])
        if last_row < first_row or last_column < first_column:
            raise ImportReadLimitError()
        max_row = max(max_row, last_row - 1)
        max_column = max(max_column, last_column - 1)
    return max_row, max_column
