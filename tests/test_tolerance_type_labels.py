# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2067: las tablas de tolerancias muestran etiquetas, no códigos crudos."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting" / "admin" / "templates" / "admin"
PLANTILLAS = ("purchase_reconciliation_config.html", "sales_matching_config.html")


def test_tablas_de_tolerancia_usan_etiquetas():
    """`percentage`/`absolute` se traducen en precio y cantidad."""
    for nombre in PLANTILLAS:
        fuente = (RAIZ / nombre).read_text(encoding="utf-8")
        assert 'tolerance_labels = {"percentage": "%", "absolute": _("Absoluto")}' in fuente
        assert "{{ cfg.price_tolerance_type }}" not in fuente
        assert "tolerance_labels.get(cfg.price_tolerance_type" in fuente
        if nombre.startswith("purchase"):
            assert "{{ cfg.qty_tolerance_type }}" not in fuente
            assert "tolerance_labels.get(cfg.qty_tolerance_type" in fuente
