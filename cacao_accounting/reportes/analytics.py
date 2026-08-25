"""Deterministic, bounded analytical services for executive questions."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import (
    Accounts,
    Book,
    Entity,
    ExchangeRate,
    GLEntry,
    PurchaseInvoice,
    SalesInvoice,
    SalesInvoiceItem,
    StockBin,
    database,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount
from cacao_accounting.ledger_queries import primary_ledger_id

ALLOWED_METRICS = frozenset({"sales", "purchases", "income", "expenses", "gross_margin"})
ALLOWED_DIMENSIONS = frozenset({"customer", "supplier", "item"})


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _percentage(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * Decimal("100")


def _invoice_base_amount(row: Any) -> Decimal:
    """Devuelve el total de la factura en la moneda base del documento."""
    amount = row.base_grand_total
    if amount is None:
        amount = row.base_total
    if amount is None:
        amount = row.grand_total or row.total
    amount = _decimal(amount)
    return -amount if getattr(row, "is_return", False) else amount


def _invoice_total(model: Any, company: str, start: date, end: date) -> Decimal:
    query = select(model).where(
        model.company == company,
        model.docstatus == 1,
        model.posting_date >= start,
        model.posting_date <= end,
    )
    return sum((_invoice_base_amount(row) for row in database.session.execute(query).scalars()), Decimal("0"))


def _convert_to_ledger_currency(
    amount: Decimal,
    source_currency: str | None,
    target_currency: str | None,
    as_of_date: date,
) -> Decimal:
    """Convierte un importe usando la tasa histórica registrada."""
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
        return amount * _decimal(rate.rate)
    inverse = (
        database.session.execute(
            select(ExchangeRate).filter_by(origin=target_currency, destination=source_currency, date=as_of_date)
        )
        .scalars()
        .first()
    )
    if inverse is not None:
        inv_value = _decimal(inverse.rate)
        if inv_value == 0:
            return Decimal("0")
        return amount / inv_value
    raise ValueError(f"No existe tipo de cambio de {source_currency} a {target_currency} en {as_of_date}.")


def _gl_totals(company: str, start: date, end: date, ledger_id: str | None = None) -> dict[str, Decimal]:
    query = (
        select(GLEntry, Accounts)
        .outerjoin(Accounts, (Accounts.id == GLEntry.account_id) & (Accounts.entity == company))
        .where(
            GLEntry.company == company,
            GLEntry.posting_date >= start,
            GLEntry.posting_date <= end,
            GLEntry.is_cancelled.is_(False),
            GLEntry.is_reversal.is_(False),
        )
    )
    effective_ledger = ledger_id or primary_ledger_id(company)
    if effective_ledger:
        query = query.where(GLEntry.ledger_id == effective_ledger)
    totals = {"income": Decimal("0"), "cost": Decimal("0"), "expense": Decimal("0")}
    for entry, account in database.session.execute(query).all():
        classification = (getattr(account, "classification", "") or "").lower()
        amount = _decimal(entry.credit) - _decimal(entry.debit)
        if classification in {"ingreso", "income"}:
            totals["income"] += amount
        elif classification in {"costo", "cost"}:
            totals["cost"] -= amount
        elif classification in {"gasto", "expense"}:
            totals["expense"] -= amount
    totals["net_income"] = totals["income"] - totals["cost"] - totals["expense"]
    return totals


def metric_value(company: str, metric: str, start: date, end: date) -> Decimal:
    """Calculate one approved metric for a company and date range."""
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"Métrica no permitida: {metric}")
    if metric == "sales":
        return _invoice_total(SalesInvoice, company, start, end)
    if metric == "purchases":
        return _invoice_total(PurchaseInvoice, company, start, end)
    gl = _gl_totals(company, start, end)
    if metric == "income":
        return gl["income"]
    if metric == "expenses":
        return gl["expense"]
    return gl["income"] - gl["cost"]


def _document_base_factor(document: Any) -> Decimal:
    """Devuelve el factor historico de moneda original a moneda base del documento."""
    original = _decimal(getattr(document, "grand_total", None) or getattr(document, "total", None))
    base_value = getattr(document, "base_grand_total", None)
    if base_value is None:
        base_value = getattr(document, "base_total", None)
    if base_value is not None and original != 0:
        return _decimal(base_value) / original
    rate = _decimal(getattr(document, "exchange_rate", None))
    return rate if rate > 0 else Decimal("1")


def get_kpi_snapshot(company: str, start: date, end: date, ledger: str | None = None) -> dict[str, Any]:
    """Build a read-only KPI snapshot for a company and date range.

    When *ledger* is provided the GL amounts are filtered by that book and
    all invoice-based totals are converted to the ledger currency so that
    metrics are expressed in a single, explicit currency.
    """
    base_currency = database.session.execute(select(Entity.currency).where(Entity.code == company)).scalar_one_or_none()
    ledger_currency = base_currency
    if ledger:
        book = database.session.execute(select(Book).where(Book.entity == company, Book.code == ledger)).scalars().first()
        if book is None:
            book = database.session.get(Book, ledger)
        if book is not None and book.currency:
            ledger_currency = book.currency
    gl = _gl_totals(company, start, end, ledger_id=ledger)
    _needs_conversion = ledger_currency and base_currency and ledger_currency != base_currency
    _target = ledger_currency if _needs_conversion else base_currency

    def _to_ledger(amount: Decimal) -> Decimal:
        if not _needs_conversion:
            return amount
        return _convert_to_ledger_currency(amount, base_currency, ledger_currency, end)

    sales = _to_ledger(_invoice_total(SalesInvoice, company, start, end))
    purchases = _to_ledger(_invoice_total(PurchaseInvoice, company, start, end))
    ar_rows = database.session.execute(
        select(SalesInvoice).where(
            SalesInvoice.company == company,
            SalesInvoice.docstatus == 1,
            SalesInvoice.posting_date <= end,
        )
    ).scalars()
    ap_rows = database.session.execute(
        select(PurchaseInvoice).where(
            PurchaseInvoice.company == company,
            PurchaseInvoice.docstatus == 1,
            PurchaseInvoice.posting_date <= end,
        )
    ).scalars()
    ar = _to_ledger(
        sum(
            (
                (-1 if row.is_return else 1)
                * _decimal(compute_outstanding_amount(row, as_of_date=end))
                * _document_base_factor(row)
                for row in ar_rows
            ),
            Decimal("0"),
        )
    )
    ap = _to_ledger(
        sum(
            (
                (-1 if row.is_return else 1)
                * _decimal(compute_outstanding_amount(row, as_of_date=end))
                * _document_base_factor(row)
                for row in ap_rows
            ),
            Decimal("0"),
        )
    )
    inventory = database.session.execute(select(StockBin.stock_value).where(StockBin.company == company)).scalars()
    inventory_value = _to_ledger(sum((_decimal(value) for value in inventory), Decimal("0")))
    return {
        "company_id": company,
        "date_from": start,
        "date_to": end,
        "metrics": {
            "sales": sales,
            "purchases": purchases,
            "income": gl["income"],
            "cost": gl["cost"],
            "expenses": gl["expense"],
            "net_income": gl["net_income"],
            "accounts_receivable": ar,
            "accounts_payable": ap,
            "working_capital": ar + inventory_value - ap,
            "inventory_value": inventory_value,
        },
        "currency": _target,
        "complete": True,
    }


def compare_periods(
    company: str,
    metric: str,
    base_start: date,
    base_end: date,
    compare_start: date,
    compare_end: date,
) -> dict[str, Any]:
    """Compare one approved metric across two date ranges."""
    current = metric_value(company, metric, base_start, base_end)
    previous = metric_value(company, metric, compare_start, compare_end)
    return {
        "metric": metric,
        "base_period": {"date_from": base_start, "date_to": base_end, "value": current},
        "comparison_period": {"date_from": compare_start, "date_to": compare_end, "value": previous},
        "variance": current - previous,
        "variance_percentage": _percentage(current, previous),
        "complete": True,
    }


def get_trend(company: str, metric: str, start: date, end: date) -> list[dict[str, Any]]:
    """Return monthly values for one approved metric."""
    if metric not in ALLOWED_METRICS:
        raise ValueError(f"Métrica no permitida: {metric}")
    buckets: list[tuple[date, date]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        next_month = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        bucket_end = min(end, next_month.fromordinal(next_month.toordinal() - 1))
        buckets.append((max(cursor, start), bucket_end))
        cursor = next_month
    return [
        {
            "period": f"{bucket_start:%Y-%m}",
            "date_from": bucket_start,
            "date_to": bucket_end,
            "value": metric_value(company, metric, bucket_start, bucket_end),
        }
        for bucket_start, bucket_end in buckets
        if bucket_start <= bucket_end
    ]


def get_concentration(company: str, dimension: str, start: date, end: date, limit: int = 10) -> list[dict[str, Any]]:
    """Return the largest contributors for an approved dimension."""
    if dimension not in ALLOWED_DIMENSIONS:
        raise ValueError(f"Dimensión no permitida: {dimension}")
    totals = _concentration_totals(company, dimension, start, end)
    ordered = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    grand_total = sum(totals.values(), Decimal("0"))
    return [
        {
            "dimension": dimension,
            "key": key,
            "amount": amount,
            "share_percentage": _share_percentage(amount, grand_total),
        }
        for key, amount in ordered[: max(1, min(limit, 100))]
    ]


def _share_percentage(amount: Decimal, total: Decimal) -> Decimal:
    """Return an item's signed contribution to a concentration total."""
    if total == 0:
        return Decimal("0")
    return amount / total * Decimal("100")


def _concentration_totals(company: str, dimension: str, start: date, end: date) -> defaultdict[str, Decimal]:
    """Aggregate approved invoice values by a concentration dimension."""
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    if dimension == "customer":
        rows = database.session.execute(_concentration_invoice_query(SalesInvoice, company, start, end)).scalars()
        for row in rows:
            totals[getattr(row, "customer_id") or ""] += _invoice_base_amount(row)
        return totals
    if dimension == "supplier":
        rows = database.session.execute(_concentration_invoice_query(PurchaseInvoice, company, start, end)).scalars()
        for row in rows:
            totals[getattr(row, "supplier_id") or ""] += _invoice_base_amount(row)
        return totals
    query = _concentration_item_query(company, start, end)
    for item, invoice in database.session.execute(query).all():
        amount = _decimal(item.base_amount if item.base_amount is not None else item.amount)
        totals[item.item_code] += -amount if invoice.is_return else amount
    return totals


def _concentration_invoice_query(model: Any, company: str, start: date, end: date) -> Any:
    """Build the shared invoice query for customer and supplier concentration."""
    return select(model).where(
        model.company == company, model.docstatus == 1, model.posting_date >= start, model.posting_date <= end
    )


def _concentration_item_query(company: str, start: date, end: date) -> Any:
    """Build the sales-item query for item concentration."""
    return (
        select(SalesInvoiceItem, SalesInvoice)
        .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.sales_invoice_id)
        .where(
            SalesInvoice.company == company,
            SalesInvoice.docstatus == 1,
            SalesInvoice.posting_date >= start,
            SalesInvoice.posting_date <= end,
        )
    )
