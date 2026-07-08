# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Registry of document types available to the printing service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from cacao_accounting.printing.context import (
    DELIVERY_NOTE_PRINT_SCHEMA,
    EXCHANGE_REVALUATION_PRINT_SCHEMA,
    JOURNAL_ENTRY_PRINT_SCHEMA,
    PAYMENT_ENTRY_PRINT_SCHEMA,
    PURCHASE_INVOICE_PRINT_SCHEMA,
    PURCHASE_ORDER_PRINT_SCHEMA,
    QUOTATION_PRINT_SCHEMA,
    SALES_INVOICE_PRINT_SCHEMA,
    STOCK_ENTRY_PRINT_SCHEMA,
    build_delivery_note_print_context,
    build_exchange_revaluation_print_context,
    build_exchange_revaluation_sample_context,
    build_journal_entry_print_context,
    build_journal_entry_sample_context,
    build_payment_entry_print_context,
    build_payment_entry_sample_context,
    build_purchase_invoice_print_context,
    build_purchase_order_print_context,
    build_purchase_order_sample_context,
    build_quotation_print_context,
    build_quotation_sample_context,
    build_sales_invoice_print_context,
    build_sales_invoice_sample_context,
    build_stock_entry_print_context,
    build_stock_entry_sample_context,
)
from cacao_accounting.printing.snippets import get_common_snippets


class PrintableDocumentDefinition(TypedDict):
    """Contract for one printable document type."""

    label: str
    module: str
    root_context_name: str
    permission: str
    context_builder: Callable[..., dict[str, Any]]
    sample_context_builder: Callable[..., dict[str, Any]]
    schema: dict[str, Any]
    snippets: list[dict[str, str]]


_PERM_SALES_VIEW = "sales.view"
_PERM_PURCHASES_VIEW = "purchases.view"
_PERM_CASH_VIEW = "cash.view"

PRINTABLE_DOCUMENTS: dict[str, PrintableDocumentDefinition] = {}


def register_printable_document(document_type: str, definition: PrintableDocumentDefinition) -> None:
    """Register or replace one printable document definition."""
    PRINTABLE_DOCUMENTS[document_type] = definition


def get_printable_document(document_type: str) -> PrintableDocumentDefinition | None:
    """Return a printable definition by document type."""
    return PRINTABLE_DOCUMENTS.get(document_type)


def list_printable_documents() -> list[tuple[str, str]]:
    """List registered document types as ``(document_type, label)`` pairs."""
    return sorted((key, value["label"]) for key, value in PRINTABLE_DOCUMENTS.items())


def init_printing_registry() -> None:
    """Initialize built-in printable documents."""
    PRINTABLE_DOCUMENTS.clear()
    snippets = get_common_snippets()
    _register(
        "journal_entry",
        "Comprobante contable",
        "accounting",
        "journal_entry",
        "accounting.view",
        build_journal_entry_print_context,
        build_journal_entry_sample_context,
        JOURNAL_ENTRY_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "sales_invoice",
        "Factura de venta",
        "sales",
        "invoice",
        _PERM_SALES_VIEW,
        build_sales_invoice_print_context,
        build_sales_invoice_sample_context,
        SALES_INVOICE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "sales_credit_note",
        "Nota de credito de venta",
        "sales",
        "invoice",
        _PERM_SALES_VIEW,
        build_sales_invoice_print_context,
        build_sales_invoice_sample_context,
        SALES_INVOICE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "sales_debit_note",
        "Nota de debito de venta",
        "sales",
        "invoice",
        _PERM_SALES_VIEW,
        build_sales_invoice_print_context,
        build_sales_invoice_sample_context,
        SALES_INVOICE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "sales_return",
        "Devolucion de venta",
        "sales",
        "invoice",
        _PERM_SALES_VIEW,
        build_sales_invoice_print_context,
        build_sales_invoice_sample_context,
        SALES_INVOICE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "purchase_invoice",
        "Factura de compra",
        "purchases",
        "invoice",
        _PERM_PURCHASES_VIEW,
        build_purchase_invoice_print_context,
        build_sales_invoice_sample_context,
        PURCHASE_INVOICE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "purchase_credit_note",
        "Nota de credito de compra",
        "purchases",
        "invoice",
        _PERM_PURCHASES_VIEW,
        build_purchase_invoice_print_context,
        build_sales_invoice_sample_context,
        PURCHASE_INVOICE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "purchase_debit_note",
        "Nota de debito de compra",
        "purchases",
        "invoice",
        _PERM_PURCHASES_VIEW,
        build_purchase_invoice_print_context,
        build_sales_invoice_sample_context,
        PURCHASE_INVOICE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "purchase_order",
        "Orden de compra",
        "purchases",
        "purchase_order",
        _PERM_PURCHASES_VIEW,
        build_purchase_order_print_context,
        build_purchase_order_sample_context,
        PURCHASE_ORDER_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "delivery_note",
        "Nota de entrega",
        "sales",
        "receipt",
        _PERM_SALES_VIEW,
        build_delivery_note_print_context,
        build_stock_entry_sample_context,
        DELIVERY_NOTE_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "stock_entry",
        "Movimiento de inventario",
        "inventory",
        "adjustment",
        "inventory.view",
        build_stock_entry_print_context,
        build_stock_entry_sample_context,
        STOCK_ENTRY_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "payment_entry",
        "Comprobante de pago",
        "cash",
        "payment",
        _PERM_CASH_VIEW,
        build_payment_entry_print_context,
        build_payment_entry_sample_context,
        PAYMENT_ENTRY_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "bank_transfer",
        "Transferencia bancaria",
        "cash",
        "payment",
        _PERM_CASH_VIEW,
        build_payment_entry_print_context,
        build_payment_entry_sample_context,
        PAYMENT_ENTRY_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "cash_receipt",
        "Recibo de caja",
        "cash",
        "payment",
        _PERM_CASH_VIEW,
        build_payment_entry_print_context,
        build_payment_entry_sample_context,
        PAYMENT_ENTRY_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "sales_quotation",
        "Cotizacion de venta",
        "sales",
        "quote",
        _PERM_SALES_VIEW,
        build_quotation_print_context,
        build_quotation_sample_context,
        QUOTATION_PRINT_SCHEMA,
        snippets,
    )
    _register(
        "exchange_revaluation",
        "Comprobante de revaluacion",
        "accounting",
        "revaluation",
        "accounting.view",
        build_exchange_revaluation_print_context,
        build_exchange_revaluation_sample_context,
        EXCHANGE_REVALUATION_PRINT_SCHEMA,
        snippets,
    )


def _register(
    document_type: str,
    label: str,
    module: str,
    root_context_name: str,
    permission: str,
    context_builder: Callable[..., dict[str, Any]],
    sample_context_builder: Callable[..., dict[str, Any]],
    schema: dict[str, Any],
    snippets: list[dict[str, str]],
) -> None:
    register_printable_document(
        document_type,
        {
            "label": label,
            "module": module,
            "root_context_name": root_context_name,
            "permission": permission,
            "context_builder": context_builder,
            "sample_context_builder": sample_context_builder,
            "schema": schema,
            "snippets": snippets,
        },
    )
