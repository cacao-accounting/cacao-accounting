# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los nombres accesibles de navegación son traducibles.

Escenario de negocio (issue #2027 y residual de QA): 156 plantillas publicaban
literalmente ``aria-label="breadcrumb"``; los lectores de pantalla recibían
texto inglés en español.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path("cacao_accounting")


def test_no_quedan_nombres_literales_sin_gettext():
    """Ninguna plantilla conserva el literal inglés."""
    ofensores = [
        str(archivo) for archivo in RAIZ.rglob("*.html") if 'aria-label="breadcrumb"' in archivo.read_text(encoding="utf-8")
    ]

    assert ofensores == []


def test_las_plantillas_usan_la_cadena_traducible():
    """El reemplazo llegó a los templates que tienen navegación."""
    con_cadena = [archivo for archivo in RAIZ.rglob("*.html") if "Ruta de navegación" in archivo.read_text(encoding="utf-8")]

    assert len(con_cadena) >= 150
