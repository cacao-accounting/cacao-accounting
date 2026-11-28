# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Fachada de compatibilidad para el módulo contabilidad."""

from __future__ import annotations

from typing import Any

from cacao_accounting.contabilidad import routes as _routes
from cacao_accounting.contabilidad import services as _services

from cacao_accounting.contabilidad.routes import (  # noqa: F401
    contabilidad as contabilidad,
)
from cacao_accounting.audit_trail_service import log_submit  # noqa: F401

_MODULES = (_services, _routes)

# Contrato histórico de la fachada: el import wildcard debe exponer los
# símbolos públicos que el módulo monolítico ofrecía, incluido `log_submit`.
__all__ = sorted(
    {
        "contabilidad",
        "log_submit",
        *(name for module in _MODULES for name in dir(module) if not name.startswith("_")),
    }
)


def __getattr__(name: str) -> Any:
    """Devuelve un símbolo histórico desde su módulo extraído."""
    for module in _MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Enumera símbolos propios y los mantenidos por compatibilidad."""
    return sorted(set(globals()) | {name for module in _MODULES for name in dir(module)})
