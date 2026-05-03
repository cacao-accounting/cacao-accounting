# Módulo: Ventas (Selling / Sales)

## Rol en el sistema

Módulo operativo que cubre el flujo **Order to Cash (O2C)**.
Gestiona la relación con clientes desde la cotización hasta el cobro.

---

## Principios de diseño

- Patrón obligatorio: Header + Items.
- La entrega y la facturación son eventos separados.
- Los cobros se manejan en el módulo Bancos.
- El impacto contable se genera automáticamente via `gl_entry`.
- Multimoneda real: un cliente puede ser facturado en cualquier moneda.
- El saldo AR se calcula como suma de partidas abiertas (Open Items model).

---

## Modelos disponibles en base de datos

| Modelo | Tabla | Descripción |
|---|---|---|
| `Party` (type=customer) | `party` | Cliente global. |
| `CompanyParty` | `company_party` | Activación del cliente en una compañía. |
| `SalesOrder` | `sales_order` | Orden de venta. Header. |
| `SalesOrderItem` | `sales_order_item` | Líneas de la orden de venta. |
| `DeliveryNote` | `delivery_note` | Nota de entrega / remisión. Header. |
| `DeliveryNoteItem` | `delivery_note_item` | Líneas de la entrega. |
| `SalesInvoice` | `sales_invoice` | Factura de cliente. Header. |
| `SalesInvoiceItem` | `sales_invoice_item` | Líneas de la factura. |
| `TaxTemplate` | `tax_template` | Plantilla de impuestos de venta. |
| `PriceList` | `price_list` | Lista de precios de venta. |
| `ItemPrice` | `item_price` | Precio por ítem en lista de precios. |

---

## Flujo Order to Cash (O2C)

```
Cotización [futuro]
    → Orden de venta (SalesOrder)
        → Anticipo total o parcial (PaymentEntry - receive)
        → Nota de entrega (DeliveryNote)
            → Factura de cliente (SalesInvoice)
                → GL Entry (AR + ingreso + impuestos)
                    → Aplicación de anticipos y/o pago final (PaymentReference)
                        → Conciliación (Reconciliation)
```

### Flujo no lineal y realista (con correcciones)

```
Orden de venta
   ├─→ Entrega parcial
   │    ├─→ Factura parcial
   │    ├─→ Ajuste de precio
   │    └─→ Nota de crédito / débito
   ├─→ Error de UOM detectado
   │    └─→ Documento de corrección + reversión contable
   ├─→ Error de precio detectado
   │    └─→ Nota de crédito o nota de débito
   ├─→ Devolución parcial o total
   │    └─→ Delivery Return + Sales Credit Note
   └─→ Cobro parcial / anticipo / sobrepago
        └─→ Reconciliación incremental
```

### Anticipos de cliente (totales y parciales)

- Se permiten anticipos antes de entrega y antes de facturación.
- Un anticipo puede cubrir el 100% de la venta o una parte.
- El anticipo se registra como pasivo/anticipo de cliente hasta aplicar a factura.
- Al facturar, la aplicación del anticipo reduce `outstanding_amount`.
- Si el anticipo supera la factura, el remanente queda como crédito del cliente.

---

## Documentos del módulo

### Sales Order

**Campos clave:**
- `party_id` — cliente.
- `company` — compañía vendedora.
- `posting_date` — fecha de la orden.
- `currency`, `exchange_rate` — moneda del cliente.
- `total_amount`, `base_total_amount` — monto en moneda original y base.
- `docstatus` — Draft / Submitted / Cancelled.

**Estados:** Draft → Submitted → (parcialmente entregado/facturado) → Cerrado.

**Reglas:**
- Una orden puede tener múltiples entregas parciales.
- Una orden puede tener múltiples facturas parciales.
- La orden no genera `gl_entry` directamente.

---

### Delivery Note

**Campos clave:**
- `sales_order_id` — referencia a la orden (opcional, entrega directa posible).
- `warehouse` — almacén origen.
- `posting_date` — fecha contable del movimiento de inventario.
- `is_return` — para devoluciones de cliente.

**Impacto:**
- Genera `StockLedgerEntry` si el ítem es inventariable.
- Genera `StockValuationLayer` para registro del costo de ventas.
- No genera AR directamente; solo movimiento de inventario y costo de ventas.

---

### Sales Invoice

**Campos clave:**
- `delivery_note_id` — referencia a la entrega (puede ser directa sin entrega).
- `party_id` — cliente.
- `outstanding_amount` / `base_outstanding_amount` — saldo pendiente de cobro.
- `is_return` — nota de crédito (devolución de cliente).
- `reversal_of` / `is_reversal` — soporte de reversión.
- `due_date` — vencimiento.

**Impacto contable (GL):**
- Débita cuenta por cobrar (AR) del cliente.
- Acredita cuenta de ingresos.
- Registra costo de ventas si el ítem es inventariable.
- Registra impuestos en cuentas de impuesto por cobrar.

**Ciclo de vida:**
```
Draft → Submitted → Partially Paid → Paid / Cancelled
```

**Documentos de corrección relacionados:**
- Nota de crédito de ventas: corrige sobrecargos, devoluciones, descuentos retroactivos.
- Nota de débito de ventas: corrige subcargos, intereses, ajustes posteriores.
- Reversión: para errores estructurales no corregibles por nota.

---

## Saldo AR y Open Items

- `outstanding_amount` en `SalesInvoice` es el saldo vivo.
- El saldo real = `total_amount` − `SUM(allocated_amount en PaymentReference)`.
- El campo persistido es cache; el cálculo dinámico es la fuente de verdad.
- Consistencia temporal: siempre filtrar por `posting_date` y `allocation_date`.
- La aplicación de anticipos solo afecta saldo desde `allocation_date`.

---

## Multimoneda en Ventas

- `SalesInvoice` tiene `currency`, `exchange_rate`.
- GL almacena el valor en moneda base y en moneda original.
- Un mismo cliente puede tener facturas activas en múltiples monedas simultáneamente.

---

## Impuestos en Ventas

- `TaxTemplate` tipo `selling` aplicada al documento.
- `TaxTemplateItem` define cada impuesto (IVA, ISC, otros).
- Los impuestos generan líneas en `gl_entry` hacia cuentas de impuesto por cobrar.
- Los impuestos y cargos deben soportar:
    - Monto fijo.
    - Porcentaje.
    - Comportamiento aditivo (suma al total de factura).
    - Comportamiento deductivo (resta del total de factura).

### Otros cargos y gastos en ventas

- Debe soportarse cargos como flete al cliente, seguro, recargos administrativos.
- Cada cargo debe definir cuenta contable de destino.
- El cargo puede formar parte del total facturado o manejarse como ajuste separado según política.
- Debe quedar trazabilidad de la base de cálculo y del signo del cargo (sumar/restar).

---

## Pricing en Ventas

- `PriceList` tipo `selling`.
- `ItemPrice` almacena precio por ítem, lista, moneda y fecha de vigencia.
- El precio es sugerido; el documento puede sobreescribirlo.
- Debe existir tolerancia de precio configurable por rol y por tipo de documento.
- Si el precio cae fuera de tolerancia, el documento requiere aprobación por workflow.

---

## Errores operativos y políticas de corrección

### Error de unidad de medida (UOM)

- No se corrige alterando el documento contabilizado.
- Se corrige por uno de estos mecanismos:
    - Reversión y recreación del documento con UOM correcta.
    - Documento de ajuste que compense diferencia de cantidad y valor.
- Todo ajuste debe recalcular COGS y margen si corresponde.

### Error de precio

- Si la factura ya fue contabilizada:
    - Diferencia a favor del cliente → nota de crédito.
    - Diferencia a favor de la empresa → nota de débito.
- Si no fue contabilizada, puede editarse en Draft con trazabilidad de cambios.

### Descuentos y rebajas

- Descuentos por línea y globales desde origen del documento.
- Rebajas posteriores se gestionan por nota de crédito, nunca por edición retroactiva.
- Debe existir razón de ajuste obligatoria (reason code).

### Auditabilidad obligatoria

- Todo documento de corrección referencia documento origen (`reference_type`, `reference_id`).
- Toda corrección debe registrar usuario, fecha, motivo y diferencia monetaria.
- Ninguna corrección puede romper el histórico de saldos por fecha.

---

## Integraciones con otros módulos

| Módulo | Relación |
|---|---|
| Inventario | `DeliveryNote` genera `StockLedgerEntry` y descarga costo de ventas. |
| Bancos | `PaymentEntry` (type=receive) cobra `SalesInvoice` vía `PaymentReference`. |
| Contabilidad | `SalesInvoice` genera `gl_entry` (AR, ingresos, impuestos, COGS). |

---

## Reportería requerida

| Reporte | Descripción |
|---|---|
| Órdenes de venta pendientes | Por cliente, ítem, estado. |
| Entregas pendientes de facturar | Estado por orden. |
| Cuentas por cobrar (AR) | Saldo pendiente por cliente. |
| Aging de AR | Vencimientos por bucket temporal (30/60/90/+90 días). |
| Ventas por cliente | Monto total por período. |
| Ventas por ítem | Unidades y valor por período. |
| Margen bruto | Ingreso − COGS por ítem / cliente / período. |

---

## Casos que debe soportar

- Entrega parcial de una orden.
- Factura sin orden de venta (factura directa).
- Devolución parcial de cliente (`is_return=True`, nota de crédito).
- Devolución total posterior a cobro parcial.
- Nota de débito posterior por diferencia de precio.
- Corrección por UOM equivocada en entrega o factura.
- Corrección por precio equivocado con documento ya contabilizado.
- Cliente con moneda distinta a moneda base.
- Un cliente con facturas abiertas en múltiples monedas.
- Pago anticipado de cliente (anticipo).
- Anticipo total con factura posterior en fecha distinta.
- Anticipo parcial aplicado a múltiples facturas.
- Sobrepago y aplicación cruzada de cobros.
- Descuentos por línea y globales.
- Rebajas comerciales posteriores a la facturación.
- Impuestos fijos y porcentuales combinados en la misma factura.
- Cargos aditivos y deductivos coexistiendo en el mismo documento.
- Flete facturado al cliente con cuenta de ingreso/recuperación diferenciada.
- Aging histórico reproducible por fecha.
