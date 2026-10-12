# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Serializable print contexts and schemas for registered documents."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import BankAccount, Entity, database
from cacao_accounting.i18n import _get_locale

SPANISH_MONTHS = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

ENGLISH_MONTHS = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def numero_a_letras(amount: Any, currency: str | None = None, lang: str | None = None) -> str:
    """Convert a numeric amount into formal text representation in Spanish or English."""
    try:
        num = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    except (TypeError, ValueError, ArithmeticError):
        num = Decimal("0.00")

    target_lang = str(lang or _get_locale() or "es").lower()
    if target_lang.startswith("en"):
        return _amount_to_words_en(num, currency)
    return _amount_to_words_es(num, currency)


def _amount_to_words_es(num: Decimal, currency: str | None = None) -> str:
    """Convert a numeric amount into formal Spanish text representation."""
    if num < 0:
        return f"MENOS {_amount_to_words_es(abs(num), currency)}"

    entero = int(abs(num))
    centavos = int(round((abs(num) - entero) * 100))

    texto_entero = "CERO" if entero == 0 else _convertir_entero_a_letras(entero)
    curr_str = f" {currency.strip().upper()}" if currency and currency.strip() else ""
    return f"{texto_entero}{curr_str} CON {centavos:02d}/100"


def _amount_to_words_en(num: Decimal, currency: str | None = None) -> str:
    """Convert a numeric amount into formal English text representation."""
    if num < 0:
        return f"MINUS {_amount_to_words_en(abs(num), currency)}"

    integer_part = int(abs(num))
    cents_part = int(round((abs(num) - integer_part) * 100))

    text_integer = "ZERO" if integer_part == 0 else _convert_integer_to_words_en(integer_part)
    curr_str = f" {currency.strip().upper()}" if currency and currency.strip() else ""
    return f"{text_integer}{curr_str} AND {cents_part:02d}/100"


UNIDADES = (
    "",
    "UN",
    "DOS",
    "TRES",
    "CUATRO",
    "CINCO",
    "SEIS",
    "SIETE",
    "OCHO",
    "NUEVE",
    "DIEZ",
    "ONCE",
    "DOCE",
    "TRECE",
    "CATORCE",
    "QUINCE",
    "DIECISÉIS",
    "DIECISIETE",
    "DIECIOCHO",
    "DIECINUEVE",
    "VEINTE",
    "VEINTIUNO",
    "VEINTIDÓS",
    "VEINTITRÉS",
    "VEINTICUATRO",
    "VEINTICINCO",
    "VEINTISÉIS",
    "VEINTISIETE",
    "VEINTIOCHO",
    "VEINTINUEVE",
)
DECENAS = ("", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA")
CENTENAS = (
    "",
    "CIENTO",
    "DOSCIENTOS",
    "TRESCIENTOS",
    "CUATROCIENTOS",
    "QUINIENTOS",
    "SEISCIENTOS",
    "SETECIENTOS",
    "OCHOCIENTOS",
    "NOVECIENTOS",
)


def _convertir_grupo_tres_cifras(num: int) -> str:
    """Convert a 3-digit number (0-999) to Spanish text."""
    if num == 0:
        return ""
    if num == 100:
        return "CIEN"

    c = num // 100
    resto = num % 100
    str_c = CENTENAS[c]

    if resto == 0:
        return str_c

    if resto < 30:
        str_r = UNIDADES[resto]
    else:
        d = resto // 10
        u = resto % 10
        str_r = f"{DECENAS[d]} Y {UNIDADES[u]}" if u > 0 else DECENAS[d]

    return f"{str_c} {str_r}".strip()


def _convertir_miles(n: int) -> str:
    """Convert thousands (1000-999999) to Spanish text."""
    miles = n // 1000
    resto = n % 1000
    str_miles = "UN MIL" if miles == 1 else f"{_convertir_grupo_tres_cifras(miles)} MIL"
    if str_miles.endswith("VEINTIUNO MIL"):
        str_miles = str_miles[:-13] + "VEINTIÚN MIL"
    elif str_miles.endswith("UNO MIL") and not str_miles.endswith("VEINTIUNO MIL"):
        str_miles = str_miles[:-7] + "UN MIL"

    str_resto = _convertir_grupo_tres_cifras(resto)
    return f"{str_miles} {str_resto}".strip()


def _convertir_millones(n: int) -> str:
    """Convert millions (>=1000000) to Spanish text."""
    millones = n // 1000000
    resto = n % 1000000
    str_millones = "UN MILLÓN" if millones == 1 else f"{_convertir_entero_a_letras(millones)} MILLONES"
    if str_millones.endswith("VEINTIUNO MILLONES"):
        str_millones = str_millones[:-18] + "VEINTIÚN MILLONES"
    elif str_millones.endswith("UNO MILLONES"):
        str_millones = str_millones[:-12] + "UN MILLONES"

    str_resto = _convertir_entero_a_letras(resto)
    return f"{str_millones} {str_resto}".strip()


def _convertir_entero_a_letras(n: int) -> str:
    """Convert a non-negative integer to Spanish text."""
    if n < 1000:
        return _convertir_grupo_tres_cifras(n)
    if n < 1000000:
        return _convertir_miles(n)
    return _convertir_millones(n)


EN_UNITS = (
    "",
    "ONE",
    "TWO",
    "THREE",
    "FOUR",
    "FIVE",
    "SIX",
    "SEVEN",
    "EIGHT",
    "NINE",
    "TEN",
    "ELEVEN",
    "TWELVE",
    "THIRTEEN",
    "FOURTEEN",
    "FIFTEEN",
    "SIXTEEN",
    "SEVENTEEN",
    "EIGHTEEN",
    "NINETEEN",
)
EN_TENS = ("", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY")


def _convert_3digits_en(num: int) -> str:
    """Convert a 3-digit number (0-999) into English text."""
    if num == 0:
        return ""
    h = num // 100
    rem = num % 100
    res = f"{EN_UNITS[h]} HUNDRED" if h > 0 else ""

    if rem == 0:
        return res

    if rem < 20:
        str_rem = EN_UNITS[rem]
    else:
        t = rem // 10
        u = rem % 10
        str_rem = f"{EN_TENS[t]} {EN_UNITS[u]}" if u > 0 else EN_TENS[t]

    return f"{res} {str_rem}".strip()


def _convert_integer_to_words_en(n: int) -> str:
    """Convert integer part to English text."""
    if n == 0:
        return ""
    if n < 1000:
        return _convert_3digits_en(n)
    if n < 1000000:
        thousands = n // 1000
        rem = n % 1000
        str_th = f"{_convert_3digits_en(thousands)} THOUSAND"
        str_rem = _convert_3digits_en(rem)
        return f"{str_th} {str_rem}".strip()

    millions = n // 1000000
    rem = n % 1000000
    str_mil = f"{_convert_integer_to_words_en(millions)} MILLION"
    str_rem = _convert_integer_to_words_en(rem)
    return f"{str_mil} {str_rem}".strip()


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
            "logo_url": "/static/media/brand.svg",
            "default_currency": _text(entity, "currency", ""),
        },
        "audit": {
            "printed_by": user_name,
            "printed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "created_by": "-",
            "created_at": None,
            "approved_by": "-",
            "approved_at": None,
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
                "debit": debit,
                "credit": credit,
            }
        )
    context["journal_entry"] = {
        "number": _document_number(document),
        "date": _date_text(_first_attr(document, "posting_date", "date")),
        "status": _document_status(document),
        "currency": _text(document, "transaction_currency", context["company"]["default_currency"]),
        "memo": _text(document, "memo", ""),
        "items": items,
        "total_debit": total_debit,
        "total_credit": total_credit,
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


def build_sales_order_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a sales order."""
    from cacao_accounting.database import SalesOrder, SalesOrderItem

    return _build_line_document_context(
        SalesOrder,
        SalesOrderItem,
        "sales_order_id",
        "sales_order",
        document_id,
        user,
        company_code,
    )


def build_sales_request_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a sales request."""
    from cacao_accounting.database import SalesRequest, SalesRequestItem

    return _build_line_document_context(
        SalesRequest,
        SalesRequestItem,
        "sales_request_id",
        "sales_request",
        document_id,
        user,
        company_code,
    )


def build_purchase_request_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a purchase request."""
    from cacao_accounting.database import PurchaseRequest, PurchaseRequestItem

    return _build_line_document_context(
        PurchaseRequest,
        PurchaseRequestItem,
        "purchase_request_id",
        "purchase_request",
        document_id,
        user,
        company_code,
    )


def build_supplier_quotation_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a supplier quotation."""
    from cacao_accounting.database import SupplierQuotation, SupplierQuotationItem

    return _build_line_document_context(
        SupplierQuotation,
        SupplierQuotationItem,
        "supplier_quotation_id",
        "supplier_quotation",
        document_id,
        user,
        company_code,
    )


def build_request_for_quotation_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a request for quotation."""
    from cacao_accounting.database import PurchaseQuotation, PurchaseQuotationItem

    return _build_line_document_context(
        PurchaseQuotation,
        PurchaseQuotationItem,
        "purchase_quotation_id",
        "request_for_quotation",
        document_id,
        user,
        company_code,
    )


def build_purchase_receipt_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a purchase receipt."""
    from cacao_accounting.database import PurchaseReceipt, PurchaseReceiptItem

    return _build_line_document_context(
        PurchaseReceipt,
        PurchaseReceiptItem,
        "purchase_receipt_id",
        "purchase_receipt",
        document_id,
        user,
        company_code,
    )


def build_landed_cost_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a landed cost voucher."""
    from cacao_accounting.database import ImportLandedCost, ImportLandedCostItem

    return _build_line_document_context(
        ImportLandedCost,
        ImportLandedCostItem,
        "import_landed_cost_id",
        "landed_cost",
        document_id,
        user,
        company_code,
    )


def build_check_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a check payment."""
    from cacao_accounting.database import PaymentEntry, PaymentReference

    document = database.session.get(PaymentEntry, document_id)
    context = build_common_context(company_code, _user_name(user))
    if document is None:
        return context

    target_lang = str((options or {}).get("lang") or _get_locale() or "es").lower()
    months_list = ENGLISH_MONTHS if target_lang.startswith("en") else SPANISH_MONTHS

    dt = _first_attr(document, "posting_date", "document_date", "date")
    if isinstance(dt, (date, datetime)):
        day_str = f"{dt.day:02d}"
        month_str = f"{dt.month:02d}"
        month_name = months_list[dt.month] if 1 <= dt.month <= 12 else ""
        year_str = f"{dt.year}"
        date_formatted = dt.strftime("%Y-%m-%d")
    else:
        day_str, month_str, month_name, year_str = "", "", "", ""
        date_formatted = str(dt or "")

    paid_amount = _number(_first_attr(document, "paid_amount", "received_amount"))
    curr = _text(document, "currency", context["company"]["default_currency"])
    amount_words = numero_a_letras(paid_amount, curr, lang=target_lang)

    bank = None
    if document.bank_account_id:
        bank = database.session.get(BankAccount, document.bank_account_id)

    check_no = _text(document, "external_number", _text(document, "reference_no", _document_number(document)))
    payee_name = _text(document, "party_name", "")

    refs = database.session.execute(select(PaymentReference).filter_by(payment_id=document_id)).scalars().all()
    context["check"] = {
        "number": check_no,
        "payment_number": _document_number(document),
        "date": date_formatted,
        "day": day_str,
        "month": month_str,
        "month_name": month_name,
        "year": year_str,
        "payee_name": payee_name,
        "amount": paid_amount,
        "amount_in_words": amount_words,
        "currency": curr,
        "bank_account_name": _text(bank, "account_name", ""),
        "bank_account_number": _text(bank, "account_number", ""),
        "bank_name": _text(bank, "bank_name", ""),
        "memo": _text(document, "remarks", ""),
        "status": _document_status(document),
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


def build_check_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample check context for format preview and editing."""
    context = _sample_common_context()
    amount = Decimal("1250.50")
    curr = "NIO"
    target_lang = str(_get_locale() or "es").lower()
    months_list = ENGLISH_MONTHS if target_lang.startswith("en") else SPANISH_MONTHS
    context["check"] = {
        "number": "10539",
        "payment_number": "PAY-2026-00001",
        "date": "2026-05-26",
        "day": "26",
        "month": "05",
        "month_name": months_list[5],
        "year": "2026",
        "payee_name": "Comercial de Suministros S.A.",
        "amount": amount,
        "amount_in_words": numero_a_letras(amount, curr, lang=target_lang),
        "currency": curr,
        "bank_account_name": "Cuenta Corriente Banpro Cacao",
        "bank_account_number": "100100998877",
        "bank_name": "Banpro",
        "memo": "Pago de factura de proveedores No. 4501",
        "status": "posted",
        "references": [
            {"reference_type": "purchase_invoice", "reference_number": "FAC-2026-00100", "allocated_amount": 1250.50}
        ],
    }
    return context


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


def build_withholding_certificate_print_context(
    document_id: str,
    user: Any,
    company_code: str,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build print context for a fiscal withholding certificate."""
    from cacao_accounting.database import PaymentEntry, WithholdingCertificate
    from cacao_accounting.withholding_service import withholding_certificate_lines

    certificate = database.session.get(WithholdingCertificate, document_id)
    context = build_common_context(company_code, _user_name(user))
    if certificate is None:
        return context
    context["withholding_certificate"] = {
        "number": certificate.certificate_no,
        "date": _date_text(certificate.posting_date),
        "status": "posted" if certificate.status == "issued" else certificate.status,
        "supplier_name": certificate.supplier_name,
        "currency": certificate.currency or context["company"]["default_currency"],
        "payment_number": _text(database.session.get(PaymentEntry, certificate.payment_id), "document_no", ""),
        "gross_amount": certificate.gross_amount,
        "withheld_amount": certificate.withheld_amount,
        "cash_amount": certificate.cash_amount,
        "lines": withholding_certificate_lines(certificate),
    }
    return context


def build_withholding_certificate_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a configurable sample withholding certificate context."""
    context = _sample_common_context()
    context["withholding_certificate"] = {
        "number": "RET-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "supplier_name": "Proveedor de ejemplo",
        "currency": "NIO",
        "payment_number": "PAY-2026-00001",
        "gross_amount": Decimal("1000.00"),
        "withheld_amount": Decimal("20.00"),
        "cash_amount": Decimal("980.00"),
        "lines": [
            {
                "concept": "retencion_renta",
                "base_amount": Decimal("1000.00"),
                "rate": Decimal("2.00"),
                "amount": Decimal("20.00"),
            }
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
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_delivery_note_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample delivery note context."""
    context = _sample_common_context()
    context["receipt"] = {
        "number": "DEL-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "customer": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_sales_order_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample sales order context."""
    context = _sample_common_context()
    context["sales_order"] = {
        "number": "SO-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "customer": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_sales_request_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample sales request context."""
    context = _sample_common_context()
    context["sales_request"] = {
        "number": "SR-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "customer": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_purchase_request_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample purchase request context."""
    context = _sample_common_context()
    context["purchase_request"] = {
        "number": "PR-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "supplier": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_supplier_quotation_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample supplier quotation context."""
    context = _sample_common_context()
    context["supplier_quotation"] = {
        "number": "SQ-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "supplier": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_request_for_quotation_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample request for quotation context."""
    context = _sample_common_context()
    context["request_for_quotation"] = {
        "number": "RFQ-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "supplier": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_purchase_receipt_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample purchase receipt context."""
    context = _sample_common_context()
    context["purchase_receipt"] = {
        "number": "REC-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "supplier": _sample_party(),
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
        "grand_total": 1150.0,
    }
    return context


def build_landed_cost_sample_context(user: Any = None, company: Any = None) -> dict[str, Any]:
    """Build a sample landed cost voucher context."""
    context = _sample_common_context()
    context["landed_cost"] = {
        "number": "LC-2026-00001",
        "date": "2026-05-26",
        "status": "posted",
        "currency": "NIO",
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
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
        "currency": "NIO",
        "purpose": "receipt",
        "items": [_sample_line()],
        "subtotal": 1000.0,
        "taxes": 150.0,
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
        "subtotal": 1000.0,
        "taxes": 150.0,
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
    item_query = select(item_model).filter_by(**{foreign_key: document_id})
    if hasattr(item_model, "is_superseded"):
        item_query = item_query.filter_by(is_superseded=False)
    items = database.session.execute(item_query).scalars().all()
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
        "subtotal": _number(_first_attr(document, "net_total", "subtotal", "total_amount", "total")),
        "discount": _number(_first_attr(document, "discount_amount", "discount")),
        "taxes": _number(_first_attr(document, "total_taxes_and_charges", "taxes", "tax_total")),
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
            "logo_url": "/static/media/brand.svg",
            "default_currency": "NIO",
        },
        "audit": {
            "printed_by": "admin",
            "printed_at": "2026-05-26 10:00",
            "created_by": "-",
            "created_at": None,
            "approved_by": "-",
            "approved_at": None,
        },
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
        "quantity": Decimal("2"),
        "unit_of_measure": "UND",
        "unit_price": Decimal("500"),
        "discount": Decimal("0"),
        "subtotal": Decimal("1000"),
        "taxes": Decimal("150"),
        "other_charges": Decimal("0"),
        "line_total": Decimal("1150"),
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
        "created_by": "User who created the document",
        "created_at": "Document creation date and time",
        "approved_by": "User who approved the document",
        "approved_at": "Document approval date and time",
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
SALES_ORDER_PRINT_SCHEMA = {**COMMON_SCHEMA, "sales_order": {_ITEMS_KEY: LINE_SCHEMA}}
SALES_REQUEST_PRINT_SCHEMA = {**COMMON_SCHEMA, "sales_request": {_ITEMS_KEY: LINE_SCHEMA}}
PURCHASE_REQUEST_PRINT_SCHEMA = {**COMMON_SCHEMA, "purchase_request": {_ITEMS_KEY: LINE_SCHEMA}}
SUPPLIER_QUOTATION_PRINT_SCHEMA = {**COMMON_SCHEMA, "supplier_quotation": {_ITEMS_KEY: LINE_SCHEMA}}
REQUEST_FOR_QUOTATION_PRINT_SCHEMA = {**COMMON_SCHEMA, "request_for_quotation": {_ITEMS_KEY: LINE_SCHEMA}}
PURCHASE_RECEIPT_PRINT_SCHEMA = {**COMMON_SCHEMA, "purchase_receipt": {_ITEMS_KEY: LINE_SCHEMA}}
LANDED_COST_PRINT_SCHEMA = {**COMMON_SCHEMA, "landed_cost": {_ITEMS_KEY: LINE_SCHEMA}}
DELIVERY_NOTE_PRINT_SCHEMA = {**COMMON_SCHEMA, "receipt": {_ITEMS_KEY: LINE_SCHEMA}}
STOCK_ENTRY_PRINT_SCHEMA = {**COMMON_SCHEMA, "adjustment": {_ITEMS_KEY: LINE_SCHEMA}}
QUOTATION_PRINT_SCHEMA = {**COMMON_SCHEMA, "quote": {_ITEMS_KEY: LINE_SCHEMA}}
PAYMENT_ENTRY_PRINT_SCHEMA = {**COMMON_SCHEMA, "payment": {"references[]": {"allocated_amount": "Allocated amount"}}}
CHECK_PRINT_SCHEMA = {
    **COMMON_SCHEMA,
    "check": {
        "number": "Check number",
        "payment_number": "Payment document number",
        "date": "Check issue date (YYYY-MM-DD)",
        "day": "Check issue day (DD)",
        "month": "Check issue month (MM)",
        "month_name": "Check issue month name in active locale",
        "year": "Check issue year (YYYY)",
        "payee_name": "Payee or beneficiary name",
        "amount": "Check amount in numeric figures",
        "amount_in_words": "Check amount spelled out in active locale words",
        "currency": _LABEL_CURRENCY_CODE,
        "bank_account_name": "Source bank account display name",
        "bank_account_number": "Source bank account number",
        "bank_name": "Bank institution name",
        "memo": "Check memo or remarks",
        "status": "Document status",
        "references[]": {"allocated_amount": "Allocated amount", "reference_number": "Reference document number"},
    },
}
WITHHOLDING_CERTIFICATE_PRINT_SCHEMA = {
    **COMMON_SCHEMA,
    "withholding_certificate": {"lines[]": {"base_amount": "Base amount", "rate": "Rate", "amount": "Withheld amount"}},
}
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


def _number(value: Any) -> Decimal:
    """Return a financial value without crossing through binary float."""
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value or 0))
        return number if number.is_finite() else Decimal("0")
    except (TypeError, ValueError, ArithmeticError):
        return Decimal("0")


def _date_text(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value or "")


def _document_number(document: Any) -> str:
    return str(_first_attr(document, "document_no", "name", "id") or "")


def _document_status(document: Any) -> str:
    docstatus = getattr(document, "docstatus", None)
    if docstatus == 2:
        return "cancelled"
    status = getattr(document, "status", None)
    if status not in (None, ""):
        return str(status)
    if docstatus == 1:
        return "posted"
    return "draft"


def _user_name(user: Any) -> str:
    return str(getattr(user, "user", None) or getattr(user, "id", None) or user or "")
