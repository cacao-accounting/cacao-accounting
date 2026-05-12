# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Registro de documentos y relaciones permitidas."""

from dataclasses import dataclass
from typing import Any

from cacao_accounting.database import (
    DeliveryNote,
    DeliveryNoteItem,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    PurchaseQuotation,
    PurchaseQuotationItem,
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
    StockEntry,
    StockEntryItem,
    SupplierQuotation,
    SupplierQuotationItem,
)


@dataclass(frozen=True)
class DocumentAction:
    """Accion UI para crear documentos relacionados."""

    label: str
    target_type: str
    endpoint: str
    source_param: str


@dataclass(frozen=True)
class DocumentType:
    """Contrato minimo para consultar un documento header + items."""

    key: str
    header_model: Any
    item_model: Any
    parent_field: str
    party_field: str | None = None
    label: str | None = None
    module: str = "general"
    module_label: str = "General"
    permission_module: str | None = None
    list_endpoint: str | None = None
    detail_endpoint: str | None = None
    detail_arg: str = "document_id"
    date_field: str = "posting_date"
    total_field: str | None = "grand_total"
    filter_fields: tuple[str, ...] = ()
    create_actions: tuple[DocumentAction, ...] = ()


@dataclass(frozen=True)
class FlowSpec:
    """Relacion permitida entre dos tipos documentales."""

    source_type: str
    target_type: str
    relation_type: str


DOCUMENT_TYPES: dict[str, DocumentType] = {
    "purchase_order": DocumentType(
        key="purchase_order",
        header_model=PurchaseOrder,
        item_model=PurchaseOrderItem,
        parent_field="purchase_order_id",
        party_field="supplier_id",
        label="Orden de Compra",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_orden_compra_lista",
        detail_endpoint="compras.compras_orden_compra",
        detail_arg="order_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "supplier_id", "supplier_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction("Crear Recepción", "purchase_receipt", "compras.compras_recepcion_nuevo", "from_order"),
            DocumentAction("Crear Factura", "purchase_invoice", "compras.compras_factura_compra_nuevo", "from_order"),
        ),
    ),
    "purchase_request": DocumentType(
        key="purchase_request",
        header_model=PurchaseRequest,
        item_model=PurchaseRequestItem,
        parent_field="purchase_request_id",
        label="Solicitud de Compra",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_solicitud_compra_lista",
        detail_endpoint="compras.compras_solicitud_compra",
        detail_arg="request_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "requested_by", "department", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction("Crear Orden de Compra", "purchase_order", "compras.compras_orden_compra_nuevo", "from_request"),
        ),
    ),
    "purchase_quotation": DocumentType(
        key="purchase_quotation",
        header_model=PurchaseQuotation,
        item_model=PurchaseQuotationItem,
        parent_field="purchase_quotation_id",
        party_field="supplier_id",
        label="Solicitud de Cotización",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_solicitud_cotizacion_lista",
        detail_endpoint="compras.compras_solicitud_cotizacion",
        detail_arg="quotation_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "supplier_id", "supplier_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction(
                "Crear Cotización de Proveedor",
                "supplier_quotation",
                "compras.compras_cotizacion_proveedor_nueva",
                "from_rfq",
            ),
        ),
    ),
    "supplier_quotation": DocumentType(
        key="supplier_quotation",
        header_model=SupplierQuotation,
        item_model=SupplierQuotationItem,
        parent_field="supplier_quotation_id",
        party_field="supplier_id",
        label="Cotización de Proveedor",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_cotizacion_proveedor_lista",
        detail_endpoint="compras.compras_cotizacion_proveedor",
        detail_arg="quotation_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "supplier_id", "supplier_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction(
                "Crear Orden de Compra", "purchase_order", "compras.compras_orden_compra_nuevo", "from_supplier_quotation"
            ),
        ),
    ),
    "purchase_receipt": DocumentType(
        key="purchase_receipt",
        header_model=PurchaseReceipt,
        item_model=PurchaseReceiptItem,
        parent_field="purchase_receipt_id",
        party_field="supplier_id",
        label="Recepción de Compra",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_recepcion_lista",
        detail_endpoint="compras.compras_recepcion",
        detail_arg="receipt_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "supplier_id", "supplier_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction("Crear Factura", "purchase_invoice", "compras.compras_factura_compra_nuevo", "from_receipt"),
            DocumentAction("Crear Entrada de Almacén", "stock_entry", "inventario.inventario_entrada_nuevo", "source_id"),
        ),
    ),
    "purchase_invoice": DocumentType(
        key="purchase_invoice",
        header_model=PurchaseInvoice,
        item_model=PurchaseInvoiceItem,
        parent_field="purchase_invoice_id",
        party_field="supplier_id",
        label="Factura de Compra",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_factura_compra_lista",
        detail_endpoint="compras.compras_factura_compra",
        detail_arg="invoice_id",
        total_field="grand_total",
        filter_fields=(
            "document_no",
            "company",
            "supplier_id",
            "supplier_name",
            "posting_date",
            "grand_total",
            "outstanding_amount",
            "docstatus",
        ),
        create_actions=(
            DocumentAction("Crear Pago", "payment_entry", "bancos.bancos_pago_nuevo", "from_purchase_invoice"),
            DocumentAction(
                "Crear Nota de Crédito", "purchase_invoice", "compras.compras_factura_compra_nuevo", "from_invoice"
            ),
        ),
    ),
    "sales_order": DocumentType(
        key="sales_order",
        header_model=SalesOrder,
        item_model=SalesOrderItem,
        parent_field="sales_order_id",
        party_field="customer_id",
        label="Orden de Venta",
        module="sales",
        module_label="Ventas",
        permission_module="sales",
        list_endpoint="ventas.ventas_orden_venta_lista",
        detail_endpoint="ventas.ventas_orden_venta",
        detail_arg="order_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "customer_id", "customer_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction("Crear Nota de Entrega", "delivery_note", "ventas.ventas_entrega_nuevo", "from_order"),
            DocumentAction("Crear Factura", "sales_invoice", "ventas.ventas_factura_venta_nuevo", "from_order"),
        ),
    ),
    "sales_request": DocumentType(
        key="sales_request",
        header_model=SalesRequest,
        item_model=SalesRequestItem,
        parent_field="sales_request_id",
        party_field="customer_id",
        label="Pedido de Venta",
        module="sales",
        module_label="Ventas",
        permission_module="sales",
        list_endpoint="ventas.ventas_pedido_venta_lista",
        detail_endpoint="ventas.ventas_pedido_venta",
        detail_arg="request_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "customer_id", "customer_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction("Crear Cotización", "sales_quotation", "ventas.ventas_cotizacion_nueva", "from_request"),
        ),
    ),
    "sales_quotation": DocumentType(
        key="sales_quotation",
        header_model=SalesQuotation,
        item_model=SalesQuotationItem,
        parent_field="sales_quotation_id",
        party_field="customer_id",
        label="Cotización de Venta",
        module="sales",
        module_label="Ventas",
        permission_module="sales",
        list_endpoint="ventas.ventas_cotizacion_lista",
        detail_endpoint="ventas.ventas_cotizacion",
        detail_arg="quotation_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "customer_id", "customer_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction("Crear Orden de Venta", "sales_order", "ventas.ventas_orden_venta_nuevo", "from_quotation"),
        ),
    ),
    "delivery_note": DocumentType(
        key="delivery_note",
        header_model=DeliveryNote,
        item_model=DeliveryNoteItem,
        parent_field="delivery_note_id",
        party_field="customer_id",
        label="Nota de Entrega",
        module="sales",
        module_label="Ventas",
        permission_module="sales",
        list_endpoint="ventas.ventas_entrega_lista",
        detail_endpoint="ventas.ventas_entrega",
        detail_arg="note_id",
        total_field="grand_total",
        filter_fields=("document_no", "company", "customer_id", "customer_name", "posting_date", "grand_total", "docstatus"),
        create_actions=(
            DocumentAction("Crear Factura", "sales_invoice", "ventas.ventas_factura_venta_nuevo", "from_note"),
            DocumentAction(
                "Crear Movimiento de Inventario", "stock_entry", "inventario.inventario_entrada_nuevo", "source_id"
            ),
        ),
    ),
    "sales_invoice": DocumentType(
        key="sales_invoice",
        header_model=SalesInvoice,
        item_model=SalesInvoiceItem,
        parent_field="sales_invoice_id",
        party_field="customer_id",
        label="Factura de Venta",
        module="sales",
        module_label="Ventas",
        permission_module="sales",
        list_endpoint="ventas.ventas_factura_venta_lista",
        detail_endpoint="ventas.ventas_factura_venta",
        detail_arg="invoice_id",
        total_field="grand_total",
        filter_fields=(
            "document_no",
            "company",
            "customer_id",
            "customer_name",
            "posting_date",
            "grand_total",
            "outstanding_amount",
            "docstatus",
        ),
        create_actions=(
            DocumentAction("Crear Pago", "payment_entry", "bancos.bancos_pago_nuevo", "from_sales_invoice"),
            DocumentAction("Crear Nota de Crédito", "sales_invoice", "ventas.ventas_factura_venta_nuevo", "from_return"),
        ),
    ),
    "payment_entry": DocumentType(
        key="payment_entry",
        header_model=PaymentEntry,
        item_model=PaymentReference,
        parent_field="payment_id",
        party_field="party_id",
        label="Pago",
        module="cash",
        module_label="Bancos",
        permission_module="cash",
        list_endpoint="bancos.bancos_pago_lista",
        detail_endpoint="bancos.bancos_pago",
        detail_arg="payment_id",
        date_field="posting_date",
        total_field="paid_amount",
        filter_fields=(
            "document_no",
            "company",
            "party_type",
            "party_id",
            "posting_date",
            "paid_amount",
            "received_amount",
            "docstatus",
        ),
    ),
    "stock_entry": DocumentType(
        key="stock_entry",
        header_model=StockEntry,
        item_model=StockEntryItem,
        parent_field="stock_entry_id",
        label="Movimiento de Inventario",
        module="inventory",
        module_label="Inventario",
        permission_module="inventory",
        list_endpoint="inventario.inventario_entrada_lista",
        detail_endpoint="inventario.inventario_entrada",
        detail_arg="entry_id",
        total_field="total_amount",
        filter_fields=("document_no", "company", "purpose", "posting_date", "total_amount", "docstatus"),
    ),
}


ALLOWED_FLOWS: dict[tuple[str, str], FlowSpec] = {
    ("purchase_request", "purchase_quotation"): FlowSpec("purchase_request", "purchase_quotation", "quotation"),
    ("purchase_request", "purchase_order"): FlowSpec("purchase_request", "purchase_order", "order"),
    ("purchase_quotation", "supplier_quotation"): FlowSpec("purchase_quotation", "supplier_quotation", "quotation"),
    ("supplier_quotation", "purchase_order"): FlowSpec("supplier_quotation", "purchase_order", "order"),
    ("purchase_order", "purchase_receipt"): FlowSpec("purchase_order", "purchase_receipt", "receipt"),
    ("purchase_order", "purchase_invoice"): FlowSpec("purchase_order", "purchase_invoice", "billing"),
    ("purchase_receipt", "purchase_invoice"): FlowSpec("purchase_receipt", "purchase_invoice", "billing"),
    ("purchase_receipt", "stock_entry"): FlowSpec("purchase_receipt", "stock_entry", "stock"),
    ("purchase_invoice", "purchase_invoice"): FlowSpec("purchase_invoice", "purchase_invoice", "return"),
    ("purchase_invoice", "payment_entry"): FlowSpec("purchase_invoice", "payment_entry", "payment"),
    ("sales_request", "sales_quotation"): FlowSpec("sales_request", "sales_quotation", "quotation"),
    ("sales_quotation", "sales_order"): FlowSpec("sales_quotation", "sales_order", "order"),
    ("sales_order", "delivery_note"): FlowSpec("sales_order", "delivery_note", "delivery"),
    ("sales_order", "sales_invoice"): FlowSpec("sales_order", "sales_invoice", "billing"),
    ("delivery_note", "sales_invoice"): FlowSpec("delivery_note", "sales_invoice", "billing"),
    ("delivery_note", "stock_entry"): FlowSpec("delivery_note", "stock_entry", "stock"),
    ("sales_invoice", "sales_invoice"): FlowSpec("sales_invoice", "sales_invoice", "return"),
    ("sales_invoice", "payment_entry"): FlowSpec("sales_invoice", "payment_entry", "payment"),
}


def normalize_doctype(value: str) -> str:
    """Normaliza nombres recibidos desde URLs o formularios."""
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def get_document_type(value: str) -> DocumentType:
    """Devuelve el contrato de un tipo documental conocido."""
    key = normalize_doctype(value)
    return DOCUMENT_TYPES[key]


def get_flow(source_type: str, target_type: str) -> FlowSpec:
    """Devuelve la relacion permitida entre dos tipos documentales."""
    return ALLOWED_FLOWS[(normalize_doctype(source_type), normalize_doctype(target_type))]


def is_allowed_flow(source_type: str, target_type: str) -> bool:
    """Indica si existe una relacion activa entre source y target."""
    return (normalize_doctype(source_type), normalize_doctype(target_type)) in ALLOWED_FLOWS
