"""Deterministic, bounded analytical services for executive questions."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from cacao_accounting.database import (
    Accounts,
    GLEntry,
    PurchaseInvoice,
    SalesInvoice,
    SalesInvoiceItem,
    StockBin,
    database,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount

ALLOWED_METRICS = frozenset({"sales", "purchases", "income", "expenses", "gross_margin"})
ALLOWED_DIMENSIONS = frozenset({"customer", "supplier", "item"})


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _percentage(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * Decimal("100")


def _invoice_total(model: Any, company: str, start: date, end: date) -> Decimal:
    query = select(model).where(
        model.company == company,
        model.docstatus == 1,
        model.posting_date >= start,
        model.posting_date <= end,
    )
    return sum((_decimal(row.grand_total or row.total) for row in database.session.execute(query).scalars()), Decimal("0"))


def _gl_totals(company: str, start: date, end: date) -> dict[str, Decimal]:
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
        return gl["net_income"]
    if metric == "expenses":
        return gl["expense"]
    return gl["income"] - gl["cost"]


def get_kpi_snapshot(company: str, start: date, end: date) -> dict[str, Any]:
    """Build a read-only KPI snapshot for a company and date range."""
    gl = _gl_totals(company, start, end)
    sales = _invoice_total(SalesInvoice, company, start, end)
    purchases = _invoice_total(PurchaseInvoice, company, start, end)
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
    ar = sum((_decimal(compute_outstanding_amount(row, as_of_date=end)) for row in ar_rows), Decimal("0"))
    ap = sum((_decimal(compute_outstanding_amount(row, as_of_date=end)) for row in ap_rows), Decimal("0"))
    inventory = database.session.execute(
        select(StockBin.stock_value).where(StockBin.company == company)
    ).scalars()
    inventory_value = sum((_decimal(value) for value in inventory), Decimal("0"))
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
        "currency": None,
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
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    if dimension == "customer":
        rows = database.session.execute(
            select(SalesInvoice).where(
                SalesInvoice.company == company,
                SalesInvoice.docstatus == 1,
                SalesInvoice.posting_date >= start,
                SalesInvoice.posting_date <= end,
            )
        ).scalars()
        for row in rows:
            totals[row.customer_id or ""] += _decimal(row.grand_total or row.total)
    elif dimension == "supplier":
        rows = database.session.execute(
            select(PurchaseInvoice).where(
                PurchaseInvoice.company == company,
                PurchaseInvoice.docstatus == 1,
                PurchaseInvoice.posting_date >= start,
                PurchaseInvoice.posting_date <= end,
            )
        ).scalars()
        for row in rows:
            totals[row.supplier_id or ""] += _decimal(row.grand_total or row.total)
    else:
        query = (
            select(SalesInvoiceItem, SalesInvoice)
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.sales_invoice_id)
            .where(
                SalesInvoice.company == company,
                SalesInvoice.docstatus == 1,
                SalesInvoice.posting_date >= start,
                SalesInvoice.posting_date <= end,
            )
        )
        for item, _ in database.session.execute(query).all():
            totals[item.item_code] += _decimal(item.amount)
    ordered = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    grand_total = sum(totals.values(), Decimal("0"))
    return [
        {
            "dimension": dimension,
            "key": key,
            "amount": amount,
            "share_percentage": _percentage(amount, grand_total) or Decimal("0"),
        }
        for key, amount in ordered[: max(1, min(limit, 100))]
    ]
