# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de conciliacion bancaria contra pagos y GL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select

from cacao_accounting.database import (
    BankAccount,
    BankTransaction,
    GLEntry,
    PaymentEntry,
    Reconciliation,
    ReconciliationItem,
    database,
)


class BankReconciliationError(ValueError):
    """Error controlado de conciliacion bancaria."""


@dataclass(frozen=True)
class BankCandidate:
    """Candidato de conciliacion para una transaccion bancaria."""

    reference_type: str
    reference_id: str
    amount: Decimal
    posting_date: date
    reference_no: str | None
    score: int
    status: str


@dataclass(frozen=True)
class BankReconciliationMatch:
    """Linea solicitada para conciliar banco contra un documento destino."""

    bank_transaction_id: str
    target_type: str
    target_id: str
    allocated_amount: Decimal


@dataclass(frozen=True)
class BankReconciliationRequest:
    """Solicitud de conciliacion bancaria."""

    company: str
    reconciliation_date: date
    matches: list[BankReconciliationMatch]


def _decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _bank_amount(transaction: BankTransaction) -> Decimal:
    return _decimal_value(transaction.deposit if transaction.deposit is not None else transaction.withdrawal)


def _payment_amount(payment: PaymentEntry) -> Decimal:
    return _decimal_value(payment.paid_amount or payment.received_amount)


def _gl_amount(entry: GLEntry) -> Decimal:
    return _decimal_value(entry.debit or entry.credit)


def _bank_company(transaction: BankTransaction) -> str:
    bank_account = database.session.get(BankAccount, transaction.bank_account_id)
    if not bank_account:
        raise BankReconciliationError("La transaccion bancaria no tiene cuenta bancaria valida.")
    return str(bank_account.company)


def _bank_gl_account_id(transaction: BankTransaction) -> str | None:
    bank_account = database.session.get(BankAccount, transaction.bank_account_id)
    return str(bank_account.gl_account_id) if bank_account and bank_account.gl_account_id else None


def _allocated_for_source(bank_transaction_id: str) -> Decimal:
    value = database.session.execute(
        select(func.coalesce(func.sum(ReconciliationItem.allocated_amount), 0)).filter_by(
            source_type="bank_transaction",
            source_id=bank_transaction_id,
        )
    ).scalar_one()
    return _decimal_value(value)


def _allocated_for_target(target_type: str, target_id: str) -> Decimal:
    value = database.session.execute(
        select(func.coalesce(func.sum(ReconciliationItem.allocated_amount), 0)).filter_by(
            target_type=target_type,
            target_id=target_id,
        )
    ).scalar_one()
    return _decimal_value(value)


def _target_amount(target_type: str, target_id: str) -> Decimal:
    if target_type == "payment_entry":
        payment = database.session.get(PaymentEntry, target_id)
        if not payment:
            raise BankReconciliationError("La entrada de pago a conciliar no existe.")
        return _payment_amount(payment)
    if target_type == "gl_entry":
        entry = database.session.get(GLEntry, target_id)
        if not entry:
            raise BankReconciliationError("La entrada GL a conciliar no existe.")
        return _gl_amount(entry)
    raise BankReconciliationError("Tipo de destino no soportado para conciliacion bancaria.")


def _target_company(target_type: str, target_id: str) -> str:
    if target_type == "payment_entry":
        payment = database.session.get(PaymentEntry, target_id)
        if not payment:
            raise BankReconciliationError("La entrada de pago a conciliar no existe.")
        return str(payment.company)
    if target_type == "gl_entry":
        entry = database.session.get(GLEntry, target_id)
        if not entry:
            raise BankReconciliationError("La entrada GL a conciliar no existe.")
        return str(entry.company)
    raise BankReconciliationError("Tipo de destino no soportado para conciliacion bancaria.")


def _candidate_score(
    *,
    bank_transaction: BankTransaction,
    amount: Decimal,
    posting_date: date,
    reference_no: str | None,
) -> int:
    score = 0
    if amount == _bank_amount(bank_transaction):
        score += 60
    if posting_date == bank_transaction.posting_date:
        score += 25
    if reference_no and bank_transaction.reference_number and reference_no == bank_transaction.reference_number:
        score += 15
    return score


def find_bank_reconciliation_candidates(bank_transaction_id: str) -> list[BankCandidate]:
    """Busca pagos y GL bancario candidatos para una transaccion bancaria."""
    transaction = database.session.get(BankTransaction, bank_transaction_id)
    if not transaction:
        raise BankReconciliationError("La transaccion bancaria no existe.")
    company = _bank_company(transaction)
    amount = _bank_amount(transaction)
    if amount <= 0:
        raise BankReconciliationError("La transaccion bancaria no tiene monto conciliable.")

    date_from = transaction.posting_date - timedelta(days=7)
    date_to = transaction.posting_date + timedelta(days=7)
    candidates: list[BankCandidate] = []

    payments = (
        database.session.execute(
            select(PaymentEntry)
            .filter_by(company=company)
            .where(PaymentEntry.posting_date >= date_from)
            .where(PaymentEntry.posting_date <= date_to)
            .where(or_(PaymentEntry.paid_amount <= amount, PaymentEntry.received_amount <= amount))
        )
        .scalars()
        .all()
    )
    for payment in payments:
        payment_amount = _payment_amount(payment)
        pending = payment_amount - _allocated_for_target("payment_entry", payment.id)
        if pending <= 0:
            continue
        candidates.append(
            BankCandidate(
                reference_type="payment_entry",
                reference_id=payment.id,
                amount=min(amount, pending),
                posting_date=payment.posting_date,
                reference_no=payment.reference_no,
                score=_candidate_score(
                    bank_transaction=transaction,
                    amount=payment_amount,
                    posting_date=payment.posting_date,
                    reference_no=payment.reference_no,
                ),
                status="exact" if pending == amount else "partial",
            )
        )

    bank_gl_account_id = _bank_gl_account_id(transaction)
    if bank_gl_account_id:
        gl_entries = (
            database.session.execute(
                select(GLEntry)
                .filter_by(company=company, account_id=bank_gl_account_id, is_cancelled=False)
                .where(GLEntry.posting_date >= date_from)
                .where(GLEntry.posting_date <= date_to)
                .where(or_(GLEntry.debit <= amount, GLEntry.credit <= amount))
            )
            .scalars()
            .all()
        )
        for entry in gl_entries:
            entry_amount = _gl_amount(entry)
            pending = entry_amount - _allocated_for_target("gl_entry", entry.id)
            if pending <= 0:
                continue
            candidates.append(
                BankCandidate(
                    reference_type="gl_entry",
                    reference_id=entry.id,
                    amount=min(amount, pending),
                    posting_date=entry.posting_date,
                    reference_no=entry.document_no,
                    score=_candidate_score(
                        bank_transaction=transaction,
                        amount=entry_amount,
                        posting_date=entry.posting_date,
                        reference_no=entry.document_no,
                    ),
                    status="exact" if pending == amount else "partial",
                )
            )

    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def reconcile_bank_items(request: BankReconciliationRequest) -> Reconciliation:
    """Crea una conciliacion bancaria parcial o total."""
    if not request.matches:
        raise BankReconciliationError("La conciliacion bancaria requiere al menos una linea.")

    reconciliation = Reconciliation(
        company=request.company,
        recon_date=request.reconciliation_date,
        recon_type="bank",
    )
    database.session.add(reconciliation)
    database.session.flush()

    source_totals: dict[str, Decimal] = {}
    target_totals: dict[tuple[str, str], Decimal] = {}
    existing_source_allocations: dict[str, Decimal] = {}
    existing_target_allocations: dict[tuple[str, str], Decimal] = {}
    for match in request.matches:
        if match.allocated_amount <= 0:
            raise BankReconciliationError("El monto conciliado debe ser mayor que cero.")
        transaction = database.session.get(BankTransaction, match.bank_transaction_id)
        if not transaction:
            raise BankReconciliationError("La transaccion bancaria no existe.")
        if _bank_company(transaction) != request.company:
            raise BankReconciliationError("La transaccion bancaria pertenece a otra compania.")
        if _target_company(match.target_type, match.target_id) != request.company:
            raise BankReconciliationError("El documento destino pertenece a otra compania.")

        target_key = (match.target_type, match.target_id)
        existing_source_allocations.setdefault(transaction.id, _allocated_for_source(transaction.id))
        existing_target_allocations.setdefault(target_key, _allocated_for_target(match.target_type, match.target_id))
        source_pending = (
            _bank_amount(transaction)
            - existing_source_allocations[transaction.id]
            - source_totals.get(transaction.id, Decimal("0"))
        )
        target_pending = (
            _target_amount(match.target_type, match.target_id)
            - existing_target_allocations[target_key]
            - target_totals.get(target_key, Decimal("0"))
        )
        if match.allocated_amount > source_pending:
            raise BankReconciliationError("El monto excede el saldo bancario pendiente de conciliar.")
        if match.allocated_amount > target_pending:
            raise BankReconciliationError("El monto excede el saldo pendiente del documento destino.")

        status = "reconciled" if match.allocated_amount == source_pending == target_pending else "partial"
        database.session.add(
            ReconciliationItem(
                reconciliation_id=reconciliation.id,
                reference_type="bank_transaction",
                reference_id=transaction.id,
                amount=match.allocated_amount,
                allocated_amount=match.allocated_amount,
                reconciliation_date=request.reconciliation_date,
                status=status,
                source_type="bank_transaction",
                source_id=transaction.id,
                target_type=match.target_type,
                target_id=match.target_id,
            )
        )
        source_totals[transaction.id] = source_totals.get(transaction.id, Decimal("0")) + match.allocated_amount
        target_totals[target_key] = target_totals.get(target_key, Decimal("0")) + match.allocated_amount

    database.session.flush()
    for bank_transaction_id in source_totals:
        transaction = database.session.get(BankTransaction, bank_transaction_id)
        if transaction and _allocated_for_source(bank_transaction_id) >= _bank_amount(transaction):
            transaction.is_reconciled = True

    return reconciliation
