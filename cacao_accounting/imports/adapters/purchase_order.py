# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de órdenes de compra."""

from datetime import date
from decimal import Decimal
from typing import List, Dict, Any
from cacao_accounting.imports.utils.validation import is_period_open
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.database import PurchaseOrder, PurchaseOrderItem, Party, Warehouse, database
from cacao_accounting.document_flow.context import company_currency
from cacao_accounting.document_identifiers import assign_document_identifier


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
        errors = []
        company_id = (context or {}).get("company_id") or ""
        posting_date = None
        try:
            posting_date = date.fromisoformat(str(document_data[0].get("fecha")))
            if not is_period_open(company_id, posting_date):
                errors.append(f"El periodo contable para la fecha {posting_date} está cerrado o no existe.")
        except (ValueError, TypeError):
            pass
        for row in document_data:
            warehouse_code = row.get("bodega")
            if not warehouse_code:
                continue
            warehouse = database.session.execute(
                database.select(Warehouse).filter_by(code=warehouse_code)
            ).scalar_one_or_none()
            if warehouse is None or warehouse.company != company_id or not warehouse.is_active:
                errors.append(f"La bodega '{warehouse_code}' no pertenece a la compañía o está inactiva.")
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
        supplier = database.session.execute(
            database.select(Party).filter_by(id=supplier_id, is_supplier=True)
        ).scalar_one_or_none()

        posting_date = None
        try:
            posting_date = date.fromisoformat(str(first_row.get("fecha")))
        except ValueError:
            pass

        transaction_currency, base_currency, exchange_rate = self._currency_and_rate(first_row, company_id, posting_date)
        orden = PurchaseOrder(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else None,
            company=company_id,
            posting_date=posting_date,
            transaction_currency=transaction_currency,
            base_currency=base_currency,
            exchange_rate=exchange_rate,
            remarks=f"Importación masiva: {first_row.get('document_ref')}",
            docstatus=0,
        )

        items = []
        total_qty = Decimal("0")
        total = Decimal("0")

        for row in document_data:
            qty = Decimal(str(row.get("cantidad") or 0))
            rate = Decimal(str(row.get("precio_unitario") or 0))
            amount = qty * rate

            item = PurchaseOrderItem(
                item_code=row.get("producto"),
                item_name=row.get("descripcion") or "",
                qty=qty,
                rate=rate,
                amount=amount,
                base_rate=(rate * exchange_rate).quantize(Decimal("0.0001")),
                base_amount=(amount * exchange_rate).quantize(Decimal("0.0001")),
                warehouse=row.get("bodega"),
            )
            items.append(item)
            total_qty += qty
            total += amount

        orden.total_qty = total_qty
        orden.total = total
        orden.net_total = total
        orden.grand_total = total
        orden.base_total = (total * exchange_rate).quantize(Decimal("0.0001"))

        return {"order": orden, "items": items, "naming_series_id": context.get("sequence_id")}

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
            rate_dec = Decimal(str(raw_rate))
        else:
            from cacao_accounting.contabilidad.posting import _lookup_exchange_rate

            rate = _lookup_exchange_rate(transaction_currency, base_currency, posting_date) if posting_date else None
            rate_dec = Decimal(str(rate)) if rate is not None else Decimal("0")
        if rate_dec <= 0:
            raise ValueError(f"No existe tipo de cambio para {transaction_currency} -> {base_currency} en {posting_date}.")
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
