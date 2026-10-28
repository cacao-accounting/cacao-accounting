# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Adapt the official AR/AP aging report to query-tool pagination."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import or_, select

from cacao_accounting.database import Entity, PurchaseInvoice, SalesInvoice, database
from cacao_accounting.document_flow.payment import _document_active_at_cutoff, compute_outstanding_amount
from cacao_accounting.query_tools.pagination import PaginatedResult, paginate
from cacao_accounting.reportes.services import AgingFilters, get_aging_report


@dataclass(frozen=True)
class AgingQuery:
    """Filters and pagination options shared by AR and AP aging tools."""

    company_id: str
    party_type: str
    party_id: str | None
    as_of_date: date
    page: int
    page_size: int


def get_aging_result(query: AgingQuery) -> dict[str, Any]:
    """Return document details and canonical bucket totals for an AR/AP cutoff."""
    page, page_size = paginate(query.page, query.page_size)
    report = _load_aging_report(query)
    documents = _load_documents(query)
    result = _paginated_result(report, documents, query, page, page_size)
    result["summary"] = {bucket: str(amount) for bucket, amount in report.totals.items()}
    result["summary_currency"] = database.session.execute(
        select(Entity.currency).where(Entity.code == query.company_id)
    ).scalar_one_or_none()
    return result


def _load_aging_report(query: AgingQuery) -> Any:
    """Run the shared accounting report with the query tool's filters."""
    return get_aging_report(
        AgingFilters(
            company=query.company_id,
            party_type=query.party_type,
            party_id=query.party_id,
            as_of_date=query.as_of_date,
        )
    )


def _load_documents(query: AgingQuery) -> dict[str, Any]:
    """Load document fields retained by the established query-tool response."""
    model, party_id_field, _party_name_field = _document_model(query.party_type)
    statement = select(model).where(
        model.company == query.company_id,
        _document_active_at_cutoff(model, query.as_of_date),
        model.posting_date <= query.as_of_date,
        or_(model.reversal_of.is_(None), model.reversal_of == ""),
    )
    if query.party_id:
        statement = statement.where(getattr(model, party_id_field) == query.party_id)
    return {str(document.id): document for document in database.session.execute(statement).scalars()}


def _paginated_result(
    report: Any,
    documents: dict[str, Any],
    query: AgingQuery,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Build the standard page while retaining the complete report summary."""
    start = (page - 1) * page_size
    report_rows = report.rows[start : start + page_size]
    items = [_aging_item(row.values, row.source_id, documents, query) for row in report_rows]
    return PaginatedResult(page=page, page_size=page_size, total_items=len(report.rows), items=items).to_dict()


def _document_model(party_type: str) -> tuple[Any, str, str]:
    """Select the invoice model and party fields used by one aging report."""
    if party_type == "customer":
        return SalesInvoice, "customer_id", "customer_name"
    return PurchaseInvoice, "supplier_id", "supplier_name"


def _aging_item(
    values: dict[str, Any],
    source_id: str | None,
    documents: dict[str, Any],
    query: AgingQuery,
) -> dict[str, Any]:
    """Combine the existing query-tool fields with canonical aging details."""
    if source_id is None:
        raise ValueError("Aging report row is missing its source document id.")
    _, party_id_field, party_name_field = _document_model(query.party_type)
    document = documents[source_id]
    due_date = values["due_date"]
    return {
        "document_no": values["document_no"],
        party_id_field: getattr(document, party_id_field),
        party_name_field: getattr(document, party_name_field),
        "posting_date": values["posting_date"].isoformat() if values["posting_date"] else None,
        "total": str(document.total),
        "outstanding": str(compute_outstanding_amount(document, query.as_of_date)),
        "transaction_currency": values["transaction_currency"],
        "base_currency": values["currency"],
        "exchange_rate": str(document.exchange_rate) if document.exchange_rate else None,
        "status": document.status,
        "due_date": due_date.isoformat() if due_date else None,
        "days": values["days"],
        "bucket": values["bucket"],
        "base_outstanding": str(values["outstanding_amount"]),
    }
