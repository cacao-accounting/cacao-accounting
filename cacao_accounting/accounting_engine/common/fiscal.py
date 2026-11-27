# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Shared fiscal policy helpers used by previews, persistence, and engines."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from cacao_accounting.i18n import _

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


def calculate_accumulated_tax_base(
    default_base: Decimal,
    concept_amounts: Mapping[str, Decimal],
    include_concepts: Sequence[str],
    exclude_concepts: Sequence[str],
) -> Decimal:
    """Resolve an accumulated tax base, applying exclusions even without inclusions."""
    if include_concepts:
        base = sum((concept_amounts.get(concept, Decimal("0")) for concept in include_concepts), Decimal("0"))
    else:
        base = default_base
    excluded_amount = sum((concept_amounts.get(concept, Decimal("0")) for concept in exclude_concepts), Decimal("0"))
    return base - excluded_amount


def has_negative_tax_amounts(*values: Decimal) -> bool:
    """Return whether a manual tax line contains a negative amount or rate."""
    return any(value < 0 for value in values)


def negative_manual_tax_amount_message() -> str:
    """Return the shared validation message for negative manual tax values."""
    return _("Las l\u00edneas fiscales manuales no pueden contener importes negativos.")
