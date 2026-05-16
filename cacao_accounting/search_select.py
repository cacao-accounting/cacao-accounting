# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio generico para campos de seleccion asistida."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Sequence

from sqlalchemy import Select, case, cast, func, or_, select, true
from sqlalchemy.orm.attributes import InstrumentedAttribute

from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Bank,
    BankAccount,
    Book,
    CompanyParty,
    CostCenter,
    Currency,
    Entity,
    ExternalCounter,
    Item,
    ItemUOMConversion,
    NamingSeries,
    Party,
    Project,
    TaxTemplate,
    Unit,
    UOM,
    Warehouse,
    GLEntry,
    database,
)

_DEDUP_QUERY_LIMIT_MULTIPLIER = 5
_DEDUP_QUERY_LIMIT_MIN = 25
_STATIC_SEARCH_SELECT_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "report_status": (("submitted", "Contabilizado"), ("cancelled", "Cancelado")),
    "party_type": (("customer", "Cliente"), ("supplier", "Proveedor")),
}


class SearchSelectError(ValueError):
    """Error validado para busquedas de campos seleccionables."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Initialize SearchSelectError with a message and HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class SearchSelectSpec:
    """Contrato de busqueda para un doctype permitido."""

    doctype: str
    model: type[Any]
    search_fields: tuple[str, ...]
    value_field: str
    label_builder: Callable[[Any], str]
    allowed_filters: dict[str, str]
    default_filters: dict[str, str | bool]
    limit: int = 20
    deduplicate_by_value: bool = False


def _account_label(account: Accounts) -> str:
    return f"{account.code} - {account.name}"


def _company_label(company: Entity) -> str:
    return f"{company.code} - {company.company_name}"


def _currency_label(currency: Currency) -> str:
    return f"{currency.code} - {currency.name}"


def _uom_label(uom: UOM) -> str:
    return f"{uom.code} - {uom.name}"


def _book_label(book: Book) -> str:
    return f"{book.code} - {book.name}"


def _accounting_period_label(period: AccountingPeriod) -> str:
    return period.name


def _cost_center_label(cost_center: CostCenter) -> str:
    return f"{cost_center.code} - {cost_center.name}"


def _unit_label(unit: Unit) -> str:
    return f"{unit.code} - {unit.name}"


def _project_label(project: Project) -> str:
    return f"{project.code} - {project.name}"


def _party_label(party: Party) -> str:
    tax_suffix = f" ({party.tax_id})" if party.tax_id else ""
    return f"{party.name}{tax_suffix}"


def _item_label(item: Item) -> str:
    return f"{item.code} - {item.name}"


def _warehouse_label(warehouse: Warehouse) -> str:
    return f"{warehouse.code} - {warehouse.name}"


def _bank_account_label(bank_account: BankAccount) -> str:
    account_no = f" {bank_account.account_no}" if bank_account.account_no else ""
    return f"{bank_account.account_name}{account_no}"


def _bank_label(bank: Bank) -> str:
    swift_suffix = f" ({bank.swift_code})" if bank.swift_code else ""
    return f"{bank.name}{swift_suffix}"


def _naming_series_label(naming_series: NamingSeries) -> str:
    return f"{naming_series.name} ({naming_series.entity_type})"


def _external_counter_label(counter: ExternalCounter) -> str:
    return f"{counter.name} (siguiente: {counter.next_suggested_formatted})"


def _string_label(value: Any) -> str:
    return str(value)


def _party_type_label(party: Party) -> str:
    labels = {"customer": "Cliente", "supplier": "Proveedor"}
    party_type = str(getattr(party, "party_type", "") or "")
    return labels.get(party_type, party_type)


def _voucher_type_label(entry: GLEntry) -> str:
    return str(getattr(entry, "voucher_type", "") or "")


def _document_no_label(entry: GLEntry) -> str:
    return str(getattr(entry, "document_no", "") or getattr(entry, "voucher_id", "") or "")


_SEARCH_SELECT_REGISTRY: dict[str, SearchSelectSpec] = {
    "company": SearchSelectSpec(
        doctype="company",
        model=Entity,
        search_fields=("code", "company_name", "name", "tax_id"),
        value_field="code",
        label_builder=_company_label,
        allowed_filters={"is_active": "enabled"},
        default_filters={"enabled": True},
    ),
    "currency": SearchSelectSpec(
        doctype="currency",
        model=Currency,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_currency_label,
        allowed_filters={"is_active": "active"},
        default_filters={},
    ),
    "uom": SearchSelectSpec(
        doctype="uom",
        model=UOM,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_uom_label,
        allowed_filters={"code": "code", "is_active": "is_active"},
        default_filters={"is_active": True},
    ),
    "account": SearchSelectSpec(
        doctype="account",
        model=Accounts,
        search_fields=("code", "name"),
        value_field="id",
        label_builder=_account_label,
        allowed_filters={"company": "entity", "account_type": "account_type", "is_active": "active"},
        default_filters={"group": False, "active": True, "enabled": True},
    ),
    "account_code": SearchSelectSpec(
        doctype="account_code",
        model=Accounts,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_account_label,
        allowed_filters={"company": "entity", "account_type": "account_type", "is_active": "active"},
        default_filters={"active": True, "enabled": True},
    ),
    "book": SearchSelectSpec(
        doctype="book",
        model=Book,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_book_label,
        allowed_filters={"company": "entity", "is_primary": "is_primary"},
        default_filters={},
    ),
    "accounting_period": SearchSelectSpec(
        doctype="accounting_period",
        model=AccountingPeriod,
        search_fields=("name",),
        value_field="name",
        label_builder=_accounting_period_label,
        allowed_filters={"company": "entity", "is_closed": "is_closed", "is_active": "enabled"},
        default_filters={"enabled": True},
    ),
    "accounting_period_id": SearchSelectSpec(
        doctype="accounting_period_id",
        model=AccountingPeriod,
        search_fields=("name",),
        value_field="id",
        label_builder=_accounting_period_label,
        allowed_filters={"company": "entity", "is_closed": "is_closed", "is_active": "enabled"},
        default_filters={"enabled": True},
    ),
    "cost_center": SearchSelectSpec(
        doctype="cost_center",
        model=CostCenter,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_cost_center_label,
        allowed_filters={"company": "entity", "is_active": "active"},
        default_filters={"group": False, "active": True, "enabled": True},
    ),
    "unit": SearchSelectSpec(
        doctype="unit",
        model=Unit,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_unit_label,
        allowed_filters={"company": "entity"},
        default_filters={},
    ),
    "project": SearchSelectSpec(
        doctype="project",
        model=Project,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_project_label,
        allowed_filters={"company": "entity", "is_active": "enabled", "status": "status"},
        default_filters={"enabled": True},
    ),
    "party": SearchSelectSpec(
        doctype="party",
        model=Party,
        search_fields=("name", "comercial_name", "tax_id"),
        value_field="id",
        label_builder=_party_label,
        allowed_filters={"company": "company", "party_type": "party_type", "is_active": "is_active"},
        default_filters={"is_active": True},
    ),
    "customer": SearchSelectSpec(
        doctype="customer",
        model=Party,
        search_fields=("name", "comercial_name", "tax_id"),
        value_field="id",
        label_builder=_party_label,
        allowed_filters={"company": "company", "party_type": "party_type", "is_active": "is_active"},
        default_filters={"party_type": "customer", "is_active": True},
    ),
    "supplier": SearchSelectSpec(
        doctype="supplier",
        model=Party,
        search_fields=("name", "comercial_name", "tax_id"),
        value_field="id",
        label_builder=_party_label,
        allowed_filters={"company": "company", "party_type": "party_type", "is_active": "is_active"},
        default_filters={"party_type": "supplier", "is_active": True},
    ),
    "item": SearchSelectSpec(
        doctype="item",
        model=Item,
        search_fields=("code", "name", "description"),
        value_field="code",
        label_builder=_item_label,
        allowed_filters={
            "company": "company",
            "is_active": "is_active",
            "item_type": "item_type",
            "is_stock_item": "is_stock_item",
        },
        default_filters={"is_active": True},
    ),
    "warehouse": SearchSelectSpec(
        doctype="warehouse",
        model=Warehouse,
        search_fields=("code", "name"),
        value_field="code",
        label_builder=_warehouse_label,
        allowed_filters={"company": "company", "is_active": "is_active"},
        default_filters={"is_group": False, "is_active": True},
    ),
    "bank_account": SearchSelectSpec(
        doctype="bank_account",
        model=BankAccount,
        search_fields=("account_name", "account_no", "iban"),
        value_field="id",
        label_builder=_bank_account_label,
        allowed_filters={"company": "company", "is_active": "is_active"},
        default_filters={"is_active": True},
    ),
    "bank": SearchSelectSpec(
        doctype="bank",
        model=Bank,
        search_fields=("name", "swift_code"),
        value_field="id",
        label_builder=_bank_label,
        allowed_filters={"is_active": "is_active"},
        default_filters={"is_active": True},
    ),
    "tax_template": SearchSelectSpec(
        doctype="tax_template",
        model=TaxTemplate,
        search_fields=("name",),
        value_field="id",
        label_builder=_string_label,
        allowed_filters={"company": "company", "template_type": "template_type", "is_active": "is_active"},
        default_filters={"is_active": True},
    ),
    "naming_series": SearchSelectSpec(
        doctype="naming_series",
        model=NamingSeries,
        search_fields=("name", "entity_type", "prefix_template"),
        value_field="id",
        label_builder=_naming_series_label,
        allowed_filters={"company": "company", "entity_type": "entity_type", "is_active": "is_active"},
        default_filters={"is_active": True},
    ),
    "external_counter": SearchSelectSpec(
        doctype="external_counter",
        model=ExternalCounter,
        search_fields=("name", "counter_type", "prefix", "description"),
        value_field="id",
        label_builder=_external_counter_label,
        allowed_filters={
            "company": "company",
            "counter_type": "counter_type",
            "is_active": "is_active",
            "naming_series_id": "naming_series_id",
        },
        default_filters={"is_active": True},
    ),
    "party_type": SearchSelectSpec(
        doctype="party_type",
        model=Party,
        search_fields=("party_type",),
        value_field="party_type",
        label_builder=_party_type_label,
        allowed_filters={"is_active": "is_active"},
        default_filters={"is_active": True},
        deduplicate_by_value=True,
    ),
    "voucher_type": SearchSelectSpec(
        doctype="voucher_type",
        model=GLEntry,
        search_fields=("voucher_type",),
        value_field="voucher_type",
        label_builder=_voucher_type_label,
        allowed_filters={"company": "company", "ledger": "ledger_id"},
        default_filters={},
        deduplicate_by_value=True,
    ),
    "document_no": SearchSelectSpec(
        doctype="document_no",
        model=GLEntry,
        search_fields=("document_no", "voucher_id"),
        value_field="document_no",
        label_builder=_document_no_label,
        allowed_filters={"company": "company", "ledger": "ledger_id"},
        default_filters={},
        deduplicate_by_value=True,
    ),
}
SEARCH_SELECT_REGISTRY = MappingProxyType(_SEARCH_SELECT_REGISTRY)


def search_select(doctype: str, query: str, filters: dict[str, list[str]], limit: int | None = None) -> dict[str, Any]:
    """Busca opciones para un doctype registrado y devuelve un payload uniforme."""
    if doctype in _STATIC_SEARCH_SELECT_OPTIONS:
        if filters:
            raise SearchSelectError("Filtros no permitidos para este tipo de seleccion.")
        return _search_static_options(doctype=doctype, query=query, limit=limit)

    spec = SEARCH_SELECT_REGISTRY.get(doctype)
    if spec is None:
        raise SearchSelectError("Tipo de seleccion no registrado.", 404)

    rejected_filters = sorted(set(filters) - set(spec.allowed_filters))
    if rejected_filters:
        raise SearchSelectError("Filtros no permitidos: " + ", ".join(rejected_filters))

    max_results = _normalize_limit(limit, spec.limit)
    normalized_query = query.strip()

    statement = select(spec.model)
    if spec.model is Party and filters.get("company"):
        statement = statement.join(CompanyParty, CompanyParty.party_id == Party.id)
        statement = statement.where(CompanyParty.is_active.is_(True))

    statement = _apply_default_filters(statement, spec)
    statement = _apply_request_filters(statement, spec, filters)
    statement = _apply_search(statement, spec, normalized_query)
    query_limit = max_results + 1
    if spec.deduplicate_by_value:
        query_limit = max(query_limit * _DEDUP_QUERY_LIMIT_MULTIPLIER, _DEDUP_QUERY_LIMIT_MIN)
    statement = statement.limit(query_limit)

    rows = database.session.execute(statement).scalars().all()
    serialized_results = _serialize_results(spec, rows)
    visible_rows = serialized_results[:max_results]
    return {
        "doctype": doctype,
        "query": normalized_query,
        "results": visible_rows,
        "has_more": len(serialized_results) > max_results,
    }


def _search_static_options(doctype: str, query: str, limit: int | None) -> dict[str, Any]:
    normalized_query = query.strip().lower()
    max_results = _normalize_limit(limit, default_limit=20)
    options = _STATIC_SEARCH_SELECT_OPTIONS.get(doctype, ())
    filtered = [
        {
            "id": value,
            "value": value,
            "label": label,
            "display_name": label,
        }
        for value, label in options
        if not normalized_query or normalized_query in value.lower() or normalized_query in label.lower()
    ]
    visible_rows = filtered[:max_results]
    return {
        "doctype": doctype,
        "query": query.strip(),
        "results": visible_rows,
        "has_more": len(filtered) > max_results,
    }


def _serialize_results(spec: SearchSelectSpec, rows: Sequence[Any]) -> list[dict[str, Any]]:
    if not spec.deduplicate_by_value:
        return [_serialize_result(spec, row) for row in rows]

    values: list[dict[str, Any]] = []
    seen_values: set[str] = set()
    for row in rows:
        payload = _serialize_result(spec, row)
        value = str(payload.get("value", ""))
        if not value or value in seen_values:
            continue
        seen_values.add(value)
        values.append(payload)
    return values


def _normalize_limit(limit: int | None, default_limit: int) -> int:
    if limit is None:
        return default_limit
    if limit < 1:
        raise SearchSelectError("El limite debe ser mayor que cero.")
    return min(limit, 50)


def _apply_default_filters(statement: Select[tuple[Any]], spec: SearchSelectSpec) -> Select[tuple[Any]]:
    for field, value in spec.default_filters.items():
        column = _column_for(spec.model, field)
        statement = statement.where(_condition_for(column, [str(value)] if isinstance(value, str) else [value]))
    return statement


def _apply_request_filters(
    statement: Select[tuple[Any]], spec: SearchSelectSpec, filters: dict[str, list[str]]
) -> Select[tuple[Any]]:
    for filter_name, values in filters.items():
        clean_values = [value for value in values if value != ""]
        if not clean_values:
            continue
        if spec.model is Item and filter_name == "company":
            # Item is global master data today; keep the company filter mandatory at the API boundary
            # so callers cannot accidentally query the global catalog without company context.
            continue
        if spec.model is Party and filter_name == "company":
            statement = statement.where(CompanyParty.company.in_(clean_values))
            continue
        column = _column_for(spec.model, spec.allowed_filters[filter_name])
        statement = statement.where(_condition_for(column, clean_values))
    return statement


def _apply_search(statement: Select[tuple[Any]], spec: SearchSelectSpec, query: str) -> Select[tuple[Any]]:
    if not query:
        searchable_columns = [_column_for(spec.model, field) for field in spec.search_fields]
        first_sort = searchable_columns[0]
        return statement.order_by(first_sort)
    like_query = f"%{query.lower()}%"
    prefix_query = f"{query.lower()}%"
    searchable_columns = [_column_for(spec.model, field) for field in spec.search_fields]
    search_conditions = [func.lower(cast(column, database.String)).like(like_query) for column in searchable_columns]
    prefix_conditions = [func.lower(cast(column, database.String)).like(prefix_query) for column in searchable_columns]
    priority = case((or_(*prefix_conditions), 0), else_=1)
    first_sort = searchable_columns[0]
    return statement.where(or_(*search_conditions)).order_by(priority, first_sort)


def _condition_for(column: InstrumentedAttribute[Any], values: Sequence[str | bool]) -> Any:
    if not values:
        return true()
    if all(isinstance(value, bool) for value in values):
        return column.is_(values[0])
    normalized_values = [_normalize_filter_value(value) for value in values]
    if len(normalized_values) == 1:
        value = normalized_values[0]
        if isinstance(value, bool):
            return column.is_(value)
        return column == value
    return column.in_(normalized_values)


def _normalize_filter_value(value: str | bool) -> str | bool:
    if isinstance(value, bool):
        return value
    match value.strip().lower():
        case "true" | "1" | "yes" | "si" | "sí":
            return True
        case "false" | "0" | "no":
            return False
        case "__empty__":
            return ""
        case other:
            return other if other == value else value


def _column_for(model: type[Any], field: str) -> InstrumentedAttribute[Any]:
    column = getattr(model, field, None)
    if column is None:
        raise SearchSelectError("Filtro no disponible para este tipo de seleccion.")
    return column


def _serialize_result(spec: SearchSelectSpec, row: Any) -> dict[str, Any]:
    value = str(getattr(row, spec.value_field))
    label = spec.label_builder(row)
    payload: dict[str, Any] = {"id": value, "value": value, "label": label, "display_name": label}
    for field in (
        "code",
        "name",
        "company_name",
        "account_type",
        "party_type",
        "item_type",
        "account_name",
        "account_no",
        "entity_type",
        "is_default",
        "default_uom",
    ):
        if hasattr(row, field):
            payload[field] = getattr(row, field)
    if isinstance(row, Item):
        payload["allowed_uoms"] = _allowed_uoms_for_item(row)
    return payload


def _allowed_uoms_for_item(item: Item) -> list[str]:
    values = [item.default_uom] if item.default_uom else []
    conversions = database.session.execute(
        select(ItemUOMConversion.from_uom, ItemUOMConversion.to_uom).filter_by(item_code=item.code)
    ).all()
    for from_uom, to_uom in conversions:
        values.extend([from_uom, to_uom])
    seen: set[str] = set()
    allowed_uoms: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        allowed_uoms.append(value)
    return allowed_uoms
