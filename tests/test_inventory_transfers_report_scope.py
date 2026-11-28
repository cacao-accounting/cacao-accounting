# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1118: el reporte de traslados excluye los sin contabilizar."""

from decimal import Decimal

from cacao_accounting.database import Item, StockEntry, StockEntryItem, UOM, Warehouse, database
from cacao_accounting.reportes.services import OperationalReportFilters, get_inventory_transfers


def _crear_transferencia(item_code: str, warehouse: str, docstatus: int, uom: str) -> StockEntry:
    """Crea una entrada de material_transfer con una línea."""
    database.session.add(Warehouse(code=warehouse, name=f"Bodega {warehouse}", company="cacao"))
    database.session.flush()
    entry = StockEntry(company="cacao", purpose="material_transfer", docstatus=docstatus)
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code=item_code,
            qty=Decimal("10"),
            qty_in_base_uom=Decimal("10"),
            uom=uom,
        )
    )
    database.session.commit()
    return entry


def test_reporte_excluye_transferencias_sin_contabilizar(app):
    """get_inventory_transfers lista solo traslados contabilizados (#1118)."""
    with app.app_context():
        database.session.add(UOM(code="UND1118", name="Unidad 1118"))
        database.session.flush()
        database.session.add(
            Item(code="ART-1118", name="Articulo 1118", item_type="goods", is_stock_item=True, default_uom="UND1118")
        )
        database.session.flush()
        draft = _crear_transferencia("ART-1118", "BOD-1118A", 0, "UND1118")
        posted = _crear_transferencia("ART-1118", "BOD-1118B", 1, "UND1118")

        report = get_inventory_transfers(OperationalReportFilters(company="cacao"))

        transfer_ids = {row.values["transfer_id"] for row in report.rows}
        assert posted.id in transfer_ids
        assert draft.id not in transfer_ids
