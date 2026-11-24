# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2001: la portada de documentación enlaza instalación y CLI correctamente."""

from __future__ import annotations

from pathlib import Path

HOME = Path(__file__).resolve().parents[1] / "docs" / "theme_override_home" / "home.html"


def test_la_portada_enlaza_la_guia_de_instalacion_vigente():
    """El botón de instalación no apunta a la ruta 404."""
    html = HOME.read_text(encoding="utf-8")

    assert "/despliegue/" not in html
    assert "https://cacao-accounting.github.io/cacao-accounting/setup/" in html


def test_la_tarjeta_cli_documenta_el_cli():
    """La tarjeta CLI enlaza cacaoctl y no presenta cobertura ni la errata."""
    html = HOME.read_text(encoding="utf-8")

    assert "covertura" not in html.lower()
    assert "app.codecov.io" not in html
    assert "https://cacao-accounting.github.io/cacao-accounting/cacaoctl/" in html
