# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de contabilizacion para documentos operativos."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

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
    DocumentRelation,
    ExchangeRate,
    GLEntry,
    ImportLandedCost,
    ImportLandedCostItem,
    Item,
    ItemAccount,
    LandedCostAllocation,
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
from cacao_accounting.warehouse_accounting import (
    inventory_account_id_for_document_line,
    warehouse_inventory_account_id,
)
from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_gl_account_usage
from cacao_accounting.document_identifiers import IdentifierConfigurationError, validate_accounting_period
from cacao_accounting.tax_pricing_service import TaxCalculationResult, calculate_taxes

JOURNAL_TRANSACTION_TYPE = "journal_entry"
_ERROR_INVENTARIO_REQUIERE_ALMACEN = "La linea de inventario requiere almacen."
_ERROR_YA_TIENE_ENTRADAS_GL = "Este documento ya tiene entradas GL contabilizadas."
_DOCUMENTO_YA_CONTABILIZADO_MSG = "El documento ya tiene asientos contables activos; no se puede contabilizar dos veces."
_REMARKS_CUENTA_BANCARIA_PAGO = "Cuenta bancaria de pago"


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


@dataclass(frozen=True)
class GLEntryParams:
    """Parametros de una linea contable."""

    account_id: str
    debit: Decimal
    credit: Decimal
    debit_in_account_currency: Decimal | None = None
    credit_in_account_currency: Decimal | None = None
    party_type: str | None = None
    party_id: str | None = None
    bank_account_id: str | None = None
    is_advance: bool = False
    cost_center_code: str | None = None
    unit_code: str | None = None
    project_code: str | None = None
    entry_remarks: str | None = None
    is_reversal: bool = False
    reversal_of: str | None = None
    is_fiscal_year_closing: bool = False


@dataclass(frozen=True)
class EnginePostingResult:
    """Resultado combinado de los motores de calculo y sus entradas GL."""

    entries: list[GLEntry]
    results: dict[str, Any]


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


def _resolve_currency_amount(specific_amount: Decimal | None, fallback_amount: Decimal, use_fallback: bool) -> Decimal | None:
    if specific_amount is not None:
        return specific_amount
    if use_fallback:
        return fallback_amount
    return None


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
    if type(document).__name__ != "ComprobanteContable":
        ledger_code = None
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
            }.get(account_type)
            if mapped:
                return mapped

    defaults = _company_defaults(company)
    if not defaults:
        return None
    return {
        "income": defaults.default_income,
        "expense": defaults.default_expense,
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


def _warehouse_inventory_account_id(document: Any, line: Any, company: str) -> str | None:
    """Resuelve la cuenta de inventario asignada a la bodega de una conciliacion."""
    return inventory_account_id_for_document_line(document, line, company)


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
    params: GLEntryParams,
) -> GLEntry:
    _validate_single_sided_amount(params.debit, params.credit)

    debit = params.debit
    credit = params.credit
    debit_in_ac = params.debit_in_account_currency
    credit_in_ac = params.credit_in_account_currency
    exchange_rate = context.exchange_rate

    if (
        not params.is_reversal
        and context.transaction_currency
        and context.company_currency
        and context.transaction_currency != context.company_currency
        and debit_in_ac is None
        and credit_in_ac is None
    ):
        if exchange_rate is None or exchange_rate == 0:
            try:
                exchange_rate = _lookup_exchange_rate(
                    context.transaction_currency,
                    context.company_currency,
                    context.posting_date,
                )
            except (PostingError, SQLAlchemyError) as exc:
                raise PostingError(f"No se pudo determinar el tipo de cambio para multimoneda: {str(exc)}") from exc

        debit_in_ac = debit
        credit_in_ac = credit
        debit = _to_company_currency(debit, exchange_rate)
        credit = _to_company_currency(credit, exchange_rate)

    resolved_debit_in_ac = _resolve_currency_amount(debit_in_ac, params.debit, bool(context.transaction_currency))
    resolved_credit_in_ac = _resolve_currency_amount(credit_in_ac, params.credit, bool(context.transaction_currency))

    return GLEntry(
        posting_date=context.posting_date,
        company=context.company,
        ledger_id=context.ledger_id,
        account_id=_require_account(params.account_id, "Toda entrada GL requiere cuenta contable."),
        account_code=_account_code_for(params.account_id),
        debit=debit,
        credit=credit,
        debit_in_account_currency=resolved_debit_in_ac,
        credit_in_account_currency=resolved_credit_in_ac,
        account_currency=context.transaction_currency,
        company_currency=context.company_currency,
        exchange_rate=exchange_rate,
        party_type=params.party_type,
        party_id=params.party_id,
        bank_account_id=params.bank_account_id,
        is_advance=params.is_advance,
        is_fiscal_year_closing=params.is_fiscal_year_closing,
        voucher_type=context.voucher_type,
        voucher_id=context.voucher_id,
        document_no=context.document_no,
        naming_series_id=context.naming_series_id,
        fiscal_year_id=context.fiscal_year_id,
        accounting_period_id=context.accounting_period_id,
        cost_center_code=params.cost_center_code,
        unit_code=params.unit_code,
        project_code=params.project_code,
        remarks=params.entry_remarks if params.entry_remarks is not None else context.document_remarks,
        is_reversal=params.is_reversal,
        reversal_of=params.reversal_of,
    )


def _assert_entries_balance(entries: list[GLEntry]) -> None:
    ledger_ids = {entry.ledger_id for entry in entries}
    for ledger_id in ledger_ids:
        ledger_entries = [entry for entry in entries if entry.ledger_id == ledger_id]
        debit_total = sum((_decimal_value(entry.debit) for entry in ledger_entries), Decimal("0"))
        credit_total = sum((_decimal_value(entry.credit) for entry in ledger_entries), Decimal("0"))
        if abs(debit_total - credit_total) > Decimal("0.01"):
            raise PostingError("Las entradas GL generadas no balancean por libro contable.")
        currency_groups: dict[str, list[GLEntry]] = {}
        for entry in ledger_entries:
            curr = getattr(entry, "account_currency", None)
            if curr is not None:
                currency_groups.setdefault(curr, []).append(entry)
        for currency, curr_entries in currency_groups.items():
            curr_debit = sum((_decimal_value(e.debit_in_account_currency) for e in curr_entries), Decimal("0"))
            curr_credit = sum((_decimal_value(e.credit_in_account_currency) for e in curr_entries), Decimal("0"))
            if abs(curr_debit - curr_credit) > Decimal("0.01"):
                raise PostingError("Las entradas GL no balancean en moneda de transaccion ({0}).".format(currency))


def _to_company_currency(amount: Decimal, exchange_rate: Decimal) -> Decimal:
    """Convierte monto a moneda de compania usando ROUND_HALF_EVEN.

    La conversion por linea es simetrica: si linea A tiene +V y linea B
    tiene -V, ambas se redondean con la misma tasa, por lo que la suma
    de debitos siempre iguala la suma de creditos. No se requiere
    tolerancia adicional en la validacion de balance.
    """
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


def _post_with_calculation_engine_payload(document: Any, ledger_code: str | None = None) -> EnginePostingResult | None:
    """Post supported documents through the accounting-engine integration."""
    from cacao_accounting.accounting_engine.document_builders import (
        CalculationContextBuilderError,
        build_calculation_context,
    )
    from cacao_accounting.accounting_engine.gl_posting_builder import post_proforma_to_gl
    from cacao_accounting.accounting_engine.orchestrator.event_orchestrator import BusinessEventOrchestrator

    try:
        context = build_calculation_context(document)
    except CalculationContextBuilderError as exc:
        raise PostingError(str(exc)) from exc
    if context is None:
        return None
    results = BusinessEventOrchestrator().handle_event(context)
    proforma = results.get("proforma")
    if proforma is None:
        return None
    entries = post_proforma_to_gl(document=document, context=context, proforma=proforma, ledger_code=ledger_code)
    return EnginePostingResult(entries=entries, results=results)


def _post_with_calculation_engine(document: Any, ledger_code: str | None = None) -> list[GLEntry] | None:
    """Post supported documents through the accounting-engine integration."""
    payload = _post_with_calculation_engine_payload(document, ledger_code=ledger_code)
    return payload.entries if payload is not None else None


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
    cost_center_code: str | None = None,
    unit_code: str | None = None,
    project_code: str | None = None,
    debit_remarks: str | None = None,
    credit_remarks: str | None = None,
) -> list[GLEntry]:
    if amount > 0:
        return [
            _create_gl_entry(
                context=context,
                params=GLEntryParams(
                    account_id=debit_account_id,
                    debit=amount,
                    credit=Decimal("0"),
                    party_type=party_type,
                    party_id=party_id,
                    cost_center_code=cost_center_code,
                    unit_code=unit_code,
                    project_code=project_code,
                    entry_remarks=debit_remarks,
                ),
            ),
            _create_gl_entry(
                context=context,
                params=GLEntryParams(
                    account_id=credit_account_id,
                    debit=Decimal("0"),
                    credit=amount,
                    cost_center_code=cost_center_code,
                    unit_code=unit_code,
                    project_code=project_code,
                    entry_remarks=credit_remarks,
                ),
            ),
        ]
    if amount < 0:
        reversed_amount = abs(amount)
        return [
            _create_gl_entry(
                context=context,
                params=GLEntryParams(
                    account_id=credit_account_id,
                    debit=reversed_amount,
                    credit=Decimal("0"),
                    cost_center_code=cost_center_code,
                    unit_code=unit_code,
                    project_code=project_code,
                    entry_remarks=credit_remarks,
                ),
            ),
            _create_gl_entry(
                context=context,
                params=GLEntryParams(
                    account_id=debit_account_id,
                    debit=Decimal("0"),
                    credit=reversed_amount,
                    party_type=party_type,
                    party_id=party_id,
                    cost_center_code=cost_center_code,
                    unit_code=unit_code,
                    project_code=project_code,
                    entry_remarks=debit_remarks,
                ),
            ),
        ]
    return []


def _invoice_items_total(items: Sequence[Any], document: Any) -> Decimal:
    total = sum((_decimal_value(getattr(item, "amount", None)) for item in items), Decimal("0"))
    signed_total = _signed_amount(document, total)
    if signed_total == 0:
        raise PostingError("El total del documento es cero y no puede contabilizarse.")
    return signed_total


def _create_receivable_entry(
    *,
    context: LedgerContext,
    receivable_account_id: str,
    amount: Decimal,
    party_id: str,
) -> GLEntry:
    is_receivable = amount > 0
    return _create_gl_entry(
        context=context,
        params=GLEntryParams(
            account_id=receivable_account_id,
            debit=amount if is_receivable else Decimal("0"),
            credit=Decimal("0") if is_receivable else abs(amount),
            party_type="customer",
            party_id=party_id,
            entry_remarks="Cuentas por cobrar",
        ),
    )


def _create_income_entry(
    *,
    context: LedgerContext,
    income_account_id: str,
    amount: Decimal,
    item_name: str | None,
    item_code: str | None,
) -> GLEntry:
    is_income = amount > 0
    return _create_gl_entry(
        context=context,
        params=GLEntryParams(
            account_id=income_account_id,
            debit=Decimal("0") if is_income else abs(amount),
            credit=amount if is_income else Decimal("0"),
            entry_remarks=item_name or item_code,
        ),
    )


def _create_expense_entry(
    *,
    context: LedgerContext,
    expense_account_id: str,
    amount: Decimal,
    item_name: str | None,
    item_code: str | None,
) -> GLEntry:
    is_expense = amount > 0
    return _create_gl_entry(
        context=context,
        params=GLEntryParams(
            account_id=expense_account_id,
            debit=amount if is_expense else Decimal("0"),
            credit=Decimal("0") if is_expense else abs(amount),
            entry_remarks=item_name or item_code,
        ),
    )


def _create_payable_entry(
    *,
    context: LedgerContext,
    payable_account_id: str,
    amount: Decimal,
    party_id: str,
) -> GLEntry:
    is_payable = amount > 0
    return _create_gl_entry(
        context=context,
        params=GLEntryParams(
            account_id=payable_account_id,
            debit=Decimal("0") if is_payable else abs(amount),
            credit=amount if is_payable else Decimal("0"),
            party_type="supplier",
            party_id=party_id,
            entry_remarks="Cuentas por pagar",
        ),
    )


def _tax_result_for_document(document: Any, items: Sequence[Any]) -> TaxCalculationResult | None:
    template_id = getattr(document, "tax_template_id", None)
    if not template_id:
        return None
    setattr(document, "_tax_items", items)
    return calculate_taxes(document, template_id)


def _payment_has_references(payment_id: str) -> bool:
    from cacao_accounting.database import PaymentReference

    return database.session.execute(select(PaymentReference.id).filter_by(payment_id=payment_id)).scalars().first() is not None


def _payment_total_allocated(payment_id: str) -> Decimal:
    """Retorna la suma de allocated_amount de las referencias de un pago."""
    from cacao_accounting.database import PaymentReference

    result = database.session.execute(
        select(func.coalesce(func.sum(PaymentReference.allocated_amount), Decimal("0"))).filter_by(payment_id=payment_id)
    ).scalar()
    return result or Decimal("0")


def _signed_tax_delta(document: Any, tax_result: TaxCalculationResult | None) -> Decimal:
    if tax_result is None:
        return Decimal("0")
    return _signed_amount(document, tax_result.payable_delta)


def _tax_gl_entry_params(account_id: str, amount: Decimal, tax_line: Any, is_deductive: bool) -> GLEntryParams:
    if is_deductive:
        debit = abs(amount) if amount > 0 else Decimal("0")
        credit = abs(amount) if amount < 0 else Decimal("0")
    else:
        debit = abs(amount) if amount < 0 else Decimal("0")
        credit = abs(amount) if amount > 0 else Decimal("0")
    return GLEntryParams(account_id=account_id, debit=debit, credit=credit, entry_remarks=tax_line.name)


def _append_tax_entries(
    *,
    entries: list[GLEntry],
    context: LedgerContext,
    document: Any,
    tax_result: TaxCalculationResult | None,
    default_account_attr: str,
    error_message: str,
) -> None:
    if tax_result is None:
        return
    company = _company_for(document)
    defaults = _company_defaults(company)
    for tax_line in tax_result.lines:
        if tax_line.is_inclusive or tax_line.amount == 0:
            continue
        default_account_id = getattr(defaults, default_account_attr, None) if defaults else None
        account_id = _require_account(
            tax_line.account_id or default_account_id,
            error_message,
        )
        amount = _signed_amount(document, tax_line.amount)
        is_deductive = tax_line.behavior == "deductive"
        tax_params = _tax_gl_entry_params(
            account_id=account_id,
            amount=amount,
            tax_line=tax_line,
            is_deductive=is_deductive,
        )
        entries.append(_create_gl_entry(context=context, params=tax_params))


def _append_sales_tax_entries(
    *,
    entries: list[GLEntry],
    context: LedgerContext,
    document: SalesInvoice,
    tax_result: TaxCalculationResult | None,
) -> None:
    _append_tax_entries(
        entries=entries,
        context=context,
        document=document,
        tax_result=tax_result,
        default_account_attr="default_sales_tax_account_id",
        error_message="Falta la cuenta contable de impuesto de venta.",
    )


def _append_purchase_tax_entries(
    *,
    entries: list[GLEntry],
    context: LedgerContext,
    document: PurchaseInvoice,
    tax_result: TaxCalculationResult | None,
) -> None:
    _append_tax_entries(
        entries=entries,
        context=context,
        document=document,
        tax_result=tax_result,
        default_account_attr="default_purchase_tax_account_id",
        error_message="Falta la cuenta contable de impuesto de compra.",
    )


def post_sales_invoice(document: SalesInvoice, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para una factura o nota de venta aprobada."""
    if _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)
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

    result = _post_with_calculation_engine(document, ledger_code=ledger_code)
    if result is not None:
        _update_grand_total_if_needed(document, items)
        return result

    tax_result = _tax_result_for_document(document, items)
    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        _add_sales_receivable_entry(entries, context, receivable_account_id, document, items, tax_result)
        _add_sales_income_entries(entries, context, company, document, items)
        _append_sales_tax_entries(entries=entries, context=context, document=document, tax_result=tax_result)

    result = _add_entries(entries)
    _update_grand_total_if_needed(document, items)
    return result


def _update_grand_total_if_needed(document: SalesInvoice, items: Sequence[Any]) -> None:
    """Actualiza el grand_total del documento si no esta establecido."""
    if document.grand_total:
        return
    from cacao_accounting.document_flow.service import refresh_outstanding_amount_cache

    tax_result = _tax_result_for_document(document, items)
    document.grand_total = abs(_invoice_items_total(items, document) + _signed_tax_delta(document, tax_result))
    refresh_outstanding_amount_cache(document)


def _add_sales_receivable_entry(
    entries: list[GLEntry],
    context: LedgerContext,
    receivable_account_id: str,
    document: SalesInvoice,
    items: Sequence[Any],
    tax_result: TaxCalculationResult | None,
) -> None:
    """Agrega la entrada de receivable para una factura de venta."""
    amount_total = _invoice_items_total(items, document) + _signed_tax_delta(document, tax_result)
    entries.append(
        _create_receivable_entry(
            context=context,
            receivable_account_id=receivable_account_id,
            amount=amount_total,
            party_id=document.customer_id,
        )
    )


def _add_sales_income_entries(
    entries: list[GLEntry],
    context: LedgerContext,
    company: str,
    document: SalesInvoice,
    items: Sequence[Any],
) -> None:
    """Agrega las entradas de ingreso por cada item de la factura de venta."""
    for item in items:
        amount = _signed_amount(document, _decimal_value(getattr(item, "amount", None)))
        if amount == 0:
            continue
        income_account_id = _require_account(
            _account_id_for_item(item, company, "income"),
            "Falta la cuenta de ingresos para una linea de factura de venta.",
        )
        entries.append(
            _create_income_entry(
                context=context,
                income_account_id=income_account_id,
                amount=amount,
                item_name=getattr(item, "item_name", None),
                item_code=getattr(item, "item_code", None),
            )
        )


def post_purchase_invoice(document: PurchaseInvoice, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para una factura o nota de compra aprobada."""
    if _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)
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

    engine_payload = _post_with_calculation_engine_payload(document, ledger_code=ledger_code)
    if engine_payload is not None:
        result = engine_payload.entries
        _persist_landed_cost_allocations(
            document=document,
            items=items,
            landed_cost_result=engine_payload.results.get("landed_cost"),
        )
    else:
        entries = _create_purchase_invoice_gl_entries(
            document=document,
            company=company,
            payable_account_id=payable_account_id,
            items=items,
            amount_total=amount_total,
            tax_result=tax_result,
            ledger_code=ledger_code,
        )
        result = _add_entries(entries)

    _update_purchase_grand_total(document, amount_total)
    _emit_purchase_invoice_event(document, company)
    return result


def post_import_landed_cost(document: ImportLandedCost, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para un costo de importacion aprobado."""
    if _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar un costo de importacion aprobado.")
    payload = _post_with_calculation_engine_payload(document, ledger_code=ledger_code)
    if payload is None:
        raise PostingError("El motor de calculo no pudo procesar el costo de importacion.")
    items = list(
        database.session.execute(select(ImportLandedCostItem).filter_by(import_landed_cost_id=document.id)).scalars().all()
    )
    _persist_landed_cost_allocations(
        document=document,
        items=items,
        landed_cost_result=payload.results.get("landed_cost"),
    )
    return payload.entries


def _create_purchase_invoice_gl_entries(
    document: PurchaseInvoice,
    company: str,
    payable_account_id: str,
    items: Sequence[Any],
    amount_total: Decimal,
    tax_result: TaxCalculationResult | None,
    ledger_code: str | None,
) -> list[GLEntry]:
    """Crea las entradas GL para una factura de compra sin motor de calculo."""
    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        _add_purchase_expense_entries(entries, context, company, document, items)
        _append_purchase_tax_entries(entries=entries, context=context, document=document, tax_result=tax_result)
        entries.append(
            _create_payable_entry(
                context=context,
                payable_account_id=payable_account_id,
                amount=amount_total,
                party_id=document.supplier_id,
            )
        )
    return entries


def _add_purchase_expense_entries(
    entries: list[GLEntry],
    context: LedgerContext,
    company: str,
    document: PurchaseInvoice,
    items: Sequence[Any],
) -> None:
    """Agrega las entradas de gasto por cada item de la factura de compra."""
    for item in items:
        amount = _signed_amount(document, _decimal_value(getattr(item, "amount", None)))
        if amount == 0:
            continue
        debit_account_type = "bridge" if getattr(document, "purchase_receipt_id", None) else "expense"
        debit_account_id = _require_account(
            _account_id_for_item(item, company, debit_account_type),
            "Falta la cuenta de gasto o cuenta puente para una linea de factura de compra.",
        )
        entries.append(
            _create_expense_entry(
                context=context,
                expense_account_id=debit_account_id,
                amount=amount,
                item_name=getattr(item, "item_name", None),
                item_code=getattr(item, "item_code", None),
            )
        )


def _update_purchase_grand_total(document: PurchaseInvoice, amount_total: Decimal) -> None:
    """Actualiza el grand_total del documento si no esta establecido."""
    from cacao_accounting.document_flow.service import refresh_outstanding_amount_cache

    if not document.grand_total:
        document.grand_total = abs(amount_total)
    refresh_outstanding_amount_cache(document)


def _emit_purchase_invoice_event(document: PurchaseInvoice, company: str) -> None:
    """Emitir el evento economico para factura de compra."""
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


def post_payment_entry(document: PaymentEntry, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera GL para cobros, pagos y transferencias internas."""
    if _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar un pago aprobado.")

    company = _company_for(document)
    amount = _decimal_value(document.paid_amount or document.received_amount)
    if amount <= 0:
        raise PostingError("El monto del pago debe ser mayor que cero.")

    payment_type = getattr(document, "payment_type", "").lower()
    if payment_type in {"pay", "receive"}:
        engine_result = _post_with_calculation_engine(document, ledger_code=ledger_code)
        if engine_result is not None:
            return engine_result
    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        if payment_type == "pay":
            entries.extend(_create_payment_pay_entries(context, document, company, amount))
        elif payment_type == "receive":
            entries.extend(_create_payment_receive_entries(context, document, company, amount))
        elif payment_type == "internal_transfer":
            entries.extend(_create_payment_transfer_entries(context, document, amount))
        elif payment_type == "debit_note":
            entries.extend(_create_bank_debit_note_entries(context, document, company, amount))
        elif payment_type == "credit_note":
            entries.extend(_create_bank_credit_note_entries(context, document, company, amount))
        else:
            raise PostingError("Tipo de pago no soportado para contabilizacion.")

    return _add_entries(entries)


def _create_payment_pay_entries(
    context: LedgerContext,
    document: PaymentEntry,
    company: str,
    amount: Decimal,
) -> list[GLEntry]:
    """Crea entradas GL para pagos a proveedores."""
    defaults = _company_defaults(company)
    party_account_id = _resolve_party_account_id(document.party_id, company, receivable=False)
    advance_account_id = defaults.supplier_advance_account_id if defaults else None
    bank_account_id = _require_account(
        _resolve_bank_gl_account_id(document, destination=False),
        "El pago no tiene una cuenta bancaria de origen configurada.",
    )

    allocated = _payment_total_allocated(document.id) if party_account_id else Decimal("0")

    if party_account_id and allocated > Decimal("0") and amount > allocated:
        entries: list[GLEntry] = []
        entries.extend(
            _normal_entries_for_amount(
                context=context,
                debit_account_id=party_account_id,
                credit_account_id=bank_account_id,
                amount=allocated,
                party_type="supplier",
                party_id=document.party_id,
                debit_remarks="Pago a proveedor",
                credit_remarks=_REMARKS_CUENTA_BANCARIA_PAGO,
            )
        )
        if advance_account_id:
            excess = amount - allocated
            entries.extend(
                _normal_entries_for_amount(
                    context=context,
                    debit_account_id=advance_account_id,
                    credit_account_id=bank_account_id,
                    amount=excess,
                    party_type="supplier",
                    party_id=document.party_id,
                    debit_remarks="Anticipo a proveedor",
                    credit_remarks=_REMARKS_CUENTA_BANCARIA_PAGO,
                )
            )
        return entries

    account_id = party_account_id or (None if _payment_has_references(document.id) else advance_account_id)
    payable_account_id = _require_account(
        account_id,
        "No existe cuenta por pagar o anticipo configurada para el proveedor.",
    )
    return _normal_entries_for_amount(
        context=context,
        debit_account_id=payable_account_id,
        credit_account_id=bank_account_id,
        amount=amount,
        party_type="supplier",
        party_id=document.party_id,
        debit_remarks="Pago a proveedor" if party_account_id else "Anticipo a proveedor",
        credit_remarks="Cuenta bancaria de pago",
    )


def _create_payment_receive_entries(
    context: LedgerContext,
    document: PaymentEntry,
    company: str,
    amount: Decimal,
) -> list[GLEntry]:
    """Crea entradas GL para cobros de clientes."""
    defaults = _company_defaults(company)
    party_account_id = _resolve_party_account_id(document.party_id, company, receivable=True)
    advance_account_id = defaults.customer_advance_account_id if defaults else None
    account_id = party_account_id or (None if _payment_has_references(document.id) else advance_account_id)
    receivable_account_id = _require_account(
        account_id,
        "No existe cuenta por cobrar o anticipo configurada para el cliente.",
    )
    bank_account_id = _require_account(
        _resolve_bank_gl_account_id(document, destination=True),
        "El pago no tiene una cuenta bancaria de destino configurada.",
    )
    return [
        _create_gl_entry(
            context=context,
            params=GLEntryParams(
                account_id=bank_account_id,
                debit=amount,
                credit=Decimal("0"),
                entry_remarks="Cuenta bancaria receptora",
            ),
        ),
        _create_gl_entry(
            context=context,
            params=GLEntryParams(
                account_id=receivable_account_id,
                debit=Decimal("0"),
                credit=amount,
                party_type="customer",
                party_id=document.party_id,
                entry_remarks="Cobro de cliente" if party_account_id else "Anticipo de cliente",
            ),
        ),
    ]


def _create_payment_transfer_entries(
    context: LedgerContext,
    document: PaymentEntry,
    amount: Decimal,
) -> list[GLEntry]:
    """Crea entradas GL para transferencias internas."""
    from_account_id = _require_account(
        _resolve_bank_gl_account_id(document, destination=False),
        "La transferencia interna requiere cuenta bancaria de origen.",
    )
    to_account_id = _require_account(
        _resolve_bank_gl_account_id(document, destination=True),
        "La transferencia interna requiere cuenta bancaria de destino.",
    )
    return _normal_entries_for_amount(
        context=context,
        debit_account_id=to_account_id,
        credit_account_id=from_account_id,
        amount=amount,
        debit_remarks="Transferencia interna entrada",
        credit_remarks="Transferencia interna salida",
    )


def _create_bank_debit_note_entries(
    context: LedgerContext,
    document: PaymentEntry,
    company: str,
    amount: Decimal,
) -> list[GLEntry]:
    """Crea entradas GL para nota de debito bancaria (retiro manual)."""
    defaults = _company_defaults(company)
    bank_account_id = _require_account(
        _resolve_bank_gl_account_id(document, destination=False),
        "La nota de debito bancaria requiere una cuenta bancaria de origen.",
    )
    expense_account_id = _require_account(
        defaults.default_expense if defaults else None,
        "No existe cuenta de gasto predeterminada para la compania.",
    )
    return _normal_entries_for_amount(
        context=context,
        debit_account_id=expense_account_id,
        credit_account_id=bank_account_id,
        amount=amount,
        debit_remarks="Nota de debito bancaria",
        credit_remarks="Retiro bancario",
    )


def _create_bank_credit_note_entries(
    context: LedgerContext,
    document: PaymentEntry,
    company: str,
    amount: Decimal,
) -> list[GLEntry]:
    """Crea entradas GL para nota de credito bancaria (deposito manual)."""
    defaults = _company_defaults(company)
    bank_account_id = _require_account(
        _resolve_bank_gl_account_id(document, destination=True),
        "La nota de credito bancaria requiere una cuenta bancaria de destino.",
    )
    income_account_id = _require_account(
        defaults.default_income if defaults else None,
        "No existe cuenta de ingreso predeterminada para la compania.",
    )
    return _normal_entries_for_amount(
        context=context,
        debit_account_id=bank_account_id,
        credit_account_id=income_account_id,
        amount=amount,
        debit_remarks="Deposito bancario",
        credit_remarks="Nota de credito bancaria",
    )


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
    """Calcula la tasa de valoración para una línea de inventario.

    Incluye item_code en mensajes de error para facilitar la depuración
    cuando hay múltiples líneas de inventario en un documento.
    """
    rate = _decimal_value(line.valuation_rate or line.basic_rate)
    if rate <= 0:
        amount = _decimal_value(line.amount)
        qty = _line_qty(line)
        if amount > 0 and qty > 0:
            rate = amount / qty
    if rate <= 0:
        raise PostingError(f"La linea de inventario {line.item_code} requiere tasa de valuacion.")
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
    """Calcula la tasa de valoración para una línea de inventario (genérica).

    Incluye item_code en mensajes de error para facilitar la depuración
    cuando hay múltiples líneas de inventario en un documento.
    """
    rate = _decimal_value(getattr(line, "valuation_rate", None) or getattr(line, "rate", None))
    if rate <= 0:
        amount = _decimal_value(getattr(line, "amount", None))
        qty = _line_qty_generic(line)
        if amount > 0 and qty > 0:
            rate = amount / qty
    if rate <= 0:
        item_code = getattr(line, "item_code", "desconocido")
        raise PostingError(f"La linea de inventario {item_code} requiere tasa de valuacion.")
    return rate


def _valuation_method_for_company(company_code: str) -> str:
    entity = database.session.get(Entity, company_code)
    if entity is None:
        entity = database.session.execute(select(Entity).filter_by(code=company_code)).scalars().first()
    if not entity:
        raise PostingError("La compañía no existe.")
    return (entity.valuation_method or "moving_average").lower()


def _consume_valuation_layer(queue: list, remaining: Decimal) -> Decimal:
    while remaining > 0 and queue:
        available_qty, available_rate = queue[0]
        consumed_qty = min(available_qty, remaining)
        remaining -= consumed_qty
        available_qty -= consumed_qty
        if available_qty > 0:
            queue[0] = (available_qty, available_rate)
        else:
            queue.pop(0)
    return remaining


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
            remaining = _consume_valuation_layer(queue, abs(qty))
            if remaining > 0:
                raise PostingError("El registro de valuacion de inventario esta inconsistente.")
    return [(qty, rate) for qty, rate in queue if qty > 0]


def _moving_average_valuation(
    available: list[tuple[Decimal, Decimal]], total_available: Decimal, quantity: Decimal
) -> tuple[Decimal, Decimal]:
    total_value = sum((qty * rate for qty, rate in available), Decimal("0"))
    average_rate = total_value / total_available
    return quantity * average_rate, average_rate


def _fifo_valuation(available: list[tuple[Decimal, Decimal]], quantity: Decimal) -> tuple[Decimal, Decimal]:
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


def _consume_stock_valuation_layers(
    company: str, item_code: str, warehouse: str, quantity: Decimal
) -> tuple[Decimal, Decimal]:
    if quantity <= 0:
        raise PostingError(
            f"La cantidad de consumo debe ser mayor que cero para el artículo {item_code} en la bodega {warehouse}."
        )
    available = _valuation_queue(company, item_code, warehouse)
    total_available: Decimal = sum((qty for qty, _ in available), Decimal("0"))
    if total_available < quantity:
        raise PostingError(
            f"No hay suficiente inventario para calcular el costo real para el artículo {item_code} en la bodega {warehouse}."
        )

    valuation_method = _valuation_method_for_company(company)
    if valuation_method == "moving_average":
        return _moving_average_valuation(available, total_available, quantity)

    return _fifo_valuation(available, quantity)


def _consume_available_layers_for_negative_stock(
    company: str, item_code: str, warehouse: str, total_qty: Decimal, fallback_rate: Decimal
) -> Decimal:
    """Consume las capas disponibles para stock negativo, retorna la tasa promedio."""
    available = _valuation_queue(company, item_code, warehouse)
    total_available = sum((qty for qty, _ in available), Decimal("0"))
    if total_available > 0:
        _, avg_rate = _consume_stock_valuation_layers(
            company=company,
            item_code=item_code,
            warehouse=warehouse,
            quantity=total_available,
        )
        return avg_rate
    return fallback_rate


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
    if _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)
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
) -> tuple[Decimal, Decimal]:
    """Actualiza StockBin con FOR UPDATE para evitar condiciones de carrera.

    La validacion de stock negativo (``allow_negative_stock``) se ejecuta
    en los callers **antes** de llamar a esta funcion, no aqui.

    Cuando ``actual_qty`` llega a cero o negativo, ``valuation_rate`` se
    establece en 0 intencionalmente: sin stock no hay tasa de valuacion
    significativa. El ``stock_value`` acumulado se preserva para recalcular
    la tasa cuando el stock vuelva a ser positivo.

    Retorna ``(qty_after, stock_value_after)``.
    """
    # INV-06: Usar SELECT FOR UPDATE para evitar condición de carrera en StockBin
    bin_row = (
        database.session.query(StockBin)
        .with_for_update()
        .filter_by(company=company, item_code=item_code, warehouse=warehouse)
        .first()
    )
    if not bin_row:
        bin_row = StockBin(
            company=company, item_code=item_code, warehouse=warehouse, actual_qty=Decimal("0"), stock_value=Decimal("0")
        )
        database.session.add(bin_row)

    bin_row.actual_qty = _decimal_value(bin_row.actual_qty) + qty_change
    bin_row.stock_value = _decimal_value(bin_row.stock_value) + value_change

    # INV-10: Ajustar reserved_qty para que no supere actual_qty
    if bin_row.reserved_qty and bin_row.reserved_qty > bin_row.actual_qty:
        bin_row.reserved_qty = bin_row.actual_qty

    if bin_row.actual_qty > 0:
        bin_row.valuation_rate = bin_row.stock_value / bin_row.actual_qty
    else:
        bin_row.valuation_rate = Decimal("0")

    return bin_row.actual_qty, bin_row.stock_value


def _has_landed_cost_allocations(document: Any) -> bool:
    """Return whether landed cost allocations were already persisted."""
    return (
        database.session.execute(
            select(LandedCostAllocation.id)
            .filter_by(
                company=_company_for(document),
                document_type=_get_voucher_type(document),
                document_id=_get_voucher_id(document),
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _serializable_cost_details(costs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert landed cost allocation details into JSON-safe values."""
    serialized: list[dict[str, Any]] = []
    for cost in costs:
        serialized.append(
            {key: str(value) if isinstance(value, Decimal) else value for key, value in cost.items() if value is not None}
        )
    return serialized


def _stock_bin_for(company: str, item_code: str, warehouse: str) -> StockBin | None:
    """Fetch the stock bin for an item and warehouse."""
    return (
        database.session.execute(select(StockBin).filter_by(company=company, item_code=item_code, warehouse=warehouse))
        .scalars()
        .first()
    )


def _persist_landed_cost_allocations(
    *,
    document: Any,
    items: Sequence[Any],
    landed_cost_result: Any,
    create_valuation_adjustment: bool = True,
) -> None:
    """Persist landed cost allocations and their inventory valuation effect."""
    if _landed_cost_result_is_invalid(landed_cost_result):
        return
    allocations = list(getattr(landed_cost_result, "allocations", []) or [])
    if not allocations:
        return
    if _has_landed_cost_allocations(document):
        raise PostingError("Este documento ya tiene prorrateos de costos capitalizables contabilizados.")

    items_by_line_id = {str(item.id): item for item in items}
    for allocation in allocations:
        _persist_single_allocation(
            document=document,
            allocation=allocation,
            items_by_line_id=items_by_line_id,
            create_valuation_adjustment=create_valuation_adjustment,
        )


def _landed_cost_result_is_invalid(landed_cost_result: Any) -> bool:
    """Check if landed cost result is None or has errors."""
    return landed_cost_result is None or bool(getattr(landed_cost_result, "errors", None))


def _persist_single_allocation(
    document: Any,
    allocation: Any,
    items_by_line_id: dict[str, Any],
    create_valuation_adjustment: bool,
) -> None:
    """Persist a single landed cost allocation and optionally create valuation layer."""
    allocated_amount = _decimal_value(getattr(allocation, "allocated_total", None))
    if allocated_amount == 0:
        return
    item = items_by_line_id.get(str(allocation.item_line_id))
    if item is None:
        raise PostingError("El prorrateo de costo capitalizable no coincide con una linea de factura.")
    warehouse = getattr(item, "warehouse", None)
    if not warehouse:
        raise PostingError("La linea con costo capitalizable requiere almacen para ajustar valuacion.")

    stock_layer_id = _create_valuation_layer_if_needed(
        document=document,
        item=item,
        warehouse=warehouse,
        allocated_amount=allocated_amount,
        create_valuation_adjustment=create_valuation_adjustment,
    )
    _persist_landed_cost_allocation_record(
        document=document,
        allocation=allocation,
        item=item,
        warehouse=warehouse,
        allocated_amount=allocated_amount,
        stock_layer_id=stock_layer_id,
    )


def _create_valuation_layer_if_needed(
    document: Any,
    item: Any,
    warehouse: str,
    allocated_amount: Decimal,
    create_valuation_adjustment: bool,
) -> Any:
    """Create stock valuation layer if adjustment flag is set."""
    if not create_valuation_adjustment:
        return getattr(item, "_stock_valuation_layer_id", None)

    bin_row = _stock_bin_for(document.company, item.item_code, warehouse)
    if bin_row is None or _decimal_value(bin_row.actual_qty) <= 0:
        raise PostingError("No hay inventario disponible para materializar el costo capitalizable.")

    _upsert_stock_bin(
        company=document.company,
        item_code=item.item_code,
        warehouse=warehouse,
        qty_change=Decimal("0"),
        valuation_rate=_decimal_value(bin_row.valuation_rate),
        value_change=allocated_amount,
    )
    database.session.flush()
    updated_bin = _stock_bin_for(document.company, item.item_code, warehouse)
    if updated_bin is None:
        raise PostingError("No se pudo actualizar la valuacion de inventario.")

    stock_layer = StockValuationLayer(
        item_code=item.item_code,
        warehouse=warehouse,
        company=document.company,
        qty=Decimal("0"),
        rate=_decimal_value(updated_bin.valuation_rate),
        stock_value_difference=allocated_amount,
        remaining_qty=max(_decimal_value(updated_bin.actual_qty), Decimal("0")),
        remaining_stock_value=max(_decimal_value(updated_bin.stock_value), Decimal("0")),
        voucher_type=_get_voucher_type(document),
        voucher_id=_get_voucher_id(document),
        posting_date=document.posting_date,
    )
    database.session.add(stock_layer)
    database.session.flush()
    return stock_layer.id


def _persist_landed_cost_allocation_record(
    document: Any,
    allocation: Any,
    item: Any,
    warehouse: str,
    allocated_amount: Decimal,
    stock_layer_id: Any,
) -> None:
    """Persist the landed cost allocation record."""
    database.session.add(
        LandedCostAllocation(
            company=document.company,
            document_type=_get_voucher_type(document),
            document_id=_get_voucher_id(document),
            document_line_id=str(item.id),
            item_code=item.item_code,
            warehouse=warehouse,
            posting_date=document.posting_date,
            base_amount=_decimal_value(getattr(allocation, "base_amount", None)),
            allocated_amount=allocated_amount,
            final_inventory_cost=_decimal_value(getattr(allocation, "final_inventory_cost", None)),
            unit_inventory_cost=_decimal_value(getattr(allocation, "unit_inventory_cost", None)),
            allocation_method=None,
            allocation_detail_json=json.dumps(
                _serializable_cost_details(list(getattr(allocation, "allocated_costs", []) or [])),
                sort_keys=True,
            ),
            stock_valuation_layer_id=stock_layer_id,
        )
    )


def _create_stock_movement(
    *,
    document: Any,
    line: Any,
    warehouse: str | None,
    qty_change: Decimal,
    valuation_rate: Decimal,
    value_change: Decimal,
    _skip_layer_consumption: bool = False,
) -> StockLedgerEntry:
    from cacao_accounting.inventario.service import InventoryServiceError, update_serial_state, validate_batch_serial

    if not warehouse:
        raise PostingError(_ERROR_INVENTARIO_REQUIERE_ALMACEN)
    try:
        validate_batch_serial(line, outgoing=qty_change < 0)
    except InventoryServiceError as exc:
        raise PostingError(str(exc)) from exc
    # INV-01: Falso positivo - La verificacion de stock negativo (allow_negative_stock)
    # ocurre ANTES de _upsert_stock_bin. Este check protege el consumo de capas FIFO,
    # no la actualizacion de StockBin. Ver docstring de _upsert_stock_bin.
    if qty_change < 0 and not _skip_layer_consumption:
        item = _stock_item_for(line)
        try:
            cost_amount, cost_rate = _consume_stock_valuation_layers(
                company=document.company,
                item_code=line.item_code,
                warehouse=warehouse,
                quantity=abs(qty_change),
            )
            valuation_rate = cost_rate
            value_change = -cost_amount
            line._inventory_cost_amount = cost_amount
        except PostingError:
            if not item.allow_negative_stock:
                raise PostingError(f"El artículo {item.name} no permite stock negativo en la bodega {warehouse}.")
            cost_rate = _consume_available_layers_for_negative_stock(
                company=document.company,
                item_code=line.item_code,
                warehouse=warehouse,
                total_qty=abs(qty_change),
                fallback_rate=_line_rate(line),
            )
            cost_amount = cost_rate * abs(qty_change)
            line._inventory_cost_amount = cost_amount
            valuation_rate = cost_rate
            value_change = -cost_amount
    update_serial_state(line, outgoing=qty_change < 0, warehouse=warehouse)
    qty_after, stock_value_after = _upsert_stock_bin(
        company=document.company,
        item_code=line.item_code,
        warehouse=warehouse,
        qty_change=qty_change,
        valuation_rate=valuation_rate,
        value_change=value_change,
    )
    if qty_after < 0:
        item = _stock_item_for(line)
        if not item.allow_negative_stock:
            raise PostingError(f"El artículo {item.name} no permite stock negativo en la bodega {warehouse}.")
    database.session.add(
        StockValuationLayer(
            item_code=line.item_code,
            warehouse=warehouse,
            company=document.company,
            qty=qty_change,
            rate=valuation_rate,
            stock_value_difference=value_change,
            remaining_qty=max(qty_after, Decimal("0")),
            remaining_stock_value=max(stock_value_after, Decimal("0")),
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
        stock_value=stock_value_after,
        voucher_type=_get_voucher_type(document),
        voucher_id=_get_voucher_id(document),
        batch_id=getattr(line, "batch_id", None),
        serial_no=getattr(line, "serial_no", None),
    )


def _create_stock_reconciliation_movement(document: StockEntry, line: StockEntryItem) -> StockLedgerEntry | None:
    """Crea movimiento de inventario para una conciliacion de cantidad/valor objetivo."""
    warehouse = line.target_warehouse or line.source_warehouse or document.to_warehouse or document.from_warehouse
    if not warehouse:
        raise PostingError("La conciliación requiere bodega.")
    current_qty = _decimal_value(line.current_qty)
    counted_qty = _decimal_value(line.counted_qty)
    qty_change = _decimal_value(line.qty_difference)
    if line.qty_difference is None:
        qty_change = counted_qty - current_qty
    current_value = _decimal_value(line.current_stock_value)
    target_value = _decimal_value(line.target_stock_value)
    value_change = _decimal_value(line.stock_value_difference)
    if line.stock_value_difference is None:
        value_change = target_value - current_value
    if qty_change == 0 and value_change == 0:
        return None
    if counted_qty < 0 or target_value < 0:
        raise PostingError("La conciliacion no permite cantidad o valor objetivo negativo.")
    if current_qty <= 0 and counted_qty <= 0 and value_change != 0:
        raise PostingError("No se puede ajustar valor sin stock positivo o cantidad contada positiva.")

    # INV-25: Consumir capas FIFO en reconciliación de inventario
    if qty_change < 0:
        item = _stock_item_for(line)
        try:
            cost_amount, cost_rate = _consume_stock_valuation_layers(
                company=document.company,
                item_code=line.item_code,
                warehouse=warehouse,
                quantity=abs(qty_change),
            )
            valuation_rate = cost_rate
            value_change = -cost_amount
            line._inventory_cost_amount = cost_amount
        except PostingError:
            if not item.allow_negative_stock:
                raise PostingError(f"El artículo {item.name} no permite stock negativo en la bodega {warehouse}.")
            cost_rate = _consume_available_layers_for_negative_stock(
                company=document.company,
                item_code=line.item_code,
                warehouse=warehouse,
                total_qty=abs(qty_change),
                fallback_rate=target_value / counted_qty if counted_qty > 0 else Decimal("0"),
            )
            cost_amount = cost_rate * abs(qty_change)
            line._inventory_cost_amount = cost_amount
            valuation_rate = cost_rate
            value_change = -cost_amount
    else:
        valuation_rate = target_value / counted_qty if counted_qty > 0 else Decimal("0")
    line.current_qty = current_qty
    line.counted_qty = counted_qty
    line.qty_difference = qty_change
    line.current_stock_value = current_value
    line.target_stock_value = target_value
    line.stock_value_difference = value_change
    line.target_valuation_rate = valuation_rate
    line.valuation_rate = valuation_rate
    line.qty = abs(qty_change)
    line.qty_in_base_uom = abs(qty_change)
    line.amount = abs(value_change)
    qty_after, stock_value_after = _upsert_stock_bin(
        company=document.company,
        item_code=line.item_code,
        warehouse=warehouse,
        qty_change=qty_change,
        valuation_rate=valuation_rate,
        value_change=value_change,
    )
    valuation_rate_after = stock_value_after / qty_after if qty_after > 0 else Decimal("0")
    database.session.add(
        StockValuationLayer(
            item_code=line.item_code,
            warehouse=warehouse,
            company=document.company,
            qty=qty_change,
            rate=valuation_rate_after,
            stock_value_difference=value_change,
            remaining_qty=max(qty_after, Decimal("0")),
            remaining_stock_value=max(stock_value_after, Decimal("0")),
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
        valuation_rate=valuation_rate_after,
        stock_value_difference=value_change,
        stock_value=stock_value_after,
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

    movements = _create_stock_movements_for_items(document, items, purpose)

    if not movements:
        raise PostingError("La conciliacion no contiene diferencias de cantidad o valuacion.")
    database.session.add_all(movements)
    return movements


def _create_stock_movements_for_items(document: StockEntry, items: Sequence[Any], purpose: str) -> list[StockLedgerEntry]:
    """Crea movimientos de inventario para una lista de lineas segun el proposito."""
    movements: list[StockLedgerEntry] = []
    for line in items:
        _stock_item_for(line)
        if purpose == "stock_reconciliation":
            movement = _create_stock_reconciliation_movement(document, line)
            if movement is not None:
                movements.append(movement)
        else:
            line_movements = _create_movement_for_purpose(document, line, purpose)
            movements.extend(line_movements)
    return movements


def _create_movement_for_purpose(document: StockEntry, line: Any, purpose: str) -> list[StockLedgerEntry]:
    """Crea movimientos de inventario para una linea segun el proposito."""
    qty = _line_qty(line)
    valuation_rate = _line_rate(line)
    value = _decimal_value(line.amount) or (qty * valuation_rate)

    if purpose in ("material_receipt", "adjustment_positive"):
        return [
            _create_stock_movement(
                document=document,
                line=line,
                warehouse=line.target_warehouse or document.to_warehouse,
                qty_change=qty,
                valuation_rate=valuation_rate,
                value_change=value,
            )
        ]
    if purpose in ("material_issue", "adjustment_negative"):
        return [
            _create_stock_movement(
                document=document,
                line=line,
                warehouse=line.source_warehouse or document.from_warehouse,
                qty_change=-qty,
                valuation_rate=valuation_rate,
                value_change=-value,
            )
        ]
    if purpose == "material_transfer":
        source_warehouse = line.source_warehouse or document.from_warehouse
        target_warehouse = line.target_warehouse or document.to_warehouse
        cost_amount, cost_rate = _consume_stock_valuation_layers(
            company=document.company,
            item_code=line.item_code,
            warehouse=source_warehouse,
            quantity=qty,
        )
        line._inventory_cost_amount = cost_amount
        return [
            _create_stock_movement(
                document=document,
                line=line,
                warehouse=source_warehouse,
                qty_change=-qty,
                valuation_rate=cost_rate,
                value_change=-cost_amount,
                _skip_layer_consumption=True,
            ),
            _create_stock_movement(
                document=document,
                line=line,
                warehouse=target_warehouse,
                qty_change=qty,
                valuation_rate=cost_rate,
                value_change=cost_amount,
            ),
        ]
    raise PostingError("Proposito de inventario no soportado para Stock Ledger.")


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
            raise PostingError(_ERROR_INVENTARIO_REQUIERE_ALMACEN)
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
            raise PostingError(_ERROR_INVENTARIO_REQUIERE_ALMACEN)
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
    qty_after, stock_value_after = _upsert_stock_bin(
        company=document.company,
        item_code=line.item_code,
        warehouse=warehouse,
        qty_change=qty_change,
        valuation_rate=valuation_rate,
        value_change=value_change,
    )
    stock_layer = StockValuationLayer(
        item_code=line.item_code,
        warehouse=warehouse,
        company=document.company,
        qty=qty_change,
        rate=valuation_rate,
        stock_value_difference=value_change,
        remaining_qty=max(qty_after, Decimal("0")),
        remaining_stock_value=max(stock_value_after, Decimal("0")),
        voucher_type=_get_voucher_type(document),
        voucher_id=_get_voucher_id(document),
        posting_date=document.posting_date,
    )
    database.session.add(stock_layer)
    database.session.flush()
    line._stock_valuation_layer_id = stock_layer.id
    return StockLedgerEntry(
        posting_date=document.posting_date,
        item_code=line.item_code,
        warehouse=warehouse,
        company=document.company,
        qty_change=qty_change,
        qty_after_transaction=qty_after,
        valuation_rate=valuation_rate,
        stock_value_difference=value_change,
        stock_value=stock_value_after,
        voucher_type=_get_voucher_type(document),
        voucher_id=_get_voucher_id(document),
        batch_id=getattr(line, "batch_id", None),
        serial_no=getattr(line, "serial_no", None),
    )


def _allocation_by_line_id(landed_cost_result: Any) -> dict[str, Any]:
    """Index landed cost allocations by document line id."""
    if landed_cost_result is None or getattr(landed_cost_result, "errors", None):
        return {}
    return {str(allocation.item_line_id): allocation for allocation in getattr(landed_cost_result, "allocations", []) or []}


def _create_stock_ledger_for_document_type(
    document: Any,
    sign: Decimal,
    landed_cost_result: Any = None,
) -> list[StockLedgerEntry]:
    if _has_stock_ledger_entries(document):
        raise PostingError("Este documento ya tiene movimientos de inventario contabilizados.")

    items = _document_items(document)
    if not items:
        raise PostingError("El documento no contiene lineas de inventario para contabilizar.")
    document._inventory_posting_items = items

    allocations_by_line_id = _allocation_by_line_id(landed_cost_result)
    movements: list[StockLedgerEntry] = []
    for line in items:
        qty = _line_qty_generic(line)
        rate = _line_rate_generic(line)
        amount = _decimal_value(getattr(line, "amount", None)) or (qty * rate)
        allocation = allocations_by_line_id.get(str(getattr(line, "id", "")))
        if allocation is not None and sign > 0:
            amount = _decimal_value(getattr(allocation, "final_inventory_cost", None))
        qty_change = _signed_amount(document, sign * qty)
        value_change = _signed_amount(document, sign * amount)
        warehouse = getattr(line, "warehouse", None)
        if not warehouse:
            raise PostingError(_ERROR_INVENTARIO_REQUIERE_ALMACEN)
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


def _should_reconcile_purchase_receipt(document: PurchaseInvoice) -> bool:
    """Check if purchase receipt should be reconciled and validate it."""
    purchase_receipt_id = getattr(document, "purchase_receipt_id", None)
    if purchase_receipt_id:
        _validate_purchase_receipt_for_reconciliation(document, purchase_receipt_id)
        return True
    return bool(getattr(document, "purchase_order_id", None))


def _validate_purchase_receipt_for_reconciliation(document: PurchaseInvoice, purchase_receipt_id: str) -> None:
    """Validate purchase receipt exists and is in valid state for reconciliation."""
    purchase_receipt = database.session.get(PurchaseReceipt, purchase_receipt_id)
    if not purchase_receipt:
        raise PostingError("La recepción de compra referenciada no existe.")
    if purchase_receipt.company != document.company:
        raise PostingError("La factura de compra y la recepción de compra deben pertenecer a la misma compañía.")
    if getattr(purchase_receipt, "docstatus", 0) != 1:
        raise PostingError("La recepción de compra referenciada debe estar aprobada.")
    if not _has_active_gl_entries(purchase_receipt) or not _has_stock_ledger_entries(purchase_receipt):
        raise PostingError("La recepción de compra referenciada debe estar contabilizada antes de facturarse.")


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

    if not _should_reconcile_purchase_receipt(document):
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
    qty_after, stock_value_after = _upsert_stock_bin(
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
            remaining_stock_value=max(stock_value_after, Decimal("0")),
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
        stock_value=stock_value_after,
        voucher_type=movement.voucher_type,
        voucher_id=movement.voucher_id,
        batch_id=movement.batch_id,
        serial_no=movement.serial_no,
    )


def _build_purchase_receipt_ledger_entries(document, company, bridge_account_id, ledger_code):

    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        for line in _document_items(document):
            qty = _line_qty_generic(line)
            rate = _line_rate_generic(line)
            amount = _decimal_value(getattr(line, "amount", None)) or (qty * rate)
            value = _signed_amount(document, amount)
            inventory_account_id = _require_account(
                _warehouse_inventory_account_id(document, line, company),
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
    return _add_entries(entries)


def post_purchase_receipt(document: PurchaseReceipt, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera Stock Ledger y GL para una recepción de compra aprobada."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una recepción de compra aprobada.")
    if _has_active_gl_entries(document):
        raise PostingError(_DOCUMENTO_YA_CONTABILIZADO_MSG)

    company = _company_for(document)
    from cacao_accounting.compras.purchase_reconciliation_service import get_matching_config

    matching_config = get_matching_config(company)
    bridge_account_id = _resolve_item_account_id(None, company, "bridge")
    if matching_config.bridge_account_required:
        bridge_account_id = _require_account(
            bridge_account_id,
            "Falta la cuenta puente configurada para lacompañia.",
        )
    engine_payload = _post_with_calculation_engine_payload(document, ledger_code=ledger_code) if bridge_account_id else None
    landed_cost_result = engine_payload.results.get("landed_cost") if engine_payload is not None else None
    movements = _create_stock_ledger_for_document_type(document, Decimal("1"), landed_cost_result=landed_cost_result)
    if not movements:
        raise PostingError("No se generaron movimientos de inventario para esta recepción de compra.")
    if landed_cost_result is not None:
        _persist_landed_cost_allocations(
            document=document,
            items=list(getattr(document, "_inventory_posting_items", []) or _document_items(document)),
            landed_cost_result=landed_cost_result,
            create_valuation_adjustment=False,
        )

    if bridge_account_id and engine_payload is not None:
        result = engine_payload.entries
    elif bridge_account_id:
        result = _build_purchase_receipt_ledger_entries(document, company, bridge_account_id, ledger_code)
    else:
        result = []

    from cacao_accounting.compras.purchase_reconciliation_service import EventType, emit_economic_event

    emit_economic_event(
        event_type=EventType.GOODS_RECEIVED,
        company=company,
        document_type="purchase_receipt",
        document_id=document.id,
        payload={"supplier_id": str(document.supplier_id), "posting_date": str(document.posting_date)},
    )

    return result


def _get_delivery_note_line_value(document: DeliveryNote, line: Any) -> Decimal:
    """Get the value for a delivery note line."""
    qty = _line_qty_generic(line)
    rate = _line_rate_generic(line)
    amount = _decimal_value(getattr(line, "amount", None)) or (qty * rate)
    cost_amount = getattr(line, "_inventory_cost_amount", None)
    return _signed_amount(document, cost_amount if cost_amount is not None else amount)


def _create_delivery_note_gl_entries(
    document: DeliveryNote,
    company: str,
    ledger_code: str | None,
) -> list[GLEntry]:
    """Create GL entries for delivery note."""
    entries: list[GLEntry] = []
    for context in _document_contexts(document, ledger_code=ledger_code):
        for line in _document_items(document):
            value = _get_delivery_note_line_value(document, line)
            inventory_account_id = _require_account(
                _warehouse_inventory_account_id(document, line, company),
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
    return entries


def post_delivery_note(document: DeliveryNote, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera Stock Ledger y GL para una nota de entrega aprobada."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una nota de entrega aprobada.")
    if _has_active_gl_entries(document):
        raise PostingError(_DOCUMENTO_YA_CONTABILIZADO_MSG)

    company = _company_for(document)
    movements = _create_stock_ledger_for_document_type(document, Decimal("-1"))
    if not movements:
        raise PostingError("No se generaron movimientos de inventario para esta nota de entrega.")

    entries = _create_delivery_note_gl_entries(document, company, ledger_code)
    return _add_entries(entries)


def _comprobante_line_value(
    context: LedgerContext,
    original_value: Decimal,
) -> tuple[LedgerContext, Decimal]:
    if not context.transaction_currency or not context.company_currency:
        return context, original_value
    if context.company_currency == context.transaction_currency:
        return context, original_value

    if context.exchange_rate is None:
        exchange_rate = _lookup_exchange_rate(
            context.transaction_currency,
            context.company_currency,
            context.posting_date,
        )
        context = context.__class__(**{**context.__dict__, "exchange_rate": exchange_rate})
    return context, _to_company_currency(original_value, context.exchange_rate or Decimal("1"))


def _comprobante_entry_params(
    context: LedgerContext,
    line: Any,
    account_id: str,
    company_value: Decimal,
    original_value: Decimal,
    is_fy_closing: bool,
) -> GLEntryParams:
    if company_value > 0:
        return GLEntryParams(
            account_id=account_id,
            debit=company_value,
            credit=Decimal("0"),
            debit_in_account_currency=original_value if context.transaction_currency else None,
            credit_in_account_currency=None,
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
    return GLEntryParams(
        account_id=account_id,
        debit=Decimal("0"),
        credit=abs(company_value),
        debit_in_account_currency=None,
        credit_in_account_currency=abs(original_value) if context.transaction_currency else None,
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


def post_comprobante_contable(document: ComprobanteContable, ledger_code: str | Sequence[str] | None = None) -> list[GLEntry]:
    """Genera GL para un comprobante contable manual."""
    if _has_active_gl_entries(document):
        raise PostingError(_DOCUMENTO_YA_CONTABILIZADO_MSG)

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
            context, company_value = _comprobante_line_value(context, original_value)
            params = _comprobante_entry_params(context, line, account_id, company_value, original_value, is_fy_closing)
            entries.append(_create_gl_entry(context=context, params=params))

    total_value = sum((_decimal_value(getattr(line, "value", None)) for line in lines), Decimal("0"))
    if total_value != 0:
        raise PostingError("El comprobante contable no está balanceado.")

    return _add_entries(entries)


def post_stock_entry(document: StockEntry, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera Stock Ledger y GL para movimientos de inventario valuado."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede contabilizar una entrada de stock aprobada.")
    if _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)

    movements = _create_stock_ledger(document)
    purpose = getattr(document, "purpose", "").lower()
    company = _company_for(document)

    # In Material Transfer, we only generate GL if source and target warehouses
    # use different GL accounts. Otherwise, it's just a stock movement.
    if purpose == "material_transfer" and not _is_cross_account_transfer(document, company):
        return []

    entries = _create_stock_entry_gl_entries(document, company, purpose, ledger_code)

    _add_entries(entries)
    if not movements and not entries:
        raise PostingError("No se generan movimientos para este documento de inventario.")
    return entries


def _is_cross_account_transfer(document: StockEntry, company: str) -> bool:
    """Check if any line in a transfer moves goods between warehouses with different GL accounts."""
    if document.purpose != "material_transfer":
        return False
    items = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=document.id)).scalars().all()
    for line in items:
        source_acc = warehouse_inventory_account_id(line.source_warehouse or document.from_warehouse, company)
        target_acc = warehouse_inventory_account_id(line.target_warehouse or document.to_warehouse, company)
        if source_acc and target_acc and source_acc != target_acc:
            return True
    return False


def _create_stock_entry_gl_entries(
    document: StockEntry,
    company: str,
    purpose: str,
    ledger_code: str | None,
) -> list[GLEntry]:
    """Create GL entries for a stock entry document."""
    entries: list[GLEntry] = []
    items = database.session.execute(select(StockEntryItem).filter_by(stock_entry_id=document.id)).scalars().all()
    for context in _document_contexts(document, ledger_code=ledger_code):
        for line in items:
            _add_stock_entry_line_gl_entries(
                entries=entries,
                context=context,
                document=document,
                company=company,
                line=line,
                purpose=purpose,
            )
    return entries


def _add_stock_entry_line_gl_entries(
    entries: list[GLEntry],
    context: LedgerContext,
    document: StockEntry,
    company: str,
    line: StockEntryItem,
    purpose: str,
) -> None:
    """Add GL entries for a single stock entry line."""
    amount = _get_stock_entry_line_amount(line, purpose)
    if amount <= 0:
        return

    dimension_kwargs = _get_dimension_kwargs(document)

    if purpose == "material_transfer":
        source_acc = warehouse_inventory_account_id(line.source_warehouse or document.from_warehouse, company)
        target_acc = warehouse_inventory_account_id(line.target_warehouse or document.to_warehouse, company)
        if source_acc and target_acc and source_acc != target_acc:
            entries.extend(
                _normal_entries_for_amount(
                    context=context,
                    debit_account_id=target_acc,
                    credit_account_id=source_acc,
                    amount=amount,
                    **dimension_kwargs,
                    debit_remarks="Transferencia inventario (Entrada)",
                    credit_remarks="Transferencia inventario (Salida)",
                )
            )
        return

    inventory_account_id = _get_inventory_account_for_line(document, line, company, purpose)
    offset_account_id = _get_offset_account_for_line(document, line, company, purpose)

    if purpose == "stock_reconciliation":
        _add_reconciliation_entries(entries, context, inventory_account_id, offset_account_id, amount, line, dimension_kwargs)
    elif purpose in ("material_receipt", "adjustment_positive"):
        entries.extend(
            _normal_entries_for_amount(
                context=context,
                debit_account_id=inventory_account_id,
                credit_account_id=offset_account_id,
                amount=amount,
                **dimension_kwargs,
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
                **dimension_kwargs,
                debit_remarks="Costo de material",
                credit_remarks="Salida de inventario",
            )
        )


def _get_stock_entry_line_amount(line: StockEntryItem, purpose: str) -> Decimal:
    """Get the amount for a stock entry line based on its purpose."""
    if purpose == "stock_reconciliation":
        return abs(_decimal_value(line.stock_value_difference))

    # Actual stock cost should always take precedence for GL posting to keep it in sync
    # with the Stock Ledger (Kardex), specially for FIFO/Moving Average outflows.
    cost_amount = getattr(line, "_inventory_cost_amount", None)
    if cost_amount is not None:
        return _decimal_value(cost_amount)

    return _decimal_value(line.amount) or (_line_qty(line) * _line_rate(line))


def _get_inventory_account_for_line(document: StockEntry, line: StockEntryItem, company: str, purpose: str) -> str:
    """Get the inventory account for a stock entry line."""
    account = _warehouse_inventory_account_id(document, line, company)
    return _require_account(account, "Falta la cuenta de inventario para la linea de stock.")


def _get_offset_account_for_line(document: StockEntry, line: StockEntryItem, company: str, purpose: str) -> str:
    """Get the offset account for a stock entry line."""
    # INV-04: Recepción manual sin origen documental debe usar cuenta de ajuste
    if purpose == "material_receipt":
        has_source = database.session.execute(
            select(DocumentRelation.id).filter_by(target_type="stock_entry", target_id=document.id, status="active").limit(1)
        ).scalar_one_or_none()
        offset_type = "inventory_adjustment" if not has_source else "bridge"
    else:
        offset_type = "inventory_adjustment"
    if purpose == "stock_reconciliation":
        account = getattr(document, "adjustment_account_id", None)
    else:
        account = _account_id_for_item(line, company, offset_type)
    return _require_account(
        account or _account_id_for_item(line, company, offset_type),
        "Falta la cuenta de contrapartida para la linea de stock.",
    )


def _get_dimension_kwargs(document: StockEntry) -> dict[str, Any]:
    """Get dimension kwargs from document."""
    return {
        "cost_center_code": getattr(document, "cost_center_code", None),
        "unit_code": getattr(document, "unit_code", None),
        "project_code": getattr(document, "project_code", None),
    }


def _add_reconciliation_entries(
    entries: list[GLEntry],
    context: LedgerContext,
    inventory_account_id: str,
    offset_account_id: str,
    amount: Decimal,
    line: StockEntryItem,
    dimension_kwargs: dict[str, Any],
) -> None:
    """Add GL entries for stock reconciliation purpose."""
    value_difference = _decimal_value(line.stock_value_difference)
    if value_difference > 0:
        entries.extend(
            _normal_entries_for_amount(
                context=context,
                debit_account_id=inventory_account_id,
                credit_account_id=offset_account_id,
                amount=amount,
                **dimension_kwargs,
                debit_remarks="Ajuste de valor de inventario",
                credit_remarks="Conciliación de inventario",
            )
        )
    else:
        entries.extend(
            _normal_entries_for_amount(
                context=context,
                debit_account_id=offset_account_id,
                credit_account_id=inventory_account_id,
                amount=amount,
                **dimension_kwargs,
                debit_remarks="Conciliación de inventario",
                credit_remarks="Ajuste de valor de inventario",
            )
        )


def post_document_to_gl(document: Any, ledger_code: str | None = None) -> list[GLEntry]:
    """Genera entradas contables para un documento ya aprobado."""
    if not isinstance(document, StockEntry) and _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)
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
    if isinstance(document, ImportLandedCost):
        return post_import_landed_cost(document, ledger_code=ledger_code)
    raise PostingError("Tipo de documento no soportado para posting contable.")


def submit_document(document: Any, ledger_code: str | None = None) -> list[GLEntry]:
    """Aprueba y contabiliza un documento operativo de forma idempotente.

    Esta funcion es un primitiva de posting: genera GL entries y
    actualiza docstatus. No registra eventos de auditoria.
    ``log_submit()`` / ``log_cancel()`` son llamados por los handlers
    de ruta que invocan esta funcion (ej. ``ventas_entrega_submit``,
    ``bancos_pago_submit``).
    """
    if getattr(document, "docstatus", 0) != 0:
        raise PostingError("Solo se puede aprobar un documento en borrador.")
    if _has_active_gl_entries(document):
        raise PostingError(_ERROR_YA_TIENE_ENTRADAS_GL)
    document.docstatus = 1
    entries = post_document_to_gl(document, ledger_code=ledger_code)
    # QR Validation support
    from cacao_accounting.printing.validation import ValidationService

    ValidationService().update_validation_from_document(document)
    return entries


def cancel_document(document: Any) -> list[GLEntry]:
    """Cancela un documento aprobado mediante reversos append-only."""
    if getattr(document, "docstatus", 0) != 1:
        raise PostingError("Solo se puede cancelar un documento aprobado.")

    if type(document).__name__ == "ComprobanteContable":
        if getattr(document, "voucher_type", None) == "Capitalización Automática de Proyecto":
            raise PostingError("No se puede anular un comprobante de capitalización automática.")
        if getattr(document, "capitalized_by_id", None) is not None:
            raise PostingError(
                "No se puede anular una transacción que ya ha sido capitalizada. Bloquear anular pero permitir revertir."
            )

    company = _company_for(document)
    _validate_cancel_accounting_period(document, company)
    voucher_type = _get_voucher_type(document)
    voucher_id = _get_voucher_id(document)
    original_entries = _get_original_gl_entries(company, voucher_type, voucher_id, document)

    document.docstatus = 2
    _update_validation_service(document)

    reversals = _create_gl_reversals(document, original_entries, voucher_type, voucher_id)

    _cancel_stock_movements_if_needed(document, company, voucher_type, voucher_id)
    _emit_cancel_events(document, voucher_id, company)

    return _add_entries(reversals)


def _validate_cancel_accounting_period(document: Any, company: str) -> None:
    """Valida el periodo contable para cancelacion."""
    try:
        allow_closing = bool(getattr(document, "is_closing", False))
        validate_accounting_period(company, _posting_date_for(document), allow_closing=allow_closing)
    except IdentifierConfigurationError as exc:
        raise PostingError(str(exc)) from exc


def _get_original_gl_entries(company: str, voucher_type: str, voucher_id: str, document: Any) -> list[GLEntry]:
    """Obtiene las entradas GL originales para reversar."""
    original_entries = list(
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
    return original_entries


def _update_validation_service(document: Any) -> None:
    """Actualiza el servicio de validacion QR."""
    from cacao_accounting.printing.validation import ValidationService

    ValidationService().update_validation_from_document(document)


def _create_gl_reversals(
    document: Any,
    original_entries: list[GLEntry],
    voucher_type: str,
    voucher_id: str,
) -> list[GLEntry]:
    """Crea entradas de reversal para las entradas GL originales."""
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
                params=GLEntryParams(
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
                ),
            )
        )
        entry.is_cancelled = True
    return reversals


def _cancel_stock_movements_if_needed(document: Any, company: str, voucher_type: str, voucher_id: str) -> None:
    """Cancela movimientos de inventario si el documento tiene stock."""
    if not isinstance(document, (StockEntry, PurchaseReceipt, DeliveryNote)):
        return

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

    stock_reversals: list[StockLedgerEntry] = []
    for movement in original_movements:
        stock_reversals.append(_create_stock_reversal(document, movement))
        movement.is_cancelled = True
    database.session.add_all(stock_reversals)


def _emit_cancel_events(document: Any, voucher_id: str, company: str) -> None:
    """Emitir eventos de cancelacion especificos por tipo de documento."""
    if isinstance(document, PurchaseReceipt):
        from cacao_accounting.compras.purchase_reconciliation_service import emit_goods_received_cancelled

        emit_goods_received_cancelled(voucher_id, company)

    if isinstance(document, PurchaseInvoice) and (
        getattr(document, "purchase_receipt_id", None) or getattr(document, "purchase_order_id", None)
    ):
        from cacao_accounting.compras.purchase_reconciliation_service import cancel_purchase_reconciliation

        cancel_purchase_reconciliation(document.id)
