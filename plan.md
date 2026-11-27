# Plan accionable de estabilización

**Repositorio:** [cacao-accounting/cacao-accounting](https://github.com/cacao-accounting/cacao-accounting)

**Tracker maestro:** [#2248](https://github.com/cacao-accounting/cacao-accounting/issues/2248)

**Rama de trabajo:** `estabilizacion`, con seguimiento de la rama remota `origin/estabilizacion`.

**Corte de estado:** 26 de noviembre de 2026. Consulta completa del API de GitHub (sin PR): 2.075 issues; 597 abiertos y 1.478 cerrados. Entre los abiertos, 507 `needs-work`, 14 `fix-proposed`, 11 `fix-confirmed`, 14 `needs-review` y 51 `sin-flujo`. El plan referencia 556 issues abiertos únicos y ningún issue cerrado; los 41 abiertos restantes no se incorporan porque esta lista es una cola curada, no un inventario completo. El corte anterior contabilizaba PR dentro del total; este los excluye. Las tablas indican el estado real del issue (open/closed) y su etiqueta de flujo observada al corte. Los issues con etiqueta `fixed` aparecen cerrados en este corte.

**Estado de commits (25 de noviembre de 2026):** al consultar GitHub, `HEAD` y `origin/estabilizacion` apuntaban al mismo commit, `167a357d`, sin commits locales por delante. El commit que registró el corte anterior se añadió sobre esa base; desde entonces `HEAD` local avanzó con trabajo propio y paralelo. Los hashes citados en las tablas deben verificarse contra la rama antes de considerarlos integrados.

## Alcance de ejecución

- El plan contiene la cola de issues abiertos con trabajo accionable. Los issues cerrados, trackers y agrupadores se usan como referencias de coordinación; no se asignan como tareas de implementación.
- El triage del 2026-11-20 verificó los issues que llegaron a `fixed`: 151 se cerraron como completados y 6 volvieron a `needs-work`. Los cerrados salen de la cola; solo se reabren si aparece una regresión documentada con evidencia.
- El producto está en **pre-alpha**: cualquier soporte legacy es carga. No se conservan esquemas, datos, parámetros ni rutas de versiones anteriores; se retiran en cuanto se identifica su consumidor, sin migraciones de datos antiguos ni shims de compatibilidad. Esto no afecta a los invariantes del core —evidencia append-only, anulaciones, reversiones y cortes históricos—, que siguen siendo obligatorios.
- `needs-work` significa implementación pendiente; `fix-proposed` significa que QA1 aprobó y falta la revisión independiente de QA2; `fix-confirmed` significa que QA2 aprobó y falta la aceptación final de QA3 expresamente autorizado o del administrador. Si una revisión encuentra una brecha, el issue vuelve a `needs-work` y reinicia el ciclo QA1 → QA2.
- Antes de intervenir y de entregar un lote, leer `feedback.md` y `review.md` si existen. Resolver las observaciones aplicables de QA1 y QA2 como parte del criterio de salida.
- Antes de atender un issue, leer su descripción y **todos sus comentarios**, con paginación completa, incluidos los del paraguas cuando establezcan el contrato compartido. Los comentarios son la bitácora de desarrollo: contienen decisiones, reproducciones, cambios existentes, rechazos de QA y limitaciones que pueden actualizar o sustituir el diagnóstico inicial. A estas alturas aportan más contexto de ejecución que la descripción original. Identificar las decisiones vigentes y los hallazgos aún aplicables antes de tocar código; no volver a decidir reglas ya aprobadas ni implementar a partir del título o de la descripción aislados. Si hay una contradicción real sin resolución posterior, presentar el caso concreto al responsable.

## Core funcional esperado

El core implementa los procesos empresariales estándar O2C, S2P, R2R, I2F y CTM de punta a punta, con comportamiento robusto, predecible, comprensible y auditable. Se espera que ventas y compras conserven sus documentos y relaciones de origen, que cobros y pagos apliquen y restituyan saldos por documento correctamente, que inventario mantenga cantidades y valoración por artículo, bodega y UOM —incluidos lote y serie cuando correspondan—, y que caja, bancos y conciliaciones reflejen los mismos hechos económicos que GL. El ledger financiero es la fuente única de verdad; AR/AP e inventario son extensiones reconciliables con él. Toda operación debe conservar atomicidad, evidencia append-only, cancelación monotónica, balance por libro y conversión explícita a la moneda de cada libro activo, bloqueando el registro cuando falte una tasa. Las anulaciones neutralizan el registro en su misma fecha y período; las reversiones conservan el efecto histórico y registran su corrección en otro período. R2R debe reportar esas operaciones con cortes y saldos reproducibles. Se aplican los procesos estándar de la industria y las decisiones documentadas del proyecto: no se reinventa su semántica ni se toman decisiones de negocio por iniciativa del implementador. Desktop, con SQLite y sin Redis, debe completar estos recorridos; Cloud agrega aislamiento multiempresa, roles y las capacidades adicionales definidas. Se conserva el monolito modular y el alcance contable; manufactura, nómina y activos fijos quedan fuera del core de este proyecto.

## Convención de lotes

Cada lote por agrupador corresponde a un cambio pequeño solo si sus hijos comparten consumidor y contrato. Si aparecen cambios independientes, dividir el lote en varios commits y dejar la lista exacta de issues cubierta por cada commit. Las referencias a un paraguas organizan el trabajo: no sustituyen el criterio de aceptación individual de sus hijos.

Antes de iniciar cada lote, leer todos los comentarios de sus issues, comprobar que continúen abiertos y que el comportamiento descrito siga presente en el código. Para cada fix, escribir o ampliar las pruebas funcionales y negativas mínimas necesarias, ejecutar los linters previos al commit y validar los motores afectados según la cadencia siguiente. Mantener el cambio por consumidor; usar `Refs: #n` en commits y no cerrar issues como consecuencia automática de un commit.

## Ritmo de desarrollo y controles

La prioridad operativa es avanzar rápido con fixes pequeños y verificables. **No es necesario ejecutar toda la suite para cada commit.** Seleccionar la menor cantidad de pruebas que demuestre el comportamiento corregido, los fallos realistas y las invariantes afectadas: empezar por casos o archivos concretos y agregar consumidores relacionados solo si el cambio o un fallo lo justifican. Conservar pruebas sustanciales y la cobertura exigida por AGENTS.md; evitar pruebas redundantes y repeticiones de controles ya aprobados sobre código que no cambió. Ejecutar desde `.venv` o `venv`; usar `pytest -n auto` cuando la selección tenga suficiente trabajo para aprovechar el paralelismo.

- **Antes de cada commit de código:** ejecutar las pruebas dirigidas del cambio y los linters exigidos por AGENTS.md, incluidos black, ruff, flake8, mypy, pylint y pydocstyle; comprobar complexipy en los archivos productivos editados. Aplicar los controles de seguridad, JavaScript e i18n pertinentes al cambio. Si el commit solo modifica Markdown, verificar el documento y su diff; no ejecutar tests ni linters de Python por ese cambio documental.
- **Cada 50 commits locales acumulados desde la última ronda completa satisfactoria:** detener la acumulación y ejecutar todos los controles de integración definidos en `.github/workflows/ci.yml` y los workflows que invoca. El umbral cuenta commits, no issues: un issue puede requerir varios commits y un fix puede cubrir varios issues. Registrar en la bitácora del issue o tracker el SHA validado y los resultados; contar desde ese SHA con `git rev-list --count <SHA-validado>..HEAD`. Reiniciar el contador únicamente cuando la ronda completa termine satisfactoriamente. Los commits de corrección también cuentan.
- **Pylint en cada ronda completa:** revisar todos los mensajes de error (`E`) y fatales (`F`), priorizando `E0602`, `E0601`, `E0606`, `E1101`, `E1102`, `E1120`, `E1121`, `E1123`, `E1131`, `E1136`, `E1111`, `E0401`, `E0611`, `E0702` y `E4702`; comparar con la línea base también `W0101`, `W0406`, `W0612` y `W1404`, corregir los defectos reales y documentar los falsos positivos, incluidos los de inferencia de ORM y frameworks.
- **Ronda completa:** reproducir la matriz vigente de `.github/workflows/python.yml`, `.github/workflows/lint.yml` y `.github/workflows/databases.yml`: suite Cloud en Python 3.12, 3.13 y 3.14, suite Desktop en Python 3.13, traducciones compiladas, cobertura, linters y Bandit, pruebas JavaScript, pruebas de base de datos SQLite/MySQL/PostgreSQL —PostgreSQL con psycopg2 y pg8000— y aislamiento de caché. Usar los comandos, variables, dependencias y preparación de bases indicados en esos workflows; ejecutarlos en entornos de prueba aislados. Los workflows son la fuente de la matriz vigente y no se modifican para eludir fallos.
- **Antes de un push autorizado a `origin/estabilizacion`:** exigir una ronda completa satisfactoria sobre el HEAD exacto que se enviará, aunque todavía no se hayan acumulado 50 commits. Reutilizar la ronda anterior si validó ese mismo SHA; si cambió el código, completar la validación del nuevo HEAD. Resolver las regresiones antes del push y revisar después el CI del PR asociado a `estabilizacion`: la configuración vigente de `ci.yml` ejecuta CI en los PR y en pushes a `main`/`development`, por lo que el push a `estabilizacion` por sí solo no garantiza un run. El objetivo de la ronda local es llegar al CI de GitHub en verde; confirmar el resultado remoto antes de considerar validada la integración.

SQLite y PostgreSQL son Tier 1: sus errores son bloqueantes. MySQL es Tier 2 y **también se prueba** en la ronda completa, además de las pruebas dirigidas cuando el fix afecta su compatibilidad; sus fallos se registran y corrigen según su impacto, sin convertirlo en un requisito de lanzamiento Tier 1. Si falta un motor, versión de Python o herramienta para reproducir la matriz, registrar el control pendiente y habilitar el entorno necesario; no declarar la ronda completa en verde con comprobaciones omitidas.

## Orden de ejecución

Avanzar por las fases y dependencias siguientes, por flujo consumidor. #1658 se divide entre esos flujos; nunca se implementa como un cambio combinado. No se espera al cierre de una fase completa cuando el lote tenga sus propios prerrequisitos satisfechos.

Para elegir el siguiente lote, aplicar en orden: dependencia explícita del issue y sus comentarios; contrato productor de la tabla siguiente; riesgo confirmado de exposición entre compañías, pérdida de evidencia, atomicidad o desbalance; resto del flujo consumidor. Si varios issues describen el mismo defecto, usar la reproducción y el consumidor compartidos para un solo fix y validar por separado el criterio de cada issue. El número de issue no establece prioridad.

| Fase consumidora | Entrada exigida para el lote | Salida verificable antes de continuar un consumidor dependiente |
|---|---|---|
| 1 — Acceso | Actor, acción y alcance aprobados para la ruta afectada. | Matriz de acceso permitido/denegado por compañía, IDs ajenos y rutas alternativas; revocación efectiva cuando aplique. |
| 2 — Persistencia | Alcance de Fase 1 definido si la operación es multiempresa; identificar todos los escritores y el límite de transacción. | Commit/rollback completos, repetición y carrera realista sin evidencia duplicada, reactivada o perdida; semántica comprobada en SQLite y PostgreSQL. |
| 3 — Entrada | Guards de acceso de Fase 1 y unidad transaccional de Fase 2 disponibles para ese escritor. | La ruta y el servicio rechazan entradas inválidas sin mutación parcial; los formatos de importación conservan el mismo contrato. |
| 4 — Contabilidad | Acceso, persistencia y validación del escritor resueltos; identificar libro, moneda, período y estado documental. | GL balanceado por libro, tasa obligatoria, corte y anulación/reversión conforme a los contratos; fallo atómico si falta configuración. |
| 5 — Operación | Contratos de Fases 2–4 que use el recorrido satisfechos. | Recorrido origen → posteo → aplicación/movimiento → corrección; AR/AP e inventario reconciliables con GL por sus dimensiones pertinentes. |
| 6 — Reportes/UI | Fuente, corte y contrato de servidor estabilizados para ese consumidor. Seguridad y pantallas que bloquean el recorrido pueden adelantarse. | Reporte reconciliado, permisos y errores visibles correctos, filtros persistentes, precisión e i18n; solicitudes async obsoletas sin efecto. |

Cada entrega de implementación sigue este flujo: leer issue y todos sus comentarios → identificar consumidor y criterio propio → agregar regresión representativa → fix mínimo → pruebas dirigidas y linters previos al commit → commit acotado con `Refs: #n` y sign-off → QA1 → QA2. Aplicar la ronda completa cada 50 commits y antes del push según la cadencia definida arriba. QA1 y QA2 son revisiones estáticas independientes; si rechazan, corregir y reiniciar el ciclo. Registrar evidencia y decisiones en GitHub. El trabajo del lote termina en `fix-confirmed`; QA3 autorizado o el administrador decide `fixed` y cierre, o retorno a `needs-work`.

## Secuencia por fases y agrupadores

### Prioridad de ejecución

1. Atender primero los contratos que protegen integridad contable: transacciones, evidencia append-only, balanceo por libro, moneda/tasa, períodos y estados de anulación/reversión. Los prerrequisitos mínimos de acceso y persistencia se corrigen antes o en paralelo; no es necesario esperar el cierre de fases completas.
2. Sobre esos contratos, completar los recorridos verticales O2C/S2P/I2F/CTM y conciliar sus extensiones con GL.
3. Simplificar flujos redundantes y retirar código residual al lado de sus consumidores; no dejar esa deuda para el final si bloquea o confunde los recorridos.
4. Integrar únicamente funciones explícitas en los issues y justificadas por las decisiones documentadas. No introducir funcionalidades adicionales por iniciativa del lote. Diferir solo con motivo, impacto y limitación aceptada.


### Primer lote listo para implementación

- Después, continuar con los lotes de las fases 1 y 2 que protegen autorización, aislamiento, atomicidad e integridad de evidencia. Avanzar por consumidor y dependencias concretas; no esperar a cerrar una fase completa.

### Ruta de ejecución de features de #1658

- **#1658 ya no es una puerta de decisión:** ejecutar sus hijos en cambios pequeños por consumidor. Integrar las funciones aprobadas, retirar código/rutas residuales tras verificar consumidores y diferir solo con motivo, impacto y limitación documentados.
- **Integrar o completar:** #1118, #1752, #1813, #1888, #1930, #1938.
- Estos hijos se ejecutan en los lotes consumidores de fases 1–6; esta lista es un índice de ruta, no un commit combinado. Para cada retiro conservar evidencia breve de búsqueda de consumidores y pruebas de que el flujo restante funciona.

#### Sub-lotes ejecutables del agrupador #1658

| Sub-lote | Issues | Trabajo para un fix acotado |
|---|---|---|
| 1658-B · O2C/R2R | #1118 ❌ QA1/QA2 rechazan; #1813 ❌ QA1/QA2 rechazan localmente | Corregir exclusión de transferencias sin postear, requisito de entrega para 3-way, exportación PDF del mayor y consumo de origen desde orden; separar commits por consumidor si no comparten servicio. |
| 1658-C · Inventario | #1888 | Aplicar conversiones UOM, moneda requerida de conciliación, persistencia de detalle y contrato de ajustes solo positivos/negativos. |
| 1658-D · Costos de compra | #1752 | Completar edición/prorrateo de landed cost y enlace a detalle; separar el enlace de interfaz si es independiente del cálculo. |
| 1658-E · Portal y vistas de administración | #1930, #1938 | Completar paginación, revocar portal inactivo, renderizar administración, aplicar tamaño/orientación PDF, habilitar historial y vistas guardadas con RBAC. Dividir por consumidor; no combinar cambios de portal, PDF y reportes en un commit. |

### Fase 1 — Acceso, aislamiento y seguridad

- **Lote 1 — Origen y autorización de documentos — #1649:** (hijos cerrados en GitHub).
- **Lote 2 — Permisos, acceso y reportes — #1649:** #1725 ✅ QA1/QA2 aprueban localmente; #1777 ❌ QA1/QA2 rechazan exposición residual de contactos globales.
- **Lote 3 — Listados y rutas adyacentes — #1649:** #1841.
- **Objetivo compartido:** aplicar el mismo alcance de compañía a rutas de lectura/escritura, IDs fuente y payloads; cubrir actor, acción, compañía propia/ajena y rutas alternativas.
- **Lote #1710 — [ROOT CAUSE][AUTH] Ciclo de vida de credenciales y mensajería: revocación, fail-safe e idempotencia:** #1732, #1958.
- **Lote #2209 — Consolidación causa-raíz: Sanitización/validación de salidas y recursos (XSS, SSRF, redirect):** #2131.
- **Lote #2231 — Consolidación causa-raíz: Invariante de operabilidad mínima (último admin/única entidad activa):** #1767, #1771.

### Fase 2 — Persistencia y garantías transversales

- **Lotes por consumidor — #1653 (Consolidación causa-raíz: atomicidad/idempotencia en read-then-post):**
  - Concurrencia en inventario/documentos: #332, #1820, #1857, #1868, #1881, #1957.
  - Concurrencia financiera/bancaria: #1776 ❌ QA1/QA2 rechazan recuperación/idempotencia; #1784 ❌ QA1/QA2 rechazan atomicidad y retry; #2129 ❌ QA1/QA2 rechazan casos legacy de idempotencia/default.
  - Concurrencia auth/base/aprobaciones: #1680 ❌ QA1/QA2 rechazan falta de expected-version en formularios; #1910 ❌ QA1/QA2 rechazan harness de concurrencia ausente.
  - Contrato de importación/UI: #1678.
  - **Dependencia:** fijar atomicidad/idempotencia por motor; no asumir que locks equivalen en SQLite y PostgreSQL. Cada fix cubre commit/rollback, repetición y carrera realista.
- **Lote #1706 — [ROOT CAUSE][TRANSVERSAL] Extender garantías append-only e inmutabilidad a toda la evidencia:** #1751, #1865, #1877, #1987.
- **Lote #2208 — Consolidación causa-raíz: Contrato de evidencia de auditoría: escritura atómica, cobertura de campos y actor:** #1794 ❌ QA1/QA2 rechazan cobertura de rollback.
- **Lote #2210 — Consolidación causa-raíz: Integridad referencial: FK desactivada y guards de uso/eliminación no replicados:** no se cambia la etiqueta.
- **Lote #2219 — Consolidación causa-raíz: Contrato de driver/base Tier-1 (portabilidad SQLite↔PostgreSQL y deploy):** #1851.
- **Lote #2220 — Consolidación causa-raíz: Idempotencia y guards de entorno en seed/bootstrap:** #1848.
- **Lote #2232 — Consolidación causa-raíz: Verificación de idempotencia por clave (mutable o sin comparar contenido):** #1815, #1836.
- **Lote #2234 — Consolidación causa-raíz: Contrato de migraciones de esquema sobre bases con datos:** #1849, #1898.

### Fase 3 — Entradas, maestros y contratos de API

- **Lote #1650 — Consolidación causa-raíz: coerción de Decimals en la frontera de entrada:** #1831, #1864, #2132.
- **Lote #1652 — Consolidación causa-raíz: contrato de lectura tabular en imports:** (hijos cerrados en GitHub).
- **Lote #1716 — [ROOT CAUSE][TRANSVERSAL] Guard de vigencia: is_active verificado al usar, no solo al crear:** #1823, #1839, #1927.
- **Lotes por dominio — #1717 ([ROOT CAUSE][VALIDACIÓN] Validación server-side de dominio en escrituras (formularios CRUD y enums)):**
  - Ventas/compras/documentos: #1760, #1947.
  - Maestros/admin/API: #1347, #1766, #1768, #1769.
  - Contabilidad/bancos/tesorería: #1083, #1088, #1742, #1922.
  - Inventario/UOM/cuentas: #1764, #1826, #1829.
  - **Salida:** rechazo consistente en ruta y servicio; pruebas con referencias inexistentes/ajenas, enums, estados y valores límite. No inferir reglas que el issue no define.
- **Lote #1718 — [ROOT CAUSE][IMPORTS] Paridad de validación y ciclo de vida de lotes de importación:** #1476, #1528, #1537.
- **Lote #2205 — Consolidación causa-raíz: Canonización de sentinelas de entrada (booleanos, 0/NULL, texto vacío):** #1483, #1555.
- **Lote #2211 — Consolidación causa-raíz: Edición con reconstrucción de payload que descarta campos:** #1818, #1822.
- **Lote #2213 — Consolidación causa-raíz: Contratos de unicidad de negocio (scope, dimensiones, defaults):** #1340, #1681, #1687.
- **Lote #2214 — Consolidación causa-raíz: Parseo de líneas por índices contiguos descarta filas posteriores:** #1871.
- **Lote #2217 — Consolidación causa-raíz: Resolución canónica de fechas/hora en UTC:** #1390, #1514.
- **Lote #2221 — Consolidación causa-raíz: Validación de dominio en parámetros de lectura:** #1969.
- **Lote #2226 — Consolidación causa-raíz: Mutación de configuración sin validar estados in-flight:** #1498.
- **Lote #2235 — Consolidación causa-raíz: Hidratación de cabecera en formularios con campos bloqueados:** #1874.

### Fase 4 — Invariantes contables y ciclo documental

- **Lote #1654 — Consolidación causa-raíz: lecturas de saldo sin filtro de libro (multilibro):** (hijos cerrados en GitHub).
- **Lote #1655 — Consolidación causa-raíz: resolver único de moneda y tasa histórica:** #1873, #1879, #1886, #1942.
- **Lote #1656 — Consolidación causa-raíz: invariantes del ciclo fiscal (año/período/cierre):** #1954, #1955.
- **Lote #1707 — [ROOT CAUSE][FISCAL] Contrato canónico del motor fiscal: una sola base para preview, persistencia y posteo:** #1757, #1911, #2058.
- **Lote #1708 — [ROOT CAUSE][TRANSVERSAL] Unificar máquina de estados documental: aprobaciones, anulaciones y transiciones:** #444, #1423, #1539, #1592, #1749, #1799, #1804, #1807, #1809, #1812, #1897.
- **Lote #1709 — [ROOT CAUSE][R2R] Contrato de cortes históricos: fecha efectiva as-of, reversas y saldo de apertura:** #1132, #1134, #1774, #1830, #2120.
- **Lote #2223 — Consolidación causa-raíz: Posteo sin guard de evidencia mínima (conjunto vacío o config faltante):** #1105.
- **Lote #2233 — Consolidación causa-raíz: Paridad de validación entre caminos paralelos de cálculo/posteo:** #1824, #1892.

### Fase 5 — Subledgers y flujos operativos

- **Lote #1651 — Consolidación causa-raíz: canonización de UOM y cantidad base entre flujos:** #841, #1810, #1847.
- **Lote #1657 — Consolidación causa-raíz: saldos derivados desincronizados en transiciones de documento:** #1264, #1559, #1728, #1770, #1872.
- **Lote #1713 — [ROOT CAUSE][TRANSVERSAL] Identidad de línea: DocumentRelation y consumo pendiente como única fuente de matching:** #1522, #1550, #1754, #1802, #1893, #1894, #1895.
- **Lote #1714 — [ROOT CAUSE][AR/AP] Contrato canónico de open items: subtipo, línea, dirección y corte:** #999, #1069, #1126, #1227.
- **Lote #1715 — [ROOT CAUSE][INVENTARIO] Contrato de valoración: rebuild no destructivo, costos capitalizados y capas en fecha:** #1726, #1727, #1759, #1858.
- **Lote #1719 — [ROOT CAUSE][DOCUMENT FLOW] Contrato del árbol documental: tipos de nodo, límites, búsqueda y cierre:** #1578, #1860.
- **Lote #2206 — Consolidación causa-raíz: Contrato de autoconciliación bancaria (reglas, filtros y ejecución):** #1080, #1081, #1470, #1504, #1508, #1509.
- **Lote #2215 — Consolidación causa-raíz: Contrato de alertas de reposición (umbral, predicado y faltante):** #1128, #1349, #1587.
- **Lote #2218 — Consolidación causa-raíz: Semántica de duplicación/copia de documentos:** #1618, #1798, #1821.
- **Lote #2224 — Consolidación causa-raíz: Método de observación de rotación de inventario:** #1129, #1246.
- **Lote #2225 — Consolidación causa-raíz: Vinculación física de crédito/devoluciones y facturas:** #1138, #1220.
- **Lote #2227 — Consolidación causa-raíz: Contrato de relaciones N:M documentadas (estado por vínculo, scalar_one):** #1551.
- **Lote #2230 — Consolidación causa-raíz: Invariantes de consistencia con origen/configuración validadas solo aguas abajo:** #1739, #1755.
- **Lote #2236 — Consolidación causa-raíz: Guard de stock negativo por lote:** #1876, #1878.

### Fase 6 — Reportes y experiencia de usuario

- **Lotes UI por subcontrato — #1711 ([ROOT CAUSE][FRONTEND] Contratos de interfaz: i18n, Alpine, endpoints y CSRF):**
  - seguridad: #1859, #1867.
  - traducción: #1782, #1814, #1963.
  - listas: #1792.
  - formularios y flujos: #1567, #1775, #1791, #1795, #1808, #1842, #1855, #1870, #1875, #1883, #1976.
  - Separar commits por componente/flujo si no comparten plantilla o contrato. Corregir el backend antes de UI salvo que la pantalla bloquee el flujo o exponga datos.
- **Lote #1712 — [ROOT CAUSE][FRONTEND] Invalidación de respuestas async: request-id/snapshot en todos los flujos:** #1862.
- **Lote #2228 — Consolidación causa-raíz: Grano/clave de agregación en reportes y KPI:** #1619.

## Issues standalone: añadirlos al flujo consumidor

- **Contabilidad, R2R y recurrentes:** #647, #1042, #1084, #1783, #1837, #1150, #1151, #1816.
- **O2C/S2P y documentos:** #1041, #1079, #1226, #1805, #1801.
- **Inventario y tesorería:** #1827, #1067, #1303, #1832.
- **Plataforma, UI, operación y documentación:** #1856, #1844, #1370, #1967, #1748.

## Issues accionables adicionales por fase

Ejecutar estas tareas junto con los lotes de la fase consumidora. La columna de coordinación indica el paraguas documentado en los vínculos o comentarios existentes; «Consumidor» identifica una tarea standalone de esa fase. #1658 coordina features distribuidas entre consumidores y no introduce una fase posterior. Los trackers y paraguas nunca se toman como fixes independientes aunque tengan `needs-work`.

### Fase 2 — Persistencia y garantías transversales

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #923 | #1706 | ✅ `5fb3e5f8` + `0181df55`: FK RESTRICT en esquema nuevo y evidencia preservada; 91 passed, 1 skipped; GitHub: open / needs-work | [HIGH][S2P][O2C][Append-only] DocumentRelation y conciliaciones permiten reescritura sin auditoría |
| #1093 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Código bloquea y revalida, pero falta regresión de doble reembolso multi-sesión PostgreSQL Tier 1 |
| #1139 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | El servicio serializa por factura y bloquea líneas, pero falta prueba con interleaving de dos transacciones PostgreSQL |
| #1177 | #1653 / #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | La reversa de recepción se interpreta como entrega y el estado final de transferencias depende del orden de movimientos |
| #1178 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Estado serial se lee y actualiza sin lock; falta regresión de doble salida en PostgreSQL |
| #1271 | #1653 | ✅ QA1/QA2 aprueban estáticamente; GitHub: open / needs-work | Evita ajustes duplicados en conciliación de caja chica |
| #1306 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Validación y actualización de serial siguen sin lock/revalidación dentro del posteo |
| #1318 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Helper retirado, pero el modelo y reporte aún exigen diagnosticar/migrar filas legacy; falta estrategia de datos verificable |
| #1683 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Modelo y MUTABLE_STATE ya limpios, pero no existe migración Alembic efectiva ni prueba de upgrade existente según ADR #1898 |
| #1697 | #1653 | ❌ QA1/QA2 rechazan; carrera de sal SMTP y DDL de arranque en conflicto con Alembic aprobado #1898; GitHub: open / needs-work | Claves únicas, escritura atómica de todos los callers y upgrade versionado de bases existentes |
| #1987 | #1706 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Asociación append-only y pruebas presentes; falta migración Alembic efectiva para la tabla nueva según #1898 |

### Fase 3 — Entradas, maestros y contratos de API

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #1059 | #1652 | ❌ QA1/QA2 rechazan; decisión aprobada 6716234735 pero el adaptador ignora impuesto y no calcula/persiste impuestos; GitHub: open / needs-work | Aplicar plantilla fiscal, comparar observado, calcular omitido y persistir resultado en orden/línea |
| #1062 | #1658 | ❌ QA1/QA2 rechazan en HEAD `45e38f2b`; GitHub: open / needs-work | Falta checkpoint/idempotencia para reanudar tras commit parcial; estado 7 no ofrece acción y `detail()` vuelve a parsear la fuente fallida |
| #1199 | #1658 | ❌ QA1/QA2 rechazan: adaptador huérfano y pruebas siguen en árbol; GitHub: open / needs-work | Retirar archivo y tests directos del adaptador no registrado; asegurar tests del activo. Contrato fiscal aprobado #1059 requiere integración separada antes de declarar paridad funcional |
| #1201 | Consumidor | ❌ QA1/QA2 rechazan: XLSX nativo ya normaliza, XLS sigue convirtiendo serial a texto y omite datemode; faltan fixtures 1900/1904 y recorrido a consumer; GitHub: open / needs-work | Normalizar fechas nativas XLS/XLSX al mismo contrato y preservar época de workbook |
| #1206 | #1652 | ❌ QA1/QA2 rechazan: endpoint sigue haciendo `list(worksheet.iter_rows())` antes de límites; el XLSXReader limitado no se usa y no hay prueba endpoint con dimensión inflada; GitHub: open / needs-work | Aplicar límites de filas/columnas durante lectura en `/parse-xlsx`, sin confiar en dimensión declarada |
| #1291 | #1652 | ❌ QA1/QA2 rechazan; GitHub: open / needs-work | Seguimiento: normalización de fechas Excel en importaciones |
| #1295 | #1652 | ❌ QA1/QA2 rechazan: falta guard de worker y regresiones de formatos; GitHub: open / needs-work | Seguimiento: rechazo de importaciones sin filas de datos |
| #1300 | #1716 | ❌ QA1/QA2 rechazan: configuración y ambos postings admiten cuentas inválidas; GitHub: open / needs-work | Rechaza cuentas AR/AP no contabilizables |
| #1302 | #1716 | ❌ QA1/QA2 rechazan: PO ya revalida; cotización/recepción/factura conservan bypasses; GitHub: open / needs-work | Valida proveedor activo al aprobar factura de compra |
| #1339 | #1716 | ❌ QA1/QA2 rechazan: sin guard de alta/selector y discovery omite vigencia; GitHub: open / needs-work | Impide agregar valores a dimensiones inactivas |
| #1342 | #1716 | ❌ QA1/QA2 rechazan template_id entre cuentas; semántica global+cuenta pendiente, GitHub: open / needs-work | Valida cuenta bancaria al elegir plantilla de cheque |
| #1373 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Limita filas XLSX antes de materializar la hoja completa |
| #1374 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza fechas inválidas en la validación de asientos importados |
| #1383 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: conserva grupo al importar terceros |
| #1389 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita insertar dos veces líneas importadas |
| #1393 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Permite corregir lotes con errores desde la interfaz |
| #1394 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Respeta la serie elegida al importar terceros |
| #1395 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Limita la cancelación de lotes al estado procesando |
| #1396 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación ODS omite filas repetidas |
| #1397 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida líneas importadas junto al comprobante existente |
| #1398 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida acumulados de pagos en importación de conciliaciones |
| #1400 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza ZIP que no sea XLSX en el importador de líneas |
| #1401 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza múltiples hojas de líneas en XLSX |
| #1403 | #1650 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza ajustes de cambio negativos al conciliar pagos |
| #1435 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importar artículos de landed cost pierde las líneas |
| #1439 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación de conciliaciones no acumula aplicaciones |
| #1446 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [API][Import] Cierra el workbook antes de borrar XLSX temporal |
| #1447 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [API][Cash] Importación no valida tipo de pago contra referencia |
| #1448 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [UI][Sales] La importación de cotización descarta el descuento |
| #1449 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [UI][Import] El pegado acepta encabezados duplicados |
| #1450 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [UI][I2F] La importación pierde bodegas por línea |
| #1451 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [UI][Import] Se descarta la descripción importada de las líneas |
| #1452 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [UI][O2C] La importación descarta la bodega de la línea |
| #1456 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conciliación: importador rechaza reference_id del esquema |
| #1461 | #1650 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Normaliza fecha antes de crear pagos destino |
| #1469 | #1650 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [Cash] NaN provoca error 500 al conciliar pagos |
| #1471 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | [Cash] Fechas ambiguas del extracto se interpretan por orden fijo |
| #1472 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [Imports] XLSX rechaza fecha final del período abierto |
| #1475 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | ODS: celdas combinadas desplazan datos de columna |
| #1477 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación transaccional acepta tercero de rol incorrecto |
| #1478 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación ignora encabezados distintos dentro del documento |
| #1479 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación de líneas pierde valores con encabezados duplicados |
| #1489 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Acepta CSV de presupuesto con BOM UTF-8 |
| #1491 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita validar importaciones de presupuesto vacías |
| #1505 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza importes negativos en columnas del extracto |
| #1506 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita interpretar fechas ambiguas del extracto |
| #1507 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Detecta transacciones duplicadas dentro del mismo lote |
| #1510 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | No deduzcas duplicados sin referencia bancaria |
| #1512 | #1650 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Preservar decimales al serializar pagos en Alpine |
| #1519 | #1650 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: conserva precisión al comparar ofertas |
| #1530 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Journal imports ignore dates that differ within a reference |
| #1531 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Transaction import templates reject their serial column |
| #1532 | #1718 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Transaction imports accept parties with the wrong role |
| #1533 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Transaction imports ignore currency changes within a document |
| #1535 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Transaction imports ignore party changes within a document |
| #1536 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importaciones omiten fechas distintas por documento |
| #1538 | #1716 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación bancaria acepta cuentas inactivas |
| #1544 | #1650 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Ventas y compras fallan con tarifas Infinity |
| #1568 | #1717 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Matching acepta tipos y tolerancias fuera de rango |
| #1623 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación XLSX operativa acepta fórmulas con valores en caché |
| #1625 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importadores ODS de presupuesto y tasas fallan con odfpy |
| #1627 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación de presupuesto valida un archivo vacío |
| #1629 | #1652 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida series y cantidades al importar documentos de inventario |
| #1670 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [Line Import] La columna description se descarta |
| #1835 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | [AUDIT][I2F] Editar conciliación de inventario borra las observaciones previas |

### Fase 4 — Invariantes contables y ciclo documental

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #2120 | #1709 | ✅ `9f129cc4`; GitHub: open / fix-proposed | Rechaza períodos ausentes/ambiguos, bloquea y revalida el período de reversa; 12 passed, 1 skipped en SQLite; PostgreSQL pendiente por entorno |
| #546 | #1655 | ✅ `d3759012` + `4012a719`; GitHub: open / fix-proposed | Inmutabilidad de tasas dentro de vigencia directa/inversa; revaluaciones usan coalesce(run_date, posting_date); 9 passed en SQLite; PostgreSQL pendiente por entorno |
| #758 | #1655 | ✅ `3fab3b73` + `99295f23`; GitHub: open / fix-proposed | Snapshots explícitos y guardas por libro; 53 passed en SQLite; sin migración legacy; PostgreSQL pendiente por entorno |
| #761 | #1708 | ⚠️ Parcial; GitHub: open / needs-work | `3cacfb3d` exige misma fecha de contabilización para anular; según decisión confirmada no hay migraciones. Pendiente completar paridad de anulaciones/reversiones operativas y reportes bajo la política aprobada del issue |
| #961 | #1655 | ✅ `18f9d598` + `d69973f5`; GitHub: open / fix-proposed | AR/AP bloquea conversión sin tasa directa/inversa/funcional; 2 passed en SQLite; PostgreSQL pendiente por entorno |
| #995 | #1707 | ✅ `ca5eb857`; GitHub: open / fix-proposed | Preview y snapshot comparten base acumulada; 13 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #996 | #1707 | ✅ `e7c46c62`; GitHub: open / fix-proposed | Creación/edición suman impuesto manual; AP y GL concilian; 2 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #1009 | #1707 | ✅ `ca2f732f`; GitHub: open / fix-proposed | Preview/persistencia rechazan base, tasa e importe negativos; 22 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #1011 | #1707 | ✅ `4da61378` + `fe8d2442`; GitHub: open / fix-proposed | Deduplica conceptos en reglas, preview, motor y snapshot; 15+23 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #1015 | #1707 | ✅ `66c49a43`; GitHub: open / fix-proposed | Buying permite purchase/both y selling sales/both; formulario y cálculo validan; 20 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #1016 | #1655 | ✅ `4fa5166d` + catálogo `09d067fd`/`56c5ba03`/`637ded51`; GitHub: open / fix-proposed | Convierte lista a moneda documental y limpia precios obsoletos; bloquea al guardar sin tasa; 7 Python + 24 JS passed; sin migraciones; PostgreSQL pendiente por entorno |
| #1017 | #1708 | ✅ `b8da6123` + `9f6bb0ba`; GitHub: open / fix-proposed | Whitelist approve/reject; POST typo conserva Pending Approval y no crea ApprovalAction; 2 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #1022 | #1708 | ✅ `d41cb51a` + `1a5f44cc`; GitHub: open / fix-proposed | Notas aprobadas publican GL; doctype sin despacho falla sin dejar Approved/acción; 2 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #1023 | #1707 | ✅ `2f2381f4` + `ec7a0c6c` + `134e9be6`; GitHub: open / fix-proposed | Snapshot acumula conceptos repetidos; compara cálculo con líneas canónicas persistidas (base 18, monto 1.80, total 119.80); 16 passed en SQLite; sin migraciones; PostgreSQL pendiente por entorno |
| #1026 | #1707 | ✅ `6cf51175`; GitHub: open / fix-proposed | Ambos motores reconstruyen base neta para `net_document`, respetan secuencia `previous_total`, inclusivos múltiples, impuestos fijos y redondeo; 56 passed en SQLite; cobertura 92%/88%; sin migraciones; PostgreSQL pendiente por entorno |
| #1027 | #1708 | ✅ `277b005c`; GitHub: open / fix-confirmed | Certificado no vigente rechaza reemisión y conserva evidencia; 4 tests passed en SQLite; Black/Ruff/Flake8/mypy/pylint/pydocstyle/complexipy OK; sin migraciones; PostgreSQL pendiente por entorno |
| #1043 | #1708 | ✅ `cd5244ab`; GitHub: open / fix-proposed | Ignora capas de consumidores borrador/anulados; mantiene bloqueo fail-closed si falta voucher; 8 tests pasaron en SQLite; Black/Ruff/Flake8/mypy/pydocstyle/complexipy OK; pylint 10/10 excluyendo R0902 preexistente; sin migraciones; PostgreSQL pendiente por entorno |
| #1078 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Comparar ofertas en moneda funcional al autorizar excepción |
| #1082 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Autorizar transición al cerrar ajuste bancario |
| #1085 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Retirar saldos legacy del pronóstico de caja |
| #1086 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluir reversiones en el flujo real de caja |
| #1091 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Reconstruir vales y gastos pendientes al corte histórico |
| #1114 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: alinea la moneda de conciliación del GL |
| #1115 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: acumula saldo previo en el Kardex |
| #1121 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: presenta saldos bancarios en una sola moneda |
| #1122 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: conserva saldos GL antes de anulación |
| #1123 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: conserva stock histórico antes de anulación |
| #1124 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: conserva facturas en reportes históricos |
| #1149 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: aplica la frecuencia de diarios recurrentes |
| #1157 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El cierre mensual revaloriza un período distinto |
| #1164 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida el balance de diarios con tasas por línea |
| #1165 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza monedas inactivas en líneas de diarios |
| #1166 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Permite contabilizar diarios tras aprobación |
| #1168 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye reversiones del año en el cierre fiscal |
| #1170 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Integra el cierre fiscal con la aprobación Cloud |
| #1171 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Protege las fechas de años cerrados financieramente |
| #1172 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Impide años fiscales con rangos superpuestos |
| #1209 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Permite cancelar recibo tras anular consumo de inventario |
| #1210 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | No bloquees cancelar factura por su propio costo capitalizado |
| #1211 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida costo de inventario consumido al cancelar landed cost |
| #1221 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Bloquea cancelar devolución física con nota de crédito activa |
| #1222 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Cancela asignaciones de notas de crédito sin recibo u orden |
| #1223 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida los enlaces de origen de notas de compra |
| #1224 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida los orígenes de las notas de venta |
| #1232 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Libera gastos de reposiciones canceladas |
| #1233 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Muestra proyecciones manuales sin tasa de cambio |
| #1234 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Proyecta cobros y pagos según vencimiento |
| #1235 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida moneda en matriz de conciliación |
| #1236 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye las cuentas fiscales configuradas en conciliación |
| #1237 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Aplica el rango de cuentas al presupuesto comparado |
| #1238 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Respeta límites parciales de período presupuestario |
| #1242 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conserva reversiones de stock en su fecha efectiva |
| #1244 | #1654 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Define valoración de inventario por libro en conciliación |
| #1245 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye saldo inicial previo en el Kardex |
| #1248 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza períodos inválidos en reportes GL |
| #1249 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita mapeos EFE sin efecto en cuentas P&L |
| #1250 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Detecta cuentas de efectivo sin clasificar en el EFE |
| #1251 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Alinea moneda del saldo bancario reportado |
| #1252 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Separa conciliaciones bancarias de AR/AP en el reporte |
| #1257 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida calendarios al comparar pronosticos de caja |
| #1259 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida fechas de entradas del pronostico |
| #1270 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Soporta reposición multimoneda de caja chica |
| #1273 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Impide cancelar un vale con gasto contabilizado activo |
| #1274 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Resta las reglas fiscales configuradas como descuento |
| #1275 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conecta affects_settlement al cálculo de pago y cobro |
| #1276 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Alinea los flags de inventario de reglas fiscales |
| #1281 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Respeta la moneda de la lista al validar precios de venta |
| #1287 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza contabilizaciones fuera de un período |
| #1293 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita reutilizar números al retroceder la fecha de posting |
| #1297 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Aplica la plantilla fiscal configurada para el tercero |
| #1311 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Respeta la fecha de corte al calcular saldo FX |
| #1312 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza períodos deshabilitados en revaluación FX |
| #1315 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Lista cierres fiscales desde el modelo equivocado |
| #1317 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Permite conciliar la pata destino multimoneda |
| #1323 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Convierte la fecha antes de consultar la tasa del pago |
| #1324 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita asumir NIO sin moneda funcional |
| #1325 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Advierte flujos omitidos por falta de tipo de cambio |
| #1337 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conecta las dimensiones analíticas con el ledger GL |
| #1341 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye saldo inicial en balanza de query tools |
| #1348 | #1709 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Apertura previa, reversas con fecha efectiva y acumulado separado por cuenta |
| #1359 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Integración dinámica ausente; revertir dirección local de retiro del modelo conforme a la decisión vigente |
| #1364 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Guard de adjudicación existe; faltan regresiones y rechazar quotes con ronda inválida/nula |
| #1365 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Cierre aún cuenta ofertas canceladas/no aprobadas en comparativos finalized/used |
| #1367 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Excepción aún acepta espacios y no conserva motivo/actor en la orden |
| #1368 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Seguimiento: conectar dimensiones analíticas con el ledger GL |
| #1372 | #1656 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Fecha fiscal parcial se acepta y se reemplaza por calendario sin aviso |
| #1375 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Guard final ya incluye las cuatro notas, pero falta regresión vigente y las notas de compra omiten importe no nulo; nota de venta solo valida origen si se informa |
| #1377 | #1709 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | KPI aún usa `include_returns=False` y `payables` filtra devoluciones; falta regresión de conciliación |
| #1378 | #1655 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Árbol reutiliza allocated en moneda ajena y total de referencias etiqueta allocated con moneda del pago |
| #1380 | #1655 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Al cambiar cuenta la UI conserva tasa positiva antigua y backend la persiste sin validar el par nuevo |
| #1381 | #1656 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | El guard secuencial existe, pero session identity stale evade aprobación concurrente; faltan Closed/Archived |
| #1382 | #1655 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | El adaptador activo pierde 0 numérico con `or` y cae a tasa histórica; faltan regresiones |
| #1386 | #1654 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Fix y regresiones principales presentes; falta regresión de libro activo de otra compañía |
| #1430 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Clave ajena no se valida y permite persistir award finalized sin líneas |
| #1434 | #1709 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | KPI cuenta todo docstatus=1 sin status ni pendientes; reproducción sigue vigente |
| #1437 | #1707 | ❌ QA1/QA2 rechazan; GitHub: open / needs-work | Notas de crédito muestran preview fiscal de factura |
| #1438 | #1655 | ❌ QA1/QA2 rechazan; GitHub: open / needs-work | Preview de factura de compra usa NIO en vez de su moneda |
| #1440 | #1655 | ❌ QA1/QA2 rechazan; GitHub: open / needs-work | Saldo de pagos previos se duplica al prorratear |
| #1441 | #1707 | ❌ QA1/QA2 rechazan; GitHub: open / needs-work | Asiento fiscal omite impuestos sin cuenta configurada |
| #1460 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Prorratea mal el valor de anticipos multimoneda |
| #1490 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Guarda cambios de libro y año fiscal del presupuesto |
| #1752 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Editar borrador ignora ID y POST crea un costo de importación duplicado |
| #1813 | #1658 | ❌ QA1/QA2 rechazan en re-revisión local; GitHub: open / needs-work | 3-way pasa con `require_sales_order=False` y sin OV/Nota, o con Nota no vinculada a OV; test solo invoca helper, falta regresión POST submit y prueba de no-posting |
| #1888 | #1658 | ❌ QA1/QA2 rechazan independientemente en revisión local; GitHub: open / needs-work | Decisión aprobada reciente: persistir/recuperar remarks y centro de costo/proyecto por línea según #1359; retirar tax payloads, ocultar/rechazar account arbitraria y campos no soportados. `StockEntryItem` carece de columnas; writer y edit renderer omiten esos valores; macro/JS aún muestran y preparan controles fiscales/dimensiones/cuenta; faltan propagación GL por línea, validación/RBAC y regresiones integradas. |
| #1930 | #1658 | ✅ QA1/QA2 aprueban estáticamente en HEAD local; GitHub: open / needs-work | Tamaño/orientación aplican a CSS/PDF/preview; POST inválidos de alta/edición re-renderizan sin alterar configuración |
| #1938 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | `show_users`/`advanced` persistidos no se restauran; falta migración de SavedReportView para DB existentes |
| #1118 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: open / needs-work | Test cubre borrador/posteado, pero no cancelado ni total exclusivo posteado |
| #1499 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye reversas de GL en el pronóstico real de caja |
| #1501 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida fechas de proyecciones dentro del año fiscal |
| #1502 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Permite conciliar reversas contabilizadas de otro período |
| #1503 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Reporta auto conciliación antes de aprobación requerida |
| #1513 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Descartar vistas previas fiscales obsoletas en pagos |
| #1523 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: respeta el corte histórico de conciliación |
| #1547 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Refleja notas aplicadas en confirmaciones de saldo |
| #1549 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Bloquea impuestos sin cuenta contable |
| #1553 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita fallos al consultar estados con historial de aprobaciones |
| #1560 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El saldo bancario se muestra en una moneda distinta |
| #1561 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Las gráficas agrupan meses de años distintos |
| #1565 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Un rango solapado permite aprobar con un nivel inferior |
| #1566 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El rechazo registra una regla ajena al monto |
| #1569 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El neteo de anticipos sobreestima el importe en otras monedas |
| #1577 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita reiniciar secuencias al volver a un periodo previo |
| #1580 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida el prefijo al registrar números externos |
| #1582 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye reversiones en métricas analíticas GL |
| #1589 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Calcula saldo inicial en detalle bancario |
| #1594 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Alinea motivo de excepción con recomendación por moneda |
| #1596 | #1709 | ⚠️ Implementación pendiente; GitHub: open / needs-work | La conciliación de caja chica no reconstruye el estado al corte |
| #1604 | #1655 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Corrige pagos con moneda distinta a la factura |
| #1605 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Maneja estado inválido al crear órdenes del comparativo |
| #1621 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | O2C: solicitud queda abierta tras convertirse en orden |
| #1634 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El motor fiscal aplica reglas de otros países |
| #1635 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Factura de venta acepta reglas fiscales incompatibles en el payload |
| #1637 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida retenciones de pago con base del cliente |
| #1638 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El estado documental omite cancelaciones pendientes |
| #1642 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | La aprobación de anulación no cancela costos de importación |
| #1686 | #1707 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [Audit][Fiscal] Consolida impuestos en un solo motor |
| #1698 | #1656 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [AUDIT][R2R] Pasos del cierre reabren corridas cerradas |
| #1701 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [AUDIT][R2R] Regla Cualquiera no asigna aprobadores |
| #1702 | #1708 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [AUDIT][R2R] GET sobrescribe confirmaciones respondidas |
| #1840 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | [AUDIT][R2R] El paquete accounting_engine no tiene suite de pruebas dedicada |

### Fase 5 — Subledgers y flujos operativos

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #651 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [MEDIO][INV] Reconstrucción de capas de valuación destructiva |
| #947 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Document Flow: cantidades pendientes mezclan UOM |
| #966 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Document status: unificar cantidades base |
| #975 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Document Flow: alinear resumen de pagos al saldo canónico |
| #1036 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Caja chica: expected_cash duplica los gastos posteados y reporta faltante fantasma en cajas físicamente cuadradas |
| #1037 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Reportes por item: get_purchases_by_item/get_sales_by_item suman cantidades en UOMs transaccionales distintas |
| #1038 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Reportes de transferencias: la fila reporta qty_in_base_uom etiquetada con la UOM de transacción |
| #1040 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Ventas: cancelar factura con nota de entrega asociada omite revertir relaciones y refrescar caches derivados |
| #1068 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conciliación automática ignora saldo bancario pendiente |
| #1073 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Reconstrucción deja bins sin ledger sin corregir |
| #1074 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Eliminar compatibilidad GR/IR sin consumidores |
| #1077 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Emparejar ofertas con su línea origen de RFQ |
| #1089 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Proteger el historial al cambiar cuenta de caja chica |
| #1099 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Retira la validación monetaria de pago sin uso |
| #1102 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | No reduz saldo AR/AP por pagos en borrador |
| #1113 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: evita descontar dos veces notas aplicadas |
| #1116 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: calcula pagos en devoluciones con signo correcto |
| #1127 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: filtra documentos abiertos por saldo vigente |
| #1133 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: valida existencia de la capa en devoluciones S2P |
| #1135 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: compara cantidades de órdenes en UOM base |
| #1136 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: normaliza UOM omitida en conciliación S2P |
| #1137 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: permite devolver líneas repetidas de recepción |
| #1140 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: revalida saldo al contabilizar pagos |
| #1143 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: calcula remanente de reembolsos con signo correcto |
| #1146 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: conserva número documental al reconstruir AR/AP |
| #1147 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: respeta open item elegido al postear diarios |
| #1152 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: muestra aplicaciones recurrentes pendientes en cierre |
| #1161 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita revaluar saldos de factura ya reducidos por notas |
| #1179 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Test suite falla |
| #1180 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Congela conversiones UOM de documentos abiertos |
| #1188 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida fondos antes de registrar gastos de caja chica |
| #1194 | Consumidor | ⚠️ Implementación pendiente; GitHub: open / needs-work | Autoconciliación bancaria registra conciliaciones pendientes como aplicadas |
| #1207 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Confirmación de saldos muestra notas de crédito ya aplicadas |
| #1214 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Impide consumir capas de inventario con fecha futura |
| #1215 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Permite conciliar inventario controlado por lote o serial |
| #1216 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye costos capitalizados de factura en devolución física |
| #1217 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Excluye landed costs anulados del costo de devolución |
| #1218 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Prorratea landed cost entre recibos parciales en devoluciones |
| #1219 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evita duplicar costo capitalizado del recibo en devolución |
| #1228 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Recalcula estado bancario al cancelar pagos conciliados |
| #1230 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Recalcula caja chica al confirmar conciliación |
| #1239 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Integra el análisis semántico de stock negativo |
| #1255 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Calcula documentos abiertos desde su saldo real |
| #1304 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Elimina el fallback a referencias de pago sin relación |
| #1307 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Evalúa cambio de UOM base tras movimientos anulados |
| #1310 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Excluye pagos cancelados del valor en libros AR/AP |
| #1313 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Impide cancelar la revaluación desde journal genérico |
| #1316 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Revierte la conciliación al anular su asiento GL |
| #1333 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Revalida cantidades al duplicar órdenes de compra |
| #1334 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Bloquea cambio de UOM si hay cotizaciones históricas |
| #1335 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Reconstruye también bins sin movimientos de ledger |
| #1336 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conserva la composición FIFO al reconstruir capas |
| #1351 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conserva liquidaciones válidas en cortes previos a cancelar el pago |
| #1363 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | [Auditoría] Normaliza eventos al reconstruir conciliación |
| #1379 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: limpia referencias al cambiar el tercero del pago |
| #1387 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Invalida los documentos fuente al cambiar el tercero |
| #1391 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Revalida capacidad fuente al aprobar documentos O2C |
| #1402 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Limpia conciliación al cambiar sus filtros |
| #1404 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Excluye referencias revertidas del saldo disponible del pago |
| #1413 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida lotes con saldo posterior a la fecha del movimiento |
| #1414 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | La reconstrucción deja bins sin movimientos intactos |
| #1415 | #1715 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rebuild de capas rompe referencias de costo capitalizable |
| #1420 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Limpiar un artículo conserva y reenvía la selección anterior |
| #1424 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Resuelve notas de crédito por línea de origen |
| #1425 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Calcula tarifas solo con líneas pendientes |
| #1426 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Respeta la línea origen al asignar facturas |
| #1429 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Normaliza UOM al adjudicar ofertas |
| #1431 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Usa relaciones para alinear líneas de ofertas |
| #1458 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Pago destino: borrador reduce saldo cacheado de factura |
| #1459 | #1657 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Cuenta en cero el remanente de reembolsos AR/AP |
| #1464 | #1719 | ⚠️ Implementación pendiente; GitHub: open / needs-work | La búsqueda documental omite resultados tras deduplicar GL |
| #1481 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Adjudicación mezcla cantidad y precio entre unidades |
| #1482 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Comparativo asigna cotización a línea RFQ equivocada |
| #1495 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida la dirección al aplicar anticipos |
| #1496 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida el tercero en relaciones documentales |
| #1497 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Rechaza tipos de pago no admitidos |
| #1516 | #1719 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El flujo documental falla con 500 al apuntar a journal_entry |
| #1517 | #1719 | ⚠️ Implementación pendiente; GitHub: open / needs-work | El árbol documental acepta límites que provocan RecursionError |
| #1521 | #1713 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: soporta devoluciones con artículos repetidos |
| #1545 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Revisar tasa histórica en aplicaciones posteriores AR/AP |
| #1552 | #1719 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Valida el origen al cerrar saldos de flujo |
| #1570 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | La nota de débito de ventas queda como abierta sin cobrar |
| #1573 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Respeta la línea al resolver referencias desde el ledger AR/AP |
| #1585 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Incluye devoluciones en reportes de CxP |
| #1611 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Cambiar el artículo conserva requisitos de lote y serie anteriores |
| #1614 | #1714 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Respeta el corte histórico al calcular saldo AR/AP |
| #1624 | #1651 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Importación cambia la UOM sin convertir la cantidad |

### Fase 6 — Reportes y experiencia de usuario

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #1071 | #1658 | ❌ QA1/QA2 confirman QA3; GitHub: open / needs-work | Retiro correcto; falta regresión HTTP que pruebe el contrato canónico ante `?legacy=1` |
| #1092 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Completar rutas enlazadas en lista de reposiciones |
| #1111 | #1711 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: permite agregar correos en confirmación |
| #1112 | #1711 | ⚠️ Implementación pendiente; GitHub: open / needs-work | fix: muestra historial de confirmaciones por tercero |
| #1119 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | refactor: elimina fallbacks gettext muertos y recursivos |
| #1131 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | refactor: elimina fechas inertes en consultas de lotes |
| #1213 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Descarta snapshots tardíos en conciliación de inventario |
| #1285 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Elimina o conecta la ruta de carga de adjuntos sin uso |
| #1331 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Elimina o integra el flujo de adjuntos sin uso |
| #1453 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Diario: aceptar validación obsoleta al importar líneas |
| #1454 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Diario: respuesta XLSX reemplaza líneas pegadas después |
| #1455 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conciliación: importación XLSX pisa líneas editadas |
| #1457 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Conciliación: mostrar candidatos de filtros anteriores |
| #1463 | #1711 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Limpia selectores dependientes al editar una selección |
| #1480 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Validación tardía reemplaza filas nuevas del comprobante |
| #1485 | #1711 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Corrige acciones rotas en listas de Caja Chica |
| #1487 | #1711 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Registra el filtro de moneda de presupuestos |
| #1574 | #1711 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Traduce las etiquetas del esquema de importación |
| #1575 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Descarta respuestas de validación obsoletas del importador |
| #1591 | #1712 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Ignora snapshots obsoletos en conciliación de inventario |
| #1646 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Editar caja chica ignora el nombre enviado |
| #1647 | #1658 | ⚠️ Implementación pendiente; GitHub: open / needs-work | Listas de caja chica usan endpoints inexistentes |

## Decisiones aprobadas: contratos de implementación

Estas decisiones se consideran resueltas según los comentarios de los issues y la matriz del responsable. No son bloqueos de triaje. El trabajo es implementar, probar y documentar su cumplimiento.

| Issue | Contrato de implementación | Lote relacionado |
|---|---|---|
| #1658 | Resolver por feature: integrar las funciones aprobadas, retirar código residual y diferir solo con justificación e impacto documentados. | Distribuir hijos entre las fases consumidoras 1–6 |
| #1340 | Unicidad por tipo, valor normalizado y compañía; precedencia del valor local. | #2213 |
| #2213 | Consolidar el contrato de unicidad para códigos y valores predeterminados con la regla aprobada en #1340. | Fase 3 |
| #1105 | Bloquear recepciones valorizadas si no pueden generar una contabilización válida. | #2223 |
| #1246 | Calcular rotación con promedio de inventario ponderado por tiempo. | #2224 |
| #1893 | Duplicar StockEntry de forma independiente, sin heredar relaciones económicas. | #1713 |
| #1895 | Al reutilizar líneas, preservar lote, serie y vencimiento. | #1713 |
| #1897 | Bloquear la duplicación mientras la cancelación está pendiente. | #1708 |
| #1930 | Aplicar tamaño y orientación de página a la salida PDF. | #1658, impresión |
| #1938 | Integrar vistas guardadas reutilizables y aplicar RBAC. | #1658, R2R/UI |
| #1955 | Los reportes de Kardex y bancos operan con períodos contables completos. | #1656 |

Si durante la implementación aparece una incompatibilidad real con estos contratos, registrar la evidencia y el caso concreto; no volver a poner estos issues en una fase genérica de decisión.

## Validación y cierre progresivo

- Para cada fix: pruebas reales orientadas a comportamiento; rollback, repetición, concurrencia, aislamiento de compañías, multilibro/moneda y reversión cuando correspondan.
- Tier 1 se valida en SQLite y PostgreSQL; MySQL Tier 2 también se prueba según la cadencia de integración. Desktop debe operar sin Redis. R2R consume fuentes conciliadas, no agregados sin grano definido.
- Antes de cada commit de código, ejecutar las pruebas mínimas pertinentes y los linters; cada 50 commits acumulados y antes del push, completar la ronda de workflows definida en «Ritmo de desarrollo y controles». Registrar comandos, SHA validado, resultados y bloqueos en GitHub. QA1 y QA2 revisan independientemente; conservar `needs-work` si falta cobertura o una observación sigue abierta. Solo QA3 expresamente autorizado o el administrador puede establecer `fixed`; no cerrar ni hacer push sin autorización expresa.
- La puerta Alpha de #2248 requiere recorridos O2C/S2P/I2F/CTM y R2R, migración de bases limpia/existente según modo, y limitaciones diferidas aceptadas con justificación e impacto.
