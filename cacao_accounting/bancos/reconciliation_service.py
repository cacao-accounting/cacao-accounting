# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de conciliacion bancaria contra pagos y GL."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from cacao_accounting.database import (
    BankAccount,
    BankMatchingRule,
    BankTransaction,
    Entity,
    ExchangeRate,
    GLEntry,
    PaymentEntry,
    Reconciliation,
    ReconciliationItem,
    database,
)
from cacao_accounting.ledger_queries import exclude_cancelled_gl_entries, primary_ledger_id

UNSUPPORTED_TARGET_TYPE_ERROR = "Tipo de destino no soportado para conciliacion bancaria."


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
    deposit = _decimal_value(transaction.deposit)
    withdrawal = _decimal_value(transaction.withdrawal)
    if deposit > 0 and withdrawal > 0:
        raise BankReconciliationError("Una transaccion bancaria no puede tener deposito y retiro simultaneos.")
    if deposit <= 0 and withdrawal <= 0:
        raise BankReconciliationError("La transaccion bancaria requiere un monto positivo.")
    return deposit if deposit > 0 else withdrawal


def _bank_direction(transaction: BankTransaction) -> str | None:
    """Devuelve la dirección económica de una transacción bancaria."""
    if _decimal_value(transaction.deposit) > 0:
        if _decimal_value(transaction.withdrawal) > 0:
            raise BankReconciliationError("Una transaccion bancaria no puede tener dos direcciones.")
        return "deposit"
    if _decimal_value(transaction.withdrawal) > 0:
        return "withdrawal"
    return None


def _payment_amount(payment: PaymentEntry, bank_account_id: str | None = None) -> Decimal:
    """Return the payment amount for the bank leg being reconciled."""
    if payment.payment_type in ("pay", "debit_note"):
        return _decimal_value(payment.paid_amount)
    if payment.payment_type == "internal_transfer" and bank_account_id:
        if payment.bank_account_id == bank_account_id:
            return _decimal_value(payment.paid_amount)
        if payment.target_bank_account_id == bank_account_id:
            return _decimal_value(payment.received_amount or payment.paid_amount)
    return _decimal_value(payment.received_amount or payment.paid_amount)


def _payment_base_amount(payment: PaymentEntry, bank_account_id: str | None = None) -> Decimal | None:
    """Return a functional-currency amount for the bank leg being reconciled."""
    if payment.payment_type in ("pay", "debit_note"):
        return payment.base_paid_amount
    if payment.payment_type == "internal_transfer" and bank_account_id == payment.bank_account_id:
        return payment.base_paid_amount
    return payment.base_received_amount


def _payment_direction(payment: PaymentEntry, transaction: BankTransaction) -> str | None:
    """Relaciona el tipo de pago con la dirección de la cuenta bancaria."""
    if payment.payment_type in ("pay", "debit_note"):
        return "withdrawal"
    if payment.payment_type in ("receive", "credit_note"):
        return "deposit"
    if payment.payment_type == "internal_transfer":
        if payment.bank_account_id == transaction.bank_account_id:
            return "withdrawal"
        if payment.target_bank_account_id == transaction.bank_account_id:
            return "deposit"
    return None


def _payment_belongs_to_bank(payment: PaymentEntry, bank_account_id: str) -> bool:
    """Return whether a payment touches the bank account being reconciled."""
    return bank_account_id in {payment.bank_account_id, payment.target_bank_account_id}


def _gl_direction(entry: GLEntry) -> str | None:
    """Interpreta débito bancario como depósito y crédito como retiro."""
    if _decimal_value(entry.debit) > 0:
        return "deposit"
    if _decimal_value(entry.credit) > 0:
        return "withdrawal"
    return None


def _gl_amount(entry: GLEntry) -> Decimal:
    return _decimal_value(entry.debit or entry.credit)


def _lookup_exchange_rate(origin: str, destination: str, posting_date: date) -> Decimal | None:
    """Look up the latest valid historical rate, including an inverse pair."""
    if origin == destination:
        return Decimal("1")

    def latest_rate(source: str, target: str) -> Decimal | None:
        row = (
            database.session.execute(
                select(ExchangeRate)
                .where(ExchangeRate.origin == source, ExchangeRate.destination == target, ExchangeRate.date <= posting_date)
                .order_by(ExchangeRate.date.desc())
            )
            .scalars()
            .first()
        )
        if row is None:
            return None
        value = _decimal_value(row.rate)
        if value <= 0:
            raise BankReconciliationError("El tipo de cambio debe ser mayor que cero.")
        return value

    direct = latest_rate(origin, destination)
    if direct is not None:
        return direct
    inverse = latest_rate(destination, origin)
    if inverse is not None:
        return Decimal("1") / inverse
    return None


def _convert_gl_amount_to_bank_currency(entry: GLEntry, bank_currency: str, company_currency: str | None) -> Decimal:
    """Resolve a GL amount expressed in the bank transaction currency.

    When the GL entry currency differs from the bank currency, the amount is
    converted from the entry's company currency using historical exchange rates.
    """
    entry_currency = str(entry.account_currency or entry.company_currency or company_currency or "")
    account_currency_amount = entry.debit_in_account_currency or entry.credit_in_account_currency
    company_amount = _gl_amount(entry)

    if entry_currency == bank_currency and account_currency_amount is not None:
        return _decimal_value(account_currency_amount)

    if bank_currency == company_currency:
        return company_amount

    if not company_currency:
        raise BankReconciliationError("La entrada GL no tiene moneda funcional para convertirla.")

    # ``debit``/``credit`` are persisted in the company currency.  The
    # account-currency amount is only authoritative when the bank itself uses
    # that currency (handled above); otherwise convert the functional amount.
    rate = _lookup_exchange_rate(company_currency, bank_currency, entry.posting_date)
    if rate is None:
        raise BankReconciliationError(
            f"No existe tipo de cambio para {company_currency} -> {bank_currency} en {entry.posting_date}."
        )
    return (company_amount * rate).quantize(Decimal("0.0001"))


def _bank_company(transaction: BankTransaction) -> str:
    bank_account = database.session.get(BankAccount, transaction.bank_account_id)
    if not bank_account:
        raise BankReconciliationError("La transaccion bancaria no tiene cuenta bancaria valida.")
    return str(bank_account.company)


def _bank_gl_account_id(transaction: BankTransaction) -> str | None:
    bank_account = database.session.get(BankAccount, transaction.bank_account_id)
    return str(bank_account.gl_account_id) if bank_account and bank_account.gl_account_id else None


def _bank_currency(transaction: BankTransaction) -> str | None:
    """Return the currency configured for the bank account."""
    bank_account = database.session.get(BankAccount, transaction.bank_account_id)
    return str(bank_account.currency) if bank_account and bank_account.currency else None


def _company_currency(company: str) -> str | None:
    """Return the functional currency configured for a company."""
    entity = database.session.execute(select(Entity).filter_by(code=company)).scalars().first()
    return str(entity.currency) if entity and entity.currency else None


def _allocated_for_source(bank_transaction_id: str) -> Decimal:
    value = database.session.execute(
        select(func.coalesce(func.sum(ReconciliationItem.allocated_amount), 0))
        .filter_by(
            source_type="bank_transaction",
            source_id=bank_transaction_id,
        )
        .where(ReconciliationItem.status != "cancelled")
    ).scalar_one()
    return _decimal_value(value)


def _allocated_for_target(target_type: str, target_id: str, *, bank_account_id: str | None = None) -> Decimal:
    """Suma asignaciones activas del destino.

    Con ``bank_account_id`` se limita a la pierna bancaria indicada: un
    ``PaymentEntry`` de transferencia interna se concilia dos veces (salida
    en la cuenta origen y entrada en la destino) y cada pierna consume su
    propio importe sin descontar el pendiente de la otra.  Las partidas con
    contexto persistido se filtran por ``ReconciliationItem.bank_account_id``
    (válido aunque la transacción fuente ya no exista); las legacy sin
    contexto conservan el fallback por la transacción fuente.
    """
    query = (
        select(func.coalesce(func.sum(ReconciliationItem.allocated_amount), 0))
        .filter_by(
            target_type=target_type,
            target_id=target_id,
        )
        .where(ReconciliationItem.status != "cancelled")
    )
    if bank_account_id:
        query = query.outerjoin(
            BankTransaction,
            database.and_(
                BankTransaction.id == ReconciliationItem.source_id,
                ReconciliationItem.source_type == "bank_transaction",
            ),
        ).where(
            database.or_(
                ReconciliationItem.bank_account_id == bank_account_id,
                database.and_(
                    ReconciliationItem.bank_account_id.is_(None),
                    BankTransaction.bank_account_id == bank_account_id,
                ),
            )
        )
    return _decimal_value(database.session.execute(query).scalar_one())


def _allocation_context(transaction: BankTransaction, company: str, reconciliation_date: date) -> dict[str, Any]:
    """Resuelve el contexto contable que se persiste en cada asignacion.

    El contexto (compania, pierna bancaria, moneda, libro, direccion y tasa
    historica) hace que los saldos pendientes sigan siendo correctos aunque la
    transacción fuente desaparezca y permite rechazar mezclas de monedas sin
    depender de datos ajenos a la propia asignación.
    """
    currency = _bank_currency(transaction)
    company_currency = _company_currency(company)
    exchange_rate: Decimal | None = None
    if currency and company_currency:
        if currency == company_currency:
            exchange_rate = Decimal("1")
        else:
            exchange_rate = _lookup_exchange_rate(company_currency, currency, reconciliation_date)
    return {
        "company": company,
        "bank_account_id": transaction.bank_account_id,
        "currency": currency,
        "ledger_id": primary_ledger_id(company),
        "direction": _bank_direction(transaction),
        "exchange_rate": exchange_rate,
    }


def backfill_reconciliation_item_context() -> dict[str, int]:
    """Migra partidas de conciliación bancaria legacy al contexto persistido.

    Recorre las asignaciones bancarias activas sin moneda y completa compania,
    cuenta bancaria, moneda, libro, dirección y tasa histórica a partir de su
    transacción fuente.  Las partidas cuya fuente ya no existe (o cuya
    conciliación no declara compañía) no tienen contexto inequívoco: se
    cuentan como ``unresolved`` para revisión manual.

    Returns:
        Conteo de partidas migradas y partidas sin contexto resoluble.
    """
    stats = {"backfilled": 0, "unresolved": 0}
    items = (
        database.session.execute(
            select(ReconciliationItem).where(
                ReconciliationItem.source_type == "bank_transaction",
                ReconciliationItem.status != "cancelled",
                ReconciliationItem.currency.is_(None),
            )
        )
        .scalars()
        .all()
    )
    for item in items:
        transaction = database.session.get(BankTransaction, item.source_id) if item.source_id else None
        reconciliation = database.session.get(Reconciliation, item.reconciliation_id)
        company = str(reconciliation.company) if reconciliation and reconciliation.company else None
        if transaction is None or not company:
            stats["unresolved"] += 1
            continue
        context = _allocation_context(transaction, company, item.reconciliation_date or transaction.posting_date)
        for field, value in context.items():
            setattr(item, field, value)
        stats["backfilled"] += 1
    return stats


def _validate_target_allocation_currency(
    target_type: str,
    target_id: str,
    transaction: BankTransaction,
) -> None:
    """Rechaza asignaciones históricas del destino en otra moneda bancaria.

    La moneda fiable de una asignación es la que la propia partida persiste;
    así la validación cubre también huérfanos cuya transacción fuente ya no
    existe.  Las partidas legacy sin contexto conservan el fallback por la
    transacción fuente y las irreconocibles se omiten (quedan diagnosticadas
    como partidas sin contexto).  La validación se limita a la pierna de la
    misma cuenta bancaria: en una transferencia interna cada pierna vive
    legítimamente en su propia moneda.
    """
    current_currency = _bank_currency(transaction)
    if not current_currency:
        return
    rows = database.session.execute(
        select(
            ReconciliationItem.currency,
            ReconciliationItem.source_id,
        )
        .outerjoin(
            BankTransaction,
            database.and_(
                BankTransaction.id == ReconciliationItem.source_id,
                ReconciliationItem.source_type == "bank_transaction",
            ),
        )
        .where(
            ReconciliationItem.target_type == target_type,
            ReconciliationItem.target_id == target_id,
            ReconciliationItem.status != "cancelled",
            database.or_(
                ReconciliationItem.bank_account_id == transaction.bank_account_id,
                database.and_(
                    ReconciliationItem.bank_account_id.is_(None),
                    BankTransaction.bank_account_id == transaction.bank_account_id,
                ),
            ),
        )
    ).all()
    for item_currency, source_id in rows:
        resolved = str(item_currency) if item_currency else None
        if not resolved:
            source = database.session.get(BankTransaction, source_id)
            resolved = _bank_currency(source) if source else None
        if resolved and resolved != current_currency:
            raise BankReconciliationError(
                "El destino ya tiene asignaciones en otra moneda bancaria; "
                "convierta o revierta la asignación anterior antes de continuar."
            )


def _target_amount(target_type: str, target_id: str, transaction: BankTransaction | None = None) -> Decimal:
    """Return a target amount expressed in the bank transaction currency."""
    bank_currency = _bank_currency(transaction) if transaction else None
    company = _bank_company(transaction) if transaction else None
    company_currency = _company_currency(company) if company else None
    if target_type == "payment_entry":
        bank_account_id = transaction.bank_account_id if transaction else None
        return _target_payment_amount(target_id, bank_currency, company_currency, bank_account_id)
    if target_type == "gl_entry":
        return _target_gl_amount(target_id, bank_currency, company_currency)
    raise BankReconciliationError(UNSUPPORTED_TARGET_TYPE_ERROR)


def _target_payment_amount(
    target_id: str,
    bank_currency: str | None,
    company_currency: str | None,
    bank_account_id: str | None = None,
) -> Decimal:
    """Resolve a payment amount in the bank transaction currency."""
    payment = database.session.get(PaymentEntry, target_id)
    if not payment:
        raise BankReconciliationError("La entrada de pago a conciliar no existe.")
    if getattr(payment, "docstatus", 0) != 1:
        raise BankReconciliationError("La entrada de pago debe estar aprobada para conciliarse.")
    payment_currency = str(payment.currency) if payment.currency else company_currency
    if not bank_currency or payment_currency == bank_currency:
        return _payment_amount(payment, bank_account_id)
    if bank_currency != company_currency:
        raise BankReconciliationError("La moneda del pago no coincide con la cuenta bancaria.")
    base_amount = _payment_base_amount(payment, bank_account_id)
    if base_amount is None:
        # Pierna receptora de una transferencia interna: ``base_received_amount``
        # se limpia al crearse y el importe de la pierna ya esta expresado en la
        # moneda del banco destino (igual a la funcional en este punto).
        return _payment_amount(payment, bank_account_id)
    return _decimal_value(base_amount)


def _target_gl_amount(target_id: str, bank_currency: str | None, company_currency: str | None) -> Decimal:
    """Resolve a GL amount in the bank transaction currency.

    When the GL entry currency differs from the bank currency, the entry amount
    is converted using historical exchange rates instead of discarding it.
    """
    entry = database.session.get(GLEntry, target_id)
    if not entry:
        raise BankReconciliationError("La entrada GL a conciliar no existe.")
    _validate_gl_entry_eligibility(entry)
    if bank_currency:
        return _convert_gl_amount_to_bank_currency(entry, bank_currency, company_currency)
    return _gl_amount(entry)


def _validate_gl_entry_eligibility(entry: GLEntry) -> None:
    """Require an active entry from the primary ledger for bank matching."""
    if getattr(entry, "is_cancelled", False) or getattr(entry, "is_reversal", False):
        raise BankReconciliationError("La entrada GL está cancelada o es una reversa.")
    if hasattr(entry, "ledger_id"):
        primary_id = primary_ledger_id(str(entry.company))
        if primary_id and entry.ledger_id != primary_id:
            raise BankReconciliationError("La entrada GL no pertenece al libro primario.")


def _target_company(target_type: str, target_id: str) -> str:
    match target_type:
        case "payment_entry":
            payment = database.session.get(PaymentEntry, target_id)
            if not payment:
                raise BankReconciliationError("La entrada de pago a conciliar no existe.")
            if getattr(payment, "docstatus", 0) != 1:
                raise BankReconciliationError("La entrada de pago debe estar aprobada para conciliarse.")
            return str(payment.company)
        case "gl_entry":
            entry = database.session.get(GLEntry, target_id)
            if not entry:
                raise BankReconciliationError("La entrada GL a conciliar no existe.")
            return str(entry.company)
        case _:
            raise BankReconciliationError(UNSUPPORTED_TARGET_TYPE_ERROR)


def _candidate_score(
    *,
    bank_transaction: BankTransaction,
    amount: Decimal,
    posting_date: date,
    reference_no: str | None,
    amount_tolerance: Decimal = Decimal("0"),
) -> int:
    """Puntúa un candidato: monto dentro de tolerancia (+60), fecha exacta (+25) y referencia (+15)."""
    score = 0
    if abs(amount - _bank_amount(bank_transaction)) <= amount_tolerance:
        score += 60
    if posting_date == bank_transaction.posting_date:
        score += 25
    if reference_no and bank_transaction.reference_number and reference_no == bank_transaction.reference_number:
        score += 15
    return score


def _append_candidate(
    candidates: list[BankCandidate],
    *,
    reference_type: str,
    reference_id: str,
    amount: Decimal,
    posting_date: date,
    reference_no: str | None,
    bank_transaction: BankTransaction,
    pending: Decimal,
    amount_tolerance: Decimal = Decimal("0"),
) -> None:
    """Agrega un candidato con el score y estado derivados."""
    bank_amount = _bank_amount(bank_transaction)
    allocated_amount = min(amount, pending, bank_amount)
    within_tolerance = abs(amount - bank_amount) <= amount_tolerance
    candidates.append(
        BankCandidate(
            reference_type=reference_type,
            reference_id=reference_id,
            amount=allocated_amount,
            posting_date=posting_date,
            reference_no=reference_no,
            score=_candidate_score(
                bank_transaction=bank_transaction,
                amount=amount,
                posting_date=posting_date,
                reference_no=reference_no,
                amount_tolerance=amount_tolerance,
            ),
            status="exact" if (pending == amount and within_tolerance) else "partial",
        )
    )


def _resolve_rule_tolerances(transaction: BankTransaction, company: str) -> tuple[int, Decimal]:
    """Resuelve las tolerancias desde las reglas activas aplicables.

    Cuando ``find_bank_reconciliation_candidates`` se invoca sin
    tolerancias explícitas (p. ej. desde el panel de conciliación o las
    sugerencias), se consultan las reglas activas para la cuenta y
    compañía de la transacción.  Se toma la ventana de días y la
    tolerancia de monto más amplias entre las reglas cuyo alcance
    (cuenta específica o toda la compañía) aplica; sin reglas aplicables
    se conservan los valores históricos (7 días, monto exacto).
    """
    rows = database.session.execute(
        select(BankMatchingRule.days_tolerance, BankMatchingRule.amount_tolerance).where(
            BankMatchingRule.company == company,
            BankMatchingRule.is_active.is_(True),
            database.or_(
                BankMatchingRule.bank_account_id == transaction.bank_account_id,
                BankMatchingRule.bank_account_id.is_(None),
            ),
        )
    ).all()
    days = 7
    amount_tolerance = Decimal("0")
    for rule_days, rule_amount in rows:
        if rule_days is not None and int(rule_days) > days:
            days = int(rule_days)
        tolerance = _decimal_value(rule_amount)
        if tolerance > amount_tolerance:
            amount_tolerance = tolerance
    return days, amount_tolerance


def find_bank_reconciliation_candidates(
    bank_transaction_id: str,
    *,
    lock: bool = False,
    days_tolerance: int | None = None,
    amount_tolerance: Decimal | None = None,
) -> list[BankCandidate]:
    """Busca pagos y GL bancario candidatos para una transaccion bancaria.

    Los parámetros ``days_tolerance`` y ``amount_tolerance`` amplían
    respectivamente la ventana de fechas y el rango de montos aceptables.
    Sin valores explícitos se resuelven desde las reglas de matching
    activas aplicables a la cuenta/compañía, de modo que las tolerancias
    configuradas afectan realmente al motor de candidatos y al scoring.
    """
    transaction = database.session.get(BankTransaction, bank_transaction_id, with_for_update=lock)
    if not transaction:
        raise BankReconciliationError("La transaccion bancaria no existe.")
    company = _bank_company(transaction)
    amount = _bank_amount(transaction)
    if amount <= 0:
        raise BankReconciliationError("La transaccion bancaria no tiene monto conciliable.")

    if days_tolerance is None or amount_tolerance is None:
        resolved_days, resolved_amount = _resolve_rule_tolerances(transaction, company)
        if days_tolerance is None:
            days_tolerance = resolved_days
        if amount_tolerance is None:
            amount_tolerance = resolved_amount

    date_from = transaction.posting_date - timedelta(days=max(0, days_tolerance))
    date_to = transaction.posting_date + timedelta(days=max(0, days_tolerance))
    candidates: list[BankCandidate] = []
    bank_currency = _bank_currency(transaction)
    company_currency = _company_currency(company)

    payments = (
        database.session.execute(
            select(PaymentEntry)
            .filter_by(company=company)
            .where(PaymentEntry.posting_date >= date_from)
            .where(PaymentEntry.posting_date <= date_to)
            .where(PaymentEntry.docstatus == 1)
        )
        .scalars()
        .all()
    )
    for payment in payments:
        if not _payment_belongs_to_bank(payment, transaction.bank_account_id):
            continue
        if _payment_direction(payment, transaction) != _bank_direction(transaction):
            continue
        payment_currency = str(payment.currency) if payment.currency else company_currency
        if bank_currency and payment_currency != bank_currency and bank_currency != company_currency:
            continue
        if not bank_currency or payment_currency == bank_currency:
            payment_amount = _payment_amount(payment, transaction.bank_account_id)
        else:
            base_amount = _payment_base_amount(payment, transaction.bank_account_id)
            if base_amount is None:
                # Pierna receptora de transferencia: el importe de la pierna ya
                # vive en la moneda del banco destino.
                payment_amount = _payment_amount(payment, transaction.bank_account_id)
            else:
                payment_amount = _decimal_value(base_amount)
        pending = payment_amount - _allocated_for_target(
            "payment_entry", payment.id, bank_account_id=transaction.bank_account_id
        )
        if pending <= 0:
            continue
        _append_candidate(
            candidates,
            reference_type="payment_entry",
            reference_id=payment.id,
            amount=payment_amount,
            posting_date=payment.posting_date,
            reference_no=payment.reference_no,
            bank_transaction=transaction,
            pending=pending,
            amount_tolerance=amount_tolerance,
        )

    bank_gl_account_id = _bank_gl_account_id(transaction)
    if bank_gl_account_id:
        gl_entries_query = exclude_cancelled_gl_entries(
            select(GLEntry).filter_by(company=company, account_id=bank_gl_account_id)
        )
        ledger_id = primary_ledger_id(company)
        if ledger_id:
            gl_entries_query = gl_entries_query.where(GLEntry.ledger_id == ledger_id)
        gl_entries = (
            database.session.execute(
                gl_entries_query.where(GLEntry.posting_date >= date_from).where(GLEntry.posting_date <= date_to)
            )
            .scalars()
            .all()
        )
        for entry in gl_entries:
            if entry.bank_account_id and entry.bank_account_id != transaction.bank_account_id:
                continue
            if _gl_direction(entry) != _bank_direction(transaction):
                continue
            try:
                entry_amount = (
                    _convert_gl_amount_to_bank_currency(entry, bank_currency, company_currency)
                    if bank_currency
                    else _gl_amount(entry)
                )
            except BankReconciliationError:
                continue
            pending = entry_amount - _allocated_for_target("gl_entry", entry.id)
            if pending <= 0:
                continue
            _append_candidate(
                candidates,
                reference_type="gl_entry",
                reference_id=entry.id,
                amount=entry_amount,
                posting_date=entry.posting_date,
                reference_no=entry.document_no,
                bank_transaction=transaction,
                pending=pending,
                amount_tolerance=amount_tolerance,
            )

    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def _update_reconciled_transactions(source_totals: dict[str, Decimal], matches: list[Any]) -> None:
    """Mark bank transactions as reconciled and populate payment_entry_id."""
    for bank_transaction_id in source_totals:
        bank_transaction = database.session.get(BankTransaction, bank_transaction_id, with_for_update=True)
        if bank_transaction is not None:
            if _allocated_for_source(bank_transaction_id) >= _bank_amount(bank_transaction):
                bank_transaction.is_reconciled = True
            _populate_payment_entry_id(bank_transaction, bank_transaction_id, matches)


def _populate_payment_entry_id(bank_transaction: BankTransaction | None, bank_transaction_id: str, matches: list[Any]) -> None:
    """Set payment_entry_id when a bank transaction is reconciled against a payment."""
    if bank_transaction is None or bank_transaction.payment_entry_id:
        return
    for match in matches:
        if match.bank_transaction_id == bank_transaction_id and match.target_type == "payment_entry":
            bank_transaction.payment_entry_id = match.target_id
            break


def reconcile_bank_items(request: BankReconciliationRequest) -> Reconciliation:
    """Crea una conciliacion bancaria parcial o total."""
    if not request.matches:
        raise BankReconciliationError("La conciliacion bancaria requiere al menos una linea.")

    _lock_request_transactions(request)
    if existing := _matching_reconciliation_replay(request):
        return existing

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
        _add_reconciliation_match(
            request,
            reconciliation,
            match,
            source_totals,
            target_totals,
            existing_source_allocations,
            existing_target_allocations,
        )

    database.session.flush()
    _update_reconciled_transactions(source_totals, request.matches)

    return reconciliation


def _lock_request_transactions(request: BankReconciliationRequest) -> None:
    """Lock sources in deterministic order before testing an idempotent replay."""
    for transaction_id in sorted({match.bank_transaction_id for match in request.matches}):
        transaction = database.session.get(BankTransaction, transaction_id, with_for_update=True)
        if transaction is None:
            raise BankReconciliationError("La transaccion bancaria no existe.")
        if _bank_company(transaction) != request.company:
            raise BankReconciliationError("La transaccion bancaria pertenece a otra compania.")


def _matching_reconciliation_replay(request: BankReconciliationRequest) -> Reconciliation | None:
    """Return a prior reconciliation only when the complete economic request matches."""
    requested = Counter(
        (match.bank_transaction_id, match.target_type, match.target_id, _decimal_value(match.allocated_amount))
        for match in request.matches
    )
    candidates = database.session.execute(
        select(Reconciliation)
        .where(
            Reconciliation.company == request.company,
            Reconciliation.recon_date == request.reconciliation_date,
            Reconciliation.recon_type == "bank",
        )
        .order_by(Reconciliation.created.desc())
    ).scalars()
    for reconciliation in candidates:
        persisted = Counter(
            (item.source_id, item.target_type, item.target_id, _decimal_value(item.allocated_amount or item.amount))
            for item in database.session.execute(
                select(ReconciliationItem).where(ReconciliationItem.reconciliation_id == reconciliation.id)
            ).scalars()
            if item.source_type == "bank_transaction" and item.status != "cancelled"
        )
        if persisted == requested:
            return reconciliation
    return None


def _add_reconciliation_match(
    request, reconciliation, match, source_totals, target_totals, existing_source_allocations, existing_target_allocations
) -> None:
    """Valida y persiste una línea de conciliación bancaria."""
    transaction = _validate_reconciliation_match(match=match, company=request.company)
    target_key = (match.target_type, match.target_id)
    source_pending, target_pending = _reconciliation_pending_amounts(
        transaction=transaction,
        target_type=match.target_type,
        target_id=match.target_id,
        source_totals=source_totals,
        target_totals=target_totals,
        existing_source_allocations=existing_source_allocations,
        existing_target_allocations=existing_target_allocations,
    )
    if match.allocated_amount > source_pending:
        raise BankReconciliationError("El monto excede el saldo bancario pendiente de conciliar.")
    if match.allocated_amount > target_pending:
        raise BankReconciliationError("El monto excede el saldo pendiente del documento destino.")
    status = "reconciled" if match.allocated_amount == source_pending == target_pending else "partial"
    context = _allocation_context(transaction, request.company, request.reconciliation_date)
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
            **context,
        )
    )
    source_totals[transaction.id] = source_totals.get(transaction.id, Decimal("0")) + match.allocated_amount
    target_totals[target_key] = target_totals.get(target_key, Decimal("0")) + match.allocated_amount


def _validate_reconciliation_match(*, match: BankReconciliationMatch, company: str) -> BankTransaction:
    """Valida una linea de conciliacion y devuelve la transaccion bancaria."""
    if match.allocated_amount <= 0:
        raise BankReconciliationError("El monto conciliado debe ser mayor que cero.")
    # CAS-02: FOR UPDATE para prevenir duplicación concurrente
    transaction = database.session.get(BankTransaction, match.bank_transaction_id, with_for_update=True)
    if not transaction:
        raise BankReconciliationError("La transaccion bancaria no existe.")
    if _bank_company(transaction) != company:
        raise BankReconciliationError("La transaccion bancaria pertenece a otra compania.")
    _lock_reconciliation_target(match.target_type, match.target_id)
    if _target_company(match.target_type, match.target_id) != company:
        raise BankReconciliationError("El documento destino pertenece a otra compania.")
    if match.target_type == "gl_entry":
        entry = database.session.get(GLEntry, match.target_id)
        bank_gl_account_id = _bank_gl_account_id(transaction)
        if not entry or not bank_gl_account_id or entry.account_id != bank_gl_account_id:
            raise BankReconciliationError("La entrada GL no pertenece a la cuenta bancaria conciliada.")
        if entry.bank_account_id and entry.bank_account_id != transaction.bank_account_id:
            raise BankReconciliationError("La entrada GL pertenece a otra cuenta bancaria.")
        _validate_gl_entry_eligibility(entry)
    elif match.target_type == "payment_entry":
        payment = database.session.get(PaymentEntry, match.target_id)
        if not payment or not _payment_belongs_to_bank(payment, transaction.bank_account_id):
            raise BankReconciliationError("El pago no pertenece a la cuenta bancaria conciliada.")
        if _payment_direction(payment, transaction) != _bank_direction(transaction):
            raise BankReconciliationError("El tipo de pago no coincide con la direccion bancaria.")
    return transaction


def _lock_reconciliation_target(target_type: str, target_id: str) -> None:
    """Bloquea el documento destino antes de leer su saldo conciliable."""
    model = {"payment_entry": PaymentEntry, "gl_entry": GLEntry}.get(target_type)
    if model is None:
        raise BankReconciliationError(UNSUPPORTED_TARGET_TYPE_ERROR)
    target = database.session.get(model, target_id, with_for_update=True)
    if target is None:
        raise BankReconciliationError("El documento destino no existe.")


def _reconciliation_pending_amounts(
    *,
    transaction: BankTransaction,
    target_type: str,
    target_id: str,
    source_totals: dict[str, Decimal],
    target_totals: dict[tuple[str, str], Decimal],
    existing_source_allocations: dict[str, Decimal],
    existing_target_allocations: dict[tuple[str, str], Decimal],
) -> tuple[Decimal, Decimal]:
    """Calcula saldos pendientes source/target considerando asignaciones previas."""
    target_key = (target_type, target_id)
    _validate_target_allocation_currency(target_type, target_id, transaction)
    leg_account_id = transaction.bank_account_id if target_type == "payment_entry" else None
    existing_source_allocations.setdefault(transaction.id, _allocated_for_source(transaction.id))
    existing_target_allocations.setdefault(
        target_key, _allocated_for_target(target_type, target_id, bank_account_id=leg_account_id)
    )
    source_pending = (
        _bank_amount(transaction)
        - existing_source_allocations[transaction.id]
        - source_totals.get(transaction.id, Decimal("0"))
    )
    target_pending = (
        _target_amount(target_type, target_id, transaction)
        - existing_target_allocations[target_key]
        - target_totals.get(target_key, Decimal("0"))
    )
    return source_pending, target_pending
