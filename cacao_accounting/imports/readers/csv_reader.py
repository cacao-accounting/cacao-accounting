# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos CSV."""

import csv
from typing import Any, TextIO
from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable
from cacao_accounting.imports.readers.limits import ImportReadLimitError, ReadBudget, validate_file_size


class CSVReader(BaseReader):
    """Lee archivos CSV."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee un archivo CSV y devuelve una NormalizedTable."""
        validate_file_size(file_path)
        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            # Intentar detectar el delimitador (normalmente , o ;)
            dialect: Any
            try:
                sample = f.read(1024)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            except csv.Error:
                dialect = csv.get_dialect("excel")  # Fallback a coma

            _validate_shape(f, dialect)
            f.seek(0)
            reader = csv.reader(f, dialect=dialect)
            try:
                columns = next(reader)
            except StopIteration:
                return NormalizedTable(source_format="csv", columns=[], rows=[])
            except csv.Error as exc:
                if str(exc).startswith("field larger than field limit"):
                    raise ImportReadLimitError() from exc
                raise
            try:
                budget = ReadBudget()
                budget.consume_header(len(columns))
                rows = []
                for row in reader:
                    budget.consume_row(len(row))
                    rows.append(row)
            except csv.Error as exc:
                if str(exc).startswith("field larger than field limit"):
                    raise ImportReadLimitError() from exc
                raise
            return NormalizedTable(columns=columns, rows=rows, source_format="csv")


def _validate_shape(file: TextIO, dialect: Any) -> None:
    """Rechaza filas anchas antes de que csv.reader construya sus listas."""
    validator = _CSVShapeValidator(dialect)
    while chunk := file.read(64 * 1024):
        for character in chunk:
            validator.consume(character)
    validator.finish()


class _CSVShapeValidator:
    """Cuenta campos y filas aplicando las reglas de comillas del dialecto."""

    def __init__(self, dialect: Any) -> None:
        """Inicia el estado del preflight CSV."""
        self.budget = ReadBudget()
        self.delimiter = dialect.delimiter
        self.quotechar = dialect.quotechar
        self.escapechar = dialect.escapechar
        self.doublequote = dialect.doublequote
        self.skipinitialspace = dialect.skipinitialspace
        self.in_quotes = False
        self.quote_pending = False
        self.escaped = False
        self.at_field_start = True
        self.field_count = 1
        self.has_record = False
        self.has_header = False

    def consume(self, character: str) -> None:
        """Consume un carácter del archivo sin almacenar el registro."""
        if self.in_quotes:
            self._consume_quoted(character)
        else:
            self._consume_unquoted(character)

    def _consume_quoted(self, character: str) -> None:
        """Procesa caracteres internos y el cierre de un campo citado."""
        self.has_record = True
        if self.escaped:
            self.escaped = False
        elif self.escapechar and character == self.escapechar:
            self.escaped = True
        elif self.quote_pending:
            self._consume_after_quote(character)
        elif character == self.quotechar:
            self.quote_pending = True

    def _consume_after_quote(self, character: str) -> None:
        """Resuelve comillas duplicadas o continúa después de cerrar el campo."""
        if self.doublequote and character == self.quotechar:
            self.quote_pending = False
            return
        self.in_quotes = False
        self.quote_pending = False
        if character == self.delimiter:
            self._next_field()
        elif character == "\n":
            self._finish_record()
        else:
            self.at_field_start = False

    def _consume_unquoted(self, character: str) -> None:
        """Procesa delimitadores, comienzos de cita y saltos de registro."""
        if character == "\n":
            self._finish_record()
            return
        self.has_record = True
        if self.quotechar and character == self.quotechar and self.at_field_start:
            self.in_quotes = True
        elif character == self.delimiter:
            self._next_field()
        elif not (self.skipinitialspace and self.at_field_start and character == " "):
            self.at_field_start = False

    def _next_field(self) -> None:
        """Cuenta el siguiente campo y comprueba el límite inmediatamente."""
        self.field_count += 1
        self.budget.check_columns(self.field_count)
        self.at_field_start = True

    def _finish_record(self) -> None:
        """Aplica el presupuesto de encabezado o fila y reinicia el contador."""
        columns = self.field_count if self.has_record else 0
        if self.has_header:
            self.budget.consume_row(columns)
        else:
            self.budget.consume_header(columns)
            self.has_header = True
        self.field_count = 1
        self.at_field_start = True
        self.has_record = False

    def finish(self) -> None:
        """Valida el último registro cuando el archivo no termina en salto."""
        if self.has_record or self.quote_pending:
            self._finish_record()
