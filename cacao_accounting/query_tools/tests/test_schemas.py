"""Pruebas de contrato para los esquemas públicos de query tools."""

from __future__ import annotations

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


def _assert_object_schema(schema: dict, required: set[str], properties: set[str]) -> None:
    """Comprueba el contrato común de un esquema de parámetros JSON."""
    assert schema["type"] == "object"
    assert set(schema.get("required", [])) == required
    assert set(schema["properties"]) == properties


def _assert_pagination_properties(schema: dict) -> None:
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
def test_receivables_and_payables_schemas_have_expected_contract(schema, required, properties):
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
