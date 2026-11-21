# Plan accionable de estabilización

**Repositorio:** [cacao-accounting/cacao-accounting](https://github.com/cacao-accounting/cacao-accounting)

**Tracker maestro:** [#2248](https://github.com/cacao-accounting/cacao-accounting/issues/2248)

**Rama de trabajo:** `estabilizacion`, con seguimiento de la rama remota `origin/estabilizacion`.

**Corte de estado:** 21 de noviembre de 2026. Issues y subissues contrastados en GitHub; incluye el triage
de cierre de los 157 issues que llegaron a `fixed` (151 cerrados y 6 devueltos a `needs-work`) y la verificación
QA3 del 2026-11-21 que cerró los 26 issues abiertos restantes con etiqueta `fixed`; hoy no queda ningún
issue abierto con esa etiqueta en GitHub.

**Estado de commits (21 de noviembre de 2026, refs locales):** `origin/estabilizacion` está en
`94d80e55`; `HEAD` local acumula 7 commits por delante y sin push. “Commit local” no
significa publicado en GitHub. Los hashes citados en las tablas deben verificarse contra la rama
antes de considerarlos integrados; el lote de cierre de esta sesión es local y aún requiere QA1 → QA2.

## Alcance de ejecución

- El plan contiene la cola de issues abiertos con trabajo accionable. Los issues cerrados, trackers y agrupadores se usan como referencias de coordinación; no se asignan como tareas de implementación.
- El triage del 2026-11-20 verificó los issues que llegaron a `fixed`: 151 se cerraron como completados y 6 volvieron a `needs-work`. Los cerrados salen de la cola; solo se reabren si aparece una regresión documentada con evidencia.
- `needs-work` significa implementación pendiente; `fix-proposed` significa que QA1 aprobó y falta la revisión independiente de QA2; `fix-confirmed` significa que QA2 aprobó y falta la aceptación final de QA3 expresamente autorizado o del administrador. Si una revisión encuentra una brecha, el issue vuelve a `needs-work` y reinicia el ciclo QA1 → QA2.
- Antes de intervenir y de entregar un lote, leer `feedback.md` y `review.md` si existen. Resolver las observaciones aplicables de QA1 y QA2 como parte del criterio de salida.
- Antes de atender un issue, leer su descripción y **todos sus comentarios**, con paginación completa, incluidos los del paraguas cuando establezcan el contrato compartido. Los comentarios son la bitácora de desarrollo: contienen decisiones, reproducciones, cambios existentes, rechazos de QA y limitaciones que pueden actualizar o sustituir el diagnóstico inicial. A estas alturas aportan más contexto de ejecución que la descripción original. Identificar las decisiones vigentes y los hallazgos aún aplicables antes de tocar código; no volver a decidir reglas ya aprobadas ni implementar a partir del título o de la descripción aislados. Si hay una contradicción real sin resolución posterior, presentar el caso concreto al responsable.
- El issue de interfaz pendiente que supera el límite de hijos de #1711 se incluye por referencia: #2193.

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
- **Integrar o completar:** #1118, #1492, #1493, #1564, #1737, #1752, #1758, #1811, #1813, #1888, #1891, #1919, #1928, #1930, #1931, #1937, #1938, #1950, #1973, #1992, #2045, #2061, #2062, #2077.
- **Retirar residual:** #1162, #1882, #1899, #1909, #1915, #1916, #2071, #2079.
- **Retirar el flujo redundante:** #2093, completar la retirada del flujo residual de comparativos de órdenes de compra.
- Estos hijos se ejecutan en los lotes consumidores de fases 1–6; esta lista es un índice de ruta, no un commit combinado. Para cada retiro conservar evidencia breve de búsqueda de consumidores y pruebas de que el flujo restante funciona.

#### Sub-lotes ejecutables del agrupador #1658

| Sub-lote | Issues | Trabajo para un fix acotado |
|---|---|---|
| 1658-A · Recurrentes | #1492, #1493 | Validar balance por plantilla y aplicar la frecuencia aprobada en la creación/ejecución. |
| 1658-B · O2C/R2R | #1118 ❌ QA1/QA2 rechazan; #1813 ❌ QA1/QA2 rechazan localmente; #2045 ❌ QA1/QA2 rechazan; #1937 ❌ QA1/QA2 rechazan | Corregir exclusión de transferencias sin postear, requisito de entrega para 3-way, exportación PDF del mayor y consumo de origen desde orden; separar commits por consumidor si no comparten servicio. |
| 1658-C · Inventario | #1737, #1811, #1888, #1891 | Aplicar conversiones UOM, moneda requerida de conciliación, persistencia de detalle y contrato de ajustes solo positivos/negativos. |
| 1658-D · Costos de compra | #1752, #1758 | Completar edición/prorrateo de landed cost y enlace a detalle; separar el enlace de interfaz si es independiente del cálculo. |
| 1658-E · Portal y vistas de administración | #1564, #1919, #1928, #1930, #1931, #1938 | Completar paginación, revocar portal inactivo, renderizar administración, aplicar tamaño/orientación PDF, habilitar historial y vistas guardadas con RBAC. Dividir por consumidor; no combinar cambios de portal, PDF y reportes en un commit. |
| 1658-F · Seguridad de formularios y configuración | #1950, #1973, #1992, #2061, #2062, #2077 | CSRF, referencias inactivas, serie elegida, credenciales iniciales seguras, eliminación de cuentas predeterminadas y registro del pipeline de archivos. Separar por módulo/contrato. |
| 1658-G · Retiro de residuales | #1162, #1882, #1899, #1909, #1915, #1916, #2071, #2079, #2093 | Retirar constantes, plantillas/macros/helpers/modelos/aliases sin consumidor y el flujo redundante de comparativos; verificar referencias antes de cada retiro. No juntar limpiezas de módulos distintos en un solo commit. |

### Fase 1 — Acceso, aislamiento y seguridad

- **Lote 1 — Origen y autorización de documentos — #1649:** #1405 ❌ QA1/QA2 rechazan cobertura HTTP; #1753 ❌ QA1/QA2 rechazan cobertura HTTP; #1971 ❌ QA1/QA2 rechazan cobertura HTTP; #2135 ❌ QA1/QA2 rechazan regresión de edición; #2142 ❌ QA1/QA2 rechazan regresión del filtro de período.
- **Lote 2 — Permisos, acceso y reportes — #1649:** #1725 ✅ QA1/QA2 aprueban localmente; #1761 ❌ QA1/QA2 rechazan falta de regresión CSRF HTTP; #1777 ❌ QA1/QA2 rechazan exposición residual de contactos globales; #1781 ❌ QA1/QA2 rechazan cobertura de acciones incompleta; #1785 ❌ QA1/QA2 rechazan falta de regresión draft/approved; #1789 ❌ QA1/QA2 rechazan falta de regresión de mapeos; #1797 ❌ QA1/QA2 rechazan mapeo de acciones y cobertura cross-company; #1828 ❌ QA1/QA2 rechazan bypass admin con `?company=`; #1833 ❌ QA1/QA2 rechazan cobertura de rol, compañía y flujo HTTP canónico; #1852 ❌ QA1/QA2 rechazan falta de regresión del permiso `editar`; #1920 ❌ QA1/QA2 rechazan bypass de admin y falta de pruebas de portal; #1926 ✅ fix local de regresiones HTTP para lista/detalle UOM, QA1/QA2 aprobados; #1998 ✅ permiso GET/POST separado y regresiones HTTP completadas en `d7a6f549`, QA1/QA2 aprueban, GitHub: `fix-proposed`; #2018 ✅ regresiones de referencias y ownership completadas en `9047d819`, QA1/QA2 aprueban, GitHub: `fix-proposed`; #2059/#2060 ✅ fix local de paridad badge/bandeja aprobado QA1/QA2 y committed en `30859cd2`; el primer set queda limitado a compañías activas concedidas; riesgo de costo O(N) en compañías autorizadas documentado como no bloqueante; #2092 ✅ fix local, regresión y QA1/QA2 aprobados; committed en `8885d843`.
- **Lote 3 — Listados y rutas adyacentes — #1649:** #1841, #1869, #1934, #2039, #2044, #2047, #2052, #2105.
- **Objetivo compartido:** aplicar el mismo alcance de compañía a rutas de lectura/escritura, IDs fuente y payloads; cubrir actor, acción, compañía propia/ajena y rutas alternativas.
- **Lote #1710 — [ROOT CAUSE][AUTH] Ciclo de vida de credenciales y mensajería: revocación, fail-safe e idempotencia:** #1732, #1762, #1917, #1948, #1958, #1965, #2023.
- **Lote #2209 — Consolidación causa-raíz: Sanitización/validación de salidas y recursos (XSS, SSRF, redirect):** #1923, #2131.
- **Lote #2231 — Consolidación causa-raíz: Invariante de operabilidad mínima (último admin/única entidad activa):** #1767, #1771.
- **Lote #2238 — Consolidación causa-raíz: Redacción de secretos en logs y evidencia:** (hijos cerrados en GitHub).

### Fase 2 — Persistencia y garantías transversales

- **Lotes por consumidor — #1653 (Consolidación causa-raíz: atomicidad/idempotencia en read-then-post):**
  - Concurrencia en inventario/documentos: #332, #1820, #1857, #1868, #1881, #1957, #2098.
  - #2140 (paraguas S2P): sus seis hallazgos anteriores tienen QA2 aprobado; QA1/QA2 aprobaron localmente el residual de cierre manual asociado a #1432 en HEAD `45e38f2b`. GitHub y etiquetas intactos; queda la decisión de QA3/autorizado.
  - Concurrencia financiera/bancaria: #1776 ❌ QA1/QA2 rechazan recuperación/idempotencia; #1784 ❌ QA1/QA2 rechazan atomicidad y retry; #2082 ❌ QA1/QA2 rechazan concurrencia PostgreSQL no probada; #2084 ❌ QA1/QA2 rechazan read-then-insert sin recuperación, #2128 ❌ QA1/QA2 rechazan faltan regresiones UA/error creación; #2129 ❌ QA1/QA2 rechazan casos legacy de idempotencia/default; #2138 ❌ QA1/QA2 rechazan falta de test PostgreSQL Tier 1.
  - Concurrencia auth/base/aprobaciones: #1680 ❌ QA1/QA2 rechazan falta de expected-version en formularios, #1730 ❌ QA1/QA2 rechazan seed no idempotente; #1910 ❌ QA1/QA2 rechazan harness de concurrencia ausente; #2076 ❌ QA1/QA2 rechazan approve que revive tras reject, #2186 ❌ QA1/QA2 rechazan falta de concurrencia PostgreSQL; #2187 ❌ QA1/QA2 rechazan test SQLite-only; #2188 ❌ QA1/QA2 rechazan posible deadlock por orden de locks.
  - Contrato de importación/UI: #1678.
  - **Dependencia:** fijar atomicidad/idempotencia por motor; no asumir que locks equivalen en SQLite y PostgreSQL. Cada fix cubre commit/rollback, repetición y carrera realista.
- **Lote #1706 — [ROOT CAUSE][TRANSVERSAL] Extender garantías append-only e inmutabilidad a toda la evidencia:** #1733, #1751, #1865, #1877, #1987, #2078.
- **Lote #2208 — Consolidación causa-raíz: Contrato de evidencia de auditoría: escritura atómica, cobertura de campos y actor:** #1794 ❌ QA1/QA2 rechazan cobertura de rollback; #1854 ❌ QA1/QA2 rechazan auditoría y datos heredados; #1863 ❌ QA1/QA2 rechazan snapshot incompleto; #2137 ❌ QA1/QA2 rechazan snapshot/enlaces y cobertura.
- **Lote #2210 — Consolidación causa-raíz: Integridad referencial: FK desactivada y guards de uso/eliminación no replicados:** #1779 ✅ QA1/QA2 aprueban localmente; no se cambia la etiqueta.
- **Lote #2219 — Consolidación causa-raíz: Contrato de driver/base Tier-1 (portabilidad SQLite↔PostgreSQL y deploy):** #1731, #1738, #1851.
- **Lote #2220 — Consolidación causa-raíz: Idempotencia y guards de entorno en seed/bootstrap:** #1848, #2168.
- **Lote #2229 — Consolidación causa-raíz: Invalidación de caché al mutar datos maestros:** #1677, #1900.
- **Lote #2232 — Consolidación causa-raíz: Verificación de idempotencia por clave (mutable o sin comparar contenido):** #1815, #1836.
- **Lote #2234 — Consolidación causa-raíz: Contrato de migraciones de esquema sobre bases con datos:** #1849, #1898.

### Fase 3 — Entradas, maestros y contratos de API

- **Lote #1650 — Consolidación causa-raíz: coerción de Decimals en la frontera de entrada:** #1196, #1663, #1741, #1746, #1831, #1864, #1972, #1984, #2108, #2132.
- **Lote #1652 — Consolidación causa-raíz: contrato de lectura tabular en imports:** #1385, #1765.
- **Lote #1716 — [ROOT CAUSE][TRANSVERSAL] Guard de vigencia: is_active verificado al usar, no solo al crear:** #1823, #1839, #1927, #1979, #1982, #2002.
- **Lotes por dominio — #1717 ([ROOT CAUSE][VALIDACIÓN] Validación server-side de dominio en escrituras (formularios CRUD y enums)):**
  - Ventas/compras/documentos: #1520, #1760, #1947, #1978, #2056.
  - Maestros/admin/API: #1347, #1579, #1722, #1766, #1768, #1769, #1913, #1929, #1962, #1994, #1995.
  - Contabilidad/bancos/tesorería: #1083, #1088, #1742, #1914, #1922, #1933, #1974, #1980, #1983, #2139.
  - Inventario/UOM/cuentas: #1747, #1764, #1826, #1829.
  - **Salida:** rechazo consistente en ruta y servicio; pruebas con referencias inexistentes/ajenas, enums, estados y valores límite. No inferir reglas que el issue no define.
- **Lote #1718 — [ROOT CAUSE][IMPORTS] Paridad de validación y ciclo de vida de lotes de importación:** #1198, #1203, #1476, #1528, #1537, #1966, #2074.
- **Lote #2205 — Consolidación causa-raíz: Canonización de sentinelas de entrada (booleanos, 0/NULL, texto vacío):** #1483, #1555, #1556, #1720, #1723, #1806, #1924.
- **Lote #2207 — Consolidación causa-raíz: Traducción de errores de dominio/registros inexistentes a 400/404:** #1465, #1787, #2109.
- **Lote #2211 — Consolidación causa-raíz: Edición con reconstrucción de payload que descarta campos:** #1790, #1818, #1822, #1825, #1834.
- **Lote #2213 — Consolidación causa-raíz: Contratos de unicidad de negocio (scope, dimensiones, defaults):** #1340, #1681, #1687, #2169.
- **Lote #2214 — Consolidación causa-raíz: Parseo de líneas por índices contiguos descarta filas posteriores:** #1039, #1788, #1871.
- **Lote #2216 — Consolidación causa-raíz: Fallback silencioso ante entradas inválidas en lecturas/reportes:** #1350, #2192, #2194.
- **Lote #2217 — Consolidación causa-raíz: Resolución canónica de fechas/hora en UTC:** #1390, #1514, #1671.
- **Lote #2221 — Consolidación causa-raíz: Validación de dominio en parámetros de lectura:** #1866, #1904, #1969.
- **Lote #2226 — Consolidación causa-raíz: Mutación de configuración sin validar estados in-flight:** #1498, #1724.
- **Lote #2235 — Consolidación causa-raíz: Hidratación de cabecera en formularios con campos bloqueados:** #1874.

### Fase 4 — Invariantes contables y ciclo documental

- **Lote #1654 — Consolidación causa-raíz: lecturas de saldo sin filtro de libro (multilibro):** #2118 y standalone #1025.
- **Lote #1655 — Consolidación causa-raíz: resolver único de moneda y tasa histórica:** #1793, #1817, #1861, #1873, #1879, #1886, #1942, #2015, #2040, #2043, #2107.
- **Lote #1656 — Consolidación causa-raíz: invariantes del ciclo fiscal (año/período/cierre):** #1773, #1786, #1941, #1952, #1954, #1955, #2185.
- **Lote #1707 — [ROOT CAUSE][FISCAL] Contrato canónico del motor fiscal: una sola base para preview, persistencia y posteo:** #1745, #1757, #1911, #1943, #2020, #2058.
- **Lote #1708 — [ROOT CAUSE][TRANSVERSAL] Unificar máquina de estados documental: aprobaciones, anulaciones y transiciones:** #444, #1423, #1539, #1592, #1749, #1799, #1804, #1807, #1809, #1812, #1897.
- **Lote #1709 — [ROOT CAUSE][R2R] Contrato de cortes históricos: fecha efectiva as-of, reversas y saldo de apertura:** #1132, #1134, #1774, #1830, #1970, #2120, #2190.
- **Lote #2223 — Consolidación causa-raíz: Posteo sin guard de evidencia mínima (conjunto vacío o config faltante):** #1105, #1819.
- **Lote #2233 — Consolidación causa-raíz: Paridad de validación entre caminos paralelos de cálculo/posteo:** #1824, #1892.

### Fase 5 — Subledgers y flujos operativos

- **Lote #1651 — Consolidación causa-raíz: canonización de UOM y cantidad base entre flujos:** #841, #1810, #1847.
- **Lote #1657 — Consolidación causa-raíz: saldos derivados desincronizados en transiciones de documento:** #1264, #1559, #1728, #1770, #1872, #2099.
- **Lote #1713 — [ROOT CAUSE][TRANSVERSAL] Identidad de línea: DocumentRelation y consumo pendiente como única fuente de matching:** #1522, #1550, #1617, #1754, #1802, #1893, #1894, #1895, #2122, #2127.
- **Lote #1714 — [ROOT CAUSE][AR/AP] Contrato canónico de open items: subtipo, línea, dirección y corte:** #999, #1069, #1126, #1227, #2073.
- **Lote #1715 — [ROOT CAUSE][INVENTARIO] Contrato de valoración: rebuild no destructivo, costos capitalizados y capas en fecha:** #1726, #1727, #1759, #1858.
- **Lote #1719 — [ROOT CAUSE][DOCUMENT FLOW] Contrato del árbol documental: tipos de nodo, límites, búsqueda y cierre:** #1578, #1860.
- **Lote #2206 — Consolidación causa-raíz: Contrato de autoconciliación bancaria (reglas, filtros y ejecución):** #1080, #1081, #1470, #1504, #1508, #1509, #1644, #1721.
- **Lote #2215 — Consolidación causa-raíz: Contrato de alertas de reposición (umbral, predicado y faltante):** #1128, #1349, #1587.
- **Lote #2218 — Consolidación causa-raíz: Semántica de duplicación/copia de documentos:** #1618, #1798, #1821.
- **Lote #2224 — Consolidación causa-raíz: Método de observación de rotación de inventario:** #1129, #1246.
- **Lote #2225 — Consolidación causa-raíz: Vinculación física de crédito/devoluciones y facturas:** #1138, #1220.
- **Lote #2227 — Consolidación causa-raíz: Contrato de relaciones N:M documentadas (estado por vínculo, scalar_one):** #1551, #1734.
- **Lote #2230 — Consolidación causa-raíz: Invariantes de consistencia con origen/configuración validadas solo aguas abajo:** #1739, #1755.
- **Lote #2236 — Consolidación causa-raíz: Guard de stock negativo por lote:** #1876, #1878.

### Fase 6 — Reportes y experiencia de usuario

- **Lotes UI por subcontrato — #1711 ([ROOT CAUSE][FRONTEND] Contratos de interfaz: i18n, Alpine, endpoints y CSRF):**
  - seguridad: #1743, #1859, #1867, #1908, #1985.
  - traducción: #1740, #1782, #1814, #1838, #1843, #1885, #1907, #1912, #1918, #1932, #1953, #1963, #1964, #1968, #1996, #1999, #2007, #2022, #2054, #2065, #2154.
  - listas: #1792, #1935, #1936, #1939, #1975, #2042, #2050, #2055.
  - formularios y flujos: #1567, #1735, #1775, #1780, #1791, #1795, #1808, #1842, #1850, #1855, #1870, #1875, #1883, #1884, #1887, #1889, #1921, #1944, #1946, #1949, #1951, #1956, #1959, #1960, #1961, #1976, #1977, #1981, #1990, #1993, #2004, #2005, #2016, #2017, #2024, #2025, #2026, #2031, #2038, #2041.
  - Referencia fuera del tope de subissues: #2193 (traducciones). Añadirla a los commits del componente correspondiente.
  - Separar commits por componente/flujo si no comparten plantilla o contrato. Corregir el backend antes de UI salvo que la pantalla bloquee el flujo o exponga datos.
- **Lote #1712 — [ROOT CAUSE][FRONTEND] Invalidación de respuestas async: request-id/snapshot en todos los flujos:** #1862.
- **Lote #2212 — Consolidación causa-raíz: Contrato de filtros de listado (persistencia al paginar y por doctype):** #2141.
- **Lote #2222 — Consolidación causa-raíz: Precisión/formato numérico derivado de Currency.decimals en frontend:** #2090.
- **Lote #2228 — Consolidación causa-raíz: Grano/clave de agregación en reportes y KPI:** #1619, #1620.
- **Lote #2237 — Consolidación causa-raíz: Plantillas compartidas con contexto por registro:** (hijos cerrados en GitHub).
- **Lote #2239 — Consolidación causa-raíz: Render del árbol jerárquico preserva el DOM del template:** (hijos cerrados en GitHub).

## Issues standalone: añadirlos al flujo consumidor

- **Contabilidad, R2R y recurrentes:** #647, #1025, #1042, #1084, #1783, #1837, #2189, #2191, #1150, #1151, #1816.
- **O2C/S2P y documentos:** #1041, #1079, #2148, #1226, #1805, #1801.
- **Inventario y tesorería:** #1827, #1729, #1067, #1303, #1832.
- **Plataforma, UI, operación y documentación:** #1679, #1856, #2177, #2019, #1844, #1905, #1370, #1967, #2001, #2106, #1748, #1029.

## Issues accionables adicionales por fase

Ejecutar estas tareas junto con los lotes de la fase consumidora. La columna de coordinación indica el paraguas documentado en los vínculos o comentarios existentes; «Consumidor» identifica una tarea standalone de esa fase. #1658 coordina features distribuidas entre consumidores y no introduce una fase posterior. Los trackers y paraguas nunca se toman como fixes independientes aunque tengan `needs-work`.

### Fase 1 — Acceso, aislamiento y seguridad

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #998 | #1649 | ✅ Email-info, listado y descarga de aliases de venta/compra cubiertos con alcance, subtipo y no lectura de archivos denegados; QA1/QA2 aprueban; commit `1da1ee73`; GitHub: fix-proposed | API: validar permisos en alias de notas documentales |
| #1019 | #1649 | ✅ Regresiones HTTP de destino, líneas y cierres con controles positivos; QA1/QA2 aprueban; commit `6b8d9ad8`; GitHub: fix-proposed | API document-flow: la autorización cubre solo el documento de cabecera; las líneas y la compañía destino se escapan |
| #1021 | #1649 | ✅ Regresión GET/POST 403 y ausencia de efectos secundarios; QA1/QA2 aprueban; commit `16eac22f`; GitHub: fix-proposed | Setup: el asistente solo requiere login; cualquier usuario autenticado cambia idioma/regional global y crea compañías |
| #1181 | #1649 | ✅ Vínculo CompanyParty activo requerido; QA1/QA2 aprueban; commit `4eca88fb`; GitHub: fix-proposed | Restringe detalle de artículos a compañías autorizadas |
| #1253 | #1649 | ⚠️ Implementado; evidencia y regresión en `b0d9003a`, `f995e0e0`; GitHub: needs-work | Define el alcance de lotes entre compañías |
| #1283 | #1658 | ✅ Regresión específica impide reintroducir los helpers retirados; QA1/QA2 aprueban; commit `914738f5`; GitHub: fix-proposed | Elimina helpers de terceros sin llamadores y protege el contrato de retiro |
| #1299 | #1658 | ✅ Retirada la rama y documentación de moneda por tercero; regresión cubre precedencia y rechazo de sustitución; QA1/QA2 aprueban; commit `ddfe074f`; GitHub: fix-proposed | Retira o integra preferencias CompanyParty sin consumidores |
| #1301 | #1649 | ✅ Ciclo HTTP de imagen global con lector/editor sin `UserCompanyAccess`; QA1/QA2 aprueban; commit `f63eb9f4`; GitHub: fix-proposed | Guard sigue la decisión de imagen global y cubre lector/editor sin asignaciones |
| #1332 | #1649 | ⚠️ Parcial: recepción de compra cubierta; Orden de Venta → entrega en conflicto sin resolver con #1515; GitHub: needs-work | Alinea permisos de líneas en flujos de inventario |
| #1338 | #1649 | ⚠️ Fix parcial en `cbac6457`: query tools rechazan compañías deshabilitadas; sigue el bypass admin de `exige_acceso_compania`; GitHub: needs-work (triage 2026-11-20) | Rechaza compañías deshabilitadas en query tools |
| #1354 | #1710 | ✅ QA1/QA2 local aprueban HEAD `45e38f2b`; GitHub: needs-work, sin cambiar estado | [Seguridad] Rechaza JWT y sesiones de usuarios deshabilitados |
| #1357 | #1658 | ✅ QA1/QA2 local aprueban el retiro en `a93657fa`; búsqueda sin consumidores; GitHub: needs-work, sin cambiar estado | [Auditoría] Elimina el blueprint admin sin rutas |
| #1433 | #1649 | ✅ Precheck bloquea una tercera alta ante duplicados históricos con clave nula usando la normalización Python, sin reescribir filas; QA1/QA2 aprueban; commit `8f0c2149`; GitHub: fix-proposed | Valida claves normalizadas y grupos históricos activos entre compañías |
| #2060 | Consumidor | ❌ QA1/QA2 rechazan independientemente la re-revisión local; GitHub `needs-work` intacto | El badge filtra por compañías del módulo accounting y estado, pero no aplica permisos/policy/nivel de `can_approve` ni `review_is_allowed`; puede sobrecontar solicitudes no visibles y omitir aprobables de otros módulos. Test solo compara compañías |

### Fase 2 — Persistencia y garantías transversales

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #759 | #1706 | 🟡 **EN CURSO — tomado por Implementador**. Parcial en `cd1aa5d4`, `c812a0da`; 127 pruebas dirigidas acumuladas (32 en confirmación de saldos). GitHub: needs-work. | HIGH: Extender garantías append-only; quedan decisiones sobre diario draft y valoración (#651). |
| #923 | #1706 | ✅ `5fb3e5f8` + `0181df55`: FK RESTRICT en esquema nuevo y evidencia preservada; 91 passed, 1 skipped; GitHub: fix-confirmed. Sin migraciones por alcance pre-alpha. | [HIGH][S2P][O2C][Append-only] DocumentRelation y conciliaciones permiten reescritura sin auditoría |
| #925 | #1706 | ✅ `5fb3e5f8`: cancelación de ledger limitada a servicios auditados, con lápida monotónica y regresiones Desktop/Cloud; 91 passed, 1 skipped; GitHub: fix-confirmed | [MEDIUM][Append-only][Accounting] Impedir reactivar asientos mediante is_cancelled=False |
| #1002 | #1706 | ✅ `5fb3e5f8`: UPDATE/DELETE de auditoría bloqueados en Desktop/Cloud por ORM/Core/SQL; 91 passed, 1 skipped; GitHub: fix-confirmed | Audit: impedir borrar la cadena en modo Desktop |
| #1093 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | Código bloquea y revalida, pero falta regresión de doble reembolso multi-sesión PostgreSQL Tier 1 |
| #1094 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | Servicio serializa y tiene unique; falta prueba multi-sesión PostgreSQL, actual es SQLite-only |
| #1139 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | El servicio serializa por factura y bloquea líneas, pero falta prueba con interleaving de dos transacciones PostgreSQL |
| #1177 | #1653 / #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | La reversa de recepción se interpreta como entrega y el estado final de transferencias depende del orden de movimientos |
| #1178 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | Estado serial se lee y actualiza sin lock; falta regresión de doble salida en PostgreSQL |
| #1266 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Lock y rollback están, pero falta restricción única persistida/migración en `PettyCashExpense.voucher_id` y prueba concurrente PostgreSQL del escenario |
| #1271 | #1653 | ✅ QA1/QA2 aprueban estáticamente; GitHub: needs-work, etiqueta intacta; pendiente QA3 | Evita ajustes duplicados en conciliación de caja chica |
| #1294 | #1658 | ✅ QA1/QA2 aprueban localmente en `45e38f2b`; GitHub: needs-work intacto tras QA3 previo | Función retirada; el test trackeado ya está presente en HEAD local, pendiente aceptación QA3/remota |
| #1306 | #1653 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | Validación y actualización de serial siguen sin lock/revalidación dentro del posteo |
| #1318 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | Helper retirado, pero el modelo y reporte aún exigen diagnosticar/migrar filas legacy; falta estrategia de datos verificable |
| #1683 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | Modelo y MUTABLE_STATE ya limpios, pero no existe migración Alembic efectiva ni prueba de upgrade existente según ADR #1898 |
| #1684 | #1658 | ❌ QA1/QA2 rechazan; persisten tres synonyms de `ARAPLedgerEntry` sin consumidor ni prueba contractual; GitHub: needs-work, etiqueta intacta | Retira los aliases restantes sin consumidores y los fija en prueba de contrato |
| #1689 | #1653 | ❌ QA1/QA2 rechazan; lock presente, regresión ThreadPoolExecutor no determinista en SQLite; GitHub: needs-work, etiqueta intacta | Evita sobreasignar factura concurrentemente con carrera real y prueba discriminante PostgreSQL |
| #1697 | #1653 | ❌ QA1/QA2 rechazan; carrera de sal SMTP y DDL de arranque en conflicto con Alembic aprobado #1898; GitHub: needs-work, etiqueta intacta | Claves únicas, escritura atómica de todos los callers y upgrade versionado de bases existentes |
| #1853 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][REFACTOR] Config mypy diverge: .mypy.ini sombreado por pyproject.toml |
| #1987 | #1706 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work intacto | Asociación append-only y pruebas presentes; falta migración Alembic efectiva para la tabla nueva según #1898 |
| #2078 | #1706 | ✅ QA1/QA2 aprueban localmente en `45e38f2b`; test trackeado en HEAD; GitHub/etiqueta intactos | Bloquea escrituras si la cadena hasheada carece de cabeza terminal; QA1 deja corrupción desconectada con cabeza válida como endurecimiento fuera de alcance |

### Fase 3 — Entradas, maestros y contratos de API

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #547 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][Importaciones] Acepta moneda inactiva |
| #1030 | #1652 | ❌ QA1/QA2 confirman QA3: blancos solo con espacios fallan y separadores mixtos mal agrupados se aceptan; GitHub: needs-work, etiqueta intacta | Importación bancaria: rechazar importes ambiguos/mal agrupados y tratar blancos opcionales como ausentes |
| #1031 | #1652 | ❌ QA1/QA2 confirman QA3: `preview()` propaga errores del lector y ficha de lote corrupto puede devolver 500; GitHub: needs-work, etiqueta intacta | Importación: hacer visible el error y recuperable el lote cuando falla lectura |
| #1032 | #1652 | ❌ QA1/QA2 confirman QA3: cancel_requested tras último check deja el lote en estado 4 y sin test vigente; GitHub: needs-work, etiqueta intacta | Toda cancelación aceptada termina en estado terminal 8, incluidos lotes vacíos y ventana de finalización |
| #1046 | #1658 | ❌ QA1/QA2 rechazan: persisten shim, plantilla sin caller y helpers del parser antiguo; GitHub: needs-work, etiqueta intacta | Retirar residuo del importador CSV; mantener adapter y servicios activos de matching/autorreconciliación |
| #1053 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación: preservar relaciones por línea origen |
| #1054 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación: validar campos de cabecera agrupados |
| #1055 | #1652 | ❌ QA1/QA2 confirman QA3: XLS omite datemode 1904; el TabularBook local convierte serial a texto; GitHub: needs-work, etiqueta intacta | Normalizar fechas Excel/XLS con época del workbook antes de validar periodo |
| #1057 | #1652 | ❌ QA1/QA2 rechazan: validate_document no valida proveedor y build permite terceros inactivos/no hallados; GitHub: needs-work, etiqueta intacta | Importación de órdenes: validar proveedor existente, activo y con rol |
| #1059 | #1652 | ❌ QA1/QA2 rechazan; decisión aprobada 6716234735 pero el adaptador ignora impuesto y no calcula/persiste impuestos; GitHub: needs-work, etiqueta intacta | Aplicar plantilla fiscal, comparar observado, calcular omitido y persistir resultado en orden/línea |
| #1060 | #1652 | ❌ QA1/QA2 rechazan en HEAD `45e38f2b`; GitHub: needs-work, etiqueta intacta | Importaciones no validan actividad/rol de Item ni UOM activa en rutas afectadas; faltan regresiones de ventas, compras y UOM inactiva |
| #1062 | #1658 | ❌ QA1/QA2 rechazan en HEAD `45e38f2b`; GitHub: needs-work, etiqueta intacta | Falta checkpoint/idempotencia para reanudar tras commit parcial; estado 7 no ofrece acción y `detail()` vuelve a parsear la fuente fallida |
| #1063 | #1652 | ❌ QA1/QA2 rechazan en HEAD `45e38f2b`; GitHub: needs-work, etiqueta intacta | Normalizar padre vacío a NULL y validar/resolver jerarquía activa, de grupo, misma compañía e intraarchivo antes de persistir |
| #1087 | #1650 | ❌ QA1/QA2 rechazan en HEAD `45e38f2b`; GitHub: needs-work, etiqueta intacta | Se rechaza >4 decimales, pero el Decimal aceptado no se cuantiza a escala 4 antes de búsqueda/identidad/persistencia; faltan pruebas de reimport equivalente y PostgreSQL |
| #1174 | #1650 | ❌ QA1/QA2 rechazan; GitHub: needs-work, etiqueta intacta | Parser/servicio rechazan no finitos, pero helper lanza antes de handlers en POST alta/edición; además `1e-10` pasa y redondea a cero en Numeric(20,9). Faltan regresiones HTTP y de representabilidad. |
| #1183 | #1717 | ✅ QA1/QA2 aprueban estáticamente en HEAD `45e38f2b`; etiqueta `needs-work` intacta | Campos vacíos no persisten, alta válida crea bodega/configuración y duplicado devuelve error controlado; queda como mejora una prueba HTTP de usuario no-admin y compañía ajena |
| #1184 | #1717 | ✅ QA1/QA2 aprueban estáticamente en HEAD `45e38f2b`; etiqueta `needs-work` intacta | Unidad vacía y presupuesto `abc` no persisten; unidad válida y presupuesto decimal exacto cubiertos; jerarquía de otra compañía se rechaza |
| #1185 | #1650 | ❌ QA1/QA2 rechazan por cobertura HTTP incompleta; GitHub: needs-work, etiqueta intacta | Coerción compartida ahora convierte parseo inválido a ValueError y callers lo capturan; falta regresión para alta de conciliación de caja chica y demás consumers/campos |
| #1197 | #1652 | ❌ QA1/QA2 rechazan; GitHub: needs-work, etiqueta intacta | Adapter copia texto y `_normalize_line()` usa `bool()`, por lo que false textual es True; no hay pruebas. Diff local rechaza cabecera extra pero no ofrece coerción solicitada ni corrige consumers centrales |
| #1199 | #1658 | ❌ QA1/QA2 rechazan: adaptador huérfano y pruebas siguen en árbol; GitHub: needs-work, etiqueta intacta | Retirar archivo y tests directos del adaptador no registrado; asegurar tests del activo. Contrato fiscal aprobado #1059 requiere integración separada antes de declarar paridad funcional |
| #1200 | Consumidor | ❌ QA1/QA2 rechazan: validation/execute preflight rechazan, pero `_execute_task()` carece de guard tras su segunda lectura; GitHub: needs-work, etiqueta intacta | Probar worker ante fuente vacía entre preflight y proceso; nunca completar con cero documentos |
| #1201 | Consumidor | ❌ QA1/QA2 rechazan: XLSX nativo ya normaliza, XLS sigue convirtiendo serial a texto y omite datemode; faltan fixtures 1900/1904 y recorrido a consumer; GitHub: needs-work, etiqueta intacta | Normalizar fechas nativas XLS/XLSX al mismo contrato y preservar época de workbook |
| #1204 | #1718 | ❌ QA1/QA2 rechazan; GitHub: needs-work, etiqueta intacta | API calcula consumo con `max(..., 0)` pero omite rechazar `discount + gain_loss >= allocated`; servicio de aplicación sí lo rechaza; faltan bordes igualdad/exceso |
| #1205 | #1718 | ❌ QA1/QA2 rechazan; GitHub: needs-work, etiqueta intacta | Cada fila compara saldo inicial; faltan acumuladores por pago/documento y tests múltiples de prevalidación vs apply |
| #1206 | #1652 | ❌ QA1/QA2 rechazan: endpoint sigue haciendo `list(worksheet.iter_rows())` antes de límites; el XLSXReader limitado no se usa y no hay prueba endpoint con dimensión inflada; GitHub: needs-work, etiqueta intacta | Aplicar límites de filas/columnas durante lectura en `/parse-xlsx`, sin confiar en dimensión declarada |
| #1212 | #1717 | ❌ QA1/QA2 rechazan; GitHub: needs-work | Rechaza filas duplicadas por artículo y bodega en conciliación |
| #1225 | #1717 | ❌ QA1/QA2 rechazan; GitHub: needs-work | Rechaza tipos desconocidos en facturas de venta |
| #1262 | #1652 | ❌ QA1/QA2 rechazan; GitHub: needs-work | Unifica deteccion de duplicados bancarios |
| #1263 | #1650 | ❌ QA1/QA2 rechazan; GitHub: needs-work | Rechaza tolerancias negativas de matching |
| #1265 | #1716 | ❌ QA1/QA2 rechazan; GitHub: needs-work | Filtra cuentas inactivas en setup de caja chica |
| #1291 | #1652 | ❌ QA1/QA2 rechazan; GitHub: needs-work | Seguimiento: normalización de fechas Excel en importaciones |
| #1292 | #1650 | ❌ QA1/QA2 rechazan por cobertura contractual; GitHub: needs-work | Seguimiento: importes positivos en pronósticos importados |
| #1295 | #1652 | ❌ QA1/QA2 rechazan: falta guard de worker y regresiones de formatos; GitHub: needs-work | Seguimiento: rechazo de importaciones sin filas de datos |
| #1296 | #1650 | ❌ QA1/QA2 rechazan: error HTTP fuera del handler y factor no representable; GitHub: needs-work | Seguimiento: rechazo de factores UOM no finitos |
| #1300 | #1716 | ❌ QA1/QA2 rechazan: configuración y ambos postings admiten cuentas inválidas; GitHub: needs-work | Rechaza cuentas AR/AP no contabilizables |
| #1302 | #1716 | ❌ QA1/QA2 rechazan: PO ya revalida; cotización/recepción/factura conservan bypasses; GitHub: needs-work | Valida proveedor activo al aprobar factura de compra |
| #1339 | #1716 | ❌ QA1/QA2 rechazan: sin guard de alta/selector y discovery omite vigencia; GitHub: needs-work | Impide agregar valores a dimensiones inactivas |
| #1342 | #1716 | ❌ QA1/QA2 rechazan template_id entre cuentas; semántica global+cuenta pendiente, GitHub: needs-work | Valida cuenta bancaria al elegir plantilla de cheque |
| #1345 | #1652 | ✅ QA1/QA2 aprueban estáticamente; GitHub: needs-work, etiqueta intacta | ODS expande filas repetidas con límites previos y filas independientes |
| #1346 | #1652 | ✅ Regresión de clientes/proveedores/cuentas y plantilla inglesa; QA1/QA2 aprueban; commit `a70171be`; GitHub: fix-proposed | Rechazar referencias de agrupación ajenas antes de perder filas |
| #1353 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Persistencia, propagación y evaluación fiscal de categoría por línea no están implementadas |
| #1358 | #1717 | ⚠️ Implementación pendiente; GitHub: needs-work | [Auditoría] Valida el tipo de grupo de terceros al guardarlo |
| #1362 | #1717 | ⚠️ Implementación pendiente; GitHub: needs-work | [Auditoría] Valida enums en configuración de matching |
| #1373 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Limita filas XLSX antes de materializar la hoja completa |
| #1374 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza fechas inválidas en la validación de asientos importados |
| #1383 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: conserva grupo al importar terceros |
| #1389 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita insertar dos veces líneas importadas |
| #1393 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Permite corregir lotes con errores desde la interfaz |
| #1394 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta la serie elegida al importar terceros |
| #1395 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Limita la cancelación de lotes al estado procesando |
| #1396 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación ODS omite filas repetidas |
| #1397 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida líneas importadas junto al comprobante existente |
| #1398 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida acumulados de pagos en importación de conciliaciones |
| #1400 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza ZIP que no sea XLSX en el importador de líneas |
| #1401 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza múltiples hojas de líneas en XLSX |
| #1403 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza ajustes de cambio negativos al conciliar pagos |
| #1419 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Líneas de inventario aceptan tarifas Infinity |
| #1435 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importar artículos de landed cost pierde las líneas |
| #1439 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación de conciliaciones no acumula aplicaciones |
| #1446 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [API][Import] Cierra el workbook antes de borrar XLSX temporal |
| #1447 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | [API][Cash] Importación no valida tipo de pago contra referencia |
| #1448 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [UI][Sales] La importación de cotización descarta el descuento |
| #1449 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [UI][Import] El pegado acepta encabezados duplicados |
| #1450 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [UI][I2F] La importación pierde bodegas por línea |
| #1451 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [UI][Import] Se descarta la descripción importada de las líneas |
| #1452 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [UI][O2C] La importación descarta la bodega de la línea |
| #1456 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Conciliación: importador rechaza reference_id del esquema |
| #1461 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Normaliza fecha antes de crear pagos destino |
| #1469 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | [Cash] NaN provoca error 500 al conciliar pagos |
| #1471 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | [Cash] Fechas ambiguas del extracto se interpretan por orden fijo |
| #1472 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | [Imports] XLSX rechaza fecha final del período abierto |
| #1475 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | ODS: celdas combinadas desplazan datos de columna |
| #1477 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación transaccional acepta tercero de rol incorrecto |
| #1478 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación ignora encabezados distintos dentro del documento |
| #1479 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Importación de líneas pierde valores con encabezados duplicados |
| #1489 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Acepta CSV de presupuesto con BOM UTF-8 |
| #1491 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Evita validar importaciones de presupuesto vacías |
| #1500 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza montos no finitos en proyecciones manuales |
| #1505 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza importes negativos en columnas del extracto |
| #1506 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Evita interpretar fechas ambiguas del extracto |
| #1507 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Detecta transacciones duplicadas dentro del mismo lote |
| #1510 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | No deduzcas duplicados sin referencia bancaria |
| #1512 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Preservar decimales al serializar pagos en Alpine |
| #1519 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: conserva precisión al comparar ofertas |
| #1529 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Journal import validation accepts invalid dates |
| #1530 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Journal imports ignore dates that differ within a reference |
| #1531 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Transaction import templates reject their serial column |
| #1532 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Transaction imports accept parties with the wrong role |
| #1533 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Transaction imports ignore currency changes within a document |
| #1535 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Transaction imports ignore party changes within a document |
| #1536 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importaciones omiten fechas distintas por documento |
| #1538 | #1716 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación bancaria acepta cuentas inactivas |
| #1544 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Ventas y compras fallan con tarifas Infinity |
| #1568 | #1717 | ⚠️ Implementación pendiente; GitHub: needs-work | Matching acepta tipos y tolerancias fuera de rango |
| #1571 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida cantidades no finitas en precio del catálogo |
| #1603 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | El importador XLSX deja archivos temporales abiertos |
| #1612 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | La base cero de un cargo manual se sustituye por el subtotal |
| #1623 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación XLSX operativa acepta fórmulas con valores en caché |
| #1625 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importadores ODS de presupuesto y tasas fallan con odfpy |
| #1626 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación de presupuesto rechaza CSV UTF-8 con BOM |
| #1627 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación de presupuesto valida un archivo vacío |
| #1628 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación agrupa filas con cabeceras incompatibles |
| #1629 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida series y cantidades al importar documentos de inventario |
| #1631 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | Acepta CSV válidos de una columna en el fallback MIME |
| #1661 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Imports accepts unsupported record types and detail returns 500 |
| #1662 | #1652 | ⚠️ Implementación pendiente; GitHub: needs-work | CSV fallback accepts tabs that the reader cannot parse |
| #1668 | #1717 | ⚠️ Implementación pendiente; GitHub: needs-work | [Imports] Valida dominios del catálogo contable |
| #1670 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | [Line Import] La columna description se descarta |
| #1672 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | [Imports] Valida cuentas de comprobantes antes de ejecutarlos |
| #1674 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación acepta lotes vencidos en recepciones |
| #1675 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación falla con lote opcional en blanco |
| #1676 | #1718 | ⚠️ Implementación pendiente; GitHub: needs-work | [Imports] Normaliza moneda vacía en cuentas |
| #1688 | #1650 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza tolerancias no finitas en reglas bancarias |
| #1835 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][I2F] Editar conciliación de inventario borra las observaciones previas |
| #2009 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Price Lists: respeta casillas de venta y vigencia |
| #2010 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Price Lists: valida compañía y moneda antes de guardar |
| #2012 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | [MEDIUM][Admin] Evita resetear matching al editar |
| #2014 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | [MEDIUM][Admin] Define eliminación de reglas fiscales |

### Fase 4 — Invariantes contables y ciclo documental

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #2076 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Prueba solo dos rechazos secuenciales; falta interleaving de aprobación/rechazo en PostgreSQL y verificar que el flujo perdedor no cree solicitud nueva ni publique efectos |
| #2120 | #1709 | ❌ QA1 rechaza; QA2 aprueba alcance nominal; GitHub: needs-work, etiqueta intacta | Barrido fiscal nominal cubierto, pero `IdentifierConfigurationError` por período ausente/ambiguo se interpreta como abierto y omite la guarda de `void`; revisar fail-closed y cierre concurrente |
| #546 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][R2R][Multimoneda] Las tasas de cambio históricas pueden editarse después de ser usadas |
| #758 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | HIGH: Enforce complete source and destination currency data on every posting |
| #761 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | MEDIUM: Apply cancellation and reversal period semantics consistently to all document types |
| #961 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | AR/AP acepta tasa unitaria sin conversión válida |
| #995 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Fiscal: aplicar exclusiones sin lista de inclusión |
| #996 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Compras: incluir líneas fiscales manuales en el total |
| #1009 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Fiscal: rechazar líneas manuales negativas en el preview |
| #1011 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Fiscal: no duplicar conceptos en bases acumuladas |
| #1015 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Impuestos: validar aplicabilidad al asignar una plantilla |
| #1016 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Ventas: no mezclar moneda de lista y factura |
| #1017 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Aprobaciones: validar la acción recibida en el POST |
| #1022 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Aprobaciones: doctypes válidos quedan sin rama de envío y quedan 'Approved' en borrador para siempre |
| #1023 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Fiscal: la persistencia de líneas de impuesto sobrescribe concept_amounts y el total no se reconstruye desde las líneas canónicas |
| #1026 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Tax pricing: impuesto aditivo se calcula sobre el precio mostrado que ya contiene el impuesto incluido |
| #1027 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Retenciones: un certificado cancelado no se re-emite al re-publicar el pago y queda irrecuperable |
| #1035 | #1654 | ⚠️ Implementación pendiente; GitHub: needs-work | Caja chica: petty_cash_ledger_balance no filtra por libro y consolida el saldo duplicado |
| #1043 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Inventario: cancelar la origen queda bloqueado para siempre por capas de consumo ya revertidas |
| #1078 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Comparar ofertas en moneda funcional al autorizar excepción |
| #1082 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Autorizar transición al cerrar ajuste bancario |
| #1085 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Retirar saldos legacy del pronóstico de caja |
| #1086 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluir reversiones en el flujo real de caja |
| #1091 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Reconstruir vales y gastos pendientes al corte histórico |
| #1114 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: alinea la moneda de conciliación del GL |
| #1115 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: acumula saldo previo en el Kardex |
| #1121 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: presenta saldos bancarios en una sola moneda |
| #1122 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: conserva saldos GL antes de anulación |
| #1123 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: conserva stock histórico antes de anulación |
| #1124 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: conserva facturas en reportes históricos |
| #1149 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: aplica la frecuencia de diarios recurrentes |
| #1157 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | El cierre mensual revaloriza un período distinto |
| #1163 | #1654 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta los libros seleccionados en comprobantes |
| #1164 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida el balance de diarios con tasas por línea |
| #1165 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza monedas inactivas en líneas de diarios |
| #1166 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Permite contabilizar diarios tras aprobación |
| #1168 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye reversiones del año en el cierre fiscal |
| #1170 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Integra el cierre fiscal con la aprobación Cloud |
| #1171 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Protege las fechas de años cerrados financieramente |
| #1172 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Impide años fiscales con rangos superpuestos |
| #1209 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Permite cancelar recibo tras anular consumo de inventario |
| #1210 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | No bloquees cancelar factura por su propio costo capitalizado |
| #1211 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida costo de inventario consumido al cancelar landed cost |
| #1221 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Bloquea cancelar devolución física con nota de crédito activa |
| #1222 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Cancela asignaciones de notas de crédito sin recibo u orden |
| #1223 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida los enlaces de origen de notas de compra |
| #1224 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida los orígenes de las notas de venta |
| #1232 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Libera gastos de reposiciones canceladas |
| #1233 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Muestra proyecciones manuales sin tasa de cambio |
| #1234 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Proyecta cobros y pagos según vencimiento |
| #1235 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida moneda en matriz de conciliación |
| #1236 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye las cuentas fiscales configuradas en conciliación |
| #1237 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Aplica el rango de cuentas al presupuesto comparado |
| #1238 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta límites parciales de período presupuestario |
| #1242 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Conserva reversiones de stock en su fecha efectiva |
| #1243 | #1654 | ⚠️ Implementación pendiente; GitHub: needs-work | Concilia AR/AP con la valoración del libro seleccionado |
| #1244 | #1654 | ⚠️ Implementación pendiente; GitHub: needs-work | Define valoración de inventario por libro en conciliación |
| #1245 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye saldo inicial previo en el Kardex |
| #1248 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza períodos inválidos en reportes GL |
| #1249 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita mapeos EFE sin efecto en cuentas P&L |
| #1250 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Detecta cuentas de efectivo sin clasificar en el EFE |
| #1251 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Alinea moneda del saldo bancario reportado |
| #1252 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Separa conciliaciones bancarias de AR/AP en el reporte |
| #1257 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Valida calendarios al comparar pronosticos de caja |
| #1259 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Valida fechas de entradas del pronostico |
| #1260 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Elimina helper GL sin referencias |
| #1269 | #1654 | ⚠️ Implementación pendiente; GitHub: needs-work | Separa saldo de caja chica por libro |
| #1270 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Soporta reposición multimoneda de caja chica |
| #1273 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Impide cancelar un vale con gasto contabilizado activo |
| #1274 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Resta las reglas fiscales configuradas como descuento |
| #1275 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Conecta affects_settlement al cálculo de pago y cobro |
| #1276 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Alinea los flags de inventario de reglas fiscales |
| #1281 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta la moneda de la lista al validar precios de venta |
| #1287 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza contabilizaciones fuera de un período |
| #1293 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita reutilizar números al retroceder la fecha de posting |
| #1297 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Aplica la plantilla fiscal configurada para el tercero |
| #1311 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta la fecha de corte al calcular saldo FX |
| #1312 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza períodos deshabilitados en revaluación FX |
| #1314 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Elimina constante sin uso en revaluación cambiaria |
| #1315 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Lista cierres fiscales desde el modelo equivocado |
| #1317 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Permite conciliar la pata destino multimoneda |
| #1323 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Convierte la fecha antes de consultar la tasa del pago |
| #1324 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita asumir NIO sin moneda funcional |
| #1325 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Advierte flujos omitidos por falta de tipo de cambio |
| #1337 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Conecta las dimensiones analíticas con el ledger GL |
| #1341 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye saldo inicial en balanza de query tools |
| #1348 | #1709 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Apertura previa, reversas con fecha efectiva y acumulado separado por cuenta |
| #1352 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Retirar helper sin caller y corregir documentación que afirma persistencia/uso de snapshot |
| #1359 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Integración dinámica ausente; revertir dirección local de retiro del modelo conforme a la decisión vigente |
| #1361 | #1658 | ✅ QA1/QA2 aprueban estáticamente el retiro en `a93657fa`; GitHub: needs-work, etiqueta intacta | `SPECIAL_ACCOUNT_TYPES` sin referencias; contratos activos de tipos de cuenta conservados |
| #1364 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Guard de adjudicación existe; faltan regresiones y rechazar quotes con ronda inválida/nula |
| #1365 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Cierre aún cuenta ofertas canceladas/no aprobadas en comparativos finalized/used |
| #1367 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Excepción aún acepta espacios y no conserva motivo/actor en la orden |
| #1368 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Seguimiento: conectar dimensiones analíticas con el ledger GL |
| #1372 | #1656 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Fecha fiscal parcial se acepta y se reemplaza por calendario sin aviso |
| #1375 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Guard final ya incluye las cuatro notas, pero falta regresión vigente y las notas de compra omiten importe no nulo; nota de venta solo valida origen si se informa |
| #1377 | #1709 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | KPI aún usa `include_returns=False` y `payables` filtra devoluciones; falta regresión de conciliación |
| #1378 | #1655 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Árbol reutiliza allocated en moneda ajena y total de referencias etiqueta allocated con moneda del pago |
| #1380 | #1655 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Al cambiar cuenta la UI conserva tasa positiva antigua y backend la persiste sin validar el par nuevo |
| #1381 | #1656 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | El guard secuencial existe, pero session identity stale evade aprobación concurrente; faltan Closed/Archived |
| #1382 | #1655 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | El adaptador activo pierde 0 numérico con `or` y cae a tasa histórica; faltan regresiones |
| #1386 | #1654 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Fix y regresiones principales presentes; falta regresión de libro activo de otra compañía |
| #1406 | #1654 | ✅ QA3 lo marcó fixed; GitHub: fixed (sin cambio de etiqueta en esta sesión) | `close_document_balances()` excluye destinos Draft igual que cierre por línea; test real vigente cubre 10 unidades |
| #1427 | #1655 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Tablas, pendientes y panel siguen mostrando importes sin moneda transaccional |
| #1430 | #1708 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | Clave ajena no se valida y permite persistir award finalized sin líneas |
| #1432 | #1708 | ✅ QA1/QA2 aprueban localmente; GitHub: needs-work, etiqueta intacta | `closed` es terminal bajo lock compartido; tests vigentes cubren servicio, POST, cierre repetido y errores |
| #1434 | #1709 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work, etiqueta intacta | KPI cuenta todo docstatus=1 sin status ni pendientes; reproducción sigue vigente |
| #1436 | #1707 | ✅ QA1/QA2 aprueban rechazo del método no soportado; GitHub: needs-work, etiqueta intacta | UI/config, motor y snapshot rechazan `quantity`; no queda cero silencioso |
| #1437 | #1707 | ❌ QA1/QA2 rechazan; GitHub: needs-work (sin cambios) | Notas de crédito muestran preview fiscal de factura |
| #1438 | #1655 | ❌ QA1/QA2 rechazan; GitHub: needs-work (sin cambios) | Preview de factura de compra usa NIO en vez de su moneda |
| #1440 | #1655 | ❌ QA1/QA2 rechazan; GitHub: needs-work (sin cambios) | Saldo de pagos previos se duplica al prorratear |
| #1441 | #1707 | ❌ QA1/QA2 rechazan; GitHub: needs-work (sin cambios) | Asiento fiscal omite impuestos sin cuenta configurada |
| #1465 | #2207 | ❌ QA1/QA2 rechazan; GitHub: needs-work (sin cambios) | Falta regresión HTTP para tipo desconocido; close-line/close-document aún pueden responder 500 |
| #1460 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Prorratea mal el valor de anticipos multimoneda |
| #1490 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Guarda cambios de libro y año fiscal del presupuesto |
| #1492 | #1658 | ❌ QA1/QA2 rechazan en re-revisión; GitHub: needs-work intacto | El test remoto está presente, pero los casos dual-positive también violan otra condición y no reproducen el defecto con totales globales balanceados; agregar regresión discriminante para creación y datos históricos |
| #1493 | #1658 | ❌ QA1/QA2 rechazan en re-revisión local; GitHub: needs-work intacto | Falta test de repetición por misma ocurrencia; tras estado `reversed`/`failed` puede propagarse IntegrityError por índice único |
| #1564 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | 9 listados aún limitan a 100 sin paginación ni total real; badges cuentan solo la página obtenida |
| #1737 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | purchase_uom/sale_uom no se cruzan con UOM base ni conversiones al crear/editar |
| #1752 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | Editar borrador ignora ID y POST crea un costo de importación duplicado |
| #1758 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | Falta test integrado persisted dims→builder→allocation y migración para cuatro columnas nuevas |
| #1811 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | El formulario de conciliación no manda moneda exigida; error controlado re-renderiza, no permite alta normal |
| #1813 | #1658 | ❌ QA1/QA2 rechazan en re-revisión local; GitHub: needs-work intacto | 3-way pasa con `require_sales_order=False` y sin OV/Nota, o con Nota no vinculada a OV; test solo invoca helper, falta regresión POST submit y prueba de no-posting |
| #1888 | #1658 | ❌ QA1/QA2 rechazan independientemente en revisión local; GitHub `needs-work` intacto | Decisión aprobada reciente: persistir/recuperar remarks y centro de costo/proyecto por línea según #1359; retirar tax payloads, ocultar/rechazar account arbitraria y campos no soportados. `StockEntryItem` carece de columnas; writer y edit renderer omiten esos valores; macro/JS aún muestran y preparan controles fiscales/dimensiones/cuenta; faltan propagación GL por línea, validación/RBAC y regresiones integradas. |
| #1891 | #1658 | ❌ QA1/QA2 rechazan independientemente en re-revisión local; GitHub `needs-work` intacto | Aunque formulario/alta rechazan `stock_adjustment` y existe test local, `/stock-entry/<id>/duplicate` copia `origen.purpose` y commitea un nuevo borrador genérico; el submit/posting aún lo admite; test no cubre duplicación histórica |
| #1915 | #1658 | ✅ QA1/QA2 aprueban estáticamente en HEAD local; GitHub: needs-work (sin cambios) | `base.ods` no tiene consumidor/documentación de uso manual; CSV operativo y flujo integrado de alta probado estáticamente |
| #1930 | #1658 | ✅ QA1/QA2 aprueban estáticamente en HEAD local; GitHub: needs-work (sin cambios) | Tamaño/orientación aplican a CSS/PDF/preview; POST inválidos de alta/edición re-renderizan sin alterar configuración |
| #1916 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | Falta migración efectiva para tablas workflow en bases existentes y queda `WORKFLOW_STATE_ID` huérfano |
| #1938 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | `show_users`/`advanced` persistidos no se restauran; falta migración de SavedReportView para DB existentes |
| #1973 | #1658 | ❌ QA1/QA2 rechazan localmente tras reevaluación; GitHub: needs-work (sin cambios) | La prueba inspecciona solo la primera llamada por template; callers posteriores no quedan protegidos |
| #1992 | #1658 | ❌ QA1/QA2 rechazan independientemente en revisión local; GitHub `needs-work` intacto | Vale omite `naming_series` aunque servicio lo acepta; gasto y reposición tampoco pasan selector ni servicio; los tres consumen default y silencian `IdentifierConfigurationError`; faltan regresiones de selección válida/inválida y contadores |
| #2061 | #1658 | ❌ QA1/QA2 rechazan independientemente en revisión local; GitHub `needs-work` intacto | `server()` solo llama el resolver si falla conexión; `verifica_coneccion_db()` trata el objeto Result como truthy aunque User no tenga filas, por lo que arranca Waitress en DB conectada sin admin; sin test de Waitress |
| #2062 | #1658 | ⏸ Revisión de alcance sin decisión funcional aprobada; GitHub `needs-work` intacto | POST delete sigue borrando `CompanyDefaultAccount`, y guard sensible lo rechaza en flush; el issue no decide entre borrado auditado, inactivación o retirar acción. AGENTS prohíbe resolver esa decisión desde QA |
| #2077 | #1658 | ✅ QA1/QA2 aprueban estáticamente en re-revisión; GitHub: needs-work (sin cambios) | Pipeline activo y regresiones de validación/almacenamiento/hash/rollback/limpieza verificados. Migración Alembic de `File.sha256` pertenece a #1898; no se cambió etiqueta ni se publicó comentario |
| #1118 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | Test cubre borrador/posteado, pero no cancelado ni total exclusivo posteado |
| #2045 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | Test HTTP solo verifica 200, no detecta si vuelve a consultarse `from_order` ni cubre origins soportados/company scope |
| #1937 | #1658 | ❌ QA1/QA2 rechazan localmente; GitHub: needs-work (sin cambios) | No existe regresión vigente con >100 filas que verifique el PDF completo; el test histórico solo mockeaba el flag |
| #1499 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye reversas de GL en el pronóstico real de caja |
| #1501 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida fechas de proyecciones dentro del año fiscal |
| #1502 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Permite conciliar reversas contabilizadas de otro período |
| #1503 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Reporta auto conciliación antes de aprobación requerida |
| #1513 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Descartar vistas previas fiscales obsoletas en pagos |
| #1523 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: respeta el corte histórico de conciliación |
| #1547 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Refleja notas aplicadas en confirmaciones de saldo |
| #1549 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Bloquea impuestos sin cuenta contable |
| #1553 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita fallos al consultar estados con historial de aprobaciones |
| #1560 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | El saldo bancario se muestra en una moneda distinta |
| #1561 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Las gráficas agrupan meses de años distintos |
| #1565 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Un rango solapado permite aprobar con un nivel inferior |
| #1566 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | El rechazo registra una regla ajena al monto |
| #1569 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | El neteo de anticipos sobreestima el importe en otras monedas |
| #1577 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita reiniciar secuencias al volver a un periodo previo |
| #1580 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida el prefijo al registrar números externos |
| #1582 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye reversiones en métricas analíticas GL |
| #1583 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye reversas en el estado de flujo |
| #1584 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza meses inválidos en retenciones |
| #1586 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Conserva saldo inicial del Kardex |
| #1589 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | Calcula saldo inicial en detalle bancario |
| #1593 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Consulta estado con varias solicitudes de aprobación |
| #1594 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Alinea motivo de excepción con recomendación por moneda |
| #1596 | #1709 | ⚠️ Implementación pendiente; GitHub: needs-work | La conciliación de caja chica no reconstruye el estado al corte |
| #1597 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | El dashboard etiqueta saldo GL base con moneda bancaria |
| #1604 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Corrige pagos con moneda distinta a la factura |
| #1605 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Maneja estado inválido al crear órdenes del comparativo |
| #1606 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | Mantiene abiertas solicitudes con órdenes parciales |
| #1607 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | Muestra en moneda incorrecta los saldos bancarios del dashboard |
| #1613 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | El estado de documento falla al conservar solicitudes de aprobación anteriores |
| #1621 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | O2C: solicitud queda abierta tras convertirse en orden |
| #1634 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | El motor fiscal aplica reglas de otros países |
| #1635 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Factura de venta acepta reglas fiscales incompatibles en el payload |
| #1636 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | El reporte suma retenciones de monedas distintas |
| #1637 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida retenciones de pago con base del cliente |
| #1638 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | El estado documental omite cancelaciones pendientes |
| #1642 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | La aprobación de anulación no cancela costos de importación |
| #1673 | #1655 | ⚠️ Implementación pendiente; GitHub: needs-work | [Imports] Balancea comprobantes usando sus tasas por linea |
| #1686 | #1707 | ⚠️ Implementación pendiente; GitHub: needs-work | [Audit][Fiscal] Consolida impuestos en un solo motor |
| #1698 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][R2R] Pasos del cierre reabren corridas cerradas |
| #1701 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][R2R] Regla Cualquiera no asigna aprobadores |
| #1702 | #1708 | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][R2R] GET sobrescribe confirmaciones respondidas |
| #1703 | #1656 | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][R2R] Colisión en número visible de confirmación |
| #1840 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | [AUDIT][R2R] El paquete accounting_engine no tiene suite de pruebas dedicada |
| #2008 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Aprobaciones: rechazo no-op tras deshabilitar motor |

### Fase 5 — Subledgers y flujos operativos

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #2098 | #1653 | ❌ QA1/QA2 rechazan; GitHub: needs-work, etiqueta intacta | Ambos caminos bloquean OC y líneas, pero la regresión 6+6 es secuencial y pasa sin locks; falta concurrencia PostgreSQL de dos aprobaciones |
| #651 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | [MEDIO][INV] Reconstrucción de capas de valuación destructiva |
| #947 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Document Flow: cantidades pendientes mezclan UOM |
| #966 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Document status: unificar cantidades base |
| #975 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Document Flow: alinear resumen de pagos al saldo canónico |
| #1034 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Inventario: convert_item_qty permite factor cero o negativo en la dirección directa (la inversa sí lo rechaza) |
| #1036 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Caja chica: expected_cash duplica los gastos posteados y reporta faltante fantasma en cajas físicamente cuadradas |
| #1037 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Reportes por item: get_purchases_by_item/get_sales_by_item suman cantidades en UOMs transaccionales distintas |
| #1038 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Reportes de transferencias: la fila reporta qty_in_base_uom etiquetada con la UOM de transacción |
| #1040 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Ventas: cancelar factura con nota de entrega asociada omite revertir relaciones y refrescar caches derivados |
| #1068 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Conciliación automática ignora saldo bancario pendiente |
| #1073 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Reconstrucción deja bins sin ledger sin corregir |
| #1074 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Eliminar compatibilidad GR/IR sin consumidores |
| #1077 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Emparejar ofertas con su línea origen de RFQ |
| #1089 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Proteger el historial al cambiar cuenta de caja chica |
| #1099 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Retira la validación monetaria de pago sin uso |
| #1100 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Elimina helpers de pagos sin referencias |
| #1102 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | No reduz saldo AR/AP por pagos en borrador |
| #1113 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: evita descontar dos veces notas aplicadas |
| #1116 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: calcula pagos en devoluciones con signo correcto |
| #1127 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: filtra documentos abiertos por saldo vigente |
| #1133 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: valida existencia de la capa en devoluciones S2P |
| #1135 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: compara cantidades de órdenes en UOM base |
| #1136 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: normaliza UOM omitida en conciliación S2P |
| #1137 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: permite devolver líneas repetidas de recepción |
| #1140 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: revalida saldo al contabilizar pagos |
| #1143 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: calcula remanente de reembolsos con signo correcto |
| #1146 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: conserva número documental al reconstruir AR/AP |
| #1147 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: respeta open item elegido al postear diarios |
| #1152 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: muestra aplicaciones recurrentes pendientes en cierre |
| #1161 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita revaluar saldos de factura ya reducidos por notas |
| #1179 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Test suite falla |
| #1180 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Congela conversiones UOM de documentos abiertos |
| #1188 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Valida fondos antes de registrar gastos de caja chica |
| #1194 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Autoconciliación bancaria registra conciliaciones pendientes como aplicadas |
| #1207 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Confirmación de saldos muestra notas de crédito ya aplicadas |
| #1214 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Impide consumir capas de inventario con fecha futura |
| #1215 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Permite conciliar inventario controlado por lote o serial |
| #1216 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye costos capitalizados de factura en devolución física |
| #1217 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Excluye landed costs anulados del costo de devolución |
| #1218 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Prorratea landed cost entre recibos parciales en devoluciones |
| #1219 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Evita duplicar costo capitalizado del recibo en devolución |
| #1228 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Recalcula estado bancario al cancelar pagos conciliados |
| #1230 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Recalcula caja chica al confirmar conciliación |
| #1239 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Integra el análisis semántico de stock negativo |
| #1255 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Calcula documentos abiertos desde su saldo real |
| #1277 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Retira o integra el helper de precio sin uso |
| #1278 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Retira o integra la tolerancia de precio sin uso |
| #1279 | Consumidor | ⚠️ Implementación pendiente; GitHub: needs-work | Prioriza la UOM específica al resolver precios |
| #1298 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Conecta la lista de compra configurada al proveedor |
| #1304 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Elimina el fallback a referencias de pago sin relación |
| #1307 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Evalúa cambio de UOM base tras movimientos anulados |
| #1308 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Elimina import legado sin uso de company_currency |
| #1310 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Excluye pagos cancelados del valor en libros AR/AP |
| #1313 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Impide cancelar la revaluación desde journal genérico |
| #1316 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Revierte la conciliación al anular su asiento GL |
| #1333 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Revalida cantidades al duplicar órdenes de compra |
| #1334 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Bloquea cambio de UOM si hay cotizaciones históricas |
| #1335 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Reconstruye también bins sin movimientos de ledger |
| #1336 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Conserva la composición FIFO al reconstruir capas |
| #1351 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Conserva liquidaciones válidas en cortes previos a cancelar el pago |
| #1363 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | [Auditoría] Normaliza eventos al reconstruir conciliación |
| #1379 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: limpia referencias al cambiar el tercero del pago |
| #1387 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Invalida los documentos fuente al cambiar el tercero |
| #1391 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Revalida capacidad fuente al aprobar documentos O2C |
| #1402 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Limpia conciliación al cambiar sus filtros |
| #1404 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Excluye referencias revertidas del saldo disponible del pago |
| #1408 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | Usa el tipo lógico de referencias de pago en el árbol |
| #1412 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | Muestra aviso de límite solo cuando haya más nodos |
| #1413 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida lotes con saldo posterior a la fecha del movimiento |
| #1414 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | La reconstrucción deja bins sin movimientos intactos |
| #1415 | #1715 | ⚠️ Implementación pendiente; GitHub: needs-work | Rebuild de capas rompe referencias de costo capitalizable |
| #1420 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Limpiar un artículo conserva y reenvía la selección anterior |
| #1421 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Limpia lote y serie al cambiar artículo |
| #1424 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | Resuelve notas de crédito por línea de origen |
| #1425 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | Calcula tarifas solo con líneas pendientes |
| #1426 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta la línea origen al asignar facturas |
| #1429 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Normaliza UOM al adjudicar ofertas |
| #1431 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | Usa relaciones para alinear líneas de ofertas |
| #1458 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Pago destino: borrador reduce saldo cacheado de factura |
| #1459 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | Cuenta en cero el remanente de reembolsos AR/AP |
| #1464 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | La búsqueda documental omite resultados tras deduplicar GL |
| #1481 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Adjudicación mezcla cantidad y precio entre unidades |
| #1482 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | Comparativo asigna cotización a línea RFQ equivocada |
| #1495 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida la dirección al aplicar anticipos |
| #1496 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida el tercero en relaciones documentales |
| #1497 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | Rechaza tipos de pago no admitidos |
| #1516 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | El flujo documental falla con 500 al apuntar a journal_entry |
| #1517 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | El árbol documental acepta límites que provocan RecursionError |
| #1521 | #1713 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: soporta devoluciones con artículos repetidos |
| #1545 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | Revisar tasa histórica en aplicaciones posteriores AR/AP |
| #1552 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | Valida el origen al cerrar saldos de flujo |
| #1570 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | La nota de débito de ventas queda como abierta sin cobrar |
| #1573 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta la línea al resolver referencias desde el ledger AR/AP |
| #1585 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | Incluye devoluciones en reportes de CxP |
| #1599 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | El dashboard cuenta órdenes completadas como abiertas |
| #1611 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Cambiar el artículo conserva requisitos de lote y serie anteriores |
| #1614 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | Respeta el corte histórico al calcular saldo AR/AP |
| #1615 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | Muestra el tipo lógico en el árbol de pagos |
| #1616 | #1714 | ⚠️ Implementación pendiente; GitHub: needs-work | Cuenta notas de débito sin factura origen en crédito |
| #1624 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | Importación cambia la UOM sin convertir la cantidad |
| #1633 | #1719 | ⚠️ Implementación pendiente; GitHub: needs-work | El árbol documental anuncia nodos omitidos al llegar exactamente al límite |
| #1639 | #1651 | ⚠️ Implementación pendiente; GitHub: needs-work | El flujo genérico omite cantidad base en líneas destino |
| #1704 | #1657 | ⚠️ Implementación pendiente; GitHub: needs-work | No persiste anticipos bancarios y bloquea su aplicación |

### Fase 6 — Reportes y experiencia de usuario

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #2065 | #1711 | ❌ QA1/QA2 confirman QA3; GitHub: needs-work, etiqueta intacta | Render real sin contaminación, pero asserts globales solo exigen ambas etiquetas; no detectan ramas booleanas invertidas por fila/columna |
| #2067 | #1711 | ⚠️ QA1/QA2 cuestionan suficiencia de cobertura; GitHub: cerrado/fixed, sin modificar | Render real aislado, pero solo cubre compra precio=percentage, compra cantidad=absolute y venta precio=absolute; faltan combinaciones restantes por campo |
| #1071 | #1658 | ❌ QA1/QA2 confirman QA3; GitHub: needs-work, etiqueta intacta | Retiro correcto; falta regresión HTTP que pruebe el contrato canónico ante `?legacy=1` |
| #1092 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Completar rutas enlazadas en lista de reposiciones |
| #1111 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: permite agregar correos en confirmación |
| #1112 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: muestra historial de confirmaciones por tercero |
| #1119 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | refactor: elimina fallbacks gettext muertos y recursivos |
| #1125 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | fix: conserva montos cero en relaciones documentales |
| #1131 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | refactor: elimina fechas inertes en consultas de lotes |
| #1213 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Descarta snapshots tardíos en conciliación de inventario |
| #1285 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Elimina o conecta la ruta de carga de adjuntos sin uso |
| #1331 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Elimina o integra el flujo de adjuntos sin uso |
| #1428 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Corrige enlaces del panel de conciliación |
| #1453 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Diario: aceptar validación obsoleta al importar líneas |
| #1454 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Diario: respuesta XLSX reemplaza líneas pegadas después |
| #1455 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Conciliación: importación XLSX pisa líneas editadas |
| #1457 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Conciliación: mostrar candidatos de filtros anteriores |
| #1463 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Limpia selectores dependientes al editar una selección |
| #1480 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Validación tardía reemplaza filas nuevas del comprobante |
| #1484 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Corrige enlaces rotos del panel de conciliación |
| #1485 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Corrige acciones rotas en listas de Caja Chica |
| #1486 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Corrige endpoint de paginación de presupuestos |
| #1487 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Registra el filtro de moneda de presupuestos |
| #1518 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | El árbol documental pierde colores de estado en inglés |
| #1554 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Conserva la búsqueda al editar una opción seleccionada |
| #1557 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | La opción Costo promedio no se traduce al inglés |
| #1574 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Traduce las etiquetas del esquema de importación |
| #1575 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Descarta respuestas de validación obsoletas del importador |
| #1581 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Corrige módulos inexistentes en herramientas de consulta |
| #1591 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | Ignora snapshots obsoletos en conciliación de inventario |
| #1609 | #1712 | ⚠️ Implementación pendiente; GitHub: needs-work | El dashboard conserva cifras tras fallar la consulta del periodo |
| #1610 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Smart select ejecuta onSelect aunque el campo esté bloqueado |
| #1622 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | [UI] Badges del flujo documental pierden estilo en inglés |
| #1632 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Actualiza selectores dependientes al cambiar compañía |
| #1643 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Vista de permisos muestra dos acciones siempre denegadas |
| #1645 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | El guardado AJAX de numeración bancaria falla por CSRF |
| #1646 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Editar caja chica ignora el nombre enviado |
| #1647 | #1658 | ⚠️ Implementación pendiente; GitHub: needs-work | Listas de caja chica usan endpoints inexistentes |
| #1648 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Importaciones: formularios POST fallan por CSRF |
| #1659 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Import wizard retains a naming series from the prior record type |
| #1666 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | [UI][Import] Etiquetas de líneas no se traducen |
| #1667 | #1711 | ⚠️ Implementación pendiente; GitHub: needs-work | Smart Select conserva listeners tras desmontarse con x-if |

## Decisiones aprobadas: contratos de implementación

Estas decisiones se consideran resueltas según los comentarios de los issues y la matriz del responsable. No son bloqueos de triaje. El trabajo es implementar, probar y documentar su cumplimiento.

| Issue | Contrato de implementación | Lote relacionado |
|---|---|---|
| #1658 | Resolver por feature: integrar las funciones aprobadas, retirar código residual y diferir solo con justificación e impacto documentados. | Distribuir hijos entre las fases consumidoras 1–6 |
| #1340 | Unicidad por tipo, valor normalizado y compañía; precedencia del valor local. | #2213 |
| #2213 | Consolidar el contrato de unicidad para códigos y valores predeterminados con la regla aprobada en #1340. | Fase 3 |
| #1105 | Bloquear recepciones valorizadas si no pueden generar una contabilización válida. | #2223 |
| #1246 | Calcular rotación con promedio de inventario ponderado por tiempo. | #2224 |
| #1891 | Los ajustes de inventario admiten únicamente ajustes positivos y negativos. | #1658; validar junto al contrato de inventario |
| #1893 | Duplicar StockEntry de forma independiente, sin heredar relaciones económicas. | #1713 |
| #1895 | Al reutilizar líneas, preservar lote, serie y vencimiento. | #1713 |
| #1897 | Bloquear la duplicación mientras la cancelación está pendiente. | #1708 |
| #1915 | Retirar el catálogo ODS obsoleto después de verificar que no tenga consumidores. | #1658, retiro de residual |
| #1916 | Retirar el modelo residual WorkflowActionLog tras verificar referencias. | #1658, retiro de residual |
| #1919 | Revocar acceso al portal cuando el tercero está inactivo. | #1649 / #1716 |
| #1930 | Aplicar tamaño y orientación de página a la salida PDF. | #1658, impresión |
| #1931 | Completar el acceso al historial de versiones. | #1658, interfaz de administración |
| #1938 | Integrar vistas guardadas reutilizables y aplicar RBAC. | #1658, R2R/UI |
| #2093 | Completar la retirada del flujo residual de comparativos de órdenes de compra. | #1658, S2P |
| #1955 | Los reportes de Kardex y bancos operan con períodos contables completos. | #1656 |

Si durante la implementación aparece una incompatibilidad real con estos contratos, registrar la evidencia y el caso concreto; no volver a poner estos issues en una fase genérica de decisión.

## Validación y cierre progresivo

- Para cada fix: pruebas reales orientadas a comportamiento; rollback, repetición, concurrencia, aislamiento de compañías, multilibro/moneda y reversión cuando correspondan.
- Tier 1 se valida en SQLite y PostgreSQL; MySQL Tier 2 también se prueba según la cadencia de integración. Desktop debe operar sin Redis. R2R consume fuentes conciliadas, no agregados sin grano definido.
- Antes de cada commit de código, ejecutar las pruebas mínimas pertinentes y los linters; cada 50 commits acumulados y antes del push, completar la ronda de workflows definida en «Ritmo de desarrollo y controles». Registrar comandos, SHA validado, resultados y bloqueos en GitHub. QA1 y QA2 revisan independientemente; conservar `needs-work` si falta cobertura o una observación sigue abierta. Solo QA3 expresamente autorizado o el administrador puede establecer `fixed`; no cerrar ni hacer push sin autorización expresa.
- La puerta Alpha de #2248 requiere recorridos O2C/S2P/I2F/CTM y R2R, migración de bases limpia/existente según modo, y limitaciones diferidas aceptadas con justificación e impacto.

### Revisión QA local — #1919 y #1931

- #1919: QA1 y QA2 rechazan. Falta revocación efectiva por `Party.is_active`/`CompanyParty.is_active`, incluso en preview/PDF. Corregir guard y cubrir listado/detalle/impresión. GitHub intacto.
- #1931: QA1 y QA2 rechazan. La ruta carga versiones, pero la interfaz las ignora y no ofrece enlace al historial. Renderizarlo bajo RBAC y agregar regresión funcional. GitHub intacto.
- #1928: QA1/QA2 rechazan. Los bloques de plantilla están corregidos, pero falta una regresión positiva de contenido para lista, formulario y settings; el test histórico citado no está en HEAD.
- #1564: QA rechaza. Los dashboards de cliente y proveedor aún limitan cada listado a 100 sin continuación y calculan conteos con las filas limitadas.
- #1950: QA1/QA2 rechazan. Los tres formularios carecen de token; el middleware global bloquea los POST y el fixture existente desactiva CSRF. Agregar token y regresiones HTTP activas/negativas por cada formulario.
- #2093: QA1/QA2 rechazan. `PurchaseOrderComparison*`, ruta/render legacy, servicio/template y test siguen en HEAD aunque se retiró el constructor; preservar `PurchaseRequestComparison` activo al completar la limpieza.
- #1162: QA1/QA2 rechazan por fix ausente. La constante solo tiene su definición en `exchange_revaluation_service.py:50`; eliminar la línea, conservar la lógica explícita de candidatos y sus pruebas existentes.
- #1882: QA1/QA2 rechazan. El template y redirect legacy siguen presentes, y el dashboard los enlaza; cambiar al asistente canónico y mantener la cobertura del pipeline bancario.
- #1899: QA1/QA2 rechazan por retiro ausente. Las tres hojas legacy no tienen consumidores; conservar `signin.css` y el CSS activo `cacaoaccounting.css`.
- #1909: QA1/QA2 rechazan. `SetupConfirmationForm` ya no existe, pero los tres forms todavía declaran `step` oculto sin consumidor; el wizard y CSRF siguen gobernados/renderizados independientemente.
- #2071: QA1/QA2 aprueban localmente el retiro presente desde `d738bcdb`; no hay referencias; dashboard y agregaciones vigentes mantienen cobertura. GitHub intacto.
- #2079: QA1/QA2 rechazan por alias aún presente en `audit_chain.py:61`. Retirar solo `_CHAIN_FIELDS`; conservar hashing heredado V1/actual V2 y reinstalar cobertura de ambos formatos.
- #2203: verificado completo localmente; macro/global retirados en `752486f1`, test estructural trackeado y QA3 cerró el issue como `fixed`. No se cambió GitHub.
- #2204: falso positivo inicial verificado; las macros compartidas restantes tienen consumidores Jinja reales, el guard estructural está versionado y QA3 cerró como `fixed`.
- #2150: completado y QA3/fixed verificado; el contrato es caller-controls-transaction y la prueba real de catálogo cubre rollback sin cuentas persistidas.
- #2147: completado localmente; link a detalle y regresión HTTP están en HEAD, QA3 autorizó `fixed` y cierre.
- #1093: QA1/QA2 rechazan. La protección del servicio parece correcta, pero la regresión concurrente vigente es SQLite-only; falta cubrir dos reembolsos simultáneos en PostgreSQL y verificar una sola nota/pago/efecto GL.
- #1094: QA1/QA2 rechazan. El lock determinista y la asociación única parecen correctos; falta regresión de reserva simultánea del mismo gasto en dos sesiones PostgreSQL.
- #1139: QA1/QA2 rechazan. El lock transaccional común de la factura y los locks de sus líneas permiten recalcular bajo serialización; la única prueba de concurrencia usa fixture SQLite y no fuerza el interleaving. Agregar regresión de dos transacciones PostgreSQL sobre recepciones distintas y una factura, verificando que la cantidad asignada nunca excede la facturada. GitHub intacto.
- #1177: QA1/QA2 rechazan. La decisión vigente (#1177/#1539) establece que cancelar una recepción no es una entrega: un serial puede recibirse de nuevo si no queda entrada activa, manteniendo unicidad y una sola ubicación. La reversa aún marca `delivered`; la cancelación de transferencia aplica varias reversas no ordenadas y puede dejar estado/ubicación incoherentes. No hay regresiones específicas. Cubrir recepción-cancelación-recepción, serial ya activo, devolución real y transferencia cancelada independiente del orden. GitHub intacto.
- #1178: QA1/QA2 rechazan. `_validate_serial()` comprueba `available` y bodega con SELECT ordinario; `update_serial_state()` vuelve a leer y mutar sin `FOR UPDATE` ni transición condicional. La unique de `SerialNumber.serial_no` evita filas duplicadas, no dos movimientos. Agregar lock/revalidación transaccional y regresión PostgreSQL multi-sesión que pruebe una salida aceptada, otra rechazada y una sola salida activa. GitHub intacto.
- #1306: QA1/QA2 rechazan. Los caminos `_create_stock_movement()` y `_outgoing_stock_values()` validan disponibilidad antes de bloquear/consumir `StockBin`, luego actualizan la fila serial sin revalidar. Falta lock de `(item_code, serial_no)` dentro de la transacción de posteo y test de doble posting concurrente con stock restante, una sola salida aceptada. Código y brecha coinciden con #1178, pero mantener criterios y seguimiento propios. GitHub intacto.
- #1318: QA1/QA2 rechazan el retiro como incompleto. El helper sin callers sí fue eliminado, pero `ReconciliationItem` aún documenta que filas legacy nullable deben migrarse y el reporte/test siguen detectando `reconciliation_item_missing_context`. Fallbacks dependen de que exista la transacción fuente; no hay backfill alternativo ni evidencia de censo/cero datos persistidos. Definir mecanismo explícito o establecer el contrato de datos legacy antes de retirar la estrategia. GitHub intacto.
- #1865: QA1/QA2 rechazan al reevaluar el contrato reciente. El test está trackeado, pero el guard rechaza hasta cambios solo de cabecera antes de comprobar las relaciones; el criterio permite guardar si conserva exactamente vínculos activos/cantidades y rechaza solo cambios/eliminaciones vinculados. Agregar caso positivo de cabecera-only y preservar rechazo/rollback de cambios de línea y cantidad. GitHub intacto.
- #1877: QA1/QA2 rechazan localmente. El test trackeado simula docstatus=1 y cambios de línea, no ejecuta `submit_document()`/`post_stock_entry()` ni rollback del savepoint. Además, el listener concede el allowance al detectar cualquier transición ORM draft→posted, no un posting autorizado, lo que abre bypass potencial del guard. Vincular la autorización al posting y probar conciliación Cloud real, edición bloqueada post-commit y limpieza en rollback. GitHub intacto.

### Revisión QA local — #1710 (continuación)

- #1732: QA1/QA2 aprueban localmente el fix de revocación administrativa: login HTTP real, invalidación de JWT/cookie previo y no resurrección al reactivar. GitHub y etiquetas intactos.
- #1917: QA1/QA2 rechazan localmente. El handler ya conserva la respuesta y setea cookie correctamente, pero falta la regresión HTTP del éxito OTP para destino, cookie, estado autenticado y destino predeterminado. GitHub y etiquetas intactos.

- #1948: QA1/QA2 rechazan localmente por test de validador retirado en `0970476b`; la dependencia está declarada y empaquetada. Falta recuperar validación inválida/vacía. GitHub y etiquetas intactos.
- #1965: QA1/QA2 rechazan localmente; el manejo `InvalidHashError` está en HEAD, pero la regresión HTTP retirada en `0970476b` no tiene reemplazo. GitHub y etiquetas intactos.
- #2023: QA1/QA2 rechazan localmente. El rollback de SMTP fallido parece preservar el token previo, pero falta prueba HTTP y un fallo de commit después de SMTP puede invalidar el enlace ya enviado. GitHub y etiquetas intactos.
- #1762: QA1/QA2 rechazan localmente por falta de regresión del endpoint. Código confirma intentos incorrectos y helper consume al límite; el test HTTP que prueba persistencia después de teardown fue retirado. GitHub y etiquetas intactos.
- #1958: QA1/QA2 rechazan localmente. El diseño conserva pending antes de SMTP, pero test de fallo de commit solo cubre reintento; falta fallo en envío inicial y destinatarios parciales. GitHub y etiquetas intactos.

### Revisión QA local — #2209

- #1923: QA1/QA2 aprueban en HEAD `45e38f2b`; el test restaurado `dfdfdf41` sí está en la rama local y cubre retorno interno, URLs externas, barras inversas/codificadas y controles. QA3 verificó ausencia en origin antes de la restauración local. GitHub/etiquetas intactos.

- #1930: QA1/QA2 aprueban localmente en HEAD `45e38f2b`; `3a81c9d2` normaliza el error y el test HTTP versionado cubre alta/edición con valores inválidos sin mutación. GitHub/etiquetas intactos.

- #1758: re-revisión QA1/QA2 rechaza localmente por cobertura de integración. La decisión funcional está aprobada; implementación guarda dimensiones y builder las propaga, pero no hay test persistido → contexto real → asignación del engine/posting. GitHub/etiquetas intactos.

- #2077: re-revisión tras QA3: no hay consenso QA1/QA2. Test restaurado cubre validación/storage/hash/rollback/cleanup y QA1 aprueba; QA2 identifica falta de POST multipart válido al endpoint consumidor activo. Registrar #1898 aparte por la columna `File.sha256`/migración. GitHub/etiquetas intactos.

- #1891: re-revisión QA1/QA2 rechaza localmente. El endpoint de duplicación copia `stock_adjustment` histórico a un draft nuevo sin usar el validator; el test de contrato no cubre el bypass. Bloquear duplicación y verificar ninguna fila nueva manteniendo consulta histórica. GitHub/etiquetas intactos.

### Revisión QA local — #1938

- QA1/QA2 rechazan en HEAD `45e38f2b`. RBAC y aislamiento actuales parecen correctos; `show_users`/`advanced` se persisten pero no se restauran desde la vista ni tienen regresión. Falta migración Alembic de `saved_report_view` conforme a #1898. GitHub/etiquetas intactos.

- #1973: re-revisión QA1/QA2 rechaza localmente por cobertura parcial: las llamadas actuales están limpias, pero test inspecciona solo el primer match por archivo; los templates con llamadas múltiples no se renderizan en los smoke tests. GitHub/etiquetas intactos.

- #1405: QA1/QA2 rechazan localmente por falta de regresión HTTP del fix actual. El handler permite origen por línea y aplica ACL de destino/fuente, pero el test de pago invoca servicio directamente; el único POST del endpoint cubre línea malformada. Agregar caso HTTP positivo y denegaciones de ACL. GitHub/etiqueta intactos.

- #1753: QA1/QA2 rechazan localmente por cobertura HTTP específica ausente. La ruta ya valida `purchases/consultar` sobre factura fuente antes de render; añadir GET positivo/negativo para controlar metadatos expuestos. GitHub/etiqueta intactos.

### Implementación local — cierre del árbol de trabajo

- #1652: contrato tabular común en `ef0cd81d`, con `TabularBook`, normalización de encabezados/celdas y fixture equivalente CSV/XLS/XLSX/ODS. Siguen abiertos los consumidores paralelos, las fechas tipadas XLS y el límite de filas XLSX previo a materializar; esta entrega no los declara resueltos.
- #1346: `d294d139` rechaza columnas ajenas al esquema antes de agrupar y prioriza etiquetas sobre aliases; `a70171be` cubre rechazo sin persistencia para los tres maestros. QA1/QA2 aprobaron y el issue quedó en `fix-proposed`.
- #2018: `41e3d615` contiene las validaciones de servicio; `9047d819` cubre alta/edición con referencias inválidas, preservación de la regla y cuenta válida en el contexto. QA1/QA2 aprobaron y el issue quedó en `fix-proposed`.
- #1998: `d7a6f549` separa `consultar` en GET de `crear` en POST y verifica vínculo activo antes de leer PII. QA1/QA2 aprobaron y el issue quedó en `fix-proposed`.
- #1926: `2725af0e` agrega regresiones HTTP de lectura de UOM por permiso de consulta. #2059/#2060: `30859cd2` comparte el predicado del badge y la bandeja de aprobaciones. #2092: `8885d843` falla cerrado cuando el documento fuente no declara compañía.
- Estado: commits locales sin push; issues #1346/#1998/#2018 abiertos en `fix-proposed`; no se cerraron issues.
