# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1879: el ajuste de solo valor lleva al GL el costo funcional del SLE."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from cacao_accounting.contabilidad.posting_service import (
    _get_stock_entry_line_amount,
    _movement_outflow_issue,
)
from cacao_accounting.database import Item, StockBin, UOM, Warehouse, database


def test_ajuste_negativo_de_solo_valor_usa_el_costo_funcional(app, entorno_contable):
    """10 USD con tasa 35 registran -350 NIO en SLE y en GL, no -10 NIO."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        uom = UOM(code=f"U{sufijo}", name="Unidad", is_active=True)
        database.session.add(uom)
        database.session.flush()
        item = Item(code=f"ART{sufijo}", name="Artículo", item_type="goods", is_stock_item=True, default_uom=uom.code)
        warehouse = Warehouse(code=f"W{sufijo}", name="Bodega", company="cacao", is_active=True)
        database.session.add_all([item, warehouse])
        database.session.flush()
        database.session.add(
            StockBin(
                company="cacao",
                item_code=item.code,
                warehouse=warehouse.code,
                actual_qty=Decimal("10"),
                stock_value=Decimal("3500"),
                valuation_rate=Decimal("350"),
            )
        )
        database.session.commit()

        documento = SimpleNamespace(
            id=f"se-{sufijo}",
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("35"),
            purpose="adjustment_negative",
            from_warehouse=warehouse.code,
            voucher_type="stock_entry",
        )
        linea = SimpleNamespace(
            id=f"line-{sufijo}",
            item_code=item.code,
            source_warehouse=warehouse.code,
            target_warehouse=None,
            amount=Decimal("10"),
            valuation_rate=Decimal("0"),
            basic_rate=Decimal("0"),
            qty=Decimal("0"),
            batch_id=None,
            serial_no=None,
        )

        movimientos = _movement_outflow_issue(documento, linea, Decimal("0"))

        assert len(movimientos) == 1
        assert movimientos[0].stock_value_difference == Decimal("-350")
        assert getattr(linea, "_inventory_cost_amount", None) == Decimal("350")
        assert _get_stock_entry_line_amount(documento, linea, "adjustment_negative") == Decimal("350")
