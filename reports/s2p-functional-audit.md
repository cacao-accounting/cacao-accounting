# INFORME DE AUDITORÍA FUNCIONAL — SOURCE TO PAY (S2P)

**Fecha:** 2026-07-09
**Alcance:** Purchase Request → Supplier Quotation → Purchase Quotation → Purchase Order → Purchase Receipt → Purchase Invoice → Payment
**Módulo:** Compras
**Versión del código:** commits hasta `487cd6e`

---

## RESUMEN EJECUTIVO

| Categoría | Cantidad |
|-----------|----------|
| Riesgo ALTO | 6 |
| Riesgo MEDIO | 10 |
| Riesgo BAJO | 4 |
| **Total** | **20** |

---

## HALLAZGOS DETALLADOS

### S2P-01 [ALTO] — Sin verificación de relaciones activas al cancelar documentos no financieros

**Descripción:** Los handlers de cancelación de PurchaseRequest, SupplierQuotation, PurchaseQuotation y PurchaseReceipt no llaman a `has_active_source_relations()` antes de transicionar `docstatus` a 2. Solo PurchaseOrder realiza esta verificación.

**Impacto:** Violación de integridad referencial. Un documento cancelado puede tener hijos activos (ej. PR cancelada con OCs activas).

**Recomendación:** Agregar `has_active_source_relations()` al inicio de cada handler de cancelación, replicando el patrón existente en `compras_orden_compra_cancel`.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:454-470` (PR cancel — sin check)
- `cacao_accounting/compras/__init__.py:911-927` (SupplierQuotation cancel — sin check)
- `cacao_accounting/compras/__init__.py:2200-2216` (PurchaseQuotation cancel — sin check)
- `cacao_accounting/compras/__init__.py:2617-2637` (PurchaseReceipt cancel — sin check)
- `cacao_accounting/compras/__init__.py:2257-2259` (PO cancel — SÍ tiene el check, patrón de contraste)

**Caso de prueba:**
1. Crear y aprobar una Purchase Request (PR-001)
2. Crear y aprobar una Purchase Order (PO-001) desde PR-001
3. Intentar cancelar PR-001
4. Assert: cancelación bloqueada con mensaje "No se puede cancelar porque tiene documentos activos"

---

### S2P-02 — ALTO — `log_create` no se llama en la creación de la mayoría de documentos

**Descripción:** Solo PurchaseReceipt llama a `log_create()`. Los demás tipos documentales (PR, SQ, PO, PQ, PI) crean el documento sin registrar el evento "created" en auditoría.

**Impacto:** Trazabilidad incompleta. No se puede determinar quién creó cada documento ni cuándo. Riesgo de cumplimiento SOX/auditoría.

**Recomendación:** Agregar `log_create(registro)` después de `database.session.commit()` en todos los handlers de creación.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:2336` — único call site de `log_create`
- Todos los demás paths de creación carecen de `log_create`

**Caso de prueba:**
1. Crear una nueva Purchase Invoice
2. Consultar `AuditTrail` para ese document_id
3. Assert: al menos un registro con action="created"

---

### S2P-03 — MEDIO — `log_update` no se llama en edición de PR, SQ, PO

**Descripción:** Los handlers de edición de PR, SupplierQuotation y PurchaseOrder guardan cambios sin llamar a `log_update()`. PQ, Receipt e Invoice SÍ lo hacen.

**Impacto:** Los cambios a estos documentos después de creados son invisibles en la pista de auditoría.

**Recomendación:** Capturar `before_state` con `_capture_purchase_state` y llamar `log_update(registro, before=before_state, after=after_state)` en cada handler de edición.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:318-336` (PR edit — sin `log_update`)
- `cacao_accounting/compras/__init__.py:733-752` (SQ edit — sin `log_update`)
- `cacao_accounting/compras/__init__.py:1781-1804` (PO edit — sin `log_update`)
- Contraste: PQ (lin. 2022-2045), Receipt (lin. 2463-2486), Invoice (lin. 2997-3035) SÍ tienen `log_update`

---

### S2P-04 — ALTO — Three-way match omitido cuando Factura salta Recepción (PO → Invoice directo)

**Descripción:** El flujo permitido `purchase_order → purchase_invoice` permite crear factura directa desde OC sin recepción intermedia. `_validate_invoice_quantities_against_receipt()` solo itera relaciones con `source_type="purchase_receipt"`. Si la factura no tiene relaciones de recepción, el loop nunca se ejecuta y no hay protección contra sobre-facturación contra la OC.

**Impacto:** Un proveedor puede ser facturado y pagado por cantidades que exceden la orden de compra. Riesgo de pérdida financiera.

**Recomendación:** Extender la validación para también verificar contra la OC cuando la factura tiene `purchase_order_id` pero no relación de recepción. O forzar three-way match obligatorio controlado por flag de compañía.

**Evidencia:**
- `cacao_accounting/document_flow/registry.py:694` — flujo PO→Invoice permitido
- `cacao_accounting/compras/__init__.py:2564-2586` — validación solo contra receipt relations
- `cacao_accounting/compras/__init__.py:3094-3126` — submit handler no valida contra PO

**Caso de prueba:**
1. Crear y aprobar PO-001 para Item-A, qty=10
2. Crear Purchase Invoice directa desde PO-001 para Item-A, qty=15
3. Aprobar la factura
4. Assert: aprobación rechazada con error de sobrefacturación

---

### S2P-05 — BAJO: Validación de cantidades solo en submit, no en draft/edit

**Descripción:** Las validaciones de sobre-recepción y sobre-facturación solo se ejecutan al aprobar (submit), no al guardar borrador o editar.

**Impacto:** UX pobre — los usuarios no detectan discrepancias de cantidad hasta el momento de aprobar.

**Recomendación:** Agregar validación server-side en handlers de POST para creación/edición, y validación client-side con Alpine.js.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:2309-2342` — creación receipt sin validación
- `cacao_accounting/compras/__init__.py:2463-2486` — edición receipt sin validación
- `cacao_accounting/compras/__init__.py:2589-2614` — submit receipt SÍ valida

---

### S2P-06 — MEDIO: `supplier_name` no establecido en Purchase Receipt

**Descripción:** Al crear Recepción, `supplier_name` no se puebla desde el registro del proveedor. El handler de edición tampoco lo establece.

**Impacto:** Listados y vistas de detalle muestran nombre de proveedor vacío para recepciones.

**Recomendación:** Agregar `supplier_name=supplier.name if supplier else None` en el handler de creación.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:2311-2318` — sin `supplier_name`
- Contraste: PO creación línea 1749 SÍ tiene `supplier_name`

---

### S2P-07 — ALTO: Tipo de cambio perdido al editar Purchase Invoice multimoneda

**Descripción:** En `_handle_purchase_invoice_edit_post`, `base_total`, `grand_total`, `base_grand_total`, `outstanding_amount` y `base_outstanding_amount` se establecen a `total` sin aplicar el tipo de cambio.

**Impacto:** Editar una factura multimoneda resetea los montos base a la moneda de transacción, asumiendo tasa 1:1. Esto causa posting GL incorrecto.

**Recomendación:** Recalcular exchange rate y montos base usando la misma lógica de creación: `_compute_base_amounts(total, fx_rate)`.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:3020-3025` — edit handler usa `total` directamente
- `cacao_accounting/compras/__init__.py:2873-2881` — creación SÍ aplica exchange rate

**Caso de prueba:**
1. Crear Factura en USD para compañía con moneda base EUR, grand_total=100 USD, rate=0.85
2. Editar la factura (cambiar un remark), guardar
3. Assert: `base_grand_total` ≈ 85 EUR, no 100 EUR

---

### S2P-08 — MEDIO: Handlers de duplicado pierden tipo de cambio (PO, Invoice)

**Descripción:** Los handlers de duplicado para PO y PI establecen `base_total = total` (1:1) en lugar de preservar o recalcular el exchange rate del documento original.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:1853` — `duplicada.base_total = total`
- `cacao_accounting/compras/__init__.py:3084-3088` — mismos montos base a `total`

---

### S2P-09 — MEDIO: `_validate_supplier_invoice_flags` omite validación cuando `CompanyParty` es None

**Descripción:** Si no existe fila `CompanyParty` para el proveedor/compañía, la función retorna tempranamente sin validar los flags, permitiendo facturas sin orden/recepción.

**Recomendación:** Tratar settings ausentes como la configuración más restrictiva (denegar factura sin orden).

**Evidencia:**
- `cacao_accounting/compras/__init__.py:2824-2825` — `if settings is None: return`

---

### S2P-10 — ALTO: Condición de carrera en asignación directa de pago (sin `with_for_update`)

**Descripción:** `_apply_payment_target_line` lee `compute_outstanding_amount` sin bloquear la fila con `with_for_update()`. Dos asignaciones concurrentes contra la misma factura podrían ver el mismo saldo y ambas prosperar.

**Evidencia:**
- `cacao_accounting/document_flow/service.py:1640-1664` — sin row lock
- Contraste: `cacao_accounting/document_flow/service.py:742` — SÍ usa `with_for_update()`

---

### S2P-11 — ALTO: `except Exception` genérico en `_purchase_exchange_rate` silencia errores

**Descripción:** La función envuelve `_lookup_exchange_rate` en un `except Exception: return Decimal("1")`. Cualquier error se traga silenciosamente y retorna 1:1.

**Recomendación:** Capturar solo la excepción esperada, loguear el error con LOGURU, y mostrar flash warning al usuario.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:2798-2799`

---

### S2P-12 — ALTO: Cancelación de Invoice no verifica referencias de pago activas

**Descripción:** `compras_factura_compra_cancel` no consulta pagos activos contra la factura antes de cancelar. Una factura con pagos parciales puede cancelarse, dejando los pagos huérfanos.

**Evidencia:**
- `cacao_accounting/compras/__init__.py:3129-3150` — sin verificación de pagos

---

### S2P-13 — MEDIO: `get_document_type` lanza KeyError para tipos desconocidos

**Evidencia:**
- `cacao_accounting/document_flow/registry.py:748-751`

---

### S2P-14 — BAJO: Creación de relaciones documentales sin auditoría

**Evidencia:**
- `cacao_accounting/document_flow/service.py:1200-1264`

---

### S2P-15 — MEDIO: Propagación de caché transitiva incompleta al cancelar Recepción

**Evidencia:**
- `cacao_accounting/document_flow/service.py:1138-1143` — solo forward propagation

---

### S2P-16 — BAJO: `supplier_invoice_no` sobrescrito por formulario vacío

**Evidencia:**
- `cacao_accounting/compras/__init__.py:3009`

---

### S2P-17 — MEDIO: Validaciones de Recepción/Factura se omiten cuando no hay enlace explícito

**Evidencia:**
- `cacao_accounting/compras/__init__.py:2539-2561`

---

### S2P-18 — MEDIO: Sin validación de existencia/actividad de almacén en Recepción

**Evidencia:**
- `cacao_accounting/compras/__init__.py:1469-1477`

---

### S2P-19 — BAJO: Sin `log_create` en `create_target_document` (API/bulk flow)

**Evidencia:**
- `cacao_accounting/document_flow/service.py:1548-1571`

---

### S2P-20 — MEDIO: Cancelación de Recepción no verifica facturas downstream

**Evidencia:**
- `cacao_accounting/compras/__init__.py:2617-2637`

---

## MATRIZ DE PRIORIDADES

| Prioridad | Hallazgos |
|-----------|-----------|
| **ALTA** | S2P-01, S2P-02, S2P-04, S2P-07, S2P-10, S2P-11, S2P-12 |
| **MEDIA** | S2P-03, S2P-06, S2P-08, S2P-09, S2P-13, S2P-15, S2P-17, S2P-18, S2P-20 |
| **BAJA** | S2P-05, S2P-14, S2P-16, S2P-19 |