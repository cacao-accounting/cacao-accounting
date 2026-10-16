# Guía para Desarrolladores

Cómo registrar un nuevo tipo de documento imprimible.

## 1. Registrar el Documento

Agrega tu documento a `cacao_accounting/printing/registry.py`:

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

## 2. Implementar los Constructores de Contexto

En `cacao_accounting/printing/context.py`, implementa:
- `build_my_doc_context(document_id, user, company_code)`: Obtiene los datos reales de la base de datos.
- `build_my_doc_sample(user=None, company=None)`: Devuelve datos de ejemplo estáticos para la vista previa.

**Regla:** Nunca pases objetos de SQLAlchemy directamente. Usa diccionarios con valores serializables.

## 3. Crear un Template Semilla

Agrega un template de sistema por defecto en `cacao_accounting/printing/seed.py` para que el documento sea imprimible inmediatamente después de la instalación.

## 4. Integrar la Validación

En el servicio de posteo de tu módulo, llama a la actualización de validación:

```python
from cacao_accounting.printing.validation import ValidationService
ValidationService().update_validation_from_document(my_doc_object)
```
