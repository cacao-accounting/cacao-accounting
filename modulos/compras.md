# Módulo: Compras (Buying / Purchasing)

## Rol en el sistema

Módulo operativo que cubre el flujo **Source to Pay (S2P)**.
Gestiona la relación con proveedores desde la cotización hasta el pago.

---

## Principios de diseño

- Todo documento tiene `company`, `posting_date`, `docstatus`.
- Patrón obligatorio: Header + Items.
- La recepción y la facturación son eventos separados (GI/IR pattern).
- Los pagos se manejan en el módulo Bancos.
- El impacto contable se genera automáticamente via `gl_entry`.
- Multimoneda real: un proveedor puede facturar en cualquier moneda.

---

## Modelos disponibles en base de datos

| Modelo | Tabla | Descripción |
|---|---|---|
| `Party` (type=supplier) | `party` | Proveedor global. |
| `CompanyParty` | `company_party` | Activación del proveedor en una compañía. |
| `PurchaseOrder` | `purchase_order` | Orden de compra. Header. |
| `PurchaseOrderItem` | `purchase_order_item` | Líneas de la orden de compra. |
| `PurchaseReceipt` | `purchase_receipt` | Recepción de mercancía. Header. |
| `PurchaseReceiptItem` | `purchase_receipt_item` | Líneas de la recepción. |
| `PurchaseInvoice` | `purchase_invoice` | Factura de proveedor. Header. |
| `PurchaseInvoiceItem` | `purchase_invoice_item` | Líneas de la factura. |
| `GRIRReconciliation` | `gr_ir_reconciliation` | Reconciliación mercancía recibida vs facturada. |
| `TaxTemplate` | `tax_template` | Plantilla de impuestos de compra. |
| `PriceList` | `price_list` | Lista de precios aplicable a compras. |
| `ItemPrice` | `item_price` | Precio por ítem en lista de precios. |

---

## Flujo Source to Pay (S2P)

```
Solicitud de cotización (RFQ) [futuro]
    → Cotización de proveedor [futuro]
        → Orden de compra (PurchaseOrder)
            → Anticipo total o parcial a proveedor (PaymentEntry - pay)
            → Recepción de mercancía (PurchaseReceipt)
                → Factura de proveedor (PurchaseInvoice)
                    → GL Entry (AP + GI/IR)
                        → Aplicación de anticipos y/o pago final (PaymentReference)
                            → Conciliación (Reconciliation)
```

### Flujo no lineal y realista (con correcciones)

```
Orden de compra
   ├─→ Recepción parcial
   │    ├─→ Factura parcial
   │    ├─→ Diferencia GI/IR
   │    └─→ Reconciliación incremental
   ├─→ Error de UOM
   │    └─→ Ajuste de inventario + corrección documental
   ├─→ Error de precio
   │    └─→ Nota de crédito / nota de débito de proveedor
   ├─→ Devolución parcial o total
   │    └─→ Purchase Return + reverso contable
   └─→ Pago parcial / anticipo / compensación
        └─→ Reconciliación AP por fecha
```

### Anticipos a proveedor (totales y parciales)

- Se permiten anticipos antes de recepción y antes de factura.
- Un anticipo puede cubrir el 100% de la compra o una parte.
- El anticipo se registra como activo/anticipo a proveedor hasta aplicar a factura.
- Al registrar factura, la aplicación del anticipo reduce `outstanding_amount`.
- Si el anticipo supera la factura, el remanente queda como saldo a favor.

---

## Documentos del módulo

### Purchase Order

**Campos clave:**
- `party_id` — proveedor.
- `company` — compañía compradora.
- `posting_date` — fecha de la orden.
- `currency`, `exchange_rate` — moneda del proveedor.
- `total_amount`, `base_total_amount` — monto en moneda original y base.
- `docstatus` — Draft / Submitted / Cancelled.

**Estados:** Draft → Submitted → (parcialmente recibido) → Cerrado.

**Reglas:**
- Una orden puede tener múltiples recepciones parciales.
- Una orden puede tener múltiples facturas parciales.
- La orden no genera `gl_entry` directamente.

---

### Purchase Receipt

**Campos clave:**
- `purchase_order_id` — referencia a la orden (opcional, recepción directa posible).
- `warehouse` — almacén destino.
- `posting_date` — fecha contable del movimiento de inventario.
- `is_return` — para devoluciones a proveedor.

**Impacto:**
- Genera `StockLedgerEntry` si el ítem es inventariable (`is_stock_item=True`).
- Genera `StockValuationLayer` según método de valuación del ítem (FIFO / Moving Average).
- Acredita la cuenta GI/IR (`goods_in_transit` / cuenta intermedia).
- No genera AP directamente; solo movimiento de inventario.

---

### Purchase Invoice

**Campos clave:**
- `purchase_receipt_id` — referencia a la recepción (puede ser directa sin recepción).
- `party_id` — proveedor.
- `outstanding_amount` / `base_outstanding_amount` — saldo pendiente de pago.
- `is_return` — nota de débito (devolución).
- `reversal_of` / `is_reversal` — soporte de reversión.
- `due_date` — vencimiento.

**Impacto contable (GL):**
- Débita cuenta de gasto o inventario (según ítem).
- Acredita cuenta por pagar (AP) del proveedor.
- Descarga la cuenta GI/IR si viene de recepción previa.
- Registra impuestos en cuentas de impuesto por pagar.

**Ciclo de vida:**
```
Draft → Submitted → Partially Paid → Paid / Cancelled
```

**Documentos de corrección relacionados:**
- Nota de crédito de proveedor: reduce AP por sobrecobro, devolución o descuento posterior.
- Nota de débito de proveedor: incrementa AP por subcobro o cargos posteriores.
- Reversión: para errores estructurales no corregibles por nota.

---

## GI/IR (Goods Received / Invoice Received)

Cuenta intermedia obligatoria para separar recepción de facturación:

- Al recibir mercancía: débita inventario, acredita GI/IR.
- Al registrar factura: débita GI/IR, acredita AP.
- `GRIRReconciliation` reconcilia las diferencias.

**Regla:** la cuenta GI/IR debe quedar en cero luego de la reconciliación.

---

## Multimoneda en Compras

- `PurchaseInvoice` tiene `currency`, `exchange_rate`.
- GL almacena el valor en moneda base y en moneda original.
- El saldo AP se calcula en moneda base; el análisis por moneda es secundario.
- La aplicación de anticipos debe respetar `allocation_date` y tipo de cambio de aplicación.

---

## Impuestos en Compras

- `TaxTemplate` aplicada al documento.
- `TaxTemplateItem` define cada impuesto (tasa, tipo, cuenta contable).
- Los impuestos generan líneas en `gl_entry` hacia cuentas de impuesto por pagar.
- Los impuestos y cargos deben soportar:
    - Monto fijo.
    - Porcentaje sobre base imponible.
    - Comportamiento aditivo (suma al total) o deductivo (resta al total).

### Cargos, costos y gastos adicionales (flete, seguro, aduana, etc.)

- Debe existir soporte para cargos adicionales por documento y por línea.
- Cada cargo debe indicar si:
    - se capitaliza al costo del producto, o
    - se reconoce como gasto inmediato en cuenta contable separada.
- Si se capitaliza, debe prorratearse entre ítems usando regla configurable:
    - por cantidad,
    - por peso/volumen,
    - por valor neto de línea.
- Si no se capitaliza, debe postear contra cuenta de gasto definida en la plantilla del cargo.
- El prorrateo debe actualizar `StockValuationLayer` para ítems inventariables.

---

## Pricing en Compras

- `PriceList` tipo `buying`.
- `ItemPrice` almacena precio por ítem, lista, moneda y fecha de vigencia.
- El precio es sugerido; el documento puede sobreescribirlo.
- Debe existir tolerancia de precio por rol y por tipo documental.
- Diferencias fuera de tolerancia deben pasar por aprobación de workflow.

---

## Errores operativos y políticas de corrección

### Error de unidad de medida (UOM)

- Si ya hubo recepción/factura contabilizada, no se edita histórico.
- Se corrige con devolución + nueva recepción/factura o con ajuste compensatorio.
- Debe recalcularse costo unitario y capa de valuación afectada.

### Error de precio

- Factura contabilizada:
    - Sobrecobro proveedor → nota de crédito de proveedor.
    - Subcobro proveedor → nota de débito de proveedor.
- Factura en Draft: edición permitida con bitácora de cambios.

### Descuentos y rebajas

- Descuentos por línea y globales desde origen del documento.
- Rebajas posteriores se registran como nota de crédito de proveedor.
- Todo ajuste debe tener motivo obligatorio (reason code).

### Auditabilidad obligatoria

- Todo documento de corrección referencia el documento original.
- Debe quedar traza de usuario, fecha, motivo, monto y moneda.
- La corrección no puede invalidar el saldo histórico por fecha.

---

## Integraciones con otros módulos

| Módulo | Relación |
|---|---|
| Inventario | `PurchaseReceipt` genera `StockLedgerEntry` y `StockValuationLayer`. |
| Bancos | `PaymentEntry` (type=pay) paga `PurchaseInvoice` vía `PaymentReference`. |
| Contabilidad | `PurchaseInvoice` genera `gl_entry` (AP, impuestos, gastos). |

---

## Reportería requerida

| Reporte | Descripción |
|---|---|
| Órdenes de compra pendientes | Por proveedor, ítem, estado. |
| Recepciones vs Facturas | Estado GI/IR por orden. |
| Cuentas por pagar (AP) | Saldo pendiente por proveedor. |
| Aging de AP | Vencimientos por bucket temporal. |
| Compras por proveedor | Monto total por período. |
| Compras por ítem | Consumo y precio promedio. |

---

## Casos que debe soportar

- Recepción parcial de una orden.
- Factura sin orden de compra (compra directa).
- Devolución parcial a proveedor (`is_return=True`).
- Devolución total posterior a pago parcial.
- Nota de crédito de proveedor posterior a factura pagada parcialmente.
- Nota de débito de proveedor por ajuste posterior.
- Corrección por UOM equivocada en recepción o factura.
- Corrección por precio equivocado con factura ya contabilizada.
- Proveedor con moneda distinta a la moneda base.
- Un proveedor con múltiples monedas en distintas facturas.
- Anticipo total con factura posterior en período distinto.
- Anticipo parcial aplicado a múltiples facturas del mismo proveedor.
- Descuentos por línea y globales.
- Rebajas comerciales posteriores a la facturación.
- Cargos adicionales (flete, seguro) distribuibles al costo.
- Impuesto fijo y porcentaje coexistiendo en la misma factura.
- Impuestos/cargos aditivos y deductivos en el mismo documento.
- Flete capitalizable prorrateado parcialmente entre ítems inventariables.
- Flete no capitalizable registrado como gasto operativo.
