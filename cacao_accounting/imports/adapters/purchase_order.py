# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de órdenes de compra."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, cast
from cacao_accounting.imports.utils.validation import (
    is_period_open,
    item_import_uom,
    validate_import_item,
    validate_import_uom,
    validate_import_warehouse,
)
from cacao_accounting.imports.utils.dates import parse_import_date
from cacao_accounting.imports.adapters.base import (
    BaseImportAdapter,
    COMMON_DOCUMENT_HEADER_FIELDS,
    normalize_header_text,
)
from cacao_accounting.database import CompanyParty, PurchaseOrder, PurchaseOrderItem, Party, database
from cacao_accounting.document_flow.context import company_currency
from cacao_accounting.document_flow.service import qty_in_base_uom
from cacao_accounting.document_identifiers import assign_document_identifier
from cacao_accounting.i18n import _


def _finite_decimal(value: Any, field: str) -> Decimal:
    """Convierte un valor de importación y rechaza números no finitos."""
    try:
        amount = Decimal(str(value if value not in (None, "") else "0"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(_("%(field)s debe ser un número decimal válido.") % {"field": field}) from exc
    if not amount.is_finite():
        raise ValueError(_("%(field)s debe ser finito.") % {"field": field})
    return amount


def _validate_purchase_order_rows(rows: List[Dict[str, Any]], company_id: str) -> List[str]:
    """Validate warehouse ownership and numeric purchase row values."""
    errors = []
    for row in rows:
        item, item_error = validate_import_item(row.get("producto"), "purchase_order")
        if item_error:
            errors.append(item_error)
        if item is not None:
            uom_error = validate_import_uom(item_import_uom(item))
            if uom_error:
                errors.append(uom_error)
        warehouse_code = row.get("bodega")
        warehouse_error = validate_import_warehouse(warehouse_code, company_id)
        if warehouse_error:
            errors.append(warehouse_error)
        try:
            quantity = _finite_decimal(row.get("cantidad"), "cantidad")
            rate = _finite_decimal(row.get("precio_unitario"), "precio_unitario")
            if rate < 0:
                raise ValueError(_("El precio unitario no puede ser negativo."))
            qty_in_base_uom(row.get("producto"), quantity, None)
        except (InvalidOperation, ValueError) as exc:
            errors.append(str(exc))
    return errors


def _build_purchase_order_items(
    document_data: List[Dict[str, Any]], exchange_rate: Decimal
) -> tuple[List[PurchaseOrderItem], Decimal, Decimal]:
    """Build purchase order lines and calculate their quantity and amount totals."""
    items = []
    total_qty = Decimal("0")
    total = Decimal("0")
    for row in document_data:
        item, item_error = validate_import_item(row.get("producto"), "purchase_order")
        if item_error:
            raise ValueError(item_error)
        if item is None:
            raise ValueError(_("El artículo no existe."))
        effective_uom = item_import_uom(item)
        uom_error = validate_import_uom(effective_uom)
        if uom_error:
            raise ValueError(uom_error)
        qty = _finite_decimal(row.get("cantidad"), "cantidad")
        rate = _finite_decimal(row.get("precio_unitario"), "precio_unitario")
        if rate < 0:
            raise ValueError(_("El precio unitario no puede ser negativo."))
        amount = qty * rate
        items.append(
            PurchaseOrderItem(
                item_code=row.get("producto"),
                item_name=row.get("descripcion") or "",
                qty=qty,
                uom=effective_uom,
                qty_in_base_uom=qty_in_base_uom(row.get("producto"), qty, effective_uom),
                rate=rate,
                amount=amount,
                base_rate=(rate * exchange_rate).quantize(Decimal("0.0001")),
                base_amount=(amount * exchange_rate).quantize(Decimal("0.0001")),
                warehouse=row.get("bodega"),
            )
        )
        total_qty += qty
        total += amount
    return items, total_qty, total


class PurchaseOrderAdapter(BaseImportAdapter):
    """Adaptador para Órdenes de Compra."""

    columns = [
        "document_ref",
        "fecha",
        "moneda",
        "tipo_cambio",
        "proveedor",
        "producto",
        "descripcion",
        "cantidad",
        "precio_unitario",
        "impuesto",
        "bodega",
    ]
    required_columns = ["document_ref", "fecha", "proveedor", "producto", "cantidad", "precio_unitario"]

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Validate purchase order document."""
        header_fields = dict(COMMON_DOCUMENT_HEADER_FIELDS)
        header_fields["proveedor"] = (("proveedor",), normalize_header_text)
        errors = self.validate_header_consistency(document_data, header_fields)
        company_id = (context or {}).get("company_id") or ""
        supplier_id = document_data[0].get("proveedor")
        if supplier_id and self._supplier_for_company(supplier_id, company_id) is None:
            errors.append(_("El proveedor debe existir, estar activo y habilitado para la compañía."))
        posting_date = None
        try:
            posting_date = parse_import_date(document_data[0].get("fecha"))
            if not is_period_open(company_id, posting_date):
                errors.append(f"El periodo contable para la fecha {posting_date} está cerrado o no existe.")
        except (ValueError, TypeError):
            pass
        errors.extend(_validate_purchase_order_rows(document_data, company_id))
        if posting_date is not None and not errors:
            try:
                self._currency_and_rate(document_data[0], company_id, posting_date)
            except ValueError as exc:
                errors.append(str(exc))
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Construye un objeto PurchaseOrder y sus ítems."""
        first_row = document_data[0]
        company_id = str(context.get("company_id") or "")
        supplier_id = first_row.get("proveedor")
        supplier = self._supplier_for_company(supplier_id, company_id)
        if supplier is None:
            raise ValueError(_("El proveedor debe existir, estar activo y habilitado para la compañía."))

        posting_date = None
        try:
            posting_date = parse_import_date(first_row.get("fecha"))
        except ValueError:
            pass

        transaction_currency, base_currency, exchange_rate = self._currency_and_rate(first_row, company_id, posting_date)
        orden = PurchaseOrder(
            supplier_id=supplier_id,
            supplier_name=supplier.name,
            company=company_id,
            posting_date=posting_date,
            transaction_currency=transaction_currency,
            base_currency=base_currency,
            exchange_rate=exchange_rate,
            remarks=f"Importación masiva: {first_row.get('document_ref')}",
            docstatus=0,
        )

        items, total_qty, total = _build_purchase_order_items(document_data, exchange_rate)

        orden.total_qty = total_qty
        orden.total = total
        orden.net_total = total
        orden.grand_total = total
        orden.base_total = (total * exchange_rate).quantize(Decimal("0.0001"))

        return {"order": orden, "items": items, "naming_series_id": context.get("sequence_id")}

    @staticmethod
    def _supplier_for_company(supplier_id: Any, company_id: str) -> Party | None:
        """Resolve an active supplier enabled for the importing company."""
        if not supplier_id or not company_id:
            return None
        return database.session.execute(
            database.select(Party)
            .join(CompanyParty, CompanyParty.party_id == Party.id)
            .filter(
                Party.id == supplier_id,
                Party.is_supplier.is_(True),
                Party.is_active.is_(True),
                CompanyParty.company == company_id,
                CompanyParty.is_active.is_(True),
            )
        ).scalar_one_or_none()

    @staticmethod
    def _currency_and_rate(
        first_row: Dict[str, Any], company_id: str, posting_date: date | None
    ) -> tuple[str | None, str | None, Decimal]:
        """Resolve an explicit or historical rate for an imported purchase order."""
        base_currency = company_currency(company_id)
        transaction_currency = first_row.get("moneda") or base_currency
        if not transaction_currency or transaction_currency == base_currency:
            return transaction_currency, base_currency, Decimal("1")
        raw_rate = first_row.get("tipo_cambio")
        if raw_rate:
            rate_dec = _finite_decimal(raw_rate, "tipo de cambio")
        else:
            from cacao_accounting.contabilidad.posting import _lookup_exchange_rate

            resolved = cast(
                Decimal | None,
                _lookup_exchange_rate(transaction_currency, cast(str, base_currency), posting_date) if posting_date else None,
            )
            rate_dec = _finite_decimal(resolved, "tipo de cambio") if resolved is not None else Decimal("0")
        if not rate_dec.is_finite():
            raise ValueError(_("Tipo de cambio debe ser finito."))
        if rate_dec <= 0:
            raise ValueError(
                _("No existe tipo de cambio para %(transaction_currency)s -> %(base_currency)s en %(posting_date)s.")
                % {
                    "transaction_currency": transaction_currency,
                    "base_currency": base_currency,
                    "posting_date": posting_date,
                }
            )
        return transaction_currency, base_currency, rate_dec

    def persist_document(self, document: Any) -> None:
        """Guarda la orden de compra y sus ítems en la base de datos."""
        orden = document["order"]
        items = document["items"]
        naming_series_id = document["naming_series_id"]

        database.session.add(orden)
        database.session.flush()

        assign_document_identifier(
            document=orden,
            entity_type="purchase_order",
            posting_date_raw=orden.posting_date,
            naming_series_id=naming_series_id,
        )

        for item in items:
            item.purchase_order_id = orden.id
            database.session.add(item)
