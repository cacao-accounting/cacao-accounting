"""Handlers de consultas bancarias: cuentas y transacciones."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func

from cacao_accounting.database import BankAccount, BankTransaction, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import (
    PaginatedResult,
    paginate,
)
from cacao_accounting.query_tools.permissions import validate_permission


@query_tool(
    name="banking.get_accounts",
    description="Lista las cuentas bancarias de una compañía.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id"],
    },
)
def get_banking_accounts(
    *,
    context: QueryContext,
    company_id: str,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Lista las cuentas bancarias de una compañía."""
    validate_permission(
        context,
        required_permission="banking.reports.read",
        required_module="cash",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(BankAccount)
        .where(BankAccount.entity == company_id)
    )

    total = database.session.execute(
        database.select(func.count()).select_from(query.subquery())
    ).scalar() or 0

    rows = (
        database.session.execute(
            query.order_by(BankAccount.bank_name, BankAccount.account_number)
            .offset((_page - 1) * _page_size)
            .limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = [
        {
            "id": a.id,
            "bank_name": a.bank_name,
            "account_number": a.account_number,
            "account_type": a.account_type,
            "currency": a.currency,
            "balance": str(a.balance) if hasattr(a, "balance") and a.balance else "0",
            "status": a.status,
        }
        for a in rows
    ]

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()


@query_tool(
    name="banking.get_transactions",
    description="Consulta movimientos bancarios.",
    required_module="cash",
    required_permission="banking.reports.read",
    max_date_range_months=12,
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "bank_account_id": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id"],
    },
)
def get_banking_transactions(
    *,
    context: QueryContext,
    company_id: str,
    bank_account_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Consulta movimientos bancarios con filtros opcionales por cuenta y fechas."""
    validate_permission(
        context,
        required_permission="banking.reports.read",
        required_module="cash",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(BankTransaction)
        .where(BankTransaction.entity == company_id)
    )

    if bank_account_id:
        query = query.where(BankTransaction.bank_account == bank_account_id)
    if date_from:
        query = query.where(BankTransaction.posting_date >= date_from)
    if date_to:
        query = query.where(BankTransaction.posting_date <= date_to)

    total = database.session.execute(
        database.select(func.count()).select_from(query.subquery())
    ).scalar() or 0

    rows = (
        database.session.execute(
            query.order_by(BankTransaction.posting_date.desc())
            .offset((_page - 1) * _page_size)
            .limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = [
        {
            "id": t.id,
            "posting_date": t.posting_date.isoformat() if t.posting_date else None,
            "description": t.description,
            "debit": str(t.debit) if t.debit else None,
            "credit": str(t.credit) if t.credit else None,
            "currency": t.currency,
            "exchange_rate": str(t.exchange_rate) if t.exchange_rate else None,
            "reference": t.reference,
            "reconciled": t.reconciled,
        }
        for t in rows
    ]

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()
