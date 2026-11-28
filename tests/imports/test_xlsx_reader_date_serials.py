# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1055: XLSX seriales de fecha usan el epoch real solo en columnas de fecha."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from openpyxl import Workbook
from openpyxl.utils.datetime import MAC_EPOCH, WINDOWS_EPOCH, to_excel

from cacao_accounting.imports.readers.xlsx_reader import XLSXReader
from cacao_accounting.imports.utils.dates import parse_import_date


@pytest.mark.parametrize("epoch", [WINDOWS_EPOCH, MAC_EPOCH], ids=["1900", "1904"])
@pytest.mark.parametrize("date_header", ["date", "fecha_contabilizacion"], ids=["en-date", "es-bank-date"])
def test_xlsx_numeric_date_serial_uses_workbook_epoch(tmp_path, epoch, date_header):
    """Seriales XLSX en fechas se normalizan y no alteran otras columnas."""
    workbook = Workbook()
    workbook.epoch = epoch
    worksheet = workbook.active
    worksheet.append([date_header, "amount"])
    worksheet.append([to_excel(datetime(2026, 5, 15), epoch=epoch), to_excel(datetime(2026, 5, 15), epoch=epoch)])
    path = tmp_path / "date_serials.xlsx"
    workbook.save(path)
    workbook.close()

    table = XLSXReader().read(str(path))

    assert table.rows[0][0] == "2026-05-15"
    assert parse_import_date(table.rows[0][0]) == date(2026, 5, 15)
    assert table.rows[0][1] == str(int(to_excel(datetime(2026, 5, 15), epoch=epoch)))


@pytest.mark.parametrize("serial", [0, -1, 999999999])
def test_xlsx_invalid_date_serial_remains_invalid(tmp_path, serial):
    """Un serial fuera del calendario no se convierte en una fecha válida."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["fecha"])
    worksheet.append([serial])
    path = tmp_path / "invalid_date_serial.xlsx"
    workbook.save(path)
    workbook.close()

    table = XLSXReader().read(str(path))

    with pytest.raises(ValueError):
        parse_import_date(table.rows[0][0])
