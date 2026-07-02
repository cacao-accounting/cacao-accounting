# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos CSV."""

import csv
from typing import Any
from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable


class CSVReader(BaseReader):
    """Lee archivos CSV."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee un archivo CSV y devuelve una NormalizedTable."""
        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            # Intentar detectar el delimitador (normalmente , o ;)
            dialect: Any
            try:
                sample = f.read(1024)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            except Exception:
                dialect = "excel"  # Fallback a coma

            reader = csv.reader(f, dialect=dialect)
            try:
                columns = next(reader)
            except StopIteration:
                return NormalizedTable(source_format="csv", columns=[], rows=[])
            rows = list(reader)
            return NormalizedTable(columns=columns, rows=rows, source_format="csv")
