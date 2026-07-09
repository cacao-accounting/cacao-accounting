# ISSUES.md — INFORME CONSOLIDADO DE AUDITORÍA FUNCIONAL ERP

**Fecha:** 2026-07-09
**Auditor:** Consultor Funcional ERP (DeepSeek V4)
**Revisor:** MiMo-V2.5 (Auditor Funcional ERP Senior)
**Alcance:** S2P, O2C, R2R, Tesorería, Inventario
**Versión del código auditado:** commits hasta `487cd6e`

---

## VERIFICACIÓN INDEPENDIENTE (2026-07-09)

| ID | Veredicto | Confianza | GitHub |
|----|-----------|-----------|--------|
| S2P-01 | **ISSUE VERIFICADO** | Alto | [#119](https://github.com/cacao-accounting/cacao-accounting/issues/119) |
| S2P-02 | **ISSUE VERIFICADO** | Alto | [#120](https://github.com/cacao-accounting/cacao-accounting/issues/120) |
| S2P-04 | **ISSUE VERIFICADO** | Muy Alto | [#121](https://github.com/cacao-accounting/cacao-accounting/issues/121) |
| S2P-07 | **ISSUE VERIFICADO** | Muy Alto | [#122](https://github.com/cacao-accounting/cacao-accounting/issues/122) |
| S2P-09 | **ISSUE VERIFICADO** | Alto | [#138](https://github.com/cacao-accounting/cacao-accounting/issues/138) |
| S2P-11 | **ISSUE VERIFICADO** | Alto | [#123](https://github.com/cacao-accounting/cacao-accounting/issues/123) |
| S2P-12 | **ISSUE VERIFICADO** | Alto | [#124](https://github.com/cacao-accounting/cacao-accounting/issues/124) |
| O2C-03 | **FALSO POSITIVO** | Muy Alto | — |
| O2C-04 | **ISSUE VERIFICADO** | Alto | [#139](https://github.com/cacao-accounting/cacao-accounting/issues/139) |
| O2C-07 | **ISSUE VERIFICADO** | Muy Alto | [#125](https://github.com/cacao-accounting/cacao-accounting/issues/125) |
| O2C-16 | **FALSO POSITIVO** | Muy Alto | — |
| O2C-18 | **ISSUE VERIFICADO** | Muy Alto | [#126](https://github.com/cacao-accounting/cacao-accounting/issues/126) |
| O2C-20 | **ISSUE VERIFICADO** | Muy Alto | [#127](https://github.com/cacao-accounting/cacao-accounting/issues/127) |
| R2R-03 | **ISSUE VERIFICADO** | Muy Alto | [#128](https://github.com/cacao-accounting/cacao-accounting/issues/128) |
| R2R-05 | **ISSUE VERIFICADO** | Alto | [#129](https://github.com/cacao-accounting/cacao-accounting/issues/129) |
| R2R-11 | **ISSUE VERIFICADO** | Alto | [#130](https://github.com/cacao-accounting/cacao-accounting/issues/130) |
| R2R-12 | **ISSUE VERIFICADO** | Alto | [#131](https://github.com/cacao-accounting/cacao-accounting/issues/131) |
| R2R-14 | **ISSUE VERIFICADO** | Muy Alto | [#132](https://github.com/cacao-accounting/cacao-accounting/issues/132) |
| CAS-10 | **ISSUE VERIFICADO** | Muy Alto | [#133](https://github.com/cacao-accounting/cacao-accounting/issues/133) |
| CAS-13 | **ISSUE VERIFICADO** | Muy Alto | [#134](https://github.com/cacao-accounting/cacao-accounting/issues/134) |
| CAS-14 | **ISSUE VERIFICADO** | Alto | [#135](https://github.com/cacao-accounting/cacao-accounting/issues/135) |
| INV-06 | **ISSUE VERIFICADO** | Muy Alto | [#136](https://github.com/cacao-accounting/cacao-accounting/issues/136) |
| INV-25 | **ISSUE VERIFICADO** | Muy Alto | [#137](https://github.com/cacao-accounting/cacao-accounting/issues/137) |
| S2P-03 | **ISSUE VERIFICADO** | Alto | [#140](https://github.com/cacao-accounting/cacao-accounting/issues/140) |
| S2P-08 | **ISSUE VERIFICADO** | Alto | [#141](https://github.com/cacao-accounting/cacao-accounting/issues/141) |
| S2P-13 | **ISSUE VERIFICADO** | Alto | [#142](https://github.com/cacao-accounting/cacao-accounting/issues/142) |
| S2P-20 | **ISSUE VERIFICADO** | Alto | [#143](https://github.com/cacao-accounting/cacao-accounting/issues/143) |
| O2C-08 | **ISSUE VERIFICADO** | Muy Alto | [#144](https://github.com/cacao-accounting/cacao-accounting/issues/144) |
| O2C-09 | **ISSUE VERIFICADO** | Alto | [#145](https://github.com/cacao-accounting/cacao-accounting/issues/145) |
| O2C-11 | **ISSUE VERIFICADO** | Alto | [#146](https://github.com/cacao-accounting/cacao-accounting/issues/146) |
| O2C-22 | **ISSUE VERIFICADO** | Alto | [#147](https://github.com/cacao-accounting/cacao-accounting/issues/147) |
| O2C-28 | **ISSUE VERIFICADO** | Alto | [#148](https://github.com/cacao-accounting/cacao-accounting/issues/148) |
| R2R-06 | **ISSUE VERIFICADO** | Alto | [#149](https://github.com/cacao-accounting/cacao-accounting/issues/149) |
| CAS-01 | **ISSUE VERIFICADO** | Alto | [#150](https://github.com/cacao-accounting/cacao-accounting/issues/150) |
| CAS-04 | **ISSUE VERIFICADO** | Alto | [#151](https://github.com/cacao-accounting/cacao-accounting/issues/151) |
| CAS-06 | **ISSUE VERIFICADO** | Alto | [#152](https://github.com/cacao-accounting/cacao-accounting/issues/152) |
| CAS-07 | **ISSUE VERIFICADO** | Alto | [#153](https://github.com/cacao-accounting/cacao-accounting/issues/153) |
| CAS-15 | **ISSUE VERIFICADO** | Alto | [#154](https://github.com/cacao-accounting/cacao-accounting/issues/154) |
| INV-01 | **FALSO POSITIVO (CERRADO)** | Muy Alto | [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) |
| INV-03 | **ISSUE VERIFICADO** | Alto | [#156](https://github.com/cacao-accounting/cacao-accounting/issues/156) |
| INV-04 | **ISSUE VERIFICADO** | Alto | [#157](https://github.com/cacao-accounting/cacao-accounting/issues/157) |
| INV-07 | **ISSUE VERIFICADO** | Alto | [#158](https://github.com/cacao-accounting/cacao-accounting/issues/158) |
| INV-10 | **ISSUE VERIFICADO** | Medio | [#159](https://github.com/cacao-accounting/cacao-accounting/issues/159) |
| S2P-05 | **ISSUE VERIFICADO** | Bajo | [#175](https://github.com/cacao-accounting/cacao-accounting/issues/175) |
| S2P-06 | **ISSUE VERIFICADO** | Alto | [#160](https://github.com/cacao-accounting/cacao-accounting/issues/160) |
| S2P-10 | **ISSUE VERIFICADO** | Alto | [#161](https://github.com/cacao-accounting/cacao-accounting/issues/161) |
| S2P-14 | **ISSUE VERIFICADO** | Bajo | [#162](https://github.com/cacao-accounting/cacao-accounting/issues/162) |
| S2P-15 | **ISSUE VERIFICADO** | Medio | [#176](https://github.com/cacao-accounting/cacao-accounting/issues/176) |
| S2P-16 | **ISSUE VERIFICADO** | Bajo | [#177](https://github.com/cacao-accounting/cacao-accounting/issues/177) |
| S2P-17 | **ISSUE VERIFICADO** | Medio | [#178](https://github.com/cacao-accounting/cacao-accounting/issues/178) |
| S2P-18 | **ISSUE VERIFICADO** | Medio | [#163](https://github.com/cacao-accounting/cacao-accounting/issues/163) |
| S2P-19 | **ISSUE VERIFICADO** | Bajo | [#179](https://github.com/cacao-accounting/cacao-accounting/issues/179) |
| O2C-01 | **FALSO POSITIVO** | Muy Alto | — |
| O2C-02 | **FALSO POSITIVO** | Alto | — |
| O2C-06 | **ISSUE VERIFICADO** | Medio | [#180](https://github.com/cacao-accounting/cacao-accounting/issues/180) |
| O2C-10 | **ISSUE VERIFICADO** | Bajo | [#181](https://github.com/cacao-accounting/cacao-accounting/issues/181) |
| O2C-12 | **FALSO POSITIVO** | Bajo | — |
| O2C-13 | **ISSUE VERIFICADO** | Medio | [#182](https://github.com/cacao-accounting/cacao-accounting/issues/182) |
| O2C-14 | **ISSUE VERIFICADO** | Medio | [#183](https://github.com/cacao-accounting/cacao-accounting/issues/183) |
| O2C-17 | **FALSO POSITIVO** | Medio | — |
| O2C-21 | **FALSO POSITIVO** | Bajo | — |
| R2R-01 | **FALSO POSITIVO** | Alto | — |
| R2R-02 | **FALSO POSITIVO** | Medio | — |
| R2R-04 | **FALSO POSITIVO** | Medio | [#174](https://github.com/cacao-accounting/cacao-accounting/issues/174) |
| R2R-07 | **ISSUE VERIFICADO** | Alto | [#164](https://github.com/cacao-accounting/cacao-accounting/issues/164) |
| R2R-08 | **FALSO POSITIVO** | Alto | — |
| R2R-09 | **ISSUE VERIFICADO** | Medio | [#165](https://github.com/cacao-accounting/cacao-accounting/issues/165) |
| R2R-10 | **ISSUE VERIFICADO** | Medio | [#184](https://github.com/cacao-accounting/cacao-accounting/issues/184) |
| R2R-13 | **ISSUE VERIFICADO** | Medio | [#185](https://github.com/cacao-accounting/cacao-accounting/issues/185) |
| R2R-15 | **ISSUE VERIFICADO** | Medio | [#166](https://github.com/cacao-accounting/cacao-accounting/issues/166) |
| R2R-16 | **ISSUE VERIFICADO** | Medio | [#167](https://github.com/cacao-accounting/cacao-accounting/issues/167) |
| CAS-02 | **ISSUE VERIFICADO** | Alto | [#169](https://github.com/cacao-accounting/cacao-accounting/issues/169) |
| CAS-03 | **ISSUE VERIFICADO** | Medio | [#168](https://github.com/cacao-accounting/cacao-accounting/issues/168) |
| CAS-05 | **FALSO POSITIVO** | Medio | — |
| CAS-08 | **FALSO POSITIVO** | Medio | — |
| CAS-09 | **FALSO POSITIVO** | Bajo | — |
| CAS-11 | **FALSO POSITIVO** | Bajo | — |
| CAS-12 | **FALSO POSITIVO** | Medio | — |
| CAS-16 | **FALSO POSITIVO** | Medio | — |
| CAS-17 | **FALSO POSITIVO** | Bajo | — |
| INV-01 | **FALSO POSITIVO (CERRADO)** | Muy Alto | [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) |
| INV-02 | **ISSUE VERIFICADO** | Bajo | [#170](https://github.com/cacao-accounting/cacao-accounting/issues/170) |
| INV-05 | **ISSUE VERIFICADO** | Bajo | [#171](https://github.com/cacao-accounting/cacao-accounting/issues/171) |
| INV-11 | **ISSUE VERIFICADO** | Bajo | [#172](https://github.com/cacao-accounting/cacao-accounting/issues/172) |
| INV-21 | **FALSO POSITIVO** | Bajo | — |
| INV-22 | **FALSO POSITIVO** | Medio | — |

**Resumen:** 54 ISSUE VERIFICADO, 14 FALSO POSITIVO, 21 pendientes de verificación

---

## RESUMEN GLOBAL

| Módulo | ALTO | MEDIO | BAJO | TOTAL |
|--------|------|-------|------|-------|
| Source to Pay (S2P) | 7 | 9 | 4 | 20 |
| Order to Cash (O2C) | 6 | 13 | 3 | 22 |
| Record to Report (R2R) | 9 | 7 | 0 | 16 |
| Tesorería (CAS) | 6 | 8 | 3 | 17 |
| Inventario (INV) | 3 | 7 | 4 | 14 |
| **TOTAL** | **31** | **44** | **14** | **89** |

---

## 1. SOURCE TO PAY (S2P) — Compras

### S2P-01 [ALTO] — Sin verificación de relaciones activas al cancelar documentos no financieros

**Descripción:** Los handlers de cancelación de PurchaseRequest, SupplierQuotation, PurchaseQuotation y PurchaseReceipt no llaman a `has_active_source_relations()` antes de transicionar `docstatus` a 2. Solo PurchaseOrder realiza esta verificación.

**Impacto:** Violación de integridad referencial. Un documento cancelado puede tener hijos activos (ej. PR cancelada con OCs activas).

**Recomendación:** Agregar `has_active_source_relations()` al inicio de cada handler de cancelación, replicando el patrón existente en `compras_orden_compra_cancel`.

**Caso de prueba:**
1. Crear y aprobar una Purchase Request (PR-001)
2. Crear y aprobar una Purchase Order (PO-001) desde PR-001
3. Intentar cancelar PR-001
4. Assert: cancelación bloqueada con mensaje

**Evidencia:** `cacao_accounting/compras/__init__.py:454-470, 911-927, 2200-2216, 2617-2637`

> **✅ Verificado por MiMo-V2.5** — [#119](https://github.com/cacao-accounting/cacao-accounting/issues/119)

### S2P-02 [ALTO] — `log_create` no se llama en la creación de la mayoría de documentos

**Descripción:** Solo PurchaseReceipt llama a `log_create()`. Los demás tipos documentales (PR, SQ, PO, PQ, PI) no registran el evento "created" en auditoría.

**Impacto:** Trazabilidad incompleta. No se puede determinar quién creó cada documento ni cuándo. Riesgo SOX.

**Recomendación:** Agregar `log_create(registro)` después de `database.session.commit()` en todos los handlers de creación.

**Evidencia:** `cacao_accounting/compras/__init__.py:2336` — único call site de `log_create`

> **✅ Verificado por MiMo-V2.5** — [#120](https://github.com/cacao-accounting/cacao-accounting/issues/120)

### S2P-03 [MEDIO] — `log_update` no se llama en edición de PR, SQ, PO

**Evidencia:** `cacao_accounting/compras/__init__.py:318-336, 733-752, 1781-1804`

> **✅ Verificado por MiMo-V2.5** — [#140](https://github.com/cacao-accounting/cacao-accounting/issues/140)

### S2P-04 [ALTO] — Three-way match omitido cuando Factura salta Recepción (PO → Invoice directo)

**Descripción:** El flujo `purchase_order → purchase_invoice` permite crear factura directa desde OC sin recepción intermedia. `_validate_invoice_quantities_against_receipt()` solo valida contra receipt relations. Si no hay receipt, no hay protección contra sobre-facturación.

**Impacto:** Un proveedor puede ser facturado y pagado por cantidades que exceden la OC. Riesgo de pérdida financiera.

**Recomendación:** Extender validación para verificar contra la OC cuando la factura tiene `purchase_order_id` pero no receipt relations.

**Evidencia:** `cacao_accounting/document_flow/registry.py:694`, `cacao_accounting/compras/__init__.py:2564-2586`

> **✅ Verificado por MiMo-V2.5** — [#121](https://github.com/cacao-accounting/cacao-accounting/issues/121)

### S2P-05 [BAJO] — Validación de cantidades solo en submit, no en draft/edit

**Evidencia:** `cacao_accounting/compras/__init__.py:2309-2342, 2463-2486`

### S2P-06 [MEDIO] — `supplier_name` no establecido en Purchase Receipt

**Evidencia:** `cacao_accounting/compras/__init__.py:2311-2318` vs PO creación línea 1749

### S2P-07 [ALTO] — Tipo de cambio perdido al editar Purchase Invoice multimoneda

**Descripción:** `_handle_purchase_invoice_edit_post` establece montos base a `total` sin aplicar exchange rate. Editar una factura multimoneda asume tasa 1:1.

**Impacto:** Posting GL incorrecto en la moneda base de la compañía.

**Recomendación:** Recalcular exchange rate y montos base usando `_compute_base_amounts(total, fx_rate)`.

**Evidencia:** `cacao_accounting/compras/__init__.py:3020-3025` vs `2873-2881`

> **✅ Verificado por MiMo-V2.5** — [#122](https://github.com/cacao-accounting/cacao-accounting/issues/122)

### S2P-08 [MEDIO] — Handlers de duplicado pierden tipo de cambio (PO, Invoice)

**Evidencia:** `cacao_accounting/compras/__init__.py:1853, 3084-3088`

> **✅ Verificado por MiMo-V2.5** — [#141](https://github.com/cacao-accounting/cacao-accounting/issues/141)

### S2P-09 [MEDIO] — `_validate_supplier_invoice_flags` omite validación cuando `CompanyParty` es None

**Evidencia:** `cacao_accounting/compras/__init__.py:2824-2825`

> **✅ Verificado por MiMo-V2.5** — [#138](https://github.com/cacao-accounting/cacao-accounting/issues/138)

### S2P-10 [ALTO] — Condición de carrera en asignación directa de pago (sin `with_for_update`)

**Evidencia:** `cacao_accounting/document_flow/service.py:1640-1664` vs `742`

### S2P-11 [ALTO] — `except Exception` genérico en `_purchase_exchange_rate` silencia errores

**Evidencia:** `cacao_accounting/compras/__init__.py:2798-2799`

> **✅ Verificado por MiMo-V2.5** — [#123](https://github.com/cacao-accounting/cacao-accounting/issues/123)

### S2P-12 [ALTO] — Cancelación de Invoice no verifica referencias de pago activas

**Evidencia:** `cacao_accounting/compras/__init__.py:3129-3150`

> **✅ Verificado por MiMo-V2.5** — [#124](https://github.com/cacao-accounting/cacao-accounting/issues/124)

### S2P-13 [MEDIO] — `get_document_type` lanza KeyError para tipos desconocidos

**Evidencia:** `cacao_accounting/document_flow/registry.py:748-751`

> **✅ Verificado por MiMo-V2.5** — [#142](https://github.com/cacao-accounting/cacao-accounting/issues/142)

### S2P-14 [BAJO] — Creación de relaciones documentales sin auditoría

**Evidencia:** `cacao_accounting/document_flow/service.py:1200-1264`

### S2P-15 [MEDIO] — Propagación de caché transitiva incompleta al cancelar Recepción

**Evidencia:** `cacao_accounting/document_flow/service.py:1138-1143`

### S2P-16 [BAJO] — `supplier_invoice_no` sobrescrito por formulario vacío

**Evidencia:** `cacao_accounting/compras/__init__.py:3009`

### S2P-17 [MEDIO] — Validaciones de Recepción/Factura se omiten sin enlace explícito

**Evidencia:** `cacao_accounting/compras/__init__.py:2539-2561`

### S2P-18 [MEDIO] — Sin validación de existencia/actividad de almacén en Recepción

**Evidencia:** `cacao_accounting/compras/__init__.py:1469-1477`

### S2P-19 [BAJO] — Sin `log_create` en `create_target_document` (API/bulk)

**Evidencia:** `cacao_accounting/document_flow/service.py:1548-1571`

### S2P-20 [MEDIO] — Cancelación de Recepción no verifica facturas downstream

**Evidencia:** `cacao_accounting/compras/__init__.py:2617-2637`

> **✅ Verificado por MiMo-V2.5** — [#143](https://github.com/cacao-accounting/cacao-accounting/issues/143)

---

## 2. ORDER TO CASH (O2C) — Ventas

### O2C-01 [MEDIO] — SalesRequest submit usa `require_party=False`

**Evidencia:** `cacao_accounting/ventas/__init__.py:500`

### O2C-02 [MEDIO] — Secuencia de cancelación inconsistente en SalesInvoice

**Evidencia:** `cacao_accounting/ventas/__init__.py:2531-2534`

### O2C-03 [ALTO] — DeliveryNote no disminuye `actual_qty` en StockBin

**Descripción:** `ventas_entrega_submit` nunca disminuye `actual_qty`. El inventario contable nunca refleja las salidas por Notas de Entrega.

**Impacto:** Stock `actual_qty` nunca se reduce. Inventario contable permanentemente desincronizado.

**Evidencia:** `cacao_accounting/ventas/__init__.py:2131-2151`, `cacao_accounting/contabilidad/posting.py:2605-2617`

> **❌ FALSO POSITIVO** (verificado por MiMo-V2.5) — El posting chain `submit_document(dn)` → `post_delivery_note(dn)` → `_upsert_stock_bin(qty_change=negative)` SÍ disminuye `actual_qty`. Test `test_uoms_full.py:207` confirma.

### O2C-04 [MEDIO] — `_release_reservation_for_delivery_note` no es idempotente

**Evidencia:** `cacao_accounting/ventas/__init__.py:186-202`

> **✅ Verificado por MiMo-V2.5** — [#139](https://github.com/cacao-accounting/cacao-accounting/issues/139)

### O2C-05 [MEDIO] — `_restore_reservation_for_delivery_note` puede sobresuscribir reserved_qty

**Evidencia:** `cacao_accounting/ventas/__init__.py:204-218`

> **❌ FALSO POSITIVO** (verificado por MiMo-V2.5) — La función lee reserved actual y suma item.qty. No sobrescribe, incrementa correctamente.

### O2C-06 [MEDIO] — Validación de precio en edición bloquea guardar borrador

**Evidencia:** `cacao_accounting/ventas/__init__.py:1180-1249, 2390-2420`

### O2C-07 [ALTO] — Factura con `update_inventory=True` no disminuye `actual_qty` ni `reserved_qty`

**Descripción:** Cuando una SalesInvoice se aprueba con `update_inventory=True`, la DN auto-creada no llama a `_release_reservation_for_delivery_note`.

**Impacto:** Ledger de inventario permanentemente fuera de sincronía.

**Evidencia:** `cacao_accounting/ventas/__init__.py:1115-1177`

> **✅ Verificado por MiMo-V2.5** — [#125](https://github.com/cacao-accounting/cacao-accounting/issues/125)

### O2C-08 [ALTO] — Cancelación de Invoice no restaura inventario cuando `update_inventory=True`

**Evidencia:** `cacao_accounting/ventas/__init__.py:2511-2541`

> **✅ Verificado por MiMo-V2.5** — [#144](https://github.com/cacao-accounting/cacao-accounting/issues/144)

### O2C-09 [MEDIO] — SalesQuotation cancel no verifica relaciones descendientes activas

**Evidencia:** `cacao_accounting/ventas/__init__.py:1808-1824` vs `1851-1871`

> **✅ Verificado por MiMo-V2.5** — [#145](https://github.com/cacao-accounting/cacao-accounting/issues/145)

### O2C-10 [BAJO] — `_handle_sales_order_new_post` retorna None en error

**Evidencia:** `cacao_accounting/ventas/__init__.py:1296-1329`

### O2C-11 [MEDIO] — Edición de SalesOrder/SalesRequest sin auditoría

**Evidencia:** `cacao_accounting/ventas/__init__.py:807-824, 827-844`

> **✅ Verificado por MiMo-V2.5** — [#146](https://github.com/cacao-accounting/cacao-accounting/issues/146)

### O2C-12 [BAJO] — Inconsistencia de naming en parámetros

**Evidencia:** `cacao_accounting/ventas/__init__.py:827, 807`

### O2C-13 [MEDIO] — `create_document_relation` no valida docstatus de origen

**Evidencia:** `cacao_accounting/document_flow/service.py:1200-1264`

### O2C-14 [MEDIO] — `validate_submit_prerequisites` no valida rate > 0, amount > 0

**Evidencia:** `cacao_accounting/document_flow/validation.py:7-34`

### O2C-15 [MEDIO] — `is_return`/`reversal_of` no protegidos en edición de crédito/débito

**Evidencia:** `cacao_accounting/ventas/__init__.py:2390-2421`

> **❌ FALSO POSITIVO** (verificado por MiMo-V2.5) — Los edit handlers no tocan is_return ni reversal_of. Los campos se preservan del registro existente.

### O2C-16 [ALTO] — `stock_value` nunca se actualiza en movimientos O2C

**Descripción:** `StockBin.stock_value` se inicializa en 0 y nunca se actualiza en el flujo de ventas.

**Evidencia:** `cacao_accounting/ventas/__init__.py:125-218`

> **❌ FALSO POSITIVO** (verificado por MiMo-V2.5) — `_upsert_stock_bin` en `posting.py:1449` actualiza `stock_value` con `value_change` derivado de `_consume_stock_valuation_layers`.

### O2C-17 [MEDIO] — DeliveryNote `is_return` sin lógica de reversión real

**Evidencia:** `cacao_accounting/ventas/__init__.py:1860-1928`

### O2C-18 [ALTO] — Nota de Crédito/Débito: `reversal_of` no validado

**Descripción:** `reversal_of` se establece desde el formulario sin validar que la factura referenciada exista, esté aprobada, y pertenezca al mismo cliente/compañía.

**Evidencia:** `cacao_accounting/ventas/__init__.py:2229-2271`

> **✅ Verificado por MiMo-V2.5** — [#126](https://github.com/cacao-accounting/cacao-accounting/issues/126)

### O2C-20 [ALTO] — Sin `SELECT...FOR UPDATE` en reserva de stock (concurrencia)

**Descripción:** `_validate_and_reserve_stock_for_sales_order` lee y actualiza StockBin sin `with_for_update()`. Bajo carga concurrente, dos órdenes pueden reservar el mismo stock.

**Evidencia:** `cacao_accounting/ventas/__init__.py:144-168`

> **✅ Verificado por MiMo-V2.5** — [#127](https://github.com/cacao-accounting/cacao-accounting/issues/127)

### O2C-21 [BAJO] — `_form_decimal` acoplada a `request.form`

**Evidencia:** `cacao_accounting/ventas/__init__.py:919-930`

### O2C-22 [MEDIO] — `validate_submit_prerequisites` no valida almacén para ítems de stock

**Evidencia:** `cacao_accounting/document_flow/validation.py:7-34`

> **✅ Verificado por MiMo-V2.5** — [#147](https://github.com/cacao-accounting/cacao-accounting/issues/147)

### O2C-28 [MEDIO] — `delivered_qty`/`billed_qty` no inicializados en 0

**Evidencia:** `cacao_accounting/database/__init__.py:1455-1456`

> **✅ Verificado por MiMo-V2.5** — [#148](https://github.com/cacao-accounting/cacao-accounting/issues/148)

---

## 3. RECORD TO REPORT (R2R) — Contabilidad

### R2R-01 [ALTO] — Validación de balance usa signed `line.value` después de redondeo por línea

**Descripción:** `post_comprobante_contable` verifica balance sumando `line.value`. Cada línea se redondea a 4 decimales por conversión de moneda. La suma puede producir desbalance falso de 0.0001.

**Impacto:** Asientos multimoneda con múltiples líneas fallan frecuentemente con falso desbalance.

**Recomendación:** Usar tolerancia `abs(total_value) > Decimal("0.01")`.

**Evidencia:** `cacao_accounting/contabilidad/posting.py:2354-2369, 418-421`

### R2R-02 [MEDIO] — Validación de período inconsistente en revaluación cambiaria

**Evidencia:** `cacao_accounting/contabilidad/exchange_revaluation_service.py:96-103`

### R2R-03 [ALTO] — `cancel_submitted_journal` fuerza cancelación en la misma fecha

**Descripción:** Requiere fecha de reversión = fecha del asiento original. IAS/IFRS 8 permite correcciones en período de descubrimiento.

**Impacto:** Usuarios no pueden corregir errores descubiertos en períodos posteriores.

**Recomendación:** Eliminar el requisito de misma fecha. Validar solo período abierto.

**Evidencia:** `cacao_accounting/contabilidad/journal_service.py:204-206`

> **✅ Verificado por MiMo-V2.5** — [#128](https://github.com/cacao-accounting/cacao-accounting/issues/128)

### R2R-04 [MEDIO] — `duplicate_journal_as_reversal_draft` bloquea reversiones mismo período

**Evidencia:** `cacao_accounting/contabilidad/journal_service.py:305-308`

### R2R-05 [ALTO] — Cierre de año fiscal crea borrador sin aprobar

**Descripción:** El voucher de cierre se crea en draft. Si el usuario olvida aprobarlo, el año fiscal queda abierto.

**Recomendación:** Auto-aprobar el voucher o mostrar indicador prominente en dashboard.

**Evidencia:** `cacao_accounting/contabilidad/fiscal_year_closing.py:168-203`

> **✅ Verificado por MiMo-V2.5** — [#129](https://github.com/cacao-accounting/cacao-accounting/issues/129)

### R2R-06 [ALTO] — Revaluación cambiaria sin auditoría

**Descripción:** `ExchangeRevaluationService.run()` y `void()` no registran eventos de auditoría.

**Recomendación:** Agregar `log_create`, `log_submit`, `log_cancel`.

**Evidencia:** `cacao_accounting/contabilidad/exchange_revaluation_service.py:80-219`

> **✅ Verificado por MiMo-V2.5** — [#149](https://github.com/cacao-accounting/cacao-accounting/issues/149)

### R2R-07 [ALTO] — Cierre de período sin auditoría

**Descripción:** `finalizar_cierre_mensual` no registra quién cerró el período.

**Evidencia:** `cacao_accounting/contabilidad/__init__.py:2717-2746`

### R2R-08 [ALTO] — Documentos operativos sin auditoría de submit/cancel

**Descripción:** `submit_document` y `cancel_document` en posting.py no llaman a `log_submit` ni `log_cancel`.

**Evidencia:** `cacao_accounting/contabilidad/posting.py:2605-2639`

### R2R-09 [MEDIO] — Diarios recurrentes sin auditoría

**Evidencia:** `cacao_accounting/contabilidad/recurring_journal_service.py:134-232`

### R2R-10 [MEDIO] — Sin control presupuestario en posting

**Evidencia:** `cacao_accounting/contabilidad/posting.py`

### R2R-11 [ALTO] — Sin protección contra doble posting en funciones `post_*` individuales

**Descripción:** Las funciones individuales `post_sales_invoice`, `post_purchase_invoice`, `post_payment_entry`, `post_bank_transaction` no verifican GL entries existentes antes de postear.

**Evidencia:** `cacao_accounting/contabilidad/posting.py:757, 846, 971, 1389`

> **✅ Verificado por MiMo-V2.5** — [#130](https://github.com/cacao-accounting/cacao-accounting/issues/130)

### R2R-12 [ALTO] — Redondeo de tipo de cambio causa fallos de balance

**Evidencia:** `cacao_accounting/contabilidad/posting.py:408-416, 418-421`

> **✅ Verificado por MiMo-V2.5** — [#131](https://github.com/cacao-accounting/cacao-accounting/issues/131)

### R2R-13 [MEDIO] — Linking item-to-entry en revaluación frágil (orden posicional)

**Evidencia:** `cacao_accounting/contabilidad/exchange_revaluation_service.py:544-546`

### R2R-14 [ALTO] — Cierre de período no exige completitud de pasos requeridos

**Descripción:** Un período puede cerrarse aunque los pasos requeridos no estén completados. `PeriodCloseCheck` no se valida su estado "passed".

**Recomendación:** Verificar `check_status == "passed"` para todos los checks antes de cerrar.

**Evidencia:** `cacao_accounting/contabilidad/__init__.py:2717-2746`

> **✅ Verificado por MiMo-V2.5** — [#132](https://github.com/cacao-accounting/cacao-accounting/issues/132)

### R2R-15 [MEDIO] — Búsqueda de tipo de cambio sin fallback a fecha más cercana

**Evidencia:** `cacao_accounting/contabilidad/exchange_revaluation_service.py:655-675`

### R2R-16 [MEDIO] — Balance proporcional en revaluación puede causar residuales

**Evidencia:** `cacao_accounting/contabilidad/exchange_revaluation_service.py:598-601`

---

## 4. TESORERÍA (Cash Management)

### CAS-01 [ALTO] — Sin constraint único en PaymentReference — aplicación duplicada concurrente

**Descripción:** Sin `UniqueConstraint(payment_id, reference_type, reference_id)` ni `FOR UPDATE`. Dos requests concurrentes pueden duplicar aplicación del mismo pago a la misma factura.

**Recomendación:** Agregar `UniqueConstraint` y `FOR UPDATE` en `_check_duplicate_application`.

**Evidencia:** `cacao_accounting/database/__init__.py:1600-1623`, `cacao_accounting/document_flow/service.py:753-767`

> **✅ Verificado por MiMo-V2.5** — [#150](https://github.com/cacao-accounting/cacao-accounting/issues/150)

### CAS-02 [ALTO] — Sin bloqueo de fila en conciliación bancaria — duplicación concurrente

**Evidencia:** `cacao_accounting/bancos/reconciliation_service.py:266-330`

### CAS-03 [MEDIO] — Sin validación cruzada de tipo de cambio entre pago y referencias

**Evidencia:** `cacao_accounting/bancos/__init__.py:1602-1714`

### CAS-04 [MEDIO] — Cancelación de pago no limpia enlace de conciliación bancaria

**Evidencia:** `cacao_accounting/bancos/__init__.py:1837-1867`

> **✅ Verificado por MiMo-V2.5** — [#151](https://github.com/cacao-accounting/cacao-accounting/issues/151)

### CAS-05 [MEDIO] — Sin saldo en tiempo real en BankAccount

**Evidencia:** `cacao_accounting/database/__init__.py:1553-1567`

### CAS-06 [ALTO] — Pago sin `FOR UPDATE` en flujo de reconciliación — sobre-aplicación concurrente

**Evidencia:** `cacao_accounting/document_flow/service.py:688` vs `742`

> **✅ Verificado por MiMo-V2.5** — [#152](https://github.com/cacao-accounting/cacao-accounting/issues/152)

### CAS-07 [MEDIO] — Sin límite de tamaño de lote en reconciliación masiva

**Evidencia:** `cacao_accounting/bancos/__init__.py:296-333`

> **✅ Verificado por MiMo-V2.5** — [#153](https://github.com/cacao-accounting/cacao-accounting/issues/153)

### CAS-08 [MEDIO] — Descuento por pronto pago usa `posting_date` no fecha de factura

**Evidencia:** `cacao_accounting/accounting_engine/document_builders.py:769-770`

> **❌ FALSO POSITIVO** (verificado por MiMo-V2.5) — El descuento usa invoice.posting_date como base, no posting_date del pago. Comportamiento correcto.

### CAS-09 [BAJO] — Descuento por pronto pago no accesible en formulario de pago

**Evidencia:** `cacao_accounting/bancos/forms.py:32-57`

### CAS-10 [ALTO] — Creación de pago masivo pierde tipo de cambio, descuento, ganancia/pérdida

**Descripción:** `_persist_payment_target_allocation` no establece `exchange_rate`, `discount_amount`, `gain_loss_amount` ni `difference_amount`. Pagos por API masiva pierden metadatos críticos.

**Evidencia:** `cacao_accounting/document_flow/service.py:1675-1708`

> **✅ Verificado por MiMo-V2.5** — [#133](https://github.com/cacao-accounting/cacao-accounting/issues/133)

### CAS-11 [BAJO] — Sin validación de asignación mínima

**Evidencia:** `cacao_accounting/bancos/__init__.py:1743-1749`

### CAS-12 [MEDIO] — Sin validación de cuenta GL al aprobar pago

**Evidencia:** `cacao_accounting/bancos/__init__.py:1815-1834`

> **❌ FALSO POSITIVO** (verificado por MiMo-V2.5) — submit_document → post_payment_entry → _require_account valida cuenta GL con fallback de 3 niveles.

### CAS-13 [ALTO] — `_cash_consumed` cero permite eludir verificación de saldo restante

**Descripción:** Si `discount + gain_loss >= allocated`, `consumed = 0` y la verificación de saldo restante siempre pasa, permitiendo aplicar un pago a facturas ilimitadas.

**Evidencia:** `cacao_accounting/document_flow/service.py:622-625, 694-696`

> **✅ Verificado por MiMo-V2.5** — [#134](https://github.com/cacao-accounting/cacao-accounting/issues/134)

### CAS-14 [ALTO] — Transacción bancaria puede reconciliarse dos veces vía ruta "apply"

**Descripción:** `bancos_conciliacion_bancaria_aplicar` no valida `is_reconciled`. El check existe solo en el endpoint batch.

**Evidencia:** `cacao_accounting/bancos/__init__.py:536-564`

> **✅ Verificado por MiMo-V2.5** — [#135](https://github.com/cacao-accounting/cacao-accounting/issues/135)

### CAS-15 [MEDIO] — Caché de saldo pendiente obsoleto puede bloquear pagos legítimos

**Evidencia:** `cacao_accounting/bancos/__init__.py:813-826`

> **✅ Verificado por MiMo-V2.5** — [#154](https://github.com/cacao-accounting/cacao-accounting/issues/154)

### CAS-16 [MEDIO] — PaymentReference rows huérfanos al cancelar pago

**Evidencia:** `cacao_accounting/bancos/__init__.py:1849-1859`

### CAS-17 [BAJO] — `_payment_numbering_defaults` no valida compañía del banco

**Evidencia:** `cacao_accounting/bancos/__init__.py:218-227`

---

## 5. INVENTARIO (Inventory Management)

### INV-01 [MEDIO] — Verificación de stock negativo ocurre después de upsert de StockBin

**Evidencia:** `cacao_accounting/contabilidad/posting.py:1681-1696`

> **❌ FALSO POSITIVO (CERRADO)** (verificado por MiMo-V2.5) — El check ocurre ANTES de _upsert_stock_bin. `_stock_qty_after` es read-only. Comentario explicativo agregado en código fuente.
>
> **GitHub:** [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) — Cerrado 2026-07-09

### INV-02 [BAJO] — Check de stock negativo en traslados funciona pero mensaje no específico

**Evidencia:** `cacao_accounting/contabilidad/posting.py:1869-1897`

### INV-03 [MEDIO] — Filtro de compañía en almacén inconsistente con `WarehouseCompanyAccount`

**Evidencia:** `cacao_accounting/database/__init__.py:927-956`

> **✅ Verificado por MiMo-V2.5** — [#156](https://github.com/cacao-accounting/cacao-accounting/issues/156)

### INV-04 [MEDIO] — Conversión de UOM en reconciliación falla silenciosamente

**Evidencia:** `cacao_accounting/inventario/__init__.py:911-919`

> **✅ Verificado por MiMo-V2.5** — [#157](https://github.com/cacao-accounting/cacao-accounting/issues/157)

### INV-05 [BAJO] — `qty_in_base_uom` no persiste al guardar entrada de stock

**Evidencia:** `cacao_accounting/inventario/__init__.py:839-865`

### INV-06 [ALTO] — `_stock_qty_after` sin `FOR UPDATE` — riesgo de condición de carrera

**Descripción:** `_stock_qty_after` ejecuta SUM sin `FOR UPDATE`. Dos emisiones concurrentes pueden evitar `allow_negative_stock=False`.

**Recomendación:** Derivar `qty_after` de `bin_row.actual_qty + qty_change` dentro de `_upsert_stock_bin` (que ya tiene `FOR UPDATE`).

**Evidencia:** `cacao_accounting/contabilidad/posting.py:1227-1233, 1427-1455`

> **✅ Verificado por MiMo-V2.5** — [#136](https://github.com/cacao-accounting/cacao-accounting/issues/136)

### INV-07 [ALTO] — Sin capacidad de reconstruir `StockValuationLayer`

**Descripción:** `rebuild_stock_bins` reconstruye StockBin pero no StockValuationLayer. FIFO irrecuperable ante corrupción.

**Recomendación:** Agregar método para reconstruir capas FIFO desde StockLedgerEntry.

**Evidencia:** `cacao_accounting/inventario/service.py:159-198`

> **✅ Verificado por MiMo-V2.5** — [#158](https://github.com/cacao-accounting/cacao-accounting/issues/158)

### INV-10 [MEDIO] — `reserved_qty` puede desviarse por movimientos fuera del flujo O2C

**Evidencia:** `cacao_accounting/contabilidad/posting.py:1427-1455`

> **✅ Verificado por MiMo-V2.5** — [#159](https://github.com/cacao-accounting/cacao-accounting/issues/159)

### INV-11 [BAJO] — Mensaje de error genérico cuando no hay capas de valoración

**Evidencia:** `cacao_accounting/contabilidad/posting.py:1181-1190`

### INV-21 [BAJO] — `valuation_rate` se resetea a 0 cuando qty=0

**Evidencia:** `cacao_accounting/contabilidad/posting.py:1452-1455`

### INV-22 [MEDIO] — Relaciones documentales creadas en draft, eliminadas en edición

**Evidencia:** `cacao_accounting/inventario/__init__.py:809-836`

> **❌ FALSO POSITIVO** (verificado por MiMo-V2.5) — El edit handler `_delete_and_resave_stock_entry_items` elimina relaciones viejas y las recrea correctamente.

### INV-25 [ALTO] — Reconciliación de inventario no consume capas FIFO

**Descripción:** Al reducir stock por reconciliación, no se consumen las capas FIFO existentes. El FIFO diverge progresivamente del stock físico.

**Recomendación:** Consumir desde capas FIFO usando `_consume_stock_valuation_layers`.

**Evidencia:** `cacao_accounting/contabilidad/posting.py:1729-1806`

> **✅ Verificado por MiMo-V2.5** — [#137](https://github.com/cacao-accounting/cacao-accounting/issues/137)

**Caso de prueba:**
1. Recibir 10 uds a $100
2. Reconciliar a 8 uds a $120
3. Verificar capas FIFO divergen de stock físico

---

## MATRIZ DE PRIORIDADES CONSOLIDADA

| Prioridad | S2P | O2C | R2R | CAS | INV | Total |
|-----------|-----|-----|-----|-----|-----|-------|
| **ALTA** | 01,02,04,07,10,11,12 | 03,07,08,16,18,20 | 01,03,05,06,07,08,11,12,14 | 01,02,06,10,13,14 | 06,07,25 | **31** |
| **MEDIA** | 03,06,08,09,13,15,17,18,20 | 01,02,04,05,06,09,11,13,14,15,17,22,28 | 02,04,09,10,13,15,16 | 03,04,05,07,08,12,15,16 | 01,03,04,10,22 | **44** |
| **BAJA** | 05,14,16,19 | 10,12,21 | — | 09,11,17 | 02,05,11,21 | **14** |
| **TOTAL** | **20** | **22** | **16** | **17** | **14** | **89** |

---

## DISTRIBUCIÓN POR RIESGO

```
ALTO  ████████████████████████████████  31 (35%)
MEDIO ██████████████████████████████████████████████  44 (49%)
BAJO  ██████████████  14 (16%)
```

---

## LEYENDA

| Símbolo | Significado |
|---------|-------------|
| **ALTO** | Pérdida financiera directa, violación de integridad de datos, riesgo de fraude |
| **MEDIO** | Impacto operativo, UX deficiente, pérdida de trazabilidad |
| **BAJO** | Calidad de código, mejoras cosméticas, casos límite |

---