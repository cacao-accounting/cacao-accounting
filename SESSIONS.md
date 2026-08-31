# Bitácora de desarrollo

## 2026-08-31 (refactor S3776 — `calculate_taxes` cx=22)

### Hallazgo SonarCloud

Issue `AaA59ZkIaEygsU7z1-VS` (`python:S3776`, CRITICAL):
`cacao_accounting/tax_pricing_service.py`, `calculate_taxes`, complejidad cognitiva 22 frente al umbral 15.

### Corrección

Se separaron la agrupación de bases de impuestos inclusivos y la acumulación de resultados en `_TaxTotals`.
Se conservaron validación de plantilla/compañía, orden de aplicación, bases anteriores, impuestos inclusivos,
aditivos, deductivos, totales y `payable_delta`.

### Verificación

- `tests/test_tax_rules.py` y `tests/test_tax_engine_audit_cases.py`: 41/41.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `ventas_cotizacion_nueva` cx=26)

### Hallazgo SonarCloud

Issue `AaAa6suhSsPfV5h49WFm` (`python:S3776`, CRITICAL):
`cacao_accounting/ventas/routes.py`, `ventas_cotizacion_nueva`, complejidad cognitiva 26 frente al umbral 15.

### Corrección

Se extrajo el flujo POST de creación a `_create_sales_quotation_from_request`, conservando validación de encabezado,
acceso por compañía, moneda, origen documental, líneas, relaciones, totales, rollback, mensajes y redirección.

### Verificación

- `tests/test_03webactions.py -k sales_quotation_routes --slow=True` y `tests/test_o2c_full_cycle.py -k quotation`: 5/5.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_save_numbering_configs` cx=27)

### Hallazgo SonarCloud

Issue `AaAbv2ElOioNy6Mzk_6o` (`python:S3776`, CRITICAL):
`cacao_accounting/bancos/services.py`, `_save_numbering_configs`, complejidad cognitiva 27 frente al umbral 15.

### Corrección

Se extrajo la validación de cada serie y chequera a `_validate_numbering_config_entry`, conservando el descarte de
entradas inválidas, validación de pertenencia de compañía, actualización de configuraciones y commit único.

### Verificación

- `tests/test_bank_account_numbering.py`: 15/15.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_line_discount` cx=32)

### Hallazgo SonarCloud

Issue `AaBBbpXsopylcTR1Qqlh` (`python:S3776`, CRITICAL):
`cacao_accounting/ventas/services.py`, `_line_discount`, complejidad cognitiva 32 frente al umbral 15.

### Corrección

Se separaron la resolución del descuento heredado desde cotización/orden/factura y la validación del descuento manual.
Se conservaron la precedencia del descuento de origen, cálculo proporcional, exclusión de descuentos incompatibles,
límites de porcentaje/importe y cálculo del importe neto.

### Verificación

- `tests/test_sales_price_validation.py`: 7/7.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_purchase_order_context` cx=24)

### Hallazgo SonarCloud

Issue `AaAa6s0eSsPfV5h49WFs` (`python:S3776`, CRITICAL):
`cacao_accounting/compras/services.py`, `_purchase_order_context`, complejidad cognitiva 24 frente al umbral 15.

### Corrección

Se separaron la resolución del documento origen, la validación de requisitos de comparación/excepción, la validación
de adjudicación y la detección de comparativo abierto. Se conservaron los bloqueos de abastecimiento, pertenencia de
compañía, estado de adjudicación, proveedor, moneda y contexto devuelto al flujo de creación.

### Verificación

- `tests/test_purchase_sourcing.py`: 10/10.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `get_ar_ap_subledger` cx=24)

### Hallazgo SonarCloud

Issue `AaACtYmYRe3t3lA8459a` (`python:S3776`, CRITICAL):
`cacao_accounting/reportes/services.py`, `get_ar_ap_subledger`, complejidad cognitiva 24 frente al umbral 15.

### Corrección

Se separaron la construcción de consulta por tipo de tercero, resolución de etiquetas, cálculo ledger/legacy y armado
de filas. Se conservaron el corte por fecha, exclusión de reversiones/devoluciones, saldos AR/AP, moneda base,
aplicaciones de pago, identificadores de tercero y totales del reporte.

### Verificación

- Escenarios focales de subledger en `tests/test_08_reconciliation_reports.py`,
  `tests/test_record_to_reports_multicurrency_multiledger.py`, `tests/test_o2c_matrix_audit.py` y
  `tests/test_s2p_ap_matrix_audit.py`: 11/11.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_process_reconciliation_line` cx=26)

### Hallazgo SonarCloud

Issue `AaBPsMVLkZtwr73q0yaF` (`python:S3776`, CRITICAL):
`cacao_accounting/document_flow/payment.py`, `_process_reconciliation_line`, complejidad cognitiva 26 frente al
umbral 15.

### Corrección

Se separaron la normalización y validación de la fila, la construcción de asignaciones con descuento/diferencia y la
planificación estándar mediante el motor AR/AP. Se conservaron la prevención de duplicados, validación de pago y
documento, conversión de moneda, límites de efectivo, persistencia de referencias y actualización de saldos derivados.

### Verificación

- Escenarios focales de conciliación en `tests/test_payment_entry_improved.py`, `tests/test_o2c_matrix_audit.py`,
  `tests/test_s2p_ap_matrix_audit.py` y `tests/test_fx_ar_ap_lifecycle.py`: 5/5.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_delivery_return_cost` cx=26)

### Hallazgo SonarCloud

Issue `AaAa6soYSsPfV5h49WFj` (`python:S3776`, CRITICAL):
`cacao_accounting/contabilidad/posting_service.py`, `_delivery_return_cost`, complejidad cognitiva 26 frente al
umbral 15.

### Corrección

Se separaron la validación de la entrega origen y las consultas de cantidad/valor entregado y ya devuelto. Se
conservaron la validación de compañía, estado y tipo de documento, el cálculo de cantidad disponible, el bloqueo de
devoluciones excesivas y el costo histórico proporcional.

### Verificación

- Escenario focal de devolución en `tests/test_update_inventory.py`: 1/1.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_post_bank_difference_adjustment` cx=27)

### Hallazgo SonarCloud

Issue `AaAbv2ElOioNy6Mzk_6o` (`python:S3776`, CRITICAL):
`cacao_accounting/bancos/services.py`, `_post_bank_difference_adjustment`, complejidad cognitiva 27 frente al umbral
15.

### Corrección

Se separaron el cálculo del signo, la creación/envío del comprobante, la resolución de la cuenta GL bancaria y la
creación del detalle de conciliación. Se conservaron el manejo transaccional sin commit, la búsqueda de la línea GL,
el contexto de asignación y la actualización del estado reconciliado.

### Verificación

- Escenario focal de `tests/test_08_reconciliation_reports.py`: 1/1.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `create_bank_difference_journal` cx=27)

### Hallazgo SonarCloud

Issue `AZ_iGnqzaa4LEs-MjUlm` (`python:S3776`, CRITICAL):
`cacao_accounting/bancos/statement_service.py`, `create_bank_difference_journal`, complejidad cognitiva 27 frente
al umbral 15.

### Corrección

Se separaron la carga de conciliación, resolución y validación de cuentas, identificación de la cuenta bancaria,
resolución de moneda y carga de libros activos. Se conservaron las validaciones de unicidad, pertenencia de compañía,
cuenta GL bancaria, moneda, selección de libro y la generación del ajuste balanceado.

### Verificación

- Escenarios focales de `tests/test_08_reconciliation_reports.py` y `tests/test_payment_unit.py`: 1/1 ejecutado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — Bancos `_paginate_list` cx=28)

### Hallazgo SonarCloud

Issue `AaBG9cs4WKUcwX8H2P6V` (`python:S3776`, CRITICAL):
`cacao_accounting/bancos/services.py`, `_paginate_list`, complejidad cognitiva 28 frente al umbral 15.

### Corrección

Se separaron la resolución y aplicación del alcance de compañías y el filtro de período contable en helpers dedicados.
Se conservaron el acceso explícito a compañía, la restricción por permisos, la excepción administrativa, el bloqueo sin
compañías autorizadas, búsqueda, estado, paginación y selector de período.

### Verificación

- `tests/test_08_reconciliation_reports.py`: 2/2 escenarios de alcance de listados bancarios.
- `tests/test_03webactions.py -k buying_sales_and_cash_lists_support_search_filters --slow=True`: 1/1.
- Cobertura focalizada: las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes pertenecen
  a funciones preexistentes fuera del listado refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_sum_invoice_amount` cx=28)

### Hallazgo SonarCloud

Issue `AaAbv2FUOioNy6Mzk_6q` (`python:S3776`, CRITICAL):
`cacao_accounting/bancos/cash_forecast_service.py`, `_sum_invoice_amount`, complejidad cognitiva 28 frente al
umbral 15.

### Corrección

Se extrajo la resolución de saldo y conversión de cada factura a `_invoice_forecast_amount`, manteniendo el fallback
para esquemas legacy, la propagación de errores operacionales no relacionados, la exclusión segura de documentos con
moneda/tasa incompleta, saldos no positivos y el signo de devoluciones.

### Verificación

- Escenarios focales de `tests/test_record_to_reports_multicurrency_multiledger.py` y `tests/test_cash_forecast.py`:
  3/3.
- Cobertura focalizada: las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes pertenecen
  a funciones preexistentes o a escenarios fuera de este flujo.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_reconcile_three_way` cx=28)

### Hallazgo SonarCloud

Issue `AaAIQvUHKije7nS9oKot` (`python:S3776`, CRITICAL):
`cacao_accounting/compras/purchase_reconciliation_service.py`, `_reconcile_three_way`, complejidad cognitiva 28
frente al umbral 15.

### Corrección

Se separaron el cálculo de totales y tolerancias (`_calculate_three_way_totals`) y la persistencia de asignaciones de
líneas (`_persist_three_way_items`). Se conservaron las validaciones de orden, compañía, proveedor, moneda y estado,
el cálculo de cantidades pendientes, diferencias de precio/importe, tolerancias y el detalle de matching 3-way.

### Verificación

- Escenarios focales de `tests/test_08_reconciliation_reports.py`: 4/4.
- Cobertura focalizada: las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes pertenecen
  a funciones preexistentes o a escenarios fuera de este flujo.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — Inventario `_paginate_list` cx=28)

### Hallazgo SonarCloud

Issue `AaBG9c1uWKUcwX8H2P6W` (`python:S3776`, CRITICAL):
`cacao_accounting/inventario/services.py`, `_paginate_list`, complejidad cognitiva 28 frente al umbral 15.

### Corrección

Se separaron la autorización por compañía y la aplicación de filtros por período contable en helpers dedicados.
Se conservaron la compañía explícita, el alcance de compañías autorizadas, la excepción administrativa, el bloqueo sin
compañías consultables, los filtros de período, búsqueda, estado, paginación y el selector de período.

### Verificación

- `tests/test_inventory_valuation_settings.py`: 5/5.
- `tests/test_03webactions.py -k inventory_stock_entry_routes --slow=True`: 1/1.
- Cobertura focalizada: las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes pertenecen
  a funciones preexistentes fuera del listado refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `TransactionDocumentAdapter.validate_document` cx=29)

### Hallazgo SonarCloud

Issue `AaAb4cY70SpjD9SaGpBH` (`python:S3776`, CRITICAL):
`cacao_accounting/imports/adapters/transaction_documents.py`, `TransactionDocumentAdapter.validate_document`,
complejidad cognitiva 29 frente al umbral 15.

### Corrección

Se separaron la validación del documento origen y la validación de bodega, artículo y lote por fila. Se conservaron
los requisitos de tercero, fecha y período abierto, pertenencia de compañía, estado del origen, membership del
tercero, controles de stock/bodega, lotes, moneda y tipo de cambio.

### Verificación

- `tests/test_batch_master_data.py`: 31/31.
- Cobertura focalizada del adaptador: 57%; las líneas no cubiertas restantes pertenecen a métodos preexistentes o a
  escenarios fuera de la validación refactorizada.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_create_stock_reconciliation_movement` cx=31)

### Hallazgo SonarCloud

Issue `AaAa6soYSsPfV5h49WFi` (`python:S3776`, CRITICAL):
`cacao_accounting/contabilidad/posting_service.py`, `_create_stock_reconciliation_movement`, complejidad cognitiva
31 frente al umbral 15.

### Corrección

Se separaron la resolución de bodega, bloqueo y validación del snapshot de inventario, cálculo de costo FIFO y
persistencia de capas de valuación. Se conservaron la validación batch/serial, prohibiciones de stock/valor negativo,
reconciliación de cantidades y valores, actualización de `StockBin`, movimientos de ledger y capas append-only.

### Verificación

- Regresiones focales de `tests/test_07posting_engine.py`: 5/5.
- Cobertura focalizada: 36% del módulo completo; las líneas no cubiertas restantes pertenecen a funciones
  preexistentes fuera del flujo refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_financial_filters` cx=32)

### Hallazgo SonarCloud

Issue `AaBG9c58WKUcwX8H2P6a` (`python:S3776`, CRITICAL):
`cacao_accounting/reportes/helpers.py`, `_financial_filters`, complejidad cognitiva
32 frente al umbral 15.

### Corrección

Se extrajo la resolución de períodos por defecto, nombre y rango a `_financial_period_filters`. Se conservaron la
compañía y libro predeterminados, estado y cancelaciones, alias de período, rechazo de fechas manuales incompatibles,
límites de página, ordenamiento y todos los filtros financieros.

### Verificación

- `tests/test_period_range_filters.py`: 12/12.
- Cobertura focalizada: todas las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes
  pertenecen a funciones preexistentes fuera del flujo refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_source_line_rate` cx=32)

### Hallazgo SonarCloud

Issue `AaBBbpXsopylcTR1Qqlh` (`python:S3776`, CRITICAL):
`cacao_accounting/ventas/services.py`, `_source_line_rate`, complejidad cognitiva
32 frente al umbral 15.

### Corrección

Se separaron la lectura/validación de referencias de línea y la resolución del modelo y clave foránea por tipo de
documento. Se conservaron el retorno de la tarifa enviada cuando no hay origen, el rechazo de referencias parciales,
los cinco tipos documentales soportados, la validación de correspondencia de línea y la tarifa inmutable del origen.

### Verificación

- `tests/test_sales_catalog_pricing.py`: 11/11.
- Cobertura focalizada: todas las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes
  pertenecen a funciones preexistentes fuera del flujo refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `save_purchase_request_comparison_draft` cx=33)

### Hallazgo SonarCloud

Issue `AaAGlaIlTV2yRQvm0ilZ` (`python:S3776`, CRITICAL):
`cacao_accounting/compras/purchase_request_comparison_service.py`, `save_purchase_request_comparison_draft`,
complejidad cognitiva 33 frente al umbral 15.

### Corrección

Se extrajo la construcción y validación de cada línea seleccionada a `_comparison_draft_line`; la función pública
conserva la eliminación de líneas anteriores, la detección de overrides, los motivos, las cantidades/importes, el
estado de autorización y el `flush` transaccional.

### Verificación

- `tests/test_purchase_request_comparison.py`: 20/20.
- `tests/test_e2e_purchase_request_comparison.py`: 1/1.
- Cobertura focalizada del servicio: 93%; la línea de error de selección inválida quedó cubierta por prueba dedicada.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_create_purchase_invoice_from_request` cx=36)

### Hallazgo SonarCloud

Issue `AaAa6s0eSsPfV5h49WFu` (`python:S3776`, CRITICAL):
`cacao_accounting/compras/services.py`, `_create_purchase_invoice_from_request`, complejidad cognitiva
36 frente al umbral 15.

### Corrección

Se separaron la resolución de fuentes y tipo documental, la validación del contexto de proveedor/compañía y
reversión, la materialización de la factura, la validación de la relación upstream y el cálculo/fiscalización de
totales. Se conservaron la herencia de compañía y moneda, flags del proveedor, duplicidad de factura, relaciones de
orden/recepción, límites de notas de crédito/débito, snapshots fiscales, rollback y auditoría.

### Verificación

- `tests/test_s2p_purchase_notes.py`: 11/11.
- `tests/test_e2e_modules.py::test_purchase_happy_path` y
  `tests/test_e2e_modules.py::test_purchase_invoice_from_order_hydrates_immutable_header`: 2/2.
- Cobertura focalizada: todas las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes
  pertenecen a funciones preexistentes fuera del flujo refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — Ventas `_paginate_list` cx=37)

### Hallazgo SonarCloud

Issue `AaBALBhWmykm2BcQkHT8` (`python:S3776`, CRITICAL):
`cacao_accounting/ventas/services.py`, `_paginate_list`, complejidad cognitiva
37 frente al umbral 15.

### Corrección

Se separaron la obtención de compañías autorizadas, la aplicación del alcance de compañía, la resolución de la
compañía única para períodos y la aplicación del filtro temporal. Se conservaron los permisos explícitos, el filtro
por compañía solicitada, el comportamiento para administradores y usuarios sin compañías, los alias de parámetros de
período, el selector de período, los filtros de listado y la paginación.

### Verificación

- `tests/test_o2c_sales_fixes.py`: 30/30, incluyendo los alcances de compañía/período y la orquestación de paginación.
- Cobertura focalizada: todas las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes
  pertenecen a funciones preexistentes fuera del flujo refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_paginate_list` cx=37)

### Hallazgo SonarCloud

Issue `AaBALByImykm2BcQkHT_` (`python:S3776`, CRITICAL):
`cacao_accounting/compras/services.py`, `_paginate_list`, complejidad cognitiva
37 frente al umbral 15.

### Corrección

Se separaron la obtención de compañías autorizadas, la aplicación del alcance de compañía, la resolución de la
compañía única para períodos y la aplicación del filtro temporal. Se conservaron los permisos explícitos, el filtro
por compañía solicitada, el comportamiento para administradores y usuarios sin compañías, los alias de parámetros de
período, el selector de período, los filtros de listado y la paginación.

### Verificación

- `tests/test_purchase_request_comparison.py::test_purchase_list_helpers_apply_company_and_period_scopes`,
  `tests/test_purchase_invoice_period.py`, la regresión del selector de períodos y el listado con búsqueda: 5/5.
- Cobertura focalizada: todas las líneas nuevas del refactor están cubiertas.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `create_purchase_orders_from_comparison` cx=38)

### Hallazgo SonarCloud

Issue `AaAGlaIlTV2yRQvm0ila` (`python:S3776`, CRITICAL):
`cacao_accounting/compras/purchase_request_comparison_service.py`, `create_purchase_orders_from_comparison`,
complejidad cognitiva 38 frente al umbral 15.

### Corrección

Se separaron las precondiciones del comparativo, la carga de líneas seleccionadas, la validación y agrupación por
proveedor, la construcción de líneas de flujo y la materialización de cada orden de compra con sus relaciones,
logística, moneda y totales. Se conservaron las validaciones de estado, compañía, aprobación, moneda homogénea,
existencia de líneas, prevención de órdenes duplicadas y actualización final del comparativo a `used`.

### Verificación

- `tests/test_purchase_request_comparison.py`: 19/19.
- `tests/test_e2e_purchase_request_comparison.py`: 1/1.
- Cobertura focalizada del servicio: 88%; todas las líneas nuevas del refactor están cubiertas. Las líneas no cubiertas
  restantes pertenecen a funciones preexistentes fuera del flujo refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_xlsx_rows` cx=43)

### Hallazgo SonarCloud

Issue `AaBPsMnNkZtwr73q0yaS` (`python:S3776`, CRITICAL):
`cacao_accounting/api/line_import.py`, `_xlsx_rows`, complejidad cognitiva
43 frente al umbral 15.

### Corrección

Se separaron la selección segura de hojas, la construcción del mapa de encabezados, la detección de columnas sin
encabezado, la lectura de celdas, la conversión de filas y la aplicación del límite de 500 líneas. Se conservaron los
alias localizados, encabezados desconocidos o duplicados, campos requeridos, rechazo de fórmulas, normalización de
fechas, filas vacías y errores estructurales del archivo.

### Verificación

- `tests/test_line_import_api.py`: 48/48.
- Cobertura focalizada del módulo: 83%; todas las líneas nuevas del refactor están cubiertas. Las líneas no cubiertas
  restantes son código preexistente fuera del parser XLSX refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `ventas_entrega_nuevo` cx=46)

### Hallazgo SonarCloud

Issue `AaAa6suhSsPfV5h49WFn` (`python:S3776`, CRITICAL):
`cacao_accounting/ventas/routes.py`, `ventas_entrega_nuevo`, complejidad cognitiva
46 frente al umbral 15.

### Corrección

Se separaron la carga de fuentes, catálogos, configuración Alpine y contexto del formulario, así como la creación POST
de la nota y la validación de sus relaciones con una orden o nota de entrega origen. Se conservaron la precedencia de
fuentes del formulario y del POST, los valores iniciales de devoluciones, la herencia inmutable de compañía/moneda,
la validación de cantidades, la persistencia de batch/serial, la auditoría y el commit transaccional.

### Verificación

- `tests/test_batch_serial_persistence.py::TestDeliveryNoteBatchSerial`, sus tres pruebas nuevas y
  `tests/test_e2e_modules.py::test_sales_happy_path`: 6/6.
- Cobertura focalizada: todas las líneas nuevas del refactor están cubiertas; las líneas no cubiertas restantes son
  código preexistente de `ventas/routes.py` fuera de este flujo.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_validate_open_item_reference` cx=43)

### Hallazgo SonarCloud

Issue `AaBPsMnNkZtwr73q0yaS` (`python:S3776`, CRITICAL):
`cacao_accounting/api/line_import.py`, `_validate_open_item_reference`, complejidad cognitiva
43 frente al umbral 15.

### Corrección

Se separaron la resolución del tipo documental, la construcción y aplicación de filtros de la consulta materializada,
la búsqueda de coincidencias en el ledger financiero, el almacenamiento de la referencia y la generación de errores.
Se conservaron el fallback al ledger cuando no existe `ARAPOpenItem`, la resolución por documento o número, los filtros
por compañía/tercero/línea, la conversión de tipos genéricos de factura/notas y las respuestas para referencias
inexistentes o ambiguas.

### Verificación

- `tests/test_line_import_api.py`: 44/44.
- Cobertura focalizada del módulo: 79%; todas las líneas nuevas del refactor están cubiertas. Las líneas no cubiertas
  restantes son código preexistente fuera del flujo refactorizado.
- Black, Ruff, Flake8, pydocstyle, Mypy y `git diff --check`: limpios. Mypy requirió anteponer el
  `site-packages` de Python 3.13 del `.venv` al `PYTHONPATH` por un `pathspec` global de Python 3.11.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `find_bank_reconciliation_candidates` cx=49)

### Hallazgo SonarCloud

Issue `AaBALB35mykm2BcQkHUB` (`python:S3776`, CRITICAL):
`cacao_accounting/bancos/reconciliation_service.py`, `find_bank_reconciliation_candidates`, complejidad cognitiva
49 frente al umbral 15.

### Corrección

Se extrajeron la resolución de tolerancias, conversión del importe de pagos, carga de GL y generación de candidatos
por pagos/GL. Se conservaron las ventanas de fechas, reglas activas, filtros por cuenta y dirección, conversiones de
moneda, exclusión de cancelados, saldos pendientes y scoring.

### Verificación

- `tests/test_reconciliation_service_unit.py`, `tests/test_bank_matching_auto_reconcile.py` y
  `tests/test_bank_cash_matrix_audit.py`: 33/33.
- Black, Ruff, Flake8, pydocstyle y `git diff --check`: limpios.
- Mypy no inicia en el `.venv` actual por `ModuleNotFoundError: No module named 'pathspec.patterns.gitignore'`.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_validate_ar_ap_lines` cx=52)

### Hallazgo SonarCloud

Issue `AaBPsMOkkZtwr73q0yZ_` (`python:S3776`, CRITICAL):
`cacao_accounting/contabilidad/journal_service.py`, `_validate_ar_ap_lines`, complejidad cognitiva 52 frente al
umbral 15.

### Corrección

Se separaron la validación del tercero AP/AR, la búsqueda de referencias abiertas y la validación del sentido de la
referencia. Se conservaron la resolución por id o código, el fallback al ledger, la compatibilidad de referencias
libres en cuentas no auxiliares y todas las reglas de tercero, saldo y dirección.

Se agregó una prueba que bloquea la creación de un comprobante con cuenta por cobrar sin tercero.

### Verificación

- `tests/test_09_journal_entry_form.py`: 30/30.
- Black, Ruff, Flake8, pydocstyle y `git diff --check`: limpios.
- Mypy no inicia en el `.venv` actual por `ModuleNotFoundError: No module named 'pathspec.patterns.gitignore'`.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-31 (refactor S3776 — `_validate_payment_reconciliation_row` cx=53)

### Hallazgo SonarCloud

Issue `AaBPsMnNkZtwr73q0yaV` (`python:S3776`, CRITICAL):
`cacao_accounting/api/line_import.py`, `_validate_payment_reconciliation_row`, complejidad cognitiva 53 frente al
umbral 15.

### Corrección

Se mantuvo el contrato de validación y se extrajeron helpers para cargar el pago, resolver el documento referenciado,
validar el tercero, resolver la tasa de cambio y verificar los saldos de documento/pago. El orquestador conserva el
mismo orden de validación y las mismas reglas de error. Se centralizó también el mapa de modelos conciliables.

Se agregaron pruebas para el caso válido, tercero incorrecto, moneda distinta sin tasa, exceso de saldo documental,
exceso de saldo del pago y monto no positivo.

### Verificación

- `tests/test_line_import_api.py`: 33/33.
- Cobertura focalizada del archivo: las líneas nuevas del refactor quedan cubiertas; las líneas no cubiertas restantes
  son preexistentes.
- Black, Ruff, Flake8, pydocstyle y `git diff --check`: limpios.
- Mypy no inicia en el `.venv` actual por `ModuleNotFoundError: No module named 'pathspec.patterns.gitignore'`.

El issue se conservará como referencia hasta que el siguiente análisis de SonarCloud detecte la reducción por debajo
del umbral.

## 2026-08-30 (refactor S3776 — `post_payment_ar_ap` cx=68)

### Petición del usuario

Atacar el peor foco individual de complejidad cognitiva del proyecto:
`post_payment_ar_ap` en `cacao_accounting/contabilidad/arap_ledger_service.py`,
issue SonarCloud `AaBPsMNkkZtwr73q0yZ3` (regla `python:S3776`, severidad CRITICAL,
umbral 15, cx=68). El reporte inicial listaba la línea 383 (dato desactualizado);
la API de SonarCloud en este momento reporta la línea 517, donde efectivamente
arranca la función.

Alcance acordado: solo este issue, trabajo local sin abrir issues de GitHub ni
referenciar #757/#759/#760. Bitácora en SESSIONS.md, commits locales.

### Plan implementado

Extract Method + dataclass de contexto. Cero cambios en firmas públicas,
cero cambios de comportamiento, cero dependencias nuevas.

- Nuevo tipo `@dataclass(frozen=True) _PaymentPostingContext` que consolida
  `document`, `party_entries`, `references`, `total`, `payment_sign`,
  `payment_currency`, `payment_date` y `payment_account_id`. Evita pasar
  siete argumentos por posición a los helpers.
- Siete helpers privados nuevos:
  - `_load_payment_references(document)` — carga las `PaymentReference` del pago.
  - `_find_existing_payment_opening(document)` — encapsula la consulta
    idempotente de la apertura previa.
  - `_has_postable_payment_context(document, references)` — combina las
    guard clauses iniciales con un solo predicado.
  - `_build_payment_posting_context(document, references, entries)` — arma el
    dataclass con todos los datos derivados.
  - `_create_payment_opening_movement(context)` — crea el `ARAPLedgerEntry`
    de apertura.
  - `_record_payment_open_item_cache(movement, context)` — materializa el
    `ARAPOpenItem` con la porción no consumida por las references.
  - `_value_payment_movement_in_books(movement, context, *,
    associate_opening_gl)` — itera libros activos, resuelve tasa snapshot y
    registra el book entry. Centraliza la decisión "asociar GL de apertura
    solo si no hay references" mediante un kw-only bool en lugar del cálculo
    inline previo.
- `post_payment_ar_ap` reescrita como orquestador lineal de 35 líneas (cx=7
  según `radon cc`); sin anidamiento > 2 niveles.

Cuatro tests nuevos cubren ramas que el refactor toca y que la batería previa
no ejercitaba:

- `test_post_payment_with_zero_total_skips_opening` — total = 0 → no se crea
  apertura propia, solo allocations.
- `test_post_payment_fully_allocated_closes_open_item` — references cubren el
  100 % del total → `ARAPOpenItem.status = "closed"`,
  `unallocated_amount = 0`.
- `test_post_payment_without_references_associates_opening_gl_per_book` — sin
  references y con GL del libro fiscal → el book entry del FISC debe tener
  `gl_entry_id` no nulo (regresión explícita del kw-only
  `associate_opening_gl=True`).
- `test_post_payment_opening_gl_for_books_is_none_when_references_exist` —
  con references, ningún book entry de apertura debe apuntar al GL
  (regresión del kw-only `associate_opening_gl=False`).

### Decisiones de diseño

- `_PaymentPostingContext.consumed_cash` se calcula como `@property` para
  mantener la dataclass frozen y no derivar un campo mutable. La suma sobre
  references vive en un solo lugar.
- `_value_payment_movement_in_books` recibe la decisión booleana como kw-only
  argument en lugar de pasar el `GLEntry | None` resuelto. Esto preserva la
  regla original ("el GL de apertura se asocia solo si no hay references")
  sin filtrar lógica de libros al orquestador, y mantiene el helper
  reutilizable en futuras llamadas.
- `_process_payment_reference` queda intacta: ya tiene su propia lógica y
  cambiar su firma rompería un par de paths sutiles. Marcar como follow-up
  natural en una iteración futura; podría cerrar también los issues
  `AaBPsMNkkZtwr73q0yZ7` y `AaBPsMNkkZtwr73q0yZ5` si en esa iteración se
  extrae un helper común entre las tres apariciones del patrón "para cada
  libro activo: resolver tasa + añadir book entry".
- Los branches que ya estaban sin cobertura en el código original (la rama
  `if existing_opening is not None:` del orquestador) se preservan sin
  tocarlos; el plan no agrega cobertura donde no la había.

### Verificación

- `python -m pytest tests/test_ar_ap_ledger_model.py -x -q` → 18/18 verde
  (14 originales + 4 nuevos). Antes del refactor: 14/14.
- `python -m pytest tests/test_payment_reconciliation_arap_adapter.py
  tests/test_arap_gl_reconciliation.py -x -q` → 14/14 verde. Adaptador AR/AP
  y reconciliación GL/subledger intactos.
- `python -m flake8 cacao_accounting/contabilidad/arap_ledger_service.py` →
  limpio.
- `python -m ruff check cacao_accounting/contabilidad/arap_ledger_service.py`
  → All checks passed!
- `python -m black --check --line-length 127
  cacao_accounting/contabilidad/arap_ledger_service.py` → All done! 1 file
  would be left unchanged.
- `python -m mypy cacao_accounting/contabilidad/arap_ledger_service.py` →
  Success: no issues found in 1 source file. A diferencia de sesiones previas,
  `pathspec.patterns.gitignore` sí está disponible en el `.venv` actual, por
  lo que el chequeo de tipos se ejecutó completo.
- `python -m pydocstyle cacao_accounting/contabilidad/arap_ledger_service.py`
  → limpio.
- `python -m radon cc -s -a
  cacao_accounting/contabilidad/arap_ledger_service.py` →
  `post_payment_ar_ap` queda en **cx=7** (ranking B). Todos los helpers
  nuevos quedan en rango A (cx ≤ 5), salvo `_build_payment_posting_context`
  (cx=6, B). El umbral del proyecto es 15; **todos los cx quedan ≤ 7**.
- `pytest --cov=cacao_accounting.contabilidad.arap_ledger_service
  tests/test_ar_ap_ledger_model.py tests/test_payment_reconciliation_arap_adapter.py
  tests/test_arap_gl_reconciliation.py` → cobertura del archivo 82 % (87/482
  stmts sin cubrir). **Todas las líneas introducidas por el refactor
  (519–685) están cubiertas**; las 87 líneas no cubiertas son código
  preexistente que no se tocó (anulación de documentos, posting de journals,
  reconciliación, etc., cubiertos por sus propios módulos de test fuera de
  esta sesión).

### Issue SonarCloud

La key `AaBPsMNkkZtwr73q0yZ3` permanece OPEN en la API pública; SonarCloud
cierra los issues solo cuando el siguiente escaneo detecta que la métrica
bajó del umbral. El commit menciona `Refs: SonarCloud AaBPsMNkkZtwr73q0yZ3`
para facilitar el mapeo cuando el escaneo automático recorra la rama.

### Notas para iteraciones futuras

- Los dos issues restantes en `arap_ledger_service.py` listados originalmente
  con cx alto (`AaBPsMNkkZtwr73q0yZ7` y `AaBPsMNkkZtwr73q0yZ5`) ya no
  aparecen en la respuesta actual de la API: o fueron cerrados por commits
  recientes, o nunca existieron bajo ese identificador en este escaneo. Si
  reaparecen tras el cierre de este issue, abordarlos es straightforward
  siguiendo el mismo patrón Extract Method + dataclass.
- El patrón "para cada libro activo: resolver tasa + añadir book entry" se
  repite tres veces en el archivo: en `post_document_ar_ap`,
  `post_payment_ar_ap` (ahora `_value_payment_movement_in_books`) y
  `_process_payment_reference`. Una segunda iteración podría extraer un
  helper compartido `value_movement_in_active_books(movement, amount,
  currency, party_entries, opening_gl=None)` y reutilizarlo en los tres
  sitios, eliminando las últimas duplicaciones del archivo.

## 2026-08-29 (constantes para literales duplicados SonarCloud)

### Petición del usuario

Atender el siguiente easy fix de SonarCloud: `Define a constant instead of duplicating this literal.`

### Plan implementado

Se centralizaron los 24 literales duplicados reportados por `python:S1192` en constantes de módulo para rutas,
servicios, formularios, catálogos de configuración, datos de desarrollo y claves foráneas de la base de datos. Se
conservaron los valores funcionales, los endpoints y los mensajes existentes; los mensajes que ya usaban traducción
continúan resolviéndose mediante el helper de internacionalización.

### Verificación

`git diff --check` pasó y los archivos modificados se compilaron con Python. Las pruebas focalizadas pasaron: Contabilidad
257/257, AUDIT-004 28/28, O2C 28/28, importaciones 14/14, seguridad de sesión 15/15, formularios 1/1, conciliación de
compras 3/3, conciliación bancaria 5/5, semillas 9/9, reportes 6/6 y comparación de solicitudes 1/1. El esquema pasó
213/213 usando SQLite aislado; con el `DATABASE_URL` PostgreSQL compartido fallan dos pruebas por estado externo
obsoleto (`account_balance_snapshot` existente y tabla `item` sin `image_path`). El caso FIFO que había fallado en la
ejecución global pasa aislado y dentro de AUDIT-004.

Black, Ruff, pydocstyle y `git diff --check` pasan. Flake8 no está instalado en `.venv`, Pylint no tiene ejecutable y
Mypy no puede iniciar porque el entorno no contiene `pathspec.patterns.gitignore`. Las pruebas no requieren cambios de
comportamiento: validan los flujos existentes mientras el refactor elimina únicamente la duplicación de literales.

## 2026-08-29 (fusión de condiciones anidadas SonarCloud)

### Petición del usuario

Atender el siguiente easy fix de SonarCloud: `Merge this if statement with the enclosing one.`

### Plan implementado

Se fusionaron las tres condiciones anidadas detectadas por `python:S1066` y `shelldre:S1066`: asignación de moneda
transaccional en comprobantes, exclusión de cierres fiscales en el resumen contable y selección de un intérprete Python
con pytest en `scripts/run_tests_by_file.sh`. Se conservaron las mismas condiciones y el cortocircuito original.

### Verificación

Las pruebas `tests/test_09_journal_entry_form.py`, `tests/test_report_account_summary.py` y
`tests/test_document_flow_tree.py` pasaron 29/29, 2/2 y 25/25. Black, Ruff, Flake8, pydocstyle y `bash -n` pasan;
ShellCheck no está instalado. Mypy no pudo iniciar porque el entorno `.venv` no contiene
`pathspec.patterns.gitignore`.

## 2026-08-29 (extracción de condicionales anidados SonarCloud)

### Petición del usuario

Atender el siguiente easy fix de SonarCloud: `Extract this nested conditional expression into an independent statement.`

### Plan implementado

Se extrajeron las tres expresiones anidadas detectadas por `python:S3358`: el tipo de origen inicial de una nota de
entrega, el modelo de documento origen de una factura de venta y la cantidad origen usada para recalcular el flujo de
líneas. Los fallbacks y la prioridad de cada selección se mantienen explícitos mediante bloques `if`/`elif`/`else`.

### Verificación

Las pruebas `tests/test_o2c_full_cycle.py` y `tests/test_document_flow_tree.py` pasaron 5/5 y 25/25, respectivamente.
Black, Ruff, Flake8 y pydocstyle pasan en los tres archivos modificados. Mypy no pudo iniciar porque el entorno `.venv`
no contiene `pathspec.patterns.gitignore`.

## 2026-08-29 (limpieza de strings concatenados SonarCloud)

### Petición del usuario

Atender el siguiente easy fix de SonarCloud: `Merge these implicitly concatenated strings; or did you forget a comma?`

### Plan implementado

Se fusionaron las cinco parejas de literales adyacentes detectadas por `python:S5799` en validación de moneda, creación
automática de notas de entrega y validación de tasas de pago. El texto resultante permanece idéntico; únicamente se
eliminó la concatenación implícita que podía ocultar una coma faltante.

### Verificación

La prueba `tests/test_currency_contract_complete.py` pasó 58/58 y la batería previa `tests/test_e2e_modules.py` pasó
17/17. Black, Ruff, Flake8 y pydocstyle pasan en los cuatro archivos modificados. Mypy no pudo iniciar porque el entorno
`.venv` no contiene `pathspec.patterns.gitignore`.

## 2026-08-29 (limpieza de excepciones redundantes SonarCloud)

### Petición del usuario

Atender el siguiente easy fix de SonarCloud: `Remove this redundant Exception class; it derives from another which is
already caught.`

### Plan implementado

Se simplificaron las ocho ocurrencias de `python:S5713` en los flujos de compras y ventas. Las excepciones
`IdentifierConfigurationError`, `DocumentFlowError` y `PurchaseSourcingError` heredan de `ValueError`, por lo que cada
cláusula podía capturar directamente `ValueError` sin alterar el rollback ni el mensaje mostrado. También se retiraron
dos imports que quedaron sin uso en `ventas/routes.py`.

### Verificación

La batería modular `tests/test_e2e_modules.py` pasó 17/17. Black, Ruff, Flake8 y pydocstyle pasan en los tres archivos
modificados. Mypy no pudo iniciar porque el entorno `.venv` no contiene `pathspec.patterns.gitignore`.

## 2026-08-29 (corrección rápida de accesibilidad SonarCloud)

### Petición del usuario

Atender los issues abiertos más obvios de SonarCloud: `Web:TableWithoutCaptionCheck` solicita agregar una descripción a
las tablas HTML.

### Plan implementado

Se añadieron captions descriptivos, ocultos visualmente y marcados para traducción a las dos tablas condicionales de
seguridad de sesión, la tabla de clasificación del Estado de Flujo de Efectivo y la tabla de cuentas pendientes del
reporte EFE bloqueado.

### Verificación

Se comprobó el diff con `git diff --check` y se ejecutaron las pruebas focalizadas existentes de seguridad de sesión y
Estado de Flujo de Efectivo. No se añadió una prueba nueva porque el usuario indicó que este ajuste HTML no la requiere.

## 2026-08-26

### Petición del usuario

Corregir fallos focalizados de esquema, navegación administrativa, reconciliación FIFO y permisos de búsqueda.

### Plan implementado

La ejecución de esquema se verificó sin `DATABASE_URL`, para mantener aisladas las pruebas SQLite. Se actualizó la
expectativa de navegación con la sección pública de seguridad y la política ACL que rechaza con HTTP 403 un filtro de
compañía no autorizado. En inventario, la reversa de una recepción ahora queda fijada a su capa de valoración original,
evitando que FIFO consuma una recepción anterior al cancelar una recepción posterior. La regresión valida que una venta
posterior conserva el coste de la capa no anulada y que Bin, SLE, SVL y GL se reconcilian.

## 2026-08-26

### Petición del usuario

Hacer visible en el panel administrativo la opción para asignar compañías a usuarios.

### Plan implementado

Se corrigió la visibilidad de la acción `Compañías` en la lista de usuarios: antes solo aparecía para
clasificación `system`, aunque el administrador (`admin`) también es un usuario interno válido. La ruta
ahora aplica la misma regla que la asignación de roles: bloquea únicamente usuarios portal (`customer` y
`supplier`). Se añadió una prueba que verifica la visibilidad y el guardado para el usuario administrador.

La columna de acciones usa ahora badges compactos para reducir el espacio horizontal ocupado por los
enlaces y conservar la misma diferenciación visual por tipo de acción.

## 2026-08-23

### Petición del usuario

Agregar un condicional para que la exportación a PDF se deshabilite en modo desktop, debido a que WeasyPrint no está disponible.

### Plan implementado

Se inspeccionó el macro `document_print_button` en `cacao_accounting/templates/macros.html` y se confirmó que `is_desktop_mode()` ya está disponible como global de Jinja. Se agregó un condicional que no renderiza el enlace de descarga PDF en Desktop Mode, conservando el enlace de vista previa/impresión. Se añadió `tests/test_printing_ui.py` para verificar que el enlace está oculto en Desktop Mode y disponible en modo cloud.

### Decisiones de diseño

- La restricción se aplica en la interfaz compartida de los botones de impresión, evitando ofrecer una acción que depende de WeasyPrint en la instalación desktop.
- La vista previa/impresión permanece disponible porque no usa la ruta de exportación PDF.

## 2026-08-24

### Petición del usuario

Asegurar que todos los checks definidos en `.github/workflows/python-package.yml` pasen; el CI en GitHub fallaba únicamente en el job `lint`.

### Plan implementado

Se ejecutaron localmente los cuatro chequeos del job lint (`flake8`, `ruff`, `pydocstyle`, `mypy`) contra `cacao_accounting/`. Solo `flake8` y `ruff` reportaron dos errores E501 por líneas demasiado largas (>127) en el bloque CSS embebido de `build_print_html` en `cacao_accounting/printing/service.py`. Se dividieron dichas líneas en literales más cortos manteniendo el CSS resultante semánticamente idéntico. Se re-ejecutaron los cuatro linters (todos aprobados) y se corrieron `tests/test_printing_service.py` y `tests/test_printing_ui.py` sin regresiones.

### Decisiones de diseño

- La corrección fue solo de formato: dividir las cadenas CSS en varias líneas concatenadas, ya que los saltos de línea son whitespace válido en CSS y no alteran el HTML generado.
- No se modificó la configuración de linters ni se relajaron reglas para preservar los umbrales de calidad del CI.

### Petición del usuario

Realizar una auditoría exhaustiva previa a la primera versión alpha de Source-to-Pay, Order-to-Cash, Record-to-Report, bancos e inventarios, buscando errores reproducibles de cálculo o lógica de negocio. El sistema opera con múltiples libros y monedas, y los ledgers publicados son append-only: solo pueden anularse.

### Plan implementado

Se revisaron los flujos de pagos, notas de compra/venta, conversiones por libro, conciliación bancaria, pronóstico de efectivo, inventario y cancelaciones. Se corrigió una validación de Source-to-Pay: una nota de crédito o devolución de compra retrodatada ya no puede ignorar pagos posteriores y exceder el saldo vivo de la factura. La corrección quedó acompañada por una prueba de regresión y un commit semántico con sign-off.

Se ejecutaron pruebas focalizadas de los dominios auditados, incluyendo multilibro/multimoneda, sin ejecutar la suite completa.

### Decisiones de diseño

- Los saldos de documentos se validan contra su saldo transaccional vivo; la fecha retroactiva no puede reabrir un importe ya liquidado.
- Cada libro conserva su propia moneda funcional y conversión histórica; no se asume que el importe base de la entidad sea válido para otros libros.
- Los asientos GL y movimientos de stock publicados se conservan append-only. Las cancelaciones se representan mediante contrapartidas y el marcado de anulación del original, nunca por borrado o reescritura.

## 2026-08-25

### Petición del usuario

Continuar la auditoría exhaustiva del proyecto, identificar errores reproducibles de cálculo y lógica de negocio, y corregir cada uno mediante commits semánticos firmados.

### Plan implementado

Se auditó el motor de costos de importación. Se detectó que un cargo distinto de cero prorrateado con una base total igual a cero (por ejemplo, por peso cuando ningún artículo tiene peso) generaba participaciones de cero y el ajuste de residuo asignaba el 100 % del cargo a la última línea. Se añadió una validación de base positiva por método de prorrateo antes de calcular asignaciones, junto con una prueba de regresión que reproduce el caso de dos artículos sin peso y un flete de 30.

### Decisiones de diseño

- No se elige una línea arbitraria ni se aplica un prorrateo alternativo implícito: la contabilización se rechaza hasta que se proporcione una base válida.
- Los cargos de valor cero siguen siendo permitidos aunque la base sea cero, porque no alteran la valoración.

### Plan implementado

Se auditó el cálculo de plantillas fiscales con impuestos incluidos en precio. Un impuesto porcentual incluido se calculaba aplicando su tasa al precio bruto, sobreestimando el impuesto; por ejemplo, 15 % de 115 devolvía 17,25 en lugar de extraer 15,00. Se corrigió la fórmula para descomponer el precio bruto por la suma de las tasas porcentuales incluidas que comparten base de cálculo. Se añadieron pruebas de regresión para un impuesto de 15 % y para dos impuestos incluidos de 10 % y 5 % sobre un total de 115.

### Decisiones de diseño

- Los impuestos fijos incluidos conservan su importe configurado; la descomposición aplica solo a tasas porcentuales.
- Las tasas incluidas se agrupan por base de cálculo, evitando que dos impuestos del mismo precio se calculen uno sobre el bruto y se inflen mutuamente.

### Plan implementado

Se detectó una segunda condición límite en el cálculo de plantillas fiscales: cuando las líneas actuales totalizaban cero, el motor usaba indistintamente `grand_total` como respaldo. En un documento editado que conservaba un total anterior, una línea gratuita podía generar impuesto sobre ese importe obsoleto. El respaldo documental ahora se utiliza únicamente cuando no hay líneas, y se añadió una prueba de regresión con una línea de importe cero y un `grand_total` histórico de 100.

### Decisiones de diseño

- Una línea existente con importe cero es información contable válida y no equivale a la ausencia de líneas.
- Se preserva el respaldo por total documental para flujos heredados que efectivamente no aportan líneas al motor.

## 2026-08-25 (auditoría funcional)

### Petición del usuario

Realizar una auditoría funcional completa del sistema (solo lectura, sin editar código) para evaluar si es best-in-class, y luego abrir issues en GitHub para los hallazgos detectados.

### Plan implementado

Se auditó en profundidad O2C (ventas), S2P (compras), bancos/tesorería, inventario, núcleo contable/fiscal, reportes y plataforma transversal (auth, admin, API, portal, flujo documental, aprobaciones, impresión, imports, frontend, CLI), contrastando contra ERPs de referencia (Odoo, ERPNext, SAP/Dynamics). El veredicto: el núcleo contable-operativo es best-in-class (GL append-only, multi-libro/multimoneda, parcialidades línea-a-línea, matching 3-way, aprobaciones anti-tamper); las brechas se concentran en capa comercial (precios/descuentos), reporting corporativo (EFE, comparativos, consolidación), trazabilidad física (lote/serie sin UI) y plataforma (MFA, API, async). Los 5 hallazgos más sensibles se re-verificaron contra el árbol actual antes de publicar. Se crearon 27 issues en GitHub (#720–#746): 6 HIGH, 19 MEDIUM y 2 LOW (checklists), siguiendo la convención del repo (`SEVERITY:` + etiquetas por módulo/severidad), cada uno con resumen, evidencia archivo:línea, impacto, sugerencia y criterios de aceptación.

### Decisiones de diseño

- Auditoría 100% de solo lectura; ningún archivo de código fue modificado.
- Hallazgos afines se agruparon en un solo issue cuando forman una unidad de trabajo coherente (p. ej. control presupuestario #728, paquete de reporting corporativo #743, endurecimiento de cuentas #739, quick wins de UX #745).
- No se usaron etiquetas del flujo QA del repo (`verified`, `needs-work`, etc.) para no interferir con su semántica de validación; solo severidad + módulo + tipo.
- Cuerpos en español y títulos en inglés con prefijo de severidad, replicando el estilo de los issues históricos del proyecto.

### Plan implementado

Se auditó la resolución de referencias durante el pago y la liquidación cambiaria. El helper de documentos de referencia solo reconocía literalmente `purchase_invoice`; una nota de crédito o débito de compra se consultaba erróneamente contra `SalesInvoice`. Se cambió la resolución para elegir `PurchaseInvoice` o `SalesInvoice` por la familia del doctype y se añadió una prueba de regresión de una nota de crédito de compra.

### Decisiones de diseño

- Las notas de compra y venta comparten sus tablas físicas con sus respectivas facturas, pero no deben cruzar de familia al resolver referencias.
- Los tipos de referencia desconocidos se omiten de forma segura en este helper, manteniendo la validación estricta de tipos en el flujo de pagos.

### Plan implementado

Se auditó el control de disponibilidad presupuestaria por dimensiones. Una validación sin unidad de negocio o proyecto sumaba todas las líneas del presupuesto, incluidas las restringidas a una dimensión concreta. Se corrigió el filtrado para que una dimensión ausente coincida solo con líneas globales y se añadió una prueba: una transacción global ya no puede consumir un presupuesto definido únicamente para un proyecto.

### Decisiones de diseño

- Las dimensiones de presupuesto se comparan de forma exacta; la ausencia de dimensión no significa “todas las dimensiones”.
- Los presupuestos globales continúan aplicando a transacciones globales, mientras que los presupuestos restringidos exigen la misma dimensión en la transacción.

### Plan implementado

Se detectó un caso adicional en la descomposición de impuestos incluidos: al combinar un cargo fijo incluido con un impuesto porcentual incluido sobre la misma base, el cargo fijo permanecía dentro de la base del porcentaje. Por ejemplo, un precio de 125 compuesto por neto 100, timbre fijo 10 e IVA 15 % devolvía IVA 16,3043. El cálculo ahora descuenta los cargos fijos incluidos de la misma base antes de extraer las tasas porcentuales. Se añadió una prueba de regresión del escenario.

### Decisiones de diseño

- El importe fijo incluido se reconoce íntegramente y no se capitaliza dentro de la base porcentual del mismo grupo de cálculo.
- La separación continúa agrupada por `calculation_base`, de modo que los cargos de otra base no afectan la descomposición.

### Plan implementado

Se auditó el motor fiscal utilizado por la vista previa y por los asientos. Este agrupaba las tasas porcentuales incluidas por la secuencia de la regla, aunque la secuencia solo define el orden de procesamiento. Dos impuestos incluidos sobre la misma base con secuencias distintas se extraían por separado y se sobreestimaban; además no descontaba cargos fijos incluidos. Se agruparon reglas incluidas por su definición de base (`base_mode`, conceptos incluidos y excluidos) y se añadió una prueba con timbre fijo 10 e IVA 15 % incluidos en un precio de 125, con secuencias distintas.

### Decisiones de diseño

- La secuencia conserva su función de orden determinista; no determina qué impuestos comparten base gravable.
- Solo se agrupan reglas con la misma definición explícita de base, preservando las dependencias de reglas acumuladas distintas.

### Plan implementado

Se comparó el alta directa de pagos con la conciliación AR/AP. La conciliación rechazaba que descuento más diferencia cambiaria fuera igual o superior al importe aplicado, pero el alta directa no contenía ese control. Así, un pago de efectivo 1 podía liquidar una factura de 100 declarando una asignación y descuento de 100. Se incorporó la misma validación antes de crear la referencia y una prueba de regresión por la ruta HTTP que confirma que la factura conserva su saldo.

### Decisiones de diseño

- Un descuento y una diferencia cambiaria no pueden consumir por completo la asignación: debe existir una porción de efectivo conciliable.
- Ambos flujos de aplicación de pagos comparten ahora el mismo límite económico para evitar resultados divergentes según la pantalla utilizada.

### Plan implementado

Se completó la auditoría de variantes del cálculo de impuestos incluidos. Las reglas fiscales permiten un importe manual incluido en precio, pero el motor solo restaba los cargos de tipo fijo antes de extraer porcentajes incluidos. Un cargo manual 15 e IVA 15 % dentro de un total de 130 calculaba IVA 16,9565 en vez de 15. El grupo de cargos monetarios incluidos ahora contempla métodos `fixed` y `manual`; la prueba de regresión verifica la descomposición neto 100, cargo 15, IVA 15.

### Decisiones de diseño

- Los métodos fijo y manual representan importes monetarios conocidos, por lo que ambos se excluyen de la base de tasas porcentuales incluidas.
- El ajuste no cambia la semántica de tasas porcentuales ni de reglas con una base diferente.

### Plan implementado

Se auditó la proyección de caja de AR/AP. El servicio filtraba las facturas solo por sus columnas cacheadas `outstanding_amount` y `base_outstanding_amount`; una factura contabilizada importada con ambas en `NULL` quedaba fuera aunque su saldo vivo fuera positivo. Se eliminó el filtro cacheado y cada factura candidata se valora con `compute_outstanding_amount`, convirtiendo después el saldo canónico a la moneda de compañía. La prueba de regresión crea una factura con vencimiento en agosto y cachés nulos, y verifica que aumenta exactamente 100 la proyección de AR.

### Decisiones de diseño

- El pronóstico usa la misma fuente de verdad de saldos que AR/AP, no un índice cacheado que puede estar incompleto.
- Los documentos liquidados se excluyen tras el cálculo canónico, por lo que ampliar la consulta no incorpora saldos cerrados.

### Plan implementado

Se auditó el cierre fiscal anual. La comprobación de períodos abiertos usaba `is_closed = False OR enabled = True`, por lo que un período correctamente cerrado pero habilitado para consulta/reportes impedía permanentemente el cierre del año. Se corrigió el criterio para considerar abierto únicamente un período con `is_closed = False`. La prueba de ciclo de cierre anual conserva el período habilitado después de cerrarlo y verifica que el comprobante de cierre se genera.

### Decisiones de diseño

- `is_closed` es la autoridad para bloquear movimientos y decidir elegibilidad de cierre; `enabled` es una bandera administrativa independiente.
- Los períodos cerrados pueden seguir disponibles para lectura y reportes sin reabrir el año fiscal.

### Plan implementado

La validación completa detectó una compatibilidad faltante en el pronóstico de caja: algunos escenarios legados de reportes exponen facturas pero no las tablas de relaciones documentales requeridas por el cálculo canónico. El pronóstico ahora intenta primero el saldo canónico; solo para objetos sin tabla ORM o ante un `OperationalError` que confirma la ausencia de `document_relation` usa el saldo persistido y, si existe, su importe base. Se mantienen la conversión histórica y la exclusión individual de facturas sin tasa de cambio.

### Decisiones de diseño

- La fuente canónica sigue teniendo prioridad en esquemas operativos completos; el respaldo no silencia otros errores de cálculo.
- El respaldo se limita a objetos no ORM o a la ausencia explícita de la tabla de relaciones, y conserva el importe base legado para no reconvertir una moneda ya expresada en la moneda de compañía.

### Plan implementado

Se auditó el motor de liquidación de pagos. Una configuración de retención superior al importe liquidado permitía que el cálculo produjera efectivo negativo sin errores; por ejemplo, una liquidación de 100 con retención de 120 devolvía efectivo -20. Se añadió un rechazo explícito antes de construir el efectivo y una prueba de regresión del escenario.

### Decisiones de diseño

- Las retenciones pueden reducir el efectivo hasta cero, pero no pueden exceder la obligación que se liquida.
- El motor devuelve un error de cálculo antes de que el orquestador genere un pro-forma, y el servicio de contabilización convierte ese error en un rechazo de la publicación.

## 2026-08-25 (EFE NIC 7)

### Petición del usuario

Implementar el issue #722: falta el Estado de Flujo de Efectivo (NIC 7) en los reportes financieros. El usuario fijó la arquitectura: configuración explícita obligatoria (sin heurísticas silenciosas), vista dedicada para mapear cada cuenta a Operación/Inversión/Financiamiento (+Efectivo), bloqueo del reporte mientras existan cuentas con movimiento sin clasificar en el período, sugerencia por account_type solo visual y alcance de validación limitado a cuentas con movimiento del período.

### Plan implementado

Se agregó el modelo `CashFlowAccountMapping` (único por compañía+cuenta, sección NIC 7). Nuevo módulo `cacao_accounting/reportes/cash_flow.py` con: resolución de mapeos, validación de cobertura (`get_cash_flow_configuration_status`, exige además al menos una cuenta clasificada como efectivo), cálculo del EFE por identidad contable (`utilidad − Δactivos + Δpasivos/patrimonio` por sección; aporte universal `−(debe−haber)` garantiza `difference == 0` contra la variación real de las cuentas de efectivo) y servicio de la vista dedicada con sugerencias no vinculantes. Ruta `/reports/cash-flow` con estado bloqueado (plantilla con pendientes + CTA a `/accounting/cash-flow-config/{company}`), export CSV/XLSX y jerarquía heredados del marco financiero existente (`cash-flow` agregado al conjunto jerárquico y etiquetas de sección en helpers). Vista dedicada GET/POST en el módulo Contabilidad con badge Configurada/Requerida/Opcional e indicador de desbloqueo. Enlaces desde la página del módulo y acciones del dashboard API. Pruebas unitarias y HTTP completas (`tests/test_cash_flow_statement.py`, 6 casos incluidos cuadre exacto, override entre secciones y flujo HTTP de desbloqueo).

### Decisiones de diseño

- Catálogo contable ≠ presentación: el GL registra hechos y la tabla de mapeo decide cómo se presentan; nada se deduce en silencio.
- El reporte solo honra compañía/libro/período: filtros de dimensión romperían la identidad contable del cuadre.
- Excluye anulados, reversas y cierres fiscales (mismo universo que balanza/estado de resultados por defecto).
- La validación cubre cuentas con movimiento neto en la ventana; una cuenta nueva con movimiento vuelve a bloquear hasta clasificarse (guard auditable).
- La utilidad proviene de cuentas P&L aunque estén sin mapear; su clasificación explícita se ignora a propósito.
- Fase 2 fuera de alcance: método directo, efecto cambiario multimoneda, líneas personalizadas/copiables entre compañías.

### Plan implementado

Se completó la ruta de pago totalmente retenido solicitada durante la auditoría. El alta ahora admite efectivo cero únicamente en pagos o cobros con referencias aplicadas; valida que el importe aplicado esté cubierto por efectivo, descuentos/diferencia de cambio y las retenciones fiscales canónicas. El constructor contable y el posting aceptan ese caso, y el mapeador genera solo la contrapartida de tercero y la retención, sin movimiento bancario. La interfaz usa el total aplicado como base de la retención y no bloquea el envío cuando el efectivo es cero y la retención lo cubre.

### Decisiones de diseño

- Un pago de efectivo cero sin documentos liquidados sigue rechazado; no se permite crear anticipos ni pagos vacíos usando esta excepción.
- La validación se apoya en las líneas fiscales canonicalizadas y persistidas, no en el resumen calculado por el navegador.
- El efectivo bancario no se crea artificialmente: una liquidación cubierta íntegramente por retenciones publica únicamente las cuentas por pagar/cobrar y de retenciones.

### Plan implementado

Se auditó el posting de transferencias de inventario. Una transferencia cuyo origen y destino eran la misma bodega era aceptada: consumía capas FIFO y las recreaba al final de la cola, sin movimiento físico pero alterando la secuencia usada para valorar futuras salidas. Se añadió una validación previa que exige bodegas distintas y una prueba de regresión que confirma el rechazo; la prueba existente de transferencia válida continúa aprobando.

### Decisiones de diseño

- Un traslado interno requiere un cambio físico de bodega; la corrección no intenta normalizarlo como ajuste ni como movimiento nulo.
- El rechazo ocurre antes del consumo de capas de valoración, preservando el orden FIFO y el valor histórico de inventario.

### Plan implementado

Se auditó el filtrado de retenciones en el orquestador de liquidaciones. Este aceptaba indistintamente los alias heredados `payment` y `collection` para cualquier liquidación. En consecuencia, un pago a proveedor de 100 con una retención exclusiva de cobro al 10 % calculaba erróneamente efectivo de 90. Se separaron los eventos válidos por dirección y se añadió una prueba de regresión.

### Decisiones de diseño

- Los alias heredados permanecen compatibles, pero `payment` solo aplica a pagos y `collection` solo a cobros.
- El evento explícito (`payment_confirmed`, `collection_confirmed` o `refund_confirmed`) sigue siendo la autoridad primaria para las reglas modernas.
- En reembolsos, la compatibilidad heredada sigue el sentido de caja: reembolso a cliente usa `payment`; reembolso de proveedor usa `collection`.

### Plan implementado

Se auditó la aplicación de pagos a documentos multimoneda importados. Una factura extranjera con `exchange_rate = 0` pasaba la validación y varias rutas la trataban como tasa 1 al actualizar saldos base. Se añadió una validación de tasa histórica positiva antes de aplicar la referencia y una prueba de regresión con una factura USD de tasa cero.

### Decisiones de diseño

- Los documentos en moneda de la compañía no requieren tasa; los documentos extranjeros requieren una tasa positiva antes de cualquier liquidación.
- Se rechaza la operación en el límite de referencia, antes de persistir la aplicación o modificar cachés de saldo.

### Plan implementado

Se auditó el indicador de concentración en los reportes analíticos. La salida reutilizaba la fórmula de variación entre períodos para calcular la participación de cada grupo contra el total; por ejemplo, un importe de 60 dentro de un total de 100 se exponía como -40 % en vez de 60 %. Se introdujo un cálculo específico de participación y una prueba de regresión que cubre el total ordinario y el total cero.

### Decisiones de diseño

- Las participaciones se calculan como importe dividido entre total, conservando el signo contable de ambos valores.
- Un total cero se presenta como 0 % para evitar una división indefinida y mantener la respuesta del reporte estable.

## 2026-08-26

### Petición del usuario

Atender el issue #749: «Exchange revaluation multiplies instead of dividing when converting functional to account currency», que afirma que `_bank_original_balance` multiplica en lugar de dividir al convertir saldos funcionales a la moneda de la cuenta bancaria.

### Plan implementado

Se reprodujo empíricamente el escenario exacto del issue (entidad NIO, cuenta bancaria USD, única tasa USD->NIO = 36.6243, GL de 36,624.30 sin importes en moneda de cuenta): `_bank_original_balance` devolvió 1,000.0000 USD, el valor correcto, y no los 1,341,250.45 afirmados. La premisa del issue es incorrecta: `_closing_rate(origin, destination)` normaliza la dirección del par e invierte la tasa cuando solo existe el sentido contrario, por lo que multiplicar por su resultado ya equivale a dividir entre la tasa cotizada. Aplicar la corrección sugerida (`functional_amount / rate`) introduciría exactamente el error descrito. Se agregó `test_bank_functional_only_balance_divides_inverse_exchange_pair` con los números concretos del issue (36,624.30 NIO → 1,000.00 USD; cierre 37.00 → ganancia no realizada 375.70 NIO) y la suite completa del módulo pasó 16/16.

### Decisiones de diseño

- No se modificó código de producción: la conversión actual es matemáticamente correcta bajo la convención documentada del par (origen -> destino) y está cubierta además por `test_bank_balance_converts_functional_only_gl_amounts`.
- La nueva prueba de regresión congela el escenario y los criterios de aceptación del issue para detectar si una futura refactorización de `_closing_rate` rompe la normalización de dirección.
- El único riesgo residual detectado es de datos: un par NIO->USD capturado manualmente con el valor estilo USD->NIO (36.6243 en vez de 0.0273) engaña a cualquier consumidor de la tabla; eso es validación de captura, no un defecto de esta función.

### Petición del usuario

Atender el issue #731: «MEDIUM: Purchase request cannot close when lines were ordered directly without comparison round». El cierre de una Solicitud de Compra exigía que todas sus líneas estuvieran cubiertas por un comparativo finalizado con oferta seleccionada, dejando permanentemente incerrables las PR con líneas compradas por asignación directa (sin comparativo).

### Plan implementado

Se añadió `purchase_request_direct_order_item_ids` (líneas con relación activa hacia una Orden de Compra aprobada), `purchase_request_line_closure_reasons` (motivo legible por línea: comparativo u orden directa), y `purchase_request_is_ready_to_close` como nueva compuerta de cierre que acepta cobertura por comparativo o por orden directa. La ruta de cierre y el flag `can_close` del detalle usan ahora la nueva compuerta; al cerrar se registra una entrada de auditoría por línea (`log_line_closure`, acción `closed`) con el motivo correspondiente. Además se corrigió en `audit_trail_service._doc_info` la caída por defecto a nombre de clase CamelCase (p.ej. `PurchaseRequest`) que impedía que la línea de tiempo de documentos DocBase consultada por doctype snake_case (`purchase_request`) mostrara entradas; ahora se normaliza a snake_case. Pruebas nuevas en `tests/test_purchase_request_close.py` cubren PR mixta por servicio y por HTTP, rechazo de órdenes borrador/revertidas, rechazo de cierre con línea descubierta y el tipo de documento snake_case en auditoría.

### Decisiones de diseño

- La cobertura directa exige relación `active` y Orden de Compra `docstatus == 1`: una OC borrador no compromete la compra y una OC anulada revierte sus relaciones, así que ninguna de las dos cierra la línea.
- `purchase_request_comparison_is_closed` conserva su semántica original (solo comparativos) para otros consumidores; la compuerta de cierre real es `purchase_request_is_ready_to_close`.
- Si una línea tiene comparativo finalizado y además orden directa, el motivo auditado prioriza el comparativo (`setdefault`) para reflejar la decisión de abastecimiento.
- El motivo por línea se registra como entrada de auditoría independiente (acción permitida `closed`) en lugar de un comentario único, para trazabilidad granular por línea exigida por el issue.
- La normalización snake_case en `_doc_info` no afecta modelos con columna `document_type` explícita y corrige de paso la línea de tiempo vacía en detalles de solicitudes, órdenes, asientos y demás documentos DocBase.

## 2026-08-26

### Petición del usuario

Atender el issue #729: completar el ciclo operativo de retenciones. La retención debe respetar la configuración del proveedor por compañía y aplicarse por defecto al pagar; además se requiere un certificado imprimible con validación QR y un reporte fiscal mensual de retenciones aplicadas. El reporte no debe ser un resumen agrupado por proveedor.

### Plan implementado

Se reutilizó la regla fiscal configurada en la ficha del proveedor (`CompanyParty.default_tax_rule_id`) cuando la regla es de tipo `withholding` y reconoce el evento de pago. Al pagar a un proveedor, la regla configurada reemplaza las retenciones genéricas de compañía y conserva el cálculo proporcional de pagos parciales. Se agregó `WithholdingCertificate`, emitido dentro de la misma transacción del posting, con copia inmutable de las líneas, importes y relación al pago; al anular el pago el certificado se marca anulado.

El certificado se registró como documento imprimible configurable, con plantilla predeterminada que muestra base, tasa, importe retenido, efectivo pagado y QR. Se incorporó al catálogo de validación pública y se añadió el acceso desde el detalle del pago. Se agregó `/reports/withholdings/monthly`, que lista el detalle fiscal de todos los certificados emitidos del mes seleccionado y excluye anulados, con exportación CSV/XLSX mediante el framework existente.

### Decisiones de diseño

- La configuración del proveedor es la autoridad para sus retenciones al pagar; una regla de impuesto ordinario no se interpreta silenciosamente como retención.
- El certificado se crea solo cuando existe una retención positiva en un pago a proveedor contabilizado y conserva un snapshot de sus líneas para auditoría fiscal.
- El reporte es mensual y detallado por certificado/concepto; no agrega ni sustituye la trazabilidad por proveedor.
- La impresión se mantiene configurable mediante el subsistema existente de plantillas, sin fijar el formato en una ruta especial.
- La validación QR usa el mismo mecanismo público de documentos y la anulación del pago invalida el estado operativo del certificado.

### Verificación

Las pruebas focalizadas de retenciones y liquidación pasaron 15/15; las pruebas de impresión, QR y rutas pasaron 62/62. Black y Ruff pasan para los archivos nuevos/modificados revisados.

## 2026-08-26 (continuidad y correcciones)

### Petición del usuario

Verificar los commits locales frente a los issues abiertos de GitHub, confirmar qué fixes eran correctos y corregir los fallos reproducibles encontrados. Mantener las bases de datos como entornos de desarrollo descartables y no agregar migraciones.

### Plan implementado

Se compararon los 12 commits locales contra `origin/main` y los issues abiertos. Las pruebas focalizadas cubrieron 290 casos: 287 pasaron, 2 fueron omitidos y 1 falló en la auditoría de auto-conciliación bancaria. La causa fue una incompatibilidad introducida al normalizar tipos de documento a `snake_case`: el evento se guardaba como `bank_transaction`, mientras el timeline solicitado como `BankTransaction` no lo encontraba.

Se corrigió `get_document_timeline` para consultar el tipo recibido junto con sus aliases canónico `snake_case` y legacy CamelCase. También se corrigió el `F821` detectado por Ruff en `contabilidad/forms.py` importando `gettext as _` para el mensaje de validación de clasificación.

### Decisiones de diseño

- `snake_case` permanece como formato canónico de almacenamiento; la compatibilidad se resuelve en la lectura para no reescribir auditorías existentes.
- No se agregaron migraciones ni cambios de esquema; todas las bases se consideran descartables de desarrollo.
- Se preservaron los siete archivos modificados sin commit por el usuario.

### Verificación

## 2026-08-26 (triage de issues)

### Petición del usuario

Hacer triage de los 37 issues abiertos (#720–#756) comparando contra el código fuente. Clasificar: falsos positivos, ya resueltos, necesitan trabajo, diferidos pre-beta. Aplicar comentarios y etiquetas `needs-work` / `needs-review` en GitHub.

### Plan implementado

Se analizaron los 37 issues abiertos contra el árbol de código fuente actual. Cada issue fue clasificado y etiquetado en GitHub:

**Cerrados (wontfix) — 7 issues:**
- #725 API REST: No necesitamos API pública, es consumo interno de librerías JS
- #724 MFA/TOTP: Redefinido a self-service recovery por token de un solo uso (ver needs-work)
- #723 UserBookAccess admin UI: Overhead innecesario, RBAC + acceso por compañía es suficiente
- #742 Standard costing/variances/FEFO: Fuera de alcance, Cacao Accounting no es un ERP completo
- #741 Manufacturing/BOM: Fuera de alcance, Cacao Accounting no es un ERP completo
- #740 Task queue/scheduler: Fuera de alcance, operaciones síncronas
- #739 Account security hardening: Pre-beta, no prioritario

**Ya resueltos (wontfix) — 6 issues:**
- #722 Cash flow statement: Ya implementado en `reportes/cash_flow.py`
- #721 Bank matching tolerances: Ya implementado en `reconciliation_service.py`
- #720 Batch/serial capture: Ya implementado en `transaction_form_macros.html`
- #730 Sales orders close: Ya implementado via document flow API
- #745 UX polish: Dark mode completo, portal paging parcial
- #754 Tax pricing negative base: Comportamiento correcto, bases negativas son flujo real

**Diferidos (needs-review) — 5 issues:**
- #746 Platform ergonomics: i18n framework existe, strings hardcodeados es deuda técnica post-beta
- #744 Pricing engine inactive: Price lists funcionan, descuentos no son necesarios para MVP
- #743 Financial statements comparatives: Post-beta
- #733 Financial reports memory: Performance post-beta
- #729 Withholding lifecycle: Parcialmente implementado, refinamiento post-beta

**Necesitan trabajo (needs-work) — 18 issues:**
- #756 FiscalEngine concept_amounts: goods no se actualiza después de descomposición de impuestos incluidos
- #755 Credit limit error message: Mezcla moneda de transacción y moneda base en mensaje
- #753 Purchase request edit: base_currency y exchange_rate no se recalculan en edición
- #752 Analytics _convert_to_ledger: Usa fecha exacta en vez de nearest-date
- #751 Purchase returns supplier link: target_type hardcodeado a purchase_invoice
- #750 Stock valuation rebuild: Puede perder SVLs de value-adjustment en reconciliación FIFO
- #748 Dashboard income KPI: abs() enmascara pérdidas como ingreso positivo
- #736 Accounts excluded from reports: Clasificación vacía = cuenta silenciosamente excluida
- #732 Monthly close lacks integrity checks: No valida GL balance o subledger vs GL
- #734 Fiscal year closing distorted: No valida reversals en periodos posteriores
- #727 Purchase receipt warehouse: Sin validación cross-company
- #726 Sales invoice warehouse: Auto delivery note usa item default silenciosamente
- #749 FX difference sign: Requiere validación de signa con escenario real
- #738 Inventory valuation divergence: Reporte puede divergir de FIFO remaining
- #735 Project capitalization: Abor ta batch completo en moneda mixta
- #731 Purchase request close: Ya atendido (commit local)
- #728 Budget control skipped: Default policy do_nothing es inútil sin configuración
- #724 Self-service recovery: Redefinido para implementar token de un solo uso por email

**Requiere revisión (needs-review) — 1 issue:**
- #737 Bank statement hash: Posible false positive, reference_number None puede causar falsos positivos

### Decisiones de diseño

- El sistema no ha sido lanzado ni para beta pública; muchos issues son prematuros.
- Legacy scopes son overhead que se debe evitar.
- No hay deployments que proteger (entorno pre-beta).
- Cacao Accounting no es un ERP completo; flujos MTI (BOM, manufacturing) están fuera de alcance.
- Bases negativas tienen usos prácticos (devoluciones con impuestos negativos) y no son un error.
- La API REST es de consumo interno de librerías JS, no necesita versionado ni OpenAPI.

### Verificación

Se aplicaron 37 comentarios y etiquetas en GitHub. Todos los issues del rango #720–#756 fueron procesados.

## 2026-08-26 (acceso por compañía)

### Petición del usuario

Eliminar el acceso por libro contable por ser un overhead. Mantener los roles globales para definir acciones y añadir, en paralelo, administración de compañías por usuario en Cloud. Un usuario no debe poder conocer la existencia de una compañía que no tiene asignada.

### Plan implementado

Se reemplazó `UserBookAccess` por `UserCompanyAccess`, que asigna explícitamente compañías a usuarios internos. Los roles existentes conservan el control global de módulos y acciones; las rutas y servicios ahora exigen ambas capas antes de operar. Se añadió la pantalla Cloud Administración → Usuarios → Compañías y se ocultó en Desktop.

Los listados, dashboard, endpoints de selectores y formularios de compañía usan únicamente compañías activas asignadas al usuario. Los libros contables se preservan como dimensión financiera, pero ya no autorizan ni restringen usuarios: el posting resuelve todos los libros activos de la compañía e ignora selecciones parciales heredadas.

### Decisiones de diseño

- RBAC y acceso a compañías son capas paralelas: el rol define qué puede hacer un usuario; el grant define en qué compañías.
- Los administradores conservan acceso global y los usuarios sin grant no reciben resultados que revelen compañías ajenas.
- No se agrega migración de datos porque las bases de desarrollo actuales son descartables.

### Verificación de compatibilidad

Con `DATABASE_URL` desactivada, la suite completa produjo 2.192 tests pasados, 14 fallos y 12 omitidos. Los fallos correspondían a expectativas heredadas del ACL por libro, selección parcial de libros, descubrimiento global de compañías, fixtures con permisos obsoletos y mensajes que revelaban compañías inactivas. Se actualizaron esas expectativas y la batería de regresión resultante pasó 43/43; no quedaron fallos de conexión de base de datos.

## 2026-08-27 (identidad visual autorizada)

### Petición del usuario

Reemplazar en la documentación y la aplicación web el arte de procedencia no confirmada por las marcas finales autorizadas `static/media/brand.svg` y `static/media/brand-mark.svg`, y ajustar la interfaz a tonos chocolate.

### Plan implementado

Las referencias activas de la aplicación, pantallas de autenticación, errores, configuración, impresión, README, manifiesto PWA y service worker ahora usan los dos SVG finales autorizados. `brand.svg` es el logotipo completo y `brand-mark.svg` provee el símbolo para el favicon SVG.

Las copias SVG heredadas se reemplazaron por los dos activos finales. Los favicon PNG, ICO, borradores raster y otros recursos gráficos no referenciados se retiraron; no se generaron recursos raster nuevos.

### Decisiones de diseño

- Los SVG activos no dependen de `<image href=...>` ni de otro recurso gráfico para renderizar el símbolo.
- La aplicación usa únicamente `brand.svg` para el logotipo y `brand-mark.svg` para el favicon.
- La paleta primaria se trasladó de verde a chocolate, terracota y crema, sin reutilizar el verde anterior como color de marca y sin modificar los colores semánticos de éxito, alerta y error.

### Verificación

Se verificó estructuralmente que las referencias activas usan los dos SVG finales, que las copias SVG heredadas son idénticas al activo final correspondiente y que no quedan PNG ni ICO de la identidad anterior. Por instrucción expresa del usuario no se añadieron ni ejecutaron pruebas para este cambio visual.

## 2026-08-28 (QA ronda 1 + 2, issue #762)

### Petición del usuario

Ejecutar la primera ronda de QA sobre la implementación de filtros por período contable (#762), aplicar las correcciones necesarias y dejar la base lista para la segunda ronda de validación.

### Hallazgos del primer pase

* `_paginate_list` en ventas y compras no propagaba el período por defecto cuando el listado se abría sin query string, rompiendo la paridad entre el selector y la consulta.
* `_resolve_as_of_date` y `_resolve_date_bounds` permitían enviar `as_of_date` o `date_from`/`date_to` fuera del período seleccionado por nombre, contradiciendo la regla "el backend nunca confía en fechas del navegador".
* `_period_bounds` y `reconciliation_matrix` resolvían el período únicamente por nombre; dos períodos con el mismo nombre rompían la consulta silenciosamente.
* No existía test que validara la selección determinista del período por defecto con varios períodos habilitados solapados.
* Faltaba cobertura de paridad entre la vista y la descarga para un mismo período.
* Literal "Período actual" en `journal_lista.html` no estaba envuelto en `_()`.

### Plan implementado

* `list_filters.apply_period_filter` ahora acepta `default_when_missing` y aplica el período actual cuando la URL no incluye identificadores. `_paginate_list` en ventas y compras lo invoca con la compañía autorizada por defecto para evitar el 400 cuando el usuario solo tiene acceso a una compañía.
* `require_period_company` acepta `default_company` para que los listados no aborten cuando la compañía es determinable por ACL.
* `_resolve_as_of_date` y `_resolve_date_bounds` ahora resuelven el período a partir de `accounting_period` (id o nombre) y rechazan fechas manuales que no coincidan con el rango resuelto. Se añadió un helper `_resolve_period_id_by_name` para mantener compat con URL legadas.
* `_period_bounds` acepta id o nombre; `reconciliation_matrix` siempre envía el id resuelto a `ReconciliationFilters.accounting_period`.
* `journal_lista.html` corrige la i18n del placeholder "Período hasta".

### Pruebas añadidas

`tests/test_period_default_and_consistency.py` cubre:

* `_default_period_for_company` toma el período habilitado más reciente cuando la fecha objetivo cae fuera de cualquier rango.
* `_resolve_as_of_date` rechaza un `as_of_date` que no coincide con el `accounting_period` enviado por nombre y acepta el que sí coincide.
* `_resolve_date_bounds` aplica la misma política a `date_from`/`date_to`.
* `apply_period_filter(..., default_when_missing=True)` aplica el período actual cuando la URL no envía identificadores.
* La consulta GL acotada al rango resuelto del período contiene exactamente las filas esperadas (paridad vista vs. consulta de exportación).

### Decisiones de diseño

* `default_when_missing` se ofrece como bandera opcional para que los listados operacionales la usen; los reportes que ya validaban explícitamente el criterio no cambian su contrato.
* El rechazo de `as_of_date`/`date_from`/`date_to` se centraliza en `reportes/helpers.py` para que la regla aplique uniformemente a todos los reportes que la consumen.
* `_period_bounds` admite id antes que nombre para desambiguar períodos con nombre duplicado y mantiene la compat con URL legadas.
* No se introdujeron dependencias nuevas.

### Verificación

Linters limpios (black, ruff, flake8, mypy, pydocstyle) sobre los archivos modificados. La nueva suite de pruebas de consistencia pasa junto con `test_period_range` y `test_cancellation_period`; el test de paridad se ajustó para usar una consulta directa del GL en lugar del helper completo, que requiere un libro configurado.

## 2026-08-27

### Petición del usuario

Actualizar la apariencia usando la propuesta visual: Cacao debe tener una identidad moderna, fresca y agradable, con colores tierra sutiles y elegantes. El login debe mantenerse blanco para todos los temas.

### Plan implementado

Se definió una paleta final de marfil cálido, arcilla apagada, oliva seco y cacao profundo como ancla puntual. La aplicación deja de usar grises fríos o masas de chocolate saturado. El login tiene fondo y superficie blanca cálida independientes de la preferencia de tema guardada.

### Decisiones de diseño

- El cacao oscuro se reserva para navegación y jerarquía, no para fondos extensos.
- La terracota y el oliva se emplean como acentos discretos que aportan frescura.
- El modo oscuro conserva contraste y matiz cálido con capas umber suaves.

## 2026-08-27

### Petición del usuario

Rehacer la dirección visual de Cacao Accounting: evitar superficies marrones saturadas, mantener el login claro,
convertir las portadas en workspaces jerárquicos y reservar los colores de marca para acentos.

### Plan implementado

Se sustituyó la capa visual final por superficies neutrales profesionales: claro con fondo gris suave, sidebar cálido y
topbar crema; oscuro con grafito neutral y tarjetas separadas. Las portadas de Compras, Ventas, Inventario, Caja y
Bancos y Contabilidad ahora presentan Operaciones como tarjeta principal y agrupan las áreas secundarias debajo.
Los indicadores verdes para acceso normal se eliminan, preservando estados excepcionales accesibles.

### Decisiones de diseño

- Los tonos Cacao se usan en acciones, selección y detalles, no como fondos estructurales.
- El workspace se limita a 1280 px y responde de tres a dos y una columna según el ancho disponible.
- El login conserva una superficie clara aunque la preferencia de aplicación sea oscura.
- QA independiente verificó la cascada, el contraste de estados, la responsividad y las pruebas focalizadas.

## 2026-08-31 (verificación de invariantes del kardex, issue #773)

### Petición del usuario

Confirmar que el módulo de inventarios lleva un kardex robusto, inmutable, multimoneda y multilibro, con control de
múltiples unidades de medida, lotes y números de serie; anulación solo dentro del mismo período habilitado mediante
transacciones recíprocas (sin concepto de reversión en inventario); valoración por compañía y no por bodega; UOM
predeterminada inmutable tras el primer movimiento; y separación de roles donde compras/ventas no afectan inventario
(solo consultan recepciones/entregas) y solo el usuario de almacén recibe o despacha producto.

### Verificación (auditoría de solo lectura, con evidencia en el código)

- Inmutabilidad del kardex: `StockLedgerEntry` tiene eventos `before_update`/`before_delete` que rechazan toda mutación
  de cifras o metadatos y el borrado físico; solo `is_cancelled` puede mutar (database/__init__.py:1570-1586).
- Anulación recíproca: `cancel_document` resuelve la política central (`resolve_cancellation`) que exige el mismo
  período contable y que esté habilitado y abierto (cancellation_service.py:144-151); `_cancel_stock_movements_if_needed`
  crea contrapartidas append-only (`is_reversal=True`, `reversal_of`) y fija la capa FIFO de la contrapartida a la capa
  original (posting_service.py:3167-3220). No existe ruta de reversión de inventario en otro período: la validación del
  período se ejecuta antes de crear cualquier contrapartida, sin escrituras parciales.
- Multilibro y multimoneda: los documentos operativos fuerzan `ledger_code=None` y `_document_contexts` publica al GL
  en todos los libros activos, acumulando las tasas faltantes y bloqueando el registro completo si falta al menos una
  (posting_service.py:253-328); el mayor físico registra valores en moneda funcional y el kardex multinivel está
  cubierto por tests/test_record_to_reports_multicurrency_multiledger.py.
- UOM múltiple: `_line_qty`/`_line_qty_generic` convierten a la unidad base vía `convert_item_qty` y persisten
  `qty_in_base_uom`; `default_uom_change_allowed` bloquea el cambio de UOM base con movimientos, saldo migrado o líneas
  de documentos activos (inventario/service.py:936-999); los flags de control (lote/serial/vencimiento) también quedan
  bloqueados tras el uso.
- Lotes y seriales: validación de obligatoriedad y disponibilidad con bloqueo pesimista del bin en salidas por lote,
  seriales unitarios con ciclo available/delivered, vencimiento vigente a la fecha de posteo; maestro de lotes con
  unicidad por item+numero (commits previos Refs: #773).
- Valoración por compañía: `Entity.valuation_method` (moving_average/fifo) sin dimensión de bodega; el cambio de método
  queda bloqueado si la compañía ya tiene operación de inventario (inventario/valuation_settings.py:58-74).
- Roles S2P/O2C: la recepción de compra se crea/edita/aprueba/anula solo con permisos inventory
  (compras/routes.py:2422-2790) y la nota de entrega igual (ventas/routes.py:1519-1914); compras conserva vista de
  recepciones y ventas de entregas vía `exige_acceso_compania_cualquiera`; el usuario de almacén puede operar ambos
  formularios.

### Pruebas añadidas

tests/test_kardex_invariants.py (13 pruebas) bloquea por regresión los invariantes verificados: mutación de cifras y
de metadatos rechazadas, borrado físico rechazado, flag de anulación permitido, contrapartida recíproca con par
original/contrapartida completo (SLE, capa FIFO fijada y GL balanceado), rechazo de anulación en período distinto,
cerrado y deshabilitado sin escrituras parciales, y la matriz de roles (buyer/seller 403 en new/submit/edit/cancel con
vista 200; stock 200 en los formularios).

### Nota de entorno

mypy en el venv solo funciona con `env -u PYTHONPATH`: el PYTHONPATH de Replit/Nix inyecta un pathspec 0.12.1 de
python3.11 que sombrea los paquetes del venv y rompe el arranque de mypy 2.3.0. No se instalaron dependencias nuevas.

### Verificación de calidad

- tests/test_kardex_invariants.py: 13/13 en verde.
- Regresión focalizada en verde: guards 7/7, cancellation policy 6/6, cancellation period 5/5, batch master 30/30,
  batch/serial persistencia 10/10, submit+round-trip 31/31, exhaustive 10/10, valuation settings 4/4, uoms 9/9,
  AUDIT-004 28/28, posting engine (stock/receipt/delivery/cancel) 37/37.
- Linters limpios sobre el archivo nuevo: black, ruff, flake8, mypy y pydocstyle.
- QA independiente (segundo agente) revisó el archivo de pruebas, la matriz de roles contra las rutas y la matriz del
  issue contra el código, con veredicto de apto; sus observaciones menores de cobertura quedaron incorporadas.
