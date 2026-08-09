# SESSIONS — Continuidad de Desarrollo

> Este archivo documenta decisiones de diseño, arquitectura y hitos clave del proyecto.
> Para detalles de implementación por sesión, consultar el historial de git.

## 2026-08-09 — Auditoría completa de flujos de negocio y apertura de issues en GitHub

### Petición

Realizar una auditoría completa de los flujos de negocio **R2R, S2P, O2C, Bancos
e Inventario** y documentar los hallazgos abriendo issues en GitHub. La auditoría
es de solo lectura (no se modificó código).

### Metodología

- Auditoría de código de los módulos `contabilidad/`, `compras/`, `ventas/`,
  `bancos/`, `inventario/`, `document_flow/`, `accounting_engine/` y
  `imports/adapters/` con subagentes de exploración en paralelo, verificando
  cada hallazgo contra el código fuente con Read/Grep.
- Los subagentes R2R devolvieron resúmenes de estado en vez de hallazgos; el
  bloque R2R se completó con revisión directa de `fiscal_year_closing.py`,
  `journal_service.py`, `project_capitalization_service.py` y
  `recurring_journal_service.py`.
- Se abrieron **51 issues** en GitHub (#287–#337) con etiquetas
  `bug`, `python`, `severity-*` y `auth` cuando aplica.

### Hallazgos por flujo

- **S2P (7 issues, #287–#293):** sobre-matching en conciliación
  (`_first_available_line` devuelve líneas agotadas), IDOR en listados/detalle
  de compras, factura que referencia OC/recepción de otro proveedor, edición de
  factura vinculada rota con flags estrictos, puente sin compensar en 2-way,
  `price_ok` con unidades incompatibles, duplicidad de `supplier_invoice_no`
  sin constraint DB.
- **O2C (10 issues, #294–#303):** notas de crédito que nunca reducen el saldo
  de la factura (`_compute_allocated_notes_amount` código muerto),
  `require_sales_order` configuración muerta, doble liberación de reserva en
  entregas parciales (sobre-venta), validación de precio omitida desde ND/manual,
  límite de crédito sin OVs aprobadas, montos negativos/`qty×rate` inconsistentes,
  NC/ND sin tope acumulativo, conciliación de pagos sin ACL por compañía,
  `_payment_order_allocated` sin filtro de compañía y neteo GL de anticipos
  condicionado a config.
- **Bancos (15 issues, #304–#318):** transacciones de solo retiro importadas
  imposibles de conciliar (CRITICAL), reversas GL sin dimensión bancaria,
  candidatos sin dirección depósito/retiro, filtro por monto total excluye
  matches parciales, conciliación de cualquier GL de la misma compañía, IDOR en
  conciliación y pronóstico de caja, borradores abandonados consumen capacidad
  de anticipos, sin limpieza de `ReconciliationItem` al cancelar pago, locks
  FOR UPDATE en GET, matriz de forecast mezcla compañías, importación sin
  dedupe, ruta legacy sin dimensión bancaria, `ExchangeRevaluation` sin
  constraint único y ajuste de diferencia bancaria inalcanzable.
- **Inventario (15 issues, #319–#333):** salida negativa rompe la valoración
  (CRITICAL), cancelación de recepción consume bin negativo, reserva en UOM de
  línea vs bin en UOM base, `stock_adjustment` imposible de postear,
  conciliación con déficit ignora el valor objetivo, capas de landed cost
  excluidas de FIFO/MA, retroactivos corrompen kardex, transferencias de misma
  cuenta sin validación de período, clamp de `reserved_qty` borra reservas,
  transferencias sin `allow_negative_stock`, conciliación mezcla UOM, edición de
  conciliación destruye campos, ND de bodega distinta deja reserva atascada,
  race de INSERT de reserva y MA retrospectivo + listados sin scope.
- **R2R (4 issues, #334–#337):** race condition de doble cierre fiscal, flags
  `is_closing`/`is_fiscal_year_closing` forjables desde el payload (elusión de
  período cerrado y cierre fiscal falso), ventana de doble capitalización de
  proyectos y `apply_recurring_template` que deja el comprobante en borrador y
  lo marca `applied` sin postear.

### Estado

- Total de issues abiertos en el repositorio: 70 (51 nuevos + preexistentes).
- La suite autoritativa previa sigue siendo **1591 passed, 10 skipped**; esta
  sesión no modificó código.
- Continuidad: corregir por severidad (2 CRITICAL: #304 y #319; luego los HIGH)
  con commits semánticos y regresión focal por issue, sin cerrar el issue hasta
  tener evidencia.

## 2026-08-09 — Dimensión bancaria en postings y conciliación de caja

### Petición

Monitorear issues nuevos de GitHub y continuar la auditoría end-to-end de caja,
asegurando que los importes publicados reconcilien con los reportes bancarios.

### Implementación y evidencia

- Se confirmó que varios postings de pagos y notas bancarias usaban la cuenta
  GL correcta, pero dejaban `GLEntry.bank_account_id` vacío. El resumen
  bancario filtra por esa dimensión y podía mostrar saldo cero pese a existir
  movimiento en el GL.
- El commit `fix(bank): preserve bank dimension in payment postings` añade la
  dimensión a los caminos clásicos y al conversor de proformas del motor de
  cálculo, incluyendo transferencias y notas bancarias.
- Se agregó una prueba end-to-end que publica un pago de 100, verifica la línea
  GL asociada a la cuenta bancaria y reconcilia el saldo reportado de -100.
- Validación: Black, Ruff, Flake8; 2 pruebas focales de conciliación bancaria y
  10 pruebas de posting de pagos/notas pasaron.
- El issue #282 fue comentado y permanece abierto para completar huérfanos,
  fees, intereses, transferencias, reversals e idempotencia.

### Continuidad

La matriz Subledger ↔ GL por compañía, libro, moneda y período (#276) sigue
siendo el siguiente control transversal.

## 2026-08-09 — Valoración de inventario al corte

### Petición

Continuar monitoreando issues y verificar que los reportes de inventario no
dupliquen cifras históricas ni incluyan movimientos futuros.

### Implementación y evidencia

- Se confirmó que `get_inventory_valuation` sumaba snapshots de todas las
  capas, aunque cada capa ya contenía el saldo acumulado posterior al
  movimiento.
- El reporte ahora selecciona la última capa por artículo/almacén hasta
  `date_to`, evitando doble conteo y contaminación temporal.
- La regresión independiente verifica capas 10/100, salida 5/50 y una capa
  futura 99/990; el resultado al 31 de mayo es exactamente 5 unidades y 50.
- Black, Ruff y Flake8 pasaron; el bloque focal de inventario y bancos terminó
  con **35 passed**.
- El issue #279 fue comentado y permanece abierto para FIFO/promedio, backdated
  transactions, reversals y conciliación Inventory ↔ GL.

### Continuidad

La corrección no sustituye la reconciliación por libro, período y cuenta
control; esa cobertura sigue pendiente.

## 2026-08-09 — Aislamiento de libros inactivos en reportes R2R

### Petición

Monitorear riesgos nuevos de GitHub y verificar que los reportes financieros no
consulten libros fuera de operación.

### Implementación y evidencia

- `reportes.services._resolve_ledger` podía devolver un `Book` explícitamente
  inactivo; esto debilitaba el aislamiento multi-ledger y permitía emitir
  reportes sobre un libro no operativo.
- El commit `fix(r2r): exclude inactive ledgers from reports` restringe la
  resolución a libros activos o a registros legacy sin estado.
- Se agregó una regresión que solicita una balanza para un libro inactivo y
  verifica que no se resuelva ni devuelva movimientos.
- Black, Ruff y Flake8 pasaron; la prueba focal R2R pasó.
- El riesgo fue documentado en el issue #276, que permanece abierto para la
  matriz completa por compañía, libro, moneda y período.

### Continuidad

La resolución segura del libro no reemplaza la reconciliación matemática de
AR, AP, inventario, banco y tax contra sus cuentas control.

## 2026-08-09 — Corte temporal de reportes de vencimiento AR/AP

### Petición

Continuar la corrección de riesgos de la auditoría, registrar los cambios con
commits semánticos y documentarlos en los issues sin cerrarlos.

### Implementación y evidencia

- El reporte de vencimientos filtraba facturas posteadas después de su fecha
  de corte, lo que podía contaminar saldos históricos de AR/AP.
- El commit `67edcc9` (`fix(ar): exclude future invoices from maturity reports`)
  aplica `posting_date <= as_of_date` para facturas de clientes y proveedores.
- Se agregó una regresión que crea una factura anterior y otra posterior al
  corte y verifica que solo la anterior forme parte del reporte.
- Black, Ruff y Flake8 pasaron; la prueba focal de AR/maturity pasó.
- El cambio fue publicado en la rama `agent/audit-risk-fixes` y comentado en
  el issue #280, que permanece abierto.

### Continuidad

La matriz O2C completa, incluyendo créditos, reversals y conciliación AR ↔ GL,
sigue pendiente en el issue #280.

## 2026-08-09 — Control de migraciones y validación multi-motor

### Petición

Continuar la auditoría y probar el flujo de migraciones en MySQL, PostgreSQL y
MariaDB, manteniendo el uso de `.venv` y evidencia reproducible en logs.

### Implementación y evidencia

- Se confirmó que `db migrate` podía devolver código 0 sin aplicar revisiones:
  el repositorio tenía `script.py.mako`, pero no una revisión en la ruta que
  Flask-Alembic inspecciona. Una SQLite limpia terminó con `alembic_version`
  vacío.
- Se añadió el baseline versionado
  `cacao_accounting/migrations/20260809_0001_baseline.py`. No modifica datos:
  registra el esquema que `db init` crea con SQLAlchemy para habilitar futuras
  migraciones ordenadas.
- `db migrate` ahora rechaza explícitamente una base sin tabla `user`, en vez
  de informar una migración exitosa sin esquema.
- Se añadieron `tests/test_database_migrations.py` para probar bootstrap,
  revisión no vacía y rechazo de base no inicializada.
- Evidencia multi-motor: MySQL 8 PASS (`test_results_migration_mysql_20260809.log`),
  PostgreSQL 16 PASS (`test_results_migration_postgresql_20260809.log`) y
  MariaDB 11.4 PASS mediante `mysql+pymysql`
  (`test_results_migration_mariadb_20260809.log`); cada uno registró
  `20260809_0001`.
- La URI `mariadb+pymysql` sigue siendo rechazada por la validación actual;
  no se presenta como soporte nativo certificado. El controlador `mariadb`
  requiere MariaDB Connector/C y no está instalado en `.venv`.
- La prueba focal de migraciones terminó **2 passed**. La suite autoritativa
  previa continúa en **1591 passed, 10 skipped, 174 warnings**.

### Continuidad

La siguiente corrección P0 sigue siendo una migración de constraints para
`Entity.code` y `Book.code` con preflight de datos históricos, además de las
reconciliaciones AR/AP/inventario/bancos/Tax por compañía, libro, moneda y
período. El baseline no debe confundirse con esa migración de constraints.

## 2026-08-09 — Auditoría profunda multi-motor y reconciliación de cifras

### Petición

Realizar una auditoría end-to-end de R2R, O2C, S2P/P2P, inventario, caja y
bancos, incluyendo doble partida, subledgers, FX realizado/no realizado,
multi-ledger, cierres, reversiones, trazabilidad, aislamiento y pruebas con
cálculos independientes. La ejecución de calidad debe usar `.venv`, Docker
puede utilizarse para motores SQL, y los commits deben ser semánticos con la
identidad `williamjmorenor@gmail.com`.

### Descubrimiento y hallazgos confirmados

- El esquema fallaba al crear `FiscalYear.entity -> Entity.code` en MariaDB
  11.4 porque `Entity.code` era nullable aunque fuera destino de una FK
  única. Después de corregirlo, MariaDB reveló el mismo problema en
  `LedgerMappingRule.source_book/target_book -> Book.code`; `Book.code` también
  quedó obligatorio. El esquema completo pasó 214 pruebas en MariaDB.
- Los datasets semánticos de ventas/compras y AR/AP expresaban devoluciones
  posteadas como importes positivos y no exponían el valor base de línea. Se
  normalizaron los signos y se agregó `base_amount` con fallback legacy.
- El pronóstico de caja podía omitir documentos cuyo saldo solo existía en
  `base_outstanding_amount`, no convertir correctamente el fallback legacy y
  tratar notas de crédito abiertas como entradas positivas. Se corrigió la
  selección, conversión histórica y signo.
- La revaluación cambiaria de cuentas bancarias sumaba el saldo original de
  todos los libros al construir una sola exposición, duplicando el saldo al
  procesar varios books. Ahora usa el libro resumen como fuente de exposición.
- Las notas de crédito abiertas se revaluaban con la naturaleza de una factura
  normal. AR credit note ahora usa naturaleza credit y AP credit note naturaleza
  debit.

### Pruebas y evidencia

- Regresión focal semántica, multi-ledger, reportes operativos y FX: **12
  passed**; nueva prueba de cifras semánticas/caja: incluida en ese bloque.
- Esquema MariaDB 11.4 en Docker mediante `mysql+pymysql`: **214 passed**.
- Black, Ruff, Flake8 y Mypy focales: sin errores; Mypy solo emitió notas
  informativas sobre cuerpos de funciones sin anotación.
- La suite completa exigida se dejó ejecutando en
  `test_results_audit_full_20260809.log`. La corrida final posterior a todos
  los cambios terminó en `test_results_audit_final_20260809.log` con **1591
  passed, 10 skipped y 242 warnings** en 26:26.

### Entregable y estado

- Se generó [`CACAO_ACCOUNTING_DEEP_AUDIT.md`](CACAO_ACCOUNTING_DEEP_AUDIT.md)
  con arquitectura, modelo contable, hallazgos en el formato solicitado,
  evidencia de pruebas, matriz de reconciliación, controles faltantes y
  evaluación final.
- La evaluación permanece **PARTIAL**: la suite está verde, pero faltan
  migraciones versionadas, una matriz consolidada AR/AP/inventario/bancos/Tax
  contra GL por dimensiones y evidencia completa de concurrencia, PostgreSQL,
  cierres FX y todas las reversiones.
- Se ejecutó una corrida focal consolidada de los flujos R2R/O2C/S2P,
  inventario, caja, FX y cierre: **161 passed, 110 warnings** en 216.61 s,
  registrada en `test_results_flow_focal_20260809.log`.
- Se sustituyeron siete usos de `Query.get()` con bloqueo por
  `Session.get(..., with_for_update=True)` en conciliación bancaria, pagos,
  referencias e importación. La regresión afectada terminó **146 passed**;
  los warnings focales bajaron a **56**, principalmente por fixtures JWT y
  avisos externos/legacy.
- La suite completa posterior a este cambio terminó en
  `test_results_audit_final2_20260809.log` con **1591 passed, 10 skipped y
  182 warnings** en 24:20. La regresión final de pagos y conciliaciones
  después del octavo reemplazo ORM terminó **131 passed y 41 warnings** en
  `test_results_payment_last_orm_20260809.log`.
- La ejecución autoritativa sobre el árbol final, registrada en
  `test_results_audit_authoritative_20260809.log`, terminó con **1591 passed,
  10 skipped y 174 warnings** en 26:33.
- La cobertura verificada incluye subledger/aging AR-AP, kardex histórico,
  banco contra GL, anulaciones, posting de inventario, matching 3-way,
  pagos/aplicaciones, cierre fiscal, doble posting y dos libros con monedas
  distintas. El informe ahora incluye una matriz explícita de estas cadenas y
  separa lo probado de lo que sigue pendiente.
- Cambios realizados en commits semánticos `5b049bf` y `8cd297f`; la identidad
  Git es `William Jose Moreno Reyes <williamjmorenor@gmail.com>`.

### Continuidad

La auditoría debe continuar con una matriz explícita de reconciliación
AR/AP/inventario/bancos contra GL por compañía, libro, moneda y período, más
la revisión de period close, impuestos, rounding, concurrencia, reversals y
los escenarios end-to-end restantes. No declarar PASS sin evidencia de cada
matriz.

## 2026-08-09 — Pruebas full de cobros y compensación 3-way multimoneda

### Petición

Ampliar el test drive de un sistema contable con escenarios end-to-end para
R2R, O2C, S2R, inventario y bancos. Se solicitó cubrir pagos parciales,
pagos de más, anticipos, devoluciones, entradas, multimoneda, multilibro y la
compensación de facturas contra reportes de recepción, usando pruebas marcadas
para ejecutarse con `pytest --full`.

### Implementación

- Se agregó la opción `--full` y el marcador `full` en pytest.
- Se agregó un ciclo integrado de cobro: factura de 1,000, cobro parcial de
  600, rechazo de aplicación de 500 sobre el saldo 400 y anticipo de 300
  aplicado después de su aprobación; el saldo manual esperado es 100.
- Se agregó una conciliación 3-way en USD con recepción de 15 unidades a 12,
  facturas de 9 y 4 unidades, y reporte pendiente de 2 unidades / USD 24.
- Los valores base del segundo escenario se fijan manualmente a NIO 6,480 y
  se conserva la trazabilidad de la recepción como fuente de compensación.
- Se configuró la identidad Git local para commits semánticos de
  `williamjmorenor@gmail.com`.

### Verificación parcial

- Prueba de cobro parcial/anticipo: **1 passed**.
- Prueba 3-way multimoneda y reporte de recepción: **1 passed**.
- Regresión focal previa de ciclos: **178 passed**.
- Black, Ruff y Flake8 sobre los archivos modificados: sin errores.
- Mypy del archivo legado de pagos conserva tres errores preexistentes no
  introducidos por esta sesión; la suite `--full` quedó ejecutándose en
  segundo plano para su resultado consolidado.

## 2026-08-09 — Matriz de valoración y reconstrucción de inventario

### Ampliación solicitada

Se pidió elevar la cobertura a aproximadamente 50 pruebas por ciclo de
negocio, con especial atención a que el sistema es contable y que inventario
debe probarse con movimientos y valores calculados, no con asserts triviales.

### Implementación y evidencia

- Se agregaron **26 escenarios `full`** de reconstrucción de inventario.
- Cada escenario persiste movimientos de recepción, salida, devolución,
  conteo o ajuste con cantidades y valores independientes, reconstruye
  `StockBin` y `StockValuationLayer`, y verifica cantidad, valor, tasa final,
  capas generadas y reserva preservada.
- La expectativa contable se calcula fuera del servicio como suma de
  `qty_change` y `stock_value_difference`, con tasa `valor / cantidad`.
- La matriz pasó **26 passed**. El primer ensayo detectó dos expectativas
  manuales mal formuladas (redondeo y signo de una salida); se corrigieron y
  se repitió el bloque completo.
- Con las suites existentes, el inventario queda en aproximadamente 50 casos
  identificables por nombre de archivo; R2R, O2C, S2R y bancos ya superan esa
  magnitud según el inventario de pruebas de esta sesión.

## 2026-08-09 — Matriz O2C y auditoría de checks de GitHub Actions

### Implementación

- Se agregaron **15 escenarios `full` O2C** de orden aprobada a factura
  aprobada, con cantidades parciales y completas, tarifas decimales,
  cantidades fraccionarias y saldos pendientes calculados manualmente.
- Las pruebas verifican la relación documental, el consumo por cantidad y el
  reporte pendiente (`orden - facturado` y `pendiente × tarifa`). El bloque
  quedó en **15 passed**.
- La cobertura por selección de workflows queda en aproximadamente R2R 270,
  O2C 50, S2R 84, inventario 102 (incluye casos compartidos de reportes) y
  bancos 153 pruebas recolectadas.

### Auditoría local de workflows

- `flake8 cacao_accounting/`: exit 0.
- `ruff check cacao_accounting/`: exit 0.
- `pydocstyle cacao_accounting/`: exit 0.
- `mypy cacao_accounting/`: sin errores en 197 archivos.
- `npm ci` + `npm test`: **33 passing**.
- `python -m build` + `twine check`: ambos artefactos PASSED.
- Bandit no es ejecutado actualmente por el workflow aunque se instala; una
  ejecución informativa detecta hallazgos heredados (139 bajos, 1 medio), por
  lo que no se presenta como check verde.
- La suite pytest focal `--full` continúa en segundo plano; su resumen final
  aún es requisito para cerrar la auditoría.

### Ajuste del workflow

- Los jobs `build`, `desktop` y `coverage` de `python-package.yml` ahora
  ejecutan pytest con `--full`, haciendo explícita la matriz de escenarios.
- `coverage` dejó de usar `continue-on-error`, de modo que una regresión de
  pruebas o cobertura no pueda aparecer como check exitoso.
- Ambos workflows locales cargan correctamente como YAML.

### Resultado final de regresión actual

- Después de los últimos cambios se ejecutó la batería afectada completa con
  `pytest --full --slow=True` y salida persistida en
  `test_results_current_full.log`: **286 passed, 129 warnings**, 7m22s.
- La batería amplia anterior del baseline terminó en **562 passed, 129
  warnings**; la regresión actual es la evidencia válida para los archivos
  modificados.
- El job de esquema SQLite del workflow se reprodujo en `.venv` con salida en
  `test_results_schema.log`: **213 passed** en 2m34s. MySQL y PostgreSQL no se
  ejecutaron localmente porque requieren servicios/servidores externos; sus
  comandos permanecen en el workflow para CI.

## 2026-08-07 — Blindaje de devoluciones en analítica y dashboard R2R

### Petición

Continuar la revisión profunda del proceso record-to-reports y blindarlo con
pruebas unitarias rigurosas para asegurar reportes financieros robustos y
confiables. El trabajo se solicitó únicamente para correcciones locales, sin
push.

### Diagnóstico e implementación

- Las consultas de `cacao_accounting/reportes/analytics.py` excluían anulaciones
  y reversas, pero sumaban las devoluciones como ventas y compras positivas.
  Esto contaminaba `metric_value`, concentración por cliente/artículo y los
  KPIs de cuentas por cobrar/pagar.
- El dashboard repetía el problema en ventas, compras, tendencias, clientes y
  tablas de facturas. Ahora las devoluciones se expresan con signo negativo.
- El saldo pendiente del dashboard calcula aplicaciones posteadas cuando el
  documento tiene total transaccional y conserva un fallback explícito para
  filas legacy que solo almacenan el importe base.
- Se agregó `test_r2r_analytics_and_dashboard_net_credit_notes`, que verifica
  ventas, compras, concentración, AR y payload ejecutivo con una factura y una
  devolución posteadas.

### Verificación

- Pruebas focales R2R/dashboard/reportes operativos: **17 passed**.
- Black, Ruff, Flake8 y Mypy focales: sin errores; Black se aplicó al archivo
  editado.
- Suite completa exigida en `test_results.log`: **1539 passed, 8 skipped, 7
  failed**. Los siete fallos están fuera de este cambio: cuatro casos requieren
  tipo de cambio NIO→USD ausente, uno requiere cuenta de revalorización y dos
  corresponden a reservas/flujo de inventario. Se conserva el resultado para
  su tratamiento separado.

### Cierre de verificación

- Las fixtures de los flujos multilibro ahora declaran tasas históricas NIO→USD
  y NIO→EUR para las fechas de posting, y la prueba de revalorización completa
  las cuentas no realizadas aun cuando ya exista una configuración parcial.
- Regresión de los módulos afectados: **7 passed**; regresión de los archivos
  completos: **1546 passed, 8 skipped**.
- Suite completa exigida en `test_results.log`: **1546 passed, 8 skipped, 239
  warnings** en 16m29s. No quedaron fallos.

---

## 2026-08-07 — Auditoría R2R: reportería robusta y KPIs sin mezcla de monedas

### Petición

Revisar el flujo records-to-reports para garantizar reportes financieros
confiables y una reportería robusta, corrigiendo los errores encontrados.

### Diagnóstico e implementación

- **Template financiero con JavaScript roto:** `financial_report.html` tenía un
  `});` sobrante al final del bloque `<script>`, lo que invalidaba todo el
  script: el toggle de filtros avanzados, el colapso/expansión del árbol de
  cuentas y la navegación jerárquica no funcionaban. Se eliminó la llave extra
  y se verificó la sintaxis.
- **Filtro «Cancelado» que devolvía siempre cero filas:** al elegir
  `status=cancelled`, `_apply_cancellation_scope` seguía aplicando
  `is_cancelled=False` y `_apply_status_filter` agregaba `is_cancelled=True`,
  produciendo una consulta contradictoria. Ahora `include_cancellations` se
  activa cuando el usuario pide explícitamente el estado cancelado, de modo que
  el reporte muestra solo los asientos originales anulados.
- **Métrica «income» inconsistente entre herramientas:** `metric_value("income")`
  devolvía el resultado neto mientras que `get_kpi_snapshot` expone el ingreso
  bruto. Ahora ambas coinciden en el ingreso bruto, dejando `net_income` y
  `gross_margin` como métricas separadas.
- **KPIs del dashboard mezclando monedas:** `_invoice_total`, la concentración
  por cliente/proveedor/artículo y el AR/AP del snapshot sumaban montos en
  moneda de transacción. Se priorizan `base_grand_total`, `base_total` y
  `base_amount` (con compatibilidad para registros antiguos), el AR/AP se
  convierte a moneda base con el factor histórico del documento y el snapshot
  ahora declara la moneda base de la entidad. Con esto `working_capital` deja
  de combinar divisas incompatibles.

---

## 2026-08-07 — Revisión de Lógica de Negocios del ERP y Solidez Financiera

### Petición

Se solicitó una revisión integral de la lógica de negocios del sistema Cacao Accounting para garantizar la precisión, consistencia y fiabilidad operacional en todos sus módulos.

### Diagnóstico e implementación

- **Ciclo de Ventas (O2C):** Validación de separación entre evento logístico (Entrega) y financiero (Factura), controles de sobre-entrega/sobre-facturación, reserva de inventario en Orden de Venta y límite de crédito por cliente.
- **Ciclo de Compras (S2P):** Verificación de matching 2-Way/3-Way con tolerancias de cantidad/monto, manejo de cuenta puente (Goods Received Not Invoiced) y costeo de importación (Landed Cost Engine) por valor, peso o volumen.
- **Gestión de Inventario (Stock):** Confirmación de inmutabilidad del Kardex (`StockLedgerEntry`), valoración por FIFO/Promedio Móvil, snapshot atómico (`StockBin`) e inserción segregada de ítems de servicio.
- **Tesorería y Bancos (Cash/Bank):** Verificación de liquidación multimoneda de pagos con reconocimiento de ganancia/pérdida cambiaria realizada, conciliación bancaria automatizada y proyección de flujo de caja.
- **Núcleo Contable (R2R):** Partida doble estricta multilibro y multimoneda (`posting.py`), revalorización cambiaria al cierre de periodo NIIF, capitalización atómica de proyectos y cierre contable de ejercicio.

---

## 2026-08-07 — Capitalización multilínea y neteo de anticipos por libro

### Petición

Como cierre del ciclo de correcciones R2R se atendieron los dos hallazgos
pendientes, evitando abrir nuevos frentes de análisis.

### Diagnóstico e implementación

- La capitalización recorría entradas individuales y marcaba el comprobante
  fuente después de la primera; las demás líneas del mismo comprobante quedaban
  sin capitalizar. Ahora agrupa todas las líneas elegibles por voucher y genera
  un único comprobante atómico, con sus dimensiones, moneda y usuario.
- El contador de resultados representa comprobantes realmente generados y una
  segunda ejecución no duplica la capitalización.
- El neteo automático de anticipos se limitaba al libro primario y usaba el mismo
  nominal en ambos lados. Ahora obtiene el valor histórico de factura y anticipo
  en cada libro, prorratea la aplicación, publica líneas funcionales dirigidas a
  todos los libros activos y reconoce la ganancia o pérdida cambiaria realizada
  cuando sus valores en libros difieren.
- La ruta conserva compatibilidad para documentos anteriores sin GL, usando la
  moneda y tasa histórica del documento como respaldo explícito.
- Verificación focal: capitalización multilínea multimoneda e idempotente, y
  neteo de anticipo existente; ambos casos aprobaron.

---

## 2026-08-07 — Diferencias bancarias con cuentas y moneda válidas

### Petición

La validación R2R continuó sobre los asientos automáticos originados por la
conciliación bancaria.

### Diagnóstico e implementación

- El comprobante de diferencia bancaria escribía IDs internos en el campo de
  código contable; el posting busca ese campo por `Accounts.code`, por lo que el
  ajuste podía fallar al contabilizar.
- Las cuentas bancaria y de diferencia se resuelven y validan ahora contra la
  compañía antes de crear líneas, y se almacenan sus códigos correctos.
- El comprobante declara la moneda de la cuenta bancaria, selecciona todos los
  libros activos y conserva el estado/tipo normal de un borrador contable.
- Evidencia focal: una diferencia USD 5 genera NIO 180 y EUR 4.50 en sus libros
  funcionales respectivos, con cuatro líneas GL balanceadas.

---

## 2026-08-07 — Capitalización multimoneda sin doble conversión

### Petición

La auditoría R2R avanzó a los generadores automáticos posteriores al registro,
comenzando por la capitalización de proyectos.

### Diagnóstico e implementación

- La capitalización tomaba el débito funcional del libro primario y lo declaraba
  como moneda original. Un gasto USD 10 registrado como NIO 360 podía volver a
  multiplicarse por 36 al crear el activo.
- El asiento automático usa ahora `debit_in_account_currency` o
  `credit_in_account_currency` cuando existe, y solo recurre al importe funcional
  para movimientos sin moneda original.
- Se eliminó el fallback fijo a NIO: la moneda se resuelve desde la entrada GL
  (`account_currency` y luego `company_currency`) y la ausencia de ambas se
  rechaza expresamente.
- La selección de gastos reconoce de forma normalizada `expense`, `gasto` y
  `gastos`, sin depender de mayúsculas.
- Evidencia focal: un gasto USD 10 / NIO 360 genera capitalización NIO 360 en el
  libro primario y EUR 9 en el libro secundario, ambos balanceados.

---

## 2026-08-07 — Submayores e inventario en moneda funcional

### Petición

Se continuó la validación rigurosa R2R conciliando AR/AP e inventario con el
mayor por libro y moneda.

### Diagnóstico e implementación

- AR/AP y el cronograma de vencimientos sumaban saldos nominales de distintas
  monedas como una sola cifra. Los importes se expresan ahora en moneda base al
  factor histórico del documento, conservando también la moneda original en
  cada fila.
- Las facturas de devolución se presentaban como cuentas por cobrar/pagar
  positivas. Ahora tienen signo contrario y reducen el saldo del submayor.
- La existencia de inventario a una fecha dependía del orden físico devuelto por
  SQL. Los movimientos se procesan cronológicamente por fecha, creación e ID,
  por lo que el saldo final es determinista incluso con inserciones retroactivas.
- Los documentos operativos de inventario sin moneda explícita clonaban su valor
  base en todos los libros. El contexto contable ahora reconoce esos importes
  como moneda base de la entidad y los convierte a la moneda funcional de cada
  libro. Los comprobantes manuales dirigidos por libro conservan su tratamiento
  específico.
- Evidencia focal: una recepción por NIO 36 produce inventario NIO 36 y EUR 0.90
  a tasa 0.025; un submayor con factura USD 10 y devolución USD 2 presenta NIO
  288, y una carga retroactiva conserva el último saldo cronológico.

---

## 2026-08-07 — Reportes operativos conciliables con moneda funcional

### Petición

Se prosiguió la validación record-to-report sobre los reportes operativos de
ventas, compras y margen bruto.

### Diagnóstico e implementación

- Los agregados por cliente, proveedor y artículo incluían documentos en
  borrador o anulados. Ahora solo consideran facturas posteadas (`docstatus=1`).
- Los importes se sumaban en moneda de transacción, mezclando divisas en una
  sola cifra. Se priorizan `base_grand_total`, `base_total` y `base_amount`, con
  compatibilidad para registros antiguos sin valores base.
- Las devoluciones se añadían como ventas/compras y cantidades positivas. Ahora
  reducen tanto el importe como la cantidad del agregado correspondiente.
- El margen bruto infería COGS buscando la palabra «costo» en observaciones y
  trataba todas las demás líneas de una factura como ingreso, incluyendo la
  cuenta por cobrar y los impuestos. Ahora clasifica exclusivamente cuentas de
  ingreso y costo desde el plan contable del GL del libro primario.
- El escenario R2R focal valida una factura extranjera, una devolución posteada
  y un borrador: el reporte presenta NIO 288 y 0.8 unidades, mientras el margen
  derivado del asiento posteado presenta NIO 360 sin contaminarse con la cuenta
  por cobrar.

---

## 2026-08-07 — KPIs R2R sin anulaciones ni mezcla de clasificaciones

### Petición

Se continuó la validación rigurosa del flujo record-to-report, priorizando la
corrección de errores e imprecisiones sobre verificaciones generales.

### Diagnóstico e implementación

- Los KPIs contables y bancarios del dashboard incluían líneas marcadas como
  anuladas o como reversas, aunque los estados financieros ordinarios las
  excluyen. Todos esos agregados usan ahora el mismo predicado vigente del GL.
- La clasificación del dashboard solo reconocía variantes capitalizadas y
  plurales. Se normalizó sin distinguir mayúsculas y se incluyeron ingreso,
  costo y gasto en sus variantes admitidas por el motor contable; la utilidad
  ya no omite el costo de ventas.
- El indicador «Asientos del periodo» ahora cuenta comprobantes distintos y no
  líneas individuales del mayor.
- Las consultas de balanza y libro mayor para herramientas de consulta también
  excluyen anulaciones y reversas. El saldo de la balanza conserva precisión
  decimal y deja de convertir importes contables a `float`.
- Comprobación focal del dashboard: 12 casos aprobados, incluyendo asientos
  anulados/reversados y una cuenta de costo en clasificación minúscula.

---

## 2026-08-07 — Cierre fiscal con saldos funcionales por libro

### Petición

Se pidió priorizar la corrección de errores e imprecisiones contables sobre la
ejecución repetitiva de pruebas y linters, manteniendo el objetivo de una
implementación realmente multimoneda y multilibro.

### Diagnóstico e implementación

- El cierre fiscal calculaba las cuentas de resultados únicamente en el libro
  principal y replicaba esos importes en todos los libros. En libros con moneda
  funcional distinta, el asiento de cierre no correspondía con sus saldos.
- El cálculo de cierre ahora se ejecuta por cada libro activo y cada línea queda
  dirigida explícitamente a ese libro. La contrapartida de utilidades acumuladas
  también se calcula independientemente por libro.
- Los comprobantes manuales admiten líneas internas dirigidas a un libro, sin
  cambiar el comportamiento normal de las líneas que deben postearse en todos
  los libros seleccionados.
- Se valida que todo libro indicado en una línea pertenezca a la compañía y a
  la selección del comprobante; así se evita omitir silenciosamente líneas al
  contabilizar.
- Comprobación focal: cierre USD 100 en el libro principal y EUR 90 en el libro
  secundario a tasa histórica 0.90; además pasaron los 42 casos existentes de
  comprobantes contables afectados.

---

## 2026-08-07 — Revaluación incremental y cierre mensual obligatorio por pasos

### Petición

Se continuó la validación rigurosa R2R multimoneda/multilibro sobre la
revaluación de partidas monetarias, su impacto en estados financieros y el
bloqueo formal del período.

### Diagnóstico e implementación

- Los ajustes de una revaluación previa se prorrateaban siempre contra el
  total original del documento. Si la primera revaluación ya se había hecho
  sobre un saldo parcial, una segunda ejecución volvía a reducir el ajuste y
  generaba una diferencia ficticia.
- Cada ajuste activo ahora se escala contra el saldo abierto que tenía su
  propia línea de revaluación. Una ejecución repetida sin cambios produce
  `completed_no_changes`, tanto para saldos completos como parciales.
- La pata monetaria de revaluación conserva la moneda extranjera original con
  importe nominal cero: modifica exclusivamente el valor funcional del libro.
  La contrapartida de resultado se registra en la moneda funcional.
- Solo facturas aprobadas (`docstatus=1`) son candidatas. Los borradores ya no
  pueden originar diferencias cambiarias ni asientos de cierre.
- El cierre mensual exige resultados actuales para comprobantes recurrentes,
  revaluación cambiaria y capitalización de proyectos. Estados `passed` y
  `skipped` completan un paso; pasos ausentes o fallidos bloquean el cierre.
  Se usa el resultado más reciente para permitir corregir y repetir un paso.

### Evidencia de aceptación

- La prueba integrada crea una factura USD mediante el posting real en libros
  USD, NIO y EUR, revalúa NIO de 3,600 a 3,700 y EUR de 90 a 93, y reconcilia
  balanza, resultados y balance general en cada libro.
- Se verifica que la revaluación no cambie las 100 unidades USD nominales, que
  los borradores sean excluidos y que una segunda corrida parcial no duplique
  diferencias.
- El cierre rechaza explícitamente períodos sin los tres controles
  obligatorios y permite cerrar cuando todos terminaron correctamente.
- La batería focal de revaluación, cierre, posting y reportes terminó con 86
  pruebas aprobadas.

### Precisiones contables posteriores

- La revaluación periódica dejó de usar cuentas de diferencia cambiaria
  realizada. Ahora postea exclusivamente en ganancia/pérdida **no realizada**;
  las cuentas realizadas quedan reservadas para cobros y pagos.
- Los totales de cabecera ya no suman importes de monedas funcionales
  incompatibles. `currency`, `total_gain` y `total_loss` representan el libro
  en la moneda base de la entidad; el detalle conserva los importes de todos
  los libros.
- Se corrigieron cinco búsquedas de `Entity` que trataban el código de compañía
  como si fuera la clave primaria interna. La resolución de moneda en posting,
  calculation contexts y revaluación ahora consulta explícitamente por
  `Entity.code`, evitando fallbacks silenciosos a otra moneda o libro.

---

## 2026-08-07 — Liquidación multimoneda recalculada por libro

### Petición

Como continuación de la auditoría R2R multimoneda/multilibro, se exigió que
los cobros y pagos conservaran por libro el costo histórico de AR/AP, la tasa
de liquidación y la diferencia cambiaria realizada hasta los reportes.

### Diagnóstico e implementación

- El motor de liquidación se ejecutaba una sola vez en la moneda base y la
  proforma resultante se clonaba a libros secundarios. Esto hacía imposible
  obtener diferencias cambiarias funcionales distintas por libro.
- Las proformas ahora se recalculan por cada moneda funcional. Para pagos, el
  saldo abierto se valora con las tasas históricas de las facturas
  referenciadas y la pata bancaria usa la tasa de la fecha de liquidación.
- Varias facturas se agregan como un costo histórico ponderado; facturas sin
  moneda explícita heredan la moneda base del pago en vez de asumir
  erróneamente la moneda del libro destino.
- Las cuentas de ganancia/pérdida cambiaria realizada y no realizada admiten
  `payment_entry`, en concordancia con las líneas que genera el propio motor
  de liquidación.
- Se tolera únicamente ruido aritmético inferior a 0.0001 antes de cuantizar
  GL y se descartan líneas que redondean a cero, preservando la restricción de
  débito o crédito positivo de `GLEntry`.

### Evidencia de aceptación

- La regresión R2R ahora continúa la factura USD con un cobro posterior: el
  libro NIO elimina AR 360, registra banco 370 y ganancia 10; el libro EUR
  elimina AR 9, registra banco 9.5 y ganancia 0.5.
- Después de liquidar, balanza, estado de resultados y balance general se
  reconcilian independientemente a NIO 370 y EUR 9.5.
- La batería focal de pagos, posting, seed multilibro, cobertura contable y
  reportes terminó con 354 pruebas aprobadas.

---

## 2026-08-07 — R2R multimoneda y multilibro por moneda funcional del libro

### Petición

Se solicitó validar rigurosamente el flujo Records to Reports y demostrar que
su implementación sea realmente multimoneda y multilibro, no solo que replique
asientos nominalmente entre libros.

### Diagnóstico e implementación

- Los documentos operativos usaban `base_currency` antes que `Book.currency`,
  por lo que un libro secundario podía almacenar montos de la moneda base del
  documento etiquetados con la moneda del libro.
- Una única tasa del documento se propagaba a todos los libros. La resolución
  ahora conserva esa tasa histórica únicamente para el libro cuya moneda
  coincide con la base documental y busca independientemente la tasa entre la
  moneda de transacción y la moneda funcional de cada libro.
- La persistencia GL ahora toma el monto original de la proforma como fuente
  para convertir cada libro. Las líneas de diferencia cambiaria que existen
  solo en moneda base preservan su importe en el libro base y se convierten
  explícitamente para libros secundarios.
- `GLEntryParams` transporta la tasa calculada por línea para distinguir tasas
  de documento y liquidación en pagos, evitando perder las diferencias
  realizadas al persistir la proforma.

### Evidencia de aceptación

- Se agregó una regresión end-to-end que registra una factura de venta de USD
  10 con libros NIO y EUR, tasas USD/NIO 36 y USD/EUR 0.9.
- La prueba exige cuatro entradas GL (dos por libro), conservación de USD 10
  en moneda original, saldos funcionales NIO 360 y EUR 9, balance por libro y
  aislamiento de resultados en balanza, estado de resultados y balance
  general.
- El bloque focal de posting, seed multilibro y reportes terminó con 53 pruebas
  aprobadas. La suite completa se ejecutó en segundo plano y su resultado se
  conserva en `/tmp/cacao-r2r-full-pytest-20260807.txt` para el control final.

---

## 2026-07-23 — Error 400 al iniciar sesión con el servidor de desarrollo

### Petición

Al iniciar la aplicación con `scripts/run_server.sh`, la pantalla de login
respondía `400 Su solicitud no se pudo procesar` al enviar las credenciales,
sin una excepción visible en el log.

### Diagnóstico e implementación

- Flask-WTF rechazaba el POST por CSRF antes de ejecutar la ruta de login: la
  aplicación fijaba `SESSION_COOKIE_SECURE=True`, pero el script sirve HTTP.
  El navegador no enviaba la cookie de sesión que contiene el token CSRF.
- `SESSION_COOKIE_SECURE` ahora conserva `True` por defecto y puede ajustarse
  con `CACAO_SESSION_COOKIE_SECURE`.
- `scripts/run_server.sh` establece esa variable en `False` por defecto para
  su servidor HTTP local; una instalación HTTPS puede sobrescribirla a
  `True`.
- Se añadió una prueba para preservar explícitamente esta configuración.

---

## 2026-07-23 — Arranque del servidor sin borrar la base de datos

### Petición

Se solicitó que `scripts/run_server.sh` no elimine datos al iniciar y que el
reinicio de la base ocurra únicamente al pasar `--clean`.

### Implementación

- El arranque normal ejecuta solo `cacaoctl --env test db init --seed`, que es
  idempotente cuando la base de datos ya existe.
- La limpieza destructiva quedó condicionada a `scripts/run_server.sh --clean`.
- Los argumentos desconocidos producen uso y código de salida 2.
- Se actualizó el README para documentar el comportamiento seguro y la opción
  explícita de reinicio.

---

## 2026-07-23 — Rechazo CSRF por host/puerto detrás de Replit

### Diagnóstico

El POST de login llegaba con HTTPS, pero Flask-WTF rechazaba el `Referer`
porque el proxy de Replit expone un host/puerto externo diferente al que Flask
observa internamente: `The referrer does not match the host.`

### Implementación

- `scripts/run_server.sh` desactiva solo la comparación estricta de
  `Referer`/host mediante `CACAO_CSRF_SSL_STRICT=False`.
- La validación del token CSRF continúa activa.
- El comportamiento seguro estricto queda como valor predeterminado de la
  aplicación y puede restaurarse con `CACAO_CSRF_SSL_STRICT=True`.

---

## 2026-07-23 — Persistencia de la base de datos del servidor local

### Diagnóstico

El script ejecutaba `db init` y `run` como procesos independientes mientras
`CACAO_TEST=True` seleccionaba SQLite en memoria. La base creada durante
`db init` se perdía al terminar ese proceso, por lo que el servidor arrancaba
sin datos ni esquema.

### Implementación

- `scripts/run_server.sh` define una URI SQLite persistente en
  `cacaoaccounting.db` dentro de la raíz del proyecto.
- La URI puede cambiarse con `CACAO_DATABASE_URL`.
- La opción `--clean` continúa siendo la única que elimina esa base.

---

## 2026-07-23 — Readiness de base de datos en Docker

### Petición

La existencia de una entidad no es suficiente para arrancar Docker. Debe
existir la tabla `user` y al menos un usuario; de lo contrario el contenedor
puede iniciar y fallar después con `no such table: user`.

### Implementación

- `db init` usa `usuarios_creados()` como criterio de base ya lista.
- Una base con entidades pero sin usuarios se repara mediante la
  inicialización normal, sin borrar datos.
- `docker-entry-point.sh` ya no ignora errores de `db init` ni `db migrate`.
  Un fallo de inicialización detiene el contenedor inmediatamente.

---

## 2026-07-22 — Validación del esquema por motor en GitHub Actions

### Petición

Se solicitó que `tests/test_04database_schema.py` se ejecutara al validar los
múltiples motores de base de datos, pero quedara fuera de las pruebas generales
de integración, del modo desktop y de coverage. El test debía respetar la
variable `DATABASE_URL` para validar el motor seleccionado.

### Implementación

- El test ahora centraliza la URI en `DATABASE_URL`, conservando SQLite en
  memoria como fallback local.
- Los jobs `build`, `desktop` y `coverage` excluyen explícitamente el test de
  esquema.
- El job `databases` prepara una base limpia por motor y ejecuta el test con
  `DATABASE_URL` para SQLite, MySQL/pymysql, PostgreSQL/psycopg2 y
  PostgreSQL/pg8000.
- La validación no usa seed, para evitar que datos demo interfieran con las
  pruebas de secuencias e identificadores.

## 2026-07-22 — Sincronización de README y script de desarrollo con cacaoctl

### Petición

Se solicitó actualizar `README.md` y `scripts/run_server.sh`, que todavía
documentaban y ejecutaban los comandos retirados `cleandb`, `setupdb` y
`flask run`.

### Implementación

- Se documentó el estado actual del núcleo contable, los módulos operativos,
  los reportes, el flujo documental, Docker y la CLI `cacaoctl`.
- Se actualizó el inventario de comandos a `db init|migrate|reset|clean|seed`,
  `run`, `serve`, `shell`, `routes`, `version`, `status` y `config`.
- `scripts/run_server.sh` ahora usa `cacaoctl --env test`, limpia y recrea la
  base de datos con seed, conserva variables configurables y ejecuta el
  servidor de desarrollo mediante `exec`.
- Se mantuvo explícito que el script es destructivo y solo debe usarse con
  datos locales/de prueba.

## 2026-07-22 — Contrato de anulación y reversión reconciliable

### Contexto y decisión contable

Se auditó el tratamiento de anulaciones en R2R, bancos e inventario partiendo de cuatro invariantes del producto:

- `GLEntry` es la única fuente de verdad financiera; bancos, AP, AR e inventario son capas reconciliables contra ella.
- Una **anulación** corrige dentro del período original. Solo se permite mientras ese período permanezca abierto, genera el contrasiento con la misma fecha contable y los reportes ordinarios ocultan tanto el asiento original como su contrasiento. El usuario puede incluir ambos para auditoría.
- Una **reversión** corrige en un período posterior. El comprobante original permanece vivo en el período anterior y un nuevo comprobante invertido permanece vivo en el período actual; ambos deben aparecer en reportes históricos y “as of”.
- El sistema es multilibro y multimoneda real: las capas operativas postean atómicamente en todos los libros activos, conservando moneda original, moneda funcional y tasa histórica. Solo Contabilidad puede seleccionar libros.

La auditoría confirmó que el reporting financiero general ya implementaba correctamente el primer contrato mediante `is_cancelled=False AND is_reversal=False`. El problema no era conservar `is_cancelled` como metadato del asiento original, sino aplicar solo la mitad del contrato en consumidores especializados.

### Causa raíz

El resumen bancario y varios cálculos derivados filtraban únicamente `GLEntry.is_cancelled=False`. Después de anular un cobro de 100, eso eliminaba el débito original pero conservaba el crédito de reversa, produciendo un saldo bancario de -100 en lugar de cero.

`StockLedgerEntry` no posee `is_reversal`. Al cancelar una recepción, el movimiento original queda marcado como cancelado y se agrega un contramovimiento con el mismo `(company, voucher_type, voucher_id)`. Los reportes y reconstrucciones filtraban solo el original, dejando vivo el contramovimiento. Como consecuencia, `StockBin` podía ser correcto inmediatamente después de cancelar pero reconstruirse con una cantidad y valoración incorrectas.

### Implementación

- Se creó `ledger_queries.py` como contrato compartido de consultas:
  - GL ordinario excluye originales cancelados y reversas del mismo período.
  - Stock ordinario excluye el grupo completo de un voucher cuando existe un movimiento original cancelado.
- Reportes bancarios, candidatos de conciliación, margen bruto, presupuesto y cierre fiscal aplican consistentemente el filtro GL completo.
- Kardex, existencias, rotación, slow-moving items y dashboard excluyen ambos lados de una anulación de stock sin requerir una migración de esquema.
- `rebuild_stock_bins()` y `rebuild_stock_valuation_layers()` suman el ledger físico completo, incluyendo original y contramovimiento. El par se neutraliza algebraicamente y la reconstrucción vuelve a ser reconciliable con el estado inmediatamente posterior a la cancelación.

### Pruebas y criterio de aceptación

La regresión integrada construye simultáneamente:

1. Un asiento bancario original cancelado y su reversa, más un movimiento activo.
2. Un movimiento de stock cancelado y su contramovimiento, más una recepción activa.

Se exige que el saldo bancario contenga solo el movimiento activo, Kardex omita el par cancelado y la reconstrucción de `StockBin` produzca cantidad y valor iguales al neto algebraico del ledger completo. Las pruebas existentes de creación de reversas GL, cancelación de recepción y preservación de reservas durante rebuild permanecen como protección complementaria.

### Alcance deliberado

No se cambió la semántica de “Revertir” del módulo contable: continúa creando un comprobante nuevo en un período distinto y no debe clasificarse como una anulación interna que los reportes oculten. Tampoco se agregó una columna a `StockLedgerEntry`; la identidad del voucher permite reconocer el grupo cancelado sin introducir una migración de esquema incompleta.

## Arquitectura y Patrones de Diseño

### Stack
- Python 3.12+, Flask, Alpine.js, SQLAlchemy, PostgreSQL (prod) / SQLite (dev/tests)
- Multi-stage Docker build: Caddy (HTTP/reverse proxy) → Waitress (WSGI) → Flask
- CLI: `cacaoctl` (Click-based, identidad propia sin Flask)

### Contabilidad
- `GLEntry` es la única fuente de verdad para saldos contables.
- Multi-ledger: modelo `Book` con `is_primary`, cada `GLEntry` lleva `ledger_id`. El posting engine genera entries paralelos por cada libro activo de la compañía.
- Políticas de integridad: 444 FKs con ON DELETE RESTRICT/CASCADE/SET_NULL + ON UPDATE CASCADE definidos en `database/__init__.py`.
- `DocBase.version` para optimistic locking en 15 modelos transaccionales.
- Secuencias atómicas con `with_for_update()` en `get_next_sequence_value()`.
- `document_no` es irreversible una vez emitido: no se reutiliza, no se renumera, no se libera.
- Reset de secuencia: la política sube a `monthly` cuando el prefijo usa tokens `*MM*`/`*MMM*`.

### Posting Engine (`contabilidad/posting.py`)
- `_document_contexts()` crea un `LedgerContext` por libro activo.
- `_assert_entries_balance()` valida balance por libro y por moneda de transacción.
- `_active_books()` resuelve libros activos de la compañía.
- Motor fiscal: `FiscalEngine` (DAG topológico), `SettlementEngine`, `AccountingMapper`.
- Motor landed cost: `LandedCostEngine` con prorrateo por valor/cantidad/peso/volumen.
- Snapshots SHA256 para trazabilidad inmutable de cada cálculo.

### Flujo Documental (`document_flow/`)
- `DOCUMENT_TYPES` en `registry.py`: 19 tipos transaccionales registrados.
- `ALLOWED_FLOWS`: pares de transiciones permitidas entre tipos.
- `create_actions`: acciones de creación dinámicas por tipo documental.
- `document_flow_tree.js`: árbol recursivo upstream/downstream con detección de ciclos.
- DocumentRelation persiste relaciones entre documentos para trazabilidad.
- Políticas de numeración: borradores conservan su `document_no` aunque cambien fecha/compañía/serie.

### Framework Transaccional
- Patrón "Voucher Pattern" (Header + Items) unificado para todos los formularios.
- `transaction_form_macros.html` + `transaction-form.js`: macro compartida con smart-select, grid, modal de detalle y bloque fiscal.
- `smart-select.js`: componente Alpine.js con `position: fixed`, filtrado server-side, autocompletado, soporte multi-filtros.
- Macro `document_flow_trace`: panel de trazabilidad con acciones dinámicas del backend.

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
- Revaluación: `ExchangeRevaluationService` multiledger, cálculo incremental por documento/cuenta.

### Maestros
- Códigos legibles: `CUSTM-00001`, `SUPLR-00001`, `ITEM-000001` via naming-series globales.
- PartyGroup como catálogo global de tipos de cliente/proveedor.
- Configuración por compañía: `CompanyParty` (AR/AP, tax rule, price list), `PartyAccount`, `ItemAccount`.
- Contactos y direcciones: `Contact`, `Address`, `PartyContact`, `PartyAddress`.
- Bloqueo de eliminación: `before_delete` en SQLAlchemy para Item/Warehouse/Party con historial transaccional.

### Importación (`cacao_accounting/imports`)
- Framework tabular: CSV (auto-detección delimitador), XLS, XLSX, ODS.
- Adaptadores por módulo: chart_of_accounts, customer, vendor, journal_entry, purchase_order, transaction_documents.
- Procesamiento asíncrono con daemon threads, rollbacks por documento, `with_for_update()`.
- Modo escritorio bloquea acceso. Generación de plantillas CSV/XLSX/ODS.

### Seguridad
- SEC-001 a SEC-011 resueltos (credenciales, JWT, CSRF, CSP, rate limiting, open redirect, etc.).
- `Flask-Limiter` (opcional): modo nube usa Redis, modo escritorio usa DummyLimiter.
- JWT tokens en caché (DummyCache o Redis) con timeout 8h, no en atributo volátil de User.
- Audit Trail: servicio centralizado en `audit_trail_service.py` (create/update/submit/cancel/reverse/reject).

### Reportes
- `financial_report.html`: patrón base para reportes financieros (account-movement, account-summary, trial-balance, balance-sheet, income-statement).
- `operational_report.html`: variante para subledger/kardex/banking/inventory.
- Drill-down: account_code → account-movement, document_no → detalle comprobante.
- Exportación XLSX/CSV con openpyxl. Hoja de filtros separada.
- Cancelados/reversas: `GLEntry.is_cancelled` y `GLEntry.is_reversal` excluidos por defecto, checkbox `show_cancellations` para incluirlos.

### CLI (`cacaoctl`)
- Click-based con `CacaoGroup` propio. `prog_name="cacaoctl"`.
- Subcomandos: `db init|migrate|reset|clean|seed`, `run`, `serve`, `shell`, `routes`, `version`, `status`, `config`.
- Confirmaciones interactivas para operaciones destructivas, `--force` para omitir.
- `db init` y `db migrate` son idempotentes: ejecutables al inicio de Docker sin bloquear.

---

## Hitos Principales (orden cronológico inverso)

### 2026-07-20
- **Bug Fix Settlement Engine**: Corregido violación de invariante `cash_amount + withholding_amount + payment_discount_amount == gross_settlement_amount` en `settlement/engine.py`. Cuando `eligible_discount_amount < gap_after_withholdings`, el `cash_amount` no se ajustaba, causando un desbalance de 2 unidades monetarias que impedía el posteo contable (`PostingError: "El asiento pro-forma no balancea"`). Fix: `cash_amount = settlement_amount - withholding_total - payment_discount_amount`. Prueba unitaria `test_settlement_discount_partial_gap_maintains_invariant` que valida el invariante.
- **CLI idempotente**: `db init` ahora es idempotente (exit 0 si la DB ya existe). Nuevo comando `db migrate` que aplica migraciones Alembic de forma idempotente. Alembic activado (`alembic.init_app(app)` habilitado). Docker entrypoint ejecuta ambos comandos al inicio.

### 2026-07-13
- **Caddy**: reverse proxy sirve assets estáticos, gzip, Cache-Control 24h, proxy a Waitress:8080.
- **Limpieza código muerto**: eliminados `gl/`, `validaciones/`, `admin/registros/`, `I18N.py`, `datos/base/data.py`.
- **Document Flow refactor (Fase 1)**: eliminado `document_flow_trace` macro muerta, `document_flow_summary()` y funciones auxiliares de `tracing.py`. Commit `e96a5da`.
- **Document Flow refactor (Fase 2)**: extraída lógica de pagos a `document_flow/payment.py` (~1150 líneas). service.py reducido de ~1818 a ~500 líneas. Re-exports para compatibilidad retroactiva. `DocumentFlowError` con status codes correctos via import tardío. Commit `25f87c3`.
- **Document Flow refactor (Fase 3)**: unificación de naming en variables de pago: `reference_type`→`model_type` (physical), `reference_id`→`document_id` (identifier), `source_type`→`flow_source_type` (logical). DB columns sin cambios. Commit `5f1b294`.
- **Document Flow refactor (Fase 4)**: 78 pruebas unitarias exhaustivas para `payment.py` cubriendo helpers puros, validaciones, payment target creation, payment candidates y outstanding cache. Commit `36e620d`.
- **Document Flow tests**: 30 pruebas unitarias para funciones publicas de `service.py` sin cobertura previa: `pending_qty`, `get_document_flow_items`, `get_pending_lines`, `close_line_balance`, `close_document_balances`, `list_source_documents`, `refresh_source_caches_for_target`. Commit `8938914`.

### 2026-07-11
- **Cash Flow Forecast**: módulo YTD con flujos reales (GLEntry), proyecciones AR/AP y manuales. Flujos de aprobación (Borrador→Aprobado→Cerrado→Archivado). Comparación side-by-side.
- **SEC-003**: Mitigación Open Redirect vía validación de `request.referrer`.
- **SEC-008**: JWT tokens en caché (no en User), con DummyCache funcional.

### 2026-07-10
- **DBA Audit**: UniqueConstraints, CheckConstraints, eliminación de 23 índices redundantes (589→566), version column, atomic sequences.
- **FK Cascade Policies**: 444 FKs con ON DELETE/ON UPDATE clasificados (RESTRICT/SET_NULL/CASCADE).
- **Dockerfile**: multi-stage build, imagen base actualizada, usuario no-root, HEALTHCHECK, npm --omit=dev.
- **R2R-19**: Bloqueo de eliminación de maestros con historial transaccional.
- **CLI cacaoctl**: rediseño con identidad propia, comandos agrupados, diagnóstico (status/config).
- **Stabilization batch**: CAS-13, S2P-15, O2C-24, CAS-18, R2R-17, CAS-20 corregidos.
- **CAS-02/CAS-03**: exchange_rate auto en pagos, FOR UPDATE en conciliación.

### 2026-07-08
- **O2C-03**: Reserva de inventario en SO, liberación en OV cancel/DN approve.
- **S2P-02/S2P-05/S2P-06/O2C-05**: Validaciones pre-submit, 3-way match, manejo amigable de errores.
- **CAS-02/CAS-03**: Auto-poblado exchange_rate, bloqueo FOR UPDATE en saldo pendiente.

### 2026-07-03
- **Códigos legibles**: CUSTM-, SUPLR-, ITEM- via naming-series globales.
- **Inventario**: cuenta por almacen+compañía, valuación global por compañía, Item y Bodega con Smart Select.
- **Reportes**: cancelados/reversas excluidos por defecto, reversión con fecha, naming series mensual.
- **Comprobantes**: importar líneas con plantilla XLSX, encabezados bilingües ES/EN.
- **Plantilla recurrente**: layout corregido (toolbar separado de cabecera).

### 2026-07-02
- **Inventario**: cuenta de inventario solo en bodega (removido de ItemAccount), valuación en Entity.

### 2026-07-01
- **Terceros**: perfil básico + cumplimiento legal, simplificación de clasificación, contactos/direcciones visibles.
- **Configuración por compañía**: AR/AP, tax rule, price list por compañía en Clientes y Proveedores.
- **Item**: configuración contable por compañía (expense/income/COGS accounts + cost center).
- **UOM**: maestro de unidades con conversiones, seed localizado ES/EN.

### 2026-06-30
- **Cobertura**: 80.4% (22,566 líneas). Tests unitarios para servicios.

### 2026-06-27
- **Filtros de listados**: búsqueda simple en Compras, Ventas y Bancos.
- **Badges semánticos**: cálculo dinámico de estados en tarjetas de módulo.
- **Navegación lateral**: Módulos e Importaciones movidos a Settings.

### 2026-06-18
- **Refresh visual global**: capa CSS en `cacaoaccounting.css` sobre design system existente.

### 2026-05-24
- **Flujo documental expandible**: journal_entry como destino contable, relaciones contables, anticipos.
- **Cierre matriz operativa**: documentos alineados con `DOCUMENT_TYPES` y `ALLOWED_FLOWS`.

### 2026-05-23
- **Conciliación AR/AP masiva**: `/cash_management/payment-reconciliation`.
- **Stock Reconciliation**: cantidad + valor, GL balanceado, cuenta de bodega.
- **Payment Entry**: impuestos/cargos visibles, UX alineada a journal.html.

### 2026-05-22
- **Payment Entry completa**: referencias, anticipos, candidatos manuales, snapshots de auditoría.
- **Documentación relaciones**: `relaciones.md` simplificada a matriz operativa.
- **Legacy eliminado**: macro `crear_dropdown` removida.

### 2026-05-21
- **Unificación acciones Crear**: 100% basada en `document_flow_trace` + `create_actions`.
- **Expansión matriz**: notas → pago, anticipos desde órdenes, notas desde recepción.
- **Hardening pre-merge**: `enabled`, `condition`, `model_target_type` en acciones.

### 2026-05-19
- **MVP Fiscal**: matriz por doctype, API preview, UX común Impuestos y Cargos.
- **Persistencia fiscal**: snapshots inmutables, consumo en submit_document.

### 2026-05-17
- **Motores de cálculo**: FiscalEngine, LandedCostEngine, SettlementEngine con snapshots SHA256.
- **AR/AP y terceros**: PartyGroup, configuración por compañía, contactos/direcciones.
- **Revalorización NIIF**: ExchangeRevaluationService multiledger.

### 2026-05-16
- **Merge Bancos**: integración con resolución de conflictos, notas/transferencias compartidas.
- **Formato monetario**: helpers Jinja para moneda con código (`NIO 1,000.00`).

### 2026-05-14
- **Estandarización S2P/O2C**: framework transaccional unificado, "Actualizar Elementos".
- **Seed contable**: empresa cacao con 3 libros (NIO, USD, EUR), tasas, dimensiones.

### 2026-05-12
- **Cierre contable**: Comprobantes Recurrentes, Asistente de Cierre Mensual, reportes financieros.

### 2026-05-11
- **UX contable**: rediseño de formularios de Cuentas y Entidades, Smart Select para cuentas padre.

### 2026-07-14
- **Per-Transaction-Type Numbering**: se agregaron 5 entity types separados en NamingSeries para transacciones bancarias (`bank_payment`, `bank_receipt`, `bank_transfer`, `bank_debit_note`, `bank_credit_note`), cada uno con su propia serie predeterminada.
- **BankAccountNumberingConfig**: nuevo modelo para configurar la numeración por tipo de transacción + cuenta bancaria (serie interna, uso de contador externo, contador externo asociado).
- **UI de configuración**: sección editable en la vista detalle de cuenta bancaria con tabla por tipo de transacción, que permite asignar serie interna y contador externo por tipo.
- **Contadores externos mejorados**: toggle activo/inactivo, edición de datos (nombre, prefijo, padding, serie asociada).
- **Fallback legacy**: las cuentas existentes sin `BankAccountNumberingConfig` siguen funcionando con los defaults legacy del modelo `BankAccount`.
- **Seed actualizado**: datos demo crean configuraciones por tipo de transacción para las chequeras NIO y USD.

### 2026-07-15
- **Macro recursivo de árbol reutilizable**: Se creó `tree_macros.html` con macros `render_tree`, `tree_toolbar` y `tree_toolbar_close` para renderizar árboles jerárquicos de profundidad ilimitada con Alpine.js expand/collapse. Reemplaza el nesting hardcodeado de 8 niveles en Cuentas y Centros de Costo.
- **Vista árbol para Unidades de Negocio y Proyectos**: Los listados `unidad_lista.html` y `proyecto_lista.html` ahora usan el macro recursivo con `build_tree_data()` en lugar de tablas planas.
- **Funciones auxiliares de árbol**: `obtener_arbol_cuentas/ccostos/unidades/proyectos()` y `build_tree_data()` en `auxiliares.py` normalizan datos para el template.
- **Helper `get_descendant_ids()`**: En `database/helpers.py`, calcula recursivamente todos los IDs descendientes de un nodo. Se usa en las rutas de edición para excluir descendientes del select de padre.
- **Edición jerarquica mejorada**: Las rutas `editar_unidad` y `editar_proyecto` ahora excluyen el nodo actual y todos sus descendientes del selector de padre, previniendo selecciones inválidas.
- **Reportes: group-by por Unidad/Proyecto**: Se agregaron `unit_code` y `project_code` como opciones de agrupación en el dropdown del reporte financiero.
- **Reportes: filtros en sección principal**: Los filtros de Unidad de Negocio y Proyecto se movieron de filtros avanzados a la sección principal, junto con el checkbox "Incluir descendientes".
- **Enlaces de capitalización en comprobante**: Se agregaron propiedades `capitalized_by_ref` y `capitalization_origin_ref` al modelo `ComprobanteContable`. El template `journal.html` muestra enlaces bidireccionales "Capitalización de" y "Capitalizado por" con links a los comprobantes relacionados.

---

### 2026-07-14 (Sesión actual)
- **IMP-02: Doctype dedicado para import_landed_cost_confirmed**: Se creó la capa documental completa alrededor de la funcionalidad existente de landed cost engine/orchestrator:
  - Modelos: `ImportLandedCost`, `ImportLandedCostItem`, `ImportLandedCostCharge` en `database/__init__.py`
  - Registro en `DOCUMENT_TYPES` (document_flow/registry.py) como `import_landed_cost`
  - Perfil en `_FISCAL_MATRIX` (fiscal_preview_service.py) con `recognition_event="import_landed_cost_confirmed"`
  - Flujo permitido: `purchase_invoice → import_landed_cost` con `relation_type="landed_cost"`
  - Naming series: código `ILC` en document_identifiers.py
  - Routes: CRUD completo en compras blueprint (list, new, detail, submit, cancel)
  - Posting engine: `post_import_landed_cost` en posting.py con integración al motor de cálculo
  - Document builder: `_build_import_landed_cost_context` en document_builders.py
  - UI templates: listado, detalle con cargos/artículos, formulario nuevo con grid transaccional y cargos dinámicos
  - Cleanup references para integridad de flujo documental
  - Primary flow target en status.py para seguimiento de progreso

### 2026-07-14 (Corrección de tests)
- **Corrección test_journal_new_route_renders_new_backend_form**: Se restauró el botón "Descargar Plantilla" en el tab de subir archivo del modal de importación de comprobantes contables. El botón previamente fue reemplazado por un enlace al asistente de importación compartido, pero el test verificaba la presencia del texto "Descargar Plantilla" en el HTML renderizado. Se mantuvo el enlace al asistente como referencia adicional.
- **Corrección test_routes_import_entries**: Se migró el test de importación de proyecciones de flujo de caja del endpoint directo `/cash-forecast/{id}/entry/import` (eliminado) al flujo del asistente de importación compartido (`ImportBatch` → upload → validate → execute). El test ahora crea lotes de importación, sube archivos CSV/XLSX, y ejecuta el pipeline completo de importación del módulo `imports`.

### 2026-07-14 (Jerarquías de Unidad/Proyecto y Capitalización Automática)
- **Jerarquías para Unidad de Negocio y Proyectos**: Se implementó una estructura de árbol recursiva de profundidad ilimitada para `Unit` (alias `Unidad`), `BusinessUnit`, y `Project` con soporte para propiedades `parent`, `children`, `ancestors`, y `descendants`.
- **Prevención de Ciclos y Validación**: Se implementaron validaciones contra ciclos (`check_hierarchy_cycle`) y propagación automática de rutas (`update_hierarchy_attributes`) en `database/helpers.py`. Se restringió la eliminación de nodos padre con hijos activos.
- **Consolidación en Reportes**: Se actualizaron las consultas de reportes (general ledger y presupuesto) para incluir opcionalmente descendientes (`include_descendants`) y consolidar sus saldos.
- **Capitalización Automática de Proyectos**: Se implementó el servicio `ProjectCapitalizationService` para identificar gastos no capitalizados de proyectos marcados como capitalizables y generar comprobantes `ComprobanteContable` de tipo `"Capitalización Automática de Proyecto"` con enlace bidireccional, restricciones de cancelación/edición, y soporte para reversas automáticas.

---

## Decisiones de Diseño Clave

1. **append-only**: Cancelaciones y reversas crean entradas nuevas (con `is_cancelled=True`), nunca eliminan originales.
2. **UniqueConstraints**: StockLedgerEntry/StockValuationLayer NO deben tener UniqueConstraint en (voucher_type, voucher_id, item_code, warehouse) porque multi-line documents, reversiones y landed cost crean duplicados legítimos.
3. **LedgerMappingRule**: modelo existe como schema-only sin lógica de negocio implementada.
4. **AuditLog legacy**: superseded por `AuditTrail` (audit_trail_service.py). El antiguo `AuditLog` solo se usa en document_flow/service.py para relaciones.
5. **import_landed_cost_confirmed**: existe como event_type string en el orchestrator, no como doctype dedicado.
6. **Smart Select migration**: completada al 100%. Solo quedan `<select>` de enum/choice.
7. **Reportes**: `financial_report.html` es el patrón superset; `operational_report.html` es la variante simplificada.
8. **Docker**: Internet → Caddy:80 → Waitress:8080 → Flask. Caddy maneja static + compresión + proxy.
9. **Document Flow naming**: `flow_source_type` (lógico, ej. `purchase_credit_note`), `model_type` (físico SQLAlchemy, ej. `purchase_invoice`), `document_id` (identificador). DB columns sin cambios, solo Python variables.
10. **Document Flow modules**: `payment.py` para lógica de pagos/conciliación AR/AP; `service.py` para relaciones documentales y creación de documentos; `registry.py` para tipos/flows permitidos.

---

## Refactorización de Complejidad Cognitiva (2026-07-21)

Se refactorizaron 6 funciones con complejidad cognitiva superior a 15, extrayendo funciones auxiliares para reducir la carga cognitiva:

| Archivo | Función original | Complejidad original | Complejidad final | Funciones extraídas |
|---|---|---|---|---|
| `compras/__init__.py` | `_create_import_landed_cost_from_request` | 34 | ~12 | `_resolve_supplier_from_invoice`, `_parse_grid_rows_from_form`, `_save_import_landed_cost_items`, `_save_import_landed_cost_charges`, `_link_landed_cost_to_invoice` |
| `bancos/__init__.py` | `bancos_cuenta_bancaria_numbering_config` | 33 | ~8 | `_save_numbering_configs`, `_get_or_create_numbering_config`, `_build_numbering_config_response`, `_build_single_config_entry` |
| `contabilidad/project_capitalization_service.py` | `run_capitalization` | 32 | ~10 | `_is_eligible_capitalization_entry`, `_find_capitalizable_project`, `_is_already_capitalized`, `_resolve_capitalization_accounts`, `_create_capitalization_journal`, `_query_eligible_entries`, `_process_single_entry` |
| `ventas/__init__.py` | `_validate_invoice_prices_against_source` | 35 | ~10 | `_load_sales_tolerance_config`, `_calculate_price_variance`, `_validate_single_item_price`, `_resolve_source_item_rate` |
| `contabilidad/__init__.py` | `nuevo_proyecto` | 20 | ~12 | `_validate_project_creation_form`, `_build_project_from_form` |
| `contabilidad/__init__.py` | `editar_proyecto` | 20 | ~8 | `_populate_project_edit_form`, `_validate_project_edit_form`, `_setup_project_edit_form` |

**Técnicas aplicadas**: Early returns, extracción de helpers, guard clauses, eliminación de duplicación de lógica (e.g., parseo de grid HTML).

### 2026-07-21 (Segundo lote - SonarCloud remainder)

Segundo lote de refactorización de 8 funciones con complejidad cognitiva > 15 (restantes de SonarCloud):

| Archivo | Función original | Complejidad original | Funciones extraídas |
|---|---|---|---|
| `imports/routes.py` | `upload` | 17 | `_extract_file_extension`, `_validate_mime_type`, `_persist_uploaded_file` |
| `accounting_engine/document_builders.py` | `_build_import_landed_cost_context` | 17 | `_build_landed_cost_item_contexts`, `_build_landed_cost_tax_rules` |
| `bancos/__init__.py` | `_create_payment_from_request` | 20 | `_resolve_payment_numbering`, `_finalize_and_commit_payment` |
| `contabilidad/__init__.py` | `external_counter_edit` | 19 | `_update_counter_from_form`, `_sync_counter_naming_series_map` |
| `approval_engine.py` | `approve` | 22 | `_find_applicable_rule`, `_finalize_approval` |
| `approval_engine.py` | `next_approver` | 24 | `_collect_approvers_from_rules` |
| `compras/purchase_reconciliation_service.py` | `get_unlinked_purchase_invoices` | 16 | `_resolve_po_number`, `_resolve_supplier_name` |
| `compras/purchase_reconciliation_service.py` | `get_unlinked_purchase_receipts_summary` | 23 | `_aggregate_pending_by_receipt`, `_resolve_po_number`, `_resolve_supplier_name` |

**Técnicas aplicadas**: Early returns con guard clauses, extracción de helpers compartidos entre funciones hermanas (`_resolve_po_number`, `_resolve_supplier_name`), separación de lógica de persistencia, eliminación de lógica duplicada de resolución de proveedor/PO.

### 2026-07-21 (Issues abiertos de SonarCloud)

La API pública de SonarCloud (`/api/issues/search`, proyecto `cacao-accounting_cacao-accounting`, `resolved=false`) reportó 34 issues abiertos: 22 de complejidad cognitiva, 8 de seguridad de GitHub Actions y 2 variables locales sin uso. Se implementó un tercer lote de correcciones:

- Extracción de helpers para aprobación administrativa, creación de facturas/recepciones, validaciones de cantidades de compras/ventas, crédito de clientes, conciliación bancaria, relaciones documentales y conciliación de inventario.
- Simplificación del parseo de artículos, cuentas por compañía, configuración de terceros y serialización de líneas contables.
- Eliminación de las variables no utilizadas en edición de proyectos.
- El workflow de CI instala dependencias con `--only-binary=:all:` y versiones explícitas; `odfpy==1.4.1` conserva una instalación aislada desde fuente por no disponer de wheel compatible.

Validación realizada: Ruff y compilación Python pasan. La suite completa se ejecutó en segundo plano con salida en `/tmp/sonar-open-issues-pytest.log`; el primer resultado fue 1508 pasadas, 8 omitidas y dos fallos. Se corrigió el contrato de mensajes de cuentas contables y se hizo tolerante la validación MIME cuando `python-magic` no está disponible, rechazando HTML y conservando el aviso de validación degradada. Las pruebas focalizadas de imports, flujo de caja e inventario pasan (15 pasadas).

Por solicitud de continuidad, la verificación final se limitó a los módulos afectados: `254 passed` en 2:42 usando aprobación, inventario, crédito de ventas, flujo documental, posting, conciliación bancaria, ventas, compras, pagos, servicios e imports. No se ejecutó nuevamente la suite completa.

### 2026-07-21 (Corrección de CI del PR #266)

El análisis del PR en SonarCloud reportó 0 issues, pero GitHub Actions falló en Mypy por inferir `BaseTabla` para los items dinámicos de las validaciones de cantidades de ventas y compras. Se anotaron explícitamente como `Any` los resultados de esos lookups, preservando el comportamiento y satisfaciendo los atributos `qty` e `item_code` usados por la validación.

### 2026-07-22 — Review contra `origin/main` y corrección D401

Se solicitó revisar los cambios locales frente a `origin/main`. Durante la validación de calidad se detectó D401 en el docstring privado de `_validate_and_fix_stock_bin_reserved_qty`; se corrigió la primera línea a modo imperativo (`Validate and correct...`) sin modificar el comportamiento.

El review continúa sobre los 52 commits divergentes, con foco en aislamiento por compañía, selección multilibro, aprobaciones y filtros de anulaciones.

### 2026-08-09 — Referencias legacy de pagos en AR/AP

Durante la auditoría end-to-end se confirmó que `compute_outstanding_amount` retornaba temprano cuando encontraba referencias modernas enlazadas mediante `DocumentRelation`. En ese caso ignoraba referencias históricas de `PaymentReference` sin relación documental, inflando el saldo pendiente. El reporte AR/AP también excluía esas referencias legacy al usar un `JOIN` interno.

Se corrigió la lectura para combinar referencias modernas y legacy, excluir relaciones canceladas y evitar duplicados en el reporte. Se añadió una prueba con una factura de 100, un pago moderno de 30 y un pago legacy de 20; el saldo y el total pagado esperado son 50.

Validación: prueba de regresión individual `1 passed`; batería AR/AP de saldos, subledger, aging, maturity y allocations `11 passed`; `git diff --check` limpio. El issue #280 permanece abierto para completar la matriz O2C, créditos, reversals y reconciliación integral contra GL.

### 2026-08-09 — Suite completa posterior a la corrección AR/AP

La ejecución indicada por `AGENTS.md`, usando `.venv`, terminó con código de salida `0`: `1603 passed, 8 skipped, 174 warnings` en 27:30. El resultado quedó persistido en `test_results_audit_current_20260809.log`.

Validación de los archivos modificados: Black, Ruff, Flake8, Mypy y `git diff --check` pasan. El chequeo global de Black todavía identifica tres tests preexistentes para reformatear y Ruff identifica 28 incidencias en el conjunto global; no se modificaron archivos no relacionados. Flake8 y Mypy globales pasan. Esto queda como deuda de calidad, no como un fallo introducido por `cab6493`.

## 2026-08-09 — Auditoría O2C (Order to Cash): hallazgos y controles verificados

### Petición
Ejecutar una auditoría READ-ONLY del flujo O2C (Cotización→OV→ND→Factura→Nota de Crédito/Débito→Pago) contra los objetivos de negocio (AR es proyección del GL, control de sobre-entrega/sobre-facturación, aislamiento por compañía), verificando la corrección del commit `561b440` y listando hasta 15 hallazgos por severidad más los controles que se verificaron como OK.

### Plan implementado
- Mapeo de rutas y validaciones en `ventas/__init__.py` (submit OV/ND/Factura, límite de crédito, tolerancia de precio, reserva de inventario, relaciones documentales) y `document_flow/` (pagos, conciliación, outstanding, validación de cantidades/precios).
- Verificación del motor de contabilización (`posting.py`: `_signed_amount`, `_upsert_stock_bin` INV-10/FOR UPDATE, `_update_grand_total_if_needed`) y del subledger AR/AP (`reportes/services.py`).
- Confirmación del fix `561b440` (aislamiento por compañía en `_document_payment_references` y `_payment_allocations`).

### Hallazgos confirmados (resumen)
1. Notas de crédito no reducen el saldo de la factura origen: `_compute_allocated_notes_amount` busca `target_type IN (sales_credit_note, purchase_credit_note)` pero `_save_sales_invoice_items` guarda relaciones con `target_type="sales_invoice"` → código muerto; sobre-aplicación de pagos, dunning y límite de crédito distorsionados (Alto).
2. `SalesMatchingConfig.require_sales_order` nunca se ejecuta: facturas sin OV/ND evaden sobre-facturación (`_validate_sales_invoice_quantities` solo revisa líneas con relación) y con `update_inventory` auto-generan ND que consume stock sin reserva (Alto).
3. Doble liberación de reserva en entregas parciales: `_release_reservation_for_delivery_note` corre DESPUÉS del posting cuyo clamp INV-10 ya redujo `reserved_qty` a `actual_qty`; OV=100/stock=100/ND=60 deja `reserved=0` en vez de 40 → sobre-venta (Alto).
4. Validación de precio solo para fuentes `sales_order`; facturas desde ND o manuales omiten la tolerancia (`_resolve_source_item_rate` retorna None) (Medio).
5. Límite de crédito ignora OVs aprobadas (solo facturas aprobadas vía `_approved_customer_invoices`) (Medio).
6. Montos de línea negativos o inconsistentes con `qty×rate` se aceptan (`_line_amount` confía en `amount_N`; solo se valida `rate>0` y `amount!=0`) (Medio).
7. `_validate_reversal_of` no limita el monto de la NC/ND contra el saldo de la factura origen (Medio).
8. Ruta de conciliación facturas/pagos (`bancos_conciliacion_facturas_pagos`) sin `exige_acceso_compania`/`verifica_permiso`: cualquier usuario autenticado puede conciliar pagos de cualquier compañía (Medio).
9. `_payment_order_allocated` sin filtro de compañía (solo usada en la ruta de anticipos sin UI) (Bajo).
10. Anticipos aplicados a factura solo generan asiento de compensación si `apply_advances_automatically=True` (default False); divergencia AR proyección vs GL si se usa la API directamente (Bajo).

### Controles verificados OK
Aislamiento por compañía en `_document_payment_references`/`_payment_allocations`; `apply_payment_reconciliation` valida compañía/tercero/tipo de pago, moneda (CAS-03), tope contra saldo (`_validate_and_get_outstanding`), duplicados y consumo de caja; límite de crédito implementado (submit + re-chequeo en approval engine); sobre-entrega en ND; sobre-facturación en líneas con relación; `StockBin` con FOR UPDATE; signo de retornos en GL (`_signed_amount`) y subledger; revalidación en aprobación final.

### 2026-08-09 — Corrección de aplicación de notas de crédito O2C

Se reprodujo el cálculo con una factura de 100 y una nota de crédito de 25 enlazada mediante `DocumentRelation`. La relación usa `target_type="sales_invoice"` porque apunta al modelo físico, mientras que `SalesInvoice.document_type` contiene `sales_credit_note`. La consulta anterior filtraba el tipo lógico en la relación y devolvía saldo 100, ignorando la nota.

La consulta AR/AP ahora identifica la naturaleza de la nota por `SalesInvoice.document_type` o `PurchaseInvoice.document_type`, manteniendo el aislamiento por documento, estado y fecha. Se añadió la regresión `test_compute_outstanding_amount_applies_credit_note_by_document_type`, que exige saldo 75.

Validación: 2 pruebas de notas `passed`; batería focal de saldos, subledger, aging, maturity y notas `15 passed`; Black, Ruff, Flake8, Mypy y `git diff --check` pasan para los archivos tocados. El issue #280 continúa abierto para completar créditos, reversals y conciliación O2C ↔ GL.

### 2026-08-09 — Control de OV obligatoria en O2C

Se confirmó que `SalesMatchingConfig.require_sales_order` se almacenaba pero no se consultaba durante el submit de facturas. Se añadió `_validate_sales_order_requirement`, que acepta una OV directa, una DN vinculada a OV o una relación activa de línea; rechaza facturas manuales cuando la compañía exige OV y mantiene exentas las notas de crédito/débito y devoluciones.

Validación: la regresión de factura manual sin OV pasa; la batería O2C de `test_o2c_sales_fixes.py` y `test_sales_price_validation.py` terminó `27 passed`. Black, Ruff, Flake8 y Mypy pasan en archivos tocados. El issue #280 permanece abierto porque aún faltan controles de reserva, precios desde DN, reversals y reconciliación contra GL.

### 2026-08-09 — Corrección de reserva de inventario en entregas parciales

Se reprodujo el caso INV-10 con stock 100, reserva 100 y una DN vinculada a OV por 60. El posting reducía el stock a 40 y el clamp de `StockBin` reducía primero la reserva; el hook posterior restaba otra vez 60. El resultado previo era reserva 0, aunque debían quedar 40 reservadas.

`_upsert_stock_bin` ahora permite preservar temporalmente la reserva para movimientos de DN vinculados a OV; `_release_reservation_for_delivery_note` continúa siendo el único punto que libera la cantidad entregada. Los movimientos generales y conciliaciones conservan el clamp de reserva.

Validación: regresión de reserva parcial `1 passed`; batería de inventario/reservas `40 passed`; Black, Ruff y Flake8 pasan en archivos tocados. El issue #279 permanece abierto para reconciliar cantidades, valoración, COGS y GL de inventario de extremo a extremo.

### 2026-08-09 — Corrección de retiros bancarios importados

Se reprodujo el flujo del issue #304 con una fila de extracto que contiene `withdrawal=25.00` y depósito vacío. El adaptador vivo convertía el lado vacío a `Decimal("0")`; `_bank_amount` prefería ese cero y la conciliación rechazaba la transacción como sin monto.

El adaptador ahora conserva el lado vacío como `None`, y los resolvers de monto usan el retiro cuando no existe un depósito positivo. Se añadió una regresión que verifica importación, monto conciliable y monto asignable de 25.

Validación: prueba nueva y prueba existente de importación `2 passed`; Black, Ruff, Flake8 y Mypy pasan en archivos tocados. El issue #304 permanece abierto para completar la conciliación bancaria, autorización, dirección y reversas.

### 2026-08-09 — Recuperación de cola FIFO/promedio tras stock negativo

Se reprodujo INV-AUDIT-01 con capas `+10 @ 10`, `-15` y `+10 @ 12`. La cola anterior lanzaba `PostingError("El registro de valuacion de inventario esta inconsistente")` al reconstruir o calcular la siguiente salida, aunque `allow_negative_stock` estuviera activo.

`_valuation_queue` ahora mantiene un déficit de cantidad; las recepciones posteriores compensan primero ese déficit y solo el remanente entra a FIFO/promedio. La regresión verifica que quedan 5 unidades a 12 y que su costo es 60.

Validación: pruebas de stock negativo/cola `4 passed`; Black, Ruff, Flake8 y Mypy pasan en archivos tocados. El issue #319 permanece abierto para revisar el resto de la valoración negativa, reconstrucción y controles de stock.

### 2026-08-09 — Protección del cierre fiscal y flags R2R (#334, #335)

Se confirmó que los flags `is_closing` e `is_fiscal_year_closing` no deben aceptarse desde un payload manual sin autorización. El servicio de comprobantes ahora exige un flujo autorizado para crear cierres, impide cambiar los flags al editar borradores y valida el año fiscal antes de generar cualquier GLEntry. El cierre fiscal requiere año indicado, entidad coincidente y cierre administrativo previo.

Para evitar doble cierre concurrente, `create_fiscal_year_closing_voucher` y `submit_journal` bloquean la fila `FiscalYear` con `with_for_update` durante la transacción; el segundo proceso observa `financial_closed` y es rechazado. Las reversiones genéricas ya no heredan flags de cierre y los cierres fiscales deben revertirse mediante el flujo fiscal dedicado.

Validación: `tests/test_09_journal_entry_form.py` y `tests/test_fiscal_year_closing.py`: `29 passed`; Ruff, Flake8, Mypy y `git diff --check` pasan en archivos tocados. Los issues #334 y #335 permanecen abiertos para tracking y revisión posterior.

### 2026-08-09 — Estado transaccional de comprobantes recurrentes (#337)

Se verificó el flujo existente: la aplicación recurrente genera intencionalmente un borrador para permitir revisión y posteo manual desde el cierre mensual, pero la marcaba `applied` antes de que existiera cualquier GLEntry. Esto era inconsistente con el modelo GL como fuente de verdad y podía ocultar borradores no contabilizados.

La aplicación ahora se registra como `pending` y cambia a `applied` únicamente dentro de `submit_journal`, después de que el posting haya sido validado. La plantilla se marca completada en ese mismo momento; una cancelación del comprobante marca la aplicación como `reversed` y reabre la plantilla cuando correspondía. La plantilla se bloquea con `with_for_update` durante la aplicación para serializar reintentos concurrentes y evitar duplicados.

Validación: `tests/test_12_recurring_journals.py`: `7 passed`; la prueba E2E comprueba `pending → applied → reversed`, junto con la reapertura de la plantilla. Black, Ruff y `git diff --check` pasan en archivos tocados. El issue #337 permanece abierto para tracking y validación en CI.

### 2026-08-09 — Idempotencia de capitalización automática de proyectos (#336)

Se confirmó una ventana transaccional en la que el comprobante de capitalización ya estaba contabilizado, pero el comprobante fuente aún no tenía `capitalized_by_id`. Dos ejecuciones concurrentes podían seleccionar el mismo gasto y duplicar el activo capitalizado.

`_process_group` ahora bloquea el comprobante fuente con `with_for_update`, vuelve a comprobar `capitalized_by_id`, asigna el vínculo antes de invocar `submit_journal` y deja que el commit del posting persista ambos cambios atómicamente. Si otra ejecución llega después del commit, omite el grupo y no lo cuenta como una nueva capitalización.

Validación: `tests/test_hierarchy_and_capitalization.py`: `4 passed`; Black, Ruff y `git diff --check` pasan en archivos tocados. El issue #336 permanece abierto para tracking y validación concurrente en CI.

### 2026-08-09 — Lote de controles de inventario y aislamiento de bodegas (#321, #327, #328, #331, #332)

Se verificaron y corrigieron cinco riesgos que afectaban cantidades físicas y reservas:

- Las reservas de órdenes de venta y sus liberaciones ahora se calculan en UOM base; una orden de 1 caja con conversión 12 reserva 12 unidades.
- La liberación/restauración de una nota de entrega consulta la relación con la orden y usa la bodega que originó la reserva, aunque la DN indique otra bodega.
- El posting de movimientos de stock valida en servidor que cada bodega exista, esté activa y pertenezca a la compañía del documento.
- `StockBin` ya no elimina reservas al cruzar stock cero o negativo; la reserva se libera solo mediante cancelación/entrega explícita.
- Las transferencias aplican el mismo fallback de costo que las salidas para artículos con `allow_negative_stock=True`.

Validación conjunta: `tests/test_stock_reservation.py`, `tests/test_07posting_engine.py` y `tests/test_o2c_sales_fixes.py`: `84 passed, 9 warnings`. Validación adicional tras el ajuste de tipos: `15 passed, 7 warnings`. Ruff, Flake8, Mypy y `git diff --check` pasan en los archivos tocados. Los issues #321, #327, #328, #331 y #332 permanecen abiertos para tracking y validación CI.

### 2026-08-09 — Lote bancario y O2C acumulado (#300, #306, #307)

Se corrigieron dos riesgos del lote acumulado. La búsqueda de candidatos bancarios ahora exige que la dirección económica coincida (depósito con cobro/débito GL; retiro con pago/crédito GL), calcula el importe conciliable limitado por el movimiento bancario y conserva matches parciales legítimos. En O2C, las notas de crédito nuevas y editadas se validan contra el saldo acumulado de la factura origen, considerando pagos y notas aprobadas anteriores; las notas de débito no se limitan porque incrementan la cuenta por cobrar.

Validación focal: `113 passed, 2 warnings`. Calidad: Black, Ruff, Flake8, Mypy y `git diff --check` pasan. Suite completa ejecutada una vez para el lote: `1616 passed, 8 skipped, 174 warnings` en `test_results_audit_batch_full_20260809.log`. Los issues #300, #306 y #307 permanecen abiertos para tracking y validación CI.

### 2026-08-10 — Lote de validación de importación bancaria (#350, #351, #353, #354, #355, #357)

Se analizaron los hallazgos upstream y se confirmaron como riesgos reales. El adaptador de extractos ahora valida que la cuenta bancaria pertenezca a la compañía del lote durante validación y persistencia; el servicio de importación valida fechas cuando el documento construido es una lista, evitando saltar períodos cerrados. Las fechas inválidas ya no se reemplazan silenciosamente por la fecha actual. Se rechazan montos no numéricos, filas sin depósito/retiro y filas con ambos lados monetarios; además, el panel de conciliación tolera transacciones históricas inválidas sin responder 500.

Verificación: batería focal `99 passed`; Black, Ruff, Flake8, Mypy y `git diff --check` pasan. Suite completa ejecutada una vez para el lote: `1620 passed, 8 skipped, 174 warnings` en `test_results_audit_bank_import_full_20260810.log`. Commit firmado: `0a00203 fix(bank): validate imported statement ownership`. Los issues permanecen abiertos para revisión posterior y CI.

### 2026-08-10 — Lote de estabilización de inventario (#359, #360, #361, #362, #363, #364, #365)

Se corrigieron controles de valoración y captura de movimientos. El promedio móvil consume la cantidad y valor actuales de `StockBin`, las capas normalizan su valor efectivo y las revalorizaciones sin cantidad distribuyen explícitamente su ajuste sobre las capas disponibles. Las recepciones y salidas convierten la tasa a UOM base; las conciliaciones bloquean el bin y recalculan el delta contra el stock vigente, evitando aplicar snapshots obsoletos. Las salidas de notas de entrega respetan `allow_negative_stock`, y los formularios rechazan UOM ausentes o conversiones inválidas en lugar de guardar cantidades crudas o provocar `IntegrityError`.

Commit de código firmado: `534c9de fix(inventory): stabilize valuation and stock entry controls`. Se detuvo deliberadamente la suite completa a solicitud del usuario en 52%; no se reporta como verde. El lote se publicará en la rama `stabilization/inventory-audit` para que CI encuentre regresiones. Los issues permanecen abiertos para tracking.

CI detectó una regresión de compatibilidad en el mensaje de rechazo de salidas sin stock. Se conservó la nueva ruta de stock negativo permitido, pero el caso no permitido vuelve a propagar el error contractual `No hay suficiente inventario`. Commit firmado: `53047c2 fix(inventory): preserve shortage rejection semantics`.

### 2026-08-10 — Lote O2C de reembolsos, FX y aplicaciones (#344, #345, #346, #347, #348, #349)

Se confirmaron y corrigieron seis riesgos upstream. Los reembolsos ahora conservan `party_type` y seleccionan AR/AP y anticipos del tercero correcto; las conciliaciones rechazan fechas anteriores a aplicaciones existentes; las notas de crédito no incrementan exposición ni bloqueo de vencidos; las devoluciones no generan notas de entrega de salida; `base_outstanding_amount` usa el tipo de cambio del documento; y la deduplicación de referencias es local a cada request.

Commit firmado: `c39ca7b fix(o2c): align refunds and payment allocation controls`. No se ejecutó pytest local por instrucción del usuario; se ejecutó Black, `compileall` y `git diff --check`. El lote queda para validación de CI. Los issues permanecen abiertos.

### 2026-08-10 — Lote S2P de matching, moneda y proveedor (#339, #340, #342, #343)

Se corrigieron cuatro hallazgos confirmados. La diferencia de precio del matching 2-way/3-way ahora se acumula como diferencia unitaria por cantidad de referencia; los detalles limitan `matched_qty` y `matched_amount` a lo realmente recibido/ordenado y conservan estado parcial. Los duplicados de órdenes y facturas de compra recalculan sus importes base con `exchange_rate`, y una recepción rechaza una orden cuyo proveedor no coincide.

Commit firmado: `0b8505e fix(s2p): enforce reconciliation quantities and supplier scope`. No se ejecutó pytest local; se ejecutó Black, `compileall` y `git diff --check`. El lote queda para CI y los issues permanecen abiertos.

### 2026-08-10 — Lote de controles de conciliación de inventario (#322, #323, #326, #329)

Se corrigió el propósito `stock_adjustment` para que pueda postearse, las conciliaciones deficitarias ahora conservan el valor objetivo en lugar de sustituirlo por el costo FIFO, las transferencias entre cuentas iguales validan el período contable antes del retorno temprano y los conteos en UOM no base se convierten a UOM base antes de calcular diferencias y valor objetivo.

Commit firmado: `4df8253 fix(inventory): honor reconciliation and period controls`. No se ejecutó pytest local; se ejecutó Black, `compileall` y `git diff --check`. Los issues permanecen abiertos para CI y verificación posterior.

CI reveló que el contrato de error de stock insuficiente también se aplicaba al camino de `DeliveryNote`. Se corrigió el segundo caller para propagar `No hay suficiente inventario` cuando `allow_negative_stock` es falso. Commit firmado: `7ade05a fix(inventory): preserve delivery shortage errors`.

CI detectó además que el caller de `StockEntry` requiere conservar su mensaje específico `no permite stock negativo`, mientras que mypy exigía estrechar la UOM base en conciliaciones. Ambos contratos quedaron corregidos. Commit firmado: `73a5a7a fix(inventory): preserve caller error contracts`.
## 2026-08-10 — Correcciones bancarias agrupadas

- Petición: continuar con bug fixes sin ejecutar la suite local ni saturar el workflow.
- Plan implementado: corregir el open redirect del parámetro `next` en Cash Forecast y preservar la cuenta bancaria origen del formulario de cobro simple en el posting GL de recepción. Se mantienen los issues abiertos para tracking.
- Verificación: Black, `compileall` y `git diff --check`; la suite pytest local no se ejecutó por instrucción del usuario.
