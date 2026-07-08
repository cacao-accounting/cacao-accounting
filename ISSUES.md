# INFORME DE AUDITORÍA FUNCIONAL ERP
## Cacao Accounting — Revisión de Flujos de Trabajo

**Fecha:** 2026-07-08
**Alcance:** S2P, O2C, R2R, Tesorería, Inventario
**Auditor:** Consultor Funcional ERP

---

## 1. SOURCE TO PAY (S2P) — Compras

### S2P-01 [Alta]: Sin prevención de sobre-recepción contra OC ✓
**Estado:** CORREGIDO — Commit `209feff`
**Descripción:** Al crear Recepción desde OC, no se validaba que `cantidad_recibida_acumulada <= cantidad_ordenada`.
**Corrección aplicada:**
- Se agregó `_validate_receipt_quantities_against_po()` que valida en submit que `consumed_qty_for_source(PO) <= PO.qty` para cada línea vinculada.
- Se corrigió `_handle_purchase_receipt_edit_post` para eliminar `DocumentRelation` viejas antes de recrear ítems, evitando doble conteo en ediciones.
- `compras_recepcion_submit` ahora captura `ValueError` además de `PostingError`.
**Caso de prueba:** Crear OC por 10 uds. Recibir 10 (éxito). Recibir 1 más (debe rechazar).

### S2P-02 [Alta]: Sin prevención de sobre-facturación contra recepción ✓
**Estado:** CORREGIDO — Commit `f920176`
**Descripción:** No se valida que `cantidad_facturada_acumulada <= cantidad_recibida` al crear Factura desde Recepción (3-way match).
**Corrección aplicada:**
- Se agregó `_validate_invoice_quantities_against_receipt()` que valida en submit que `consumed_qty_for_source(Receipt) <= Receipt.qty` para cada línea vinculada.
- Se corrigió `_handle_purchase_invoice_edit_post` para eliminar `DocumentRelation` viejas antes de recrear ítems, evitando doble conteo en ediciones.
- `compras_factura_compra_submit` ahora captura `(PostingError, ValueError, DocumentFlowError)` en lugar de solo `PostingError`.
**Caso de prueba:** OC 10 uds, Recepción 10 uds. Facturar 10 (éxito). Facturar 1 más (debe rechazar).

### S2P-03 [Alta]: Sin prevención de pagos duplicados o en exceso
**Estado:** REQUIERE MÁS REVISIÓN — atender después
**Descripción:** No se valida `sum(payments) <= outstanding_amount` de la factura. Sin bloqueo de concurrencia (`SELECT FOR UPDATE`) al leer saldo pendiente.
**Impacto:** Pagos duplicados o en exceso con pérdida financiera directa.
**Recomendación:** Validar `paid_amount <= outstanding_amount` antes de crear `PaymentReference`. Implementar `SELECT FOR UPDATE` en la lectura de saldo.
**Caso de prueba:** Factura $1,000. Pago 1 $1,000 (éxito). Pago 2 $500 (debe fallar).
**Nota:** Las validaciones contra sobre-pago ya existen (8 capas de validación en `bancos/__init__.py` y `document_flow/service.py`). El riesgo real es la condición de carrera (TOCTOU) por falta de `SELECT FOR UPDATE`, pero es bajo en uso manual típico.

### S2P-04 [Alta]: Cancelación de OC con documentos descendientes activos ✓
**Estado:** CORREGIDO — Commit `22cfa69f`
**Descripción:** Se puede cancelar una OC aunque tenga Recepciones o Facturas activas. Las relaciones se marcan "reverted" pero los hijos siguen activos.
**Impacto:** Documentos huérfanos, inventario revertido pero factura por pagar permanece.
**Recomendación:** Verificar que no existan Recepciones/Facturas con `docstatus=1` vinculadas antes de cancelar. Bloquear anular si hay decendientes que afecter ledger, verificar misma logica para orden de venta.
**Caso de prueba:** Crear OC, Recepción contra OC. Cancelar OC (debe fallar).
**Corrección aplicada:**
- Nueva función `has_active_source_relations()` en `document_flow/repository.py` que verifica si un documento tiene hijos activos no cancelados.
- `compras_orden_compra_cancel()` ahora valida hijos activos antes de cancelar y aborta con mensaje flash si existen Recepciones/Facturas activas.
- `ventas_orden_venta_cancel()` aplica la misma validación para Notas de Entrega/Facturas de Venta activas.

### S2P-05 [Alta]: `PurchaseReconciliationError` causa error 500 no manejado ✓
**Estado:** CORREGIDO — Commit `f920176`
**Descripción:** `_record_purchase_reconciliation` lanza `PurchaseReconciliationError` (hereda de `ValueError`), pero `compras_factura_compra_submit` solo captura `PostingError`.
**Corrección aplicada:**
- `compras_factura_compra_submit` ahora captura `(PostingError, ValueError, DocumentFlowError)`, cubriendo `PurchaseReconciliationError` que hereda de `ValueError`.
- El error se muestra como mensaje flash `danger` en lugar de crash 500.
**Caso de prueba:** OC ítem X a $10, Recibir, Facturar a $12 con tolerancia 0%. Submit → debe mostrar error amigable, no 500.

### S2P-06 [Media]: Validaciones pre-submit insuficientes
**Descripción:** Los endpoints `submit` solo verifican `docstatus != 0`. No validan que el documento tenga líneas, cantidades positivas, proveedor, compañía, fecha.
**Impacto:** Se pueden aprobar documentos vacíos o inválidos.
**Recomendación:** Validar al menos una línea con `qty > 0` y campos obligatorios del header.
**Caso de prueba:** Enviar OC sin líneas (debe rechazar).

### S2P-07 [Media]: Anticipos no reconciliados contra facturas
**Descripción:** Pagos anticipados desde OC usan `supplier_advance_account_id`. Al pagar la factura posterior, no hay neteo del anticipo contra la cuenta por pagar.
**Impacto:** El anticipo queda permanentemente en cuenta de anticipos, sobreestimando activos y pasivos.
**Recomendación:** Agregar tanto en la configuración global de coompras y ventas una opción "Aplicar automaticamente anticipos a facturas de la misma OCImplementar settlement de anticipos: Dr. Payable / Cr. Advance al pagar factura con anticipo.
**Caso de prueba:** OC $1,000. Anticipo $500. Factura $1,000. Pago $500. Verificar cuenta de anticipo en cero.

### S2P-08 [Media]: Flags de proveedor no validados
**Descripción:** `allow_purchase_invoice_without_order` y `allow_purchase_invoice_without_receipt` existen en el formulario de proveedor pero no se validan al crear facturas.
**Impacto:** Configuración existe en UI pero no se respeta.
**Recomendación:** Validar estos flags en la creación de factura de compra.
**Caso de prueba:** Proveedor con `allow_invoice_without_order=False`. Crear factura sin OC (debe rechazar).

### S2P-09 [Media]: Multimoneda no implementada en compras
**Descripción:** `transaction_currency`, `exchange_rate` y montos base en OC/Recepción/Factura siempre se establecen como 1:1.
**Impacto:** Transacciones en moneda extranjera se registran incorrectamente en contabilidad.
**Recomendación:** Agregar selección de moneda en formularios y calcular `base_total = total * exchange_rate`.
**Caso de prueba:** Empresa en USD. Crear OC en EUR con tasa 1.10. Verificar `base_total = total * 1.10`.

---

## 2. ORDER TO CASH (O2C) — Ventas

### O2C-01 [Alta]: COGS no se genera al facturar (feature request) ✓
**Estado:** CORREGIDO — Commit `1e6fced`
**Descripción:** Actualmente el COGS se genera al crear la Nota de Entrega (Delivery Note). Si se requiere facturar antes de entregar, no hay COGS asociado. Se propone agregar una bandera booleana `update_inventory` en la Factura de Venta.
**Impacto:** Sin la bandera, empresas que facturan antes de entregar no pueden generar COGS simultáneo.
**Recomendación:** Agregar campo booleano `update_inventory` (default `False`) en `SalesInvoice`. Si está activo, `post_sales_invoice` genera asiento Dr. COGS / Cr. Inventory calculando el costo desde `StockValuationLayer`. Si hay Delivery Note previa, la bandera debe omitirse para no duplicar.
**Caso de prueba:** Factura sin DN y `update_inventory=True`: GL con Dr. COGS $100 / Cr. Inventory $100. Factura ya entregada con `update_inventory=True`: no duplicar COGS.
**Corrección aplicada:**
- Campo `update_inventory` (Boolean) en `SalesInvoice`.
- `_save_sales_invoice_items()` ahora guarda `warehouse` por línea.
- `ventas_factura_venta_submit()` auto-crea y aprueba una Delivery Note cuando `update_inventory=True` y no hay DN previa, usando la bodega predeterminada del ítem.
- `ventas_factura_venta_cancel()` cancela la DN vinculada cuando `update_inventory=True`.
- Flash message: "Se ha creado y aprobado la Nota de Entrega {doc_no} asociada a esta factura."
- Checkbox en formulario de factura de venta (visible cuando no hay DN vinculada).

### O2C-02 [Alta]: Sin validación de precio entre Orden de Venta y Factura ✓
**Estado:** CORREGIDO — Commit `0ab8b9d`
**Descripción:** La factura puede usar precios diferentes a la SO sin advertencia.
**Impacto:** Riesgo de facturar a precio incorrecto (mayor o menor al autorizado).
**Recomendación:** Agregar validación de tolerancia de precio configurable. Si el precio de factura difiere de la SO en más del X%, bloquear o requerir aprobación.
**Caso de prueba:** SO: $100/unidad. Facturar a $80/unidad (debe advertir o rechazar según tolerancia).
**Corrección aplicada:**
- Modelo `SalesMatchingConfig` por compañía: tolerancia de precio (porcentaje/absoluto), matching type (3-way), allow_price_difference, require_sales_order.
- Admin UI en `/settings/sales-matching` para configurar tolerancias por compañía.
- `_validate_invoice_prices_against_source()` en `ventas/__init__.py` valida precios al aprobar/editar factura.
- Default: tolerancia 0%, rechazo estricto de diferencias.
- Si `allow_price_difference=True`: flash warning pero permite continuar.

### O2C-03 [Alta]: Sin reserva de inventario al confirmar Orden de Venta
**Descripción:** La SO no reserva existencias. No hay campo `reserved_qty` en `StockBin`.
**Impacto:** Se puede sobregirar inventario (overselling): aceptar más órdenes de las que se pueden entregar.
**Recomendación:** Implementar reserva de inventario al aprobar SO: decrementar `actual_qty` e incrementar `reserved_qty` en `StockBin`. Liberar al cancelar SO o al crear Delivery Note.
**Caso de prueba:** Stock: 10 uds. SO-1: 10 uds (reserva 10). SO-2: 5 uds (debe fallar).

### O2C-04 [Media]: Notas de Crédito y Devolución — dos transacciones separadas (diseño correcto)
**Descripción:** El diseño actual separa correctamente la NC (ajuste financiero: descuentos, diferencias de precio) de la Devolución física (movimiento de inventario vía `stock_entry`). Esto es correcto.
**Recomendación:** No requiere cambio. Solo documentar explícitamente en la UI que:
- Nota de Crédito = ajuste financiero (no afecta inventario)
- Devolución = movimiento físico de inventario (requiere stock entry aparte)

### O2C-05 [Alta]: Validaciones pre-submit insuficientes en ventas
**Descripción:** Ídem S2P-06 para documentos de venta.
**Recomendación:** Ídem S2P-06.

---

## 3. RECORD TO REPORT (R2R) — Contabilidad

### R2R-01 [Alta]: Periodos contables no validados al postear
**Descripción:** `validate_period` no se llama consistentemente en todos los puntos de posting.
**Impacto:** Transacciones en períodos cerrados comprometen la integridad de los estados financieros.
**Recomendación:** Centralizar la validación de período abierto en un decorador o middleware que se ejecute antes de cualquier posting.
**Caso de prueba:** Cerrar período Ene-2026. Postear factura con fecha 15-Ene-2026 (debe rechazar).

### R2R-02 [Alta]: Asientos GL sin verificación de balance débito/crédito
**Descripción:** No hay validación explícita de `sum(debits) == sum(credits)` antes de persistir un lote de asientos GL.
**Impacto:** Libro mayor desbalanceado si una regla de mapeo falla.
**Recomendación:** Agregar validación en el motor de posting: `abs(total_debits - total_credits) < rounding_tolerance`, con rechazo si no se cumple.
**Caso de prueba:** Manipular regla de mapeo para que genere débitos sin crédito. Postear (debe fallar).

### R2R-03 [Media]: Trazabilidad incompleta entre documentos operativos y GL
**Descripción:** `GLEntry` tiene `voucher_type` y `voucher_id`, pero algunos postings no establecen estos campos correctamente o usan convenciones inconsistentes.
**Impacto:** Dificultad para auditar desde un asiento GL al documento origen y viceversa.
**Recomendación:** Estandarizar `voucher_type` en todas las fuentes de posting y verificar que cada `GLEntry` tenga ambos campos poblados.
**Caso de prueba:** Consultar `GLEntry` filtrando por `voucher_type='purchase_receipt'`. Verificar que todas las recepciones posteadas aparecen.

### R2R-04 [Media]: Cierre mensual no bloquea posting efectivamente
**Descripción:** `PeriodCloseRun` existe pero no integra todos los pasos de cierre ni bloquea posting en períodos cerrados.
**Impacto:** Cierres contables manuales y riesgo de omitir pasos.
**Recomendación:** Completar el asistente de cierre mensual como orquestador: recurrentes → revaluación → ajustes → bloqueo de período.
**Caso de prueba:** Ejecutar cierre mensual. Verificar que todos los pasos se ejecutan y el período queda bloqueado.

---

## 4. TESORERÍA (Cash Management)

### CAS-01 [Alta]: Sin saldo de cuenta bancaria en tiempo real
**Descripción:** `BankAccount` no tiene campo `current_balance`. El saldo debe derivarse consultando `GLEntry`.
**Impacto:** Sin visibilidad de posición de efectivo. No se previenen pagos que exceden el saldo disponible.
**Recomendación:** Agregar `current_balance` actualizado automáticamente en cada posting de pago/cobro.
**Caso de prueba:** Cuenta con saldo 0. Recibir $5,000. Verificar `current_balance = $5,000`.

### CAS-02 [Alta]: `exchange_rate` hardcodeado a `None` en pagos
**Descripción:** `_create_payment_entry` en `bancos/__init__.py` asigna `exchange_rate=None`.
**Impacto:** Diferencias cambiarias no registradas en pagos multi-moneda.
**Recomendación:** Auto-poblar `exchange_rate` desde `ExchangeRate` usando moneda de cuenta bancaria vs moneda base de compañía.
**Caso de prueba:** Cuenta en EUR, empresa en USD, tasa 1.10. Pagar 1,000 EUR. Verificar `exchange_rate = 1.10`.

### CAS-03 [Alta]: Condición de carrera en saldo pendiente de facturas
**Descripción:** `compute_outstanding_amount` lee `PaymentReference.allocated_amount` sin bloqueo de fila.
**Impacto:** Dos pagos concurrentes por la misma factura pueden sobrescribir el saldo (doble pago/cobro).
**Recomendación:** Usar `SELECT FOR UPDATE` en la transacción que lee outstanding_amount.
**Caso de prueba:** Factura $1,000. Dos cobros simultáneos de $1,000. Solo uno debe prosperar.

### CAS-04 [Baja]: `BankTransaction.payment_entry_id` nunca se puebla
**Descripción:** El campo `payment_entry_id` en `BankTransaction` existe en el modelo pero nunca se asigna durante la reconciliación.
**Recomendación:** Poblar el campo al reconciliar contra un payment_entry, o eliminar la columna.

---

## 5. INVENTARIO (Inventory Management)

### INV-01 [Alta]: Diferencia de valoración en traslados entre bodegas
**Descripción:** En `_create_movement_for_purpose` para `material_transfer`, la salida de bodega origen consume capas FIFO/MA (costo real), pero la entrada a bodega destino usa la tasa del usuario (no el costo real de salida).
**Impacto:** Valor de inventario en bodega destino incorrecto. El valor total del inventario no se conserva.
**Recomendación:** Calcular el costo real de salida primero, luego usar ese mismo costo para la entrada en destino.
**Caso de prueba:** Bodega A: 10 uds a $100. Transferir 5 uds a Bodega B. Verificar B: qty=5, value=$500.

### INV-02 [Alta]: `allow_negative_stock` no se valida al postear
**Descripción:** El campo `Item.allow_negative_stock` existe pero nunca se consulta en `_create_stock_movement`.
**Impacto:** Ítems marcados como "no permitir stock negativo" pueden quedar en negativo.
**Recomendación:** Agregar validación: si `qty_after < 0` y `item.allow_negative_stock == False`, rechazar.
**Caso de prueba:** Item con `allow_negative_stock=False`, stock 0. Emitir 10 (debe fallar).

### INV-03 [Media]: Bodega no validada contra compañía seleccionada
**Descripción:** `from_warehouse` y `to_warehouse` no se validan contra la compañía del documento al crear stock entry.
**Impacto:** Se pueden usar bodegas de otra compañía, violando aislamiento multi-compañía.
**Recomendación:** Validar que cada bodega pertenezca a la compañía del documento.
**Caso de prueba:** Bodega A pertenece a Compañía X. Stock entry para Compañía Y con bodega A (debe rechazar).

### INV-04 [Media]: Recepción manual usa cuenta puente incorrectamente
**Descripción:** `_get_offset_account_for_line` para `material_receipt` siempre usa cuenta puente (bridge). Si la entrada es manual (sin OC/Recepción de compra), el crédito debe ir a cuenta de ajuste.
**Impacto:** La cuenta puente queda con saldo que nunca se concilia.
**Recomendación:** Usar `stock_adjustment_account` para entradas de stock sin origen documental.
**Caso de prueba:** Entrada de stock manual. Verificar GL: Dr. Inventory / Cr. Adjustment (no Bridge).

### INV-05 [Media]: Edición de borrador huérfana relaciones documentales
**Descripción:** `_delete_and_resave_stock_entry_items` borra todos los `StockEntryItem` y los recrea. Las `DocumentRelation` viejas quedan huérfanas.
**Recomendación:** Limpiar relaciones viejas antes de recrear ítems.
**Caso de prueba:** Stock entry desde purchase receipt (2 líneas). Editar draft, agregar ítem nuevo. Verificar relaciones viejas limpias.

### INV-06 [Media]: Sin protección contra concurrencia en inventario
**Descripción:** `_stock_qty_after` lee `SUM(StockLedgerEntry.qty_change)` sin bloqueo.
**Impacto:** Inconsistencia entre StockBin y StockLedgerEntry bajo carga concurrente.
**Recomendación:** Usar `SELECT FOR UPDATE` sobre `StockBin` al leer saldo actual.
**Caso de prueba:** Stock: 10 uds. Dos emisiones simultáneas de 6 uds. Solo una debe prosperar.

### INV-07 [Media]: `qty_in_base_uom` en reconciliación salta conversión UOM
**Descripción:** `_save_stock_reconciliation_items` asigna `qty_in_base_uom = abs(qty_difference)` sin convertir a UOM base.
**Impacto:** StockLedgerEntry registra cantidad en UOM equivocada.
**Recomendación:** Convertir qty_difference a UOM base antes de asignar.
**Caso de prueba:** UOM base=kg. Reconciliación: count=10 lb, current=0 lb. `qty_in_base_uom` debe ser ~4.536 kg, no 10.

---

## 6. CROSS-CUTTING

### CROSS-01 [Media]: Sin logging de auditoría para ediciones en borrador
**Descripción:** Solo submit y cancel tienen registro en `AuditLog`. Las ediciones de draft no generan entrada.
**Recomendación:** Agregar `log_update` en todas las rutas `edit` de documentos transaccionales.
**Caso de prueba:** Editar borrador de OC. Verificar entrada en `AuditLog` con acción "updated".

### CROSS-02 [Baja]: Configuraciones duplicadas en `setup.cfg` y `pyproject.toml`
**Descripción:** Ambos archivos definen configuraciones para flake8, pytest, coverage que pueden solaparse.
**Recomendación:** Unificar toda configuración en `pyproject.toml` y eliminar duplicados de `setup.cfg`.

---

## RESUMEN DE PRIORIDADES

| Prioridad | Hallazgos |
|-----------|-----------|
| **Alta** | ~~S2P-01~~, ~~S2P-02~~, S2P-03*, ~~S2P-04~~, ~~S2P-05~~, ~~O2C-01~~, ~~O2C-02~~, O2C-03, O2C-05, R2R-01, R2R-02, CAS-01 al CAS-03, INV-01, INV-02 |
| **Media** | S2P-06 al S2P-09, R2R-03, R2R-04, INV-03 al INV-07, CROSS-01 |
| **Baja** | CAS-04, CROSS-02 |

\* S2P-03: Las validaciones contra sobre-pago ya existen. Solo falta `SELECT FOR UPDATE` para concurrencia. Requiere más revisión.

---

## PLAN DE ACCIÓN RECOMENDADO

| Semana | Hallazgos | Enfoque |
|--------|-----------|---------|
| **1-2** | ~~S2P-01~~, ~~S2P-02~~, ~~S2P-05~~, S2P-03 (pagos duplicados — revisión futura), ~~S2P-04 (cancelaciones)~~ | Validaciones críticas de integridad |
| **2-3** | ~~O2C-01 (COGS)~~, ~~O2C-02 (precios)~~, O2C-03 (reserva inventario), O2C-05 (validaciones pre-submit) | O2C y controles de ventas |
| **3-4** | R2R-01 (períodos), R2R-02 (balanceo GL), CAS-01 (saldo bancario), CAS-02 (exchange rate), CAS-03 (concurrencia) | Contabilidad y tesorería |
| **4-5** | INV-01 (traslados), INV-02 (negative stock), S2P-07 (anticipos), resto hallazgos medios | Inventario y anticipos |
| **5-6** | S2P-09 (multimoneda), S2P-08 (flags proveedor), INV-04 (cuenta puente), CROSS-01 (auditoría) | Multimoneda y cross-cutting |
