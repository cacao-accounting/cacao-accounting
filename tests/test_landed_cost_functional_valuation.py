# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1793: la capitalización de landed cost valora el inventario en moneda funcional."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

from cacao_accounting.contabilidad.posting_service import _persist_single_allocation
from cacao_accounting.database import (
    Item,
    LandedCostAllocation,
    StockBin,
    StockValuationLayer,
    UOM,
    Warehouse,
    database,
)


def test_landed_cost_en_usd_ajusta_el_stock_en_nio(app, entorno_contable):
    """Una capitalización de 10 USD con tasa 36 aumenta el stock en 360 NIO."""
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
                stock_value=Decimal("1000"),
                valuation_rate=Decimal("100"),
            )
        )
        database.session.commit()

        documento = SimpleNamespace(
            id=f"doc-{sufijo}",
            company="cacao",
            posting_date=date(2026, 5, 15),
            transaction_currency="USD",
            base_currency="NIO",
            exchange_rate=Decimal("36"),
            voucher_type="purchase_invoice",
        )
        linea = SimpleNamespace(id=f"line-{sufijo}", item_code=item.code, warehouse=warehouse.code)
        allocation = SimpleNamespace(
            item_line_id=linea.id,
            allocated_total=Decimal("10"),
            base_amount=Decimal("360"),
            final_inventory_cost=Decimal("0"),
            unit_inventory_cost=Decimal("0"),
            allocated_costs=[],
        )

        _persist_single_allocation(
            document=documento,
            allocation=allocation,
            items_by_line_id={linea.id: linea},
            create_valuation_adjustment=True,
        )
        database.session.commit()

        bin_actualizado = database.session.execute(
            select(StockBin).filter_by(company="cacao", item_code=item.code)
        ).scalar_one()
        capa = database.session.execute(
            select(StockValuationLayer).filter_by(item_code=item.code, warehouse=warehouse.code)
        ).scalar_one()
        registro = database.session.execute(select(LandedCostAllocation).filter_by(document_id=documento.id)).scalar_one()

        assert bin_actualizado.stock_value == Decimal("1360")
        assert capa.stock_value_difference == Decimal("360")
        assert registro.allocated_amount == Decimal("10")
