# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de importacion de extractos y reglas de matching bancario."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

from sqlalchemy import select

from cacao_accounting.audit_trail_service import log_task_event

from cacao_accounting.bancos.reconciliation_service import (
    BankCandidate,
    BankReconciliationMatch,
    BankReconciliationRequest,
    find_bank_reconciliation_candidates,
    reconcile_bank_items,
)
from cacao_accounting.database import (
    Accounts,
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    Book,
    ComprobanteContable,
    ComprobanteContableDetalle,
    CompanyDefaultAccount,
    Entity,
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
    bank_transaction_id: str | None = None


@dataclass(frozen=True)
class BankImportResult:
    """Resultado de importacion o preview."""

    rows: list[BankImportRow]
    imported_count: int
    duplicate_count: int
    auto_reconciled: list[BankAutoReconciliationResult] = field(default_factory=list)


@dataclass(frozen=True)
class BankMatchingRun:
    """Resultado de ejecucion de una regla de matching."""

    rule_id: str
    candidates_by_transaction: dict[str, list[BankCandidate]]


@dataclass(frozen=True)
class BankAutoReconciliationResult:
    """Resultado auditable de una conciliacion automatica de una transaccion bancaria."""

    bank_transaction_id: str
    reconciled: bool
    rule_id: str | None
    candidate_reference_type: str | None
    candidate_reference_id: str | None
    allocated_amount: Decimal | None
    reason: str | None
    reconciliation_id: str | None = None


def _find_auto_reconcile_rules(bank_account_id: str, company: str) -> list[BankMatchingRule]:
    """Devuelve las reglas activas de matching con auto-reconciliacion para una cuenta.

    Una regla aplica cuando su alcance es la cuenta específica (``bank_account_id``)
    o toda la compañía (``bank_account_id IS NULL``).  Se priorizan las
    específicas sobre las globales ordenando por ``priority``.
    """
    query = select(BankMatchingRule).where(
        BankMatchingRule.company == company,
        BankMatchingRule.is_active.is_(True),
        BankMatchingRule.auto_reconcile.is_(True),
        database.or_(
            BankMatchingRule.bank_account_id == bank_account_id,
            BankMatchingRule.bank_account_id.is_(None),
        ),
    )
    rules = database.session.execute(query.order_by(BankMatchingRule.priority)).scalars().all()
    return list(rules)


def auto_reconcile_bank_transaction(bank_transaction_id: str) -> BankAutoReconciliationResult:
    """Intenta conciliar automaticamente una transaccion contra un unico candidato exacto.

    Busca las reglas de matching activas con ``auto_reconcile`` habilitado para la
    cuenta y compañía de la transacción.  Si una regla produce un único candidato
    con estado ``exact`` (importe dentro de la tolerancia y saldo total pendiente
    del destino), aplica la conciliación y devuelve el resultado auditable.

    No se concilia cuando hay más de un candidato exacto (ambigüedad) o cuando
    ninguna regla produce candidatos; en esos casos la conciliación queda a cargo
    manual.
    """
    transaction = database.session.get(BankTransaction, bank_transaction_id)
    if not transaction:
        raise BankStatementError("La transaccion bancaria no existe.")
    if transaction.is_reconciled:
        return BankAutoReconciliationResult(
            bank_transaction_id=bank_transaction_id,
            reconciled=False,
            rule_id=None,
            candidate_reference_type=None,
            candidate_reference_id=None,
            allocated_amount=None,
            reason="already_reconciled",
        )
    bank_account = database.session.get(BankAccount, transaction.bank_account_id)
    if not bank_account:
        raise BankStatementError("La cuenta bancaria no existe.")
    company = str(bank_account.company)

    rules = _find_auto_reconcile_rules(transaction.bank_account_id, company)
    if not rules:
        return BankAutoReconciliationResult(
            bank_transaction_id=bank_transaction_id,
            reconciled=False,
            rule_id=None,
            candidate_reference_type=None,
            candidate_reference_id=None,
            allocated_amount=None,
            reason="no_active_rule",
        )

    seen_candidates: dict[tuple[str, str], BankCandidate] = {}
    best_rule: BankMatchingRule | None = None
    for rule in rules:
        candidates = find_bank_reconciliation_candidates(
            bank_transaction_id,
            days_tolerance=rule.days_tolerance,
            amount_tolerance=rule.amount_tolerance,
        )
        exact_candidates = [candidate for candidate in candidates if candidate.status == "exact"]
        if len(exact_candidates) == 1:
            candidate = exact_candidates[0]
            key = (candidate.reference_type, candidate.reference_id)
            existing = seen_candidates.get(key)
            if existing is None or candidate.score > existing.score:
                seen_candidates[key] = candidate
                best_rule = rule
        elif len(exact_candidates) > 1:
            return BankAutoReconciliationResult(
                bank_transaction_id=bank_transaction_id,
                reconciled=False,
                rule_id=rule.id,
                candidate_reference_type=None,
                candidate_reference_id=None,
                allocated_amount=None,
                reason="ambiguous",
            )

    if not seen_candidates:
        return BankAutoReconciliationResult(
            bank_transaction_id=bank_transaction_id,
            reconciled=False,
            rule_id=None,
            candidate_reference_type=None,
            candidate_reference_id=None,
            allocated_amount=None,
            reason="no_unique_exact_match",
        )

    candidate = max(seen_candidates.values(), key=lambda candidate: candidate.score)
    transaction_amount = Decimal(str(transaction.deposit if transaction.deposit is not None else transaction.withdrawal))
    allocated = min(transaction_amount, candidate.amount)
    reconciliation = reconcile_bank_items(
        BankReconciliationRequest(
            company=company,
            reconciliation_date=transaction.posting_date,
            matches=[
                BankReconciliationMatch(
                    bank_transaction_id=bank_transaction_id,
                    target_type=candidate.reference_type,
                    target_id=candidate.reference_id,
                    allocated_amount=allocated,
                )
            ],
        )
    )
    log_task_event(
        transaction,
        "reconciled",
        "Conciliación automática aplicada por la regla de matching '{0}' contra {1} {2} "
        "por {3} (conciliación {4}).".format(
            best_rule.name if best_rule else "",
            candidate.reference_type,
            candidate.reference_id,
            allocated,
            reconciliation.id,
        ),
    )
    return BankAutoReconciliationResult(
        bank_transaction_id=bank_transaction_id,
        reconciled=True,
        rule_id=best_rule.id if best_rule else None,
        candidate_reference_type=candidate.reference_type,
        candidate_reference_id=candidate.reference_id,
        allocated_amount=allocated,
        reason=None,
        reconciliation_id=reconciliation.id,
    )


def _decimal_value(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    normalized = str(value).strip().replace(" ", "")
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        decimal_part = normalized.rsplit(",", 1)[1]
        if len(decimal_part) > 2:
            raise InvalidOperation("Separador de miles ambiguo")
        normalized = normalized.replace(",", ".")
    elif normalized.count(".") > 1:
        raise InvalidOperation("Separador de miles ambiguo")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise BankStatementError(f"El monto del extracto no es válido: {value}") from exc


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
    query = query.filter_by(reference_number=reference_number)
    if deposit is not None:
        query = query.filter_by(deposit=deposit)
    if withdrawal is not None:
        query = query.filter_by(withdrawal=withdrawal)
    return database.session.execute(query).scalars().first() is not None


def import_bank_statement(
    file: Any,
    mapping: dict[str, str],
    bank_account_id: str,
    *,
    company: str,
    preview: bool = False,
) -> BankImportResult:
    """Importa o previsualiza un extracto CSV validando la compañía de la cuenta.

    Tras persistir las filas (``preview=False``) intenta la conciliación
    automática opcional end-to-end: cada transacción importada se evalúa
    contra las reglas activas con ``auto_reconcile`` habilitado y, cuando
    existe un único candidato exacto dentro de las tolerancias configuradas,
    se aplica la conciliación dejando un resultado auditable en
    ``auto_reconciled``.
    """
    bank_account = database.session.get(BankAccount, bank_account_id)
    if not bank_account:
        raise BankStatementError("La cuenta bancaria no existe.")
    if not company or bank_account.company != company:
        raise BankStatementError("La cuenta bancaria no pertenece a la compañía indicada.")
    raw = file.read() if hasattr(file, "read") else str(file)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw))
    rows: list[BankImportRow] = []
    imported = 0
    duplicate_count = 0
    imported_transaction_ids: list[str] = []
    for source in reader:
        row = _parse_bank_statement_row(source, mapping)
        duplicate = _is_duplicate(
            bank_account_id=bank_account_id,
            posting_date=row.posting_date,
            reference_number=row.reference_number,
            deposit=row.deposit,
            withdrawal=row.withdrawal,
        )
        transaction_id: str | None = None
        if duplicate:
            duplicate_count += 1
        elif not preview:
            persisted = _persist_bank_transaction(bank_account_id=bank_account_id, row=row)
            database.session.flush()
            transaction_id = str(persisted.id)
            imported_transaction_ids.append(transaction_id)
            imported += 1
        rows.append(
            BankImportRow(
                posting_date=row.posting_date,
                reference_number=row.reference_number,
                description=row.description,
                deposit=row.deposit,
                withdrawal=row.withdrawal,
                duplicate=duplicate,
                bank_transaction_id=transaction_id,
            )
        )
    auto_results: list[BankAutoReconciliationResult] = []
    for transaction_id in imported_transaction_ids:
        try:
            # Savepoint: cualquier fallo de conciliación automática no revierte
            # la importación de la fila del extracto.
            with database.session.begin_nested():
                auto_results.append(auto_reconcile_bank_transaction(transaction_id))
        except Exception:  # noqa: BLE001 - la conciliación opcional nunca rompe la importación
            auto_results.append(
                BankAutoReconciliationResult(
                    bank_transaction_id=transaction_id,
                    reconciled=False,
                    rule_id=None,
                    candidate_reference_type=None,
                    candidate_reference_id=None,
                    allocated_amount=None,
                    reason="error",
                )
            )
    return BankImportResult(
        rows=rows,
        imported_count=imported,
        duplicate_count=duplicate_count,
        auto_reconciled=auto_results,
    )


def suggest_bank_matches(bank_transaction_id: str, **kwargs: Any) -> list[BankCandidate]:
    """Alias publico para sugerencias de conciliacion bancaria.

    Acepta los mismos parámetros de tolerancia que
    ``find_bank_reconciliation_candidates`` (``days_tolerance``,
    ``amount_tolerance``) para que las sugerencias respeten la
    configuración de tolerancias cuando se solicita explícitamente.
    """
    return find_bank_reconciliation_candidates(bank_transaction_id, **kwargs)


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
        result[transaction.id] = find_bank_reconciliation_candidates(
            transaction.id,
            days_tolerance=rule.days_tolerance,
            amount_tolerance=rule.amount_tolerance,
        )
    return BankMatchingRun(rule_id=rule_id, candidates_by_transaction=result)


def _parse_bank_statement_row(source: dict[str, str], mapping: dict[str, str]) -> BankImportRow:
    """Normaliza una fila de extracto y valida sus importes mínimos."""
    posting_date = _parse_date(source[mapping["date"]])
    reference_number = source.get(mapping.get("reference", ""), "") or None
    description = source.get(mapping.get("description", ""), "") or None
    deposit_value = _decimal_value(source.get(mapping.get("deposit", ""), ""))
    withdrawal_value = _decimal_value(source.get(mapping.get("withdrawal", ""), ""))
    deposit = deposit_value if deposit_value > 0 else None
    withdrawal = withdrawal_value if withdrawal_value > 0 else None
    if not deposit and not withdrawal:
        raise BankStatementError("Cada fila debe tener deposito o retiro.")
    if deposit and withdrawal:
        raise BankStatementError("Cada fila debe tener deposito o retiro, no ambos.")
    return BankImportRow(posting_date, reference_number, description, deposit, withdrawal, False)


def _persist_bank_transaction(*, bank_account_id: str, row: BankImportRow) -> BankTransaction:
    """Persist a statement row as a bank transaction and return it."""
    transaction = BankTransaction(
        bank_account_id=bank_account_id,
        posting_date=row.posting_date,
        reference_number=row.reference_number,
        description=row.description,
        deposit=row.deposit,
        withdrawal=row.withdrawal,
    )
    database.session.add(transaction)
    return transaction


def create_bank_difference_journal(
    reconciliation_id: str,
    amount: Decimal,
    account_id: str | None = None,
    transaction_id: str | None = None,
    user_id: str | None = None,
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
    item_query = select(ReconciliationItem).filter_by(
        reconciliation_id=reconciliation.id,
        source_type="bank_transaction",
    )
    if transaction_id:
        item_query = item_query.where(ReconciliationItem.source_id == transaction_id)
    reconciliation_items = database.session.execute(item_query.limit(2)).scalars().all()
    if len(reconciliation_items) != 1:
        raise BankStatementError("La conciliacion no identifica una transaccion bancaria unica.")
    reconciliation_item = reconciliation_items[0]
    bank_account = None
    if reconciliation_item:
        transaction = database.session.get(BankTransaction, reconciliation_item.source_id)
        bank_account = database.session.get(BankAccount, transaction.bank_account_id) if transaction else None
    bank_account_gl_id = bank_account.gl_account_id if bank_account else None
    if not bank_account or not bank_account_gl_id:
        raise BankStatementError("No se encontro cuenta bancaria GL para balancear el ajuste.")
    difference_account = database.session.get(Accounts, difference_account_id)
    bank_gl_account = database.session.get(Accounts, bank_account_gl_id)
    if not difference_account or difference_account.entity != reconciliation.company:
        raise BankStatementError("La cuenta de diferencia bancaria no pertenece a la compañía.")
    if not bank_gl_account or bank_gl_account.entity != reconciliation.company:
        raise BankStatementError("La cuenta bancaria GL no pertenece a la compañía.")
    entity = database.session.execute(select(Entity).where(Entity.code == reconciliation.company)).scalars().first()
    transaction_currency = (bank_account.currency if bank_account else None) or (entity.currency if entity else None)
    if not transaction_currency:
        raise BankStatementError("No se pudo determinar la moneda de la cuenta bancaria.")
    books = list(
        database.session.execute(
            select(Book).where(Book.entity == reconciliation.company, Book.status == "activo").order_by(Book.code)
        ).scalars()
    )
    journal = ComprobanteContable(
        entity=reconciliation.company,
        date=reconciliation.recon_date,
        memo="Ajuste de diferencia bancaria",
        status="draft",
        user_id=user_id,
        voucher_type="journal_entry",
        book=books[0].code if books else None,
        book_codes=json.dumps([book.code for book in books]) if books else None,
        transaction_currency=transaction_currency,
    )
    database.session.add(journal)
    database.session.flush()
    debit_account = difference_account if amount > 0 else bank_gl_account
    credit_account = bank_gl_account if amount > 0 else difference_account
    database.session.add_all(
        [
            ComprobanteContableDetalle(
                transaction="journal_entry",
                transaction_id=journal.id,
                entity=reconciliation.company,
                account=debit_account.code,
                currency_id=transaction_currency,
                bank_account_id=bank_account.id if debit_account.id == bank_gl_account.id else None,
                value=abs(amount),
                memo="Diferencia bancaria",
            ),
            ComprobanteContableDetalle(
                transaction="journal_entry",
                transaction_id=journal.id,
                entity=reconciliation.company,
                account=credit_account.code,
                currency_id=transaction_currency,
                bank_account_id=bank_account.id if credit_account.id == bank_gl_account.id else None,
                value=-abs(amount),
                memo="Diferencia bancaria",
            ),
        ]
    )
    return journal
