"""Fachada de compatibilidad para los reportes y sus rutas HTTP.

La lógica de dominio se mantiene en :mod:`reportes.services`, los auxiliares
de presentación en :mod:`reportes.helpers` y los controladores en
:mod:`reportes.routes`. La resolución delegada conserva los imports históricos
sin acoplar esta fachada a cada símbolo interno.
"""

from __future__ import annotations

from typing import Any

from cacao_accounting.reportes import helpers as _helpers
from cacao_accounting.reportes import routes as _routes
from cacao_accounting.reportes import services as _services

reportes = _routes.reportes

_MODULES = (_services, _helpers, _routes)
__all__ = tuple(
    dict.fromkeys(
        (
            "reportes",
            *(name for module in _MODULES for name in getattr(module, "__all__", dir(module)) if not name.startswith("_")),
        )
    )
)


def __getattr__(name: str) -> Any:
    """Devuelve un símbolo histórico desde el submódulo que lo implementa."""
    for module in _MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Enumera los símbolos propios y los mantenidos por compatibilidad."""
    return sorted(set(globals()) | set(__all__) | set(dir(_helpers)))
