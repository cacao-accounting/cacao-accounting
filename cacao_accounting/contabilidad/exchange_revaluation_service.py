# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes

"""Servicio de revalorizacion cambiaria NIIF multiledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from sqlalchemy import select

from cacao_accounting.contabilidad.default_accounts import DefaultAccountError, validate_gl_account_usage
from cacao_accounting.database import (
    Accounts,
    AccountingPeriod,
    BankAccount,
    Book,
    CompanyDefaultAccount,
    ComprobanteContable,
    Entity,
    ExchangeRate,
    ExchangeRevaluation,
    ExchangeRevaluationItem,
    GLEntry,
    PartyAccount,
    PurchaseInvoice,
    SalesInvoice,
    database,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount
from cacao_accounting.document_identifiers import IdentifierConfigurationError, assign_document_identifier
from cacao_accounting.audit_trail_service import log_cancel, log_create, log_submit

EXCHANGE_REVALUATION_ENTITY_TYPE = "exchange_revaluation"
EXCHANGE_REVALUATION_STATUS_POSTED = "posted"
EXCHANGE_REVALUATION_STATUS_VOIDED = "voided"
EXCHANGE_REVALUATION_STATUS_NO_CHANGES = "completed_no_changes"
MONETARY_ACCOUNT_TYPES = {"receivable", "payable", "bank", "cash", "asset", "liability"}


class ExchangeRevaluationError(ValueError):
    """Error controlado del proceso de revalorizacion cambiaria."""


@dataclass(frozen=True)
class RevaluationCandidate:
    """Partida monetaria abierta candidata a revalorizacion."""

    source_document_type: str
    source_document_id: str
    source_document_no: str | None
    partner_type: str | None
    partner_id: str | None
    account_id: str
    original_currency: str
    open_amount_original: Decimal
    normal_balance: str
    total_amount_original: Decimal
    bank_account_id: str | None = None
    as_of_date: date | None = None


@dataclass(frozen=True)
class RevaluationLineDraft:
    """Calculo incremental de una linea documental."""

    candidate: RevaluationCandidate
    ledger: Book
    closing_rate: Decimal
    previous_ledger_balance: Decimal
    revalued_balance: Decimal
    exchange_difference: Decimal


class ExchangeRevaluationService:
    """Ejecuta y reversa revalorizaciones cambiarias auditables."""

    def run(
        self,
        *,
        company: str,
        year: int | None = None,
        month: int | None = None,
        period_id: str | None = None,
        user_id: str | None = None,
    ) -> ExchangeRevaluation:
        """Ejecuta una revalorizacion para compania y periodo."""
        if period_id:
            period = database.session.get(AccountingPeriod, period_id)
            if period is None:
                raise ExchangeRevaluationError("No existe el periodo contable seleccionado.")
            if period.entity != company:
                raise ExchangeRevaluationError("El periodo contable no pertenece a la compañía seleccionada.")
            if period.is_closed:
                raise ExchangeRevaluationError("No se puede operar revalorizacion en un periodo cerrado o inexistente.")
            year = period.end.year
            month = period.end.month
        elif year is None or month is None:
            raise ExchangeRevaluationError("El año y el mes son requeridos para ejecutar la revalorización.")
        else:
            period = self._period_for(company, year, month)

        defaults = self._validated_defaults(company)
        ledgers = self._active_ledgers(company)
        candidates = self._open_candidates(company, period.end)

        run = ExchangeRevaluation(
            company=company,
            posting_date=period.end,
            document_date=period.end,
            run_date=period.end,
            year=year,
            month=month,
            status=EXCHANGE_REVALUATION_STATUS_NO_CHANGES,
            docstatus=1,
            created_by=user_id,
            processed_documents_count=len(candidates),
            affected_documents_count=0,
            total_gain=Decimal("0"),
            total_loss=Decimal("0"),
            generated_journal=False,
            voucher_type=EXCHANGE_REVALUATION_ENTITY_TYPE,
        )
        database.session.add(run)
        database.session.flush()
        self._assign_identifier(run)
        log_create(run)

        drafts = self._calculate_lines(candidates, ledgers, period.end)
        affected = [draft for draft in drafts if draft.exchange_difference != 0]
        if not affected:
            database.session.commit()
            return run

        journal = self._create_journal(run, user_id)
        entries, items = self._build_entries_and_items(run, journal, affected, defaults)
        self._validate_entries(entries)
        database.session.add_all(entries)
        database.session.flush()
        self._link_items_to_entries(items, entries)
        database.session.add_all(items)

        run.status = EXCHANGE_REVALUATION_STATUS_POSTED
        run.generated_journal = True
        run.journal_entry_id = journal.id
        run.affected_documents_count = len(affected)
        run.total_gain = sum(
            (self._decimal(entry.credit) for entry in entries if entry.account_id == defaults.exchange_gain_account_id),
            Decimal("0"),
        )
        run.total_loss = sum(
            (self._decimal(entry.debit) for entry in entries if entry.account_id == defaults.exchange_loss_account_id),
            Decimal("0"),
        )
        log_submit(run)
        database.session.commit()
        return run

    def void(self, *, run_id: str, user_id: str | None = None, reason: str | None = None) -> ExchangeRevaluation:
        """Anula una revalorizacion contabilizada mediante reversos GL."""
        run = database.session.get(ExchangeRevaluation, run_id)
        if run is None:
            raise ExchangeRevaluationError("La revalorizacion indicada no existe.")
        if run.status != EXCHANGE_REVALUATION_STATUS_POSTED:
            raise ExchangeRevaluationError("Solo se puede anular una revalorizacion contabilizada.")
        self._ensure_period_open(str(run.company), self._date_for(run))

        journal = self._create_journal(run, user_id, reversal=True)
        originals = self._active_run_entries(run.id)
        if not originals:
            raise ExchangeRevaluationError("La revalorizacion no tiene entradas GL activas para reversar.")

        reversals: list[GLEntry] = []
        for entry in originals:
            reversals.append(
                GLEntry(
                    posting_date=self._date_for(run),
                    company=entry.company,
                    ledger_id=entry.ledger_id,
                    account_id=entry.account_id,
                    account_code=entry.account_code,
                    debit=self._decimal(entry.credit),
                    credit=self._decimal(entry.debit),
                    debit_in_account_currency=self._decimal(entry.credit_in_account_currency),
                    credit_in_account_currency=self._decimal(entry.debit_in_account_currency),
                    account_currency=entry.account_currency,
                    company_currency=entry.company_currency,
                    exchange_rate=entry.exchange_rate,
                    party_type=entry.party_type,
                    party_id=entry.party_id,
                    bank_account_id=entry.bank_account_id,
                    is_advance=entry.is_advance,
                    voucher_type=EXCHANGE_REVALUATION_ENTITY_TYPE,
                    voucher_id=run.id,
                    document_no=run.document_no,
                    naming_series_id=run.naming_series_id,
                    fiscal_year_id=entry.fiscal_year_id,
                    accounting_period_id=entry.accounting_period_id,
                    cost_center_code=entry.cost_center_code,
                    unit_code=entry.unit_code,
                    project_code=entry.project_code,
                    remarks="Reversion revalorizacion cambiaria",
                    is_reversal=True,
                    reversal_of=entry.id,
                    exchange_revaluation_run_id=run.id,
                )
            )
            entry.is_cancelled = True

        self._validate_entries(reversals)
        database.session.add_all(reversals)
        run.status = EXCHANGE_REVALUATION_STATUS_VOIDED
        run.docstatus = 2
        run.reversal_journal_id = journal.id
        run.voided_by = user_id
        run.voided_at = datetime.now(UTC).replace(tzinfo=None)
        run.void_reason = reason
        log_cancel(run)
        database.session.commit()
        return run

    def list_runs(self) -> list[ExchangeRevaluation]:
        """Lista ejecuciones recientes de revalorizacion."""
        return list(
            database.session.execute(
                select(ExchangeRevaluation).order_by(
                    ExchangeRevaluation.run_date.desc(),
                    ExchangeRevaluation.created.desc(),
                    ExchangeRevaluation.id.desc(),
                )
            )
            .scalars()
            .all()
        )

    def list_lines(self, run_id: str) -> list[ExchangeRevaluationItem]:
        """Lista lineas documentales de una revalorizacion."""
        return list(
            database.session.execute(
                select(ExchangeRevaluationItem)
                .filter_by(revaluation_id=run_id)
                .order_by(ExchangeRevaluationItem.source_document_no, ExchangeRevaluationItem.id)
            )
            .scalars()
            .all()
        )

    def _period_for(self, company: str, year: int, month: int) -> AccountingPeriod:
        period = (
            database.session.execute(
                select(AccountingPeriod)
                .filter_by(entity=company, is_closed=False)
                .where(AccountingPeriod.start <= date(year, month, 28))
                .where(AccountingPeriod.end >= date(year, month, 1))
                .order_by(AccountingPeriod.start)
            )
            .scalars()
            .first()
        )
        if period is None:
            raise ExchangeRevaluationError("No existe un periodo contable abierto para la compania, mes y anio.")
        return period

    def _ensure_period_open(self, company: str, posting_date: date) -> None:
        period = (
            database.session.execute(
                select(AccountingPeriod)
                .filter_by(entity=company)
                .where(AccountingPeriod.start <= posting_date)
                .where(AccountingPeriod.end >= posting_date)
            )
            .scalars()
            .first()
        )
        if period is None or period.is_closed:
            raise ExchangeRevaluationError("No se puede operar revalorizacion en un periodo cerrado o inexistente.")

    def _validated_defaults(self, company: str) -> CompanyDefaultAccount:
        defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()
        if defaults is None:
            raise ExchangeRevaluationError("No existe configuracion de cuentas predeterminadas para la compania.")
        if not defaults.exchange_gain_account_id:
            raise ExchangeRevaluationError("No existe cuenta de ganancia cambiaria configurada.")
        if not defaults.exchange_loss_account_id:
            raise ExchangeRevaluationError("No existe cuenta de perdida cambiaria configurada.")
        return defaults

    def _active_ledgers(self, company: str) -> list[Book]:
        ledgers = (
            database.session.execute(
                select(Book)
                .filter(Book.entity == company)
                .where((Book.status == "activo") | (Book.status.is_(None)))
                .order_by(Book.is_primary.desc(), Book.code)
            )
            .scalars()
            .all()
        )
        if not ledgers:
            raise ExchangeRevaluationError("No existen libros contables activos para la compania.")
        invalid = [ledger.code for ledger in ledgers if not ledger.currency]
        if invalid:
            raise ExchangeRevaluationError("Hay libros activos sin moneda configurada: " + ", ".join(invalid))
        return list(ledgers)

    def _open_candidates(self, company: str, as_of_date: date) -> list[RevaluationCandidate]:
        candidates = self._open_sales_invoices(company, as_of_date)
        candidates.extend(self._open_purchase_invoices(company, as_of_date))
        candidates.extend(self._open_bank_accounts(company, as_of_date))
        return candidates

    def _open_sales_invoices(self, company: str, as_of_date: date) -> list[RevaluationCandidate]:
        rows = (
            database.session.execute(
                select(SalesInvoice)
                .filter_by(company=company)
                .where(SalesInvoice.posting_date <= as_of_date)
                .where(SalesInvoice.docstatus != 2)
            )
            .scalars()
            .all()
        )
        candidates = []
        for invoice in rows:
            outstanding = compute_outstanding_amount(invoice, as_of_date=as_of_date)
            if outstanding <= 0:
                continue
            currency = self._document_currency(invoice, company)
            account_id = self._party_account(invoice.customer_id, company, receivable=True)
            if account_id and currency:
                candidates.append(
                    RevaluationCandidate(
                        source_document_type="sales_invoice",
                        source_document_id=invoice.id,
                        source_document_no=invoice.document_no,
                        partner_type="customer",
                        partner_id=invoice.customer_id,
                        account_id=account_id,
                        original_currency=currency,
                        open_amount_original=outstanding,
                        normal_balance="debit",
                        total_amount_original=self._decimal(invoice.grand_total),
                        as_of_date=as_of_date,
                    )
                )
        return candidates

    def _open_purchase_invoices(self, company: str, as_of_date: date) -> list[RevaluationCandidate]:
        rows = (
            database.session.execute(
                select(PurchaseInvoice)
                .filter_by(company=company)
                .where(PurchaseInvoice.posting_date <= as_of_date)
                .where(PurchaseInvoice.docstatus != 2)
            )
            .scalars()
            .all()
        )
        candidates = []
        for invoice in rows:
            outstanding = compute_outstanding_amount(invoice, as_of_date=as_of_date)
            if outstanding <= 0:
                continue
            currency = self._document_currency(invoice, company)
            account_id = self._party_account(invoice.supplier_id, company, receivable=False)
            if account_id and currency:
                candidates.append(
                    RevaluationCandidate(
                        source_document_type="purchase_invoice",
                        source_document_id=invoice.id,
                        source_document_no=invoice.document_no,
                        partner_type="supplier",
                        partner_id=invoice.supplier_id,
                        account_id=account_id,
                        original_currency=currency,
                        open_amount_original=outstanding,
                        normal_balance="credit",
                        total_amount_original=self._decimal(invoice.grand_total),
                        as_of_date=as_of_date,
                    )
                )
        return candidates

    def _open_bank_accounts(self, company: str, as_of_date: date) -> list[RevaluationCandidate]:
        bank_accounts = (
            database.session.execute(select(BankAccount).filter_by(company=company, is_active=True)).scalars().all()
        )
        candidates = []
        for account in bank_accounts:
            if not account.gl_account_id or not account.currency:
                continue
            amount = self._bank_original_balance(account, as_of_date)
            if amount == 0:
                continue
            candidates.append(
                RevaluationCandidate(
                    source_document_type="bank_account",
                    source_document_id=account.id,
                    source_document_no=account.account_no or account.account_name,
                    partner_type=None,
                    partner_id=None,
                    account_id=account.gl_account_id,
                    original_currency=account.currency,
                    open_amount_original=amount,
                    normal_balance="debit",
                    total_amount_original=amount,
                    bank_account_id=account.id,
                    as_of_date=as_of_date,
                )
            )
        return candidates

    def _calculate_lines(
        self, candidates: list[RevaluationCandidate], ledgers: list[Book], closing_date: date
    ) -> list[RevaluationLineDraft]:
        drafts: list[RevaluationLineDraft] = []
        for candidate in candidates:
            for ledger in ledgers:
                ledger_currency = str(ledger.currency or "")
                if not ledger_currency or ledger_currency == candidate.original_currency:
                    continue
                rate = self._closing_rate(candidate.original_currency, ledger_currency, closing_date)
                previous = self._current_ledger_balance(candidate, ledger)
                revalued = (candidate.open_amount_original * rate).quantize(Decimal("0.0001"))
                difference = (revalued - previous).quantize(Decimal("0.0001"))
                drafts.append(
                    RevaluationLineDraft(
                        candidate=candidate,
                        ledger=ledger,
                        closing_rate=rate,
                        previous_ledger_balance=previous,
                        revalued_balance=revalued,
                        exchange_difference=difference,
                    )
                )
        return drafts

    def _build_entries_and_items(
        self,
        run: ExchangeRevaluation,
        journal: ComprobanteContable,
        drafts: list[RevaluationLineDraft],
        defaults: CompanyDefaultAccount,
    ) -> tuple[list[GLEntry], list[ExchangeRevaluationItem]]:
        entries: list[GLEntry] = []
        items: list[ExchangeRevaluationItem] = []
        period_id, fiscal_year_id = self._period_ids(str(run.company), self._date_for(run))
        for draft in drafts:
            monetary_entry, offset_entry = self._entries_for_draft(run, journal, draft, defaults, period_id, fiscal_year_id)
            entries.extend([monetary_entry, offset_entry])
            items.append(self._item_for_draft(run, draft))
        return entries, items

    def _entries_for_draft(
        self,
        run: ExchangeRevaluation,
        journal: ComprobanteContable,
        draft: RevaluationLineDraft,
        defaults: CompanyDefaultAccount,
        period_id: str | None,
        fiscal_year_id: str | None,
    ) -> tuple[GLEntry, GLEntry]:
        amount = abs(draft.exchange_difference)
        monetary_debit, monetary_credit, offset_account = self._entry_sides(draft, defaults)
        common = {
            "posting_date": self._date_for(run),
            "company": run.company,
            "ledger_id": draft.ledger.id,
            "voucher_type": EXCHANGE_REVALUATION_ENTITY_TYPE,
            "voucher_id": run.id,
            "document_no": run.document_no,
            "naming_series_id": run.naming_series_id,
            "fiscal_year_id": fiscal_year_id,
            "accounting_period_id": period_id,
            "account_currency": draft.ledger.currency,
            "company_currency": draft.ledger.currency,
            "exchange_rate": draft.closing_rate,
            "exchange_revaluation_run_id": run.id,
        }
        monetary = GLEntry(
            **common,
            account_id=draft.candidate.account_id,
            account_code=self._account_code(draft.candidate.account_id),
            debit=amount if monetary_debit else Decimal("0"),
            credit=amount if monetary_credit else Decimal("0"),
            debit_in_account_currency=amount if monetary_debit else None,
            credit_in_account_currency=amount if monetary_credit else None,
            party_type=draft.candidate.partner_type,
            party_id=draft.candidate.partner_id,
            bank_account_id=draft.candidate.bank_account_id,
            remarks=f"Revalorizacion {draft.candidate.source_document_no or draft.candidate.source_document_id}",
        )
        offset = GLEntry(
            **common,
            account_id=offset_account,
            account_code=self._account_code(offset_account),
            debit=amount if not monetary_debit else Decimal("0"),
            credit=amount if not monetary_credit else Decimal("0"),
            debit_in_account_currency=amount if not monetary_debit else None,
            credit_in_account_currency=amount if not monetary_credit else None,
            remarks=f"Resultado cambiario {journal.document_no or run.document_no}",
        )
        return monetary, offset

    def _entry_sides(self, draft: RevaluationLineDraft, defaults: CompanyDefaultAccount) -> tuple[bool, bool, str]:
        increased = draft.exchange_difference > 0
        if draft.candidate.normal_balance == "credit":
            monetary_debit = not increased
            monetary_credit = increased
            offset_account = defaults.exchange_loss_account_id if increased else defaults.exchange_gain_account_id
        else:
            monetary_debit = increased
            monetary_credit = not increased
            offset_account = defaults.exchange_gain_account_id if increased else defaults.exchange_loss_account_id
        if offset_account is None:
            raise ExchangeRevaluationError("No existe cuenta de resultado cambiario configurada.")
        return monetary_debit, monetary_credit, offset_account

    def _item_for_draft(self, run: ExchangeRevaluation, draft: RevaluationLineDraft) -> ExchangeRevaluationItem:
        candidate = draft.candidate
        return ExchangeRevaluationItem(
            revaluation_id=run.id,
            reference_type=candidate.source_document_type,
            reference_id=candidate.source_document_id,
            old_rate=None,
            new_rate=draft.closing_rate,
            difference_amount=draft.exchange_difference,
            source_document_type=candidate.source_document_type,
            source_document_id=candidate.source_document_id,
            source_document_no=candidate.source_document_no,
            partner_id=candidate.partner_id,
            partner_type=candidate.partner_type,
            account_id=candidate.account_id,
            ledger_id=draft.ledger.id,
            original_currency_id=candidate.original_currency,
            ledger_currency_id=draft.ledger.currency,
            open_amount_original=candidate.open_amount_original,
            previous_ledger_balance=draft.previous_ledger_balance,
            closing_rate=draft.closing_rate,
            revalued_balance=draft.revalued_balance,
            exchange_difference=draft.exchange_difference,
            bank_account_id=candidate.bank_account_id,
        )

    def _link_items_to_entries(self, items: list[ExchangeRevaluationItem], entries: list[GLEntry]) -> None:
        for item, entry in zip(items, entries[::2], strict=False):
            item.journal_line_id = entry.id

    def _validate_entries(self, entries: list[GLEntry]) -> None:
        for entry in entries:
            if self._decimal(entry.debit) < 0 or self._decimal(entry.credit) < 0:
                raise ExchangeRevaluationError("Los montos GL de revalorizacion no pueden ser negativos.")
            if (self._decimal(entry.debit) > 0) == (self._decimal(entry.credit) > 0):
                raise ExchangeRevaluationError("Cada linea GL debe afectar solo debe o haber.")
            try:
                validate_gl_account_usage(entry.account_id, entry.voucher_type)
            except DefaultAccountError as exc:
                raise ExchangeRevaluationError(str(exc)) from exc
        for ledger_id in {entry.ledger_id for entry in entries}:
            ledger_entries = [entry for entry in entries if entry.ledger_id == ledger_id]
            debit = sum((self._decimal(entry.debit) for entry in ledger_entries), Decimal("0"))
            credit = sum((self._decimal(entry.credit) for entry in ledger_entries), Decimal("0"))
            if debit != credit:
                raise ExchangeRevaluationError("Las entradas de revalorizacion no balancean por libro.")

    def _current_ledger_balance(self, candidate: RevaluationCandidate, ledger: Book) -> Decimal:
        original = self._source_gl_balance(candidate, ledger)
        revaluations = self._active_revaluation_balance(candidate, ledger)
        return (original + revaluations).quantize(Decimal("0.0001"))

    def _source_gl_balance(self, candidate: RevaluationCandidate, ledger: Book) -> Decimal:
        query = (
            select(GLEntry)
            .filter_by(
                company=ledger.entity,
                ledger_id=ledger.id,
                account_id=candidate.account_id,
                voucher_type=candidate.source_document_type,
                voucher_id=candidate.source_document_id,
                is_cancelled=False,
            )
            .where(GLEntry.is_reversal.is_(False))
        )
        if candidate.bank_account_id:
            query = (
                select(GLEntry)
                .filter_by(
                    company=ledger.entity,
                    ledger_id=ledger.id,
                    account_id=candidate.account_id,
                    bank_account_id=candidate.bank_account_id,
                    is_cancelled=False,
                )
                .where(GLEntry.is_reversal.is_(False))
                .where(GLEntry.posting_date <= (candidate.as_of_date or date.today()))
                .where(GLEntry.voucher_type != EXCHANGE_REVALUATION_ENTITY_TYPE)
            )
        balance = self._normal_balance(database.session.execute(query).scalars().all(), candidate.normal_balance)
        if candidate.total_amount_original > 0 and candidate.open_amount_original < candidate.total_amount_original:
            proportion = candidate.open_amount_original / candidate.total_amount_original
            return (balance * proportion).quantize(Decimal("0.0001"))
        return balance

    def _active_revaluation_balance(self, candidate: RevaluationCandidate, ledger: Book) -> Decimal:
        items = (
            database.session.execute(
                select(ExchangeRevaluationItem)
                .join(ExchangeRevaluation, ExchangeRevaluation.id == ExchangeRevaluationItem.revaluation_id)
                .filter(ExchangeRevaluation.status == EXCHANGE_REVALUATION_STATUS_POSTED)
                .filter(ExchangeRevaluationItem.source_document_type == candidate.source_document_type)
                .filter(ExchangeRevaluationItem.source_document_id == candidate.source_document_id)
                .filter(ExchangeRevaluationItem.account_id == candidate.account_id)
                .filter(ExchangeRevaluationItem.ledger_id == ledger.id)
            )
            .scalars()
            .all()
        )
        entry_ids = [item.journal_line_id for item in items if item.journal_line_id]
        if not entry_ids:
            return Decimal("0")
        entries = (
            database.session.execute(select(GLEntry).where(GLEntry.id.in_(entry_ids)).where(GLEntry.is_cancelled.is_(False)))
            .scalars()
            .all()
        )
        balance = self._normal_balance(entries, candidate.normal_balance)
        if candidate.total_amount_original > 0 and candidate.open_amount_original < candidate.total_amount_original:
            proportion = candidate.open_amount_original / candidate.total_amount_original
            return (balance * proportion).quantize(Decimal("0.0001"))
        return balance

    def _normal_balance(self, entries: Sequence[GLEntry], normal_balance: str) -> Decimal:
        debit = sum((self._decimal(entry.debit) for entry in entries), Decimal("0"))
        credit = sum((self._decimal(entry.credit) for entry in entries), Decimal("0"))
        if normal_balance == "credit":
            return credit - debit
        return debit - credit

    def _bank_original_balance(self, account: BankAccount, as_of_date: date) -> Decimal:
        entries = (
            database.session.execute(
                select(GLEntry)
                .filter_by(
                    company=account.company,
                    account_id=account.gl_account_id,
                    bank_account_id=account.id,
                    is_cancelled=False,
                )
                .where(GLEntry.is_reversal.is_(False))
                .where(GLEntry.posting_date <= as_of_date)
                .where(GLEntry.voucher_type != EXCHANGE_REVALUATION_ENTITY_TYPE)
            )
            .scalars()
            .all()
        )
        debit = sum((self._decimal(entry.debit_in_account_currency) for entry in entries), Decimal("0"))
        credit = sum((self._decimal(entry.credit_in_account_currency) for entry in entries), Decimal("0"))
        return (debit - credit).quantize(Decimal("0.0001"))

    def _closing_rate(self, origin: str, destination: str, closing_date: date) -> Decimal:
        if origin == destination:
            return Decimal("1")

        def _rate(pair_origin: str, pair_destination: str, target_date: date) -> Decimal | None:
            rate = (
                database.session.execute(
                    select(ExchangeRate).filter_by(origin=pair_origin, destination=pair_destination, date=target_date)
                )
                .scalars()
                .first()
            )
            if rate is not None:
                return self._decimal(rate.rate)
            return None

        def _nearest_rate(origin: str, destination: str, target_date: date) -> Decimal | None:
            before = (
                database.session.execute(
                    select(ExchangeRate)
                    .filter_by(origin=origin, destination=destination)
                    .where(ExchangeRate.date <= target_date)
                    .order_by(ExchangeRate.date.desc())
                )
                .scalars()
                .first()
            )
            if before is not None:
                return self._decimal(before.rate)
            after = (
                database.session.execute(
                    select(ExchangeRate)
                    .filter_by(origin=origin, destination=destination)
                    .where(ExchangeRate.date >= target_date)
                    .order_by(ExchangeRate.date.asc())
                )
                .scalars()
                .first()
            )
            if after is not None:
                return self._decimal(after.rate)
            return None

        rate_val = _rate(origin, destination, closing_date)
        if rate_val is not None:
            return rate_val

        rate_val = _nearest_rate(origin, destination, closing_date)
        if rate_val is not None:
            return rate_val

        rate_val = _rate(destination, origin, closing_date)
        if rate_val is not None:
            if rate_val == 0:
                raise ExchangeRevaluationError("El tipo de cambio no puede ser cero.")
            return (Decimal("1") / rate_val).quantize(Decimal("0.000000001"))

        rate_val = _nearest_rate(destination, origin, closing_date)
        if rate_val is not None:
            if rate_val == 0:
                raise ExchangeRevaluationError("El tipo de cambio no puede ser cero.")
            return (Decimal("1") / rate_val).quantize(Decimal("0.000000001"))

        raise ExchangeRevaluationError(f"Falta tasa de cierre para {origin} -> {destination} en {closing_date}.")

    def _party_account(self, party_id: str | None, company: str, *, receivable: bool) -> str | None:
        if party_id:
            mapping = (
                database.session.execute(select(PartyAccount).filter_by(party_id=party_id, company=company)).scalars().first()
            )
            if mapping:
                account_id = mapping.receivable_account_id if receivable else mapping.payable_account_id
                if account_id:
                    return str(account_id)
        defaults = database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalars().first()
        if defaults is None:
            return None
        return str(defaults.default_receivable if receivable else defaults.default_payable)

    def _document_currency(self, document: Any, company: str) -> str:
        entity = database.session.get(Entity, company)
        return str(
            getattr(document, "transaction_currency", None)
            or getattr(document, "base_currency", None)
            or getattr(entity, "currency", None)
        )

    def _account_code(self, account_id: str) -> str | None:
        account = database.session.get(Accounts, account_id)
        return str(account.code) if account and account.code else None

    def _period_ids(self, company: str, posting_date: date) -> tuple[str | None, str | None]:
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
        if period is None:
            return None, None
        return period.id, period.fiscal_year_id

    def _create_journal(self, run: ExchangeRevaluation, user_id: str | None, *, reversal: bool = False) -> ComprobanteContable:
        journal = ComprobanteContable(
            entity=run.company,
            user_id=user_id,
            date=self._date_for(run),
            reference=run.document_no or run.id,
            memo=("Reversion " if reversal else "") + "Revalorizacion cambiaria",
            status="submitted",
            voucher_type=EXCHANGE_REVALUATION_ENTITY_TYPE,
            voucher_id=run.id,
            transaction_currency=None,
        )
        database.session.add(journal)
        database.session.flush()
        return journal

    def _assign_identifier(self, run: ExchangeRevaluation) -> None:
        try:
            assign_document_identifier(
                document=run,
                entity_type=EXCHANGE_REVALUATION_ENTITY_TYPE,
                posting_date_raw=run.posting_date,
                naming_series_id=run.naming_series_id,
            )
        except IdentifierConfigurationError:
            run.document_no = f"{run.company}-EXR-{run.year}-{str(run.month).zfill(2)}-{run.id[-6:]}"

    def _active_run_entries(self, run_id: str) -> list[GLEntry]:
        return list(
            database.session.execute(
                select(GLEntry)
                .filter_by(
                    voucher_type=EXCHANGE_REVALUATION_ENTITY_TYPE,
                    voucher_id=run_id,
                    is_reversal=False,
                    is_cancelled=False,
                )
                .order_by(GLEntry.id)
            )
            .scalars()
            .all()
        )

    def _date_for(self, run: ExchangeRevaluation) -> date:
        posting_date = run.posting_date or run.run_date
        if not posting_date:
            raise ExchangeRevaluationError("La revalorizacion no tiene fecha contable.")
        return posting_date

    def _decimal(self, value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError) as exc:
            raise ExchangeRevaluationError("Valor numerico invalido en revalorizacion.") from exc
