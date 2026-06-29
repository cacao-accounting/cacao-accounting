# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptadores para documentos transaccionales de Compras y Ventas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseRequest,
    PurchaseRequestItem,
    SalesInvoice,
    SalesInvoiceItem,
    SalesOrder,
    SalesOrderItem,
    SalesQuotation,
    SalesQuotationItem,
    SalesRequest,
    SalesRequestItem,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)
from cacao_accounting.document_identifiers import assign_document_identifier
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.imports.utils.validation import is_period_open


@dataclass(frozen=True)
class TransactionImportConfig:
    """Configuración declarativa para importar un documento transaccional."""

    entity_type: str
    header_model: type[Any]
    item_model: type[Any]
    parent_field: str
    party_type: str | None = None
    party_field: str | None = None
    party_name_field: str | None = None
    source_field: str | None = None
    source_column: str | None = None
    receipt_fields: tuple[str, ...] = ()
    invoice_fields: tuple[str, ...] = ()
    include_batch_serial: bool = False


class TransactionDocumentAdapter(BaseImportAdapter):
    """Adaptador genérico para documentos por encabezado y líneas."""

    columns = [
        "document_ref",
        "fecha",
        "tercero",
        "documento_origen",
        "producto",
        "descripcion",
        "uom",
        "cantidad",
        "precio_unitario",
        "bodega",
        "lote",
        "serie",
        "notas",
    ]
    required_columns = ["document_ref", "fecha", "producto", "cantidad", "precio_unitario"]

    def __init__(self, config: TransactionImportConfig) -> None:
        """Inicializa el adaptador con la configuración del documento."""
        self.config = config

    def validate_row(self, row_data: dict[str, Any]) -> list[str]:
        """Valida fila individual incluyendo montos numéricos."""
        errors = super().validate_row(row_data)
        for field in ("cantidad", "precio_unitario"):
            try:
                Decimal(str(row_data.get(field) or 0))
            except (InvalidOperation, ValueError):
                errors.append(f"Valor numérico inválido en columna '{field}'.")
        return errors

    def validate_document(self, document_data: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[str]:
        """Valida fecha, período y tercero requerido por el documento."""
        errors = []
        first_row = document_data[0]

        if self.config.party_field and not first_row.get("tercero"):
            errors.append("La columna tercero es obligatoria para este tipo de registro.")

        try:
            posting_date = date.fromisoformat(str(first_row.get("fecha")))
        except (ValueError, TypeError):
            errors.append("La fecha debe usar formato ISO YYYY-MM-DD.")
            return errors

        company_id = (context or {}).get("company_id") or ""
        if not is_period_open(company_id, posting_date):
            errors.append(f"El periodo contable para la fecha {posting_date} está cerrado o no existe.")
        return errors

    def build_document(self, document_data: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        """Construye encabezado e ítems desde las filas del archivo."""
        first_row = document_data[0]
        posting_date = date.fromisoformat(str(first_row.get("fecha")))
        header = self.config.header_model(
            company=context.get("company_id"),
            posting_date=posting_date,
            document_date=posting_date,
            docstatus=0,
            remarks=first_row.get("notas") or f"Importación masiva: {first_row.get('document_ref')}",
        )
        self._apply_party(header, first_row.get("tercero"))
        self._apply_source(header, first_row.get("documento_origen"))

        items = []
        total_qty = Decimal("0")
        total = Decimal("0")
        for row in document_data:
            qty = Decimal(str(row.get("cantidad") or 0))
            rate = Decimal(str(row.get("precio_unitario") or 0))
            amount = qty * rate
            item = self.config.item_model(
                item_code=row.get("producto"),
                item_name=row.get("descripcion") or "",
                qty=qty,
                uom=row.get("uom") or None,
                qty_in_base_uom=qty,
                rate=rate,
                amount=amount,
                warehouse=row.get("bodega") or None,
            )
            self._apply_optional_item_fields(item, amount, row)
            items.append(item)
            total_qty += qty
            total += amount

        self._apply_totals(header, total_qty, total)
        return {
            "header": header,
            "items": items,
            "entity_type": self.config.entity_type,
            "naming_series_id": context.get("sequence_id"),
        }

    def persist_document(self, document: Any) -> None:
        """Persist header, assign identifier, and save document lines."""
        header = document["header"]
        database.session.add(header)
        database.session.flush()

        assign_document_identifier(
            document=header,
            entity_type=document["entity_type"],
            posting_date_raw=header.posting_date,
            naming_series_id=document["naming_series_id"],
        )

        for item in document["items"]:
            setattr(item, self.config.parent_field, header.id)
            database.session.add(item)

    def _apply_party(self, header: Any, party_id: Any) -> None:
        if not self.config.party_field:
            return
        setattr(header, self.config.party_field, party_id or None)
        party = None
        if party_id:
            party = database.session.execute(
                database.select(Party).filter_by(id=party_id, party_type=self.config.party_type)
            ).scalar_one_or_none()
        if self.config.party_name_field:
            setattr(header, self.config.party_name_field, party.name if party else None)

    def _apply_source(self, header: Any, source_id: Any) -> None:
        if self.config.source_field and source_id:
            setattr(header, self.config.source_field, source_id)

    def _apply_totals(self, header: Any, total_qty: Decimal, total: Decimal) -> None:
        if hasattr(header, "total_qty"):
            header.total_qty = total_qty
        for field in ("total", "base_total", "net_total", "grand_total", "base_grand_total"):
            if hasattr(header, field):
                setattr(header, field, total)
        for field in ("outstanding_amount", "base_outstanding_amount"):
            if hasattr(header, field):
                setattr(header, field, total)

    def _apply_optional_item_fields(self, item: Any, amount: Decimal, row: dict[str, Any]) -> None:
        self._apply_item_amount_fields(item, amount)
        self._apply_item_rate_fields(item)
        self._apply_item_zero_fields(item, self.config.receipt_fields)
        self._apply_item_zero_fields(item, self.config.invoice_fields)
        self._apply_item_batch_serial_fields(item, row)

    def _apply_item_amount_fields(self, item: Any, amount: Decimal) -> None:
        if hasattr(item, "base_amount"):
            item.base_amount = amount

    def _apply_item_rate_fields(self, item: Any) -> None:
        for field in ("base_rate", "valuation_rate"):
            if hasattr(item, field):
                setattr(item, field, item.rate)

    def _apply_item_zero_fields(self, item: Any, fields: tuple[str, ...]) -> None:
        for field in fields:
            if hasattr(item, field):
                setattr(item, field, Decimal("0"))

    def _apply_item_batch_serial_fields(self, item: Any, row: dict[str, Any]) -> None:
        if not self.config.include_batch_serial:
            return
        if hasattr(item, "batch_id"):
            item.batch_id = row.get("lote") or None
        if hasattr(item, "serial_no"):
            item.serial_no = row.get("serie") or None


class PurchaseRequestAdapter(TransactionDocumentAdapter):
    """Adaptador para Solicitudes de Compra."""

    def __init__(self) -> None:
        """Configura importación de solicitudes de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_request",
                header_model=PurchaseRequest,
                item_model=PurchaseRequestItem,
                parent_field="purchase_request_id",
            )
        )


class PurchaseQuotationAdapter(TransactionDocumentAdapter):
    """Adaptador para Solicitudes de Cotización."""

    def __init__(self) -> None:
        """Configura importación de solicitudes de cotización."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_quotation",
                header_model=PurchaseQuotation,
                item_model=PurchaseQuotationItem,
                parent_field="purchase_quotation_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
            )
        )


class SupplierQuotationAdapter(TransactionDocumentAdapter):
    """Adaptador para Cotizaciones de Proveedor."""

    def __init__(self) -> None:
        """Configura importación de cotizaciones de proveedor."""
        super().__init__(
            TransactionImportConfig(
                entity_type="supplier_quotation",
                header_model=SupplierQuotation,
                item_model=SupplierQuotationItem,
                parent_field="supplier_quotation_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                source_field="purchase_quotation_id",
            )
        )


class PurchaseOrderAdapter(TransactionDocumentAdapter):
    """Adaptador para Órdenes de Compra."""

    def __init__(self) -> None:
        """Configura importación de órdenes de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_order",
                header_model=PurchaseOrder,
                item_model=PurchaseOrderItem,
                parent_field="purchase_order_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                receipt_fields=("received_qty",),
                invoice_fields=("billed_qty",),
            )
        )


class PurchaseReceiptAdapter(TransactionDocumentAdapter):
    """Adaptador para Recepciones de Compra."""

    def __init__(self) -> None:
        """Configura importación de recepciones de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_receipt",
                header_model=PurchaseReceipt,
                item_model=PurchaseReceiptItem,
                parent_field="purchase_receipt_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                source_field="purchase_order_id",
                include_batch_serial=True,
            )
        )


class PurchaseInvoiceAdapter(TransactionDocumentAdapter):
    """Adaptador para Facturas de Compra."""

    def __init__(self) -> None:
        """Configura importación de facturas de compra."""
        super().__init__(
            TransactionImportConfig(
                entity_type="purchase_invoice",
                header_model=PurchaseInvoice,
                item_model=PurchaseInvoiceItem,
                parent_field="purchase_invoice_id",
                party_type="supplier",
                party_field="supplier_id",
                party_name_field="supplier_name",
                source_field="purchase_order_id",
            )
        )


class SalesRequestAdapter(TransactionDocumentAdapter):
    """Adaptador para Pedidos de Venta."""

    def __init__(self) -> None:
        """Configura importación de pedidos de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_request",
                header_model=SalesRequest,
                item_model=SalesRequestItem,
                parent_field="sales_request_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
            )
        )


class SalesQuotationAdapter(TransactionDocumentAdapter):
    """Adaptador para Cotizaciones de Venta."""

    def __init__(self) -> None:
        """Configura importación de cotizaciones de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_quotation",
                header_model=SalesQuotation,
                item_model=SalesQuotationItem,
                parent_field="sales_quotation_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_request_id",
            )
        )


class SalesOrderAdapter(TransactionDocumentAdapter):
    """Adaptador para Órdenes de Venta."""

    def __init__(self) -> None:
        """Configura importación de órdenes de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_order",
                header_model=SalesOrder,
                item_model=SalesOrderItem,
                parent_field="sales_order_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_quotation_id",
                receipt_fields=("delivered_qty",),
                invoice_fields=("billed_qty",),
            )
        )


class DeliveryNoteAdapter(TransactionDocumentAdapter):
    """Adaptador para Notas de Entrega."""

    def __init__(self) -> None:
        """Configura importación de notas de entrega."""
        super().__init__(
            TransactionImportConfig(
                entity_type="delivery_note",
                header_model=DeliveryNote,
                item_model=DeliveryNoteItem,
                parent_field="delivery_note_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_order_id",
                include_batch_serial=True,
            )
        )


class SalesInvoiceAdapter(TransactionDocumentAdapter):
    """Adaptador para Facturas de Venta."""

    def __init__(self) -> None:
        """Configura importación de facturas de venta."""
        super().__init__(
            TransactionImportConfig(
                entity_type="sales_invoice",
                header_model=SalesInvoice,
                item_model=SalesInvoiceItem,
                parent_field="sales_invoice_id",
                party_type="customer",
                party_field="customer_id",
                party_name_field="customer_name",
                source_field="sales_order_id",
                include_batch_serial=True,
            )
        )
