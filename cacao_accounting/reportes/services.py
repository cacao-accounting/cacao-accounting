# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de reportes operativos derivados de GL, stock ledger y conciliaciones."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select

from cacao_accounting.compras.purchase_reconciliation_service import get_purchase_reconciliation_pending
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Batch,
    Book,
    GLEntry,
    PaymentReference,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    Reconciliation,
    ReconciliationItem,
    SalesInvoice,
    SalesInvoiceItem,
    SerialNumber,
    StockBin,
    StockLedgerEntry,
    StockValuationLayer,
    database,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount


@dataclass(frozen=True)
class SubledgerFilters:
    """Filtros para subledger AR/AP."""

    company: str
    party_type: str
    party_id: str | None = None
    as_of_date: date | None = None


@dataclass(frozen=True)
class AgingFilters:
    """Filtros para reporte aging."""

    company: str
    party_type: str
    as_of_date: date
    party_id: str | None = None


@dataclass(frozen=True)
class KardexFilters:
    """Filtros para Kardex."""

    company: str
    item_code: str | None = None
    warehouse: str | None = None
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class OperationalReportFilters:
    """Filtros comunes para reportes operativos."""

    company: str
    date_from: date | None = None
    date_to: date | None = None
    party_id: str | None = None
    item_code: str | None = None
    warehouse: str | None = None


@dataclass(frozen=True)
class FinancialReportFilters:
    """Filtros comunes para reportes financieros del libro mayor."""

    company: str
    ledger: str | None = None
    accounting_period: str | None = None
    voucher_number: str | None = None
    account_code: str | None = None
    account_from: str | None = None
    account_to: str | None = None
    cost_center_code: str | None = None
    unit_code: str | None = None
    project_code: str | None = None
    party_type: str | None = None
    party_id: str | None = None
    voucher_type: str | None = None
    status: str | None = None
    include_running_balance: bool = False
    include_closing: bool = False
    page: int = 1
    page_size: int = 100
    sort_by: str = "posting_date"
    sort_dir: str = "asc"
    export_all: bool = False


@dataclass(frozen=True)
class ReportRow:
    """Fila generica de reporte."""

    values: dict[str, Any]


@dataclass(frozen=True)
class PaginatedReport:
    """Reporte paginado simple."""

    rows: list[ReportRow]
    totals: dict[str, Decimal]
    columns: list[str] | None = None
    total_rows: int = 0
    page: int = 1
    page_size: int = 0
    ledger_currency: str | None = None


@dataclass(frozen=True)
class AgingReport:
    """Reporte aging con buckets fijos."""

    rows: list[ReportRow]
    totals: dict[str, Decimal]


def _decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_account_classification(account: Accounts | None) -> str:
    """Normaliza aliases de clasificaciones de cuentas para reportes financieros."""
    raw_classification = (account.classification or "").strip().lower() if account else ""
    aliases = {
        "activos": "activo",
        "pasivos": "pasivo",
        "ingresos": "ingreso",
        "costos": "costo",
        "gastos": "gasto",
        "assets": "asset",
        "liabilities": "liability",
        "equities": "equity",
        "incomes": "income",
        "costs": "cost",
        "expenses": "expense",
    }
    return aliases.get(raw_classification, raw_classification)


def _payment_allocations(reference_type: str, reference_id: str, as_of_date: date | None) -> Decimal:
    query = select(PaymentReference).filter_by(reference_type=reference_type, reference_id=reference_id)
    if as_of_date is not None:
        query = query.where(PaymentReference.allocation_date <= as_of_date)
    return sum(
        (_decimal_value(reference.allocated_amount) for reference in database.session.execute(query).scalars().all()),
        Decimal("0"),
    )


def get_ar_ap_subledger(filters: SubledgerFilters) -> PaginatedReport:
    """Devuelve subledger AR/AP basado en documentos y aplicaciones de pago."""
    if filters.party_type == "customer":
        document_type = "sales_invoice"
        document_model = SalesInvoice
        query = select(SalesInvoice).filter_by(company=filters.company)
        if filters.party_id:
            query = query.filter_by(customer_id=filters.party_id)
    elif filters.party_type == "supplier":
        document_type = "purchase_invoice"
        document_model = PurchaseInvoice
        query = select(PurchaseInvoice).filter_by(company=filters.company)
        if filters.party_id:
            query = query.filter_by(supplier_id=filters.party_id)
    else:
        raise ValueError("El subledger solo soporta customer o supplier.")

    if filters.as_of_date is not None:
        query = query.where(document_model.posting_date <= filters.as_of_date)

    rows: list[ReportRow] = []
    total_original = Decimal("0")
    total_paid = Decimal("0")
    total_outstanding = Decimal("0")
    for document in database.session.execute(query.order_by(document_model.posting_date)).scalars():
        original = _decimal_value(document.grand_total)
        paid = _payment_allocations(document_type, document.id, filters.as_of_date)
        outstanding = compute_outstanding_amount(document, as_of_date=filters.as_of_date)
        total_original += original
        total_paid += paid
        total_outstanding += outstanding
        rows.append(
            ReportRow(
                values={
                    "document_type": document_type,
                    "document_id": document.id,
                    "document_no": getattr(document, "document_no", None) or document.id,
                    "posting_date": document.posting_date,
                    "party_id": getattr(document, "customer_id", None) or getattr(document, "supplier_id", None),
                    "original_amount": original,
                    "paid_amount": paid,
                    "outstanding_amount": outstanding,
                }
            )
        )

    return PaginatedReport(
        rows=rows,
        totals={
            "original_amount": total_original,
            "paid_amount": total_paid,
            "outstanding_amount": total_outstanding,
        },
    )


def get_aging_report(filters: AgingFilters) -> AgingReport:
    """Devuelve aging AR/AP con buckets fijos."""
    subledger = get_ar_ap_subledger(
        SubledgerFilters(
            company=filters.company,
            party_type=filters.party_type,
            party_id=filters.party_id,
            as_of_date=filters.as_of_date,
        )
    )
    bucket_totals = {
        "0_30": Decimal("0"),
        "31_60": Decimal("0"),
        "61_90": Decimal("0"),
        "over_90": Decimal("0"),
    }
    rows: list[ReportRow] = []
    for row in subledger.rows:
        outstanding = _decimal_value(row.values["outstanding_amount"])
        if outstanding <= 0:
            continue
        days = (filters.as_of_date - row.values["posting_date"]).days
        bucket = "0_30"
        if days > 90:
            bucket = "over_90"
        elif days > 60:
            bucket = "61_90"
        elif days > 30:
            bucket = "31_60"
        bucket_totals[bucket] += outstanding
        values = dict(row.values)
        values["days"] = days
        values["bucket"] = bucket
        rows.append(ReportRow(values=values))
    return AgingReport(rows=rows, totals=bucket_totals)


def get_kardex(filters: KardexFilters) -> PaginatedReport:
    """Devuelve Kardex desde StockLedgerEntry."""
    query = select(StockLedgerEntry).filter_by(company=filters.company, is_cancelled=False)
    if filters.item_code:
        query = query.filter_by(item_code=filters.item_code)
    if filters.warehouse:
        query = query.filter_by(warehouse=filters.warehouse)
    if filters.date_from:
        query = query.where(StockLedgerEntry.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(StockLedgerEntry.posting_date <= filters.date_to)

    rows: list[ReportRow] = []
    total_in = Decimal("0")
    total_out = Decimal("0")
    total_value = Decimal("0")
    for entry in database.session.execute(
        query.order_by(StockLedgerEntry.posting_date, StockLedgerEntry.created, StockLedgerEntry.id)
    ).scalars():
        qty = _decimal_value(entry.qty_change)
        incoming = qty if qty > 0 else Decimal("0")
        outgoing = abs(qty) if qty < 0 else Decimal("0")
        value_change = _decimal_value(entry.stock_value_difference)
        total_in += incoming
        total_out += outgoing
        total_value += value_change
        rows.append(
            ReportRow(
                values={
                    "posting_date": entry.posting_date,
                    "item_code": entry.item_code,
                    "warehouse": entry.warehouse,
                    "voucher_type": entry.voucher_type,
                    "voucher_id": entry.voucher_id,
                    "incoming_qty": incoming,
                    "outgoing_qty": outgoing,
                    "balance_qty": _decimal_value(entry.qty_after_transaction),
                    "valuation_rate": _decimal_value(entry.valuation_rate),
                    "value_change": value_change,
                    "stock_value": _decimal_value(entry.stock_value),
                }
            )
        )
    return PaginatedReport(
        rows=rows,
        totals={"incoming_qty": total_in, "outgoing_qty": total_out, "value_change": total_value},
    )


def get_reconciliation_report(company: str, as_of_date: date | None = None) -> PaginatedReport:
    """Devuelve reconciliaciones bancarias y conciliaciones de compras pendientes."""
    query = (
        select(Reconciliation, ReconciliationItem)
        .join(
            ReconciliationItem,
            ReconciliationItem.reconciliation_id == Reconciliation.id,
        )
        .filter(Reconciliation.company == company)
    )
    if as_of_date:
        query = query.where(Reconciliation.recon_date <= as_of_date)

    rows = [
        ReportRow(
            values={
                "reconciliation_id": reconciliation.id,
                "recon_date": reconciliation.recon_date,
                "recon_type": reconciliation.recon_type,
                "source_type": item.source_type or item.reference_type,
                "source_id": item.source_id or item.reference_id,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "amount": _decimal_value(item.allocated_amount or item.amount),
                "status": item.status,
            }
        )
        for reconciliation, item in database.session.execute(query).all()
    ]
    bank_total = sum((_decimal_value(row.values["amount"]) for row in rows), Decimal("0"))
    purchase_pending = get_purchase_reconciliation_pending(company=company, as_of_date=as_of_date)
    for pending in purchase_pending:
        rows.append(
            ReportRow(
                values={
                    "reconciliation_id": pending.purchase_receipt_id,
                    "recon_date": as_of_date,
                    "recon_type": "purchase_reconciliation",
                    "source_type": "purchase_receipt_item",
                    "source_id": pending.purchase_receipt_item_id,
                    "target_type": None,
                    "target_id": None,
                    "amount": pending.pending_amount,
                    "status": pending.status,
                }
            )
        )
    return PaginatedReport(
        rows=rows,
        totals={
            "bank_reconciled_amount": bank_total,
            "purchase_pending_amount": sum((row.pending_amount for row in purchase_pending), Decimal("0")),
        },
    )


def _resolve_ledger(company: str, ledger: str | None) -> Book | None:
    query = select(Book).where(Book.entity == company)
    if ledger:
        query = query.where(or_(Book.id == ledger, Book.code == ledger))
    else:
        query = query.order_by(Book.is_primary.desc(), Book.default.desc(), Book.created.asc())
    return database.session.execute(query).scalars().first()


def _period_bounds(company: str, period_name: str | None) -> tuple[date | None, date | None, AccountingPeriod | None]:
    if not period_name:
        return None, None, None
    period = (
        database.session.execute(
            select(AccountingPeriod).where(AccountingPeriod.entity == company, AccountingPeriod.name == period_name)
        )
        .scalars()
        .first()
    )
    if period is None:
        return None, None, None
    return period.start, period.end, period


def _apply_gl_filters(query: Any, filters: FinancialReportFilters, period_start: date | None, period_end: date | None) -> Any:
    query = query.where(GLEntry.company == filters.company)
    if not filters.include_closing:
        query = query.where(GLEntry.is_fiscal_year_closing.is_(False))
    if filters.voucher_number:
        like_value = f"%{filters.voucher_number.strip()}%"
        query = query.where(GLEntry.document_no.ilike(like_value))
    if filters.account_code:
        query = query.where(GLEntry.account_code == filters.account_code)
    if filters.account_from:
        query = query.where(GLEntry.account_code >= filters.account_from)
    if filters.account_to:
        query = query.where(GLEntry.account_code <= filters.account_to)
    if filters.cost_center_code:
        query = query.where(GLEntry.cost_center_code == filters.cost_center_code)
    if filters.unit_code:
        query = query.where(GLEntry.unit_code == filters.unit_code)
    if filters.project_code:
        query = query.where(GLEntry.project_code == filters.project_code)
    if filters.party_type:
        query = query.where(GLEntry.party_type == filters.party_type)
    if filters.party_id:
        query = query.where(GLEntry.party_id == filters.party_id)
    if filters.voucher_type:
        query = query.where(GLEntry.voucher_type == filters.voucher_type)
    if filters.status == "cancelled":
        query = query.where(GLEntry.is_cancelled.is_(True))
    elif filters.status in {"submitted", "posted"}:
        query = query.where(GLEntry.is_cancelled.is_(False))
    if period_start:
        query = query.where(GLEntry.posting_date >= period_start)
    if period_end:
        query = query.where(GLEntry.posting_date <= period_end)
    return query


def _sorted_gl_query(query: Any, sort_by: str, sort_dir: str) -> Any:
    sort_columns = {
        "posting_date": GLEntry.posting_date,
        "document_no": GLEntry.document_no,
        "account_code": GLEntry.account_code,
        "debit": GLEntry.debit,
        "credit": GLEntry.credit,
        "created": GLEntry.created,
    }
    column = sort_columns.get(sort_by, GLEntry.posting_date)
    direction = column.desc() if sort_dir.lower() == "desc" else column.asc()
    return query.order_by(direction, GLEntry.id.asc())


def get_account_movement_detail(filters: FinancialReportFilters) -> PaginatedReport:
    """Detalle de movimiento contable (diario + mayor) desde GL."""
    period_start, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={"debit": Decimal("0"), "credit": Decimal("0")}, columns=[])

    query = (
        select(GLEntry, Accounts, AccountingPeriod)
        .join(
            Accounts,
            (Accounts.id == GLEntry.account_id),
            isouter=True,
        )
        .join(
            AccountingPeriod,
            (AccountingPeriod.id == GLEntry.accounting_period_id),
            isouter=True,
        )
    )
    query = _apply_gl_filters(query, filters, period_start, period_end).where(GLEntry.ledger_id == selected_ledger.id)
    query = _sorted_gl_query(query, filters.sort_by, filters.sort_dir)

    count_query = query.order_by(None).with_only_columns(func.count())
    total_rows = database.session.execute(count_query).scalar_one()
    page = max(filters.page, 1)
    page_size = max(filters.page_size, 1)
    row_offset = (page - 1) * page_size
    display_from_index = 0
    if not filters.export_all:
        if filters.include_running_balance and row_offset > 0:
            query = query.limit(row_offset + page_size)
            display_from_index = row_offset
        else:
            query = query.offset(row_offset).limit(page_size)

    running_per_account: dict[str, Decimal] = defaultdict(Decimal)
    rows: list[ReportRow] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for index, (entry, account, period) in enumerate(database.session.execute(query).all()):
        account_code = entry.account_code or (account.code if account else None) or ""
        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        running_per_account[account_code] += debit - credit
        if index < display_from_index:
            continue
        total_debit += debit
        total_credit += credit
        row_values: dict[str, Any] = {
            "posting_date": entry.posting_date,
            "accounting_period": period.name if period else None,
            "document_no": entry.document_no or entry.voucher_id,
            "voucher_type": entry.voucher_type,
            "account_code": account_code,
            "account_name": account.name if account else None,
            "debit": debit,
            "credit": credit,
            "currency": selected_ledger.currency or entry.company_currency or entry.account_currency,
            "ledger": selected_ledger.code,
            "company": entry.company,
            "cost_center": entry.cost_center_code,
            "unit": entry.unit_code,
            "project": entry.project_code,
            "party_type": entry.party_type,
            "party_id": entry.party_id,
            "line_comment": entry.remarks,
            "created_by": entry.created_by,
            "created_at": entry.created,
            "voucher_status": "cancelled" if entry.is_cancelled else "submitted",
        }
        if filters.include_running_balance:
            row_values["running_balance"] = running_per_account[account_code]
        rows.append(ReportRow(values=row_values))

    columns = list(rows[0].values.keys()) if rows else []
    return PaginatedReport(
        rows=rows,
        totals={"debit": total_debit, "credit": total_credit, "difference": total_debit - total_credit},
        columns=columns,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        ledger_currency=selected_ledger.currency,
    )


def get_account_summary_report(filters: FinancialReportFilters) -> PaginatedReport:
    """Resumen de movimientos por cuenta contable (Sábana analítica)."""
    period_start, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={}, columns=[])

    # Siempre unimos con Accounts para obtener metadatos de la cuenta
    base_query = select(GLEntry, Accounts).join(Accounts, Accounts.id == GLEntry.account_id, isouter=True)
    base_query = _apply_gl_filters(base_query, filters, None, None).where(GLEntry.ledger_id == selected_ledger.id)

    # El requerimiento sugiere que puede haber agrupaciones dinámicas (Cuenta, Centro de Costo, Proyecto, etc.)
    # Por ahora implementamos la agrupación base por cuenta, pero permitimos extraer metadatos.
    entries = database.session.execute(base_query).all()

    account_totals: dict[str, dict[str, Any]] = {}
    for entry, account in entries:
        if period_start and entry.posting_date < period_start:
            bucket = "opening"
        elif period_end and entry.posting_date > period_end:
            continue
        else:
            bucket = "movement"

        account_code = entry.account_code or (account.code if account else "")
        # Podemos extender la llave de agrupación si en el futuro se requiere soportar
        # agrupaciones múltiples (ej. Cuenta + Centro de Costos) en una sola fila.
        group_key = account_code

        row = account_totals.setdefault(
            group_key,
            {
                "account_code": account_code,
                "account_name": account.name if account else None,
                "account_type": account.account_type if account else None,
                "classification": _normalize_account_classification(account),
                "currency": account.currency if account else None,
                "opening_balance": Decimal("0"),
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "movement_count": 0,
                "first_movement": None,
                "last_movement": None,
                "level": account_code.count(".") + 1 if account_code else 1,
            },
        )

        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)

        if bucket == "opening":
            row["opening_balance"] += debit - credit
        else:
            row["debit"] += debit
            row["credit"] += credit
            row["movement_count"] += 1
            if row["first_movement"] is None or entry.posting_date < row["first_movement"]:
                row["first_movement"] = entry.posting_date
            if row["last_movement"] is None or entry.posting_date > row["last_movement"]:
                row["last_movement"] = entry.posting_date

    rows = []
    total_opening = Decimal("0")
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    total_ending = Decimal("0")

    for group_key in sorted(account_totals):
        values = account_totals[group_key]
        ending = values["opening_balance"] + values["debit"] - values["credit"]
        total_opening += values["opening_balance"]
        total_debit += values["debit"]
        total_credit += values["credit"]
        total_ending += ending

        rows.append(
            ReportRow(
                values={
                    "account_code": values["account_code"],
                    "account_name": values["account_name"],
                    "account_type": values["account_type"],
                    "classification": values["classification"],
                    "currency": values["currency"],
                    "opening_balance": values["opening_balance"],
                    "debit": values["debit"],
                    "credit": values["credit"],
                    "ending_balance": ending,
                    "movement_count": values["movement_count"],
                    "first_movement": values["first_movement"],
                    "last_movement": values["last_movement"],
                    "level": values["level"],
                }
            )
        )

    return PaginatedReport(
        rows=rows,
        totals={
            "opening_balance": total_opening,
            "debit": total_debit,
            "credit": total_credit,
            "ending_balance": total_ending,
            "difference": total_debit - total_credit,
        },
        columns=list(rows[0].values.keys()) if rows else [],
        total_rows=len(rows),
        page=1,
        page_size=len(rows),
        ledger_currency=selected_ledger.currency,
    )


def get_trial_balance_report(filters: FinancialReportFilters) -> PaginatedReport:
    """Balanza de comprobación por cuenta contable."""
    period_start, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={}, columns=[])

    base_query = select(GLEntry, Accounts).join(Accounts, Accounts.id == GLEntry.account_id, isouter=True)
    base_query = _apply_gl_filters(base_query, filters, None, None).where(GLEntry.ledger_id == selected_ledger.id)
    entries = database.session.execute(_sorted_gl_query(base_query, "account_code", "asc")).all()

    account_totals: dict[str, dict[str, Any]] = {}
    for entry, account in entries:
        if period_start and entry.posting_date < period_start:
            bucket = "opening"
        elif period_end and entry.posting_date > period_end:
            continue
        else:
            bucket = "movement"
        account_code = entry.account_code or (account.code if account else "")
        row = account_totals.setdefault(
            account_code,
            {
                "account_code": account_code,
                "account_name": account.name if account else None,
                "opening": Decimal("0"),
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "level": account_code.count(".") + 1 if account_code else 1,
            },
        )
        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        if bucket == "opening":
            row["opening"] += debit - credit
        else:
            row["debit"] += debit
            row["credit"] += credit

    rows = []
    total_opening = Decimal("0")
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    total_ending = Decimal("0")
    for account_code in sorted(account_totals):
        values = account_totals[account_code]
        ending = values["opening"] + values["debit"] - values["credit"]
        total_opening += values["opening"]
        total_debit += values["debit"]
        total_credit += values["credit"]
        total_ending += ending
        rows.append(
            ReportRow(
                values={
                    "account_code": values["account_code"],
                    "account_name": values["account_name"],
                    "opening_balance": values["opening"],
                    "debit": values["debit"],
                    "credit": values["credit"],
                    "ending_balance": ending,
                    "level": values["level"],
                }
            )
        )
    return PaginatedReport(
        rows=rows,
        totals={
            "opening_balance": total_opening,
            "debit": total_debit,
            "credit": total_credit,
            "ending_balance": total_ending,
            "difference": total_debit - total_credit,
        },
        columns=list(rows[0].values.keys()) if rows else [],
        total_rows=len(rows),
        page=1,
        page_size=len(rows),
        ledger_currency=selected_ledger.currency,
    )


def get_income_statement_report(filters: FinancialReportFilters) -> PaginatedReport:
    """Estado de resultado acumulado por clasificación contable."""
    _, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={}, columns=[])
    base_query = select(GLEntry, Accounts).join(Accounts, Accounts.id == GLEntry.account_id, isouter=True)
    base_query = _apply_gl_filters(base_query, filters, None, period_end).where(GLEntry.ledger_id == selected_ledger.id)
    summary = {
        "income": Decimal("0"),
        "cost": Decimal("0"),
        "expense": Decimal("0"),
    }
    account_summary: dict[str, dict[str, Any]] = {}
    for entry, account in database.session.execute(base_query).all():
        if account is None:
            continue
        classification = _normalize_account_classification(account)
        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        account_code = account.code or (entry.account_code or "")
        account_name = account.name
        account_bucket = account_summary.setdefault(
            account_code,
            {
                "account_code": account_code,
                "account_name": account_name,
                "section": None,
                "amount": Decimal("0"),
                "level": account_code.count(".") + 1 if account_code else 1,
            },
        )
        if classification in {"ingreso", "income"}:
            amount = credit - debit
            summary["income"] += amount
            account_bucket["section"] = "income"
            account_bucket["amount"] += amount
        elif classification in {"costo", "cost"}:
            amount = debit - credit
            summary["cost"] += amount
            account_bucket["section"] = "cost"
            account_bucket["amount"] += amount
        elif classification in {"gasto", "expense"}:
            amount = debit - credit
            summary["expense"] += amount
            account_bucket["section"] = "expense"
            account_bucket["amount"] += amount
    gross_profit = summary["income"] - summary["cost"]
    operating_profit = gross_profit - summary["expense"]
    rows: list[ReportRow] = []
    for section in ("income", "cost", "expense"):
        section_amount = summary[section]
        rows.append(
            ReportRow({"section": section, "account_code": None, "account_name": None, "amount": section_amount, "level": 0})
        )
        section_rows = [
            row
            for row in account_summary.values()
            if row.get("section") == section and _decimal_value(row.get("amount")) != Decimal("0")
        ]
        for values in sorted(section_rows, key=lambda item: str(item["account_code"])):
            rows.append(
                ReportRow(
                    {
                        "section": section,
                        "account_code": values["account_code"],
                        "account_name": values["account_name"],
                        "amount": values["amount"],
                        "level": values["level"],
                    }
                )
            )
    rows.extend(
        [
            ReportRow(
                {"section": "gross_profit", "account_code": None, "account_name": None, "amount": gross_profit, "level": 0}
            ),
            ReportRow(
                {"section": "net_profit", "account_code": None, "account_name": None, "amount": operating_profit, "level": 0}
            ),
        ]
    )
    return PaginatedReport(
        rows=rows,
        totals={
            "income": summary["income"],
            "cost": summary["cost"],
            "expense": summary["expense"],
            "gross_profit": gross_profit,
            "net_profit": operating_profit,
        },
        columns=["section", "account_code", "account_name", "amount", "level"],
        total_rows=len(rows),
        page=1,
        page_size=len(rows),
        ledger_currency=selected_ledger.currency,
    )


def get_balance_sheet_report(filters: FinancialReportFilters) -> PaginatedReport:
    """Balance general por clasificación Activo/Pasivo/Patrimonio."""
    _, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={}, columns=[])
    base_query = select(GLEntry, Accounts).join(Accounts, Accounts.id == GLEntry.account_id, isouter=True)
    base_query = _apply_gl_filters(base_query, filters, None, period_end).where(GLEntry.ledger_id == selected_ledger.id)

    by_account: dict[str, dict[str, Any]] = {}
    totals = {
        "assets": Decimal("0"),
        "liabilities": Decimal("0"),
        "equity": Decimal("0"),
        "income": Decimal("0"),
        "cost": Decimal("0"),
        "expense": Decimal("0"),
    }
    for entry, account in database.session.execute(base_query).all():
        if account is None:
            continue
        classification = _normalize_account_classification(account)
        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        if classification in {"activo", "asset"}:
            amount = debit - credit
            section = "assets"
        elif classification in {"pasivo", "liability"}:
            amount = credit - debit
            section = "liabilities"
        elif classification in {"patrimonio", "equity"}:
            amount = credit - debit
            section = "equity"
        elif classification in {"ingreso", "income"}:
            totals["income"] += credit - debit
            continue
        elif classification in {"costo", "cost"}:
            totals["cost"] += debit - credit
            continue
        elif classification in {"gasto", "expense"}:
            totals["expense"] += debit - credit
            continue
        else:
            continue
        account_code = account.code or (entry.account_code or "")
        record = by_account.setdefault(
            account_code,
            {
                "section": section,
                "account_code": account_code,
                "account_name": account.name,
                "amount": Decimal("0"),
            },
        )
        record["amount"] += amount
        totals[section] += amount

    period_profit = totals["income"] - totals["cost"] - totals["expense"]
    totals["equity"] += period_profit
    rows = [ReportRow(values=value) for _, value in sorted(by_account.items())]
    rows.append(
        ReportRow(
            values={
                "section": "equity",
                "account_code": None,
                "account_name": "period_profit_summary",
                "amount": period_profit,
            }
        )
    )
    difference = totals["assets"] - (totals["liabilities"] + totals["equity"])
    return PaginatedReport(
        rows=rows,
        totals={
            "assets": totals["assets"],
            "liabilities": totals["liabilities"],
            "equity": totals["equity"],
            "period_profit": period_profit,
            "difference": difference,
        },
        columns=["section", "account_code", "account_name", "amount"],
        total_rows=len(rows),
        page=1,
        page_size=len(rows),
        ledger_currency=selected_ledger.currency,
    )


def get_purchases_by_supplier(filters: OperationalReportFilters) -> PaginatedReport:
    """Compras agregadas por proveedor."""
    query = select(PurchaseInvoice).filter_by(company=filters.company)
    if filters.party_id:
        query = query.filter_by(supplier_id=filters.party_id)
    if filters.date_from:
        query = query.where(PurchaseInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(PurchaseInvoice.posting_date <= filters.date_to)
    totals: dict[str, Decimal] = {}
    for invoice in database.session.execute(query).scalars():
        supplier_id = invoice.supplier_id or ""
        totals[supplier_id] = totals.get(supplier_id, Decimal("0")) + _decimal_value(invoice.grand_total or invoice.total)
    rows = [ReportRow({"supplier_id": supplier_id, "amount": amount}) for supplier_id, amount in sorted(totals.items())]
    return PaginatedReport(rows=rows, totals={"amount": sum(totals.values(), Decimal("0"))})


def get_purchases_by_item(filters: OperationalReportFilters) -> PaginatedReport:
    """Compras agregadas por item."""
    query = (
        select(PurchaseInvoice, PurchaseInvoiceItem)
        .join(PurchaseInvoiceItem, PurchaseInvoiceItem.purchase_invoice_id == PurchaseInvoice.id)
        .filter(PurchaseInvoice.company == filters.company)
    )
    if filters.item_code:
        query = query.filter(PurchaseInvoiceItem.item_code == filters.item_code)
    if filters.date_from:
        query = query.where(PurchaseInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(PurchaseInvoice.posting_date <= filters.date_to)
    totals: dict[str, dict[str, Decimal]] = {}
    for _, item in database.session.execute(query).all():
        row = totals.setdefault(item.item_code, {"qty": Decimal("0"), "amount": Decimal("0")})
        row["qty"] += _decimal_value(item.qty)
        row["amount"] += _decimal_value(item.amount)
    rows = [
        ReportRow({"item_code": item_code, "qty": values["qty"], "amount": values["amount"]})
        for item_code, values in sorted(totals.items())
    ]
    return PaginatedReport(
        rows=rows,
        totals={
            "qty": sum((values["qty"] for values in totals.values()), Decimal("0")),
            "amount": sum((values["amount"] for values in totals.values()), Decimal("0")),
        },
    )


def get_sales_by_customer(filters: OperationalReportFilters) -> PaginatedReport:
    """Ventas agregadas por cliente."""
    query = select(SalesInvoice).filter_by(company=filters.company)
    if filters.party_id:
        query = query.filter_by(customer_id=filters.party_id)
    if filters.date_from:
        query = query.where(SalesInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(SalesInvoice.posting_date <= filters.date_to)
    totals: dict[str, Decimal] = {}
    for invoice in database.session.execute(query).scalars():
        customer_id = invoice.customer_id or ""
        totals[customer_id] = totals.get(customer_id, Decimal("0")) + _decimal_value(invoice.grand_total or invoice.total)
    rows = [ReportRow({"customer_id": customer_id, "amount": amount}) for customer_id, amount in sorted(totals.items())]
    return PaginatedReport(rows=rows, totals={"amount": sum(totals.values(), Decimal("0"))})


def get_sales_by_item(filters: OperationalReportFilters) -> PaginatedReport:
    """Ventas agregadas por item."""
    query = (
        select(SalesInvoice, SalesInvoiceItem)
        .join(SalesInvoiceItem, SalesInvoiceItem.sales_invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.company == filters.company)
    )
    if filters.item_code:
        query = query.filter(SalesInvoiceItem.item_code == filters.item_code)
    if filters.date_from:
        query = query.where(SalesInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(SalesInvoice.posting_date <= filters.date_to)
    totals: dict[str, dict[str, Decimal]] = {}
    for _, item in database.session.execute(query).all():
        row = totals.setdefault(item.item_code, {"qty": Decimal("0"), "amount": Decimal("0")})
        row["qty"] += _decimal_value(item.qty)
        row["amount"] += _decimal_value(item.amount)
    rows = [
        ReportRow({"item_code": item_code, "qty": values["qty"], "amount": values["amount"]})
        for item_code, values in sorted(totals.items())
    ]
    return PaginatedReport(
        rows=rows,
        totals={
            "qty": sum((values["qty"] for values in totals.values()), Decimal("0")),
            "amount": sum((values["amount"] for values in totals.values()), Decimal("0")),
        },
    )


def get_gross_margin(filters: OperationalReportFilters) -> PaginatedReport:
    """Margen bruto basado en GL: ingresos menos COGS."""
    query = select(GLEntry).filter_by(company=filters.company, is_cancelled=False)
    if filters.date_from:
        query = query.where(GLEntry.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(GLEntry.posting_date <= filters.date_to)
    income = Decimal("0")
    cogs = Decimal("0")
    for entry in database.session.execute(query).scalars():
        remarks = (entry.remarks or "").lower()
        if "costo" in remarks:
            cogs += _decimal_value(entry.debit) - _decimal_value(entry.credit)
        elif entry.voucher_type == "sales_invoice":
            income += _decimal_value(entry.credit) - _decimal_value(entry.debit)
    margin = income - cogs
    return PaginatedReport(
        rows=[ReportRow({"income": income, "cogs": cogs, "gross_margin": margin})],
        totals={"income": income, "cogs": cogs, "gross_margin": margin},
    )


def get_stock_balance(filters: OperationalReportFilters) -> PaginatedReport:
    """Existencia actual desde StockBin."""
    query = select(StockBin).filter_by(company=filters.company)
    if filters.item_code:
        query = query.filter_by(item_code=filters.item_code)
    if filters.warehouse:
        query = query.filter_by(warehouse=filters.warehouse)
    rows = [
        ReportRow(
            {
                "item_code": bin_row.item_code,
                "warehouse": bin_row.warehouse,
                "actual_qty": _decimal_value(bin_row.actual_qty),
                "valuation_rate": _decimal_value(bin_row.valuation_rate),
                "stock_value": _decimal_value(bin_row.stock_value),
            }
        )
        for bin_row in database.session.execute(query).scalars()
    ]
    return PaginatedReport(
        rows=rows, totals={"stock_value": sum((_decimal_value(row.values["stock_value"]) for row in rows), Decimal("0"))}
    )


def get_inventory_valuation(filters: OperationalReportFilters) -> PaginatedReport:
    """Valoracion de inventario desde capas de valuacion."""
    query = select(StockValuationLayer).filter_by(company=filters.company)
    if filters.item_code:
        query = query.filter_by(item_code=filters.item_code)
    if filters.warehouse:
        query = query.filter_by(warehouse=filters.warehouse)
    rows = [
        ReportRow(
            {
                "item_code": layer.item_code,
                "warehouse": layer.warehouse,
                "remaining_qty": _decimal_value(layer.remaining_qty),
                "remaining_stock_value": _decimal_value(layer.remaining_stock_value),
            }
        )
        for layer in database.session.execute(query).scalars()
    ]
    return PaginatedReport(
        rows=rows,
        totals={
            "remaining_stock_value": sum((_decimal_value(row.values["remaining_stock_value"]) for row in rows), Decimal("0"))
        },
    )


def get_batch_report(filters: OperationalReportFilters) -> PaginatedReport:
    """Reporte de lotes."""
    query = select(Batch)
    if filters.item_code:
        query = query.filter_by(item_code=filters.item_code)
    rows = [
        ReportRow(
            {
                "item_code": batch.item_code,
                "batch_no": batch.batch_no,
                "expiry_date": batch.expiry_date,
                "is_active": batch.is_active,
            }
        )
        for batch in database.session.execute(query).scalars()
    ]
    return PaginatedReport(rows=rows, totals={"count": Decimal(len(rows))})


def get_serial_report(filters: OperationalReportFilters) -> PaginatedReport:
    """Reporte de numeros de serie."""
    query = select(SerialNumber)
    if filters.item_code:
        query = query.filter_by(item_code=filters.item_code)
    if filters.warehouse:
        query = query.filter_by(warehouse=filters.warehouse)
    rows = [
        ReportRow(
            {
                "item_code": serial.item_code,
                "serial_no": serial.serial_no,
                "status": serial.serial_status,
                "warehouse": serial.warehouse,
            }
        )
        for serial in database.session.execute(query).scalars()
    ]
    return PaginatedReport(rows=rows, totals={"count": Decimal(len(rows))})
