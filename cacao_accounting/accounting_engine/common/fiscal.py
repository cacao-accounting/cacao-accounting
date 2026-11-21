# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Shared fiscal policy helpers used by previews, persistence, and engines."""

from __future__ import annotations

from collections.abc import Iterable

SUPPORTED_TAX_CALCULATION_METHODS = frozenset({"percentage", "fixed", "manual"})


def find_duplicate_rule_id(values: Iterable[str | None]) -> str | None:
    """Devuelve el primer identificador fiscal repetido, ignorando vacíos."""
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        if normalized in seen:
            return normalized
        seen.add(normalized)
    return None


def affects_inventory_from_treatment(accounting_treatment: str | None) -> bool:
    """Return whether a fiscal component is capitalized into inventory."""
    return accounting_treatment == "capitalizable_inventory_cost"
