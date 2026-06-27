# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from cacao_accounting.imports.readers.csv_reader import CSVReader
from cacao_accounting.imports.readers.xlsx_reader import XLSXReader
import openpyxl


def test_csv_reader(tmp_path):
    p = tmp_path / "test.csv"
    with open(p, "w", encoding="utf-8") as f:
        f.write("col1,col2\nval1,val2\nval3,val4")

    reader = CSVReader()
    table = reader.read(str(p))

    assert table.columns == ["col1", "col2"]
    assert table.rows == [["val1", "val2"], ["val3", "val4"]]
    assert table.source_format == "csv"


def test_xlsx_reader(tmp_path):
    p = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["col1", "col2"])
    ws.append(["val1", "val2"])
    wb.save(str(p))

    reader = XLSXReader()
    table = reader.read(str(p))

    assert table.columns == ["col1", "col2"]
    assert table.rows == [["val1", "val2"]]
    assert table.source_format == "xlsx"
