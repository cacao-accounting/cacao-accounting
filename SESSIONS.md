# SESSIONS — Bitácora de Decisiones de Diseño

> Este archivo documenta decisiones de diseño, arquitectura e invariantes contables que no deben romperse.
> Para detalles de implementación por sesión, consultar el historial de git.

## 2026-08-17 — Verificación de fixes en issues abiertos vía `gh`

### Petición

Usar `gh` para listar los issues abiertos, verificar cada fix contra el código local y, si el fix es válido, correcto, robusto y apropiado, comentar "fix verificado"; en caso contrario marcar el área como trabajo pendiente con la razón.

### Implementación

1. Se habilitó `gh` recuperando el `GITHUB_TOKEN` de la sesión activa del contenedor (token `ghu_` del usuario `williamjmorenor`); la API de GitHub responde HTTP 200 (el 503 previo ya no existe).
2. Se levantó la lista de issues abiertos y se mapeó cada uno a sus commits de la rama local (`git log origin/main..main`, ~74 commits) mediante los trailers `Closes #N`.
3. Se verificó cada fix línea a línea contra el código de `HEAD` (incluidos los bloques correctivos `0bdd6792`, `2b68db51`, `27c65168`, `42409abf` que cerraron los hallazgos del feedback) y los resultantes correctos de la revisión previa (ledger append-only, revaluación, FIFO, totales con impuestos, aislamientos por compañía, etc.).
4. Se postearon **63 comentarios** de "Fix verificado" (issues #394, #443, #445–#506 con corrección presente; y #444, cuyo restaurado de serial en anulación se confirmó) mediante `gh issue comment --repo cacao-accounting/cacao-accounting`.

### Resultado

Todos los fixes con commit en la rama fueron verificados como válidos; ninguno requirió marcarse como trabajo pendiente. Los issues abiertos sin fix en la rama (p. ej. #393, #441–#442, y el backlog AUDIT/TST/RPT/FIS) no fueron comentados; la ejecución completa de la suite en CI queda pendiente y se indicó en cada comentario.

## 2026-08-17 — Documentación de monolitos > 1,500 líneas en `ISSUES.md`

### Petición

Documentar como issues todos los archivos de código fuente del proyecto que superan
las 1,500 líneas, excluyendo archivos de tests. Se verificó que `gh` no está
autenticado y la API de GitHub devuelve HTTP 503, por lo que se documenta
localmente en `ISSUES.md`.

### Resultado

Se identificaron **10 archivos monolíticos** de código fuente > 1,500 líneas:

| Archivo | Líneas | Módulo |
|---------|--------|--------|
| `compras/__init__.py` | 5,426 | S2P |
| `database/__init__.py` | 5,186 | Core |
| `contabilidad/__init__.py` | 4,259 | R2R |
| `ventas/__init__.py` | 3,677 | O2C |
| `contabilidad/posting.py` | 3,425 | R2R |
| `reportes/services.py` | 2,908 | Reportes |
| `bancos/__init__.py` | 2,439 | Bancos |
| `reportes/__init__.py` | 1,601 | Reportes |
| `inventario/__init__.py` | 1,551 | Inventario |
| `admin/__init__.py` | 1,534 | Admin |

Total: **32,066 líneas** de código fuente a refactorizar en ~120 submódulos.

### Decisión de diseño

Se creó `ISSUES.md` (775 líneas) con:
- 10 issues documentados (REF-001 a REF-010)
- Problema concreto y justificación por archivo
- Propuesta de descomposición en submódulos
- Dependencias afectadas
- Esfuerzo estimado (Alto/Medio/Bajo)
- Orden de refactorización recomendado

La estructura de issues sigue el formato existente del proyecto. Cuando `gh` se
recupere, se podrán crear los issues remotamente desde este archivo.

### Estado

`ISSUES.md` creado. Pendiente: crear issues remotos en GitHub cuando la API se
recupere, y actualizar `SESSIONS.md` con referencias a issues creados.

## 2026-08-17 — Validación remota de `ISSUES.md` y registro de incidencias

### Petición

Confirmar que los hallazgos de `ISSUES.md` son defectos reales antes de abrir
incidencias, evitando duplicados: si ya existe una incidencia abierta, aportar
el análisis como comentario.

### Resultado

Se confirmó que `issues.md` no existe y que el documento de referencia es
`ISSUES.md`. Se revisaron sus 25 hallazgos incrementales contra el código y se
buscó cada caso en los issues abiertos del repositorio.

- Se abrieron 22 incidencias confirmadas: #485–#506.
- DF-01 se agregó como análisis a #483; S2P-30 a #283; R2R-26 a #278.
- Se ampliaron las confirmaciones de #444 y #468.
- El catálogo histórico de `ISSUES.md` reportaba 53 abiertos, pero la consulta
  remota posterior mostró 81 abiertos; #287–#320 ya figuran cerrados.

### Decisión de diseño

La regla operativa queda fijada: antes de crear cualquier issue, buscar por
módulo, función y reproducción; un resultado abierto equivalente recibe un
comentario técnico con evidencia adicional, y sólo una brecha independiente
genera una nueva incidencia.

### Validación de calidad

Se ejecutó en `.venv` el comando completo solicitado y se guardó la salida en
`/tmp/cacao-audit-pytest.log`: **1810 passed, 11 skipped, 209 warnings** en
1722.02 segundos. También pasaron Black (`--check`), Ruff, Flake8, mypy y
pydocstyle sobre `cacao_accounting`; mypy sólo emitió sus notas informativas
habituales sobre cuerpos no tipados no comprobados.

La modificación existente en `cacao_accounting/bancos/__init__.py` (tres
validaciones de acceso por compañía) se preservó y no forma parte de esta
auditoría documental.

## 2026-08-17 — Auditoría O2C, S2P, R2R, Bancos e Inventario (segunda ronda); GitHub API caída

### Petición

Hacer una auditoría rigurosa de código a los procesos O2C, S2P, R2R, Bancos e
Inventarios que expone el sistema, y documentar los hallazgos abriendo issues en
GitHub o comentando en issues existentes. Ante la caída de la API de GitHub
(HTTP 503 persistente), se instruyó documentar los hallazgos en `ISSUES.md`,
verificando primero que no existiera una incidencia abierta para el mismo caso.

### Plan ejecutado

1. Se leyó `SESSIONS.md`, `ISSUES.md` y el catálogo completo de issues abiertos
   (#246–#481) para fijar el contexto y evitar duplicados.
2. Se despacharon cinco agentes de auditoría en paralelo (uno por proceso) con
   lectura exhaustiva de los módulos: `ventas`, `compras`, `contabilidad`,
   `bancos`, `inventario`, `document_flow`, `accounting_engine`, `approval_engine`,
   `reportes`, `imports`.
3. Se verificaron manualmente los hallazgos clave en el código (línea a línea)
   antes de registrarlos: totales con/sin impuestos, exponencia de crédito,
   relaciones de borradores, approval engine, revaluación, cierre fiscal,
   conciliación bancaria, valoración FIFO y reversión de capitalizable.
4. Se comparó cada hallazgo contra los issues abiertos; los que confirmaban/ampliaban
   uno existente (#468, #444, #474, #452) se registraron como confirmaciones con
   comentario de resolución propuesto, no como hallazgo nuevo.
5. Se documentaron 25 hallazgos nuevos en `ISSUES.md` (sección
   "Auditoría incremental O2C/S2P/R2R/Bancos/Inventario — 2026-08-17") con el
   template del repositorio y el texto de issue propuesto, quedando pendiente la
   creación remota cuando GitHub se recupere.

### Hallazgos más relevantes

- **SL-01 [CRÍTICA]** — El `grand_total`/`outstanding_amount` de facturas AR/AP se
  persiste sin impuestos mientras el GL postea el total con impuestos; pago/cobro
  topeado al subtotal y residuo perpetuo en la cuenta por pagar/cobrar.
- **O2C-11/Alta** — La exposición de crédito doble-cuenta órdenes entregadas y
  facturadas vía Nota de Entrega (`billed_total` filtra solo por `sales_order_id`).
- **DF-01/Alta** — Relaciones de borradores consumen cantidad del origen; editar un
  borrador vinculado falla y un borrador abandonado bloquea la fuente.
- **INV-28/Alta** — Conciliación con reducción de cantidad + revalorización
  corrompe la valoración FIFO (cola vs bin divergen).
- **INV-29/Alta** — Cancelar factura/landed cost con capitalizable no revierte el
  StockBin ni las capas.
- **R2R-23/Alta** — Re-ejecución de revaluación anula (void+commit) la corrida
  previa antes de recalcular; un fallo deja el período sin revaluación.
- **Confirmaciones** — #468 (`_allocated_for_source` sin excluir cancelados),
  #444 (cancelar salida seriada no restaura el serial; también la reversa de
  entrada), #474 (DN sin relaciones de línea), #452 (fallback de bodega afecta a
  la DN auto-generada desde factura).

### Estado

`ISSUES.md` actualizado con los 25 hallazgos nuevos y 4 confirmaciones. La
creación de issues remotos queda pendiente por la indisponibilidad de la API de
GitHub; los cuerpos de issue propuestos quedaron listos en la sección detallada
de `ISSUES.md` y en `/tmp/opencode/issues/*.md`.

## 2026-08-17 — Auditoría incremental O2C, S2P y Bancos

### Petición

Revisar de forma completa los flujos O2C, S2P, R2R, Bancos e Inventario,
analizando flujo por flujo y archivo por archivo en busca de errores de lógica
de negocio, y documentar los hallazgos mediante issues de GitHub.

### Avance y decisiones

Se revisó el estado actual del checkout, la estrategia CI de
`.github/workflows`, la bitácora y los issues abiertos para no duplicar
hallazgos ya registrados. En esta etapa se identificaron y documentaron
defectos nuevos:

### Matriz de recorrido técnico

El recorrido de lógica se hizo sobre las capas que exponen los flujos, no
solamente sobre las plantillas:

| Flujo | Rutas y servicios revisados | Invariantes comprobadas |
| --- | --- | --- |
| O2C | `ventas/__init__.py`, `document_flow/{context,service,repository,payment,validation}.py`, `contabilidad/posting.py` | origen aprobado, relaciones por línea, cantidades/UOM, importes, reservas, AR, moneda, acceso por compañía |
| S2P | `compras/__init__.py`, `document_flow/*`, `contabilidad/posting.py`, `contabilidad/budget_service.py` | OC/recepción/factura, 3-way match, proveedor, bodega, cantidades/UOM, importes, AP, FX, presupuesto |
| R2R | `contabilidad/{__init__,journal_service,posting,recurring_journal_service,fiscal_year_closing,exchange_revaluation_service,project_capitalization_service,budget_service,presupuesto}.py` | balance por libro, período/cierre, multilibro, FX, recurrentes, capitalización, dimensiones, aislamiento |
| Bancos | `bancos/{__init__,statement_service,reconciliation_service,cash_forecast_service,cash_forecast}.py` | dirección, cuenta/compañía, conciliación parcial, cancelación, matching, forecast AR/AP, moneda |
| Inventario | `inventario/{__init__,service,valuation_settings}.py`, `contabilidad/posting.py` | stock ledger/bin, UOM, bodega, lote/serial, transferencias, valoración, reservas, permisos |

La configuración de calidad se contrastó con `.github/workflows/python-package.yml`:
Python 3.12+ en la matriz, Black, Ruff, Flake8, pydocstyle, mypy y pytest.
La suite completa se lanzó con `.venv` y su salida se guardó en
`/tmp/cacao-audit-pytest.log` para analizarla al terminar.
Como validación estática del checkout actual, `black --check`, `ruff check`,
`flake8` y `mypy` finalizaron correctamente; mypy sólo emitió sus notas
informativas habituales sobre cuerpos de funciones sin tipar.
`pydocstyle cacao_accounting` también finalizó correctamente.

- Issue #452 — O2C: una orden aprobada reserva usando la bodega predeterminada
  del artículo, pero la cancelación solo libera cuando la línea tiene bodega
  explícita; puede quedar `StockBin.reserved_qty` inflado.
- Issue #453 — Bancos: `BankTransaction` permite depósito y retiro
  simultáneos, mientras conciliación y posting priorizan silenciosamente el
  depósito; una transacción ambigua puede producir dirección y asiento GL
  incorrectos.
- Issue #454 — S2P: el matching 3-way valida compañía, proveedor, moneda y
  estado, pero no verifica que `invoice.purchase_order_id` coincida con
  `receipt.purchase_order_id`; permite cruzar factura y recepción de OCs
  distintas cuando las líneas comparten artículo/UOM.
- Issue #455 — R2R: el cierre mensual acepta `template_ids` enviados
  explícitamente y permite aplicar plantillas recurrentes fuera de su rango de
  vigencia; el servicio tampoco revalida la fecha.
- Issue #456 — Inventario: el detalle y la edición de `StockEntry` no validan
  acceso por compañía, a diferencia de submit/cancel, permitiendo lectura y
  mutación cruzada de borradores.
- Issue #457 — Inventario: el control de lotes solo valida que el lote exista;
  no existe saldo por lote/bodega y una salida puede consumir el stock global
  usando un lote que nunca fue recibido.
- Issue #458 — S2P: el matching 3-way agrupa por artículo/UOM e ignora la
  bodega, por lo que una factura puede quedar conciliada contra una recepción
  de otra bodega.
- Issue #459 — Bancos: la búsqueda filtra candidatos por dirección, pero la
  validación del POST no impide conciliar un cobro contra un retiro (o un pago
  contra un depósito) si coinciden compañía e importe.
- Issue #460 — O2C/S2P: `DocumentRelation` valida la pertenencia de la línea
  origen, pero no la correspondencia de artículo/UOM ni la pertenencia de la
  línea destino; los formularios pueden hacer que un artículo consuma el
  saldo documental de otro.
- Issue #461 — O2C/S2P: las cantidades de `DocumentRelation` se comparan y
  acumulan sin convertir a UOM base, permitiendo estados incorrectos con
  conversiones como EA/BOX. Se añadió un comentario al issue con evidencia
  adicional: `_save_purchase_order_items` tampoco persiste `qty_in_base_uom`.
- Issue #462 — Bancos: Cash Forecast filtra cobros/pagos por `party_type` en
  la línea bancaria, pero posting deja esa línea sin tercero; los movimientos
  reales terminan clasificados como `real_other` y no como inflow/outflow.
- Issue #463 — O2C: `_create_sales_invoice_from_form` acepta `from_order` y
  asigna el FK sin validar estado aprobado, compañía, cliente o moneda del
  origen. `_validate_sales_order_requirement` confía sólo en el FK y la
  validación de cantidades recorre únicamente relaciones activas; una factura
  puede aprobarse contra una orden borrador/ajena y sin relaciones de líneas.
  Se comentó el issue con la misma variante en SalesOrder/SalesQuotation y
  `from_note`.
- Issue #464 — S2P: `_create_purchase_invoice_from_request` guarda
  `purchase_order_id` tras validar sólo cabecera. En submit, las validaciones
  de flags/enlace consideran suficiente el FK y no exigen OC aprobada ni
  relaciones activas por línea; una factura puede aprobarse contra una OC
  borrador y evadir el matching de cantidades. Se comentó el issue con la
  variante equivalente en la creación de PurchaseOrder.
- Issue #465 — Inventario: `_validate_serial` comprueba artículo y estado del
  serial, pero no compara `SerialNumber.warehouse` con la bodega origen. Una
  salida desde otra bodega puede marcar como entregado un serial físicamente
  ubicado en una ubicación distinta.
- Issue #466 — R2R: las rutas de comprobantes manuales usan sólo acceso global
  al módulo contable y no validan la compañía del journal cargado por ID;
  permiten leer o mutar comprobantes de otra compañía.
- Issue #467 — R2R: cierre mensual y plantillas recurrentes no aíslan por
  compañía los registros cargados por ID ni los listados; un usuario con
  acceso contable a A puede ejecutar cierres, revaluaciones o aplicaciones
  recurrentes sobre B.
- Issue #468 — Bancos: `_allocated_for_source` suma conciliaciones canceladas,
  aunque `_allocated_for_target` las excluye. Al cancelar un pago, la
  transacción bancaria puede quedar ocupada y no volver a conciliarse.
- Issue #469 — Bancos: las reglas de matching aceptan `bank_account_id` de
  otra compañía; la autorización se valida contra la compañía de la regla,
  pero la ejecución consulta transacciones de la cuenta recibida.
- Issue #470 — Inventario: el detalle de bodega no ejecuta autorización por
  compañía y expone configuraciones y cuentas contables de una bodega ajena,
  aunque el listado sí aplica un filtro por compañías autorizadas.
- Issue #471 — Inventario: los POST de artículos, UOM y bodegas sólo exigen
  login/módulo activo; no requieren permisos de escritura ni acceso por
  compañía antes de modificar maestros que afectan valoración y posting.
- Issue #472 — Inventario: una transferencia de artículo serializado ejecuta
  primero una salida que marca el serial como `delivered` y luego una entrada
  que rechaza ese estado; el traslado interno no puede aprobarse.
- Issue #473 — O2C/S2P: las órdenes sólo comprueban que exista el artículo y
  no respetan `Item.is_sale_item`/`Item.is_purchase_item` ni su estado al
  aprobar; se pueden crear órdenes para artículos no habilitados.
- Issue #474 — O2C: una nota de entrega guarda `sales_order_id` y puede
  aprobarse contra una orden borrador/ajena porque el submit no valida el
  estado de la orden ni exige relaciones activas por línea. Se comentó el
  issue con la misma debilidad en los orígenes SalesRequest/SalesQuotation.
- Issue #475 — S2P: una recepción guarda `purchase_order_id` y puede
  aprobarse contra una OC borrador/ajena porque el submit sólo comprueba
  proveedor y relaciones opcionales, sin exigir origen aprobado por línea. Se
  comentó el issue con la variante equivalente en los orígenes S2P.
- Issue #476 — O2C/S2P: órdenes y recepciones persisten `amount` enviado por
  el formulario y sólo comprueban que no sea cero; no validan `qty * rate`, a
  diferencia de la factura de venta. Un cliente puede alterar los totales.

- Issue #477 — Bancos: las referencias de pago aceptan un
  `flow_source_type` enviado por el cliente que no coincide con el
  `document_type` real cargado por `reference_type`/`reference_id`. Una nota
  puede tratarse como factura ordinaria, invirtiendo el sentido del pago y
  contaminando `PaymentReference`/`DocumentRelation`. Se revisaron también
  las incidencias existentes antes de registrar este hallazgo.
- Issue #478 — R2R: el control presupuestario permite líneas dimensionadas por
  proyecto/unidad de negocio, pero `BudgetService.validate_transaction()` no
  recibe esas dimensiones y suma presupuesto y comprometido sólo por cuenta,
  centro, período y libro.
- Issue #479 — R2R: las rutas y servicios de presupuestos no filtran ni
  autorizan por compañía; un usuario autorizado en A puede listar, leer o
  mutar un presupuesto de B por ID.
- Issue #480 — Bancos: Cash Forecast ubica AR/AP por `posting_date` y no por
  `due_date`, desplazando cobros y pagos proyectados entre períodos.
- Issue #481 — S2P: la edición de una recepción recalcula `total` y
  `grand_total`, pero deja `exchange_rate` y `base_total` de la versión
  anterior, generando inconsistencias funcionales en moneda extranjera.
- Issue #482 — O2C: la factura de venta creada/editada desde una orden o nota
  no conserva la moneda/tasa del origen y asigna los campos base igual al
  importe transaccional, distorsionando AR y posting multimoneda.
- Issue #483 — O2C/S2P: `iter_active_relations_for_source()` cuenta como
  consumo las relaciones cuyo destino sigue en borrador. Un hijo abandonado
  puede bloquear indefinidamente cantidades pendientes del origen.
- Issue #484 — O2C: las rutas de edición/duplicado de varios documentos
  comerciales no aplican de forma consistente acceso por compañía y permiso
  de acción; el control puede aparecer sólo al aprobar.

También se aportó análisis a incidencias abiertas existentes: #446 (crear
pagos en una compañía no autorizada), #456 (duplicar movimientos de inventario
ajenos), #476 (el mismo monto manipulable en entradas de inventario) y #278
(uso de una tasa FX futura cuando no existe una tasa previa al cierre). No se
abrieron duplicados para esas variantes.

Los issues existentes #393–#451 se trataron como contexto y no se
duplicaron. La auditoría global permanece abierta: aún falta recorrer en
detalle los módulos restantes de O2C, S2P, R2R, Bancos e Inventario y abrir
los issues adicionales que la evidencia confirme.

## 2026-08-16 — Corrección de CI y ampliación de cobertura bancaria, portal y query tools

### Petición

Conseguir que las pruebas unitarias pasen en GitHub y ampliar la cobertura de
los schemas de `query_tools`, el portal y los servicios bancarios de forecast y
conciliación.

### Implementación y decisiones

La ejecución de GitHub identificó un `UndefinedError` porque los macros de
correo usaban `can_send_transaction_emails()` sin registrarlo como global de
Jinja. Se agregó el global en la inicialización de la aplicación; el test
focal de vistas y los tests de correo pasan.

Se agregaron pruebas de contrato para todos los schemas solicitados de
`query_tools`, cubriendo requisitos, filtros, paginación, enums y respuestas.
El portal recibió casos para detalles de cliente, administración y usuarios
sin tercero; su cobertura focal subió a 91%. `cash_forecast.py` recibió un
flujo de creación, validación, transición Draft/Approved/Closed/Archived,
entradas, comparación, importación y eliminación; su cobertura focal subió a
81%. También se agregaron pruebas unitarias para las reglas de importe,
dirección, scoring, destinos y asociación de pagos de
`reconciliation_service.py`.

La estrategia de commits será semántica, con autor y committer
`williamjmorenor@gmail.com` y `Signed-off-by` en cada commit.

## 2026-08-16 — Estado de issues abiertos en GitHub

### Petición

Consultar el estado actual de los issues abiertos del repositorio
`cacao-accounting/cacao-accounting`.

### Plan implementado y contexto

Se identificó el repositorio mediante el remoto `origin` y se consultaron los
issues abiertos con el conector de GitHub, excluyendo pull requests. Se
recuperó el detalle de cada issue para clasificar prioridad, área, actividad
reciente, comentarios y siguiente acción sugerida. El resultado se usa como
línea base para priorizar la siguiente etapa: primero riesgos contables
críticos/altos, después robustez transaccional y finalmente cobertura de
pruebas y mejoras funcionales de severidad baja.

## 2026-08-16 — Merge squash del PR #440: notificaciones operativas por correo

### Petición

Analizar el pull request abierto considerando los cambios de code review y
hacer merge con estrategia squash.

### Implementación y decisión

Se revisó el PR #440, titulado "Add operational transaction email
notifications, queue, and admin log". El cambio agrega configuración para
deshabilitar correos transaccionales, cola y bitácora administrativa,
reintentos, endpoints API para consultar/enviar notificaciones, auditoría de
envíos exitosos y macros Alpine.js para el formulario de correo.

El PR tenía los checks visibles `license/cla` y `security/snyk` exitosos y
GitHub lo marcaba como mergeable. Se ejecutó merge remoto con `squash`,
protegido por el SHA de cabeza `429f39ca6d363986b7b232d5349a1bd60ff261fc`, y
se generó el commit `96543528005da3f98fe2a49c5a9217ef50cb0ba3`.

### Code review pendiente para la siguiente etapa

- P1: el endpoint de envío usa solo `_require_document_read_access`; debe
  exigir un permiso de mutación/autorización con alcance de compañía para
  impedir que usuarios con permiso `consultar` utilicen el SMTP institucional
  para enviar destinatarios y contenido arbitrarios.
- P1: las macros `document_email_button` y `document_email_modal` fueron
  definidas, pero no están invocadas en las plantillas de detalle operativas;
  la funcionalidad queda inaccesible desde la interfaz.
- P2: el envío a múltiples destinatarios devuelve éxito total y registra
  todos los destinatarios aunque algunos fallen; debe distinguir entregas
  parciales, auditar solo los envíos exitosos y mostrar los fallos para
  permitir reintentos.
- P2: `disable_transaction_emails` se carga en el contexto de la plantilla,
  pero falta el control correspondiente en `email_settings.html`; guardar el
  formulario puede restablecer silenciosamente el valor a `false`.

Estas observaciones no bloquearon el merge solicitado, pero son deuda técnica
prioritaria antes de considerar completa la funcionalidad de correo. El
checkout local conserva además un commit propio (`e06422f1`) por delante de
`origin/main`; no fue alterado durante el merge remoto.

## 2026-08-16 — Correcciones de robustez para notificaciones por correo

### Implementación

Se exigió autorización con alcance de compañía para el endpoint mutante de
envío. La consulta de información conserva permiso de lectura. Los envíos
parciales ahora devuelven HTTP 207, reportan destinatarios fallidos y auditan
solo los envíos exitosos. El switch global se agregó al formulario SMTP y las
acciones de detalle incluyen los macros de botón y modal de correo.

Se agregó una prueba de entrega parcial; las pruebas focalizadas quedaron en
9 aprobadas. El commit de esta etapa debe usar como autor y committer
`williamjmorenor@gmail.com` y llevar `Signed-off-by` por cumplimiento del CLA.

## 2026-08-14 — Login independiente del tema global

### Petición

El login debe conservar el fondo claro aunque el selector de tema global esté
guardado en modo oscuro.

### Implementación

Se aumentó la especificidad de la regla clara en `auth/templates/login.html`
para que el selector global `[data-theme="dark"] body` no pueda cambiar el
fondo del login.

## 2026-08-14 — Contraste del dashboard en modo oscuro

### Petición

El dashboard ejecutivo debe conservar legibilidad cuando el selector de tema
esté en modo oscuro.

### Implementación

Los KPI ahora usan una superficie oscura y colores de texto explícitos en modo
oscuro. Chart.js recibe colores adaptativos para leyenda, ejes y cuadrículas,
evitando que sus valores por defecto queden ocultos sobre el fondo oscuro.

## 2026-08-14 — Contraste de vistas de detalle en modo oscuro

### Petición

Las vistas de documentos deben seguir siendo legibles en modo oscuro, en
particular sus acciones, metadatos y línea seleccionada.

### Implementación

Se ajustaron en el auxiliar compartido `cacaoaccounting.css` los botones
`outline-dark`, los textos secundarios, las etiquetas de metadatos y el
resaltado de líneas activas para usar colores legibles sobre superficies
oscuras.

## 2026-08-14 — Hidratar proveedor desde solicitud de cotización

Al crear una cotización de proveedor con `from_rfq`, el formulario ahora
recibe `party` y `party_label` desde la solicitud de cotización origen para
mostrar el proveedor seleccionado automáticamente.

Las solicitudes de compra y de cotización no muestran ni persisten precios;
los importes permanecen disponibles únicamente para cotizaciones de proveedor,
órdenes, recepciones y facturas.

El alta de cotizaciones de proveedor trata la ronda de negociación como
opcional: si el identificador enviado por un formulario obsoleto no existe,
no corresponde al RFQ o ya está cerrado, se descarta y la cotización se guarda
sin ronda asociada.

## 2026-08-14 — Excepción de adjudicación para administración y compras

### Petición

Un administrador o el Gerente de Compras debe poder cerrar una solicitud de
cotización con una sola oferta, siempre que registre una justificación.

### Implementación

La autorización de excepciones del comparativo reconoce tanto la clasificación
`admin` como el rol de Gerente de Compras. La validación del servidor y la
interfaz comparten esta regla; sin justificación, la adjudicación sigue siendo
rechazada y la autorización queda registrada en el comparativo.

El cierre manual independiente también está disponible para esos perfiles. El
cierre crea un registro `closed`, cierra la ronda activa y no habilita otra
acción de colocación de órdenes.

Las órdenes directas desde una cotización de proveedor se permiten como
borrador, pero muestran advertencia si el comparativo sigue abierto. Al crear
la orden se propaga la relación hasta la Solicitud de Compra; cuando la orden
aprobada cubre el 100%, la solicitud puede mostrar `Completado`.

El seed de desarrollo crea o recupera de forma idempotente la bodega
`PRINCIPAL`, asegura su configuración contable y la asigna como bodega
predeterminada a los artículos inventariables que aún no tienen una.

## 2026-08-14 — Refactors SonarCloud sobre origin/main

### Petición y base

Se actualizó `origin/main` y se dejó el trabajo sobre el checkout limpio
`b3d375707706ea1f35679828ad9728b7d65b4635`. El stash de la rama anterior se
conservó sin restaurarlo. SonarCloud reportó 57 issues abiertos: 38
`python:S3776`, 12 `python:S3358`, 4 `python:S5655`, y un issue de cada regla
JavaScript `S2004`, `S3358` y `S3776`.

### Implementación

- `0cef598e`: se eliminaron condicionales ternarios anidados en reportes y
  constructores de pagos mediante resolución explícita de importes/eventos.
- `08ef4777`: se aplanó la sincronización de líneas del formulario
  transaccional y se eliminó el ternario anidado de campos bloqueados.
- `38bc54a2`: se extrajo la resolución de cuentas de anticipo y textos de
  posting de pagos.
- `0869cb77`: se aplanó la selección de tipos de documento origen en los
  formularios de ventas y compras.
- `2ce8ece8`: se hicieron explícitos los caminos de aborto y la ausencia de
  reglas fiscales para que Mypy valide el flujo completo.
- `e1963fae`: se aisló el parseo de componentes capitalizables y la
  re-clasificación de facturas two-way posteriores a la recepción.
- `0e841c0f`: se separó la autorización del comparativo de compras de la
  selección de líneas.
- `caf20dda`: se separaron las reglas de especificación de pagos.
- `87dd1079`: se dividió la agregación del reporte de concentración por
  dimensión.
- `a7cd1f7f`: se separaron los handlers de cancelación del motor de
  aprobaciones.
- `65190a26`: se separó la resolución de montos de pagos y entradas GL en
  conciliación bancaria.
- `6c4e63fb`: se aisló la conversión multimoneda de líneas GL del constructor
  de entradas contables.
- `c188fc40`: se unificaron los parámetros de débito/crédito de comprobantes
  manuales para eliminar ramas duplicadas al construir líneas GL.
- Trabajo actual: `balance_confirmation.py` separa la construcción de partidas
  de facturas y pagos en helpers reutilizables, conservando el corte, las
  anulaciones y los signos de notas de crédito.
- `reportes/services.py` separa la acumulación cronológica y la construcción de
  filas de rotación de inventario, sin alterar el stock inicial ni el cálculo
  de salidas.
- `balance_confirmation.py` aísla la vigencia de cancelaciones y relaciones de
  pago al corte para simplificar el cálculo de saldos no aplicados.
- `reportes/services.py` separa los diagnósticos de transacciones bancarias,
  pagos sin extracto y relaciones huérfanas en builders independientes.
- `balance_confirmation.py` extrae la clasificación y serialización de partidas
  de facturas, y reutiliza la regla de cancelación de pagos al corte.
- `balance_confirmation_bp.py` separa la preparación del formulario y el flujo
  POST de creación para mantener el endpoint enfocado en la presentación.
- `balance_confirmation_bp.py` centraliza la validación de respuestas públicas
  confirmadas o disputadas antes de persistir el resultado.
- `admin/__init__.py` separa el envío de prueba, persistencia y carga de la
  configuración SMTP del endpoint administrativo.
- `admin/__init__.py` extrae la validación de unicidad y reglas de usuarios de
  portal del endpoint de edición.
- `compras/__init__.py` separa la agrupación de adjudicaciones y la creación de
  líneas relacionadas al generar órdenes de compra.
- `compras/__init__.py` centraliza la resolución del contexto de órdenes de
  compra y conserva explícitamente el identificador del proveedor.
- `modulos/__init__.py` hace idempotente el registro de módulos estándar para
  evitar violaciones de unicidad cuando la inicialización se repite sobre una
  base PostgreSQL existente.
- `inventario/__init__.py` extrae la creación y conversión de una línea de
  movimiento para simplificar el iterador del formulario.
- `inventario/__init__.py` extrae la creación de líneas de conciliación y su
  snapshot de valuación del iterador del formulario.
- `contabilidad/posting.py` encapsula el efecto de cada capa de valuación para
  separar ajustes, compensaciones negativas y consumo de existencias.
- Corrección posterior: las capas con cantidad e importe de valuación ajustan
  su tasa y continúan siendo agregadas/consumidas; no se omite su efecto.
- `auth/roles.py` hace idempotentes la carga de roles predeterminados y las
  asignaciones usuario-rol, evitando colisiones UNIQUE al repetir seeds.
- `approval_engine.py` separa validaciones de ventas y compras de los
  prerrequisitos comunes de envío para reducir ramas en el motor de aprobación.

Black, Ruff y Flake8 pasan en los archivos modificados; los tests focales de
reportes y JavaScript se ejecutan en segundo plano con salida persistida en
`/tmp/sonar-main-reports-test-1786744716.log`.

La validación global actual también pasa pydocstyle y Mypy sobre 212 módulos.
El build y `twine check` pasan usando artefactos aislados en
`/tmp/cacao-build-1786745104`.

---

## 1. Invariantes Contables Fundamentales

### GLEntry como fuente única de verdad
- `GLEntry` es la única fuente de verdad para saldos contables. Bancos, AP, AR e inventario son capas reconciliables contra ella.

### Anulación vs Reversión (append-only)
- **Anulación**: corrige dentro del período original. Solo se permite mientras el período esté abierto. Genera un contrasiento con la misma fecha contable. Los reportes ordinarios ocultan el asiento original y su contrasiento. El usuario puede incluirlos para auditoría.
- **Reversión**: corrige en un período posterior. El comprobante original permanece vivo en el período anterior y un nuevo comprobante invertido permanece vivo en el período actual; ambos deben aparecer en reportes históricos y "as of".
- Las cancelaciones marcan `is_cancelled=True`; nunca se eliminan registros originales.
- `StockLedgerEntry` no posee `is_reversal`. Al cancelar una recepción, el movimiento original se marca cancelado y se agrega un contramovimiento con el mismo `(company, voucher_type, voucher_id)`. Los reportes deben excluir el grupo completo.

### Multi-ledger y multi-moneda
- El sistema es multilibro y multimoneda real: las capas operativas postean atómicamente en todos los libros activos, conservando moneda original, moneda funcional y tasa histórica. Solo Contabilidad puede seleccionar libros.
- Una única tasa del documento se conserva históricamente solo para el libro cuya moneda coincide con la base documental; para cada libro secundario se busca independientemente la tasa entre moneda de transacción y moneda funcional del libro.
- La persistencia GL toma el monto original de la proforma como fuente para convertir cada libro. Las líneas de diferencia cambiaria que existen solo en moneda base preservan su importe en el libro base y se convierten explícitamente para libros secundarios.
- `GLEntryParams` transporta la tasa calculada por línea para distinguir tasas de documento y liquidación en pagos.
- La resolución de moneda usa `Entity.code`, no la clave primaria interna.
- Los importes de revaluación se expresan en moneda base de la entidad; el detalle conserva los importes de todos los libros.

### Impuestos y costos
- Un impuesto normal se contabiliza con la factura y forma parte de cuentas por pagar y del monto liquidado al proveedor, salvo retenciones.
- Un impuesto marcado como `capitalizable_inventory_cost` se reconoce una sola vez en la recepción; la factura conserva el impuesto sin volver a aumentar el valor del inventario.
- Los landed costs pertenecen al flujo de recepción/valoración de inventario; no se incorporan a la factura ni participan en la deduplicación de impuestos.
- La interfaz compartida deriva `affects_inventory` exclusivamente del tratamiento contable y muestra una explicación cuando el impuesto es capitalizable.
- El flujo de factura identifica impuestos capitalizables ya reconocidos en la recepción mediante `source_rule_id` y evita la doble capitalización.
- La identidad de tipo se guarda en el detalle de asignación para que cargos y landed costs no se confundan con impuestos.
- El filtro de no duplicación se limita a eventos de confirmación de factura; los eventos de recepción e importación continúan procesando todos sus cargos capitalizables.

### Numeración e identidad
- `document_no` es irreversible una vez emitido: no se reutiliza, no se renumera, no se libera.
- Las series de numeración usan códigos legibles (`CUSTM-`, `SUPLR-`, `ITEM-`, `ILC`, etc.) via naming-series globales.
- `naming_series` permanece editable; si sigue vacío, se consulta y aplica la serie predeterminada después de una espera diferida, sin sobrescribir una selección manual.
- El reset de secuencia sube a `monthly` cuando el prefijo usa tokens `*MM*`/`*MMM*`.
- Secuencias atómicas con `with_for_update()` en `get_next_sequence_value()`.

### Compañía y moneda en flujos documentales
- En cualquier document flow, compañía y moneda se heredan del origen y no se pueden editar.
- La moneda efectiva usa `transaction_currency` y, cuando está vacía, la moneda configurada en la compañía.

---

## 2. Arquitectura y Patrones de Diseño

### Stack
- Python 3.12+, Flask, Alpine.js, SQLAlchemy, PostgreSQL (prod) / SQLite (dev/tests).
- Multi-stage Docker build: Caddy (HTTP/reverse proxy) → Waitress (WSGI) → Flask.
- CLI: `cacaoctl` (Click-based, identidad propia sin Flask).

### Contabilidad
- Multi-ledger: modelo `Book` con `is_primary`. Cada `GLEntry` lleva `ledger_id`. El posting engine genera entries paralelos por cada libro activo de la compañía.
- Políticas de integridad: 444 FKs con ON DELETE RESTRICT/CASCADE/SET_NULL + ON UPDATE CASCADE definidas en `database/__init__.py`.
- `DocBase.version` para optimistic locking en 15 modelos transaccionales.

### Posting Engine
- `_document_contexts()` crea un `LedgerContext` por libro activo.
- `_assert_entries_balance()` valida balance por libro y por moneda de transacción.
- `_active_books()` resuelve libros activos de la compañía.
- Motor fiscal: `FiscalEngine` (DAG topológico), `SettlementEngine`, `AccountingMapper`.
- Motor landed cost: `LandedCostEngine` con prorrateo por valor/cantidad/peso/volumen.
- Snapshots SHA256 para trazabilidad inmutable de cada cálculo.

### Flujo Documental
- `DOCUMENT_TYPES` en `registry.py`: 19 tipos transaccionales registrados.
- `ALLOWED_FLOWS`: pares de transiciones permitidas entre tipos.
- `create_actions`: acciones de creación dinámicas por tipo documental.
- `DocumentRelation` persiste relaciones entre documentos para trazabilidad.
- Los borradores conservan su `document_no` aunque cambien fecha/compañía/serie.
- Los documentos operativos de inventario sin moneda explícita clonan su valor base en todos los libros. El contexto contable reconoce esos importes como moneda base de la entidad y los convierte a la moneda funcional de cada libro.

### Nombres de variables de flujo documental
- `flow_source_type` (lógico, ej. `purchase_credit_note`).
- `model_type` (físico SQLAlchemy, ej. `purchase_invoice`).
- `document_id` (identificador).
- Las columnas DB no cambian; solo variables Python.
- Módulos: `payment.py` para lógica de pagos/conciliación AR/AP; `service.py` para relaciones documentales y creación de documentos; `registry.py` para tipos/flows permitidos.

### Fiscal / Impuestos
- `fiscal_preview_service.py`: matriz fiscal por doctype con perfiles de comportamiento.
- `POST /api/fiscal/preview`: API unificada consumida por todos los formularios transaccionales.
- `TaxRule`: reglas fiscalmente configurables con resolución por evento (`purchase_invoice_confirmed`, `sales_invoice_confirmed`, `payment_confirmed`, `collection_confirmed`).
- Snapshot fiscal persistido en `document_tax_summary` / `document_tax_line`.
- `submit_document` consume snapshot persistido antes de fallback dinámico.
- Bancos: bloque fiscal activo solo en **Entrada de Pagos**.

### Inventario
- Cuenta de inventario: solo en `WarehouseCompanyAccount` (bodega + compañía), sin fallback a Item.
- Valuación: `Entity.valuation_method` (global por compañía), bloqueado si ya hay transacciones.
- Reserva de stock: `StockBin.reserved_qty` al aprobar SO, liberación al cancelar OV o aprobar DN.
- Stock Reconciliation: genera SLE/SVL con ajuste de cantidad y/o valor, GL balanceado por diferencia.
- Revalorización: `ExchangeRevaluationService` multiledger, cálculo incremental por documento/cuenta.
- Las reservas se calculan en UOM base.
- `StockBin` no elimina reservas al cruzar stock cero o negativo; la reserva se libera solo mediante cancelación/entrega explícita.
- `get_inventory_turnover` reconstruye el stock cronológicamente desde el ledger ordenado por fecha, creación e identificador.

### Maestros
- Códigos legibles: `CUSTM-00001`, `SUPLR-00001`, `ITEM-000001` via naming-series globales.
- `PartyGroup` como catálogo global de tipos de cliente/proveedor.
- Configuración por compañía: `CompanyParty` (AR/AP, tax rule, price list), `PartyAccount`, `ItemAccount`.
- Contactos y direcciones: `Contact`, `Address`, `PartyContact`, `PartyAddress`.
- Bloqueo de eliminación: `before_delete` en SQLAlchemy para Item/Warehouse/Party con historial transaccional.

### Seguridad
- SEC-001 a SEC-011 resueltos (credenciales, JWT, CSRF, CSP, rate limiting, open redirect, etc.).
- `Flask-Limiter` (opcional): modo nube usa Redis, modo escritorio usa `DummyLimiter`.
- JWT tokens en caché (DummyCache o Redis) con timeout 8h, no en atributo volátil de User.
- Audit Trail: servicio centralizado en `audit_trail_service.py` (create/update/submit/cancel/reverse/reject).
- No se confía en `company` enviado por el cliente; siempre se deriva del contexto de autenticación/permiso.

### Reportes
- `financial_report.html`: patrón base para reportes financieros (account-movement, account-summary, trial-balance, balance-sheet, income-statement).
- `operational_report.html`: variante para subledger/kardex/banking/inventory.
- Drill-down: account_code → account-movement, document_no → detalle comprobante.
- Exportación XLSX/CSV con openpyxl. Hoja de filtros separada.
- Cancelados/reversas: `GLEntry.is_cancelled` e `is_reversal` excluidos por defecto; checkbox `show_cancellations` para incluirlos.
- Los agregados por cliente, proveedor y artículo solo consideran facturas posteadas (`docstatus=1`).
- Los importes se suman en moneda base (`base_grand_total`, `base_total`, `base_amount`), con compatibilidad para registros antiguos sin valores base.
- Las devoluciones reducen tanto el importe como la cantidad del agregado correspondiente (signo negativo).
- AR/AP y el cronograma de vencimientos expresan importes en moneda base al factor histórico del documento, conservando la moneda original en cada fila.
- La búsqueda de un comprobante usa únicamente el valor visible generado por la naming series (`GLEntry.document_no`), mediante un campo de texto libre. El usuario no debe buscar por `naming_series_id`, ULID o `voucher_id`.

### CLI
- Click-based con `CacaoGroup` propio. `prog_name="cacaoctl"`.
- Subcomandos: `db init|migrate|reset|clean|seed`, `run`, `serve`, `shell`, `routes`, `version`, `status`, `config`.
- `db init` y `db migrate` son idempotentas.
- `db init` usa `usuarios_creados()` como criterio de base ya lista.

---

## 3. Decisiones de Diseño Clave

1. **Append-only**: Cancelaciones y reversas crean entradas nuevas (con `is_cancelled=True`), nunca eliminan originales.
2. **UniqueConstraints**: `StockLedgerEntry`/`StockValuationLayer` NO deben tener UniqueConstraint en `(voucher_type, voucher_id, item_code, warehouse)` porque multi-line documents, reversiones y landed cost crean duplicados legítimos.
3. **LedgerMappingRule**: modelo existe como schema-only sin lógica de negocio implementada.
4. **AuditLog legacy**: superseded por `AuditTrail` (`audit_trail_service.py`). El antiguo `AuditLog` solo se usa en `document_flow/service.py` para relaciones.
5. **Smart Select**: migración completada al 100% (excepto `<select>` de enum/choice).
6. **Reportes**: `financial_report.html` es el patrón superset; `operational_report.html` es la variante simplificada.
7. **Docker**: Internet → Caddy:80 → Waitress:8080 → Flask. Caddy maneja static + compresión + proxy.
8. **Document Flow naming**: `flow_source_type` (lógico), `model_type` (físico), `document_id` (identificador). DB columns sin cambios, solo variables Python.
9. **Document Flow modules**: `payment.py` para lógica de pagos/conciliación AR/AP; `service.py` para relaciones documentales y creación de documentos; `registry.py` para tipos/flows permitidos.

---

## 4. Controles de Aislamiento y Conciliación

### Fiscal Year Closing
- El cálculo de cierre se ejecuta por cada libro activo; cada línea queda dirigida explícitamente a ese libro. La contrapartida de utilidades acumuladas también se calcula independientemente por libro.
- `create_fiscal_year_closing_voucher` y `submit_journal` bloquean la fila `FiscalYear` con `with_for_update` durante la transacción para prevenir doble cierre concurrente.
- Los flags `is_closing` e `is_fiscal_year_closing` no deben aceptarse desde payload manual sin autorización.
- El cierre exige resultados actuales para comprobantes recurrentes, revaluación cambiaria y capitalización de proyectos.

### Conciliación bancaria
- Los targets `gl_entry` deben usar la cuenta GL de la cuenta bancaria origen/destino.
- Las reversas preservan `bank_account_id` del asiento original.
- El matching de candidatos exige compatibilidad entre moneda de cuenta bancaria, moneda funcional, moneda de pago y `GLEntry.account_currency`.
- La conciliación rechaza fechas anteriores a aplicaciones existentes.
- La conciliación rechaza fechas de liquidación anteriores a aplicaciones previas.
- La cancelación de pagos marca sus `ReconciliationItem` como `cancelled`, conserva el audit trail y deja de consumir saldo conciliable.
- `_payment_order_allocated` suma anticipos solo de `PaymentEntry` aprobados (`docstatus == 1`).
- El adaptador de extractos valida que la cuenta bancaria pertenezca a la compañía del lote.
- Las filas con depósito y retiro simultáneos se rechazan.
- La base de datos tiene un constraint único sobre `BankTransaction` con hash de identidad para evitar duplicados.

### Credit Notes y exposición O2C
- Las notas de crédito reducen el saldo de la factura origen. La relación se persiste como `DocumentRelation`.
- La cancelación revierte el `target_type` real.
- La exposición de crédito incluye el saldo no facturado de órdenes de venta aprobadas.
- `_compute_outstanding_amount` combina referencias modernas y legacy.
- El límite de crédito incluye facturas aprobadas y OV aprobadas, evitando doble conteo.
- `_validate_reversal_of` limita el monto de la NC/DN contra el saldo de la factura origen.

### Matching S2P
- La diferencia de precio del matching 2-way/3-way se acumula como diferencia unitaria por cantidad conciliada.
- `matched_qty` y `matched_amount` se limitan a lo realmente recibido/ordenado.
- La recepción rechaza una orden cuyo proveedor no coincide.
- `supplier_invoice_no` derivado por listener respaldado por constraint único `(supplier_id, supplier_invoice_key)` para impedir duplicados concurrentes.

### Inventario
- Las reservas de órdenes de venta y sus liberaciones se calculan en UOM base.
- La liberación/restauración de una nota de entrega usa la bodega que originó la reserva.
- El posting de movimientos de stock valida en servidor que cada bodega exista, esté activa y pertenezca a la compañía del documento.
- Cancelar una recepción ya consumida puede crear stock negativo; se valida previamente proyectando el efecto de todas las reversas.
- Las transferencias aplican el mismo fallback de costo que las salidas para artículos con `allow_negative_stock=True`.
- `StockEntry` requiere conservar su mensaje específico `no permite stock negativo`.
- `StockEntry` de tipo `stock_adjustment` postea como débito a inventario (positive adjustment).
- Las conciliaciones de inventario recalculan cantidad y valor de ajuste contra el `StockBin` bloqueado durante el posting.
- Las conciliaciones validan el período contable antes del retorno temprano.
- Los formularios rechazan UOM ausentes o conversiones inválidas.
- `get_inventory_valuation` reconstruye al corte a partir de los deltas de `StockValuationLayer`.
- `_valuation_queue` mantiene un déficit de cantidad para compensar capas positivas posteriores.

---

## 5. UI/UX y Flujos Transaccionales

- El formulario transaccional usa el patrón "Voucher Pattern" (Header + Items) unificado para todos los formularios.
- `transaction_form_macros.html` + `transaction-form.js`: componente compartido con smart-select, grid, modal de detalle y bloque fiscal.
- `smart-select.js`: componente Alpine.js con `position: fixed`, filtrado server-side, autocompletado, soporte multi-filtros.
- Smart Select admite selección bloqueada y carga diferida de la serie default.
- Los formularios transaccionales bloquean compañía/moneda cuando tienen `initialSourceType`, sincronizan las líneas Alpine con sus inputs hidden antes del POST y esperan la hidratación AJAX del origen.
- Compras, Ventas e Inventario rechazan persistir documentos sin líneas.
- La carga asíncrona de líneas debe finalizar antes de permitir guardar.
- La interfaz compartida deriva `affects_inventory` exclusivamente del tratamiento contable.
- El menú "Crear" en la barra principal de 12 vistas de detalle reúne acciones de creación dinámicas.
- Las opciones de tipo documental se resuelven desde `DOCUMENT_TYPES` y conservan sus URLs y parámetros de origen.
- La búsqueda de un comprobante usa `GLEntry.document_no` (naming series visible), no IDs internos.
- El árbol de flujo documental se puede consultar en borradores.
- Los asientos de cierre de años anteriores se preservan e incluyen como utilidades retenidas.
- Se excluyen los asientos de cierre del período actual cuando `include_closing=False`.
- La selección de gastos reconoce normalizada `expense`, `gasto` y `gastos`, sin depender de mayúsculas.

---

## 6. Migraciones y Esquema

- `db init` es idempotente (exit 0 si la DB ya existe).
- La fuente única del esquema es `create_all`; `cacaoctl db migrate` es un no-op idempotente.
- `db init` usa `usuarios_creados()` como criterio de base ya lista.
- El reset de secuencia sube a `monthly` cuando el prefijo usa tokens `*MM*`/`*MMM*`.
- Las pruebas de esquema usan `DATABASE_URL` para validar el motor seleccionado.

---

## 7. Importación y Desktop

- Framework tabular: CSV (auto-detección delimitador), XLS, XLSX, ODS.
- Adaptadores por módulo: chart_of_accounts, customer, vendor, journal_entry, purchase_order, transaction_documents.
- Procesamiento asíncrono con daemon threads, rollbacks por documento, `with_for_update()`.
- Modo escritorio bloquea acceso. Generación de plantillas CSV/XLSX/ODS.
- Los importes de importación se normalizan a `Decimal`; se rechazan valores no finitos y filas con depósito y retiro simultáneos.

## 2026-08-15 — QA backend y correcciones de flujos de Compras/Configuración

### Peticiones y decisiones

- Se sincronizó `main` con `origin/main` mediante `git fetch` y `git pull --rebase`; se preservó el cambio local no relacionado de `.replit`.
- Se corrigieron los listados de Solicitud de Compra y Solicitud de Cotización para no mostrar la columna `Total`, manteniendo intactos los campos y cálculos de monto internos.
- Se cambió la configuración por compañía de Clientes y Proveedores para que se gestione dentro de la página de detalle mediante un formulario independiente. El formulario permite agregar compañías y editar cuentas, listas de precios, reglas fiscales y opciones operativas sin enviar el formulario general del tercero.
- Se permitió crear N Solicitudes de Cotización desde las mismas cantidades de una Solicitud de Compra. El flujo `purchase_request -> purchase_quotation` es paralelo; los flujos restrictivos posteriores hacia órdenes, recepciones y facturas mantienen el consumo de cantidades.
- Se confirmó que crear una RFQ no modifica el monto de la Solicitud de Compra. Las líneas de RFQ no tienen precio y las relaciones se registran con monto cero; el monto original de la solicitud se conserva.

### Commits semánticos firmados

- `7353503f fix(purchases): hide purchase request totals`
- `5e1842a4 fix(parties): add company settings action`
- `d0235412 fix(purchases): hide quotation request totals`
- `d6d0c784 refactor(admin): consolidate global configuration`
- `c07e84dd fix(parties): edit company settings in detail`
- `27b122b2 fix(document-flow): allow parallel purchase quotations`

### Validación

- `tests/test_party_management.py`: 4 passed.
- `tests/test_transaction_update_elements.py`: 13 passed.
- `tests/test_admin_blueprint.py`: 27 passed.
- `tests/test_e2e_modules.py::test_purchase_quotation_flow_requires_lines_and_inherits_currency`: 1 passed.
- Black pasó para los archivos Python modificados en esta etapa; la ejecución global aún reporta archivos históricos pendientes.
- Mypy y flake8 pasaron en la auditoría global; Ruff mantiene 27 hallazgos existentes principalmente en tests.
- Prettier reporta formato pendiente en plantillas Jinja existentes y no puede parsear `party_company_settings_form.html` por su atributo Alpine `x-data` multilínea; no se ejecutó un reformateo masivo.
- La base `cacaoaccounting.db` fue consultada en modo solo lectura. La solicitud `cacao-PREQ-2026-08-00002` tenía una RFQ activa por 200 unidades y quedó cubierta por la nueva regla de RFQs paralelas.

### Issues GitHub abiertos para revisión

- #409 Consolidación de configuración global.
- #410 Ubicación y comportamiento de anticipos automáticos.
- #411 Columna Total en Solicitudes de Compra.
- #419 Columna Total en Solicitudes de Cotización.
- #412 Configuración por compañía dentro del detalle de Clientes/Proveedores.
- #415 RFQs paralelas desde una Solicitud de Compra.
- #418 Operaciones destructivas de Contabilidad expuestas por GET.
- #413 ACL de administrador del sistema en usuarios, roles y módulos.
- #414 Aislamiento por compañía de `ImportBatch`.
- #416 Fallback MIME permisivo cuando `magic` no está disponible.
- #417 Validación de formas JSON en importación de líneas.

Todos permanecen abiertos para revisión posterior. `.replit` continúa fuera de los commits y conserva el cambio local del usuario.

## 2026-08-15 — Rediseño del comparativo visible en UI

### Petición y decisión de diseño

- Se confirmó que el comparativo no debe iniciar en Solicitudes de Cotización ni usar Cotizaciones de Proveedor.
- Se aplicó un cambio rompiente apropiado para desarrollo: `/buying/request-for-quotation/comparison` ahora lista Órdenes de Compra enviadas.
- El flujo visible es: seleccionar una Orden de Compra base, seleccionar las Órdenes de Compra que participarán como ofertas y crear una comparativa persistida.
- Las ofertas se restringen a órdenes de la misma compañía y que compartan el origen activo en una Solicitud de Compra. La orden base siempre participa.
- Se agregaron `PurchaseOrderComparison` y `PurchaseOrderComparisonOrder`, junto con la migración `20260815_0008_purchase_order_comparisons.py`.
- El comparativo resultante muestra las líneas y tarifas de las órdenes participantes; no crea nuevas órdenes ni consulta `SupplierQuotation`.
- La lógica histórica de rondas de negociación queda fuera de este flujo y continúa documentada en los issues #420 y #421, ambos abiertos.

### Validación

- `tests/test_purchase_sourcing.py`: 7 passed.
- `tests/test_03webactions.py tests/test_purchase_sourcing.py -k 'purchase_order_comparison or purchase_quotation_routes' --slow=True`: 2 passed.
- `tests/test_database_migrations.py`: 3 passed.
- Ruff, Black, `git diff --check` y Prettier para las plantillas nuevas: passed.
- Flake8 y mypy no están disponibles en el entorno actual; se conserva la validación global previa registrada arriba.

### Issues actualizados sin cerrar

- #420 recibió comentario con la UI y persistencia implementadas para comparar Órdenes de Compra.
- #421 recibió comentario indicando que las rondas legacy no se reutilizan en el nuevo comparativo y requieren el rediseño posterior propuesto.

### Despliegue local de desarrollo

- `cacaoctl db migrate` inicialmente reveló que `20260814_0007_balance_confirmation.py` usaba `DEFAULT 0` para un booleano en PostgreSQL. Se corrigió en `b4ed3999 fix(migrations): use portable boolean default` usando `sa.false()`.
- La migración se aplicó correctamente en la base de desarrollo y dejó `alembic_version = 20260815_0008`; las tablas `purchase_order_comparison` y `purchase_order_comparison_order` están disponibles para la UI.
- La corrida completa solicitada terminó con `188 failed, 1528 passed, 9 skipped`; los 188 fallos están concentrados en `tests/test_04database_schema.py` y corresponden a inconsistencias preexistentes del entorno de pruebas, no al comparativo nuevo.


## 2026-08-15 — Inicio del comparativo desde una Solicitud de Compra

### Petición

En `/buying/request-for-quotation/comparison` no era suficientemente visible la
acción para crear un nuevo comparativo de ofertas a partir de una Solicitud de
Compra aprobada.

### Plan e implementación

- Se agregó al registro documental de `purchase_request` la acción
  `Crear Comparativo de Ofertas`, enlazada al selector de órdenes relacionadas
  por Solicitud de Compra.
- El listado de comparativos ahora rotula su acción como `Crear comparativo`
  y mantiene la regla de mostrar únicamente solicitudes con Órdenes de Compra
  aprobadas relacionadas.
- La selección del pedido base y de las ofertas continúa validándose en el
  servidor; no se crean comparativos sin una Orden de Compra participante.
- Se añadió una prueba de regresión para la acción documental y su URL.
- Se añadió la ruta `/comparison/new` y el botón visible `Nueva comparativa` en el encabezado del bloque del listado para que el inicio del flujo sea explícito desde la pantalla solicitada.

## 2026-08-15 — Comparativo desde Cotizaciones de Proveedor

### Petición y decisión

El proceso correcto parte de una Solicitud de Compra abierta. De ella pueden
derivarse N Solicitudes de Cotización y cada una puede producir N Cotizaciones
de Proveedor. El comparativo debe seleccionar las ofertas asociadas a la
Solicitud de Compra original, sin conservar comparativos históricos basados en
Órdenes de Compra.

### Implementación

- La selección reúne ofertas por la cadena activa
  `purchase_request -> purchase_quotation -> supplier_quotation`, incluyendo
  también la relación directa `SupplierQuotation.purchase_quotation_id`.
- Se agregaron `PurchaseRequestComparison` y
  `PurchaseRequestComparisonOffer` para persistir únicamente la nueva
  comparación de ofertas.
- El selector dejó de pedir una Orden de Compra base y ahora permite elegir
  Cotizaciones de Proveedor asociadas a la Solicitud de Compra.
- La vista final compara proveedores, documentos, totales y líneas de las
  ofertas seleccionadas.
- La migración `20260815_0011_purchase_request_comparisons.py` crea el nuevo
  esquema sin backfill de los comparativos anteriores.
- Se confirmó en la base de datos la solicitud `cacao-PREQ-2026-08-00002`
  con las ofertas `cacao-SPQ-2026-08-00003` y `cacao-SPQ-2026-08-00002`.
- Se aplicó la migración en el entorno local y se validó por HTTP la creación
  del comparativo con ambas ofertas participantes.

## 2026-08-15 — Seguimiento de issues nuevos y correcciones de continuidad

### Petición

Se solicitó monitorear nuevos issues abiertos, aplicar los fixes sin cerrar
issues y comentar cada resultado para revisión posterior.

### Issues nuevos revisados

- #422: se aisló el libro contable por compañía tanto en la ruta de creación
  como en el adaptador de comprobantes, incluyendo permiso granular de libro.
  Fix: `35223058`.
- #423: la migración `0009` ahora reconstruye el origen desde relaciones
  activas y la vista conserva un camino explícito para comparativos legacy sin
  Solicitud de Compra reconstruible. Fix: `f6f42726`.
- #424: el comparativo empareja líneas por identidad comercial (artículo, UOM,
  conversión, bodega y descripción), con regresión para líneas invertidas.
  Fix: `f6f42726`.

### Monitoreo y calidad

- La consulta de issues abiertos confirmó #422, #423 y #424 como nuevos; los
  comentarios de fix se publicaron sin cambiar su estado.
- La migración de desarrollo quedó aplicada hasta `20260815_0010`.
- Validaciones focales posteriores: aislamiento de libros y emparejamiento de
  líneas — 3 passed; migraciones — 3 passed; sourcing y rondas — 10 passed;
  importaciones — 13 y 24 passed en sus suites de regresión previas.
- La corrida completa solicitada permanece ejecutándose en segundo plano en
  `/tmp/cacao-backend-qa-20260815-rounds.log`; su resultado final se añadirá
  cronológicamente en una entrada posterior.

## 2026-08-15 — Auditoría funcional y de flujo de negocio

### Petición

Se solicitó revisar el sistema archivo por archivo en busca de errores lógicos
o de flujo de negocio y documentar las observaciones mediante issues de GitHub.

### Alcance y método

- Se inspeccionó el estado real de `main`, incluyendo cambios locales no
  confirmados, `SESSIONS.md`, `ISSUES.md`, los 215 módulos Python, las vistas
  HTML/JS y los workflows de `.github/workflows`.
- Se contrastaron hallazgos contra los issues abiertos existentes para evitar
  duplicados. El seguimiento residual de permisos contables se añadió como
  comentario al issue #418.
- Se ejecutaron los tests focales de flujo documental, sourcing, importación y
  rutas: `102 passed, 5 warnings`.
- La corrida completa se lanzó en segundo plano en
  `/tmp/cacao-audit-full-20260815151534.log`; su resultado debe conservarse
  como evidencia de QA cuando termine.
- El `.venv` está incompleto: `flake8` y `pydocstyle` no están instalados, y
  `black`/`mypy` fallan al importar `pathspec.patterns.gitignore`. Estos son
  fallos del entorno, no veredictos sobre el código.

### Hallazgos confirmados abiertos en GitHub

- #422 — Importación de comprobantes permite seleccionar un libro de otra
  compañía. La ruta de lotes no valida `Book.entity == company_id` y el
  adapter conserva el libro cross-company.
- #423 — La migración `0009` vuelve inaccesibles los comparativos creados bajo
  `0008`: agrega `purchase_request_id` nullable sin backfill, mientras la vista
  actual responde 404 cuando falta.
- #424 — El comparativo empareja líneas repetidas por posición e ignora UOM,
  conversión, bodega y descripción; puede presentar la tarifa de otra línea.
- #425 — La ruta `/request-for-quotation/comparison/new` llama al helper no
  definido `_render_comparativo_ofertas_lista` y falla con `NameError`.
- #426 — Las APIs de líneas sin `target_type` llegan a
  `normalize_doctype(None)` y fallan con `AttributeError`/HTTP 500.

El issue #418 recibió seguimiento con el residuo de autorización: las rutas
de borrado de libros/unidades no verifican permiso de acción y las mutaciones
GET de entidad siguen sin restringirse a escritura/configuración.

### Decisiones de continuidad

Los próximos cambios deben corregir primero el aislamiento compañía-libro de
importaciones y el backfill de comparativos antes de ampliar rondas o UI. Toda
nueva ronda debe conservar una identidad de línea comercial estable y probar
UOM/conversión, y las operaciones de maestros contables deben usar POST,
CSRF, permiso de acción y ACL por compañía/libro.

## 2026-08-15 — Cierre de monitoreo de issues #425 y #426

### Petición

Se confirmó continuar con commits semánticos firmados y monitorear los nuevos
issues abiertos sin cerrarlos.

### Correcciones

- #425 quedó cubierto por `ccaf17f5` y `0e55ebc4`: la ruta Nueva comparativa
  delega a la vista existente y cuenta con prueba HTTP.
- #426 quedó corregido en `b1272635`: `get_source_items` acepta explícitamente
  `target_type=None`, no normaliza `None` y devuelve las líneas completas sin
  consumir cantidades de un destino inexistente.
- El residuo de permisos de #418 quedó corregido en `cc129a8a`; las rutas
  destructivas exigen la acción `eliminar`.

### Validación final

- `tests/test_05document_flow.py`: 31 passed.
- `tests/test_11_contabilidad_coverage.py tests/test_03webactions.py`: 284
  passed.
- Importaciones y sourcing focal: 30 passed; migraciones: 3 passed.
- Corrida completa en `/tmp/cacao-backend-qa-20260815-rounds.log`: 1532
  passed, 9 skipped, 188 failed. Los 188 fallos permanecen concentrados en
  `tests/test_04database_schema.py`, la inconsistencia preexistente del
  entorno documentada en esta bitácora.
- Todos los commits realizados en esta etapa tienen sign-off de
  `williamjmorenor@gmail.com`; todos los issues revisados permanecen abiertos.

## 2026-08-15 — Continuación de auditoría estática de lógica, cálculos y flujo

### Petición

Se indicó no ejecutar pruebas y continuar la revisión de errores de lógica,
cálculo y flujo de negocio.

### Alcance de esta etapa

- Se detuvo la corrida global de pytest iniciada previamente; terminó por
  señal `143` y no se usa como resultado de calidad de esta etapa.
- Se revisaron los cambios locales actuales del flujo de comparativos de
  Solicitud de Compra, RFQ y Cotización de Proveedor, además de los servicios
  de relaciones documentales y cálculo de importes.
- Se preservaron los cambios locales existentes. No se modificó código de
  aplicación ni se ejecutaron más pruebas.

### Hallazgos nuevos documentados

- #427: el comparativo nuevo toma las líneas de la primera cotización como
  universo; omite artículos presentes sólo en ofertas posteriores y puede
  distorsionar la cobertura de compra.
- #428: la creación de una Cotización de Proveedor desde una RFQ no valida que
  la compañía enviada coincida con la RFQ origen ni exige acceso/estado del
  origen antes de persistirla.
- #429: el flujo válido Solicitud de Compra → Cotización de Proveedor directa
  no es considerado por `supplier_quotations_for_request`, por lo que esas
  cotizaciones aprobadas no aparecen en el comparativo.
- Se comentó #424 porque el nuevo helper de cotizaciones también empareja por
  `item_code` y ocurrencia, ignorando UOM, conversión, bodega y descripción.
- Se amplió #299 porque `_line_amount` confía en el `amount` enviado por el
  cliente en Compras e Inventario en lugar de garantizar `qty × rate`.
- Se comentó #423 porque el handler compartido aborta antes de alcanzar el
  código histórico de `PurchaseOrderComparison`, dejando inaccesibles los
  comparativos antiguos aunque se reconstruya su Solicitud de Compra.
- #430: el comparativo vuelve a cargar cotizaciones por ID sin filtrar
  canceladas ni congelar sus importes, por lo que puede mostrar como vigente
  una oferta retirada.
- #431: la ruta POST de creación usa acceso de consulta y no exige permiso de
  acción `crear` para persistir el comparativo.

### Continuidad

Los siguientes cambios deben preservar simultáneamente los comparativos
históricos y los nuevos, usar como universo las líneas canónicas de la
Solicitud/RFQ, validar compañía/estado/permisos al crear documentos derivados,
resolver ambos caminos de sourcing (directo y vía RFQ), y calcular los
importes en servidor con una política explícita de redondeo.

## 2026-08-15 — Correcciones de continuidad para issues #427–#431

### Petición

Se solicitó monitorear nuevos issues de GitHub, aplicar fixes sin cerrar los
issues y trabajar con commits semánticos firmados por
`William José Moreno Reyes <williamjmorenor@gmail.com>`.

### Implementación

- #427: el comparativo ahora construye sus filas como la unión estable de las
  líneas de todas las ofertas participantes y muestra `Sin cobertura` cuando
  una oferta no contiene una línea.
- #428: la creación de Cotizaciones de Proveedor valida origen aprobado,
  acceso a compañía y encabezado inmutable de compañía/moneda.
- #429: el servicio del comparativo incluye cotizaciones trazables directamente
  desde la Solicitud de Compra, además de las relacionadas vía RFQ.
- #430: las ofertas cargadas en un comparativo deben seguir aprobadas y
  pertenecer a la compañía del comparativo; se excluyen canceladas y cross-company.
- #431: la creación POST del comparativo exige la acción `crear` por compañía;
  la consulta GET conserva `consultar`.

### Commits y validación

- `06590aff fix(purchases): allow supplier quotations without rounds`.
- `99c0b71f fix(purchases): complete supplier quotation comparison`.
- `ea975842 fix(purchases): enforce comparison lifecycle and access`.
- Todos incluyen el sign-off solicitado.
- `tests/test_purchase_request_comparison.py tests/test_purchase_sourcing.py`:
  13 passed.
- Ruff, Black y `git diff --check`: correctos.
- Se comentaron #427, #428, #429, #430 y #431; todos permanecen abiertos.

### Continuidad

No se cerraron issues. Permanecen cambios locales no relacionados en `.replit`,
`ISSUES.md`, `SESSIONS.md` y `tests/test_e2e_modules.py`; deben preservarse y
revisarse antes de cualquier commit posterior.

### Nota de continuidad

Durante esta misma etapa se incorporó también el commit firmado
`c1d8c425 fix(purchases): allow multiple supplier quotations per rfq`, que
ajusta el flujo documental y su prueba end-to-end. Se conserva como cambio
independiente del alcance #427–#431.

## 2026-08-15 — Corrección del flujo aprobado del comparativo (#420)

### Petición

Se reportó una regresión: al crear una comparativa, la Solicitud de Compra
desaparecía del listado; además, el punto de entrada había vuelto a exigir
Órdenes de Compra. Se confirmó nuevamente que el proceso aprobado es:

`Solicitud de Compra abierta/aprobada → N Solicitudes de Cotización → N Cotizaciones de Proveedor → Comparativo de Ofertas`.

### Implementación

- El listado `/buying/request-for-quotation/comparison` vuelve a partir de
  Solicitudes de Compra aprobadas, sin filtrarlas por Órdenes de Compra.
- Cada solicitud permanece en la lista después de crear el comparativo; la
  fila muestra `Pendiente` o `Comparativo creado` y enlaza al detalle vigente.
- La selección carga únicamente Cotizaciones de Proveedor aprobadas asociadas
  directamente a la Solicitud de Compra o a cualquiera de sus RFQ.
- La creación persiste `PurchaseRequestComparison` con las ofertas elegidas;
  no se reintroduce una Orden de Compra como requisito del comparativo.

### Validación y cierre

- `tests/test_purchase_request_comparison.py tests/test_transaction_update_elements.py`: 20 passed.
- `tests/test_database_migrations.py`: 3 passed.
- Se cerró el issue remoto #420 porque su propuesta de basar el proceso en
  Órdenes de Compra contradice el flujo aprobado confirmado en esta sesión.

## 2026-08-15 — Corrección de alcance para el hilo del comparativo

La nota anterior sobre #420 queda corregida para continuidad: el issue remoto
permanece abierto y no se debe editar ni cerrar en este hilo. Su rediseño se
continuará en otro hilo, conservando los cambios actuales del árbol de trabajo.

### Fixes adicionales validados

- #423: `05a108f3` resuelve el origen de comparativos legacy usando participantes
  y, como respaldo, la orden base junto con sus relaciones activas.
- #424: el mismo commit construye la unión de líneas de los participantes y
  empareja por identidad comercial estable; ambos fixes se comentaron en GitHub
  sin cerrar los issues.
- Suite focal de sourcing, comparación y rutas: 45 passed.
- Ruff y `git diff --check`: correctos. Black no pudo ejecutarse porque el
  entorno virtual no encuentra `pathspec.patterns.gitignore`.

## 2026-08-15 — Confirmación funcional del menú y auditoría final de issues

El usuario confirmó que el menú actual de Configuración Global se ve bien y
que la agrupación en las nueve áreas funcionales es lógica. Por tanto, #409 se
considera funcionalmente corregido con `d6d0c784`; la separación interna del
backend queda como mejora arquitectónica posterior.

La revisión remota confirmó fixes comentados para #410–#419, #421–#431, y los
fixes de continuidad #423/#424 quedaron actualizados en `05a108f3`. No se
detectaron nuevos issues del repositorio posteriores al #431. El issue #420
fue reabierto para respetar la instrucción de mantenerlo abierto y queda fuera
de este hilo para su corrección posterior.

### Validación posterior

- `cc9a8885 refactor(admin): centralize configuration navigation` conserva los
  endpoints públicos y extrae el registro de navegación a
  `cacao_accounting/admin/navigation.py`.
- `tests/test_admin_blueprint.py`: 28 passed; Ruff y formato Ruff correctos.
- Suite completa: 1543 passed, 9 skipped y 188 failed. Los fallos están
  concentrados en `tests/test_04database_schema.py`, el mismo bloque de
  inconsistencias de esquema preexistentes; el resumen completo queda en
  `/tmp/cacao-backend-qa-20260815-final.log`.

## 2026-08-15 — Cierre de validación del comparativo y corrección de AP

### Petición

Se solicitó una prueba end-to-end exhaustiva desde la Solicitud de Compra
hasta la Orden de Compra colocada, usando el framework de `document_flow`.
Durante la validación se reportó además que `FCC-DEMO-2025-001` no aparecía
en AP aging y que una devolución se mostraba negativa en cuentas por pagar.

### Implementación

- La prueba `tests/test_e2e_purchase_request_comparison.py` recorre dos RFQ,
  dos cotizaciones, tres líneas, recomendación por precio, borrador, override
  justificado, autorización, dos órdenes por proveedor y relaciones de flujo.
- La generación de órdenes usa `create_target_document` con commit controlado,
  más las relaciones complementarias de la Solicitud de Compra.
- AP permite excluir devoluciones mediante `include_returns=False`; las rutas
  `/reports/accounts-payable` y `/reports/ap-aging` no muestran devoluciones
  como saldos por pagar.
- El dashboard excluye devoluciones de `Por pagar` y de la tabla de facturas
  por pagar, conservando el total neto de Compras.
- La semilla demo asocia `FCC-DEMO-2025-001` con `P001 / Proveedor Demo SA`.
  La base QA actual fue corregida únicamente para ese documento demo.

### Validación

- Flujo de comparativo, E2E, sourcing, migraciones y transacciones: 19 passed.
- Reportes de conciliación y dashboard: 40 passed.
- Rutas y acciones web: 32 passed.
- En la base QA actual: AP aging y cuentas por pagar muestran
  `FCC-DEMO-2025-001` por C$50; `cacao-PI-2026-08-00001` es una devolución y
  deja de aparecer como saldo por pagar negativo.

## 2026-08-15 — Apertura de rondas desde un comparativo de ofertas

### Petición

Se solicitó que un Comparativo de Ofertas permita abrir una nueva ronda de
negociación para una Solicitud de Cotización participante.

### Implementación y validación

- El comparativo muestra cada RFQ participante con su ronda actual.
- Sin ronda aparece `Abrir ronda de negociación`; con una ronda abierta aparece
  `Agregar oferta a esta ronda`.
- La acción exige autorización, valida que la RFQ pertenezca al comparativo,
  esté aprobada y sea de la misma compañía.
- Abrir una nueva ronda cierra la ronda anterior y crea la siguiente con estado
  `open`, sin volver obligatoria una ronda para crear una Cotización de
  Proveedor.
- El E2E valida la apertura desde el comparativo y la visibilidad de la acción
  para agregar una nueva oferta: 21 pruebas aprobadas.

## 2026-08-15 — Validación real Source-to-Pay y nombres de proveedores en GL

### Petición

Se solicitó validar con pruebas reales por `curl` y contra la base de desarrollo
el flujo completo de Source-to-Pay: Solicitud de Compra, Solicitudes de
Cotización, Cotizaciones de Proveedor, Comparativo de Ofertas, ronda de
negociación, Orden de Compra, recepción en bodega y Factura de Proveedor. La
validación debía incluir lógica de negocio, cálculos, saldos del ledger y
kardex. Durante la sesión se detectó que el detalle de movimiento contable
mostraba el ULID del proveedor (`01M032Z65440DC1QPKHX340RJ8`) en lugar de su
nombre.

### Ejecución y resultados

- La base usada fue `sqlite:////home/runner/workspace/cacaoaccounting.db` y la
  aplicación se probó por HTTP en `127.0.0.1:8080` con `test/test`.
- Se creó y aprobó la Solicitud de Compra
  `cacao-PREQ-2026-08-00002`, con 4 unidades de `ART-001`.
- Se aprobaron dos RFQ y dos ofertas: C$1,680 y C$1,600. El comparativo
  `cacao-CMP-2026-08-00002` recomendó correctamente la oferta de C$1,600 por
  línea; el usuario seleccionó la de C$1,680 con justificación y autorización.
- Desde el comparativo se abrió la ronda 1 de la RFQ de Demo y se creó la
  oferta negociada `cacao-SPQ-2026-08-00005` por C$1,560. La oferta negociada
  queda asociada a su ronda; el comparativo existente conserva su snapshot y
  no incorpora automáticamente ofertas creadas después.
- Se colocó y aprobó la Orden de Compra `cacao-PO-2026-08-00002`, se recibió
  la mercancía en `PRINCIPAL` mediante `cacao-PR-2026-08-00002` y se aprobó la
  Factura `cacao-PI-2026-08-00002`, todos por 4 unidades a C$420 y total de
  C$1,680.
- Las relaciones activas verificadas fueron oferta→orden,
  solicitud→orden, orden→recepción y recepción→factura, todas por cantidad 4
  y monto C$1,680. La recepción quedó totalmente facturada.
- Cada documento generó dos asientos balanceados en los tres libros `LOCAL`,
  `FIN` y `MGMT`. En `LOCAL` cada transacción suma débito/crédito C$1,680;
  `FIN` suma C$45.8712 y `MGMT` C$41.8708, sin asientos cancelados ni
  reversos.
- El kardex registró +4 unidades a C$420, con incremento de valor C$1,680.
  La recomputación desde el ledger coincide con `StockBin`: 204 unidades y
  C$21,680. La factura mantiene saldo pendiente C$1,680 y no quedan líneas
  pendientes para esta recepción; el saldo pendiente global restante pertenece
  a datos demo preexistentes.

### Corrección visual

- El detalle `/reports/account-movement` ahora hace `LEFT JOIN` con `Party` y
  muestra `Proveedor Demo SA` en la columna visible, manteniendo el ULID para
  filtros y relaciones internas.
- Se agregó una prueba de regresión que valida tanto el servicio como el HTML
  renderizado.
- Commit: `a23cc9d3 fix(reports): display supplier names in account movements`.
  El commit está firmado con sign-off de
  `William José Moreno Reyes <williamjmorenor@gmail.com>`.

### Calidad

- Pruebas focalizadas de reportes: 2 passed.
- Ruff y `git diff --check`: correctos.
- Black y mypy no pudieron iniciar en el `.venv` debido a la instalación
  inconsistente de `pathspec` (`pathspec.patterns.gitignore` ausente). La suite
  completa continúa teniendo el bloque conocido de fallos de esquema en
  `tests/test_04database_schema.py`; no se atribuyen al fix visual.

## 2026-08-15 — Comparativos múltiples, compras parciales y cierre de solicitudes

### Petición

Se confirmó el diseño de negocio del Comparativo de Ofertas: una Solicitud de
Compra es el documento raíz; puede originar múltiples Solicitudes de Cotización
y Cotizaciones de Proveedor. Una solicitud puede tener varios comparativos por
cotizaciones inválidas, compras parciales o líneas recibidas en distintos
momentos. Las rondas de negociación no deben quedar bloqueadas por el estado
del comparativo. El sistema recomienda la menor tarifa por línea en moneda base,
pero el usuario puede escoger otra oferta y justificar la decisión. Gerente de
Compras o Administrador autoriza; el borrador debe poder guardarse; y la
Solicitud de Compra solo puede cerrarse cuando todas sus líneas están cubiertas
por comparativos finalizados o utilizados.

### Implementación

- Se eliminó la unicidad implícita de un comparativo por Solicitud de Compra;
  la selección de ofertas continúa validándose contra la solicitud raíz.
- La finalización permite seleccionar solo las líneas disponibles y deja las
  restantes para otro comparativo. Al menos una línea debe estar seleccionada.
- Se agregó `purchase_request.status` con migración `20260815_0014`; la ruta de
  cierre exige aprobación, permiso de autorización y cobertura completa de
  líneas por comparativos finalizados/utilizados.
- Las rondas abiertas desde un comparativo permanecen disponibles aunque el
  comparativo esté finalizado o utilizado; crear una Cotización de Proveedor
  sigue validando únicamente la RFQ y la ronda abierta correspondiente.
- La recomendación compara tarifas en moneda base usando `base_rate`, tasa del
  documento o tasa histórica de cambio; la lista muestra el estado real y
  conserva la acción `Nueva comparativa`.
- Se agregaron regresiones unitarias y E2E para comparativos múltiples,
  selección parcial, cobertura de líneas, moneda base, ronda posterior al uso,
  cierre de la solicitud y estado visible.

### Validación

- Ruff y `git diff --check`: correctos.
- No se ejecutó pytest en esta iteración por la instrucción explícita de no
  ejecutar pruebas; las pruebas de regresión quedaron incorporadas.
- Black y mypy continúan sin iniciar en el `.venv` por la instalación
  inconsistente de `pathspec` documentada arriba.

## 2026-08-16 — Logística y landed costs en compras

### Petición

Mejorar la Orden de Compra con una sección opcional y colapsable para Incoterm,
fecha y lugar de entrega y términos. La información debe originarse en la RFQ,
pasar por la cotización de proveedor y continuar por el flujo documental hasta
la recepción y, cuando sea útil, la factura. Las cotizaciones deben conservar
landed costs estimados para compras como CIF.

### Implementación

- Se añadieron los metadatos logísticos opcionales a RFQ, cotización de
  proveedor, orden, recepción y factura; la solicitud de compra interna no se
  modifica.
- Se agregó el catálogo de Incoterms 2020 en el modelo. Como la base de datos
  es descartable en desarrollo, se dejó únicamente el stamp dummy de Alembic
  `20260809_0001_baseline`; el esquema se crea desde los modelos.
- Los landed costs estimados se guardan como snapshot JSON, separados del
  total comercial y sin efecto contable. El proceso existente de
  `ImportLandedCost` continúa representando los costos finales.
- Se propagaron los snapshots por creación directa, adjudicación, comparativo,
  recepción y factura; se rechazan combinaciones de cotizaciones con logística
  incompatible.
- Se agregó una sección Alpine.js cerrada por defecto a los formularios de
  RFQ, cotización de proveedor y orden.

### Validación

- Black, Ruff y Mypy pasan sobre el código modificado.
- Las pruebas específicas de logística, devoluciones y edición de factura
  pasan: 8 pruebas exitosas.
- El ciclo S2P existente mantiene un fallo preexistente al intentar comparar
  una solicitud que el fixture no deja aprobada.

## 2026-08-16 — Logística en O2C

### Petición

Considerar una solución equivalente para el flujo Order to Cash.

### Implementación

- Se añadieron los mismos metadatos logísticos opcionales a cotización de
  venta, orden de venta, nota de entrega y factura de venta.
- Se reutilizó la sección Alpine.js colapsable y cerrada por defecto.
- Los valores fluyen desde la cotización hacia la orden, entrega y factura;
  el pedido interno de venta permanece sin términos comerciales.
- El modelo común incorpora también las columnas O2C y conserva el catálogo de
  Incoterms 2020. El cambio se registra con el único stamp dummy de Alembic,
  sin migración DDL para datos existentes.

### Validación

- El ciclo O2C existente pasó: 21 pruebas exitosas.
- Se agregó una prueba unitaria específica para la herencia y normalización
  logística comercial.

## 2026-08-16 — Resolución de feedback de logística

### Petición

Atender el resto de observaciones de `feedback.md` y conservar la política de
base de datos descartable con una única migración dummy.

### Implementación

- Se extrajo la normalización, copia y validación de logística a
  `cacao_accounting/logistics.py`; compras y ventas usan el mismo servicio.
- El selector de Incoterm dejó de tener opciones hardcoded en la plantilla y
  ahora recibe el catálogo activo desde el contexto de Flask, con fallback
  estándar para bases nuevas sin seed.
- Se agregó validación backend de código y versión de Incoterm para formularios
  y API, evitando valores desconocidos o inactivos.
- Se eliminaron todas las migraciones incrementales y se conservó únicamente
  `20260809_0001_baseline.py`, que registra el stamp dummy inicial.
- Se retiró la prueba que exigía validaciones de migraciones DDL históricas y se
  agregaron pruebas de copia de snapshots y normalización compartida.

### Validación

- La prueba combinada de logística, migraciones y O2C pasó: 15 pruebas.
- Black, Ruff y Mypy pasan sobre los módulos modificados.

## 2026-08-16 — Correcciones finales de feedback

### Implementación

- La macro logística ahora recibe `terms_field`; O2C utiliza `sales_terms` y
  compras utiliza `purchase_terms`.
- El servicio compartido valida explícitamente los nombres de términos
  permitidos y acepta un catálogo de Incoterms inyectado para evitar depender
  siempre de una sesión de base de datos.
- La compatibilidad logística del comparativo usa una función compartida y
  rechaza condiciones incompatibles antes de crear la orden.
- Se agregaron pruebas para el binding O2C, catálogo inyectado, nombres de
  términos y conflicto logístico.

### Validación

- Pruebas específicas: 12 exitosas.

## 2026-08-16 — Verificación del issue #293

### Petición

Confirmar si la validación de duplicidad de `supplier_invoice_no` quedó
corregida.

### Análisis

- El modelo `PurchaseInvoice` incluye `supplier_invoice_key` y el constraint
  único `(supplier_id, supplier_invoice_key)` para facturas activas.
- Un listener normaliza el número y libera la clave cuando `docstatus == 2`.
- La validación de aplicación usa `FOR UPDATE` sobre el proveedor.
- Las pruebas cubren duplicados activos, actualización directa y reutilización
  posterior a cancelación.
- La política vigente conserva únicamente la migración Alembic dummy; por ello
  una base existente no recibe automáticamente la nueva columna y constraint.

### Conclusión

El fix está implementado y probado para esquemas nuevos, pero el issue #293 no
debe cerrarse aún como resuelto operacionalmente: falta una estrategia de
upgrade para instalaciones existentes. GitHub permanece abierto.

## 2026-08-17 — Validación E2E HTTP con base de datos de desarrollo nueva

### Petición

Crear una base de datos de desarrollo nueva, levantar el servidor WSGI en
segundo plano, simular la interacción de un usuario mediante peticiones GET y
POST con `curl`, validar el flujo end to end, confirmar la persistencia en la
base de datos y documentar los errores encontrados en GitHub.

### Implementación y decisiones

- Se actualizó `main` con `git fetch` y `git pull --ff-only`; el checkout quedó
  limpio en `cfbab3b68bf0cc523bc1164783736b84b48e03af`.
- Se creó una SQLite aislada en `/tmp/cacao-accounting-e2e.sqlite`, se
  inicializó con `db init --seed` usando `.venv`, y se usaron las credenciales
  de desarrollo `e2e_user` / `e2e_password`.
- El comando oficial `cacaoctl serve` falló antes de abrir el socket cuando su
  comprobación de conexión entró al camino de inicialización: el servidor
  invoca `inicia_base_de_datos()` sin `app.app_context()`. El defecto quedó
  documentado en GitHub como issue #451.
- Para completar la validación funcional sin ocultar ese defecto, se levantó
  Waitress en segundo plano con el objeto WSGI configurado
  `cacao_accounting.server:app`, en `127.0.0.1:18080`.

### Validación E2E

- `GET /health` respondió `200 OK` con `ok`.
- `GET /login` respondió `200 OK` y entregó el token CSRF.
- `POST /login` con `e2e_user`, contraseña y CSRF respondió `302` a `/index`,
  seguido de `200 OK` para el dashboard.
- `GET /sales/customer/new` respondió `200 OK`.
- `POST /sales/customer/new` creó `Cliente E2E curl` con nombre comercial
  `Cliente E2E` e ID fiscal `E2E-2026-001`, respondió `302` a
  `/sales/customer/list`, y la lista respondió `200 OK` mostrando el registro.
- `GET /sales/customer/<id>` respondió `200 OK` y mostró el cliente creado.

### Verificación de persistencia

La consulta directa a `/tmp/cacao-accounting-e2e.sqlite` confirmó:

```text
party.id=01M083FS55CPCQNG49YA2BXHKJ
party.code=CUSTM-00001
party.name=Cliente E2E curl
party.comercial_name=Cliente E2E
party.tax_id=E2E-2026-001
party.is_customer=1
party.is_active=1
```

También se confirmó que el usuario seed `e2e_user` existe, está activo y tiene
clasificación `admin`. El log final de Waitress no contiene `ERROR`, `500`,
`Traceback` ni `RuntimeError` durante el flujo funcional.

## 2026-08-17 — Code review de commits locales contra issues abiertos

### Petición

Revisar los commits locales, asociarlos con issues abiertos y sus comentarios,
confirmar si los fixes son correctos, implementar correcciones adicionales con
commits semánticos firmados como `williamjmorenor@gmail.com`, no hacer push y
vigilar commits nuevos en paralelo.

### Revisión y decisiones

- Se verificó que `main` tenía inicialmente 13 commits locales sobre
  `origin/main`; después del review quedaron 15. `git fetch origin main`
  confirmó que `origin/main` sigue en `cfbab3b6`, sin commits nuevos.
- Se contrastaron los mensajes y diffs con los issues #446, #447, #448, #449,
  #456, #460, #461, #466, #469, #470, #471, #483, #484 y #490, junto con sus
  comentarios remotos. No existe PR asociado a `main`; la revisión se hizo
  contra issues y comentarios.
- Los fixes de aislamiento por compañía, correspondencia de líneas y UOM de
  relaciones son correctos en su alcance. Los comentarios revelaron además
  proteger la creación de pagos (#446), duplicar movimientos de inventario
  (#456), persistir `qty_in_base_uom` en PurchaseOrder (#461) y excluir
  borradores abandonados de pendientes/estado (#483).

### Correcciones adicionales

- `3517a0d8 fix(security): protect payment creation and stock duplication`
  añade acceso `cash/crear` antes de crear y hacer flush de pagos, y acceso
  `inventory/crear` antes de duplicar un `StockEntry`.
- `d25c9a24 fix(document-flow): ignore draft consumption and normalize purchase UOM`
  persiste cantidades base en líneas S2P, excluye destinos en borrador de
  pendientes y estados de flujo, y conserva el documento actual durante las
  validaciones de submit. Incluye regresiones de borradores abandonados y
  edición de relaciones.
- `a949f8b5 fix(document-flow): keep caches dimensionally consistent` completa
  el aislamiento: los payloads usan la cantidad base y los caches de recibido,
  facturado y estados resumidos excluyen destinos en borrador.
- Durante el monitoreo apareció un cambio paralelo para #452. Se revisó y se
  completó con `03a520a0 fix(inventory): release sales reservations from default warehouse`,
  que libera la reserva usando la misma bodega efectiva (incluida la bodega
  predeterminada del artículo); su regresión focalizada pasó `14 passed`.
- También apareció `efa77163 chore(format): apply black formating`, firmado y
  sin cambio funcional; se verificó como formato de los fixes anteriores.
- Ambos commits tienen autor/committer `William José Moreno Reyes
  <williamjmorenor@gmail.com>` y `Signed-off-by`. No se hizo push.

La API de bajo nivel `consumed_qty_for_source()` conserva por compatibilidad su
modo histórico cuando no se solicita el nuevo filtro; disponibilidad, creación
de relaciones, submit y estados cacheados usan explícitamente
`exclude_draft_targets=True`. La suite completa y los chequeos finales quedan
pendientes para la etapa final solicitada.

La ejecución completa fue detenida a solicitud del usuario con `SIGINT` cuando
había alcanzado aproximadamente 38%; el log parcial queda en
`/tmp/cacao-review-full.log`. El usuario proporcionará el resultado de pruebas
para continuar el diagnóstico.

### Issues abiertos sin fix local y propuesta

La consulta REST de GitHub confirmó que #485–#506 siguen abiertos y no tienen
comentarios que anuncien commits implementados. La API GraphQL respondió 503,
por lo que la evidencia de detalle se tomó de `ISSUES.md` y del catálogo REST.
Las propuestas priorizadas son:

| Issues | Propuesta de corrección y regresión mínima |
| --- | --- |
| #485, #476 | Centralizar snapshot fiscal/totales con impuestos y retenciones; recalcular `grand_total`, base y outstanding en la misma transacción. Probar AR/AP, moneda extranjera y `qty * rate` manipulado. |
| #486, #493 | Resolver cadena documental completa OV→ND→factura y excluir asientos de cierre de presupuesto/margen. Probar límite de crédito antes/después de facturar y reportes tras cierre. |
| #487, #488 | Revalidar en la transición final del Approval Engine y en `create-target`: docstatus, tercero, compañía, moneda, cantidades y saldos bajo bloqueo. Probar cambios concurrentes entre solicitud y aprobación. |
| #489, #497 | Persistir las cuentas GL origen/destino y filtrar/validar cuenta bancaria, libro y moneda en candidatos y aplicación. Probar transferencias A→B y pagos de otra cuenta. |
| #491, #454, #458 | Hacer matching por línea y por dimensiones (OC, recepción, bodega, artículo/UOM), sin netear desviaciones opuestas. Probar tolerancia por línea y OCs distintas. |
| #492, #474, #475 | Bloquear cancelación de documentos con downstream activo y exigir origen aprobado con relaciones por línea. Probar cadenas de NC/DN y borradores ajenos. |
| #494, #278 | Calcular/validar la nueva revaluación antes de anular la anterior y limitarla al saldo abierto por fecha de corte. Probar fallo de tasa y pagos parciales. |
| #495, #496 | Omitir líneas cero en cierre con resultado neto cero y persistir/validar la tasa manual según política. Probar cierre equilibrado y tasa explícita sin catálogo. |
| #497–#501 | En conciliación/cash forecast validar dirección, cuenta, compañía, tipo canónico, `due_date`, importación y moneda; corregir alerta receive y comparar outstanding sólo en una moneda. Probar pagos parciales, cobros duplicados e importación cross-company. |
| #502–#506 | Hacer atómica la mutación FIFO/bin/GL, revertir ajustes capitalizables idempotentemente, validar cuentas/dimensiones por compañía, resolver cuenta de ajuste por artículo y separar líneas relacionadas/manuales. Probar reducción FIFO, cancelación, cuenta cross-company y recepción mixta. |

También permanecen sin fix local los issues abiertos #453, #455, #457,
#459, #462, #463, #464, #465, #467, #468, #472, #477–#482 y los issues de
auditoría #393–#445; requieren aplicar las mismas propuestas detalladas en
`ISSUES.md` antes de considerarlos resueltos. No se implementaron en esta
etapa porque la petición fue proponerlos; no se hizo push.

## 2026-08-17 — Smoke E2E completo por módulos con curl

### Petición

Ampliar la validación para cubrir la funcionalidad principal de la aplicación
simulando una sesión de usuario real con peticiones GET y POST de `curl`.

### Implementación

- Se creó una segunda base aislada en
  `/tmp/cacao-accounting-complete-20260817.sqlite` y se cargó con
  `db init --seed` dentro de `.venv`.
- Se levantó Waitress en segundo plano en `127.0.0.1:18081`, usando el objeto
  WSGI configurado `cacao_accounting.server:app`.
- Se autenticó `complete_user` obteniendo y enviando el token CSRF como lo
  haría un navegador.

### Cobertura HTTP

El barrido autenticado cubrió 56 endpoints principales: salud y readiness,
dashboard, ventas, compras, inventario, bancos/tesorería, contabilidad,
reportes, configuración y búsqueda. El resultado fue `55` respuestas `200` y
un `400` controlado de `/api/dashboard/data` sin el parámetro obligatorio
`company`. Al repetir la petición con el ID de la compañía (`cacao`), la API
respondió `200` con secciones de ventas, compras, bancos, inventario y
contabilidad.

Además se ejecutaron estos flujos POST y sus GET de confirmación:

- Cliente: creación de `Cliente Completo E2E`, ID fiscal
  `COMPLETE-2026-001`; respuesta `302` a la lista y posterior `200`.
- Solicitud de compra con `ART-001`, cantidad `3` y compañía `cacao`; creación
  y consulta `200`, seguida de submit `302` y estado `docstatus=1`.
- Pedido de venta con `ART-001`, cantidad `2` y tarifa `12`; creación y
  consulta `200`, seguida de submit `302` y estado `docstatus=1`.

Un primer pedido de venta con tarifa cero permaneció correctamente en borrador
y registró el mensaje de validación “Todas las tarifas deben ser mayores a
cero”; no se considera un defecto, sino una regla de negocio ejercitada.

### Persistencia y errores

SQLite confirmó un cliente, una solicitud de compra con una línea y dos
pedidos de venta con dos líneas. El log WSGI no mostró errores 500 ni
excepciones; el único mensaje fue la validación esperada de tarifa cero. El
único defecto de arranque identificado en las etapas E2E sigue documentado en
GitHub issue #451.

## 2026-08-17 — Fixes adicionales de bancos #498 y #501

### Petición

Continuar con los bug fixes de issues abiertos, usando un commit semántico por
fix, firmado como `williamjmorenor@gmail.com`, con referencias compatibles con
GitHub para cerrar los issues al hacer push; no hacer push y dejar los cambios
locales.

### Implementación

- `5d52e51f fix(banks): validate manual cash forecast entry types` (`Closes #498`):
  normaliza `Income`/`Expense` en alta y edición de entradas manuales del Cash
  Forecast y rechaza otros valores. Se agregó una regresión para impedir que
  `Transfer` se persista.
- `c0c74cf7 fix(banks): keep invoice balances in transaction currency`
  (`Closes #501`): `_invoice_outstanding` deja de comparar el saldo transaccional
  con el cache en moneda base, evitando subestimar saldos multimoneda. Se agregó
  una prueba aislada para el caso de tasas distintas.

No se ejecutaron tests ni se hizo push, conforme a la instrucción vigente. Los
tests quedan preparados para que el usuario proporcione o ejecute sus resultados.

## 2026-08-17 — Revisión continua y fixes #499 y #497

### Revisión

Se actualizó `origin/main` y no aparecieron commits nuevos en el remoto. GitHub
mantiene abiertos los issues asociados porque los commits aún no se han
publicado; no se encontraron comentarios nuevos que anuncien fixes paralelos
para #498, #499, #500, #501 o #497.

### Fixes implementados

- `7f26a82f fix(imports): isolate cash forecast entries by company`
  (`Closes #499`): la importación valida la compañía del pronóstico durante el
  lote y vuelve a comprobarla antes de persistir; el contexto de compañía viaja
  en el documento construido.
- `bedf36cd fix(banks): isolate reconciliation by bank account`
  (`Closes #497`): candidatos y matches de pagos quedan restringidos a la cuenta
  bancaria conciliada, incluyendo las cuentas origen/destino de transferencias
  internas. Se actualizan regresiones para cubrir aislamiento y datos válidos.

Ambos commits tienen sign-off de `williamjmorenor@gmail.com`. No se ejecutaron
tests ni se hizo push; quedan como cambios locales para que el usuario entregue
o ejecute los resultados de pruebas.

## 2026-08-17 — Fix de pagos vía create-target #488

La revisión del flujo `POST /api/document-flow/create-target` encontró que la
aplicación de líneas contra facturas solo validaba compañía, moneda y saldo. El
commit `264a2176 fix(document-flow): validate payment target references`
(`Closes #488`) agrega validación de factura aprobada, coincidencia de tercero y
compatibilidad entre tipo de pago y documento (AR/AP y notas). Se agregaron
regresiones para facturas en borrador y facturas de otro cliente.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests ni
se hizo push.

## 2026-08-17 — Resultados de pruebas proporcionados por el usuario

El usuario proporcionó el resultado de la ejecución completa: `7 failed,
1806 passed, 9 skipped, 209 warnings` en aproximadamente 60 minutos.

Clasificación de los fallos:

- `test_05document_flow.py` falló porque aún esperaba que una relación de
  borrador actualizara `received_qty` y el estado a parcial. La regla implementada
  para #483 exige que los borradores no consuman el origen; las expectativas se
  actualizaron en `972b0459 test(document-flow): align draft relation
  expectations` (`Closes #483`).
- `test_11_contabilidad_coverage.py::test_route_journal_reject_flash_error`
  esperaba 200/302 para un identificador inexistente, pero la ruta correctamente
  devuelve 404.
- `test_accounting_exhaustive.py::test_rbac_manager_vs_auxiliar_vs_user`
  devuelve 403 para `conta` porque el fixture de datos no crea `UserBookAccess`
  para los libros de los usuarios demo; no se debilitó el aislamiento de #466.
- Los fallos de `test_bank_account_numbering.py` usan `inspect.unwrap` sobre una
  ruta protegida sin usuario autenticado, por lo que reciben un resultado sin
  `status_code` y no crean el pago.
- `test_payment_entry_improved.py` también accede a `current_user` sin sesión
  autenticada. Estos tres grupos requieren ajustar fixtures/helpers de pruebas,
  no retirar controles de autorización.

En esta iteración también se implementaron y firmaron:

- `1ae1a178 fix(accounting): skip zero net fiscal closing lines` (`Closes #495`).
- `a3069307 fix(accounting): preserve manual journal exchange rates`
  (`Closes #496`).

No se ejecutaron nuevas pruebas después de estos commits y no se hizo push.

## 2026-08-17 — Fix transaccional de revaluación #494

Se detectó que la reejecución de una revaluación anulaba y confirmaba la corrida
anterior antes de calcular y validar la nueva. El commit
`15e14518 fix(accounting): keep prior revaluation on failed rerun` (`Closes
#494`) agrega un modo transaccional a `void()` y hace rollback de la anulación
si falla el recálculo. La regresión elimina la tasa de cierre después de una
primera corrida y verifica que esta permanezca `posted` tras el fallo.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
después del cambio y no se hizo push.

## 2026-08-17 — Fix de presupuesto y cierre fiscal #493

La revisión del issue #493 confirmó que las consultas de presupuesto comprometido
y del reporte Real vs Presupuesto filtraban cancelaciones y reversas, pero no
`GLEntry.is_fiscal_year_closing`. El commit
`9a732aaa fix(budgets): exclude fiscal closing entries from actuals` (`Closes
#493`) añade el filtro en ambos servicios y cubre un asiento normal de 300 junto
a uno de cierre de 999, que debe quedar excluido.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests ni
se hizo push.

## 2026-08-17 — Alineación del escenario de estado documental #483

El nuevo resultado de pruebas mostró que `test_document_status_uses_single_operational_badge`
seguía creando la recepción usada para la transición a facturación como borrador.
Como los borradores ya no consumen cantidades ni alteran el estado operativo, el
escenario se corrigió para representar una recepción aprobada (`docstatus=1`) y
mantener la expectativa de recepción parcial antes del cierre del saldo. La
prueba independiente de relaciones en borrador conserva la validación de #483.

Se dejó el cambio local para revisión; no se ejecutaron tests y no se hizo push.

## 2026-08-17 — Revisión de `feedback.md`

Se analizó el review de los commits `d54c2339..a7586e02`. Los comentarios sobre
ausencia de pruebas son brechas de cobertura, no evidencia de regresión de
producción; el comentario sobre el mensaje de validación de Cash Forecast (#498)
ya está resuelto en el código actual porque los handlers muestran el mensaje de
`ValueError` mediante `str(exc)`. También se descartó cambiar silenciosamente la
seguridad o el comportamiento de conversión sólo para satisfacer sugerencias de
cobertura.

El escenario documental que mezclaba una recepción borrador con una transición
de facturación se corrigió en `38b3becb test(document-flow): distinguish draft
and approved statuses`, firmado por `williamjmorenor@gmail.com`. No se ejecutaron
tests ni se hizo push.

## 2026-08-17 — Revalidación de Approval Engine #487 y transferencias #489

La revisión del issue #487 confirmó que `ApprovalEngine._validate_final_submission`
no repetía la validación de sobre-recepción para recepciones ni el límite de
notas de crédito/débito para la factura origen. El commit
`21e82c98 fix(approval): revalidate purchase submissions` (`Closes #487`) añadió
ambas comprobaciones y regresiones focales.

El issue #489 confirmó que `create-target` construía transferencias internas sin
persistir las cuentas GL de origen y destino. El commit
`5771b959 fix(banks): preserve transfer accounts in document flow` (`Closes
#489`) resuelve ambas cuentas desde sus cuentas bancarias, valida compañía,
cuentas distintas y configuraciones inconsistentes, con regresión focal.

Ambos commits tienen sign-off de `williamjmorenor@gmail.com`. No se ejecutaron
tests ni se hizo push. El commit paralelo `08758313 docs: cleanup` fue detectado
durante el monitoreo y se conservó; sólo eliminó contenido histórico de
`ISSUES.md`.

## 2026-08-17 — Tolerancia de matching por línea #491

El matching 2-way/3-way acumulaba diferencias de precio con signo y permitía
que un sobreprecio y un subprecio de líneas distintas se cancelaran. El commit
`23c68365 fix(purchases): enforce price tolerance per line` (`Closes #491`)
evalúa la tolerancia de cada línea antes de finalizar la conciliación, conserva
el total firmado para trazabilidad y marca el resultado como fallido si alguna
línea excede la tolerancia. Se añadió regresión para diferencias opuestas.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.

## 2026-08-17 — Revisión de comentarios y snapshots multimoneda #481/#482

La revisión de los issues abiertos confirmó que #481 seguía dejando el
snapshot funcional de `PurchaseReceipt` obsoleto al editar y que #482 igualaba
los importes transaccionales y funcionales de `SalesInvoice`. El commit
`95b642e3 fix(currency): refresh transactional document snapshots` (`Closes
#481`, `Closes #482`) agrega `base_total` persistente a las recepciones,
recalcula tasa/moneda funcional al crear y editar, y conserva la moneda y tasa
histórica del documento origen en facturas de venta. Incluye pruebas unitarias
de ambos snapshots.

## 2026-08-17 — Fixes iniciales de issues #480–#393 solicitados

Se consultaron directamente en GitHub los issues #480, #479, #478, #477, #473,
#472, #468, #467, #465, #462, #459, #458, #457, #455, #453, #452, #451,
#445, #444, #443, #442, #441, #394 y #393, y se contrastaron con el checkout
actual antes de modificarlo.

El commit firmado `690bf30a fix(banking): enforce transaction direction and
reconciliation state` (`Closes #480, #453, #459, #465, #468, #472`) hace que
Cash Forecast use vencimiento, excluye conciliaciones canceladas, valida la
dirección de pagos, rechaza transacciones bancarias ambiguas y valida/actualiza
la ubicación de seriales en salidas, transferencias y reversas.

El commit firmado `d1ad7197 fix(accounting): preserve document dimensions and
validity` (`Closes #455, #458, #477, #478`) valida vigencia de recurrentes,
deriva el tipo documental real de referencias de pago, separa matching por
bodega con fallback sólo cuando es inequívoco y conserva proyecto/unidad de
negocio en el control presupuestario.

El cambio pendiente para el siguiente commit corrige el contexto Flask de
`cacaoctl serve` durante la inicialización de base existente (#451). La
revisión actual confirma implementaciones previas para #452, #441, #442 y
#393, pero todavía requieren auditoría focal y/o pruebas independientes antes
de cerrar esos issues. Permanecen pendientes #443, #445, #467, #473, #479,
#394 y el saldo por lote de #457; no se hizo push.

Durante la continuación se añadieron además los commits firmados:
`593b6e68 fix(server): initialize database inside app context` (`Closes
#451`), `080574a5 fix(orders): enforce item commercial eligibility` (`Closes
#473`), `d78ace45 fix(ledger): enforce append-only accounting evidence` (`Closes
#445`) y `aa500476 fix(inventory): validate batch balances by warehouse`
(`Closes #457`). Sus pruebas focales pasaron: 33, 65 y 69 tests según el
bloque, respectivamente. La suite completa se deja ejecutándose en
`/tmp/cacao-issues-full.log`; no se hizo push.

Posteriormente se creó `2f6ac620 fix(accounting): isolate cash flow and
company operations` (`Closes #462, #467, #479`), que clasifica las líneas
bancarias de pagos en Cash Forecast y restringe presupuestos, cierres y
plantillas recurrentes a libros/compañías autorizados. El bloque pasó 23
pruebas focales. `c83d2ac6 ci(security): audit javascript dependencies`
(`Closes #443`) añadió `npm audit --audit-level=high` al workflow; la auditoría
local no pudo consultar el registry por DNS, por lo que la resolución de
vulnerabilidades transitivas requiere verificación en CI con red.

El commit `6a39b6a3 fix(currency): persist functional currency for journals`
(`Closes #394`) infiere la moneda funcional de la compañía cuando un journal
manual no declara moneda, y la persiste/aplica a sus líneas. Las pruebas
multimoneda pasaron; un fallo aislado del cierre fiscal sigue siendo el fixture
existente fuera de contexto Flask. El commit `d191128f fix(types): align
warehouse matching key annotations` corrige las anotaciones de mypy del
matching por bodega.

La ejecución focal de `test_transaccional_full_transition_routes_get_post`
descubrió una regresión en #473: la validación de compras buscaba `Item` por
clave primaria usando el código comercial, por lo que rechazaba artículos
válidos. `b5d51dbc fix(orders): resolve purchase items by code` (`Closes #473`)
usa la consulta correcta por `Item.code` y ajusta el fixture para declarar un
artículo válido no inventariable; la prueba pasa (`1 passed`). La suite
completa anterior se interrumpió para no conservar un resultado contaminado
por ese defecto y debe ejecutarse nuevamente.

## 2026-08-17 — Validación de orígenes upstream O2C/S2P #463/#464/#474/#475

Los comentarios de los issues indicaban que el bypass también existía en los
pasos solicitud/cotización → orden. El commit `a452feef
fix(document-flow): validate upstream source links` (`Closes #463`, `Closes
#464`, `Closes #474`, `Closes #475`) exige origen aprobado, compañía,
contraparte, moneda y relación activa por cada línea al crear/enviar órdenes y
cotizaciones downstream.

Se detectó y revisó el commit paralelo `194c82a4 chore(format): apply black
formater`; sus cambios fueron sólo de formato sobre el fix de relaciones y la
bitácora, sin conflicto funcional. No se ejecutó la suite; se validó
compilación, `black --check` y `git diff --check`. No se hizo push.

## 2026-08-17 — Análisis de la corrida final de pruebas y validaciones de documentos

El usuario reportó nueve fallos en la suite final. Los errores de importación de
helpers de Compras/Bancos eran causados por la sombra de los módulos con los
objetos `Blueprint` exportados por `cacao_accounting.__init__`; se corrigieron
los tests para importar los módulos mediante `import_module`. Los fallos 404,
403, `NoResultFound`, ausencia de `book` y `current_user is None` quedaron
clasificados como problemas de rutas o fixtures/entorno de pruebas y no se
debilitaron las reglas de autorización ni las rutas para hacerlos pasar.

Además, se dejó preparado el fix para los issues O2C/S2P #463, #464, #474 y
#475: los documentos origen deben estar aprobados, pertenecer a la misma
compañía y contraparte/moneda, y conservar una relación activa por cada línea.
La validación se ejecuta tanto al crear como al enviar/aprobar documentos.

No se ejecutó la suite por indicación del usuario; únicamente se verificaron
espacios en blanco y compilación de Python. No se hizo push.

## 2026-08-17 — Corrección de fixtures de posting #502/#503/#506

El resultado de pruebas reportó `IntegrityError` en las tres regresiones nuevas:
las líneas de `StockEntryItem` no tenían `qty`/`uom` y el `ImportLandedCost` no
tenía una `PurchaseInvoice` origen. El commit
`b15d82b6 test(inventory): complete posting regression fixtures` completa esos
datos obligatorios y mantiene los casos enfocados en los fixes funcionales.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push; queda pendiente que el usuario reejecute las pruebas.

## 2026-08-17 — Revisión de commit paralelo de formato

Durante el trabajo apareció el commit paralelo firmado
`19b2d8ae chore(format): apply black formater`. Aunque el mensaje indica
formato, su diff contiene las llamadas de reversión de relaciones de borrador
que estaban siendo integradas en las rutas O2C/S2P; se revisó el diff y se
conservó sin sobrescribirlo. El commit posterior `8c6de536` contiene sólo la
parte adicional del Approval Engine y su regresión.

No se hizo push ni se ejecutaron tests.

## 2026-08-17 — Relaciones de borradores al editar o rechazar #483

La revisión de comentarios de GitHub confirmó que el fix inicial no cubría
ediciones de todos los documentos ni el rechazo desde Approval Engine. Varias
rutas eliminaban líneas y podían dejar relaciones activas; además, rechazar un
borrador mantenía su consumo temporal. El commit
`8c6de536 fix(document-flow): release draft relations on edit rejection`
(`Closes #483`) revierte las relaciones antes de editar documentos O2C/S2P,
actualiza los caches de origen y revierte las relaciones de un documento cuando
su aprobación es rechazada. Se añadió regresión al flujo de rechazo y se
conserva la trazabilidad histórica.

La revisión de comentarios también confirmó que los hallazgos adicionales de
#446 (crear pagos), #456 (duplicar movimientos) y #461 (cantidad base en OC)
ya estaban cubiertos por commits locales anteriores.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push; queda pendiente que el usuario reejecute las pruebas.

## 2026-08-17 — Totales fiscales persistidos y exposición desde notas de entrega #485/#486

Las facturas de ventas y compras persistían `grand_total` y `outstanding_amount`
con el subtotal, aunque el posting contable ya incorporaba impuestos. El commit
`e05b1e49 fix(fiscal): persist invoice totals including taxes` (`Closes #485`)
calcula el total final usando la plantilla fiscal o el snapshot manual del
formulario y lo aplica también a las validaciones de reversas. El mismo commit
(`Closes #486`) hace que la exposición de crédito relacione facturas directas y
facturas originadas desde notas de entrega asociadas a una orden de venta.
Se añadieron regresiones para ambos casos.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.

## 2026-08-17 — Reducción FIFO con ajuste de valor #502

La conciliación de inventario calculaba el costo FIFO de una reducción pero lo
descartaba y registraba sólo el cambio neto hacia el valor objetivo. El commit
`9cf01da5 fix(inventory): preserve FIFO value on reconciliation` (`Closes #502`)
registra una capa de salida FIFO y, cuando corresponde, una capa adicional de
ajuste de valor con `qty=0`; así la cola FIFO, `StockBin` y el valor objetivo
permanecen consistentes. Se añadió regresión de reducción seguida de
revalorización.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.

## 2026-08-17 — Reversa de costos capitalizados #503

La cancelación de facturas de compra y `ImportLandedCost` sólo revertía el GL;
no revertía las capas/valores de inventario creados por
`LandedCostAllocation`. El commit `e398fd1f fix(inventory): reverse capitalized
landed costs` (`Closes #503`) agrega reversas append-only de valoración y ajusta
el `StockBin` asociado, abortando si falta la capa o el saldo necesario. Se
añadió regresión del caso capitalizado.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.

## 2026-08-17 — Offset contable por línea en recepción mixta #506

`_get_offset_account_for_line` consultaba cualquier relación activa del
documento y podía enviar también líneas manuales a la cuenta puente. El commit
`6085b5e0 fix(inventory): resolve receipt offsets per line` (`Closes #506`)
restringe la consulta a `target_item_id` de la línea actual y añade regresión
para una recepción mixta relacionada/manual.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.

## 2026-08-17 — Cuenta de ajuste específica por artículo #505

El posting sólo resolvía cuentas de ingreso/gasto desde `ItemAccount`; por ello
`stock_adjustment_account_id` nunca se usaba y los ajustes caían al default de
compañía. El commit `3b684e52 fix(inventory): honor item adjustment accounts`
(`Closes #505`) añade ambos alias de resolución, mantiene fallback al default y
exige que la cuenta resultante pertenezca a la compañía. Se añadió regresión de
cuenta específica por artículo.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.

## 2026-08-17 — Aislamiento de conciliación de inventario #504

El posting de conciliaciones aceptaba una cuenta de ajuste explícita sin
comprobar su entidad y propagaba dimensiones sin validar su compañía. El commit
`d3eb19b6 fix(inventory): validate reconciliation company dimensions` (`Closes
#504`) valida la cuenta contra la compañía del documento y comprueba centro de
costo, unidad y proyecto antes de generar movimientos. Se añadió regresión
cross-company.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.

## 2026-08-17 — Bloqueo de cancelación con notas activas #492

La cancelación de una factura de compra sólo comprobaba pagos activos y podía
dejar NC/DN aprobadas apuntando a una factura cancelada. El commit
`0f7042c1 fix(purchases): block cancellation with active reversal notes`
(`Closes #492`) añade una consulta explícita de notas downstream activas en la
ruta de cancelación y en la revalidación final del Approval Engine. Se añadió
regresión para una relación activa y su posterior cancelación.

El commit tiene sign-off de `williamjmorenor@gmail.com`. No se ejecutaron tests
ni se hizo push.
