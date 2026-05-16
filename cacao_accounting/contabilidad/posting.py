# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de contabilizacion para documentos operativos."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from sqlalchemy import func, or_, select

from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    BankTransaction,
    BankAccount,
    Book,
    CompanyDefaultAccount,
    ComprobanteContable,
    ComprobanteContableDetalle,
    DeliveryNote,
    DeliveryNoteItem,
    ExchangeRate,
    GLEntry,
    Item,
    ItemAccount,
    PartyAccount,
    PaymentEntry,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseReceipt,
    PurchaseReceiptItem,
    SalesInvoice,
    SalesInvoiceItem,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    Entity,
    database,
)
from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_gl_account_usage
from cacao_accounting.document_identifiers import IdentifierConfigurationError, validate_accounting_period
from cacao_accounting.tax_pricing_service import TaxCalculationResult, calculate_taxes

JOURNAL_TRANSACTION_TYPE = "journal_entry"


class PostingError(ValueError):
    """Error controlado del motor de contabilizacion."""


@dataclass(frozen=True)
class LedgerContext:
    """Contexto comun para generar lineas contables por libro."""

    company: str
    posting_date: Any
    ledger_id: str | None
    voucher_type: str
    voucher_id: str
    document_no: str | None
    naming_series_id: str | None
    accounting_period_id: str | None
    fiscal_year_id: str | None
    transaction_currency: str | None
    company_currency: str | None
    exchange_rate: Decimal | None
    document_remarks: str | None


def _decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise PostingError("Valor numerico invalido para contabilizacion.") from exc


def _validate_single_sided_amount(debit: Decimal, credit: Decimal) -> None:
    if debit < 0 or credit < 0:
        raise PostingError("Los montos de debito y credito deben ser no negativos.")
    if not ((debit > 0 and credit == 0) or (debit == 0 and credit > 0)):
        raise PostingError("Cada entrada GL debe tener un debito o un credito positivo, no ambos.")


def _get_voucher_type(document: Any) -> str:
    if isinstance(document, ComprobanteContable):
        return JOURNAL_TRANSACTION_TYPE
    return str(getattr(document, "voucher_type", None) or getattr(document, "__tablename__", ""))


def _get_voucher_id(document: Any) -> str:
    return str(getattr(document, "voucher_id", None) or getattr(document, "id", ""))


def _find_period_ids(company: str, posting_date: Any) -> tuple[str | None, str | None]:
    period = (
        database.session.execute(
            select(AccountingPeriod)
            .filter_by(entity=company, enabled=True)
            .where(AccountingPeriod.start <= posting_date)
            .where(AccountingPeriod.end >= posting_date)
        )
        .scalars()
        .first()
    )
    if not period:
        return None, None
    return period.id, period.fiscal_year_id


def _normalize_ledger_codes(ledger_code: str | Sequence[str] | None) -> list[str] | None:
    if ledger_code is None:
        return None
    if isinstance(ledger_code, str):
        normalized = ledger_code.strip()
        return [normalized] if normalized else None

    codes: list[str] = []
    for item in ledger_code:
        normalized = str(item).strip()
        if normalized and normalized not in codes:
            codes.append(normalized)
    return codes or None


def _active_books(company: str, ledger_code: str | Sequence[str] | None = None) -> list[Book | None]:
    selected_codes = _normalize_ledger_codes(ledger_code)
    query = select(Book).where(
        Book.entity == company,
        or_(Book.status == "activo", Book.status.is_(None)),
    )
    if selected_codes:
        query = query.where(Book.code.in_(selected_codes))
    books = database.session.execute(query.order_by(Book.is_primary.desc(), Book.code)).scalars().all()
    if selected_codes:
        found_codes = {book.code for book in books}
        missing_codes = [code for code in selected_codes if code not in found_codes]
        if missing_codes:
            raise PostingError("Uno o más libros contables seleccionados no existen o están inactivos para la compañia.")
    return list(books) if books else [None]


def _document_contexts(document: Any, ledger_code: str | Sequence[str] | None = None) -> list[LedgerContext]:
    company = _company_for(document)
    posting_date = _posting_date_for(document)
    allow_closing = bool(getattr(document, "is_closing", False))
    validate_accounting_period(company, posting_date, allow_closing=allow_closing)
    accounting_period_id, fiscal_year_id = _find_period_ids(company, posting_date)
    exchange_rate = getattr(document, "exchange_rate", None)
    entity = database.session.get(Entity, company)
    default_company_currency = getattr(entity, "currency", None) if entity else None
    contexts: list[LedgerContext] = []
    for book in _active_books(company, ledger_code):
        book_currency = getattr(book, "currency", None)
        company_currency = getattr(document, "base_currency", None) or book_currency or default_company_currency
        contexts.append(
            LedgerContext(
                company=company,
                posting_date=posting_date,
                ledger_id=book.id if book else None,
                voucher_type=_get_voucher_type(document),
                voucher_id=_get_voucher_id(document),
                document_no=getattr(document, "document_no", None),
                naming_series_id=getattr(document, "naming_series_id", None),
                accounting_period_id=accounting_period_id,
                fiscal_year_id=fiscal_year_id,
                transaction_currency=getattr(document, "transaction_currency", None),
                company_currency=company_currency,
                exchange_rate=_decimal_value(exchange_rate) if exchange_rate is not None else None,
                document_remarks=getattr(document, "remarks", None),
            )
        )
    return contexts


def _account_code_for(account_id: str) -> str | None:
    account = database.session.get(Accounts, account_id)
    return getattr(account, "code", None)


def _require_account(account_id: str | None, message: str) -> str:
    if not account_id:
        raise PostingError(message)
    if not database.session.get(Accounts, account_id):
        raise PostingError("La cuenta contable configurada no existe.")
    return account_id


def _company_defaults(company: str) -> CompanyDefaultAccount | None:
    return database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()


def _resolve_party_account_id(party_id: str | None, company: str, receivable: bool) -> str | None:
    if party_id:
        mapping = (
            database.session.execute(select(PartyAccount).filter_by(party_id=party_id, company=company)).scalars().first()
        )
        if mapping:
            account_id = mapping.receivable_account_id if receivable else mapping.payable_account_id
            if account_id:
                return account_id
    defaults = _company_defaults(company)
    if not defaults:
        return None
    return defaults.default_receivable if receivable else defaults.default_payable


def _resolve_item_account_id(item_code: str | None, company: str, account_type: str) -> str | None:
    if item_code:
        mapping = (
            database.session.execute(select(ItemAccount).filter_by(item_code=item_code, company=company)).scalars().first()
        )
        if mapping:
            mapped = {
                "income": mapping.income_account_id,
                "expense": mapping.expense_account_id,
                "inventory": mapping.inventory_account_id,
            }.get(account_type)
            if mapped:
                return mapped

    defaults = _company_defaults(company)
    if not defaults:
        return None
    return {
        "income": defaults.default_income,
        "expense": defaults.default_expense,
        "inventory": defaults.default_inventory,
        "cogs": defaults.default_cogs or defaults.default_expense,
        "inventory_adjustment": defaults.inventory_adjustment_account_id or defaults.default_expense,
        "bridge": defaults.bridge_account_id,
    }.get(account_type)


def _account_id_for_item(item: Any, company: str, account_type: str) -> str | None:
    explicit_field = f"{account_type}_account_id"
    if hasattr(item, explicit_field):
        value = getattr(item, explicit_field)
        if value:
            return str(value)
    return _resolve_item_account_id(getattr(item, "item_code", None), company, account_type)


def _account_id_for_comprobante_line(line: Any, company: str) -> str:
    explicit_account_id = getattr(line, "account_id", None)
    if explicit_account_id:
        return _require_account(
            str(explicit_account_id),
            "No existe cuenta contable configurada para la línea del comprobante contable.",
        )

    account_code = getattr(line, "account", None)
    if not account_code:
        raise PostingError("La línea del comprobante contable no tiene cuenta especificada.")

    account = database.session.execute(select(Accounts).filter_by(entity=company, code=account_code)).scalars().first()
    if not account:
        raise PostingError(f"La cuenta contable '{account_code}' no existe para la compañía.")
    return account.id


def _resolve_bank_gl_account_id(document: PaymentEntry, destination: bool) -> str | None:
    explicit = document.paid_to_account_id if destination else document.paid_from_account_id
    if explicit:
        return explicit
    if document.bank_account_id:
        bank_account = database.session.get(BankAccount, document.bank_account_id)
        if bank_account and bank_account.gl_account_id:
            return bank_account.gl_account_id
    defaults = _company_defaults(_company_for(document))
    return defaults.default_bank if defaults else None


def _has_active_gl_entries(document: Any) -> bool:
    return (
        database.session.execute(
            select(GLEntry.id)
            .filter_by(
                company=_company_for(document),
                voucher_type=_get_voucher_type(document),
                voucher_id=_get_voucher_id(document),
                is_cancelled=False,
                is_reversal=False,
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _has_stock_ledger_entries(document: Any) -> bool:
    return (
        database.session.execute(
            select(StockLedgerEntry.id)
            .filter_by(
                company=_company_for(document),
                voucher_type=_get_voucher_type(document),
                voucher_id=_get_voucher_id(document),
                is_cancelled=False,
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _create_gl_entry(
    *,
    context: LedgerContext,
    account_id: str,
    debit: Decimal,
    credit: Decimal,
    debit_in_account_currency: Decimal | None = None,
    credit_in_account_currency: Decimal | None = None,
    party_type: str | None = None,
    party_id: str | None = None,
    bank_account_id: str | None = None,
    is_advance: bool = False,
    cost_center_code: str | None = None,
    unit_code: str | None = None,
    project_code: str | None = None,
    entry_remarks: str | None = None,
    is_reversal: bool = False,
    reversal_of: str | None = None,
    is_fiscal_year_closing: bool = False,
) -> GLEntry:
    _validate_single_sided_amount(debit, credit)
    return GLEntry(
        posting_date=context.posting_date,
        company=context.company,
        ledger_id=context.ledger_id,
        account_id=_require_account(account_id, "Toda entrada GL requiere cuenta contable."),
        account_code=_account_code_for(account_id),
        debit=debit,
        credit=credit,
        debit_in_account_currency=(
            debit_in_account_currency
            if debit_in_account_currency is not None
            else (debit if context.transaction_currency else None)
        ),
        credit_in_account_currency=(
            credit_in_account_currency
            if credit_in_account_currency is not None
            else (credit if context.transaction_currency else None)
        ),
        account_currency=context.transaction_currency,
        company_currency=context.company_currency,
        exchange_rate=context.exchange_rate,
        party_type=party_type,
        party_id=party_id,
        bank_account_id=bank_account_id,
        is_advance=is_advance,
        is_fiscal_year_closing=is_fiscal_year_closing,
        voucher_type=context.voucher_type,
        voucher_id=context.voucher_id,
        document_no=context.document_no,
        naming_series_id=context.naming_series_id,
        fiscal_year_id=context.fiscal_year_id,
        accounting_period_id=context.accounting_period_id,
        cost_center_code=cost_center_code,
        unit_code=unit_code,
        project_code=project_code,
        remarks=entry_remarks if entry_remarks is not None else context.document_remarks,
        is_reversal=is_reversal,
        reversal_of=reversal_of,
    )


def _assert_entries_balance(entries: list[GLEntry]) -> None:
    ledger_ids = {entry.ledger_id for entry in entries}
    for ledger_id in ledger_ids:
        ledger_entries = [entry for entry in entries if entry.ledger_id == ledger_id]
        debit_total = sum((_decimal_value(entry.debit) for entry in ledger_entries), Decimal("0"))
        credit_total = sum((_decimal_value(entry.credit) for entry in ledger_entries), Decimal("0"))
        if debit_total != credit_total:
            raise PostingError("Las entradas GL generadas no balancean por libro contable.")


def _to_company_currency(amount: Decimal, exchange_rate: Decimal) -> Decimal:
    if exchange_rate == 0:
        raise PostingError("El tipo de cambio no puede ser cero.")
    return (amount * exchange_rate).quantize(Decimal("0.0001"))


def _lookup_exchange_rate(origin: str, destination: str, posting_date: Any) -> Decimal:
    if origin == destination:
        return Decimal("1")
    rate = (
        database.session.execute(select(ExchangeRate).filter_by(origin=origin, destination=destination, date=posting_date))
        .scalars()
        .first()
    )
    if rate is not None:
        return _decimal_value(rate.rate)

    inverse_rate = (
        database.session.execute(select(ExchangeRate).filter_by(origin=destination, destination=origin, date=posting_date))
        .scalars()
        .first()
    )
    if inverse_rate is not None:
        inverse_value = _decimal_value(inverse_rate.rate)
        if inverse_value == 0:
            raise PostingError("El tipo de cambio no puede ser cero.")
        return Decimal("1") / inverse_value

    raise PostingError(f"No existe tipo de cambio registrado para {origin} -> {destination} en la fecha {posting_date}.")


def _add_entries(entries: list[GLEntry]) -> list[GLEntry]:
    if not entries:
        return []
    _assert_entries_balance(entries)
    for entry in entries:
        try:
            validate_gl_account_usage(entry.account_id, entry.voucher_type)
        except DefaultAccountError as exc:
            raise PostingError(str(exc)) from exc
    database.session.add_all(entries)
    return entries


def _signed_amount(document: Any, amount: Decimal) -> Decimal:
    return -amount if getattr(document, "is_return", False) or getattr(document, "is_reversal", False) else amount


def _normal_entries_for_amount(
    *,
    context: LedgerContext,
    debit_account_id: str,
    credit_account_id: str,
    amount: Decimal,
    party_type: str | None = None,
    party_id: str | None = None,
    debit_remarks: str | None = None,
    credit_remarks: str | None = None,
) -> list[GLEntry]:
    if amount > 0:
        return [
            _create_gl_entry(
                context=context,
                account_id=debit_account_id,
                debit=amount,
                credit=Decimal("0"),
                party_type=party_type,
                party_id=party_id,
                entry_remarks=debit_remarks,
            ),
            _create_gl_entry(
                context=context,
                account_id=credit_account_id,
                debit=Decimal("0"),
                credit=amount,
                entry_remarks=credit_remarks,
            ),
        ]
    if amount < 0:
        reversed_amount = abs(amount)
        return [
            _create_gl_entry(
                context=context,
                account_id=credit_account_id,
                debit=reversed_amount,
                credit=Decimal("0"),
                entry_remarks=credit_remarks,
            ),
            _create_gl_entry(
                context=context,
                account_id=debit_account_id,
                debit=Decimal("0"),
                credit=reversed_amount,
                party_type=party_type,
                party_id=party_id,
                entry_remarks=debit_remarks,
            ),
        ]
    return []


def _invoice_items_total(items: Sequence[Any], document: Any) -> Decimal:
    total = sum((_decimal_value(getattr(item, "amount", None)) for item in items), Decimal("0"))
    signed_total = _signed_amount(document, total)
    if signed_total == 0:
        raise PostingError("El total del documento es cero y no puede contabilizarse.")
    return signed_total


def _tax_result_for_document(document: Any, items: Sequence[Any]) -> TaxCalculationResult | None:
    template_id = getattr(document, "tax_template_id", None)
    if not template_id:
        return None
    setattr(document, "_tax_items", items)
    return calculate_taxes(document, template_id)


def _payment_has_references(payment_id: str) -> bool:
    from cacao_accounting.database import PaymentReference

    return database.session.execute(select(PaymentReference.id).filter_by(payment_id=payment_id)).scalars().first() is not None


def _signed_tax_delta(document: Any, tax_result: TaxCalculationResult | None) -> Decimal:
    if tax_result is None:
        return Decimal("0")
    return _signed_amount(document, tax_result.payable_delta)


def _append_sales_tax_entries(
    *,
    entries: list[GLEntry],
    context: LedgerContext,
    document: SalesInvoice,
    tax_result: TaxCalculationResult | None,
) -> None:
    if tax_result is None:
        return
    for tax_line in tax_result.lines:
        if tax_line.is_inclusive or tax_line.amount == 0:
            continue
        defaults = _company_defaults(_company_for(document))
        account_id = _require_account(
            tax_line.account_id or (defaults.default_sales_tax_account_id if defaults else None),
            "Falta la cuenta contable de impuesto de venta.",
        )
        amount = _signed_amount(document, tax_line.amount)
        if tax_line.behavior == "deductive":
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=account_id,
                    debit=abs(amount) if amount > 0 else Decimal("0"),
                    credit=abs(amount) if amount < 0 else Decimal("0"),
                    entry_remarks=tax_line.name,
                )
            )
        else:
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=account_id,
                    debit=abs(amount) if amount < 0 else Decimal("0"),
                    credit=abs(amount) if amount > 0 else Decimal("0"),
                    entry_remarks=tax_line.name,
                )
            )


def _append_purchase_tax_entries(
    *,
    entries: list[GLEntry],
    context: LedgerContext,
    document: PurchaseInvoice,
    tax_result: TaxCalculationResult | None,
) -> None:
    if tax_result is None:
        return
    for tax_line in tax_result.lines:
        if tax_line.is_inclusive or tax_line.amount == 0:
            continue
        defaults = _company_defaults(_company_for(document))
        account_id = _require_account(
            tax_line.account_id or (defaults.default_purchase_tax_account_id if defaults else None),
            "Falta la cuenta contable de impuesto de compra.",
        )
        amount = _signed_amount(document, tax_line.amount)
        if tax_line.behavior == "deductive":
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=account_id,
                    debit=abs(amount) if amount < 0 else Decimal("0"),
                    credit=abs(amount) if amount > 0 else Decimal("0"),
                    entry_remarks=tax_line.name,
                )
            )
        else:
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=account_id,
                    debit=abs(amount) if amount > 0 else Decimal("0"),
                    credit=abs(amount) if amount < 0 else Decimal("0"),
                    entry_remarks=tax_line.name,
                )
            )


def post_sales_invoice(document: SalesInvoice, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para una factura o nota de venta aprobada."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una factura de venta aprobada.")

    company = _company_for(document)
    receivable_account_id = _require_account(
        _resolve_party_account_id(document.customer_id, company, receivable=True),
        "No existe cuenta por cobrar configurada para el cliente.",
    )
    items = database.session.execute(select(SalesInvoiceItem).filter_by(sales_invoice_id=document.id)).scalars().all()
    if not items:
        raise PostingError("La factura de venta no contiene lineas para contabilizar.")

    tax_result = _tax_result_for_document(document, items)
    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        amount_total = _invoice_items_total(items, document) + _signed_tax_delta(document, tax_result)
        if amount_total > 0:
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=receivable_account_id,
                    debit=amount_total,
                    credit=Decimal("0"),
                    party_type="customer",
                    party_id=document.customer_id,
                    entry_remarks="Cuentas por cobrar",
                )
            )
        else:
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=receivable_account_id,
                    debit=Decimal("0"),
                    credit=abs(amount_total),
                    party_type="customer",
                    party_id=document.customer_id,
                    entry_remarks="Cuentas por cobrar",
                )
            )

        for item in items:
            amount = _signed_amount(document, _decimal_value(getattr(item, "amount", None)))
            if amount == 0:
                continue
            income_account_id = _require_account(
                _account_id_for_item(item, company, "income"),
                "Falta la cuenta de ingresos para una linea de factura de venta.",
            )
            if amount > 0:
                entries.append(
                    _create_gl_entry(
                        context=context,
                        account_id=income_account_id,
                        debit=Decimal("0"),
                        credit=amount,
                        entry_remarks=getattr(item, "item_name", None) or getattr(item, "item_code", None),
                    )
                )
            else:
                entries.append(
                    _create_gl_entry(
                        context=context,
                        account_id=income_account_id,
                        debit=abs(amount),
                        credit=Decimal("0"),
                        entry_remarks=getattr(item, "item_name", None) or getattr(item, "item_code", None),
                    )
                )

        _append_sales_tax_entries(entries=entries, context=context, document=document, tax_result=tax_result)

    result = _add_entries(entries)

    from cacao_accounting.document_flow.service import refresh_outstanding_amount_cache

    if not document.grand_total:
        # Se asume que el debito a cuentas por cobrar (amount_total calculado arriba) es el total
        document.grand_total = abs(_invoice_items_total(items, document) + _signed_tax_delta(document, tax_result))
    refresh_outstanding_amount_cache(document)

    return result


def post_purchase_invoice(document: PurchaseInvoice, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para una factura o nota de compra aprobada."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una factura de compra aprobada.")

    company = _company_for(document)
    payable_account_id = _require_account(
        _resolve_party_account_id(document.supplier_id, company, receivable=False),
        "No existe cuenta por pagar configurada para el proveedor.",
    )
    items = database.session.execute(select(PurchaseInvoiceItem).filter_by(purchase_invoice_id=document.id)).scalars().all()
    if not items:
        raise PostingError("La factura de compra no contiene lineas para contabilizar.")

    tax_result = _tax_result_for_document(document, items)
    item_amount_total = _invoice_items_total(items, document)
    amount_total = item_amount_total + _signed_tax_delta(document, tax_result)
    if getattr(document, "purchase_receipt_id", None) or getattr(document, "purchase_order_id", None):
        _record_purchase_reconciliation(document, abs(item_amount_total))

    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        for item in items:
            amount = _signed_amount(document, _decimal_value(getattr(item, "amount", None)))
            if amount == 0:
                continue
            debit_account_type = "bridge" if getattr(document, "purchase_receipt_id", None) else "expense"
            debit_account_id = _require_account(
                _account_id_for_item(item, company, debit_account_type),
                "Falta la cuenta de gasto o cuenta puente para una linea de factura de compra.",
            )
            if amount > 0:
                entries.append(
                    _create_gl_entry(
                        context=context,
                        account_id=debit_account_id,
                        debit=amount,
                        credit=Decimal("0"),
                        entry_remarks=getattr(item, "item_name", None) or getattr(item, "item_code", None),
                    )
                )
            else:
                entries.append(
                    _create_gl_entry(
                        context=context,
                        account_id=debit_account_id,
                        debit=Decimal("0"),
                        credit=abs(amount),
                        entry_remarks=getattr(item, "item_name", None) or getattr(item, "item_code", None),
                    )
                )

        _append_purchase_tax_entries(entries=entries, context=context, document=document, tax_result=tax_result)

        if amount_total > 0:
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=payable_account_id,
                    debit=Decimal("0"),
                    credit=amount_total,
                    party_type="supplier",
                    party_id=document.supplier_id,
                    entry_remarks="Cuentas por pagar",
                )
            )
        else:
            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=payable_account_id,
                    debit=abs(amount_total),
                    credit=Decimal("0"),
                    party_type="supplier",
                    party_id=document.supplier_id,
                    entry_remarks="Cuentas por pagar",
                )
            )

    result = _add_entries(entries)

    from cacao_accounting.document_flow.service import refresh_outstanding_amount_cache

    if not document.grand_total:
        document.grand_total = abs(amount_total)
    refresh_outstanding_amount_cache(document)

    from cacao_accounting.compras.purchase_reconciliation_service import EventType, emit_economic_event

    emit_economic_event(
        event_type=EventType.INVOICE_RECEIVED,
        company=company,
        document_type="purchase_invoice",
        document_id=document.id,
        payload={
            "supplier_id": str(document.supplier_id),
            "posting_date": str(document.posting_date),
            "purchase_order_id": str(document.purchase_order_id) if document.purchase_order_id else None,
            "purchase_receipt_id": str(document.purchase_receipt_id) if document.purchase_receipt_id else None,
        },
    )

    return result


def post_payment_entry(document: PaymentEntry, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para cobros, pagos y transferencias internas."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar un pago aprobado.")

    company = _company_for(document)
    amount = _decimal_value(document.paid_amount or document.received_amount)
    if amount <= 0:
        raise PostingError("El monto del pago debe ser mayor que cero.")

    payment_type = getattr(document, "payment_type", "").lower()
    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        if payment_type == "pay":
            defaults = _company_defaults(company)
            party_account_id = _resolve_party_account_id(document.party_id, company, receivable=False)
            account_id = party_account_id or (
                None if _payment_has_references(document.id) else (defaults.supplier_advance_account_id if defaults else None)
            )
            payable_account_id = _require_account(
                account_id,
                "No existe cuenta por pagar o anticipo configurada para el proveedor.",
            )
            bank_account_id = _require_account(
                _resolve_bank_gl_account_id(document, destination=False),
                "El pago no tiene una cuenta bancaria de origen configurada.",
            )
            entries.extend(
                _normal_entries_for_amount(
                    context=context,
                    debit_account_id=payable_account_id,
                    credit_account_id=bank_account_id,
                    amount=amount,
                    party_type="supplier",
                    party_id=document.party_id,
                    debit_remarks="Pago a proveedor" if party_account_id else "Anticipo a proveedor",
                    credit_remarks="Cuenta bancaria de pago",
                )
            )
        elif payment_type == "receive":
            defaults = _company_defaults(company)
            party_account_id = _resolve_party_account_id(document.party_id, company, receivable=True)
            account_id = party_account_id or (
                None if _payment_has_references(document.id) else (defaults.customer_advance_account_id if defaults else None)
            )
            receivable_account_id = _require_account(
                account_id,
                "No existe cuenta por cobrar o anticipo configurada para el cliente.",
            )
            bank_account_id = _require_account(
                _resolve_bank_gl_account_id(document, destination=True),
                "El pago no tiene una cuenta bancaria de destino configurada.",
            )
            entries.extend(
                [
                    _create_gl_entry(
                        context=context,
                        account_id=bank_account_id,
                        debit=amount,
                        credit=Decimal("0"),
                        entry_remarks="Cuenta bancaria receptora",
                    ),
                    _create_gl_entry(
                        context=context,
                        account_id=receivable_account_id,
                        debit=Decimal("0"),
                        credit=amount,
                        party_type="customer",
                        party_id=document.party_id,
                        entry_remarks="Cobro de cliente" if party_account_id else "Anticipo de cliente",
                    ),
                ]
            )
        elif payment_type == "internal_transfer":
            from_account_id = _require_account(
                _resolve_bank_gl_account_id(document, destination=False),
                "La transferencia interna requiere cuenta bancaria de origen.",
            )
            to_account_id = _require_account(
                _resolve_bank_gl_account_id(document, destination=True),
                "La transferencia interna requiere cuenta bancaria de destino.",
            )
            entries.extend(
                _normal_entries_for_amount(
                    context=context,
                    debit_account_id=to_account_id,
                    credit_account_id=from_account_id,
                    amount=amount,
                    debit_remarks="Transferencia interna entrada",
                    credit_remarks="Transferencia interna salida",
                )
            )
        else:
            raise PostingError("Tipo de pago no soportado para contabilizacion.")

    return _add_entries(entries)


def _stock_item_for(line: Any) -> Item:
    item = database.session.get(Item, line.item_code)
    if item is None:
        item = database.session.execute(select(Item).filter_by(code=line.item_code)).scalars().first()
    if not item:
        raise PostingError("La linea de inventario referencia un item inexistente.")
    if item.item_type == "service" or not item.is_stock_item:
        raise PostingError("Solo los bienes inventariables pueden generar Stock Ledger.")
    return item


def _line_qty(line: StockEntryItem) -> Decimal:
    from cacao_accounting.inventario.service import InventoryServiceError, convert_item_qty

    item = _stock_item_for(line)
    qty = _decimal_value(line.qty_in_base_uom)
    if qty <= 0:
        try:
            qty = convert_item_qty(line.item_code, _decimal_value(line.qty), line.uom, item.default_uom)
        except InventoryServiceError as exc:
            raise PostingError(str(exc)) from exc
    if qty <= 0:
        raise PostingError("La cantidad de inventario debe ser mayor que cero.")
    line.qty_in_base_uom = qty
    return qty


def _line_rate(line: StockEntryItem) -> Decimal:
    rate = _decimal_value(line.valuation_rate or line.basic_rate)
    if rate <= 0:
        amount = _decimal_value(line.amount)
        qty = _line_qty(line)
        if amount > 0 and qty > 0:
            rate = amount / qty
    if rate <= 0:
        raise PostingError("La linea de inventario requiere tasa de valuacion.")
    return rate


def _line_qty_generic(line: Any) -> Decimal:
    from cacao_accounting.inventario.service import InventoryServiceError, convert_item_qty

    item = _stock_item_for(line)
    qty = _decimal_value(getattr(line, "qty_in_base_uom", None))
    if qty <= 0:
        try:
            qty = convert_item_qty(
                getattr(line, "item_code"),
                _decimal_value(getattr(line, "qty", None)),
                getattr(line, "uom", None) or item.default_uom,
                item.default_uom,
            )
        except InventoryServiceError as exc:
            raise PostingError(str(exc)) from exc
    if qty <= 0:
        raise PostingError("La cantidad de inventario debe ser mayor que cero.")
    if hasattr(line, "qty_in_base_uom"):
        line.qty_in_base_uom = qty
    return qty


def _line_rate_generic(line: Any) -> Decimal:
    rate = _decimal_value(getattr(line, "valuation_rate", None) or getattr(line, "rate", None))
    if rate <= 0:
        amount = _decimal_value(getattr(line, "amount", None))
        qty = _line_qty_generic(line)
        if amount > 0 and qty > 0:
            rate = amount / qty
    if rate <= 0:
        raise PostingError("La linea de inventario requiere tasa de valuacion.")
    return rate


def _stock_qty_after(company: str, item_code: str, warehouse: str, qty_change: Decimal) -> Decimal:
    current = database.session.execute(
        select(func.coalesce(func.sum(StockLedgerEntry.qty_change), 0)).filter_by(
            company=company, item_code=item_code, warehouse=warehouse, is_cancelled=False
        )
    ).scalar_one()
    return _decimal_value(current) + qty_change


def _valuation_method_for_item(item_code: str) -> str:
    item = database.session.get(Item, item_code)
    if item is None:
        item = database.session.execute(select(Item).filter_by(code=item_code)).scalars().first()
    if not item:
        raise PostingError("El item de inventario no existe.")
    return (getattr(item, "valuation_method", None) or "fifo").lower()


def _valuation_queue(company: str, item_code: str, warehouse: str) -> list[tuple[Decimal, Decimal]]:
    layers = (
        database.session.execute(
            select(StockValuationLayer)
            .filter_by(company=company, item_code=item_code, warehouse=warehouse)
            .order_by(StockValuationLayer.posting_date, StockValuationLayer.id)
        )
        .scalars()
        .all()
    )
    queue: list[tuple[Decimal, Decimal]] = []
    for layer in layers:
        qty = _decimal_value(layer.qty)
        rate = _decimal_value(layer.rate)
        if qty > 0:
            queue.append((qty, rate))
            continue
        if qty < 0:
            remaining = abs(qty)
            while remaining > 0 and queue:
                available_qty, available_rate = queue[0]
                consumed_qty = min(available_qty, remaining)
                remaining -= consumed_qty
                available_qty -= consumed_qty
                if available_qty > 0:
                    queue[0] = (available_qty, available_rate)
                else:
                    queue.pop(0)
            if remaining > 0:
                raise PostingError("El registro de valuacion de inventario esta inconsistente.")
    return [(qty, rate) for qty, rate in queue if qty > 0]


def _consume_stock_valuation_layers(
    company: str, item_code: str, warehouse: str, quantity: Decimal
) -> tuple[Decimal, Decimal]:
    if quantity <= 0:
        raise PostingError("La cantidad de consumo debe ser mayor que cero.")
    available = _valuation_queue(company, item_code, warehouse)
    total_available = sum(qty for qty, _ in available)
    if total_available < quantity:
        raise PostingError("No hay suficiente inventario para calcular el costo real.")

    valuation_method = _valuation_method_for_item(item_code)
    if valuation_method == "moving_average":
        total_value = sum((qty * rate for qty, rate in available), Decimal("0"))
        average_rate = total_value / total_available
        return quantity * average_rate, average_rate

    total_cost = Decimal("0")
    remaining = quantity
    queue = list(available)
    while remaining > 0 and queue:
        available_qty, rate = queue[0]
        consume_qty = min(available_qty, remaining)
        total_cost += consume_qty * rate
        remaining -= consume_qty
        available_qty -= consume_qty
        if available_qty > 0:
            queue[0] = (available_qty, rate)
        else:
            queue.pop(0)
    if remaining > 0:
        raise PostingError("No hay suficiente inventario para calcular el costo real.")
    return total_cost, total_cost / quantity


def _company_for(document: Any) -> str:
    company = getattr(document, "company", None) or getattr(document, "entity", None)
    if not company and isinstance(document, BankTransaction):
        company = _bank_transaction_company(document)
    if not company:
        raise PostingError("El documento no tiene compania definida.")
    return str(company)


def _posting_date_for(document: Any) -> Any:
    posting_date = getattr(document, "posting_date", None) or getattr(document, "date", None)
    if not posting_date:
        raise PostingError("El documento no tiene fecha de contabilizacion definida.")
    return posting_date


def _bank_transaction_account_id(document: BankTransaction) -> str:
    bank_account = database.session.get(BankAccount, document.bank_account_id)
    if not bank_account or not bank_account.gl_account_id:
        raise PostingError("La transacción bancaria no tiene una cuenta GL bancaria configurada.")
    return bank_account.gl_account_id


def _bank_transaction_company(document: BankTransaction) -> str:
    bank_account = database.session.get(BankAccount, document.bank_account_id)
    if not bank_account or not bank_account.company:
        raise PostingError("La transacción bancaria no esta asociada a una compañía.")
    return str(bank_account.company)


def _bank_transaction_offset_account_id(document: BankTransaction, credit: bool) -> str:
    company = _bank_transaction_company(document)
    defaults = _company_defaults(company)
    if not defaults:
        raise PostingError("No existe configuración contable predeterminada para la compañía.")
    if credit:
        return _require_account(
            defaults.default_income,
            "No existe cuenta de ingresos configurada para notas bancarias de depósito.",
        )
    return _require_account(
        defaults.default_expense,
        "No existe cuenta de gastos configurada para notas bancarias de retiro.",
    )


def post_bank_transaction(document: BankTransaction, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para una nota bancaria manual."""
    amount = _decimal_value(document.deposit if document.deposit is not None else document.withdrawal)
    if amount <= 0:
        raise PostingError("La nota bancaria no tiene un monto valido.")

    bank_account_id = _bank_transaction_account_id(document)
    credit = document.deposit is not None
    offset_account_id = _bank_transaction_offset_account_id(document, credit=credit)

    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        if credit:
            entries.extend(
                _normal_entries_for_amount(
                    context=context,
                    debit_account_id=bank_account_id,
                    credit_account_id=offset_account_id,
                    amount=amount,
                    debit_remarks="Depósito bancario",
                    credit_remarks="Ingreso bancario",
                )
            )
        else:
            entries.extend(
                _normal_entries_for_amount(
                    context=context,
                    debit_account_id=offset_account_id,
                    credit_account_id=bank_account_id,
                    amount=amount,
                    debit_remarks="Gasto bancario",
                    credit_remarks="Retiro bancario",
                )
            )

    return _add_entries(entries)


def _upsert_stock_bin(
    *,
    company: str,
    item_code: str,
    warehouse: str,
    qty_change: Decimal,
    valuation_rate: Decimal,
    value_change: Decimal,
) -> None:
    bin_row = (
        database.session.execute(select(StockBin).filter_by(company=company, item_code=item_code, warehouse=warehouse))
        .scalars()
        .first()
    )
    if not bin_row:
        bin_row = StockBin(
            company=company, item_code=item_code, warehouse=warehouse, actual_qty=Decimal("0"), stock_value=Decimal("0")
        )
        database.session.add(bin_row)

    bin_row.actual_qty = _decimal_value(bin_row.actual_qty) + qty_change
    bin_row.stock_value = _decimal_value(bin_row.stock_value) + value_change

    if bin_row.actual_qty > 0:
        bin_row.valuation_rate = bin_row.stock_value / bin_row.actual_qty
    else:
        bin_row.valuation_rate = Decimal("0")


def _create_stock_movement(
    *,
    document: Any,
    line: Any,
    warehouse: str | None,
    qty_change: Decimal,
    valuation_rate: Decimal,
    value_change: Decimal,
) -> StockLedgerEntry:
    from cacao_accounting.inventario.service import InventoryServiceError, update_serial_state, validate_batch_serial

    if not warehouse:
        raise PostingError("La linea de inventario requiere almacen.")
    try:
        validate_batch_serial(line, outgoing=qty_change < 0)
    except InventoryServiceError as exc:
        raise PostingError(str(exc)) from exc
    if qty_change < 0:
        cost_amount, cost_rate = _consume_stock_valuation_layers(
            company=document.company,
            item_code=line.item_code,
            warehouse=warehouse,
            quantity=abs(qty_change),
        )
        valuation_rate = cost_rate
        value_change = -cost_amount
        line._inventory_cost_amount = cost_amount
    update_serial_state(line, outgoing=qty_change < 0, warehouse=warehouse)
    qty_after = _stock_qty_after(document.company, line.item_code, warehouse, qty_change)
    _upsert_stock_bin(
        company=document.company,
        item_code=line.item_code,
        warehouse=warehouse,
        qty_change=qty_change,
        valuation_rate=valuation_rate,
        value_change=value_change,
    )
    database.session.add(
        StockValuationLayer(
            item_code=line.item_code,
            warehouse=warehouse,
            company=document.company,
            qty=qty_change,
            rate=valuation_rate,
            stock_value_difference=value_change,
            remaining_qty=max(qty_after, Decimal("0")),
            remaining_stock_value=max(qty_after * valuation_rate, Decimal("0")),
            voucher_type=_get_voucher_type(document),
            voucher_id=_get_voucher_id(document),
            posting_date=document.posting_date,
        )
    )
    return StockLedgerEntry(
        posting_date=document.posting_date,
        item_code=line.item_code,
        warehouse=warehouse,
        company=document.company,
        qty_change=qty_change,
        qty_after_transaction=qty_after,
        valuation_rate=valuation_rate,
        stock_value_difference=value_change,
        stock_value=qty_after * valuation_rate,
        voucher_type=_get_voucher_type(document),
        voucher_id=_get_voucher_id(document),
        batch_id=getattr(line, "batch_id", None),
        serial_no=getattr(line, "serial_no", None),
    )


def _create_stock_ledger(document: StockEntry) -> list[StockLedgerEntry]:
    if _has_stock_ledger_entries(document):
        raise PostingError("Este documento ya tiene movimientos de inventario contabilizados.")

    purpose = getattr(document, "purpose", "").lower()
    items = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=document.id)).scalars().all()
    if not items:
        raise PostingError("La entrada de stock no contiene lineas para contabilizar.")

    movements: list[StockLedgerEntry] = []
    for line in items:
        _stock_item_for(line)
        qty = _line_qty(line)
        valuation_rate = _line_rate(line)
        value = _decimal_value(line.amount) or (qty * valuation_rate)
        if purpose in ("material_receipt", "adjustment_positive"):
            movements.append(
                _create_stock_movement(
                    document=document,
                    line=line,
                    warehouse=line.target_warehouse or document.to_warehouse,
                    qty_change=qty,
                    valuation_rate=valuation_rate,
                    value_change=value,
                )
            )
        elif purpose in ("material_issue", "adjustment_negative"):
            movements.append(
                _create_stock_movement(
                    document=document,
                    line=line,
                    warehouse=line.source_warehouse or document.from_warehouse,
                    qty_change=-qty,
                    valuation_rate=valuation_rate,
                    value_change=-value,
                )
            )
        elif purpose == "material_transfer":
            movements.append(
                _create_stock_movement(
                    document=document,
                    line=line,
                    warehouse=line.source_warehouse or document.from_warehouse,
                    qty_change=-qty,
                    valuation_rate=valuation_rate,
                    value_change=-value,
                )
            )
            movements.append(
                _create_stock_movement(
                    document=document,
                    line=line,
                    warehouse=line.target_warehouse or document.to_warehouse,
                    qty_change=qty,
                    valuation_rate=valuation_rate,
                    value_change=value,
                )
            )
        elif purpose == "stock_reconciliation":
            warehouse = line.target_warehouse or line.source_warehouse or document.to_warehouse or document.from_warehouse
            if not warehouse:
                raise PostingError("La conciliación requiere bodega origen o destino.")
            qty_change = qty if (line.target_warehouse or document.to_warehouse) else -qty
            value_change = value if qty_change >= 0 else -value
            movements.append(
                _create_stock_movement(
                    document=document,
                    line=line,
                    warehouse=warehouse,
                    qty_change=qty_change,
                    valuation_rate=valuation_rate,
                    value_change=value_change,
                )
            )
        else:
            raise PostingError("Proposito de inventario no soportado para Stock Ledger.")

    database.session.add_all(movements)
    return movements


def _document_items(document: Any) -> list[Any]:
    if isinstance(document, PurchaseReceipt):
        return list(
            database.session.execute(select(PurchaseReceiptItem).filter_by(purchase_receipt_id=document.id)).scalars().all()
        )
    if isinstance(document, DeliveryNote):
        return list(database.session.execute(select(DeliveryNoteItem).filter_by(delivery_note_id=document.id)).scalars().all())
    raise PostingError("El documento no contiene lineas de inventario compatibles.")


def _comprobante_lines(document: ComprobanteContable) -> list[ComprobanteContableDetalle]:
    return list(
        database.session.execute(
            select(ComprobanteContableDetalle).filter_by(transaction=JOURNAL_TRANSACTION_TYPE, transaction_id=document.id)
        )
        .scalars()
        .all()
    )


def _create_stock_ledger_for_document(
    document: Any,
    qty_change: Decimal,
    value_change: Decimal,
    warehouse: str | None,
    line: Any,
) -> StockLedgerEntry:
    from cacao_accounting.inventario.service import InventoryServiceError, update_serial_state, validate_batch_serial

    _stock_item_for(line)
    if qty_change < 0:
        if not warehouse:
            raise PostingError("La linea de inventario requiere almacen.")
        try:
            validate_batch_serial(line, outgoing=True)
        except InventoryServiceError as exc:
            raise PostingError(str(exc)) from exc
        cost_amount, cost_rate = _consume_stock_valuation_layers(
            company=document.company,
            item_code=line.item_code,
            warehouse=warehouse,
            quantity=abs(qty_change),
        )
        valuation_rate = cost_rate
        value_change = -cost_amount
        line._inventory_cost_amount = cost_amount
    else:
        if not warehouse:
            raise PostingError("La linea de inventario requiere almacen.")
        try:
            validate_batch_serial(line, outgoing=False)
        except InventoryServiceError as exc:
            raise PostingError(str(exc)) from exc
        valuation_rate = (
            value_change / qty_change
            if qty_change != 0
            else _decimal_value(line.valuation_rate or getattr(line, "rate", None) or 0)
        )

    update_serial_state(line, outgoing=qty_change < 0, warehouse=warehouse)
    qty_after = _stock_qty_after(document.company, line.item_code, warehouse, qty_change)
    _upsert_stock_bin(
        company=document.company,
        item_code=line.item_code,
        warehouse=warehouse,
        qty_change=qty_change,
        valuation_rate=valuation_rate,
        value_change=value_change,
    )
    database.session.add(
        StockValuationLayer(
            item_code=line.item_code,
            warehouse=warehouse,
            company=document.company,
            qty=qty_change,
            rate=valuation_rate,
            stock_value_difference=value_change,
            remaining_qty=max(qty_after, Decimal("0")),
            remaining_stock_value=max(qty_after * valuation_rate, Decimal("0")),
            voucher_type=_get_voucher_type(document),
            voucher_id=_get_voucher_id(document),
            posting_date=document.posting_date,
        )
    )
    return StockLedgerEntry(
        posting_date=document.posting_date,
        item_code=line.item_code,
        warehouse=warehouse,
        company=document.company,
        qty_change=qty_change,
        qty_after_transaction=qty_after,
        valuation_rate=valuation_rate,
        stock_value_difference=value_change,
        stock_value=qty_after * valuation_rate,
        voucher_type=_get_voucher_type(document),
        voucher_id=_get_voucher_id(document),
        batch_id=getattr(line, "batch_id", None),
        serial_no=getattr(line, "serial_no", None),
    )


def _create_stock_ledger_for_document_type(document: Any, sign: Decimal) -> list[StockLedgerEntry]:
    if _has_stock_ledger_entries(document):
        raise PostingError("Este documento ya tiene movimientos de inventario contabilizados.")

    items = _document_items(document)
    if not items:
        raise PostingError("El documento no contiene lineas de inventario para contabilizar.")

    movements: list[StockLedgerEntry] = []
    for line in items:
        qty = _line_qty_generic(line)
        rate = _line_rate_generic(line)
        amount = _decimal_value(getattr(line, "amount", None)) or (qty * rate)
        qty_change = _signed_amount(document, sign * qty)
        value_change = _signed_amount(document, sign * amount)
        warehouse = getattr(line, "warehouse", None)
        if not warehouse:
            raise PostingError("La linea de inventario requiere almacen.")
        movements.append(
            _create_stock_ledger_for_document(
                document=document,
                line=line,
                warehouse=warehouse,
                qty_change=qty_change,
                value_change=value_change,
            )
        )
    database.session.add_all(movements)
    return movements


def _receipt_total(document: PurchaseReceipt) -> Decimal:
    items = _document_items(document)
    total = sum(
        (
            _decimal_value(getattr(item, "amount", None)) or (_line_qty_generic(item) * _line_rate_generic(item))
            for item in items
        ),
        Decimal("0"),
    )
    if total <= 0:
        raise PostingError("La recepción de compra no tiene monto conciliable.")
    return total


def _record_purchase_reconciliation(document: PurchaseInvoice, matched_amount: Decimal) -> None:
    from cacao_accounting.compras.purchase_reconciliation_service import (
        PurchaseReconciliationError,
        get_matching_config,
        reconcile_purchase_invoice,
    )

    _ = matched_amount
    config = get_matching_config(str(document.company))
    if not config.auto_reconcile:
        return

    if getattr(document, "purchase_receipt_id", None):
        purchase_receipt = database.session.get(PurchaseReceipt, document.purchase_receipt_id)
        if not purchase_receipt:
            raise PostingError("La recepción de compra referenciada no existe.")
        if purchase_receipt.company != document.company:
            raise PostingError("La factura de compra y la recepción de compra deben pertenecer a la misma compañía.")
        if getattr(purchase_receipt, "docstatus", 0) != 1:
            raise PostingError("La recepción de compra referenciada debe estar aprobada.")
        if not _has_active_gl_entries(purchase_receipt) or not _has_stock_ledger_entries(purchase_receipt):
            raise PostingError("La recepción de compra referenciada debe estar contabilizada antes de facturarse.")
    elif not getattr(document, "purchase_order_id", None):
        return

    try:
        reconcile_purchase_invoice(document.id)
    except PurchaseReconciliationError as exc:
        raise PostingError(str(exc)) from exc


def _create_stock_reversal(document: Any, movement: StockLedgerEntry) -> StockLedgerEntry:
    qty_change = -_decimal_value(movement.qty_change)
    value_change = -_decimal_value(movement.stock_value_difference)
    valuation_rate = _decimal_value(movement.valuation_rate)
    posting_date = _posting_date_for(document)
    qty_after = _stock_qty_after(movement.company, movement.item_code, movement.warehouse, qty_change)

    _upsert_stock_bin(
        company=movement.company,
        item_code=movement.item_code,
        warehouse=movement.warehouse,
        qty_change=qty_change,
        valuation_rate=valuation_rate,
        value_change=value_change,
    )
    database.session.add(
        StockValuationLayer(
            item_code=movement.item_code,
            warehouse=movement.warehouse,
            company=movement.company,
            qty=qty_change,
            rate=valuation_rate,
            stock_value_difference=value_change,
            remaining_qty=max(qty_after, Decimal("0")),
            remaining_stock_value=max(qty_after * valuation_rate, Decimal("0")),
            voucher_type=movement.voucher_type,
            voucher_id=movement.voucher_id,
            posting_date=posting_date,
        )
    )
    return StockLedgerEntry(
        posting_date=posting_date,
        item_code=movement.item_code,
        warehouse=movement.warehouse,
        company=movement.company,
        qty_change=qty_change,
        qty_after_transaction=qty_after,
        valuation_rate=valuation_rate,
        stock_value_difference=value_change,
        stock_value=qty_after * valuation_rate,
        voucher_type=movement.voucher_type,
        voucher_id=movement.voucher_id,
        batch_id=movement.batch_id,
        serial_no=movement.serial_no,
    )


def post_purchase_receipt(document: PurchaseReceipt, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera Stock Ledger y GL para una recepción de compra aprobada."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una recepción de compra aprobada.")

    company = _company_for(document)
    from cacao_accounting.compras.purchase_reconciliation_service import get_matching_config

    matching_config = get_matching_config(company)
    bridge_account_id = _resolve_item_account_id(None, company, "bridge")
    if matching_config.bridge_account_required:
        bridge_account_id = _require_account(
            bridge_account_id,
            "Falta la cuenta puente configurada para la compañia.",
        )
    movements = _create_stock_ledger_for_document_type(document, Decimal("1"))
    if not movements:
        raise PostingError("No se generaron movimientos de inventario para esta recepción de compra.")

    entries: list[GLEntry] = []
    if bridge_account_id:
        for context in _document_contexts(document, ledger_code=ledger_code):
            for line in _document_items(document):
                qty = _line_qty_generic(line)
                rate = _line_rate_generic(line)
                amount = _decimal_value(getattr(line, "amount", None)) or (qty * rate)
                value = _signed_amount(document, amount)
                inventory_account_id = _require_account(
                    _account_id_for_item(line, company, "inventory"),
                    "Falta la cuenta de inventario para una linea de recepcion de compra.",
                )
                entries.extend(
                    _normal_entries_for_amount(
                        context=context,
                        debit_account_id=inventory_account_id,
                        credit_account_id=bridge_account_id,
                        amount=value,
                        party_type="supplier",
                        party_id=document.supplier_id,
                        debit_remarks="Recepción de compra",
                        credit_remarks="Cuenta puente compras",
                    )
                )
    result = _add_entries(entries)

    from cacao_accounting.compras.purchase_reconciliation_service import EventType, emit_economic_event

    emit_economic_event(
        event_type=EventType.GOODS_RECEIVED,
        company=company,
        document_type="purchase_receipt",
        document_id=document.id,
        payload={"supplier_id": str(document.supplier_id), "posting_date": str(document.posting_date)},
    )

    return result


def post_delivery_note(document: DeliveryNote, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera Stock Ledger y GL para una nota de entrega aprobada."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una nota de entrega aprobada.")

    company = _company_for(document)
    movements = _create_stock_ledger_for_document_type(document, Decimal("-1"))
    if not movements:
        raise PostingError("No se generaron movimientos de inventario para esta nota de entrega.")

    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        for line in _document_items(document):
            qty = _line_qty_generic(line)
            rate = _line_rate_generic(line)
            amount = _decimal_value(getattr(line, "amount", None)) or (qty * rate)
            cost_amount = getattr(line, "_inventory_cost_amount", None)
            value = _signed_amount(document, cost_amount if cost_amount is not None else amount)
            inventory_account_id = _require_account(
                _account_id_for_item(line, company, "inventory"),
                "Falta la cuenta de inventario para una linea de nota de entrega.",
            )
            expense_account_id = _require_account(
                _account_id_for_item(line, company, "cogs"),
                "Falta la cuenta de costo de ventas para una linea de nota de entrega.",
            )
            entries.extend(
                _normal_entries_for_amount(
                    context=context,
                    debit_account_id=expense_account_id,
                    credit_account_id=inventory_account_id,
                    amount=value,
                    debit_remarks="Costo de ventas",
                )
            )
    return _add_entries(entries)


def post_comprobante_contable(document: ComprobanteContable, ledger_code: str | Sequence[str] | None = None) -> list[GLEntry]:
    """Genera GL para un comprobante contable manual."""
    company = _company_for(document)
    lines = _comprobante_lines(document)
    if not lines:
        raise PostingError("El comprobante contable no contiene lineas.")

    entries: list[GLEntry] = []
    is_fy_closing = bool(getattr(document, "is_fiscal_year_closing", False))
    for context in _document_contexts(document, ledger_code=ledger_code):
        for line in lines:
            original_value = _decimal_value(getattr(line, "value", None))
            if original_value == 0:
                raise PostingError("Las lineas del comprobante contable deben tener un valor distinto de cero.")

            account_id = _account_id_for_comprobante_line(line, company)
            company_value = original_value
            if (
                context.transaction_currency
                and context.company_currency
                and context.company_currency != context.transaction_currency
            ):
                if context.exchange_rate is None:
                    context_exchange_rate = _lookup_exchange_rate(
                        context.transaction_currency,
                        context.company_currency,
                        context.posting_date,
                    )
                    context = context.__class__(**{**context.__dict__, "exchange_rate": context_exchange_rate})
                company_value = _to_company_currency(original_value, context.exchange_rate or Decimal("1"))

            if company_value > 0:
                debit = company_value
                credit = Decimal("0")
                debit_in_account_currency = original_value if context.transaction_currency else None
                credit_in_account_currency = None
            else:
                debit = Decimal("0")
                credit = abs(company_value)
                debit_in_account_currency = None
                credit_in_account_currency = abs(original_value) if context.transaction_currency else None

            entries.append(
                _create_gl_entry(
                    context=context,
                    account_id=account_id,
                    debit=debit,
                    credit=credit,
                    debit_in_account_currency=debit_in_account_currency,
                    credit_in_account_currency=credit_in_account_currency,
                    party_type=getattr(line, "third_type", None),
                    party_id=getattr(line, "third_code", None),
                    bank_account_id=getattr(line, "bank_account_id", None),
                    is_advance=bool(getattr(line, "is_advance", False)),
                    cost_center_code=getattr(line, "cost_center", None),
                    unit_code=getattr(line, "unit", None),
                    project_code=getattr(line, "project", None),
                    entry_remarks=getattr(line, "memo", None) or getattr(line, "line_memo", None),
                    is_fiscal_year_closing=is_fy_closing,
                )
            )

    total_value = sum((_decimal_value(getattr(line, "value", None)) for line in lines), Decimal("0"))
    if total_value != 0:
        raise PostingError("El comprobante contable no está balanceado.")

    return _add_entries(entries)


def post_stock_entry(document: StockEntry, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera Stock Ledger y GL para movimientos de inventario valuado."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una entrada de stock aprobada.")
    if _has_active_gl_entries(document):
        raise PostingError("Este documento ya tiene entradas GL contabilizadas.")

    movements = _create_stock_ledger(document)
    purpose = getattr(document, "purpose", "").lower()
    if purpose == "material_transfer":
        return []

    company = _company_for(document)
    entries: list[GLEntry] = []
    items = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=document.id)).scalars().all()
    for context in _document_contexts(document, ledger_code=ledger_code):
        for line in items:
            amount = _decimal_value(line.amount) or (_line_qty(line) * _line_rate(line))
            if amount <= 0:
                continue
            inventory_account_id = _require_account(
                _account_id_for_item(line, company, "inventory"),
                "Falta la cuenta de inventario para la linea de stock.",
            )
            offset_type = "bridge" if purpose == "material_receipt" else "inventory_adjustment"
            offset_account_id = _require_account(
                _account_id_for_item(line, company, offset_type),
                "Falta la cuenta de contrapartida para la linea de stock.",
            )
            if purpose in ("material_receipt", "adjustment_positive"):
                entries.extend(
                    _normal_entries_for_amount(
                        context=context,
                        debit_account_id=inventory_account_id,
                        credit_account_id=offset_account_id,
                        amount=amount,
                        debit_remarks="Ingreso de inventario",
                        credit_remarks="Cuenta puente compras",
                    )
                )
            else:
                entries.extend(
                    _normal_entries_for_amount(
                        context=context,
                        debit_account_id=offset_account_id,
                        credit_account_id=inventory_account_id,
                        amount=amount,
                        debit_remarks="Costo de material",
                        credit_remarks="Salida de inventario",
                    )
                )

    _add_entries(entries)
    if not movements and not entries:
        raise PostingError("No se generan movimientos para este documento de inventario.")
    return entries


def post_document_to_gl(document: Any, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera entradas contables para un documento ya aprobado."""
    if not isinstance(document, StockEntry) and _has_active_gl_entries(document):
        raise PostingError("Este documento ya tiene entradas GL contabilizadas.")
    if isinstance(document, SalesInvoice):
        return post_sales_invoice(document, ledger_code=ledger_code)
    if isinstance(document, PurchaseInvoice):
        return post_purchase_invoice(document, ledger_code=ledger_code)
    if isinstance(document, PurchaseReceipt):
        return post_purchase_receipt(document, ledger_code=ledger_code)
    if isinstance(document, DeliveryNote):
        return post_delivery_note(document, ledger_code=ledger_code)
    if isinstance(document, PaymentEntry):
        return post_payment_entry(document, ledger_code=ledger_code)
    if isinstance(document, StockEntry):
        return post_stock_entry(document, ledger_code=ledger_code)
    if isinstance(document, BankTransaction):
        return post_bank_transaction(document, ledger_code=ledger_code)
    if isinstance(document, ComprobanteContable):
        return post_comprobante_contable(document, ledger_code=ledger_code)
    raise PostingError("Tipo de documento no soportado para posting contable.")


def submit_document(document: Any, ledger_code: str | None = None) -> list[GLEntry]:
    """Aprueba y contabiliza un documento operativo de forma idempotente."""
    if getattr(document, "docstatus", 0) != 0:
        raise PostingError("Solo se puede aprobar un documento en borrador.")
    if _has_active_gl_entries(document):
        raise PostingError("Este documento ya tiene entradas GL contabilizadas.")
    document.docstatus = 1
    return post_document_to_gl(document, ledger_code=ledger_code)


def cancel_document(document: Any) -> list[GLEntry]:
    """Cancela un documento aprobado mediante reversos append-only."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede cancelar un documento aprobado.")

    company = _company_for(document)
    try:
        allow_closing = bool(getattr(document, "is_closing", False))
        validate_accounting_period(company, _posting_date_for(document), allow_closing=allow_closing)
    except IdentifierConfigurationError as exc:
        raise PostingError(str(exc)) from exc
    voucher_type = _get_voucher_type(document)
    voucher_id = _get_voucher_id(document)
    original_entries = (
        database.session.execute(
            select(GLEntry).filter_by(
                company=company,
                voucher_type=voucher_type,
                voucher_id=voucher_id,
                is_reversal=False,
                is_cancelled=False,
            )
        )
        .scalars()
        .all()
    )
    if not original_entries and not isinstance(document, StockEntry):
        raise PostingError("El documento no tiene entradas GL para reversar.")

    document.docstatus = 2
    reversals: list[GLEntry] = []
    for entry in original_entries:
        context = LedgerContext(
            company=entry.company,
            posting_date=_posting_date_for(document),
            ledger_id=entry.ledger_id,
            voucher_type=voucher_type,
            voucher_id=voucher_id,
            document_no=getattr(document, "document_no", None),
            naming_series_id=getattr(document, "naming_series_id", None),
            accounting_period_id=entry.accounting_period_id,
            fiscal_year_id=entry.fiscal_year_id,
            transaction_currency=entry.account_currency,
            company_currency=entry.company_currency,
            exchange_rate=entry.exchange_rate,
            document_remarks=getattr(document, "remarks", None),
        )
        reversals.append(
            _create_gl_entry(
                context=context,
                account_id=entry.account_id,
                debit=_decimal_value(entry.credit),
                credit=_decimal_value(entry.debit),
                party_type=entry.party_type,
                party_id=entry.party_id,
                cost_center_code=entry.cost_center_code,
                unit_code=entry.unit_code,
                project_code=entry.project_code,
                entry_remarks="Reversion " + (entry.remarks or ""),
                is_reversal=True,
                reversal_of=entry.id,
                is_fiscal_year_closing=entry.is_fiscal_year_closing,
            )
        )
        entry.is_cancelled = True

    if isinstance(document, (StockEntry, PurchaseReceipt, DeliveryNote)):
        stock_reversals: list[StockLedgerEntry] = []
        original_movements = (
            database.session.execute(
                select(StockLedgerEntry).filter_by(
                    company=company,
                    voucher_type=voucher_type,
                    voucher_id=voucher_id,
                    is_cancelled=False,
                )
            )
            .scalars()
            .all()
        )
        if not original_movements:
            raise PostingError("El documento no tiene movimientos de inventario para reversar.")
        for movement in original_movements:
            stock_reversals.append(_create_stock_reversal(document, movement))
        database.session.add_all(stock_reversals)

    if isinstance(document, PurchaseReceipt):
        from cacao_accounting.compras.purchase_reconciliation_service import emit_goods_received_cancelled

        emit_goods_received_cancelled(voucher_id, company)

    if isinstance(document, PurchaseInvoice) and (
        getattr(document, "purchase_receipt_id", None) or getattr(document, "purchase_order_id", None)
    ):
        from cacao_accounting.compras.purchase_reconciliation_service import cancel_purchase_reconciliation

        cancel_purchase_reconciliation(document.id)

    return _add_entries(reversals)
