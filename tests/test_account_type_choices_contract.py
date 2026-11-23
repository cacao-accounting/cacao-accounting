# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1914: todo tipo de cuenta usado por el motor existe en el formulario."""

from __future__ import annotations

import re
from pathlib import Path

from cacao_accounting.contabilidad.forms import ACCOUNT_TYPE_CHOICES

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"


def test_los_tipos_del_motor_son_editables():
    """Cada account_type del motor aparece en ACCOUNT_TYPE_CHOICES."""
    elegibles = {valor for valor, _etiqueta in ACCOUNT_TYPE_CHOICES}
    usados: set[str] = set()
    for archivo in (RAIZ / "accounting_engine").rglob("*.py"):
        usados.update(re.findall(r'account_type\s*=\s*"([a-z_]+)"', archivo.read_text(encoding="utf-8")))

    assert usados
    assert usados <= elegibles, f"tipos no editables: {sorted(usados - elegibles)}"
