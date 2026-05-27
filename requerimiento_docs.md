Confirmado.

Agregar al requerimiento:

> El módulo de formatos de impresión debe incluir documentación comprensiva en `docs/` dirigida al **diseñador de formatos de impresión**.

Ubicación sugerida:

```text
docs/
  print-formats/
    index.md
    designer-guide.md
    jinja-context-reference.md
    css-guide.md
    filters-and-helpers.md
    examples/
      sales-invoice.md
      journal-entry.md
      bank-payment.md
```

Contenido mínimo obligatorio:

* Qué es un formato de impresión.
* Cómo funcionan `template_body` y `stylesheet_body`.
* Cómo usar variables Jinja2.
* Campos disponibles por tipo de documento, en inglés.
* Ejemplos de loops, especialmente líneas/items.
* Filtros disponibles: `money`, `date`, `datetime`, `number`, `percent`, etc.
* Snippets comunes: encabezado, tabla de líneas, totales, firmas.
* Guía CSS compatible con WeasyPrint.
* Limitaciones: sin JavaScript, sin cálculos fiscales/contables en template.
* Cómo usar preview en iframe.
* Cómo exportar a PDF.
* Cómo duplicar una plantilla de sistema.
* Cómo publicar o marcar default.
* Reglas de seguridad y permisos.
* Ejemplos completos por transacción crítica.

También debe existir documentación técnica breve para desarrolladores sobre cómo registrar un nuevo `document_type`, crear su `context_builder`, `sample_context_builder`, `schema` y seed de plantilla básica.
