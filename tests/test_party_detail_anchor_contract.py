# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1935: los enlaces a secciones de terceros apuntan a anclas existentes."""

from __future__ import annotations

import re
from pathlib import Path

from cacao_accounting.database import Party, database

RAIZ = Path(__file__).resolve().parents[1] / "cacao_accounting"
SECCIONES = RAIZ / "templates" / "party_detail_sections.html"


def test_secciones_declaran_los_ids_que_ventas_enlaza():
    """Los anclajes existen; ventas no ofrece un enlace a una sección sin destino."""
    secciones = SECCIONES.read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', secciones))

    texto_ventas = "".join(
        plantilla.read_text(encoding="utf-8") for plantilla in (RAIZ / "ventas" / "templates").rglob("*.html")
    )
    enlaces = set(re.findall(r"#(party-[A-Za-z0-9_-]+)", texto_ventas))

    assert {"party-contacts", "party-addresses"} <= ids
    assert enlaces <= ids, f"anclas sin destino: {sorted(enlaces - ids)}"
    assert "contactos-direcciones" not in texto_ventas
    assert "Contactos y Direcciones de Clientes" not in texto_ventas


def test_detalle_renderiza_secciones_y_menus_no_enlazan_ancla_rota(app, authenticated_client, entorno_contable):
    """El detalle real declara los IDs y Ventas/Compras no emiten el ancla antigua."""
    del entorno_contable
    with app.app_context():
        customer_id = database.session.execute(database.select(Party.id).filter_by(code="CLI001")).scalar_one()

    cliente = authenticated_client("admin")
    detalle = cliente.get(f"/sales/customer/{customer_id}")

    assert detalle.status_code == 200
    cuerpo_detalle = detalle.get_data(as_text=True)
    assert 'id="party-contacts"' in cuerpo_detalle
    assert 'id="party-addresses"' in cuerpo_detalle

    for menu in ("/sales/", "/buying/"):
        response = cliente.get(menu)
        assert response.status_code == 200, menu
        assert "contactos-direcciones" not in response.get_data(as_text=True), menu
