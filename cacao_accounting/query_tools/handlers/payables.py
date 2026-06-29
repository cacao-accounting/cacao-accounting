"""Handlers de consultas de cuentas por pagar."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func

from cacao_accounting.database import (
    PurchaseInvoice,
    database,
)
from cacao_accounting.document_flow.service import compute_outstanding_amount
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import (
    PaginatedResult,
    paginate,
)
from cacao_accounting.query_tools.permissions import validate_permission


@query_tool(
    name="payables.get_aging",
    description="Obtiene la antigüedad de saldos de cuentas por pagar.",
    required_module="purchases",
    required_permission="payables.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "as_of_date": {"type": "string", "format": "date"},
            "party_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id", "as_of_date"],
    },
)
def get_payables_aging(
    *,
    context: QueryContext,
    company_id: str,
    as_of_date: str,
    party_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Obtiene la antigüedad de saldos de cuentas por pagar."""
    validate_permission(
        context,
        required_permission="payables.reports.read",
        required_module="purchases",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(PurchaseInvoice)
        .where(PurchaseInvoice.company == company_id)
        .where(PurchaseInvoice.docstatus == 1)
        .where(PurchaseInvoice.posting_date <= as_of_date)
    )

    if party_id:
        query = query.where(PurchaseInvoice.supplier_id == party_id)

    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0

    rows = (
        database.session.execute(
            query.order_by(PurchaseInvoice.supplier_id, PurchaseInvoice.posting_date)
            .offset((_page - 1) * _page_size)
            .limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = []
    for inv in rows:
        outstanding = compute_outstanding_amount(inv)
        items.append(
            {
                "document_no": inv.document_no,
                "supplier_id": inv.supplier_id,
                "supplier_name": inv.supplier_name,
                "posting_date": inv.posting_date.isoformat() if inv.posting_date else None,
                "total": str(inv.total),
                "outstanding": str(outstanding),
                "transaction_currency": inv.transaction_currency,
                "base_currency": inv.base_currency,
                "exchange_rate": str(inv.exchange_rate) if inv.exchange_rate else None,
                "status": inv.status,
            }
        )

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()


@query_tool(
    name="payables.get_open_documents",
    description="Consulta documentos de compra abiertos (pendientes de pago).",
    required_module="purchases",
    required_permission="payables.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "party_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id"],
    },
)
def get_payables_open_documents(
    *,
    context: QueryContext,
    company_id: str,
    party_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Consulta documentos de compra abiertos pendientes de pago."""
    validate_permission(
        context,
        required_permission="payables.reports.read",
        required_module="purchases",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(PurchaseInvoice)
        .where(PurchaseInvoice.company == company_id)
        .where(PurchaseInvoice.docstatus == 1)
        .where(PurchaseInvoice.status.in_(["open", "overdue"]))
    )

    if party_id:
        query = query.where(PurchaseInvoice.supplier_id == party_id)

    total = database.session.execute(database.select(func.count()).select_from(query.subquery())).scalar() or 0

    rows = (
        database.session.execute(
            query.order_by(PurchaseInvoice.posting_date.desc()).offset((_page - 1) * _page_size).limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = []
    for inv in rows:
        outstanding = compute_outstanding_amount(inv)
        items.append(
            {
                "id": inv.id,
                "document_no": inv.document_no,
                "supplier_id": inv.supplier_id,
                "supplier_name": inv.supplier_name,
                "posting_date": inv.posting_date.isoformat() if inv.posting_date else None,
                "total": str(inv.total),
                "outstanding": str(outstanding),
                "transaction_currency": inv.transaction_currency,
                "status": inv.status,
            }
        )

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()
