# Guía para Diseñadores de Formatos de Impresión

Esta guía explica cómo crear y editar templates de impresión en Cacao Accounting.

## Componentes del Template

Un formato de impresión consta de:
1. **Cuerpo del Template**: Estructura HTML que usa variables de Jinja2.
2. **Cuerpo de la Hoja de Estilos**: Reglas CSS para el diseño y el estilo.

## Variables Disponibles

Cada template tiene acceso a nodos comunes:
- `company`: Información sobre la entidad emisora (`name`, `tax_id`, `address`, etc.).
- `audit`: Metadatos sobre el trabajo de impresión (`printed_by`, `printed_at`).
- `validation`: Datos de validación por QR (`enabled`, `public_url`, `qr_data_uri`).

### Detalles Específicos del Documento

Cada tipo de documento tiene su propio nodo raíz (p. ej., `journal_entry`).

## Agregar el Bloque de Validación QR

Para incluir el código QR de validación en tu template, agrega este bloque:

```html
{% if validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
    <img src="{{ validation.qr_data_uri }}" class="qr-code">
    <div class="validation-text">
        <strong>Validate document</strong><br>
        Scan this QR code to verify this document.
    </div>
</div>
{% endif %}
```

## Consejos de CSS

Los templates se renderizan a PDF usando WeasyPrint. Usa `@page` para los márgenes:

```css
@page {
    size: letter portrait;
    margin: 15mm;
}
```
