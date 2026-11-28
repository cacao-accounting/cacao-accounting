# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Clase base para adaptadores de importación."""

from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Mapping, Sequence

from cacao_accounting.i18n import _
from cacao_accounting.imports.column_labels import localized_columns
from cacao_accounting.imports.utils.dates import parse_import_date

HeaderNormalizer = Callable[[Any], Any]


class BaseImportAdapter:
    """Interfaz base para adaptadores de importación."""

    columns: List[str] = []
    required_columns: List[str] = []
    column_aliases: dict[str, str] = {}

    def localized_columns(self, language: str | None) -> List[str]:
        """Return this adapter's headers in the requested language."""
        return localized_columns(self.columns, language)

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Valida una fila individual. Retorna lista de errores."""
        errors = []

        # Protección contra inyección de fórmulas
        for key, value in row_data.items():
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                errors.append(f"Fórmula detectada en columna '{key}': {value}. Las fórmulas no están permitidas.")

        for col in self.required_columns:
            value = row_data.get(col)
            if value in (None, "") or (isinstance(value, str) and not value.strip()):
                errors.append(f"Columna requerida faltante: {col}")
        return errors

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Valida un documento completo (agrupación de filas)."""
        return []

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Construye un objeto de dominio a partir de los datos."""
        raise NotImplementedError()

    def persist_document(self, document: Any) -> None:
        """Persist the document using domain services."""
        raise NotImplementedError()

    def validate_header_consistency(
        self,
        document_data: Sequence[Dict[str, Any]],
        fields: Mapping[str, tuple[Sequence[str], HeaderNormalizer]],
    ) -> List[str]:
        """Reject header values that differ among rows grouped as one document.

        Values are normalized before comparison so equivalent dates, decimal
        rates, and blank cells do not create false conflicts.
        """
        if len(document_data) < 2:
            return []

        errors: List[str] = []
        first_row = document_data[0]
        reference = first_row.get("document_ref") or first_row.get("reference") or ""
        for field, (aliases, normalizer) in fields.items():
            first_value = self._normalized_header_field(first_row, aliases, normalizer)
            for row_index, row in enumerate(document_data[1:], start=2):
                current_value = self._normalized_header_field(row, aliases, normalizer)
                if current_value == first_value:
                    continue
                source_row = getattr(row, "row_number", row_index)
                errors.append(
                    _("El campo '%(field)s' no coincide en la fila %(row)s del documento '%(document)s'.")
                    % {"field": field, "row": source_row, "document": reference}
                )
        return errors

    @staticmethod
    def _normalized_header_field(row: Dict[str, Any], aliases: Sequence[str], normalizer: HeaderNormalizer) -> Any:
        """Read and normalize one canonical header value, treating blanks alike."""
        raw_value = next((row.get(key) for key in aliases if row.get(key) not in (None, "")), None)
        if isinstance(raw_value, str):
            raw_value = raw_value.strip() or None
        if raw_value is None:
            return None
        try:
            return normalizer(raw_value)
        except (TypeError, ValueError, InvalidOperation):
            return ("invalid", str(raw_value).strip())


def normalize_header_text(value: Any) -> str:
    """Normalize text identifiers for comparison across grouped rows."""
    return str(value).strip()


def normalize_header_date(value: Any) -> Any:
    """Normalize supported spreadsheet date representations for comparison."""
    return parse_import_date(value)


def normalize_header_decimal(value: Any) -> Decimal:
    """Normalize decimal text and spreadsheet numbers for comparison."""
    result = Decimal(str(value).strip())
    if not result.is_finite():
        raise ValueError("Header values must be finite")
    return result


COMMON_DOCUMENT_HEADER_FIELDS: Mapping[str, tuple[Sequence[str], HeaderNormalizer]] = {
    "fecha": (("fecha",), normalize_header_date),
    "moneda": (("moneda",), normalize_header_text),
    "tipo_cambio": (("tipo_cambio",), normalize_header_decimal),
}
