# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1198: la recepción manual exige bodega para artículos de inventario."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.compras.services import _validate_receipt_warehouse
from cacao_accounting.database import Item, UOM, database
from cacao_accounting.document_flow import DocumentFlowError


def test_codigo_de_articulo_stock_sin_bodega_se_rechaza(app, entorno_contable):
    """La validación manual resuelve por code aunque id sea otra clave."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        uom = UOM(code=f"U{suffix}", name="Unidad", is_active=True)
        database.session.add(uom)
        database.session.commit()
        item = Item(
            code=f"STK{suffix}",
            name="Artículo con inventario",
            item_type="stock",
            is_stock_item=True,
            is_purchase_item=True,
            default_uom=uom.code,
        )
        database.session.add(item)
        database.session.flush()
        assert item.id != item.code

        with pytest.raises(DocumentFlowError, match="requiere una bodega"):
            _validate_receipt_warehouse(None, item.code, "cacao")


def test_servicio_sin_bodega_sigue_permitido_en_recepcion_manual(app, entorno_contable):
    """La corrección conserva la recepción sin bodega para artículos de servicio."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        uom = UOM(code=f"US{suffix}", name="Unidad", is_active=True)
        database.session.add(uom)
        database.session.commit()
        item = Item(
            code=f"SRV{suffix}",
            name="Servicio",
            item_type="service",
            is_stock_item=False,
            is_purchase_item=True,
            default_uom=uom.code,
        )
        database.session.add(item)
        database.session.flush()

        _validate_receipt_warehouse(None, item.code, "cacao")
