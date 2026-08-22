# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de órdenes de compra."""

from datetime import date
from decimal import Decimal
from typing import List, Dict, Any
from cacao_accounting.imports.utils.validation import is_period_open
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.database import PurchaseOrder, PurchaseOrderItem, Party, Warehouse, database
from cacao_accounting.document_identifiers import assign_document_identifier


class PurchaseOrderAdapter(BaseImportAdapter):
    """Adaptador para Órdenes de Compra."""

    columns = [
        "document_ref",
        "fecha",
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
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Construye un objeto PurchaseOrder y sus ítems."""
        first_row = document_data[0]
        supplier_id = first_row.get("proveedor")
        supplier = database.session.execute(
            database.select(Party).filter_by(id=supplier_id, is_supplier=True)
        ).scalar_one_or_none()

        posting_date = None
        try:
            posting_date = date.fromisoformat(str(first_row.get("fecha")))
        except ValueError:
            pass

        orden = PurchaseOrder(
            supplier_id=supplier_id,
            supplier_name=supplier.name if supplier else None,
            company=context.get("company_id"),
            posting_date=posting_date,
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
                warehouse=row.get("bodega"),
            )
            items.append(item)
            total_qty += qty
            total += amount

        orden.total_qty = total_qty
        orden.total = total
        orden.net_total = total
        orden.grand_total = total
        orden.base_total = total

        return {"order": orden, "items": items, "naming_series_id": context.get("sequence_id")}

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
