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

## QA1 — Refs: #2191 — needs-work

### Hallazgo bloqueante

- `cacao_accounting/api/dashboard.py::_income_expense_balances` y
  `_accounting_monthly_result` filtran filas en SQL por
  `Accounts.classification` antes de aplicar `normalize_account_classification`.
  El contrato nuevo indica que `account_type=cost_of_goods_sold` o
  `cost_of_service` determina la sección de costo aunque la clasificación esté
  vacía o sea desconocida. En esos estados válidos del contrato, el filtro
  actual elimina la fila y el dashboard omite el costo del gasto total,
  utilidad y serie mensual. La prueba cubre `classification=expense`, pero no
  el caso sin clasificación/alias desconocido con tipo de costo.
- Recomendación: ampliar el predicado para incluir explícitamente tipos de costo
  o retirar el filtro previo y clasificar con la normalización compartida; añadir
  regresión del dashboard para ambos tipos con clasificación vacía/inesperada.

### Evidencia y alcance revisado

- El cambio de `get_income_statement_report` aplica `account_type` antes de
  clasificar, conserva saldos históricos y no escribe cuentas ni asientos. Los
  catálogos base cambian solo la fila 51.01; gastos de operación conservan su
  rubro. Los tipos de costo quedan preservados por la normalización aun cuando
  las cuentas existentes mantengan `Expense`.
- Analytics y margen bruto reutilizan el resolver común. `gross_margin` conserva
  el importe histórico; el porcentaje se expone como campo/métrica adicional.
  El cálculo del caso de referencia es congruente con 600/1000 = 60 % y la
  utilidad neta 500. Budget actualiza la consulta y el signo natural de costos.
- #684 fijó exclusión de cierres fiscales y clasificación normalizada en el
  margen bruto; ambas condiciones se conservan. #982 normalizó alias usados por
  los KPIs; se preserva la normalización y se amplía a `account_type`.
- Las pruebas cubren catálogos base ES/EN, NIIF Pymes, US GAAP, bienes,
  servicios, gasto operativo, catálogos inconsistentes y métricas. No cubren la
  ruta de filtro SQL del dashboard para clasificación vacía/desconocida.

### Dictamen

QA1 rechaza la propuesta actual y recomienda `needs-work` hasta corregir el
filtrado previo del dashboard y cubrir el caso indicado. No ejecuté pruebas ni
linters, conforme al rol de revisión estática.

## QA1 — Revisión posterior — Refs: #2191 — fix-proposed recomendado

### Reevaluación

- El filtro de ambas consultas del dashboard ahora conserva las clasificaciones
  reconocidas y añade `account_type` de costo mediante `or_`; posteriormente
  ambas rutas pasan por `normalize_account_classification`. Esto atiende el
  hallazgo QA1 para clasificación vacía o desconocida sin incluir otras cuentas
  de balance sin clasificar.
- La regresión nueva incluye un costo `cost_of_service` con clasificación
  desconocida y un `cost_of_goods_sold` sin clasificación. Verifica que ambos
  aparezcan en `_income_expense_balances`, el resultado mensual y el Estado de
  Resultados. La cobertura corresponde al defecto reportado.
- La revisión visual del template confirma que las etiquetas de la nueva tasa
  porcentual se entregan por `column_labels`; la cadena visible está marcada
  para traducción en el helper y cuenta con traducción inglesa.
- No encuentro un hallazgo bloqueante pendiente en el diff actualizado. Se
  conservan los filtros de cancelados, libro y fechas, así como los cálculos de
  cierres fiscales revisados para #684. La semántica existente de `gross_margin`
  (importe) sigue intacta y el porcentaje se añade como campo/métrica separado.

### Dictamen

QA1 aprueba estáticamente el cambio actualizado y recomienda `fix-proposed`.
No ejecuté pruebas ni linters y no realicé cambios de estado en GitHub.
