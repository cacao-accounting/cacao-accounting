# ISSUES.md — REGISTRO DE AUDITORÍA FUNCIONAL ERP

**Última actualización:** 2026-07-10
**Versión del código auditado:** HEAD `5a1374d`

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
| **S2P-21** | Control presupuestario configurable (global) en aprobación PR/PO | PENDIENTE | [#188](https://github.com/cacao-accounting/cacao-accounting/issues/188) | — |
| **S2P-22** | Sin automatización de punto de reorden | PENDIENTE | [#189](https://github.com/cacao-accounting/cacao-accounting/issues/189) | — |
| **S2P-23** | Ausencia de límites de aprobación jerárquica por monto en Órdenes de Compra | PENDIENTE | — | — |
| **S2P-24** | Duplicidad del número de factura del proveedor (`supplier_invoice_no`) no validada | PENDIENTE | — | — |
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
| **O2C-24** | Precios negativos permitidos en documentos de venta | CORREGIDO | [#191](https://github.com/cacao-accounting/cacao-accounting/issues/191) | `93cdadb` |
| **O2C-25** | Falta de control de sobre-entrega (Over-delivery) en Notas de Entrega | PENDIENTE | — | — |
| **O2C-26** | Falta de control de sobre-facturación (Over-billing) en Ventas | PENDIENTE | — | — |
| **R2R-01** | Validación de balance usa signed `line.value` después de redondeo por línea | FALSO POSITIVO | — | — |
| **R2R-02** | Validación de período inconsistente en revaluación cambiaria | FALSO POSITIVO | — | — |
| **R2R-04** | `duplicate_journal_as_reversal_draft` bloquea reversiones mismo período | FALSO POSITIVO | [#174](https://github.com/cacao-accounting/cacao-accounting/issues/174) | — |
| **R2R-06** | Revaluación cambiaria sin auditoría | FALSO POSITIVO | [#149](https://github.com/cacao-accounting/cacao-accounting/issues/149) | `5a1374d` |
| **R2R-07** | Cierre de período sin auditoría | FALSO POSITIVO | [#164](https://github.com/cacao-accounting/cacao-accounting/issues/164) | `5a1374d` |
| **R2R-08** | Documentos operativos sin auditoría de submit/cancel | FALSO POSITIVO | — | — |
| **R2R-10** | Sin control presupuestario en posting | PENDIENTE | [#186](https://github.com/cacao-accounting/cacao-accounting/issues/186) | — |
| **R2R-11** | Sin protección contra doble posting en funciones `post_*` individuales | CORREGIDO | [#130](https://github.com/cacao-accounting/cacao-accounting/issues/130) | `ab45e31` |
| **R2R-13** | Linking item-to-entry en revaluación frágil (orden posicional) | CORREGIDO | [#187](https://github.com/cacao-accounting/cacao-accounting/issues/187) | `ab45e31` |
| **R2R-17** | Sin validación de balance en moneda de transacción | CORREGIDO | [#192](https://github.com/cacao-accounting/cacao-accounting/issues/192) | `4003b55` |
| **R2R-18** | Sin consolidación multi-empresa | PENDIENTE | [#193](https://github.com/cacao-accounting/cacao-accounting/issues/193) | — |
| **R2R-19** | Falta de bloqueo de eliminación de maestros con historial transaccional activo | PENDIENTE | — | — |
| **CAS-05** | Sin saldo en tiempo real en BankAccount | FALSO POSITIVO | — | — |
| **CAS-08** | Descuento por pronto pago usa `posting_date` no fecha de factura | FALSO POSITIVO | — | — |
| **CAS-09** | Descuento por pronto pago no accesible en formulario de pago | FALSO POSITIVO | — | — |
| **CAS-11** | Sin validación de asignación mínima | FALSO POSITIVO | — | — |
| **CAS-12** | Sin validación de cuenta GL al aprobar pago | FALSO POSITIVO | — | — |
| **CAS-13** | `_cash_consumed` cero permite eludir verificación de saldo restante | CORREGIDO | [#134](https://github.com/cacao-accounting/cacao-accounting/issues/134) | `189da6e` |
| **CAS-16** | PaymentReference rows huérfanos al cancelar pago | FALSO POSITIVO | — | — |
| **CAS-17** | `_payment_numbering_defaults` no valida compañía del banco | FALSO POSITIVO | — | — |
| **CAS-18** | Conciliación bancaria no valida docstatus del pago destino | CORREGIDO | [#194](https://github.com/cacao-accounting/cacao-accounting/issues/194) | `a0d3845` |
| **CAS-19** | Sin pronóstico de flujo de caja | PENDIENTE | [#195](https://github.com/cacao-accounting/cacao-accounting/issues/195) | — |
| **CAS-20** | Sin alerta de pagos duplicados por monto y proveedor cercano | CORREGIDO | [#196](https://github.com/cacao-accounting/cacao-accounting/issues/196) | `de7c43d` |
| **CAS-21** | Ausencia de flujo de aprobación para cancelaciones de pagos | PENDIENTE | — | — |
| **INV-01** | Verificación de stock negativo ocurre después de upsert de StockBin | FALSO POSITIVO (CERRADO) | [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) | — |
| **INV-10** | `reserved_qty` puede desviarse por movimientos fuera del flujo O2C | CORREGIDO | [#159](https://github.com/cacao-accounting/cacao-accounting/issues/159) | clamp en `_upsert_stock_bin` |
| **INV-21** | `valuation_rate` se resetea a 0 cuando qty=0 | FALSO POSITIVO | — | — |
| **INV-22** | Relaciones documentales creadas en draft, eliminadas en edición | FALSO POSITIVO | — | — |
| **INV-26** | Sin alerta de punto de reorden en movimientos de salida | PENDIENTE | [#197](https://github.com/cacao-accounting/cacao-accounting/issues/197) | — |
| **INV-27** | Falta de auditoría y log de cambios en edición de borradores (eliminación física de líneas) | PENDIENTE | — | — |
| **SEC-01** | Ausencia de validación de propiedad (created_by) en submit/cancel | FALSO POSITIVO | [#198](https://github.com/cacao-accounting/cacao-accounting/issues/198) | — |
| **SEC-02** | Eliminación física de líneas de documento al editar (sin trazabilidad) | PENDIENTE | [#199](https://github.com/cacao-accounting/cacao-accounting/issues/199) | — |

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
[cacao_accounting/<modulo>/<archivo>.py:<línas>]

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

# INFORME DE AUDITORÍA DE WORKFLOWS Y PROCESOS ERP (10-JUL-2026)

Este reporte detalla los hallazgos de lógica de negocio, inconsistencias funcionales y de auditoría detectados durante la revisión del sistema ERP Cacao Accounting.

---

## 1. MÓDULO SOURCE TO PAY (S2P)

### S2P-23 [ALTO] — Ausencia de límites de aprobación jerárquica por monto en Órdenes de Compra

**Descripción:**
Actualmente, cualquier usuario con rol de compras y acceso al endpoint de aprobación puede autorizar Órdenes de Compra por cualquier monto financiero sin restricciones (ej. órdenes de $100k+). El sistema aprueba el documento directamente sin verificar una matriz de firmas o límites de aprobación jerárquica basados en el valor monetario del documento.

**Impacto:**
Riesgo severo de fraude interno, compras no autorizadas, sobrefacturación y desviación masiva de presupuesto. Pérdida del control financiero y de segregación de funciones.

**Recomendación:**
Implementar una matriz de autorizaciones configurable por compañía (`ApprovalMatrix`) que asocie límites monetarios máximos a roles de usuario. Al exceder un límite, la Orden de Compra debe quedar en estado `Pending Approval` (pendiente de un rol jerárquico superior como Director de Compras o CFO) en lugar de aprobarse inmediatamente.

**Módulo/Archivo:**
`cacao_accounting/compras/__init__.py:2289` (`compras_orden_compra_submit`)

**Caso de prueba:**
1. Crear una Orden de Compra con un total de $150,000.
2. Iniciar sesión con un usuario con el rol de comprador estándar ("Buyer").
3. Intentar aprobar (submit) la orden.
4. El sistema debe lanzar un error indicando que excede el límite de aprobación del usuario y debe requerir la autorización de un CFO o Gerente General.

**Veredicto:** PENDIENTE
**Confianza:** Muy Alto
**GitHub Issue:** —
**Commit(s):** —

---

### S2P-24 [ALTO] — Duplicidad del número de factura del proveedor (`supplier_invoice_no`) no validada

**Descripción:**
No se realiza ninguna validación de duplicidad en el número físico de la factura emitida por el proveedor (`supplier_invoice_no`) para un mismo tercero (`supplier_id`). El sistema permite registrar y aprobar múltiples facturas de compra con el mismo número del mismo proveedor.

**Impacto:**
Alto riesgo de pagos duplicados al mismo proveedor, doble contabilización de gastos e IVA acreditable (inconsistencias fiscales), lo cual vulnera las normas fiscales y de auditoría básica.

**Recomendación:**
Agregar un validador en el guardado y en la función de submit de facturas de compra. Se debe lanzar un error de validación si existe otra factura de compra activa (no cancelada, `docstatus != 2`) para el mismo `supplier_id` y con el mismo `supplier_invoice_no`.

**Módulo/Archivo:**
`cacao_accounting/compras/__init__.py:3239` (`compras_factura_compra_submit`) y `cacao_accounting/database/__init__.py:1318`

**Caso de prueba:**
1. Crear y aprobar una Factura de Compra para el proveedor "SUPLR-00001" con `supplier_invoice_no = "FAC-2026-001"`.
2. Crear una segunda Factura de Compra diferente para el mismo proveedor "SUPLR-00001" e ingresar el mismo número `supplier_invoice_no = "FAC-2026-001"`.
3. Intentar aprobar la factura. El sistema debe rechazar el submit con un mensaje claro de duplicidad.

**Veredicto:** PENDIENTE
**Confianza:** Muy Alto
**GitHub Issue:** —
**Commit(s):** —

---

## 2. MÓDULO ORDER TO CASH (O2C)

### O2C-25 [ALTO] — Falta de control de sobre-entrega (Over-delivery) en Notas de Entrega

**Descripción:**
En el flujo comercial, al aprobar una Nota de Entrega (Delivery Note) vinculada a una Orden de Venta, no se valida que la cantidad entregada acumulada no exceda la cantidad originalmente ordenada en la Orden de Venta (`SalesOrder`). Un usuario puede emitir notas de entrega por cantidades superiores a las pactadas con el cliente.

**Impacto:**
Pérdida material directa (fuga de inventario no facturada), problemas de conciliación logística y disputas severas con el cliente por entregas no acordadas.

**Recomendación:**
Implementar un validador similar a `_validate_receipt_quantities_against_po` pero para ventas. El método `_validate_delivery_quantities_against_so` debe calcular la cantidad consumida para la Orden de Venta y validar que la nueva entrega no la exceda.

**Módulo/Archivo:**
`cacao_accounting/ventas/__init__.py:2235` (`ventas_entrega_submit`)

**Caso de prueba:**
1. Crear y aprobar una Orden de Venta con una línea de producto "ART-RESERVE" por 10 unidades.
2. Crear una Nota de Entrega asociada a esta Orden de Venta por 12 unidades.
3. Intentar aprobar la Nota de Entrega. El sistema debe arrojar una excepción por sobre-entrega y bloquear el submit.

**Veredicto:** PENDIENTE
**Confianza:** Muy Alto
**GitHub Issue:** —
**Commit(s):** —

---

### O2C-26 [ALTO] — Falta de control de sobre-facturación (Over-billing) en Ventas

**Descripción:**
Al aprobar una Factura de Venta vinculada a un documento previo (Orden de Venta o Nota de Entrega), el sistema no valida que la cantidad facturada acumulada sea menor o igual a la cantidad entregada o pactada. Esto permite sobrefacturar de manera descontrolada.

**Impacto:**
Riesgos contables por reconocimiento inflado de ingresos, reclamaciones legales de clientes, multas por facturación fiscal errónea y descontrol en la conciliación interna.

**Recomendación:**
Desarrollar una validación de cantidades en `ventas_factura_venta_submit` para asegurar que las cantidades acumuladas facturadas no excedan las de la Orden de Venta (para flujos de facturación directa de pedido) o las de la Nota de Entrega (para flujos de entrega-facturación).

**Módulo/Archivo:**
`cacao_accounting/ventas/__init__.py:2620` (`ventas_factura_venta_submit`)

**Caso de prueba:**
1. Crear una Nota de Entrega aprobada por 5 unidades de un artículo.
2. Crear una Factura de Venta vinculada a dicha Nota de Entrega por 7 unidades.
3. Intentar aprobar la Factura de Venta. El sistema debe lanzar un error de validación de sobre-facturación.

**Veredicto:** PENDIENTE
**Confianza:** Muy Alto
**GitHub Issue:** —
**Commit(s):** —

---

## 3. MÓDULO RECORD TO REPORT (R2R)

### R2R-19 [ALTO] — Falta de bloqueo de eliminación de maestros con historial transaccional activo

**Descripción:**
El sistema permite eliminar registros maestros esenciales (Artículos, Almacenes, Proveedores, Clientes) del catálogo general aun cuando ya tienen un historial de transacciones registradas y contabilizadas (registros activos en `GLEntry`, `StockLedgerEntry`, etc.).

**Impacto:**
Corrupción catastrófica de la integridad referencial en la base de datos. Los reportes financieros de periodos cerrados y el Kardex del inventario pueden quedar huérfanos, perdiendo toda la trazabilidad y la consistencia histórica.

**Recomendación:**
Implementar una regla de negocio que intercepte los métodos de eliminación (u operaciones en la BD) de entidades maestras críticas. Si existen registros dependientes en las tablas de diario contable o de inventario, se debe restringir la eliminación física y sugerir en su lugar la inactivación o bloqueo del maestro.

**Módulo/Archivo:**
`cacao_accounting/` (rutas generales de delete de maestros en `inventario`, `compras`, `ventas` y `contabilidad`)

**Caso de prueba:**
1. Registrar transacciones y contabilizar la compra de un artículo "ART-RESERVE" en la bodega "WH-RESERVE".
2. Intentar eliminar físicamente el artículo o la bodega del sistema a través de la API o pantalla de edición.
3. El sistema debe lanzar una excepción de integridad operativa indicando que el registro cuenta con transacciones activas y sugerir su inactivación.

**Veredicto:** PENDIENTE
**Confianza:** Muy Alto
**GitHub Issue:** —
**Commit(s):** —

---

## 4. GESTIÓN DE TESORERÍA (CASH MANAGEMENT)

### CAS-21 [ALTO] — Ausencia de flujo de aprobación para cancelaciones de pagos

**Descripción:**
Cualquier usuario con permisos básicos del módulo de bancos puede cancelar un cobro de cliente o un pago a proveedor ya procesado (`PaymentEntry` con `docstatus = 1`) mediante una solicitud POST. No existe segregación de funciones ni control jerárquico que requiera una aprobación secundaria para revertir movimientos de efectivo.

**Impacto:**
Vulnerabilidad crítica para el desvío fraudulento de fondos y ocultamiento de faltantes en caja. Un usuario malintencionado podría anular un pago real, liberar la factura y desviar la contrapartida contable sin supervisión.

**Recomendación:**
Implementar un doble control o flujo de autorización para las cancelaciones del módulo de Tesorería. Toda cancelación de pagos debe quedar registrada como un "Borrador de Cancelación" o requerir un rol supervisor (`FinanceManager`) para que el reverso del flujo y del GL se haga efectivo.

**Módulo/Archivo:**
`cacao_accounting/bancos/__init__.py:1924` (cancelaciones de pagos)

**Caso de prueba:**
1. Crear y aprobar un pago a proveedor por un valor de $10,000.
2. Usar un usuario operativo ("Cashier" o analista contable) para cancelar el pago.
3. El sistema debe bloquear la operación directa y notificar que requiere autorización del Gerente de Finanzas.

**Veredicto:** PENDIENTE
**Confianza:** Muy Alto
**GitHub Issue:** —
**Commit(s):** —

---

## 5. GESTIÓN DE INVENTARIO

### INV-27 [MEDIO] — Falta de auditoría y log de cambios en edición de borradores (eliminación física de líneas)

**Descripción:**
Al editar un documento de inventario en borrador (ej. un `StockEntry` tipo traslado o ajuste), las líneas del documento anteriores se eliminan físicamente de la base de datos antes de insertar las nuevas líneas provenientes de la petición. No se mantiene un log o historial de los cambios previos de cantidades o costos que sufrió el borrador durante su ciclo de vida.

**Impacto:**
Pérdida de trazabilidad de auditoría de borradores. Un operador de almacén puede modificar cantidades a discreción antes de la aprobación final sin dejar rastro de qué datos originales ingresó o modificó, facilitando el robo hormiga o encubrimiento de diferencias.

**Recomendación:**
Integrar el `audit_trail_service` o un decorador de auditoría que documente el historial completo de ediciones (changelog) en documentos transaccionales de inventario, incluso en estado borrador (`docstatus = 0`).

**Módulo/Archivo:**
`cacao_accounting/inventario/__init__.py:1217` (`_update_stock_entry_from_form`) y `cacao_accounting/database/__init__.py:1557`

**Caso de prueba:**
1. Crear una entrada de stock en borrador con 100 unidades de un producto de alto costo.
2. Editar el borrador y cambiar la cantidad a 80 unidades.
3. Consultar la bitácora o log de auditoría del documento. Se debe poder visualizar el valor anterior (100) y el nuevo valor modificado (80).

**Veredicto:** PENDIENTE
**Confianza:** Muy Alto
**GitHub Issue:** —
**Commit(s):** —
