# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Clase base para lectores de archivos."""

from dataclasses import dataclass, field
from typing import List, Any


@dataclass
class NormalizedTable:
    """Representa una tabla de datos normalizada."""

    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    source_format: str = ""


class BaseReader:
    """Interfaz base para lectores de archivos."""

    def read(self, file_path: str) -> NormalizedTable:
        """Lee un archivo y devuelve una NormalizedTable."""
        raise NotImplementedError("Subclasses must implement read()")
