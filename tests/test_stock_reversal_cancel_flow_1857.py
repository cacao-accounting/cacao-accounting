# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1857: la cancelación valida el neto del documento, no prefijos arbitrarios."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.contabilidad.posting_service import (
    PostingError,
    _cancel_stock_movements_if_needed,
    _create_stock_movements_for_items,
    _persist_stock_book_valuations,
)
from cacao_accounting.database import (
    Item,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerBookEntry,
    StockLedgerEntry,
    StockValuationLayer,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.internal_control_service import _LEDGER_CANCELLATION_ACTIVE, authorized_posting

FECHA = date(2026, 5, 20)
ITEM_CODE = "ART-1857-FLOW"
WAREHOUSE = "BOD-1857-FLOW"
UOM_CODE = "UND-1857-FLOW"


def _crear_maestros() -> None:
    """Crea un artículo sin stock negativo y una bodega aislados."""
    database.session.add(UOM(code=UOM_CODE, name="Unidad 1857 flujo"))
    database.session.flush()
    database.session.add(
        Item(
            code=ITEM_CODE,
            name="Artículo 1857 flujo",
            item_type="goods",
            is_stock_item=True,
            default_uom=UOM_CODE,
            allow_negative_stock=False,
        )
    )
    database.session.flush()
    database.session.add(Warehouse(code=WAREHOUSE, name="Bodega 1857 flujo", company="cacao", is_active=True))
    database.session.commit()


def _persistir_movimientos(entry: StockEntry, purpose: str) -> list[str]:
    """Ejecuta el helper productivo de movimientos y conserva su valoración por libro."""
    database.session.commit()
    lineas = list(
        database.session.execute(
            database.select(StockEntryItem).filter_by(stock_entry_id=entry.id).order_by(StockEntryItem.id)
        )
        .scalars()
        .all()
    )
    movimientos = _create_stock_movements_for_items(entry, lineas, purpose)
    database.session.add_all(movimientos)
    _persist_stock_book_valuations(entry, movimientos)
    database.session.commit()
    return [str(movimiento.id) for movimiento in movimientos]


def _crear_conciliacion(objetivos: list[tuple[str, str]]) -> tuple[str, list[str]]:
    """Materializa una conciliación histórica con líneas repetidas del mismo bin."""
    entry = StockEntry(
        company="cacao",
        purpose="stock_reconciliation",
        posting_date=FECHA,
        document_no="REC-1857-FLOW",
        from_warehouse=WAREHOUSE,
        to_warehouse=WAREHOUSE,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        status="submitted",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    for counted_qty, target_rate in objetivos:
        database.session.add(
            StockEntryItem(
                stock_entry_id=entry.id,
                item_code=ITEM_CODE,
                qty=Decimal("1"),
                qty_in_base_uom=Decimal("1"),
                uom=UOM_CODE,
                counted_qty=Decimal(counted_qty),
                target_valuation_rate=Decimal(target_rate),
                target_stock_value=Decimal(counted_qty) * Decimal(target_rate),
                source_warehouse=WAREHOUSE,
                target_warehouse=WAREHOUSE,
            )
        )
    movimientos = _persistir_movimientos(entry, "stock_reconciliation")
    return str(entry.id), movimientos


def _crear_salida(qty: str) -> str:
    """Consume el stock disponible mediante el flujo productivo de salida."""
    entry = StockEntry(
        company="cacao",
        purpose="material_issue",
        posting_date=FECHA,
        document_no="ISS-1857-FLOW",
        from_warehouse=WAREHOUSE,
        to_warehouse=WAREHOUSE,
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
        status="submitted",
        docstatus=1,
    )
    database.session.add(entry)
    database.session.flush()
    database.session.add(
        StockEntryItem(
            stock_entry_id=entry.id,
            item_code=ITEM_CODE,
            qty=Decimal(qty),
            qty_in_base_uom=Decimal(qty),
            uom=UOM_CODE,
            basic_rate=Decimal("1"),
            valuation_rate=Decimal("1"),
            amount=Decimal(qty),
            source_warehouse=WAREHOUSE,
            target_warehouse=WAREHOUSE,
        )
    )
    _persistir_movimientos(entry, "material_issue")
    return str(entry.id)


def _cancelizar(entry_id: str) -> None:
    """Invoca el camino real de cancelación de movimientos bajo sus permisos."""
    entry = database.session.get(StockEntry, entry_id)
    assert entry is not None
    token = _LEDGER_CANCELLATION_ACTIVE.set(("stock_entry", entry_id))
    try:
        with authorized_posting():
            _cancel_stock_movements_if_needed(entry, "cacao", "stock_entry", entry_id, FECHA)
    finally:
        _LEDGER_CANCELLATION_ACTIVE.reset(token)


def _bin() -> StockBin:
    """Devuelve el bin del escenario."""
    return database.session.execute(
        database.select(StockBin).filter_by(company="cacao", item_code=ITEM_CODE, warehouse=WAREHOUSE)
    ).scalar_one()


def test_cancelacion_neta_cero_completa_y_conserva_contrapartidas(entorno_contable_aislado):
    """Una conciliación histórica +5/-5 se cancela sin fallar por el primer prefijo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _crear_maestros()
        entry_id, original_ids = _crear_conciliacion([("5", "1"), ("0", "0")])
        assert sorted(
            database.session.execute(
                database.select(StockLedgerEntry.qty_change).where(StockLedgerEntry.voucher_id == entry_id)
            ).scalars()
        ) == [Decimal("-5"), Decimal("5")]
        assert Decimal(_bin().actual_qty) == Decimal("0")

        _cancelizar(entry_id)
        database.session.commit()
        database.session.expire_all()

        originales = list(
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id, is_reversal=False))
            .scalars()
            .all()
        )
        reversas = list(
            database.session.execute(
                database.select(StockLedgerEntry).filter_by(voucher_id=entry_id, is_reversal=True, is_cancelled=False)
            )
            .scalars()
            .all()
        )
        assert {str(movimiento.id) for movimiento in originales} == set(original_ids)
        assert all(movimiento.is_cancelled for movimiento in originales)
        assert len(reversas) == 2
        assert {str(reversa.reversal_of) for reversa in reversas} == set(original_ids)
        assert sorted(reversa.qty_change for reversa in reversas) == [Decimal("-5"), Decimal("5")]
        assert Decimal(_bin().actual_qty) == Decimal("0")
        assert Decimal(_bin().stock_value) == Decimal("0")

        capas = list(
            database.session.execute(database.select(StockValuationLayer).where(StockValuationLayer.voucher_id == entry_id))
            .scalars()
            .all()
        )
        assert len(capas) == 4
        assert sum((capa.qty for capa in capas), Decimal("0")) == Decimal("0")
        assert sum((capa.stock_value_difference for capa in capas), Decimal("0")) == Decimal("0")

        valores_originales = list(
            database.session.execute(
                database.select(StockLedgerBookEntry).where(StockLedgerBookEntry.stock_ledger_entry_id.in_(original_ids))
            )
            .scalars()
            .all()
        )
        assert valores_originales
        for original in originales:
            monto_original = sum(
                (valor.book_amount for valor in valores_originales if valor.stock_ledger_entry_id == original.id),
                Decimal("0"),
            )
            reversa = next(reversa for reversa in reversas if reversa.reversal_of == original.id)
            monto_reversa = database.session.execute(
                database.select(database.func.coalesce(database.func.sum(StockLedgerBookEntry.book_amount), 0)).where(
                    StockLedgerBookEntry.stock_ledger_entry_id == reversa.id
                )
            ).scalar_one()
            assert monto_reversa == -monto_original


def test_cancelacion_con_neto_negativo_rechaza_sin_mutaciones(entorno_contable_aislado):
    """Un conjunto que realmente deja saldo negativo se rechaza antes de mutar."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _crear_maestros()
        entry_id, _original_ids = _crear_conciliacion([("5", "1"), ("11", "1")])
        salida_id = _crear_salida("11")
        assert Decimal(_bin().actual_qty) == Decimal("0")

        with pytest.raises(PostingError, match="stock negativo"):
            _cancelizar(entry_id)

        originales = list(
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id, is_reversal=False))
            .scalars()
            .all()
        )
        assert len(originales) == 2
        assert all(not movimiento.is_cancelled for movimiento in originales)
        assert (
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=entry_id, is_reversal=True))
            .scalars()
            .all()
            == []
        )
        assert Decimal(_bin().actual_qty) == Decimal("0")
        salida = list(
            database.session.execute(database.select(StockLedgerEntry).filter_by(voucher_id=salida_id)).scalars().all()
        )
        assert salida and all(not movimiento.is_cancelled for movimiento in salida)
        database.session.rollback()
