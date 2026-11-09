# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los enlaces de contactos apuntan a destinos existentes.

Escenario de negocio (issue #1935): el menú enlazaba a
``#contactos-direcciones``, un ID que ninguna plantilla declara.
"""

from __future__ import annotations

from pathlib import Path

MENU_VENTAS = Path("cacao_accounting/ventas/templates/ventas.html")
MENU_COMPRAS = Path("cacao_accounting/compras/templates/compras.html")
DETALLE_TERCERO = Path("cacao_accounting/templates/party_detail_sections.html")


def test_no_quedan_anclas_de_contactos_inexistentes():
    """#1935: ventas y compras no enlazan a un ID ausente."""
    for menu in (MENU_VENTAS, MENU_COMPRAS):
        texto = menu.read_text(encoding="utf-8")
        assert "#contactos-direcciones" not in texto


def test_el_detalle_de_tercero_expone_los_ids_reales():
    """#1935: los destinos reales siguen existiendo en la macro compartida."""
    detalle = DETALLE_TERCERO.read_text(encoding="utf-8")
    assert 'id="party-contacts"' in detalle
    assert 'id="party-addresses"' in detalle
