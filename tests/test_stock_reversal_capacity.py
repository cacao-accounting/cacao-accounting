# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1857: validación de reversión valida el neto por bin, no los prefijos."""

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.contabilidad.posting_service import (
    PostingError,
    _validate_stock_reversal_capacity,
)
from cacao_accounting.database import Item, StockBin, StockLedgerEntry, UOM, Warehouse, database

FECHA = date(2026, 5, 20)


def _sembrar(artefacto: str, bodega: str, uom: str) -> None:
    """Crea item, bodega y bin con saldo cero."""
    database.session.add(UOM(code=uom, name="Unidad 1857"))
    database.session.flush()
    database.session.add(Item(code=artefacto, name="Articulo 1857", item_type="goods", is_stock_item=True, default_uom=uom))
    database.session.flush()
    database.session.add(Warehouse(code=bodega, name="Bodega 1857", company="cacao"))
    database.session.flush()
    database.session.add(StockBin(company="cacao", item_code=artefacto, warehouse=bodega, actual_qty=Decimal("0")))
    database.session.commit()


def _movimiento(artefacto: str, bodega: str, qty_change: Decimal) -> StockLedgerEntry:
    """Crea un movimiento histórico real para validar la reversión (#1857)."""
    movement = StockLedgerEntry(
        posting_date=FECHA,
        item_code=artefacto,
        warehouse=bodega,
        company="cacao",
        qty_change=qty_change,
        voucher_type="stock_entry",
        voucher_id=f"SE-1857-{abs(int(qty_change))}",
    )
    database.session.add(movement)
    database.session.flush()
    return movement


def test_validar_capacidad_acepta_set_neto_restaurado(app):
    """Movimientos +5 y -5 sobre bin 0 no bloquean: el neto es cero (#1857)."""
    with app.app_context():
        _sembrar("ART-1857A", "BOD-1857A", "UND1857A")
        movements = [
            _movimiento("ART-1857A", "BOD-1857A", Decimal("5")),
            _movimiento("ART-1857A", "BOD-1857A", Decimal("-5")),
        ]
        _validate_stock_reversal_capacity(movements)


def test_validar_capacidad_rechaza_neto_negativo(app):
    """Movimientos que dejan neto negativo en la bodega quedan bloqueados (#1857)."""
    with app.app_context():
        _sembrar("ART-1857B", "BOD-1857B", "UND1857B")
        movements = [
            _movimiento("ART-1857B", "BOD-1857B", Decimal("5")),
            _movimiento("ART-1857B", "BOD-1857B", Decimal("6")),
        ]
        with pytest.raises(PostingError, match="stock negativo"):
            _validate_stock_reversal_capacity(movements)
