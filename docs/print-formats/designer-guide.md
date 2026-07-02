# Guide for Print Format Designers

This guide explains how to create and edit print templates in Cacao Accounting.

## Template Components

A print format consists of:
1. **Template Body**: HTML structure using Jinja2 variables.
2. **Stylesheet Body**: CSS rules for layout and styling.

## Available Variables

Every template has access to common nodes:
- `company`: Information about the emitting entity (`name`, `tax_id`, `address`, etc.).
- `audit`: Metadata about the print job (`printed_by`, `printed_at`).
- `validation`: QR validation data (`enabled`, `public_url`, `qr_data_uri`).

### Document Specifics

Each document type has its own root node (e.g., `journal_entry`).

## Adding the QR Validation Block

To include the validation QR code in your template, add this block:

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

## CSS Tips

Templates are rendered to PDF using WeasyPrint. Use `@page` for margins:

```css
@page {
    size: letter portrait;
    margin: 15mm;
}
```
