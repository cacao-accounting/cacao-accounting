"""Load the built-in read-only query handlers exactly once."""

from __future__ import annotations

from importlib import import_module

_HANDLER_MODULES = (
    "companies",
    "discovery",
    "accounting",
    "banking",
    "receivables",
    "payables",
    "documents",
    "audit_trail",
    "advanced",
    "analytics",
    "operational",
    "treasury",
)


def load_query_tools() -> None:
    """Register all built-in handlers in the shared global registry."""
    for module_name in _HANDLER_MODULES:
        import_module(f"cacao_accounting.query_tools.handlers.{module_name}")
