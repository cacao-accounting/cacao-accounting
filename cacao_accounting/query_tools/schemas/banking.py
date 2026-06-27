"""Esquemas de validación para los endpoints del módulo de banca."""

BANKING_ACCOUNTS_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id"],
}

BANKING_TRANSACTIONS_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "bank_account_id": {"type": "string", "description": "Filtrar por cuenta bancaria (opcional)"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id"],
}
