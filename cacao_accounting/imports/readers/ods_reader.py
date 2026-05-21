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
            row_data = []
            cells = row.getElementsByType(table.TableCell)

            # ODS can have repeated empty cells, we need to respect the table structure
            for cell in cells:
                repeated = int(cell.getAttribute("numbercolumnsrepeated") or 1)

                # Get the value based on type
                value = None
                value_type = cell.getAttribute("valuetype")

                if value_type == "float":
                    value = cell.getAttribute("value")
                elif value_type == "date":
                    value = cell.getAttribute("datevalue")
                elif value_type == "boolean":
                    value = cell.getAttribute("booleanvalue")
                else:
                    # Fallback to text content
                    text_nodes = cell.getElementsByType(opendocument.teletype.Text)
                    value = "".join([opendocument.teletype.extractText(node) for node in text_nodes])

                for _ in range(repeated):
                    row_data.append(value or "")

            if any(v != "" for v in row_data):
                rows_data.append(row_data)

        if not rows_data:
            return NormalizedTable(source_format="ods", columns=[], rows=[])

        columns = [str(c) for c in rows_data[0]]
        rows = rows_data[1:]

        # Filter empty columns if header was empty
        # Also ensure all rows have same length as columns
        valid_cols = []
        col_indices = []
        for i, col in enumerate(columns):
            if col:
                valid_cols.append(col)
                col_indices.append(i)

        final_rows = []
        for r in rows:
            final_rows.append([r[i] if i < len(r) else "" for i in col_indices])

        return NormalizedTable(columns=valid_cols, rows=final_rows, source_format="ods")
