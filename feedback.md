# Feedback de revisión — Refs: #1170

## Estado

Los hallazgos de QA1 y QA2 fueron atendidos en el árbol de trabajo. No queda
feedback técnico pendiente conocido.

## Hallazgos y resolución

- El cierre fiscal usa el motor de aprobación común; el borrador, su vínculo al
  año fiscal y la solicitud se confirman en una sola transacción.
- Las reversas bloquean el mismo registro de año fiscal que el cierre. La
  revalidación usa una lectura bloqueante actual para no reutilizar un snapshot
  antiguo en MySQL `REPEATABLE READ`.
- La lectura con `FOR UPDATE` ya no usa `DISTINCT`, por compatibilidad con
  PostgreSQL. Los pares duplicados se deduplican y ordenan en Python.
- Un borrador rechazado solo se puede reingresar si su contenido normalizado
  coincide con los saldos y la configuración de cierre recalculados. El cotejo
  incluye las líneas completas, la serie de numeración y los campos que afectan
  al GL, incluida la cuenta bancaria.
- El fixture no cambia el estado de un módulo contable ya existente. Si hay una
  colisión al crear el registro, vuelve a leerlo con `SELECT FOR UPDATE` para
  obtener el estado confirmado en MySQL.
- Las pruebas de concurrencia llevan `skipif` en Windows, según la limitación
  reportada para esa plataforma.
- WeasyPrint se importa al renderizar PDF; solo sus pruebas se omiten cuando
  falta su runtime nativo. La DLL no impide importar la aplicación ni ejecutar
  pruebas de otros módulos.

## Dictámenes

- QA1: `fix-proposed`; sin hallazgos bloqueantes en la última revisión.
- QA2: `fix-confirmed`; sin riesgos bloqueantes pendientes.

## Verificación del implementador

- `tests/test_approval_workflow_preflight.py`: 11 passed, 3 skipped en SQLite.
- El test dirigido a WeasyPrint: 4 skipped porque este Windows no tiene el
  runtime nativo de WeasyPrint.
- Black, Ruff, Flake8, mypy, pydocstyle y complexipy pasaron en los archivos
  modificados. `pylint` no está instalado en `.venv`.
- `git diff --check` pasó sobre los archivos de este trabajo; se dejaron intactos
  cambios paralelos de otros archivos.

Los tests específicos de locks de base de datos y MySQL `REPEATABLE READ` se
omiten al ejecutar contra SQLite; deben correr en PostgreSQL/MySQL CI.
