# ISSUES.md — REGISTRO DE AUDITORÍA FUNCIONAL ERP

**Última actualización:** 2026-07-10 (Revisión y limpieza de auditoría)
**Versión del código auditado:** HEAD `5a1374d`

---

## TABLA RESUMEN

| ID | Descripción | Status | GitHub | Commits |
|---|---|---|---|---|
| **S2P-02** | Sin `log_create` en rutas de duplicado y `create_target_document` | CORREGIDO | [#120](https://github.com/cacao-accounting/cacao-accounting/issues/120) | `0381b76` |
| **S2P-04** | Three-way match omitido cuando Factura salta Recepción (PO → Invoice directo) | FALSO POSITIVO | [#121](https://github.com/cacao-accounting/cacao-accounting/issues/121) | `5a1374d` |
| **S2P-05** | Validación de cantidades solo en submit, no en draft/edit | CORREGIDO | [#178](https://github.com/cacao-accounting/cacao-accounting/issues/178) | `d6e2200` |
| **S2P-06** | `supplier_name` no establecido en edición de Purchase Receipt | CORREGIDO | [#160](https://github.com/cacao-accounting/cacao-accounting/issues/160) | `fff2f81` |
| **S2P-08** | Handlers de duplicado pierden tipo de cambio (PO, Invoice) | FALSO POSITIVO | [#141](https://github.com/cacao-accounting/cacao-accounting/issues/141) | `d93b09e` |
| **S2P-11** | `except Exception` genérico en `_purchase_exchange_rate` silencia errores | FALSO POSITIVO | [#123](https://github.com/cacao-accounting/cacao-accounting/issues/123) | `5a1374d` |
| **S2P-15** | Propagación de caché transitiva incompleta al cancelar Recepción | CORREGIDO | [#179](https://github.com/cacao-accounting/cacao-accounting/issues/179) | `fix-S2P-15` |
| **S2P-16** | `supplier_invoice_no` sobrescrito por formulario vacío en edición | CORREGIDO | [#177](https://github.com/cacao-accounting/cacao-accounting/issues/177) | `fff2f81` |
| **S2P-17** | Validaciones de Recepción/Factura se omiten sin enlace explícito | CORREGIDO | [#180](https://github.com/cacao-accounting/cacao-accounting/issues/180) | `fff2f81` |
| **S2P-18** | Sin validación de existencia/actividad de almacén en Recepción | FALSO POSITIVO | [#163](https://github.com/cacao-accounting/cacao-accounting/issues/163) | `5a1374d` |
| **S2P-19** | Sin `log_create` en `create_target_document` (API/bulk) | CORREGIDO | [#181](https://github.com/cacao-accounting/cacao-accounting/issues/181) | `0381b76` |
| **S2P-20** | Cancelación de Recepción no verifica facturas downstream con pago asociado | FALSO POSITIVO | [#143](https://github.com/cacao-accounting/cacao-accounting/issues/143) | `5a1374d` |
| **S2P-21** | Control presupuestario configurable (global) en aprobación PR/PO: do_nothing/notify/block | PENDIENTE | [#188](https://github.com/cacao-accounting/cacao-accounting/issues/188) | — |
| **S2P-22** | Sin automatización de punto de reorden | PENDIENTE | [#189](https://github.com/cacao-accounting/cacao-accounting/issues/189) | — |
| **O2C-01** | SalesRequest submit usa `require_party=False` | FALSO POSITIVO | — | — |
| **O2C-02** | Secuencia de cancelación inconsistente en SalesInvoice | FALSO POSITIVO | — | — |
| **O2C-04** | `_release_reservation_for_delivery_note` no es idempotente | CORREGIDO | [#139](https://github.com/cacao-accounting/cacao-accounting/issues/139) | `d794cfa` |
| **O2C-06** | Validación de precio en edición bloquea guardar borrador | CORREGIDO | [#182](https://github.com/cacao-accounting/cacao-accounting/issues/182) | `d794cfa` |
| **O2C-09** | SalesQuotation cancel no verifica relaciones descendientes activas | FALSO POSITIVO | [#145](https://github.com/cacao-accounting/cacao-accounting/issues/145) | `5a1374d` |
| **O2C-10** | `_handle_sales_order_new_post` retorna None en error | CORREGIDO | [#183](https://github.com/cacao-accounting/cacao-accounting/issues/183) | `d794cfa` |
| **O2C-11** | Edición de SalesOrder/SalesRequest sin auditoría | FALSO POSITIVO | [#146](https://github.com/cacao-accounting/cacao-accounting/issues/146) | `5a1374d` |
| **O2C-12** | Inconsistencia de naming en parámetros | FALSO POSITIVO | — | — |
| **O2C-13** | `create_document_relation` no valida docstatus de origen | CORREGIDO | [#184](https://github.com/cacao-accounting/cacao-accounting/issues/184) | `45611d0` |
| **O2C-14** | `validate_submit_prerequisites` no valida rate > 0, amount > 0 | CORREGIDO | [#185](https://github.com/cacao-accounting/cacao-accounting/issues/185) | `d88a578` |
| **O2C-17** | DeliveryNote `is_return` sin lógica de reversión real | FALSO POSITIVO | — | — |
| **O2C-18** | Nota de Crédito/Débito: `reversal_of` no validado en edición | CORREGIDO | [#126](https://github.com/cacao-accounting/cacao-accounting/issues/126) | `d794cfa` |
| **O2C-21** | `_form_decimal` acoplada a `request.form` | FALSO POSITIVO | — | — |
| **O2C-22** | `validate_submit_prerequisites` exige almacén para ítems de servicio | CORREGIDO | [#147](https://github.com/cacao-accounting/cacao-accounting/issues/147) | `d88a578` |
| **O2C-23** | Sin validación de límite de crédito en documentos de venta | PENDIENTE | [#190](https://github.com/cacao-accounting/cacao-accounting/issues/190) | — |
| **O2C-24** | Precios negativos permitidos en documentos de venta | PENDIENTE | [#191](https://github.com/cacao-accounting/cacao-accounting/issues/191) | — |
| **R2R-01** | Validación de balance usa signed `line.value` después de redondeo por línea | FALSO POSITIVO | — | — |
| **R2R-02** | Validación de período inconsistente en revaluación cambiaria | FALSO POSITIVO | — | — |
| **R2R-04** | `duplicate_journal_as_reversal_draft` bloquea reversiones mismo período | FALSO POSITIVO | [#174](https://github.com/cacao-accounting/cacao-accounting/issues/174) | — |
| **R2R-06** | Revaluación cambiaria sin auditoría | FALSO POSITIVO | [#149](https://github.com/cacao-accounting/cacao-accounting/issues/149) | `5a1374d` |
| **R2R-07** | Cierre de período sin auditoría | FALSO POSITIVO | [#164](https://github.com/cacao-accounting/cacao-accounting/issues/164) | `5a1374d` |
| **R2R-08** | Documentos operativos sin auditoría de submit/cancel | FALSO POSITIVO | — | — |
| **R2R-10** | Sin control presupuestario en posting | PENDIENTE | [#186](https://github.com/cacao-accounting/cacao-accounting/issues/186) | — |
| **R2R-11** | Sin protección contra doble posting en funciones `post_*` individuales | CORREGIDO | [#130](https://github.com/cacao-accounting/cacao-accounting/issues/130) | `ab45e31` |
| **R2R-13** | Linking item-to-entry en revaluación frágil (orden posicional) | CORREGIDO | [#187](https://github.com/cacao-accounting/cacao-accounting/issues/187) | `ab45e31` |
| **R2R-17** | Sin validación de balance en moneda de transacción | PENDIENTE | [#192](https://github.com/cacao-accounting/cacao-accounting/issues/192) | — |
| **R2R-18** | Sin consolidación multi-empresa | PENDIENTE | [#193](https://github.com/cacao-accounting/cacao-accounting/issues/193) | — |
| **CAS-05** | Sin saldo en tiempo real en BankAccount | FALSO POSITIVO | — | — |
| **CAS-08** | Descuento por pronto pago usa `posting_date` no fecha de factura | FALSO POSITIVO | — | — |
| **CAS-09** | Descuento por pronto pago no accesible en formulario de pago | FALSO POSITIVO | — | — |
| **CAS-11** | Sin validación de asignación mínima | FALSO POSITIVO | — | — |
| **CAS-12** | Sin validación de cuenta GL al aprobar pago | FALSO POSITIVO | — | — |
| **CAS-13** | `_cash_consumed` cero permite eludir verificación de saldo restante | CORREGIDO | [#134](https://github.com/cacao-accounting/cacao-accounting/issues/134) | `189da6e` |
| **CAS-16** | PaymentReference rows huérfanos al cancelar pago | FALSO POSITIVO | — | — |
| **CAS-17** | `_payment_numbering_defaults` no valida compañía del banco | FALSO POSITIVO | — | — |
| **CAS-18** | Conciliación bancaria no valida docstatus del pago destino | PENDIENTE | [#194](https://github.com/cacao-accounting/cacao-accounting/issues/194) | — |
| **CAS-19** | Sin pronóstico de flujo de caja | PENDIENTE | [#195](https://github.com/cacao-accounting/cacao-accounting/issues/195) | — |
| **CAS-20** | Sin alerta de pagos duplicados por monto y proveedor cercano | PENDIENTE | [#196](https://github.com/cacao-accounting/cacao-accounting/issues/196) | — |
| **INV-01** | Verificación de stock negativo ocurre después de upsert de StockBin | FALSO POSITIVO (CERRADO) | [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) | — |
| **INV-10** | `reserved_qty` puede desviarse por movimientos fuera del flujo O2C | CORREGIDO | [#159](https://github.com/cacao-accounting/cacao-accounting/issues/159) | clamp en `_upsert_stock_bin` |
| **INV-21** | `valuation_rate` se resetea a 0 cuando qty=0 | FALSO POSITIVO | — | — |
| **INV-22** | Relaciones documentales creadas en draft, eliminadas en edición | FALSO POSITIVO | — | — |
| **INV-26** | Sin alerta de punto de reorden en movimientos de salida | PENDIENTE | [#197](https://github.com/cacao-accounting/cacao-accounting/issues/197) | — |
| **SEC-01** | Ausencia de validación de propiedad (created_by) en submit/cancel | PENDIENTE | [#198](https://github.com/cacao-accounting/cacao-accounting/issues/198) | — |
| **SEC-02** | Eliminación física de líneas de documento al editar (sin trazabilidad) | PENDIENTE | [#199](https://github.com/cacao-accounting/cacao-accounting/issues/199) | — |

**Totales (revisión 2026-07-10, HEAD `5a1374d`):** 0 VERIFICADO · 29 FALSO POSITIVO · 1 FALSO POSITIVO (CERRADO) · 13 PENDIENTE · 46 CORREGIDO (archivados en GitHub; no requieren seguimiento en este archivo — ver sección de referencia al final).

> Nota de auditoría 2026-07-10: contraste de los 94 hallazgos contra el código fuente. Se reclasificaron como FALSO POSITIVO los IDs S2P-04, S2P-08, S2P-11, S2P-18, S2P-20, O2C-09, O2C-11, R2R-06, R2R-07. Se marcaron CORREGIDO (verificado en código) S2P-01/03/07/09/10/12/13/14, O2C-07/08/20, R2R-03/05/09/12/14/15/16, CAS-01/02/03/04/06/07/10/14/15, INV-02/03/04/05/06/07/11/25. O2C-04, O2C-18, R2R-11, R2R-13 y CAS-13 fueron corregidos en iteraciones posteriores.


---

## TEMPLATE DE ISSUE PARA FUTURAS REVISIONES

```markdown
### ID-[XXX] [SEVERIDAD] — Título descriptivo

**Descripción:**
[Comportamiento actual vs esperado]

**Impacto:**
[Consecuencia funcional, financiera o de integridad]

**Recomendación:**
[Qué debe corregirse y cómo]

**Módulo/Archivo:**
[cacao_accounting/<modulo>/<archivo>.py:<líneas>]

**Caso de prueba:**
[Pasos para reproducir / test name]

**Veredicto:** [PENDIENTE | VERIFICADO | FALSO POSITIVO]
**Confianza:** [Muy Alto | Alto | Medio | Bajo]
**GitHub Issue:** [#NNN](https://github.com/cacao-accounting/cacao-accounting/issues/NNN)
**Commit(s):** `abc1234`, `def5678`
```

### Guía rápida de severidad

| Severidad | Criterio |
|-----------|----------|
| ALTO | Pérdida financiera directa, violación de integridad de datos, riesgo de fraude |
| MEDIO | Impacto operativo, UX deficiente, pérdida de trazabilidad |
| BAJO | Calidad de código, mejoras cosméticas, casos límite |

### Estados de veredicto

- **PENDIENTE** — Hallazgo inicial, no revisado aún
- **VERIFICADO** — Confirmado como error real tras revisión independiente
- **FALSO POSITIVO** — Descartado tras análisis (código correcto)
- **FALSO POSITIVO (CERRADO)** — Cerrado formalmente con comentario en el issue

---

## HALLAZGOS POR MÓDULO

---

### 1. SOURCE TO PAY (S2P) | PROCESO DE ABASTECIMIENTO Y PAGO

**Flujo auditado:** Solicitud de Compra → Cotización → Orden de Compra → Recepción → Factura → Pago

---

#### S2P-02 [MEDIO] — Sin `log_create` en rutas de duplicado y `create_target_document`

**Descripción:** Las rutas principales de creación (`/new`) llaman correctamente a `log_create()`, pero las 6 rutas de duplicado (`compras_*_duplicar`) y `create_target_document` en `document_flow/service.py` no registran auditoría de creación.

**Impacto:** Documentos creados por duplicado o vía API carecen de trazabilidad de creación.

**Recomendación:** Agregar `log_create()` en todas las rutas de duplicado y en `_create_target_header`.

**Módulo/Archivo:** `compras/__init__.py:390-434`, `document_flow/service.py:1495-1531`

**Caso de prueba:** Duplicar una PO y verificar `AuditLog` con `action="create"`.

---

#### S2P-05 [MEDIO] — Validación de cantidades solo en submit, no en draft/edit

**Descripción:** `qty > 0` solo valida en `validate_submit_prerequisites` (submit). Draft save no valida cantidades.

**Impacto:** Borradores pueden guardarse con qty=0 o negativa, detectándose recién al aprobar.

**Recomendación:** Agregar validación de `qty > 0` en funciones `_save_*_items`.

**Módulo/Archivo:** `document_flow/validation.py:40-43`, `compras/__init__.py:1374,1434,1461,1491,1531`

**Caso de prueba:** Guardar borrador PO con qty=0 → debe rechazar.

---

#### S2P-06 [MEDIO] — `supplier_name` no actualizado en edición de Purchase Receipt

**Descripción:** `_handle_purchase_receipt_edit_post` omite actualizar `supplier_name` al cambiar `supplier_id`.

**Impacto:** Si cambia el proveedor en edición, `supplier_name` queda desactualizado en reportes.

**Recomendación:** Agregar `registro.supplier_name = supplier.name if supplier else None`.

**Módulo/Archivo:** `compras/__init__.py:2520-2543`

**Caso de prueba:** Editar recepción cambiando proveedor A→B, verificar `supplier_name` = B.

---

#### S2P-16 [MEDIO] — `supplier_invoice_no` sobrescrito por formulario vacío en edición

**Descripción:** `supplier_invoice_no` se actualiza sin guarda `or None` (L3089). Ausente del `initialHeader` en `transaction_config` de edición.

**Impacto:** Número de factura del proveedor puede perderse al editar.

**Recomendación:** Usar `request.form.get("supplier_invoice_no") or registro.supplier_invoice_no`. Incluir en `initialHeader`.

**Módulo/Archivo:** `compras/__init__.py:3089`

**Caso de prueba:** Editar factura con `supplier_invoice_no` poblado → valor preservado.

---

#### S2P-17 [ALTO] — Validaciones de Recepción/Factura se omiten sin enlace explícito

**Descripción:** `_validate_receipt_quantities_against_po` y `_validate_invoice_quantities_against_receipt` iteran `DocumentRelation`. Sin relaciones (standalone), el `for` nunca ejecuta cuerpo → no hay validación de sobre-recepción/sobre-facturación.

**Impacto:** Se pueden recibir/facturar cantidades sin control si no se vincula explícitamente a PO/recepción.

**Recomendación:** Validar banderas del proveedor (`allow_purchase_invoice_without_order`) y exigir vínculo si es requerido.

**Módulo/Archivo:** `compras/__init__.py:2596-2618`, `2621-2660`

**Caso de prueba:** Proveedor con `allow_purchase_invoice_without_receipt=False`, crear invoice sin vínculo a recepción → debe rechazar.

---

#### S2P-19 [MEDIO] — Sin `log_create` en `create_target_document` (API/bulk)

**Descripción:** `_create_target_header` persiste documento sin llamar `log_create()`.

**Impacto:** Trazabilidad incompleta para documentos generados por flujo documental.

**Recomendación:** Agregar `log_create(target)` en `_create_target_header` y `_create_payment_target`.

**Módulo/Archivo:** `document_flow/service.py:1495-1531`

**Caso de prueba:** Crear DN desde SO vía flujo documental → `AuditLog` debe tener `action="create"`.

---

#### S2P-21 [ALTO] — Sin control presupuestario en aprobación de PR/PO

**Descripción:** El módulo de presupuestos no está integrado con compras. `compras_solicitud_compra_submit` y `compras_orden_compra_submit` no consultan presupuesto.

**Impacto:** Se aprueban compras que exceden el presupuesto sin alerta ni bloqueo.

**Recomendación:** Validación configurable por compañía: verificar presupuesto vs cuentas contables y centro de costo. Modo advertencia o bloqueante.

**Módulo/Archivo:** `compras/__init__.py:440-467` (PR submit), `2272-2294` (PO submit)

**Caso de prueba:** Presupuesto $1,000, aprobar PO por $1,500 → debe rechazar o advertir.

---

#### S2P-22 [MEDIO] — Sin automatización de punto de reorden

**Descripción:** `Item` tiene campos `reorder_level` pero no existe proceso que los consuma.

**Impacto:** Datos maestros de reorden sin efecto operativo. Rupturas de stock no detectadas.

**Recomendación:** Implementar servicio que verifique `actual_qty < reorder_level` tras cada salida y genere alerta o PR.

**Módulo/Archivo:** `database/__init__.py:904-906`

**Caso de prueba:** Item con `reorder_level=10`, stock=15, consumir 10 unidades → alerta de reorden.

---

### 2. ORDER TO CASH (O2C) | PROCESO COMERCIAL

**Flujo auditado:** Cotización → Orden de Venta → Nota de Entrega → Factura → Pago → Devolución

---

#### O2C-04 [MEDIO] — `_release_reservation_for_delivery_note` no es idempotente

**Descripción:** Resta `item.qty` de `reserved_qty` sin verificar si ya se ejecutó. Segunda llamada corrompe la reserva.

**Impacto:** En reintentos, `reserved_qty` se reduce múltiples veces → sobre-venta o bloqueo de liberación.

**Recomendación:** Agregar flag `reservation_released` en DN o check de idempotencia.

**Módulo/Archivo:** `ventas/__init__.py:205-226`

**Caso de prueba:** Aprobar DN, llamar `_release_reservation_for_delivery_note` dos veces → segunda llamada no debe cambiar `reserved_qty`.

---

#### O2C-06 [ALTO] — Validación de precio en edición bloquea guardar borrador

**Descripción:** `_validate_invoice_prices_against_source` se ejecuta en edición (draft). Si precios difieren de OV, lanza `ValueError` que revierte el guardado.

**Impacto:** Usuario no puede guardar borrador con precios tentativos. Bloquea operación normal.

**Recomendación:** Mover validación de precios a submit, no ejecutar en edit handler.

**Módulo/Archivo:** `ventas/__init__.py:2481-2516`

**Caso de prueba:** OV precio $100, factura borrador $110 → guardar borrador debe funcionar (validar al aprobar).

---

#### O2C-10 [MEDIO] — Captura solo `IdentifierConfigurationError` en creación de OV

**Descripción:** `_handle_sales_order_new_post` captura solo `IdentifierConfigurationError`. Otros errores → 500.

**Impacto:** Errores de datos inválidos producen error 500 en lugar de mensaje amigable.

**Recomendación:** Capturar `ValueError` y retornar redirect con flash. Capturar `Exception` como fallback.

**Módulo/Archivo:** `ventas/__init__.py:1348-1382`

**Caso de prueba:** Crear OV con fecha mal formateada → debe redirigir al formulario con error flash.

---

#### O2C-13 [ALTO] — `create_document_relation` no valida docstatus de origen ni destino

**Descripción:** No verifica `source.docstatus == 1` ni `target.docstatus == 0`. Relaciones desde cancelados o hacia aprobados son posibles.

**Impacto:** Documentos cancelados pueden alimentar hijos. Documentos aprobados pueden recibir relaciones adicionales. Violación de integridad del flujo.

**Recomendación:** Agregar validaciones de docstatus en `create_document_relation`.

**Módulo/Archivo:** `document_flow/service.py:1225-1297`

**Caso de prueba:** Cancelar OV, crear DN desde OV cancelada → debe rechazar.

---

#### O2C-14 [MEDIO] — `validate_submit_prerequisites` no valida rate > 0 ni amount > 0

**Descripción:** Valida `qty > 0` pero omite `rate > 0` y `amount > 0`.

**Impacto:** Documentos con valor cero o negativo pueden aprobarse, generando asientos sin sentido económico.

**Recomendación:** Validar `rate > 0` y `amount != 0` (o `amount > 0`).

**Módulo/Archivo:** `document_flow/validation.py:7-53`

**Caso de prueba:** OV con rate=0, qty=10 → rechazar aprobación.

---

#### O2C-18 [MEDIO] — `reversal_of` no re-validado en edición de NC/ND

**Descripción:** En creación valida `reversal_of` contra cliente y compañía. En edición, si cambia `customer_id`, `reversal_of` queda apuntando a factura de otro cliente.

**Impacto:** Inconsistencia referencial. `outstanding_amount` se ajusta incorrectamente.

**Recomendación:** Re-validar `reversal_of` en edición cuando `customer_id` o `company` cambian.

**Módulo/Archivo:** `ventas/__init__.py:2481-2504`

**Caso de prueba:** NC para cliente A vinculada a FA-001 (cliente A). Editar a cliente B → rechazar o re-validar.

---

#### O2C-22 [MEDIO] — `validate_submit_prerequisites` exige almacén para ítems de servicio

**Descripción:** `require_warehouse=True` exige almacén para TODOS los ítems, incluso servicios (`is_stock_item=False`).

**Impacto:** DN con ítems de servicio no pueden aprobarse sin asignar almacén ficticio.

**Recomendación:** Validar almacén solo para `is_stock_item=True`.

**Módulo/Archivo:** `document_flow/validation.py:44-53`

**Caso de prueba:** DN con ítem servicio (sin almacén) → aprobación exitosa.

---

#### O2C-23 [ALTO] — Sin validación de límite de crédito en documentos de venta

**Descripción:** `Party.credit_limit` y `CompanyParty.block_overdue` existen pero no se consultan en submit de OV/facturas. Cero referencias en `ventas/`.

**Impacto:** Se aprueban ventas a clientes que exceden su límite de crédito. Riesgo de cuentas incobrables.

**Recomendación:** Validación configurable en submit de OV y facturas: calcular saldo pendiente vs `credit_limit`. Si `block_overdue` activo, bloquear si hay vencidas.

**Módulo/Archivo:** `ventas/__init__.py:1901-1919`, `2575-2606`. `database/__init__.py:842`

**Caso de prueba:** Cliente con `credit_limit=$1,000`, factura $800, nueva factura $400 → rechazar.

---

#### O2C-24 [MEDIO] — Precios negativos permitidos en documentos de venta

**Descripción:** `validate_submit_prerequisites` no valida `rate > 0`. Cotizaciones, OV, facturas pueden aprobarse con precios negativos.

**Impacto:** Manipulación de ingresos mediante precios negativos. Asientos contables invertidos no deseados.

**Recomendación:** Validar `rate > 0` (o `amount != 0`). Rate negativo solo con flag explícito.

**Módulo/Archivo:** `document_flow/validation.py:7-53`

**Caso de prueba:** Factura con rate=-$50 → rechazar aprobación.

---

### 3. RECORD TO REPORT (R2R) | PROCESO CONTABLE Y FINANCIERO

**Flujo auditado:** Asientos contables → Ledgers → Cierres → Reportes financieros

---

#### R2R-11 [ALTO] — Sin protección contra doble posting en `post_*` individuales

**Descripción:** `submit_document` tiene doble protección. Pero `post_purchase_receipt`, `post_delivery_note`, `post_comprobante_contable` carecen de `_has_active_gl_entries()`.

**Impacto:** Llamadas directas a estas funciones (bypassando `submit_document`) pueden duplicar GL entries.

**Recomendación:** Agregar `_has_active_gl_entries()` en las 3 funciones faltantes.

**Módulo/Archivo:** `contabilidad/posting.py:2240-2243`, `2327-2330`, `2403-2407`

**Caso de prueba:** Llamar `post_purchase_receipt(receipt)` dos veces → segunda debe fallar con `PostingError`.

---

#### R2R-13 [BAJO] — Linking item-to-entry en revaluación frágil (orden posicional)

**Descripción:** `_link_items_to_entries` usa `zip(items, entries[::2], strict=False)`. Correspondencia posicional frágil.

**Impacto:** Cambio en orden de generación rompe linking silenciosamente.

**Recomendación:** Usar `strict=True` y clave explícita para linking.

**Módulo/Archivo:** `contabilidad/exchange_revaluation_service.py:548`

---

#### R2R-17 [MEDIO] — Sin validación de balance en moneda de transacción

**Descripción:** `_assert_entries_balance` solo valida débito/crédito en moneda de compañía. No valida `debit_in_account_currency`/`credit_in_account_currency` por moneda.

**Impacto:** Documentos multimoneda pueden contabilizarse desbalanceados en moneda original.

**Recomendación:** Extender validación para balance por moneda de transacción.

**Módulo/Archivo:** `contabilidad/posting.py:408-415`

**Caso de prueba:** JE EUR: Débito EUR 100, Crédito EUR 99.99 → debe detectar desbalance en EUR.

---

#### R2R-18 [MEDIO] — Sin consolidación multi-empresa

**Descripción:** No existe funcionalidad de consolidación financiera. `ConsolidatedFinancialReport` es solo almacenamiento.

**Impacto:** Empresas multi-entidad no pueden generar reportes consolidados en el sistema.

**Recomendación:** Implementar consolidación con eliminación intercompañía y ajustes de moneda.

**Módulo/Archivo:** `database/__init__.py:2160`

---

### 4. GESTIÓN DE TESORERÍA (CASH MANAGEMENT)

**Flujo auditado:** Cobros → Pagos → Transferencias → Notas Débito/Crédito → Conciliación Bancaria

---

#### CAS-18 [MEDIO] — Conciliación bancaria no valida docstatus del pago destino

**Descripción:** `_validate_reconciliation_match` y `_target_company` no verifican `docstatus == 1`.

**Impacto:** Se concilian transacciones contra pagos en borrador o cancelados. Distorsiona conciliación bancaria.

**Recomendación:** Validar `payment.docstatus == 1` en `_target_company` y `_target_amount` para `payment_entry`.

**Módulo/Archivo:** `bancos/reconciliation_service.py:130-143`, `335-347`

**Caso de prueba:** PaymentEntry borrador $100, BankTransaction $100 → conciliación debe rechazar.

---

#### CAS-19 [BAJO] — Sin pronóstico de flujo de caja

**Descripción:** No existe funcionalidad de proyección de flujo de caja.

**Impacto:** Gestión de tesorería reactiva sin visibilidad predictiva.

**Recomendación:** Implementar proyección considerando AR, AP y saldos bancarios.

---

#### CAS-20 [MEDIO] — Sin alerta de pagos duplicados

**Descripción:** No hay detección de pagos duplicados por (proveedor, monto, fechas cercanas).

**Impacto:** Riesgo de fraude o error: pagar misma factura dos veces.

**Recomendación:** Alertar si se crea pago al mismo proveedor por monto similar en N días.

---

### 5. GESTIÓN DE INVENTARIO

**Flujo auditado:** Recepción → Entrega → Traslados → Ajustes → Kardex → Valoración

---

#### INV-26 [MEDIO] — Sin alerta de punto de reorden en movimientos de salida

**Descripción:** Tras cada salida, no hay verificación de `actual_qty < reorder_level`.

**Impacto:** Rupturas de stock no detectadas.

**Recomendación:** Verificar `reorder_level` después de `_upsert_stock_bin` y emitir alerta.

**Módulo/Archivo:** `contabilidad/posting.py` (en `_create_stock_movement`)

---

### 6. SEGURIDAD Y AUDITORÍA (CROSS-MODULE)

---

#### SEC-01 [ALTO] — Ausencia de validación de propiedad en submit/cancel

**Descripción:** Ninguna ruta de submit/cancel verifica que el usuario sea el creador del documento. Cualquier usuario con acceso al módulo puede aprobar/cancelar documentos de otros.

**Impacto:** Riesgo de seguridad: usuarios no autorizados alteran flujo documental. Fraude potencial.

**Recomendación:** Agregar verificación configurable de `registro.created_by == current_user.id`.

**Módulo/Archivo:** Todas las rutas de submit/cancel en compras, ventas, inventario, bancos.

**Caso de prueba:** Usuario B aprueba PO creada por usuario A → debe denegar (o permitir según config).

---

#### SEC-02 [MEDIO] — Eliminación física de líneas al editar documentos (sin trazabilidad)

**Descripción:** `database.session.delete(item)` elimina líneas al editar. No se preservan valores originales en auditoría.

**Impacto:** Imposible auditar cambios en líneas de documentos. Violación de pista de auditoría.

**Recomendación:** Capturar snapshot JSON de líneas en `log_update`. Alternativa: borrado lógico.

**Módulo/Archivo:** `compras/__init__.py:1828-1831`, `ventas/__init__.py:2144,2497`, `inventario/__init__.py:1259-1261`

**Caso de prueba:** PO con items A($10) y B($20). Editar a A y C($30). `AuditLog` debe tener valores originales.

---

## REFERENCIA PARA FUTURAS AUDITORÍAS (no duplicar códigos/issues)

Los hallazgos con veredicto **CORREGIDO** fueron resueltos y archivados como issues cerrados en GitHub; ya no requieren seguimiento en este archivo. Para futuras auditorías usar los siguientes códigos/issues como punto de partida (no reutilizar los ya emitidos):

- **Siguiente número de issue de GitHub libre:** `#200`
- **Por componente (último código emitido → issue de GitHub):**
  - `S2P`: S2P-22 → #189 → siguiente código: **S2P-23**
  - `O2C`: O2C-24 → #191 → siguiente código: **O2C-25**
  - `R2R`: R2R-18 → #193 → siguiente código: **R2R-19**
  - `CAS`: CAS-20 → #196 → siguiente código: **CAS-21**
  - `INV`: INV-26 → #197 → siguiente código: **INV-27**
  - `SEC`: SEC-02 → #199 → siguiente código: **SEC-03**
  - `CROSS`: CROSS-02 → #118 → siguiente código: **CROSS-03**

> Nota: los issues `#175`–`#185` citados originalmente en este archivo apuntaban a pull requests o no existían; esos hallazgos se reemitieron como issues `#178`–`#199`.

---

## ANÁLISIS DE VEREDICTOS — REVISIÓN 2026-07-09

### Falsos positivos confirmados tras análisis de código

| ID | Veredicto Anterior | Confirmado | Fundamento |
|---|---|---|---|
| **S2P-03** | VERIFICADO → Corregido | LOG_UPDATE presente | Las 3 rutas de edición (PR, SQ, PO) llaman `log_update` con before/after state. |
| **S2P-07** | VERIFICADO → Corregido | Exchange rate recalculado | `_purchase_exchange_rate` recalcula desde `transaction_currency` preservado. |
| **S2P-13** | VERIFICADO → Corregido | KeyError capturado | `get_document_type` captura KeyError y lanza ValueError. |
| **S2P-09** | VERIFICADO → Corregido | CompanyParty=None manejado | Código ya lanza PostingError con `# S2P-09` explícito. |
| **O2C-01** | FALSO POSITIVO | Confirmado | Intentional: SalesRequest es documento interno sin cliente. |
| **O2C-02** | FALSO POSITIVO | Confirmado | Secuencia correcta: DN auto-generado no requiere reversion de relaciones propias. |
| **O2C-17** | FALSO POSITIVO | Confirmado | `is_return` sí tiene lógica via `_signed_amount` en posting. |
| **O2C-21** | FALSO POSITIVO | Confirmado | `_form_decimal` es helper de vista, acoplamiento intencional. |
| **R2R-01** | FALSO POSITIVO | Confirmado | Balance sobre original_value correcto para >99% moneda local. |
| **R2R-02** | FALSO POSITIVO | Confirmado | Revaluation tiene su propia validación de período, más estricta. |
| **R2R-04** | FALSO POSITIVO | Confirmado | Reversión entre períodos por IAS/IFRS. Documentado explícitamente. |
| **R2R-08** | FALSO POSITIVO | Confirmado | `log_submit`/`log_cancel` en TODAS las rutas. |
| **CAS-05** | FALSO POSITIVO | Confirmado | Saldo deriva de GL (doble entrada). Diseño intencional. |
| **CAS-08** | FALSO POSITIVO | Confirmado | Descuento calcula desde `invoice.posting_date`, documentado. |
| **CAS-09** | FALSO POSITIVO | Confirmado | `discount_amount` presente en ambos formularios. |
| **CAS-11** | FALSO POSITIVO | Confirmado | `allocated > 0` es la validación mínima correcta. |
| **CAS-12** | FALSO POSITIVO | Confirmado | Cuentas GL validadas via `_require_account` en posting. |
| **CAS-16** | FALSO POSITIVO | Confirmado | PaymentReference preservado como historial append-only. |
| **CAS-17** | FALSO POSITIVO | Confirmado | Función utilitaria; validación de compañía está separada. |
| **INV-01** | FALSO POSITIVO (CERRADO) | Confirmado | Dos verificaciones: pre-FIFO y post-Bin. Ambas presentes. |
| **INV-21** | FALSO POSITIVO | Confirmado | `valuation_rate=0` cuando qty≤0 es intencional. `stock_value` preservado. |
| **INV-22** | FALSO POSITIVO | Confirmado | Delete-then-resave intencional para consistencia. |
