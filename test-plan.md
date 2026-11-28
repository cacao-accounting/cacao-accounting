# Plan de pruebas para ampliar la cobertura

**Repositorio:** cacao-accounting/cacao-accounting. **Rama:** `estabilizacion`.
**Issue del documento:** [#2250](https://github.com/cacao-accounting/cacao-accounting/issues/2250).
**PR asociado:** [#1660](https://github.com/cacao-accounting/cacao-accounting/pull/1660).
**Estado:** plan pendiente de ejecución tras finalizar `plan.md`; publicar este documento no completa sus lotes.

## Objetivo y línea base

Ampliar gradualmente la cobertura con pruebas que protejan comportamientos observables, reglas e invariantes del negocio.
La cobertura ayuda a decidir dónde investigar; no justifica pruebas triviales ni es por sí sola un criterio de cierre.

La referencia es Coveralls build **83054254**, job **191563108**, rama `estabilizacion`, del 15 de noviembre de 2026:
**50.26 %**, 25,312 líneas cubiertas de 50,362 relevantes, 25,050 sin cubrir en 245 archivos. El job individual
reporta 50.19 %. El commit del build solo modificó `plan.md`; el dato es una línea base global, no una regresión de ese
commit.

Estas cifras son la referencia histórica declarada por el plan, no una medición actual verificada. Antes de ejecutar
los lotes, registrar SHA, modo, versión de Python, motor, selección, exclusiones, líneas cubiertas/relevantes y artefacto
de cobertura. Comparar mediciones del mismo alcance; no mezclar la cobertura agregada del build con un job individual.

## Inicio y ejecución gradual

Al finalizar la ejecución de `plan.md`, comenzar este plan sin esperar una nueva instrucción. Antes del primer lote,
comprobar y registrar en `SESSIONS.md` el estado de cierre de aquella ejecución, el commit o estado de trabajo utilizado,
los controles pendientes y los riesgos conocidos. Si existe un issue asociado al lote, usar ese issue como bitácora y
seguir el flujo de revisión y trazabilidad de `AGENTS.md`; no cerrar issues ni hacer push sin autorización expresa.

Actualizar la línea base de cobertura sobre el estado de código disponible y revisar `SESSIONS.md`, las decisiones
vigentes y las pruebas existentes. A continuación, iniciar la etapa 1 con un escenario acotado; continuar por la
secuencia indicada, dividiendo cada etapa en lotes pequeños y revisables. Para cada lote, registrar el contrato y las
pruebas existentes, implementar las pruebas funcionales que falten, ejecutar los controles pertinentes y documentar
resultados, cobertura relevante, omisiones y siguiente lote. Si una expectativa de negocio no está definida o existe
una contradicción sin resolver, documentar el caso y consultar antes de establecer el resultado esperado; continuar con
otros escenarios independientes cuando sea posible.

Un fallo descubierto por las pruebas debe documentarse con su reproducción y riesgo. No modificar el core ni adoptar
decisiones de negocio solo para satisfacer la cobertura; cualquier corrección requiere comprender su alcance y seguir
las instrucciones del proyecto. Mantener la cadencia de controles y las restricciones de commits y push de `plan.md` y
`AGENTS.md`.

La finalización de `plan.md` se verifica contra su cola y sus criterios de salida vigentes, no solo por el transcurso del
tiempo o por llegar al final del archivo. Registrar cualquier trabajo diferido y su decisión aprobada; una revisión o
control obligatorio pendiente no se presenta como completado. Una vez terminada esa ejecución, este plan pasa a ser la
cola activa de trabajo. Si se reanuda una sesión, consultar la bitácora y continuar desde el primer lote pendiente.

## Contrato operativo de cada lote

1. Identificar un recorrido o invariante concreto, sus consumidores y la decisión de negocio vigente. Revisar
   `SESSIONS.md`, `feedback.md` y `review.md` si existen, las pruebas existentes y, si hay issue, su descripción y todos
   sus comentarios, incluidos los del agrupador cuando definan el contrato. Contrastar las cifras
   de cobertura con el código actual; una línea sin cubrir no demuestra por sí sola que falte un escenario funcional.
2. Anotar el caso, datos de entrada, resultado esperado independiente de la implementación, dimensiones afectadas y
   pruebas existentes. Dividir por contrato y consumidor; no agrupar módulos independientes en un cambio gigante.
3. Ampliar o agregar pruebas con datos representativos. Verificar persistencia y consecuencias observables; incluir
   fallo, límite y aislamiento cuando correspondan. Consultar si el comportamiento esperado no está definido.
4. Ejecutar la selección dirigida individualmente y en paralelo, y los controles previos al commit de `AGENTS.md` y
   `plan.md`. Para escenarios dependientes del motor, realizar además la validación Tier 1 indicada abajo. Registrar
   comandos, motor, resultado, skips, SHA o estado de trabajo y limitaciones en la bitácora correspondiente.
5. Revisar el diff y la cobertura de las áreas abordadas; registrar qué escenario quedó protegido y cuál sigue
   pendiente. Si hay issue, aplicar sus revisiones independientes QA1 y QA2, referencias y trazabilidad exigidas por
   `AGENTS.md`. No declarar resuelto un defecto solo porque una prueba nueva lo reproduzca.

Un escenario falla si detecta un defecto: conservar la evidencia y distinguir defecto de regresión en la prueba o
problema del entorno. No desactivar ni debilitar la aserción para obtener verde. Si la corrección requiere modificar el
core o decidir una regla de negocio, detener esa corrección y consultar; los lotes independientes pueden continuar.

Antes de ampliar pruebas, contrastar el consumidor con el resultado de `plan.md`. No restaurar código retirado para
probarlo: esto incluye el comparativo residual de órdenes de compra (#2093), adaptadores sin consumidor y catálogos
residuales. El comparativo de solicitudes solo se prueba si conserva un consumidor productivo. Las referencias de este
documento son puntos de partida que deben revalidarse tras la estabilización, no una orden de conservar esos módulos.

## Cola de lotes y dependencias

Los IDs son estables para el seguimiento. La prioridad ordena lotes cuyos prerrequisitos estén satisfechos; un bloqueo
no impide avanzar otro consumidor independiente. Cada fila se divide en commits si contiene contratos independientes.
En cada lote, identificar primero la brecha concreta: si ya está cubierta, registrar las pruebas que lo demuestran y
continuar, sin duplicarlas para aumentar cobertura.

| ID | Prioridad y consumidor | Dependencia | Trabajo y salida verificable |
| --- | --- | --- | --- |
| T00 | Preparación | Finalización de `plan.md` | Registrar entrega de estabilización, decisiones y diferidos; actualizar cobertura y mapear escenarios a pruebas actuales. Dejar elegido el primer escenario faltante de T01. |
| T01 | P0 · Publicación multilibro | T00 | Documento operativo único publicado en todos los libros activos, balanceado en la moneda de cada libro; libro inactivo sin movimientos. Comprobar conversión histórica y trazabilidad de origen. |
| T02 | P0 · Fallos de publicación | T01 | Tasa ausente para un libro destino, período cerrado o configuración inválida: operación bloqueada sin GL, subledger ni saldo parcial. Verificar desde una sesión nueva tras resolver la transacción. |
| T03 | P0 · Anulación y reversión GL | T01 | Anulación en fecha/período original y reversión contable en otro período, con contrapartidas y vínculos por línea; evidencia cancelada jamás reactivada. Ampliar las regresiones manuales existentes. |
| T04 | P0 · Pagos AR/AP | T01, T02 | Aplicación parcial, total y a varios documentos; saldo por documento y suma del tercero reconciliables con GL. Anular restaura exactamente lo aplicado y conserva evidencia por libro. |
| T05 | P0 · Reintentos y carreras | Contrato T03 o T04 afectado | Reutilizar regresiones de reversión y aplicación AR/AP; cubrir la carrera faltante con conexiones independientes. Resultado conforme al contrato de replay o rechazo, sin efectos económicos duplicados. |
| T06 | P0 · O2C documental | T01, T04 | Origen → factura → cobro: relaciones persistidas, consumo parcial y pendiente correctos; referencias ajenas y usuario sin permiso rechazados sin mutación. Ampliar `test_o2c_credit_sale.py` solo donde falte cobertura. |
| T07 | P0 · O2C físico y correcciones | T06, T13 | Entrega/devolución y nota de crédito según contrato vigente: cantidad, costo, AR y GL reconciliados sin confundir devolución física con ajuste financiero. Conservar origen e historial. |
| T08 | P0 · S2P documental | T01, T04 | Orden → recepción → factura → pago: vínculos y cantidades parciales correctos; tercero de doble rol conserva AP; rechazos por compañía y permisos sin escritura parcial. |
| T09 | P0 · Matching de compras | T08 | Separar 2-way y 3-way, repetición de artículos, UOM y límites de tolerancia. Verificar resultado, estado y motivo según configuración, asignaciones persistidas y reconstrucción desde eventos. |
| T10 | P0 · Correcciones S2P | T09, T13 | Devolución física, nota de crédito y cancelación conservan sus relaciones. La devolución física no reduce por sí sola AP; comprobar efecto de la nota de crédito explícita y evidencia histórica. |
| T11 | P2 · Abastecimiento vigente | T00 y consumidor superviviente | Comparativo de solicitudes/ofertas, selección y órdenes resultantes: línea origen correcta con artículos repetidos, disponibilidad y monedas; autorización y reintento según contrato, sin depender del orden SQL. |
| T12 | P1 · UOM y maestros de inventario | T00 | Conversión exacta y fraccionaria, factor inválido y restricciones tras movimientos. Artículos globales y filas por compañía conservan su alcance aprobado. |
| T13 | P1 · Cantidad y valoración | T01, T12 | Entradas/salidas bajo FIFO y promedio móvil donde estén soportados: cantidades y costos calculados a mano, bins y stock ledger reconciliados con GL por libro y moneda. |
| T14 | P1 · Lotes, series y transferencias | T13 | Disponibilidad/vencimiento a fecha de posteo; transferencia entre bodegas distintas conserva cantidad y valor. Rechazo atómico por lote/serie inválido o dimensión de compañía ajena. |
| T15 | P1 · Ajustes y reconstrucción | T13 | Ajustes positivos/negativos conforme a #1891; rechazo del ajuste mixto inválido. Previsualización sin mutaciones y reconstrucción repetible preservan cifras y evidencia del ledger. |
| T16 | P1 · Conciliación bancaria | T01, T04 | Pago o GL elegible, dirección y cuenta correctos; asignación parcial/total actualiza pendientes. Replay equivalente sin duplicados; petición distinta no reutiliza indebidamente el resultado previo. |
| T17 | P1 · Fallos y monedas bancarias | T16 | Tolerancias de candidatos separadas de reglas de asignación; conversión banco/pago/libro, tasa ausente, sobreasignación y compañía ajena: resultado contractual y atomicidad comprobados. |
| T18 | P1 · Caja chica | T01, T04 | Ampliar regresiones existentes de gasto, vale, conciliación y reposición: saldos GL, transiciones y reserva única; aprobación Cloud y ejecución Desktop según modo. |
| T19 | P1 · Reportes financieros | T01, T03 | Mayor, balance de comprobación, balance general y resultados reconciliados con cifras independientes; apertura, período vacío, cierre, anulación/reversión y aislamiento por libro/compañía. |
| T20 | P1 · Reportes operativos y tesorería | Consumidor T04, T13 o T16 pertinente | AR/AP, antigüedad, kardex, bancos y matriz de conciliación usan cortes y grano correctos. Saldos históricos no dependen del saldo actual cacheado; totales y paginación no duplican movimientos. |
| T21 | P1 · Cierre, revaluación y EFE | T19, T16 para bancos | Ampliar casos de tasa ausente, corrida única, anulación y Estado de Flujos de Efectivo; saldos inicial/final y movimientos cuadran con GL, sin repetir regresiones ya existentes. |
| T22 | P2 · Importación | T00 y contrato del documento importado | Diferenciar API de validación de líneas de importación por lotes; archivo real, precisión, encabezados, permisos, fallo por fila/global, reintento y recuperación con el contrato de atomicidad correspondiente. |
| T23 | P2 · Adjuntos y administración | T00 y rutas supervivientes | Acceso propio/ajeno, contenido y límites de archivo, integridad y limpieza tras fallo; cambios administrativos con permisos y estado válidos. Respetar disponibilidad por modo. |
| T24 | Integración y cierre | Lotes anteriores resueltos o diferidos con aprobación | Reconciliar matriz de escenarios, cobertura comparable, revisiones y ronda de integración; documentar riesgos y diferidos aceptados. Ningún control omitido se registra como aprobado. |

### Primer lote ejecutable y seguimiento

Comenzar por T00. Su entrega es la línea base reproducible y una matriz de escenarios con columnas: ID del lote,
contrato/consumidor, prueba existente, brecha, motor/modo, estado, evidencia y siguiente acción. Registrar la matriz en el
issue del lote o en `SESSIONS.md` si no existe uno. No crear un nuevo sistema de seguimiento ni otra fuente divergente.
T00 termina al identificar la primera brecha concreta de T01; si T01 ya está cubierto, dejar esa evidencia y pasar a T02.

Usar estados `pendiente`, `en curso`, `bloqueado`, `en revisión`, `validado` o `diferido con aprobación` para los lotes;
estos estados locales no sustituyen las etiquetas GitHub de `AGENTS.md`. Cada bloqueo indica causa y condición de salida.
Cada diferido requiere decisión aprobada, motivo e impacto. Al reanudar, tomar el primer lote pendiente con dependencias
satisfechas y revisar antes sus observaciones de QA. La publicación de #2250 entrega el plan; no valida T00–T24.

## Matriz de validación y cadencia

| Alcance | Evidencia mínima |
| --- | --- |
| Cada lote | Pruebas dirigidas en `.venv` o `venv`, individualmente y con `pytest -n auto` cuando la selección lo permita; registrar skips y controles previos al commit exigidos por `AGENTS.md`. |
| Persistencia, SQL, transacciones o concurrencia dependientes del motor | Escenarios aplicables ejecutados en SQLite y PostgreSQL reales, con configuración y motor verificados; los fallos Tier 1 bloquean la aceptación del lote afectado. |
| Desktop y Cloud | Validar Desktop con SQLite y sin Redis cuando el recorrido dependa del modo o de la caché; validar permisos y aislamiento multiempresa en Cloud cuando correspondan. |
| Ronda completa | Seguir la cadencia de `plan.md`: cada 50 commits locales desde la última ronda satisfactoria y antes de un push autorizado, sobre el HEAD exacto. Reproducir los workflows vigentes de Python, lint y bases de datos; registrar controles pendientes sin declarar verde una ronda incompleta. |

La matriz de `.github/workflows/databases.yml` incluye SQLite, MySQL y PostgreSQL con psycopg2 y pg8000. MySQL se
comprueba en la ronda completa como Tier 2; un fallo no se transforma en bloqueo de lanzamiento Tier 1. La suite
`database` debe usar una aplicación y conexiones que realmente apunten al motor configurado: la fixture `app` de
`tests/conftest.py` fuerza SQLite en memoria, incluso si `DATABASE_URL` apunta a PostgreSQL. Comprobar el dialecto y la
infraestructura de las pruebas de motor antes de atribuirles cobertura PostgreSQL. Marcar `database` por sí solo no
cambia la conexión. Preparar bases aisladas siguiendo el workflow, sin ejecutar su reset contra datos de usuario.

Las pruebas de concurrencia deben usar conexiones y transacciones independientes, sincronizar los puntos de carrera y
comprobar el estado final persistido. No extrapolar semántica de bloqueo desde SQLite. Si falta un motor, driver o
herramienta, registrar el control pendiente y preparar el entorno; el lote que necesita esa evidencia no se considera
validado hasta ejecutarla.

## Principios

- Usar las fixtures de `tests/conftest.py` (`app`, `db_session`, `client`, `authenticated_client`) y SQLite real en
  memoria cuando sean adecuadas al escenario. `db_session` crea una sesión separada: no aísla automáticamente servicios
  que escriben mediante `database.session`. Comprobar el escritor, la conexión y la limpieza efectiva por prueba.
- Preparar datos representativos y comprobar saldos, filas persistidas, estados, respuestas y reportes esperados. No
  sustituir resultados funcionales por aserciones de llamadas internas.
- Minimizar mocks. Reservarlos para límites externos inevitables, como transporte de correo; no simular la base de datos
  cuando la regla depende de SQLAlchemy.
- Cubrir fallos y transiciones relevantes: entradas inválidas, límites, acceso entre compañías, duplicados/reintentos,
  rollback, reversión y conservación de evidencia.
- Mantener cada prueba pequeña y explicable. Reutilizar helpers existentes; crear fixtures cuando expresen un concepto
  de negocio y simplifiquen casos reales.
- No cambiar workflows ni agregar dependencias. La regla de 90 % para código nuevo y 85 % para código preexistente
  editado se aplica a esos cambios, no es una cuota para el repositorio completo.

## Prioridades basadas en Coveralls

La tabla combina volumen sin cubrir, riesgo del flujo y exposición contable. Las cifras pertenecen al commit del build y
se deben actualizar antes de iniciar cada etapa. No se debe abordar un módulo entero solo por su porcentaje.

| Prioridad | Archivo/área | Líneas sin cubrir | Motivo |
| --- | --- | ---: | --- |
| P0 | `contabilidad/posting_service.py` | 1,524 | Publicación y fuente de verdad financiera |
| P0 | `compras/routes.py` + `compras/services.py` | 2,372 | Flujo S2P, autorización y persistencia |
| P0 | `compras/purchase_reconciliation_service.py` | 670 | Conciliación orden/recepción/factura |
| P0 | `document_flow/payment.py` | 425 | Aplicación y saldos AP/AR por documento |
| P1 | `reportes/services.py` | 873 | Consultas e informes R2R |
| P1 | `inventario/service.py` | 462 | Cantidad, lote, unidad y valoración |
| P1 | `bancos/reconciliation_service.py` | 369 | Conciliación de banco, pagos y GL |
| P1 | `contabilidad/routes.py` | 1,350 | Entrada a operaciones y permisos |
| P2 | `api/line_import.py` | 463 | Validación y recuperación de importaciones |
| P2 | `attachment_service.py` | 447 | Evidencia, acceso y manejo de archivos |
| P2 | `compras/purchase_request_comparison_service.py` | 245 | Comparación de ofertas y órdenes |

Antes de agregar pruebas, revisar las existentes y ampliar las que ya describan el mismo contrato.

## Etapas

### 1. Publicación contable y pagos documentales (P0)

Archivo nuevo propuesto si existe una brecha no cubierta: `tests/test_posting_service.py`. Revisar las pruebas de pagos y
`test_manual_journal_reversal_gl.py`, `test_manual_journal_reversal_atomicity.py`,
`test_manual_journal_reversal_concurrency.py` y `test_payment_target_allocation_contract.py`.

- Publicar a varios libros activos: comprobar una sola operación origen y las líneas correctas por libro/moneda.
- Tasa de cambio ausente o datos inválidos: publicación bloqueada y ninguna escritura/saldo parcial.
- Pago parcial y total: verificar saldo pendiente por documento y reconciliación de la suma con GL.
- Anulación de un pago aplicado: conservar líneas originales, registrar contraasientos permitidos y restaurar el saldo de
  las facturas asociadas.
- Reintentar una solicitud idempotente: sin duplicar publicaciones ni asignaciones.
- Revertir en otro período: preservar documento original, fecha y evidencia histórica.
- Comprobar que una línea cancelada nunca vuelve a activarse ni se borran o reescriben cifras de evidencia; distinguir
  esas prohibiciones de la actualización permitida de saldos derivados. La anulación ocurre en la fecha y período
  originales y la reversión conserva el efecto histórico del período anterior.

### 1B. Order to Cash y conciliación de AR (P0)

Revisar `tests/test_o2c_credit_sale.py`, las pruebas O2C existentes y los contratos de documentos y pagos antes de
seleccionar cada caso. Avanzar por lotes independientes: origen y facturación; entrega e inventario; cobro y aplicación;
anulación, devolución y reversión, según las capacidades y decisiones vigentes del proyecto.

- Trazar una venta representativa desde su documento origen hasta factura, AR y GL; verificar vínculos, importes y
  saldo por documento, y reconciliar con GL por compañía y libro.
- Para entregas y devoluciones soportadas, verificar cantidades y valoración por artículo y bodega, evidencia y su
  conciliación con GL. Cubrir documentos parciales y rechazo sin escrituras parciales cuando el contrato lo exija.
- Aplicar cobros parciales o a más de un documento y comprobar saldos, moneda y evidencia. Al anular, verificar la
  restitución de los saldos aplicados y la conservación del historial.
- Probar permisos y referencias de otra compañía, reintentos y períodos cuando correspondan. Confirmar la semántica
  aprobada antes de fijar expectativas sobre devoluciones, exceso o idempotencia.

### 2. Conciliación de compras y Source to Pay (P0)

Archivo nuevo propuesto si hace falta: `tests/test_purchase_reconciliation_service.py`. Revisar
`test_s2p_purchase_receipt_source_scope.py`, `test_purchase_sourcing_authorization.py` y
`test_s2p_import_landed_cost_form.py`.

- Orden, recepción y factura coincidentes: cantidades, líneas y estado final persistidos.
- Recepción/facturación parcial, artículos repetidos y unidades compatibles: cantidades agregadas y conversiones
  correctas.
- Diferencia justo dentro y justo fuera de tolerancia: resultado y motivo esperados.
- Exceso de cantidad: comprobar el resultado de matching y estado definidos por la configuración, sin asumir que toda
  discrepancia lanza una excepción. Referencias de otra compañía/orden incompatibles: rechazo sin escrituras parciales.
- Reprocesar evento o cancelar: idempotencia, estado reconstruido y eventos históricos conservados.
- Comparar ofertas con artículo repetido, disponibilidad parcial y monedas aplicables; comprobar recomendación y órdenes
  resultantes sin depender del orden accidental de SQL.
- En rutas, validar autorizado, usuario sin rol y usuario de otra compañía.

### 3. Reportes Record to Report (P1)

Archivo nuevo propuesto si hace falta: `tests/test_r2r_report_services.py`. Revisar `test_r2r_cash_flow_statement.py`,
`test_r2r_income_statement_cost_classification.py`, `test_financial_report_ledger_validation.py` y
`test_report_reconciliation_company_scope.py`.

- Comparar resultados con débitos/créditos del GL para datos contables representativos.
- Cubrir período vacío, apertura, cuenta sin clasificación y límites de fecha.
- Verificar anulaciones y reversiones entre períodos contra las reglas aprobadas, no solo contra el comportamiento actual.
- Aislar resultados por compañía, libro, cuenta y período.
- Validar clasificación de costo de bienes/servicios, ingresos y gastos con utilidad bruta/neta esperadas, sin reescribir
  cuentas ni GL históricos.
- Comprobar errores de filtro/exportación inválidos y orden/etiquetas de resultados válidos.

### 4. Inventario to Fulfillment (P1)

Archivo nuevo propuesto si hace falta: `tests/test_inventory_service_flows.py`. Revisar `test_i2f_uom_editing.py`,
`test_stock_entry_dimensions.py`, `test_inventory_batch_company_scope.py` y
`test_inventory_master_duplicate_codes.py`.

- Conversión entre unidad base y alternativa: factor exacto, fracción, misma unidad y unidad/factor inválido.
- Validar lote/serie en entradas, salidas, transferencias y devoluciones: lote/serie inexistente, usada o en otra
  bodega.
- Movimientos por artículo, lote y bodega: cantidades y valores monetarios esperados.
- Reconstrucción de valoración: capas correctas y sin duplicados al repetir el proceso.
- La identidad física de capas derivadas reconstruibles no se confunde con evidencia append-only: comprobar sus cifras
  y correspondencia sin exigir IDs permanentes. El GL y stock ledger originales conservan sus filas y cifras.
- La anulación de inventario sigue el contrato vigente del mismo período; no introducir una reversión de inventario en
  otro período por analogía con los asientos manuales.
- Restricciones de edición con movimientos existentes y aislamiento de compañía.

### 5. Cash & Treasury (P1)

Archivo nuevo propuesto si hace falta: `tests/test_bank_reconciliation_service.py`. Revisar `test_cash_payment_source_company_scope.py`,
`test_ctm_cash_forecast_import.py` y `test_payment_target_allocation_contract.py`.

- Conciliar movimiento con pago y asiento GL: dirección, importe y pendiente antes/después.
- Importe exacto, dentro/fuera de tolerancia y asignación parcial.
- Monedas de banco/pago/compañía: conversión correcta; sin tasa, rechazo atómico.
- Rechazar otra compañía, cuenta incompatible, partida conciliada o asignación superior al saldo.
- Reintento equivalente: resultado idempotente sin duplicados.

### 6. Importación, adjuntos y administración (P2)

Ampliar `tests/imports/test_reader_resource_limits.py` y `tests/imports/test_import_structure.py`; crear pruebas de
adjuntos solo si queda una regla sin cobertura existente.

- Archivo real con filas válidas e inválidas: conservar válidas, identificar fila/campo inválido y evitar escrituras
  incompletas ante fallo global.
- Archivo vacío, encabezados faltantes/duplicados, límites de tamaño/filas, precisión y tipos inválidos.
- Acceso a adjuntos autorizado y denegado entre compañías.
- Rechazar rutas manipuladas, tipos no permitidos y archivos que exceden límites; comprobar limpieza de temporales tras
  fallos.
- En rutas administrativas, cubrir cambios de estado, validación, permisos y aislamiento; no probar presentación sin
  contrato funcional.

## Referencias por consumidor y cálculos de control

Además de las referencias anteriores, revisar `tests/test_ar_ap_application_concurrency.py` para T04/T05,
`tests/test_database_engine_smoke.py` para verificar motor, `tests/test_s2p_dual_role_supplier_invoice.py` para T08,
`tests/test_petty_cash_replenishment_approval.py` y `tests/test_petty_cash_fund_scope.py` para T18,
`tests/test_trial_balance_opening_balance.py` para T19, y `tests/test_r2r_exchange_revaluation.py` y
`tests/test_exchange_revaluation_missing_rate.py` para T21. Son pruebas existentes, no una afirmación de que cubran todos
los escenarios del lote. Ampliarlas donde compartan contrato y fixture; no convertir un archivo existente en un lote gigante.

Usar cálculos independientes de las funciones productivas. Ejemplos sin impuestos, descuentos ni cargos adicionales:

- Factura 100, cobro aplicado 40: pendiente 60; al anular el cobro, pendiente 100 con evidencia del pago y contraasiento.
- Entrada de 10 unidades a 5 y otras 10 a 7; salida de 12: FIFO consume 64 y conserva 56; promedio móvil consume 72 y
  conserva 48. Validar cada método por separado según la configuración vigente.
- Ingreso 1.000, costo 400 y gasto 100: utilidad bruta 600, margen bruto 60 % y utilidad neta 500. Este escenario ya tiene
  regresiones; usarlo como control de coherencia, sin crear una copia redundante.

Respetar precisión y redondeo de `docs/precision_contract.md` y los contratos fiscales vigentes; usar `Decimal`, tasas
explícitas y fechas fijas. Kardex y bancos respetan los períodos contables completos aprobados en #1955 de `plan.md`.
Los cortes diarios se aplican solo a consumidores cuyo contrato los admita. Para impuestos, retenciones y landed cost,
seguir `docs/tax-cost-engines/` y las decisiones aprobadas, verificando que las pruebas citadas por la documentación
existan en el estado final del repositorio antes de reutilizarlas.

## Paralelismo y aislamiento

El workflow de Python ya ejecuta `python -m pytest -n auto --full` (sin modificarlo como parte de este plan). Las
pruebas nuevas deben poder ejecutarse solas y junto a la suite:

- Elegir una fixture que aísle la sesión utilizada realmente por el consumidor; no depender de otra prueba ni del orden.
- No compartir archivos, puertos, cachés mutables ni datos globales. Usar `tmp_path` y `monkeypatch` para recursos
  temporales y entorno.
- No llamar servicios externos desde pruebas unitarias. Respetar marcadores existentes `cache` y `database` para los
  escenarios que necesitan servicios/motores reales.
- No inferir garantías de concurrencia de PostgreSQL a partir de SQLite. Los casos de locking/aislamiento requieren
  prueba marcada `database` sobre el motor correspondiente.
- Revisar qué sesión utiliza el servicio antes de afirmar atomicidad: un `commit()` sobre otra sesión puede escapar de
  la transacción externa de la fixture.
- Tras cada etapa, ejecutar la selección dirigida de la etapa y su integración paralela; registrar fallos, skips y
  cobertura de los módulos tocados. La ronda completa sigue la cadencia definida en la matriz anterior.

## Criterios de cierre por etapa

1. Cada prueba protege una historia, regla o invariante nombrable.
2. Las aserciones verifican cifras/resultados independientes de la implementación y, cuando aplica, datos persistidos.
3. Se cubren recorrido válido, fallo relevante, límite y aislamiento.
4. Las pruebas pasan individualmente y con `pytest -n auto`, sin dependencias de orden ni colisiones entre workers.
5. No se introducen decisiones de negocio ni cambios al core para satisfacer la métrica.
6. Se revisa el reporte actualizado y se documentan escenarios cubiertos y riesgos pendientes; el porcentaje global no
   es la única medida de calidad.
7. Las comprobaciones SQLite y PostgreSQL aplicables están ejecutadas y registradas; no se confunde una prueba que usa
   la fixture SQLite con una ejecución PostgreSQL. Los controles omitidos mantienen pendiente el lote afectado.
8. La bitácora identifica el estado de cada lote, evidencia, defectos, decisiones pendientes y el siguiente paso. Un
   issue asociado sigue el ciclo de revisión de `AGENTS.md` y permanece abierto salvo autorización expresa de cierre.

## Secuencia sugerida

1. Publicación contable y pagos documentales.
2. Recorridos O2C y conciliación de AR.
3. Conciliación de compras y comparación de cotizaciones.
4. Reportes R2R.
5. Servicios de inventario.
6. Conciliación bancaria.
7. Importación, adjuntos y rutas administrativas.

La secuencia prioriza invariantes que conectan ledgers y áreas con mucho código sin cubrir. Mantener cada etapa pequeña,
revisable y compatible con ejecución paralela.

La cola T00–T24 resuelve las dependencias de esta secuencia: por ejemplo, completar la evidencia de valoración requerida
por T07 antes de dar por validada la integración física O2C. Se puede adelantar ese lote de inventario sin esperar el
cierre de todos los escenarios documentales.

## Entrega y cierre del plan

El implementador ejecuta los controles; QA1 y QA2 realizan revisiones estáticas independientes, sin modificar código ni
repetir pruebas o linters. Para cada issue, documentar evidencia y decisión; cualquier rechazo exige corregir y reiniciar
QA1 → QA2. `fix-proposed` y `fix-confirmed` siguen las reglas de `AGENTS.md`; solo QA3 expresamente autorizado o el
administrador pueden establecer `fixed`. Los commits usan `Refs: #n`, sign-off e identidad Git configurada, sin cierres
automáticos ni coautorías. El inicio automático de este plan no autoriza futuros pushes.

T24 cierra la ejecución cuando cada lote tenga evidencia de validación o un diferido expresamente aceptado, las
observaciones aplicables estén resueltas y se haya registrado la ronda de integración y sus resultados. Informar el
alcance realmente cubierto, riesgos pendientes y comparación reproducible con T00; no imponer un porcentaje global
arbitrario ni declarar completa una funcionalidad por haber aumentado la métrica.

Los cambios exclusivos de Markdown requieren revisión del contenido, enlaces locales y diff; no ejecutar pruebas ni
linters de Python por editar este documento. La cadencia de pruebas anterior rige la implementación futura de los lotes.
