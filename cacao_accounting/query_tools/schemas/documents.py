"""Esquemas de validación para los endpoints del módulo de documentos."""

from typing import Any

DOCUMENTS_FLOW_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "document_type": {"type": "string", "description": "Tipo de documento (e.g. sales_invoice, purchase_invoice)"},
        "document_id": {"type": "string", "description": "ID del documento"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id", "document_type", "document_id"],
}
