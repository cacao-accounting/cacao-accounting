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
