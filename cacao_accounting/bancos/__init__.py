"""Fachada de compatibilidad para el módulo bancos."""

from __future__ import annotations

from typing import Any

from cacao_accounting.bancos import routes as _routes
from cacao_accounting.bancos import services as _services

from cacao_accounting.bancos.routes import (  # noqa: F401
    bancos as bancos,
)

from cacao_accounting.bancos.services import (  # noqa: F401
    _apply_payment_cancellation_hooks as _apply_payment_cancellation_hooks,
    _validate_payment_header as _validate_payment_header,
    create_default_petty_cash as create_default_petty_cash,
    create_petty_cash_account as create_petty_cash_account,
    petty_cash_accounts as petty_cash_accounts,
    petty_cash_ledger_balance as petty_cash_ledger_balance,
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
