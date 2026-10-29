# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de contrato para los esquemas públicos de query tools."""

from __future__ import annotations

from inspect import Parameter, signature
from typing import Any
import pytest

from cacao_accounting.query_tools.schemas.accounting import (
    ACCOUNTING_PERIODS_PARAMS,
    ACCOUNTS_SEARCH_PARAMS,
    GENERAL_LEDGER_PARAMS,
    TRIAL_BALANCE_PARAMS,
)
from cacao_accounting.query_tools.schemas.audit_trail import DOCUMENT_TIMELINE_PARAMS
from cacao_accounting.query_tools.schemas.banking import (
    BANKING_ACCOUNTS_PARAMS,
    BANKING_TRANSACTIONS_PARAMS,
)
from cacao_accounting.query_tools.schemas.common import (
    COMPANY_PARAM,
    DATE_FILTERS,
    ERROR_RESPONSE,
    PAGINATED_RESPONSE,
    PAGINATION_PARAMS,
)
from cacao_accounting.query_tools.schemas.companies import (
    COMPANIES_LIST_PARAMS,
    COMPANIES_LIST_RESPONSE,
)
from cacao_accounting.query_tools.schemas.documents import DOCUMENTS_FLOW_PARAMS
from cacao_accounting.query_tools.schemas.payables import (
    PAYABLES_AGING_PARAMS,
    PAYABLES_OPEN_DOCUMENTS_PARAMS,
)
from cacao_accounting.query_tools.schemas.receivables import (
    RECEIVABLES_AGING_PARAMS,
    RECEIVABLES_OPEN_DOCUMENTS_PARAMS,
)


def _assert_object_schema(schema: dict[str, Any], required: set[str], properties: set[str]) -> None:
    """Comprueba el contrato común de un esquema de parámetros JSON."""
    assert schema["type"] == "object"
    assert set(schema.get("required", [])) == required
    assert set(schema["properties"]) == properties


def _assert_pagination_properties(schema: dict[str, Any]) -> None:
    """Comprueba los límites públicos de paginación."""
    assert schema["properties"]["page"] == {"type": "integer", "default": 1}
    assert schema["properties"]["page_size"] == {"type": "integer", "default": 100, "maximum": 500}


@pytest.mark.parametrize(
    ("schema", "required", "properties"),
    [
        (
            RECEIVABLES_AGING_PARAMS,
            {"company_id", "as_of_date"},
            {"company_id", "as_of_date", "party_id", "page", "page_size"},
        ),
        (
            RECEIVABLES_OPEN_DOCUMENTS_PARAMS,
            {"company_id"},
            {"company_id", "party_id", "page", "page_size"},
        ),
        (
            PAYABLES_AGING_PARAMS,
            {"company_id", "as_of_date"},
            {"company_id", "as_of_date", "party_id", "page", "page_size"},
        ),
        (
            PAYABLES_OPEN_DOCUMENTS_PARAMS,
            {"company_id"},
            {"company_id", "party_id", "page", "page_size"},
        ),
    ],
)
def test_receivables_and_payables_schemas_have_expected_contract(
    schema: dict[str, Any], required: set[str], properties: set[str]
) -> None:
    """Verifica filtros, requisitos y paginación de AR y AP."""
    _assert_object_schema(schema, required, properties)
    _assert_pagination_properties(schema)
    assert schema["properties"]["company_id"]["type"] == "string"
    if "as_of_date" in schema["properties"]:
        assert schema["properties"]["as_of_date"] == {"type": "string", "format": "date"}


def test_documents_and_audit_trail_require_document_identity() -> None:
    """Verifica que los endpoints documentales no acepten una identidad parcial."""
    expected = {"company_id", "document_type", "document_id"}
    properties = expected | {"page", "page_size"}
    for schema in (DOCUMENTS_FLOW_PARAMS, DOCUMENT_TIMELINE_PARAMS):
        _assert_object_schema(schema, expected, properties)
        _assert_pagination_properties(schema)


def test_banking_schemas_support_account_and_date_filters() -> None:
    """Verifica los filtros de cuentas y movimientos bancarios."""
    _assert_object_schema(
        BANKING_ACCOUNTS_PARAMS,
        {"company_id"},
        {"company_id", "page", "page_size"},
    )
    _assert_object_schema(
        BANKING_TRANSACTIONS_PARAMS,
        {"company_id"},
        {"company_id", "bank_account_id", "date_from", "date_to", "page", "page_size"},
    )
    _assert_pagination_properties(BANKING_ACCOUNTS_PARAMS)
    _assert_pagination_properties(BANKING_TRANSACTIONS_PARAMS)
    assert BANKING_TRANSACTIONS_PARAMS["properties"]["date_from"]["format"] == "date"
    assert BANKING_TRANSACTIONS_PARAMS["properties"]["date_to"]["format"] == "date"


def test_accounting_schemas_expose_required_filters_and_enums() -> None:
    """Verifica períodos, cuentas, balance de comprobación y mayor general."""
    schemas = (
        (ACCOUNTING_PERIODS_PARAMS, {"company_id"}),
        (ACCOUNTS_SEARCH_PARAMS, {"company_id"}),
        (TRIAL_BALANCE_PARAMS, {"company_id", "ledger_id", "date_from", "date_to"}),
        (GENERAL_LEDGER_PARAMS, {"company_id", "ledger_id", "date_from", "date_to"}),
    )
    for schema, required in schemas:
        _assert_object_schema(schema, required, set(schema["properties"]))
        _assert_pagination_properties(schema)
    assert ACCOUNTING_PERIODS_PARAMS["properties"]["status"]["enum"] == ["open", "closed"]
    assert ACCOUNTS_SEARCH_PARAMS["properties"]["classification"]["enum"] == [
        "Activo",
        "Pasivo",
        "Patrimonio",
        "Ingresos",
        "Gastos",
    ]
    for schema in (TRIAL_BALANCE_PARAMS, GENERAL_LEDGER_PARAMS):
        assert schema["properties"]["date_from"]["format"] == "date"
        assert schema["properties"]["date_to"]["format"] == "date"


def test_companies_schemas_describe_paginated_list_and_response_items() -> None:
    """Verifica el contrato de consulta y respuesta de compañías."""
    _assert_object_schema(COMPANIES_LIST_PARAMS, set(), {"page", "page_size"})
    _assert_pagination_properties(COMPANIES_LIST_PARAMS)
    assert COMPANIES_LIST_RESPONSE["type"] == "object"
    assert set(COMPANIES_LIST_RESPONSE["properties"]) == {
        "page",
        "page_size",
        "total_items",
        "items",
    }
    item_properties = COMPANIES_LIST_RESPONSE["properties"]["items"]["items"]["properties"]
    assert set(item_properties) == {"code", "company_name", "tax_id", "currency", "country", "enabled"}
    assert item_properties["enabled"] == {"type": "boolean"}


def test_common_schemas_define_shared_filters_responses_and_company_parameter() -> None:
    """Verifica contratos compartidos por todos los handlers de consulta."""
    assert PAGINATION_PARAMS["page"]["minimum"] == 1
    assert PAGINATION_PARAMS["page_size"]["maximum"] == 500
    assert DATE_FILTERS["date_from"]["format"] == "date"
    assert DATE_FILTERS["date_to"]["format"] == "date"
    assert COMPANY_PARAM["company_id"]["required"] is True
    assert PAGINATED_RESPONSE["properties"]["items"] == {"type": "array"}
    assert PAGINATED_RESPONSE["properties"]["has_next_page"] == {"type": "boolean"}
    error_properties = ERROR_RESPONSE["properties"]["error"]["properties"]
    assert set(error_properties) == {"code", "message", "request_id"}
    assert all(value == {"type": "string"} for value in error_properties.values())


def test_registered_tool_schemas_only_publish_accepted_handler_parameters() -> None:
    """Verifica que cada parámetro anunciado pueda recibirse por su handler."""
    from cacao_accounting.query_tools import load_query_tools
    from cacao_accounting.query_tools.registry import registry

    load_query_tools()
    for tool in registry.list_tools().values():
        if tool.handler is None:
            continue

        handler_parameters = signature(tool.handler).parameters
        accepts_arbitrary_keywords = any(parameter.kind is Parameter.VAR_KEYWORD for parameter in handler_parameters.values())
        if accepts_arbitrary_keywords:
            continue

        accepted_parameters = set(handler_parameters) - {"context"}
        published_parameters = set(tool.parameters_schema.get("properties", {}))
        required_parameters = set(tool.parameters_schema.get("required", []))

        assert published_parameters <= accepted_parameters, (
            f"{tool.name} publishes unsupported parameters: " f"{sorted(published_parameters - accepted_parameters)}"
        )
        assert required_parameters <= accepted_parameters, (
            f"{tool.name} requires unsupported parameters: " f"{sorted(required_parameters - accepted_parameters)}"
        )


def test_operational_tool_schemas_only_include_supported_filters() -> None:
    """Protege contratos específicos de ventas, compras, inventario y bancos."""
    from cacao_accounting.query_tools import load_query_tools
    from cacao_accounting.query_tools.registry import registry

    load_query_tools()
    common = {"company_id", "page", "page_size"}
    date_range = {"date_from", "date_to"}
    expected_properties = {
        "sales.get_by_customer": common | date_range | {"party_id"},
        "sales.get_by_item": common | date_range | {"item_code"},
        "sales.get_gross_margin": common | date_range,
        "purchases.get_by_supplier": common | date_range | {"party_id"},
        "purchases.get_by_item": common | date_range | {"item_code"},
        "documents.get_related_documents": common | {"document_type", "document_id"},
        "receivables.get_subledger": common | {"party_id", "as_of_date"},
        "payables.get_subledger": common | {"party_id", "as_of_date"},
        "inventory.get_kardex": common | date_range | {"item_code", "warehouse"},
        "inventory.get_existence": common | date_range | {"item_code", "warehouse"},
        "inventory.get_batches": common | {"item_code", "warehouse"},
        "inventory.get_serials": common | {"item_code", "warehouse"},
        "inventory.get_negative_stock": common | {"item_code", "warehouse"},
        "inventory.get_reorder_alerts": common | {"item_code", "warehouse"},
        "inventory.get_transfers": common | date_range | {"item_code", "warehouse"},
        "inventory.get_slow_moving_items": common | {"date_to", "item_code", "warehouse", "inactivity_days"},
        "inventory.get_turnover": common | date_range | {"item_code", "warehouse"},
        "inventory.get_stock_balance": common | {"item_code", "warehouse"},
        "inventory.get_valuation": common | {"date_to", "item_code", "warehouse"},
        "banking.get_balance_summary": common | {"as_of_date", "bank_account_id"},
        "banking.get_unreconciled_transactions": common | date_range | {"bank_account_id"},
    }

    tools = registry.list_tools()
    for name, expected in expected_properties.items():
        schema = tools[name].parameters_schema
        assert set(schema["properties"]) == expected, name
        expected_required = {
            "inventory.get_turnover": {"company_id", "date_from", "date_to"},
            "documents.get_related_documents": {"company_id", "document_type", "document_id"},
        }.get(name, {"company_id"})
        assert set(schema.get("required", [])) == expected_required, name
