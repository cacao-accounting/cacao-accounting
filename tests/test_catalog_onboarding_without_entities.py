# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2165: los catálogos muestran onboarding cuando no hay entidades."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"
USO_SIN_LLAMADA = re.compile(r"entidades_creadas(?!\s*\()")


@pytest.mark.parametrize(
    ("ruta", "cta_creacion"),
    [
        ("/accounting/unit/list", "Nueva Unidad"),
        ("/accounting/project/list", "Nuevo Proyecto"),
    ],
)
def test_catalogo_sin_entidades_muestra_el_alta_inicial(app, authenticated_client, ruta, cta_creacion):
    """Sin entidades se ofrece crear la primera y no acciones que no pueden completarse."""
    original = app.jinja_env.globals["entidades_creadas"]
    app.jinja_env.globals["entidades_creadas"] = lambda: False
    try:
        response = authenticated_client().get(ruta)
    finally:
        app.jinja_env.globals["entidades_creadas"] = original

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Al parecer es la primera vez que accedes al sistema." in html
    assert "Crear Nueva Entidad" in html
    assert cta_creacion not in html


def test_las_plantillas_invocan_el_global_de_entidades():
    """`entidades_creadas` es una función: usarla sin paréntesis siempre es verdadera."""
    afectadas = [
        str(ruta.relative_to(RAIZ))
        for ruta in sorted(RAIZ.rglob("*.html"))
        if USO_SIN_LLAMADA.search(ruta.read_text(encoding="utf-8", errors="ignore"))
    ]

    assert afectadas == []
