"""Utilidades de paginación para resultados de herramientas de consulta."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Any

from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500


@dataclass
class PaginatedResult:
    """Resultado paginado que encapsula ítems, metadatos de página y totales."""

    page: int
    page_size: int
    total_items: int
    items: list[Any] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        """Calcula el número total de páginas redondeando hacia arriba."""
        return max(1, ceil(self.total_items / self.page_size))

    @property
    def has_next_page(self) -> bool:
        """Indica si existe una página siguiente después de la actual."""
        return self.page < self.total_pages

    def to_dict(self) -> dict[str, Any]:
        """Convierte el resultado paginado a un diccionario serializable."""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total_items": self.total_items,
            "total_pages": self.total_pages,
            "has_next_page": self.has_next_page,
            "items": self.items,
        }


def paginate(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[int, int]:
    """Valida y normaliza los parámetros de paginación, lanzando error si se excede el máximo."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    if page_size > MAX_PAGE_SIZE:
        raise QueryToolError(
            code=ErrorCode.PAGE_SIZE_EXCEEDED,
            message=f"El tamaño de página no puede exceder {MAX_PAGE_SIZE}.",
        )
    return page, page_size
