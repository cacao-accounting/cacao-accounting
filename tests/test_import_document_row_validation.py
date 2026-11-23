# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1198: la importación de documentos resuelve el artículo por código y exige bodega."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import Item, UOM, Warehouse, database
from cacao_accounting.imports.adapters.transaction_documents import DeliveryNoteAdapter, PurchaseReceiptAdapter


def _item_stock() -> Item:
    sufijo = uuid4().hex[:6]
    uom = UOM(code=f"U{sufijo}", name="Unidad", is_active=True)
    database.session.add(uom)
    database.session.flush()
    item = Item(
        code=f"STK{sufijo}",
        name="Artículo con stock",
        item_type="stock",
        is_stock_item=True,
        is_purchase_item=True,
        is_sale_item=True,
        default_uom=uom.code,
    )
    database.session.add(item)
    database.session.commit()
    return item


@pytest.mark.parametrize("adapter_class", [DeliveryNoteAdapter, PurchaseReceiptAdapter])
def test_articulo_se_resuelve_por_codigo_y_exige_bodega(app, entorno_contable, adapter_class):
    """`producto` es un código, no la PK del artículo; sin bodega se rechaza."""
    with app.app_context():
        item = _item_stock()
        adapter = adapter_class()
        errores: list[str] = []

        adapter._validate_document_row({"producto": item.code, "cantidad": "1"}, "cacao", errores)

        assert not any("no existe" in error.lower() for error in errores), errores
        assert any("requiere una bodega" in error for error in errores), errores


@pytest.mark.parametrize("adapter_class", [DeliveryNoteAdapter, PurchaseReceiptAdapter])
def test_con_bodega_valida_no_genera_error_de_bodega(app, entorno_contable, adapter_class):
    """Con bodega presente la regla no aplica."""
    with app.app_context():
        item = _item_stock()
        bodega = Warehouse(code=f"W{uuid4().hex[:5]}", name="Bodega", company="cacao", is_active=True)
        database.session.add(bodega)
        database.session.commit()
        adapter = adapter_class()
        errores: list[str] = []

        adapter._validate_document_row({"producto": item.code, "cantidad": "1", "bodega": bodega.code}, "cacao", errores)

        assert not any("requiere una bodega" in error for error in errores), errores
