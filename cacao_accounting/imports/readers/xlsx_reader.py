# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos XLSX."""

import openpyxl
from cacao_accounting.imports.readers.base import BaseReader, TabularBook
from cacao_accounting.imports.readers.limits import (
    ReadBudget,
    validate_archive_size,
)


class XLSXReader(BaseReader):
    """Lee archivos XLSX usando openpyxl."""

    def read(self, file_path: str) -> TabularBook:
        """Lee un archivo XLSX y devuelve un TabularBook canónico."""
        validate_archive_size(file_path)
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        try:
            ws = wb.active
            ws.reset_dimensions()

            rows_iter = ws.iter_rows(values_only=True)
            try:
                columns = [str(c) if c is not None else "" for c in next(rows_iter)]
            except StopIteration:
                return TabularBook(source_format="xlsx")

            budget = ReadBudget()
            budget.consume_header(len(columns))
            rows = []
            for row in rows_iter:
                values = list(row)
                budget.consume_row(len(values))
                rows.append(values)

            return TabularBook(columns=columns, rows=rows, source_format="xlsx")
        finally:
            wb.close()
