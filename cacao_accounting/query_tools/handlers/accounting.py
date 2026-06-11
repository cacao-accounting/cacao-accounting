from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, or_

from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Book,
    GLEntry,
    database,
)
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import (
    PaginatedResult,
    paginate,
)
from cacao_accounting.query_tools.permissions import (
    validate_company_access,
    validate_permission,
)


@query_tool(
    name="accounting_periods.list",
    description="Lista los períodos contables de una compañía.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["open", "closed"],
            },
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id"],
    },
)
def list_accounting_periods(
    *,
    context: QueryContext,
    company_id: str,
    status: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(
        context,
        required_permission="accounting.reports.read",
        required_module="accounting",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(AccountingPeriod)
        .where(AccountingPeriod.entity == company_id)
    )

    if status == "open":
        query = query.where(AccountingPeriod.is_closed == False)  # noqa: E712
    elif status == "closed":
        query = query.where(AccountingPeriod.is_closed == True)  # noqa: E712

    total = database.session.execute(
        database.select(func.count()).select_from(query.subquery())
    ).scalar() or 0

    rows = (
        database.session.execute(
            query.order_by(AccountingPeriod.start.desc())
            .offset((_page - 1) * _page_size)
            .limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = [
        {
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "is_closed": p.is_closed,
            "start": p.start.isoformat() if p.start else None,
            "end": p.end.isoformat() if p.end else None,
            "fiscal_year_id": p.fiscal_year_id,
        }
        for p in rows
    ]

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()


@query_tool(
    name="accounts.search",
    description="Busca cuentas contables por código o nombre.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "query": {"type": "string"},
            "classification": {
                "type": "string",
                "enum": ["Activo", "Pasivo", "Patrimonio", "Ingresos", "Gastos"],
            },
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id"],
    },
)
def search_accounts(
    *,
    context: QueryContext,
    company_id: str,
    query: str | None = None,
    classification: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(
        context,
        required_permission="accounting.reports.read",
        required_module="accounting",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    q = database.select(Accounts).where(Accounts.entity == company_id)

    if query:
        like = f"%{query}%"
        q = q.where(
            or_(Accounts.code.ilike(like), Accounts.name.ilike(like))
        )
    if classification:
        q = q.where(Accounts.classification == classification)

    total = database.session.execute(
        database.select(func.count()).select_from(q.subquery())
    ).scalar() or 0

    rows = (
        database.session.execute(
            q.order_by(Accounts.code)
            .offset((_page - 1) * _page_size)
            .limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "classification": a.classification,
            "type": a.type_,
            "account_type": a.account_type,
            "group": a.group,
            "parent": a.parent,
            "currency": a.currency,
            "active": a.active,
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
    name="accounting.get_trial_balance",
    description="Obtiene la balanza de comprobación para una compañía, libro y rango de fechas.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    max_date_range_months=12,
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "ledger_id": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id", "ledger_id", "date_from", "date_to"],
    },
)
def get_trial_balance(
    *,
    context: QueryContext,
    company_id: str,
    ledger_id: str,
    date_from: str,
    date_to: str,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(
        context,
        required_permission="accounting.reports.read",
        required_module="accounting",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(
            GLEntry.account_id,
            Accounts.code,
            Accounts.name,
            func.sum(GLEntry.debit).label("total_debit"),
            func.sum(GLEntry.credit).label("total_credit"),
        )
        .join(Accounts, GLEntry.account_id == Accounts.id)
        .where(GLEntry.company == company_id)
        .where(GLEntry.ledger_id == ledger_id)
        .where(GLEntry.posting_date >= date_from)
        .where(GLEntry.posting_date <= date_to)
        .group_by(GLEntry.account_id, Accounts.code, Accounts.name)
    )

    total = database.session.execute(
        database.select(func.count()).select_from(query.subquery())
    ).scalar() or 0

    rows = database.session.execute(
        query.order_by(Accounts.code)
        .offset((_page - 1) * _page_size)
        .limit(_page_size)
    ).all()

    items = [
        {
            "account_id": r.account_id,
            "account_code": r.code,
            "account_name": r.name,
            "total_debit": str(r.total_debit),
            "total_credit": str(r.total_credit),
            "balance": str(
                abs(float(r.total_debit) - float(r.total_credit))
            ),
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
    name="accounting.get_general_ledger",
    description="Consulta los movimientos del libro mayor por cuenta.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    max_date_range_months=12,
    parameters_schema={
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "ledger_id": {"type": "string"},
            "account_id": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
            "page": {"type": "integer", "default": 1},
            "page_size": {"type": "integer", "default": 100, "maximum": 500},
        },
        "required": ["company_id", "ledger_id", "date_from", "date_to"],
    },
)
def get_general_ledger(
    *,
    context: QueryContext,
    company_id: str,
    ledger_id: str,
    account_id: str | None = None,
    date_from: str,
    date_to: str,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(
        context,
        required_permission="accounting.reports.read",
        required_module="accounting",
        company_id=company_id,
    )

    _page, _page_size = paginate(page, page_size)

    query = (
        database.select(GLEntry)
        .where(GLEntry.company == company_id)
        .where(GLEntry.ledger_id == ledger_id)
        .where(GLEntry.posting_date >= date_from)
        .where(GLEntry.posting_date <= date_to)
    )

    if account_id:
        query = query.where(GLEntry.account_id == account_id)

    total = database.session.execute(
        database.select(func.count()).select_from(query.subquery())
    ).scalar() or 0

    rows = (
        database.session.execute(
            query.order_by(GLEntry.posting_date, GLEntry.created)
            .offset((_page - 1) * _page_size)
            .limit(_page_size)
        )
        .scalars()
        .all()
    )

    items = [
        {
            "id": e.id,
            "posting_date": e.posting_date.isoformat() if e.posting_date else None,
            "account_id": e.account_id,
            "debit": str(e.debit),
            "credit": str(e.credit),
            "debit_in_account_currency": str(e.debit_in_account_currency) if e.debit_in_account_currency else None,
            "credit_in_account_currency": str(e.credit_in_account_currency) if e.credit_in_account_currency else None,
            "exchange_rate": str(e.exchange_rate) if e.exchange_rate else None,
            "account_currency": e.account_currency,
            "company_currency": e.company_currency,
            "voucher_type": e.voucher_type,
            "voucher_id": e.voucher_id,
            "document_no": e.document_no,
            "remarks": e.remarks,
            "cost_center_code": e.cost_center_code,
            "unit_code": e.unit_code,
            "project_code": e.project_code,
            "party_type": e.party_type,
            "party_id": e.party_id,
        }
        for e in rows
    ]

    result = PaginatedResult(
        page=_page,
        page_size=_page_size,
        total_items=total,
        items=items,
    )
    return result.to_dict()
