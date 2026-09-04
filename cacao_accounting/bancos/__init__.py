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
    cancel_petty_cash_expense as cancel_petty_cash_expense,
    create_default_petty_cash as create_default_petty_cash,
    create_petty_cash_account as create_petty_cash_account,
    create_petty_cash_expense as create_petty_cash_expense,
    create_petty_cash_expense_from_voucher as create_petty_cash_expense_from_voucher,
    create_petty_cash_reconciliation as create_petty_cash_reconciliation,
    create_petty_cash_replenishment as create_petty_cash_replenishment,
    create_petty_cash_voucher as create_petty_cash_voucher,
    petty_cash_accounts as petty_cash_accounts,
    petty_cash_expenses as petty_cash_expenses,
    petty_cash_ledger_balance as petty_cash_ledger_balance,
    petty_cash_expenses_available_for_replenishment as petty_cash_expenses_available_for_replenishment,
    petty_cash_open_vouchers_total as petty_cash_open_vouchers_total,
    petty_cash_pending_replenishment_total as petty_cash_pending_replenishment_total,
    petty_cash_replenishment_expenses as petty_cash_replenishment_expenses,
    petty_cash_vouchers as petty_cash_vouchers,
    petty_cash_vouchers_for_fund as petty_cash_vouchers_for_fund,
    set_petty_cash_voucher_status as set_petty_cash_voucher_status,
    set_petty_cash_replenishment_status as set_petty_cash_replenishment_status,
    reconcile_petty_cash as reconcile_petty_cash,
    post_petty_cash_reconciliation_adjustment as post_petty_cash_reconciliation_adjustment,
    replenish_petty_cash as replenish_petty_cash,
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
