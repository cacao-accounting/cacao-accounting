# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1810: el detalle y la edición de StockEntry muestran el nombre del artículo.

``StockEntryItem`` no denormaliza ``item_name``. La edición ya resolvía el
nombre con un join; el detalle seguía leyendo el atributo inexistente y la
columna Descripción mostraba ``-`` aunque el artículo existiera.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import Item, StockEntry, StockEntryItem, database


def _crear_movimiento(app) -> tuple[str, str]:
    """Crea un borrador con una línea y devuelve (entry_id, item_name)."""
    sufijo = uuid4().hex[:6].upper()
    item_code = f"ART-1810-{sufijo}"
    item_name = f"Cemento gris {sufijo}"
    with app.app_context():
        database.session.add(
            Item(
                code=item_code,
                name=item_name,
                item_type="goods",
                is_stock_item=True,
                default_uom="UND",
            )
        )
        entry = StockEntry(
            company="cacao",
            purpose="material_receipt",
            docstatus=0,
            posting_date=date(2026, 5, 20),
            transaction_currency="NIO",
            base_currency="NIO",
        )
        database.session.add(entry)
        database.session.flush()
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=item_code,
                qty=Decimal("4"),
                uom="UND",
                basic_rate=Decimal("25"),
                amount=Decimal("100"),
            )
        )
        database.session.commit()
        return entry.id, item_name


def test_el_detalle_del_movimiento_muestra_el_nombre_del_articulo(app, entorno_contable, authenticated_client):
    """La columna Descripción usa el nombre real del Item de la línea."""
    del entorno_contable
    entry_id, item_name = _crear_movimiento(app)

    response = authenticated_client("admin").get(f"/inventory/stock-entry/{entry_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert item_name in body
    assert f'data-item-name="{item_name}"' in body


def test_la_edicion_de_un_movimiento_con_lineas_renderiza(app, entorno_contable, authenticated_client):
    """Abrir la edición de un borrador con líneas no responde 500."""
    del entorno_contable
    entry_id, item_name = _crear_movimiento(app)

    response = authenticated_client("admin").get(f"/inventory/stock-entry/{entry_id}/edit")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert item_name in body
