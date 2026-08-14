"""Shared fiscal policy helpers used by previews, persistence, and engines."""

from __future__ import annotations


def affects_inventory_from_treatment(accounting_treatment: str | None) -> bool:
    """Return whether a fiscal component is capitalized into inventory."""
    return accounting_treatment == "capitalizable_inventory_cost"
