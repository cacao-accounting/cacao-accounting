# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de inventario para UOM, lote/serial y reconstruccion de bins."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from cacao_accounting.database import (
    Batch,
    Item,
    ItemUOMConversion,
    SerialNumber,
    StockBin,
    StockLedgerEntry,
    database,
)


class InventoryServiceError(ValueError):
    """Error controlado de servicios de inventario."""


@dataclass(frozen=True)
class StockRebuildResult:
    """Resultado de reconstruccion de StockBin."""

    rebuilt_bins: int
    inconsistencies: list[str]


def _decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def convert_item_qty(item_code: str, qty: Decimal, from_uom: str, to_uom: str) -> Decimal:
    """Convierte cantidad de un item entre UOM configuradas."""
    if from_uom == to_uom:
        return qty
    conversion = (
        database.session.execute(select(ItemUOMConversion).filter_by(item_code=item_code, from_uom=from_uom, to_uom=to_uom))
        .scalars()
        .first()
    )
    if conversion:
        return qty * _decimal_value(conversion.conversion_factor)
    inverse = (
        database.session.execute(select(ItemUOMConversion).filter_by(item_code=item_code, from_uom=to_uom, to_uom=from_uom))
        .scalars()
        .first()
    )
    if inverse:
        factor = _decimal_value(inverse.conversion_factor)
        if factor == 0:
            raise InventoryServiceError("La conversion de UOM no puede tener factor cero.")
        return qty / factor
    raise InventoryServiceError("No existe conversion UOM para el item.")


def validate_batch_serial(line: Any, *, outgoing: bool) -> None:
    """Valida obligatoriedad y disponibilidad de lote/serial en una linea."""
    item = database.session.get(Item, getattr(line, "item_code", None))
    if not item or not item.is_stock_item:
        return
    if item.has_batch:
        batch_id = getattr(line, "batch_id", None)
        if not batch_id:
            raise InventoryServiceError("El item requiere lote.")
        batch = database.session.get(Batch, batch_id)
        if not batch or batch.item_code != item.code or not batch.is_active:
            raise InventoryServiceError("El lote no existe, esta inactivo o no pertenece al item.")
    if item.has_serial_no:
        serial_no = getattr(line, "serial_no", None)
        if not serial_no:
            raise InventoryServiceError("El item requiere numero de serie.")
        serial = database.session.execute(
            select(SerialNumber).filter_by(item_code=item.code, serial_no=serial_no)
        ).scalar_one_or_none()
        if outgoing:
            if not serial or serial.serial_status != "available":
                raise InventoryServiceError("El serial no esta disponible para salida.")
        elif serial and serial.serial_status == "delivered":
            raise InventoryServiceError("El serial ya fue entregado.")


def update_serial_state(line: Any, *, outgoing: bool, warehouse: str | None) -> None:
    """Actualiza estado y bodega del serial despues del movimiento."""
    serial_no = getattr(line, "serial_no", None)
    if not serial_no:
        return
    serial = database.session.execute(
        select(SerialNumber).filter_by(item_code=getattr(line, "item_code", None), serial_no=serial_no)
    ).scalar_one_or_none()
    if not serial:
        serial = SerialNumber(
            item_code=getattr(line, "item_code", None),
            serial_no=serial_no,
            serial_status="available",
            warehouse=warehouse,
        )
        database.session.add(serial)
    serial.serial_status = "delivered" if outgoing else "available"
    serial.warehouse = None if outgoing else warehouse


def rebuild_stock_bins(company: str, item_code: str | None = None, warehouse: str | None = None) -> StockRebuildResult:
    """Reconstruye StockBin desde StockLedgerEntry append-only."""
    query = select(StockLedgerEntry.company, StockLedgerEntry.item_code, StockLedgerEntry.warehouse).filter_by(
        company=company, is_cancelled=False
    )
    if item_code:
        query = query.filter_by(item_code=item_code)
    if warehouse:
        query = query.filter_by(warehouse=warehouse)
    groups = database.session.execute(query.distinct()).all()
    rebuilt = 0
    inconsistencies: list[str] = []
    for group_company, group_item, group_warehouse in groups:
        totals = database.session.execute(
            select(
                func.coalesce(func.sum(StockLedgerEntry.qty_change), 0),
                func.coalesce(func.sum(StockLedgerEntry.stock_value_difference), 0),
            ).filter_by(company=group_company, item_code=group_item, warehouse=group_warehouse, is_cancelled=False)
        ).one()
        qty = _decimal_value(totals[0])
        value = _decimal_value(totals[1])
        valuation_rate = value / qty if qty else Decimal("0")
        bin_row = database.session.execute(
            select(StockBin).filter_by(company=group_company, item_code=group_item, warehouse=group_warehouse)
        ).scalar_one_or_none()
        if not bin_row:
            bin_row = StockBin(company=group_company, item_code=group_item, warehouse=group_warehouse)
            database.session.add(bin_row)
        old_qty = _decimal_value(bin_row.actual_qty)
        if old_qty != qty:
            inconsistencies.append(f"{group_item}/{group_warehouse}: {old_qty} -> {qty}")
        bin_row.actual_qty = qty
        bin_row.stock_value = value
        bin_row.valuation_rate = valuation_rate
        rebuilt += 1
    return StockRebuildResult(rebuilt_bins=rebuilt, inconsistencies=inconsistencies)
