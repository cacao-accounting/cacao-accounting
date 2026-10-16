# Filtros y Auxiliares

El Servicio de Impresión proporciona un conjunto de filtros Jinja2 seguros para dar formato a los datos en tus templates.

## `money`

Da formato a un valor numérico como una cadena de moneda.

**Uso:** `{{ invoice.grand_total | money(invoice.currency) }}`
**Salida:** `NIO 1,150.00`

## `date`

Da formato a un objeto de fecha o una cadena ISO usando la configuración regional del sistema.

**Uso:** `{{ invoice.date | date }}`
**Salida:** `26/05/2026`

## `datetime`

Da formato a una marca de tiempo usando la configuración regional del sistema.

**Uso:** `{{ audit.printed_at | datetime }}`
**Salida:** `26/05/2026 10:15`

## `number`

Da formato a un número con una cantidad específica de decimales.

**Uso:** `{{ item.quantity | number(3) }}`
**Salida:** `1.000`

## `percent`

Da formato a un valor como porcentaje.

**Uso:** `{{ tax.rate | percent }}`
**Salida:** `15.0%`

## `default_text`

Proporciona una cadena de respaldo si el valor está vacío o es None.

**Uso:** `{{ invoice.notes | default_text("No notes.") }}`

## `status_label`

Convierte un código de estado técnico en una etiqueta legible por humanos.

**Uso:** `{{ invoice.status | status_label }}`
**Salida:** `Posted` (desde "posted")
