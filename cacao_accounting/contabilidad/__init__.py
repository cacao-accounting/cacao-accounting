"""Fachada de compatibilidad para el módulo contabilidad."""

from __future__ import annotations

from typing import Any

from cacao_accounting.contabilidad import routes as _routes
from cacao_accounting.contabilidad import services as _services

from cacao_accounting.contabilidad.routes import (  # noqa: F401
    contabilidad as contabilidad,
)

_MODULES = (_services, _routes)


def __getattr__(name: str) -> Any:
    """Devuelve un símbolo histórico desde su módulo extraído."""
    for module in _MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Enumera símbolos propios y los mantenidos por compatibilidad."""
    return sorted(set(globals()) | {name for module in _MODULES for name in dir(module)})
