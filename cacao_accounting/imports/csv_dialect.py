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
ALLOWED_DELIMITERS = ",;"


class ImportCSVFormatError(ValueError):
    """El contenido CSV usa una tabulación como delimitador."""

    def __init__(self) -> None:
        """Construye el error con su mensaje traducible."""
        super().__init__(_("El archivo CSV usa tabulaciones fuera de un campo entrecomillado."))


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

    def __init__(self, quotechar: str, escapechar: str | None, doublequote: bool) -> None:
        """Inicia el estado de comillas y escapes del dialecto."""
        self.quotechar = quotechar
        self.escapechar = escapechar
        self.doublequote = doublequote
        self.in_quotes = False
        self.quote_pending = False
        self.escaped = False

    def consume(self, character: str) -> bool:
        """Indica si el carácter es una tabulación fuera de un campo citado."""
        if self.escaped:
            self.escaped = False
            return False
        if self.escapechar and character == self.escapechar:
            self.escaped = True
            return False
        if self.in_quotes:
            self._consume_quoted(character)
            return False
        if character == "\t":
            return True
        if self.quotechar and character == self.quotechar:
            self.in_quotes = True
        return False

    def _consume_quoted(self, character: str) -> None:
        """Resuelve cierres y comillas duplicadas dentro del campo citado."""
        if self.quote_pending:
            if self.doublequote and character == self.quotechar:
                self.quote_pending = False
            else:
                self.in_quotes = False
                self.quote_pending = False
        elif character == self.quotechar:
            self.quote_pending = True


def contains_unquoted_tab(sample: str, dialect: Any) -> bool:
    """Indica si alguna tabulación de la muestra queda fuera de las comillas."""
    scanner = _QuoteScanner(dialect.quotechar or '"', dialect.escapechar, dialect.doublequote)
    return any(scanner.consume(character) for character in sample[:CSV_SAMPLE_CHARS])
