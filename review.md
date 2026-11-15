# Revisión QA — Refs: #1170

## Resultado

QA1 aprobó como `fix-proposed`; QA2 confirmó como `fix-confirmed`. Ambos
realizaron revisiones estáticas independientes; ninguno ejecutó pruebas ni
linters.

## Criterios revisados

- El cierre sigue el flujo común de aprobación Cloud y no publica un asiento
  mientras la solicitud requiere otra persona.
- La propuesta y el vínculo con el cierre se guardan atómicamente. La falta de
  regla de aprobación y los fallos de persistencia no dejan borradores huérfanos.
- Los rechazos conservan la solicitud y permiten reintentar el mismo borrador
  solo si sus datos normalizados coinciden con el cálculo vigente. Se cubren
  cambios de importes, cuenta bancaria y serie de numeración.
- La aprobación revalida reversiones cruzadas. La reversa bloquea el mismo año
  fiscal antes de publicar, evitando confirmar ambos hechos en una carrera.
- La consulta de reversiones es una lectura bloqueante actual compatible con
  PostgreSQL; los pares repetidos se deduplican fuera de SQL.
- Las rutas y servicios impiden editar el asiento mientras una solicitud de
  aprobación está pendiente.
- Los casos de concurrencia se omiten en Windows. La carga diferida de WeasyPrint
  evita que un runtime PDF ausente bloquee la importación de toda la aplicación.

## Evidencia de pruebas y controles

- Implementador: 11 passed y 3 skipped en
  `tests/test_approval_workflow_preflight.py` con SQLite.
- Los 3 skips de SQLite corresponden a las pruebas que requieren `SELECT FOR
  UPDATE` real (dos concurrencias PostgreSQL/MySQL y una regresión MySQL
  `REPEATABLE READ`).
- Las cuatro pruebas PDF se omiten por runtime nativo ausente en Windows; las
  pruebas de aprobación sí se ejecutan.
- Black, Ruff, Flake8, mypy, pydocstyle y complexipy pasaron. Pylint no está
  disponible en el entorno virtual.
- QA1 aprobó `fix-proposed`. QA2 aprobó `fix-confirmed` tras revisar de forma
  independiente el bloqueo de año, el cotejo del borrador y los casos límite.

El issue #1170 sigue abierto. No se hizo commit, push ni cierre del issue.

## Revisión QA2 — Refs: #2191

### Dictamen

QA2 aprueba la implementación como `fix-confirmed` desde la revisión estática.

### Evidencia revisada

- `normalize_account_classification` da precedencia a `cost_of_goods_sold` y
  `cost_of_service`, y luego aplica la normalización de aliases existente. El
  Estado de Resultados, el reporte de margen bruto, los KPIs y el dashboard
  consumen esa misma resolución; no se reescriben cuentas ni asientos.
- `base_es.csv` y `base_en.csv` clasifican 51.01 como `Cost`, conservan su
  `account_type` y no reclasifican 51.02, 51.03 ni los gastos operativos. La
  carga de catálogos conserva ambos campos, por lo que instalaciones nuevas
  reciben el rubro y tipo esperados. Las cuentas existentes se corrigen en
  lectura por `account_type` sin migración ni modificación de historia.
- Las pruebas de regresión cubren ambos catálogos base, NIIF Pymes y US GAAP,
  costo de bienes/servicios con clasificación histórica Expense, gasto
  operativo, costo sin `account_type`, signos de presupuesto y el escenario
  1,000 / 400 / 100. Se verifican utilidad bruta 600, porcentaje 60%, utilidad
  neta 500 y consistencia del KPI. El campo existente `gross_margin` conserva
  el valor monetario; el porcentaje tiene un campo/métrica adicional.
- El cambio de #684 que excluye cierres fiscales y normaliza clasificaciones en
  `get_gross_margin` permanece intacto. El cambio de #982 que normaliza los
  KPIs se amplía con el tipo de cuenta, sin retirar sus aliases ni alterar la
  semántica de `gross_margin`.
- Los cálculos de presupuesto comparten la clasificación normalizada y
  mantienen signo deudor para costos y gastos. La opción de tipo de cuenta de
  costo de servicios queda disponible en el formulario.

### Riesgos y límites residuales

- Esta evaluación fue estática; QA2 no ejecutó pruebas ni linters, conforme al
  procedimiento. No se encontró evidencia local de cambios en #982 aparte de
  su commit; la compatibilidad se evaluó contra ese diff y sus pruebas.
- El porcentaje se define como cero cuando el ingreso es cero para evitar
  división por cero; los casos de ingresos nulos o negativos no se detallan en
  los requisitos funcionales.
- No se modificaron etiquetas ni estado de GitHub. No se hizo commit, push ni
  cierre del issue.

## Segunda revisión QA2 — Refs: #2191

### Dictamen

QA2 confirma la corrección actualizada como `fix-confirmed`. Esta revisión
reemplaza el dictamen previo para el árbol de trabajo actualizado; conserva
el registro anterior como trazabilidad.

### Revisión de los cambios posteriores

- Las consultas del dashboard ahora admiten, además de clasificaciones
  conocidas, `account_type` igual a `cost_of_goods_sold` o `cost_of_service`.
  Por ello, las filas con clasificación nula o desconocida ya no se descartan
  antes de la normalización. Ambas series agrupan por `classification` y
  `account_type`, y resuelven cada fila con la función compartida.
- La prueba del dashboard incorpora un tipo de costo de servicio con rubro
  desconocido y un tipo de costo de bienes con rubro nulo; verifica que ambos
  integran el saldo/serie y que el Estado de Resultados refleja el mismo costo.
- El campo `gross_margin_percentage` recibe etiqueta visible en el reporte y
  está marcado para traducción; `messages.po` incluye la traducción inglesa.
  Se conserva el campo monetario `gross_margin`, evitando cambio semántico del
  contrato existente.

### Evaluación final

El predicado SQL y los casos de regresión resuelven el hallazgo bloqueante de
QA1. La corrección mantiene los invariantes de lectura histórica: no modifica
cuentas, importes ni asientos. No identifico defectos bloqueantes ni riesgo
pendiente que impida aceptar el cambio. Esta revisión fue estática; no ejecuté
pruebas ni linters. No cambié etiquetas o estado de GitHub.

## QA de aislamiento de pruebas — Refs: #2190 #2191

### Dictámenes

- QA1 aprueba estáticamente el aislamiento de los escenarios.
- QA2 aprueba de forma independiente; no encontró defectos bloqueantes.

### Evidencia

- #2190 usa el libro dedicado `TB2190`; la balanza y la sábana ya no suman GL ajeno publicado en `DEFAULT_BOOK`.
- #2191 usa `FY2191`/`P2191-05` y fecha de posteo en 2091. El estado de resultados filtra por período propio y las consultas de dashboard/margen bruto filtran por fecha propia. Conserva el libro primario que esas consultas requieren.
- Los fixtures eliminan primero sus asientos y luego sus períodos, año fiscal o libro, respetando las claves foráneas. Las fórmulas contables verificadas no cambian.
- QA2 observó que el cleanup de identificadores dedicados es incondicional; no lo considera riesgo bloqueante en la base aislada por worker.

La revisión fue estática. No se modificaron etiquetas ni estado de GitHub.

## QA2 — Correcciones de CI — Refs: #1170

### Dictamen

Apruebo estáticamente los dos ajustes del árbol de trabajo como correctos para
los fallos observados. La aceptación del objetivo de CI verde queda pendiente
del resultado de una nueva ejecución en GitHub.

### Evidencia revisada

- `_PrintPDFURLFetcher` expone `_fail_on_errors = False`, propiedad que
  WeasyPrint 70 consulta al envolver errores de `url_fetcher`. La clase sigue
  rechazando esquemas, hosts y rutas fuera de `static`; el error no fatal hace
  que un recurso remoto rechazado no interrumpa el renderizado. La regresión
  existente comprueba que la solicitud HTTP no llega al servidor y que el PDF
  conserva el recurso estático local.
- El fixture de cierre usaba una única ventana contable de diciembre mientras
  insertaba el asiento fuente y creaba el borrador en junio. Ambas fechas ahora
  son 31 de diciembre, dentro del período configurado, sin cambiar las reglas
  de cierre ni el escenario de reversión al período siguiente.
- No encontré cambios en la lógica de publicación contable ni en la política de
  seguridad del fetcher. Esta revisión fue estática; no ejecuté pruebas ni
  linters. El estado final del workflow aún debe comprobarse en GitHub.
