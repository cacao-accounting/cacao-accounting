# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Handlers de consultas de cuentas por cobrar."""

from __future__ import annotations

from typing import Any


from cacao_accounting.database import (
    SalesInvoice,
    database,
)
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.handlers.dates import parse_iso_date
from cacao_accounting.query_tools.handlers.aging import AgingQuery, get_aging_result
from cacao_accounting.query_tools.handlers.open_documents import paginate_positive_outstanding
from cacao_accounting.query_tools.pagination import (
    PaginatedResult,
    paginate,
)
from cacao_accounting.query_tools.permissions import validate_permission
from cacao_accounting.i18n import _l

_PERM_RECEIVABLES_REPORTS_READ = "receivables.reports.read"


@query_tool(
    name="receivables.get_aging",
    description=_l("Obtiene la antigüedad de saldos de cuentas por cobrar."),
    required_module="sales",
    required_permission=_PERM_RECEIVABLES_REPORTS_READ,
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
def get_receivables_aging(
    *,
    context: QueryContext,
    company_id: str,
    as_of_date: str,
    party_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Obtiene la antigüedad de saldos de cuentas por cobrar."""
    validate_permission(
        context,
        required_permission=_PERM_RECEIVABLES_REPORTS_READ,
        required_module="sales",
        company_id=company_id,
    )
    cutoff_date = parse_iso_date(as_of_date, required=True)
    assert cutoff_date is not None
    return get_aging_result(
        AgingQuery(
            company_id=company_id,
            party_type="customer",
            party_id=party_id,
            as_of_date=cutoff_date,
            page=page,
            page_size=page_size,
        )
    )


@query_tool(
    name="receivables.get_open_documents",
    description=_l("Consulta documentos de venta abiertos (pendientes de pago)."),
    required_module="sales",
    required_permission=_PERM_RECEIVABLES_REPORTS_READ,
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
def get_receivables_open_documents(
    *,
    context: QueryContext,
    company_id: str,
    party_id: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Consulta documentos de venta abiertos pendientes de pago."""
    validate_permission(
        context,
        required_permission=_PERM_RECEIVABLES_REPORTS_READ,
        required_module="sales",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(SalesInvoice)
        .where(SalesInvoice.company == company_id)
        .where(SalesInvoice.docstatus == 1)
        .where(SalesInvoice.status.in_(["open", "overdue"]))
    )

    if party_id:
        query = query.where(SalesInvoice.customer_id == party_id)

    total, page_rows = paginate_positive_outstanding(
        model=SalesInvoice,
        query=query,
        page=_page,
        page_size=_page_size,
    )

    items = []
    for inv, outstanding in page_rows:
        items.append(
            {
                "id": inv.id,
                "document_no": inv.document_no,
                "customer_id": inv.customer_id,
                "customer_name": inv.customer_name,
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
