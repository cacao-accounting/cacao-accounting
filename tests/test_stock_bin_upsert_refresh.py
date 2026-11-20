# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1868: el upsert del bin refresca la instancia tras el bloqueo."""

from decimal import Decimal

from cacao_accounting.contabilidad.posting_service import _upsert_stock_bin
from cacao_accounting.database import Item, StockBin, UOM, Warehouse, database


def test_upsert_stock_bin_refresca_instancia_tras_lock(app):
    """El upsert con lock aplica sobre el saldo refrescado del bin (#1868)."""
    with app.app_context():
        database.session.add(UOM(code="UND", name="Unidad"))
        database.session.flush()
        database.session.add(
            Item(code="ART-1868", name="Articulo 1868", item_type="goods", is_stock_item=True, default_uom="UND")
        )
        database.session.flush()
        database.session.add(Warehouse(code="BOD-1868", name="Bodega 1868", company="cacao"))
        database.session.flush()
        bin_row = StockBin(
            company="cacao", item_code="ART-1868", warehouse="BOD-1868", actual_qty=Decimal("5"), stock_value=Decimal("50")
        )
        database.session.add(bin_row)
        database.session.commit()
        bin_id = bin_row.id

        # Simula una transaccion concurrente que reduce el bin tras la carga.
        database.session.query(StockBin).filter_by(id=bin_id).update(
            {StockBin.actual_qty: Decimal("2"), StockBin.stock_value: Decimal("20")}, synchronize_session=False
        )

        qty_after, stock_value_after = _upsert_stock_bin(
            company="cacao",
            item_code="ART-1868",
            warehouse="BOD-1868",
            qty_change=Decimal("-1"),
            valuation_rate=Decimal("10"),
            value_change=Decimal("-10"),
        )

        assert qty_after == Decimal("1")
        assert stock_value_after == Decimal("10")
        persisted = database.session.get(StockBin, bin_id)
        assert persisted.actual_qty == Decimal("1")
