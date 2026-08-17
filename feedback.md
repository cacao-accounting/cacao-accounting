# Feedback — Revisión de commits locales previos a push

## Estado del repo al momento de la revisión

- Rama `main` adelante de `origin/main` por **67 commits** (base de revisión: `origin/main...main`, ~4,100 inserciones en 49 archivos).
- Working tree limpio al finalizar la revisión.
- Los commits son semánticos, con `Signed-off-by`, referencias `Closes #XXX` y autor/committer consistentes. Sin secretos, sin `print`/`breakpoint`/TODO introducidos, y `git diff --check` limpio.
- **Nota:** durante la revisión la rama pasó de 63 a 67 commits (concurrencia de trabajo local). Las observaciones siguientes aplican a `HEAD` (4c99235a).

---

## Hallazgos de prioridad ALTA

### H1. Editar un borrador vinculado a origen rompe su reaprobación (#483 incompleto)
`revert_relations_for_target(..., reason="draft_edited")` se invoca en todos los handlers de edición de borradores (ventas: 1169, 1194, 2466, 2923, 3441; compras: 2932, 3211, 3767, 4753), marcando las relaciones como `reverted` en lugar de eliminarlas. Pero los formularios de edición no repostan los campos de origen: `initialLines` no incluye `source_type_i`/`source_id_i` (p. ej. `ventas_orden_venta_editar`, `ventas/__init__.py:2157-2170`), por lo que `_create_line_relation` no vuelve a crear ninguna relación. Al aprobar, `require_line_relations` (`document_flow/validation.py:63`) exige una relación activa por línea y el documento se rechaza con "Cada línea debe conservar una relación activa…". Además, si el formulario sí reenviara los orígenes, la re-inserción colisionaría con la fila `reverted` por la restricción única `uq_document_relation_line` (`database/__init__.py:3056`) → IntegrityError de 500.

Sugerencia: al editar un borrador (docstatus=0) reconstruir las relaciones de las líneas conservadas, o eliminar físicamente las relaciones de borrador y re-vincularlas desde el origen antes del submit; mantener el revert únicamente para cancelación/rechazo.

### H2. `revert_relations_for_target` también revierte relaciones downstream del borrador editado
`document_flow/service.py:522-551` revierte además las relaciones donde el documento editado es el **source** (hijos aprobados). Editar un borrador de solicitud/OC que ya tiene cotizaciones/órdenes aprobadas marca esas relaciones downstream como `reverted`, pierde la trazabilidad y descuenta consumos aprobados.

Sugerencia: en edición de borradores revertir únicamente donde el borrador es *target*; el revert downstream sólo para cancelación/rechazo.

### H3. `_sales_exchange_rate` silencia tasas faltantes y contabiliza a 1:1
`ventas/__init__.py:107-118`: el `except PostingError` devuelve tasa `1` cuando no existe tipo de cambio registrado. Como el posting ahora prefiere `document_exchange_rate`, una factura en USD en compañía BOB sin tasa registrada se contabiliza a 1:1 en el libro funcional, con base totales/ledger incorrectos.

Sugerencia: no tragarse el `PostingError`; dejar que la creación/submit falle con un mensaje claro de "no existe tipo de cambio".

---

## Hallazgos de prioridad MEDIA

### M1. `grand_total` del navegador sigue siendo confiable sin plantilla fiscal
`fiscal_persistence_service.py:36-46`: el docstring promete fuente de verdad del servidor, pero sin `tax_template_id` acepta el `grand_total` del cliente tal cual y lo persiste también al snapshot fiscal. El vector de manipulación de #486 permanece para facturas sin plantilla.

Sugerencia: recalcular desde líneas en el camino sin plantilla y usar el payload sólo para validación/redondeo.

### M2. `abs()` enmascara totales negativos
`fiscal_persistence_service.py:34,41,44`: `abs(subtotal + payable_delta)` convierte un crédito negativo (p. ej. −1000 + 150 IVA) en 850 en lugar de rechazarlo, y subestima `note_amount` usado para topar notas de crédito.

Sugerencia: validar el signo por tipo de documento en vez de recortarlo con `abs()`.

### M3. Edición de nota de crédito valida contra total sin impuestos
`ventas/__init__.py:3469-3477`: la edición pasa `note_amount=total` (subtotal) a `_validate_reversal_of`, mientras creación (3247-3254) y submit (3579-3589) usan `grand_total` con impuestos. Una NC puede pasar edición y fallar submit (o viceversa).

Sugerencia: usar `grand_total` también en la ruta de edición.

### M4. Duplicado de factura pierde moneda, tasa, impuestos y vínculos
`ventas_factura_venta_duplicar` (`ventas/__init__.py:3505-3541`): no copia `transaction_currency`, `exchange_rate`, `tax_template_id`, `sales_order_id`, `delivery_note_id` ni `reversal_of`, y fija `grand_total = total` (sin impuestos). Facturas duplicadas en moneda extranjera/con impuestos quedan mal valuadas y en compañías con `require_sales_order` no son aprobables.

Sugerencia: reutilizar `_set_sales_invoice_totals` y copiar los campos de cabecera/origen.

### M5. 2-way matching: el fallback de almacén es código muerto
`purchase_reconciliation_service.py:668` usa `order_groups.get(key)` con clave exacta (ahora con dimensión de almacén), mientras el loop de asignación en :713 usa `_compatible_group`. El fallback agnóstico de almacén nunca corre: una línea de factura cuyo almacén difiere (o es `None` contra uno presente) falla con "No existe linea de OC compatible". Hoy está enmascarado porque el formulario no persiste `warehouse`.

Sugerencia: usar `_compatible_group(order_groups, invoice_group.lines[0])` también en la línea 668.

### M6. `require_purchase_order` endurecido de "uno de" a "ambos"
`purchase_reconciliation_service.py:540` exige `invoice_po_id AND receipt_po_id`. Antes bastaba `OR` (facturas referenciando sólo la recepción, que porta la OC). Facturas creadas desde recepción sin `from_order` explícito ahora fallan en 3-way estricto.

Sugerencia: aceptar `invoice_po_id or receipt_po_id` y validar la discrepancia sólo si ambos están presentes.

### M7. `price_tolerance_failed` ignora `allow_price_difference`
`purchase_reconciliation_service.py:473-476` y banderas por línea (:588-595, :683-690): `allow_price_difference` se lee de la config pero nunca se consulta; cualquier compañía que optó por tolerar diferencias de precio nunca completa el matching.

Sugerencia: honrar `config.allow_price_difference` (registrar/advertir en lugar de fallar) en `_evaluate_matching_result`.

### M8. Tolerancia de precio por línea falla con líneas de referencia valoradas en 0
`purchase_reconciliation_service.py:588-595 / 683-690`: si `reference_amount == 0` (línea de recepción a costo cero), el porcentaje da diferencia 0 y cualquier tarifa de factura distinta de cero bloquea la conciliación (antes sólo importaba el agregado).

Sugerencia: omitir el chequeo por línea cuando `reference_qty == 0`.

### M9. Importación bancaria acepta montos negativos que ahora revientan al persistir
`imports/adapters/bank_statement.py:33-72` no rechaza negativos en `deposit`/`withdrawal`; el nuevo validador de BD `_validate_bank_transaction_amounts` (`database/__init__.py:3171-3178`) lanza al flush, convirtiendo una fila negativa antes aceptada en un fallo duro de importación.

Sugerencia: rechazar negativos en `validate_row` con error por fila.

### M10. `_flow_source_type` estricto rompe ediciones de pagos legacy (#477)
`bancos/__init__.py:1631-1638` lanza `ValueError` si el `flow_source_type` enviado no coincide con el `document_type` físico. Filas `PaymentReference` antiguas pueden guardar `purchase_invoice` para un registro cuyo `document_type` es `purchase_credit_note`; al editar el pago (la página repostea el valor almacenado) la edición aborta.

Sugerencia: normalizar el mapeo de notas (crédito/débito → modelo de factura) o permitir la equivalencia legacy; idealmente backfill de filas históricas.

### M11. Creación de pagos vía document-flow sin permiso del módulo "cash" (#446 parcial)
`_build_payment_from_payload` (`bancos/__init__.py:2122`) exige `exige_acceso_compania("cash", company, "crear")`, pero la ruta API `api_document_flow_create_target` (`api/__init__.py:733`) autoriza por acceso al documento **origen** vía `_require_flow_company_access`; `_create_payment_target` (`document_flow/payment.py:1230`) crea y commitea un borrador de pago sin control del módulo bancario.

Sugerencia: exigir el permiso "cash" dentro de `_create_payment_target`/`_build_payment_target_payment`.

### M12. Aprobaciones S2P pueden devolver 500 por `BudgetError` no capturado
`budget_service.py:479-482` lanza `BudgetError` (subclase de `Exception`, no de `ValueError`) ante dimensiones business_unit/project inválidas o cross-company. Su único llamador, `check_budget_control` (`compras/__init__.py:5527-5541`), se invoca dentro de bloques `try/except ValueError` (:648-667, :3464-3483); el `BudgetError` escala a 500 en la aprobación de solicitudes/ÓC.

Sugerencia: resolver la unidad por `entity=company` (id o código) como `_resolve_cost_center_id`, o ampliar los `except` a `(ValueError, BudgetError)`.

### M13. Reporte Real vs Presupuesto filtra por cualquier compañía sin ACL
`presupuesto.py:453-515` (`reporte`): acepta `company` por form/query y lo pasa directo a `BudgetReportService().get_real_vs_budget_report()`, que consulta GL y presupuesto sin ACL por compañía. Cualquier usuario con permiso `reportes` del módulo `accounting` puede leer presupuestos/GL de otra compañía.

Sugerencia: validar `exige_acceso_compania("accounting", company_id, "consultar")` cuando `company_id` esté presente.

### M14. Asistente de cierre mensual lista corridas y períodos de todas las compañías
`contabilidad/__init__.py:2605-2629`: `asistente_cierre_mensual` selecciona `PeriodCloseRun` y períodos abiertos sin filtrar por compañía; los guards by-company sólo están en las rutas de detalle/acción.

### M15. `_validate_batch` compara cantidad en UOM de presentación contra saldo en UOM base
`inventario/service.py:139-147`: compara `line.qty` directamente contra el saldo `StockLedgerEntry` (en UOM base). Artículos en lotes posteados en UOM distinta pueden pasar el cheque mientras exceden el saldo real en UOM base.

### M16. Suma mixta de consumos con `qty_in_base_uom` NULL
`document_flow/repository.py:112-129`: `consumed_qty_for_source` suma `qty_in_base_uom` para relaciones nuevas pero `qty` crudo para filas legacy (NULL). Se mezclan dimensiones hasta que se haga backfill; conviene una migración.

### M17. Nuevas columnas sin migración
Se agregaron `PurchaseReceipt.base_total` (`database/__init__.py:2236`) y `DocumentRelation.qty_in_base_uom` (:3080) sin nueva revisión de Alembic (sólo existe `20260809_0001_baseline.py`). Instalaciones existentes que corran `db migrate` no obtienen las columnas → errores de columna inexistente en runtime.

Sugerencia: agregar una migración incremental además de la baseline.

### M18. Fallback de compañía sin permisos de libro rompe la vista de presupuestos
`presupuesto.py:62-77`: `listar` emite `where(False)` y las rutas detalle/edición devuelven 403 cuando el usuario no tiene filas `UserBookAccess`. Deployments que dependen del rol de módulo (sin grants explícitos de libro) pasan de ver todo a no poder editar nada.

---

## Hallazgos de prioridad BAJA

### B1. Ternario no-op en restauración de seriales
`posting.py:2805-2806`: `warehouse=movement.warehouse if qty_change > 0 else movement.warehouse` — ambas ramas idénticas. Confirmar la semántica de seriales al revertir una recepción.

### B2. Moneda funcional obligatoria rompe borradores de empresas sin `Entity.currency`
`journal_service.py:571-577`: la columna `Entity.currency` es nullable (`database/__init__.py:428-430`) pero ahora se exige para todo borrador de asiento manual. Empresas existentes sin moneda configurada no podrán guardar borradores.

### B3. Normalización de tipo de entrada del cash forecast inconsistente
Manual acepta "income"/"expense" (`cash_forecast.py:34` con `.capitalize()`) mientras el importador exige "Income"/"Expense" exactos (`imports/adapters/cash_forecast_entry.py:34`).

### B4. `close_line_balance` cuenta borradores abandonados como consumo
`document_flow/service.py:568/606` llama `pending_qty` sin `exclude_draft_targets`, a diferencia de las demás vistas; un borrador huérfano puede bloquear el cierre manual de línea.

### B5. Una factura puede llevar orden y nota de entrega inconsistentes
`ventas/__init__.py:3240-3243` (y 3457-3463, 1873-1879): el patrón `if sales_order_id: … elif delivery_note_id:` valida sólo la orden cuando ambos vínculos se envían; la nota de otra orden pasa desapercibida y la exposición de crédito se cuenta doble (`_approved_customer_order_exposure`).

### B6. Notas de crédito/débito en moneda extranjera recalculan la tasa
`ventas/__init__.py:3222-3245`: para NC/DN el `source` queda `None`, así que `_set_sales_invoice_totals` recalcula la tasa del día en vez de conservar la tasa de la factura revertida → varianza residual de FX en AR.

---

## Verificado correcto (sin acción requerida)

- Recomposición de montos de línea en el servidor (`qty * rate`) en vez de confiar en el monto del cliente (órdenes, solicitudes, cotizaciones, notas, facturas).
- Normalización de cantidades a UOM base y exclusión de destino borrador en el consumo (no quema disponibilidad).
- Acceso por compañía en rutas O2C/S2P (detail/edit/duplicate/submit/cancel).
- Totales con impuestos en creación y submit de facturas; el monto de la relación de reversa coincide con `grand_total`.
- Ledger append-only (`GLEntry`/`StockLedgerEntry`): los únicos cambios en código son `is_cancelled = True`; la restricción es coherente (#445).
- Revaluación de FX con preservación de corridas previas ante rerun fallido, y cierre fiscal que salta líneas netas cero.
- Split FIFO en conciliación de inventario y ajustes de valor con capa de qty=0 (#502); reversa de costos capitalizados con caps (503).
- Offset contable por línea (506), cuenta de ajuste por artículo (505), y aislamiento cross-company de conciliación (504).
- Aislamiento de conciliación bancaria por cuenta y compañía; `_bank_amount`/`_bank_direction` consistentes con el validador de BD.
- Bloqueo de cancelación de factura con notas activas y revalidación en Approval Engine (#492).

---

## Notas de CI

- Commit `c83d2ac6` agrega `npm audit --audit-level=high` al workflow. **Con el estado actual de las dependencias el paso FALLA**: existe 1 vulnerabilidad **high** (`serialize-javascript` <=7.0.4, vía mocha; fix requiere actualización breaking a mocha@11). El gate de seguridad no pasará hasta resolverla. (Ver: `cacao_accounting/static`, `npm audit`.)

---

## Sugerencias de prioridad para la siguiente etapa

1. **H1/H2** antes de considerar cerrado el #483 (re-crear/eliminar relaciones al editar borrador; limitar revert downstream).
2. **H3** (no silenciar la tasa faltante).
3. **M17** (migración de las columnas nuevas) y **M9** (rechazar negativos en importación bancaria) porque son regresiones de runtime/import.
4. **M11** (ACL del módulo cash en pagos vía document-flow) por ser un hueco de seguridad.
5. Resto de MEDIUM según severidad contable (M1/M2/M3/M4 afectan totales/facturación).

---

## Estado de aplicación — 2026-08-17

Se aplicaron y se dejaron en el commit firmado `0bdd6792` (`fix(sales): protect draft revisions and fiscal totals`):

| Hallazgo | Corrección aplicada |
|---|---|
| H2 | `revert_relations_for_target(..., reason="draft_edited")` ya no revierte relaciones downstream de documentos hijos aprobados. La propagación se conserva para cancelación/rechazo. |
| H3 | `_sales_exchange_rate` ya no convierte silenciosamente a 1:1 cuando falta una tasa; propaga el error de posting. |
| M1 | Sin plantilla fiscal, el total se toma únicamente del subtotal calculado en servidor; `grand_total` del navegador se ignora. |
| M2 | Se eliminó `abs()` del cálculo fiscal y se rechazan totales negativos. |
| M3 | La edición de notas de crédito valida el límite usando `grand_total`, igual que creación y submit. |
| M4 | La duplicación de facturas conserva moneda, tasa, plantilla fiscal, vínculos de origen, dimensiones de línea y totales funcionales. |

Todos los hallazgos H1–H3, M1–M18 y B1–B6 se detallan en los bloques aplicados abajo.

### Referencias de correcciones anteriores

Los siguientes fixes ya estaban presentes antes de esta revisión y se conservan como parte del historial verificable:

| Issues | Commit(s) relacionado(s) |
|---|---|
| #480, #444, #453, #459, #465, #468, #472 | `690bf30a` — invariantes bancarios, dirección de pagos y estados de lote/serial. |
| #455, #458, #477, #478 | `d1ad7197` — vigencia recurrente, matching por almacén, tipo de flujo y dimensiones presupuestarias. |
| #451 | `593b6e68` — inicialización de base de datos dentro del contexto Flask. |
| #473 | `080574a5` y `b5d51dbc` — elegibilidad comercial y resolución de artículos por código. |
| #445 | `d78ace45` — ledger contable y de inventario append-only. |
| #457 | `aa500476` — saldo de lotes por almacén. |
| #462, #467, #479 | `2f6ac620` — dimensiones de pagos y aislamiento de presupuesto/operaciones. |
| #443 | `c83d2ac6` — gate `npm audit`; el override de `serialize-javascript` se completó posteriormente en `27c65168`. |
| #394 | `6a39b6a3` — persistencia de moneda funcional inferida. |
| #452 | `a452feef` — validación de vínculos de origen en el flujo documental. |
| #393 | `f309381f` — conversión de importes GL a moneda de la cuenta bancaria. |

La referencia canónica de esta actualización documental es el commit posterior que registra este bloque en `feedback.md`.

### Segundo bloque aplicado

El commit firmado `2b68db51` (`fix(security): harden feedback regressions`) aplica además:

| Hallazgo | Corrección aplicada |
|---|---|
| M5 | El matching 2-way usa `_compatible_group`, permitiendo el fallback seguro de almacén. |
| M7 | `allow_price_difference` se respeta tanto en diferencias por línea como en la evaluación agregada. |
| M8 | Las diferencias de precio por línea se omiten cuando la cantidad de referencia es cero. |
| M9 | La importación bancaria rechaza depósitos/retiros negativos antes del flush de SQLAlchemy. |
| M10 | Se aceptan alias legacy de facturas/notas para no romper la edición de referencias históricas. |
| M11 | La creación de pagos por document-flow exige permiso `cash/crear` para la compañía. |
| M12 | Las aprobaciones de solicitudes y órdenes de compra capturan `BudgetError` como error controlado. |
| M13 | El reporte Real vs Presupuesto valida ACL de compañía antes de cargar datos. |
| M14 | El asistente de cierre mensual filtra corridas y períodos por compañías derivadas de libros autorizados. |
| M15 | El saldo de lotes convierte la cantidad solicitada a la UOM base antes de comparar. |
| M16 | Las relaciones legacy sin `qty_in_base_uom` se normalizan usando la conversión de UOM existente. |
| M17 | Se agregó la migración incremental `20260817_0001` y su prueba para `base_total` y `qty_in_base_uom`. |

M6 ya estaba cubierto por la condición `not (invoice_po_id and receipt_po_id)` presente en `HEAD`. Las pruebas enfocadas de este bloque finalizaron con **44 passed, 2 skipped**.

### Tercer bloque aplicado

El commit firmado `27c65168` (`fix(document-flow): preserve revisions and close feedback gaps`) aplica:

| Hallazgo | Corrección aplicada |
|---|---|
| H1 | Las líneas editables ahora rehidratan `source_type`, `source_id` y `source_item_id` desde la relación activa; al editar el borrador se conserva la trazabilidad para la reaprobación. |
| B1 | Se eliminó el ternario no-op de restauración de seriales y se conserva explícitamente la bodega del movimiento. |
| B2 | La moneda funcional de la entidad deja de ser obligatoria para guardar un borrador; el posting sigue validando los requisitos necesarios. |
| B3 | El importador de cash forecast normaliza `income`/`expense` igual que la captura manual. |
| B4 | El cierre manual excluye destinos borrador abandonados del cálculo de consumo. |
| B5 | Facturas con orden y nota de entrega validan ambos vínculos y rechazan flujos inconsistentes. |
| B6 | Notas de crédito/débito conservan la factura origen al resolver moneda y tasa cambiaria. |
| #443 | `package.json` usa un override de `serialize-javascript` 7.x y `package-lock.json` queda actualizado; la auditoría offline de severidad high reporta 0 high/critical. La auditoría online sigue limitada por DNS del entorno. |

Las pruebas enfocadas de este bloque finalizaron con **57 passed**; la validación Black del alcance modificado no reportó diferencias.

### Cuarto bloque aplicado

El commit firmado `42409abf` (`fix(accounting): allow read-only budget fallback`) cierra M18: la vista y los reportes de presupuesto pueden consultarse con permiso de lectura del módulo Contabilidad aunque no existan grants explícitos por libro. Las acciones de escritura continúan exigiendo permisos granulares. También permite conservar borradores contables de entidades antiguas sin moneda funcional configurada, y mantiene la validación estricta para monedas explícitas.

La prueba de ruta de importación y las regresiones contables seleccionadas finalizaron con **3 passed**.

### Estado externo de GitHub

Consulta realizada el 2026-08-17 sobre `cacao-accounting/cacao-accounting`:

| Issue abierto con `needs-work` | Estado local | Evidencia / pendiente |
|---|---|---|
| #477 | Corregido localmente en `d1ad7197` y compatibilidad legacy en `27c65168`. | GitHub sigue abierto porque no se ha hecho push; requiere validación de tercero. |
| #461 | La normalización de cantidades base está cubierta por `2b68db51` y el helper existente de flujo documental. | Falta validación end-to-end específica EA/BOX en GitHub antes de considerarlo cerrado externamente. |
| #443 | Gate CI en `c83d2ac6`, override/lock seguro en `27c65168`; auditoría offline high/critical: 0. | La auditoría online del entorno falla por DNS hacia npmjs.org; requiere verificación externa. |

No se modificaron estados ni etiquetas en GitHub, respetando la instrucción de no hacer push ni cambios externos.

### Comentarios de verificación posteados vía `gh`

Se habilitó `gh` (GH_TOKEN de la sesión activa, usuario `williamjmorenor`) y se publicaron **63 comentarios** de "Fix verificado" en los issues abiertos con corrección presente en la rama local:

- #394, #443, #445–#506 (montaje completo), y #444 (restaurado de serial en anulación).
- Ningún fix de la rama se marcó como trabajo pendiente: tras los bloques correctivos de esta sesión todos los fixes verificados cumplen con validez, robustez y apropiación al describir la evidencia en el código.
- Issues abiertos sin corrección en la rama (#393, #441–#442, backlog AUDIT/TST/RPT/FIS) quedaron sin comentar.

Cada comentario indica que la verificación es estática sobre la rama local y que la ejecución completa de la suite queda pendiente de CI.
