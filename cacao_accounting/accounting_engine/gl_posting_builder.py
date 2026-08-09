# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Convert accounting-engine proformas into persisted GL entries."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.accounting_engine.common.context import CalculationContext, JournalEntryProforma
from cacao_accounting.contabilidad.posting import (
    GLEntryParams,
    LedgerContext,
    PostingError,
    _add_entries,
    _create_gl_entry,
    _document_contexts,
    _lookup_exchange_rate,
)
from cacao_accounting.database import (
    BankAccount,
    GLEntry,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    SalesInvoice,
    database,
)


def post_proforma_to_gl(
    *,
    document: Any,
    context: CalculationContext,
    proforma: JournalEntryProforma,
    ledger_code: str | None = None,
) -> list[GLEntry]:
    """Persist a balanced pro-forma as real `GLEntry` rows."""
    if not proforma.lines:
        return []
    if not proforma.is_balanced:
        raise PostingError("El asiento pro-forma no balancea y no puede contabilizarse.")
    entries: list[GLEntry] = []
    for ledger_context in _document_contexts(document, ledger_code=ledger_code):
        ledger_proforma = _proforma_for_ledger(document, context, proforma, ledger_context)
        persistence_context = ledger_context
        if ledger_context.company_currency != context.company_currency:
            persistence_context = replace(ledger_context, document_base_currency=ledger_context.company_currency)
        for line in ledger_proforma.lines:
            account_id = str(line.account_id or "").strip()
            if not account_id:
                raise PostingError("Falta una cuenta contable requerida para contabilizar el asiento.")
            debit = Decimal(line.debit or Decimal("0"))
            credit = Decimal(line.credit or Decimal("0"))
            debit_in_account_currency = line.amount_transaction_currency if debit > 0 else None
            credit_in_account_currency = line.amount_transaction_currency if credit > 0 else None
            entry = _create_gl_entry(
                context=persistence_context,
                params=GLEntryParams(
                    account_id=account_id,
                    debit=debit,
                    credit=credit,
                    debit_in_account_currency=debit_in_account_currency,
                    credit_in_account_currency=credit_in_account_currency,
                    exchange_rate=Decimal(line.exchange_rate_used or Decimal("1")),
                    party_type=context.party_type if line.party_id else None,
                    party_id=line.party_id,
                    bank_account_id=_bank_account_id_for_line(document, account_id),
                    cost_center_code=line.cost_center_id,
                    project_code=line.project_id,
                    entry_remarks=line.description or proforma.memo,
                ),
            )
            if entry.debit == 0 and entry.credit == 0:
                continue
            entries.append(entry)
    return _add_entries(entries)


def _bank_account_id_for_line(document: Any, account_id: str) -> str | None:
    """Return the bank dimension for a payment pro-forma line, when applicable."""
    if not isinstance(document, PaymentEntry):
        return None
    for bank_account_id in (document.bank_account_id, document.target_bank_account_id):
        if not bank_account_id:
            continue
        bank_account = database.session.get(BankAccount, bank_account_id)
        if bank_account and bank_account.gl_account_id == account_id:
            return bank_account.id
    return None


def _proforma_for_ledger(
    document: Any,
    context: CalculationContext,
    proforma: JournalEntryProforma,
    ledger_context: LedgerContext,
) -> JournalEntryProforma:
    """Recalculate a pro-forma when the book uses another currency."""
    ledger_currency = ledger_context.company_currency
    if not ledger_currency or ledger_currency == context.company_currency:
        return proforma
    from cacao_accounting.accounting_engine.orchestrator.event_orchestrator import BusinessEventOrchestrator

    ledger_calculation_context = _calculation_context_for_ledger(document, context, ledger_context)
    result = BusinessEventOrchestrator().handle_event(ledger_calculation_context).get("proforma")
    if not isinstance(result, JournalEntryProforma) or not _is_balanced(result):
        debit = sum((line.debit for line in result.lines), Decimal("0")) if isinstance(result, JournalEntryProforma) else 0
        credit = sum((line.credit for line in result.lines), Decimal("0")) if isinstance(result, JournalEntryProforma) else 0
        raise PostingError(
            f"El asiento pro-forma no balancea en la moneda funcional del libro "
            f"{ledger_currency}: débitos {debit}, créditos {credit}."
        )
    return result


def _is_balanced(proforma: JournalEntryProforma) -> bool:
    """Accept only sub-cent arithmetic noise before GL quantization."""
    debit = sum((line.debit for line in proforma.lines), Decimal("0"))
    credit = sum((line.credit for line in proforma.lines), Decimal("0"))
    return abs(debit - credit) <= Decimal("0.0001")


def _calculation_context_for_ledger(
    document: Any,
    context: CalculationContext,
    ledger_context: LedgerContext,
) -> CalculationContext:
    """Build the calculation context for one book's functional currency."""
    ledger_currency = ledger_context.company_currency or context.company_currency
    transaction_rate = ledger_context.exchange_rate or Decimal("1")
    references = context.references
    if isinstance(document, PaymentEntry):
        open_balance = _payment_open_balance_in_ledger(document, ledger_currency)
        document_total = sum((item.net_amount for item in context.items), Decimal("0"))
        document_rate = open_balance / document_total if open_balance > 0 and document_total > 0 else transaction_rate
        custom_references = {**references.custom_references, "settlement_exchange_rate": transaction_rate}
        references = replace(references, open_balance=open_balance, custom_references=custom_references)
        transaction_rate = document_rate
    return replace(
        context,
        company_currency=ledger_currency,
        exchange_rate=transaction_rate,
        fiscal_exchange_rate=transaction_rate,
        references=references,
    )


def _payment_open_balance_in_ledger(payment: PaymentEntry, ledger_currency: str) -> Decimal:
    """Value referenced invoice balances at their historical rate for a book."""
    references = database.session.execute(select(PaymentReference).filter_by(payment_id=payment.id)).scalars().all()
    fallback_currency = str(payment.base_currency or payment.transaction_currency or ledger_currency)
    valued_balance = sum(
        (_reference_balance_in_ledger(reference, ledger_currency, fallback_currency) for reference in references),
        Decimal("0"),
    )
    if valued_balance > 0:
        return valued_balance
    transaction_amount = Decimal(str(payment.received_amount or payment.paid_amount or 0))
    payment_rate = _lookup_exchange_rate(str(payment.transaction_currency), ledger_currency, payment.posting_date)
    return transaction_amount * payment_rate


def _reference_balance_in_ledger(
    reference: PaymentReference,
    ledger_currency: str,
    fallback_currency: str,
) -> Decimal:
    """Return one referenced invoice balance in the target book currency."""
    reference_type = str(reference.reference_type or "")
    if "invoice" not in reference_type and "credit_note" not in reference_type and "debit_note" not in reference_type:
        return Decimal("0")
    model = PurchaseInvoice if reference_type.startswith("purchase_") else SalesInvoice
    invoice = database.session.get(model, reference.reference_id)
    if invoice is None:
        return Decimal("0")
    balance = Decimal(str(reference.outstanding_amount or reference.total_amount or reference.allocated_amount or 0))
    transaction_currency = str(invoice.transaction_currency or invoice.base_currency or fallback_currency)
    rate = _lookup_exchange_rate(transaction_currency, ledger_currency, invoice.posting_date)
    return balance * rate
