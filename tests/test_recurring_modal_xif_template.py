# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2162: el modal de línea recurrente usa `x-if` sobre `<template>`."""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "cacao_accounting"
    / "contabilidad"
    / "templates"
    / "contabilidad"
    / "recurring_journal_nuevo.html"
)


def test_x_if_solo_se_aplica_a_templates():
    """Alpine 3 exige `<template>`; un `div` con `x-if` no construye el modal."""
    source = TEMPLATE.read_text(encoding="utf-8")

    tags_with_x_if = re.findall(r"<([a-zA-Z0-9-]+)[^>]*\sx-if=", source)

    assert tags_with_x_if, "La plantilla debe conservar el modal condicional"
    assert set(tags_with_x_if) == {"template"}
    assert '<template x-if="modalLine">' in source
    assert '<div class="modal-content" x-if="modalLine">' not in source
