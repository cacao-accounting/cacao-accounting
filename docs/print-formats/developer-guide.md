# Developer Guide

How to register a new printable document type.

## 1. Register the Document

Add your document to `cacao_accounting/printing/registry.py`:

```python
register_printable_document(
    "my_new_doc",
    {
        "label": "My New Document",
        "module": "my_module",
        "root_context_name": "doc",
        "permission": "my_module.view",
        "context_builder": build_my_doc_context,
        "sample_context_builder": build_my_doc_sample,
        "schema": MY_DOC_SCHEMA,
        "snippets": [],
    },
)
```

## 2. Implement Context Builders

In `cacao_accounting/printing/context.py`, implement:
- `build_my_doc_context(document_id, user, company_code)`: Fetches real data from DB.
- `build_my_doc_sample(user=None, company=None)`: Returns static sample data for preview.

**Rule:** Never pass SQLAlchemy objects directly. Use dictionaries with serializable values.

## 3. Create a Seed Template

Add a default system template in `cacao_accounting/printing/seed.py` so the document is immediately printable after installation.

## 4. Integrate Validation

In your module's posting service, call the validation update:

```python
from cacao_accounting.printing.validation import ValidationService
ValidationService().update_validation_from_document(my_doc_object)
```
