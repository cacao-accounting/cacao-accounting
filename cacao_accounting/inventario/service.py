# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de inventario para UOM, lote/serial y reconstruccion de bins."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import func, select

from cacao_accounting.database import (
    Batch,
    Item,
    ItemUOMConversion,
    PurchaseInvoiceItem,
    PurchaseOrderItem,
    PurchaseReceiptItem,
    SalesInvoiceItem,
    SalesOrderItem,
    SerialNumber,
    StockBin,
    StockLedgerEntry,
    StockEntryItem,
    DeliveryNoteItem,
    database,
    UOM,
)


class InventoryServiceError(ValueError):
    """Error controlado de servicios de inventario."""


@dataclass(frozen=True)
class StockRebuildResult:
    """Resultado de reconstruccion de StockBin."""

    rebuilt_bins: int
    inconsistencies: list[str]


@dataclass(frozen=True)
class ItemUOMRow:
    """Fila de conversion de UOM para un item."""

    uom_code: str
    conversion_factor: Decimal


def _decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise InventoryServiceError("La conversion UOM debe ser un numero valido.") from exc


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


def _validate_batch(line, item):
    batch_id = getattr(line, "batch_id", None)
    if not batch_id:
        raise InventoryServiceError("El item requiere lote.")
    batch = database.session.get(Batch, batch_id)
    if not batch or batch.item_code != item.code or not batch.is_active:
        raise InventoryServiceError("El lote no existe, esta inactivo o no pertenece al item.")


def _validate_serial(line, item, outgoing):
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


def validate_batch_serial(line: Any, *, outgoing: bool) -> None:
    """Valida obligatoriedad y disponibilidad de lote/serial en una linea."""
    item = database.session.get(Item, getattr(line, "item_code", None))
    if not item or not item.is_stock_item:
        return
    if item.has_batch:
        _validate_batch(line, item)
    if item.has_serial_no:
        _validate_serial(line, item, outgoing)


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


def list_item_uom_conversions(item_code: str) -> list[ItemUOMConversion]:
    """Lista las conversiones UOM configuradas para un item."""
    query = select(ItemUOMConversion).filter_by(item_code=item_code).order_by(ItemUOMConversion.from_uom)
    return list(database.session.execute(query).scalars().all())


def parse_item_uom_rows(form: Mapping[str, Any]) -> list[ItemUOMRow]:
    """Convierte las filas UOM enviadas por formulario en objetos tipados."""
    codes = _request_values(form, "uom_code")
    factors = _request_values(form, "uom_conversion_factor")
    rows: list[ItemUOMRow] = []
    for index, code in enumerate(codes):
        factor = factors[index] if index < len(factors) else ""
        cleaned_code = str(code or "").strip()
        cleaned_factor = str(factor or "").strip()
        if not cleaned_code and not cleaned_factor:
            continue
        rows.append(ItemUOMRow(uom_code=cleaned_code, conversion_factor=_decimal_value(cleaned_factor)))
    return rows


def validate_item_uom_rows(default_uom: str, rows: list[ItemUOMRow]) -> None:
    """Valida que las conversiones UOM sean coherentes con la unidad base."""
    if not default_uom:
        raise InventoryServiceError("La unidad de medida predeterminada es obligatoria.")
    if database.session.execute(select(UOM).filter_by(code=default_uom)).scalar_one_or_none() is None:
        raise InventoryServiceError("La unidad de medida predeterminada no existe.")
    seen: set[str] = set()
    for row in rows:
        if not row.uom_code:
            raise InventoryServiceError("Todas las UOM adicionales deben tener una unidad seleccionada.")
        if row.uom_code == default_uom:
            raise InventoryServiceError("La UOM adicional no puede ser la misma unidad predeterminada.")
        if row.uom_code in seen:
            raise InventoryServiceError("No se puede repetir la misma UOM adicional.")
        if database.session.execute(select(UOM).filter_by(code=row.uom_code)).scalar_one_or_none() is None:
            raise InventoryServiceError(f"La UOM '{row.uom_code}' no existe.")
        if row.conversion_factor <= 0:
            raise InventoryServiceError("La conversión a la unidad predeterminada debe ser mayor que cero.")
        seen.add(row.uom_code)


def create_item_with_uoms(
    *,
    code: str,
    name: str,
    description: str | None,
    item_type: str,
    is_stock_item: bool,
    default_uom: str,
    uom_rows: list[ItemUOMRow],
) -> Item:
    """Crea un item junto con sus conversiones de UOM."""
    validate_item_uom_rows(default_uom, uom_rows)
    resolved_item_type = item_type or "goods"
    resolved_stock_flag = is_stock_item if resolved_item_type != "service" else False
    item = Item(
        code=code,
        name=name,
        description=description,
        item_type=resolved_item_type,
        is_stock_item=resolved_stock_flag,
        default_uom=default_uom,
    )
    database.session.add(item)
    database.session.flush()
    for row in uom_rows:
        database.session.add(
            ItemUOMConversion(
                item_code=item.code,
                from_uom=row.uom_code,
                to_uom=default_uom,
                conversion_factor=row.conversion_factor,
            )
        )
    return item


def default_uom_change_allowed(item_code: str, new_default_uom: str) -> bool:
    """Indica si una nueva unidad base puede aplicarse al item."""
    if not item_code or not new_default_uom:
        return True
    current_item = database.session.execute(select(Item).filter_by(code=item_code)).scalar_one_or_none()
    if not current_item:
        return True
    if current_item.default_uom == new_default_uom:
        return True
    return not _item_has_records(item_code)


def _item_has_records(item_code: str) -> bool:
    """Detecta si el item ya participa en documentos operativos o de stock."""
    tables = (
        StockLedgerEntry.__table__,
        StockEntryItem.__table__,
        PurchaseOrderItem.__table__,
        PurchaseReceiptItem.__table__,
        PurchaseInvoiceItem.__table__,
        SalesOrderItem.__table__,
        DeliveryNoteItem.__table__,
        SalesInvoiceItem.__table__,
    )
    for table in tables:
        if table.c.get("item_code") is None:
            continue
        statement = select(1).select_from(table).where(table.c.item_code == item_code).limit(1)
        if database.session.execute(statement).first():
            return True
    return False


def _request_values(form: Mapping[str, Any], key: str) -> list[Any]:
    """Obtiene una lista de valores desde un formulario o mapping multi-valor."""
    if hasattr(form, "getlist"):
        return list(form.getlist(key))  # type: ignore[attr-defined]
    value = form.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
