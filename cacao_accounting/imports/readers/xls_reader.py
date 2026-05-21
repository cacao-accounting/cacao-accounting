# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos XLS."""

import xlrd
from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable


class XLSReader(BaseReader):
    """Lee archivos XLS usando xlrd."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee un archivo XLS y devuelve una NormalizedTable."""
        wb = xlrd.open_workbook(file_path)
        ws = wb.sheet_by_index(0)
        if ws.nrows == 0:
            return NormalizedTable(source_format="xls")

        columns = [str(ws.cell_value(0, col)) for col in range(ws.ncols)]
        rows = []
        for row_idx in range(1, ws.nrows):
            rows.append([ws.cell_value(row_idx, col) for col in range(ws.ncols)])

        return NormalizedTable(columns=columns, rows=rows, source_format="xls")
