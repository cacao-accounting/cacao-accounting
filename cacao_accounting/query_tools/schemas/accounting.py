ACCOUNTING_PERIODS_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string", "description": "Código de la compañía"},
        "status": {
            "type": "string",
            "description": "Filtrar por estado (opcional)",
            "enum": ["open", "closed"],
        },
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id"],
}

ACCOUNTS_SEARCH_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "query": {"type": "string", "description": "Búsqueda por código o nombre"},
        "classification": {
            "type": "string",
            "description": "Filtrar por clasificación",
            "enum": ["Activo", "Pasivo", "Patrimonio", "Ingresos", "Gastos"],
        },
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id"],
}

TRIAL_BALANCE_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "ledger_id": {"type": "string", "description": "Código del libro contable"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id", "ledger_id", "date_from", "date_to"],
}

GENERAL_LEDGER_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "ledger_id": {"type": "string"},
        "account_id": {"type": "string", "description": "ID de la cuenta contable"},
        "date_from": {"type": "string", "format": "date"},
        "date_to": {"type": "string", "format": "date"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id", "ledger_id", "date_from", "date_to"],
}
