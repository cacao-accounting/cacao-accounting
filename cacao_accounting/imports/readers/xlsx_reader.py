# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos XLSX."""

import openpyxl
from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable


class XLSXReader(BaseReader):
    """Lee archivos XLSX usando openpyxl."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee un archivo XLSX y devuelve una NormalizedTable."""
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        try:
            columns = [str(c) if c is not None else "" for c in next(rows_iter)]
        except StopIteration:
            return NormalizedTable(source_format="xlsx")

        rows = [list(row) for row in rows_iter]

        return NormalizedTable(columns=columns, rows=rows, source_format="xlsx")
