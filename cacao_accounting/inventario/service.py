# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de inventario para UOM, lote/serial y reconstruccion de bins."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import func, select

from cacao_accounting.database import (
    Accounts,
    Batch,
    CostCenter,
    Entity,
    Item,
    ItemAccount,
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
    obtiene_texto_unico,
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


@dataclass(frozen=True)
class ItemAccountRow:
    """Fila de cuenta contable por compania para un item."""

    company: str
    expense_account_id: str | None
    cost_center_code: str | None = None
    income_account_id: str | None = None
    cogs_account_id: str | None = None
    stock_adjustment_account_id: str | None = None


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
        reserved_qty = Decimal("0")
        if not bin_row:
            bin_row = StockBin(company=group_company, item_code=group_item, warehouse=group_warehouse)
            database.session.add(bin_row)
        else:
            reserved_qty = _decimal_value(bin_row.reserved_qty)
        old_qty = _decimal_value(bin_row.actual_qty)
        if old_qty != qty:
            inconsistencies.append(f"{group_item}/{group_warehouse}: {old_qty} -> {qty}")
        bin_row.actual_qty = qty
        bin_row.reserved_qty = reserved_qty
        bin_row.stock_value = value
        bin_row.valuation_rate = valuation_rate
        rebuilt += 1
    return StockRebuildResult(rebuilt_bins=rebuilt, inconsistencies=inconsistencies)


def update_item_with_uoms(
    item_code: str,
    *,
    name: str,
    description: str | None = None,
    item_type: str = "goods",
    is_stock_item: bool = False,
    is_purchase_item: bool = True,
    is_sale_item: bool = True,
    item_category_id: str | None = None,
    default_uom: str,
    purchase_uom: str | None = None,
    sale_uom: str | None = None,
    default_warehouse_id: str | None = None,
    default_supplier_id: str | None = None,
    allow_negative_stock: bool = False,
    min_stock_qty: Decimal | None = None,
    max_stock_qty: Decimal | None = None,
    reorder_level: Decimal | None = None,
    standard_rate: Decimal | None = None,
    last_purchase_rate: Decimal | None = None,
    currency: str | None = None,
    brand: str | None = None,
    model_name: str | None = None,
    barcode: str | None = None,
    has_batch: bool = False,
    has_serial_no: bool = False,
    has_expiry_date: bool = False,
    uom_rows: list[ItemUOMRow] | None = None,
    account_rows: list[ItemAccountRow] | None = None,
) -> Item:
    """Actualiza un item existente junto con sus conversiones de UOM.

    Reemplaza por completo las conversiones UOM y la configuracion contable.
    """
    item = database.session.execute(select(Item).filter_by(code=item_code)).scalar_one_or_none()
    if item is None:
        raise InventoryServiceError(f"El item '{item_code}' no existe.")
    if not default_uom_change_allowed(item_code, default_uom):
        raise InventoryServiceError("No se puede cambiar la UOM base si el item tiene transacciones.")
    resolved_uom_rows = uom_rows or []
    resolved_account_rows = account_rows or []
    resolved_item_type = item_type or "goods"
    resolved_stock_flag = is_stock_item if resolved_item_type != "service" else False
    validate_item_uom_rows(default_uom, resolved_uom_rows)
    validate_item_account_rows(resolved_item_type, resolved_stock_flag, resolved_account_rows)
    item.name = name
    item.description = description
    item.item_type = resolved_item_type
    item.is_stock_item = resolved_stock_flag
    item.is_purchase_item = is_purchase_item
    item.is_sale_item = is_sale_item
    item.item_category_id = item_category_id
    item.default_uom = default_uom
    item.purchase_uom = purchase_uom
    item.sale_uom = sale_uom
    item.default_warehouse_id = default_warehouse_id
    item.default_supplier_id = default_supplier_id
    item.allow_negative_stock = allow_negative_stock
    item.min_stock_qty = min_stock_qty
    item.max_stock_qty = max_stock_qty
    item.reorder_level = reorder_level
    item.standard_rate = standard_rate
    item.last_purchase_rate = last_purchase_rate
    item.currency = currency
    item.brand = brand
    item.model_name = model_name
    item.barcode = barcode
    item.has_batch = has_batch
    item.has_serial_no = has_serial_no
    item.has_expiry_date = has_expiry_date
    database.session.flush()
    for old in database.session.execute(select(ItemUOMConversion).filter_by(item_code=item_code)).scalars():
        database.session.delete(old)
    for uom_row in resolved_uom_rows:
        database.session.add(
            ItemUOMConversion(
                item_code=item.code,
                from_uom=uom_row.uom_code,
                to_uom=default_uom,
                conversion_factor=uom_row.conversion_factor,
            )
        )
    for old_account in database.session.execute(select(ItemAccount).filter_by(item_code=item_code)).scalars():
        database.session.delete(old_account)
    for account_row in resolved_account_rows:
        database.session.add(
            ItemAccount(
                item_code=item.code,
                company=account_row.company,
                expense_account_id=account_row.expense_account_id,
                income_account_id=account_row.income_account_id,
                cogs_account_id=account_row.cogs_account_id,
                stock_adjustment_account_id=account_row.stock_adjustment_account_id,
                cost_center_code=account_row.cost_center_code,
            )
        )
    return item


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
    code: str | None = None,
    name: str,
    description: str | None = None,
    item_type: str = "goods",
    is_stock_item: bool = False,
    is_purchase_item: bool = True,
    is_sale_item: bool = True,
    item_category_id: str | None = None,
    default_uom: str,
    purchase_uom: str | None = None,
    sale_uom: str | None = None,
    default_warehouse_id: str | None = None,
    default_supplier_id: str | None = None,
    allow_negative_stock: bool = False,
    min_stock_qty: Decimal | None = None,
    max_stock_qty: Decimal | None = None,
    reorder_level: Decimal | None = None,
    standard_rate: Decimal | None = None,
    last_purchase_rate: Decimal | None = None,
    currency: str | None = None,
    brand: str | None = None,
    model_name: str | None = None,
    barcode: str | None = None,
    has_batch: bool = False,
    has_serial_no: bool = False,
    has_expiry_date: bool = False,
    uom_rows: list[ItemUOMRow] | None = None,
    account_rows: list[ItemAccountRow] | None = None,
) -> Item:
    """Crea un item junto con sus conversiones de UOM.

    Si ``code`` no se proporciona, se genera automaticamente mediante
    :func:`~cacao_accounting.database.helpers.generate_identifier`.
    """
    resolved_uom_rows = uom_rows or []
    resolved_account_rows = account_rows or []
    validate_item_uom_rows(default_uom, resolved_uom_rows)
    resolved_item_type = item_type or "goods"
    resolved_stock_flag = is_stock_item if resolved_item_type != "service" else False
    validate_item_account_rows(
        resolved_item_type,
        resolved_stock_flag,
        resolved_account_rows,
    )
    item_id = obtiene_texto_unico()
    if code is None:
        from cacao_accounting.document_identifiers import generate_entity_code

        code = generate_entity_code(entity_type="item", entity_id=item_id)
    item = Item(
        id=item_id,
        code=code,
        name=name,
        description=description,
        item_type=resolved_item_type,
        is_stock_item=resolved_stock_flag,
        is_purchase_item=is_purchase_item,
        is_sale_item=is_sale_item,
        item_category_id=item_category_id,
        default_uom=default_uom,
        purchase_uom=purchase_uom,
        sale_uom=sale_uom,
        default_warehouse_id=default_warehouse_id,
        default_supplier_id=default_supplier_id,
        allow_negative_stock=allow_negative_stock,
        min_stock_qty=min_stock_qty,
        max_stock_qty=max_stock_qty,
        reorder_level=reorder_level,
        standard_rate=standard_rate,
        last_purchase_rate=last_purchase_rate,
        currency=currency,
        brand=brand,
        model_name=model_name,
        barcode=barcode,
        has_batch=has_batch,
        has_serial_no=has_serial_no,
        has_expiry_date=has_expiry_date,
    )
    database.session.add(item)
    database.session.flush()
    for uom_row in resolved_uom_rows:
        database.session.add(
            ItemUOMConversion(
                item_code=item.code,
                from_uom=uom_row.uom_code,
                to_uom=default_uom,
                conversion_factor=uom_row.conversion_factor,
            )
        )
    for account_row in resolved_account_rows:
        database.session.add(
            ItemAccount(
                item_code=item.code,
                company=account_row.company,
                expense_account_id=account_row.expense_account_id,
                income_account_id=account_row.income_account_id,
                cogs_account_id=account_row.cogs_account_id,
                stock_adjustment_account_id=account_row.stock_adjustment_account_id,
                cost_center_code=account_row.cost_center_code,
            )
        )
    return item


def list_item_account_rows(item_code: str) -> list[ItemAccount]:
    """Lista la configuracion contable por compania de un item."""
    query = select(ItemAccount).filter_by(item_code=item_code).order_by(ItemAccount.company)
    return list(database.session.execute(query).scalars().all())


def parse_item_account_rows(form: Mapping[str, Any]) -> list[ItemAccountRow]:
    """Convierte filas contables por compania enviadas por formulario en objetos tipados."""
    companies = _request_values(form, "account_company")
    expense_accounts = _request_values(form, "expense_account_id")
    income_accounts = _request_values(form, "income_account_id")
    cogs_accounts = _request_values(form, "cogs_account_id")
    stock_adjustment_accounts = _request_values(form, "stock_adjustment_account_id")
    cost_centers = _request_values(form, "cost_center_code")
    rows: list[ItemAccountRow] = []
    for index, company in enumerate(companies):
        expense_account_id = expense_accounts[index] if index < len(expense_accounts) else ""
        income_account_id = income_accounts[index] if index < len(income_accounts) else ""
        cogs_account_id = cogs_accounts[index] if index < len(cogs_accounts) else ""
        stock_adjustment_account_id = stock_adjustment_accounts[index] if index < len(stock_adjustment_accounts) else ""
        cost_center_code = cost_centers[index] if index < len(cost_centers) else ""
        cleaned_company = str(company or "").strip()
        cleaned_expense = str(expense_account_id or "").strip() or None
        cleaned_income = str(income_account_id or "").strip() or None
        cleaned_cogs = str(cogs_account_id or "").strip() or None
        cleaned_stock_adjustment = str(stock_adjustment_account_id or "").strip() or None
        cleaned_cost_center = str(cost_center_code or "").strip() or None
        if not cleaned_company and not cleaned_expense and not cleaned_cost_center:
            continue
        rows.append(
            ItemAccountRow(
                company=cleaned_company,
                expense_account_id=cleaned_expense,
                income_account_id=cleaned_income,
                cogs_account_id=cleaned_cogs,
                stock_adjustment_account_id=cleaned_stock_adjustment,
                cost_center_code=cleaned_cost_center,
            )
        )
    return rows


def validate_item_account_rows(
    item_type: str,
    is_stock_item: bool,
    rows: list[ItemAccountRow],
) -> None:
    """Valida la configuracion contable del item por compania."""
    requires_expense_by_company = item_type == "service" or not is_stock_item
    if requires_expense_by_company and not rows:
        raise InventoryServiceError(
            "Los servicios y articulos no inventariables requieren cuenta de gasto predeterminada por compañia."
        )

    seen_companies: set[str] = set()
    for row in rows:
        if not row.company:
            raise InventoryServiceError("Cada fila contable del item debe indicar una compañia.")
        if row.company in seen_companies:
            raise InventoryServiceError("No se puede repetir la misma compañia en la configuracion contable del item.")
        company = database.session.execute(select(Entity).filter_by(code=row.company)).scalar_one_or_none()
        if company is None:
            raise InventoryServiceError(f"La compañia '{row.company}' no existe.")
        _validate_item_account(row.company, row.expense_account_id, "expense", "gasto")
        _validate_item_account(row.company, row.income_account_id, "income", "ingreso")
        _validate_item_account(row.company, row.cogs_account_id, "cogs", "costo de venta")
        _validate_item_account(row.company, row.stock_adjustment_account_id, "stock_adjustment", "ajuste de inventario")
        _validate_cost_center(row.company, row.cost_center_code)
        if requires_expense_by_company and not row.expense_account_id:
            raise InventoryServiceError(
                "Los servicios y articulos no inventariables requieren cuenta de gasto predeterminada por compañia."
            )
        if requires_expense_by_company and not row.cost_center_code:
            raise InventoryServiceError(
                "Los servicios y articulos no inventariables requieren centro de costo predeterminado por compañia."
            )
        seen_companies.add(row.company)


def _validate_item_account(company: str, account_id: str | None, expected_type: str, label: str) -> None:
    """Valida que una cuenta exista, pertenezca a la compañia y coincida con el tipo esperado."""
    if not account_id:
        return
    account = database.session.get(Accounts, account_id)
    if account is None or account.entity != company:
        raise InventoryServiceError(f"La cuenta de {label} no pertenece a la compañia seleccionada.")
    account_type = (account.account_type or "").strip().lower()
    expected_aliases = {
        "expense": {"expense", "cogs"},
        "income": {"income"},
        "cogs": {"cogs", "expense"},
        "inventory": {"inventory", "current_asset"},
        "stock_adjustment": {"expense", "income"},
    }[expected_type]
    if account_type and account_type not in expected_aliases:
        raise InventoryServiceError(f"La cuenta de {label} debe ser valida para {label} en la compañia.")


def _validate_cost_center(company: str, cost_center_code: str | None) -> None:
    """Valida que el centro de costo exista y pertenezca a la compañia."""
    if not cost_center_code:
        return
    cost_center = database.session.execute(
        select(CostCenter).filter_by(entity=company, code=cost_center_code, active=True, enabled=True)
    ).scalar_one_or_none()
    if cost_center is None:
        raise InventoryServiceError("El centro de costo no pertenece a la compañia seleccionada.")


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
