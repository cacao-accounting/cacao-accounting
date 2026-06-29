# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Serializable print contexts and schemas for registered documents."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import Entity, database


def build_common_context(company_code: str | None, user_name: str) -> dict[str, Any]:
    """Build common company and audit roots."""
    entity = None
    if company_code:
        entity = database.session.execute(select(Entity).filter_by(code=company_code)).scalars().first()
    return {
        "company": {
            "code": company_code or "",
            "name": _text(entity, "company_name", company_code or ""),
            "legal_name": _text(entity, "name", _text(entity, "company_name", company_code or "")),
            "tax_id": _text(entity, "tax_id", ""),
            "address": _text(entity, "address", ""),
            "phone": _text(entity, "phone1", ""),
            "email": _text(entity, "e_mail", ""),
            "website": _text(entity, "web", ""),
            "logo_url": "/static/img/logo.png",
            "default_currency": _text(entity, "currency", ""),
        },
        "audit": {
            "printed_by": user_name,
            "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    }


def build_journal_entry_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a journal entry."""
    from cacao_accounting.database import Accounts, ComprobanteContable, ComprobanteContableDetalle

    document = database.session.get(ComprobanteContable, document_id)
    context = build_common_context(company_code, _user_name(user))
    if document is None:
        return context

    lines = (
        database.session.execute(
            select(ComprobanteContableDetalle).filter_by(transaction_id=document_id).order_by(ComprobanteContableDetalle.order)
        )
        .scalars()
        .all()
    )
    account_names = {
        account.code: account.name
        for account in database.session.execute(select(Accounts).filter_by(entity=company_code)).scalars().all()
    }
    items: list[dict[str, Any]] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line in lines:
        value = Decimal(str(line.value or 0))
        debit = value if value > 0 else Decimal("0")
        credit = abs(value) if value < 0 else Decimal("0")
        total_debit += debit
        total_credit += credit
        items.append(
            {
                "line_number": int(line.order or len(items) + 1),
                "account_code": line.account or "",
                "account_name": account_names.get(line.account, ""),
                "description": line.memo or line.line_memo or "",
                "debit": float(debit),
                "credit": float(credit),
            }
        )
    context["journal_entry"] = {
        "number": _document_number(document),
        "date": _date_text(_first_attr(document, "posting_date", "date")),
        "status": _document_status(document),
        "currency": _text(document, "transaction_currency", context["company"]["default_currency"]),
        "memo": _text(document, "memo", ""),
        "items": items,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
    }
    return context


def build_sales_invoice_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a sales invoice."""
    from cacao_accounting.database import SalesInvoice, SalesInvoiceItem

    return _build_invoice_context(
        SalesInvoice,
        SalesInvoiceItem,
        "sales_invoice_id",
        "invoice",
        document_id,
        user,
        company_code,
        party_root="customer",
    )


def build_purchase_invoice_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a purchase invoice."""
    from cacao_accounting.database import PurchaseInvoice, PurchaseInvoiceItem

    return _build_invoice_context(
        PurchaseInvoice,
        PurchaseInvoiceItem,
        "purchase_invoice_id",
        "invoice",
        document_id,
        user,
        company_code,
        party_root="supplier",
    )


def build_purchase_order_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a purchase order."""
    from cacao_accounting.database import PurchaseOrder, PurchaseOrderItem

    return _build_line_document_context(
        PurchaseOrder,
        PurchaseOrderItem,
        "purchase_order_id",
        "purchase_order",
        document_id,
        user,
        company_code,
    )


def build_delivery_note_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a delivery note."""
    from cacao_accounting.database import DeliveryNote, DeliveryNoteItem

    return _build_line_document_context(
        DeliveryNote,
        DeliveryNoteItem,
        "delivery_note_id",
        "receipt",
        document_id,
        user,
        company_code,
    )


def build_stock_entry_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for an inventory movement."""
    from cacao_accounting.database import StockEntry, StockEntryItem

    return _build_line_document_context(
        StockEntry,
        StockEntryItem,
        "stock_entry_id",
        "adjustment",
        document_id,
        user,
        company_code,
    )


def build_quotation_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a sales quotation."""
    from cacao_accounting.database import SalesQuotation, SalesQuotationItem

    return _build_line_document_context(
        SalesQuotation,
        SalesQuotationItem,
        "sales_quotation_id",
        "quote",
        document_id,
        user,
        company_code,
    )


def build_payment_entry_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a payment entry."""
    from cacao_accounting.database import PaymentEntry, PaymentReference

    document = database.session.get(PaymentEntry, document_id)
    context = build_common_context(company_code, _user_name(user))
    if document is None:
        return context
    refs = database.session.execute(select(PaymentReference).filter_by(payment_id=document_id)).scalars().all()
    context["payment"] = {
        "number": _document_number(document),
        "date": _date_text(_first_attr(document, "posting_date", "document_date", "date")),
        "status": _document_status(document),
        "party_name": _text(document, "party_name", ""),
        "currency": _text(document, "currency", context["company"]["default_currency"]),
        "paid_amount": _number(_first_attr(document, "paid_amount", "received_amount")),
        "references": [
            {
                "reference_type": _text(ref, "reference_type", ""),
                "reference_number": _text(ref, "reference_document_no", ""),
                "allocated_amount": _number(_text(ref, "allocated_amount", 0)),
            }
            for ref in refs
        ],
    }
    return context


def build_exchange_revaluation_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for an exchange revaluation run."""
    from cacao_accounting.database import ExchangeRevaluation, ExchangeRevaluationItem

    document = database.session.get(ExchangeRevaluation, document_id)
    context = build_common_context(company_code, _user_name(user))
    if document is None:
        return context
    items = database.session.execute(select(ExchangeRevaluationItem).filter_by(revaluation_id=document_id)).scalars().all()
    context["revaluation"] = {
        "number": _document_number(document),
        "date": _date_text(_first_attr(document, "run_date", "posting_date", "date")),
        "status": _document_status(document),
        "currency": _text(document, "currency", context["company"]["default_currency"]),
        "items": [
            {
                "line_number": index,
                "reference_type": _text(item, "reference_type", ""),
                "reference_id": _text(item, "reference_id", ""),
                "old_rate": _number(_text(item, "old_rate", 0)),
                "new_rate": _number(_text(item, "new_rate", 0)),
                "difference_amount": _number(_text(item, "difference_amount", 0)),
            }
            for index, item in enumerate(items, start=1)
        ],
        "total_gain": _number(_text(document, "total_gain", 0)),
        "total_loss": _number(_text(document, "total_loss", 0)),
    }
    return context


def build_journal_entry_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample journal entry context."""
    context = _sample_common_context()
    context["journal_entry"] = {
        "number": "JOU-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "memo": "Opening petty cash",
        "items": [
            {
                "line_number": 1,
                "account_code": "1101.01",
                "account_name": "Petty Cash",
                "description": "Petty cash funding",
                "debit": 1000.0,
                "credit": 0.0,
            },
            {
                "line_number": 2,
                "account_code": "1102.01",
                "account_name": "Bank",
                "description": "Check 123",
                "debit": 0.0,
                "credit": 1000.0,
            },
        ],
        "total_debit": 1000.0,
        "total_credit": 1000.0,
    }
    return context


def build_sales_invoice_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample invoice context."""
    context = _sample_common_context()
    context["invoice"] = {
        "number": "FAC-2026-00001",
        "date": "2026-05-26",
        "due_date": "2026-06-25",
        "status": "posted",
        "currency": "NIO",
        "customer": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "discount": 0.0,
        "taxes": 150.0,
        "other_charges": 0.0,
        "grand_total": 1150.0,
        "amount_in_words": "One thousand one hundred fifty cordobas",
        "notes": "Thank you for your purchase.",
    }
    return context


def build_purchase_order_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample purchase order context."""
    context = _sample_common_context()
    context["purchase_order"] = {
        "number": "PO-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "supplier": _sample_party(),
        "items": [_sample_line()],
        "grand_total": 1150.0,
    }
    return context


def build_payment_entry_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample payment context."""
    context = _sample_common_context()
    context["payment"] = {
        "number": "PAY-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "party_name": "Example Customer",
        "currency": "NIO",
        "paid_amount": 1150.0,
        "references": [{"reference_type": "sales_invoice", "reference_number": "FAC-2026-00001", "allocated_amount": 1150.0}],
    }
    return context


def build_stock_entry_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample inventory movement context."""
    context = _sample_common_context()
    context["adjustment"] = {
        "number": "STE-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "purpose": "receipt",
        "items": [_sample_line()],
        "grand_total": 1150.0,
    }
    return context


def build_exchange_revaluation_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample exchange revaluation context."""
    context = _sample_common_context()
    context["revaluation"] = {
        "number": "REV-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "USD",
        "items": [
            {
                "line_number": 1,
                "reference_type": "sales_invoice",
                "reference_id": "FCV-2026-00001",
                "old_rate": 36.5,
                "new_rate": 36.8,
                "difference_amount": 300.0,
            }
        ],
        "total_gain": 300.0,
        "total_loss": 0.0,
    }
    return context


def build_quotation_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample quotation context."""
    context = _sample_common_context()
    context["quote"] = {
        "number": "QUO-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "customer": _sample_party(),
        "items": [_sample_line()],
        "grand_total": 1150.0,
    }
    return context


def _build_invoice_context(
    model: Any,
    item_model: Any,
    foreign_key: str,
    root_name: str,
    document_id: str,
    user: Any,
    company_code: str,
    party_root: str,
) -> dict[str, Any]:
    context = _build_line_document_context(model, item_model, foreign_key, root_name, document_id, user, company_code)
    document = database.session.get(model, document_id)
    if document is not None:
        context[root_name][party_root] = {
            "code": _text(document, f"{party_root}_id", ""),
            "legal_name": _text(document, f"{party_root}_name", ""),
            "commercial_name": _text(document, f"{party_root}_name", ""),
            "tax_id": _text(document, f"{party_root}_tax_id", ""),
            "address": _text(document, f"{party_root}_address", ""),
            "phone": "",
            "email": "",
        }
    return context


def _build_line_document_context(
    model: Any,
    item_model: Any,
    foreign_key: str,
    root_name: str,
    document_id: str,
    user: Any,
    company_code: str,
) -> dict[str, Any]:
    document = database.session.get(model, document_id)
    context = build_common_context(company_code, _user_name(user))
    if document is None:
        return context
    items = database.session.execute(select(item_model).filter_by(**{foreign_key: document_id})).scalars().all()
    context[root_name] = {
        "number": _document_number(document),
        "date": _date_text(_first_attr(document, "posting_date", "document_date", "date")),
        "due_date": _date_text(_first_attr(document, "due_date", "delivery_date")),
        "status": _document_status(document),
        "currency": _text(
            document, "transaction_currency", _text(document, "currency", context["company"]["default_currency"])
        ),
        "purpose": _text(document, "purpose", ""),
        "items": [_line_context(line, index) for index, line in enumerate(items, start=1)],
        "subtotal": _number(_first_attr(document, "net_total", "subtotal", "total_amount")),
        "discount": _number(_first_attr(document, "discount_amount", "discount")),
        "taxes": _number(_first_attr(document, "total_taxes_and_charges", "taxes")),
        "other_charges": _number(_first_attr(document, "other_charges")),
        "grand_total": _number(_first_attr(document, "grand_total", "total_amount")),
        "notes": _text(document, "remarks", _text(document, "notes", "")),
    }
    return context


def _line_context(line: Any, index: int) -> dict[str, Any]:
    return {
        "line_number": index,
        "item_code": _text(line, "item_code", ""),
        "description": _text(line, "description", _text(line, "item_name", _text(line, "item_code", ""))),
        "quantity": _number(_first_attr(line, "quantity", "qty", "actual_qty")),
        "unit_of_measure": _text(line, "uom", _text(line, "unit_of_measure", "")),
        "unit_price": _number(_first_attr(line, "unit_price", "rate", "valuation_rate")),
        "discount": _number(_first_attr(line, "discount_amount", "discount")),
        "subtotal": _number(_first_attr(line, "net_amount", "amount")),
        "taxes": _number(_first_attr(line, "taxes")),
        "other_charges": _number(_first_attr(line, "other_charges")),
        "line_total": _number(_first_attr(line, "line_total", "amount")),
    }


def _sample_common_context() -> dict[str, Any]:
    return {
        "company": {
            "code": "cacao",
            "name": "Example Company S.A.",
            "legal_name": "Example Company Sociedad Anonima",
            "tax_id": "J0310000000001",
            "address": "Managua, Nicaragua",
            "phone": "+505 2222 0000",
            "email": "info@example.com",
            "website": "www.example.com",
            "logo_url": "/static/img/logo.png",
            "default_currency": "NIO",
        },
        "audit": {"printed_by": "admin", "printed_at": "2026-05-26 10:00"},
    }


def _sample_party() -> dict[str, str]:
    return {
        "code": "CUST-001",
        "legal_name": "Example Customer S.A.",
        "commercial_name": "Example Customer",
        "tax_id": "J0310000000002",
        "address": "Managua, Nicaragua",
        "phone": "+505 8888 0000",
        "email": "buyer@example.com",
    }


def _sample_line() -> dict[str, Any]:
    return {
        "line_number": 1,
        "item_code": "ITEM-001",
        "description": "Example item",
        "quantity": 2.0,
        "unit_of_measure": "UND",
        "unit_price": 500.0,
        "discount": 0.0,
        "subtotal": 1000.0,
        "taxes": 150.0,
        "other_charges": 0.0,
        "line_total": 1150.0,
    }


_LABEL_CURRENCY_CODE = "Currency code"
_ITEMS_KEY = "items[]"

COMMON_SCHEMA = {
    "company": {
        "code": "Company code",
        "name": "Company display name",
        "legal_name": "Company legal name",
        "tax_id": "Company tax identification number",
        "address": "Company address",
        "phone": "Company phone number",
        "email": "Company email address",
        "website": "Company website",
        "logo_url": "Company logo URL",
        "default_currency": "Company default currency code",
    },
    "audit": {
        "printed_by": "User who printed the document",
        "printed_at": "Print date and time",
    },
    "validation": {
        "enabled": "Whether public validation QR is available",
        "public_url": "Public validation URL",
        "qr_data_uri": "QR image encoded as a data URI",
        "token": "Public validation token",
    },
}

LINE_SCHEMA = {
    "line_number": "Line number",
    "item_code": "Item or service code",
    "description": "Line description",
    "quantity": "Quantity",
    "unit_of_measure": "Unit of measure",
    "unit_price": "Unit price",
    "discount": "Line discount amount",
    "subtotal": "Line subtotal",
    "taxes": "Line tax amount",
    "other_charges": "Line additional charges",
    "line_total": "Final line total",
}

INVOICE_SCHEMA = {
    **COMMON_SCHEMA,
    "invoice": {
        "number": "Invoice number",
        "date": "Invoice date",
        "due_date": "Due date",
        "status": "Invoice status",
        "currency": _LABEL_CURRENCY_CODE,
        "customer": "Customer or supplier data",
        _ITEMS_KEY: LINE_SCHEMA,
        "subtotal": "Subtotal before taxes and charges",
        "discount": "Discount amount",
        "taxes": "Tax total",
        "other_charges": "Additional charges",
        "grand_total": "Final total",
        "notes": "Public document notes",
    },
}

JOURNAL_ENTRY_PRINT_SCHEMA = {
    **COMMON_SCHEMA,
    "journal_entry": {
        "number": "Journal entry number",
        "date": "Posting date",
        "status": "Document status",
        "currency": _LABEL_CURRENCY_CODE,
        "memo": "Public memo",
        _ITEMS_KEY: {
            "line_number": "Line number",
            "account_code": "Account code",
            "account_name": "Account name",
            "description": "Line memo",
            "debit": "Debit amount",
            "credit": "Credit amount",
        },
        "total_debit": "Total debit",
        "total_credit": "Total credit",
    },
}

SALES_INVOICE_PRINT_SCHEMA = INVOICE_SCHEMA
PURCHASE_INVOICE_PRINT_SCHEMA = INVOICE_SCHEMA
PURCHASE_ORDER_PRINT_SCHEMA = {**COMMON_SCHEMA, "purchase_order": {_ITEMS_KEY: LINE_SCHEMA}}
DELIVERY_NOTE_PRINT_SCHEMA = {**COMMON_SCHEMA, "receipt": {_ITEMS_KEY: LINE_SCHEMA}}
STOCK_ENTRY_PRINT_SCHEMA = {**COMMON_SCHEMA, "adjustment": {_ITEMS_KEY: LINE_SCHEMA}}
QUOTATION_PRINT_SCHEMA = {**COMMON_SCHEMA, "quote": {_ITEMS_KEY: LINE_SCHEMA}}
PAYMENT_ENTRY_PRINT_SCHEMA = {**COMMON_SCHEMA, "payment": {"references[]": {"allocated_amount": "Allocated amount"}}}
EXCHANGE_REVALUATION_PRINT_SCHEMA = {
    **COMMON_SCHEMA,
    "revaluation": {
        "number": "Revaluation number",
        "date": "Run date",
        "status": "Document status",
        "currency": _LABEL_CURRENCY_CODE,
        _ITEMS_KEY: {
            "reference_type": "Source document type",
            "reference_id": "Source document id",
            "old_rate": "Previous exchange rate",
            "new_rate": "New exchange rate",
            "difference_amount": "Gain or loss amount",
        },
        "total_gain": "Total exchange gain",
        "total_loss": "Total exchange loss",
    },
}


def _first_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value not in (None, ""):
                return value
    return None


def _text(obj: Any, attr: str, default: Any = "") -> str:
    if obj is None:
        return str(default or "")
    return str(getattr(obj, attr, default) or default or "")


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date_text(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value or "")


def _document_number(document: Any) -> str:
    return str(_first_attr(document, "document_no", "name", "id") or "")


def _document_status(document: Any) -> str:
    status = _first_attr(document, "status")
    if status:
        return str(status)
    docstatus = getattr(document, "docstatus", 0)
    if docstatus == 1:
        return "posted"
    if docstatus == 2:
        return "cancelled"
    return "draft"


def _user_name(user: Any) -> str:
    return str(getattr(user, "user", None) or getattr(user, "id", None) or user or "")
