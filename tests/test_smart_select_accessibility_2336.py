# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2336: las opciones Smart Select inline se eligen con click y teclado.

Enter y Espacio sobre un botón generan ``click``; si la opción solo escucha
``mousedown``, la selección por teclado no existe. El blur diferido tampoco
puede cerrar el menú mientras el foco está en una opción.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).parents[1] / "cacao_accounting"
BUTTON = re.compile(r"<button\b[^>]*\bca-smart-select-option\b[^>]*>", re.DOTALL)
MOUSEDOWN_SELECT = re.compile(r"@mousedown(?:\.prevent)?=\"[^\"]*selectOption", re.DOTALL)


def _option_buttons() -> list[tuple[Path, str]]:
    """Devuelve los botones de opción inline y compartidos de las plantillas."""
    buttons: list[tuple[Path, str]] = []
    for path in TEMPLATES.rglob("*.html"):
        for match in BUTTON.finditer(path.read_text(encoding="utf-8")):
            buttons.append((path, match.group(0)))
    return buttons


def test_ninguna_opcion_depende_solo_de_mousedown():
    """Una opción que solo escucha mousedown queda inaccesible por teclado."""
    infractores = [
        str(path.relative_to(TEMPLATES))
        for path in TEMPLATES.rglob("*.html")
        if MOUSEDOWN_SELECT.search(path.read_text(encoding="utf-8"))
    ]
    assert infractores == []


def test_las_opciones_responden_a_click_y_cierran_al_salir_del_foco():
    """Cada botón con selectOption debe enlazar click y blur a closeSoon."""
    botones = _option_buttons()
    assert botones
    sin_click = []
    sin_blur = []
    for path, tag in botones:
        if "selectOption" not in tag:
            continue
        relativo = str(path.relative_to(TEMPLATES))
        if '@click="selectOption' not in tag:
            sin_click.append(relativo)
        if '@blur="closeSoon"' not in tag:
            sin_blur.append(relativo)
    assert sin_click == []
    assert sin_blur == []


def test_el_cierre_diferido_consulta_el_foco_antes_de_cerrar():
    """El componente compartido no cierra si el foco está en una opción."""
    fuente = (TEMPLATES / "static/js/smart-select.js").read_text(encoding="utf-8")
    assert "_focusIsInsideOption()" in fuente
    assert "root.contains(active)" in fuente
    assert "ca-smart-select-option" in fuente


@pytest.mark.parametrize(
    "plantilla",
    [
        "inventario/templates/inventario/articulo_nuevo.html",
        "ventas/templates/ventas/cliente_nuevo.html",
        "bancos/templates/bancos/banco_cuenta_nuevo.html",
        "contabilidad/templates/contabilidad/book_crear.html",
        "admin/templates/admin/default_accounts.html",
    ],
)
def test_formularios_representativos_conservan_la_seleccion(plantilla: str):
    """Los formularios citados por el issue mantienen click y blur."""
    contenido = (TEMPLATES / plantilla).read_text(encoding="utf-8")
    assert 'class="ca-smart-select-option"' in contenido
    assert '@click="selectOption' in contenido
    assert '@blur="closeSoon"' in contenido
    assert "@mousedown" not in contenido
