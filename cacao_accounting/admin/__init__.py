"""Fachada de compatibilidad para el módulo admin."""

from __future__ import annotations

from typing import Any

from cacao_accounting.admin import routes as _routes
from cacao_accounting.admin import services as _services

from cacao_accounting.admin.routes import (  # noqa: F401
    admin as admin,
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
