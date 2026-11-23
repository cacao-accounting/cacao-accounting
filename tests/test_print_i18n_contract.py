# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1932: las plantillas base y las etiquetas de estado pasan por gettext."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_plantillas_base_marcan_las_etiquetas_visibles():
    """Description, Qty y Printed by deben renderizarse con `_()`."""
    semilla = (RAIZ / "cacao_accounting" / "printing" / "seed.py").read_text(encoding="utf-8")

    for etiqueta in ("Description", "Qty", "Printed by"):
        assert f'{{{{ _("{etiqueta}") }}}}' in semilla


def test_etiquetas_de_estado_usan_gettext():
    """Los estados visibles en el documento no son literales fijos."""
    servicio = (RAIZ / "cacao_accounting" / "printing" / "service.py").read_text(encoding="utf-8")

    for estado in ("BORRADOR", "CONTABILIZADO", "APROBADO", "ANULADO"):
        assert f'_("{estado}")' in servicio


def test_catalogo_ingles_tiene_traduccion_para_las_etiquetas():
    """Cada etiqueta usada por impresión tiene msgstr en inglés."""
    catalogo = (RAIZ / "cacao_accounting" / "translations" / "en" / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")

    for etiqueta in ("BORRADOR", "CONTABILIZADO", "APROBADO", "ANULADO", "Description", "Qty", "Printed by"):
        assert f'msgid "{etiqueta}"' in catalogo
