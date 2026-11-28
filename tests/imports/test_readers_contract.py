# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contrato común de lectura para los cuatro formatos tabulares admitidos."""

import csv
import struct
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P

from cacao_accounting.imports.readers.base import TabularBook
from cacao_accounting.imports.readers.csv_reader import CSVReader
from cacao_accounting.imports.readers.ods_reader import ODSReader
from cacao_accounting.imports.readers.xls_reader import XLSReader
from cacao_accounting.imports.readers.xlsx_reader import XLSXReader

EXPECTED_COLUMNS = ["name", "quantity", "amount", "active", "posting_date"]
EXPECTED_ROWS = [["A-1", "2", "12.5", "true", "2026-05-15"]]


def _write_csv(path: Path) -> None:
    """Escribe la tabla de referencia en CSV UTF-8 con BOM."""
    with path.open("w", encoding="utf-8-sig", newline="") as source:
        writer = csv.writer(source)
        writer.writerow([f"\ufeff{EXPECTED_COLUMNS[0]}", *EXPECTED_COLUMNS[1:]])
        writer.writerow(["A-1", "2", "12.5", "true", "2026-05-15"])


def _write_xlsx(path: Path) -> None:
    """Escribe la misma tabla con valores Excel tipados y BOM en el primer título."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append([f"\ufeff{EXPECTED_COLUMNS[0]}", *EXPECTED_COLUMNS[1:]])
    sheet.append(["A-1", 2, 12.5, True, datetime(2026, 5, 15)])
    workbook.save(path)
    workbook.close()


def _write_ods(path: Path) -> None:
    """Escribe la tabla equivalente usando tipos nativos ODF."""
    document = OpenDocumentSpreadsheet()
    sheet = Table(name="Contract")
    header = TableRow()
    for index, value in enumerate(EXPECTED_COLUMNS):
        cell = TableCell()
        cell.addElement(P(text=f"\ufeff{value}" if index == 0 else value))
        header.addElement(cell)
    sheet.addElement(header)

    row = TableRow()
    typed_values = (
        ("string", "stringvalue", "A-1"),
        ("float", "value", "2"),
        ("float", "value", "12.5"),
        ("boolean", "booleanvalue", "true"),
        ("date", "datevalue", "2026-05-15"),
    )
    for value_type, value_attribute, value in typed_values:
        cell = TableCell(valuetype=value_type, **{value_attribute: value})
        row.addElement(cell)
    sheet.addElement(row)
    document.spreadsheet.addElement(sheet)
    document.save(str(path))


def _biff_record(record_id: int, data: bytes) -> bytes:
    """Encode one BIFF record used by this tiny test-only XLS workbook."""
    return struct.pack("<HH", record_id, len(data)) + data


def _biff2_label(row: int, column: int, value: str) -> bytes:
    """Encode a BIFF2 label cell using the workbook's legacy byte encoding."""
    encoded = value.encode("latin-1")
    return struct.pack("<HH3sB", row, column, b"\0\0\0", len(encoded)) + encoded


def _write_xls(path: Path) -> None:
    """Write a minimal real BIFF2 workbook without a runtime writer dependency."""
    records = [
        _biff_record(0x0009, struct.pack("<HH", 0x0002, 0x0010)),
        _biff_record(0x0004, _biff2_label(0, 0, EXPECTED_COLUMNS[0])),
    ]
    for index, header in enumerate(EXPECTED_COLUMNS[1:], start=1):
        records.append(_biff_record(0x0004, _biff2_label(0, index, header)))
    records.extend(
        [
            _biff_record(0x0004, _biff2_label(1, 0, "A-1")),
            _biff_record(0x0002, struct.pack("<HH3sH", 1, 1, b"\0\0\0", 2)),
            _biff_record(0x0003, struct.pack("<HH3sd", 1, 2, b"\0\0\0", 12.5)),
            _biff_record(0x0004, _biff2_label(1, 3, "true")),
            _biff_record(0x0004, _biff2_label(1, 4, "2026-05-15")),
            _biff_record(0x000A, b""),
        ]
    )
    path.write_bytes(b"".join(records))


@pytest.fixture(params=("csv", "xls", "xlsx", "ods"))
def tabular_source(request, tmp_path):
    """Build the same logical table as a real file for each reader."""
    format_name = request.param
    path = tmp_path / f"contract.{format_name}"
    writers = {"csv": _write_csv, "xls": _write_xls, "xlsx": _write_xlsx, "ods": _write_ods}
    writers[format_name](path)
    return format_name, path


def test_readers_return_the_same_canonical_tabular_book(tabular_source):
    """Every file reader removes BOM and normalizes typed scalar values equally."""
    source_format, path = tabular_source
    readers = {"csv": CSVReader, "xls": XLSReader, "xlsx": XLSXReader, "ods": ODSReader}

    book = readers[source_format]().read(str(path))

    assert isinstance(book, TabularBook)
    assert book.source_format == source_format
    assert book.columns == EXPECTED_COLUMNS
    assert book.rows == EXPECTED_ROWS


def test_tabular_book_preserves_text_and_normalizes_empty_and_nonfinite_values():
    """Common scalar normalization keeps literal text and non-finite tokens intact."""
    book = TabularBook(columns=["\ufeffname", "value", "empty"], rows=[["  text  ", float("inf"), None]])

    assert book.columns == ["name", "value", "empty"]
    assert book.rows == [["  text  ", "inf", ""]]
