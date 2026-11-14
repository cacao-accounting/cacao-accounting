# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Lector de archivos ODS."""

from xml.sax import make_parser
from xml.sax.handler import ContentHandler, feature_external_ges, feature_namespaces
from xml.sax.xmlreader import AttributesNSImpl
from zipfile import ZipFile

from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable
from cacao_accounting.imports.readers.limits import (
    MAX_IMPORT_ARCHIVE_BYTES,
    MAX_IMPORT_TEXT_CHARS,
    ImportReadLimitError,
    ReadBudget,
    validate_archive_size,
)

TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
TABLE = (TABLE_NS, "table")
ROW = (TABLE_NS, "table-row")
CELL = (TABLE_NS, "table-cell")
COVERED_CELL = (TABLE_NS, "covered-table-cell")
MAX_IMPORT_XML_DEPTH = 256


class ODSReader(BaseReader):
    """Lee archivos ODS mediante el XML incremental del contenedor."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee la primera tabla sin construir el árbol XML completo."""
        validate_archive_size(file_path)
        with ZipFile(file_path) as archive, archive.open("content.xml") as content:
            parser = make_parser()
            parser.setFeature(feature_namespaces, True)
            parser.setFeature(feature_external_ges, False)
            handler = _ODSContentParser()
            parser.setContentHandler(handler)
            parser.parse(content)
            return NormalizedTable(columns=handler.columns, rows=handler.rows, source_format="ods")


class _ODSContentParser(ContentHandler):
    """Mantiene un estado acotado mientras recorre eventos de content.xml."""

    def __init__(self) -> None:
        """Inicia el parser sin materializar nodos fuera de la fila actual."""
        super().__init__()
        self.budget = ReadBudget()
        self.columns: list[str] = []
        self.rows: list[list[str]] = []
        self.row_data: list[str] | None = None
        self.row_depth = 0
        self.row_repeat = 1
        self.header_seen = False
        self.spreadsheet_depth = 0
        self.table_depth = 0
        self.table_seen = False
        self.cell_depth = 0
        self.cell_repeat = 1
        self.cell_type = ""
        self.cell_attribute_value = ""
        self.cell_uses_attribute = False
        self.cell_pieces: list[str] = []
        self.text_characters = 0
        self.ignored_text_depth = 0
        self.element_stack: list[tuple[str | None, str]] = []

    def startElementNS(self, name, qname, attributes: AttributesNSImpl) -> None:
        """Registra tabla, fila, celda y elementos de texto al entrar."""
        self.element_stack.append(name)
        if len(self.element_stack) > MAX_IMPORT_XML_DEPTH:
            raise ImportReadLimitError()
        depth = len(self.element_stack)
        if name == (OFFICE_NS, "spreadsheet"):
            self.spreadsheet_depth = depth
        elif name == TABLE and self.spreadsheet_depth and not self.table_seen:
            self.table_depth = depth
            self.table_seen = True
        elif name == ROW and self.table_depth and self.row_data is None:
            self.row_data = []
            self.row_depth = depth
            self.row_repeat = _repeat(attributes, "number-rows-repeated")
        elif name in (CELL, COVERED_CELL) and self._is_direct_cell():
            self._start_cell(name, attributes, depth)
        elif self.cell_depth and not self.cell_uses_attribute:
            self._start_text_element(name, attributes, depth)

    def endElementNS(self, name, qname) -> None:
        """Completa celdas y filas, y libera el estado XML ya procesado."""
        depth = len(self.element_stack)
        if name in (CELL, COVERED_CELL) and depth == self.cell_depth:
            self._finish_cell()
        elif name == ROW and depth == self.row_depth:
            self._finish_row()
        elif depth == self.ignored_text_depth:
            self.ignored_text_depth = 0
        if name == TABLE and depth == self.table_depth:
            self.table_depth = 0
        if name == (OFFICE_NS, "spreadsheet"):
            self.spreadsheet_depth = 0
        if self.element_stack:
            self.element_stack.pop()

    def characters(self, content: str) -> None:
        """Acumula texto de celda con una cota antes de conservar cada bloque."""
        if not self.cell_depth or self.cell_uses_attribute or self.ignored_text_depth or not content:
            return
        self._append_cell_text(content)

    def _is_direct_cell(self) -> bool:
        """Acepta celdas directas de la fila actual, sin entrar en tablas anidadas."""
        return self.row_data is not None and self.element_stack[-2] == ROW

    def _start_cell(self, name, attributes: AttributesNSImpl, depth: int) -> None:
        """Prevalida ancho de celda y prepara el acumulador de texto."""
        self.cell_depth = depth
        self.cell_repeat = _repeat(attributes, "number-columns-repeated")
        assert self.row_data is not None
        self.budget.check_columns(len(self.row_data) + self.cell_repeat)
        self.cell_pieces = []
        self.cell_type = attributes.get((OFFICE_NS, "value-type"), "") if name == CELL else ""
        value_name = {
            "float": "value",
            "percentage": "value",
            "currency": "value",
            "date": "date-value",
            "time": "time-value",
            "boolean": "boolean-value",
            "string": "string-value",
        }.get(self.cell_type)
        attribute = (OFFICE_NS, value_name) if value_name else None
        self.cell_uses_attribute = False
        self.cell_attribute_value = ""
        if attribute is not None and attribute in attributes:
            self.cell_uses_attribute = True
            self.cell_attribute_value = attributes.get(attribute, "")

    def _start_text_element(self, name, attributes: AttributesNSImpl, depth: int) -> None:
        """Representa espacios, tabs y saltos según el modelo de texto ODF."""
        if name == (TEXT_NS, "s"):
            count = _space_count(attributes)
            self._append_repeated_spaces(count)
            self.ignored_text_depth = depth
        elif name == (TEXT_NS, "tab"):
            self._append_cell_text("\t")
            self.ignored_text_depth = depth
        elif name == (TEXT_NS, "line-break"):
            self._append_cell_text("\n")
            self.ignored_text_depth = depth

    def _append_cell_text(self, value: str, character_count: int | None = None) -> None:
        """Añade texto únicamente si cabe en el presupuesto total del libro."""
        count = len(value) if character_count is None else character_count
        if self.text_characters + count > MAX_IMPORT_TEXT_CHARS:
            raise ImportReadLimitError()
        self.text_characters += count
        self.cell_pieces.append(value)

    def _append_repeated_spaces(self, count: int) -> None:
        """Reserva el presupuesto antes de crear espacios repetidos."""
        if self.text_characters + count > MAX_IMPORT_TEXT_CHARS:
            raise ImportReadLimitError()
        self.text_characters += count
        self.cell_pieces.append(" " * count)

    def _finish_cell(self) -> None:
        """Añade una celda a la fila y conserva referencias para columnas repetidas."""
        value = self.cell_attribute_value if self.cell_uses_attribute else "".join(self.cell_pieces)
        if self.cell_uses_attribute:
            value_length = len(value)
            if self.text_characters + value_length > MAX_IMPORT_TEXT_CHARS:
                raise ImportReadLimitError()
            self.text_characters += value_length
        assert self.row_data is not None
        self.row_data.extend([value] * self.cell_repeat)
        self.cell_depth = 0
        self.cell_type = ""
        self.cell_attribute_value = ""
        self.cell_uses_attribute = False
        self.cell_pieces = []

    def _finish_row(self) -> None:
        """Aplica límites de fila antes de expandir repeticiones del formato ODS."""
        assert self.row_data is not None
        if not self.header_seen and self._has_data(self.row_data):
            if self.row_repeat != 1:
                raise ImportReadLimitError()
            self.columns = self.row_data
            self.budget.consume_header(len(self.columns))
            self.header_seen = True
        else:
            self.budget.consume_repeated_rows(len(self.row_data), self.row_repeat)
            if self.header_seen and self._has_data(self.row_data):
                self.rows.extend([self.row_data] * self.row_repeat)
        self.row_data = None
        self.row_depth = 0

    @staticmethod
    def _has_data(row: list[str]) -> bool:
        """Indica si una fila tiene algún valor que no sea una cadena vacía."""
        return bool(row) and any(value != "" for value in row)


def _repeat(attributes: AttributesNSImpl, attribute: str) -> int:
    """Lee una repetición positiva; valores cero y negativos son inválidos."""
    try:
        count = int(attributes.get((TABLE_NS, attribute), "1"))
    except ValueError as exc:
        raise ImportReadLimitError() from exc
    if count < 1:
        raise ImportReadLimitError()
    return count


def _space_count(attributes: AttributesNSImpl) -> int:
    """Lee la repetición de espacios ODF y previene expansiones excesivas."""
    try:
        count = int(attributes.get((TEXT_NS, "c"), "1"))
    except ValueError as exc:
        raise ImportReadLimitError() from exc
    if count < 0 or count > MAX_IMPORT_ARCHIVE_BYTES:
        raise ImportReadLimitError()
    return count
