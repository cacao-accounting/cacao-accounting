# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2065: las tablas administrativas no muestran booleanos crudos."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting" / "admin" / "templates" / "admin"


def test_ledger_mapping_muestra_estado_traducido():
    fuente = (RAIZ / "ledger_mapping_rules.html").read_text(encoding="utf-8")
    assert "{{ rule.is_active }}" not in fuente
    assert "_('Activo') if rule.is_active else _('Inactivo')" in fuente


def test_price_lists_muestra_booleanos_traducidos():
    fuente = (RAIZ / "price_lists.html").read_text(encoding="utf-8")
    for campo in ("is_buying", "is_selling", "is_default"):
        assert f"{{{{ price_list.{campo} }}}}" not in fuente
        assert f"price_list.{campo} else _('No')" in fuente
