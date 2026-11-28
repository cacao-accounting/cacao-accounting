# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos XLSX."""

from datetime import datetime
from typing import Any

import openpyxl
from openpyxl.utils.datetime import from_excel
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from cacao_accounting.i18n import _
from cacao_accounting.imports.readers.base import BaseReader, TabularBook, is_import_date_column
from cacao_accounting.imports.readers.limits import (
    ReadBudget,
    validate_archive_size,
)


class XLSXReader(BaseReader):
    """Lee archivos XLSX usando openpyxl."""

    def read(self, file_path: str) -> TabularBook:
        """Lee un archivo XLSX y devuelve un TabularBook canónico."""
        validate_archive_size(file_path)
        wb = openpyxl.load_workbook(file_path, data_only=False, read_only=True)
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
            date_columns = {index for index, column in enumerate(columns) if is_import_date_column(column)}
            rows = []
            for row in rows_iter:
                values = [
                    _reject_formula_value(_normalize_date_serial(value, wb.epoch) if index in date_columns else value)
                    for index, value in enumerate(row)
                ]
                budget.consume_row(len(values))
                rows.append(values)

            return TabularBook(columns=columns, rows=rows, source_format="xlsx")
        finally:
            wb.close()


def _reject_formula_value(value: Any) -> Any:
    """Rechaza fórmulas, incluidas matrices/data-table, antes de normalizar."""
    if isinstance(value, str) and value.startswith("="):
        raise ValueError(_("El archivo contiene fórmulas. Reemplace las celdas por valores fijos."))
    if isinstance(value, (ArrayFormula, DataTableFormula)):
        raise ValueError(_("El archivo contiene fórmulas. Reemplace las celdas por valores fijos."))
    return value


def _normalize_date_serial(value: Any, epoch: datetime) -> Any:
    """Convierte seriales numéricos solo en columnas reconocidas como fecha."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return value
    try:
        return from_excel(value, epoch=epoch)
    except (OverflowError, ValueError):
        return value
