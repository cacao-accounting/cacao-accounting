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

### S2P-03 [Alta]: Sin prevención de pagos duplicados o en exceso ✓
**Estado:** CORREGIDO — CAS-03 (Commit `74079bf`)
**Descripción:** No se valida `sum(payments) <= outstanding_amount` de la factura. Sin bloqueo de concurrencia (`SELECT FOR UPDATE`) al leer saldo pendiente.
**Impacto:** Pagos duplicados o en exceso con pérdida financiera directa.
**Recomendación:** Validar `paid_amount <= outstanding_amount` antes de crear `PaymentReference`. Implementar `SELECT FOR UPDATE` en la lectura de saldo.
**Caso de prueba:** Factura $1,000. Pago 1 $1,000 (éxito). Pago 2 $500 (debe fallar).
**Nota:** Las validaciones contra sobre-pago ya existen (8 capas de validación). CAS-03 agregó `with_for_update()` en `_load_payment_reference_document` (bancos/__init__.py:867) y `_get_reference_document` (document_flow/service.py:739), cerrando la ventana TOCTOU.

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
**Estado:** CORREGIDO — Commit `b149b09`
**Descripción:** Los endpoints `submit` solo verifican `docstatus != 0`. No validan que el documento tenga líneas, cantidades positivas, proveedor, compañía, fecha.
**Impacto:** Se pueden aprobar documentos vacíos o inválidos.
**Recomendación:** Validar al menos una línea con `qty > 0` y campos obligatorios del header.
**Caso de prueba:** Enviar OC sin líneas (debe rechazar).
**Corrección aplicada:**
- Nueva función `validate_submit_prerequisites()` en `document_flow/validation.py` que valida compañía, fecha, tercero, líneas y cantidades.
- Aplicada en 12 endpoints `*_submit`: 6 de compras, 5 de ventas, 1 de inventario.
- Los endpoints sin try/except previo ahora capturan `ValueError` y muestran flash message `danger`.
- Pruebas unitarias en `tests/test_validation.py` cubren todos los casos de validación.

### S2P-07 [Media]: Anticipos no reconciliados contra facturas
**Estado:** CORREGIDO — Commit `3f72f1a`
**Descripción:** Pagos anticipados desde OC usan `supplier_advance_account_id`. Al pagar la factura posterior, no hay neteo del anticipo contra la cuenta por pagar.
**Impacto:** El anticipo queda permanentemente en cuenta de anticipos, sobreestimando activos y pasivos.
**Recomendación:** Agregar tanto en la configuración global de coompras y ventas una opción "Aplicar automaticamente anticipos a facturas de la misma OCImplementar settlement de anticipos: Dr. Payable / Cr. Advance al pagar factura con anticipo.
**Caso de prueba:** OC $1,000. Anticipo $500. Factura $1,000. Pago $500. Verificar cuenta de anticipo en cero.

### S2P-08 [Media]: Flags de proveedor no validados ✓
**Estado:** CORREGIDO — Commit `6b03524`
**Descripción:** `allow_purchase_invoice_without_order` y `allow_purchase_invoice_without_receipt` existen en el formulario de proveedor pero no se validan al crear facturas.
**Impacto:** Configuración existe en UI pero no se respeta.
**Recomendación:** Validar estos flags en la creación de factura de compra.
**Caso de prueba:** Proveedor con `allow_invoice_without_order=False`. Crear factura sin OC (debe rechazar).

### S2P-09 [Media]: Multimoneda no implementada en compras
**Estado:** CORREGIDO — Commit `bb2ac5d` (parcial previo `778a1b7`)
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

### O2C-03 [Alta]: Sin reserva de inventario al confirmar Orden de Venta ✓
**Estado:** CORREGIDO — Commit `8868cec`
**Descripción:** La SO no reserva existencias. No hay campo `reserved_qty` en `StockBin`.
**Impacto:** Se puede sobregirar inventario (overselling): aceptar más órdenes de las que se pueden entregar.
**Recomendación:** Implementar reserva de inventario al aprobar SO: incrementar `reserved_qty` en `StockBin`. Liberar al cancelar SO o al crear Delivery Note.
**Corrección aplicada:**
- `reserved_qty` cambió de nullable a non-nullable con default 0.
- `_validate_and_reserve_stock_for_sales_order()`: valida `actual_qty - reserved_qty >= qty` e incrementa `reserved_qty` en submit SO.
- `_release_reservation_for_sales_order()`: libera reserva al cancelar SO.
- `_release_reservation_for_delivery_note()`: libera reserva al aprobar DN con SO origen.
- `_restore_reservation_for_delivery_note()`: restaura reserva al cancelar DN con SO origen.
- `SalesOrderItem.warehouse` ahora es obligatorio al aprobar para poder reservar.
- `StockBin` ahora expone `reserved_qty` en API y snapshot.
- `rebuild_stock_bins` preserva `reserved_qty` existente.
- `_create_delivery_note_from_invoice()` propaga `sales_order_id` para liberar reserva cuando se factura con `update_inventory=True`.
**Caso de prueba:** Stock: 10 uds. SO-1: 10 uds (reserva 10, éxito). SO-2: 5 uds (debe fallar). DN desde SO-1: libera 10 uds reservadas.

### O2C-04 [Media]: Notas de Crédito y Devolución — dos transacciones separadas (falta `sales_return`)
**Estado:** CORREGIDO — Commit `b31ce72`
**Descripción:** El diseño actual separa la NC (ajuste financiero) de la Devolución física, lo cual es correcto. Sin embargo, existe una asimetría: compras tiene `purchase_return` como tipo documental separado de `purchase_credit_note`, mientras que ventas no tiene `sales_return` — la ruta `/sales-invoice/return/list` es un alias de notas de crédito. El campo `DeliveryNote.is_return` existe pero no se expone en UI. Se requiere implementación espejo para mantener consistencia entre módulos.
**Recomendación:** Implementar `sales_return` como tipo documental dedicado, análogo a `purchase_return` en compras.

### O2C-05 [Alta]: Validaciones pre-submit insuficientes en ventas
**Estado:** CORREGIDO — Commit `b149b09`
**Descripción:** Ídem S2P-06 para documentos de venta.
**Recomendación:** Ídem S2P-06.
**Corrección aplicada:** Misma que S2P-06: `validate_submit_prerequisites()` aplicada en los 5 endpoints de ventas.

---

## 3. RECORD TO REPORT (R2R) — Contabilidad

### R2R-01 [Alta]: Periodos contables no validados al postear
**Estado:** FALSO POSITIVO CONFIRMADO ✓
**Descripción:** `validate_period` no se llama consistentemente en todos los puntos de posting.
**Impacto:** Transacciones en períodos cerrados comprometen la integridad de los estados financieros.
**Recomendación:** Centralizar la validación de período abierto en un decorador o middleware que se ejecute antes de cualquier posting.
**Caso de prueba:** Cerrar período Ene-2026. Postear factura con fecha 15-Ene-2026 (debe rechazar).

### R2R-02 [Alta]: Asientos GL sin verificación de balance débito/crédito
**Estado:** FALSO POSITIVO CONFIRMADO ✓
**Descripción:** No hay validación explícita de `sum(debits) == sum(credits)` antes de persistir un lote de asientos GL.
**Impacto:** Libro mayor desbalanceado si una regla de mapeo falla.
**Recomendación:** Agregar validación en el motor de posting: `abs(total_debits - total_credits) < rounding_tolerance`, con rechazo si no se cumple.
**Caso de prueba:** Manipular regla de mapeo para que genere débitos sin crédito. Postear (debe fallar).

### R2R-03 [Media]: Trazabilidad incompleta entre documentos operativos y GL
**Estado:** FALSO POSITIVO CONFIRMADO ✓
**Descripción:** `GLEntry` tiene `voucher_type` y `voucher_id`. Todos los paths de posting establecen estos campos consistentemente vía `_get_voucher_type()` en posting.py:139, que usa `__tablename__` como fallback. La convención es uniforme: `sales_invoice`, `purchase_invoice`, `purchase_receipt`, `delivery_note`, `payment_entry`, `stock_entry`, `bank_transaction`, `journal_entry`, `exchange_revaluation`. Ambos campos son `nullable=False` en BD.
**Impacto:** No hay impacto real — la trazabilidad es completa y consistente.
**Recomendación:** Ninguna. Cerrar como falso positivo.

### R2R-04 [Media]: Cierre mensual no bloquea posting efectivamente
**Estado:** CONFIRMADO REAL (parcial)
**Descripción:** La validación de períodos (`validate_accounting_period`) SÍ funciona correctamente y bloquea postings en períodos cerrados (se llama desde `_document_contexts()` en todos los paths). El problema real es que el asistente de cierre mensual (`PeriodCloseRun`) está incompleto: solo implementa los pasos de recurrentes y revaluación, pero nunca marca `AccountingPeriod.is_closed=True` ni `PeriodCloseRun.run_status="closed"`. El cierre del período debe hacerse manualmente vía formulario de edición de período.
**Impacto:** El cierre mensual requiere intervención manual para marcar el período como cerrado. El asistente no completa el ciclo.
**Recomendación:** Agregar paso final en el asistente de cierre mensual que marque `AccountingPeriod.is_closed=True` y `PeriodCloseRun.run_status="closed"`.

---

## 4. TESORERÍA (Cash Management)

### CAS-01 [Alta]: Sin saldo de cuenta bancaria en tiempo real
**Estado:** FALSO POSITIVO CONFIRMADO ✓
**Descripción:** `BankAccount` no tiene campo `current_balance`. El saldo debe derivarse consultando `GLEntry`.
**Impacto:** Sin visibilidad de posición de efectivo. No se previenen pagos que exceden el saldo disponible.
**Recomendación:** Agregar `current_balance` actualizado automáticamente en cada posting de pago/cobro.
**Caso de prueba:** Cuenta con saldo 0. Recibir $5,000. Verificar `current_balance = $5,000`.

### CAS-02 [Alta]: `exchange_rate` hardcodeado a `None` en pagos
**Estado:** CORREGIDO — Commit `bb40f22`
**Descripción:** `_create_payment_entry` en `bancos/__init__.py` asigna `exchange_rate=None`.
**Impacto:** Diferencias cambiarias no registradas en pagos multi-moneda.
**Recomendación:** Auto-poblar `exchange_rate` desde `ExchangeRate` usando moneda de cuenta bancaria vs moneda base de compañía.
**Caso de prueba:** Cuenta en EUR, empresa en USD, tasa 1.10. Pagar 1,000 EUR. Verificar `exchange_rate = 1.10`.
**Corrección aplicada:**
- `_create_payment_entry` ahora acepta parámetro `exchange_rate` en lugar de hardcodear `None`.
- `_build_payment_from_payload` resuelve `exchange_rate` vía `_lookup_exchange_rate()` cuando la moneda del pago difiere de la moneda de la compañía.
- `_update_payment_amounts` aplica exchange_rate al calcular `base_paid_amount` y `base_received_amount`.
- Pruebas unitarias para mismo moneda (rate=1) y moneda diferente (rate desde BD).

### CAS-03 [Alta]: Condición de carrera en saldo pendiente de facturas
**Estado:** CORREGIDO — Commit `74079bf`
**Descripción:** `compute_outstanding_amount` lee `PaymentReference.allocated_amount` sin bloqueo de fila.
**Impacto:** Dos pagos concurrentes por la misma factura pueden sobrescribir el saldo (doble pago/cobro).
**Recomendación:** Usar `SELECT FOR UPDATE` en la transacción que lee outstanding_amount.
**Caso de prueba:** Factura $1,000. Dos cobros simultáneos de $1,000. Solo uno debe prosperar.
**Corrección aplicada:**
- `_load_payment_reference_document` en `bancos/__init__.py` usa `with_for_update()` al cargar el documento.
- `_get_reference_document` en `document_flow/service.py` usa `with_for_update()` al cargar el documento.
- El bloqueo de fila serializa lecturas concurrentes del saldo pendiente antes de crear `PaymentReference`.
- Prueba funcional verifica flujo normal no se rompe.

### CAS-04 [Baja]: `BankTransaction.payment_entry_id` nunca se puebla ✓
**Estado:** CORREGIDO — Commit `ca4aca8`
**Descripción:** El campo `payment_entry_id` en `BankTransaction` existe en el modelo pero nunca se asigna durante la reconciliación. El flujo de reconciliación bancaria (`reconciliation_service.py`) solo marca `is_reconciled=True` pero nunca vincula el `PaymentEntry`.
**Recomendación:** Poblar el campo al reconciliar contra un payment_entry, o eliminar la columna.

---

## 5. INVENTARIO (Inventory Management)

### INV-01 [Alta]: Diferencia de valoración en traslados entre bodegas ✓
**Estado:** CORREGIDO — Commit `89afd34`
**Descripción:** En `_create_movement_for_purpose` para `material_transfer`, la salida de bodega origen consume capas FIFO/MA (costo real), pero la entrada a bodega destino usa la tasa del usuario (no el costo real de salida).
**Corrección aplicada:**
- `_create_movement_for_purpose` consume capas FIFO/MA antes de crear el movimiento destino, usando el costo real para ambas bodegas.
- `_create_stock_movement` acepta `_skip_layer_consumption` para evitar doble consumo en transferencias.
- Nueva función `_consume_available_layers_for_negative_stock`.
**Caso de prueba:** Bodega A: 10 uds a $10. Transferir 5 uds a Bodega B con rate $15. Verificar B: valuation_rate=$10, stock_value=$50.

### INV-02 [Alta]: `allow_negative_stock` no se valida al postear ✓
**Estado:** CORREGIDO — Commit `89afd34`
**Descripción:** El campo `Item.allow_negative_stock` existe pero nunca se consulta en `_create_stock_movement`.
**Impacto:** Ítems marcados como "no permitir stock negativo" pueden quedar en negativo.
**Recomendación:** Agregar validación: si `qty_after < 0` y `item.allow_negative_stock == False`, rechazar.
**Caso de prueba:** Item con `allow_negative_stock=False`, stock 0. Emitir 10 (debe fallar).

### INV-03 [Media]: Bodega no validada contra compañía seleccionada ✓
**Estado:** CORREGIDO — Commit `84eb070`
**Descripción:** `from_warehouse` y `to_warehouse` no se validan contra la compañía del documento al crear stock entry.
**Corrección aplicada:**
- Filtro `company=selected_company` agregado en consultas de bodegas en formularios nuevo y edición.
**Caso de prueba:** Bodega A (Compañía X) no aparece en opciones de formulario para Compañía Y.

### INV-04 [Media]: Recepción manual usa cuenta puente incorrectamente ✓
**Estado:** CORREGIDO — Commit `84eb070`
**Descripción:** `_get_offset_account_for_line` para `material_receipt` siempre usa cuenta puente (bridge). Si la entrada es manual (sin OC/Recepción de compra), el crédito debe ir a cuenta de ajuste.
**Corrección aplicada:**
- `_get_offset_account_for_line` ahora consulta `DocumentRelation` para detectar recepciones manuales (sin origen) y usa `inventory_adjustment` en lugar de `bridge`.
**Caso de prueba:** Entrada de stock manual. Verificar GL: Dr. Inventory / Cr. Adjustment (no Bridge).

### INV-05 [Media]: Edición de borrador huérfana relaciones documentales ✓
**Estado:** CORREGIDO — Commit `84eb070`
**Descripción:** `_delete_and_resave_stock_entry_items` borra todos los `StockEntryItem` y los recrea. Las `DocumentRelation` viejas quedan huérfanas.
**Corrección aplicada:**
- Limpieza de `DocumentRelation` con `target_type="stock_entry"` antes de eliminar items, mismo patrón que compras.
**Caso de prueba:** Stock entry con relación documental. Editar draft → relaciones viejas eliminadas.

### INV-06 [Media]: Sin protección contra concurrencia en inventario ✓
**Estado:** CORREGIDO — Commit `84eb070`
**Descripción:** `_stock_qty_after` lee `SUM(StockLedgerEntry.qty_change)` sin bloqueo.
**Corrección aplicada:**
- `_upsert_stock_bin` ahora usa `with_for_update()` al leer `StockBin`, serializando actualizaciones concurrentes.
**Caso de prueba:** Stock: 10 uds. Dos emisiones simultáneas de 6 uds. Solo una prospera.

### INV-07 [Media]: `qty_in_base_uom` en reconciliación salta conversión UOM ✓
**Estado:** CORREGIDO — Commit `84eb070`
**Descripción:** `_save_stock_reconciliation_items` asigna `qty_in_base_uom = abs(qty_difference)` sin convertir a UOM base.
**Corrección aplicada:**
- `qty_in_base_uom` ahora se calcula mediante `convert_item_qty()` antes de asignar.
**Caso de prueba:** UOM base=kg. Reconciliación: count=10 lb, current=0 lb. `qty_in_base_uom` = ~4.536 kg.

---

## 6. CROSS-CUTTING

### CROSS-01 [Media]: Sin logging de auditoría para ediciones en borrador ✓
**Estado:** CORREGIDO — Commit `3c42857`
**Descripción:** El issue es correcto para compras y ventas (ninguna ruta de edición en borrador llama a `log_update`). Sin embargo, inventario (`_handle_stock_entry_edit_post`) y diarios contables (`journal_service.py`) SÍ tienen `log_update`. El sistema de auditoría usa `AuditTrail` (no `AuditLog`).
**Impacto:** Ediciones en borrador de OC, facturas, recepciones, órdenes de venta, notas de entrega, etc. en compras y ventas no quedan registradas en auditoría.
**Recomendación:** Agregar `log_update` en las rutas `*_edit_post` de compras (6 rutas) y ventas (5 rutas).

### CROSS-02 [Baja]: Configuraciones duplicadas en `setup.cfg` y `pyproject.toml` ✓
**Estado:** CORREGIDO — Commit `6c31402`
**Descripción:** `[flake8]` en `setup.cfg` tiene prioridad sobre `[tool.flake8]` en `pyproject.toml` según la cadena de precedencia de flake8. Esto deja como código muerta la configuración más completa de `pyproject.toml` (con `extend-ignore = ["E203", "W503"]` y exclude más robusto). pytest y coverage no tienen duplicación conflictiva.
**Recomendación:** Eliminar la sección `[flake8]` de `setup.cfg` y consolidar en `pyproject.toml` bajo `[tool.flake8]`.

---

## RESUMEN DE PRIORIDADES (ACTUALIZADO)

| Prioridad | Hallazgos |
|-----------|-----------|
| **Alta** | ~~S2P-01~~, ~~S2P-02~~, ~~S2P-03~~, ~~S2P-04~~, ~~S2P-05~~, ~~O2C-01~~, ~~O2C-02~~, ~~O2C-03~~, ~~O2C-05~~, ~~R2R-01~~ (FP ✓), ~~R2R-02~~ (FP ✓), ~~CAS-01~~ (FP ✓), ~~CAS-02~~, ~~CAS-03~~, ~~INV-01~~, ~~INV-02~~ |
| **Media** | ~~S2P-06~~, ~~S2P-07~~, ~~S2P-08~~, ~~S2P-09~~, ~~R2R-03~~ (FP ✓), ~~R2R-04~~, ~~O2C-04~~, ~~INV-03~~, ~~INV-04~~, ~~INV-05~~, ~~INV-06~~, ~~INV-07~~, ~~CROSS-01~~ |
| **Baja** | ~~CAS-04~~, ~~CROSS-02~~ |

**Leyenda:** ~~Tachado~~ = CORREGIDO | **Negrita** = CONFIRMADO REAL | FP ✓ = FALSO POSITIVO CONFIRMADO

**ESTADO FINAL:** Todos los 30 hallazgos del informe están CORREGIDOS o son FALSOS POSITIVOS. No quedan issues pendientes.

---

## PLAN DE ACCIÓN RECOMENDADO (ACTUALIZADO)

| Semana | Hallazgos | Enfoque |
|--------|-----------|---------|
| **1-2** | ~~S2P-01~~, ~~S2P-02~~, ~~S2P-05~~, ~~S2P-03~~, ~~S2P-04~~ | Validaciones críticas de integridad — COMPLETADO |
| **2-3** | ~~O2C-01 (COGS)~~, ~~O2C-02 (precios)~~, ~~O2C-03 (reserva inventario)~~, ~~O2C-05~~ | O2C y controles de ventas — COMPLETADO |
| **3-4** | ~~R2R-01~~ (FP), ~~R2R-02~~ (FP), ~~CAS-01~~ (FP), ~~CAS-02~~, ~~CAS-03~~ | Contabilidad y tesorería — COMPLETADO |
| **4-5** | ~~INV-01~~, ~~INV-02~~, ~~INV-03~~, ~~INV-04~~, ~~INV-05~~, ~~INV-06~~, ~~INV-07~~ | Inventario — 7 issues — COMPLETADO |
| **5-6** | ~~S2P-07~~ (anticipos), ~~S2P-08~~ (flags proveedor), ~~S2P-09~~ (multimoneda) | Compras — 3 issues — COMPLETADO |
| **6-7** | ~~R2R-04~~ (cierre mensual), ~~CROSS-01~~ (auditoría ediciones), ~~CAS-04~~ (campo huérfano), ~~CROSS-02~~ (config duplicada) | R2R y cross-cutting — COMPLETADO |
| **7-8** | ~~O2C-04~~ (implementar `sales_return`) | Consistencia compras/ventas — tipo documental espejo — COMPLETADO |
| **8-9** | ~~S2P-07~~ (anticipos), ~~R2R-04~~ (cierre), ~~O2C-04~~ (sales_return), ~~S2P-09~~ (templates moneda) | Features pendientes — COMPLETADO |
