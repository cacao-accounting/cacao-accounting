# INFORME DE AUDITORÍA FUNCIONAL — ORDER TO CASH (O2C)

**Fecha:** 2026-07-09
**Alcance:** Sales Request → Sales Quotation → Sales Order → Delivery Note → Sales Invoice → Customer Payment
**Módulo:** Ventas
**Versión del código:** commits hasta `487cd6e`

---

## RESUMEN EJECUTIVO

| Categoría | Cantidad |
|-----------|----------|
| Riesgo ALTO | 5 |
| Riesgo MEDIO | 14 |
| Riesgo BAJO | 3 |
| **Total** | **22** |

---

## HALLAZGOS DETALLADOS

### O2C-01 [MEDIO] — SalesRequest submit usa `require_party=False`

**Descripción:** En `ventas_pedido_venta_submit`, `validate_submit_prerequisites` se llama con `require_party=False`. Todos los demás doctypes de ventas usan `require_party=True`.

**Impacto:** Un SalesRequest aprobado sin customer_id propagará documentos downstream sin referencia de tercero válida, rompiendo la trazabilidad de AR.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:500`

---

### O2C-02 [MEDIO] — Secuencia de cancelación inconsistente en SalesInvoice

**Descripción:** En `ventas_factura_venta_cancel`, `revert_relations_for_target` se llama DESPUÉS de `cancel_document`. En otros doctypes se llama ANTES.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:2531-2534`

---

### O2C-03 [ALTO] — DeliveryNote no disminuye `actual_qty` en StockBin

**Descripción:** El handler `ventas_entrega_submit` llama `submit_document` y `_release_reservation_for_delivery_note` pero nunca disminuye `actual_qty`. El inventario contable nunca se reduce al emitir una Nota de Entrega.

**Impacto:** El stock `actual_qty` nunca se reduce cuando se entrega mercancía. El inventario contable no refleja las salidas.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:2131-2151`
- `cacao_accounting/contabilidad/posting.py:2605-2617`

**Caso de prueba:**
1. Crear SO con ítem (qty=10)
2. Entregar qty=5 vía Delivery Note
3. Aprobar DN
4. Verificar StockBin: `reserved_qty` debe ser 5 menos, `actual_qty` también debe ser 5 menos. Actualmente `actual_qty` queda en 10.

---

### O2C-04 [MEDIO] — `_release_reservation_for_delivery_note` no es idempotente

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:186-202, 2131-2151`

---

### O2C-05 [MEDIO] — `_restore_reservation_for_delivery_note` puede sobresuscribir reserved_qty

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:204-218, 2157-2175`

---

### O2C-06 [MEDIO] — Validación de precio en edición bloquea guardar borrador

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:1180-1249, 2390-2420, 2476-2508`

---

### O2C-07 [ALTO] — Factura con `update_inventory=True` no disminuye `actual_qty` ni `reserved_qty`

**Descripción:** Cuando una SalesInvoice se aprueba con `update_inventory=True` y sin DeliveryNote previa, `_create_delivery_note_from_invoice` crea y aprueba una DN pero no llama a `_release_reservation_for_delivery_note`. `reserved_qty` no se reduce ni `actual_qty` disminuye.

**Impacto:** El ledger de inventario queda permanentemente fuera de sincronía con el stock físico.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:1115-1177`

**Caso de prueba:**
1. Crear SO con ítem qty=10, reserva exitosa
2. Crear Sales Invoice con `update_inventory=True`, vincular desde SO
3. Aprobar factura
4. Verificar StockBin: `actual_qty` = 10 (debería ser 9 después de 1 unidad entregada). `reserved_qty` = 10 (debería ser 9).

---

### O2C-08 [ALTO] — Cancelación de Invoice no restaura inventario cuando `update_inventory=True`

**Descripción:** `ventas_factura_venta_cancel` llama `cancel_document(dn)` cuando existe delivery_note_id, pero no llama a `_restore_reservation_for_delivery_note(dn)` ni aumenta `actual_qty`.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:2511-2541`

---

### O2C-09 [MEDIO] — SalesQuotation cancel no verifica relaciones descendientes activas

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:1808-1824` vs `1851-1871`

---

### O2C-10 [BAJO] — `_handle_sales_order_new_post` retorna None en error

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:1296-1329`

---

### O2C-11 [MEDIO] — Edición de SalesOrder/SalesRequest sin auditoría

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:807-824, 827-844`

---

### O2C-12 — BAJO — Inconsistencia de naming en parámetros

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:827, 807`

---

### O2C-13 — MEDIO — `create_document_relation` no valida docstatus de origen

**Evidencia:**
- `cacao_accounting/document_flow/service.py:1200-1264`
- `cacao_accounting/ventas/__init__.py:933-961`

---

### O2C-14 — MEDIO — `validate_submit_prerequisites` no valida rate > 0, amount > 0

**Evidencia:**
- `cacao_accounting/document_flow/validation.py:7-34`

---

### O2C-15 — MEDIO-BAJO — `is_return`/`reversal_of` no protegidos en edición de crédito/debito

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:2390-2421`

---

### O2C-16 [ALTO] — `stock_value` nunca se actualiza en movimientos O2C

**Descripción:** StockBin.stock_value se inicializa en 0 y nunca se actualiza en el flujo de ventas. La valoración del inventario en reportes siempre es 0.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:125-218`

**Caso de prueba:**
1. Aprobar una DeliveryNote
2. Verificar `stock_value` en StockBin — nunca se redujo por el costo de los ítems

---

### O2C-17 — MEDIO — DeliveryNote `is_return` sin lógica de reversión real

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:1860-1928`
- `cacao_accounting/database/__init__.py:1459-1491`

---

### O2C-18 — ALTO — Nota de Crédito/Débito: `reversal_of` no validado

**Descripción:** Al crear notas de crédito/débito, `reversal_of` se establece desde el formulario pero NO se valida que (1) la factura referenciada exista, (2) esté aprobada (docstatus=1), (3) pertenezca al mismo cliente/compañía.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:2229-2271`

**Caso de prueba:**
1. Crear nota de crédito vía POST con un `from_invoice_id` inválido
2. Debe rechazar con error de validación

---

### O2C-20 — ALTO — Sin `SELECT...FOR UPDATE` en reserva de stock (concurrencia)

**Descripción:** `_validate_and_reserve_stock_for_sales_order` lee y actualiza StockBin sin `with_for_update()`. Bajo carga concurrente, dos órdenes pueden reservar el mismo stock.

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:144-168`

**Caso de prueba:**
1. Stock disponible = 10 unidades
2. Dos SOs simultáneas solicitando 6 unidades cada una
3. Solo una debe prosperar; la otra debe fallar con "stock insuficiente"

---

### O2C-21 — BAJO: `_form_decimal` acoplada a `request.form`

**Evidencia:**
- `cacao_accounting/ventas/__init__.py:919-930`

---

### O2C-22 — MEDIO: `validate_submit_prerequisites` no valida almacén para ítems de stock

**Evidencia:**
- `cacao_accounting/document_flow/validation.py:7-34`

---

### O2C-28 — MEDIO: `delivered_qty`/`billed_qty` no inicializados en 0

**Evidencia:**
- `cacao_accounting/database/__init__.py:1455-1456`
- `cacao_accounting/ventas/__init__.py:963-990`

---

## MATRIZ DE PRIORIDADES

| Prioridad | Hallazgos |
|-----------|-----------|
| **ALTA** | O2C-03, O2C-07, O2C-08, O2C-16, O2C-18, O2C-20 |
| **MEDIA** | O2C-01, O2C-02, O2C-04, O2C-05, O2C-06, O2C-09, O2C-11, O2C-13, O2C-14, O2C-15, O2C-17, O2C-22, O2C-28 |
| **BAJA** | O2C-10, O2C-12, O2C-21 |