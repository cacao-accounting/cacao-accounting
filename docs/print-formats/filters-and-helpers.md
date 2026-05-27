# Filters and Helpers

The Printing Service provides a set of secure Jinja2 filters to format data in your templates.

## `money`

Formats a numeric value as a currency string.

**Usage:** `{{ invoice.grand_total | money(invoice.currency) }}`
**Output:** `NIO 1,150.00`

## `date`

Formats a date object or ISO string using the system locale.

**Usage:** `{{ invoice.date | date }}`
**Output:** `26/05/2026`

## `datetime`

Formats a timestamp using the system locale.

**Usage:** `{{ audit.printed_at | datetime }}`
**Output:** `26/05/2026 10:15`

## `number`

Formats a number with a specific number of decimal places.

**Usage:** `{{ item.quantity | number(3) }}`
**Output:** `1.000`

## `percent`

Formats a value as a percentage.

**Usage:** `{{ tax.rate | percent }}`
**Output:** `15.0%`

## `default_text`

Provides a fallback string if the value is empty or None.

**Usage:** `{{ invoice.notes | default_text("No notes.") }}`

## `status_label`

Converts a technical status code into a human-readable label.

**Usage:** `{{ invoice.status | status_label }}`
**Output:** `Posted` (from "posted")
