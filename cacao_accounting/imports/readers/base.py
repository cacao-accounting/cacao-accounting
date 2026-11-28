# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contrato común para tablas leídas desde CSV, XLS, XLSX y ODS."""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from cacao_accounting.i18n import _

DATE_COLUMN_HEADERS = {
    "date",
    "estimated_date",
    "estimated date",
    "fecha",
    "fecha_contabilizacion",
    "fecha contabilizacion",
    "fecha_estimada",
    "fecha estimada",
    "posting_date",
    "posting date",
}


def is_import_date_column(header: str) -> bool:
    """Indica si el encabezado identifica una fecha consumida por un adaptador."""
    normalized = header.removeprefix("\ufeff").strip().lower()
    return normalized in DATE_COLUMN_HEADERS


class NumericCellValue(str):
    """Texto numérico canónico que conserva que la celda de origen era numérica."""

    @classmethod
    def from_number(cls, normalized_value: str) -> "NumericCellValue":
        """Crea el marcador para una celda con valor numérico real."""
        return cls(normalized_value)


def normalize_cell_value(value: Any) -> str:
    """Devuelve cada celda como texto canónico sin interpretar formatos de negocio."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date, time)):
        if isinstance(value, datetime) and value.time() == time.min:
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return str(value)
        if number.is_finite():
            return NumericCellValue.from_number(format(number.normalize(), "f"))
    return str(value)


@dataclass
class TabularBook:
    """Representa la primera tabla de un archivo con encabezados/celdas canónicos.

    Los lectores conservan su preflight específico para que filas, columnas y
    expansiones se limiten antes de materializar datos. Esta clase armoniza los
    escalares y encabezados una vez que el lector ha producido una tabla segura.
    """

    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    source_format: str = ""

    def __post_init__(self) -> None:
        """Quita BOM de encabezados y normaliza celdas sin cambiar texto literal."""
        self.columns = [_normalize_header(column) for column in self.columns]
        self.rows = [[normalize_cell_value(value) for value in row] for row in self.rows]


def _normalize_header(value: Any) -> str:
    """Normaliza el encabezado al contrato de texto y quita el BOM inicial."""
    header = normalize_cell_value(value)
    return header.removeprefix("\ufeff")


# Compatibilidad temporal para código y pruebas que aún importan el nombre previo.
NormalizedTable = TabularBook


class BaseReader:
    """Interfaz de los lectores de importación tabular."""

    def read(self, file_path: str) -> TabularBook:
        """Lee un archivo y devuelve su tabla canónica."""
        raise NotImplementedError(_("Subclasses must implement read()"))
