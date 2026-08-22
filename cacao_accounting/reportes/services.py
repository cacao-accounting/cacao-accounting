# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicios de reportes operativos derivados de GL, stock ledger y conciliaciones."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Sequence, cast

from sqlalchemy import and_, func, or_, select

from cacao_accounting.compras.purchase_reconciliation_service import get_purchase_reconciliation_pending
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Batch,
    BankAccount,
    BankTransaction,
    Book,
    Budget,
    BudgetLine,
    CompanyDefaultAccount,
    CompanyParty,
    CostCenter,
    DocumentRelation,
    Entity,
    ExchangeRate,
    FiscalYear,
    GLEntry,
    Item,
    PaymentReference,
    PaymentEntry,
    PaymentTerms,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    Reconciliation,
    ReconciliationItem,
    SalesInvoice,
    SalesInvoiceItem,
    SerialNumber,
    StockBin,
    StockEntry,
    StockEntryItem,
    StockLedgerEntry,
    StockValuationLayer,
    WarehouseCompanyAccount,
    database,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount
from cacao_accounting.ledger_queries import exclude_cancelled_gl_entries, exclude_cancelled_stock_entries, primary_ledger_id


@dataclass(frozen=True)
class SubledgerFilters:
    """Filtros para subledger AR/AP."""

    company: str
    party_type: str
    party_id: str | None = None
    as_of_date: date | None = None
    include_returns: bool = True
    page: int = 1
    page_size: int = 100


@dataclass(frozen=True)
class AgingFilters:
    """Filtros para reporte aging."""

    company: str
    party_type: str
    as_of_date: date
    party_id: str | None = None
    include_returns: bool = True


@dataclass(frozen=True)
class MaturityFilters:
    """Filtros para cronograma de vencimientos calculado desde términos de pago."""

    company: str
    as_of_date: date
    party_type: str | None = None
    party_id: str | None = None
    horizon_days: int = 365
    page: int = 1
    page_size: int = 100


@dataclass(frozen=True)
class KardexFilters:
    """Filtros para Kardex."""

    company: str
    item_code: str | None = None
    warehouse: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    page: int = 1
    page_size: int = 100


@dataclass(frozen=True)
class BankingFilters:
    """Filtros para reportes bancarios."""

    company: str
    bank_account_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    as_of_date: date | None = None
    page: int = 1
    page_size: int = 100


@dataclass(frozen=True)
class OperationalReportFilters:
    """Filtros comunes para reportes operativos."""

    company: str
    date_from: date | None = None
    date_to: date | None = None
    party_id: str | None = None
    item_code: str | None = None
    warehouse: str | None = None
    page: int = 1
    page_size: int = 100


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
    include_cancellations: bool = False
    include_running_balance: bool = False
    include_closing: bool = False
    page: int = 1
    page_size: int = 100
    sort_by: str = "posting_date"
    sort_dir: str = "asc"
    export_all: bool = False
    include_descendants: bool = False
    budget_code: str | None = None


@dataclass(frozen=True)
class ReconciliationFilters:
    """Dimensiones de la matriz independiente de submayores contra GL."""

    company: str
    ledger: str | None = None
    accounting_period: str | None = None
    as_of_date: date | None = None
    currency: str | None = None


@dataclass(frozen=True)
class ReportRow:
    """Fila generica de reporte."""

    values: dict[str, Any]


@dataclass(frozen=True)
class PaginatedReport:
    """Reporte paginado simple."""

    rows: list[ReportRow]
    totals: dict[str, Any]
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


def _invoice_report_amount(invoice: Any) -> Decimal:
    """Return the most precise available base amount for an invoice."""
    amount = invoice.base_grand_total
    if amount is None:
        amount = invoice.base_total
    if amount is None:
        amount = invoice.grand_total or invoice.total
    return _decimal_value(amount)


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


def _payment_allocations(reference_type: str, reference_id: str, company: str, as_of_date: date | None) -> Decimal:
    query = (
        select(PaymentReference)
        .outerjoin(
            DocumentRelation,
            and_(
                DocumentRelation.target_type == "payment_entry",
                DocumentRelation.target_item_id == PaymentReference.id,
            ),
        )
        .join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
        .where(
            PaymentReference.reference_type == reference_type,
            PaymentReference.reference_id == reference_id,
            PaymentEntry.docstatus == 1,
            PaymentEntry.company == company,
            or_(DocumentRelation.company.is_(None), DocumentRelation.company == company),
            or_(DocumentRelation.id.is_(None), DocumentRelation.status == "active"),
        )
        .distinct()
    )
    if as_of_date is not None:
        query = query.where(
            or_(
                PaymentReference.allocation_date.is_(None),
                PaymentReference.allocation_date <= as_of_date,
            )
        )
    return sum(
        (_decimal_value(reference.allocated_amount) for reference in database.session.execute(query).scalars().all()),
        Decimal("0"),
    )


def _document_base_factor(document: Any) -> Decimal:
    """Obtiene el factor histórico de moneda original a moneda base del documento."""
    original = _decimal_value(getattr(document, "grand_total", None) or getattr(document, "total", None))
    base_value = getattr(document, "base_grand_total", None)
    if base_value is None:
        base_value = getattr(document, "base_total", None)
    if base_value is not None and original != 0:
        return _decimal_value(base_value) / original
    rate = _decimal_value(getattr(document, "exchange_rate", None))
    return rate if rate > 0 else Decimal("1")


def _document_sign(document: Any) -> Decimal:
    """Devuelve signo negativo para devoluciones que reducen el submayor."""
    return Decimal("-1") if bool(getattr(document, "is_return", False)) else Decimal("1")


def get_ar_ap_subledger(filters: SubledgerFilters) -> PaginatedReport:
    """Devuelve subledger AR/AP basado en documentos y aplicaciones de pago.

    Todas las columnas comparten el mismo corte: cuando ``as_of_date`` no se
    indica se usa ``date.today()`` de forma explicita para que documentos,
    aplicaciones de pago y outstanding sean consistentes entre si.
    """
    effective_as_of = filters.as_of_date if filters.as_of_date is not None else date.today()
    if filters.party_type == "customer":
        document_type = "sales_invoice"
        document_model = SalesInvoice
        query = select(SalesInvoice).filter_by(company=filters.company, docstatus=1)
        query = query.where(or_(SalesInvoice.reversal_of.is_(None), SalesInvoice.reversal_of == ""))
        if filters.party_id:
            query = query.filter_by(customer_id=filters.party_id)
    elif filters.party_type == "supplier":
        document_type = "purchase_invoice"
        document_model = PurchaseInvoice
        query = select(PurchaseInvoice).filter_by(company=filters.company, docstatus=1)
        query = query.where(or_(PurchaseInvoice.reversal_of.is_(None), PurchaseInvoice.reversal_of == ""))
        if filters.party_id:
            query = query.filter_by(supplier_id=filters.party_id)
    else:
        raise ValueError("El subledger solo soporta customer o supplier.")

    query = query.where(document_model.posting_date <= effective_as_of)
    if not filters.include_returns:
        query = query.where(document_model.is_return.is_(False))

    rows: list[ReportRow] = []
    total_original = Decimal("0")
    total_paid = Decimal("0")
    total_outstanding = Decimal("0")
    party_ids = {
        getattr(document, "customer_id", None) or getattr(document, "supplier_id", None)
        for document in database.session.execute(query).scalars()
    }
    party_labels = {
        party.id: party.code or party.name or party.id
        for party in database.session.execute(select(Party).where(Party.id.in_(party_ids))).scalars()
        if party_ids
    }
    for document in database.session.execute(query.order_by(document_model.posting_date)).scalars():
        sign = _document_sign(document)
        base_factor = _document_base_factor(document)
        original_original_currency = _decimal_value(document.grand_total)
        paid_original_currency = _payment_allocations(document_type, document.id, filters.company, effective_as_of)
        outstanding_original_currency = compute_outstanding_amount(document, as_of_date=effective_as_of)
        original = sign * original_original_currency * base_factor
        paid = sign * paid_original_currency * base_factor
        outstanding = sign * outstanding_original_currency * base_factor
        total_original += original
        total_paid += paid
        total_outstanding += outstanding
        rows.append(
            ReportRow(
                values={
                    "document_type": document_type,
                    "document_id": document.document_no or document.id,
                    "document_no": getattr(document, "document_no", None) or document.id,
                    "posting_date": document.posting_date,
                    "party_id": party_labels.get(
                        getattr(document, "customer_id", None) or getattr(document, "supplier_id", None),
                        getattr(document, "customer_id", None) or getattr(document, "supplier_id", None),
                    ),
                    "original_amount": original,
                    "paid_amount": paid,
                    "outstanding_amount": outstanding,
                    "transaction_currency": document.transaction_currency,
                    "currency": document.base_currency or document.transaction_currency,
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


def _convert_to_ledger_currency(
    amount: Decimal,
    source_currency: str | None,
    target_currency: str | None,
    as_of_date: date,
) -> Decimal:
    """Convierte un importe de ``source_currency`` a ``target_currency`` usando la tasa histórica.

    Si alguna moneda es ``None`` o ambas coinciden, devuelve el importe sin
    conversión.  Si no existe tasa registrada en la fecha exacta, busca la
    tasa inversa y aplica su recíproco.  Si no hay tasa disponible se
    levanta ``ValueError`` para que el llamador pueda decidir si separar
    por moneda.
    """
    if not source_currency or not target_currency or source_currency == target_currency:
        return amount
    rate = (
        database.session.execute(
            select(ExchangeRate).filter_by(origin=source_currency, destination=target_currency, date=as_of_date)
        )
        .scalars()
        .first()
    )
    if rate is not None:
        return amount * _decimal_value(rate.rate)
    inverse = (
        database.session.execute(
            select(ExchangeRate).filter_by(origin=target_currency, destination=source_currency, date=as_of_date)
        )
        .scalars()
        .first()
    )
    if inverse is not None:
        inverse_value = _decimal_value(inverse.rate)
        if inverse_value == 0:
            return Decimal("0")
        return amount / inverse_value
    raise ValueError(f"No existe tipo de cambio de {source_currency} a {target_currency} en {as_of_date}.")


def _reconciliation_gl_amount(
    company: str,
    ledger_id: str,
    account_ids: Sequence[str],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> Decimal:
    """Calcula el saldo GL filtrando todas las dimensiones contables."""
    if not account_ids:
        return Decimal("0")
    query = exclude_cancelled_gl_entries(select(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0))).where(
        GLEntry.company == company,
        GLEntry.ledger_id == ledger_id,
        GLEntry.account_id.in_(list(account_ids)),
    )
    if date_from is not None:
        query = query.where(GLEntry.posting_date >= date_from)
    if date_to is not None:
        query = query.where(GLEntry.posting_date <= date_to)
    if currency:
        # Legacy GL rows did not persist ``company_currency``.  They belong to
        # the selected functional-currency ledger and must remain visible;
        # foreign-currency ledgers are rejected by the caller before this path.
        query = query.where(or_(GLEntry.company_currency == currency, GLEntry.company_currency.is_(None)))
    return _decimal_value(database.session.execute(query).scalar_one())


def _reconciliation_row(
    area: str,
    account_ids: Sequence[str],
    subledger_amount: Decimal,
    gl_amount: Decimal,
    *,
    basis: str,
    currency: str | None,
    note: str | None = None,
) -> ReportRow:
    """Construye una fila con diferencia explícita y trazabilidad de cuentas."""
    difference = subledger_amount - gl_amount
    return ReportRow(
        values={
            "area": area,
            "basis": basis,
            "account_ids": ",".join(sorted(set(account_ids))),
            "subledger_amount": subledger_amount,
            "gl_control_amount": gl_amount,
            "difference": difference,
            "currency": currency or "—",
            "status": "reconciled" if difference == 0 else "difference",
            "note": note or "",
        }
    )


def get_reconciliation_matrix(filters: ReconciliationFilters) -> PaginatedReport:
    """Reconcilia submayores independientes contra GL por compañía, libro y período.

    AR/AP se calculan desde facturas y aplicaciones; inventario desde Stock Ledger;
    impuestos desde impuestos de facturas; bancos se presentan como movimientos
    de pagos, porque el extracto bancario no tiene un saldo contable persistido.
    La cuenta GL siempre se filtra por ``company`` y ``ledger_id`` para impedir
    contaminación entre libros.
    """
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={}, columns=[])
    company_currency = database.session.execute(
        select(Entity.currency).where(Entity.code == filters.company)
    ).scalar_one_or_none()
    comparison_currency = filters.currency or selected_ledger.currency
    ledger_needs_conversion = selected_ledger.currency and company_currency and selected_ledger.currency != company_currency
    _, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    as_of_date = filters.as_of_date or period_end or date.today()
    defaults = database.session.execute(
        select(CompanyDefaultAccount).where(CompanyDefaultAccount.company == filters.company)
    ).scalar_one_or_none()

    def _convert(subledger_amount: Decimal, source_currency: str | None) -> Decimal:
        if not ledger_needs_conversion:
            return subledger_amount
        return _convert_to_ledger_currency(subledger_amount, source_currency, selected_ledger.currency, as_of_date)

    rows: list[ReportRow] = []
    ar_account = str(defaults.default_receivable) if defaults and defaults.default_receivable else None
    ap_account = str(defaults.default_payable) if defaults and defaults.default_payable else None
    ar_subledger = get_ar_ap_subledger(
        SubledgerFilters(company=filters.company, party_type="customer", as_of_date=as_of_date)
    ).totals.get("outstanding_amount", Decimal("0"))
    ap_subledger = get_ar_ap_subledger(
        SubledgerFilters(company=filters.company, party_type="supplier", as_of_date=as_of_date)
    ).totals.get("outstanding_amount", Decimal("0"))
    rows.append(
        _reconciliation_row(
            "AR",
            [ar_account] if ar_account else [],
            _convert(ar_subledger, company_currency),
            _reconciliation_gl_amount(
                filters.company,
                selected_ledger.id,
                [ar_account] if ar_account else [],
                date_to=as_of_date,
                currency=comparison_currency,
            ),
            basis="ending_balance",
            currency=selected_ledger.currency,
            note="Fuente: facturas de venta y aplicaciones de pago.",
        )
    )
    rows.append(
        _reconciliation_row(
            "AP",
            [ap_account] if ap_account else [],
            _convert(-ap_subledger, company_currency),
            _reconciliation_gl_amount(
                filters.company,
                selected_ledger.id,
                [ap_account] if ap_account else [],
                date_to=as_of_date,
                currency=comparison_currency,
            ),
            basis="ending_balance",
            currency=selected_ledger.currency,
            note="Fuente: facturas de compra y aplicaciones de pago; el pasivo se expresa como crédito neto.",
        )
    )

    inventory_accounts = [
        str(account_id)
        for account_id in database.session.execute(
            select(WarehouseCompanyAccount.inventory_account_id).where(
                WarehouseCompanyAccount.company == filters.company,
                WarehouseCompanyAccount.is_active.is_(True),
                WarehouseCompanyAccount.inventory_account_id.is_not(None),
            )
        ).scalars()
        if account_id
    ]
    inventory_query = exclude_cancelled_stock_entries(
        select(func.coalesce(func.sum(StockLedgerEntry.stock_value_difference), 0)).where(
            StockLedgerEntry.company == filters.company,
            StockLedgerEntry.posting_date <= as_of_date,
        )
    )
    inventory_subledger = _decimal_value(database.session.execute(inventory_query).scalar_one())
    rows.append(
        _reconciliation_row(
            "Inventory",
            inventory_accounts,
            _convert(inventory_subledger, company_currency),
            _reconciliation_gl_amount(
                filters.company, selected_ledger.id, inventory_accounts, date_to=as_of_date, currency=comparison_currency
            ),
            basis="ending_balance",
            currency=selected_ledger.currency,
            note="Fuente: Stock Ledger; cuentas derivadas de la configuración activa por bodega.",
        )
    )

    bridge_account = str(defaults.bridge_account_id) if defaults and defaults.bridge_account_id else None
    pending_receipts = get_purchase_reconciliation_pending(company=filters.company, as_of_date=as_of_date)
    pending_grni = sum((pending.pending_amount for pending in pending_receipts), Decimal("0"))
    rows.append(
        _reconciliation_row(
            "GRNI/AP 3-way",
            [bridge_account] if bridge_account else [],
            _convert(-pending_grni, company_currency),
            _reconciliation_gl_amount(
                filters.company,
                selected_ledger.id,
                [bridge_account] if bridge_account else [],
                date_to=as_of_date,
                currency=comparison_currency,
            ),
            basis="ending_balance",
            currency=selected_ledger.currency,
            note="Fuente: recepciones aprobadas pendientes de factura; el puente se expresa como crédito neto.",
        )
    )

    sales_tax_account = (
        str(defaults.default_sales_tax_account_id) if defaults and defaults.default_sales_tax_account_id else None
    )
    purchase_tax_account = (
        str(defaults.default_purchase_tax_account_id) if defaults and defaults.default_purchase_tax_account_id else None
    )
    sales_tax = sum(
        (
            _decimal_value(invoice.tax_total) * _document_base_factor(invoice) * _document_sign(invoice)
            for invoice in database.session.execute(
                select(SalesInvoice).where(
                    SalesInvoice.company == filters.company,
                    SalesInvoice.docstatus == 1,
                    SalesInvoice.posting_date <= as_of_date,
                )
            ).scalars()
        ),
        Decimal("0"),
    )
    purchase_tax = sum(
        (
            _decimal_value(invoice.tax_total) * _document_base_factor(invoice) * _document_sign(invoice)
            for invoice in database.session.execute(
                select(PurchaseInvoice).where(
                    PurchaseInvoice.company == filters.company,
                    PurchaseInvoice.docstatus == 1,
                    PurchaseInvoice.posting_date <= as_of_date,
                )
            ).scalars()
        ),
        Decimal("0"),
    )
    tax_accounts = [account for account in (sales_tax_account, purchase_tax_account) if account]
    rows.append(
        _reconciliation_row(
            "Tax",
            tax_accounts,
            _convert(purchase_tax - sales_tax, company_currency),
            _reconciliation_gl_amount(
                filters.company, selected_ledger.id, tax_accounts, date_to=as_of_date, currency=comparison_currency
            ),
            basis="ending_balance",
            currency=selected_ledger.currency,
            note="Impuestos netos: compras debitadas menos ventas acreditadas.",
        )
    )

    bank_accounts = [
        account
        for account in database.session.execute(
            select(BankAccount.gl_account_id).where(
                BankAccount.company == filters.company,
                BankAccount.gl_account_id.is_not(None),
            )
        ).scalars()
        if account
    ]
    bank_subledger = _decimal_value(
        database.session.execute(
            select(
                func.coalesce(
                    func.sum(func.coalesce(BankTransaction.deposit, 0) - func.coalesce(BankTransaction.withdrawal, 0)),
                    0,
                )
            )
            .join(BankAccount, BankTransaction.bank_account_id == BankAccount.id)
            .where(BankAccount.company == filters.company, BankTransaction.posting_date <= as_of_date)
        ).scalar_one()
    )
    rows.append(
        _reconciliation_row(
            "Bank",
            [str(account) for account in bank_accounts],
            _convert(bank_subledger, company_currency),
            _reconciliation_gl_amount(
                filters.company,
                selected_ledger.id,
                [str(account) for account in bank_accounts],
                date_to=as_of_date,
                currency=comparison_currency,
            ),
            basis="statement_movement",
            currency=selected_ledger.currency,
            note="Movimiento de extracto; no equivale a saldo de libro si existe saldo inicial no importado.",
        )
    )
    return PaginatedReport(
        rows=rows,
        totals={
            "subledger_amount": sum((_decimal_value(row.values["subledger_amount"]) for row in rows), Decimal("0")),
            "gl_control_amount": sum((_decimal_value(row.values["gl_control_amount"]) for row in rows), Decimal("0")),
            "difference": sum((_decimal_value(row.values["difference"]) for row in rows), Decimal("0")),
        },
        columns=list(rows[0].values.keys()),
        total_rows=len(rows),
        page=1,
        page_size=len(rows),
        ledger_currency=selected_ledger.currency,
    )


def get_aging_report(filters: AgingFilters) -> AgingReport:
    """Devuelve aging AR/AP con buckets fijos."""
    subledger = get_ar_ap_subledger(
        SubledgerFilters(
            company=filters.company,
            party_type=filters.party_type,
            party_id=filters.party_id,
            as_of_date=filters.as_of_date,
            include_returns=filters.include_returns,
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


def _compute_maturity_bucket(days: int) -> str:
    """Classify days into an aging bucket."""
    if days < 0:
        return "overdue"
    if days <= 7:
        return "0_7"
    if days <= 30:
        return "8_30"
    if days <= 90:
        return "31_90"
    return "over_90"


def _fetch_maturity_documents(filters: MaturityFilters) -> list[tuple[Any, str, str | None]]:
    """Fetch sales and purchase invoices for maturity calculation."""
    documents: list[tuple[Any, str, str | None]] = []
    if filters.party_type in (None, "customer"):
        query = select(SalesInvoice).where(SalesInvoice.company == filters.company, SalesInvoice.docstatus == 1)
        query = query.where(SalesInvoice.posting_date <= filters.as_of_date)
        if filters.party_id:
            query = query.where(SalesInvoice.customer_id == filters.party_id)
        documents.extend((doc, "customer", doc.customer_id) for doc in database.session.execute(query).scalars())
    if filters.party_type in (None, "supplier"):
        query = select(PurchaseInvoice).where(PurchaseInvoice.company == filters.company, PurchaseInvoice.docstatus == 1)
        query = query.where(PurchaseInvoice.posting_date <= filters.as_of_date)
        if filters.party_id:
            query = query.where(PurchaseInvoice.supplier_id == filters.party_id)
        documents.extend((doc, "supplier", doc.supplier_id) for doc in database.session.execute(query).scalars())
    return documents


def _load_party_payment_terms(filters: MaturityFilters) -> dict[str, int]:
    """Load payment terms for all active parties."""
    return {
        party_id: terms.due_days
        for party_id, terms in database.session.execute(
            select(CompanyParty.party_id, PaymentTerms)
            .join(PaymentTerms, PaymentTerms.id == CompanyParty.payment_terms_id, isouter=True)
            .where(CompanyParty.company == filters.company, CompanyParty.is_active.is_(True))
        ).all()
        if terms is not None
    }


def get_maturity_schedule(filters: MaturityFilters) -> PaginatedReport:
    """Calcula vencimientos de cartera usando términos de pago por tercero."""
    if filters.horizon_days < 0 or filters.horizon_days > 3650:
        raise ValueError("horizon_days debe estar entre 0 y 3650")
    party_terms = _load_party_payment_terms(filters)
    documents = _fetch_maturity_documents(filters)

    cutoff = filters.as_of_date + timedelta(days=filters.horizon_days)
    rows: list[ReportRow] = []
    for document, party_type, party_id in documents:
        outstanding_original_currency = compute_outstanding_amount(document, as_of_date=filters.as_of_date)
        outstanding = _document_sign(document) * outstanding_original_currency * _document_base_factor(document)
        if outstanding == 0 or not document.posting_date:
            continue
        due_date = document.posting_date + timedelta(days=party_terms.get(party_id or "", 0))
        if due_date > cutoff:
            continue
        days = (due_date - filters.as_of_date).days
        bucket = _compute_maturity_bucket(days)
        rows.append(
            ReportRow(
                values={
                    "document_type": "sales_invoice" if party_type == "customer" else "purchase_invoice",
                    "document_id": document.id,
                    "document_no": document.document_no or document.id,
                    "party_type": party_type,
                    "party_id": party_id,
                    "posting_date": document.posting_date,
                    "due_date": due_date,
                    "days_to_due": days,
                    "bucket": bucket,
                    "outstanding_amount": outstanding,
                    "transaction_currency": document.transaction_currency,
                    "currency": document.base_currency or document.transaction_currency,
                }
            )
        )
    rows.sort(key=lambda row: (row.values["due_date"], str(row.values["document_no"])))
    page = max(filters.page, 1)
    size = max(filters.page_size, 1)
    total = len(rows)
    page_rows = rows[(page - 1) * size : page * size]
    return PaginatedReport(
        rows=page_rows,
        totals={"outstanding_amount": sum((_decimal_value(row.values["outstanding_amount"]) for row in rows), Decimal("0"))},
        columns=list(rows[0].values.keys()) if rows else [],
        total_rows=total,
        page=page,
        page_size=size,
    )


def get_kardex(filters: KardexFilters) -> PaginatedReport:
    """Devuelve Kardex desde StockLedgerEntry."""
    query = exclude_cancelled_stock_entries(select(StockLedgerEntry).filter_by(company=filters.company))
    if filters.item_code:
        query = query.filter_by(item_code=filters.item_code)
    if filters.warehouse:
        query = query.filter_by(warehouse=filters.warehouse)
    if filters.date_to:
        query = query.where(StockLedgerEntry.posting_date <= filters.date_to)

    rows: list[ReportRow] = []
    total_in = Decimal("0")
    total_out = Decimal("0")
    total_value = Decimal("0")
    running: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
    for entry in database.session.execute(
        query.order_by(StockLedgerEntry.posting_date, StockLedgerEntry.created, StockLedgerEntry.id)
    ).scalars():
        qty = _decimal_value(entry.qty_change)
        incoming = qty if qty > 0 else Decimal("0")
        outgoing = abs(qty) if qty < 0 else Decimal("0")
        value_change = _decimal_value(entry.stock_value_difference)
        key = (entry.item_code, entry.warehouse)
        current_qty, current_value = running.get(key, (Decimal("0"), Decimal("0")))
        running_qty = current_qty + qty
        running_value = current_value + value_change
        running[key] = (running_qty, running_value)
        if filters.date_from and entry.posting_date < filters.date_from:
            continue
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
                    "balance_qty": running_qty,
                    "valuation_rate": running_value / running_qty if running_qty > 0 else Decimal("0"),
                    "value_change": value_change,
                    "stock_value": running_value,
                }
            )
        )
    return PaginatedReport(
        rows=rows,
        totals={"incoming_qty": total_in, "outgoing_qty": total_out, "value_change": total_value},
        columns=[
            "posting_date",
            "item_code",
            "warehouse",
            "voucher_type",
            "voucher_id",
            "incoming_qty",
            "outgoing_qty",
            "balance_qty",
            "valuation_rate",
            "value_change",
            "stock_value",
        ],
    )


def get_inventory_existence(filters: KardexFilters) -> PaginatedReport:
    """Devuelve existencias de inventario a una fecha clave desde stock ledger."""
    as_of_date = filters.date_to or filters.date_from
    query = exclude_cancelled_stock_entries(select(StockLedgerEntry).filter_by(company=filters.company))
    if filters.item_code:
        query = query.filter_by(item_code=filters.item_code)
    if filters.warehouse:
        query = query.filter_by(warehouse=filters.warehouse)
    if as_of_date is not None:
        query = query.where(StockLedgerEntry.posting_date <= as_of_date)

    item_names = {item.code: item.name for item in database.session.execute(select(Item)).scalars().all()}
    grouped: dict[tuple[str, str], dict[str, Decimal | str]] = {}
    for entry in database.session.execute(
        query.order_by(StockLedgerEntry.posting_date, StockLedgerEntry.created, StockLedgerEntry.id)
    ).scalars():
        key = (entry.item_code, entry.warehouse)
        row = grouped.setdefault(
            key,
            {
                "item_code": entry.item_code,
                "item_name": item_names.get(entry.item_code, entry.item_code),
                "warehouse": entry.warehouse,
                "balance_qty": Decimal("0"),
                "valuation_rate": Decimal("0"),
                "stock_value": Decimal("0"),
            },
        )
        row["balance_qty"] = _decimal_value(row["balance_qty"]) + _decimal_value(entry.qty_change)
        row["stock_value"] = _decimal_value(row["stock_value"]) + _decimal_value(entry.stock_value_difference)
        balance_qty = _decimal_value(row["balance_qty"])
        row["valuation_rate"] = _decimal_value(row["stock_value"]) / balance_qty if balance_qty > 0 else Decimal("0")

    rows = [ReportRow(values=row) for row in grouped.values() if _decimal_value(row["balance_qty"]) != Decimal("0")]
    rows.sort(key=lambda row: (str(row.values["item_code"]), str(row.values["warehouse"])))
    return PaginatedReport(
        rows=rows,
        totals={
            "balance_qty": sum((_decimal_value(row.values["balance_qty"]) for row in rows), Decimal("0")),
            "stock_value": sum((_decimal_value(row.values["stock_value"]) for row in rows), Decimal("0")),
        },
        columns=["item_code", "item_name", "warehouse", "balance_qty", "valuation_rate", "stock_value"],
    )


def get_negative_stock(filters: OperationalReportFilters) -> PaginatedReport:
    """Detecta saldos negativos actuales por artículo y almacén."""
    query = select(StockBin).where(StockBin.company == filters.company, StockBin.actual_qty < 0)
    if filters.item_code:
        query = query.where(StockBin.item_code == filters.item_code)
    if filters.warehouse:
        query = query.where(StockBin.warehouse == filters.warehouse)
    rows = [
        ReportRow(
            values={
                "item_code": row.item_code,
                "warehouse": row.warehouse,
                "actual_qty": _decimal_value(row.actual_qty),
                "shortage_qty": abs(_decimal_value(row.actual_qty)),
                "valuation_rate": _decimal_value(row.valuation_rate),
                "stock_value": _decimal_value(row.stock_value),
            }
        )
        for row in database.session.execute(query.order_by(StockBin.item_code, StockBin.warehouse)).scalars()
    ]
    return PaginatedReport(
        rows=rows,
        totals={"shortage_qty": sum((row.values["shortage_qty"] for row in rows), Decimal("0"))},
        columns=["item_code", "warehouse", "actual_qty", "shortage_qty", "valuation_rate", "stock_value"],
    )


def get_reorder_alerts(filters: OperationalReportFilters) -> PaginatedReport:
    """Detecta existencias por debajo del mínimo o punto de reorden configurado."""
    query = (
        select(StockBin, Item)
        .join(Item, Item.code == StockBin.item_code)
        .where(
            StockBin.company == filters.company,
            Item.is_active.is_(True),
            or_(
                and_(Item.reorder_level.is_not(None), StockBin.actual_qty <= Item.reorder_level),
                and_(Item.min_stock_qty.is_not(None), StockBin.actual_qty <= Item.min_stock_qty),
            ),
        )
    )
    if filters.item_code:
        query = query.where(StockBin.item_code == filters.item_code)
    if filters.warehouse:
        query = query.where(StockBin.warehouse == filters.warehouse)
    rows = []
    for stock, item in database.session.execute(query.order_by(StockBin.item_code, StockBin.warehouse)).all():
        reorder_level = item.reorder_level if item.reorder_level is not None else item.min_stock_qty
        rows.append(
            ReportRow(
                values={
                    "item_code": stock.item_code,
                    "item_name": item.name,
                    "warehouse": stock.warehouse,
                    "actual_qty": _decimal_value(stock.actual_qty),
                    "reorder_level": _decimal_value(reorder_level),
                    "shortage_qty": max(_decimal_value(reorder_level) - _decimal_value(stock.actual_qty), Decimal("0")),
                    "stock_value": _decimal_value(stock.stock_value),
                }
            )
        )
    return PaginatedReport(
        rows=rows,
        totals={"shortage_qty": sum((row.values["shortage_qty"] for row in rows), Decimal("0"))},
        columns=["item_code", "item_name", "warehouse", "actual_qty", "reorder_level", "shortage_qty", "stock_value"],
    )


def get_inventory_transfers(filters: OperationalReportFilters) -> PaginatedReport:
    """Consulta traslados de material contabilizados entre almacenes."""
    query = (
        select(StockEntry, StockEntryItem)
        .join(StockEntryItem, StockEntryItem.stock_entry_id == StockEntry.id)
        .where(StockEntry.company == filters.company, StockEntry.purpose == "material_transfer", StockEntry.docstatus != 2)
    )
    if filters.item_code:
        query = query.where(StockEntryItem.item_code == filters.item_code)
    if filters.warehouse:
        query = query.where(or_(StockEntry.from_warehouse == filters.warehouse, StockEntry.to_warehouse == filters.warehouse))
    if filters.date_from:
        query = query.where(StockEntry.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(StockEntry.posting_date <= filters.date_to)
    rows = [
        ReportRow(
            values={
                "transfer_id": entry.id,
                "document_no": entry.document_no or entry.id,
                "posting_date": entry.posting_date,
                "item_code": line.item_code,
                "from_warehouse": line.source_warehouse or entry.from_warehouse,
                "to_warehouse": line.target_warehouse or entry.to_warehouse,
                "qty": _decimal_value(line.qty_in_base_uom or line.qty),
                "uom": line.uom,
                "status": {0: "draft", 1: "submitted", 2: "cancelled"}.get(entry.docstatus, "unknown"),
            }
        )
        for entry, line in database.session.execute(
            query.order_by(StockEntry.posting_date.desc(), StockEntry.id, StockEntryItem.id)
        ).all()
    ]
    return PaginatedReport(
        rows=rows,
        totals={"qty": sum((_decimal_value(row.values["qty"]) for row in rows), Decimal("0"))},
        columns=list(rows[0].values.keys()) if rows else [],
    )


def _append_slow_moving_row(
    rows: list[ReportRow], row: Any, latest: dict[tuple[str, str], date], cutoff: date, threshold: date
) -> None:
    """Append a slow-moving item row if it meets the inactivity threshold."""
    last_out = latest.get((row.item_code, row.warehouse))
    if last_out is not None and last_out >= threshold:
        return
    rows.append(
        ReportRow(
            values={
                "item_code": row.item_code,
                "warehouse": row.warehouse,
                "actual_qty": _decimal_value(row.actual_qty),
                "stock_value": _decimal_value(row.stock_value),
                "last_outgoing_date": last_out,
                "inactive_days": (cutoff - last_out).days if last_out else None,
            }
        )
    )


def get_slow_moving_items(
    filters: OperationalReportFilters, inactivity_days: int = 90, as_of_date: date | None = None
) -> PaginatedReport:
    """Lista existencias sin movimientos de salida durante el umbral indicado."""
    if inactivity_days < 1 or inactivity_days > 3650:
        raise ValueError("inactivity_days debe estar entre 1 y 3650")
    cutoff = as_of_date or filters.date_to or date.today()
    query = exclude_cancelled_stock_entries(select(StockLedgerEntry)).where(
        StockLedgerEntry.company == filters.company,
        StockLedgerEntry.posting_date <= cutoff,
    )
    if filters.item_code:
        query = query.where(StockLedgerEntry.item_code == filters.item_code)
    if filters.warehouse:
        query = query.where(StockLedgerEntry.warehouse == filters.warehouse)
    latest: dict[tuple[str, str], date] = {}
    for entry in database.session.execute(query).scalars():
        if entry.qty_change is not None and _decimal_value(entry.qty_change) < 0:
            key = (entry.item_code, entry.warehouse)
            latest[key] = max(latest.get(key, date.min), entry.posting_date)
    bins = select(StockBin).where(StockBin.company == filters.company, StockBin.actual_qty > 0)
    if filters.item_code:
        bins = bins.where(StockBin.item_code == filters.item_code)
    if filters.warehouse:
        bins = bins.where(StockBin.warehouse == filters.warehouse)
    rows: list[ReportRow] = []
    threshold = cutoff - timedelta(days=inactivity_days)
    for row in database.session.execute(bins.order_by(StockBin.item_code, StockBin.warehouse)).scalars():
        _append_slow_moving_row(rows, row, latest, cutoff, threshold)
    return PaginatedReport(
        rows=rows,
        totals={"stock_value": sum((_decimal_value(row.values["stock_value"]) for row in rows), Decimal("0"))},
        columns=["item_code", "warehouse", "actual_qty", "stock_value", "last_outgoing_date", "inactive_days"],
    )


def _record_turnover_entry(
    entry: StockLedgerEntry,
    filters: OperationalReportFilters,
    running_balances: dict[tuple[str, str], Decimal],
    keys_with_activity: set[tuple[str, str]],
    stock_observations: dict[tuple[str, str], list[Decimal]],
    outgoing_quantities: dict[tuple[str, str], Decimal],
    initial_stock_recorded: dict[tuple[str, str], bool],
) -> None:
    """Update turnover accumulators with one chronological stock movement."""
    key = (entry.item_code, entry.warehouse)
    qty_change = _decimal_value(entry.qty_change)
    if entry.posting_date < filters.date_from:
        running_balances[key] += qty_change
        return
    keys_with_activity.add(key)
    if not initial_stock_recorded[key]:
        stock_observations[key].append(max(running_balances[key], Decimal("0")))
        initial_stock_recorded[key] = True
    running_balances[key] += qty_change
    stock_observations[key].append(max(running_balances[key], Decimal("0")))
    if qty_change < 0:
        outgoing_quantities[key] += abs(qty_change)


def _turnover_rows(
    keys_with_activity: set[tuple[str, str]],
    stock_observations: dict[tuple[str, str], list[Decimal]],
    outgoing_quantities: dict[tuple[str, str], Decimal],
) -> list[ReportRow]:
    """Build report rows from the accumulated turnover measurements."""
    rows: list[ReportRow] = []
    for item_code, warehouse in sorted(keys_with_activity):
        observations = stock_observations[(item_code, warehouse)]
        outgoing_qty = outgoing_quantities[(item_code, warehouse)]
        average_stock = sum(observations, Decimal("0")) / len(observations) if observations else Decimal("0")
        rows.append(
            ReportRow(
                values={
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "outgoing_qty": outgoing_qty,
                    "average_stock_qty": average_stock,
                    "turnover_ratio": outgoing_qty / average_stock if average_stock else None,
                }
            )
        )
    return rows


def get_inventory_turnover(filters: OperationalReportFilters) -> PaginatedReport:
    """Calcula rotación por artículo/almacén como salidas sobre stock promedio reconstruido de forma cronológica."""
    if not filters.date_from or not filters.date_to or filters.date_to < filters.date_from:
        raise ValueError("date_from y date_to válidos son obligatorios para calcular rotación")
    query = exclude_cancelled_stock_entries(select(StockLedgerEntry)).where(
        StockLedgerEntry.company == filters.company,
        StockLedgerEntry.posting_date <= filters.date_to,
    )
    if filters.item_code:
        query = query.where(StockLedgerEntry.item_code == filters.item_code)
    if filters.warehouse:
        query = query.where(StockLedgerEntry.warehouse == filters.warehouse)

    running_balances: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    keys_with_activity: set[tuple[str, str]] = set()
    stock_observations: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    outgoing_quantities: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    initial_stock_recorded: dict[tuple[str, str], bool] = defaultdict(bool)

    for entry in database.session.execute(
        query.order_by(StockLedgerEntry.posting_date, StockLedgerEntry.created, StockLedgerEntry.id)
    ).scalars():
        _record_turnover_entry(
            entry,
            filters,
            running_balances,
            keys_with_activity,
            stock_observations,
            outgoing_quantities,
            initial_stock_recorded,
        )

    rows = _turnover_rows(keys_with_activity, stock_observations, outgoing_quantities)
    return PaginatedReport(rows=rows, totals={"outgoing_qty": sum((row.values["outgoing_qty"] for row in rows), Decimal("0"))})


def _bank_diagnostic_row(
    source_type: str,
    source_id: str,
    recon_date: date,
    target_type: str,
    target_id: str | None,
    amount: Decimal,
    status: str,
) -> ReportRow:
    """Build one normalized bank diagnostic row."""
    return ReportRow(
        values={
            "reconciliation_id": source_id,
            "recon_date": recon_date,
            "recon_type": "bank_diagnostic",
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "amount": amount,
            "status": status,
        }
    )


def _transaction_bank_diagnostics(company: str, as_of_date: date | None) -> tuple[list[ReportRow], set[str]]:
    """Find bank transactions linked to missing payments or missing GL."""
    transaction_query = (
        select(BankTransaction)
        .join(BankAccount, BankAccount.id == BankTransaction.bank_account_id)
        .where(BankAccount.company == company)
    )
    if as_of_date:
        transaction_query = transaction_query.where(BankTransaction.posting_date <= as_of_date)
    transactions = database.session.execute(transaction_query).scalars().all()
    transaction_ids = {transaction.id for transaction in transactions}
    rows: list[ReportRow] = []
    for transaction in transactions:
        if not transaction.payment_entry_id:
            continue
        payment = database.session.get(PaymentEntry, transaction.payment_entry_id)
        amount = _decimal_value(transaction.deposit or transaction.withdrawal)
        if payment is None or payment.company != company:
            rows.append(
                _bank_diagnostic_row(
                    "bank_transaction",
                    transaction.id,
                    transaction.posting_date,
                    "payment_entry",
                    transaction.payment_entry_id,
                    amount,
                    "orphan_payment_link",
                )
            )
            continue
        gl_exists = database.session.execute(
            select(GLEntry.id)
            .where(
                GLEntry.company == company,
                GLEntry.voucher_type == "payment_entry",
                GLEntry.voucher_id == payment.id,
                GLEntry.bank_account_id == transaction.bank_account_id,
                GLEntry.is_cancelled.is_(False),
            )
            .limit(1)
        ).scalar_one_or_none()
        if gl_exists is None and payment.docstatus == 1:
            rows.append(
                _bank_diagnostic_row(
                    "bank_transaction",
                    transaction.id,
                    transaction.posting_date,
                    "payment_entry",
                    payment.id,
                    amount,
                    "payment_without_bank_gl",
                )
            )
    return rows, transaction_ids


def _payment_bank_diagnostics(company: str, as_of_date: date | None) -> list[ReportRow]:
    """Find posted bank payments without a matching transaction."""
    payment_query = select(PaymentEntry).where(
        PaymentEntry.company == company,
        PaymentEntry.docstatus == 1,
        PaymentEntry.bank_account_id.is_not(None),
    )
    if as_of_date:
        payment_query = payment_query.where(PaymentEntry.posting_date <= as_of_date)
    rows: list[ReportRow] = []
    for payment in database.session.execute(payment_query).scalars():
        linked = database.session.execute(
            select(BankTransaction.id).where(BankTransaction.payment_entry_id == payment.id).limit(1)
        ).scalar_one_or_none()
        if linked is not None:
            continue
        rows.append(
            _bank_diagnostic_row(
                "payment_entry",
                payment.id,
                payment.posting_date,
                "bank_transaction",
                None,
                _decimal_value(payment.paid_amount or payment.received_amount),
                "posting_without_bank_transaction",
            )
        )
    return rows


def _reconciliation_item_diagnostics(transaction_ids: set[str]) -> list[ReportRow]:
    """Find active reconciliation items whose bank transaction is missing."""
    item_query = select(ReconciliationItem).where(
        ReconciliationItem.source_type == "bank_transaction",
        ReconciliationItem.status != "cancelled",
    )
    rows: list[ReportRow] = []
    for item in database.session.execute(item_query).scalars():
        if item.source_id not in transaction_ids:
            rows.append(
                _bank_diagnostic_row(
                    "bank_transaction",
                    item.source_id,
                    item.reconciliation_date,
                    item.target_type,
                    item.target_id,
                    _decimal_value(item.allocated_amount or item.amount),
                    "orphan_reconciliation_item",
                )
            )
    return rows


def _bank_orphan_diagnostics(company: str, as_of_date: date | None) -> list[ReportRow]:
    """Detecta vínculos bancarios rotos sin confundirlos con partidas pendientes."""
    transaction_rows, transaction_ids = _transaction_bank_diagnostics(company, as_of_date)
    return (
        transaction_rows + _payment_bank_diagnostics(company, as_of_date) + _reconciliation_item_diagnostics(transaction_ids)
    )


def get_reconciliation_report(company: str, as_of_date: date | None = None) -> PaginatedReport:
    """Devuelve reconciliaciones bancarias y conciliaciones de compras pendientes."""
    from cacao_accounting.database import AuditTrail

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

    cancel_dates = {}
    if as_of_date:
        audit_records = database.session.execute(
            select(AuditTrail.document_id, AuditTrail.timestamp).where(
                AuditTrail.document_type == "payment_entry",
                AuditTrail.action == "cancelled",
            )
        ).all()
        for doc_id, timestamp in audit_records:
            if timestamp:
                cancel_dates[doc_id] = timestamp.date()

    rows = []
    for reconciliation, item in database.session.execute(query).all():
        if item.status == "cancelled":
            cancel_date = cancel_dates.get(item.target_id)
            if as_of_date and cancel_date and cancel_date > as_of_date:
                # Cancellation happened after the cutoff, so historically it was reconciled
                status = "reconciled"
            else:
                # Cancelled on or before the cutoff (or no cutoff specified), so exclude it
                continue
        else:
            status = item.status

        rows.append(
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
                    "status": status,
                }
            )
        )

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
    orphan_rows = _bank_orphan_diagnostics(company, as_of_date)
    rows.extend(orphan_rows)
    return PaginatedReport(
        rows=rows,
        totals={
            "bank_reconciled_amount": bank_total,
            "purchase_pending_amount": sum((row.pending_amount for row in purchase_pending), Decimal("0")),
            "bank_orphan_count": Decimal(len(orphan_rows)),
        },
    )


def _build_payment_row_values(
    payment: PaymentEntry,
    bank_account_id: str | None,
    incoming: Decimal,
    outgoing: Decimal,
    bank_accounts: dict[str, BankAccount],
    party_names: dict[str, str],
) -> dict[str, object]:
    bank_account = bank_accounts.get(bank_account_id) if bank_account_id else None
    currency = bank_account.currency if bank_account and bank_account.currency else payment.currency
    return {
        "posting_date": payment.posting_date,
        "document_no": payment.document_no or payment.id,
        "voucher_type": "payment_entry",
        "bank_account": bank_account.account_name if bank_account else bank_account_id,
        "party_name": payment.party_name or party_names.get(payment.party_id, payment.party_id),
        "payment_type": payment.payment_type,
        "reference_no": payment.reference_no,
        "incoming_amount": incoming,
        "outgoing_amount": outgoing,
        "currency": currency,
        "status": "cancelled" if payment.docstatus == 2 else "submitted",
        "remarks": payment.remarks,
    }


def _build_transaction_row_values(
    transaction: BankTransaction,
    bank_account: BankAccount | None,
) -> dict[str, object]:
    incoming = _decimal_value(transaction.deposit)
    outgoing = _decimal_value(transaction.withdrawal)
    return {
        "posting_date": transaction.posting_date,
        "document_no": transaction.reference_number or transaction.id,
        "voucher_type": "bank_transaction",
        "bank_account": bank_account.account_name if bank_account else transaction.bank_account_id,
        "party_name": None,
        "payment_type": "statement",
        "reference_no": transaction.reference_number,
        "incoming_amount": incoming,
        "outgoing_amount": outgoing,
        "currency": bank_account.currency if bank_account else None,
        "status": "reconciled" if transaction.is_reconciled else "pending",
        "remarks": transaction.description,
    }


def _payment_entry_primary_amounts(payment: PaymentEntry) -> tuple[Decimal, Decimal]:
    """Devuelve los importes de ingreso y egreso para la cuenta principal."""
    if payment.payment_type == "receive":
        return _decimal_value(payment.received_amount or payment.paid_amount), Decimal("0")
    if payment.payment_type == "pay":
        return Decimal("0"), _decimal_value(payment.paid_amount or payment.received_amount)
    if payment.payment_type == "internal_transfer":
        return Decimal("0"), _decimal_value(payment.paid_amount)
    return Decimal("0"), Decimal("0")


def _append_payment_rows(
    rows: list[ReportRow],
    payment: PaymentEntry,
    bank_account_id: str | None,
    incoming: Decimal,
    outgoing: Decimal,
    bank_accounts: dict[str, BankAccount],
    party_names: dict[str, str],
) -> tuple[Decimal, Decimal]:
    """Agrega filas de reporte para un movimiento y retorna sus totales."""
    if incoming > 0:
        rows.append(
            ReportRow(
                values=_build_payment_row_values(payment, bank_account_id, incoming, Decimal("0"), bank_accounts, party_names)
            )
        )
    if outgoing > 0:
        rows.append(
            ReportRow(
                values=_build_payment_row_values(payment, bank_account_id, Decimal("0"), outgoing, bank_accounts, party_names)
            )
        )
    return incoming, outgoing


def _payment_entry_target_amount(payment: PaymentEntry) -> Decimal:
    """Devuelve el importe de ingreso para la cuenta destino de una transferencia."""
    return _decimal_value(payment.received_amount or payment.paid_amount)


def _process_payment_entry(
    payment: PaymentEntry,
    filters: BankingFilters,
    bank_accounts: dict[str, BankAccount],
    party_names: dict[str, str],
) -> tuple[list[ReportRow], Decimal, Decimal]:
    """Procesa un PaymentEntry para el reporte de movimientos bancarios."""
    rows: list[ReportRow] = []
    total_incoming = Decimal("0")
    total_outgoing = Decimal("0")

    # 1. Movimiento en la cuenta principal (bank_account_id)
    bank_account_id = payment.bank_account_id
    if bank_account_id and (not filters.bank_account_id or bank_account_id == filters.bank_account_id):
        incoming, outgoing = _payment_entry_primary_amounts(payment)
        incoming_total, outgoing_total = _append_payment_rows(
            rows, payment, bank_account_id, incoming, outgoing, bank_accounts, party_names
        )
        total_incoming += incoming_total
        total_outgoing += outgoing_total

    # 2. Movimiento en la cuenta destino (solo para transferencias internas)
    if payment.payment_type == "internal_transfer" and payment.target_bank_account_id:
        target_bank_id = payment.target_bank_account_id
        if not filters.bank_account_id or target_bank_id == filters.bank_account_id:
            incoming = _payment_entry_target_amount(payment)
            if incoming > 0:
                rows.append(
                    ReportRow(
                        values=_build_payment_row_values(
                            payment,
                            target_bank_id,
                            incoming,
                            Decimal("0"),
                            bank_accounts,
                            party_names,
                        )
                    )
                )
                total_incoming += incoming

    return rows, total_incoming, total_outgoing


def _process_payment_entries(
    filters: BankingFilters,
    bank_accounts: dict[str, BankAccount],
    party_names: dict[str, str],
) -> tuple[list[ReportRow], Decimal, Decimal]:
    rows: list[ReportRow] = []
    total_incoming = Decimal("0")
    total_outgoing = Decimal("0")

    payments = select(PaymentEntry).where(PaymentEntry.company == filters.company, PaymentEntry.docstatus == 1)
    if filters.date_from is not None:
        payments = payments.where(PaymentEntry.posting_date >= filters.date_from)
    if filters.date_to is not None:
        payments = payments.where(PaymentEntry.posting_date <= filters.date_to)

    for payment in database.session.execute(
        payments.order_by(PaymentEntry.posting_date.asc(), PaymentEntry.created.asc())
    ).scalars():
        entry_rows, entry_incoming, entry_outgoing = _process_payment_entry(payment, filters, bank_accounts, party_names)
        rows.extend(entry_rows)
        total_incoming += entry_incoming
        total_outgoing += entry_outgoing

    return rows, total_incoming, total_outgoing


def _process_bank_transactions(
    filters: BankingFilters,
    bank_accounts: dict[str, BankAccount],
) -> list[ReportRow]:
    rows: list[ReportRow] = []
    transactions = select(BankTransaction).join(BankAccount, BankTransaction.bank_account_id == BankAccount.id)
    transactions = transactions.where(BankAccount.company == filters.company, BankTransaction.payment_entry_id.is_(None))
    if filters.bank_account_id:
        transactions = transactions.where(BankTransaction.bank_account_id == filters.bank_account_id)
    if filters.date_from is not None:
        transactions = transactions.where(BankTransaction.posting_date >= filters.date_from)
    if filters.date_to is not None:
        transactions = transactions.where(BankTransaction.posting_date <= filters.date_to)

    for transaction in database.session.execute(
        transactions.order_by(BankTransaction.posting_date.asc(), BankTransaction.created.asc())
    ).scalars():
        bank_account = bank_accounts.get(transaction.bank_account_id)
        rows.append(ReportRow(values=_build_transaction_row_values(transaction, bank_account)))
    return rows


def _compute_running_balance(rows: list[ReportRow]) -> Decimal:
    running_balance = Decimal("0")
    for row in rows:
        running_balance += _decimal_value(row.values["incoming_amount"]) - _decimal_value(row.values["outgoing_amount"])
        row.values["running_balance"] = running_balance
    return running_balance


def get_bank_movement_detail(filters: BankingFilters) -> PaginatedReport:
    """Devuelve detalle de movimiento bancario desde pagos y extractos."""
    bank_accounts = {
        account.id: account
        for account in database.session.execute(select(BankAccount).where(BankAccount.company == filters.company)).scalars()
    }
    party_names = {party.id: party.name for party in database.session.execute(select(Party)).scalars().all()}

    payment_rows, _, _ = _process_payment_entries(filters, bank_accounts, party_names)
    transaction_rows = _process_bank_transactions(filters, bank_accounts)

    rows = payment_rows + transaction_rows
    rows.sort(
        key=lambda row: (
            row.values.get("posting_date") or date.min,
            str(row.values.get("document_no") or ""),
            str(row.values.get("bank_account") or ""),
        )
    )
    running_balance = _compute_running_balance(rows)

    currencies: set[str] = {str(row.values.get("currency")) for row in rows if row.values.get("currency") is not None}

    total_incoming: dict[str, Decimal] | Decimal
    total_outgoing: dict[str, Decimal] | Decimal
    total_running_balance: dict[str, Decimal] | Decimal

    if len(currencies) > 1:
        total_incoming = {curr: Decimal("0") for curr in currencies}
        total_outgoing = {curr: Decimal("0") for curr in currencies}
        for row in rows:
            curr = row.values.get("currency")
            if curr:
                curr_str = str(curr)
                total_incoming[curr_str] += _decimal_value(row.values.get("incoming_amount"))
                total_outgoing[curr_str] += _decimal_value(row.values.get("outgoing_amount"))
        total_running_balance = {curr: Decimal("0") for curr in currencies}
        for curr in currencies:
            total_running_balance[curr] = total_incoming[curr] - total_outgoing[curr]
        for row in rows:
            row.values["running_balance"] = None
    else:
        total_incoming = sum((_decimal_value(row.values.get("incoming_amount")) for row in rows), Decimal("0"))
        total_outgoing = sum((_decimal_value(row.values.get("outgoing_amount")) for row in rows), Decimal("0"))
        total_running_balance = running_balance

    return PaginatedReport(
        rows=rows,
        totals={
            "incoming_amount": total_incoming,
            "outgoing_amount": total_outgoing,
            "running_balance": total_running_balance,
        },
        columns=[
            "posting_date",
            "document_no",
            "voucher_type",
            "bank_account",
            "party_name",
            "payment_type",
            "reference_no",
            "incoming_amount",
            "outgoing_amount",
            "running_balance",
            "currency",
            "status",
            "remarks",
        ],
    )


def get_unreconciled_bank_transactions(filters: BankingFilters) -> PaginatedReport:
    """Devuelve extractos bancarios pendientes de conciliación, sin mutar datos."""
    bank_accounts = {
        account.id: account
        for account in database.session.execute(select(BankAccount).where(BankAccount.company == filters.company)).scalars()
    }
    query = (
        select(BankTransaction)
        .join(BankAccount, BankTransaction.bank_account_id == BankAccount.id)
        .where(BankAccount.company == filters.company, BankTransaction.is_reconciled.is_(False))
    )
    if filters.bank_account_id:
        query = query.where(BankTransaction.bank_account_id == filters.bank_account_id)
    if filters.date_from is not None:
        query = query.where(BankTransaction.posting_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(BankTransaction.posting_date <= filters.date_to)
    rows = [
        ReportRow(values=_build_transaction_row_values(transaction, bank_accounts.get(transaction.bank_account_id)))
        for transaction in database.session.execute(
            query.order_by(BankTransaction.posting_date.asc(), BankTransaction.created.asc())
        ).scalars()
    ]
    return PaginatedReport(
        rows=rows,
        totals={
            "incoming_amount": sum((_decimal_value(row.values["incoming_amount"]) for row in rows), Decimal("0")),
            "outgoing_amount": sum((_decimal_value(row.values["outgoing_amount"]) for row in rows), Decimal("0")),
            "transaction_count": Decimal(len(rows)),
        },
        columns=[
            "posting_date",
            "document_no",
            "bank_account",
            "incoming_amount",
            "outgoing_amount",
            "currency",
            "status",
            "remarks",
        ],
    )


def _compute_account_receipts_and_payments(
    bank_account_id: str,
    company: str,
    as_of_date: date | None,
) -> tuple[Decimal, Decimal]:
    receipts = Decimal("0")
    payments = Decimal("0")
    movements_query = _bank_account_movements_query(bank_account_id, company, as_of_date)
    for payment in database.session.execute(movements_query).scalars():
        receipt_amount, payment_amount = _bank_account_payment_movements(payment, bank_account_id)
        receipts += receipt_amount
        payments += payment_amount
    return receipts, payments


def _bank_account_movements_query(bank_account_id: str, company: str, as_of_date: date | None) -> Any:
    """Construye la consulta de movimientos que afectan una cuenta bancaria.

    Solo incluye PaymentEntry posteadas (docstatus == 1) para reportes consistentes.
    """
    movements_query = select(PaymentEntry).where(PaymentEntry.company == company, PaymentEntry.docstatus == 1)
    movements_query = movements_query.where(
        (PaymentEntry.bank_account_id == bank_account_id) | (PaymentEntry.target_bank_account_id == bank_account_id)
    )
    if as_of_date is not None:
        movements_query = movements_query.where(PaymentEntry.posting_date <= as_of_date)
    return movements_query


def _bank_account_payment_movements(payment: PaymentEntry, bank_account_id: str) -> tuple[Decimal, Decimal]:
    """Devuelve el impacto de un PaymentEntry sobre una cuenta bancaria."""
    return (
        _bank_account_receipt_amount(payment, bank_account_id),
        _bank_account_payment_amount(payment, bank_account_id),
    )


def _bank_account_receipt_amount(payment: PaymentEntry, bank_account_id: str) -> Decimal:
    """Devuelve el importe recibido por una cuenta bancaria para un pago."""
    if payment.payment_type == "receive":
        return _received_payment_amount(payment, bank_account_id)
    if payment.payment_type == "internal_transfer":
        return _transfer_receipt_amount(payment, bank_account_id)
    return Decimal("0")


def _bank_account_payment_amount(payment: PaymentEntry, bank_account_id: str) -> Decimal:
    """Devuelve el importe pagado por una cuenta bancaria para un pago."""
    if payment.payment_type == "pay":
        return _paid_payment_amount(payment, bank_account_id)
    if payment.payment_type == "internal_transfer":
        return _transfer_payment_amount(payment, bank_account_id)
    return Decimal("0")


def _received_payment_amount(payment: PaymentEntry, bank_account_id: str) -> Decimal:
    """Calcula el importe recibido cuando la cuenta principal coincide."""
    if payment.bank_account_id != bank_account_id:
        return Decimal("0")
    return _decimal_value(payment.received_amount or payment.paid_amount)


def _paid_payment_amount(payment: PaymentEntry, bank_account_id: str) -> Decimal:
    """Calcula el importe pagado cuando la cuenta principal coincide."""
    if payment.bank_account_id != bank_account_id:
        return Decimal("0")
    return _decimal_value(payment.paid_amount or payment.received_amount)


def _transfer_receipt_amount(payment: PaymentEntry, bank_account_id: str) -> Decimal:
    """Calcula el importe recibido por la cuenta destino de una transferencia."""
    if payment.target_bank_account_id != bank_account_id:
        return Decimal("0")
    return _decimal_value(payment.received_amount or payment.paid_amount)


def _transfer_payment_amount(payment: PaymentEntry, bank_account_id: str) -> Decimal:
    """Calcula el importe pagado por la cuenta origen de una transferencia."""
    if payment.bank_account_id != bank_account_id:
        return Decimal("0")
    return _decimal_value(payment.paid_amount)


def _compute_gl_balance(company: str, bank_account_id: str, as_of_date: date | None) -> Decimal:
    gl_balance_query = exclude_cancelled_gl_entries(select(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0))).where(
        GLEntry.company == company,
        GLEntry.bank_account_id == bank_account_id,
    )
    ledger_id = primary_ledger_id(company)
    if ledger_id:
        gl_balance_query = gl_balance_query.where(GLEntry.ledger_id == ledger_id)
    if as_of_date is not None:
        gl_balance_query = gl_balance_query.where(GLEntry.posting_date <= as_of_date)
    return _decimal_value(database.session.execute(gl_balance_query).scalar_one())


def get_bank_balance_summary(filters: BankingFilters) -> PaginatedReport:
    """Devuelve resumen de saldos bancarios por cuenta."""
    bank_accounts_query = select(BankAccount).where(BankAccount.company == filters.company)
    if filters.bank_account_id:
        bank_accounts_query = bank_accounts_query.where(BankAccount.id == filters.bank_account_id)
    bank_accounts = database.session.execute(bank_accounts_query.order_by(BankAccount.account_name.asc())).scalars().all()

    rows: list[ReportRow] = []
    for bank_account in bank_accounts:
        balance = _compute_gl_balance(filters.company, bank_account.id, filters.as_of_date)
        receipts, payments = _compute_account_receipts_and_payments(bank_account.id, filters.company, filters.as_of_date)

        rows.append(
            ReportRow(
                values={
                    "bank_account": bank_account.account_name,
                    "account_no": bank_account.account_no,
                    "currency": bank_account.currency,
                    "receipts_amount": receipts,
                    "payments_amount": payments,
                    "ending_balance": balance,
                }
            )
        )

    currencies: set[str] = {str(row.values.get("currency")) for row in rows if row.values.get("currency") is not None}

    total_receipts: dict[str, Decimal] | Decimal
    total_payments: dict[str, Decimal] | Decimal
    total_ending: dict[str, Decimal] | Decimal

    if len(currencies) > 1:
        total_receipts = {curr: Decimal("0") for curr in currencies}
        total_payments = {curr: Decimal("0") for curr in currencies}
        total_ending = {curr: Decimal("0") for curr in currencies}
        for row in rows:
            curr = row.values.get("currency")
            if curr:
                curr_str = str(curr)
                total_receipts[curr_str] += _decimal_value(row.values.get("receipts_amount"))
                total_payments[curr_str] += _decimal_value(row.values.get("payments_amount"))
                total_ending[curr_str] += _decimal_value(row.values.get("ending_balance"))
    else:
        total_receipts = sum((_decimal_value(row.values["receipts_amount"]) for row in rows), Decimal("0"))
        total_payments = sum((_decimal_value(row.values["payments_amount"]) for row in rows), Decimal("0"))
        total_ending = sum((_decimal_value(row.values["ending_balance"]) for row in rows), Decimal("0"))

    return PaginatedReport(
        rows=rows,
        totals={
            "receipts_amount": total_receipts,
            "payments_amount": total_payments,
            "ending_balance": total_ending,
        },
        columns=["bank_account", "account_no", "currency", "receipts_amount", "payments_amount", "ending_balance"],
    )


def _resolve_ledger(company: str, ledger: str | None) -> Book | None:
    query = select(Book).where(
        Book.entity == company,
        or_(Book.status == "activo", Book.status.is_(None)),
    )
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
    query = _apply_base_filters(query, filters)
    query = _apply_account_filters(query, filters)
    query = _apply_party_filters(query, filters)
    query = _apply_cancellation_scope(query, filters)
    query = _apply_status_filter(query, filters)
    query = _apply_period_filter(query, period_start, period_end)
    return query


def _apply_base_filters(query: Any, filters: FinancialReportFilters) -> Any:
    query = query.where(GLEntry.company == filters.company)
    if not filters.include_closing:
        query = query.where(GLEntry.is_fiscal_year_closing.is_(False))
    if filters.voucher_number:
        like_value = f"%{filters.voucher_number.strip()}%"
        query = query.where(GLEntry.document_no.ilike(like_value))
    return query


def _apply_hierarchical_filter(query: Any, column: Any, code_value: str, model_class: Any) -> Any:
    """Aplica filtro jerarquico con soporte de descendientes."""
    node = database.session.execute(select(model_class).filter_by(code=code_value)).scalar_one_or_none()
    if node:
        codes_list = [node.code] + [d.code for d in node.descendants]
        return query.where(column.in_(codes_list))
    return query.where(column == code_value)


def _apply_account_filters(query: Any, filters: FinancialReportFilters) -> Any:
    from cacao_accounting.database import Unit, Project

    if filters.account_code:
        query = query.where(GLEntry.account_code == filters.account_code)
    if filters.account_from:
        query = query.where(GLEntry.account_code >= filters.account_from)
    if filters.account_to:
        query = query.where(GLEntry.account_code <= filters.account_to)
    if filters.cost_center_code:
        query = query.where(GLEntry.cost_center_code == filters.cost_center_code)
    if filters.unit_code:
        if filters.include_descendants:
            query = _apply_hierarchical_filter(query, GLEntry.unit_code, filters.unit_code, Unit)
        else:
            query = query.where(GLEntry.unit_code == filters.unit_code)
    if filters.project_code:
        if filters.include_descendants:
            query = _apply_hierarchical_filter(query, GLEntry.project_code, filters.project_code, Project)
        else:
            query = query.where(GLEntry.project_code == filters.project_code)
    return query


def _apply_party_filters(query: Any, filters: FinancialReportFilters) -> Any:
    if filters.party_type:
        query = query.where(GLEntry.party_type == filters.party_type)
    if filters.party_id:
        query = query.where(GLEntry.party_id == filters.party_id)
    if filters.voucher_type:
        query = query.where(func.lower(GLEntry.voucher_type) == filters.voucher_type.strip().lower())
    return query


def _apply_cancellation_scope(query: Any, filters: FinancialReportFilters) -> Any:
    if filters.include_cancellations or filters.status == "cancelled":
        return query
    return query.where(GLEntry.is_cancelled.is_(False), GLEntry.is_reversal.is_(False))


def _apply_status_filter(query: Any, filters: FinancialReportFilters) -> Any:
    if filters.status == "cancelled":
        query = query.where(GLEntry.is_cancelled.is_(True))
    elif filters.status in {"submitted", "posted"}:
        query = query.where(GLEntry.is_cancelled.is_(False), GLEntry.is_reversal.is_(False))
    return query


def _apply_period_filter(query: Any, period_start: date | None, period_end: date | None) -> Any:
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


def _entry_bucket(posting_date: date, period_start: date | None, period_end: date | None) -> str | None:
    """Clasifica una entrada como saldo inicial o movimiento del periodo."""
    if period_start and posting_date < period_start:
        return "opening"
    if period_end and posting_date > period_end:
        return None
    return "movement"


def _account_summary_base_values(account_code: str, account: Accounts | None) -> dict[str, Any]:
    """Construye el acumulador inicial para la sabana por cuenta."""
    return {
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
    }


def _apply_account_summary_entry(row: dict[str, Any], bucket: str, entry: GLEntry, debit: Decimal, credit: Decimal) -> None:
    """Acumula una entrada en el resumen por cuenta."""
    if bucket == "opening":
        row["opening_balance"] += debit - credit
        return
    row["debit"] += debit
    row["credit"] += credit
    row["movement_count"] += 1
    if row["first_movement"] is None or entry.posting_date < row["first_movement"]:
        row["first_movement"] = entry.posting_date
    if row["last_movement"] is None or entry.posting_date > row["last_movement"]:
        row["last_movement"] = entry.posting_date


def _build_account_summary_row(values: dict[str, Any]) -> tuple[ReportRow, Decimal]:
    """Construye la fila de salida y su saldo final para la sabana por cuenta."""
    ending = values["opening_balance"] + values["debit"] - values["credit"]
    return (
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
        ),
        ending,
    )


def _trial_balance_base_values(account_code: str, account: Accounts | None) -> dict[str, Any]:
    """Construye el acumulador inicial para la balanza de comprobación."""
    return {
        "account_code": account_code,
        "account_name": account.name if account else None,
        "opening": Decimal("0"),
        "debit": Decimal("0"),
        "credit": Decimal("0"),
        "level": account_code.count(".") + 1 if account_code else 1,
    }


def _apply_trial_balance_entry(row: dict[str, Any], bucket: str, debit: Decimal, credit: Decimal) -> None:
    """Acumula una entrada en la balanza de comprobación."""
    if bucket == "opening":
        row["opening"] += debit - credit
        return
    row["debit"] += debit
    row["credit"] += credit


def _build_trial_balance_row(values: dict[str, Any]) -> tuple[ReportRow, Decimal]:
    """Construye la fila de salida y su saldo final para la balanza."""
    ending = values["opening"] + values["debit"] - values["credit"]
    return (
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
        ),
        ending,
    )


def _movement_detail_row_values(
    entry: GLEntry,
    account: Accounts | None,
    period: AccountingPeriod | None,
    party: Party | None,
    selected_ledger: Book,
    running_balance: Decimal | None,
    include_running_balance: bool,
) -> dict[str, Any]:
    """Construye el diccionario de salida para una fila de movimiento contable."""
    account_code = entry.account_code or (account.code if account else "") or ""
    if entry.is_cancelled:
        voucher_status = "cancelled"
    elif entry.is_reversal:
        voucher_status = "reversal"
    else:
        voucher_status = "submitted"
    row_values: dict[str, Any] = {
        "posting_date": entry.posting_date,
        "accounting_period": period.name if period else None,
        "document_no": entry.document_no or entry.voucher_id,
        "voucher_type": entry.voucher_type,
        "account_code": account_code,
        "account_name": account.name if account else None,
        "debit": _decimal_value(entry.debit),
        "credit": _decimal_value(entry.credit),
        "currency": selected_ledger.currency or entry.company_currency or entry.account_currency,
        "ledger": selected_ledger.code,
        "company": entry.company,
        "cost_center": entry.cost_center_code,
        "unit": entry.unit_code,
        "project": entry.project_code,
        "party_type": entry.party_type,
        "party_id": party.name or party.code if party else entry.party_id,
        "line_comment": entry.remarks,
        "created_by": entry.created_by,
        "created_at": entry.created,
        "voucher_status": voucher_status,
    }
    if include_running_balance and running_balance is not None:
        row_values["running_balance"] = running_balance
    return row_values


def _collect_movement_detail_rows(
    entries: Sequence[tuple[GLEntry, Accounts | None, AccountingPeriod | None, Party | None]],
    selected_ledger: Book,
    filters: FinancialReportFilters,
    display_from_index: int,
) -> tuple[list[ReportRow], Decimal, Decimal]:
    """Convierte las entradas del mayor en filas y totales para el reporte."""
    running_per_account: dict[str, Decimal] = defaultdict(Decimal)
    rows: list[ReportRow] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for index, (entry, account, period, party) in enumerate(entries):
        account_code = entry.account_code or (account.code if account else None) or ""
        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        running_per_account[account_code] += debit - credit
        if index < display_from_index:
            continue

        total_debit += debit
        total_credit += credit
        row_values = _movement_detail_row_values(
            entry,
            account,
            period,
            party,
            selected_ledger,
            running_per_account[account_code],
            filters.include_running_balance,
        )
        rows.append(ReportRow(values=row_values))

    return rows, total_debit, total_credit


def _movement_detail_query(
    filters: FinancialReportFilters,
    period_start: date | None,
    period_end: date | None,
    selected_ledger: Book,
) -> Any:
    """Construye la consulta base del detalle de movimiento contable."""
    query = (
        select(GLEntry, Accounts, AccountingPeriod, Party)
        .join(Accounts, (Accounts.id == GLEntry.account_id), isouter=True)
        .join(AccountingPeriod, (AccountingPeriod.id == GLEntry.accounting_period_id), isouter=True)
        .join(Party, (Party.id == GLEntry.party_id), isouter=True)
    )
    query = _apply_gl_filters(query, filters, period_start, period_end).where(GLEntry.ledger_id == selected_ledger.id)
    return _sorted_gl_query(query, filters.sort_by, filters.sort_dir)


def get_account_movement_detail(filters: FinancialReportFilters) -> PaginatedReport:
    """Detalle de movimiento contable (diario + mayor) desde GL."""
    period_start, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={"debit": Decimal("0"), "credit": Decimal("0")}, columns=[])

    query = _movement_detail_query(filters, period_start, period_end, selected_ledger)

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

    entries = cast(
        Sequence[tuple[GLEntry, Accounts | None, AccountingPeriod | None, Party | None]],
        database.session.execute(query).all(),
    )
    rows, total_debit, total_credit = _collect_movement_detail_rows(entries, selected_ledger, filters, display_from_index)

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


def _build_actual_query(
    filters: FinancialReportFilters,
    selected_ledger: Any,
    line: Any,
    cost_center: Any,
    period_start: date,
    period_end: date,
) -> Any:
    """Build the query to fetch actual GL amount for a budget line."""
    actual_query = select(func.coalesce(func.sum(GLEntry.debit - GLEntry.credit), 0)).where(
        GLEntry.company == filters.company,
        GLEntry.ledger_id == selected_ledger.id,
        GLEntry.account_id == line.account_id,
        GLEntry.posting_date >= period_start,
        GLEntry.posting_date <= period_end,
        GLEntry.is_cancelled.is_(False),
        GLEntry.is_reversal.is_(False),
        GLEntry.is_fiscal_year_closing.is_(False),
    )
    if cost_center and cost_center.code:
        actual_query = actual_query.where(GLEntry.cost_center_code == cost_center.code)
    return actual_query


def _build_budget_variance_rows(
    query_results: list[Any],
    filters: FinancialReportFilters,
    selected_ledger: Any,
    period_start: date,
    period_end: date,
    period: Any,
) -> tuple[list[ReportRow], Decimal, Decimal]:
    """Build budget variance report rows from query results."""
    rows: list[ReportRow] = []
    total_budget = Decimal("0")
    total_actual = Decimal("0")
    for line, budget, account, cost_center in query_results:
        actual_query = _build_actual_query(filters, selected_ledger, line, cost_center, period_start, period_end)
        actual = _decimal_value(database.session.execute(actual_query).scalar())
        planned = _decimal_value(line.amount)
        variance = actual - planned
        total_budget += planned
        total_actual += actual
        rows.append(
            ReportRow(
                values={
                    "budget_code": budget.budget_code,
                    "account_code": account.code if account else None,
                    "account_name": account.name if account else None,
                    "cost_center": cost_center.code if cost_center else None,
                    "period": period.name,
                    "budget_amount": planned,
                    "actual_amount": actual,
                    "variance": variance,
                    "utilization_pct": (actual / planned * Decimal("100")) if planned else None,
                }
            )
        )
    return rows, total_budget, total_actual


def get_budget_variance(filters: FinancialReportFilters) -> PaginatedReport:
    """Compara presupuesto aprobado contra GL para un período contable."""
    period_start, period_end, period = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if period is None or selected_ledger is None:
        return PaginatedReport(rows=[], totals={"budget": Decimal("0"), "actual": Decimal("0"), "variance": Decimal("0")})

    query = (
        select(BudgetLine, Budget, Accounts, CostCenter)
        .join(Budget, Budget.id == BudgetLine.budget_id)
        .join(Accounts, Accounts.id == BudgetLine.account_id, isouter=True)
        .join(CostCenter, CostCenter.id == BudgetLine.cost_center_id, isouter=True)
        .where(
            Budget.company == filters.company,
            Budget.ledger_id == selected_ledger.id,
            BudgetLine.period_id == period.id,
            Budget.status == "approved",
        )
    )
    if filters.budget_code:
        query = query.where(Budget.budget_code == filters.budget_code)
    rows, total_budget, total_actual = _build_budget_variance_rows(
        list(database.session.execute(query).all()),
        filters,
        selected_ledger,
        period_start or date.today(),
        period_end or date.today(),
        period,
    )
    return PaginatedReport(
        rows=rows,
        totals={"budget": total_budget, "actual": total_actual, "variance": total_actual - total_budget},
        columns=list(rows[0].values.keys()) if rows else [],
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
        bucket = _entry_bucket(entry.posting_date, period_start, period_end)
        if bucket is None:
            continue

        account_code = entry.account_code or (account.code if account else "")
        # Podemos extender la llave de agrupación si en el futuro se requiere soportar
        # agrupaciones múltiples (ej. Cuenta + Centro de Costos) en una sola fila.
        group_key = account_code

        summary_row = account_totals.setdefault(group_key, _account_summary_base_values(account_code, account))

        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        _apply_account_summary_entry(summary_row, bucket, entry, debit, credit)

    rows: list[ReportRow] = []
    total_opening = Decimal("0")
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    total_ending = Decimal("0")

    for group_key in sorted(account_totals):
        values = account_totals[group_key]
        row, ending = _build_account_summary_row(values)
        total_opening += values["opening_balance"]
        total_debit += values["debit"]
        total_credit += values["credit"]
        total_ending += ending
        rows.append(row)

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
        bucket = _entry_bucket(entry.posting_date, period_start, period_end)
        if bucket is None:
            continue
        account_code = entry.account_code or (account.code if account else "")
        trial_row = account_totals.setdefault(account_code, _trial_balance_base_values(account_code, account))
        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        _apply_trial_balance_entry(trial_row, bucket, debit, credit)

    rows: list[ReportRow] = []
    total_opening = Decimal("0")
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    total_ending = Decimal("0")
    for account_code in sorted(account_totals):
        values = account_totals[account_code]
        row, ending = _build_trial_balance_row(values)
        total_opening += values["opening"]
        total_debit += values["debit"]
        total_credit += values["credit"]
        total_ending += ending
        rows.append(row)
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


def _classify_income_account(
    classification: str,
    debit: Decimal,
    credit: Decimal,
    account_code: str,
    account_name: str,
) -> tuple[str, Decimal] | None:
    """Clasifica cuenta para estado de resultado y devuelve seccion y monto."""
    if classification in {"ingreso", "income"}:
        return "income", credit - debit
    if classification in {"costo", "cost"}:
        return "cost", debit - credit
    if classification in {"gasto", "expense"}:
        return "expense", debit - credit
    return None


def _accumulate_income_entry(
    classification: str,
    debit: Decimal,
    credit: Decimal,
    account_code: str,
    account_name: str,
    account_summary: dict[str, dict[str, Any]],
    summary: dict[str, Decimal],
) -> None:
    """Acumula una entrada en el resumen del estado de resultado."""
    result = _classify_income_account(classification, debit, credit, account_code, account_name)
    if result is None:
        return
    section, amount = result
    summary[section] += amount
    bucket = account_summary.setdefault(
        account_code,
        {
            "account_code": account_code,
            "account_name": account_name,
            "section": None,
            "amount": Decimal("0"),
            "level": account_code.count(".") + 1 if account_code else 1,
        },
    )
    bucket["section"] = section
    bucket["amount"] += amount


def get_income_statement_report(filters: FinancialReportFilters) -> PaginatedReport:
    """Estado de resultado del periodo contable seleccionado."""
    period_start, period_end, _ = _period_bounds(filters.company, filters.accounting_period)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={}, columns=[])
    base_query = select(GLEntry, Accounts).join(Accounts, Accounts.id == GLEntry.account_id, isouter=True)
    base_query = _apply_gl_filters(base_query, filters, period_start, period_end).where(
        GLEntry.ledger_id == selected_ledger.id
    )
    summary: dict[str, Decimal] = {
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
        _accumulate_income_entry(
            classification,
            debit,
            credit,
            account_code,
            account_name,
            account_summary,
            summary,
        )
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


def _classify_balance_sheet_account(
    classification: str,
    debit: Decimal,
    credit: Decimal,
) -> tuple[str, Decimal] | None:
    """Clasifica cuenta para balance general y devuelve seccion y monto."""
    if classification in {"activo", "asset"}:
        return "assets", debit - credit
    if classification in {"pasivo", "liability"}:
        return "liabilities", credit - debit
    if classification in {"patrimonio", "equity"}:
        return "equity", credit - debit
    return None


def _accumulate_balance_sheet_entry(
    classification: str,
    debit: Decimal,
    credit: Decimal,
    account_code: str,
    account_name: str,
    by_account: dict[str, dict[str, Any]],
    totals: dict[str, Decimal],
) -> bool:
    """Acumula una entrada en el balance general. Retorna True si se procesó."""
    result = _classify_balance_sheet_account(classification, debit, credit)
    if result is not None:
        section, amount = result
        record = by_account.setdefault(
            account_code,
            {
                "section": section,
                "account_code": account_code,
                "account_name": account_name,
                "amount": Decimal("0"),
            },
        )
        record["amount"] += amount
        totals[section] += amount
        return True
    if classification in {"ingreso", "income"}:
        totals["income"] += credit - debit
        return True
    if classification in {"costo", "cost"}:
        totals["cost"] += debit - credit
        return True
    if classification in {"gasto", "expense"}:
        totals["expense"] += debit - credit
        return True
    return False


def _fiscal_year_start_for_period(period: AccountingPeriod | None) -> date | None:
    """Resuelve la fecha de inicio del año fiscal del período dado."""
    if period is None or not period.fiscal_year_id:
        return None
    fy = database.session.get(FiscalYear, period.fiscal_year_id)
    return fy.year_start_date if fy else None


_PL_CLASSIFICATIONS = frozenset({"ingreso", "income", "costo", "cost", "gasto", "expense"})


def get_balance_sheet_report(filters: FinancialReportFilters) -> PaginatedReport:
    """Balance general por clasificación Activo/Pasivo/Patrimonio."""
    _, period_end, period_obj = _period_bounds(filters.company, filters.accounting_period)
    fiscal_year_start = _fiscal_year_start_for_period(period_obj)
    selected_ledger = _resolve_ledger(filters.company, filters.ledger)
    if selected_ledger is None:
        return PaginatedReport(rows=[], totals={}, columns=[])
    # For balance sheet, query with include_closing=True to retrieve the closing entries (e.g. for retained earnings)
    query_filters = replace(filters, include_closing=True)
    base_query = select(GLEntry, Accounts).join(Accounts, Accounts.id == GLEntry.account_id, isouter=True)
    base_query = _apply_gl_filters(base_query, query_filters, None, period_end).where(GLEntry.ledger_id == selected_ledger.id)

    by_account: dict[str, dict[str, Any]] = {}
    totals: dict[str, Decimal] = {
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
        # Skip closing entries if include_closing is False and they are P&L or current FY
        if not filters.include_closing and entry.is_fiscal_year_closing:
            if classification in _PL_CLASSIFICATIONS or (fiscal_year_start and entry.posting_date >= fiscal_year_start):
                continue
        # Limitar cuentas de P&L al año fiscal para no acumular ejercicios cerrados
        if classification in _PL_CLASSIFICATIONS and fiscal_year_start and entry.posting_date < fiscal_year_start:
            continue
        debit = _decimal_value(entry.debit)
        credit = _decimal_value(entry.credit)
        account_code = account.code or (entry.account_code or "")
        account_name = account.name
        _accumulate_balance_sheet_entry(
            classification,
            debit,
            credit,
            account_code,
            account_name,
            by_account,
            totals,
        )

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
    query = select(PurchaseInvoice).filter_by(company=filters.company, docstatus=1)
    if filters.party_id:
        query = query.filter_by(supplier_id=filters.party_id)
    if filters.date_from:
        query = query.where(PurchaseInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(PurchaseInvoice.posting_date <= filters.date_to)
    totals: dict[str, Decimal] = {}
    for invoice in database.session.execute(query).scalars():
        supplier_id = invoice.supplier_id or ""
        amount = _invoice_report_amount(invoice)
        totals[supplier_id] = totals.get(supplier_id, Decimal("0")) + (-amount if invoice.is_return else amount)
    rows = [ReportRow({"supplier_id": supplier_id, "amount": amount}) for supplier_id, amount in sorted(totals.items())]
    return PaginatedReport(rows=rows, totals={"amount": sum(totals.values(), Decimal("0"))})


def get_purchases_by_item(filters: OperationalReportFilters) -> PaginatedReport:
    """Compras agregadas por item."""
    query = (
        select(PurchaseInvoice, PurchaseInvoiceItem)
        .join(PurchaseInvoiceItem, PurchaseInvoiceItem.purchase_invoice_id == PurchaseInvoice.id)
        .filter(PurchaseInvoice.company == filters.company, PurchaseInvoice.docstatus == 1)
    )
    if filters.item_code:
        query = query.filter(PurchaseInvoiceItem.item_code == filters.item_code)
    if filters.date_from:
        query = query.where(PurchaseInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(PurchaseInvoice.posting_date <= filters.date_to)
    totals: dict[str, dict[str, Decimal]] = {}
    for invoice, item in database.session.execute(query).all():
        sign = Decimal("-1") if invoice.is_return else Decimal("1")
        row = totals.setdefault(item.item_code, {"qty": Decimal("0"), "amount": Decimal("0")})
        row["qty"] += sign * _decimal_value(item.qty)
        row["amount"] += sign * _decimal_value(item.base_amount if item.base_amount is not None else item.amount)
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
    query = select(SalesInvoice).filter_by(company=filters.company, docstatus=1)
    if filters.party_id:
        query = query.filter_by(customer_id=filters.party_id)
    if filters.date_from:
        query = query.where(SalesInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(SalesInvoice.posting_date <= filters.date_to)
    totals: dict[str, Decimal] = {}
    for invoice in database.session.execute(query).scalars():
        customer_id = invoice.customer_id or ""
        amount = _invoice_report_amount(invoice)
        totals[customer_id] = totals.get(customer_id, Decimal("0")) + (-amount if invoice.is_return else amount)
    rows = [ReportRow({"customer_id": customer_id, "amount": amount}) for customer_id, amount in sorted(totals.items())]
    return PaginatedReport(rows=rows, totals={"amount": sum(totals.values(), Decimal("0"))})


def get_sales_by_item(filters: OperationalReportFilters) -> PaginatedReport:
    """Ventas agregadas por item."""
    query = (
        select(SalesInvoice, SalesInvoiceItem)
        .join(SalesInvoiceItem, SalesInvoiceItem.sales_invoice_id == SalesInvoice.id)
        .filter(SalesInvoice.company == filters.company, SalesInvoice.docstatus == 1)
    )
    if filters.item_code:
        query = query.filter(SalesInvoiceItem.item_code == filters.item_code)
    if filters.date_from:
        query = query.where(SalesInvoice.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(SalesInvoice.posting_date <= filters.date_to)
    totals: dict[str, dict[str, Decimal]] = {}
    for invoice, item in database.session.execute(query).all():
        sign = Decimal("-1") if invoice.is_return else Decimal("1")
        row = totals.setdefault(item.item_code, {"qty": Decimal("0"), "amount": Decimal("0")})
        row["qty"] += sign * _decimal_value(item.qty)
        row["amount"] += sign * _decimal_value(item.base_amount if item.base_amount is not None else item.amount)
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
    query = exclude_cancelled_gl_entries(
        select(GLEntry, Accounts)
        .join(Accounts, Accounts.id == GLEntry.account_id)
        .where(GLEntry.company == filters.company, Accounts.entity == filters.company)
    )
    ledger_id = primary_ledger_id(filters.company)
    if ledger_id:
        query = query.where(GLEntry.ledger_id == ledger_id)
    if filters.date_from:
        query = query.where(GLEntry.posting_date >= filters.date_from)
    if filters.date_to:
        query = query.where(GLEntry.posting_date <= filters.date_to)
    income = Decimal("0")
    cogs = Decimal("0")
    for entry, account in database.session.execute(query).all():
        classification = (account.classification or "").lower()
        if classification in {"costo", "cost"}:
            cogs += _decimal_value(entry.debit) - _decimal_value(entry.credit)
        elif classification in {"ingreso", "income"}:
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
    if filters.date_to:
        query = query.where(StockValuationLayer.posting_date <= filters.date_to)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for layer in database.session.execute(
        query.order_by(StockValuationLayer.posting_date, StockValuationLayer.created, StockValuationLayer.id)
    ).scalars():
        key = (layer.item_code, layer.warehouse)
        if key not in grouped:
            grouped[key] = {
                "item_code": layer.item_code,
                "warehouse": layer.warehouse,
                "remaining_qty": Decimal("0"),
                "remaining_stock_value": Decimal("0"),
            }
        grouped[key]["remaining_qty"] += _decimal_value(layer.qty)
        grouped[key]["remaining_stock_value"] += _decimal_value(layer.stock_value_difference)
    rows = [
        ReportRow(
            {
                "item_code": val["item_code"],
                "warehouse": val["warehouse"],
                "remaining_qty": _decimal_value(val["remaining_qty"]),
                "remaining_stock_value": _decimal_value(val["remaining_stock_value"]),
            }
        )
        for val in grouped.values()
        if _decimal_value(val["remaining_qty"]) != Decimal("0")
    ]
    rows.sort(key=lambda row: (str(row.values["item_code"]), str(row.values["warehouse"])))
    return PaginatedReport(
        rows=rows,
        totals={
            "remaining_stock_value": sum((_decimal_value(row.values["remaining_stock_value"]) for row in rows), Decimal("0"))
        },
    )


def get_batch_report(filters: OperationalReportFilters) -> PaginatedReport:
    """Report inventory batches."""
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
    """Report inventory serial numbers."""
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
