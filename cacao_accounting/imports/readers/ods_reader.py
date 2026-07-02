# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos ODS."""

from odf import opendocument, table
from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable


class ODSReader(BaseReader):
    """Lee archivos ODS usando odfpy."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee un archivo ODS y devuelve una NormalizedTable."""
        doc = opendocument.load(file_path)
        spreadsheet = doc.spreadsheet.getElementsByType(table.Table)[0]
        rows_data = []

        for row in spreadsheet.getElementsByType(table.TableRow):
            row_data = self._extract_row_data(row)
            if row_data and any(v != "" for v in row_data):
                rows_data.append(row_data)

        if not rows_data:
            return NormalizedTable(source_format="ods", columns=[], rows=[])

        columns = [str(c) for c in rows_data[0]]
        rows = rows_data[1:]
        valid_cols, col_indices = self._compute_valid_columns(columns, rows)

        final_rows = []
        for r in rows:
            final_rows.append([r[i] if i < len(r) else "" for i in col_indices])

        return NormalizedTable(columns=valid_cols, rows=final_rows, source_format="ods")

    def _extract_row_data(self, row: table.TableRow) -> list:
        """Extrae los datos de una fila de tabla ODS."""
        row_data = []
        for cell in row.getElementsByType(table.TableCell):
            value = self._extract_cell_value(cell)
            repeated = int(cell.getAttribute("numbercolumnsrepeated") or 1)
            for _ in range(repeated):
                row_data.append(value or "")
        return row_data

    def _extract_cell_value(self, cell: table.TableCell) -> str | None:
        """Extrae el valor de una celda ODS según su tipo."""
        value_type = cell.getAttribute("valuetype")

        if value_type == "float":
            return cell.getAttribute("value")
        if value_type == "date":
            return cell.getAttribute("datevalue")
        if value_type == "boolean":
            return cell.getAttribute("booleanvalue")

        text_nodes = cell.getElementsByType(opendocument.teletype.Text)
        return "".join(opendocument.teletype.extractText(node) for node in text_nodes)

    def _compute_valid_columns(self, columns: list, rows: list) -> tuple[list, list]:
        """Calcula los índices de columnas válidas (no vacías)."""
        valid_cols = []
        col_indices = []
        for i, col in enumerate(columns):
            if col:
                valid_cols.append(col)
                col_indices.append(i)
        return valid_cols, col_indices
