"""Fachada de compatibilidad para el módulo ventas."""

from __future__ import annotations

from typing import Any

from cacao_accounting.ventas import routes as _routes
from cacao_accounting.ventas import services as _services

from cacao_accounting.ventas.routes import (  # noqa: F401
    ventas as ventas,
)

from cacao_accounting.ventas.services import (  # noqa: F401
    _cancel_linked_delivery_note as _cancel_linked_delivery_note,
    _create_delivery_note_from_invoice as _create_delivery_note_from_invoice,
    _persist_sales_reversal_relation as _persist_sales_reversal_relation,
    _release_reservation_for_delivery_note as _release_reservation_for_delivery_note,
    _release_reservation_for_sales_order as _release_reservation_for_sales_order,
    _restore_reservation_for_delivery_note as _restore_reservation_for_delivery_note,
    _validate_and_reserve_stock_for_sales_order as _validate_and_reserve_stock_for_sales_order,
    _validate_credit_limit_and_overdue as _validate_credit_limit_and_overdue,
    _validate_invoice_prices_against_source as _validate_invoice_prices_against_source,
    _validate_reversal_of as _validate_reversal_of,
    _validate_sales_invoice_quantities as _validate_sales_invoice_quantities,
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
