"""Paginated identifier discovery for conversational clients."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from cacao_accounting.database import (
    BankAccount,
    Book,
    CompanyParty,
    CostCenter,
    Currency,
    DimensionType,
    DimensionValue,
    Item,
    Party,
    UOM,
    Warehouse,
    database,
)
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.decorators import query_tool
from cacao_accounting.query_tools.pagination import PaginatedResult, paginate
from cacao_accounting.query_tools.permissions import validate_permission


def _page(page: int, page_size: int) -> tuple[int, int]:
    return paginate(page, page_size)


def _result(page: int, size: int, items: list[dict[str, Any]], total: int, company_id: str) -> dict[str, Any]:
    result = PaginatedResult(page=page, page_size=size, total_items=total, items=items).to_dict()
    result["provenance"] = {"company_id": company_id, "completeness": {"truncated": result["page"]["has_more"]}}
    return result


_SCHEMA = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "query": {"type": "string", "maxLength": 100},
        "page": {"type": "integer", "minimum": 1, "default": 1},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
    },
    "required": ["company_id"],
}


@query_tool(
    "ledgers.list",
    "Lista libros contables autorizados de una compañía.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_SCHEMA,
)
def list_ledgers(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    current, size = _page(page, page_size)
    statement = database.select(Book).where(Book.entity == company_id)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(Book.code.ilike(pattern), Book.name.ilike(pattern)))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(Book.code).offset((current - 1) * size).limit(size)).scalars()
    return _result(
        current,
        size,
        [{"id": row.id, "code": row.code, "name": row.name, "currency": row.currency} for row in rows],
        total,
        company_id,
    )


@query_tool(
    "parties.search",
    "Busca clientes y proveedores activos de una compañía.",
    required_module="accounting",
    required_permission="documents.reports.read",
    parameters_schema={
        **_SCHEMA,
        "properties": {**_SCHEMA["properties"], "party_type": {"type": "string", "enum": ["customer", "supplier", "all"]}},
    },
)
def search_parties(
    *,
    context: QueryContext,
    company_id: str,
    query: str | None = None,
    party_type: str = "all",
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "documents.reports.read", "accounting", company_id)
    current, size = _page(page, page_size)
    statement = (
        database.select(Party)
        .join(CompanyParty, CompanyParty.party_id == Party.id)
        .where(CompanyParty.company == company_id, CompanyParty.is_active.is_(True), Party.is_active.is_(True))
    )
    if party_type == "customer":
        statement = statement.where(Party.is_customer.is_(True))
    elif party_type == "supplier":
        statement = statement.where(Party.is_supplier.is_(True))
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(Party.code.ilike(pattern), Party.name.ilike(pattern), Party.tax_id.ilike(pattern)))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(Party.code).offset((current - 1) * size).limit(size)).scalars()
    items = [
        {"id": row.id, "code": row.code, "name": row.name, "is_customer": row.is_customer, "is_supplier": row.is_supplier}
        for row in rows
    ]
    return _result(current, size, items, total, company_id)


@query_tool(
    "items.search",
    "Busca artículos activos por código o nombre.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_SCHEMA,
)
def search_items(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "inventory.reports.read", "inventory", company_id)
    current, size = _page(page, page_size)
    statement = database.select(Item).where(Item.is_active.is_(True))
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(Item.code.ilike(pattern), Item.name.ilike(pattern)))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(Item.code).offset((current - 1) * size).limit(size)).scalars()
    return _result(
        current,
        size,
        [
            {"id": row.id, "code": row.code, "name": row.name, "item_type": row.item_type, "is_stock_item": row.is_stock_item}
            for row in rows
        ],
        total,
        company_id,
    )


@query_tool(
    "warehouses.list",
    "Lista almacenes activos de una compañía.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_SCHEMA,
)
def list_warehouses(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "inventory.reports.read", "inventory", company_id)
    current, size = _page(page, page_size)
    statement = database.select(Warehouse).where(Warehouse.company == company_id, Warehouse.is_active.is_(True))
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(Warehouse.code.ilike(pattern), Warehouse.name.ilike(pattern)))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(Warehouse.code).offset((current - 1) * size).limit(size)).scalars()
    return _result(
        current,
        size,
        [{"id": row.id, "code": row.code, "name": row.name, "company_id": row.company} for row in rows],
        total,
        company_id,
    )


@query_tool(
    "bank_accounts.search",
    "Busca cuentas bancarias activas de una compañía.",
    required_module="cash",
    required_permission="banking.reports.read",
    parameters_schema=_SCHEMA,
)
def search_bank_accounts(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "banking.reports.read", "cash", company_id)
    current, size = _page(page, page_size)
    statement = database.select(BankAccount).where(BankAccount.company == company_id, BankAccount.is_active.is_(True))
    if query:
        pattern = f"%{query}%"
        statement = statement.where(or_(BankAccount.account_name.ilike(pattern), BankAccount.account_no.ilike(pattern)))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(
        statement.order_by(BankAccount.account_name).offset((current - 1) * size).limit(size)
    ).scalars()
    return _result(
        current,
        size,
        [
            {"id": row.id, "account_name": row.account_name, "account_no": row.account_no, "currency": row.currency}
            for row in rows
        ],
        total,
        company_id,
    )


@query_tool(
    "currencies.list",
    "Lista monedas configuradas.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        "type": "object",
        "properties": {"company_id": {"type": "string"}, **{k: v for k, v in _SCHEMA["properties"].items() if k != "query"}},
        "required": ["company_id"],
    },
)
def list_currencies(*, context: QueryContext, company_id: str, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    current, size = _page(page, page_size)
    statement = database.select(Currency).where(Currency.active.is_(True))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(Currency.code).offset((current - 1) * size).limit(size)).scalars()
    return _result(
        current,
        size,
        [{"code": row.code, "name": row.name, "decimals": row.decimals, "default": row.default} for row in rows],
        total,
        company_id,
    )


@query_tool(
    "dimensions.list",
    "Lista tipos de dimensión analítica activos.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_SCHEMA,
)
def list_dimensions(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    current, size = _page(page, page_size)
    statement = database.select(DimensionType).where(DimensionType.is_active.is_(True))
    if query:
        statement = statement.where(DimensionType.name.ilike(f"%{query}%"))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(DimensionType.name).offset((current - 1) * size).limit(size)).scalars()
    return _result(current, size, [{"id": row.id, "name": row.name} for row in rows], total, company_id)


@query_tool(
    "dimension_values.search",
    "Busca valores de una dimensión por compañía.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema={
        **_SCHEMA,
        "properties": {**_SCHEMA["properties"], "dimension_type_id": {"type": "string"}},
        "required": ["company_id", "dimension_type_id"],
    },
)
def search_dimension_values(
    *,
    context: QueryContext,
    company_id: str,
    dimension_type_id: str,
    query: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    current, size = _page(page, page_size)
    statement = database.select(DimensionValue).where(
        DimensionValue.dimension_type_id == dimension_type_id,
        DimensionValue.is_active.is_(True),
        or_(DimensionValue.company.is_(None), DimensionValue.company == company_id),
    )
    if query:
        statement = statement.where(DimensionValue.value.ilike(f"%{query}%"))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(
        statement.order_by(DimensionValue.value).offset((current - 1) * size).limit(size)
    ).scalars()
    return _result(
        current,
        size,
        [{"id": row.id, "dimension_type_id": row.dimension_type_id, "value": row.value} for row in rows],
        total,
        company_id,
    )


@query_tool(
    "cost_centers.list",
    "Lista centros de costo activos de una compañía.",
    required_module="accounting",
    required_permission="accounting.reports.read",
    parameters_schema=_SCHEMA,
)
def list_cost_centers(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "accounting.reports.read", "accounting", company_id)
    current, size = _page(page, page_size)
    statement = database.select(CostCenter).where(CostCenter.entity == company_id, CostCenter.enabled.is_(True))
    if query:
        statement = statement.where(or_(CostCenter.code.ilike(f"%{query}%"), CostCenter.name.ilike(f"%{query}%")))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(CostCenter.code).offset((current - 1) * size).limit(size)).scalars()
    return _result(current, size, [{"id": row.id, "code": row.code, "name": row.name} for row in rows], total, company_id)


@query_tool(
    "uoms.list",
    "Lista unidades de medida activas.",
    required_module="inventory",
    required_permission="inventory.reports.read",
    parameters_schema=_SCHEMA,
)
def list_uoms(
    *, context: QueryContext, company_id: str, query: str | None = None, page: int = 1, page_size: int = 100
) -> dict[str, Any]:
    validate_permission(context, "inventory.reports.read", "inventory", company_id)
    current, size = _page(page, page_size)
    statement = database.select(UOM).where(UOM.is_active.is_(True))
    if query:
        statement = statement.where(or_(UOM.code.ilike(f"%{query}%"), UOM.name.ilike(f"%{query}%")))
    total = database.session.execute(database.select(database.func.count()).select_from(statement.subquery())).scalar() or 0
    rows = database.session.execute(statement.order_by(UOM.code).offset((current - 1) * size).limit(size)).scalars()
    return _result(current, size, [{"id": row.id, "code": row.code, "name": row.name} for row in rows], total, company_id)
