# SPDX-License-Identifier: Apache-2.0
"""Continuous reconciliation between the documentary AR/AP ledger and GL."""

from __future__ import annotations

import logging
import os
import warnings
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable, Literal, Mapping

from flask import current_app, has_app_context
from sqlalchemy import select

from cacao_accounting.database import (
    Accounts,
    ArApReconciliationPolicy,
    ARAPLedgerBookEntry,
    ARAPLedgerEntry,
    Book,
    GLEntry,
    database,
)

ReconciliationMode = Literal["strict", "warn", "log"]
AR_AP_ACCOUNT_TYPES = frozenset({"receivable", "payable", "customer_advance", "supplier_advance"})
EXCHANGE_REVALUATION_VOUCHER_TYPE = "exchange_revaluation"
_LOGGER = logging.getLogger(__name__)


class ARAPGLReconciliationError(ValueError):
    """A strict AR/AP-to-GL reconciliation found one or more differences."""

    def __init__(self, result: "ARAPGLReconciliationResult") -> None:
        """Retain the structured result for callers and audit handlers."""
        self.result = result
        super().__init__(result.message)


@dataclass(frozen=True, order=True)
class ARAPGLReconciliationKey:
    """Dimensions that must agree between the subledger and GL."""

    company: str
    ledger_id: str
    ledger_type: str
    party_type: str
    party_id: str
    currency: str


@dataclass(frozen=True)
class ARAPGLReconciliationLine:
    """One dimensional comparison in the target book currency."""

    key: ARAPGLReconciliationKey
    subledger_amount: Decimal
    gl_amount: Decimal
    difference: Decimal
    tolerance: Decimal

    @property
    def is_balanced(self) -> bool:
        """Return whether the absolute difference is within tolerance."""
        return abs(self.difference) <= self.tolerance


@dataclass(frozen=True)
class ARAPGLReconciliationResult:
    """Structured reconciliation outcome suitable for APIs and transition guards."""

    company: str
    as_of_date: date
    mode: ReconciliationMode
    tolerance: Decimal
    lines: tuple[ARAPGLReconciliationLine, ...]

    @property
    def differences(self) -> tuple[ARAPGLReconciliationLine, ...]:
        """Return only dimensions outside tolerance."""
        return tuple(line for line in self.lines if not line.is_balanced)

    @property
    def is_balanced(self) -> bool:
        """Return whether every dimension agrees."""
        return not self.differences

    @property
    def blocked(self) -> bool:
        """Return whether policy requires the surrounding transaction to fail."""
        return self.mode == "strict" and not self.is_balanced

    @property
    def message(self) -> str:
        """Build a concise diagnostic that identifies every drift dimension."""
        if self.is_balanced:
            return f"AR/AP y GL conciliados para {self.company} al {self.as_of_date}."
        details = "; ".join(
            (
                f"libro={line.key.ledger_id}, tipo={line.key.ledger_type}, tercero={line.key.party_id}, "
                f"moneda={line.key.currency}, diferencia={line.difference}"
            )
            for line in self.differences
        )
        return f"Diferencias AR/AP contra GL para {self.company} al {self.as_of_date}: {details}."


def _decimal(value: object, *, field: str) -> Decimal:
    """Normalize configured and persisted numeric values."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} debe ser un número decimal válido.") from exc
    if not result.is_finite():
        raise ValueError(f"{field} debe ser finito.")
    return result


def resolve_arap_gl_policy(
    *, company: str | None = None, mode: str | None = None, tolerance: Decimal | str | None = None
) -> tuple[ReconciliationMode, Decimal]:
    """Resolve policy from explicit values, company policy, config, or environment."""
    configured_mode = mode
    configured_tolerance: Decimal | str | None = tolerance
    if company and mode is None and tolerance is None and has_app_context():
        persisted = database.session.execute(
            select(ArApReconciliationPolicy).where(
                ArApReconciliationPolicy.company == company,
                ArApReconciliationPolicy.enabled.is_(True),
            )
        ).scalar_one_or_none()
        if persisted is not None:
            configured_mode = str(persisted.mode or "strict")
            configured_tolerance = persisted.tolerance
    if has_app_context():
        configured_mode = configured_mode or current_app.config.get("ARAP_GL_RECONCILIATION_MODE")
        if configured_tolerance is None:
            configured_tolerance = current_app.config.get("ARAP_GL_RECONCILIATION_TOLERANCE")
    configured_mode = configured_mode or os.getenv("ARAP_GL_RECONCILIATION_MODE", "strict")
    if configured_tolerance is None:
        configured_tolerance = os.getenv("ARAP_GL_RECONCILIATION_TOLERANCE", "0.01")
    normalized_mode = str(configured_mode).strip().lower()
    if normalized_mode not in {"strict", "warn", "log"}:
        raise ValueError("La política AR/AP contra GL debe ser strict, warn o log.")
    normalized_tolerance = _decimal(configured_tolerance, field="La tolerancia")
    if normalized_tolerance < 0:
        raise ValueError("La tolerancia no puede ser negativa.")
    return normalized_mode, normalized_tolerance  # type: ignore[return-value]


def compare_arap_gl_totals(
    *,
    company: str,
    as_of_date: date,
    subledger_totals: Mapping[ARAPGLReconciliationKey, Decimal],
    gl_totals: Mapping[ARAPGLReconciliationKey, Decimal],
    mode: ReconciliationMode = "log",
    tolerance: Decimal = Decimal("0.01"),
) -> ARAPGLReconciliationResult:
    """Compare pre-aggregated matrices, retaining zero-sided drift rows."""
    lines = tuple(
        ARAPGLReconciliationLine(
            key=key,
            subledger_amount=_decimal(subledger_totals.get(key, 0), field="Saldo AR/AP"),
            gl_amount=_decimal(gl_totals.get(key, 0), field="Saldo GL"),
            difference=(
                _decimal(subledger_totals.get(key, 0), field="Saldo AR/AP") - _decimal(gl_totals.get(key, 0), field="Saldo GL")
            ),
            tolerance=tolerance,
        )
        for key in sorted(set(subledger_totals) | set(gl_totals))
    )
    return ARAPGLReconciliationResult(company, as_of_date, mode, tolerance, lines)


def _subledger_totals(
    company: str,
    as_of_date: date,
    *,
    party_type: str | None = None,
    party_id: str | None = None,
    ledger_ids: set[str] | None = None,
    currencies: set[str] | None = None,
) -> dict[ARAPGLReconciliationKey, Decimal]:
    """Aggregate book-valued AR/AP evidence by the required matrix."""
    query = (
        select(ARAPLedgerEntry, ARAPLedgerBookEntry)
        .join(ARAPLedgerBookEntry, ARAPLedgerBookEntry.ledger_entry_id == ARAPLedgerEntry.id)
        .where(ARAPLedgerEntry.company == company, ARAPLedgerBookEntry.posting_date <= as_of_date)
    )
    if party_type:
        query = query.where(ARAPLedgerEntry.party_type == party_type)
    if party_id:
        query = query.where(ARAPLedgerEntry.party_id == party_id)
    if ledger_ids:
        query = query.where(ARAPLedgerBookEntry.ledger_id.in_(ledger_ids))
    if currencies:
        query = query.where(ARAPLedgerBookEntry.book_currency.in_(currencies))
    totals: dict[ARAPGLReconciliationKey, Decimal] = {}
    for movement, book_row in database.session.execute(query):
        key = ARAPGLReconciliationKey(
            company=company,
            ledger_id=str(book_row.ledger_id),
            ledger_type=str(movement.ledger_type),
            party_type=str(movement.party_type),
            party_id=str(movement.party_id),
            currency=str(book_row.book_currency),
        )
        totals[key] = totals.get(key, Decimal("0")) + _decimal(book_row.book_amount, field="Saldo AR/AP")
    return totals


def _gl_totals(
    company: str,
    as_of_date: date,
    *,
    party_type: str | None = None,
    party_id: str | None = None,
    ledger_ids: set[str] | None = None,
    currencies: set[str] | None = None,
) -> dict[ARAPGLReconciliationKey, Decimal]:
    """Aggregate control-account GL entries using the subledger sign convention.

    Las revalorizaciones cambiarias no realizada son ajustes de valuacion y no
    eventos documentales AR/AP; no se reflejan en el subledger documental, por
    lo que se excluyen de los totales de las cuentas de control para evitar
    desviaciones espurias en la conciliacion.
    """
    query = (
        select(GLEntry, Accounts, Book)
        .join(Accounts, Accounts.id == GLEntry.account_id)
        .join(Book, Book.id == GLEntry.ledger_id)
        .where(
            GLEntry.company == company,
            GLEntry.posting_date <= as_of_date,
            GLEntry.party_id.is_not(None),
            GLEntry.voucher_type != EXCHANGE_REVALUATION_VOUCHER_TYPE,
        )
    )
    if party_type:
        query = query.where(GLEntry.party_type == party_type)
    if party_id:
        query = query.where(GLEntry.party_id == party_id)
    if ledger_ids:
        query = query.where(GLEntry.ledger_id.in_(ledger_ids))
    if currencies:
        query = query.where(Book.currency.in_(currencies))
    totals: dict[ARAPGLReconciliationKey, Decimal] = {}
    for entry, account, book in database.session.execute(query):
        account_type = str(account.account_type or "").lower()
        if account_type not in AR_AP_ACCOUNT_TYPES:
            continue
        ledger_type = "AR" if account_type in {"receivable", "customer_advance"} else "AP"
        debit = _decimal(entry.debit, field="Débito GL")
        credit = _decimal(entry.credit, field="Crédito GL")
        amount = debit - credit if ledger_type == "AR" else credit - debit
        key = ARAPGLReconciliationKey(
            company=company,
            ledger_id=str(entry.ledger_id),
            ledger_type=ledger_type,
            party_type=str(entry.party_type or ("customer" if ledger_type == "AR" else "supplier")),
            party_id=str(entry.party_id),
            currency=str(book.currency or entry.company_currency or ""),
        )
        totals[key] = totals.get(key, Decimal("0")) + amount
    return totals


def reconcile_arap_to_gl(
    *,
    company: str,
    as_of_date: date,
    mode: str | None = None,
    tolerance: Decimal | str | None = None,
    party_type: str | None = None,
    party_id: str | None = None,
    ledger_ids: Iterable[str] | None = None,
    currencies: Iterable[str] | None = None,
) -> ARAPGLReconciliationResult:
    """Build the company/book/party/currency matrix and enforce its policy."""
    if not company:
        raise ValueError("La compañía es obligatoria para conciliar AR/AP contra GL.")
    resolved_mode, resolved_tolerance = resolve_arap_gl_policy(company=company, mode=mode, tolerance=tolerance)
    database.session.flush()
    normalized_ledger_ids = {str(value) for value in ledger_ids or () if value}
    normalized_currencies = {str(value) for value in currencies or () if value}
    result = compare_arap_gl_totals(
        company=company,
        as_of_date=as_of_date,
        subledger_totals=_subledger_totals(
            company,
            as_of_date,
            party_type=party_type,
            party_id=party_id,
            ledger_ids=normalized_ledger_ids or None,
            currencies=normalized_currencies or None,
        ),
        gl_totals=_gl_totals(
            company,
            as_of_date,
            party_type=party_type,
            party_id=party_id,
            ledger_ids=normalized_ledger_ids or None,
            currencies=normalized_currencies or None,
        ),
        mode=resolved_mode,
        tolerance=resolved_tolerance,
    )
    enforce_arap_gl_policy(result)
    return result


def enforce_arap_gl_policy(result: ARAPGLReconciliationResult) -> None:
    """Block, warn, or log drift without committing the current transaction."""
    if result.is_balanced:
        return
    if result.mode == "strict":
        raise ARAPGLReconciliationError(result)
    if result.mode == "warn":
        warnings.warn(result.message, RuntimeWarning, stacklevel=2)
        return
    _LOGGER.error(result.message)


def reconcile_companies_arap_to_gl(
    companies: Iterable[str], *, as_of_date: date, mode: str | None = None, tolerance: Decimal | str | None = None
) -> tuple[ARAPGLReconciliationResult, ...]:
    """Reconcile multiple companies without hiding which matrix failed."""
    return tuple(
        reconcile_arap_to_gl(company=company, as_of_date=as_of_date, mode=mode, tolerance=tolerance) for company in companies
    )
