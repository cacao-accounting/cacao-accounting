# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1891/#1873: una entrada de stock no puede tener valor funcional cero."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.contabilidad.posting_service import PostingError, _movement_inflow_receipt
from cacao_accounting.database import Item, StockBin, UOM, Warehouse, database


def test_recepcion_con_valor_funcional_cero_se_rechaza(app, entorno_contable):
    """100 unidades de 0.0001 USD con tasa 0.1 redondean a cero y se rechazan."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        uom = UOM(code=f"U{sufijo}", name="Unidad", is_active=True)
        database.session.add(uom)
        database.session.commit()
        item = Item(
            code=f"ART{sufijo}",
            name="Artículo",
            item_type="goods",
            is_stock_item=True,
            default_uom=uom.code,
        )
        warehouse = Warehouse(code=f"W{sufijo}", name="Bodega", company="cacao", is_active=True)
        database.session.add_all([item, warehouse])
        database.session.flush()
        database.session.add(
            StockBin(
                company="cacao",
                item_code=item.code,
                warehouse=warehouse.code,
                actual_qty=Decimal("10"),
                stock_value=Decimal("10"),
                valuation_rate=Decimal("1"),
            )
        )
        database.session.commit()

        documento = SimpleNamespace(
            id=f"se-{sufijo}",
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("0.1"),
            purpose="adjustment_positive",
            to_warehouse=warehouse.code,
            voucher_type="stock_entry",
        )
        linea = SimpleNamespace(
            id=f"line-{sufijo}",
            item_code=item.code,
            target_warehouse=warehouse.code,
            source_warehouse=None,
            amount=Decimal("0.0001"),
            valuation_rate=Decimal("0.0001"),
            basic_rate=Decimal("0.0001"),
            qty=Decimal("1"),
            qty_in_base_uom=Decimal("1"),
            batch_id=None,
            serial_no=None,
        )

        with pytest.raises(PostingError, match="valor funcional mayor que cero"):
            _movement_inflow_receipt(documento, linea, "adjustment_positive", Decimal("1"))
