# SESSIONS — Continuidad de Desarrollo

> Este archivo documenta decisiones de diseño, arquitectura y hitos clave del proyecto.
> Para detalles de implementación por sesión, consultar el historial de git.

## 2026-08-12 — Auditoría integral al motor de cálculo de impuestos

### Petición
Realizar una auditoría exhaustiva de nivel de código y diseño al motor de cálculo de impuestos y cargos del sistema, analizando mecánicas de cálculo, descomposiciones, redondeo y prioridades.

### Implementación y Decisiones de Diseño
- Se realizó un análisis profundo a nivel de código de los dos motores coexistentes: el **Motor de Impuestos Clásico** (`calculate_taxes` en `tax_pricing_service.py`) y el **Motor Fiscal unificado** (`FiscalEngine` en `cacao_accounting/accounting_engine/fiscal/engine.py`).
- Se documentaron de forma rigurosa los hallazgos en `TAX_CALCULATION_ENGINE_AUDIT.md`:
  - **Diferencia de descomposición de impuestos incluidos:** El motor clásico trata `is_inclusive` como un aditivo simple, mientras que el `FiscalEngine` realiza una descomposición matemática de precios brutos.
  - **Redondeo y precisión:** Diferencias en el momento de cuantizar intermediarios frente a totalizadores.
  - **Lógica de resolución del RuleResolver:** El orden de resolución y fusión por diseño de especificidad, donde las reglas de ítem sobreescriben a las generales de compañía.
  - **Aislamiento por compañía:** Verificado como seguro y libre de fugas de datos.
- Se implementó una suite completa de pruebas unitarias y de integración (`tests/test_tax_engine_audit_cases.py`) para validar matemáticamente:
  - Descomposición concurrente de múltiples tasas de impuestos incluidos en el precio.
  - Redondeo por pasos del `RoundingManager` en cascadas de impuestos de alta precisión.
  - Comportamiento de bases imponible en cero o negativas (notas de crédito y devoluciones).
  - Jerarquías del resolvedor donde las reglas de ítem sobreescriben correctamente las reglas de compañía.
- Toda la suite pasó con éxito, asegurando la robustez e inmutabilidad del comportamiento fiscal de la aplicación.

## 2026-08-12 — Plan transversal para document flow y cobertura de pruebas

### Hallazgo

La RFQ `01KZVMT9H6KVVXJWM5EVARB6T7`, creada desde la solicitud
`01KZVMJP10S2JSEZ5FRTMGT4S4` en `cacaoaccounting.db`, se guardó sin líneas
aunque el formulario las mostraba. El origen pertenece a la compañía `cacao`,
usa `NIO` como moneda efectiva por configuración de compañía y la RFQ quedó
con total cero.

### Decisiones para la implementación

- En cualquier document flow, compañía y moneda se heredan del origen y no se
  pueden editar.
- `naming_series` permanece editable; si sigue vacío, se consulta y aplica la
  serie predeterminada después de una espera diferida de aproximadamente 1.5
  segundos, sin sobrescribir una selección manual.
- La carga asíncrona de líneas debe finalizar antes de permitir guardar y el
  backend debe rechazar documentos requeridos sin líneas.
- La revisión cubre S2P, O2C, Inventario y pagos de Bancos derivados de
  facturas, notas y órdenes.
- La moneda efectiva usa `transaction_currency` y, cuando está vacía, la
  moneda configurada en la compañía.
- Se agregará cobertura unitaria e integración para persistencia de líneas,
  bloqueo de compañía/moneda, naming series, monedas incompatibles y pagos
  documentales.

### Implementación aplicada

- Smart Select admite selección bloqueada y carga diferida de la serie default;
  la serie sigue siendo editable y nunca sobrescribe una selección manual.
- Los formularios transaccionales bloquean compañía/moneda cuando tienen
  `initialSourceType`, sincronizan las líneas Alpine con sus inputs hidden antes
  del POST y esperan la hidratación AJAX del origen.
- Compras, Ventas e Inventario rechazan persistir documentos sin líneas.
- RFQ y órdenes de compra heredan/validan compañía y moneda efectiva del
  documento origen; Bancos usa la moneda efectiva también para pagos
  documentales y bloquea visualmente la compañía prefijada.
- El árbol de flujo documental se puede consultar en borradores; las acciones
  para crear downstream continúan restringidas a documentos aprobados.
- Cobertura focalizada agregada para Smart Select, formulario transaccional,
  RFQ sin líneas, moneda heredada y compañía manipulada.

### Revisión transversal de formularios

Se revisaron los formularios basados en `transactionForm` de compras, ventas e
inventario. Se corrigió el mismo riesgo en Smart Select personalizados: el
`header` podía tener valores iniciales, pero el control no recibía
`initialValue`/`initialLabel`. Proveedor, cliente y moneda ahora se hidratan
desde el documento origen; compañía y moneda quedan bloqueadas cuando existe
flujo documental, mientras `naming_series` permanece editable.

Para documentos que afectan inventario, el almacén se modela como dato global:
las recepciones de compra usan `to_warehouse` (bodega destino) y las
remisiones usan `from_warehouse` (bodega origen), siguiendo el patrón de
`stock_entry`. Las líneas usan ese valor al persistir y la cuenta de inventario
se resuelve desde la configuración contable de esa bodega y compañía.

La revisión visual de S2P/O2C también consolidó `Observaciones` dentro de la
misma tarjeta de cabecera que proveedor/cliente y almacén cuando el formulario
tiene campos adicionales. La cabecera compartida deja de renderizar un bloque
duplicado de observaciones en esos casos.

### Correcciones del feedback de revisión

- La moneda base ahora se resuelve por `Entity.code`, no mediante la clave
  primaria interna, por lo que funciona también cuando el origen no declara
  `transaction_currency` y debe heredar la moneda de la compañía.
- Se eliminó la moneda duplicada de la Orden de Compra y se corrigió
  `base_currency` para usar la moneda base de la compañía.
- Recepciones y remisiones validan compañía y moneda también en el backend.
- Los errores de hidratación y de documento sin líneas se muestran en el
  formulario; la sincronización contempla inputs y selects.
- Inventario unificó el error de documento sin líneas en `DocumentFlowError` y
  las remisiones usan el mensaje correcto de bodega de origen.

## 2026-08-11 — Comparativo de ofertas y colocación separada de órdenes

### Petición

Convertir el comparativo de ofertas en una adjudicación por línea, exigirlo de
forma configurable y separar la confirmación del comparativo de la colocación
de Órdenes de Compra.

### Implementación

- Se agregaron las configuraciones globales `Requerir Comparativo de Ofertas` y
  `Mínimo de Ofertas Requeridas`, con valores predeterminados `False` y `2`.
- El comparativo permite seleccionar proveedor por línea, aceptar cobertura
  parcial y generar una adjudicación finalizada.
- Una oferta única o una selección distinta de la recomendación exige al rol
  `Gerente de Compras` y una justificación obligatoria.
- La adjudicación finalizada no crea órdenes inmediatamente. El usuario debe
  ejecutar el helper `Colocar Órdenes de Compra`, que genera una orden por
  proveedor y cambia el comparativo a `used`.
- Las Órdenes de Compra creadas desde adjudicación conservan la referencia al
  comparativo y a las cotizaciones de proveedor mediante relaciones documentales.
- Se agregaron modelos, migración, interfaz administrativa y pruebas unitarias
  para mínimo de ofertas, oferta única, override y cobertura parcial.
- Se incorporaron rondas opcionales de negociación: una ronda abierta es la
  fuente activa de ofertas, cada nueva ronda cierra la anterior y no se pueden
  abrir rondas después de finalizar el comparativo.

### Revisión por pares aplicada

- La justificación de gerente ahora se solicita también cuando se selecciona
  una oferta no recomendada con el mínimo de ofertas cumplido.
- `manual_override`, `override_reason` and `authorized_by` se registran por línea
  y no contaminan las líneas adjudicadas sin override.
- Se validan las rondas recibidas desde formularios y se correlacionan líneas
  repetidas del RFQ por ocurrencia, evitando reutilizar una línea de proveedor.
- La colocación de órdenes reclama atómicamente el comparativo antes de crear
  documentos, cerrando la posibilidad de doble colocación concurrente.
- La ronda activa se cierra al finalizar; se eliminó el hook sin generador de
  `from_award` y el detalle post-adjudicación permanece visible.
- Se añadieron pruebas para overrides por línea y códigos de artículo repetidos.
- La revisión adicional confirmó que `from_award_id` no tiene referencias
  restantes; la colocación conserva una única transacción y ahora revierte
  explícitamente ante errores conocidos. Se separaron los mensajes de ronda y
  se agregó logging para cotizaciones con cobertura insuficiente.

## 2026-08-11 — RBAC para operaciones físicas y nomenclatura de remisiones

### Hallazgo

Compras y Ventas necesitan consultar recepciones y remisiones, pero Inventario
debe administrar las operaciones físicas. La entrega de productos vendidos se
presenta funcionalmente como “Remisión de Mercadería Vendida”.

### Implementación

- Compras conserva lectura de recepciones y Ventas conserva lectura de
  remisiones mediante acceso por compañía en cualquiera de sus módulos.
- Crear, editar, duplicar, aprobar y anular recepción/remisión se valida con
  permisos RBAC del módulo Inventario.
- Se retiró la creación de un `stock_entry` downstream desde una recepción de
  compra para evitar doble movimiento y doble contabilización.
- El registro documental usa Inventario para ambos documentos físicos, sin
  cambiar sus identificadores técnicos (`purchase_receipt` y `delivery_note`).
- La interfaz reemplaza “Nota de Entrega” por “Remisión de Mercadería
  Vendida”.
- Inventario incorpora el acceso de consulta a “Remisiones de Mercadería
  Vendida” dentro de “Registros del Módulo”.
- Inventario no muestra “Órdenes de Compra” en sus registros; la orden se
  consulta desde Compras y sirve como origen al crear una recepción.
- Se agregaron pruebas del contrato de propiedad RBAC y se conserva la suite
  focalizada como evidencia de regresión.

## 2026-08-11 — Atajos de creación en barra principal para flujos documentales

### Petición

Corregir la usabilidad de las acciones disponibles en la trazabilidad y
revisar el mismo problema en los formularios de O2C, S2P e Inventario. Las
acciones downstream deben funcionar como atajos visibles junto a “Nuevo”.

### Implementación

- Se creó el menú reutilizable “Crear” en la barra principal de 12 vistas de
  detalle de ventas, compras e inventario.
- El menú aparece como última acción a la derecha, después de “Nuevo”, con
  azul institucional; “Nuevo” conserva su estilo verde.
- Se eliminaron los botones duplicados del panel de flujo documental, que
  queda enfocado en trazabilidad y relaciones.
- Las opciones se siguen resolviendo desde `DOCUMENT_TYPES` y conservan sus
  URLs y parámetros de origen.

## 2026-08-11 — Fallback de moneda local en datasets semánticos (#386)

### Petición

Corregir el issue P1 que dejaba sin moneda a facturas locales creadas sin `transaction_currency` ni `base_currency`.

### Implementación

- `get_receivables_analysis` y `get_payables_analysis` ahora resuelven la moneda configurada en `Entity` como fallback.
- La consulta se realiza una vez por conjunto de resultados, evitando consultas repetidas por factura.
- Se agregó `test_semantic_reports_fallback_to_company_currency`.
- Prueba focalizada: 7 casos exitosos.

## 2026-08-11 — Verificación y cierre selectivo de issues

### Implementación

- Se ejecutaron las pruebas de los módulos relacionados con los fixes: `228 passed`.
- Se cerraron con evidencia los issues #374, #375, #378, #379, #380, #299, #303, #309 y #311.
- Permanecen abiertos #376 y #377 porque el código aún no firma las cantidades de devoluciones y todavía no filtra pagos cancelados en `get_settlement_analysis`.
- No se cerró #284: continúa requiriendo un contrato integral de precisión y redondeo, y su referencia documental fue eliminada por petición explícita, no por resolución funcional.

## 2026-08-11 — Corrección de datasets semánticos para devoluciones y pagos cancelados

### Petición

Completar los fixes pendientes de los issues #376 y #377 para poder cerrarlos.

### Implementación

- `get_sales_analysis` y `get_purchase_analysis` ahora firman las cantidades de devoluciones igual que los importes.
- `get_settlement_analysis` excluye pagos cancelados mediante `PaymentEntry.docstatus == 1`.
- Se añadieron pruebas de cantidades netas y de exclusión de pagos cancelados.
- Pruebas focalizadas: `2 passed`.

## 2026-08-11 — Cobertura ampliada para Record-to-Reports (R2R) Multimoneda y Multilibros

### Petición
Agregar pruebas adicionales que cubran el flujo de Record-to-Reports (record a reportes), enfocándose en multi moneda y multilibros.

### Implementación
- Se agregaron pruebas unitarias exhaustivas en `tests/test_record_to_reports_multicurrency_multiledger.py`.
- **Comprobación Contable Multimoneda:** `test_r2r_multi_currency_journal_entry_all_reports` valida la contabilización manual de comprobantes en moneda extranjera (GBP) a través de tres libros activos con distintas monedas funcionales (NIO, EUR, USD). Verifica que las tasas de cambio de cada libro se resuelvan correctamente y que la reportería financiera core (Trial Balance, Income Statement, Balance Sheet, y Account Summary) muestre importes exactos en la moneda de cada libro.
- **Flujo de Compras y Conciliación Multimoneda:** `test_r2r_purchase_flow_reconciliation_multicurrency` registra una factura de compra en USD y su respectiva devolución (Credit Note), afectando múltiples libros. Verifica que el saldo pendiente en el submayor de proveedores (AP Subledger) y los reportes operativos de compras por proveedor y artículo se neteen correctamente. Además, valida que la matriz de conciliación (Reconciliation Matrix) equilibre perfectamente y exponga con precisión las diferencias de traducción entre submayores en moneda base y mayor en moneda extranjera por cada libro.
- Se formateó el código mediante Black y se verificó con Ruff, Flake8, mypy y pytest.

## 2026-08-11 — Corrección de Rotación de Inventario para Movimientos Retroactivos (RPT-AUDIT-02)

### Petición

Corregir el cálculo de rotación de inventario cuando existen movimientos retroactivos y asegurar que el stock inicial del período participe en el promedio.

### Implementación

- `get_inventory_turnover` reconstruye el stock cronológicamente desde el ledger ordenado por fecha, creación e identificador.
- Se incluyó el saldo inicial del período dentro del promedio.
- Se agregó `test_get_inventory_turnover_with_backdated_transaction` para cubrir la reconstrucción ante transacciones retroactivas.

## 2026-08-11 — Corrección del Balance General Multianual y Utilidades Retenidas

### Petición

Corregir el descuadre del balance general al consultar períodos que abarcan varios años fiscales cerrados.

### Implementación

- Se preservan e incluyen los asientos de cierre de años anteriores como utilidades retenidas.
- Se continúan excluyendo los asientos de cierre del período actual cuando `include_closing=False`.
- Se agregó cobertura en `tests/test_fiscal_year_closing.py`.
## 2026-08-10 — Revisión de pull requests abiertos y comentarios de code review

### Petición

Revisar los pull requests abiertos del repositorio y sus comentarios de revisión
de código, distinguiendo los hilos pendientes de los informativos o ya obsoletos.

### Revisión realizada

- Se inspeccionaron los PR abiertos #384–#392, sus conversaciones, reviews y
  hilos inline con estado de resolución.
- Se identificaron hallazgos pendientes en #385, #386, #388, #389, #391 y
  #392. Los PR #384, #387 y #390 no tienen comentarios inline accionables.
- Los hallazgos prioritarios se concentran en preservación histórica de
  conciliaciones, fallback de moneda local, replay de conciliaciones de
  inventario, cálculo de utilidades retenidas, conciliación por moneda del
  ledger y reportes bancarios multi-moneda.
- No se publicaron respuestas, reacciones, resoluciones de hilos ni cambios de
  código; quedan como siguiente etapa para aprobación explícita de fixes.

## 2026-08-10 — Corrección y publicación de hallazgos de code review

### Petición

Verificar si los hallazgos de los PR abiertos habían sido corregidos y publicar
los fixes faltantes en sus ramas correspondientes.

### Implementación

- Se confirmó que los hallazgos de #385, #386 y #388 ya estaban corregidos en
  las ramas actuales.
- Se publicó en #389 el fallback al año fiscal vigente para evitar doble conteo
  de resultados históricos cuando no se selecciona período.
- Se publicó en #391 la conversión de los saldos AR/AP a la moneda del ledger
  seleccionado, junto con expectativas de reconciliación multi-moneda.
- Se publicó en #392 el cálculo del saldo GL bancario usando importes en moneda
  de cuenta cuando coinciden con la moneda de la cuenta bancaria.
- Las pruebas focalizadas pasaron: #389 (3), #391 (5) y #392 (1); Ruff,
  Flake8, Mypy, Black y `git diff --check` pasaron sobre los archivos tocados.

## 2026-08-11 — Reejecución de revalorización cambiaria en pre-release

- Se eliminó la unicidad artificial por compañía/período de `ExchangeRevaluation`.
- Una nueva ejecución anula primero las afectaciones GL publicadas previamente
  del mismo período y calcula nuevamente los saldos actuales.
- Las ejecuciones sin cambios también se registran como eventos independientes,
  preservando la trazabilidad y permitiendo recalcular después de cambios en
  saldos, tasas o documentos abiertos.

## 2026-08-10 — Sincronización de PR #372 con estabilización

- Se integró `stabilization/inventory-audit` en la rama del PR #372 para
  resolver sus conflictos y permitir su incorporación posterior.
- Se preservaron el cálculo de reclasificaciones parciales del PR y las
  protecciones de estabilización, incluida la exclusión de facturas futuras.

## 2026-08-10 — Compensación de recepción posterior a factura 2-way en múltiples recepciones

### Petición

Cuando una factura de 2 vías cubre solo parte de una orden y la orden es recibida en múltiples documentos, deducir la cantidad ya reclasificada por las recepciones enviadas anteriormente antes de devolver el monto disponible de la factura de 2 vías.

### Implementación

- Se modificó `_late_two_way_invoice_amounts(document: PurchaseReceipt)` en `cacao_accounting/accounting_engine/document_builders.py`.
- Ahora consulta todas las demás recepciones de compra ya confirmadas/enviadas (`docstatus == 1`, excluyendo devoluciones y el documento actual) asociadas al mismo `purchase_order_id`.
- Simula la reclasificación secuencial/cronológica de cada recepción previa para deducir de forma precisa los importes ya consumidos de la factura de 2 vías.
- Se agregó la prueba unitaria `test_late_two_way_reclassification_deducts_prior_receipts` en `tests/test_07posting_engine.py` para asegurar que las recepciones posteriores no sobre-clasifiquen los gastos y que el remanente correcto se asigne a la cuenta puente (GRNI).
- Se ejecutaron Black, Ruff, Flake8, mypy y la suite de pruebas unitarias relevante, confirmando el cumplimiento de calidad al 100%.
## 2026-08-11 — Corrección de hallazgos del análisis del PR #366

- Se evitó la doble reclasificación de facturas 2-way cuando existen varias
  recepciones posteriores y se escaló la variación de precio a la cantidad
  realmente conciliada.
- Los ajustes bancarios ahora preservan la atomicidad de la conciliación,
  derivan el signo según depósito/retiro y seleccionan explícitamente la
  transacción bancaria afectada.
- La valuación histórica se reconstruye con deltas al corte solicitado.
- Las notas de crédito validan nuevamente el saldo de la factura origen con
  bloqueo `FOR UPDATE` inmediatamente antes de la aprobación, incluyendo el
  flujo de aprobaciones.

## 2026-08-11 — Refactor del workflow CI: lint en job separado

### Petición

Refactorizar `.github/workflows/python-package.yml` para separar las pruebas de
lint en un job particular, de modo que los fallos de estilo (línea en blanco
faltante, línea de 121 caracteres, etc.) no frenen la ejecución de las pruebas
unitarias.

### Implementación

- Se creó el job `lint` (Python 3.13) que ejecuta `flake8`, `ruff`,
  `pydocstyle` y `mypy` sobre `cacao_accounting/`.
- Se eliminó el paso "Lint project code" del job `build`, que corría dentro de
  cada elemento de la matriz (3.12/3.13/3.14) y abortaba el pytest del mismo job.
- Decisión de diseño: los jobs de CI quedan sin dependencias entre sí
  (`needs`), por lo que `build`, `databases`, `desktop` y `coverage` corren en
  paralelo e independientemente del resultado del lint, que pasa a ser un
  chequeo informativo por separado.

## 2026-08-10 — Integración de diferencias bancarias dentro de la transacción de conciliación

- `submit_journal(commit=False)` permite publicar el asiento de diferencia sin
  confirmar la transacción externa.
- `_post_bank_difference_adjustment` usa ese camino y la prueba de atomicidad
  verifica que un fallo posterior revierta el asiento y la conciliación.

## 2026-08-10 — Triage de issues de auditoría contra el código vigente

### Petición

Comparar los issues abiertos de GitHub contra el código de la rama
`stabilization/inventory-audit`: cerrar los superados y proponer fixes con
commit semántico (author/sign-off `williamjmorenor@gmail.com`) sin cerrar los
no resueltos.

### Implementación

- Se trabajó en la comparación y cierre de issues, implementando fixes específicos
  en O2C, Bancos e importaciones, y manteniendo un alto control de calidad en los
  módulos afectados.
