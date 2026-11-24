# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1927: una UOM inactiva no se ofrece para artículos nuevos.

Las referencias históricas se conservan y se muestran al editar, pero una
configuración nueva (alta o cambio de unidad) no puede seleccionar una UOM
inactiva. El backend aplica la misma política que el selector.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Item, UOM, database
from cacao_accounting.inventario.service import (
    InventoryServiceError,
    ItemParams,
    validate_item_uom_policy,
)


@pytest.fixture
def uoms_activas_e_inactivas(app, entorno_contable):
    """Una UOM activa y dos inactivas para probar el selector y el servicio."""
    del entorno_contable
    sufijo = uuid4().hex[:5]
    with app.app_context():
        activa = UOM(code=f"A{sufijo}", name="Unidad activa", is_active=True)
        inactiva = UOM(code=f"I{sufijo}", name="Unidad inactiva", is_active=False)
        otra_inactiva = UOM(code=f"J{sufijo}", name="Otra inactiva", is_active=False)
        database.session.add_all([activa, inactiva, otra_inactiva])
        database.session.commit()
        ids = {"activa": activa.code, "inactiva": inactiva.code, "otra": otra_inactiva.code}
    yield ids
    with app.app_context():
        database.session.execute(database.delete(UOM).where(UOM.code.in_(ids.values())))
        database.session.commit()


def test_alta_de_articulo_no_ofrece_uom_inactiva(app, authenticated_client, uoms_activas_e_inactivas):
    """El selector de un artículo nuevo solo contiene unidades activas."""
    ids = uoms_activas_e_inactivas

    response = authenticated_client("admin").get("/inventory/item/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert ids["activa"] in cuerpo
    assert ids["inactiva"] not in cuerpo


def test_el_servicio_rechaza_uom_inactiva_en_alta(app, uoms_activas_e_inactivas):
    """Aunque se fuerce el POST, el servicio no crea el artículo."""
    ids = uoms_activas_e_inactivas
    with app.app_context():
        with pytest.raises(InventoryServiceError, match="inactiva"):
            from cacao_accounting.inventario.service import create_item_with_uoms

            create_item_with_uoms(ItemParams(name="Artículo inválido", default_uom=ids["inactiva"]))


def test_edicion_conserva_uom_historica_inactiva(app, authenticated_client, uoms_activas_e_inactivas):
    """Una UOM inactiva ya vinculada se muestra y solo se permite cambiarla por una activa."""
    ids = uoms_activas_e_inactivas
    sufijo = uuid4().hex[:5]
    with app.app_context():
        item = Item(
            code=f"HIST-{sufijo}",
            name="Artículo histórico",
            item_type="goods",
            is_stock_item=False,
            default_uom=ids["inactiva"],
        )
        database.session.add(item)
        database.session.commit()
        item_code = item.code

        validate_item_uom_policy(ItemParams(name=item.name, default_uom=ids["inactiva"]), item=item)
        with pytest.raises(InventoryServiceError, match="inactiva"):
            validate_item_uom_policy(ItemParams(name=item.name, default_uom=ids["otra"]), item=item)

    try:
        response = authenticated_client("admin").get(f"/inventory/item/{item_code}/edit")
        assert response.status_code == 200
        assert ids["inactiva"] in response.get_data(as_text=True)
    finally:
        with app.app_context():
            database.session.execute(database.delete(Item).where(Item.code == item_code))
            database.session.commit()
