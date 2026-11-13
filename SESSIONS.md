# Contexto de sesiones y decisiones técnicas

Este documento es la fuente de verdad para las decisiones técnicas pasadas del proyecto. No es una bitácora de QA
ni una especificación vigente: los estados, nombres y números de issue son históricos. El código es la autoridad
para el estado actual; las reglas de negocio y desarrollo están en `AGENTS.md`; la bitácora de cada tarea vive en
su issue.

Historial completo, con hallazgos, verificaciones y QA por issue:

```sh
git show fbef114431e603a89599c3c3c3de7e1a1cf5143e:SESSIONS.md
```

## Contabilidad y ledgers

- **Append-only**: no se borran filas de evidencia (GL, stock, AR/AP, subledger) ni se reescriben sus cifras; la
  corrección se hace con contraasientos. Sí pueden cambiar el estado lógico y los saldos derivados
  (`outstanding_amount`, `unallocated_amount`, `status`, `is_cancelled`). La anulación es monotónica.
- **Multilibro**: los módulos operativos publican en todos los libros activos; solo Contabilidad elige libros. Un
  documento no se duplica por libro.
- **Multimoneda**: cada libro conserva su moneda funcional y conversión histórica; el importe base de la entidad no
  se reutiliza en otros libros. Si falta una tasa, se bloquea el registro completo.
- **AR/AP por documento**: el saldo del tercero es la suma de documentos no cerrados. Anular un pago devuelve el
  saldo de las facturas asociadas sin borrar el pago original ni su anulación.
- **Anulación vs reversión**: la anulación es del mismo período y fecha; la reversión es de otro período. Ambas se
  representan con contraasientos, nunca con borrado.
- **Cierre fiscal**: `is_closed` es la autoridad para bloquear movimientos y decidir elegibilidad; `enabled` solo
  controla consulta y reportes. Un período cerrado puede seguir disponible para lectura.
- **Aperturas de pago**: el GL de apertura se asocia solo cuando el pago no tiene `references`; con referencias, la
  apertura no apunta al GL.
- **Referencias documentales**: las notas de crédito/débito de compra resuelven `PurchaseInvoice`; las de venta,
  `SalesInvoice`. No se cruzan familias aunque compartan tabla física.

## Impuestos, precios y costos

- **Impuestos incluidos**: se descomponen agrupando las tasas porcentuales por definición de base (`base_mode`,
  conceptos incluidos y excluidos), no por secuencia. Los cargos fijos y manuales se reconocen íntegros y se
  excluyen de la base porcentual. La secuencia solo ordena el procesamiento.
- **Casos límite fiscales**: una línea con importe cero es información válida y no equivale a ausencia de líneas;
  `grand_total` solo respalda documentos sin líneas. El motor rechaza bases de prorrateo no positivas cuando hay
  cargos distintos de cero; los cargos de valor cero son válidos.
- **Retenciones**: no pueden exceder la obligación liquidada; pueden reducir el efectivo a cero. Un pago con
  efectivo cero solo se admite con referencias aplicadas y cobertura por descuento, diferencia cambiaria o
  retención. La configuración del proveedor es la autoridad para sus retenciones; una regla ordinaria no se
  interpreta como retención.
- **Aplicación de pagos**: descuento más diferencia cambiaria no pueden consumir toda la asignación; debe quedar una
  porción de efectivo conciliable. Un documento extranjero exige tasa positiva antes de aplicar la referencia.
- **Transferencias internas**: la conversión cross-currency usa la tasa del sistema, no la tasa por defecto de la UI.
- **Landed cost**: el prorrateo exige base positiva por método; no se elige una línea arbitraria ni se aplica un
  método alternativo implícito.
- **Pronóstico de caja**: usa el saldo canónico (`compute_outstanding_amount`), no las columnas cacheadas. El
  respaldo por saldo persistido se limita a objetos no ORM o a la ausencia explícita de la tabla de relaciones.
- **Analítica**: la participación se calcula como importe dividido entre total, conservando el signo contable; un
  total cero se presenta como 0 %.

## Inventario y valoración

- **Kardex inmutable**: solo `is_cancelled` puede mutar; el borrado físico y la reescritura de cifras están
  bloqueados. La anulación es recíproca, del mismo período habilitado y abierto, y crea contrapartidas append-only;
  no existe reversión de inventario en otro período.
- **Valoración por compañía**: el método (`moving_average`/`fifo`) no depende de la bodega y no puede cambiarse si la
  compañía ya tiene operación de inventario.
- **Devoluciones FIFO**: consumen capas fijadas a la recepción origen y crean una capa de salida con costo
  histórico. Si no hay capa o cantidad suficiente, el posting se bloquea; no se permiten capas de retorno con costo
  derivado de la tasa de la devolución ni saldo FIFO negativo.
- **Transferencias**: origen y destino deben ser bodegas distintas; el rechazo ocurre antes de consumir capas FIFO.
- **UOM, lotes y seriales**: la UOM base y los flags de control (lote/serie/vencimiento) quedan bloqueados tras el
  primer movimiento. Las salidas validan obligatoriedad, disponibilidad y vencimiento a la fecha de posteo.
- **Roles**: compras y ventas no reciben ni despachan inventario; solo el usuario de almacén opera recepciones y
  entregas. Compras y ventas conservan la vista de consulta.
- **Devoluciones de compra**: la devolución física no es un documento AP. No cancela el matching de la factura ni
  reduce por sí sola el saldo del proveedor; una nota de crédito explícita es la que reduce `outstanding_amount`.
- **Líneas de borrador**: se versionan con `is_superseded` en lugar de borrarse; los lectores usan solo la versión
  vigente y los eventos de aprobación son idempotentes por documento y ciclo.
- **Reconciliación de stock**: un ajuste mixto (cantidad positiva, valor negativo) se rechaza antes de mutar la
  línea, el bin o las capas, porque puede producir tasa unitaria negativa y separar GL de kardex.

## Caja chica y tesorería

- **Documentos append-only**: conciliaciones y reposiciones conservan saldos derivados del GL; el ajuste contable de
  una conciliación requiere acción explícita y cuenta de diferencia.
- **Reposición**: sigue borrador → solicitado → aprobado → reembolsado y crea una Nota de Débito bancaria (débito
  Caja Chica, crédito Banco). Se bloquea si la moneda del fondo y la del banco no coinciden.
- **Idempotencia**: un gasto se reserva a lo más una reposición, una reposición genera a lo más una nota de débito y
  una conciliación un solo ajuste. Se resuelve con lock y transición condicional, no con claves idempotentes.

## Concurrencia e idempotencia

- **Patrón**: lock de fila (`SELECT ... FOR UPDATE`) más transición condicional, reutilizando
  `_lock_document_for_transition`. Se descartaron columnas `idempotency_key` y restricciones unique parciales; la
  decisión sigue abierta en #1653.
- **SQLAlchemy**: `FOR UPDATE` no refresca una instancia ya cargada en el identity map; se requiere
  `populate_existing` antes de reevaluar la guardia. Sin él se duplican efectos concurrentes.
- **SQLite**: ignora `FOR UPDATE`; en Desktop la protección es un solo usuario más guards de servicio.
- **Flujos cubiertos**: submit/cancel, pagos AR/AP, conciliación bancaria, subledgers, caja chica y revaluación
  cambiaria.
- **Revaluación**: `run` bloquea la fila del período (empresa + período) antes de leer corridas previas; `void` usa
  transición condicional y la reversión automática salta corridas ya anuladas.
- **Pendientes**: liquidación de vales, reserva de caja chica por defecto, aplicaciones AR/AP y
  cierres/presupuestos/configuración.

## Auditoría y controles internos (Cloud)

- **Inmutabilidad de evidencia**: los guards impiden mutar `audit_trail`, `approval_action`, `audit_log`, el ledger
  y los datos financieros posteados; solo se admite estado derivado.
- **Cuatro ojos**: el aprobador debe ser distinto de todos los preparadores, estar activo y autorizado, y tener
  rango al menos igual al máximo de los preparadores. `approve` es la autoridad de aprobación; `approval_rank` es la
  jerarquía de independencia. Un admin solo puede ser aprobado por otro admin distinto. Sin autoaprobación ni
  preparadores/aprobadores sin clasificar; el bypass silencioso se rechaza (fail-closed).
- **Reglas de aprobación deterministas**: se ordenan por `approval_level DESC`, `min_amount DESC`, `id`; la
  selección prefiere mayor nivel, luego el rango más específico y finalmente `id`, independiente del orden de la
  base.
- **Configuración de matching**: `PurchaseMatchingConfig`/`SalesMatchingConfig` se actualizan solo por su servicio.
  Los cambios que debilitan controles se enrutan a revisión `config_change`; la conciliación previa conserva su
  snapshot histórico.
- **Cadena de auditoría**: SHA-256 sobre el contenido canónico de la fila (incluye timestamp UTC; v2 incluye `id`),
  encadenada en `before_flush`, idempotente ante rollback y verificable con `cacaoctl audit-verify`. Las filas
  legacy sin hash se excluyen como cola heredada.
- **Límites de la cadena**: un DBA con UPDATE directo puede rearmarla; la defensa real son los GRANT/REVOKE de
  despliegue. Escritores concurrentes en PostgreSQL requieren serialización/advisory lock; el patrón asume READ
  COMMITTED. Solo cubre `audit_trail`; `approval_action` y `audit_log` dependen de la inmutabilidad runtime.
- **`cacao_config`**: los UPDATE/DELETE Core directos están bloqueados; los prefijos sensibles se centralizan en una
  sola lista. El flush ORM queda exento.
- **Desktop**: las revisiones y los controles Cloud no aplican; el comportamiento es síncrono y sin flujo de
  aprobación.

## Acceso multiempresa y caché

- **Dos capas**: el rol define qué puede hacer un usuario; `UserCompanyAccess` define en qué compañías. Ambas se
  exigen antes de operar. Los libros contables ya no autorizan usuarios; el posting resuelve todos los libros
  activos de la compañía.
- **Aislamiento**: un usuario no debe conocer compañías que no tiene asignadas. Los administradores conservan acceso
  global. Los usuarios sin grant no reciben resultados que revelen compañías ajenas.
- **search-select**: cuando la solicitud no declara compañía, el backend aplica el conjunto de compañías
  autorizadas. Los artículos son globales; los terceros se restringen por `CompanyParty` activo y se deduplican con
  `DISTINCT`.
- **Jerarquías**: las APIs exigen permiso `accounting/consultar` sobre la entidad y rechazan árboles con vínculos
  padre/hijo entre compañías.
- **#1705 — Unit/Project**: cada padre y todos sus descendientes deben permanecer en la misma compañía. La validación
  también se ejecuta al quitar el padre propuesto para impedir que cambiar la compañía del nodo fracture el árbol;
  los selectores muestran solo padres de compañías autorizadas y, si se eligió una, de esa misma compañía.
- **Caché**: Redis es opcional y requiere `CACHE_REDIS_URL` explícita; Desktop no depende de caché. La llave incluye
  usuario y alcance de compañías, se reevalúa en cada solicitud y se invalida después del commit. TTL de datos
  maestros: 300 s. El rate limit usa `RATELIMIT_STORAGE_URI` y no hereda la URL de caché.

## Reportes y datos

- **EFE NIC 7**: configuración explícita obligatoria; el reporte se bloquea mientras existan cuentas con movimiento
  sin clasificar. La sugerencia por `account_type` es solo visual. Solo honra compañía/libro/período y excluye
  anulados, reversas y cierres fiscales.
- **Períodos**: el backend no confía en fechas del navegador. `as_of_date`, `date_from` y `date_to` deben coincidir
  con el período resuelto; se prefiere id sobre nombre para desambiguar períodos homónimos. `default_when_missing`
  es una bandera opcional para listados operativos.
- **Clasificación contable**: el aviso de cuenta desconocida se emite solo para valores vacíos o desconocidos; las
  cuentas de balance válidas no se marcan como desconocidas.
- **SQLAlchemy**: se aplica `selectinload` solo donde se midió un N+1; las importaciones usan un savepoint por fila
  para conservar las válidas; no se crean índices sin EXPLAIN y validación multi-motor.

## Internacionalización e impresión

- **i18n**: toda cadena visible se marca para traducción; español como base e inglés en `messages.po`. La guarda AST
  detecta f-strings incompatibles, incluidas variantes con contexto y pluralización.
- **Impresión**: en Desktop se oculta la exportación PDF porque WeasyPrint no está disponible; la vista
  previa/impresión se conserva.

## Entorno y calidad

- **Desktop** es la base operativa: una empresa, un usuario y SQLite. No asume Redis ni WeasyPrint. **Cloud** añade
  multiusuario, multiempresa y servicios opcionales; el sistema no debe fallar por falta de caché.
- **Esquema**: las bases de desarrollo se consideran descartables. Los cambios recientes usan `create_all` o
  suplencia idempotente; cuando existe migración incremental (p. ej. hash v2), es idempotente.
- **SQLite/FK (#1630)**: antes de Alpha no hay instalaciones que preservar; las bases locales previas a activar
  `PRAGMA foreign_keys` se consideran descartables y deben recrearse si contienen referencias inválidas. No se
  migran ni reparan automáticamente bases antiguas en este ciclo.
- **Calidad**: black a 127 caracteres, ruff, flake8, mypy, pydocstyle, complexipy ≤ 20 en código nuevo y pytest. El
  runner descubre `test_*.py` de forma recursiva; los utilitarios no son tests.
- **mypy con PYTHONPATH inyectado**: puede requerir `env -u PYTHONPATH` para evitar un `pathspec` externo que
  sombrea el del `.venv`.

## Contexto de issues (caché local)

- **Fuente de contexto**: el trabajo de estabilización usa una caché local de issues en `.local/github/issues.db`
  (SQLite) en lugar de consultas en vivo a la API de GitHub. Se evita así el rate limit de GitHub y se trabaja sobre
  un conjunto congelado de issues, de modo que el análisis y los commits son reproducibles aunque el tablero cambie.
- **Contenido de la instantánea** (2026-11-09): 1.245 issues abiertos, 4.055 comentarios, 2.740 vínculos
  issue-etiqueta, 29 etiquetas, 578 sub-issues y 59 umbrellas `root` repartidos en 8 fases. Incluye búsqueda FTS5
  insensible a acentos y las vistas `v_issues`, `v_phases` y `v_umbrellas`.
- **Sincronización**: `python scripts/sync_github_issues.py` (stdlib + `gh`). La caché es una foto, no una fuente
  autoritativa: antes de citar un issue se confirma contra el código. `.local/` está fuera de Git.
- **Límites**: la caché no sustituye la verificación en el repositorio ni las pruebas; solo aporta el enunciado y la
  discusión histórica de cada issue.

## Decisiones abiertas

- **#1653**: unique parcial con clave de idempotencia frente a lock más transición condicional. Se eligió el lock;
  la alternativa queda needs-review. Faltan los flujos hijos enumerados arriba.
- **Cadena de auditoría**: concurrencia real en PostgreSQL, escenarios REPEATABLE READ, paginación de la verificación
  y cobertura de `approval_action`/`audit_log`.
- **Cuatro ojos**: excepciones explícitas por módulo y compañía (con motivo, autorizador y vigencia) si el negocio
  las requiere; hoy no hay bypass.
- **Despliegue ICFR**: las bases ya desplegadas no reciben por migración las columnas de rank/snapshot; requieren
  recreación o clasificación manual.

## Notas de mantenimiento

- El procedimiento `AUDIT_MATRIX.csv` / `AUDIT_PROMT.md` fue retirado; su contenido histórico queda en Git y no debe
  citarse como vigente.
- Los números de issue y los nombres de funciones citados son referencias históricas; verificar el código antes de
  asumir que la decisión sigue implementada igual.

## Referencias

- `AGENTS.md`: reglas de negocio y desarrollo vigentes.
- `docs/cloud/internal-controls.md`: controles internos, despliegue y GRANT/REVOKE.
- `docs/tax-cost-engines/`: motor fiscal, retenciones, landed cost y auditoría.
- `docs/redis_data_cache.md`: contrato de caché.
- `docs/precision_contract.md`: contrato de precisión decimal.
