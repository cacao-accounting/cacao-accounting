# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Contrato compartido de detección de dialectos CSV.

La carga y el lector deben oler el delimitador sobre la misma muestra y
aplicar la misma regla de tabulaciones: solo se admiten dentro de un campo
entrecomillado, nunca como separador encubierto de un TSV.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from cacao_accounting.i18n import _

CSV_SAMPLE_CHARS = 2048
# UTF-8 necesita hasta 4 bytes por carácter: esta ventana garantiza la muestra
# completa incluso cuando el archivo usa caracteres multibyte.
CSV_SAMPLE_BYTES = CSV_SAMPLE_CHARS * 4
ALLOWED_DELIMITERS = ",;"


class ImportCSVFormatError(ValueError):
    """El contenido CSV usa una tabulación como delimitador."""

    def __init__(self) -> None:
        """Construye el error con su mensaje traducible."""
        super().__init__(_("El archivo CSV usa tabulaciones fuera de un campo entrecomillado."))


def csv_sample_from_bytes(chunk: bytes) -> str:
    """Decodifica la ventana de bytes y devuelve la muestra textual acordada."""
    window = chunk[:CSV_SAMPLE_BYTES]
    # Un corte de bytes puede dejar un carácter UTF-8 incompleto al final;
    # se prueban los últimos tres bytes antes de declarar el contenido inválido.
    for trim in range(4):
        candidate = window if trim == 0 else window[:-trim]
        try:
            return candidate.decode("utf-8-sig")[:CSV_SAMPLE_CHARS]
        except UnicodeDecodeError:
            continue
    return window.decode("utf-8-sig")[:CSV_SAMPLE_CHARS]


def sniff_csv_dialect(sample: str) -> Any:
    """Detecta el dialecto sobre la muestra acordada, con coma por defecto."""
    try:
        return csv.Sniffer().sniff(sample[:CSV_SAMPLE_CHARS], delimiters=ALLOWED_DELIMITERS)
    except csv.Error:
        return csv.get_dialect("excel")


def parse_csv_rows(text: str, dialect: Any) -> list[list[str]]:
    """Parsea el texto completo con el dialecto ya detectado."""
    return list(csv.reader(io.StringIO(text), dialect))


class _QuoteScanner:
    """Recorre la muestra para distinguir tabulaciones citadas de separadores."""

    def __init__(
        self,
        delimiter: str,
        quotechar: str,
        escapechar: str | None,
        doublequote: bool,
        skipinitialspace: bool,
    ) -> None:
        """Inicia el estado de comillas, escapes y comienzo de campo."""
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.escapechar = escapechar
        self.doublequote = doublequote
        self.skipinitialspace = skipinitialspace
        self.in_quotes = False
        self.quote_pending = False
        self.escaped = False
        self.at_field_start = True

    def consume(self, character: str) -> bool:
        """Indica si el carácter es una tabulación fuera de un campo citado."""
        if self.escaped:
            self.escaped = False
            self.at_field_start = False
            return False
        if self.escapechar and character == self.escapechar:
            self.escaped = True
            return False
        if self.in_quotes and self._consume_quoted(character):
            return False
        return self._consume_unquoted(character)

    def _consume_unquoted(self, character: str) -> bool:
        """Evalúa un carácter fuera de comillas y reporta tabulaciones."""
        if character == "\t":
            self.at_field_start = False
            return True
        if character in ("\n", "\r"):
            self.at_field_start = True
            return False
        if character == self.delimiter:
            self.at_field_start = True
            return False
        if self.skipinitialspace and self.at_field_start and character == " ":
            return False
        if self.quotechar and character == self.quotechar and self.at_field_start:
            self.in_quotes = True
            return False
        self.at_field_start = False
        return False

    def _consume_quoted(self, character: str) -> bool:
        """Procesa el carácter citado e indica si el campo sigue entrecomillado."""
        if self.quote_pending:
            if self.doublequote and character == self.quotechar:
                self.quote_pending = False
                return True
            self.in_quotes = False
            self.quote_pending = False
        elif character == self.quotechar:
            self.quote_pending = True
        return self.in_quotes


def contains_unquoted_tab(sample: str, dialect: Any) -> bool:
    """Indica si alguna tabulación de la muestra queda fuera de las comillas."""
    scanner = _QuoteScanner(
        dialect.delimiter,
        dialect.quotechar or '"',
        dialect.escapechar,
        dialect.doublequote,
        bool(dialect.skipinitialspace),
    )
    return any(scanner.consume(character) for character in sample[:CSV_SAMPLE_CHARS])
