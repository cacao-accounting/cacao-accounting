# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para el cierre contable de año fiscal."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from cacao_accounting.contabilidad.journal_service import (
    _normalize_journal_payload,
    create_journal_draft,
    serialize_journal_for_form,
    submit_journal,
)
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    ComprobanteContable,
    FiscalYear,
    GLEntry,
    Book,
    database,
)
from cacao_accounting.ledger_queries import primary_ledger_id


from cacao_accounting.i18n import _

PENDING_APPROVAL_STATUS = "Pending Approval"


class FiscalYearClosingError(ValueError):
    """Error en el proceso de cierre de año fiscal."""


def _cross_year_reversal_pairs(company: str, fiscal_year: FiscalYear) -> list[tuple[str, str]]:
    """Return original/reversal voucher pairs that cross the fiscal-year boundary."""
    original = aliased(GLEntry)
    reversal = aliased(GLEntry)
    query = (
        select(original.voucher_id, reversal.voucher_id)
        .join(reversal, reversal.reversal_of == original.id)
        .where(
            original.company == company,
            original.posting_date >= fiscal_year.year_start_date,
            original.posting_date <= fiscal_year.year_end_date,
            original.is_reversal.is_(False),
            original.is_cancelled.is_(False),
            reversal.company == company,
            reversal.posting_date > fiscal_year.year_end_date,
            reversal.is_reversal.is_(True),
            reversal.is_cancelled.is_(False),
        )
    )
    current_rows = database.session.execute(query.with_for_update()).all()
    reversal_pairs = {(str(original_id), str(reversal_id)) for original_id, reversal_id in current_rows}
    return sorted(reversal_pairs)


def calculate_closing_balances(
    company: str,
    fiscal_year: FiscalYear,
    ledger_id: str | None = None,
) -> list[dict[str, Any]]:
    """Calcula los saldos de cierre para cuentas de ingresos, costos y gastos."""
    # Filtrar entradas por compañia y rango de fechas del año fiscal
    # Excluir registros de cierre previos si los hubiera (is_fiscal_year_closing=False)
    query = (
        select(
            GLEntry.account_id,
            GLEntry.account_code,
            GLEntry.cost_center_code,
            GLEntry.unit_code,
            GLEntry.project_code,
            func.sum(GLEntry.debit - GLEntry.credit).label("balance"),
        )
        .join(Accounts, Accounts.id == GLEntry.account_id)
        .where(
            GLEntry.company == company,
            GLEntry.posting_date >= fiscal_year.year_start_date,
            GLEntry.posting_date <= fiscal_year.year_end_date,
            GLEntry.is_fiscal_year_closing.is_(False),
            GLEntry.is_cancelled.is_(False),
            GLEntry.is_reversal.is_(False),
            Accounts.classification.in_(["ingreso", "costo", "gasto", "income", "cost", "expense"]),
        )
        .group_by(
            GLEntry.account_id,
            GLEntry.account_code,
            GLEntry.cost_center_code,
            GLEntry.unit_code,
            GLEntry.project_code,
        )
    )
    ledger_id = ledger_id or primary_ledger_id(company)
    if ledger_id:
        query = query.where(GLEntry.ledger_id == ledger_id)

    results = database.session.execute(query).all()
    balances = []
    for row in results:
        if row.balance != 0:
            balances.append(
                {
                    "account_id": row.account_id,
                    "account_code": row.account_code,
                    "cost_center": row.cost_center_code,
                    "unit": row.unit_code,
                    "project": row.project_code,
                    "balance": row.balance,
                }
            )
    return balances


def _closing_entry_amounts(balance: Decimal) -> tuple[Decimal, Decimal]:
    """Calcula el débito y crédito para una cuenta de resultados."""
    debit = Decimal("0")
    credit = Decimal("0")
    if balance > 0:
        credit = balance
    else:
        debit = abs(balance)
    return debit, credit


def _closing_line_payload(
    *,
    fiscal_year_name: str,
    order: int,
    balance_row: dict[str, Any],
    book_currency: str | None = None,
) -> dict[str, Any]:
    """Construye una línea de cierre para una cuenta de resultados."""
    debit, credit = _closing_entry_amounts(Decimal(str(balance_row["balance"])))
    return {
        "order": order,
        "book": balance_row.get("book"),
        "account": balance_row["account_code"],
        "cost_center": balance_row["cost_center"],
        "unit": balance_row["unit"],
        "project": balance_row["project"],
        "currency": book_currency,
        "debit": str(debit) if debit > 0 else "",
        "credit": str(credit) if credit > 0 else "",
        "remarks": _("Cierre año fiscal %(year)s") % {"year": fiscal_year_name},
    }


def _closing_retain_earnings_payload(
    *,
    fiscal_year_name: str,
    order: int,
    total_net_balance: Decimal,
    retained_earnings_code: str,
    book: str,
    book_currency: str | None = None,
) -> dict[str, Any]:
    """Construye la línea de contrapartida para utilidades acumuladas."""
    debit = Decimal("0")
    credit = Decimal("0")
    if total_net_balance > 0:
        debit = total_net_balance
    else:
        credit = abs(total_net_balance)
    return {
        "order": order,
        "book": book,
        "account": retained_earnings_code,
        "currency": book_currency,
        "debit": str(debit) if debit > 0 else "",
        "credit": str(credit) if credit > 0 else "",
        "remarks": _("Resultado neto año fiscal %(year)s") % {"year": fiscal_year_name},
    }


def _build_closing_voucher_payload(
    *,
    company: str,
    fiscal_year: FiscalYear,
    balances: list[dict[str, Any]],
    retained_earnings_code: str,
) -> dict[str, Any]:
    """Construye el payload completo del comprobante de cierre."""
    lines: list[dict[str, Any]] = []
    order = 1
    book_currencies = {
        book.code: str(book.currency or "")
        for book in database.session.execute(select(Book).where(Book.entity == company)).scalars().all()
    }
    for book in sorted({str(row["book"]) for row in balances}):
        book_balances = [row for row in balances if row["book"] == book]
        total_net_balance = Decimal("0")
        for balance_row in book_balances:
            lines.append(
                _closing_line_payload(
                    fiscal_year_name=fiscal_year.name,
                    order=order,
                    balance_row=balance_row,
                    book_currency=book_currencies.get(book),
                )
            )
            total_net_balance += Decimal(str(balance_row["balance"]))
            order += 1
        if total_net_balance != 0:
            lines.append(
                _closing_retain_earnings_payload(
                    fiscal_year_name=fiscal_year.name,
                    order=order,
                    total_net_balance=total_net_balance,
                    retained_earnings_code=retained_earnings_code,
                    book=book,
                    book_currency=book_currencies.get(book),
                )
            )
            order += 1

    return {
        "company": company,
        # Cada línea ya contiene el saldo funcional de su libro. La selección
        # completa permite que posting cree únicamente las entradas dirigidas
        # a cada libro, sin reconvertir ni replicar importes de otro libro.
        "books": [
            book.code
            for book in database.session.execute(
                select(Book).where(Book.entity == company, Book.status == "activo").order_by(Book.code)
            ).scalars()
        ],
        "posting_date": fiscal_year.year_end_date.isoformat(),
        "reference": f"CIERRE-{fiscal_year.name}",
        "memo": _("Cierre contable automático del año fiscal %(year)s") % {"year": fiscal_year.name},
        "is_closing": True,
        "is_fiscal_year_closing": True,
        "fiscal_year_id": fiscal_year.id,
        "lines": lines,
    }


def _existing_fiscal_year_closing(fiscal_year_id: str, *, pending_only: bool) -> ComprobanteContable | None:
    """Find an existing draft/proposal so retries do not create duplicate closes."""
    query = select(ComprobanteContable).where(
        ComprobanteContable.fiscal_year_id == fiscal_year_id,
        ComprobanteContable.is_fiscal_year_closing.is_(True),
    )
    if pending_only:
        from cacao_accounting.database import ApprovalRequest

        query = (
            query.join(
                ApprovalRequest,
                (ApprovalRequest.document_id == ComprobanteContable.id) & (ApprovalRequest.document_type == "journal_entry"),
            )
            .where(ApprovalRequest.status == PENDING_APPROVAL_STATUS)
            .order_by(ApprovalRequest.created_at.desc())
        )
    else:
        query = query.where(ComprobanteContable.status == "draft").order_by(ComprobanteContable.created.desc())
    return database.session.execute(query.limit(1)).scalars().first()


def _closing_draft_matches_calculated_payload(journal: ComprobanteContable, payload: dict[str, Any]) -> bool:
    """Reject a previously rejected draft if its close content was edited."""
    try:
        current = _normalize_journal_payload(serialize_journal_for_form(journal))
        expected = _normalize_journal_payload(payload)
    except ValueError:
        return False
    header_fields = (
        "company",
        "posting_date",
        "naming_series_id",
        "reference",
        "memo",
        "transaction_currency",
        "base_currency",
        "exchange_rate",
        "is_closing",
        "is_fiscal_year_closing",
        "fiscal_year_id",
    )
    return (
        all(getattr(current, field) == getattr(expected, field) for field in header_fields)
        and set(current.books or ()) == set(expected.books or ())
        and current.lines == expected.lines
    )


def _create_or_reuse_closing_draft(
    company: str,
    fiscal_year: FiscalYear,
    balances: list[dict[str, Any]],
    retained_earnings_code: str,
    user_id: str,
) -> ComprobanteContable:
    """Create a close draft or reuse it only when it still matches ledger balances."""
    payload = _build_closing_voucher_payload(
        company=company,
        fiscal_year=fiscal_year,
        balances=balances,
        retained_earnings_code=retained_earnings_code,
    )
    from cacao_accounting.document_identifiers import _pick_naming_series

    payload["naming_series_id"] = str(_pick_naming_series("journal_entry", company, None).id)
    journal = _existing_fiscal_year_closing(fiscal_year.id, pending_only=False)
    if journal:
        if not _closing_draft_matches_calculated_payload(journal, payload):
            raise FiscalYearClosingError(
                _("El borrador del cierre fiscal no coincide con los saldos calculados; no se envió para aprobación.")
            )
        return journal
    return create_journal_draft(
        payload,
        user_id=user_id,
        allow_closing=True,
        allow_fiscal_year_closing=True,
        commit=False,
    )


def _submit_or_request_closing_approval(journal: ComprobanteContable, company: str, user_id: str) -> None:
    """Route a fiscal close through the configured approval workflow atomically."""
    from cacao_accounting.approval_engine import ApprovalEngine

    if ApprovalEngine.is_enabled(company):
        from cacao_accounting.database import User

        actor = database.session.get(User, user_id)
        request = ApprovalEngine.request_approval(journal, actor=actor)
        if request is None:
            if ApprovalEngine.requires_different_approver(company):
                raise FiscalYearClosingError(
                    _("No existe una regla de aprobación para el cierre fiscal; no se creó el asiento contable.")
                )
            return
        if actor is not None and ApprovalEngine.can_approve(journal, actor):
            ApprovalEngine.approve(journal, actor, _("Aprobado por el remitente"))
        return

    posted_entries = submit_journal(journal.id, commit=False, user_id=user_id)
    from cacao_accounting.contabilidad.arap_ledger_service import post_journal_ar_ap

    post_journal_ar_ap(journal, posted_entries)


def create_fiscal_year_closing_voucher(company: str, fiscal_year_id: str, user_id: str) -> ComprobanteContable:
    """Ejecuta el proceso de cierre de año fiscal."""
    fiscal_year = database.session.execute(
        select(FiscalYear).where(FiscalYear.id == fiscal_year_id).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if not fiscal_year:
        raise FiscalYearClosingError(_("Año fiscal no encontrado."))

    if fiscal_year.entity != company:
        raise FiscalYearClosingError(_("La compañía no coincide con la entidad del año fiscal."))

    from cacao_accounting.database import AccountingPeriod

    open_periods = database.session.execute(
        select(AccountingPeriod.id)
        .where(AccountingPeriod.fiscal_year_id == fiscal_year.id)
        .where(AccountingPeriod.is_closed.is_(False))
    ).all()
    if open_periods:
        raise FiscalYearClosingError(
            _("No se puede cerrar el año fiscal: hay %(open_period_count)s período(s) contable(s) abierto(s).")
            % {"open_period_count": len(open_periods)}
        )

    if not fiscal_year.is_closed:
        raise FiscalYearClosingError(_("El año fiscal debe estar cerrado administrativamente antes del cierre contable."))
    if fiscal_year.financial_closed:
        raise FiscalYearClosingError(_("El año fiscal ya tiene un cierre contable realizado."))

    reversal_pairs = _cross_year_reversal_pairs(company, fiscal_year)
    if reversal_pairs:
        details = ", ".join(f"{original} → {reversal}" for original, reversal in reversal_pairs)
        raise FiscalYearClosingError(
            _("No se puede cerrar el año fiscal: existen reversas publicadas posteriormente (%(details)s).")
            % {"details": details}
        )

    pending_journal = _existing_fiscal_year_closing(fiscal_year.id, pending_only=True)
    if pending_journal:
        return pending_journal

    books = list(
        database.session.execute(
            select(Book).where(Book.entity == company, Book.status == "activo").order_by(Book.code)
        ).scalars()
    )
    balances: list[dict[str, Any]] = []
    for book in books:
        book_balances = calculate_closing_balances(company, fiscal_year, ledger_id=book.id)
        balances.extend({**balance, "book": book.code} for balance in book_balances)
    if not balances:
        raise FiscalYearClosingError(_("No hay movimientos en cuentas de resultados para cerrar en este año fiscal."))

    defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()
    if not defaults or not defaults.retained_earnings_account_id:
        raise FiscalYearClosingError(_("No se ha definido la cuenta de utilidades acumuladas en la configuración."))

    retained_earnings_account = database.session.get(Accounts, defaults.retained_earnings_account_id)
    if not retained_earnings_account:
        raise FiscalYearClosingError(_("La cuenta de utilidades acumuladas configurada no existe."))

    try:
        journal = _create_or_reuse_closing_draft(
            company,
            fiscal_year,
            balances,
            retained_earnings_account.code,
            user_id,
        )
        _submit_or_request_closing_approval(journal, company, user_id)
        database.session.add(journal)
        database.session.commit()
    except FiscalYearClosingError:
        database.session.rollback()
        raise
    except ValueError as exc:
        database.session.rollback()
        raise FiscalYearClosingError(str(exc)) from exc
    except Exception:
        database.session.rollback()
        raise
    return journal


def reverse_fiscal_year_closing(fiscal_year_id: str, user_id: str) -> None:
    """Revierte el cierre contable de un año fiscal."""
    fiscal_year = database.session.get(FiscalYear, fiscal_year_id, with_for_update=True)
    if not fiscal_year:
        raise FiscalYearClosingError(_("Año fiscal no encontrado."))
    if not fiscal_year.financial_closed or not fiscal_year.closing_voucher_id:
        raise FiscalYearClosingError(_("El año fiscal no tiene un cierre contable que revertir."))

    journal = database.session.get(ComprobanteContable, fiscal_year.closing_voucher_id)
    if not journal:
        # Si el comprobante no existe por alguna razon, permitimos resetear la bandera
        fiscal_year.financial_closed = False
        fiscal_year.closing_voucher_id = None
        database.session.add(fiscal_year)
        database.session.commit()
        return

    # Anular el comprobante. Esto disparará el hook en journal_service para actualizar el año fiscal.
    from cacao_accounting.contabilidad.journal_service import cancel_submitted_journal

    cancel_submitted_journal(
        journal.id,
        user_id=user_id,
        reason="Reversión del cierre fiscal",
    )
