# CSS Guide for Print Formats

Cacao Accounting uses **WeasyPrint** to convert HTML and CSS into PDF documents. To ensure your templates look great, follow these guidelines.

## @page Rule

Use the `@page` rule to define paper size and margins.

```css
@page {
    size: letter portrait;
    margin: 1cm;
}
```

## Tables

For documents with many items (like invoices), use standard table headers and footers that repeat across pages.

```css
thead {
    display: table-header-group;
}
tfoot {
    display: table-footer-group;
}
```

## Helper Classes

It is recommended to define utility classes for common needs:

```css
.text-right { text-align: right; }
.text-center { text-align: center; }
.bold { font-weight: bold; }
.mt-20 { margin-top: 20px; }
```

## Page Breaks

Force a page break when needed:

```css
.page-break {
    page-break-before: always;
}
```

## Limitations

- **No JavaScript**: Scripts are strictly prohibited and will not run.
- **Modern CSS**: While WeasyPrint supports many CSS3 features (Flexbox, Grid), avoid very complex or experimental properties.
- **External Resources**: External fonts or images should be hosted on the same server or accessible via HTTPS.
