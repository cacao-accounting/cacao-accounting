# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1912: el badge de permisos usa el keyword real de module_badge."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"


def test_plantilla_admin_usa_required():
    """admin.html no puede llamar module_badge con required_permission."""
    plantilla = (RAIZ / "admin" / "templates" / "admin.html").read_text(encoding="utf-8")

    assert "module_badge(" in plantilla
    assert "required_permission=" not in plantilla

