"""Esquemas de validación para los endpoints del módulo de compañías."""

from typing import Any

COMPANIES_LIST_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
}

COMPANIES_LIST_RESPONSE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page": {"type": "integer"},
        "page_size": {"type": "integer"},
        "total_items": {"type": "integer"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "company_name": {"type": "string"},
                    "tax_id": {"type": "string"},
                    "currency": {"type": "string"},
                    "country": {"type": "string"},
                    "enabled": {"type": "boolean"},
                },
            },
        },
    },
}
