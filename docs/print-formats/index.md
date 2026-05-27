# Printing Service in Cacao Accounting

The Printing Service is a reusable component designed to generate consistent, professional, and secure HTML and PDF documents for all system transactions.

## For Administrators

Administrators can manage print formats globally or per company.

- **Centralized Management**: Create, edit, and duplicate templates from a single interface.
- **System Templates**: Each transaction includes a standard, non-editable system template that can be used as a starting point.
- **Versioning**: Every change to a template is saved as a new version, allowing for historical review and restoration.
- **Security**: Templates are rendered in a safe sandbox environment to prevent malicious code execution.

## Key Concepts

### Template vs. Stylesheet
A print format consists of two parts:
1. **Template Body**: The HTML structure using Jinja2 syntax for dynamic data.
2. **Stylesheet Body**: CSS rules to control the layout and appearance.

### No Snapshots
Cacao Accounting does **not** store generated PDFs or HTML snapshots. Documents are always rendered using the current data in the database and the latest published version of the selected template.

### QR Validation
Documents can include a QR code that allows third parties to verify the authenticity and integrity of the document by scanning it.
