# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptadores para documentos transaccionales de Compras y Ventas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from cacao_accounting.database import (
    Batch,
    CompanyParty,
    DeliveryNote,
    DeliveryNoteItem,
    Item,
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
    Warehouse,
    database,
)
from cacao_accounting.document_identifiers import assign_document_identifier
from cacao_accounting.document_flow.context import company_currency, effective_currency
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
        "moneda",
        "tipo_cambio",
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
        """Valida fecha, período, origen, bodega, tercero y moneda del documento."""
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
        source = self._source_document(first_row.get("documento_origen"))
        if first_row.get("documento_origen") and self.config.source_field:
            if source is None:
                errors.append("El documento origen no existe o no corresponde al flujo importado.")
            elif source.docstatus != 1:
                errors.append("El documento origen debe estar aprobado.")
            elif source.company != company_id:
                errors.append("El documento origen debe pertenecer a la compañía de la importación.")
            elif self.config.party_field and getattr(source, self.config.party_field, None) != first_row.get("tercero"):
                errors.append("El tercero del documento origen no coincide con la fila importada.")
        if self.config.party_field and first_row.get("tercero"):
            membership = database.session.execute(
                database.select(CompanyParty).filter_by(party_id=first_row.get("tercero"), company=company_id, is_active=True)
            ).scalar_one_or_none()
            if membership is None:
                errors.append("El tercero no está habilitado para la compañía de la importación.")
        for row in document_data:
            warehouse_code = row.get("bodega")
            if warehouse_code:
                warehouse = database.session.execute(
                    database.select(Warehouse).filter_by(code=warehouse_code)
                ).scalar_one_or_none()
                if warehouse is None or warehouse.company != company_id or not warehouse.is_active:
                    errors.append(f"La bodega '{warehouse_code}' no pertenece a la compañía o está inactiva.")
            item = database.session.get(Item, row.get("producto"))
            if (
                item is not None
                and item.is_stock_item
                and not warehouse_code
                and self.config.entity_type
                in {
                    "purchase_receipt",
                    "delivery_note",
                }
            ):
                errors.append(f"El item de inventario '{item.code}' requiere una bodega.")
            errors.extend(self._validate_row_batch(row.get("producto"), row.get("lote")))
        try:
            self._currency_and_rate(first_row, source, company_id, posting_date)
        except ValueError as exc:
            errors.append(str(exc))
        return errors

    def _validate_row_batch(self, item_code: Any, batch_no: Any) -> list[str]:
        """Valida que el lote de la fila exista en el maestro y aplique al item."""
        if not self.config.include_batch_serial or not item_code:
            return []
        item = database.session.execute(database.select(Item).filter_by(code=item_code)).scalar_one_or_none()
        if item is None or not item.is_stock_item:
            return []
        cleaned = str(batch_no or "").strip()
        if (item.has_batch or item.has_expiry_date) and not cleaned:
            return [f"El item de inventario '{item.code}' requiere lote."]
        if not cleaned:
            return []
        batch = database.session.execute(
            database.select(Batch).filter_by(item_code=item.code, batch_no=cleaned)
        ).scalar_one_or_none()
        if batch is None:
            return [f"El lote '{cleaned}' del item '{item.code}' no existe en el maestro de lotes."]
        if not batch.is_active:
            return [f"El lote '{cleaned}' del item '{item.code}' está inactivo."]
        return []

    def build_document(self, document_data: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        """Construye encabezado e ítems desde las filas del archivo."""
        first_row = document_data[0]
        posting_date = date.fromisoformat(str(first_row.get("fecha")))
        source = self._source_document(first_row.get("documento_origen"))
        company_id = str(context.get("company_id") or "")
        transaction_currency, base_currency, exchange_rate = self._currency_and_rate(
            first_row, source, company_id, posting_date
        )
        header = self.config.header_model(
            company=company_id,
            posting_date=posting_date,
            document_date=posting_date,
            docstatus=0,
            remarks=first_row.get("notas") or f"Importación masiva: {first_row.get('document_ref')}",
            transaction_currency=transaction_currency,
            base_currency=base_currency,
            exchange_rate=exchange_rate,
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
            self._apply_optional_item_fields(item, amount * exchange_rate, row, exchange_rate)
            items.append(item)
            total_qty += qty
            total += amount

        self._apply_totals(header, total_qty, total, exchange_rate)
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
            if self.config.party_type == "customer":
                party_filter = Party.is_customer.is_(True)
            elif self.config.party_type == "supplier":
                party_filter = Party.is_supplier.is_(True)
            else:
                party_filter = None
            if party_filter is not None:
                party = database.session.execute(
                    database.select(Party).filter(Party.id == party_id, party_filter)
                ).scalar_one_or_none()
            else:
                party = database.session.execute(database.select(Party).filter_by(id=party_id)).scalar_one_or_none()
        if self.config.party_name_field:
            setattr(header, self.config.party_name_field, party.name if party else None)

    def _apply_source(self, header: Any, source_id: Any) -> None:
        if self.config.source_field and source_id:
            setattr(header, self.config.source_field, source_id)

    def _source_document(self, source_id: Any) -> Any | None:
        """Resuelve el documento origen permitido por el tipo importado."""
        if not source_id or not self.config.source_field:
            return None
        source_models = {
            "supplier_quotation": PurchaseQuotation,
            "purchase_receipt": PurchaseOrder,
            "purchase_invoice": PurchaseOrder,
            "sales_quotation": SalesRequest,
            "sales_order": SalesQuotation,
            "delivery_note": SalesOrder,
            "sales_invoice": SalesOrder,
        }
        source_model = source_models.get(self.config.entity_type)
        return database.session.get(source_model, source_id) if source_model else None

    def _currency_and_rate(
        self, first_row: dict[str, Any], source: Any | None, company: str, posting_date: date
    ) -> tuple[str | None, str | None, Decimal]:
        """Resuelve moneda funcional y tasa, rechazando conversiones implicitas 1:1.

        La moneda transaccional debe venir explicita en la primera fila o
        heredarse del documento origen. No se permite inferir desde la
        compania: si falta, se rechaza con ``ValueError``.
        """
        base_currency = company_currency(company)
        if not base_currency:
            raise ValueError("La compania no tiene moneda funcional configurada.")
        row_currency = first_row.get("moneda") or first_row.get("transaction_currency")
        source_currency = effective_currency(source)
        if row_currency:
            transaction_currency = str(row_currency).strip()
        elif source_currency:
            transaction_currency = source_currency
        else:
            raise ValueError(
                "El documento importado requiere una moneda transaccional explicita en la primera fila "
                "o un documento origen con moneda transaccional persistida."
            )
        explicit_rate = first_row.get("tipo_cambio") or first_row.get("exchange_rate")
        if transaction_currency == base_currency:
            return transaction_currency, base_currency, Decimal("1")
        if explicit_rate not in (None, ""):
            rate = Decimal(str(explicit_rate))
        elif source is not None and getattr(source, "exchange_rate", None):
            rate = Decimal(str(source.exchange_rate))
        else:
            from cacao_accounting.contabilidad.posting import PostingError, _lookup_exchange_rate

            try:
                rate = _lookup_exchange_rate(transaction_currency, base_currency, posting_date)
            except PostingError as exc:
                raise ValueError(
                    f"No existe tipo de cambio para {transaction_currency} -> {base_currency} en {posting_date}."
                ) from exc
        if rate <= 0:
            raise ValueError("El tipo de cambio debe ser positivo.")
        return transaction_currency, base_currency, rate

    def _apply_totals(self, header: Any, total_qty: Decimal, total: Decimal, exchange_rate: Decimal = Decimal("1")) -> None:
        if hasattr(header, "total_qty"):
            header.total_qty = total_qty
        for field in ("total", "base_total", "net_total", "grand_total", "base_grand_total"):
            if hasattr(header, field):
                value = total if not field.startswith("base_") else (total * exchange_rate).quantize(Decimal("0.0001"))
                setattr(header, field, value)
        for field in ("outstanding_amount", "base_outstanding_amount"):
            if hasattr(header, field):
                value = total if field == "outstanding_amount" else (total * exchange_rate).quantize(Decimal("0.0001"))
                setattr(header, field, value)

    def _apply_optional_item_fields(
        self, item: Any, amount: Decimal, row: dict[str, Any], exchange_rate: Decimal = Decimal("1")
    ) -> None:
        self._apply_item_amount_fields(item, amount)
        self._apply_item_rate_fields(item, exchange_rate)
        self._apply_item_zero_fields(item, self.config.receipt_fields)
        self._apply_item_zero_fields(item, self.config.invoice_fields)
        self._apply_item_batch_serial_fields(item, row)

    def _apply_item_amount_fields(self, item: Any, amount: Decimal) -> None:
        if hasattr(item, "base_amount"):
            item.base_amount = amount

    def _apply_item_rate_fields(self, item: Any, exchange_rate: Decimal = Decimal("1")) -> None:
        for field in ("base_rate", "valuation_rate"):
            if hasattr(item, field):
                setattr(item, field, (item.rate * exchange_rate).quantize(Decimal("0.0001")))

    def _apply_item_zero_fields(self, item: Any, fields: tuple[str, ...]) -> None:
        for field in fields:
            if hasattr(item, field):
                setattr(item, field, Decimal("0"))

    def _apply_item_batch_serial_fields(self, item: Any, row: dict[str, Any]) -> None:
        if not self.config.include_batch_serial:
            return
        if hasattr(item, "batch_id"):
            item.batch_id = self._resolve_batch_id(item.item_code, row.get("lote"))
        if hasattr(item, "serial_no"):
            item.serial_no = row.get("serie") or None

    def _resolve_batch_id(self, item_code: Any, batch_no: Any) -> str | None:
        """Resuelve el numero de lote del archivo al registro del maestro.

        La columna ``lote`` contiene el numero legible del lote, no su
        identificador interno: se resuelve contra el maestro por item y numero
        de lote y se rechaza la fila cuando el lote no existe, en lugar de
        persistir un texto que el posting nunca podria validar.
        """
        if batch_no in (None, ""):
            return None
        cleaned = str(batch_no).strip()
        batch = database.session.execute(
            database.select(Batch).filter_by(item_code=item_code, batch_no=cleaned)
        ).scalar_one_or_none()
        if batch is None:
            raise ValueError(f"El lote '{cleaned}' del item '{item_code}' no existe en el maestro de lotes.")
        if not batch.is_active:
            raise ValueError(f"El lote '{cleaned}' del item '{item_code}' está inactivo.")
        return batch.id


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
