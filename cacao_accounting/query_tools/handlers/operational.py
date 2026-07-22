"""Read-only operational drill-down queries for treasury and audit users."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import func

from cacao_accounting.database import (
    AuditTrail,
    DocumentRelation,
    ExchangeRevaluation,
    PaymentEntry,
    PaymentReference,
    database,
)
from cacao_accounting.document_flow.payment import compute_payment_unallocated_amount
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import PaginatedResult, paginate
from cacao_accounting.query_tools.permissions import validate_permission


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _decimal(value: Any) -> str:
    return str(Decimal(str(value or 0)))


def _with_provenance(result: dict[str, Any], company_id: str, **filters: Any) -> dict[str, Any]:
    page = result.get("page") or {}
    result["provenance"] = {
        "company_id": company_id,
        "filters": {key: value for key, value in filters.items() if value is not None},
        "completeness": {
            "truncated": bool(page.get("has_more")),
            "returned_items": len(result.get("items", [])),
            "total_items": page.get("total_items", len(result.get("items", []))),
        },
    }
    return result


_PAYMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
        "party_id": {"type": "string"},
        "payment_type": {"type": "string", "enum": ["receive", "pay", "internal_transfer"]},
        "page": {"type": "integer", "minimum": 1, "default": 1},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
    },
    "required": ["company_id"],
}


def _payment_items(rows: list[PaymentEntry] | Sequence[PaymentEntry]) -> list[dict[str, Any]]:
    return [
        {
            "id": row.id,
            "document_no": row.document_no,
            "posting_date": row.posting_date.isoformat() if row.posting_date else None,
            "company_id": row.company,
            "payment_type": row.payment_type,
            "party_type": row.party_type,
            "party_id": row.party_id,
            "party_name": row.party_name,
            "bank_account_id": row.bank_account_id,
            "currency": row.currency,
            "paid_amount": _decimal(row.paid_amount),
            "received_amount": _decimal(row.received_amount),
            "base_paid_amount": _decimal(row.base_paid_amount),
            "base_received_amount": _decimal(row.base_received_amount),
            "status": row.status,
            "docstatus": row.docstatus,
            "created_by": row.created_by,
        }
        for row in rows
    ]


@query_tool(
    "payments.search",
    "Busca pagos y cobros de una compañía por fecha, tercero y tipo.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema=_PAYMENT_SCHEMA,
)
def search_payments(
    *,
    context: QueryContext,
    company_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    party_id: str | None = None,
    payment_type: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    current_page, size = paginate(page, page_size)
    query = database.select(PaymentEntry).where(PaymentEntry.company == company_id)
    start, end = _parse_date(date_from), _parse_date(date_to)
    if start:
        query = query.where(PaymentEntry.posting_date >= start)
    if end:
        query = query.where(PaymentEntry.posting_date <= end)
    if party_id:
        query = query.where(PaymentEntry.party_id == party_id)
    if payment_type:
        query = query.where(PaymentEntry.payment_type == payment_type)
    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = database.session.execute(
        query.order_by(PaymentEntry.posting_date.desc(), PaymentEntry.created.desc())
        .offset((current_page - 1) * size)
        .limit(size)
    ).scalars().all()
    return _with_provenance(
        PaginatedResult(page=current_page, page_size=size, total_items=total, items=_payment_items(rows)).to_dict(),
        company_id,
        date_from=date_from,
        date_to=date_to,
        party_id=party_id,
        payment_type=payment_type,
    )


@query_tool(
    "payments.get_unapplied",
    "Obtiene pagos y cobros con importe todavía no aplicado.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema=_PAYMENT_SCHEMA,
)
def get_unapplied_payments(
    *,
    context: QueryContext,
    company_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    party_id: str | None = None,
    payment_type: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    current_page, size = paginate(page, page_size)
    query = database.select(PaymentEntry).where(PaymentEntry.company == company_id)
    start, end = _parse_date(date_from), _parse_date(date_to)
    if start:
        query = query.where(PaymentEntry.posting_date >= start)
    if end:
        query = query.where(PaymentEntry.posting_date <= end)
    if party_id:
        query = query.where(PaymentEntry.party_id == party_id)
    if payment_type:
        query = query.where(PaymentEntry.payment_type == payment_type)
    rows = database.session.execute(query.order_by(PaymentEntry.posting_date.desc())).scalars().all()
    items = []
    for row in rows:
        unallocated = compute_payment_unallocated_amount(row)
        if unallocated <= 0:
            continue
        item = _payment_items([row])[0]
        item["unallocated_amount"] = _decimal(unallocated)
        items.append(item)
    total = len(items)
    start_index = (current_page - 1) * size
    return _with_provenance(
        PaginatedResult(
            page=current_page,
            page_size=size,
            total_items=total,
            items=items[start_index : start_index + size],
        ).to_dict(),
        company_id,
        date_from=date_from,
        date_to=date_to,
        party_id=party_id,
        payment_type=payment_type,
    )


@query_tool(
    "payments.get_applications",
    "Obtiene las aplicaciones de un pago o de un documento.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "payment_id": {"type": "string"},
            "document_id": {"type": "string"},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
        "required": ["company_id"],
    },
)
def get_payment_applications(
    *,
    context: QueryContext,
    company_id: str,
    payment_id: str | None = None,
    document_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    if not payment_id and not document_id:
        raise ValueError("payment_id o document_id es obligatorio")
    current_page, size = paginate(page, page_size)
    query = database.select(PaymentReference).where(PaymentReference.company == company_id)
    if payment_id:
        query = query.where(PaymentReference.payment_id == payment_id)
    if document_id:
        query = query.where(PaymentReference.reference_id == document_id)
    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = database.session.execute(
        query.order_by(PaymentReference.allocation_date.desc()).offset((current_page - 1) * size).limit(size)
    ).scalars().all()
    items = [
        {
            "id": row.id,
            "payment_id": row.payment_id,
            "reference_type": row.reference_type,
            "reference_id": row.reference_id,
            "reference_document_no": row.reference_document_no,
            "party_type": row.party_type,
            "party_id": row.party_id,
            "company_id": row.company,
            "currency": row.currency,
            "allocated_amount": _decimal(row.allocated_amount),
            "difference_amount": _decimal(row.difference_amount),
            "gain_loss_amount": _decimal(row.gain_loss_amount),
            "allocation_date": row.allocation_date.isoformat() if row.allocation_date else None,
        }
        for row in rows
    ]
    return _with_provenance(
        PaginatedResult(page=current_page, page_size=size, total_items=total, items=items).to_dict(),
        company_id,
        payment_id=payment_id,
        document_id=document_id,
    )


@query_tool(
    "documents.search_relations",
    "Busca relaciones documentales por compañía, documento o tipo de relación.",
    required_permission="documents.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "document_id": {"type": "string"},
            "relation_type": {"type": "string"},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
        "required": ["company_id"],
    },
)
def search_document_relations(
    *,
    context: QueryContext,
    company_id: str,
    document_id: str | None = None,
    relation_type: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "documents.reports.read", None, company_id)
    current_page, size = paginate(page, page_size)
    query = database.select(DocumentRelation).where(DocumentRelation.company == company_id)
    if document_id:
        query = query.where((DocumentRelation.source_id == document_id) | (DocumentRelation.target_id == document_id))
    if relation_type:
        query = query.where(DocumentRelation.relation_type == relation_type)
    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = database.session.execute(
        query.order_by(DocumentRelation.created.desc()).offset((current_page - 1) * size).limit(size)
    ).scalars().all()
    items = [
        {
            "id": row.id,
            "company_id": row.company,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "source_item_id": row.source_item_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "target_item_id": row.target_item_id,
            "relation_type": row.relation_type,
            "qty": _decimal(row.qty),
            "amount": _decimal(row.amount),
        }
        for row in rows
    ]
    return _with_provenance(
        PaginatedResult(page=current_page, page_size=size, total_items=total, items=items).to_dict(),
        company_id,
        document_id=document_id,
        relation_type=relation_type,
    )


@query_tool(
    "audit.search_events",
    "Busca eventos de auditoría por compañía, documento, acción y fecha.",
    required_permission="audit.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "document_id": {"type": "string"},
            "action": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
        "required": ["company_id"],
    },
)
def search_audit_events(
    *,
    context: QueryContext,
    company_id: str,
    document_id: str | None = None,
    action: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "audit.reports.read", None, company_id)
    current_page, size = paginate(page, page_size)
    query = database.select(AuditTrail).where(AuditTrail.company == company_id)
    if document_id:
        query = query.where(AuditTrail.document_id == document_id)
    if action:
        query = query.where(AuditTrail.action == action)
    start, end = _parse_date(date_from), _parse_date(date_to)
    if start:
        query = query.where(func.date(AuditTrail.timestamp) >= start)
    if end:
        query = query.where(func.date(AuditTrail.timestamp) <= end)
    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = database.session.execute(
        query.order_by(AuditTrail.timestamp.desc()).offset((current_page - 1) * size).limit(size)
    ).scalars().all()
    items = [
        {
            "id": row.id,
            "company_id": row.company,
            "document_type": row.document_type,
            "document_id": row.document_id,
            "document_no": row.document_no,
            "action": row.action,
            "actor_user_id": row.actor_user_id,
            "actor_name": row.actor_name,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            "comment": row.comment,
            "source_module": row.source_module,
        }
        for row in rows
    ]
    return _with_provenance(
        PaginatedResult(page=current_page, page_size=size, total_items=total, items=items).to_dict(),
        company_id,
        document_id=document_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )


@query_tool(
    "accounting.get_revaluations",
    "Consulta ejecuciones de revalorización cambiaria y sus ganancias o pérdidas.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "year": {"type": "integer"},
            "currency": {"type": "string"},
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
        "required": ["company_id"],
    },
)
def get_revaluations(
    *,
    context: QueryContext,
    company_id: str,
    year: int | None = None,
    currency: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    current_page, size = paginate(page, page_size)
    query = database.select(ExchangeRevaluation).where(ExchangeRevaluation.company == company_id)
    if year is not None:
        query = query.where(ExchangeRevaluation.year == year)
    if currency:
        query = query.where(ExchangeRevaluation.currency == currency)
    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = database.session.execute(
        query.order_by(ExchangeRevaluation.run_date.desc()).offset((current_page - 1) * size).limit(size)
    ).scalars().all()
    items = [
        {
            "id": row.id,
            "company_id": row.company,
            "year": row.year,
            "month": row.month,
            "run_date": row.run_date.isoformat() if row.run_date else None,
            "currency": row.currency,
            "generated_journal": row.generated_journal,
            "journal_entry_id": row.journal_entry_id,
            "processed_documents_count": row.processed_documents_count,
            "affected_documents_count": row.affected_documents_count,
            "total_gain": _decimal(row.total_gain),
            "total_loss": _decimal(row.total_loss),
        }
        for row in rows
    ]
    return _with_provenance(
        PaginatedResult(page=current_page, page_size=size, total_items=total, items=items).to_dict(),
        company_id,
        year=year,
        currency=currency,
    )
