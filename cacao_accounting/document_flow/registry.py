# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Registro de documentos y relaciones permitidas."""

from dataclasses import dataclass
from typing import Any

from cacao_accounting.database import (
    ComprobanteContable,
    ComprobanteContableDetalle,
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

COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO = "compras.compras_factura_compra_nuevo"
CREAR_FACTURA = "Crear Factura"
VENTAS_VENTAS_FACTURA_VENTA_NUEVO = "ventas.ventas_factura_venta_nuevo"

_ACTION_CREAR_PAGO = "Crear Pago"
_ACTION_CREAR_NOTA_CREDITO = "Crear Nota de Crédito"
_ACTION_CREAR_NOTA_DEBITO = "Crear Nota de Débito"
_ACTION_CREAR_ORDEN_COMPRA = "Crear Orden de Compra"
_ENDPOINT_PAGO_NUEVO = "bancos.bancos_pago_nuevo"
_ENDPOINT_ORDEN_COMPRA_NUEVO = "compras.compras_orden_compra_nuevo"
_ENDPOINT_FACTURA_COMPRA = "compras.compras_factura_compra"
_ENDPOINT_FACTURA_VENTA = "ventas.ventas_factura_venta"
_ENDPOINT_ENTRADA_NUEVO = "inventario.inventario_entrada_nuevo"


@dataclass(frozen=True)
class DocumentAction:
    """Accion UI para crear documentos relacionados."""

    label: str
    target_type: str
    endpoint: str
    source_param: str
    query_params: dict[str, str] | None = None
    model_target_type: str | None = None
    condition: str | None = None
    enabled: bool = True


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
            DocumentAction(CREAR_FACTURA, "purchase_invoice", COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO, "from_order"),
            DocumentAction(_ACTION_CREAR_PAGO, "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_purchase_order"),
            DocumentAction(
                _ACTION_CREAR_NOTA_CREDITO,
                "purchase_credit_note",
                COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO,
                "from_order",
                {"document_type": "purchase_credit_note"},
                model_target_type="purchase_invoice",
            ),
            DocumentAction(
                _ACTION_CREAR_NOTA_DEBITO,
                "purchase_debit_note",
                COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO,
                "from_order",
                {"document_type": "purchase_debit_note"},
                model_target_type="purchase_invoice",
            ),
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
            DocumentAction(
                "Crear Solicitud de Cotización",
                "purchase_quotation",
                "compras.compras_solicitud_cotizacion_nueva",
                "from_request",
            ),
            DocumentAction(
                "Crear Cotización de Proveedor",
                "supplier_quotation",
                "compras.compras_cotizacion_proveedor_nueva",
                "from_request",
            ),
            DocumentAction(_ACTION_CREAR_ORDEN_COMPRA, "purchase_order", _ENDPOINT_ORDEN_COMPRA_NUEVO, "from_request"),
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
            DocumentAction(_ACTION_CREAR_ORDEN_COMPRA, "purchase_order", _ENDPOINT_ORDEN_COMPRA_NUEVO, "from_rfq"),
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
                _ACTION_CREAR_ORDEN_COMPRA, "purchase_order", _ENDPOINT_ORDEN_COMPRA_NUEVO, "from_supplier_quotation"
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
            DocumentAction(CREAR_FACTURA, "purchase_invoice", COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO, "from_receipt"),
            DocumentAction(
                _ACTION_CREAR_NOTA_CREDITO,
                "purchase_credit_note",
                COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO,
                "from_receipt",
                {"document_type": "purchase_credit_note"},
                model_target_type="purchase_invoice",
            ),
            DocumentAction(
                _ACTION_CREAR_NOTA_DEBITO,
                "purchase_debit_note",
                COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO,
                "from_receipt",
                {"document_type": "purchase_debit_note"},
                model_target_type="purchase_invoice",
            ),
            DocumentAction(
                "Crear Devolución",
                "purchase_return",
                COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO,
                "from_receipt",
                {"document_type": "purchase_return"},
                model_target_type="purchase_invoice",
            ),
            DocumentAction(
                "Crear Entrada de Almacén",
                "stock_entry",
                _ENDPOINT_ENTRADA_NUEVO,
                "source_id",
                {"source_type": "purchase_receipt"},
            ),
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
        detail_endpoint=_ENDPOINT_FACTURA_COMPRA,
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
            DocumentAction(_ACTION_CREAR_PAGO, "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_purchase_invoice"),
            DocumentAction(
                _ACTION_CREAR_NOTA_CREDITO,
                "purchase_credit_note",
                COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO,
                "from_invoice",
                {"document_type": "purchase_credit_note"},
                model_target_type="purchase_invoice",
            ),
            DocumentAction(
                _ACTION_CREAR_NOTA_DEBITO,
                "purchase_debit_note",
                COMPRAS_COMPRAS_FACTURA_COMPRA_NUEVO,
                "from_invoice",
                {"document_type": "purchase_debit_note"},
                model_target_type="purchase_invoice",
            ),
        ),
    ),
    "purchase_credit_note": DocumentType(
        key="purchase_credit_note",
        header_model=PurchaseInvoice,
        item_model=PurchaseInvoiceItem,
        parent_field="purchase_invoice_id",
        party_field="supplier_id",
        label="Nota de Crédito de Compra",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_factura_compra_nota_credito_lista",
        detail_endpoint=_ENDPOINT_FACTURA_COMPRA,
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
            DocumentAction("Crear Reembolso", "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_purchase_credit_note"),
        ),
    ),
    "purchase_debit_note": DocumentType(
        key="purchase_debit_note",
        header_model=PurchaseInvoice,
        item_model=PurchaseInvoiceItem,
        parent_field="purchase_invoice_id",
        party_field="supplier_id",
        label="Nota de Débito de Compra",
        module="purchases",
        module_label="Compras",
        permission_module="purchases",
        list_endpoint="compras.compras_factura_compra_nota_debito_lista",
        detail_endpoint=_ENDPOINT_FACTURA_COMPRA,
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
            DocumentAction(_ACTION_CREAR_PAGO, "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_purchase_debit_note"),
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
            DocumentAction(CREAR_FACTURA, "sales_invoice", VENTAS_VENTAS_FACTURA_VENTA_NUEVO, "from_order"),
            DocumentAction(_ACTION_CREAR_PAGO, "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_sales_order"),
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
            DocumentAction("Crear Orden de Venta", "sales_order", "ventas.ventas_orden_venta_nuevo", "from_request"),
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
            DocumentAction(CREAR_FACTURA, "sales_invoice", VENTAS_VENTAS_FACTURA_VENTA_NUEVO, "from_note"),
            DocumentAction(
                _ACTION_CREAR_NOTA_CREDITO,
                "sales_credit_note",
                VENTAS_VENTAS_FACTURA_VENTA_NUEVO,
                "from_note",
                {"document_type": "sales_credit_note"},
                model_target_type="sales_invoice",
            ),
            DocumentAction(
                _ACTION_CREAR_NOTA_DEBITO,
                "sales_debit_note",
                VENTAS_VENTAS_FACTURA_VENTA_NUEVO,
                "from_note",
                {"document_type": "sales_debit_note"},
                model_target_type="sales_invoice",
            ),
            DocumentAction(
                "Crear Movimiento de Inventario",
                "stock_entry",
                _ENDPOINT_ENTRADA_NUEVO,
                "source_id",
                {"source_type": "delivery_note"},
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
        detail_endpoint=_ENDPOINT_FACTURA_VENTA,
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
            DocumentAction(_ACTION_CREAR_PAGO, "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_sales_invoice"),
            DocumentAction(
                _ACTION_CREAR_NOTA_CREDITO,
                "sales_credit_note",
                VENTAS_VENTAS_FACTURA_VENTA_NUEVO,
                "from_invoice",
                {"document_type": "sales_credit_note"},
                model_target_type="sales_invoice",
            ),
            DocumentAction(
                _ACTION_CREAR_NOTA_DEBITO,
                "sales_debit_note",
                VENTAS_VENTAS_FACTURA_VENTA_NUEVO,
                "from_invoice",
                {"document_type": "sales_debit_note"},
                model_target_type="sales_invoice",
            ),
        ),
    ),
    "sales_credit_note": DocumentType(
        key="sales_credit_note",
        header_model=SalesInvoice,
        item_model=SalesInvoiceItem,
        parent_field="sales_invoice_id",
        party_field="customer_id",
        label="Nota de Crédito de Venta",
        module="sales",
        module_label="Ventas",
        permission_module="sales",
        list_endpoint="ventas.ventas_factura_venta_nota_credito_lista",
        detail_endpoint=_ENDPOINT_FACTURA_VENTA,
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
        create_actions=(DocumentAction("Crear Reembolso", "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_sales_credit_note"),),
    ),
    "sales_debit_note": DocumentType(
        key="sales_debit_note",
        header_model=SalesInvoice,
        item_model=SalesInvoiceItem,
        parent_field="sales_invoice_id",
        party_field="customer_id",
        label="Nota de Débito de Venta",
        module="sales",
        module_label="Ventas",
        permission_module="sales",
        list_endpoint="ventas.ventas_factura_venta_nota_debito_lista",
        detail_endpoint=_ENDPOINT_FACTURA_VENTA,
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
        create_actions=(DocumentAction("Crear Cobro", "payment_entry", _ENDPOINT_PAGO_NUEVO, "from_sales_debit_note"),),
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
        create_actions=(
            DocumentAction(
                "Crear Reuso Interno",
                "stock_entry",
                _ENDPOINT_ENTRADA_NUEVO,
                "source_id",
                {"source_type": "stock_entry"},
            ),
        ),
    ),
    "journal_entry": DocumentType(
        key="journal_entry",
        header_model=ComprobanteContable,
        item_model=ComprobanteContableDetalle,
        parent_field="transaction_id",
        label="Comprobante Contable",
        module="accounting",
        module_label="Contabilidad",
        permission_module="accounting",
        list_endpoint="contabilidad.listar_comprobantes",
        detail_endpoint="contabilidad.ver_comprobante",
        detail_arg="identifier",
        date_field="date",
        total_field=None,
        filter_fields=("document_no", "entity", "date", "status", "docstatus"),
    ),
}


ALLOWED_FLOWS: dict[tuple[str, str], FlowSpec] = {
    ("purchase_request", "purchase_request"): FlowSpec("purchase_request", "purchase_request", "reuse"),
    ("purchase_request", "purchase_quotation"): FlowSpec("purchase_request", "purchase_quotation", "quotation"),
    ("purchase_request", "supplier_quotation"): FlowSpec("purchase_request", "supplier_quotation", "quotation"),
    ("purchase_request", "purchase_order"): FlowSpec("purchase_request", "purchase_order", "order"),
    ("purchase_quotation", "purchase_quotation"): FlowSpec("purchase_quotation", "purchase_quotation", "reuse"),
    ("purchase_quotation", "supplier_quotation"): FlowSpec("purchase_quotation", "supplier_quotation", "quotation"),
    ("purchase_quotation", "purchase_order"): FlowSpec("purchase_quotation", "purchase_order", "order"),
    ("supplier_quotation", "supplier_quotation"): FlowSpec("supplier_quotation", "supplier_quotation", "reuse"),
    ("supplier_quotation", "purchase_order"): FlowSpec("supplier_quotation", "purchase_order", "order"),
    ("purchase_order", "purchase_order"): FlowSpec("purchase_order", "purchase_order", "reuse"),
    ("purchase_order", "purchase_receipt"): FlowSpec("purchase_order", "purchase_receipt", "receipt"),
    ("purchase_order", "purchase_invoice"): FlowSpec("purchase_order", "purchase_invoice", "billing"),
    ("purchase_order", "payment_entry"): FlowSpec("purchase_order", "payment_entry", "advance"),
    ("purchase_order", "purchase_credit_note"): FlowSpec("purchase_order", "purchase_credit_note", "credit_note"),
    ("purchase_order", "purchase_debit_note"): FlowSpec("purchase_order", "purchase_debit_note", "debit_note"),
    ("purchase_receipt", "purchase_receipt"): FlowSpec("purchase_receipt", "purchase_receipt", "reuse"),
    ("purchase_receipt", "purchase_invoice"): FlowSpec("purchase_receipt", "purchase_invoice", "billing"),
    ("purchase_receipt", "purchase_credit_note"): FlowSpec("purchase_receipt", "purchase_credit_note", "credit_note"),
    ("purchase_receipt", "purchase_debit_note"): FlowSpec("purchase_receipt", "purchase_debit_note", "debit_note"),
    ("purchase_receipt", "purchase_return"): FlowSpec("purchase_receipt", "purchase_return", "return"),
    ("purchase_receipt", "stock_entry"): FlowSpec("purchase_receipt", "stock_entry", "stock"),
    ("purchase_invoice", "purchase_invoice"): FlowSpec("purchase_invoice", "purchase_invoice", "return"),
    ("purchase_invoice", "purchase_credit_note"): FlowSpec("purchase_invoice", "purchase_credit_note", "credit_note"),
    ("purchase_invoice", "purchase_debit_note"): FlowSpec("purchase_invoice", "purchase_debit_note", "debit_note"),
    ("purchase_invoice", "payment_entry"): FlowSpec("purchase_invoice", "payment_entry", "payment"),
    ("purchase_credit_note", "payment_entry"): FlowSpec("purchase_credit_note", "payment_entry", "refund"),
    ("purchase_debit_note", "payment_entry"): FlowSpec("purchase_debit_note", "payment_entry", "payment"),
    ("sales_request", "sales_request"): FlowSpec("sales_request", "sales_request", "reuse"),
    ("sales_request", "sales_quotation"): FlowSpec("sales_request", "sales_quotation", "quotation"),
    ("sales_request", "sales_order"): FlowSpec("sales_request", "sales_order", "order"),
    ("sales_quotation", "sales_quotation"): FlowSpec("sales_quotation", "sales_quotation", "reuse"),
    ("sales_quotation", "sales_order"): FlowSpec("sales_quotation", "sales_order", "order"),
    ("sales_order", "sales_order"): FlowSpec("sales_order", "sales_order", "reuse"),
    ("sales_order", "delivery_note"): FlowSpec("sales_order", "delivery_note", "delivery"),
    ("sales_order", "sales_invoice"): FlowSpec("sales_order", "sales_invoice", "billing"),
    ("sales_order", "payment_entry"): FlowSpec("sales_order", "payment_entry", "advance"),
    ("delivery_note", "delivery_note"): FlowSpec("delivery_note", "delivery_note", "reuse"),
    ("delivery_note", "sales_invoice"): FlowSpec("delivery_note", "sales_invoice", "billing"),
    ("delivery_note", "sales_credit_note"): FlowSpec("delivery_note", "sales_credit_note", "credit_note"),
    ("delivery_note", "sales_debit_note"): FlowSpec("delivery_note", "sales_debit_note", "debit_note"),
    ("delivery_note", "stock_entry"): FlowSpec("delivery_note", "stock_entry", "stock"),
    ("sales_invoice", "sales_invoice"): FlowSpec("sales_invoice", "sales_invoice", "return"),
    ("sales_invoice", "sales_credit_note"): FlowSpec("sales_invoice", "sales_credit_note", "credit_note"),
    ("sales_invoice", "sales_debit_note"): FlowSpec("sales_invoice", "sales_debit_note", "debit_note"),
    ("sales_invoice", "payment_entry"): FlowSpec("sales_invoice", "payment_entry", "payment"),
    ("sales_credit_note", "payment_entry"): FlowSpec("sales_credit_note", "payment_entry", "refund"),
    ("sales_debit_note", "payment_entry"): FlowSpec("sales_debit_note", "payment_entry", "collection"),
    ("stock_entry", "stock_entry"): FlowSpec("stock_entry", "stock_entry", "reuse"),
}

for _journal_source_type in tuple(DOCUMENT_TYPES):
    if _journal_source_type != "journal_entry":
        ALLOWED_FLOWS.setdefault(
            (_journal_source_type, "journal_entry"),
            FlowSpec(_journal_source_type, "journal_entry", "accounting"),
        )


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
