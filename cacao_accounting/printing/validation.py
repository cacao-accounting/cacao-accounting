# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Public QR validation service for printed documents."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import secrets
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import Entity, database
from cacao_accounting.printing.models import PublicDocumentValidation

VALIDATION_STATUS_VALID = "valid"
VALIDATION_STATUS_INVALID = "invalid"
VALIDATION_STATUS_UNAVAILABLE = "unavailable"
VALIDATION_STATUS_CANCELLED = "cancelled"
VALIDATION_STATUS_REVERTED = "reverted"

VALIDATABLE_TYPES = {
    "sales_invoice",
    "sales_credit_note",
    "sales_return",
    "sales_debit_note",
    "purchase_invoice",
    "purchase_credit_note",
    "purchase_debit_note",
    "purchase_order",
    "journal_entry",
    "exchange_revaluation",
    "payment_entry",
    "bank_transfer",
    "cash_receipt",
    "purchase_receipt",
    "delivery_note",
    "sales_quotation",
    "stock_entry",
}


@dataclass(frozen=True)
class PublicValidationView:
    """Public-safe validation result view model."""

    status: str
    company_name: str
    company_tax_id: str
    document_type: str
    document_number: str
    document_date: date | str | None
    currency: str | None
    total: float
    document_status: str
    validation_time: datetime


def generate_validation_token() -> str:
    """Generate a non-predictable public token."""
    return secrets.token_urlsafe(32)


def get_canonical_payload(document_data: dict[str, Any]) -> str:
    """Serialize validation-safe document data deterministically."""
    allowed_keys = {
        "company_code",
        "company_tax_id",
        "document_type",
        "document_id",
        "document_number",
        "document_date",
        "currency",
        "grand_total",
        "status",
        "party_tax_id",
        "line_count",
    }
    payload = {key: _json_value(value) for key, value in document_data.items() if key in allowed_keys}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def calculate_validation_hash(canonical_payload: str) -> str:
    """Return the SHA256 hash for a canonical payload."""
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


class ValidationService:
    """Create and validate public document validation records."""

    def create_or_update_validation(
        self,
        document_type: str,
        document_id: str,
        document_data: dict[str, Any],
    ) -> PublicDocumentValidation | None:
        """Create or update validation metadata for an official document."""
        status = str(document_data.get("status") or "draft")
        if status in {"draft", "borrador"}:
            return None

        existing = (
            database.session.execute(
                select(PublicDocumentValidation).filter_by(
                    document_type=document_type,
                    document_id=str(document_id),
                )
            )
            .scalars()
            .first()
        )
        validation_hash = calculate_validation_hash(get_canonical_payload(document_data))
        if existing is not None:
            existing.validation_hash = validation_hash
            existing.document_status = status
            existing.document_date = document_data.get("document_date")
            existing.document_number = str(document_data.get("document_number") or existing.document_number)
            return existing

        record = PublicDocumentValidation(
            public_token=generate_validation_token(),
            company_code=str(document_data.get("company_code") or ""),
            document_type=document_type,
            document_id=str(document_id),
            document_number=str(document_data.get("document_number") or ""),
            document_date=document_data.get("document_date"),
            document_status=status,
            validation_hash=validation_hash,
            is_enabled=True,
        )
        database.session.add(record)
        return record

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate a public token against the current document state."""
        record = database.session.execute(select(PublicDocumentValidation).filter_by(public_token=token)).scalars().first()
        if record is None or not record.is_enabled:
            return {"status": VALIDATION_STATUS_UNAVAILABLE}

        current_data = self.get_document_data(record.document_type, record.document_id)
        if current_data is None:
            return {"status": VALIDATION_STATUS_UNAVAILABLE, "record": record}

        status = str(current_data.get("status") or "")
        if status in {"cancelled", "void"}:
            return {"status": VALIDATION_STATUS_CANCELLED, "record": record, "data": current_data}
        if status == "reverted":
            return {"status": VALIDATION_STATUS_REVERTED, "record": record, "data": current_data}

        current_hash = calculate_validation_hash(get_canonical_payload(current_data))
        result = VALIDATION_STATUS_VALID if current_hash == record.validation_hash else VALIDATION_STATUS_INVALID
        return {"status": result, "record": record, "data": current_data}

    def build_public_view(self, validation_result: dict[str, Any]) -> PublicValidationView | None:
        """Build a public-safe view model from a validation result."""
        record = validation_result.get("record")
        if record is None:
            return None
        data = validation_result.get("data") or {}
        entity = database.session.execute(select(Entity).filter_by(code=record.company_code)).scalars().first()
        return PublicValidationView(
            status=str(validation_result["status"]),
            company_name=str(data.get("company_name") or getattr(entity, "company_name", record.company_code)),
            company_tax_id=str(data.get("company_tax_id") or getattr(entity, "tax_id", "")),
            document_type=str(data.get("document_type") or record.document_type),
            document_number=str(record.document_number or data.get("document_number") or ""),
            document_date=data.get("document_date") or record.document_date,
            currency=data.get("currency"),
            total=float(data.get("grand_total") or 0),
            document_status=str(data.get("status") or record.document_status),
            validation_time=datetime.now(),
        )

    def update_validation_from_document(self, document: Any) -> PublicDocumentValidation | None:
        """Extract validation data from a document model and persist it."""
        document_data = self.extract_document_data(document)
        if document_data is None:
            return None
        return self.create_or_update_validation(
            document_data["document_type"],
            document_data["document_id"],
            document_data,
        )

    def extract_document_data(self, document: Any) -> dict[str, Any] | None:
        """Extract a safe canonical payload source from a document model."""
        document_type = _document_type(document)
        if document_type not in VALIDATABLE_TYPES:
            return None

        company_code = str(getattr(document, "company", None) or getattr(document, "entity", "") or "")
        entity = database.session.execute(select(Entity).filter_by(code=company_code)).scalars().first()
        line_count, grand_total = _document_line_summary(document_type, str(document.id))
        explicit_total = _first_attr(document, "grand_total", "paid_amount", "received_amount", "total_amount", "total_loss")
        return {
            "company_code": company_code,
            "company_name": getattr(entity, "company_name", company_code) if entity else company_code,
            "company_tax_id": getattr(entity, "tax_id", "") if entity else "",
            "document_type": document_type,
            "document_id": str(document.id),
            "document_number": str(_first_attr(document, "document_no", "name") or document.id),
            "document_date": _first_attr(document, "posting_date", "document_date", "run_date", "date"),
            "currency": _first_attr(document, "transaction_currency", "currency"),
            "grand_total": float(explicit_total if explicit_total is not None else grand_total),
            "status": _status(document),
            "line_count": line_count,
        }

    def get_document_data(self, document_type: str, document_id: str) -> dict[str, Any] | None:
        """Load a document by registered type and extract validation data."""
        model = _model_for_type(document_type)
        if model is None:
            return None
        document = database.session.get(model, document_id)
        if document is None:
            return None
        return self.extract_document_data(document)

    def get_qr_data_uri(self, url: str) -> str:
        """Encode a validation URL as a PNG QR data URI."""
        try:
            import segno
        except ImportError as exc:
            raise RuntimeError("QR dependency missing: install segno to generate validation QR codes.") from exc
        qr = segno.make(url)
        output = io.BytesIO()
        qr.save(output, kind="png", scale=4)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"


def _model_for_type(document_type: str) -> Any | None:
    from cacao_accounting.database import (
        ComprobanteContable,
        DeliveryNote,
        ExchangeRevaluation,
        PaymentEntry,
        PurchaseInvoice,
        PurchaseOrder,
        PurchaseReceipt,
        SalesInvoice,
        SalesQuotation,
        StockEntry,
    )

    return {
        "journal_entry": ComprobanteContable,
        "sales_invoice": SalesInvoice,
        "sales_credit_note": SalesInvoice,
        "sales_return": SalesInvoice,
        "sales_debit_note": SalesInvoice,
        "purchase_invoice": PurchaseInvoice,
        "purchase_credit_note": PurchaseInvoice,
        "purchase_debit_note": PurchaseInvoice,
        "purchase_order": PurchaseOrder,
        "payment_entry": PaymentEntry,
        "bank_transfer": PaymentEntry,
        "cash_receipt": PaymentEntry,
        "purchase_receipt": PurchaseReceipt,
        "delivery_note": DeliveryNote,
        "sales_quotation": SalesQuotation,
        "stock_entry": StockEntry,
        "exchange_revaluation": ExchangeRevaluation,
    }.get(document_type)


def _document_line_summary(document_type: str, document_id: str) -> tuple[int, float]:
    from cacao_accounting.database import (
        ComprobanteContableDetalle,
        DeliveryNoteItem,
        ExchangeRevaluationItem,
        PaymentReference,
        PurchaseInvoiceItem,
        PurchaseOrderItem,
        PurchaseReceiptItem,
        SalesInvoiceItem,
        SalesQuotationItem,
        StockEntryItem,
    )

    line_map: dict[str, tuple[Any, str, str]] = {
        "journal_entry": (ComprobanteContableDetalle, "transaction_id", "value"),
        "sales_invoice": (SalesInvoiceItem, "sales_invoice_id", "amount"),
        "sales_credit_note": (SalesInvoiceItem, "sales_invoice_id", "amount"),
        "sales_return": (SalesInvoiceItem, "sales_invoice_id", "amount"),
        "sales_debit_note": (SalesInvoiceItem, "sales_invoice_id", "amount"),
        "purchase_invoice": (PurchaseInvoiceItem, "purchase_invoice_id", "amount"),
        "purchase_credit_note": (PurchaseInvoiceItem, "purchase_invoice_id", "amount"),
        "purchase_debit_note": (PurchaseInvoiceItem, "purchase_invoice_id", "amount"),
        "purchase_order": (PurchaseOrderItem, "purchase_order_id", "amount"),
        "purchase_receipt": (PurchaseReceiptItem, "purchase_receipt_id", "amount"),
        "delivery_note": (DeliveryNoteItem, "delivery_note_id", "amount"),
        "sales_quotation": (SalesQuotationItem, "sales_quotation_id", "amount"),
        "stock_entry": (StockEntryItem, "stock_entry_id", "amount"),
        "payment_entry": (PaymentReference, "payment_id", "allocated_amount"),
        "bank_transfer": (PaymentReference, "payment_id", "allocated_amount"),
        "cash_receipt": (PaymentReference, "payment_id", "allocated_amount"),
        "exchange_revaluation": (ExchangeRevaluationItem, "revaluation_id", "difference_amount"),
    }
    config = line_map.get(document_type)
    if config is None:
        return 0, 0.0
    model, fk_name, amount_name = config
    rows = database.session.execute(select(model).filter_by(**{fk_name: document_id})).scalars().all()
    total = sum(abs(float(getattr(row, amount_name, 0) or 0)) for row in rows)
    return len(rows), total


def _document_type(document: Any) -> str:
    raw_type = getattr(document, "voucher_type", None) or getattr(document, "document_type", None)
    if raw_type:
        return "journal_entry" if raw_type == "comprobante_contable" else str(raw_type)
    table_name = str(getattr(document, "__tablename__", "unknown"))
    if table_name == "comprobante_contable":
        return "journal_entry"
    if table_name == "payment_entry":
        return _payment_document_type(document)
    return table_name


def _payment_document_type(document: Any) -> str:
    payment_type = str(getattr(document, "payment_type", ""))
    if payment_type == "internal_transfer":
        return "bank_transfer"
    if payment_type == "receive":
        return "cash_receipt"
    return "payment_entry"


def _status(document: Any) -> str:
    if _document_type(document) == "journal_entry":
        status = str(getattr(document, "status", "draft"))
        return "posted" if status == "submitted" else status
    if hasattr(document, "voided_at") and getattr(document, "voided_at"):
        return "cancelled"
    docstatus = getattr(document, "docstatus", 0)
    if docstatus == 1:
        return "posted"
    if docstatus == 2:
        return "cancelled"
    return "draft"


def _first_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value not in (None, ""):
                return value
    return None


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return value
