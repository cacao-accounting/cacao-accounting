DOCUMENT_TIMELINE_PARAMS = {
    "type": "object",
    "properties": {
        "company_id": {"type": "string"},
        "document_type": {"type": "string"},
        "document_id": {"type": "string"},
        "page": {"type": "integer", "default": 1},
        "page_size": {"type": "integer", "default": 100, "maximum": 500},
    },
    "required": ["company_id", "document_type", "document_id"],
}
