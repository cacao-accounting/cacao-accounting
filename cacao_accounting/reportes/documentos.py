"""Proyecciones controladas de documentos para drill-down de solo lectura."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from cacao_accounting.database import (
    PaymentEntry,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    SalesInvoice,
    SalesInvoiceItem,
    database,
)

_DOCUMENTS = {
    "sales_invoice": (SalesInvoice, SalesInvoiceItem, "sales_invoice_id", "customer_id"),
    "purchase_invoice": (PurchaseInvoice, PurchaseInvoiceItem, "purchase_invoice_id", "supplier_id"),
    "payment_entry": (PaymentEntry, None, None, "party_id"),
}


def _decimal(value: Any) -> str:
    return str(Decimal(str(value or 0)))


def _status(docstatus: int | None) -> str:
    return {0: "draft", 1: "submitted", 2: "cancelled"}.get(docstatus or 0, "unknown")


def _resolve(document_type: str, document_id: str, company: str) -> tuple[Any, Any, str | None, str] | None:
    definition = _DOCUMENTS.get(document_type)
    if definition is None:
        raise ValueError(f"Tipo de documento no permitido: {document_type}")
    model, line_model, foreign_key, party_field = definition
    document = database.session.get(model, document_id)
    if document is None or document.company != company:
        return None
    return document, line_model, foreign_key, party_field


def get_document_details(company: str, document_type: str, document_id: str) -> dict[str, Any] | None:
    """Return a controlled read-only document projection."""
    resolved = _resolve(document_type, document_id, company)
    if resolved is None:
        return None
    document, _line_model, _foreign_key, party_field = resolved
    return {
        "id": document.id,
        "document_type": document_type,
        "company_id": document.company,
        "document_no": document.document_no,
        "posting_date": document.posting_date,
        "document_date": document.document_date,
        "status": _status(document.docstatus),
        "docstatus": document.docstatus,
        "party_id": getattr(document, party_field, None),
        "currency": getattr(document, "transaction_currency", None),
        "grand_total": _decimal(getattr(document, "grand_total", None)),
        "outstanding_amount": _decimal(getattr(document, "outstanding_amount", None)),
        "payment_type": getattr(document, "payment_type", None),
        "is_reversal": bool(getattr(document, "is_reversal", False)),
    }


def get_document_lines(company: str, document_type: str, document_id: str) -> list[dict[str, Any]] | None:
    """Return controlled line projections for a document."""
    resolved = _resolve(document_type, document_id, company)
    if resolved is None:
        return None
    _document, line_model, foreign_key, _party_field = resolved
    if line_model is None or foreign_key is None:
        return []
    rows = database.session.execute(
        database.select(line_model).where(getattr(line_model, foreign_key) == document_id).order_by(line_model.id)
    ).scalars()
    return [
        {
            "id": row.id,
            "item_code": getattr(row, "item_code", None),
            "item_name": getattr(row, "item_name", None),
            "qty": _decimal(getattr(row, "qty", None)),
            "uom": getattr(row, "uom", None),
            "rate": _decimal(getattr(row, "rate", None)),
            "amount": _decimal(getattr(row, "amount", None)),
        }
        for row in rows
    ]


def get_document_status(company: str, document_type: str, document_id: str) -> dict[str, Any] | None:
    """Return the controlled status projection for a document."""
    details = get_document_details(company, document_type, document_id)
    if details is None:
        return None
    return {
        "id": details["id"],
        "document_type": details["document_type"],
        "company_id": details["company_id"],
        "document_no": details["document_no"],
        "status": details["status"],
        "docstatus": details["docstatus"],
        "posting_date": details["posting_date"],
        "is_reversal": details["is_reversal"],
    }
