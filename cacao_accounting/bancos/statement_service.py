# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de importacion de extractos y reglas de matching bancario."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from typing import Any

from sqlalchemy import select

from cacao_accounting.bancos.reconciliation_service import BankCandidate, find_bank_reconciliation_candidates
from cacao_accounting.database import (
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    ComprobanteContable,
    ComprobanteContableDetalle,
    CompanyDefaultAccount,
    Reconciliation,
    ReconciliationItem,
    database,
)


class BankStatementError(ValueError):
    """Error controlado de extractos bancarios."""


@dataclass(frozen=True)
class BankImportRow:
    """Fila procesada de extracto bancario."""

    posting_date: date
    reference_number: str | None
    description: str | None
    deposit: Decimal | None
    withdrawal: Decimal | None
    duplicate: bool


@dataclass(frozen=True)
class BankImportResult:
    """Resultado de importacion o preview."""

    rows: list[BankImportRow]
    imported_count: int
    duplicate_count: int


@dataclass(frozen=True)
class BankMatchingRun:
    """Resultado de ejecucion de una regla de matching."""

    rule_id: str
    candidates_by_transaction: dict[str, list[BankCandidate]]


def _decimal_value(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value).replace(",", ""))


def _parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise BankStatementError("La fecha del extracto no tiene un formato soportado.")


def _is_duplicate(
    *,
    bank_account_id: str,
    posting_date: date,
    reference_number: str | None,
    deposit: Decimal | None,
    withdrawal: Decimal | None,
) -> bool:
    query = select(BankTransaction).filter_by(bank_account_id=bank_account_id, posting_date=posting_date)
    if reference_number:
        query = query.filter_by(reference_number=reference_number)
    if deposit is not None:
        query = query.filter_by(deposit=deposit)
    if withdrawal is not None:
        query = query.filter_by(withdrawal=withdrawal)
    return database.session.execute(query).scalars().first() is not None


def import_bank_statement(file: Any, mapping: dict[str, str], bank_account_id: str, preview: bool = False) -> BankImportResult:
    """Importa o previsualiza un extracto CSV."""
    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        raise BankStatementError("La cuenta bancaria no existe.")
    raw = file.read() if hasattr(file, "read") else str(file)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw))
    rows: list[BankImportRow] = []
    imported = 0
    duplicate_count = 0
    for source in reader:
        posting_date = _parse_date(source[mapping["date"]])
        reference_number = source.get(mapping.get("reference", ""), "") or None
        description = source.get(mapping.get("description", ""), "") or None
        deposit_value = _decimal_value(source.get(mapping.get("deposit", ""), ""))
        withdrawal_value = _decimal_value(source.get(mapping.get("withdrawal", ""), ""))
        deposit = deposit_value if deposit_value > 0 else None
        withdrawal = withdrawal_value if withdrawal_value > 0 else None
        if not deposit and not withdrawal:
            raise BankStatementError("Cada fila debe tener deposito o retiro.")
        duplicate = _is_duplicate(
            bank_account_id=bank_account_id,
            posting_date=posting_date,
            reference_number=reference_number,
            deposit=deposit,
            withdrawal=withdrawal,
        )
        if duplicate:
            duplicate_count += 1
        elif not preview:
            database.session.add(
                BankTransaction(
                    bank_account_id=bank_account_id,
                    posting_date=posting_date,
                    reference_number=reference_number,
                    description=description,
                    deposit=deposit,
                    withdrawal=withdrawal,
                )
            )
            imported += 1
        rows.append(BankImportRow(posting_date, reference_number, description, deposit, withdrawal, duplicate))
    return BankImportResult(rows=rows, imported_count=imported, duplicate_count=duplicate_count)


def suggest_bank_matches(bank_transaction_id: str) -> list[BankCandidate]:
    """Alias publico para sugerencias de conciliacion bancaria."""
    return find_bank_reconciliation_candidates(bank_transaction_id)


def apply_bank_matching_rule(rule_id: str, bank_account_id: str, date_range: tuple[date, date]) -> BankMatchingRun:
    """Ejecuta una regla y devuelve candidatos por transaccion."""
    rule = database.session.get(BankMatchingRule, rule_id)
    if not rule or not rule.is_active:
        raise BankStatementError("La regla de matching no existe o esta inactiva.")
    query = (
        select(BankTransaction)
        .filter_by(bank_account_id=bank_account_id, is_reconciled=False)
        .where(BankTransaction.posting_date >= date_range[0])
        .where(BankTransaction.posting_date <= date_range[1])
    )
    if rule.reference_contains:
        query = query.where(BankTransaction.reference_number.contains(rule.reference_contains))
    result: dict[str, list[BankCandidate]] = {}
    for transaction in database.session.execute(query).scalars().all():
        result[transaction.id] = find_bank_reconciliation_candidates(transaction.id)
    return BankMatchingRun(rule_id=rule_id, candidates_by_transaction=result)


def create_bank_difference_journal(
    reconciliation_id: str, amount: Decimal, account_id: str | None = None
) -> ComprobanteContable:
    """Crea un comprobante de ajuste por diferencia bancaria."""
    reconciliation = database.session.get(Reconciliation, reconciliation_id)
    if not reconciliation:
        raise BankStatementError("La conciliacion no existe.")
    defaults = database.session.execute(
        select(CompanyDefaultAccount).filter_by(company=reconciliation.company)
    ).scalar_one_or_none()
    difference_account_id = account_id or (defaults.bank_difference_account_id if defaults else None)
    if not difference_account_id:
        raise BankStatementError("Falta cuenta de diferencia bancaria configurada.")
    reconciliation_item = database.session.execute(
        select(ReconciliationItem).filter_by(reconciliation_id=reconciliation.id, source_type="bank_transaction")
    ).scalar_one_or_none()
    bank_account_id = None
    if reconciliation_item:
        transaction = database.session.get(BankTransaction, reconciliation_item.source_id)
        bank_account = database.session.get(BankAccount, transaction.bank_account_id) if transaction else None
        bank_account_id = bank_account.gl_account_id if bank_account else None
    if not bank_account_id:
        raise BankStatementError("No se encontro cuenta bancaria GL para balancear el ajuste.")
    journal = ComprobanteContable(
        entity=reconciliation.company,
        date=reconciliation.recon_date,
        memo="Ajuste de diferencia bancaria",
    )
    database.session.add(journal)
    database.session.flush()
    debit_account_id = difference_account_id if amount > 0 else bank_account_id
    credit_account_id = bank_account_id if amount > 0 else difference_account_id
    database.session.add_all(
        [
            ComprobanteContableDetalle(
                transaction="journal_entry",
                transaction_id=journal.id,
                account=debit_account_id,
                value=abs(amount),
                memo="Diferencia bancaria",
            ),
            ComprobanteContableDetalle(
                transaction="journal_entry",
                transaction_id=journal.id,
                account=credit_account_id,
                value=-abs(amount),
                memo="Diferencia bancaria",
            ),
        ]
    )
    return journal
