# Snippets Reutilizables

Usa estos snippets en tus templates para las secciones comunes de los documentos.

## Encabezado de Compañía

Encabezado estándar con logo e información de la entidad.

```html
<div class="company-header">
    <img src="{{ company.logo_url }}" alt="Logo" style="height: 60px;">
    <h1>{{ company.name }}</h1>
    <p>Tax ID: {{ company.tax_id }}</p>
    <p>{{ company.address }}</p>
</div>
```

## Bloque de Validación QR

Incluye este bloque para mostrar el código QR de autenticidad.

```html
{% if validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
    <img src="{{ validation.qr_data_uri }}" class="qr-code">
    <div class="validation-text">
        <strong>Validate document</strong><br>
        Scan this QR code to verify authenticity.
    </div>
</div>
{% endif %}
```

## Pie de Auditoría

Muestra metadatos sobre quién imprimió el documento y cuándo.

```html
<div class="audit-footer">
    <p>Printed by: {{ audit.printed_by }} on {{ audit.printed_at | datetime }}</p>
</div>
```
