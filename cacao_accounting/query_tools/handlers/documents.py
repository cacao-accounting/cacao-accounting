"""Handlers de consultas de relaciones documentales."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func

from cacao_accounting.database import DocumentRelation, database
from cacao_accounting.reportes.documentos import get_document_details, get_document_lines, get_document_status
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import (
    PaginatedResult,
    paginate,
)
from cacao_accounting.query_tools.permissions import validate_permission


@query_tool(
    name="documents.get_flow",
    description="Obtiene las relaciones documentales de un documento.",
    required_permission="documents.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "document_type": {"type": "string"},
            "document_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id", "document_type", "document_id"],
    },
)
def get_document_flow(
    *,
    context: QueryContext,
    company_id: str,
    document_type: str,
    document_id: str,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Obtiene las relaciones documentales de un documento."""
    validate_permission(
        context,
        required_permission="documents.reports.read",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = database.select(DocumentRelation).where(
        DocumentRelation.company == company_id,
        (DocumentRelation.source_id == document_id) | (DocumentRelation.target_id == document_id),
    )

    if document_type:
        query = query.where((DocumentRelation.source_type == document_type) | (DocumentRelation.target_type == document_type))

    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0

    rows = (
        database.session.execute(
            query.order_by(DocumentRelation.created.desc()).offset((_page - 1) * _page_size).limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = [
        {
            "id": r.id,
            "source_type": r.source_type,
            "source_id": r.source_id,
            "source_item_id": r.source_item_id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_item_id": r.target_item_id,
            "relation_type": r.relation_type,
            "status": r.status,
            "qty": str(r.qty),
            "amount": str(r.amount) if r.amount else None,
            "company": r.company,
            "created": r.created.isoformat() if r.created else None,
        }
        for r in rows
    ]

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()


@query_tool(
    name="documents.get_related_documents",
    description="Obtiene documentos relacionados y sus líneas de flujo.",
    required_permission="documents.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "document_type": {"type": "string"},
            "document_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id", "document_type", "document_id"],
    },
)
def get_related_documents(**kwargs: Any) -> dict[str, Any]:
    """Alias semántico estable para clientes que preguntan por relacionados."""
    handler = get_document_flow.handler
    if handler is None:
        raise RuntimeError("documents.get_flow handler is not configured")
    return handler(**kwargs)


_DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "document_type": {"type": "string", "enum": ["sales_invoice", "purchase_invoice", "payment_entry"]},
        "document_id": {"type": "string"},
    },
    "required": ["company_id", "document_type", "document_id"],
}


def _document_context(context: QueryContext, company_id: str) -> None:
    validate_permission(context, "documents.reports.read", "documents", company_id)


@query_tool(
    "documents.get_details",
    "Obtiene un DTO controlado de una factura o pago.",
    required_permission="documents.reports.read",
    parameters_schema=_DOCUMENT_SCHEMA,
)
def get_document_details_handler(
    *, context: QueryContext, company_id: str, document_type: str, document_id: str
) -> dict[str, Any]:
    _document_context(context, company_id)
    item = get_document_details(company_id, document_type, document_id)
    return {"item": item, "found": item is not None, "provenance": {"company_id": company_id}}


@query_tool(
    "documents.get_lines",
    "Obtiene líneas controladas de una factura; los pagos no tienen líneas.",
    required_permission="documents.reports.read",
    parameters_schema=_DOCUMENT_SCHEMA,
)
def get_document_lines_handler(
    *, context: QueryContext, company_id: str, document_type: str, document_id: str
) -> dict[str, Any]:
    _document_context(context, company_id)
    items = get_document_lines(company_id, document_type, document_id)
    return {
        "items": items or [],
        "found": items is not None,
        "page": {"number": 1, "size": len(items or []), "total_items": len(items or []), "has_more": False},
        "provenance": {"company_id": company_id},
    }


@query_tool(
    "documents.get_status",
    "Obtiene el estado contable controlado de una factura o pago.",
    required_permission="documents.reports.read",
    parameters_schema=_DOCUMENT_SCHEMA,
)
def get_document_status_handler(
    *, context: QueryContext, company_id: str, document_type: str, document_id: str
) -> dict[str, Any]:
    _document_context(context, company_id)
    item = get_document_status(company_id, document_type, document_id)
    return {"item": item, "found": item is not None, "provenance": {"company_id": company_id}}
