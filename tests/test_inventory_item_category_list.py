# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1944: la lista de artículos muestra el nombre de su categoría.

La pantalla anunciaba la columna pero imprimía siempre ``-``. La regresión
crea una categoría real, la asigna a un artículo y exige que el listado
renderizado muestre su nombre en la fila del artículo.
"""

from __future__ import annotations

import re
from uuid import uuid4

from cacao_accounting.database import Item, ItemCategory, database


def _fila_del_articulo(html: str, code: str) -> str:
    """Extrae la fila de la tabla que contiene el código del artículo."""
    patron = rf"<tr[^>]*>(?:(?!</tr>).)*{re.escape(code)}(?:(?!</tr>).)*</tr>"
    fila = re.search(patron, html, re.S)
    assert fila is not None, f"No se encontró la fila del artículo {code}."
    return fila.group(0)


def test_lista_de_articulos_muestra_la_categoria(app, entorno_contable, authenticated_client):
    """Un artículo con categoría renderiza su nombre y no el guion genérico."""
    sufijo = uuid4().hex[:8].upper()
    nombre_categoria = f"Materia Prima {sufijo}"
    codigo = f"CAT-{sufijo}"

    with app.app_context():
        categoria = ItemCategory(name=nombre_categoria, is_active=True)
        database.session.add(categoria)
        database.session.flush()
        database.session.add(
            Item(
                code=codigo,
                name=f"Artículo {sufijo}",
                item_type="goods",
                is_stock_item=True,
                default_uom=entorno_contable.uom.code,
                item_category_id=categoria.id,
            )
        )
        database.session.commit()

    respuesta = authenticated_client("admin").get(f"/inventory/item/list?search={codigo}")

    assert respuesta.status_code == 200
    fila = _fila_del_articulo(respuesta.get_data(as_text=True), codigo)
    assert nombre_categoria in fila
