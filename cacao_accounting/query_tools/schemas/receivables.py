RECEIVABLES_AGING_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "as_of_date": {"type": "string", "format": "date"},
        "party_id": {"type": "string", "description": "Filtrar por cliente (opcional)"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id", "as_of_date"],
}

RECEIVABLES_OPEN_DOCUMENTS_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "party_id": {"type": "string", "description": "Filtrar por cliente (opcional)"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id"],
}
