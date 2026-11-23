# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2054: el estado operativo de la orden se muestra traducido."""

from __future__ import annotations

from pathlib import Path

PLANTILLA = Path(__file__).resolve().parents[1] / "cacao_accounting" / "ventas" / "templates" / "ventas" / "orden_venta.html"


def test_plantilla_traduce_estados_operativos():
    """El template mapea los estados persistidos a etiquetas traducibles."""
    html = PLANTILLA.read_text(encoding="utf-8")

    for estado in ("open", "partial", "closed", "cancelled"):
        assert f"'{estado}'" in html
    assert "_({" in html


def test_catalogo_ingles_tiene_las_etiquetas():
    """Cada etiqueta nueva tiene traducción inglesa."""
    raiz = Path(__file__).resolve().parents[1] / "cacao_accounting" / "translations" / "en" / "LC_MESSAGES"
    catalogo = (raiz / "messages.po").read_text(encoding="utf-8")

    for etiqueta in ("Abierta", "Parcial", "Cerrada", "Anulada"):
        assert f'msgid "{etiqueta}"' in catalogo
