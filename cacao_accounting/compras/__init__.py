"""Fachada de compatibilidad para el módulo compras."""

from __future__ import annotations

from typing import Any

from cacao_accounting.compras import routes as _routes
from cacao_accounting.compras import services as _services

from cacao_accounting.compras.routes import (  # noqa: F401
    compras as compras,
)

from cacao_accounting.compras.services import (  # noqa: F401
    _copy_logistics as _copy_logistics,
    _has_active_purchase_reversal_notes as _has_active_purchase_reversal_notes,
    _landed_cost_snapshot as _landed_cost_snapshot,
    _persist_purchase_reversal_relation as _persist_purchase_reversal_relation,
    _purchase_exchange_rate as _purchase_exchange_rate,
    _validate_duplicate_supplier_invoice as _validate_duplicate_supplier_invoice,
    _validate_invoice_quantities_against_receipt as _validate_invoice_quantities_against_receipt,
    _validate_invoice_requires_supplier_link as _validate_invoice_requires_supplier_link,
    _validate_purchase_reversal_of as _validate_purchase_reversal_of,
    _validate_receipt_quantities_against_po as _validate_receipt_quantities_against_po,
    _validate_supplier_invoice_flags as _validate_supplier_invoice_flags,
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
