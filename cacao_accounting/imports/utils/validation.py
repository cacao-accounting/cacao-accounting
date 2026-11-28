# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validation utilities for accounting."""

from datetime import date
from sqlalchemy import select
from cacao_accounting.database import database, AccountingPeriod, Item, UOM, Warehouse
from cacao_accounting.i18n import _

PURCHASE_ITEM_DOCTYPES = {
    "purchase_request",
    "purchase_quotation",
    "supplier_quotation",
    "purchase_order",
    "purchase_receipt",
    "purchase_invoice",
}
SALES_ITEM_DOCTYPES = {"sales_request", "sales_quotation", "sales_order", "delivery_note", "sales_invoice"}


def is_period_open(company: str, posting_date: date) -> bool:
    """Check if the accounting period for the given company and date is open."""
    period = (
        database.session.execute(
            select(AccountingPeriod)
            .filter_by(entity=company, is_closed=False, enabled=True)
            .where(AccountingPeriod.start <= posting_date)
            .where(AccountingPeriod.end >= posting_date)
        )
        .scalars()
        .first()
    )
    return period is not None


def validate_import_item(item_code: str | None, document_type: str) -> tuple[Item | None, str | None]:
    """Resolve an item and enforce activity and role for the imported document."""
    if not item_code:
        return None, None
    item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one_or_none()
    if item is None:
        return None, _("El artículo no existe.")
    if not item.is_active:
        return item, _("El artículo '%(item)s' está inactivo.") % {"item": item.code}
    if document_type in PURCHASE_ITEM_DOCTYPES and not item.is_purchase_item:
        return item, _("El artículo '%(item)s' no está habilitado para compra.") % {"item": item.code}
    if document_type in SALES_ITEM_DOCTYPES and not item.is_sale_item:
        return item, _("El artículo '%(item)s' no está habilitado para venta.") % {"item": item.code}
    return item, None


def item_import_uom(item: Item, requested_uom: str | None = None) -> str | None:
    """Return the line UOM or the base UOM used by quantity conversion."""
    if requested_uom:
        return requested_uom
    return item.default_uom


def validate_import_uom(uom_code: str | None) -> str | None:
    """Reject missing or inactive units used by imported line items."""
    if not uom_code:
        return None
    uom = database.session.execute(database.select(UOM).filter_by(code=uom_code)).scalar_one_or_none()
    if uom is None:
        return _("La unidad de medida no existe.")
    if not uom.is_active:
        return _("La unidad de medida está inactiva.")
    return None


def validate_import_warehouse(warehouse_code: str | None, company_id: str) -> str | None:
    """Ensure an optional warehouse is active and belongs to the company."""
    if not warehouse_code:
        return None
    warehouse = database.session.execute(database.select(Warehouse).filter_by(code=warehouse_code)).scalar_one_or_none()
    if warehouse is None or warehouse.company != company_id or not warehouse.is_active:
        return _("La bodega '%(warehouse)s' no pertenece a la compañía o está inactiva.") % {"warehouse": warehouse_code}
    return None
