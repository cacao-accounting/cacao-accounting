# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Helpers for reading indexed line rows from submitted forms."""

from collections.abc import Mapping
from typing import Any


def form_line_indexes(form: Mapping[str, Any], prefix: str) -> list[int]:
    """Return unique numeric row indexes submitted for ``prefix``, in order.

    Gaps are valid because users may leave empty rows in a transaction grid.
    Numeric aliases such as ``01`` map to the same row as ``1``. Very long
    decimal suffixes that Python cannot safely convert are ignored.
    """
    indexes: set[int] = set()
    field_prefix = f"{prefix}_"
    for key in form:
        if not key.startswith(field_prefix):
            continue
        suffix = key[len(field_prefix) :]
        if not suffix.isdigit():
            continue
        try:
            indexes.add(int(suffix))
        except ValueError:
            continue
    return sorted(indexes)


def form_line_items(form: Mapping[str, Any], prefix: str) -> list[tuple[int, str]]:
    """Return non-empty indexed rows for ``prefix`` without truncating gaps."""
    rows: list[tuple[int, str]] = []
    for index in form_line_indexes(form, prefix):
        value = str(form.get(f"{prefix}_{index}") or "")
        if value.strip():
            rows.append((index, value))
    return rows
