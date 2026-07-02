# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Clase base para adaptadores de importación."""

from typing import List, Dict, Any


class BaseImportAdapter:
    """Interfaz base para adaptadores de importación."""

    columns: List[str] = []
    required_columns: List[str] = []

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Valida una fila individual. Retorna lista de errores."""
        errors = []

        # Protección contra inyección de fórmulas
        for key, value in row_data.items():
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                errors.append(f"Fórmula detectada en columna '{key}': {value}. Las fórmulas no están permitidas.")

        for col in self.required_columns:
            if col not in row_data or row_data[col] in (None, ""):
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
