# Reusable Snippets

Use these snippets in your templates for common document sections.

## Company Header

Standard header with logo and entity information.

```html
<div class="company-header">
    <img src="{{ company.logo_url }}" alt="Logo" style="height: 60px;">
    <h1>{{ company.name }}</h1>
    <p>Tax ID: {{ company.tax_id }}</p>
    <p>{{ company.address }}</p>
</div>
```

## QR Validation Block

Include this block to show the authenticity QR code.

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

## Audit Footer

Shows metadata about who and when printed the document.

```html
<div class="audit-footer">
    <p>Printed by: {{ audit.printed_by }} on {{ audit.printed_at | datetime }}</p>
</div>
```
