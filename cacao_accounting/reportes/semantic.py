"""Stable semantic dataset services used by external reporting adapters.

These functions deliberately return plain dictionaries rather than ORM
objects.  Connector and future BI adapters can therefore consume the same
company-scoped, read-only domain projection without learning the database
schema.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select

from cacao_accounting.database import (
    AuditTrail,
    DocumentRelation,
    PaymentEntry,
    PaymentReference,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    SalesInvoice,
    SalesInvoiceItem,
    StockEntry,
    StockEntryItem,
    database,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount
from cacao_accounting.reportes.services import (
    OperationalReportFilters,
    get_inventory_turnover,
    get_negative_stock,
    get_slow_moving_items,
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _bounded(query: Any, limit: int | None, offset: int | None) -> Any:
    if offset is not None:
        query = query.offset(max(offset, 0))
    if limit is not None:
        query = query.limit(max(limit, 0))
    return query


def get_sales_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    item_code: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Return one row per posted sales invoice line."""
    query = (
        select(SalesInvoice, SalesInvoiceItem)
        .join(SalesInvoiceItem, SalesInvoiceItem.sales_invoice_id == SalesInvoice.id)
        .where(SalesInvoice.docstatus == 1)
    )
    if company:
        query = query.where(SalesInvoice.company == company)
    if date_from:
        query = query.where(SalesInvoice.posting_date >= date_from)
    if date_to:
        query = query.where(SalesInvoice.posting_date <= date_to)
    if item_code:
        query = query.where(SalesInvoiceItem.item_code == item_code)
    query = _bounded(query.order_by(SalesInvoice.posting_date, SalesInvoice.id), limit, offset)
    return [
        {
            "document_number": invoice.document_no or invoice.id,
            "date": invoice.posting_date,
            "company_code": invoice.company,
            "customer_code": invoice.customer_id,
            "item_code": line.item_code,
            "quantity": _decimal(line.qty),
            "amount": _decimal(line.amount),
        }
        for invoice, line in database.session.execute(query).all()
    ]


def get_purchase_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    item_code: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Return one row per posted purchase invoice line."""
    query = (
        select(PurchaseInvoice, PurchaseInvoiceItem)
        .join(PurchaseInvoiceItem, PurchaseInvoiceItem.purchase_invoice_id == PurchaseInvoice.id)
        .where(PurchaseInvoice.docstatus == 1)
    )
    if company:
        query = query.where(PurchaseInvoice.company == company)
    if date_from:
        query = query.where(PurchaseInvoice.posting_date >= date_from)
    if date_to:
        query = query.where(PurchaseInvoice.posting_date <= date_to)
    if item_code:
        query = query.where(PurchaseInvoiceItem.item_code == item_code)
    query = _bounded(query.order_by(PurchaseInvoice.posting_date, PurchaseInvoice.id), limit, offset)
    return [
        {
            "document_number": invoice.document_no or invoice.id,
            "date": invoice.posting_date,
            "company_code": invoice.company,
            "supplier_code": invoice.supplier_id,
            "item_code": line.item_code,
            "quantity": _decimal(line.qty),
            "amount": _decimal(line.amount),
        }
        for invoice, line in database.session.execute(query).all()
    ]


def get_receivables_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Return one row per posted customer invoice with live outstanding value."""
    query = select(SalesInvoice).where(SalesInvoice.docstatus == 1)
    if company:
        query = query.where(SalesInvoice.company == company)
    if date_from:
        query = query.where(SalesInvoice.posting_date >= date_from)
    if date_to:
        query = query.where(SalesInvoice.posting_date <= date_to)
    query = _bounded(query.order_by(SalesInvoice.posting_date, SalesInvoice.id), limit, offset)
    return [
        {
            "document_number": invoice.document_no or invoice.id,
            "date": invoice.posting_date,
            "company_code": invoice.company,
            "customer_code": invoice.customer_id,
            "amount": _decimal(invoice.grand_total or invoice.total),
            "outstanding_amount": _decimal(compute_outstanding_amount(invoice)),
        }
        for invoice in database.session.execute(query).scalars().all()
    ]


def get_payables_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Return one row per posted supplier invoice with live outstanding value."""
    query = select(PurchaseInvoice).where(PurchaseInvoice.docstatus == 1)
    if company:
        query = query.where(PurchaseInvoice.company == company)
    if date_from:
        query = query.where(PurchaseInvoice.posting_date >= date_from)
    if date_to:
        query = query.where(PurchaseInvoice.posting_date <= date_to)
    query = _bounded(query.order_by(PurchaseInvoice.posting_date, PurchaseInvoice.id), limit, offset)
    return [
        {
            "document_number": invoice.document_no or invoice.id,
            "date": invoice.posting_date,
            "company_code": invoice.company,
            "supplier_code": invoice.supplier_id,
            "amount": _decimal(invoice.grand_total or invoice.total),
            "outstanding_amount": _decimal(compute_outstanding_amount(invoice)),
        }
        for invoice in database.session.execute(query).scalars().all()
    ]


def get_settlement_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Return payment applications at their allocation grain (N:N safe)."""
    query = select(PaymentReference, PaymentEntry).join(PaymentEntry, PaymentEntry.id == PaymentReference.payment_id)
    if company:
        query = query.where(
            PaymentEntry.company == company,
            or_(PaymentReference.company.is_(None), PaymentReference.company == company),
        )
    if date_from:
        query = query.where(PaymentReference.allocation_date >= date_from)
    if date_to:
        query = query.where(PaymentReference.allocation_date <= date_to)
    query = _bounded(query.order_by(PaymentReference.allocation_date, PaymentReference.id), limit, offset)
    return [
        {
            "document_number": reference.reference_document_no or reference.reference_id,
            "date": reference.allocation_date or payment.posting_date,
            "company_code": reference.company or payment.company,
            "supplier_code": reference.party_id if reference.party_type == "supplier" else None,
            "customer_code": reference.party_id if reference.party_type == "customer" else None,
            "amount": _decimal(reference.allocated_amount),
        }
        for reference, payment in database.session.execute(query).all()
    ]


def get_document_relations(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    query = select(DocumentRelation)
    if company:
        query = query.where(DocumentRelation.company == company)
    if date_from:
        query = query.where(DocumentRelation.created >= date_from)
    if date_to:
        query = query.where(DocumentRelation.created < date_to + timedelta(days=1))
    query = _bounded(query.order_by(DocumentRelation.created, DocumentRelation.id), limit, offset)
    return [
        {
            "relation_id": relation.id,
            "company_code": relation.company,
            "source_document_id": relation.source_id,
            "target_document_id": relation.target_id,
            "relation_type": relation.relation_type,
        }
        for relation in database.session.execute(query).scalars().all()
    ]


def get_audit_events(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    query = select(AuditTrail)
    if company:
        query = query.where(AuditTrail.company == company)
    if date_from:
        query = query.where(AuditTrail.timestamp >= date_from)
    if date_to:
        query = query.where(AuditTrail.timestamp < date_to + timedelta(days=1))
    query = _bounded(query.order_by(AuditTrail.timestamp, AuditTrail.id), limit, offset)
    return [
        {
            "audit_event_id": event.id,
            "company_code": event.company,
            "entity_type": event.document_type,
            "entity_id": event.document_id,
            "action": event.action,
            "actor_user_id": event.actor_user_id,
            "timestamp": event.timestamp,
        }
        for event in database.session.execute(query).scalars().all()
    ]


def _report_items(report: Any, company: str) -> list[dict[str, Any]]:
    return [{"company_code": company, **row.values} for row in report.rows]


def get_inventory_slow_moving_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    if not company:
        return []
    rows = _report_items(
        get_slow_moving_items(OperationalReportFilters(company=company, date_to=date_to), as_of_date=date_to), company
    )
    return rows[(offset or 0) : (offset or 0) + limit] if limit is not None else rows[(offset or 0) :]


def get_inventory_negative_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    if not company:
        return []
    rows = _report_items(get_negative_stock(OperationalReportFilters(company=company)), company)
    return rows[(offset or 0) : (offset or 0) + limit] if limit is not None else rows[(offset or 0) :]


def get_inventory_turnover_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    if not company:
        return []
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=365))
    rows = _report_items(
        get_inventory_turnover(OperationalReportFilters(company=company, date_from=start, date_to=end)), company
    )
    return rows[(offset or 0) : (offset or 0) + limit] if limit is not None else rows[(offset or 0) :]


def get_inventory_transfer_analysis(
    company: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict[str, Any]]:
    """Return one governed row per material-transfer line."""
    if not company:
        return []
    query = (
        select(StockEntry, StockEntryItem)
        .join(StockEntryItem, StockEntryItem.stock_entry_id == StockEntry.id)
        .where(StockEntry.company == company, StockEntry.purpose == "material_transfer", StockEntry.docstatus != 2)
    )
    if date_from:
        query = query.where(StockEntry.posting_date >= date_from)
    if date_to:
        query = query.where(StockEntry.posting_date <= date_to)
    query = _bounded(query.order_by(StockEntry.posting_date, StockEntry.id, StockEntryItem.id), limit, offset)
    return [
        {
            "transfer_id": entry.id,
            "document_number": entry.document_no or entry.id,
            "date": entry.posting_date,
            "company_code": entry.company,
            "item_code": line.item_code,
            "from_warehouse": line.source_warehouse or entry.from_warehouse,
            "to_warehouse": line.target_warehouse or entry.to_warehouse,
            "quantity": _decimal(line.qty_in_base_uom or line.qty),
            "uom": line.uom,
            "status": {0: "draft", 1: "submitted", 2: "cancelled"}.get(entry.docstatus, "unknown"),
        }
        for entry, line in database.session.execute(query).all()
    ]
