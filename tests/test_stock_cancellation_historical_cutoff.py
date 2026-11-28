# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Existencias y Kardex respetan la fecha efectiva histórica de anulación."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.database import DocumentTransition, Item, StockLedgerEntry, User, Warehouse, database
from cacao_accounting.ledger_queries import exclude_cancelled_stock_entries
from cacao_accounting.reportes.services import (
    KardexFilters,
    OperationalReportFilters,
    get_inventory_existence,
    get_inventory_turnover,
    get_kardex,
)


def test_reportes_stock_conservan_el_corte_anterior_a_la_anulacion(entorno_contable_aislado):
    """Los datos heredados permanecen vigentes antes de la transición y netean después."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item_code = database.session.execute(select(Item.code).limit(1)).scalar_one()
        warehouse_code = database.session.execute(select(Warehouse.code).limit(1)).scalar_one()
        original = StockLedgerEntry(
            company="cacao",
            item_code=item_code,
            warehouse=warehouse_code,
            posting_date=date(2026, 5, 1),
            qty_change=Decimal("10"),
            stock_value_difference=Decimal("100"),
            voucher_type="stock_entry",
            voucher_id="STOCK-CANCELADO-TARDIO",
            is_cancelled=True,
        )
        database.session.add(original)
        database.session.flush()
        reversal = StockLedgerEntry(
            company="cacao",
            item_code=item_code,
            warehouse=warehouse_code,
            posting_date=date(2026, 5, 20),
            qty_change=Decimal("-10"),
            stock_value_difference=Decimal("-100"),
            voucher_type="stock_entry",
            voucher_id="STOCK-CANCELADO-TARDIO",
            is_reversal=True,
            reversal_of=original.id,
        )
        database.session.add(reversal)
        actor_id = database.session.execute(select(User.id).where(User.classification == "admin").limit(1)).scalar_one()
        database.session.add(
            DocumentTransition(
                source_type=original.voucher_type,
                source_id=original.voucher_id,
                transition_type="cancellation",
                company="cacao",
                posting_date=date(2026, 5, 20),
                accounting_period_id="P2026-05",
                actor_user_id=actor_id,
                reason="Registro heredado para corte de inventario",
            )
        )
        database.session.flush()

        current_entries = (
            database.session.execute(
                exclude_cancelled_stock_entries(
                    select(StockLedgerEntry).where(StockLedgerEntry.voucher_id == original.voucher_id)
                )
            )
            .scalars()
            .all()
        )
        existences_before = get_inventory_existence(
            KardexFilters(
                company="cacao",
                item_code=item_code,
                warehouse=warehouse_code,
                date_to=date(2026, 5, 10),
            )
        )
        existences_after = get_inventory_existence(
            KardexFilters(
                company="cacao",
                item_code=item_code,
                warehouse=warehouse_code,
                date_to=date(2026, 5, 20),
            )
        )
        kardex_before = get_kardex(
            KardexFilters(
                company="cacao",
                item_code=item_code,
                warehouse=warehouse_code,
                date_to=date(2026, 5, 10),
            )
        )
        kardex_after = get_kardex(
            KardexFilters(
                company="cacao",
                item_code=item_code,
                warehouse=warehouse_code,
                date_to=date(2026, 5, 20),
            )
        )
        turnover_before = get_inventory_turnover(
            OperationalReportFilters(
                company="cacao",
                item_code=item_code,
                warehouse=warehouse_code,
                date_from=date(2026, 5, 1),
                date_to=date(2026, 5, 10),
            )
        )
        turnover_after = get_inventory_turnover(
            OperationalReportFilters(
                company="cacao",
                item_code=item_code,
                warehouse=warehouse_code,
                date_from=date(2026, 5, 1),
                date_to=date(2026, 5, 20),
            )
        )

    assert current_entries == []
    assert existences_before.totals["balance_qty"] == Decimal("10")
    assert existences_before.totals["stock_value"] == Decimal("100")
    assert existences_after.totals["balance_qty"] == Decimal("0")
    assert existences_after.totals["stock_value"] == Decimal("0")
    assert kardex_before.rows[0].values["balance_qty"] == Decimal("10")
    assert kardex_after.totals["incoming_qty"] == Decimal("0")
    assert kardex_after.totals["outgoing_qty"] == Decimal("0")
    assert turnover_before.rows[0].values["average_stock_qty"] == Decimal("5")
    assert turnover_after.rows == []
