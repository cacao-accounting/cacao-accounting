"""Esquemas de validación comunes compartidos entre módulos."""

PAGINATION_PARAMS = {
    "page": {
        "type": "integer",
        "description": "Número de página (empieza en 1)",
        "default": 1,
        "minimum": 1,
    },
    "page_size": {
        "type": "integer",
        "description": "Elementos por página",
        "default": 100,
        "maximum": 500,
    },
}

DATE_FILTERS = {
    "date_from": {
        "type": "string",
        "format": "date",
        "description": "Fecha inicial (YYYY-MM-DD)",
    },
    "date_to": {
        "type": "string",
        "format": "date",
        "description": "Fecha final (YYYY-MM-DD)",
    },
}

PAGINATED_RESPONSE = {
    "type": "object",
    "properties": {
        "page": {"type": "integer"},
        "page_size": {"type": "integer"},
        "total_items": {"type": "integer"},
        "total_pages": {"type": "integer"},
        "has_next_page": {"type": "boolean"},
        "items": {"type": "array"},
    },
}

ERROR_RESPONSE = {
    "type": "object",
    "properties": {
        "error": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "request_id": {"type": "string"},
            },
        }
    },
}

COMPANY_PARAM = {
    "company_id": {
        "type": "string",
        "description": "Código de la compañía",
        "required": True,
    }
}
