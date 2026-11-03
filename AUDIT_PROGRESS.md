# Progreso de auditoría integral — Cacao Accounting

## Reorganizacion y reconciliacion del inventario Python (2026-11-01)

- Criterios confirmados por el responsable durante la auditoria: el producto está en pre-alpha, no ofrece soporte legacy ni rutas alternas; evaluar el flujo actual como una sola implementación que debe quedar limpia y probada. No justificar duplicidad o fallos por compatibilidad histórica. El código productivo muerto también cuenta como issue si se confirma su falta de uso; contrastar referencias, imports/registro, rutas, CLI y consumidores antes de clasificarlo.
- Rama verificada: `estabilizacion`; HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`, igual a `origin/estabilizacion` al inicio de este checkpoint.
- Worktree inicial: `.codex/` y `AUDIT_PROGRESS.md` sin seguimiento. `.codex/` se conserva intacto; este archivo es el unico artefacto modificado por la auditoria.
- Inventario Python de primera parte: **245 archivos**, incluidos lanzadores y herramientas operativas. Se excluyen los 2 archivos de `cacao_accounting/migrations/`, pruebas, entornos/dependencias, build y codigo generado. No se encontraron archivos Python de produccion fuera del paquete y los lanzadores raiz.
- El manifiesto previo contenia 247 filas Python, incluidas esas 2 migraciones. Estados reconciliados para el conjunto de 245: **19 auditados**, **40 requieren revision** (26 parciales y 14 con solo lectura previa), **186 pendientes**. Tras cerrar Imports e iniciar la revision de `database/__init__.py`, el estado comprobable es **27 auditados**, **1 en revision**, **31 requieren revision** y **186 pendientes**.
- Reconciliacion de "44 de aproximadamente 500": no hay una afirmacion ni una lista de 44 archivos auditados verificable en esta bitacora. La unica coincidencia literal con 44 es "S2P / Compras (44 archivos)", que describe el tamano de un modulo, no avance. El checkpoint historico de 29/32/42/433 se refiere a 536 filas mixtas Python/HTML/JS y no se interpreta como 44 archivos auditados.
- Regla del conteo funcional: se cuentan `def` y `async def` del AST, incluidos metodos y funciones anidadas. `N/N` se conserva solo para archivos marcados completos por evidencia previa; `0/N` significa que no hay revision funcional acreditada; `NC/N` indica revision parcial descrita antes pero sin numero exacto reconstruible sin repetir trabajo. `NC` no cuenta como cobertura ni como archivo auditado.
- Orden de revisión por dependencias: se conserva Imports como componente activo preexistente y se cierra primero; después se audita la capa de datos (`database` y helpers), contexto/configuración/autorización (`runtime_mode`, compañía, auth, decoradores y cache), arranque de la app, servicios transversales (identificadores, auditoría, terceros y fiscalidad), API/document_flow, motor contable y libro mayor, luego operaciones en dependencia funcional (inventario → compras/S2P → ventas/O2C → bancos/CTM), y finalmente reportes, consultas, impresión/portal, setup/admin y utilidades restantes. Esta secuencia es una guía de dependencias, no un cambio a la prioridad Imports ya en curso.
- Los estados y notas del manifiesto anterior se conservan abajo para trazabilidad; esta tabla es la vista autoritativa del inventario Python excluyendo migraciones.

### Modulos, responsabilidad y estado por modulo

| Modulo/submodulo | Responsabilidad | Archivos | Auditados | En revision | Requieren revision | Pendientes |
|---|---|---:|---:|---:|---:|---:|
| `[raiz]` | Arranque del proceso y servidor WSGI | 2 | 0 | 0 | 0 | 2 |
| `cacao_accounting (transversal)` | Contexto de compania, politicas, auditoria, impuestos y servicios compartidos | 39 | 0 | 0 | 8 | 31 |
| `cacao_accounting/accounting_engine` | Motores de calculo y construccion de asientos | 3 | 0 | 0 | 0 | 3 |
| `cacao_accounting/accounting_engine/common` | Contexto, periodos y redondeo comunes | 4 | 0 | 0 | 0 | 4 |
| `cacao_accounting/accounting_engine/fiscal` | Resolucion y calculo fiscal | 3 | 0 | 0 | 0 | 3 |
| `cacao_accounting/accounting_engine/landed_cost` | Distribucion de costo de importacion | 2 | 0 | 0 | 0 | 2 |
| `cacao_accounting/accounting_engine/orchestrator` | Orquestacion y mapeo de eventos contables | 3 | 0 | 0 | 0 | 3 |
| `cacao_accounting/accounting_engine/settlement` | Liquidacion y aplicacion de pagos | 2 | 0 | 0 | 0 | 2 |
| `cacao_accounting/accounting_engine/snapshots` | Serializacion de snapshots | 2 | 0 | 0 | 0 | 2 |
| `cacao_accounting/admin` | Administracion, roles y controles de sesion | 5 | 0 | 0 | 0 | 5 |
| `cacao_accounting/api` | Endpoints de seleccion, dashboard e importacion de lineas | 4 | 2 | 0 | 1 | 1 |
| `cacao_accounting/app` | Inicializacion de Flask y servicios de aplicacion | 1 | 0 | 0 | 1 | 0 |
| `cacao_accounting/auth` | Autenticacion, permisos, sesiones y roles | 7 | 0 | 0 | 7 | 0 |
| `cacao_accounting/bancos` | CTM: bancos, pagos, conciliacion y prevision de caja | 8 | 0 | 0 | 8 | 0 |
| `cacao_accounting/compras` | S2P: solicitudes, ordenes, recepcion y compras | 10 | 0 | 0 | 0 | 10 |
| `cacao_accounting/contabilidad` | R2R: libro mayor, diarios, AP/AR, cierre y presupuestos | 29 | 0 | 0 | 3 | 26 |
| `cacao_accounting/database` | Acceso a datos y utilidades de base de datos | 2 | 0 | 1 | 0 | 1 |
| `cacao_accounting/datos` | Catalogos y datos iniciales/de desarrollo | 4 | 0 | 0 | 0 | 4 |
| `cacao_accounting/document_flow` | Relaciones, estados y validacion de flujos documentales | 11 | 0 | 0 | 0 | 11 |
| `cacao_accounting/exceptions` | Excepciones y mensajes de error | 2 | 0 | 0 | 0 | 2 |
| `cacao_accounting/imports` | Lotes, contratos y rutas de importacion | 4 | 4 | 0 | 0 | 0 |
| `cacao_accounting/imports/adapters` | Conversion y persistencia de registros importados | 10 | 10 | 0 | 0 | 0 |
| `cacao_accounting/imports/readers` | Lectura de CSV, XLS, XLSX y ODS | 6 | 6 | 0 | 0 | 0 |
| `cacao_accounting/imports/services` | Orquestacion de validacion y ejecucion de lotes | 2 | 2 | 0 | 0 | 0 |
| `cacao_accounting/imports/utils` | Validacion de periodos y recuperacion de lotes | 3 | 3 | 0 | 0 | 0 |
| `cacao_accounting/inventario` | I2F: articulos, existencias, bodegas y valoracion | 6 | 0 | 0 | 0 | 6 |
| `cacao_accounting/messaging` | Mensajeria y correo electronico | 2 | 0 | 0 | 0 | 2 |
| `cacao_accounting/modulos` | Registro y navegacion de modulos | 1 | 0 | 0 | 0 | 1 |
| `cacao_accounting/portal` | Portal externo | 1 | 0 | 0 | 0 | 1 |
| `cacao_accounting/printing` | Configuracion, validacion y generacion de impresiones | 13 | 0 | 0 | 0 | 13 |
| `cacao_accounting/query_tools` | Consulta y descubrimiento de datos | 10 | 0 | 0 | 0 | 10 |
| `cacao_accounting/query_tools/handlers` | Lectores de datos por dominio | 15 | 0 | 0 | 0 | 15 |
| `cacao_accounting/query_tools/schemas` | Esquemas y filtros de consulta | 9 | 0 | 0 | 0 | 9 |
| `cacao_accounting/reportes` | Reportes financieros y operativos | 10 | 0 | 0 | 3 | 7 |
| `cacao_accounting/setup` | Configuracion inicial y catalogos | 5 | 0 | 0 | 0 | 5 |
| `cacao_accounting/ventas` | O2C: ventas, pedidos y facturacion | 4 | 0 | 0 | 0 | 4 |
| `cacao_accounting/version` | Version del producto | 1 | 0 | 0 | 0 | 1 |

### Manifiesto por archivo

#### `[raiz]` - Arranque del proceso y servidor WSGI

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `run.py` | pendiente | 0/0 |
| `wsgi.py` | pendiente | 0/0 |

#### `cacao_accounting (transversal)` - Contexto de compania, politicas, auditoria, impuestos y servicios compartidos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/__init__.py` | requiere revision | NC/29 |
| `cacao_accounting/__main__.py` | pendiente | 0/0 |
| `cacao_accounting/approval_engine.py` | pendiente | 0/46 |
| `cacao_accounting/approval_policy.py` | pendiente | 0/7 |
| `cacao_accounting/attachment_service.py` | requiere revision | 0/17 |
| `cacao_accounting/audit_chain.py` | requiere revision | 0/15 |
| `cacao_accounting/audit_trail_service.py` | requiere revision | 0/38 |
| `cacao_accounting/cache.py` | pendiente | 0/14 |
| `cacao_accounting/cancellation_scope.py` | pendiente | 0/4 |
| `cacao_accounting/cli.py` | pendiente | 0/27 |
| `cacao_accounting/collaboration_service.py` | pendiente | 0/24 |
| `cacao_accounting/company_context.py` | pendiente | 0/3 |
| `cacao_accounting/config.py` | pendiente | 0/3 |
| `cacao_accounting/control_review_service.py` | requiere revision | NC/12 |
| `cacao_accounting/decorators.py` | pendiente | 0/13 |
| `cacao_accounting/document_authorship.py` | pendiente | 0/9 |
| `cacao_accounting/document_identifiers.py` | requiere revision | NC/21 |
| `cacao_accounting/fiscal_persistence_service.py` | pendiente | 0/36 |
| `cacao_accounting/fiscal_preview_service.py` | pendiente | 0/18 |
| `cacao_accounting/i18n.py` | pendiente | 0/6 |
| `cacao_accounting/internal_control_service.py` | requiere revision | NC/75 |
| `cacao_accounting/internal_control_sql.py` | pendiente | 0/15 |
| `cacao_accounting/ledger_queries.py` | pendiente | 0/3 |
| `cacao_accounting/limiter.py` | pendiente | 0/8 |
| `cacao_accounting/list_filters.py` | pendiente | 0/8 |
| `cacao_accounting/logistics.py` | pendiente | 0/7 |
| `cacao_accounting/logs.py` | pendiente | 0/0 |
| `cacao_accounting/matching_config_service.py` | pendiente | 0/3 |
| `cacao_accounting/module_badges.py` | pendiente | 0/3 |
| `cacao_accounting/num2words.py` | pendiente | 0/13 |
| `cacao_accounting/party_management.py` | pendiente | 0/29 |
| `cacao_accounting/party_settings.py` | pendiente | 0/35 |
| `cacao_accounting/runtime_mode.py` | pendiente | 0/5 |
| `cacao_accounting/search_select.py` | requiere revision | NC/49 |
| `cacao_accounting/server.py` | pendiente | 0/1 |
| `cacao_accounting/tax_pricing_service.py` | pendiente | 0/10 |
| `cacao_accounting/tax_rule_service.py` | pendiente | 0/15 |
| `cacao_accounting/warehouse_accounting.py` | pendiente | 0/2 |
| `cacao_accounting/withholding_service.py` | pendiente | 0/4 |

#### `cacao_accounting/accounting_engine` - Motores de calculo y construccion de asientos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/accounting_engine/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/accounting_engine/document_builders.py` | pendiente | 0/88 |
| `cacao_accounting/accounting_engine/gl_posting_builder.py` | pendiente | 0/10 |

#### `cacao_accounting/accounting_engine/common` - Contexto, periodos y redondeo comunes

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/accounting_engine/common/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/accounting_engine/common/context.py` | pendiente | 0/5 |
| `cacao_accounting/accounting_engine/common/fiscal.py` | pendiente | 0/1 |
| `cacao_accounting/accounting_engine/common/rounding.py` | pendiente | 0/3 |

#### `cacao_accounting/accounting_engine/fiscal` - Resolucion y calculo fiscal

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/accounting_engine/fiscal/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/accounting_engine/fiscal/engine.py` | pendiente | 0/9 |
| `cacao_accounting/accounting_engine/fiscal/resolver.py` | pendiente | 0/7 |

#### `cacao_accounting/accounting_engine/landed_cost` - Distribucion de costo de importacion

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/accounting_engine/landed_cost/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/accounting_engine/landed_cost/engine.py` | pendiente | 0/10 |

#### `cacao_accounting/accounting_engine/orchestrator` - Orquestacion y mapeo de eventos contables

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/accounting_engine/orchestrator/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/accounting_engine/orchestrator/event_orchestrator.py` | pendiente | 0/6 |
| `cacao_accounting/accounting_engine/orchestrator/mapper.py` | pendiente | 0/26 |

#### `cacao_accounting/accounting_engine/settlement` - Liquidacion y aplicacion de pagos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/accounting_engine/settlement/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/accounting_engine/settlement/engine.py` | pendiente | 0/4 |

#### `cacao_accounting/accounting_engine/snapshots` - Serializacion de snapshots

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/accounting_engine/snapshots/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/accounting_engine/snapshots/serializer.py` | pendiente | 0/3 |

#### `cacao_accounting/admin` - Administracion, roles y controles de sesion

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/admin/__init__.py` | pendiente | 0/2 |
| `cacao_accounting/admin/navigation.py` | pendiente | 0/0 |
| `cacao_accounting/admin/routes.py` | pendiente | 0/51 |
| `cacao_accounting/admin/services.py` | pendiente | 0/24 |
| `cacao_accounting/admin/session_security_service.py` | pendiente | 0/9 |

#### `cacao_accounting/api` - Endpoints de seleccion, dashboard e importacion de lineas

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/api/__init__.py` | requiere revision | NC/78 |
| `cacao_accounting/api/dashboard.py` | pendiente | 0/39 |
| `cacao_accounting/api/line_import.py` | auditado | 59/59 |
| `cacao_accounting/api/line_import_registry.py` | auditado | 1/1 |

#### `cacao_accounting/app` - Inicializacion de Flask y servicios de aplicacion

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/app/__init__.py` | requiere revision | NC/8 |

#### `cacao_accounting/auth` - Autenticacion, permisos, sesiones y roles

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/auth/__init__.py` | requiere revision | 0/22 |
| `cacao_accounting/auth/account_throttling.py` | requiere revision | 0/10 |
| `cacao_accounting/auth/device_verification.py` | requiere revision | 0/13 |
| `cacao_accounting/auth/forms.py` | requiere revision | 0/0 |
| `cacao_accounting/auth/helpers.py` | requiere revision | 0/7 |
| `cacao_accounting/auth/permisos.py` | requiere revision | 0/14 |
| `cacao_accounting/auth/roles.py` | requiere revision | 0/4 |

#### `cacao_accounting/bancos` - CTM: bancos, pagos, conciliacion y prevision de caja

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/bancos/__init__.py` | requiere revision | 0/2 |
| `cacao_accounting/bancos/cash_forecast.py` | requiere revision | 0/20 |
| `cacao_accounting/bancos/cash_forecast_service.py` | requiere revision | 0/20 |
| `cacao_accounting/bancos/forms.py` | requiere revision | 0/0 |
| `cacao_accounting/bancos/reconciliation_service.py` | requiere revision | NC/47 |
| `cacao_accounting/bancos/routes.py` | requiere revision | NC/56 |
| `cacao_accounting/bancos/services.py` | requiere revision | NC/130 |
| `cacao_accounting/bancos/statement_service.py` | requiere revision | NC/18 |

#### `cacao_accounting/compras` - S2P: solicitudes, ordenes, recepcion y compras

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/compras/__init__.py` | pendiente | 0/2 |
| `cacao_accounting/compras/forms.py` | pendiente | 0/0 |
| `cacao_accounting/compras/gr_ir_service.py` | pendiente | 0/0 |
| `cacao_accounting/compras/purchase_invoice_draft_service.py` | pendiente | 0/19 |
| `cacao_accounting/compras/purchase_order_comparison_service.py` | pendiente | 0/11 |
| `cacao_accounting/compras/purchase_reconciliation_service.py` | pendiente | 0/80 |
| `cacao_accounting/compras/purchase_request_comparison_service.py` | pendiente | 0/29 |
| `cacao_accounting/compras/purchase_sourcing_service.py` | pendiente | 0/15 |
| `cacao_accounting/compras/routes.py` | pendiente | 0/92 |
| `cacao_accounting/compras/services.py` | pendiente | 0/131 |

#### `cacao_accounting/contabilidad` - R2R: libro mayor, diarios, AP/AR, cierre y presupuestos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/contabilidad/__init__.py` | pendiente | 0/2 |
| `cacao_accounting/contabilidad/arap_allocation.py` | pendiente | 0/26 |
| `cacao_accounting/contabilidad/arap_gl_reconciliation.py` | pendiente | 0/15 |
| `cacao_accounting/contabilidad/arap_ledger_service.py` | pendiente | 0/52 |
| `cacao_accounting/contabilidad/auxiliares.py` | pendiente | 0/15 |
| `cacao_accounting/contabilidad/balance_confirmation.py` | pendiente | 0/18 |
| `cacao_accounting/contabilidad/balance_confirmation_bp.py` | pendiente | 0/16 |
| `cacao_accounting/contabilidad/budget_import_service.py` | pendiente | 0/29 |
| `cacao_accounting/contabilidad/budget_report_service.py` | pendiente | 0/22 |
| `cacao_accounting/contabilidad/budget_service.py` | pendiente | 0/26 |
| `cacao_accounting/contabilidad/cancellation_service.py` | requiere revision | NC/14 |
| `cacao_accounting/contabilidad/ctas/__init__.py` | pendiente | 0/3 |
| `cacao_accounting/contabilidad/currency_guard.py` | pendiente | 0/5 |
| `cacao_accounting/contabilidad/default_accounts.py` | pendiente | 0/13 |
| `cacao_accounting/contabilidad/exchange_rate_import_service.py` | pendiente | 0/18 |
| `cacao_accounting/contabilidad/exchange_revaluation_service.py` | pendiente | 0/49 |
| `cacao_accounting/contabilidad/fiscal_year_closing.py` | pendiente | 0/8 |
| `cacao_accounting/contabilidad/forms.py` | pendiente | 0/2 |
| `cacao_accounting/contabilidad/gl/__init__.py` | pendiente | 0/2 |
| `cacao_accounting/contabilidad/journal_repository.py` | pendiente | 0/5 |
| `cacao_accounting/contabilidad/journal_service.py` | requiere revision | NC/57 |
| `cacao_accounting/contabilidad/ledger_mapping_service.py` | pendiente | 0/7 |
| `cacao_accounting/contabilidad/posting.py` | pendiente | 0/2 |
| `cacao_accounting/contabilidad/posting_service.py` | requiere revision | NC/197 |
| `cacao_accounting/contabilidad/presupuesto.py` | pendiente | 0/15 |
| `cacao_accounting/contabilidad/project_capitalization_service.py` | pendiente | 0/9 |
| `cacao_accounting/contabilidad/recurring_journal_service.py` | pendiente | 0/17 |
| `cacao_accounting/contabilidad/routes.py` | pendiente | 0/103 |
| `cacao_accounting/contabilidad/services.py` | pendiente | 0/48 |

#### `cacao_accounting/database` - Acceso a datos y utilidades de base de datos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/database/__init__.py` | en revisión | 49/49 |
| `cacao_accounting/database/helpers.py` | pendiente | 0/24 |

#### `cacao_accounting/datos` - Catalogos y datos iniciales/de desarrollo

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/datos/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/datos/base/__init__.py` | pendiente | 0/6 |
| `cacao_accounting/datos/dev/__init__.py` | pendiente | 0/23 |
| `cacao_accounting/datos/dev/data.py` | pendiente | 0/22 |

#### `cacao_accounting/document_flow` - Relaciones, estados y validacion de flujos documentales

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/document_flow/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/document_flow/context.py` | pendiente | 0/3 |
| `cacao_accounting/document_flow/currency_resolver.py` | pendiente | 0/8 |
| `cacao_accounting/document_flow/payment.py` | pendiente | 0/81 |
| `cacao_accounting/document_flow/registry.py` | pendiente | 0/5 |
| `cacao_accounting/document_flow/repository.py` | pendiente | 0/15 |
| `cacao_accounting/document_flow/service.py` | pendiente | 0/35 |
| `cacao_accounting/document_flow/status.py` | pendiente | 0/15 |
| `cacao_accounting/document_flow/tracing.py` | pendiente | 0/6 |
| `cacao_accounting/document_flow/tree.py` | pendiente | 0/22 |
| `cacao_accounting/document_flow/validation.py` | pendiente | 0/11 |

#### `cacao_accounting/exceptions` - Excepciones y mensajes de error

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/exceptions/__init__.py` | pendiente | 0/1 |
| `cacao_accounting/exceptions/mensajes.py` | pendiente | 0/0 |

#### `cacao_accounting/imports` - Lotes, contratos y rutas de importacion

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/imports/__init__.py` | auditado | 0/0 |
| `cacao_accounting/imports/column_labels.py` | auditado | 2/2 |
| `cacao_accounting/imports/models.py` | auditado | 0/0 |
| `cacao_accounting/imports/routes.py` | auditado | 18/18 |

#### `cacao_accounting/imports/adapters` - Conversion y persistencia de registros importados

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/imports/adapters/__init__.py` | auditado | 0/0 |
| `cacao_accounting/imports/adapters/bank_statement.py` | auditado | 6/6 |
| `cacao_accounting/imports/adapters/base.py` | auditado | 5/5 |
| `cacao_accounting/imports/adapters/cash_forecast_entry.py` | auditado | 5/5 |
| `cacao_accounting/imports/adapters/chart_of_accounts.py` | auditado | 2/2 |
| `cacao_accounting/imports/adapters/customer.py` | auditado | 2/2 |
| `cacao_accounting/imports/adapters/journal_entry.py` | auditado | 9/9 |
| `cacao_accounting/imports/adapters/purchase_order.py` | auditado | 4/4 |
| `cacao_accounting/imports/adapters/transaction_documents.py` | auditado | 31/31 |
| `cacao_accounting/imports/adapters/vendor.py` | auditado | 2/2 |

#### `cacao_accounting/imports/readers` - Lectura de CSV, XLS, XLSX y ODS

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/imports/readers/__init__.py` | auditado | 0/0 |
| `cacao_accounting/imports/readers/base.py` | auditado | 1/1 |
| `cacao_accounting/imports/readers/csv_reader.py` | auditado | 1/1 |
| `cacao_accounting/imports/readers/ods_reader.py` | auditado | 4/4 |
| `cacao_accounting/imports/readers/xls_reader.py` | auditado | 1/1 |
| `cacao_accounting/imports/readers/xlsx_reader.py` | auditado | 1/1 |

#### `cacao_accounting/imports/services` - Orquestacion de validacion y ejecucion de lotes

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/imports/services/__init__.py` | auditado | 0/0 |
| `cacao_accounting/imports/services/import_service.py` | auditado | 26/26 |

#### `cacao_accounting/imports/utils` - Validacion de periodos y recuperacion de lotes

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/imports/utils/__init__.py` | auditado | 0/0 |
| `cacao_accounting/imports/utils/recovery.py` | auditado | 2/2 |
| `cacao_accounting/imports/utils/validation.py` | auditado | 1/1 |

#### `cacao_accounting/inventario` - I2F: articulos, existencias, bodegas y valoracion

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/inventario/__init__.py` | pendiente | 0/2 |
| `cacao_accounting/inventario/forms.py` | pendiente | 0/0 |
| `cacao_accounting/inventario/routes.py` | pendiente | 0/34 |
| `cacao_accounting/inventario/service.py` | pendiente | 0/52 |
| `cacao_accounting/inventario/services.py` | pendiente | 0/49 |
| `cacao_accounting/inventario/valuation_settings.py` | pendiente | 0/7 |

#### `cacao_accounting/messaging` - Mensajeria y correo electronico

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/messaging/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/messaging/email.py` | pendiente | 0/13 |

#### `cacao_accounting/modulos` - Registro y navegacion de modulos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/modulos/__init__.py` | pendiente | 0/9 |

#### `cacao_accounting/portal` - Portal externo

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/portal/__init__.py` | pendiente | 0/12 |

#### `cacao_accounting/printing` - Configuracion, validacion y generacion de impresiones

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/printing/__init__.py` | pendiente | 0/1 |
| `cacao_accounting/printing/admin_routes.py` | pendiente | 0/20 |
| `cacao_accounting/printing/context.py` | pendiente | 0/50 |
| `cacao_accounting/printing/exceptions.py` | pendiente | 0/0 |
| `cacao_accounting/printing/models.py` | pendiente | 0/0 |
| `cacao_accounting/printing/registry.py` | pendiente | 0/5 |
| `cacao_accounting/printing/routes.py` | pendiente | 0/5 |
| `cacao_accounting/printing/seed.py` | pendiente | 0/4 |
| `cacao_accounting/printing/service.py` | pendiente | 0/24 |
| `cacao_accounting/printing/settings.py` | pendiente | 0/5 |
| `cacao_accounting/printing/snippets.py` | pendiente | 0/1 |
| `cacao_accounting/printing/validation.py` | pendiente | 0/18 |
| `cacao_accounting/printing/validators.py` | pendiente | 0/2 |

#### `cacao_accounting/query_tools` - Consulta y descubrimiento de datos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/query_tools/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/audit.py` | pendiente | 0/3 |
| `cacao_accounting/query_tools/bootstrap.py` | pendiente | 0/1 |
| `cacao_accounting/query_tools/context.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/decorators.py` | pendiente | 0/3 |
| `cacao_accounting/query_tools/errors.py` | pendiente | 0/2 |
| `cacao_accounting/query_tools/pagination.py` | pendiente | 0/4 |
| `cacao_accounting/query_tools/permissions.py` | pendiente | 0/3 |
| `cacao_accounting/query_tools/publication.py` | pendiente | 0/3 |
| `cacao_accounting/query_tools/registry.py` | pendiente | 0/8 |

#### `cacao_accounting/query_tools/handlers` - Lectores de datos por dominio

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/query_tools/handlers/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/handlers/accounting.py` | pendiente | 0/4 |
| `cacao_accounting/query_tools/handlers/advanced.py` | pendiente | 0/32 |
| `cacao_accounting/query_tools/handlers/aging.py` | pendiente | 0/6 |
| `cacao_accounting/query_tools/handlers/analytics.py` | pendiente | 0/8 |
| `cacao_accounting/query_tools/handlers/audit_trail.py` | pendiente | 0/2 |
| `cacao_accounting/query_tools/handlers/banking.py` | pendiente | 0/3 |
| `cacao_accounting/query_tools/handlers/companies.py` | pendiente | 0/1 |
| `cacao_accounting/query_tools/handlers/configuration.py` | pendiente | 0/2 |
| `cacao_accounting/query_tools/handlers/discovery.py` | pendiente | 0/12 |
| `cacao_accounting/query_tools/handlers/documents.py` | pendiente | 0/6 |
| `cacao_accounting/query_tools/handlers/operational.py` | pendiente | 0/10 |
| `cacao_accounting/query_tools/handlers/payables.py` | pendiente | 0/2 |
| `cacao_accounting/query_tools/handlers/receivables.py` | pendiente | 0/2 |
| `cacao_accounting/query_tools/handlers/treasury.py` | pendiente | 0/6 |

#### `cacao_accounting/query_tools/schemas` - Esquemas y filtros de consulta

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/query_tools/schemas/__init__.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/accounting.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/audit_trail.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/banking.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/common.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/companies.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/documents.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/payables.py` | pendiente | 0/0 |
| `cacao_accounting/query_tools/schemas/receivables.py` | pendiente | 0/0 |

#### `cacao_accounting/reportes` - Reportes financieros y operativos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/reportes/__init__.py` | pendiente | 0/2 |
| `cacao_accounting/reportes/analytics.py` | pendiente | 0/19 |
| `cacao_accounting/reportes/cash_flow.py` | pendiente | 0/15 |
| `cacao_accounting/reportes/documentos.py` | pendiente | 0/6 |
| `cacao_accounting/reportes/helpers.py` | requiere revision | NC/78 |
| `cacao_accounting/reportes/internal_control.py` | pendiente | 0/4 |
| `cacao_accounting/reportes/periods.py` | pendiente | 0/11 |
| `cacao_accounting/reportes/routes.py` | requiere revision | NC/33 |
| `cacao_accounting/reportes/semantic.py` | pendiente | 0/20 |
| `cacao_accounting/reportes/services.py` | requiere revision | NC/126 |

#### `cacao_accounting/setup` - Configuracion inicial y catalogos

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/setup/__init__.py` | pendiente | 0/7 |
| `cacao_accounting/setup/catalogs.py` | pendiente | 0/9 |
| `cacao_accounting/setup/forms.py` | pendiente | 0/2 |
| `cacao_accounting/setup/repository.py` | pendiente | 0/15 |
| `cacao_accounting/setup/service.py` | pendiente | 0/13 |

#### `cacao_accounting/ventas` - O2C: ventas, pedidos y facturacion

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/ventas/__init__.py` | pendiente | 0/2 |
| `cacao_accounting/ventas/forms.py` | pendiente | 0/0 |
| `cacao_accounting/ventas/routes.py` | pendiente | 0/65 |
| `cacao_accounting/ventas/services.py` | pendiente | 0/99 |

#### `cacao_accounting/version` - Version del producto

| Archivo | Estado | Funciones revisadas verificables / total |
|---|---|---:|
| `cacao_accounting/version/__init__.py` | pendiente | 0/1 |


## Referencia actual

- Rama: `estabilizacion`
- HEAD actual observado: `c62c3604646f65ce37100412edf2432a8f74cef6` en `estabilizacion`, igual a `origin/estabilizacion`. El checkpoint anterior observó `origin` en `4154dbe29730cca4efa27d9fd620dda144bef4e1`; la referencia remota ya avanzó al mismo commit, sin cambio de HEAD local ni invalidación de evidencia.
- Fecha de checkpoint: 2026-11-01
- Alcance: código productivo ejecutable, contratos UI/API, SQL y configuración con impacto funcional.
- Restricción: solo lectura del producto; este archivo es el único artefacto local que la auditoría puede modificar.
- Los commits `54e67656` (fix de alcance de impresión del portal), `b32394cc` (fix de permisos de escritura contable) y `5ae4b5ae` (fix para devolver la CI al verde) quedan como deltas pendientes al llegar a sus componentes; las pruebas adjuntas se excluyen del inventario productivo. El commit `b32394cc` incorpora cambios de `decorators.py`, `contabilidad/presupuesto.py` y `contabilidad/routes.py`. El commit `5ae4b5ae` incluye cambios en `inventario/routes.py`, `inventario/services.py` y `requirements.txt`, pendientes de revisar en I2F/configuración. El commit `4d899a36` retiró Python 3.15 del workflow y añadió una línea en `inventario/services.py`; se conserva la evidencia previa con delta pendiente. Los commits posteriores `67d41a0c` y `4154dbe2` reformatearon `accounting_engine/fiscal/engine.py`, `accounting_engine/gl_posting_builder.py`, `inventario/service.py`, `printing/service.py` y `contabilidad/balance_confirmation_bp.py`; sus cambios quedan como deltas pendientes de revisión al llegar a esos componentes. `4eb8e131` solo modifica `tests/test_cache_isolation.py` (fuera del inventario productivo); `c62c3604` cambia el comando de Complexipy en `.github/workflows/lint.yml`, delta de configuración pendiente. Las pruebas adjuntas quedan fuera del inventario productivo. Ningún cambio posterior invalida revisiones previas. `.codex/` y `AUDIT_PROGRESS.md` siguen sin seguimiento.

## Inventario reconciliado

El inventario anterior `INVENTORY.md` cubre principalmente símbolos Python y mapeo de issues; no constituye evidencia de revisión funcional por componente. El contador histórico de 508 archivos mezclaba código productivo con seis JS de pruebas y no incluía configuración/arranques fuera del paquete. Se preservan abajo hallazgos y referencias previas, pero el avance actual se calcula desde este inventario reconciliado.

- Python/HTML/JS productivos: **504 archivos** (incluye `run.py` y `wsgi.py`; excluye traducciones, pruebas JS, dependencias y archivos generados).
- Configuración, catálogos serializados y herramientas operativas: **32 archivos**; SQL de producción encontrados: **0** (las migraciones están expresadas en Python).
- La clasificación es funcional; los archivos compartidos pueden estar relacionados con más de un flujo y deben auditarse junto a sus consumidores.

## Orden de componentes basado en dependencias

El componente activo se mantiene hasta completar su estado funcional; las dependencias de otros modulos se revisan como contratos sin cambiar el objetivo. Dentro de cada componente se sigue el orden lectores/modelos -> reglas de dominio/servicios -> rutas/API -> interfaz y consumidores.

| Orden | Componente | Estado | Dependencias principales |
|---:|---|---|---|
| 1 | Imports - lotes y lineas | **En curso** | lectores, modelos, validacion, servicio de lotes, adaptadores, API y rutas; contratos con CTM, GL, S2P y O2C |
| 2 | Identidad y plataforma compartida | Pendiente | base de datos, contexto de compania, autenticacion, permisos, roles, cache opcional y configuracion |
| 3 | Catalogos y politicas comunes | Pendiente | secuencias, libros, moneda, impuestos, terceros, articulos y controles internos |
| 4 | R2R - ledger y motor contable | Pendiente | posting, GL, moneda, periodos, anulaciones/reversiones, AP/AR y conciliacion |
| 5 | CTM restante - pagos, caja chica, conciliacion y prevision | Pendiente | R2R, bancos, moneda y aprobaciones |
| 6 | S2P - requisicion a pago | Pendiente | catalogos, compras, inventario recibido, impuestos, AP y R2R |
| 7 | O2C - pedido a cobro | Pendiente | catalogos, ventas, impuestos, AR y R2R |
| 8 | I2F - inventario y fulfillment | Pendiente | articulos, almacenes, UOM, costos, movimientos y R2R |
| 9 | Interfaces transversales | Pendiente | impresion, portal, mensajeria, colaboracion, reportes y ACL de consumidores |
| 10 | Configuracion, migraciones y despliegue | Pendiente | SQLite/PostgreSQL/MySQL, empaquetado y disponibilidad de cache |

## Componente activo: Imports — lotes y líneas

La unidad principal de auditoría es el subsistema de importación, con subflujos de extracto bancario, datos maestros, documentos transaccionales, asientos y conciliación de pagos. `api/line_import.py` se mantiene como subflujo separado dentro de este componente: comparte contratos de importación, esquema y consumidores, pero conserva sus dependencias de contabilidad/conciliación trazadas individualmente. No se cambia al siguiente componente principal hasta cerrar este inventario; los riesgos y dudas de negocio quedan pendientes sin decidir.

### Cobertura identificada y relaciones por cerrar

- Revisados con lectura técnica en este checkpoint: `imports/readers/{base,csv_reader,xls_reader,xlsx_reader,ods_reader}.py`, `imports/utils/{recovery,validation}.py`, `imports/models.py`, `imports/column_labels.py`, `imports/adapters/{base,bank_statement}.py` y los adaptadores `cash_forecast_entry`, `chart_of_accounts`, `customer`, `vendor`, que forman los subflujos maestros y transaccionales del mismo subsistema.
- Revisados en la ronda anterior: `bancos/routes.py`, `bancos/statement_service.py`, `bancos/reconciliation_service.py`, `bancos/services.py`, `bancos/templates/bancos/extracto_importar.html`; el componente sigue parcial hasta verificar contratos e import service/API sobre el estado actual.
- Contrato de búsqueda verificado parcialmente: `api/__init__.py` (`/api/search-select`, autorización de filtros explícitos y alcance de compañía) y `search_select.py` (catálogos `company`, `book`, `naming_series`, filtros permitidos y scoping). Los selectores envían `Entity.code`; los tres catálogos filtran por el mismo código de compañía y las secuencias por `entity_type`. La compañía se valida contra RBAC antes de construir la consulta. No se detecté incompatibilidad en este recorrido; ambos módulos siguen parciales porque contienen otras rutas y catálogos no pertenecientes al componente.
- Flujo de conciliación manual verificado: `/bank-reconciliation` y `/bank-reconciliation/<bank_account_id>` cargan movimientos pendientes con alcance de compañía; `POST /bank-reconciliation/apply` vuelve a validar pertenencia de cada movimiento y autorización, analiza candidato/importe/diferencia, delega validación transaccional a `reconcile_bank_items()` y revierte ante `BankReconciliationError`. La plantilla envía IDs, candidato, importe y diferencia. Hallazgo existente [#1556](https://github.com/cacao-accounting/cacao-accounting/issues/1556) reproducido de nuevo: con `deposit=0` y `withdrawal=125`, el Jinja imprime y precarga 0 (línea 42); el backend rechaza importe `<=0` (`reconciliation_service.py::_validate_reconciliation_match`, 968–969). Se añadí análisis reproducible al issue (comentario 6558601402).
- Cancelación de comprobante y dependencia de conciliación contrastadas: `cancellation_service.active_cancellation_dependencies`, `journal_service.cancel_submitted_journal` y `posting_service.cancel_document`/`_create_gl_reversals`. Reproducción en SQLite: una `ReconciliationItem` activa con `target_type="gl_entry"`/`target_id=<línea GL>` no aparece como dependencia al comprobar el comprobante (`journal_entry`, ID distinto); el detector solo consulta partidas cuando el documento es `BankTransaction`. Se confirmé el issue existente [#1316](https://github.com/cacao-accounting/cacao-accounting/issues/1316) y se publiqué comentario con la ejecución (6558614117).
- Umbral de importación y actor de autoconciliación revisados de nuevo: `ImportService._execute_task()` sí carga `batch.created_by` en su contexto, pero `_process_document()` no lo entrega a `persist_document()`; `BankStatementAdapter.build_document()` omite el actor y `_auto_reconcile()` llama al servicio sin `actor_id`. `require_review()` exige un actor autorizado en Cloud; el error de actor termina absorbido como fallo opcional, dejando la fila sin conciliar. Se confirmé #1067 mediante comentario de código actual (6558621689). Casos cercanos #1194/#1503 describen otra raíz adicional: reportar una solicitud de aprobación como conciliación aplicada; se mantienen asociados para revisar aprobación, sin fusionar causas.
- Tres ramas relacionadas revalidadas con reproducción aislada sobre SQLite: (1) `auto_reconcile_bank_transaction()` con un retorno pendiente de `reconcile_bank_items()` reporta `reconciled=True`, el ID de aprobación y ninguna conciliación persistida; evidencia añadida a #1194 (6558651499; #1503 es duplicado del mismo núcleo). (2) En transferencia interna USD→EUR con moneda funcional NIO, `_payment_amount()` identifica 92 EUR para la pata destino, pero `_candidate_payment_amount()` devuelve `None`; #1317 sigue reproducible y se añadí comentario (6558635751). (3) Con controles internos habilitados, asignar directamente `BankTransaction.is_reconciled=True` produce el ValueError que bloquea el final de `_post_bank_difference_adjustment()`; la ruta solo captura `BankReconciliationError`. #1082 sigue confirmado; comentario con reproducción SQLite 6558642353.
- Regla de referencia revalidada: una `BankMatchingRule` real activa con `reference_contains="INV-"` y una transacción `UNRELATED-REF` se autoconcilian si el candidato exacto contiene `INV-`; la función manual `apply_bank_matching_rule()` sí aplica el filtro. Reproducción SQLite y comentario al issue #1509 (6558664104).
- Ciclo de validacion/ejecucion revalidado con datos de SQLite: un lote de clientes con CSV valido pasa de estado 1 a 3 pero conserva `started_at`; luego `execute()` y `validate()` devuelven `False` y no crean el tercero. Evidencia añadida al issue [#1528](https://github.com/cacao-accounting/cacao-accounting/issues/1528) (comentario 6558712437).
- Archivo corrupto y detalle UI: el XLSX con firma `PK\x03\x04` y zip invalido ahora deja el lote en estado 7 con error `SYSTEM_ERROR`, pero `preview()` vuelve a leerlo y lanza `BadZipFile`; `detail()` lo llama para estados >=1, de modo que el redirect de validacion acaba en 500 y el mensaje no se muestra. Reproducido con SQLite; evidencia actual añadida al issue [#1031](https://github.com/cacao-accounting/cacao-accounting/issues/1031) (6558701294).
- Cancelacion de importacion: revalidado [#1032](https://github.com/cacao-accounting/cacao-accounting/issues/1032). El caso original de sobrescribir estado 8 parece cubierto, pero si `cancel_requested=True` llega tras el ultimo chequeo y antes de finalizar, `_finalize_execution()` deja `import_status=4` con `completed_at` establecido. Reproducido invocando el cierre con lote real en SQLite; comentario 6558687131. Tambien confirmado [#1395](https://github.com/cacao-accounting/cacao-accounting/issues/1395): `cancel()` acepta estado 0 y deja `cancel_requested=True`; reproducido y comentado (6558689662).
- Dependencia UI revisada: `templates/smart_select_field.html` y `static/js/smart-select.js`; inspeccionados macro Alpine, filtros por selectores, serialización a `/api/search-select`, eventos `input/change`, precarga, invalidación de solicitudes, selección y limpieza. En este componente el selector de compañía notifica cambio; `recordType` es solo filtro para secuencia y no afecta el adaptador de extracto. Otros consumidores quedan pendientes de sus componentes.
- `imports/templates/imports/{new,index,detail}.html`: revisados herencia/macros, selectores Alpine de tipo/libro/secuencia, estados de lotes, tablas de progreso, condicionales y endpoints. Hallazgo confirmado: formularios POST sin CSRF global; issue [#1648](https://github.com/cacao-accounting/cacao-accounting/issues/1648). La carga se muestra solo en estado 0 aunque el servidor acepta estado 1; reproducción GET Flask 200 sin formulario vs. estado 0 con formulario; se añadí evidencia al issue [#1528](https://github.com/cacao-accounting/cacao-accounting/issues/1528).
- `api/line_import.py` y `line_import_registry.py` no son dependencias del flujo `bank_statement` del asistente: búsqueda de consumidores muestra uso desde conciliación de pagos y comprobante contable. Se difieren al componente funcional correspondiente para evitar mezclar flujos. Revisión cruzada posterior de `_xlsx_rows()` únicamente para confirmar la fuga temporal ya consolidada en #1652; no cambia el componente principal.
- `imports/routes.py`: revisados `_load_magic`, `check_desktop_mode`, `check_permission`, `_batch_or_404`, `_resolve_company_book`, `before_request`, `index`, `new`, `detail`, MIME/fallback, guardado, upload, validate, execute, cancel y descarga de plantilla. `record_type` no se valida contra `ImportService.ADAPTERS`: en SQLite, POST crea lote `not_a_real_adapter` (302) y GET detalle con estado cargado devuelve 500 por `preview()`; issue nuevo #1661 (`needs-work`). El fallback MIME acepta tabulado, pero el lector CSV no lo parsea; el lote termina status 7 (#1662, `needs-work`). Descargas CSV/XLSX/ODS probadas autenticadas (200); las tres contienen `serie` en la plantilla `purchase_order`, rechazada en validacion (#1531, comentario 6561507861). La discrepancia validar/editar queda pendiente de politica; quedan por cerrar criterios/integracion de permisos.
- `imports/services/import_service.py`: revisados `ImportService` (resolución lector/adaptador, normalización y canonicalización de encabezados, validación estructural y de negocio, vista previa, ejecución síncrona/asíncrona, cancelación, procesamiento transaccional por documento, actualización/finalización de lotes, manejo de errores y agrupación por referencia) y `_IndexedImportRow`. Las dependencias de rutas/API aún están pendientes; no se registra defecto adicional en esta pasada.
- Persistencia bancaria y valores vacíos revalidados en SQLite: el adaptador guarda `"None"` para celdas vacías `None`; dos filas del mismo lote con `DUP-01` generan dos filas; una fila idéntica sin referencia (`""`) a una comisión existente se rechaza. Comentarios a #1033/#1507/#1262 registrados arriba.
- Pruebas focalizadas con `.venv`: `tests/test_bank_statement_import.py` (6 passed; corrida previa en este checkpoint), `tests/test_import_batch_recovery.py` (3 passed; reejecutada tras los hallazgos de estado), `tests/test_import_batch_cancellation.py` (1 passed; reejecutada). Los tests actuales no ejercitan la carrera de finalizacion #1032, la cancelacion fuera de estado 4 #1395, el reintento valido #1528 ni el GET de detalle con lector corrupto #1031. No se modificaron pruebas.
- Verificaciones realizadas: `XLSXReader` sobre un XLSX real entrega `datetime.datetime`; con SQLite y un período abierto cuyo fin coincide con la fecha, `BankStatementAdapter.validate_document()` rechaza `datetime(2026,10,15)` aunque la fecha `date(2026,10,15)` es válida. `build_document()` conserva el `datetime`. No se cambió código.
- Hallazgos existentes revalidados y evidencia añadida: [#1472 — XLSX rechaza fecha final del período abierto](https://github.com/cacao-accounting/cacao-accounting/issues/1472); [#1507 — duplicados dentro del mismo lote](https://github.com/cacao-accounting/cacao-accounting/issues/1507), reproducido persistiendo dos filas idénticas con la misma identidad bancaria; y [#1644 — matching automático con reglas discrepantes](https://github.com/cacao-accounting/cacao-accounting/issues/1644), cuyo mismo defecto también puede atribuir el candidato ganador a la regla incorrecta porque `best_rule` se sobrescribe independientemente del candidato de mayor puntaje. Evidencia añadida a los issues existentes; no se abrió duplicado.
- Revalidación adicional de issues de importación y persistencia: #1033 sigue confirmado para extractos: celdas de XLSX vacías (`None`) se convierten y persisten como texto `"None"` en referencia/descripción; el lado de caja pronosticada de ese issue sigue pendiente. #1507 se reproduce: dos filas idénticas con referencia en un lote insertan dos `BankTransaction` (comentario 6558747980); #1195/#1047 son informes del mismo defecto. #1262 se reproduce en el adaptador activo: una nueva comisión sin referencia, misma fecha/importe y referencia `""` se rechaza como duplicada (6558749356); el antiguo `import_bank_statement` no tiene consumidor de ruta. #1319: tabla sin restricción única sobre `identity_key`; dos filas idénticas se confirman en SQLite con hash igual (6558760233), sin simular concurrencia PostgreSQL. #1505: parser legacy acepta retiro -50 y descarta ese lado, mientras el adaptador activo lo rechaza; acotación añadida al issue (6558764252). #1645/#1647 se difieren al componente de bancos/caja correspondiente. `58d181a` registra fixes propuestos de #1031/#1032, pero se documentaron los casos residuales actuales.
- Evidencia complementaria de identidad de fila: `BankTransaction` no declara restricción única sobre el hash y se confirmaron dos filas con hash idéntico; la búsqueda de `identity_key` en el repositorio no encontré migración que añada unicidad. Comentario adicional a #1319 (6558771141).

### Checkpoint de workflows, identidad y filtro reactivo del importador (2026-11-01)

- `.github/workflows/ci.yml`: revisados trigger, jobs reutilizables y concurrencia; invoca lint, bases de datos y pruebas Python.
- `.github/workflows/databases.yml`: revisados jobs SQLite, MySQL, PostgreSQL con psycopg2 y pg8000, y aislamiento de cache. Los motores se inicializan y ejecutan `pytest -m database --full`; la corrida no contiene una prueba de concurrencia para `BankTransaction.identity_key`.
- `.github/workflows/python.yml`: revisada matriz Python 3.12 a 3.15; los modos deps solo importan el paquete y full/desktop ejecutan la suite general. Delta del commit `4d899a36`: se retira Python 3.15; cotejo pendiente, evidencia previa conservada.
- `.github/workflows/lint.yml`: revisados linters del backend, complejidad y seguridad, y pruebas npm de Smart Select.
- `tests/test_database.py`: revisada su cobertura usada por el job database: crea esquema, verifica tablas criticas y columnas/restriccion de GL; no comprueba unicidad de `identity_key` ni inserciones concurrentes. `rg` confirma que `identity_key` solo se define en `database/__init__.py` y su listener; no hay una restriccion unica ni migracion localizada.
- Evidencia negativa del entorno: no estan disponibles los comandos `psql` ni `docker`, ni se encontro un servicio PostgreSQL local; por ello #1319 no se reproduce aqui en PostgreSQL. El CI configura PostgreSQL en Ubuntu, pero el workflow no ejecuta una prueba de carrera especifica para esa identidad. Comentario de cobertura y limite agregado al issue #1319: 6558807358.
- Revalidaciones disparadas por el caso de serie: un CSV `purchase_order` que conserva la columna `serie` de la plantilla se rechaza con estado 7 y `PROHIBITED_COLUMN` (#1531; comentario 6558923644). Al retirar la columna opcional, el lote valido llega a estado 3 pero `execute()` no arranca y el lote queda sin filas procesadas (#1528; comentario 6558924997).
- Alcance de reglas bancarias manuales reproducido en SQLite real: una regla ligada a la cuenta A evaluo una transaccion de la cuenta B de la misma compania cuando se invoco `apply_bank_matching_rule(rule_id, B.id, rango)`. El formulario muestra todas las cuentas y la ruta solo compara compania; #1261 confirmado, comentario 6558955269. No se concilio ni altero ninguna transaccion.
- Archivo CSV bancario con solo encabezados revalidado con `ImportService.validate()`: devuelve True, estado 3, `total_rows=0`, cero exito/error y sin errores de validacion. #1200 confirmado con comentario 6558992267 (#1065 refleja el mismo hallazgo). El `execute()` normal actualmente devuelve False por el bloqueo independiente #1528, por lo que no se afirma estado final 5 en esta reproduccion.
- Asociacion de cuenta bancaria probada por `ImportService.validate()` en SQLite: una cuenta activa de otra compania se rechaza (estado 2 y error explicito); una cuenta inactiva de la misma compania pasa a estado 3 sin error. El rechazo entre companias queda verificado. La regla de importacion historica en cuentas inactivas no esta definida en la evidencia de negocio revisada; no se abre issue hasta confirmar ese criterio.
- Reproduccion adicional del selector de serie: en `new.html`, el `<select>` cambia `recordType`, y `:value` actualiza `#import-entity-type` sin emitir evento sobre ese input. El Smart Select solo escucha `input/change` en `filterSources`; reproduccion con el JS actual y DOM de JSDOM deja `selectedValue=SER-SALES` y las opciones antiguas mientras `entity_type` ya es `purchase_order`. `npm test` pasa (95); no incluye este camino. El servidor guarda el `sequence_id` sin validarlo y `assign_document_identifier()` rechaza serie de tipo distinto durante persistencia. Issue nuevo #1659 (needs-work). Reproduccion backend en app SQLite aislada con Entity y NamingSeries reales: `_pick_naming_series(entity_type="purchase_order", naming_series_id=<serie sales_invoice>)` lanza `IdentifierConfigurationError: La serie seleccionada no coincide con el tipo de documento`. `_process_all_documents()` captura `ValueError` y contabiliza las filas como error. Es una prueba del guard de identificador, no una ejecucion completa de ImportService. Comentario adicional en #1659: 6558888239. Busqueda en tests: no hay cobertura de `sequence_id`/`naming_series_id` para importaciones. Reproduccion con ImportService real: un CSV valido de orden de compra alcanza estado 3, pero `execute()` devuelve `False` porque `started_at` sigue establecido (#1528; comentario 6558924997). Tras limpiar `started_at` solo en SQLite temporal para aislar esa barrera, `execute()` devuelve `True` y termina estado 6 con 0 exitos, 1 fila fallida y el error de serie incompatible; comentario #1659 6558930840. No representa el camino normal actual hasta que se corrija #1528.
- Se mantiene #1319 como defecto reproducible en SQLite por ausencia de unicidad atomica, sin afirmar una reproduccion concurrente PostgreSQL.

### Proximo archivo

Siguiente: continuar la revisión de `ImportService` por documento, enlazando agrupación por referencia, persistencia/deduplicación y commits de filas con los resultados ya reproducidos en #1507 y #1062. Después cerrar transiciones/reintentos y permisos de `imports/routes.py`; la política para cuentas inactivas y permisos imports-only sigue pendiente de criterio. `xls_reader.py` queda parcial por falta de fixture XLS.

### Checkpoint de continuidad y reconciliacion del arbol (2026-11-01)

- Estado autoritativo comprobado: rama `estabilizacion`, HEAD `87196e651373cbc4c803301ae856ef288cc5ecf3`, un commit delante de `origin/estabilizacion`; cambios sin commit en `cacao_accounting/__init__.py`, `api/__init__.py`, `api/dashboard.py` y `collaboration_service.py`. Se preservan; no fueron revisados en este paso y los dos primeros se marcan invalidados.
- El commit local `87196e65` anade alcance por compania para movimientos bancarios a `_apply_cash_company_scope()` en `bancos/services.py`; el cambio afecta consultas paginadas CTM y no el flujo de persistencia/autoconciliacion de importaciones. Otros archivos del commit y la prueba adjunta quedan para sus componentes funcionales.
- Revision funcional de `imports/adapters/bank_statement.py`, funcion `_auto_reconcile()`, contrastada con `ImportService._process_document()`/`_execute_task()`, `statement_service.auto_reconcile_bank_transaction()`, `reconciliation_service.reconcile_bank_items()` y `control_review_service.require_review()`/`_operation_actor()`. `created_by` esta disponible en el contexto del lote, pero no se propaga a `persist_document()` ni a los datos de transaccion; la autoconciliacion invoca sin `actor_id`. En Cloud, el control exige actor autorizado y convierte la ausencia/no autorizacion en `BankReconciliationError`; el savepoint revierte el intento y `_auto_reconcile()` lo absorbe. La importacion conserva la fila sin conciliar. Esto sustenta el defecto #1067 previamente reproducido y comentado (6558621689); no se abrio duplicado ni se ejecuto una nueva reproduccion en este checkpoint.
- Revisadas de nuevo las rutas y sus guardas de permiso en `imports/routes.py`: el acceso requiere permiso de modulo y `_batch_or_404()` valida alcance/accion por compania; subida, validacion, ejecucion y cancelacion aplican respectivamente `actualizar`+`editar`, `validar`+`editar`, `autorizar` y `anular`. No se observo en esta inspeccion una ruta POST sin ambas barreras pertinentes; queda pendiente resolver si validar requiere tambien permiso de edicion segun la politica del producto. Los hallazgos funcionales #1661/#1662/#1531 permanecen y no se duplican.
- Pruebas focalizadas ejecutadas en `.venv`, cada archivo por separado: `tests/test_bank_statement_import.py` (6 passed), `tests/test_import_batch_recovery.py` (3 passed), `tests/test_import_batch_cancellation.py` (1 passed). Estas pruebas pasan, pero no cubren los defectos registrados #1031/#1032/#1067/#1194/#1395/#1528 ni los flujos POST de permisos/errores de rutas; no se modificaron pruebas.
- La logica de solicitud de aprobacion continua vinculada a #1194/#1503: si `reconcile_bank_items()` devuelve la propuesta pendiente, el llamador de `auto_reconcile_bank_transaction()` la maneja como conciliacion aplicada. El contrato de retorno no distingue resultado persistido de solicitud pendiente en esta cadena; hallazgo previamente reproducido/comentado (#1194, 6558651499). Causa distinta de #1067.
- El progreso permanece parcial; no se declara completo el componente. La lectura de permisos de `imports/routes.py` se retomó y quedó documentada arriba; siguiente: inspeccionar `ImportBatch` y la máquina de estados completa frente a `validate/upload/execute/cancel`, y verificar que los datos de `created_by` y los retornos pendientes no se pierdan en reintentos y ejecuciones asíncronas. La regla de cuentas bancarias inactivas continúa sin criterio de negocio documentado.

## Hallazgos previos preservados

- Issues nuevos de la revisión previa: #1640, #1641, #1642, #1643, #1644, #1645, #1646 y #1647. No se elimina ni se reemplaza su evidencia.
- Issues nuevos recientes de la revisión Imports: #1667 (listeners Smart Select retenidos en desmontaje), #1668 (clasificación contable inválida aceptada por importación), #1669 (recoveries concurrentes duplican SYSTEM_TIMEOUT) y #1670 (la descripción de esquema se descarta en el mapeo frontend; destino requiere revisión). #1668 se afinó tras QA para reflejar el monto visible como “no clasificado”; #1669 tiene tres reproducciones SQLite WAL. No se cerraron issues.
- Comentarios previos en issues existentes: #1443 (tokens de usuario al desactivar/reactivar), #1468 (API de flujo documental sin ACL de compañía), #1434 (conteo de órdenes cerradas), entre otros registrados en GitHub.
- Las revisiones anteriores sumaban un contador histórico de 126/508 antes de reconciliar. No se usa como porcentaje vigente porque no tenía manifest por componente ni incluía todo el alcance nuevo. Los archivos conocidos se conservan como «lectura previa» en el manifiesto; el estado de componente permanece parcial hasta revisar integración y cambios desde el checkpoint.

## Progreso por archivo

Estado `Lectura previa`: revisado anteriormente, pendiente de reconciliación funcional/componente. `Revisado en checkpoint`: evidencia registrada para ese archivo; aún no implica componente completo. `Pendiente`: sin evidencia suficiente. Un fix posterior conserva la revisión previa y se registra como delta pendiente/parcial hasta cotejar su alcance; no borra ni invalida el trabajo anterior.

### Arranque y composición de aplicación (20 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/__init__.py` | Parcial: revisión previa de inicialización CSRF/manejador 400 conservada; cotejar delta de fix reciente |
| `cacao_accounting/api/__init__.py` | Parcial: revisiones previas Smart Select/#1327/#1321 conservadas; cotejar delta ACL/document-flow |
| `cacao_accounting/app/__init__.py` | Parcial: revisión previa conservada; cotejar filtro de `AccountingPeriod` por compañías autorizadas añadido en fix |
| `cacao_accounting/app/templates/app.html` | Pendiente |
| `cacao_accounting/app/templates/development.html` | Pendiente |
| `cacao_accounting/datos/__init__.py` | Pendiente |
| `cacao_accounting/datos/base/__init__.py` | Pendiente |
| `cacao_accounting/datos/dev/__init__.py` | Pendiente |
| `cacao_accounting/exceptions/__init__.py` | Pendiente |
| `cacao_accounting/messaging/__init__.py` | Pendiente |
| `cacao_accounting/modulos/__init__.py` | Pendiente |
| `cacao_accounting/portal/__init__.py` | Pendiente |
| `cacao_accounting/printing/__init__.py` | Pendiente |
| `cacao_accounting/query_tools/__init__.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/__init__.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/__init__.py` | Pendiente |
| `cacao_accounting/setup/__init__.py` | Pendiente |
| `cacao_accounting/version/__init__.py` | Pendiente |
| `run.py` | Pendiente |
| `wsgi.py` | Pendiente |

### CTM — Bancos, pagos, conciliación y caja (45 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/bancos/__init__.py` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/cash_forecast.py` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/cash_forecast_service.py` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/forms.py` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/reconciliation_service.py` | Parcial: validación de asignaciones y conciliación revisadas para flujo de extracto; resto pendiente |
| `cacao_accounting/bancos/routes.py` | Parcial: importacion, conciliacion, matching y falta de validacion de cuenta contra alcance de regla (#1261) revisados; otros endpoints pendientes |
| `cacao_accounting/bancos/services.py` | Parcial: aplicación de ajuste por diferencia bancaria revisada (#1082); resto pendiente |
| `cacao_accounting/bancos/statement_service.py` | Parcial: autoconciliacion, resultado aprobacion (#1194/#1644), alcance manual de regla (#1261) y parser legacy (#1505) revisados; resto pendiente |
| `cacao_accounting/bancos/templates/bancos.html` | Pendiente |
| `cacao_accounting/bancos/templates/bancos/banco.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/banco_cuenta.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/banco_cuenta_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/banco_cuenta_nuevo.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/banco_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/banco_nuevo.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_conciliacion_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_conciliacion_nueva.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_gasto_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_gasto_nuevo.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_nuevo.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_reposicion_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_reposicion_nueva.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_vale_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/caja_chica_vale_nuevo.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_comparar.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_detalle.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_entradas.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_nuevo.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/conciliacion_bancaria.html` | Revisado en checkpoint: estados, valores y contrato de POST; defecto #1556 reproducido |
| `cacao_accounting/bancos/templates/bancos/conciliacion_facturas_pagos.html` | Parcial: `importExcel()` envía XLSX a parse/validate, mapea filas a líneas y `buildPayload()` las POSTea al endpoint que llama `apply_payment_reconciliation()`. Dos repros confirmaron que la API acepta 60+60 para pago 100, pero el apply rechaza/rollback (#1398, comentarios 6563728434/6563739357; #1205/#1439). El esquema oficial solo provee `reference_id` y antes falla por #1456; repros añadieron `reference_document` para aislar acumulación. Carga de candidatos, estados async y resto del template pendientes |
| `cacao_accounting/bancos/templates/bancos/extracto_importar.html` | Revisado en checkpoint: ruta actual solo redirige al asistente compartido; plantilla sin consumidor activo |
| `cacao_accounting/bancos/templates/bancos/nota_nueva.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/pago.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/pago_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/pago_nuevo.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/reglas_matching.html` | Revisado en checkpoint: el selector de ejecucion permite cuentas de otra cuenta de alcance de la regla (#1261) |
| `cacao_accounting/bancos/templates/bancos/transaccion_lista.html` | Lectura previa; integración pendiente |
| `cacao_accounting/bancos/templates/bancos/transferencia_nueva.html` | Lectura previa; integración pendiente |
| `cacao_accounting/imports/adapters/bank_statement.py` | Revisado y revalidado: existencia, compañía, fecha y montos; celda de fecha XLS llega como serial `38406.0` y falla parseo ISO (#1201, comentario 6563435620); descripción con LF inicial sobrevive validación y persiste hacia reporte vulnerable (#1664); fecha XLSX del último día abierto rechazada por `datetime` frente a `date` (#1472); whitespace-only en monto opcional rechaza fila válida (#1030); precisión >4 se redondea al persistir sin error y desalineó el identity hash (#1663); cuenta inactiva permitida, criterio pendiente |
| `cacao_accounting/imports/adapters/cash_forecast_entry.py` | Revisado en checkpoint y revalidado: #1049/#1381 permite insertar en forecast Approved; #1050/#1196/#1292 monto <=0; `Infinity` pasa validación y se persiste en `Numeric(20,4)` (#950, comentario 6562154670); XLSX con `notes=None` persiste literalmente `"None"` (#1033, comentario 6562169667) |
| `cacao_accounting/query_tools/handlers/banking.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/banking.py` | Pendiente |

### Flujo documental compartido (11 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/document_flow/__init__.py` | Pendiente |
| `cacao_accounting/document_flow/context.py` | Pendiente |
| `cacao_accounting/document_flow/currency_resolver.py` | Pendiente |
| `cacao_accounting/document_flow/payment.py` | Pendiente |
| `cacao_accounting/document_flow/registry.py` | Pendiente |
| `cacao_accounting/document_flow/repository.py` | Pendiente |
| `cacao_accounting/document_flow/service.py` | Pendiente |
| `cacao_accounting/document_flow/status.py` | Pendiente |
| `cacao_accounting/document_flow/tracing.py` | Pendiente |
| `cacao_accounting/document_flow/tree.py` | Pendiente |
| `cacao_accounting/document_flow/validation.py` | Pendiente |

### Frontend compartido (6 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/static/js/dashboard.js` | Pendiente |
| `cacao_accounting/static/js/document-flow-tree.js` | Pendiente |
| `cacao_accounting/static/js/purchase-sourcing.js` | Pendiente |
| `cacao_accounting/static/js/smart-select.js` | Parcial: en Imports se revisaron `init()`, `bindFilterSources()`, `handleFilterChange()`, `preloadOptions()` y `fetchOptions()`; no limpia listeners externos al desmontarse el libro dentro de `x-if` (#1667); siguen pendientes otras funciones y consumidores |
| `cacao_accounting/static/js/sw.js` | Pendiente |
| `cacao_accounting/static/js/transaction-form.js` | Parcial: `mapColumnHeader()`/plantillas XLSX muestran `col.label` crudo (#1666); #1670 confirma por traza que `description` del schema/API no existe en `newLine()` ni se serializa en payload; mapeo por doctype pendiente de criterio (QA independiente, comentario 6563786423). `validateImport()` protege respuestas tardías por snapshot/requestId; resto de eventos, serialización y estados pendiente |

### I2F / Inventario (23 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/inventario/__init__.py` | Pendiente |
| `cacao_accounting/inventario/forms.py` | Pendiente |
| `cacao_accounting/inventario/routes.py` | Pendiente |
| `cacao_accounting/inventario/service.py` | Pendiente; commits `4d899a36`/`67d41a0c` incluyen deltas de fix de alcance/complejidad por revisar en I2F |
| `cacao_accounting/inventario/services.py` | Pendiente |
| `cacao_accounting/inventario/templates/inventario.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/articulo.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/articulo_lista.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/articulo_nuevo.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/bodega.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/bodega_lista.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/bodega_nuevo.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/entrada.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/entrada_lista.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/entrada_nuevo.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/lote.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/lote_lista.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/lote_nuevo.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/stock_reconciliation_nuevo.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/uom.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/uom_lista.html` | Pendiente |
| `cacao_accounting/inventario/templates/inventario/uom_nuevo.html` | Pendiente |
| `cacao_accounting/inventario/valuation_settings.py` | Pendiente |

### Identidad, permisos y administración (50 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/admin/__init__.py` | Pendiente |
| `cacao_accounting/admin/navigation.py` | Pendiente |
| `cacao_accounting/admin/routes.py` | Pendiente |
| `cacao_accounting/admin/services.py` | Pendiente |
| `cacao_accounting/admin/session_security_service.py` | Pendiente |
| `cacao_accounting/admin/templates/admin.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/approval_matrix.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/budget_control_config.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/default_accounts.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/dimension_values.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/email_log.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/email_settings.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/external_document_validation.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/inventory_valuation.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/item_prices.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/ledger_mapping_rules.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/modulos.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/party_groups.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/pending_approvals.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/price_lists.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/purchase_reconciliation_config.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/purchase_sourcing_config.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/rol_form.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/rol_permisos.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/roles.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/sales_matching_config.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/session_security.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/system_language.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/tax_rules.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/tax_template_items.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/tax_templates.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/taxes.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/usuario_companias.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/usuario_form.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/usuario_password.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/usuario_roles.html` | Pendiente |
| `cacao_accounting/admin/templates/admin/usuarios.html` | Pendiente |
| `cacao_accounting/auth/__init__.py` | Lectura previa; integración pendiente |
| `cacao_accounting/auth/account_throttling.py` | Lectura previa; integración pendiente |
| `cacao_accounting/auth/device_verification.py` | Lectura previa; integración pendiente |
| `cacao_accounting/auth/forms.py` | Lectura previa; integración pendiente |
| `cacao_accounting/auth/helpers.py` | Lectura previa; integración pendiente |
| `cacao_accounting/auth/permisos.py` | Lectura previa; integración pendiente |
| `cacao_accounting/auth/roles.py` | Lectura previa; integración pendiente |
| `cacao_accounting/auth/templates/forgot_password.html` | Pendiente |
| `cacao_accounting/auth/templates/login.html` | Pendiente |
| `cacao_accounting/auth/templates/profile.html` | Pendiente |
| `cacao_accounting/auth/templates/reset_password.html` | Pendiente |
| `cacao_accounting/auth/templates/test_roles.html` | Pendiente |
| `cacao_accounting/auth/templates/verify_otp.html` | Pendiente |

### Importaciones — flujos y adaptadores (28 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/api/line_import.py` | Revisado/revalidado: los cuatro endpoints y helpers de carga, esquema, parsing XLSX, ownership, permisos, validación de líneas y respuestas se cotejaron con todos sus consumidores. Workbook/temporal y materialización previa al límite (#1446/#1603/#1652, 6563114348/6563704367); `bank_account` sin ownership (#1665); validación no acumulativa de pagos (#1398, comentarios 6563728434/6563739357; #1205/#1439), aislada al agregar `reference_document` porque el esquema oficial tropieza antes con #1456. Los demás referencias revisadas validan compañía; no se detectó fuga cross-company adicional |
| `cacao_accounting/api/line_import_registry.py` | Revisado/revalidado: 15 doctype keys/módulos y todos sus campos, alias, requeridos y tipos cotejados con `_validate_schema_columns()` y normalizadores JS; sin colisiones key/label/alias. Contratos de API, `transaction-form.js`, formulario journal y consumer dedicado en `bancos/templates/bancos/conciliacion_facturas_pagos.html` rastreados. Etiquetas sin localización (#1666); `journal_entry.bank_account` sin ownership (#1665). 13 schemas operacionales declaran `description`; su pérdida al insertar líneas genéricas queda trazada a #1670 y el campo destino varía por doctype, pendiente de política |
| `cacao_accounting/imports/__init__.py` | Revisado en checkpoint: módulo solo declara el paquete y su docstring |
| `cacao_accounting/imports/adapters/__init__.py` | Revisado en checkpoint: módulo solo declara el paquete y su docstring |
| `cacao_accounting/imports/adapters/base.py` | Revisado/revalidado: `localized_columns()` delega al normalizador común; `validate_row()` revisado con sus consumidores y cubre prefijos `=,+,-,@` y columnas ausentes/None/cadena vacía; no recorta whitespace (`nombre="   "`, #1052) ni detecta LF inicial en celdas bancarias (#1664). `validate_document()` es no-op; `build_document()` y `persist_document()` son contratos abstractos. Los validadores particulares se auditan en cada adaptador |
| `cacao_accounting/imports/adapters/chart_of_accounts.py` | Parcial: filas con `document_ref` repetido se pierden (#1346); padre inexistente aceptado/persistido (#1063, comentario 6563571527); `clasificacion=not-a-class` pasa y persiste pese al guard del formulario (#1668). Los clasificadores normales devuelven `None`, pero el reporte conserva el monto bajo “no clasificados”; no hay evidencia de pérdida del total GL ni de bloqueo de posteo. `tipo` arbitrario también persiste; valores permitidos/uso pendientes de triaje. `grupo` solo reconoce `true,1,si,yes`; typos pasan como false y `sí` no coincide con el loader de catálogos; formato de plantilla no definido. `moneda` se asigna directa, pero disponibilidad/actividad como moneda de cuenta sigue sin contrato. Candidato estático de cache: import no invalida `smart-select-master-data`, mientras el alta manual sí; efecto TTL Redis 300s sin repro aún. Criterios `tipo`/grupo/moneda/cache pendientes |
| `cacao_accounting/imports/adapters/customer.py` | Parcial: revisión completa de columnas, build/persist, IDs/código, `CompanyParty`, agrupación/contadores, rutas/modelos y aislamiento. `document_ref` repetido o vacío (`no_ref`) pierde filas posteriores (#1346, comentarios 6562095933/6562263037); nombre whitespace-only persiste (#1052, comentario 6562136172). Dos batches con el mismo tax_id crean Party distintos; no hay unicidad ni dedupe en la ruta manual, por lo que la política de reutilización queda pendiente. `clasificacion`/`grupo` se omiten y el mapping destino no está definido. Sin issue nuevo |
| `cacao_accounting/imports/adapters/journal_entry.py` | Parcial: importes/balance, fecha/período, validación contable, construcción, libros y persistencia revisados. Fechas distintas por asiento aceptadas y segunda descartada (#1530); fecha XLSX `datetime` pasa preview y falla en `_parse_date()` (#1201, 6563618846); libro seleccionado se amplía a activos (#1163, 6563588354). Referencias AP/AR exigen compañía/tipo/tercero y open item único. Moneda explícita fuera de columnas no se valida activa en `_validate_accounting_lines`, aunque el service valida moneda de cabecera (#758; discrepancia pendiente de repro/alcance, sin nuevo issue). Resto de excepciones/consumidores contables pendiente |
| `cacao_accounting/imports/adapters/purchase_order.py` | Revisado/revalidado: adaptador legado completo (validación, moneda/tasa, construcción y persistencia); sin consumidores productivos encontrados, no es el adaptador registrado. Su `_currency_and_rate()` también sustituye tasa numérica cero por fallback histórico (#1382); el adaptador activo está en `transaction_documents.py` |
| `cacao_accounting/imports/adapters/transaction_documents.py` | Parcial: base y 12 subclases revisadas con `ImportService`; `sequence_id`/identificador (#1659), tasa numérica cero fallback (#1382), fecha XLSX (#1201), origen solo FK sin `DocumentRelation` (#1053, 6563564158), artículo no habilitado (#1060, 6563561540), tercero de rol incorrecto (#1532, 6563563136), y precio unitario cero pasa importación pero no aprobación (criterio pendiente). Solo construye/adjunta borradores y líneas; no muta ni cancela evidencia ya registrada. Posting de GL valida conversión por libro, pero conversión de otros ledgers no se rastreó aquí. Pendientes sin confirmar: cabeceras distintas dentro del grupo, serial requerido/cantidad en subtipos (#1531 comparte la palabra `serie`, raíz distinta), mapeo por línea fuente y semántica de precio cero |
| `cacao_accounting/imports/adapters/vendor.py` | Parcial: revisión completa de columnas, build/persist, generación de código, `CompanyParty`, agrupación/contadores, rutas/modelos y aislamiento de compañía. `document_ref` repetido pierde filas posteriores (#1346, comentario 6562113952); nombre whitespace-only persiste (#1052). `clasificacion`/`grupo` figuran en la plantilla pero no se asignan; campo/semántica destino pendientes de criterio. No se confirmó otro defecto |
| `cacao_accounting/imports/column_labels.py` | Revisado/revalidado: las etiquetas visibles español/inglés y la normalización canónica se cotejaron con `BaseImportAdapter`, generación de plantillas, `ImportService.validate()/preview()` y todas las listas `columns` declaradas por adaptadores (incluidos tipos derivados de documentos); las 9 clases con listas literales hacen round-trip sin colisiones por idioma |
| `cacao_accounting/imports/models.py` | Revisado/revalidado: campos y FK de `ImportBatch`/`ImportBatchError` cotejados con creación, subida, validación, ejecución, cancelación, recuperación y consultas; estados 0–8 documentados en el modelo y tratados en servicio/rutas. `ImportBatchError` usa cascade al borrar lote; no existe ruta de borrado del lote. No hay migración SQL dedicada localizada; resto del componente sigue abierto |
| `cacao_accounting/imports/readers/__init__.py` | Revisado/revalidado: solo contiene cabecera SPDX y docstring; no registra lectores ni ejecuta lógica al importar |
| `cacao_accounting/imports/readers/base.py` | Revisado/revalidado: `NormalizedTable` usa listas independientes por defecto y declara columnas/filas/formato; el contrato coincide con las cuatro clases de lector registradas y con `ImportService`/`_normalize_rows()`. Las filas de ancho irregular pasan sin validación y la truncación por `zip` queda documentada en #1534/#1474/#1652 como comportamiento del consumidor |
| `cacao_accounting/imports/readers/csv_reader.py` | Revisado y revalidado: encabezado/cero filas (#1200), celda excedente descartada por `_normalize_rows()` (#1534/#1474/#1652), y tabulado aceptado por fallback pero leido como una columna (#1662) |
| `cacao_accounting/imports/readers/ods_reader.py` | Revisado y revalidado: celdas vacias -> `""`; expansion `numbercolumnsrepeated=100000` (#1392), `numberrowsrepeated=3` omite dos filas (#1345/#1396), `CoveredTableCell` desplaza campos (#1475, comentario 6559273111) |
| `cacao_accounting/imports/readers/xls_reader.py` | Revisado y revalidado: lector contrastado con 12 muestras oficiales xlrd y `Formate.xls`; celdas fecha se devuelven como serial numérico y el adaptador bancario falla ISO (#1201, comentarios 6562216349/6563435620). Un XLS corrupto lanza `CompDocError`; ver checkpoint de fixtures oficiales |
| `cacao_accounting/imports/readers/xlsx_reader.py` | Revisado y revalidado en HEAD actual: `read()` usa `data_only=True`, hoja activa y `values_only`; celda XLSX vacía llega como `None` y se confirmó su persistencia como `"None"` en notes (#1033, comentario 6562169667). Las fechas Excel llegan como `datetime` (#1201); no se abrió hallazgo adicional en este pase |
| `cacao_accounting/imports/routes.py` | Parcial: matriz completa de helpers/rutas/permisos/estados y contratos revalidada en HEAD `c62c360`; `record_type` inválido -> 500 (#1661), fallback tabulado (#1662), CSV de una columna sin python-magic (#1631), plantillas con `serie` (#1531), estado/reintentos (#1528), cero filas (#1200), CSRF (#1648). Candidato de acceso directo con `access=False, consultar=True` reproducido en misma compañía; semántica del permiso `access` aún requiere criterio, no issue nuevo. Relación posible con consolidación general #1649, sin duplicado específico. Política `validar` + `editar` también abierta. Segunda revisión no halló fuga entre compañías; la selección de libro de asientos sí se pierde aguas abajo en `journal_service.py` y se vinculó a #1163 (comentario 6563588354) |
| `cacao_accounting/imports/services/__init__.py` | Revisado en checkpoint: módulo solo declara el paquete y su docstring |
| `cacao_accounting/imports/services/import_service.py` | Parcial: `validate()` cero filas (#1200), celdas excedentes (#1534/#1474/#1652), agrupación/worker contrastados con persistencia bancaria y maestra; duplicados intra-grupo (#1507), pérdida de filas con referencia repetida o vacía `no_ref` (#1346), requeridos whitespace-only (#1052), montos no finitos (#950), commit previo a contador y handler SQL sin rollback (#1062), fecha XLSX de cierre del período rechazada mientras el CSV equivalente pasa (#1472), fechas distintas del asiento aceptadas con fecha primera (#1530); se revalidaron capturas de ejecución y cancelación (#1032/#1395/#1319/#1528). `_finalize_execution()` posterior a recuperación puede cambiar status 7 a 5/6 y dejar `SYSTEM_TIMEOUT` (#1203). Dos reproducciones independientes confirmaron que cancelar status 4 con CSV vacío deja `cancel_requested=True`/`completed_at` y status 4; evidencia añadida a #1032 (6563598406), relacionada con CSV vacío #1200. Estados/reintentos restantes pendientes |
| `cacao_accounting/imports/templates/imports/detail.html` | Revisado/revalidado: estados, compañía, permisos, descarga, upload/validate/execute/cancel y preview contrastados con las rutas; CSRF ausente en los POST (#1648), estados 2/7 sin controles de recuperación (#1393); botón Validar depende de `validar`, aunque la ruta requiere además `editar` (política abierta) |
| `cacao_accounting/imports/templates/imports/index.html` | Revisado y revalidado: herencia, permisos visibles, estados 0–8, progreso de lotes, enlaces y valores nulos contrastados con `routes.index`; sin defecto nuevo aislado |
| `cacao_accounting/imports/templates/imports/new.html` | Revisado/revalidado: permisos/formulario y Smart Select de compañía, tipo, serie y libro; filtro reactivo conserva serie de otro tipo (#1659); alternar `journal_entry` desmonta el libro pero deja listeners externos retenidos (#1667); POST sin CSRF (#1648) |
| `cacao_accounting/imports/utils/__init__.py` | Revisado/revalidado: solo contiene cabecera SPDX y docstring; los consumidores importan `recovery`/`validation` directamente y el paquete no expone lógica implícita |
| `cacao_accounting/imports/utils/recovery.py` | Parcial: función y llamada de `create_app()` revalidadas en HEAD `c62c360`; recovery al arranque marca status 4 como fallo si `started_at` es nulo o supera 4 h (#1203); `started_at` retenido bloquea reintento (#1528). Transición posterior del worker status 7→5/6 deja `SYSTEM_TIMEOUT` (#1203, 6563427237). Tres agentes reprodujeron recoveries concurrentes sobre un lote expirado que generan dos errores `SYSTEM_TIMEOUT` para un batch (#1669; QA 6563660967); SQLite WAL únicamente, PostgreSQL no probado. Resto de concurrencia y errores del arranque pendiente |
| `cacao_accounting/imports/utils/validation.py` | Revisado/revalidado: función única `is_period_open()` filtra compañía, período habilitado/abierto y límites inclusivos. Se enumeraron todos los consumidores (bank_statement, journal_entry, purchase_order legado, transaction_documents e ImportService); sus discrepancias `date`/`datetime` y parsing Excel quedan trazadas a #1472/#1201 en cada adaptador |

### Interfaz compartida — Jinja2 (22 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/templates/400.html` | Pendiente |
| `cacao_accounting/templates/403.html` | Pendiente |
| `cacao_accounting/templates/404.html` | Pendiente |
| `cacao_accounting/templates/admin/balance_confirmation_detail.html` | Pendiente |
| `cacao_accounting/templates/admin/balance_confirmation_new.html` | Pendiente |
| `cacao_accounting/templates/base.html` | Pendiente |
| `cacao_accounting/templates/detail_view_macros.html` | Pendiente |
| `cacao_accounting/templates/document_flow_related_list.html` | Pendiente |
| `cacao_accounting/templates/macros.html` | Pendiente |
| `cacao_accounting/templates/party_company_settings_form.html` | Pendiente |
| `cacao_accounting/templates/party_detail_sections.html` | Pendiente |
| `cacao_accounting/templates/party_legal_fields.html` | Pendiente |
| `cacao_accounting/templates/party_profile_fields.html` | Pendiente |
| `cacao_accounting/templates/public/confirm_balance_status.html` | Pendiente |
| `cacao_accounting/templates/public/confirm_balance_success.html` | Pendiente |
| `cacao_accounting/templates/public/confirm_balance_verify.html` | Pendiente |
| `cacao_accounting/templates/public/confirm_balance_view.html` | Pendiente |
| `cacao_accounting/templates/public/validation_result.html` | Pendiente |
| `cacao_accounting/templates/setup/setup.html` | Pendiente |
| `cacao_accounting/templates/smart_select_field.html` | Parcial: macro/contrato del selector revisado para Imports; fuente externa y recarga con cambio confirmaron #1667; otros consumidores pendientes |
| `cacao_accounting/templates/tasks/my.html` | Pendiente |
| `cacao_accounting/templates/transaction_form_macros.html` | Pendiente |

### O2C — Ventas (24 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/ventas/__init__.py` | Pendiente |
| `cacao_accounting/ventas/forms.py` | Pendiente |
| `cacao_accounting/ventas/routes.py` | Pendiente |
| `cacao_accounting/ventas/services.py` | Pendiente |
| `cacao_accounting/ventas/templates/ventas.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/cliente.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/cliente_lista.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/cliente_nuevo.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/cotizacion.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/cotizacion_lista.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/cotizacion_nuevo.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/entrega.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/entrega_lista.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/entrega_nuevo.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/factura_venta.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/factura_venta_devolucion_lista.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/factura_venta_lista.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/factura_venta_nuevo.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/orden_venta.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/orden_venta_lista.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/orden_venta_nuevo.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/solicitud_venta.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/solicitud_venta_lista.html` | Pendiente |
| `cacao_accounting/ventas/templates/ventas/solicitud_venta_nuevo.html` | Pendiente |

### Persistencia y modelos compartidos (2 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/database/__init__.py` | Parcial: identidad/hash y eventos de BankTransaction verificados; índice identity_key no único; `ComprobanteContableDetalle.bank_account_id` y `GLEntry.bank_account_id` tienen FK simples sin restricción de misma compañía (#1665); resto pendiente |
| `cacao_accounting/database/helpers.py` | Pendiente |

### R2R / Contabilidad y motor (110 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/accounting_engine/__init__.py` | Pendiente |
| `cacao_accounting/accounting_engine/common/__init__.py` | Pendiente |
| `cacao_accounting/accounting_engine/common/context.py` | Pendiente |
| `cacao_accounting/accounting_engine/common/fiscal.py` | Pendiente |
| `cacao_accounting/accounting_engine/common/rounding.py` | Pendiente |
| `cacao_accounting/accounting_engine/document_builders.py` | Pendiente |
| `cacao_accounting/accounting_engine/fiscal/__init__.py` | Pendiente |
| `cacao_accounting/accounting_engine/fiscal/engine.py` | Pendiente; commit `67d41a0c` reestructura código para umbral de complejidad, delta por auditar |
| `cacao_accounting/accounting_engine/fiscal/resolver.py` | Pendiente |
| `cacao_accounting/accounting_engine/gl_posting_builder.py` | Pendiente; commit `67d41a0c` reestructura código para umbral de complejidad, delta por auditar |
| `cacao_accounting/accounting_engine/landed_cost/__init__.py` | Pendiente |
| `cacao_accounting/accounting_engine/landed_cost/engine.py` | Pendiente |
| `cacao_accounting/accounting_engine/orchestrator/__init__.py` | Pendiente |
| `cacao_accounting/accounting_engine/orchestrator/event_orchestrator.py` | Pendiente |
| `cacao_accounting/accounting_engine/orchestrator/mapper.py` | Pendiente |
| `cacao_accounting/accounting_engine/settlement/__init__.py` | Pendiente |
| `cacao_accounting/accounting_engine/settlement/engine.py` | Pendiente |
| `cacao_accounting/accounting_engine/snapshots/__init__.py` | Pendiente |
| `cacao_accounting/accounting_engine/snapshots/serializer.py` | Pendiente |
| `cacao_accounting/contabilidad/__init__.py` | Pendiente |
| `cacao_accounting/contabilidad/arap_allocation.py` | Pendiente |
| `cacao_accounting/contabilidad/arap_gl_reconciliation.py` | Pendiente |
| `cacao_accounting/contabilidad/arap_ledger_service.py` | Pendiente |
| `cacao_accounting/contabilidad/auxiliares.py` | Pendiente |
| `cacao_accounting/contabilidad/balance_confirmation.py` | Pendiente |
| `cacao_accounting/contabilidad/balance_confirmation_bp.py` | Pendiente; commit `4154dbe2` ajusta formato para lint, delta por auditar |
| `cacao_accounting/contabilidad/budget_import_service.py` | Pendiente |
| `cacao_accounting/contabilidad/budget_report_service.py` | Pendiente |
| `cacao_accounting/contabilidad/budget_service.py` | Pendiente |
| `cacao_accounting/contabilidad/cancellation_service.py` | Parcial: detector de dependencias activas y filtro de partidas bancarias revisados (#1316) |
| `cacao_accounting/contabilidad/ctas/__init__.py` | Pendiente |
| `cacao_accounting/contabilidad/currency_guard.py` | Pendiente |
| `cacao_accounting/contabilidad/default_accounts.py` | Pendiente |
| `cacao_accounting/contabilidad/exchange_rate_import_service.py` | Pendiente |
| `cacao_accounting/contabilidad/exchange_revaluation_service.py` | Pendiente |
| `cacao_accounting/contabilidad/fiscal_year_closing.py` | Pendiente |
| `cacao_accounting/contabilidad/forms.py` | Pendiente |
| `cacao_accounting/contabilidad/gl/__init__.py` | Pendiente |
| `cacao_accounting/contabilidad/gl/static/gl.js` | Pendiente |
| `cacao_accounting/contabilidad/gl/templates/gl_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/gl/templates/gl_new.html` | Pendiente |
| `cacao_accounting/contabilidad/journal_repository.py` | Pendiente |
| `cacao_accounting/contabilidad/journal_service.py` | Parcial: ruta `cancel_submitted_journal` y guardas revisadas para dependencia bancaria (#1316); `_validate_journal_line()` no contrasta la compañía de `bank_account_id` y `_line_model()` persiste la cuenta cruzada (#1665). `_authorized_journal_books()` ignora `requested_books` y devuelve todos los libros activos, descartando el selector del formulario/importación (#1163; import repro y comentario 6563588354) |
| `cacao_accounting/contabilidad/ledger_mapping_service.py` | Pendiente |
| `cacao_accounting/contabilidad/posting.py` | Pendiente |
| `cacao_accounting/contabilidad/posting_service.py` | Parcial: `cancel_document` y reversión GL revisados para dependencia bancaria (#1316); `_comprobante_entry_params()` copia `bank_account_id` a GL sin revisar la compañía propietaria (#1665) |
| `cacao_accounting/contabilidad/presupuesto.py` | Pendiente |
| `cacao_accounting/contabilidad/project_capitalization_service.py` | Pendiente |
| `cacao_accounting/contabilidad/recurring_journal_service.py` | Pendiente |
| `cacao_accounting/contabilidad/routes.py` | Pendiente |
| `cacao_accounting/contabilidad/services.py` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/book.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/book_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/book_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/centro-costo.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/centro-costo_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/centro-costo_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/cuenta.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/cuenta_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/cuenta_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad_editar.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/exchange_revaluation.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/exchange_revaluation_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/exchange_revaluation_nueva.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_ajuste.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_auditoria.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_nuevo.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_closing_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_closing_nuevo.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/journal.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/journal_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/journal_nuevo.html` | Parcial: importación copia `bank_account` al renglón y renderiza `column.label` sin traducir en headers/plantilla/preview (#1665/#1666); resto de Alpine/Jinja, permisos y guardado pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/moneda.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/moneda_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/moneda_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/monthly_close_assistant.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/naming_series_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/naming_series_nueva.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/periodo.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/periodo_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/periodo_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/detail.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/form.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/import.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/line_form.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/list.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/real_vs_budget.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/proyecto.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/proyecto_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/proyecto_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/recurring_journal_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/recurring_journal_nuevo.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/recurring_journal_ver.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/tc.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/tc_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/tc_importar.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/tc_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/tree_macros.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/unidad.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/unidad_crear.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/unidad_lista.html` | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad_cash_flow_config.html` | Pendiente |

### R2R / Reportes (17 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/reportes/__init__.py` | Pendiente |
| `cacao_accounting/reportes/analytics.py` | Pendiente |
| `cacao_accounting/reportes/cash_flow.py` | Pendiente |
| `cacao_accounting/reportes/documentos.py` | Pendiente |
| `cacao_accounting/reportes/helpers.py` | Parcial: `_report_to_matrix()` y `_export_operational_report()` contrastados en CSV de movimiento bancario; `_spreadsheet_value()` neutraliza `= + - @ TAB CR` pero no LF, que se exporta intacto (#1664). Otros helpers/formatos pendientes |
| `cacao_accounting/reportes/internal_control.py` | Pendiente |
| `cacao_accounting/reportes/periods.py` | Pendiente |
| `cacao_accounting/reportes/routes.py` | Parcial: `/reports/bank-movement` requiere login y módulo cash/banking, construye filtros y obtiene el reporte; `_render_operational_framework()` llama `_export_operational_report()` con el estado de filtros. La ruta completa, demás reportes y permisos/alcances siguen pendientes (#1664) |
| `cacao_accounting/reportes/semantic.py` | Pendiente |
| `cacao_accounting/reportes/services.py` | Parcial: `get_bank_movement_detail()`/`_build_transaction_row_values()` llevan `BankTransaction.description` a `remarks` del reporte sin sanitizar (#1664); otros reportes y servicios pendientes |
| `cacao_accounting/reportes/templates/reportes/cash_flow_blocked.html` | Pendiente |
| `cacao_accounting/reportes/templates/reportes/financial_report.html` | Pendiente |
| `cacao_accounting/reportes/templates/reportes/internal_control.html` | Pendiente |
| `cacao_accounting/reportes/templates/reportes/operational_report.html` | Parcial: los enlaces de exportación conservan los parámetros actuales y agregan `export=csv|xlsx|pdf`; el CSV llega al helper del reporte bancario (#1664). Resto de expresiones, paginación y presentación pendiente |
| `cacao_accounting/reportes/templates/reportes/report_macros.html` | Pendiente |
| `cacao_accounting/reportes/templates/reportes/report_pdf.html` | Pendiente |
| `cacao_accounting/reportes/templates/reportes/report_table.html` | Pendiente |

### S2P / Compras (44 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/compras/__init__.py` | Pendiente |
| `cacao_accounting/compras/forms.py` | Pendiente |
| `cacao_accounting/compras/gr_ir_service.py` | Pendiente |
| `cacao_accounting/compras/purchase_invoice_draft_service.py` | Pendiente |
| `cacao_accounting/compras/purchase_order_comparison_service.py` | Pendiente |
| `cacao_accounting/compras/purchase_reconciliation_service.py` | Pendiente |
| `cacao_accounting/compras/purchase_request_comparison_service.py` | Pendiente |
| `cacao_accounting/compras/purchase_sourcing_service.py` | Pendiente |
| `cacao_accounting/compras/routes.py` | Pendiente |
| `cacao_accounting/compras/services.py` | Pendiente |
| `cacao_accounting/compras/templates/compras.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/comparativo_ofertas.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/comparativo_ofertas_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/comparativo_ordenes.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/comparativo_ordenes_seleccionar.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/comparativo_solicitud.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/cotizacion_proveedor.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/cotizacion_proveedor_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/cotizacion_proveedor_nueva.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/factura_compra.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/factura_compra_devolucion_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/factura_compra_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/factura_compra_nuevo.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/gr_ir.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/import_landed_cost.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/import_landed_cost_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/import_landed_cost_nuevo.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/orden_compra.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/orden_compra_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/orden_compra_nuevo.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/proveedor.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/proveedor_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/proveedor_nuevo.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/purchase_reconciliation.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/purchase_reconciliation_panel.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/recepcion.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/recepcion_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/recepcion_nuevo.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_compra.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_compra_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_compra_nueva.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_cotizacion.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_cotizacion_lista.html` | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_cotizacion_nuevo.html` | Pendiente |

### Servicios compartidos y plataforma (102 archivos)

| Archivo | Estado |
|---|---|
| `cacao_accounting/__main__.py` | Pendiente |
| `cacao_accounting/api/dashboard.py` | Pendiente |
| `cacao_accounting/api/templates/empy.html` | Pendiente |
| `cacao_accounting/approval_engine.py` | Pendiente |
| `cacao_accounting/approval_policy.py` | Pendiente |
| `cacao_accounting/attachment_service.py` | Lectura previa; integración pendiente |
| `cacao_accounting/audit_chain.py` | Lectura previa; integración pendiente |
| `cacao_accounting/audit_trail_service.py` | Lectura previa; integración pendiente |
| `cacao_accounting/cache.py` | Pendiente |
| `cacao_accounting/cancellation_scope.py` | Pendiente |
| `cacao_accounting/cli.py` | Pendiente |
| `cacao_accounting/collaboration_service.py` | Pendiente; modificado en HEAD `41c96c43`, diff de guards de estado aún sin revisar |
| `cacao_accounting/company_context.py` | Pendiente |
| `cacao_accounting/config.py` | Pendiente |
| `cacao_accounting/control_review_service.py` | Parcial: resolución de actor y flujo de revisión bancaria contrastados (#1067/#1194); resto pendiente |
| `cacao_accounting/datos/dev/data.py` | Pendiente |
| `cacao_accounting/decorators.py` | Pendiente |
| `cacao_accounting/document_authorship.py` | Pendiente |
| `cacao_accounting/document_identifiers.py` | Parcial: _pick_naming_series valida tipo/compania y rechaza serie incompatible (#1659); resto pendiente |
| `cacao_accounting/exceptions/mensajes.py` | Pendiente |
| `cacao_accounting/fiscal_persistence_service.py` | Pendiente |
| `cacao_accounting/fiscal_preview_service.py` | Pendiente |
| `cacao_accounting/i18n.py` | Pendiente |
| `cacao_accounting/internal_control_service.py` | Parcial: transición permitida y guard de `BankTransaction` contrastados (#1082); resto pendiente |
| `cacao_accounting/internal_control_sql.py` | Pendiente |
| `cacao_accounting/ledger_queries.py` | Pendiente |
| `cacao_accounting/limiter.py` | Pendiente |
| `cacao_accounting/list_filters.py` | Pendiente |
| `cacao_accounting/logistics.py` | Pendiente |
| `cacao_accounting/logs.py` | Pendiente |
| `cacao_accounting/matching_config_service.py` | Pendiente |
| `cacao_accounting/messaging/email.py` | Pendiente |
| `cacao_accounting/migrations/20260809_0001_baseline.py` | Pendiente |
| `cacao_accounting/migrations/20261015_0001_audit_hash_version.py` | Pendiente |
| `cacao_accounting/module_badges.py` | Pendiente |
| `cacao_accounting/num2words.py` | Pendiente |
| `cacao_accounting/party_management.py` | Pendiente; modificado en HEAD `41c96c43`, diff de guards de edición aún sin revisar |
| `cacao_accounting/party_settings.py` | Pendiente |
| `cacao_accounting/portal/templates/portal/base_portal.html` | Pendiente |
| `cacao_accounting/portal/templates/portal/customer_dashboard.html` | Pendiente |
| `cacao_accounting/portal/templates/portal/delivery_detail.html` | Pendiente |
| `cacao_accounting/portal/templates/portal/invoice_detail.html` | Pendiente |
| `cacao_accounting/portal/templates/portal/order_detail.html` | Pendiente |
| `cacao_accounting/portal/templates/portal/quotation_detail.html` | Pendiente |
| `cacao_accounting/portal/templates/portal/receipt_detail.html` | Pendiente |
| `cacao_accounting/portal/templates/portal/supplier_dashboard.html` | Pendiente |
| `cacao_accounting/printing/admin_routes.py` | Pendiente |
| `cacao_accounting/printing/context.py` | Pendiente |
| `cacao_accounting/printing/exceptions.py` | Pendiente |
| `cacao_accounting/printing/models.py` | Pendiente |
| `cacao_accounting/printing/registry.py` | Pendiente |
| `cacao_accounting/printing/routes.py` | Pendiente |
| `cacao_accounting/printing/seed.py` | Pendiente |
| `cacao_accounting/printing/service.py` | Pendiente; commit `67d41a0c` reestructura código para complejidad, delta pendiente de auditar |
| `cacao_accounting/printing/settings.py` | Pendiente |
| `cacao_accounting/printing/snippets.py` | Pendiente |
| `cacao_accounting/printing/templates/admin/print_template_form.html` | Pendiente |
| `cacao_accounting/printing/templates/admin/print_template_list.html` | Pendiente |
| `cacao_accounting/printing/templates/admin/print_validation_settings.html` | Pendiente |
| `cacao_accounting/printing/validation.py` | Pendiente |
| `cacao_accounting/printing/validators.py` | Pendiente |
| `cacao_accounting/query_tools/audit.py` | Pendiente |
| `cacao_accounting/query_tools/bootstrap.py` | Pendiente |
| `cacao_accounting/query_tools/context.py` | Pendiente |
| `cacao_accounting/query_tools/decorators.py` | Pendiente |
| `cacao_accounting/query_tools/errors.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/accounting.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/advanced.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/aging.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/analytics.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/audit_trail.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/companies.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/configuration.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/discovery.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/documents.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/operational.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/payables.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/receivables.py` | Pendiente |
| `cacao_accounting/query_tools/handlers/treasury.py` | Pendiente |
| `cacao_accounting/query_tools/pagination.py` | Pendiente |
| `cacao_accounting/query_tools/permissions.py` | Pendiente |
| `cacao_accounting/query_tools/publication.py` | Pendiente |
| `cacao_accounting/query_tools/registry.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/accounting.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/audit_trail.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/common.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/companies.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/documents.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/payables.py` | Pendiente |
| `cacao_accounting/query_tools/schemas/receivables.py` | Pendiente |
| `cacao_accounting/runtime_mode.py` | Pendiente |
| `cacao_accounting/search_select.py` | Parcial: catálogo y filtros de company/book/naming_series revisados; resto pendiente |
| `cacao_accounting/server.py` | Pendiente |
| `cacao_accounting/setup/catalogs.py` | Pendiente |
| `cacao_accounting/setup/forms.py` | Pendiente |
| `cacao_accounting/setup/repository.py` | Pendiente |
| `cacao_accounting/setup/service.py` | Pendiente |
| `cacao_accounting/setup/templates/setup.html` | Pendiente |
| `cacao_accounting/tax_pricing_service.py` | Pendiente |
| `cacao_accounting/tax_rule_service.py` | Pendiente |
| `cacao_accounting/warehouse_accounting.py` | Pendiente |
| `cacao_accounting/withholding_service.py` | Pendiente |

## Configuración, SQL y catálogos

| Archivo | Estado |
|---|---|
| `.dockerignore` | Pendiente |
| `.gitignore` | Pendiente |
| `.replit` | Pendiente |
| `docker-entry-point.sh` | Pendiente |
| `scripts/run_server.sh` | Pendiente |
| `scripts/run_test.sh` | Pendiente |
| `scripts/run_tests_by_file.sh` | Pendiente |
| `scripts/update_translations.sh` | Pendiente |
| `.github/FUNDING.yml` | Pendiente |
| `.github/workflows/ci.yml` | Revisado en checkpoint: definicion completa leida; integracion aun pendiente |
| `.github/workflows/databases.yml` | Revisado en checkpoint: definicion completa leida; integracion aun pendiente |
| `.github/workflows/lint.yml` | Revisado en checkpoint: definición completa leída; el cambio `c62c3604` al comando de Complexipy queda pendiente de integrar |
| `.github/workflows/publish.yml` | Pendiente |
| `.github/workflows/python.yml` | Revisado en checkpoint: definicion completa leida; integracion aun pendiente |
| `.mypy.ini` | Pendiente |
| `Dockerfile` | Pendiente |
| `babel.cfg` | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/base_en.json` | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/base_es.json` | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/ifrs_smes_en.json` | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/niif_pymes_es.json` | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/us_gaap.json` | Pendiente |
| `cacao_accounting/static/manifest.json` | Pendiente |
| `cacao_accounting/static/package-lock.json` | Pendiente |
| `cacao_accounting/static/package.json` | Pendiente |
| `codecov.yml` | Pendiente |
| `development.txt` | Pendiente |
| `docker-compose.yml` | Pendiente |
| `mkdocs.yml` | Pendiente |
| `pyproject.toml` | Pendiente |
| `requirements.txt` | Pendiente |
| `setup.cfg` | Pendiente |

## Estado del inventario de codigo

- Revisados/revalidados con evidencia registrada en la tabla por archivo: **26**.
- Parciales (solo se verifico parte de la logica o sus relaciones): **29**.
- Lectura previa registrada, aun sin integracion funcional suficiente: **43**.
- Pendientes de revision: **438**.
- Invalidaciones: **0**; el trabajo previo se conserva al aparecer fixes y se agregan deltas pendientes cuando corresponda.
- Total reconciliado desde las filas del inventario: **536** entradas unicas (**504** productivas + **32** de configuracion/herramientas). La suma de estados es 536; los 43 registros de lectura previa no se cuentan como auditoria completa.

## Criterio de avance

- Un archivo solo pasa a «revisado» tras inspección de funciones/métodos/expresiones ejecutables y sus contratos relevantes.
- Un componente solo pasa a completo después de cubrir backend, interfaz, API, permisos, estados, transacciones, límites y pruebas de comportamiento pertinentes; el simple conteo de archivos no basta.
- Los cambios posteriores no invalidan la evidencia previa: se conserva y se agrega como delta pendiente el alcance del fix antes de cerrar el archivo/componente.
- Los issues se verifican contra el estado actual y se comentan en el issue existente; solo se crea uno si el defecto es reproducible y no está reportado.


### Reconciliacion de estado actual (2026-11-01)

- Rama comprobada: `estabilizacion`; HEAD `103955a73c579ca4b1c5ea92c0bcf1416a1e6173`, igual a `origin/estabilizacion` al momento de esta revision.
- Desde `58d181a`, `api/__init__.py` cambio en `322c57fc` y `103955a7`; revisar documento-flow y el nuevo mapa de ACL de catalogos antes de reusar conclusiones previas. El commit mas reciente asigna `naming_series` a accounting. En prueba SQLite, usuario con permiso imports/create y acceso a cacao, sin permiso accounting, ve `/imports/new` (200) pero la consulta de naming_series devuelve 403. El impacto de impedir series explicitas para ese perfil queda pendiente de criterio; no se abre issue aun.
- Cambios de pruebas posteriores al checkpoint: `tests/conftest.py`, `tests/test_document_flow_acl.py`, `tests/test_sqlite_infra.py`, `tests/test_business_infra_pilot.py` y `tests/test_cross_module_acl.py`; se preservan y quedan fuera del inventario productivo.
- En el arbol local tambien cambiaron `cacao_accounting/inventario/routes.py`, `cacao_accounting/inventario/services.py`, `requirements.txt`, `tests/test_cache_isolation.py` y aparecio `tests/test_inventory_company_scope.py`; son ajenos a la auditoria y se preservan. `app/__init__.py` filtra `AccountingPeriod` por `authorized_codes` y queda invalidado para identidad/permisos. Los archivos nuevos/alterados de inventario estan pendientes de auditoria hasta el componente I2F; `requirements.txt` queda pendiente como configuracion.
- Reconciliacion de conteos: 33 revisados en checkpoint, 15 parciales, 43 lecturas previas por integrar, 443 pendientes y 2 invalidados = 536 entradas. Ningun componente se cierra por el mero estado "revisado en checkpoint".
- Se mantiene activo el componente de importacion bancaria. Proximo paso: continuar verificando limites de carga y asociacion de cuenta, y cotejar lectores con el contrato de extractos.
- #1033: XLSX temporal y lector real confirman `notes=None` -> `"None"` en el objeto construido; `concept` y `currency` vacios son columnas requeridas y se rechazan antes de `build_document()`. ODS temporal devuelve `""` para celda vacia, por lo que esa ruta no reproduce el defecto. No se afirma persistencia; comentario de delimitacion: 6559062297. La misma prueba ODS confirma en #1392 que 100,000 repeticiones de columnas se materializan desde un archivo de 1,539 bytes (comentario 6559122490); no se intento agotar memoria.
- Pendiente de politica de permisos: en SQLite aislado, usuario autenticado con acceso a `cacao`, permisos imports `view=True`, `validate=True`, `edit=False`, lote estado 1: GET de detalle HTTP 200 y boton Validar visible; POST `/imports/<id>/validate` HTTP 403. `routes.py::validate()` verifica `validar` y luego `_batch_or_404(..., "editar")`; la plantilla solo verifica `acceso.validar`. No se abre issue hasta confirmar si validar sin editar debe admitirse; evidencia no altera datos productivos.
- #1393 revalidado contra plantilla/servicio/rutas actuales; confirmada falta de controles visibles y bloqueo por `started_at` al corregir lotes en estados 2/7. Comentario con cadena causal y relacion con #1528: 6559108901.
- Revalidacion del lector ODS para #1392: archivo real de 1,539 bytes con `numbercolumnsrepeated=100000`; `ODSReader.read()` materializo la expansion antes de proyectar el ancho del encabezado (100,000 copias, ~0.035 s local). Evidencia agregada al issue; no se probaron payloads extremos ni agotamiento de memoria.
- Reconciliacion posterior a commit externo `103955a7`: modifico `api/__init__.py` (nuevo mapa `_SEARCH_SELECT_MODULE`, guard `_catalogo_permitido` y filtrado de fuentes de document-flow) y agrego `tests/test_cross_module_acl.py`; el endpoint API queda invalidado hasta revisar todo el diff. La rama coincide con origin; se conserva el cambio local pendiente en `app/__init__.py`.
- Verificacion de consumidor de `naming_series`: `imports/new.html` muestra el selector para todos los tipos, y API devuelve 403 para usuario autenticado con acceso a cacao y permiso imports/create pero sin accounting/view. Como `sequence_id` se persiste opcionalmente y el impacto depende de si el perfil debe poder elegir una serie explicita, queda pendiente de criterio; no se reporta como defecto confirmado.
- #1321 revalidado contra API actual en SQLite aislado: usuario limitado a cacao obtiene HTTP 200 y el ID/nombre de un usuario activo asociado solo a alpha mediante `/api/search-select?doctype=user&q=alpha-only-probe`; `company=cacao` se rechaza como filtro no permitido. Comentario agregado: 6559178919.
- Cobertura a?adida por commit `103955a7`: `.venv\Scripts\python.exe -m pytest tests/test_cross_module_acl.py -q` -> 4 passed, 4 warnings de `InsecureKeyLengthWarning` del JWT de prueba. El archivo cubre #1327 y #1515, no cubre `doctype=user` ni selector de series de importacion.

- Cambios locales observados al cierre del checkpoint: `app/__init__.py` invalida; `inventario/routes.py`, `inventario/services.py` y `requirements.txt` aun no revisados, con cambios ajenos pendientes para componente I2F/configuracion. `tests/test_cache_isolation.py` y `tests/test_inventory_company_scope.py` se preservan fuera del inventario productivo. HEAD no cambio: `103955a73c579ca4b1c5ea92c0bcf1416a1e6173`; worktree no limpio por estos cambios externos.
- Reproduccion de regresion en API Smart Select a partir de #1327: `tests/test_cache_isolation.py` ejecutado con `.venv` dio 1 failed, 10 passed, 1 skipped; usuario con Sales/view y compania autorizada no puede consultar catalogo propio al omitir filtro company. El guard pasa `None` a `tiene_acceso_compania()`, que lo deniega. Comentario al issue: 6559203201.
- Pronostico de caja: reproduccion directa en SQLite temporal con forecast `status="Approved"`; `validate_row()` y `validate_document()` devuelven `[]`, y `build_document()` + `persist_document()` insertan una fila de entrada sin cambiar el estado. Confirma #1049/#1381; ya existen comentarios con evidencia equivalente, no se repitio comentario.
- Regla de signo en entradas de pronostico: los issues #1050/#1196 estan enlazados a consolidacion #1292 y ya contienen reproducciones de monto <= 0, incluyendo CSV con espacios antes del signo; quedan revalidados por inspeccion actual de `validate_row()`/`build_document()`, que siguen sin comparar contra cero.
- Pruebas existentes de monto de extracto: `.venv\Scripts\python.exe -m pytest tests/test_bank_statement_import.py -q` -> 6 passed. Cubren interpretacion/validacion de importes y filas con lados cero/dobles; no ejercitan persistencia, lectores de archivo, cuentas inactivas ni autoconciliacion.
- Reproduccion ODS de filas comprimidas: archivo real temporal de 1,548 bytes con fila `numberrowsrepeated="3"`; lector devuelve una fila fisica y omite dos logicas. Evidencia agregada a consolidacion #1652, comentario 6559261615 (#1345/#1396).
- Reproduccion ODS de celda combinada: archivo temporal real de 1,568 bytes, nodos `table-cell/covered-table-cell/table-cell`; `ODSReader` devolvio `Cliente, 250, vacio`, ubicando monto bajo cuenta. Comentario al issue #1475: 6559273111.
- Durante reproduccion ODS hubo un error transitorio de importacion al leer `inventario/routes.py` mientras su cambio local se estaba escribiendo; al revalidar el estado actual, `py_compile` pasa y la reproduccion funciona. No se modifico el archivo; continua pendiente de auditoria en I2F.
- Revalidacion CSV del contrato lector/servicio: se rastreo una fila con 7 valores contra 6 encabezados; `CSVReader` conserva los 7 valores y `ImportService._normalize_rows()` genera un diccionario con 6 campos, descartando el ultimo antes de validar negocio. Es evidencia del defecto ya consolidado en #1534/#1474/#1652; comentarios previos #1534 6555603462 y #1652 6558887309 ya describen esta causa, no se duplico comentario. El servicio queda revisado para este contrato de ancho, pero sus rutas, persistencia y adaptadores continúan en integración pendiente.
- Ruta de creacion/detalle revalidada con Flask y SQLite aislado: un admin envia `record_type=not_a_real_adapter`; `POST /imports/new` responde 302, `POST /imports/<id>/upload` con CSV real responde 302/estado 1 y `GET /imports/<id>` responde 500 por `ValueError` no capturado en `ImportService.preview()` -> `_get_adapter()`. Issue #1661 actualizado con el flujo real y referencias de archivo/linea; datos solo en la app temporal.
- Descarga de plantilla revalidada con cliente Flask admin: purchase_order CSV/XLSX/ODS responde 200 y las cabeceras parseadas en cada formato contienen `serie`. La validacion estructural mantiene `serie` en `FORBIDDEN_COLUMNS`, por lo que coincide con #1531; comentario de ampliacion sobre los tres formatos: 6561507861. El parametro `format=unknown` tambien produce CSV por la rama de fallback; como la interfaz solo ofrece csv/xlsx/ods y no hay criterio distinto documentado, no se clasifica como defecto.
- Reconciliacion de HEAD posterior: `c5fbbc0` quedo integrado en `origin/estabilizacion`; el HEAD actual es `559ca1dd8bdab07263cc0a95815dc30b7a844568` y coincide con origin. El commit `c5fbbc0` cambia `api/__init__.py` y `app/__init__.py`; `559ca1dd` solo elimina dos lineas de `inventario/service.py` y ajusta su prueba. No afecta el codigo de Imports. Worktree: `.codex/` y `AUDIT_PROGRESS.md` sin seguimiento; se preservan.
- Revalidacion post-c5 de regresion #1327: `.venv\Scripts\python.exe -m pytest tests/test_cache_isolation.py -q` -> 11 passed, 1 skipped. El endpoint sin filtro `company` responde 200 para `customer` y el test comprueba que cada usuario solo recibe el Party de su compania. La correccion del 403 previo queda verificada en esta prueba; comentario a #1327 6561553843. No se da por fix-confirmed por requerir validacion independiente/humana.
- Revalidacion post-c5 de #1321: app SQLite temporal, Sales/view, requester con alcance solo `COMP-A`, y usuario activo asociado a `COMP-B`; `/api/search-select?doctype=user&q=Foreign%20User%20Probe` devuelve 200 e incluye el ID ajeno. Con `company=COMP-A` la consulta devuelve 400 porque el doctype solo admite `active`. `_build_base_query()` no aplica `company_scope` a `User`. Comentario actualizado en #1321: 6561572758; el defecto sigue vigente en HEAD 559ca1dd.
- Desalineacion de delimitador comprobada con archivo real temporal: `_valid_csv_fallback()` devuelve `True` para contenido tabulado, mientras `CSVReader.read()` solo prueba `,;` y produce una sola columna. `ImportService.validate()` en SQLite deja el lote `bank_statement` en estado 7 con `MISSING_COLUMN` para `bank_account_id` y `posting_date`, `total_rows=0`. Búsqueda de issues no encontró uno existente; issue nuevo #1662 (`needs-work`) con reproducción y archivos afectados.
- Revalidacion de whitespace-only en importes opcionales: con `BankAccount` real en SQLite, una fila con `deposit="100.00"` y `withdrawal=" "` genera `InvalidOperation` en `BankStatementAdapter.validate_row()` y se rechaza, aunque el depósito sea válido. `_optional_amount()` comprueba string vacío antes de `strip()`. Defecto existente #1030; comentario actual 6561657240. `.venv\Scripts\python.exe -m pytest tests/test_bank_statement_import.py -q` -> 6 passed; no incluye este borde.
- Intento de habilitar reproduccion XLS de fecha: inventario del repositorio no contiene `.xls`; entorno no tiene `xlwt`, `xlsxwriter`, `pandas`, `pyexcel_xls`, Excel, LibreOffice ni convertidor XLS. `xlrd 2.0.2` permite lectura pero no generar el fixture; se deja `xls_reader.py` parcial sin concluir comportamiento de fechas.
- Reconciliacion de cambios locales detectados: `bancos/services.py` cambia `_apply_cash_company_scope()` para consultas que pasan por `_paginate_list()`; busqueda de consumidores confirma que el camino de importacion automatica usa `BankStatementAdapter._auto_reconcile()` -> `statement_service.auto_reconcile_bank_transaction()` -> `reconciliation_service`, sin llamar a ese helper. No invalida esta conclusion de autoconciliacion; queda pendiente en el componente CTM general. Cambios de compras/terceros/ventas tambien se preservan y se revisaran al llegar a esos componentes.
- Reconciliacion posterior de HEAD: rama `estabilizacion` avanzo localmente a `d3fa193367d451e2de6e390a2a6e01f12bc7f952` (`fix: ancla el alcance de compañía del listado de inventario`), mientras `origin/estabilizacion` sigue en `103955a73c579ca4b1c5ea92c0bcf1416a1e6173` (ahead 1). El commit toca `inventario/routes.py`, `inventario/services.py` y agrega `tests/test_inventory_company_scope.py`; el arbol tambien tiene modificaciones locales adicionales en `inventario/routes.py`, `inventario/service.py`, `api/__init__.py` y `app/__init__.py`. Se preserva todo ese trabajo ajeno. Imports sigue como componente activo y el inventario de I2F permanece pendiente; no se reutiliza una conclusion previa de esos archivos sin revisar commit y diff cuando llegue ese componente.

### Continuidad de revisión del flujo de imports (2026-11-01)

- Estado del modelo `ImportBatch` y sus transiciones contrastado con `ImportService.validate/execute/cancel/_execute_task/_check_batch_cancellation/_finalize_execution`. `validate()` deja `started_at` tanto al pasar al estado 3 como al registrar errores; los guardas de `validate()` y `execute()` rechazan después lotes con ese campo, bloqueando el reintento ordinario (#1528, reproducido y comentado previamente). `cancel()` solo activa `cancel_requested` sin validar estado; #1395 permanece como defecto separado. Se confirma la evidencia existente; no hay issue nuevo.
- Pruebas focalizadas ejecutadas en `.venv`, una por archivo: `tests/test_bank_statement_import.py` (6 passed), `tests/test_import_batch_recovery.py` (3 passed), `tests/test_import_batch_cancellation.py` (1 passed). Son pruebas existentes, no cubren todas las reproducciones registradas y no se modificaron.
- Próximo: inspeccionar integridad y reintentos entre solicitud y worker, cerrar dependencias pendientes del API de selector y precisar criterios operativos. La política para importar cuentas bancarias inactivas sigue sin criterio de negocio documentado.

### Reconciliacion tras commit de alcance dashboard (2026-11-01)

- HEAD avanzó a `90195b7c2cdbd030db849b7423e2b237c41aa9ce` (`fix: acota dashboard y tareas al alcance vigente`), `estabilizacion` ahead 2 de origin. El commit modifica `cacao_accounting/__init__.py`, `api/__init__.py`, `api/dashboard.py`, `collaboration_service.py` y `tests/test_dashboard_task_scope.py`. No se auditó su diff en este checkpoint; los dos primeros archivos estaban parcialmente revisados y quedan invalidados, los otros dos pasan a cambios recientes pendientes. Prueba excluida del inventario productivo.
- `git status` confirma worktree limpio respecto de archivos versionados; solo quedan los artefactos locales no seguidos `.codex/` y `AUDIT_PROGRESS.md`. No se realizó push.
- El componente activo sigue siendo importación bancaria. El commit nuevo es de ACL/dashboard/colaboración y se revisará en sus componentes asignados, sin cambiar el orden del componente activo.

### Contrato de controles del asistente de importación (2026-11-01)

- Reconcilié `imports/templates/imports/detail.html` y `new.html` con rutas y estados del modelo. Los controles de validación (estado 1), ejecución (estado 3) y cancelación (estado 4) coinciden con sus rutas y permisos visibles. El upload aparece solo en estado 0, aunque `/upload` permite estado 1 cuando no hay filas procesadas ni `started_at`; esa recuperación UI queda oculta y sigue asociada a #1528, además del bloqueo backend por `started_at`.
- Estados 2 y 7 no presentan control de revalidación; el backend incluye ambos en `REVALIDATABLE_IMPORT_STATUSES`, pero su `started_at` no nulo impide revalidar de forma ordinaria (#1528). El caso de archivo corrupto con `status >= 1` sigue haciendo que `detail()` renderice la vista previa y propague error del lector (#1031).
- Los formularios POST de crear lote, subir, validar, ejecutar y cancelar no contienen token CSRF en estas plantillas; hallazgo existente #1648. No se abrió issue duplicado. La salida de datos de vista previa se imprime en HTML escapado por Jinja; no se confirmó XSS en el recorrido inspeccionado.
- No hay API JSON separada del wizard: el contrato de este flujo es POST/redirect/GET de Flask más `/api/search-select` en los selectores, ya revisado parcialmente. El componente no se cierra: faltan dependencias de selector/ACL completas, los casos XLS sin fixture y cerrar los criterios operativos pendientes.


### Reproducción de carrera de recuperación (2026-11-01)

- Revisé `imports/utils/recovery.py` y su invocación durante creación de aplicación, y la secuencia asíncrona `ImportService.execute()` -> `Thread.start()` -> `_execute_task()`.
- Reproducción nueva con lote real de SQLite y CSV de 101 filas: `execute()` confirmó status 4, luego se pausó la llamada a `Thread.start()`; mientras `started_at` seguía NULL, `recover_crashed_batches()` recuperó 1 lote, lo marcó status 7 y agregó `SYSTEM_TIMEOUT`. Resultado observado: `execute_return=True`, `recovery_count=1`, `status_after_recovery_before_worker_start=7`. Se usó pausa controlada únicamente para programar la intercalación concurrente; no se modificó código ni pruebas.
- La recuperación de NULL atiende el estado atascado descrito en #1203/#1031, pero actualmente no distingue un lote recién encolado cuyo worker aún no arrancó. Comentario detallado publicado en #1203: 6561758648. No se abrió issue duplicado.
- Pendiente del componente: investigar ordenamiento/atomicidad de recuperación entre varias instancias, comprobar al menos una réplica en PostgreSQL si el entorno lo permite, y cerrar el contrato de reinicio evitando duplicar documentos ya confirmados.
- Tras la reproducción se ejecutó `.venv\Scripts\python.exe -m pytest tests/test_import_batch_recovery.py -q`: 3 passed. La prueba de status 4/null confirma recuperación de huérfanos, pero construye un lote ya detenido y no representa la ventana entre el commit de `execute()` y `Thread.start()`; por eso no detecta la clasificación prematura recién reproducida.

### Reconciliación de trabajo concurrente (2026-11-01)

- Se detectaron nuevas modificaciones locales, sin commit, en `cacao_accounting/collaboration_service.py`, `party_management.py` y `ventas/routes.py` (diff actual: 69 inserciones y 2 eliminaciones). Son ajenas al componente activo de importación; se preservan intactas y se revisarán/revalidarán en los componentes de colaboración, terceros y O2C.
- Estado base de auditoría continúa en HEAD `90195b7c2cdbd030db849b7423e2b237c41aa9ce`; no se hizo checkout, reset, commit ni push.

### Confirmación multiinstancia y límites del entorno (2026-11-01)

- Reproducción fortalecida con SQLite en archivo compartido: primera instancia ejecuta lote de 101 filas, hilo worker pausado después del commit, segunda instancia creada con `create_app()` dispara el hook real de recuperación. Resultado después de liberar la solicitud: `execute() == True`, `create_app()` de la segunda instancia observó status 7 antes del worker y la solicitud terminó. Reproducción en comentario adicional #1203, id 6561799033.
- PostgreSQL no está disponible en este entorno: `psql`, `pg_isready`, `docker`, `psycopg2` y `psycopg` no están disponibles; por tanto la intercalación se verifica en SQLite y no se declara prueba Tier 1/PostgreSQL.
- Al último `git status`, además del archivo de progreso, se preservan cambios de terceros sin commit en `collaboration_service.py`, `compras/routes.py`, `party_management.py` y `ventas/routes.py`. No se inspeccionaron ni modificaron como parte del flujo activo.

### Caída entre commit del documento y avance del lote (2026-11-01)

- Reproducción real aislada de `ImportService._execute_task()` con el adaptador bancario: dos filas CSV son documentos independientes; inyecté `SystemExit` al entrar a `_update_batch_progress()`, que ocurre después del commit por documento. La base mostró status 4, `started_at` establecido, contadores `processed_rows=0`/`success_rows=0` y una `BankTransaction` persistida; el segundo documento no se procesó. Los guardas del servicio rechazan revalidar/ejecutar el lote en ese estado.
- El resultado demuestra que el commit del documento y el registro del avance del lote no son atómicos; una caída puede dejar documentos confirmados invisibles a los contadores. Reproducción y alcance append-only comentados en issue existente #1062, comentario 6561838726. No se abrió duplicado ni se cambiaron archivos productivos/tests.
- Continuación: integrar el hallazgo con el contrato de recuperación #1062, verificar identidad/deduplicación en reinicios de extractos bancarios y determinar qué evidencia puede identificar documentos ya confirmados. No asumir repetición segura del CSV completo.
- Reconciliación al cierre del turno: apareció el archivo de prueba no seguido `tests/test_party_task_mutation.py` junto con las cuatro modificaciones de producción ajenas ya descritas. No se abrió ni alteró ese trabajo paralelo; las pruebas quedan fuera del inventario productivo.


### Precisión monetaria de extractos bancarios (2026-11-01)

- Revisión de `BankStatementAdapter._optional_amount()`/`validate_row()` cruzada con `BankTransaction.deposit/withdrawal`, el listener de `identity_key` y el formulario de configuración de monedas (`Currency.decimals`, máximo 8).
- Reproducción SQLite: cuenta en moneda `C5` (`decimals=5`), fila con depósito `123.45678`: validación devuelve `[]`; después de persistir y recargar, `BankTransaction.deposit` vale `123.4568` (diferencia `0.00002`). El hash guardado difiere del que `_bank_transaction_identity()` calcula con el importe realmente persistido. Una importación repetida del mismo dato se detectó como duplicada; no se afirma duplicación adicional.
- Hallazgo nuevo #1663, `bug`/`severity-medium`/`imports`, abierto con archivos, reproducción e impacto sobre conciliación. No se modificó código ni pruebas. Falta acordar la política de precisión para importes fuera de escala 4; no se propone una decisión de negocio en la auditoría.
- `psql`, `pg_isready`, `docker`, `psycopg2` y `psycopg` siguen ausentes; la evidencia de esta ronda es SQLite.
- `.venv\Scripts\python.exe -m pytest tests/test_bank_statement_import.py -q`: 6 passed after the precision finding. Existing accepted-decimal test stops at four fractional places (`123.4567`); it does not test a currency with `decimals=5` or compare source amount to reloaded persistence, so green tests do not cover #1663.
- Reconciliación al cierre de este checkpoint: HEAD continúa `90195b7c2cdbd030db849b7423e2b237c41aa9ce`; modificaciones ajenas sin commit siguen en `collaboration_service.py`, `compras/routes.py`, `party_management.py`, `ventas/routes.py` (diff observado: 100 inserciones/4 eliminaciones), con `tests/test_party_task_mutation.py` sin seguimiento. Se preservan intactas.

### Contrato común de lectores y adaptadores (flujo bancario, 2026-11-01)

- Releí `imports/adapters/base.py`, `imports/readers/base.py`, `imports/column_labels.py` y el consumidor `BankStatementAdapter`. Para este flujo, las seis columnas de plantilla en español e inglés round-trip a sus nombres canónicos. `NormalizedTable` expone columnas, filas y formato, que concuerdan con `CSVReader` y `_normalize_rows()`.
- `BaseImportAdapter.validate_row()` añade validación de campos requeridos y marca cualquier cadena que empiece exactamente por `=`, `+`, `-` o `@`. No confirmé un defecto adicional en el consumidor bancario; el efecto sobre otros adaptadores y usos/exports se revisará al llegar a sus componentes, así que el estado de estos archivos queda parcial.
- El componente de imports sigue abierto: hay pendientes fuera del contrato común (lectores XLS, reintentos/idempotencia, permisos y decisiones operativas no documentadas).

### Reconciliación tras commit de guards y mutaciones locales (2026-11-01)

- HEAD avanzó durante esta ronda a `41c96c43483df262a4eb76554148b896cf64d9c2` (`fix: guard party edits and task status updates`), rama `estabilizacion` ahead 3 de origin. El commit modifica `collaboration_service.py` y `party_management.py`; ambos archivos estaban pendientes y ahora se registran como cambios de HEAD pendientes de revisión en componentes transversales/terceros.
- Worktree actual: modificaciones sin commit en `compras/routes.py` y `ventas/routes.py`; `tests/test_party_task_mutation.py` sin seguimiento. Se preservan sin inspección ni modificación. Los tests no forman parte del inventario productivo.
- El componente activo sigue siendo Importación de extractos bancarios; los cambios nuevos son ajenos y no alteran su orden.


### Reconciliación tras commit de guards de terceros (2026-11-01)

- HEAD avanzó a `5ffeb3b902fefe68d7c7ffe63518cf1fc92fab7f` (`fix: propiedad y alcance en mutaciones de terceros y tareas`), rama `estabilizacion` ahead 4 de origin. El commit agrega guards por compañía/edición en `compras/routes.py` y `ventas/routes.py`; archivos y funciones afectados siguen pendientes para los componentes S2P/O2C. La prueba `tests/test_party_task_mutation.py` queda fuera del inventario productivo.
- El worktree versionado está limpio; únicamente persisten sin seguimiento `.codex/`, `AUDIT_PROGRESS.md` y `tests/test_party_task_mutation.py`.
- Continúa activo el componente de importación bancaria. El commit no modifica dependencias de ese flujo.
- Comentario de cobertura añadido a #1663: `.venv\Scripts\python.exe -m pytest tests/test_bank_statement_import.py -q` -> 6 passed; la suite solo acepta hasta 4 decimales y no compara el importe fuente con persistencia de una moneda de precisión 5 (#1663, comentario 6561937982).

### Reanudación del flujo bancario (2026-11-01)

- HEAD actual comprobado: `5ffeb3b902fefe68d7c7ffe63518cf1fc92fab7f`, ahead 4. El worktree versionado está limpio; `.codex/` y esta bitácora sin seguimiento. No surgieron cambios en el flujo de imports.
- El issue #1663 conserva reproducción SQLite y el comentario de cobertura #6561937982. La prueba focalizada sigue en 6/6; no cubre el monto de cinco decimales.
- Próxima unidad funcional: `ImportService` por documento — cotejar `_group_by_reference()`, `persist_document()`/commit, conteo de filas y la deduplicación existente (#1507/#1319) con la reproducción de crash parcial (#1062). Después volver a las validaciones y permisos pendientes de `imports/routes.py`; criterios de cuenta inactiva y permiso imports-only siguen sin decisión documentada.

### Reconciliación de divergencia de rama (2026-11-01)

- HEAD autoritativo: `ebefe4fd6d6828e1ba25224264d128b06013540c`; estado `estabilizacion...origin/estabilizacion [ahead 6, behind 2]`. La rama remota contiene `c5fbbc0b` y `559ca1dd`; la local incorpora commits distintos sobre permisos/inventario/terceros. Se mantiene el checkout actual sin integrar refs divergentes.
- La comparación de nombres entre refs no muestra altas de código productivo; las altas/bajas son archivos de pruebas. El inventario productivo/configuración conserva 536 entradas del manifiesto. El conteo de estados 33/15/43/443/2 sigue siendo el último recuento de bitácora, no recalculado todavía contra todos los cambios parciales.
- Estado de trabajo versionado limpio. `.codex/`, `.git-rewrite/`, `AUDIT_PROGRESS.md` son artefactos locales no seguidos; pruebas fuera del inventario de producción.

### Reproducción del flujo agrupado y deduplicación bancaria (2026-11-01)

- En la rama divergente actual `HEAD=ebefe4fd6d6828e1ba25224264d128b06013540c` (ahead 6 / behind 2), ejecuté `_execute_task()` con app SQLite aislada, cuenta y período abiertos, lote CSV de status 3 y dos filas bancarias idénticas agrupadas por `document_ref`.
- Resultado: status 5, `success_rows=2`, `error_rows=0`, `processed_rows=2` y dos movimientos bancarios iguales persistidos. La causa observada es que `persist_document()` filtra fuera de la consulta los IDs ya insertados en el grupo. La evidencia se publicó en issue existente #1507, comentario 6561976411; la reproducción invoca el worker directamente para aislar esta causa del bloqueo de `execute()` (#1528).
- La lectura integrada confirma que `_process_document()` confirma el documento antes de incrementar/confirmar contadores; ya se reprodujo que una terminación en esa ventana deja evidencia bancaria persistida con contadores cero (#1062, comentario 6561838726). No se abre duplicado.
- El inventario continúa con 536 entradas conocidas; la divergencia de rama no agrega archivos productivos en los diffs revisados, aunque el desglose de estados de auditoría sigue pendiente de recalcular contra el manifiesto. No hay servicio PostgreSQL disponible; esta reproducción se hizo con SQLite.
- El trabajo versionado sigue limpio. Artefactos locales sin seguimiento actuales: `.codex/`, `.git-rewrite/`, `AUDIT_PROGRESS.md`.

### Reconciliación masiva de estados del inventario (2026-11-01)

- Recalculé los estados directamente desde las 536 filas de archivos del manifiesto, en vez de conservar el desglose histórico 33/15/43/443/2. Resultado autoritativo antes del ajuste de criterio: 28 revisados/revalidados, 19 parciales, 43 lecturas previas sin integración funcional, 443 pendientes y 3 etiquetados entonces como invalidados.
- La bitácora no contiene una categoría de 49 archivos para integrar: los 43 con estado `Lectura previa; integración pendiente` siguen claramente diferenciados de los 28 con revisión registrada y los 19 parciales. No se promovieron lecturas a auditoría completa sin evidencia por función/contrato.
- Los archivos de Imports ya marcados como revisados permanecen descritos individualmente; su cierre como componente depende de completar contratos cruzados, reintentos, permisos y casos límite. No cambia el componente activo.
- Ajuste de criterio solicitado: se conserva el historial de revisión de `__init__.py`, `api/__init__.py` y `app/__init__.py`; sus cambios posteriores quedan como tres deltas parciales pendientes, sin invalidar revisiones anteriores.

### Verificación de estatus de auditoría (2026-11-01)

- Recuento actualizado del manifiesto: 536 entradas; 28 revisadas/revalidadas, 22 parciales (incluye tres deltas de fixes), 43 con lectura previa aún sin integración, 443 pendientes y cero invalidadas. Ningún componente está cerrado.
- HEAD verificado en `ebefe4fd6d6828e1ba25224264d128b06013540c`; coincide con `origin/estabilizacion` (0/0). Worktree no limpio por `cacao_accounting/printing/service.py` y `tests/test_portal_print_scope.py`, cambios preservados y no auditados en esta ronda.
- El componente activo sigue siendo importación bancaria. Siguiente unidad: persistencia por documento en `ImportService`, y luego contratos restantes de permisos/reintentos.
- Tras esta verificación, HEAD avanzó a `54e6765659d8ce1af95294cf57eaa925c06e6601` (`fix: ancla la impresión del portal a su compañía`), rama `estabilizacion` ahead 1. Se registra el fix para revisión cuando corresponda al componente de impresión; no altera el conteo del inventario y no invalida trabajo previo.
- Apareció además un cambio local sin commit en `cacao_accounting/decorators.py` (8 inserciones/3 eliminaciones), que ya estaba Pendiente. Se conserva intacto y se auditará al llegar al módulo correspondiente.
- El estado del árbol mostró cambios adicionales sin commit en `contabilidad/presupuesto.py` (8 líneas afectadas) y `contabilidad/routes.py` (40 líneas afectadas); ambos están Pendientes. Se preservan y se revisarán dentro de R2R. No cambian el conteo ni invalidan revisiones previas.
- Tras revisar parcialmente el consumidor `JournalEntryAdapter` del agrupamiento compartido y verificar #1530, el conteo de filas por estado es 28 revisadas/revalidadas, 23 parciales, 43 con lectura previa pendiente de integrar y 442 pendientes; 0 invalidadas (536 en total).

### Fechas inconsistentes en asientos importados (2026-11-01)

- Para comprobar la semántica compartida de `_group_by_reference()`, inspeccioné parcialmente `JournalEntryAdapter` como consumidor vecino sin cambiar el componente activo. En SQLite aislado creé períodos de enero abierto y febrero cerrado, dos cuentas y dos líneas balanceadas con la misma referencia `JE-1`, fechas 2026-01-15 y 2026-02-15.
- `ImportService.validate()` devolvió `True`, marcó el lote listo (estado 3) y no produjo errores. `build_document()` tomó `posting_date=2026-01-15`, descartando la fecha de la segunda fila; el período de febrero estaba cerrado. No afirmo que se haya persistido un asiento: el bloqueo existente de ejecución #1528 impide la ruta normal.
- El defecto coincide con issue existente #1530; publiqué reproducción del validador real y límite de ejecución en comentario 6562053166. `journal_entry.py` pasa de pendiente a parcial; revisión del resto del adaptador sigue pendiente.
- Pruebas focalizadas ejecutadas con `.venv`, cada archivo por separado: `tests/test_bank_statement_import.py` (6 passed), `tests/test_import_batch_recovery.py` (3 passed) y `tests/test_import_batch_cancellation.py` (1 passed). No cubren el caso de fechas de diario #1530.

### Pérdida de filas al agrupar importación de clientes (2026-11-01)

- Como `ImportService._group_by_reference()` es compartido, inspeccioné este consumidor maestro para comprobar que el agrupamiento no cambia la cardinalidad de registros independientes. En SQLite aislado usé el CSV `document_ref,nombre` con dos clientes `Cliente A` y `Cliente B` bajo `lote-1`.
- `validate()` devolvió `True`, lote estado 3, dos filas y cero errores. Invocando el worker directamente para aislar #1528, terminó estado 5 con `success_rows=2` y `processed_rows=2`, pero solo persistió `Cliente A` y un vínculo `CompanyParty`; `Cliente B` no se guardó.
- La causa coincide con issue existente #1346. Publiqué evidencia del flujo real, conteo y límite del worker en comentario 6562095933. `customer.py` pasa de revisado general a parcial porque solo se verificó este camino; el resto sigue pendiente. La revisión es puntual del consumidor compartido y no cambia el componente principal activo.
- Recuento posterior a la inspecci?n del consumidor cliente, calculado de las 536 filas: 27 revisadas/revalidadas, 24 parciales, 43 lecturas previas pendientes de integraci?n, 442 pendientes y cero invalidadas.

### Confirmacion de agrupamiento en los tres adaptadores maestros (2026-11-01)

- En HEAD `b32394ccd644340e4b22ba603814a7511364c265`, repeti el flujo con `VendorAdapter` y `ChartOfAccountsAdapter`, cada uno con dos filas y `document_ref=lote-1`. En ambos casos `validate()` no registro errores y marco estado 3; el worker termino estado 5 con dos exitos, pero persistio un proveedor/cuenta.
- Se amplio la evidencia del issue existente #1346 con comentario 6562113952. Junto con la reproduccion de clientes, la perdida se confirma en los tres adaptadores mencionados; cada adaptador queda parcial y el resto de su logica sigue pendiente.
- El manifiesto, recalculado desde sus 536 filas, queda en: 25 revisadas/revalidadas, 26 parciales, 43 lecturas previas pendientes de integrar, 442 pendientes y cero invalidadas. No cambia el componente principal activo.
- El commit `b32394cc` incorpora un fix de permisos contables y pruebas; queda registrado para el componente R2R, aun pendiente, sin invalidar trabajo previo.

### Validacion de campos requeridos en importacion de clientes (2026-11-01)

- En SQLite temporal, el CSV de cliente con encabezado `nombre` y una fila de tres espacios pas? `ImportService.validate()` sin `ImportBatchError`, qued? listo (estado 3), y el worker persisti? un `Party` con `name="   "` (`strip()` devuelve vac?o), contando una fila exitosa. Se confirm? que `BaseImportAdapter.validate_row()` no normaliza espacios y `CustomerAdapter` guarda el nombre sin limpieza.
- Se a?adi? la reproducci?n al issue existente #1052 (comentario 6562136172); no se abri? duplicado. El worker se invoc? directamente por el bloqueo conocido #1528.
- Rastreo de cardinalidad del agrupamiento: `CustomerAdapter`, `VendorAdapter` y `ChartOfAccountsAdapter` leen solo la primera fila y reproducen #1346; `CashForecastEntryAdapter`, `BankStatementAdapter`, `JournalEntryAdapter` y los adaptadores transaccionales iteran l?neas para construir detalle. Estos ?ltimos tienen sem?ntica de documento agrupado y requieren validar consistencia de cabecera donde corresponde (#1530/#1628/#1054).
- El manifiesto mantiene 536 entradas: 25 revisadas/revalidadas, 26 parciales, 43 lecturas previas pendientes de integraci?n y 442 pendientes; cero invalidadas. El componente principal contin?a en importaci?n bancaria; la revisi?n de consumidores se limita al riesgo del agrupamiento com?n.

### Monto no finito en pronostico de caja (2026-11-01)

- Reproduccion aislada con SQLite, pronostico Draft, moneda NIO activa y anio fiscal: una fila CSV con monto `Infinity` paso `ImportService.validate()` sin errores (estado 3); el worker termino estado 5 con un exito y `CashForecastEntry.amount` persistio/leyo como `Decimal('Infinity')` en la columna `Numeric(20,4)`. Usar Draft aislo el resultado de #1049, que es independiente.
- `CashForecastEntryAdapter.validate_row()` construye `Decimal` pero no revisa `is_finite()`; `build_document()` pasa la cifra no finita a persistencia. Evidencia a?adida al issue existente #950, comentario 6562154670. El worker fue invocado directamente por el bloqueo de ejecucion #1528; no se modificaron pruebas ni codigo productivo.
- Conteo del inventario sin cambio: 25 revisadas/revalidadas, 26 parciales, 43 lecturas previas pendientes de integrar y 442 pendientes; cero invalidadas.

### Persistencia de notes vacias de XLSX en pronostico (2026-11-01)

- Con XLSX real temporal, `XLSXReader` devolvio `None` para celda `notes` vacia. `ImportService.validate()` acepto lote de pronostico Draft (estado 3, cero errores); el worker termino en estado 5 con una fila exitosa y SQLite guardo `CashForecastEntry.notes="None"`.
- Se confirmo persistencia (no solo el objeto construido) y se agrego detalle al issue existente #1033, comentario 6562169667. El Draft aisla el caso del issue #1049; worker invocado directamente por #1528.
- El inventario conserva 536 filas con estado actual 25 revisadas/revalidadas, 26 parciales, 43 lecturas previas pendientes y 442 pendientes; cero invalidadas.

### Revalidacion del lector XLSX (2026-11-01)

- Revis? el unico metodo ejecutable `XLSXReader.read()`: carga el libro con `data_only=True`, selecciona la hoja activa, obtiene tuplas `values_only`, convierte la primera fila en encabezados y conserva las filas restantes. El flujo real de importacion XLSX confirmo que una celda opcional vacia llega como `None` y se persiste como literal `"None"` en el pronostico (#1033, comentario 6562169667).
- La observacion confirma la dependencia del lector y adaptador; no genera issue duplicado. Las fechas nativas tipo Excel se conservan como `datetime`, ya cubiertas por #1201; el comportamiento con formato XLS permanece parcialmente pendiente por falta de fixture.
- El conteo del manifiesto no cambia: 536 entradas, 25 revisadas/revalidadas, 26 parciales, 43 lecturas previas por integrar, 442 pendientes, cero invalidadas.

### Revalidacion del lector XLS con fixtures oficiales (2026-11-01)

- Rama `estabilizacion`, HEAD comprobado `5ae4b5ae6663922f9bbc99fd3ab45dc6281cfb56`, tres commits por delante de `origin/estabilizacion`. Worktree versionado limpio; solo `.codex/` y `AUDIT_PROGRESS.md` aparecen sin seguimiento. No se descarta ni invalida evidencia previa por los fixes posteriores.
- Revisado `XLSReader.read()` con 12 muestras oficiales del corpus de pruebas de xlrd: `Formate.xls`, `biff4_no_format_no_window2.xls`, `corrupted_error.xls`, `formula_test_names.xls`, `formula_test_sjmachin.xls`, `invalid_formula.xls`, `issue20.xls`, `namesdemo.xls`, `picture_in_cell.xls`, `profiles.xls`, `ragged.xls` y `xf_class.xls`. El lector devuelve la primera hoja como filas/columnas normalizadas; en `picture_in_cell.xls` el resultado vacío es un `NormalizedTable` sin filas.
- `Formate.xls` contiene celdas identificadas como fecha por xlrd, pero `XLSReader.read()` devuelve el serial crudo (por ejemplo `38406.0`, que con el datemode del libro corresponde a 2005-02-23). Confirma el defecto existente #1201; evidencia añadida al issue en comentario 6562216349. No se abrió duplicado.
- Reproduje la ruta `ImportService.preview()` con `corrupted_error.xls` y un `ImportBatch` XLS en SQLite aislado: el lector lanza `xlrd.compdoc.CompDocError: Workbook corruption: seen[2] == 4`, y la ficha queda expuesta a la excepción porque `detail()` llama a `preview()` para estados >=1. Amplié el issue existente #1031 (ya cubre lectores corruptos y preview) con esta evidencia, comentario 6562242894; no se abrió issue adicional.
- El manifiesto queda en 536 entradas: **26 revisadas/revalidadas**, **25 parciales**, **43 lecturas previas pendientes de integración**, **442 pendientes**, **0 invalidadas**. El cambio de XLS pasa una fila de parcial a revisado; la evidencia previa se conserva.
- Último commit `5ae4b5ae` incluye cambios de CI/configuración y un ajuste de alcance en `inventario/services.py`; se conserva como delta pendiente de revisar en configuración/I2F al llegar a esos componentes. Pruebas anexas fuera del inventario productivo. No se ejecutaron pruebas nuevas en este checkpoint.
- Componente principal activo: importación bancaria/Imports. Próxima unidad: continuar `ImportService` por documento, estados y reintentos; después completar las relaciones pendientes de rutas, API, permisos y adaptadores antes de cerrar el componente.

### Colision de referencias vacias en importacion maestra (2026-11-01)

- Reconciliación al reanudar: HEAD sigue en `5ae4b5ae6663922f9bbc99fd3ab45dc6281cfb56`, rama `estabilizacion`, ahead 3 de `origin/estabilizacion`; el árbol versionado permanece limpio. Se conserva el historial sin invalidaciones por fixes posteriores.
- Revisión parcial de `ImportService._group_by_reference()`, `_process_document()` y `_process_all_documents()` con `CustomerAdapter`: un CSV con dos filas y `document_ref` vacío se agrupa bajo la clave común `no_ref`. `validate()` acepta las dos filas; al invocar el worker para aislar el bloqueo conocido #1528, termina en estado 5 con dos éxitos/procesadas, pero persiste solo `Cliente A` y omite `Cliente B`.
- El caso comparte causa raíz con #1346 (agrupador genérico combinado con adaptadores maestros que consumen solo la primera fila). Añadí reproducción SQLite real como comentario 6562263037; no abrí duplicado ni modifiqué archivos productivos o pruebas.
- Suites focalizadas ejecutadas por archivo con `.venv`: `tests/test_bank_statement_import.py` 6 passed; `tests/test_import_batch_recovery.py` 3 passed; `tests/test_import_batch_cancellation.py` 1 passed. Estos resultados no cubren la colisión de referencias vacías.
- En el mismo repaso contrasté `execute()`, `cancel()`, `_execute_task()`, `_process_all_documents()`, `_check_batch_cancellation()` y `_finalize_execution()` con los estados documentados por `ImportBatch` y las rutas POST. Se mantienen las transiciones ya reproducidas en #1528 (marca `started_at` bloquea ejecución/reintento), #1395 (`cancel()` acepta estados que no están ejecutándose) y #1032 (ventana de cancelación al finalizar); no se abrió otro issue por esas mismas causas. El worker vuelve a leer el archivo después de la lectura inicial de `execute()`; un cambio entre ambas lecturas queda como caso límite pendiente de evidencia reproducible, no como hallazgo confirmado.
- El inventario conserva 536 entradas: 26 revisadas/revalidadas, 25 parciales, 43 lecturas previas pendientes de integrar, 442 pendientes y 0 invalidadas. `import_service.py` permanece parcial: falta cerrar los demás caminos, estados/reintentos y contratos cruzados.
- Próximo dentro del componente: revisar `execute()` y la transición de validación a ejecución junto con las restricciones de `ImportBatch`/rutas, sin repetir como nuevos los defectos ya documentados (#1528, #1031, #1032, #1395).

### Revision de listado de lotes (2026-11-01)

- Reconciliación: HEAD `5ae4b5ae6663922f9bbc99fd3ab45dc6281cfb56`, `estabilizacion` ahead 3; sin cambios versionados nuevos. Se conserva el trabajo anterior sin invalidaciones.
- Revisión de `imports/templates/imports/index.html` junto con `routes.index()`: herencia de `base.html`; permiso `crear` solo controla el enlace de alta; la ruta requiere `consultar`, y el listado se limita a compañías autorizadas salvo administrador. Revisé tabla/empty state, estados 0–8, `created.strftime`, expresiones de progreso con `total_rows` nulo/cero, traducciones y enlaces de detalle. No encontré un defecto funcional aislado en este recorrido.
- Búsqueda de cobertura no encontró pruebas de `/imports` ni del render de este listado; no se atribuye cobertura a las suites previas. La fila ya estaba clasificada como revisada en checkpoint; la inspección añade evidencia funcional y no cambia el conteo. El componente Imports continúa abierto por sus otros archivos y contratos.
- Recuento verificado contra las 536 filas del manifiesto: **26 revisadas/revalidadas**, **25 parciales**, **43 lecturas previas pendientes de integración**, **442 pendientes**, **0 invalidadas**. Próximo: volver a la integración `execute()`/`ImportBatch` y después completar el resto de plantillas y rutas de Imports.

### Revalidacion de detalle y acciones del lote (2026-11-01)

- Reconciliación del repositorio: HEAD continúa `5ae4b5ae6663922f9bbc99fd3ab45dc6281cfb56` en `estabilizacion`, tres commits ahead. Sin cambios versionados posteriores; se conserva la evidencia previa.
- Releí `imports/templates/imports/detail.html` línea por línea y lo contrasté con `routes.detail`, `upload`, `validate`, `execute`, `cancel`, `ImportBatch` y `ImportService.preview()`. La plantilla muestra los estados 0–8; condiciona subida/validación/ejecución/cancelación por estado y permiso; recorre errores y las primeras filas del preview. Sus valores se insertan como expresiones Jinja escapadas dentro de HTML; no usa Alpine ni scripts embebidos.
- Los desajustes conocidos permanecen en sus issues: reemplazo de archivo oculto en estado 1 y `started_at` que bloquea reintento (#1528), ausencia de controles para recuperar estados 2/7 (#1393), preview que puede lanzar excepción con entrada corrupta (#1031), y discrepancia permiso visible `validar` vs. guard de `editar` aún pendiente de criterio. No detecté causa adicional confirmada ni abrí otro issue.
- La revisión del archivo ya estaba registrada como revalidada; no cambia el recuento: 536 entradas (26 revisadas/revalidadas, 25 parciales, 43 lecturas previas pendientes, 442 pendientes, 0 invalidadas). El componente Imports sigue abierto.
- Próximo: continuar la revisión de los métodos no cerrados de `ImportService` y sus interacciones con estado y errores; después reconciliar el contrato de ejecución asíncrona, rutas y adaptadores del flujo bancario.

### Error de persistencia no recuperado por el manejador fatal (2026-11-01)

- Reproducción con `ImportService._execute_task()` real y SQLite en memoria: un trigger temporal que falla el `UPDATE` de `processed_rows` con `IntegrityError` provoca fallo en `_update_batch_progress()` después del commit del documento.
- `_execute_task()` atrapa `SQLAlchemyError` y llama `_handle_execution_error()`, pero el handler no revierte la sesión fallida. La llamada intenta registrar el error y su commit lanza `PendingRollbackError`. Después de revertir la sesión de auditoría, el estado durable del lote sigue 4, `started_at` está poblado, `completed_at` está nulo y los contadores siguen cero; no existe `FATAL_ERROR`. El documento previamente confirmado permanece, por lo que la evidencia de negocio y el progreso divergen.
- Hallazgo añadido como causa complementaria del fallo parcial/recuperación en issue existente #1062, comentario 6562319043. La reproducción usó trigger temporal; no se modificó código productivo, pruebas ni esquema del repositorio.
- El issue #1062 ya cubre el commit de documento previo a los contadores y la imposibilidad de reanudar de forma segura; este resultado identifica que también falla el manejador fatal al recibir una sesión en estado rollback requerido. No se abrió duplicado.
- Estado del inventario sin cambio: 536 filas, 26 revisadas/revalidadas, 25 parciales, 43 lecturas previas pendientes de integración, 442 pendientes y 0 invalidadas. `ImportService` sigue parcial.
- Próximo: revisar el contrato lector/worker entre `execute()` y `_execute_task()` y continuar el resto de métodos/relaciones de Imports; no considerar el componente cerrado por estos hallazgos.

### Rechazo de CSV válido en fallback MIME (2026-11-01)

- Revisión del fallback de `imports/routes.py`: al forzar que `_load_magic()` represente una dependencia no disponible, `_validate_mime_type()` con `FileStorage` real y `nombre\nCliente A\n` devuelve `False`. El helper rechaza el contenido porque `csv.Sniffer` no puede inferir delimitador en un CSV de una columna.
- El mismo payload, guardado temporalmente y procesado por `CSVReader.read()`, produce `columns=['nombre']`, `rows=[['Cliente A']]`; `CustomerAdapter.validate_row()` devuelve cero errores. Por tanto es un CSV válido para el esquema mínimo de cliente que el fallback rechaza antes de persistirlo. Se comprobó que el archivo conserva el stream en posición cero.
- Issue existente #1631 describe exactamente la causa y el impacto; añadí revalidación del árbol actual en comentario 6562345455. No se abrió issue duplicado ni se tocaron producto o pruebas. La búsqueda del directorio `tests` no encontró cobertura para `_valid_csv_fallback()`/`_validate_mime_type()` ni CSV de una columna.
- Recuento sin cambio: 536 archivos (26 revisados/revalidados, 25 parciales, 43 lecturas previas pendientes de integración, 442 pendientes, 0 invalidados). `routes.py` continúa parcial por sus demás contratos y los casos #1661/#1662/#1631.
- Próximo: continuar con `ImportService`/`execute()` y el contrato lector-worker; luego terminar los paths de subida y autorización antes de cerrar Imports.

### Fecha Excel al cierre de período bancario (2026-11-01)

- Reproducción end-to-end con archivo XLSX real, `XLSXReader`, `BankStatementAdapter`, `ImportService.validate()` y SQLite aislado. Con cuenta bancaria de `cacao` y período abierto 2026-01-01 a 2026-01-31, una fila con celda fecha Excel `datetime(2026, 1, 31, 00:00)` quedó en estado 2 con error de período cerrado/inexistente.
- Contraste controlado: un CSV con la misma cuenta y fecha ISO `2026-01-31` pasó validación (estado 3, cero errores). La celda XLSX fue leída como `datetime`; `is_period_open()` recibe el `datetime` sin normalizar y la comparación del campo SQLite `DATE` con el parámetro `DATETIME` devuelve falso en la fecha final inclusiva.
- Hallazgo existente #1472; amplié la evidencia al recorrido completo del importador en comentario 6562383234. No se abrió duplicado ni se modificó código o pruebas.
- Recuento sin cambio, verificado desde el manifiesto: 536 filas (26 revisadas/revalidadas, 25 parciales, 43 lecturas previas pendientes de integración, 442 pendientes, 0 invalidadas). `imports/utils/validation.py` queda documentado para este consumidor; la revisión de otros consumidores de `is_period_open()` sigue pendiente.
- Próximo dentro del componente: continuar las dependencias del lector/worker y los casos de fecha de otros adaptadores, sin asumir que normalizar el valor para bancos resuelve los demás flujos.

### Inyeccion de formula mediante LF en exportacion de movimientos bancarios (2026-11-01)

- Reproducción con SQLite aislado, cuenta bancaria real y `BankStatementAdapter`: una descripción `"\n=1+1"` pasó `validate_row()` sin errores, se persistió en `BankTransaction` y `get_bank_movement_detail()` la devolvió íntegra como `remarks`.
- Pasé el reporte real por `_export_operational_report(..., export=csv)`. El CSV producido contiene el campo entre comillas con LF al inicio seguido de `=1+1`. `_spreadsheet_value()` no lo altera porque filtra `=`, `+`, `-`, `@`, TAB y CR, pero omite LF; `csv.writer` conserva el salto de línea. OWASP identifica LF inicial como iniciador de fórmula en CSV. Reproducción real del pipeline importación → persistencia → consulta → exportación.
- No encontré issue equivalente. Creé #1664 (`needs-work`) con severidad media, impacto, reproducción, archivos y comportamiento esperado. No se modificó código ni prueba. El guard de entrada y la sanitización de salida son barreras distintas; el issue documenta el camino verificable completo.
- `imports/adapters/base.py` permanece parcial; `reportes/helpers.py`, `reportes/services.py`, `reportes/routes.py` y `reportes/templates/reportes/operational_report.html` quedan parciales por esta dependencia cruzada. Recuento reconciliado: 536 filas, **26 revisadas/revalidadas**, **29 parciales**, **43 lecturas previas pendientes de integración**, **438 pendientes**, **0 invalidadas**.
- Trazado de la dependencia de exportación: `/reports/bank-movement` está protegido por `login_required` y `modulo_activo(("cash", "banking"))`, carga `get_bank_movement_detail()` y lo pasa a `_render_operational_framework()`. Este marco transforma los datos con `report_authorship()`, llama `_export_operational_report()` y devuelve el archivo cuando `export` es CSV/XLSX/PDF. `operational_report.html` expone enlaces CSV/XLSX que preservan la query actual. La reproducción de contenido malicioso ejecutó el helper de exportación directamente; el acceso y delegación HTTP se confirmaron por inspección, no mediante cliente HTTP. Rutas de otros reportes, autorización por compañía/cuenta y el resto de la plantilla siguen sin auditar.
- `reportes/routes.py` y `reportes/templates/reportes/operational_report.html` pasan de pendientes a parciales por este trazado; el issue #1664 queda sustentado por el pipeline importación → persistencia → servicio → exportador y el enlace de la interfaz. Recuento reconciliado: 536 filas, **26 revisadas/revalidadas**, **29 parciales**, **43 lecturas previas pendientes de integración**, **438 pendientes**, **0 invalidadas**.
- El componente principal sigue siendo Imports/Extractos bancarios. La relación concreta con la exportación bancaria está trazada; siguen pendientes el resto de imports y la auditoría amplia de reportes, sin cerrar ninguno de esos componentes.

### Reconciliacion de HEAD y continuidad de Imports (2026-11-01)

- HEAD registrado al inicio de esta secuencia: `4d899a368e100c2155bb435b405a9baebfce993e`, rama `estabilizacion`, alineado entonces con origin; su padre era `5ae4b5ae6663922f9bbc99fd3ab45dc6281cfb56`. La referencia vigente está al inicio del archivo y el checkpoint más reciente al final.
- El commit `4d899a36` quita Python 3.15 de `.github/workflows/python.yml`, cambia una línea en `cacao_accounting/inventario/services.py` y modifica `tests/test_cache_isolation.py`. Se preserva la revisión previa del workflow con un delta de matriz pendiente; `inventario/services.py` sigue pendiente en su componente. La prueba no forma parte del inventario productivo. Sin invalidaciones.
- Worktree observado durante la revisión: modificaciones ajenas en `cacao_accounting/accounting_engine/fiscal/engine.py`, `cacao_accounting/accounting_engine/gl_posting_builder.py`, `cacao_accounting/inventario/service.py`, `cacao_accounting/printing/service.py` y `tests/test_cache_isolation.py`. Se preservan sin inspección ni edición; registrar/revisar sus deltas en sus componentes. No invalidan evidencia previa.
- Revisión cruzada limitada de `api/line_import.py`: sus consumidores son conciliación de pagos y comprobante contable, no el importador `bank_statement`. `_xlsx_rows()` deja abierto el workbook; con un XLSX válido, `os.unlink()` inmediato devuelve `PermissionError`/WinError 32 y funciona después de `gc.collect()`. `parse_xlsx_lines()` ignora el error de borrado. Coincide con #1446/#1603, ligados a #1652; agregué evidencia independiente en el comentario 6563114348. No se abrió duplicado ni se editó código.
- Revalidé `imports/models.py` cruzando campos, claves foráneas y estados con `imports/routes.py`, `ImportService` y `recover_crashed_batches()`. La ruta no ofrece borrado de lotes; `ImportBatchError` tiene cascade para la eliminación de su padre. Los defectos de ciclo de estado/reintento/cancelación están ya vinculados a #1528/#1395/#1032. No se encontró una migración SQL separada; la tabla se define en el modelo ORM.
- Reconcilié las 536 filas actuales del manifiesto: **26 revisadas/revalidadas**, **30 parciales**, **43 lecturas previas pendientes de integración**, **437 pendientes** y **0 invalidadas**. No se modificó código ni pruebas.
- La revisión paralela reprodujo en SQLite la falta de ownership de `bank_account` en `journal_entry`: la validación, `create_journal_draft()` y `submit_journal()` permiten cuenta B en comprobante A y producen dos `GLEntry` (dos libros), cada uno de A con BankAccount de B. Abrí #1665 (`severity-high`, `needs-work`) con reproducción y refs #350/#595/#757, añadí análisis del vector en #350 (6563167803) y confirmé el fanout multilibro en #1665 (6563197094). Tres agentes independientes confirmaron el recorrido; la revisión no cubrió consultas posteriores/reconciliación.
- En `LineImportSchemaRegistry`, los 15 esquemas revisados tienen columnas/alias estructuralmente consistentes; `LABEL_*` permanece en español. `/api/line-import/schema` devuelve el diccionario sin localizarlo, y la plantilla/JS muestran `column.label` directamente. El helper devuelve `Cuenta`, `Débito`, etc. aunque el catálogo inglés ya traduce `Cuenta` a `Account`. Abrí #1666 (`needs-work`, severidad baja) para el defecto de interfaz. Los archivos afectados pasan a parciales.
- HEAD avanzó y quedó alineado con origin en `4154dbe29730cca4efa27d9fd620dda144bef4e1`: `67d41a0c` reorganizó complejidad en `accounting_engine/fiscal/engine.py`, `accounting_engine/gl_posting_builder.py`, `inventario/service.py`, `printing/service.py` y una prueba; `4154dbe2` ajustó `balance_confirmation_bp.py`. Se registran deltas pendientes en las filas correspondientes. Se conserva toda revisión anterior y no se invalida ningún archivo.
- Reproducción adicional del caso #1382 en el adaptador activo registrado: `_currency_and_rate()` con `moneda=USD`, base `NIO` y tasa histórica `36.5` devuelve `36.5` al recibir `tipo_cambio=0` numérico; con `"0"` textual lanza `ValueError` de tasa no positiva. Comentario al issue existente: 6563203811. `ImportService.ADAPTERS` usa `PurchaseOrderAdapter` desde `transaction_documents.py`; `rg` no encontró referencias productivas al adaptador legado `purchase_order.py`, que se conserva en el inventario como parcial.
- Revisión paralela de excepciones: cotejé las capturas de ejecución de `ImportService` con `BankStatementAdapter`, `CashForecastEntryAdapter`, `JournalEntryAdapter`, `TransactionDocumentAdapter` y adaptadores maestros. No hallé/reproduje un archivo válido que pase `validate()` y luego arroje una excepción no capturada que deje el lote procesando. Excepciones de ORM y errores típicos de datos están cubiertos; #1031/#1062/#1203 son fallos distintos ya documentados. Sin issue nuevo ni cambios de código.
- Delta de concurrencia, funciones revisadas `ImportService.execute()`/`_execute_task()`/`_update_batch_progress()`/`_finalize_execution()`, `BankStatementAdapter.persist_document()` y `BankTransaction.identity_key`: dos agentes reprodujeron con SQLite temporal dos workers reclamando el mismo lote (`status=3`, `started_at=NULL`). Ambas llamadas devolvieron `True`. Dependiendo del interleaving, se persistió una fila pero status/contadores indicaron fallo sin éxitos (`6/1/0/1`), o se insertaron dos movimientos con identidad igual y se cerró como éxito (`5/1/0`). Agregué ambas salidas a #1319, comentario 6563266209; no abrí duplicado. Alcance: `validate()` actual asigna `started_at` en status 3 y #1528 bloquea la ruta normal, por lo que el estado listo sin inicio se aisló para probar el guard de concurrencia; la atomicidad debe resolverse al corregir ese bloqueo.
- Recuento actual de las 536 filas: **26 revisadas/revalidadas**, **34 parciales**, **43 lecturas previas pendientes de integrar**, **433 pendientes**, **0 invalidadas**.
- Continuidad: Imports bancarios permanece como componente principal; las revisiones paralelas de S2P y diario se conservan como parciales y no cambian el orden. `ImportService` sigue parcial por el ciclo de estado/reintentos. Próximo: cerrar las dependencias restantes de `imports/routes.py` y el frontend bancario, documentando por separado los criterios aún abiertos de reintento y reemplazo de archivos; no repetir los casos #1031/#1062/#1203/#1528 ya registrados.

### Reconciliación incremental y auditoría paralela (2026-11-01)

- HEAD observado: `c62c3604646f65ce37100412edf2432a8f74cef6`; `origin/estabilizacion` sigue en `4154dbe29730cca4efa27d9fd620dda144bef4e1`, por lo que la rama está 2 commits adelante. `4eb8e131` modifica solo `tests/test_cache_isolation.py`, excluido del inventario; `c62c3604` cambia la invocación de Complexipy en `.github/workflows/lint.yml`, registrada como delta pendiente. Ninguno toca Imports y no se invalidan revisiones previas.
- Revisé `imports/column_labels.py` función por función y sus consumidores `BaseImportAdapter.localized_columns()`, generación CSV/XLSX/ODS en `imports/routes.py` y canonicalización antes de validación/preview en `ImportService`. Un cotejo estático sobre las 9 clases con listas literales de columnas confirmó round-trip español/inglés sin colisiones para ambas lenguas, incluyendo listas heredadas por los tipos de documento. Los encabezados no reconocidos se conservan literalmente; no hay criterio de producto que establezca tolerancia a espacios/capitalización, así que no se reporta como defecto.
- Revisé `imports/readers/base.py`: contrasté defaults aislados del dataclass, salida de `BaseReader.read()` y las cuatro clases CSV/XLS/XLSX/ODS registradas con el servicio. El contrato de `NormalizedTable` coincide; los lectores pueden conservar filas de ancho irregular y `ImportService._normalize_rows()` las trunca al combinar `zip`, ya vinculado a #1534/#1474/#1652. No encontré un hallazgo adicional atribuible al archivo base.
- Revalidé `imports/readers/__init__.py` y `imports/utils/__init__.py` y sus importadores: ambos contienen solo SPDX/docstring, sin reexportaciones ni efectos ejecutables; los servicios utilizan imports explícitos de submódulo.
- Las revisiones paralelas del mismo componente terminaron en HEAD `c62c360`: `routes.py` quedó cotejado por helper/ruta/permiso/estado y contrato; las tres plantillas Imports y el recorrido Smart Select quedaron trazados; `BankStatementAdapter` y sus dependencias directas de ledger/conciliación se revisaron sin defecto nuevo. Se conserva `imports/routes.py` parcial porque el criterio de exigir `access` además de permiso de acción sigue incierto; `validar` + `editar` también requiere política.
- Evidencia de cobertura por símbolo: `imports/routes.py` incluye `_load_magic`, `check_desktop_mode`, `check_permission`, `_batch_or_404`, `_resolve_company_book`, `_extract_file_extension`, `_validate_mime_type`, `_valid_csv_fallback`, `_persist_uploaded_file` y endpoints `index/new/detail/upload/validate/execute/cancel/download_template`. En `new.html` se cotejaron `x-data`, selector de compañía, `recordType`, `#import-entity-type`, filtro de `sequence_id` y `x-if` de `accounting_book_id`; `index.html` permisos/listado/estados/progreso; `detail.html` permisos, transiciones/controles, descargas y preview. `smart_select_field.html` y `smart-select.js` se siguieron desde config/preload hasta eventos/fetch; `index/detail` no contienen JS/Alpine adicional.
- Candidato `access=False, consultar=True`: dos agentes reprodujeron HTTP 200 en `/imports/`, detalle de lote y descarga de plantilla para una compañía explícitamente asignada; `/imports/new` devuelve 403 sin `crear`. `modulo_activo` solo verifica módulo habilitado; `check_permission` y `exige_acceso_compania` verifican acción/compañía sin `Permisos.autorizado`. No hay acceso cross-company. #1600/#1601 describen la combinación inversa, #1327 otro flujo y #1649 es una consolidación amplia sin esta combinación Imports específica; como no está confirmado si `access` debe ser requisito adicional a una acción, queda como pendiente de criterio, sin issue.
- Fuga de listeners del selector de libro confirmada por dos reproducciones independientes en Node/JSDOM: montajes y desmontajes repetidos bajo `x-if` dejan listeners `input`/`change` en `#import-company`; con cuatro instancias desconectadas, un cambio invoca cuatro cargas redundantes. Revisé #1420/#1463/#1554 y no cubren ese ciclo de vida. Abrí #1667 (`bug`, `needs-work`, `severity-low`, `javascript`, `imports`, `audit`) con reproducción y refs #757. No se observó cambio persistido ni exposición adicional.
- El hallazgo CSRF de las plantillas ya corresponde a #1648; no se abrió duplicado. En `BankStatementAdapter` se revisaron `_optional_amount()`, `validate_row()`, `validate_document()`, `build_document()`, `persist_document()` y `_auto_reconcile()`, más los checks de período, idempotencia/identity key, modelos/listeners de BankAccount/BankTransaction y llamadas a `statement_service`/`reconciliation_service`; no surgió otro defecto confirmado aparte de los issues listados. Cuenta bancaria inactiva y moneda nullable quedan como criterios de negocio. PostgreSQL no está disponible; una sonda de concurrencia de conciliación SQLite no logró un interleaving reproducible (bloqueo DB antes del barrier).
- Revalidé `recover_crashed_batches()` y su llamada por `create_app()`: ejecuta solo al crear app, filtra status 4 sin fecha o con más de 4 h, actualiza a 7 e inserta `SYSTEM_TIMEOUT` en un commit; el caso nulo previo al worker ya está en #1203. La marca de inicio que bloquea reintentos coincide con #1528. No hay heartbeat; si ese umbral debe detener workers vivos es criterio de producto. Dos agentes reprodujeron secuencialmente con ORM/servicio reales que recovery deja status 7 y `_finalize_execution()` posterior lo cambia a 5 conservando `SYSTEM_TIMEOUT`; la condición operacional exige un worker vivo que supere 4 h y un arranque que ejecute recovery. Vinculé la evidencia a #1203 (comentario 6563427237), sin abrir duplicado; la carrera entre dos recoveries no se probó.
- Revalidé el camino de fechas nativas XLS para bancos: dos agentes confirmaron con archivos `.xls` reales/fixture que `XLSReader.read()` devuelve serial fecha como `float` y `BankStatementAdapter.validate_row()` lo rechaza como ISO inválido; añadí evidencia bancaria a #1201 (comentario 6563435620), sin duplicar #1472 (fechas XLSX como `datetime` que fallan en límite de período).
- En la revisión completa de `ChartOfAccountsAdapter`, el importador hereda `validate_document() -> []`, asigna `padre` directo a `Accounts.parent` y persiste sin llamada a `_validate_account_parent()`. Un repro aislado dejó `Accounts.parent='NO_SUCH_PARENT'` y el lote completado con una fila exitosa. Encontré el issue abierto #1063, que describe esta raíz; una segunda validación independiente está en curso antes de añadir comentario. También se detectó descarte de `clasificacion`/`grupo` en Customer/Vendor, pero el mapping esperado no está definido y queda como criterio, no issue confirmado.
- Recuento recalculado sobre las 536 filas del manifiesto: **25 revisadas/revalidadas**, **35 parciales**, **43 lecturas previas pendientes de integrar**, **433 pendientes** y **0 invalidadas**. `smart-select.js` y `smart_select_field.html` pasan a parciales porque el alcance compartido fuera de Imports queda por revisar; `recovery.py` queda parcial por el comportamiento de timeout/worker que aún necesita triaje operacional. Se conservan los incrementos de `column_labels.py` y `readers/base.py`.
- Continuidad: Imports bancarios sigue como componente principal y no está cerrado. Próximo paso: resolver/registrar el criterio de permiso `access` cuando exista decisión del producto y continuar exhaustivamente el servicio y adaptadores pendientes de Imports; después auditar otros componentes en el orden ya listado.

### Evidencia paralela adicional de adaptadores de importación (2026-11-01)

- `imports/adapters/transaction_documents.py`: revisadas en paralelo las doce subclases, sus validadores/builders/persistencia y los checks reales de aprobación. Dos revisiones independientes reprodujeron que `PurchaseReceiptAdapter` acepta y persiste una cabecera de PO sin crear `DocumentRelation` por línea; el precheck de aprobación rechaza el recibo. Añadida la segunda reproducción a #1053 (comentario 6563564158); el mapeo de líneas fuente sigue pendiente de criterio para líneas repetidas y entregas parciales.
- `imports/adapters/transaction_documents.py`: segunda revisión independiente reprodujo importación exitosa de una orden con `is_purchase_item=False` que el submit normal rechaza; añadida evidencia end-to-end a #1060 (6563561540). Otra reproducción independiente importó un cliente como proveedor, guardando su ID en `PurchaseOrder.supplier_id` y `supplier_name=None`; añadida a #1532 (6563563136). En ambos repros se limpió `started_at` solo en la DB temporal para aislar el bloqueo conocido #1528; el código, las pruebas y el estado del worktree no se modificaron.
- `imports/adapters/transaction_documents.py`: QA reprodujo que tarifa unitaria cero pasa validación/importación pero el precheck de aprobación exige tarifa positiva; el constraint de base permite cero. No hay issue dedicado localizado y #950/#1050 son otros casos. Se registra como discrepancia confirmada pendiente de criterio de producto, sin abrir issue.
- Estado reconciliado directamente desde las 536 filas del inventario: **26 revisadas/revalidadas**, **34 parciales**, **43 lecturas previas pendientes de integrar**, **433 pendientes** y **0 invalidadas**. La rama continúa en `c62c3604646f65ce37100412edf2432a8f74cef6`; no se invalida evidencia por cambios posteriores.
- Próximo trabajo paralelo registrado en este checkpoint: validar ChartOfAccountsAdapter y `imports/routes.py`; ya completado por dos revisores independientes (Chart #1063 confirmado; rutas sin fuga entre compañías; libro seleccionado vinculado a #1163). El criterio sobre precio cero y permisos `access`/`editar` sigue abierto.
- Actualización de `imports/adapters/chart_of_accounts.py`: QA validó independientemente el padre inexistente y contrastó persistencia del adaptador con `_validate_account_parent()` de la ruta manual; se agregó evidencia a #1063 (comentario 6563571527). El manifiesto conserva el archivo como parcial porque quedan otros caminos/campos del adaptador por revisar; conteo de archivos sin cambio.
- Actualización de `imports/adapters/base.py`: revisé las cinco funciones/métodos de la clase y crucé `validate_row()` con sus ocho adaptadores directos, incluidas reglas de columnas requeridas y detección de prefijos de fórmula. Los defectos whitespace-only (#1052) y LF inicial (#1664) se mantienen vinculados a issues; no se abrió otro. Archivo promovido a revisado/revalidado; el manifiesto pasa de 26/34 a 27 revisados y 33 parciales, sujeto al recálculo mecánico siguiente.
- Actualización de `imports/routes.py`: el segundo revisor no encontró fuga entre compañías ni defecto adicional de handlers. QA confirmó que el libro elegido se amplía a todos los libros activos; AGENTS y el formulario manual fijan la expectativa, y la raíz existente es #1163 (comentario 6563588354). El archivo sigue parcial por criterios de permisos pendientes.
- Actualización de `imports/services/import_service.py`: tres agentes revisaron la validación, agrupación, commits/rollback, bloqueo y cancelación/recovery; no encontraron raíz adicional independiente. Dos reproducciones independientes con SQLite confirmaron que un batch cancelado sin filas queda status 4 aun con `cancel_requested=True` y `completed_at`; evidencia añadida a #1032 (comentario 6563598406), vinculada al caso sin cancelación #1200. El archivo sigue parcial.
- Actualización cruzada `imports/adapters/journal_entry.py` → `contabilidad/journal_service.py`: dos agentes reprodujeron en SQLite que una importación con `BOOK1` guarda un draft con `BOOK1` y `BOOK2`. El formulario contable permite desmarcar libros y AGENTS limita la selección específica al módulo contable; el hallazgo coincide con #1163. Añadí la evidencia del flujo importador al issue (comentario 6563588354); no se abrió duplicado. Ambas filas siguen parciales porque sus archivos tienen más lógica sin revisar.
- Actualización de `imports/adapters/journal_entry.py`: revisé fecha/balance/período, el adaptador de accounting lines, construcción, resolución de libros y persistencia. Un repro focalizado confirma que `datetime` nativo de XLSX retorna `validate_document() == []`, sobrevive en el payload y el parser del servicio lo rechaza; añadí evidencia a #1201 (comentario 6563618846). Se conserva #1530 (fechas diferentes por línea) y #1163 (libros seleccionados descartados). El archivo sigue parcial por revisión restante de excepciones, multimoneda y consumidores contables.
- Estado actual recalculado desde las 536 filas: **29 revisadas/revalidadas**, **32 parciales**, **42 lecturas previas pendientes de integrar**, **433 pendientes**, **0 invalidadas**. HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`, rama `estabilizacion`; los cambios posteriores se registran como deltas y no invalidan la evidencia previa.
- Siguiente revisión del componente Imports: retomar el primer archivo parcial de su manifiesto, `cacao_accounting/imports/adapters/chart_of_accounts.py`, para cerrar el dominio de los campos además del padre/clasificación. `api/line_import.py` y `api/line_import_registry.py` ya quedaron revisados. Después continuar las rutas, servicio y adaptadores restantes con sus dependencias.
- Actualización de `imports/adapters/vendor.py`: revisión completa e independiente de los métodos, campos, código de proveedor, `Party`/`CompanyParty`, consumidores y rutas manuales. Se confirmó la integración con agrupación (#1346) y requeridos whitespace-only (#1052); el tax ID no es unique, pero la ruta manual también permite ese valor y no hay política de deduplicación. Sin issue nuevo. El archivo continúa parcial únicamente porque `clasificacion`/`grupo` no tienen un mapeo de negocio confirmado.
- Actualización de `imports/adapters/customer.py`: revisión paralela de todos los métodos y de la creación manual. El repro en dos batches creó dos Parties y dos vínculos CompanyParty con el mismo tax_id; no hay constraint ni dedupe manual, por lo que se registra como criterio de identidad, sin issue confirmado. El flujo import crea vínculo CompanyParty pero omite settings/PartyAccount; el resolver usa los defaults de compañía cuando faltan, sin impacto demostrado. Se mantienen #1052/#1346 y el criterio pendiente de `clasificacion`/`grupo`; el archivo continúa parcial.
- Actualización de `imports/utils/validation.py`: revalidé la función y enumeré los cinco consumidores productivos por `rg`, cotejándolos con las revisiones de bancos, asientos, órdenes de compra/transacciones e ImportService. Los valores `datetime` que desajustan SQLite y la normalización Excel ya están registrados en #1472/#1201. El archivo ya figuraba como revisado; su estado y el recuento no cambian.
- Actualización de `imports/adapters/chart_of_accounts.py`: revisión completa adicional por QA de clasificación, tipo, grupo, moneda, unicidad y compañía. SQLite confirmó que `clasificacion=not-a-class` pasa validación y persiste aunque el formulario rechaza ese dominio; abrí #1668 con el repro. También se registran como criterios pendientes el dominio de `tipo`, los booleanos de `grupo` y el uso de `moneda` para cuentas. No se agrupan con #1063 (padre) ni se abrió issue para campos sin semántica acordada.
- Actualización de `imports/utils/recovery.py`: revisión independiente identificó/reprodujo en SQLite WAL una carrera entre dos recoveries sobre el mismo status 4 expirado: ambos devuelven 1 y añaden errores SYSTEM_TIMEOUT, queda un lote status 7 con dos errores. El interleaving se fijó en el harness temporal después del SELECT real; sin cambios en el repo. Se solicitó reproducción de QA antes de agregar evidencia a #1203; no se abre duplicado por ahora.
- Actualización de `imports/utils/recovery.py`: tres agentes reprodujeron independientemente la duplicación de errores `SYSTEM_TIMEOUT` con dos invocaciones reales concurrentes y SQLite WAL temporal. Los issues #1203/#1031 cubren lotes zombis, no errores duplicados; abrí #1669 (`bug`, `needs-work`, `severity-low`, `imports`, `audit`) con el límite de que PostgreSQL no se probó y añadí tercera corroboración QA (6563660967). No se afirma comportamiento específico de ese motor.
- Actualización de `imports/adapters/chart_of_accounts.py`: abrí #1668 (`bug`, `needs-work`, severidad media) por clasificación arbitraria persistida y no reconocida. QA verificó independientemente que el clasificador no asigna categoría normal, pero el reporte muestra la cuenta y su monto como “no clasificados”; corregí el body para no afirmar pérdida silenciosa ni bloqueo del GL. Los candidatos de tipo/grupo/moneda permanecen pendientes de definición y no se mezclaron en el issue.
- Candidato adicional de `ChartOfAccountsAdapter`: la ruta manual invalida `smart-select-master-data` al crear cuenta, mientras la persistencia por import no llama esa invalidación; la API de selección cachea cuentas por 300s cuando Redis está disponible. Sin un repro de Redis no se afirma impacto; queda pendiente dentro del mismo subflujo, sin issue.
- Actualización de `api/line_import_registry.py`: el revisor cotejó los 15 esquemas, alias, tipos, campos requeridos, mapeo de módulos y normalizadores de cabeceras del servidor/JS; no encontró colisiones. #1665/#1666 quedan vinculados a los campos/labels ya reportados. El revisor API encontró el consumidor dedicado de `payment_reconciliation` en `bancos/templates/bancos/conciliacion_facturas_pagos.html` (no está en `transaction-form.js`); se corrige el gap aparente. Detectó pérdida posible de `description` en la asignación genérica de líneas, pendiente de criterio/repro UI. El archivo sigue revisado/revalidado; el conteo no cambia.
- Actualización de `api/line_import.py`: inspección de código y QA con SQLite real confirman que `/api/line-import/validate` acepta dos aplicaciones de 60 a un pago de 100, pero `apply_payment_reconciliation()` rechaza la segunda y revierte la conciliación. El repro añadió `reference_document` para aislar este defecto, porque el esquema oficial tropieza antes con #1456. Es duplicado de #1398 (comentario 6563728434) y también está cubierto por #1205/#1439; no se abre nuevo. El XLSX sparse de 60,000 filas está vinculado a #1652 (6563704367). El archivo sigue parcial por revisión restante de contratos.
- Reproducción independiente de `api/line_import.py`: QA y un segundo agente confirmaron por separado el mismo 100/60+60 con endpoint/reconciliador reales; agregué la corroboración a #1398 (comentario 6563739357). El formulario oficial de cuatro columnas queda bloqueado antes por #1456, y la segunda prueba agregó `reference_document` para aislar #1398. El archivo de conciliación bancaria pasa de lectura previa a parcial por este seguimiento; conteo actualizado: **28 revisadas**, **33 parciales**, **42 lecturas previas**, **433 pendientes**, **0 invalidadas**.
- Revisión de `api/line_import.py` completada: contrasté el inventario de sus endpoints/helpers con la revisión paralela de permisos, parsing XLSX, límites, referencias y errores; no hay un hallazgo nuevo independiente de los issues vinculados. El archivo pasa de parcial a revisado/revalidado. Conteo actual: **29 revisadas**, **32 parciales**, **42 lecturas previas**, **433 pendientes**, **0 invalidadas**.
- Reconciliación de referencias Git: al recalcular, `origin/estabilizacion` y HEAD local `c62c360` coinciden; el commit local no cambió desde el checkpoint anterior. El único cambio local autorizado sigue siendo `AUDIT_PROGRESS.md`; `.codex/` permanece sin tocar.
- Delimitación de continuidad: la unidad de trabajo sigue siendo el componente funcional Imports, ahora descrito explícitamente como lotes y líneas con subflujos CTM/O2C/S2P/R2R. El paso a `CTM restante` queda pendiente hasta reconciliar todos los archivos, contratos e incertidumbres del componente Imports.
- Hallazgo confirmado en `transaction-form.js` y contrato de line-import: #1670 (`needs-review`, `severity-low`) registra que el schema/API conserva `description`, pero la conversión genérica la descarta; QA corroboró el recorrido en comentario 6563786423. Los modelos/formularios usan `item_name`, `description` y `remarks` de forma distinta por doctype, por lo que el destino queda como criterio sin decidir. El issue se limita a la pérdida demostrable y pide definir el mapping.
- Revisión cruzada adicional de `JournalEntryAdapter`: el segundo lector cotejó moneda, libros y referencias con `create_journal_draft()`; no encontró hallazgo fuera de #1201/#1530/#1163. La discrepancia de validación de moneda de línea queda bajo #758 pendiente de reproducción, no issue nuevo.
- Revisión de control de bordes en `TransactionDocumentAdapter`: no aparecieron defectos confirmados nuevos ni rutas de mutación/anulación del ledger en el adaptador, que solo crea borradores. Multimoneda operativa fuera del posting GL no se verificó en esta pasada. Se dejan cabeceras distintas por grupo y serial requerido/cantidad como pendientes de reproducción/triaje; no se fusionan con #1531 sin confirmar raíz.


### Checkpoint de archivo - `cacao_accounting/imports/services/import_service.py` (2026-11-01)

- Estado: auditado en HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; 26/26 funciones AST revisadas. Incluye `_IndexedImportRow.__init__`, lectura/adaptador, normalizacion de filas y encabezados, validacion estructural/de negocio, preview, ejecucion sincrona/asincrona, cancelacion, procesamiento y commits por documento, control de periodo, manejo de errores, progreso/finalizacion y agrupacion por referencia.
- Contratos revisados: `ImportBatch` y `ImportBatchError`, estados 0-8, `validate()`/`execute()`/`cancel()` en routes, adaptadores y lectores registrados, recuperacion al iniciar la app y cambio de actor en trabajo asincrono. Los adaptadores no hacen commits propios dentro de `imports/adapters`; `_process_document()` delimita el commit por documento.
- Hallazgo nuevo confirmado: `validate()` asigna `started_at` UTC, `ImportBatch.started_at` usa `DateTime` sin zona y `recover_crashed_batches()` calcula el timeout con hora local. La reproduccion real SQLite en memoria bajo UTC-6 dejo un lote con 5 h en estado 4 (`started_at` almacenado ingenuo a las 16:00, hora local 15:00, limite local 11:00): recuperacion=0 y estado=4. QA independiente reprodujo tambien vencimiento prematuro con UTC+6. Busqueda de issues y contraste con #1031/#1062/#1203 no encontraron duplicado; issue [#1671](https://github.com/cacao-accounting/cacao-accounting/issues/1671) creado (`bug`, `needs-work`, `severity-low`, `imports`, `audit`), con referencias precisas y limites de motor.
- Issues existentes corroborados en la lectura actual: #949 (fila fuente al agrupar), #956 (encabezados localizados), #1031 (lector corrupto), #1032 (cancelacion/finalizacion), #1062 (lote fallido sin recuperacion segura), #1067 (actor en conciliacion asincrona), #1200 (lote sin filas), #1203 (estado 4 sin inicio/recovery), #1319 (duplicados bajo concurrencia), #1392 (limites de materializacion), #1395 (cancelacion fuera de estado), #1528 (marca de inicio retenida que bloquea revalidacion). El historial anterior conserva las reproducciones; no se abrieron duplicados.
- Criterio pendiente, sin issue: `validate()` ejecuta bulk DELETE de `ImportBatchError` al revalidar (`import_service.py:138`). El codigo confirma la eliminacion, pero queda por definir si estos errores operativos son evidencia historica append-only o resultados reemplazables de validacion; no se asume una politica nueva.
- Riesgo conocido no resuelto en este pase: `execute()` confirma estado 4 antes de iniciar el hilo; `_execute_task()` no reclama atomicamente el lote; algunos finales/cancelaciones ya estan vinculados a #1032/#1203/#1319. No se modifica codigo productivo.
- Siguiente archivo en la secuencia inicial: `cacao_accounting/imports/utils/recovery.py`; su revision completa queda registrada en el checkpoint siguiente.


### Checkpoint de archivo - `cacao_accounting/imports/utils/recovery.py` (2026-11-01)

- Estado: auditado en HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; 2/2 funciones revisadas: `_import_tables_exist()` y `recover_crashed_batches()`.
- Contratos e interacciones: inspeccion de tablas antes de consultar; recuperacion invocada durante el inicio de `create_app()`; filtro de estado 4, limite de cuatro horas, insercion de `SYSTEM_TIMEOUT` y cambio de estado en un commit; lectores de `ImportBatch.started_at`/`ImportBatchError` cotejados con `imports/models.py`.
- Causas confirmadas y issues: el SELECT y el cambio/alta no reclaman el lote atomicamente; dos recoveries concurrentes pueden insertar dos errores por el mismo timeout (#1669). La comparacion UTC/local y SQLite esta documentada en #1671. #1203 cubre el estado 4 con marca de inicio nula; la ruta actual trata NULL como vencido inmediatamente, lo que evita un lote perpetuamente invisible pero deja una ventana de carrera con un worker que acaba de reclamar el lote. No se abrio issue separado porque requiere una reproduccion cross-process que determine si la causa ya esta cubierta por #1203/#1669.
- No se encontro otra mutacion ni borrado en este archivo; una falla del commit mantiene en una sola transaccion el cambio de estado y el error de timeout. No se probo PostgreSQL; la limitacion de motor esta declarada en #1669.
- Siguiente archivo despues de `recovery.py`: `cacao_accounting/imports/adapters/journal_entry.py`; se completa en el checkpoint siguiente.


### Checkpoint de archivo - `cacao_accounting/imports/adapters/journal_entry.py` (2026-11-01)

- Estado: auditado en HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; 9/9 funciones AST revisadas: `_amount`, `_value`, `_validate_amounts`, `_validate_period`, `_validate_accounting_lines`, `validate_document`, `build_document`, `persist_document` y `_resolve_books`.
- Contratos cotejados con `ImportService` y `contabilidad/journal_service.py`: fecha/persistencia, normalizacion de lineas, cuentas, tasas, balance por libro, authorization del actor y seleccion de libros. No se modifico codigo.
- Hallazgo nuevo #1672 (`bug`, `needs-work`, severidad baja): una cuenta inexistente pasa validacion y falla al persistir. Reproduccion SQLite en memoria con compania NIO activa, periodo abierto y lineas balanceadas con cuentas inexistentes: `validate_document()` devuelve `[]`; `create_journal_draft()` rechaza la cuenta con `JournalValidationError` y no deja borrador. QA independiente confirmo el resultado. Busqueda sin duplicado; #1529 es sobre fecha invalida, #758 sobre moneda y #1665 sobre ownership de cuenta bancaria.
- Hallazgo nuevo #1673 (`bug`, `needs-work`, severidad media): el prechequeo suma importes nominales sin tasa. Una linea USD 100 debitada a 36.5 y otra NIO 3,650 acreditada a 1 queda balanceada en moneda funcional, y el motor contable la acepta, pero `_validate_amounts()` la rechaza antes de llegar a ese motor. Reproduccion SQLite en memoria con cuentas existentes y periodo abierto; QA independiente confirmo el mismo resultado. #758 es relacionado por multimoneda, pero no describe esta exclusion concreta; #284 trata precision/redondeo y no es duplicado.
- Causas existentes corroboradas: `_validate_period()` no reporta fechas invalidas durante la validacion (#1529); las fechas Excel nativas no se normalizan de forma uniforme (#1201); solo se valida/usa la fecha de la primera linea por referencia (#1530); el servicio sustituye la seleccion de libro por todos los activos (#1163). Se conserva la evidencia previa en el manifiesto y en esos issues.
- Criterio pendiente sin issue nuevo: `_validate_accounting_lines()` convierte cualquier `RuntimeError` en ausencia de errores; no se encontro un `RuntimeError` de negocio alcanzable en las funciones llamadas durante esta revision, por lo que no se afirma impacto sin una reproduccion concreta.
- Proximo archivo exacto del componente Imports: `cacao_accounting/imports/adapters/transaction_documents.py` (31 funciones AST, parcial). Cerrar con prioridad fechas, multimoneda/tasas, relaciones de origen y persistencia contra `document_flow`, servicios de posting y recepcion de inventario; contrastar #1053, #1060, #1201, #1382, #1531 y #1659 antes de proponer issues.


### Checkpoint de archivo - `cacao_accounting/imports/adapters/transaction_documents.py` (2026-11-01)

- Estado: auditado en HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; **31/31 funciones AST** revisadas: configuracion declarativa, validacion numerica y documental, conversion/persistencia de encabezados e items, resolucion de moneda, lote y serie, y los 11 constructores de adaptadores de compras/ventas.
- Contratos cotejados: `ImportService` agrupa por referencia, valida cada fila/documento y confirma por documento; `DocumentFlow` valida moneda heredada y consume relaciones por linea; inventario convierte UOM, exige controles de lote/serie y valida vigencia en posting; compras/ventas validan roles, articulos, bodegas y precondiciones al aprobar; `DocBase`, modelos de linea y `assign_document_identifier()` fijan FKs, escalas y tipo de serie. El adaptador solo crea borradores y no muta evidencia ya registrada.
- Hallazgo nuevo #1674 (`bug`, `needs-work`, severidad baja): una recepcion de compra con lote activo pero vencido pasa `validate_document()` y se persiste como borrador; `validate_batch_serial()` la rechaza al aprobar por `expiry_date <= posting_date`. Reproducido por este agente en SQLite y por QA con posting real. Sin duplicado: #773 cubria resolver el numero de lote al ID y esta cerrado como corregido; no cubre vigencia.
- Hallazgo nuevo #1675 (`bug`, `needs-work`, severidad baja): `lote="   "` para articulo que no requiere lote pasa validacion pero `_resolve_batch_id()` falla durante `build_document()`; el worker termina con una fila fallida y sin borrador. Reproducido en SQLite por este agente y QA a traves del `ImportService` real. #1052 trata campos requeridos en blanco, causa funcional distinta.
- Residuo monetario verificado y registrado al reabrir #547 (sin issue duplicado): con tasa explicita positiva, `_currency_and_rate()` acepta moneda inactiva o inexistente. En SQLite con FKs activas, una moneda inactiva pasa validacion y persiste en borrador; una inexistente pasa validacion y falla en el `flush()` de persistencia por FK. QA independiente confirmo ambos resultados. #547 fue renombrado a `[AUDIT][Importaciones] Acepta moneda inactiva`, reabierto con `needs-work` y severidad baja; #758 sigue relacionado con el contrato monetario general.
- Issues existentes contrastados y no duplicados: #1053 (relaciones por linea origen), #1060 (elegibilidad/estado de articulo), #1198 (bodega obligatoria), #1382 (tasa numerica cero como fallback), #1531 (plantilla `serie` bloqueada por columna prohibida), #1532 (rol de tercero), #1533/#1535 (moneda/tercero no consistentes por referencia), #1054/#1478/#1628 (cabeceras distintas en grupo), #1201 (fecha Excel), #1659 (serie incompatible). #548 ya esta cerrado y el codigo actual valida existencia, aprobacion/compania del origen y compania/estado de bodega; #773 esta cerrado por la resolucion del ID de lote.
- Casos actuales sin hallazgo nuevo: `validate_row()` rechaza cantidad no positiva y valores numericos no finitos (#954/#950); las tasas explicitas no positivas se rechazan salvo el caso ya cubierto de cero numerico por `or` (#1382). El lote existente se resuelve a `batch_id`; UOM faltante/invalida genera error; bodegas se cotejan por codigo global unico, compania y estado activo. No se encontro ruta de anulacion/reversion en este adaptador.
- Pendientes de criterio/verificacion, sin issue nuevo: precio unitario cero pasa la importacion y el precheck de aprobacion requiere tasa positiva; el destino final y semantica de cero siguen sin decision de producto. Los requisitos de serie/cantidad dependen de que se resuelva #1531, y el posting impone una unidad por serie. La persistencia de escala monetaria en PostgreSQL no se reprodujo; una prueba ad hoc en SQLite conserva precision mas alla de `NUMERIC(20,4)`, por lo que no se afirma discrepancia cross-engine. No se modifico codigo productivo; no se ejecutaron suites automatizadas y no se encontro un archivo de pruebas vigente que cubra este adaptador mediante `rg`.
- Cobertura de inventario actualizada: 245 archivos Python productivos; **23 auditados**, **0 en revision**, **36 requieren revision**, **186 pendientes**. En `imports/adapters`: 7/10 auditados y 3/10 requieren revision.
- El componente Imports sigue en curso. **Siguiente archivo exacto:** `cacao_accounting/imports/adapters/chart_of_accounts.py`, para retomar la revision de sus campos y contratos pendientes; despues continuar `customer.py`, `vendor.py` y cerrar rutas/API segun el orden del manifiesto. No avanzar a otro componente antes de cerrar Imports.


### Checkpoint de archivo - `cacao_accounting/imports/adapters/chart_of_accounts.py` (2026-11-01)

- Estado: **auditado en HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; 2/2 funciones AST revisadas**: `build_document()` y `persist_document()`. Se evaluaron también el único adaptador/clase, columnas y campos requeridos.
- Contratos cotejados: el servicio agrupa/persiste por documento y captura fallos de ORM por documento; `Accounts` impone unicidad por `(entity, code)`, mantiene `parent` sin FK y `currency` nullable con FK. El contexto de importación aporta compañía y los flujos de consulta/alta manual del catálogo se contrastaron para padre, clasificación, tipo y moneda.
- Hallazgos y trazabilidad: #1063 cubre la asignación sin validar de `padre`; se añadió el caso `padre=""`, que queda como cadena vacía, se omite de raíces (`IS NULL`) y se trata como cuenta hija (`IS NOT NULL`). QA independiente confirmó el resultado y no abrió duplicado. #1668 ahora también cubre `tipo` fuera de `ACCOUNT_TYPE_CHOICES`, además de clasificación no reconocida; QA reprodujo ambos mediante `ImportService` y SQLite. El tipo arbitrario se persiste; no se reprodujo un asiento ni se afirma impacto contable específico. #1676 cubre `moneda=""`: con las FKs SQLite desactivadas persiste un valor vacío; con FKs activadas se cuenta como `IMPORT_ERROR`. No se probó otro motor.
- Hallazgo relacionado ya registrado: #1346 cubre que filas posteriores se descarten cuando maestros se agrupan por un `document_ref` repetido; aplica a este adaptador y a Customer/Vendor.
- Criterios pendientes sin issue: `grupo="sí"` se convierte a `False` en este adaptador y a `True` en `contabilidad.ctas._is_group()`, pero el README del catálogo documenta el formato `1`/`0`; falta confirmar si `sí` pertenece al contrato de esta importación. El parser también convierte valores booleanos desconocidos a `False`; no se reporta hasta fijar tratamiento requerido para entradas malformadas. Otro cargador asigna `tipo` a `Accounts.type_` y lee `account_type` por separado, mientras este adaptador acepta `tipo` como `Accounts.account_type`; la correspondencia entre esquemas queda pendiente de criterio. La validación de moneda no vacía/activa también requiere definir contrato. Estos criterios no amplían los issues confirmados.
- Se verificaron los límites de compañía y unicidad del modelo y el manejo por documento de errores de persistencia. No se halló ruta de anulación/reversión en este adaptador. No se ejecutó la suite automatizada; las reproducciones funcionales de los hallazgos fueron hechas independientemente por QA en SQLite. No se modificó código productivo.
- Cobertura recalculada sobre el inventario autoritativo de 245 archivos Python: **24 auditados**, **0 en revisión**, **35 requieren revisión**, **186 pendientes**. En `imports/adapters`: **8/10 auditados**, 2 requieren revisión (`customer.py`, `vendor.py`).
- Resumen del componente actual: `chart_of_accounts.py` queda cerrado como archivo; Imports continúa incompleto por los adaptadores Customer/Vendor y las rutas/criterios de permisos ya registrados. **Siguiente archivo exacto:** `cacao_accounting/imports/adapters/customer.py`. No cambiar a otro componente antes de terminar Imports.


### Checkpoint de archivo - `cacao_accounting/imports/adapters/customer.py` (2026-11-01)

- Estado: **auditado en HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; 2/2 funciones AST revisadas**: `build_document()` y `persist_document()`. Se aprovechó evidencia previa completa sobre campos, generación de código, `Party`/`CompanyParty`, rutas manuales y aislamiento; el HEAD no cambió. Este pase revalidó el contrato y cerró la cobertura verificable del archivo.
- Contratos: cada Party nueva es global y se vincula a la compañía del lote mediante `CompanyParty`; `(company, party_id)` es único y `/api/search-select` filtra por el alcance de compañías autorizadas. `ImportBatch.company_id` es obligatorio y se pasa como contexto. El código y vínculo se agregan dentro de la transacción del documento; si el procesamiento falla, `ImportService` hace rollback y registra error por documento.
- Hallazgo confirmado nuevo #1677 (`bug`, `needs-work`, severidad baja): tras una búsqueda vacía cacheada de cliente, importar mediante CSV real deja la Party disponible en DB pero el mismo Smart Select devuelve el resultado vacío hasta invalidación/TTL. QA reprodujo `0` cacheado frente a `1` directo en DB y luego `1` después de invalidar. Requiere modo cloud, Redis y misma clave autenticada; TTL 300 segundos. No afecta desktop ni la persistencia del registro. El issue cubre el caso reproducido en Customer y lista Vendor/ChartOfAccounts como rutas relacionadas por inspección, no como reproducciones adicionales.
- Issues existentes contrastados: #1346 cubre la pérdida de filas posteriores cuando referencias repetidas se agrupan, incluido `no_ref`; #1052 cubre `nombre` requerido con espacios que se valida y persiste; #1048, #1476 y #1383 describen el mismo descarte de `clasificacion`/`grupo` en importaciones de terceros y permanecen como criterio de mapeo, sin abrir duplicado. Los campos se anuncian en la plantilla pero `Party` no tiene un campo `clasificacion`; `grupo` necesita resolución a `party_group_id`, cuyo formato de entrada (nombre/ID/código) no está definido.
- Criterios pendientes sin issue nuevo: `tax_id` no es único y dos importaciones de la misma identidad generan dos Parties; el flujo manual tampoco aplica deduplicación y no hay política de identidad documentada. El importador no crea settings/PartyAccount por tercero; la resolución existente recurre a defaults de compañía cuando faltan, sin impacto contable adicional reproducido. No se afirman defectos sin resolver esas políticas.
- Cobertura funcional de pruebas: no se encontró un archivo de pruebas dedicado a `CustomerAdapter`; las pruebas relacionadas cubren import batches genéricos y Party ACL/settings, no el mapeo de columnas de este adaptador. No se ejecutó la suite automatizada. La reproducción de #1677 fue una sonda funcional con SQLite en memoria y backend de cache en memoria para activar la ruta condicional Redis; no se editó código productivo.
- Cobertura recalculada del inventario Python de 245 archivos: **25 auditados**, **0 en revisión**, **34 requieren revisión**, **186 pendientes**. En `imports/adapters`: **9/10 auditados**, 1 requiere revisión (`vendor.py`).
- Resumen del componente actual: `customer.py` queda cerrado como archivo; Imports sigue activo. **Siguiente archivo exacto:** `cacao_accounting/imports/adapters/vendor.py`. No cambiar a otro componente antes de terminar Imports.


### Cierre del subcomponente - `cacao_accounting/imports/adapters` (2026-11-01)

- Los **10/10 archivos** del subcomponente están auditados. En `vendor.py` se revalidó el estado del HEAD contra la revisión funcional previa de ambos métodos (`build_document()` y `persist_document()`), sus campos, código secuencial, vínculo `CompanyParty`, ruta manual y alcance por compañía; el archivo no cambió desde esa evidencia.
- La cobertura del subcomponente incluye: adaptador base y protección de fórmulas; estados/concurrencia del extracto bancario; forecast; catálogo de cuentas; clientes/proveedores; diarios; adaptador legado de órdenes de compra sin referencia productiva encontrada; y los 11 tipos de documento transaccional. Se cotejaron modelos, validación/persistencia de `ImportService`, `DocumentFlow`, ledger y posting de inventario/AP/AR según el tipo.
- Issues confirmados o ampliados en esta pasada: #547 (moneda inactiva/no existente con tasa explícita), #1063 (padre de cuenta inválido y vacío), #1668 (dominios de clasificación/tipo), #1672 (cuenta inexistente en diario), #1673 (prevalidación multimoneda), #1674 (lote vencido), #1675 (lote opcional de espacios), #1676 (moneda vacía de cuenta) y #1677 (Smart Select cacheado tras importar maestros). #1346 cubre pérdida de filas de maestros agrupadas por `document_ref`; #1052 cubre valores requeridos whitespace-only. Otros problemas de importación bancaria/transaccional referenciados en checkpoints anteriores siguen vinculados a sus issues existentes y no se duplicaron.
- Riesgos/criterios en espera, sin issue nuevo: criterios de permisos de `imports/routes.py`; semántica de grupo/clasificación de clientes y proveedores (#1048/#1476/#1383 repetidos en el tracker); identidad/deduplicación por tax ID; elección de campos `tipo` y `account_type` entre cargadores; booleanos de grupo no documentados; estados/monedas de maestros donde el contrato no está fijado; y límites de motor cuando solo se reprodujo SQLite. No se modificó código productivo ni se ejecutaron suites automatizadas.
- Reconciliación actual del inventario Python de 245 archivos: **26 auditados**, **0 en revisión**, **33 requieren revisión**, **186 pendientes**. `imports/adapters` queda completo; el módulo Imports aún no, pues `imports/routes.py` y otros criterios/artefactos propios del flujo requieren revisión.
- **Siguiente archivo exacto del componente Imports:** `cacao_accounting/imports/routes.py` (`NC/18` en el manifiesto previo). Retomar su triaje de permisos/estado de lote y los contratos de rutas; conservar los hallazgos ya verificados y continuar sin volver a probarlos salvo cambio de código.


### Cierre del componente - `cacao_accounting/imports` (2026-11-01)

- Todos los archivos Python del paquete y subpaquetes están auditados: `imports/` 4/4, `adapters/` 10/10, `readers/` 6/6, `services/` 2/2 y `utils/` 3/3. En `routes.py` se revalidó contra HEAD el inventario previo de 18 funciones y se revisaron los casos pendientes de ruta, carga, permisos, libro/serie y descargas; HEAD no cambió desde la revisión previa.
- Hallazgo nuevo #1678 (`bug`, `needs-work`, severidad baja): dos descargas concurrentes de la misma plantilla CSV en locales distintos escriben al mismo path y ambas pueden devolver los encabezados del último locale. QA reprodujo el cruce con la función de ruta real; no vio contenido mezclado. XLSX/ODS comparten el patrón, sin reproducción concurrente adicional.
- Hallazgos de rutas/flujo ya contrastados y no duplicados: #1032 (cancelación sobrescrita al finalizar), #1395 (cancelar lote fuera del estado procesando), #1200 (archivo solo con encabezados aparece completado), #1528 (marca `started_at` bloquea ejecutar/revalidar), #1531 (plantilla transaccional incluye columna `serie` prohibida), #1631 (fallback rechaza CSV válido de una columna), #1648 (CSRF bloquea POST sin token), #1661 (tipo de registro no soportado deja detalle 500), #1662 (fallback acepta TSV que el lector no parsea) y #1659 (serie anterior/no compatible persiste hasta fallar al ejecutar). La selección de libro descartada posteriormente por el servicio contable sigue en #1163.
- Criterios pendientes, sin issue nuevo: la combinación `access=False` con permiso `consultar` permite lecturas dentro de la compañía asignada; validar requiere además `editar`; el selector de serie depende del permiso `accounting`; son decisiones de política ACL aún sin confirmar. No se encontró acceso a otra compañía. La ruta valida la compañía del libro, mientras la validación del tipo/compañía de serie está cubierta por #1659. El límite de carga global es 16 MiB; los paths de carga usan nombres saneados. No se halló una ruta de borrado de lotes ni un bypass adicional de estado fuera de issues existentes.
- Cobertura del inventario Python de 245 archivos: **27 auditados**, **0 en revisión**, **32 requieren revisión**, **186 pendientes**. El paquete Imports queda completo para esta auditoría; su módulo se resume con los issues anteriores y #547/#1063/#1319/#1667/#1668/#1672-#1678, sin reabrir causas ya cubiertas.
- No se modificó código productivo ni se ejecutaron pruebas automatizadas; #1678 se verificó con dos solicitudes concurrentes coordinadas. Issues abiertos por esta revisión: #1676 (moneda vacía), #1677 (cache de maestros) y #1678 (locale de plantilla). Issues existentes #1063 y #1668 se ampliaron; no se abrió duplicado para grupos de cliente/proveedor (#1048/#1476/#1383) ni para series (#1659).
- **Siguiente componente de la secuencia por dependencias:** `cacao_accounting/database`. **Siguiente archivo exacto:** `cacao_accounting/database/__init__.py` (estado `requiere revision` en el manifiesto). Antes de continuar se mantendrá Imports cerrado y se conservará el orden de capas establecido arriba.


### En revisión - `cacao_accounting/database/__init__.py` (2026-11-01)

- HEAD verificado: `c62c3604646f65ce37100412edf2432a8f74cef6`, rama `estabilizacion`; worktree solo tiene `.codex/` ajeno y `AUDIT_PROGRESS.md` de auditoría.
- Inventario AST exacto: 49 funciones/métodos y aproximadamente 120 clases ORM. Archivo de más de 6.1k líneas; el inventario incluye propiedades, listeners y validadores declarativos. Una revisión previa parcial cubrió identidad/hash/eventos de `BankTransaction` y confirmó la falta de unicidad de `identity_key`, ya anotada en #1319, además de FKs sin aislamiento de compañía en cuentas bancarias (#1665); no se contará esa lectura como cobertura completa hasta revalidar símbolos.
- Cobertura funcional del archivo: **49/49 funciones/métodos AST revisados**. A las 42 ya descritas se suman `_item_has_usage`, `_warehouse_has_usage`, `_party_has_usage` y los cuatro listeners de protección de uso de `Item`, `Warehouse` y `Party` (7). Se cotejaron sus tablas con las referencias FK y las rutas de modificación/borrado; la evidencia append-only histórica sigue bloqueando cambiar UOM después de líneas canceladas/revertidas, y las referencias de configuración no incluidas en los detectores quedan protegidas por FK `RESTRICT`. La ruta de edición captura el `ValueError` del listener y hace rollback. La cobertura de funciones ya está completa, pero el archivo sigue **en revisión**: falta revisar contratos de modelo pendientes y criterios ya anotados.
- Hallazgo confirmado agregado al issue existente #1579: las altas reales de `Unit` y `Project` en SQLite aceptan un padre de otra compañía; recalcular el padre también reescribe el `path` del hijo ajeno. El hijo queda fuera de ambos árboles de listado por el filtrado de compañía y la búsqueda de raíces. QA reprodujo ambas altas; APIs de jerarquía actuales abortan 404 al detectar el vínculo. Se agregó evidencia, referencias precisas e impacto al issue existente en [comentario de #1579](https://github.com/cacao-accounting/cacao-accounting/issues/1579#issuecomment-6564428076), sin crear duplicado. Severidad media, con `Refs: 757`.
- Hallazgo confirmado #1682: duplicados `(user_id, role_id)` en `RolesUser` por carrera en asignación, sin índice único; SQLite permitió dos llamadas sincronizadas, y `tiene_rol()`/`User.is_portal_customer` lanzan `MultipleResultsFound`. QA independiente reprodujo carrera y efecto; no hay issue equivalente. `needs-work`, severidad media, `Refs: 757`.
- Revalidación de #925: una reactivación ORM con entero `0` evita el guard de transición monotónica, y SQLite persiste `is_cancelled=False` para una fila previamente cancelada. Reproducido independientemente por QA. No se halló ruta de usuario actual que pase ese entero; es un bypass verificable del guard de tipo. El helper afectado también protege `GLEntry`, `StockLedgerEntry`, `ARAPLedgerEntry` y `ARAPLedgerBookEntry`. Se añadió la evidencia al [comentario de #925](https://github.com/cacao-accounting/cacao-accounting/issues/925#issuecomment-6564503309), se reabrió el issue y se retiró `fixed`; ahora está `verified`/`needs-work`, severidad media. Sin issue duplicado.
- Hallazgos confirmados previos: #1679, con Redis configurado pero fuera de servicio, `User.token` propaga `redis.exceptions.ConnectionError`; login y autenticación API fallan. QA independiente reprodujo la ruta. #1680, `DocBase.version` no se incrementa ni se compara y los formularios de documento permiten sobrescribir cambios obsoletos; QA reprodujo el lost update técnico y confirmó el CRUD de PurchaseOrder. Ambos `needs-work`, severidad media y con `Refs: 757`.
- Hallazgos actuales: #1683 confirma columnas muertas heredadas en `BaseTransaccion` (`canceled`, `canceled_by`, `applied_by`, `sequential`, `sequential_id`) y mutabilidad redundante de las marcas `canceled*`; los consumidores canónicos usan `cancelled_*`/`applied`. #1684 registra aliases/synonyms de compatibilidad sin consumidores productivos y el único caller restante de `Modulos`, migrable a `Modules`. En #1319 se agregó evidencia: `BankTransaction.identity_key` se escribe pero ningún flujo productivo lo lee; los importadores deduplican directamente por campos, además de la carrera ya cubierta.
- Pendientes de validación/criterio: `CacaoConfig.key` permite duplicados aunque lectores usan `scalar_one_or_none()` y escritores hacen read-then-insert; el probe confirmó `MultipleResultsFound` tras duplicar, falta verificar carrera concurrente y rutas alcanzables. #1681 sigue `needs-review`: `Unit.code`, `Project.code` y `Book.code` tienen unicidad global además de `(entity, code)`, pero el alcance esperado del código no está definido. Los periodos contables se pueden superponer en SQLite; falta cotejar validaciones de alta/edición. El índice parcial de `PurchaseReconciliation` compila como índice único completo en MySQL; QA confirmó DDL y reuso en el servicio con SQLite, pero falta criterio sobre reabrir/reconciliar una factura ya cancelada.
- Riesgo evaluado sin issue por ahora: `_validate_bank_transaction_amounts()` acepta `Decimal('Infinity')` por ORM, pero ambos caminos actuales de importación (`BankStatementAdapter` y `statement_service`) rechazan importes no finitos antes de crear el modelo; no se encontró otra construcción productiva de `BankTransaction`.
- `DocumentRelation.__init__` convierte `None` explícito de IDs de línea a `""`, consistente con columnas no-null y unicidad para relaciones a nivel documento; creación normal de flujo y relaciones de reversa usan ese constructor. No se halló defecto en este método.
- `_bank_transaction_identity()` y `_set_bank_transaction_identity()` se revalidaron: hash determinista, ambos listeners activos en insert/update; solo asignan la columna indexada. No hay lectores productivos y la deduplicación usa campos directos; evidencia agregada a #1319 en [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1319#issuecomment-6564601759). La escala bancaria y el posible hash distinto tras normalización quedan cubiertos por #1087/#1663, sin duplicado.
- `ComprobanteContable.total`, `capitalized_by_ref` y `capitalization_origin_ref` se verificaron. `total` se consume por introspección en aprobación; las dos propiedades de capitalización se consumen en `contabilidad/templates/contabilidad/journal.html`, por lo que no son código muerto.
- Los detectores `_item_has_usage`, `_warehouse_has_usage` y `_party_has_usage` se ejecutan desde listeners ORM activos. Los dos primeros se apoyan en claves globalmente únicas (`Item.code`, `Warehouse.code`); restricciones FK `RESTRICT` bloquean referencias de configuración omitidas por los detectores. El guard de UOM preserva historial append-only aun para documentos cancelados. El servicio de inventario tiene una prevalidación más estrecha que filtra anulados/reversiones; el guard ORM rechaza esos casos y la ruta captura la excepción y revierte la sesión, así que no se reprodujo una escritura parcial.
- Contratos fiscales `Tax`, `TaxTemplate`, `TaxTemplateItem`, `TaxRule`, `DocumentTaxSummary` y `DocumentTaxLine` cotejados con servicios, rutas, motor y guardas: #1685 confirma que `Tax.tax_type` inválido se guarda y se convierte silenciosamente a porcentaje; #1686 registra las dos rutas de cálculo y solicita consolidar al motor canónico; #1274/#1436 ya cubren defectos concretos del motor de reglas. La columna `Tax.applies_to` se escribe y muestra pero no se aplica al calcular plantillas; queda ligada a la eliminación de esa ruta en #1686. Snapshots fiscales de documentos tienen guardas polimórficas y solo se reemplazan mientras el documento permanece editable.
- Las dos vistas POST de plantillas fiscales también carecen de token CSRF; se agregó evidencia de '/settings/tax-templates' y '/settings/tax-templates/<id>/items' al issue existente #1648, junto con el hallazgo previo de la segunda ruta; no se duplicó.
- Cobertura de funciones completa (49/49), pendiente el contrato de modelos: permanecen por cerrar las reglas de `CacaoConfig`, periodos superpuestos, unicidad de códigos por compañía, diferencias de DDL en `PurchaseReconciliation` MySQL y modelos contables/flujo-auditoría/acceso/aprobación. **Siguiente bloque exacto sin cobertura completa:** `ComprobanteContable`, `RecurringJournalTemplate`/`RecurringJournalApplication`, `ComprobanteContableDetalle` y `GLEntry`, alrededor de la línea 4007; luego dimensiones y mapeos de cuentas. Los grupos ya revisados no se repetirán salvo contradicción o cambio de HEAD. No pasar a `database/helpers.py` hasta cerrar `database/__init__.py`.

### Continuación de contratos de modelo — `database/__init__.py` (2026-11-01)

- Se comenzó el bloque contable pendiente en el mismo archivo. `ComprobanteContable.total` y sus referencias de capitalización ya estaban verificadas como usados. Los cuatro constructores productivos de `GLEntry` encontrados están en `posting_service.py` y `exchange_revaluation_service.py`; todos asignan `ledger_id` y `account_id`, y el constructor central exige cuenta y un único lado positivo. Falta cerrar si esos contratos críticos también deben estar forzados por el esquema DB y revisar sus condiciones de compañía/moneda.
- `GLEntry` tiene checks de monto positivo exactamente en un lado y FK compuesta para centro de costo; unidades/proyectos y cuenta usan FKs simples. `GLEntryDimension` no tiene writer/reader en producción; `rg` solo encuentra la declaración. Evidencia añadida al issue agrupador #1658: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6564678706). No se duplican #1337/#1359/#1368; #770 está cerrado con aceptación limitada a administración/discovery.
- Las plantillas recurrentes se contrastaron con `recurring_journal_service.py`, cierre de período y posting de diarios. La frecuencia guardada no interviene en selección/programación; ya está cubierta por #1149 y #1493 (causa duplicada), y la validación que acepta líneas con ambos importes está reproducida en #1492. No se abrieron issues duplicados. Los campos `RecurringJournalItem.reference_type`, `reference_name`, `reference1`, `reference2`, `is_advance` y `RecurringJournalApplication.error_message` no participan en formulario, escritura ni lectura productiva; se dejó evidencia en [#1658](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6567580349). El campo `RecurringJournalTemplate.ledger_id` es FK a `Book.id` y el escritor guarda UUID, pero quedan comparaciones por código marcadas como compatibilidad; se registró en [#1658](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6564686583), vinculado al antecedente cerrado #836, conforme al criterio vigente de pre-alpha sin legacy.
- Se revisaron los campos de `ItemAccount`, `PartyAccount` y preferencias `CompanyParty`: el centro de costo del mapeo de artículo sí se escribe/valida y se usa en presupuestos; las cuentas AR/AP de `PartyAccount` pasan por validación de compañía. Las preferencias de cuentas/moneda/banco de `CompanyParty` sin consumidor ya están cubiertas por #1299, agrupado bajo #1658; no se abre otro issue.
- Cobertura de funciones de `database/__init__.py`: **49/49**, archivo aún **en revisión** por contratos de modelo incompletos. **Siguiente bloque exacto:** `CompanyDefaultAccount` (línea ~4476), validando escritor y consumidores por compañía; después `CashFlowAccountMapping`. Más adelante siguen los contratos de `ComprobanteContableDetalle`/`GLEntry`, los grupos de conciliación/cierre, workflow/auditoría y acceso/aprobación, y criterios pendientes de `CacaoConfig`, períodos, unicidad y DDL MySQL. `database/helpers.py` permanece pendiente; no cambiar de archivo/componente hasta cerrar este.

### Continuación del archivo - `cacao_accounting/database/__init__.py` (2026-11-01)

- Reconciliación al retomar: rama `estabilizacion`, HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; sin cambios productivos. `.codex/` permanece ajeno. Inventario total: 245 archivos; 27 auditados, 1 en revisión, 31 requieren revisión y 186 pendientes. Por tanto, quedan 218 archivos sin auditoría completa. `database/__init__.py` conserva el estado en revisión y no aumenta el conteo de terminados.
- Se reconstruyó la cobertura posterior al checkpoint anterior a partir de las verificaciones de esta misma sesión: `CompanyDefaultAccount`, `CashFlowAccountMapping`, asignaciones de recepción/factura, revaluación, cierre mensual, cola de correo, presupuesto, OTP y recuperación. Los hallazgos confirmados siguen trazados a #1689–#1696, #1319 y #1658; no se volvieron a abrir duplicados. Las funciones AST permanecen en 49/49, pero faltan criterios/contratos de modelo para completar el archivo.
- Contratos de `CashForecast`/`CashForecastEntry` contrastados con rutas, servicio y adaptador de importación. Ambos modelos tienen escritores y consumidores activos; las relaciones compañía-año fiscal se validan en las rutas/servicio. Periodicidad inválida ya está reproducida y cubierta por #1258 (también relacionada con #1083); importación de montos no positivos y entrada no finita ya tienen #1050/#1196/#950/#1500. No se abrió duplicado.
- `ApprovalMatrix`, `ApprovalRequest` y `ApprovalAction` se contrastaron con `ApprovalEngine`, revisión de control interno y configuración administrativa. El motor bloquea por documento; control interno llama con bloqueos de las filas de operación/configuración asociadas. No se encontró borrado productivo de solicitudes/acciones. La entrada administrativa limita `approval_level >= 1` solo en HTML: el servidor acepta `0`, que colisiona con el sentinel de “sin nivel” y deja el documento sin solicitud (permanece borrador). Se mantiene pendiente de reproducción por ruta antes de abrir issue; no se afirma como hallazgo confirmado.
- `BalanceConfirmation` e invitaciones se contrastaron con creación, envío, reenvío, cancelación y endpoints públicos. Confirmación/invitación guardan hashes de token/código; correo se normaliza al crear; la respuesta compite mediante UPDATE condicional. Se agregó evidencia de una transición terminal reescrita por expiración al issue existente #1110: visita GET después del vencimiento cambia `confirmed`/`disputed` a `expired`, porque `_mark_expired()` corre antes de comprobar estados terminales y no los excluye. Comentario: [#1110](https://github.com/cacao-accounting/cacao-accounting/issues/1110#issuecomment-6567759536). No se abrió duplicado.
- Posible pérdida concurrente de incrementos de `BalanceConfirmationInvitation.failed_attempts` quedó como pendiente de validación de concurrencia en PostgreSQL: el endpoint público lee/incrementa/escribe en tres pasos y no tiene limiter local ni UPDATE atómico; no se abrió issue sin reproducción independiente. La expiración terminal anterior sí tiene evidencia determinista de flujo de código.
- Estos bloques no contienen campos muertos nuevos verificados; los hallazgos de dead code previos permanecen agrupados en #1658, #1683 y #1684. No se tocó código productivo ni se ejecutaron pruebas automatizadas.
- Próximo símbolo exacto en el mismo archivo: `CacaoConfig` (línea 167), para cerrar la duplicidad de `key`, identificar todas las rutas de lectura/escritura y reproducir o descartar la carrera de alta. Después resolver período superpuesto, unicidad de códigos por compañía y DDL MySQL de `PurchaseReconciliation`. No pasar a `database/helpers.py` hasta cerrar el archivo.

### Bloque revisado - `CacaoConfig` en `database/__init__.py` (2026-11-01)

- `CacaoConfig.key` solo está indexada, no es única. Se cotejaron los escritores activos en `setup/repository.py`, `messaging/email.py`, `printing/settings.py`, `compras/purchase_sourcing_service.py` y `admin/session_security_service.py`; varios hacen read-then-insert sin lock sobre la clave ausente. Se buscó en migraciones y no se encontró una restricción única adicional.
- Reproducción funcional SQLite en memoria: dos filas con la misma `key` persisten; una consulta `scalar_one_or_none()` a esa clave lanza `MultipleResultsFound`. El lector activo `ApprovalEngine.is_enabled()` usa exactamente ese patrón. El interleaving de dos inserts en PostgreSQL se sustenta por el read-then-insert sin clave única ni lock; no se ejecutó un servidor PostgreSQL.
- Hallazgo nuevo #1697 (`bug`, `needs-work`, severidad media, `audit`, `Refs: 757`): [Evita duplicar claves de configuración](https://github.com/cacao-accounting/cacao-accounting/issues/1697). Se contrastaron duplicados por búsqueda; no había issue equivalente. No se modificó código.
- El bloque `CacaoConfig` queda revisado; no cambia el estado del archivo ni el conteo global. **Siguiente símbolo exacto:** `Unit` (línea 508), luego `Book` y `AccountingPeriod`, para cerrar unicidad por compañía y períodos superpuestos sin asumir alcance de negocio no documentado.

### Revisión de `Unit`, `Book` y `AccountingPeriod` - mismo archivo (2026-11-01)

- Se cotejaron restricciones con referencias y consumidores. `Book.code`, `Unit.code` y `Project.code` se usan como claves foráneas simples en libros, GL e inventario; la unicidad global es necesaria para el esquema actual. Se añadió esta evidencia al criterio no resuelto #1681: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1681#issuecomment-6567809967). Sigue pendiente la política de producto si se pretende admitir códigos repetidos por compañía, lo que requeriría rediseñar las referencias.
- `BusinessUnit` no se clasifica como muerto: tiene consumidores activos en API de jerarquía, Smart Select y presupuestos; se confirmó mediante búsqueda de referencias.
- Hallazgos de períodos se contrastaron con rutas de alta/edición, modelo, validación central, asignación de contexto GL y pruebas existentes leídas. #1154 ya cubre que editar un período cerrado evita la reapertura auditada. #1155 cubre rangos contables solapados; no se abrió duplicado.
- Reproducción funcional SQLite en memoria para el solapamiento: un período habilitado/cerrado amplio (2026-01-01–2026-12-31) insertado antes de un período habilitado/abierto (2026-06-01–2026-08-31). La fecha 2026-07-15 pasa `validate_accounting_period()` porque esta elige el inicio más reciente, pero `posting_service._find_period_ids()` sin `order_by` asigna el período amplio cerrado. Se añadió evidencia reproducible a la causa consolidada #1656: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1656#issuecomment-6567803593). Impacto: una publicación autorizada puede quedar vinculada a un `AccountingPeriod` cerrado. No se modificó código.
- Los casos anteriores de períodos/años sellados, rangos superpuestos, edición de períodos cerrados y posting sin período ya tienen issues (#1024, #1154, #1155, #1158/#1287, #1172, enlazados a #1656); no se abrieron duplicados. El inventario global sigue en 27 auditados, 1 en revisión, 31 requieren revisión y 186 pendientes.
- Próxima verificación exacta: completar el contrato de `AccountingPeriod` frente al rango del `FiscalYear` asignado y el flujo de creación/edición; después volver al orden físico del archivo para terminar `Unit`/`Book`/`Project` y continuar con el DDL MySQL de `PurchaseReconciliation`. El archivo activo continúa sin cerrar.

### Revisión de dimensiones por compañía - extensión del modelo GL (2026-11-01)

- Se siguió el recorrido de `Unit`/`Project` desde líneas de diario hasta `GLEntry`. `JournalEntryAdapter` conserva ambos valores; `_validate_balanced_lines()` acepta una línea con códigos existentes de otra compañía porque `_validate_journal_line()` no consulta ownership; `_line_model()` y `_comprobante_entry_params()` los propagan y `_create_gl_entry()` persiste códigos con FKs simples globales.
- Reproducción funcional SQLite en memoria con FKs activas: cuenta de `COA`, `Unit` y `Project` de `COB`. El validador real aceptó el diario; se insertó GL con compañía COA y dimensiones propiedad de COB (`journal_line_validation=accepted; persisted_gl_company=COA; unit_owner=COB; project_owner=COB`). La sonda utilizó funciones de validación/construcción reales, no ruta HTTP completa.
- Evidencia añadida como extensión del mismo límite de ownership a #1665, sin duplicar issue: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1665#issuecomment-6567843104). Hallazgo relacionado con #1579 (propiedad de padres jerárquicos), pero causa de posting/diario distinta; mantener las trazas separadas.
- Verificación de límites de período: se reprodujo también que un período puede referenciar un año fiscal distinto del que cubren sus fechas; `validate_accounting_period()` lo permite y `_find_period_ids()` devuelve su `fiscal_year_id`. Evidencia agregada a #1656: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1656#issuecomment-6567817988).
- Ninguna de estas verificaciones cierra `database/__init__.py`; funciones AST 49/49, contrato de modelos todavía parcial. Próximo bloque: volver al inventario de constraints de `Unit`/`Book`/`Project` y completar las decisiones de período por FY, y luego inspeccionar `PurchaseReconciliation` MySQL según #1656. Conteo total permanece 27/245 auditados (1 en revisión, 31 requieren revisión, 186 pendientes).

### Checkpoint de continuación y validación paralela (2026-11-01)

- Se inició una segunda ronda paralela, read-only y dentro del componente activo `cacao_accounting/database/__init__.py`: QA revisó por separado `PurchaseReconciliation`/DDL y `StockLedgerEntry`; no se permitió que los agentes editaran código o esta bitácora.
- Reconciliación de cobertura al reanudar: `database/__init__.py` sigue **en revisión**; su inventario de funciones AST permanece en 49/49, pero aún falta cerrar contratos/modelos. El conteo de archivos completos no cambia: 27/245 completos, 1 en revisión, 31 requieren revisión y 186 pendientes; 218 todavía no están completos. No se convierte lectura o revisión parcial en archivo terminado.
- `PurchaseReconciliation` y `PurchaseReconciliationItem` se contrastaron con `purchase_reconciliation_service.py`, cancelación en `posting_service.py`, guardas de `internal_control_service.py` y rutas de factura/recepción. El índice parcial para facturas activas compila con predicado en SQLite/PostgreSQL, pero como UNIQUE global en MySQL. QA no confirmó un defecto del flujo normal: la factura anulada queda en `docstatus=2` y la corrección normal genera un documento con ID nuevo; el posting actual no usa `idempotency_key`. Una llamada directa del servicio a una factura anulada es un límite interno no validado por `docstatus`, pero su resultado permitiría conciliar una factura anulada y no se abrió issue sin criterio funcional. Se anotó #1076 como antecedente adyacente de colisión de claves, no equivalente.
- Reproducción propia SQLite en memoria con `MODO_ESCRITORIO=True`: después de insertar una `PurchaseReconciliation`, actualizar `matched_amount` por ORM y borrar la fila por ORM ambos commits fueron aceptados. La misma causa afecta `PurchaseReconciliationItem`: `_enabled()` en `internal_control_service.py:174-185` desactiva las guardas transversales en Desktop; no hay listener de modelo alternativo. Se agregó evidencia a #923 y se reabrió con `needs-work`: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/923#issuecomment-6567887123). No se creó duplicado.
- QA reprodujo de forma independiente una mutación bulk ORM de `StockLedgerEntry.qty_change` en Desktop (`1 -> 77`). Reproducción propia SQLite en memoria confirmó el mismo resultado: `session.execute(update(StockLedgerEntry)...)` persiste el cambio porque el listener mapper no intercepta bulk y la guarda global se desactiva en Desktop. No se encontró callsite productivo actual de ese bulk; es un bypass verificable de la garantía de persistencia. Evidencia agregada al issue general existente #759 y este se reabrió como `verified`/`needs-work`: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/759#issuecomment-6567899148). #925 conserva el caso separado de reactivación `is_cancelled` con entero `0`; no se abrió otro issue.
- No se modificó código productivo ni se ejecutó la suite automatizada. Las verificaciones anteriores fueron reproducciones manuales SQLite en memoria; no cubren PostgreSQL/MySQL servidores reales. El worktree conserva `.codex/` de terceros y `AUDIT_PROGRESS.md` como artefacto de esta auditoría.
- **Próximo punto exacto:** continuar en `cacao_accounting/database/__init__.py`, clase `PurchaseReconciliationItem` (línea aproximada 5035), terminar sus invariantes y luego los contratos restantes posteriores hasta poder cerrar el archivo. No pasar a `database/helpers.py` antes de cerrar este componente.

### Extensión QA del bloque de inventario y fecha de anulación (2026-11-01)

- QA independiente cerró la lectura de `StockLedgerEntry` en `database/__init__.py:1513-1617`. Además del bulk ORM probado por mí, confirmó que tanto `Session.execute(update(StockLedgerEntry)...)` como `Connection.execute(update(StockLedgerEntry.__table__)...)` reescriben `qty_change` en SQLite/Desktop. El mapper guard solo cubre cambios de instancia; los guards transversales se desactivan en modo Desktop. No encontró un callsite productivo de esas mutaciones bulk, así que el impacto verificado es el bypass del invariante de persistencia, no una ruta actual de usuario. Se agregó al issue existente #759 y se reabrió; no se creó issue duplicado. La cobertura de regresión que falta debe comprobar ORM bulk y Core `UPDATE`/`DELETE` en SQLite/Desktop y preservar posting normal.
- Otros límites revisados por QA: `StockLedgerEntry.company` y `warehouse` tienen FKs independientes, sin constraint compuesto; no se confirmó incumplimiento en rutas productivas porque posting/recepción validan pertenencia. Los writers normales bloquean el documento y verifican movimientos previos, sin duplicado concurrente confirmado. La valoración por libro sigue en el issue existente #1244. No se abrió issue para estos puntos.
- **Pendiente de reproducir en PostgreSQL:** `_validate_stock_reversal_capacity()` lee el saldo derivado sin lock y luego `_create_stock_reversal()` actualiza el bin con lock; una salida concurrente entre ambas fases podría producir stock negativo. No se confirmó interleaving ni se creó issue; #112/#636 son adyacentes, pero no se confirmó que cubran este caso.
- **Fecha de anulación:** `cancellation_service._resolve_effective_dates()` rechaza solo fechas anteriores, las rutas aceptan `cancellation_date` de formulario y la reversa SLE usa esa fecha. Esto contradice `AGENTS.md:46`, que exige misma fecha y período. En SQLite se reprodujo un original del 1 de enero con anulación el 10: una consulta del ledger al día 5 omite el saldo de 5 unidades porque `exclude_cancelled_stock_entries()` excluye el original por `is_cancelled` y aún no incluye la reversa. Como los reportes operativos pueden limitar cortes a períodos completos, el impacto de esa consulta intermedia depende del servicio invocado; la violación de la regla de fecha sí es directa. Se agregó evidencia al issue existente #761 y se reabrió como `verified`/`needs-work`, sin issue duplicado: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/761#issuecomment-6567920067). El cierre anterior de #761 aceptaba fecha posterior dentro del período; prevalece el criterio actual explícito de `AGENTS.md`.
- En `ledger_queries.py:43-45` hay una rama `cancelled_sibling` descrita como compatibilidad histórica; parece redundante con la cancelación atómica y los flags actuales, pero el archivo pertenece a un componente posterior. Se conserva como candidato de dead code pendiente de auditoría y contraste integral, no como defecto confirmado todavía.
- El único conteo verificable sigue 27/245 archivos completos, 1 en revisión, 31 requieren revisión y 186 pendientes. No se cambió código productivo ni se ejecutó suite automatizada. **Siguiente símbolo:** terminar `PurchaseReconciliationItem` y seguir cerrando `database/__init__.py` antes de abrir cualquier otro archivo de este módulo.

### Revisión de `PurchaseReconciliationItem` (2026-11-01)

- Se cotejó el esquema de `PurchaseReconciliationItem` con sus únicos consumidores productivos en `purchase_reconciliation_service.py`: los agregadores consultan `matched_qty`/`matched_amount` y estado; el replay usa `matched_qty`/`price_difference`; cancelación solo transiciona `status`. La construcción normal distribuye cantidades entre líneas fuente bajo locks de filas de OC/recepción y conserva claves de artículo, UOM, bodega y factura.
- Hallazgo de replay validado en SQLite en memoria: para cantidad 4 y diferencia unitaria 2, el cálculo inicial devuelve diferencia extendida 8, pero `_result_from_existing_reconciliation()` suma el snapshot unitario y devuelve 2. El único caller productivo actual llama `reconcile_purchase_invoice()` sin clave; no encontré ruta actual que provea `idempotency_key`. Evidencia añadida a #1076, sin abrir duplicado: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1076#issuecomment-6567937554). La rama de replay, además de ese defecto, sigue sin consumidor actual bajo el flujo de producto; queda trazada para integrar o retirar.
- Referencias Python no mostraron lectores productivos para los snapshots `purchase_invoice_item_id`, `item_code`, `warehouse`, `uom`, `received_qty`, `invoiced_qty`, `received_amount` e `invoiced_amount`; solo los constructores los escriben. Se agregó este grupo al inventario existente de código/superficie muerta #1658: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6567945401). Esos campos no se consideran eliminables automáticamente: queda criterio de conectar a una vista/validación de evidencia o retirarlos.
- Las reglas de ownership compañía/proveedor/moneda y límites de cantidades se aplican en el servicio antes de insertar; las filas de origen se bloquean antes de calcular saldos pendientes. No se confirmó otro defecto de la ruta normal en esta clase. Los límites Desktop append-only y fecha de anulación permanecen en #923/#759/#761, con checkpoints anteriores.
- `PurchaseReconciliationItem` queda revisada a nivel de columnas, escritores, lectores y transiciones. El archivo `database/__init__.py` sigue en revisión por clases posteriores y contratos globales; el conteo permanece 27/245 completos, 1 en revisión, 31 requieren revisión y 186 pendientes.
- Recuento mecánico del manifiesto tras las actualizaciones: 245 filas de archivo; estados exactos en la tabla: 27 `auditado`, 1 `en revisión`, 31 `requiere revisión`, 186 `pendiente`. La diferencia con 20% se mantiene: cobertura completa verificable = 27/245 (≈11%), no se suman parciales.
- **Siguiente bloque en curso:** `PurchaseReceiptReturnAllocation`, `PurchaseInvoiceReceiptAllocation` y `PurchaseCreditNoteAllocation` (clases alrededor de 5094-5197), con revisión paralela read-only asignada; después `ExchangeRevaluation`/`ExchangeRevaluationItem`. No pasar a otro componente antes de cerrar `database/__init__.py`.

### Revisión de allocations S2P (2026-11-01, QA paralelo)

- QA cerró la revisión read-only de `PurchaseReceiptReturnAllocation`, `PurchaseInvoiceReceiptAllocation` y `PurchaseCreditNoteAllocation` (clases desde línea ~5094), contrastando FKs/constraints, escritores/lectores, hooks de cancelación, ownership compañía/proveedor y transiciones de flujo. No se encontró ruta productiva actual que reactive allocations canceladas; los escritores insertan `active` y cleanup solo transiciona `active -> cancelled`. El guard transversal no fuerza terminalidad del estado, pero no se abrió issue sin caller actual.
- **Sin issue duplicado:** #1689 cubre la carrera de sobreasignación de una línea de factura entre recepciones distintas; el lock actual cubre la recepción individual, no serializa la cantidad compartida de factura. No se reprodujo contra PostgreSQL.
- **Sin issue duplicado:** #1220 cubre notas físicas cuya validación pone límite de importe por línea fuente pero no prorratea al importe de la cantidad devuelta; el criterio de descuento/impuestos/FX sigue sin resolver en ese issue.
- **Sin issue duplicado:** #1221 cubre cancelar una devolución física mientras una nota sigue aprobada y conserva AP/GL, aunque cleanup cancele sus allocation rows.
- **Sin issue duplicado:** #1222 cubre cancelar una nota comercial sin vínculo a OC/recepción y dejar activa la asignación que limita futuras notas.
- #1134 (cortes históricos de GRNI) y #1218 (landed cost en devoluciones) son fallos de lectores/valuación relacionados, de causa distinta. No se reportaron duplicados.
- Los escritores validan compañía/proveedor y cantidades base en las rutas actuales; no se confirmó mezcla multiempresa. `PurchaseInvoiceReceiptAllocation.purchase_order_item_id` no tiene escritor/lector; los snapshots de moneda/tasa/importes base y `allocation_type` en las tres tablas tampoco se consumen. La evidencia quedó agregada a #1658: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6567982512), sin issues separados.
- Límite de esta ronda: los cuatro issues existentes se verificaron por recorrido estático, sin reproducción runtime extremo a extremo ni concurrencia contra PostgreSQL/MySQL. Los modelos quedan cubiertos dentro de `database/__init__.py`; el archivo continúa en revisión. **Siguiente bloque exacto:** `ExchangeRevaluation` y `ExchangeRevaluationItem` (~5198-5287), revisados en paralelo.

### Revisión paralela de modelos de colaboración, correo, adjuntos, auditoría y cierre (2026-11-01)

- Se revisaron `Comment`, `CommentMention`, `Assignment`, `Workflow`, `WorkflowState`, `WorkflowTransition`, `WorkflowInstance` y `WorkflowActionLog` (`database/__init__.py:5328-5455`). La búsqueda exacta en fuentes productivas, templates y JS no halló consumidores; el comentario del issue #1658 ya documenta este grupo como esquema ORM muerto. El comentario funcional de documentos escribe `AuditTrail` mediante `log_comment()`, no la tabla `Comment`. No se abrieron duplicados.
- `EmailQueue` (`:5558-5571`) tiene escritores en la API de notificación y lector/reintento en administración/messaging. Reintentar filas `sent` y serializar retries ya están documentados en #1693; #1018/#1360 describen la misma repetición desde estado enviado. No se creó duplicado. El estado del servicio de email se auditará en el componente correspondiente.
- `DocumentTask` (`:5573-5612`) tiene consumidores en `collaboration_service.py`, API, bandeja y panel de documento; `company` se deriva del documento y la creación verifica permiso del asignado sobre el mismo módulo/compañía. No se observó un hallazgo nuevo en el contrato del modelo; la lógica completa del servicio queda para su propio archivo.
- Revisión QA de `File`, `FileAttachment` y `AuditLog` (`:5463-5557`): `File.blob_reference` ya está bajo #1658; la ruta auxiliar `validate_upload`/`store_attachment` no tiene llamadores y solo su cleanup interno, mientras `upload_attachment()` es el flujo activo; se agregó evidencia a #1658 en [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568033217). `AuditLog` conserva escritores productivos, sin lector de aplicación hallado; no se marcó la tabla como muerta. QA reprodujo que un `UPDATE` bulk puede reescribir `after_data` en SQLite/Desktop; se añadió a la causa append-only #759 en [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/759#issuecomment-6568032983), sin duplicar el caso SLE. La revisión de aislamiento de imágenes sigue en #1376 `needs-review`.
- Revisión QA de `PeriodCloseRun` y `PeriodCloseCheck` (`:5288-5322`): los endpoints de capitalización y plantillas recurrentes mutan el estado incluso en una corrida `closed`; si no hay trabajo, pasan a `in_progress` o `open`. `reopen_accounting_period()` busca `run_status='closed'`, por lo que falla aunque el período permanezca cerrado. Se creó #1698 con rutas de reproducción y limitación explícita: recorrido estático, sin POST runtime ni prueba PostgreSQL. #732 cubre causas distintas; #1692/#1153 cubren carrera de creación, no este reset.
- Revisión QA de `ExchangeRevaluation`/`ExchangeRevaluationItem` (`:5198-5286`): `ExchangeRevaluationService.void()` está bloqueado por `_guard_flush` en Cloud al cambiar metadatos de void no incluidos en `MUTABLE_STATE`; se añadió reproducción app+SQLite a #1313 ([comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1313#issuecomment-6568024257)), relacionado pero distinto del bypass de journal genérico descrito originalmente. La tasa anterior `nearest-before` usada por una corrida del 31 no es reconocida por las guardas de edición que comparan fechas exactas; se reabrió #546, se quitó `needs-review`, se marcó `verified`/`needs-work`/`severity-medium`, con reproducción QA en SQLite ([comentario](https://github.com/cacao-accounting/cacao-accounting/issues/546#issuecomment-6568040830)). No se probó HTTP/PG para este segundo hallazgo. `target_account_id` sin consumidores ya está en #1658; `MONETARY_ACCOUNT_TYPES` ya está en #1314. Las carreras de void y run están en #1159/#1160; sin reproducción PostgreSQL.
- Los contadores de archivo no cambian: `database/__init__.py` permanece **en revisión** (49/49 funciones AST, contratos de modelo incompletos); total **27/245 auditados**, **1 en revisión**, **31 requieren revisión** y **186 pendientes**. No se modificó código productivo ni se ejecutó suite automatizada.
- **Siguiente bloque exacto:** modelos `Budget`/`BudgetLine` y clases contiguas de presupuesto dentro de `database/__init__.py`, asignados a QA read-only; yo sigo con el grafo de modelos restante en este mismo archivo. No pasar a otro archivo antes de cerrar este componente.

### Cierre QA del bloque `Budget` en `database/__init__.py` (2026-11-01)

- QA revisó `Budget`, `BudgetLine`, `BudgetImport` y `BudgetImportLine` (`database/__init__.py:5613-5747`), trazando escritores de servicio/importación, lectores de totales y reportes, estados y validación compañía/libro/FY/moneda. No se modificó código.
- Hallazgo confirmado #1699 (`bug`, `needs-work`, severidad media): `uq_budget_line` abarca dos dimensiones nullable y no garantiza unicidad para `NULL`; una vista previa de `BudgetImport` se valida con una foto de combinaciones existentes, pero `insert_lines()` no vuelve a validar contra las filas actuales. QA reprodujo dos INSERT idénticos con dimensiones nulas aceptados por SQLite. Los acumuladores y `validate_transaction()` suman ambas filas, permitiendo inflar el límite presupuestario. No hubo carrera PostgreSQL. Issue: https://github.com/cacao-accounting/cacao-accounting/issues/1699.
- Sin duplicado: #1488 (lote sin vínculo al presupuesto autorizado), #1490 (persistencia de compañía/libro/FY en edición), #1491 (lote vacío) y #1656 (períodos/FY) son causas distintas.
- Campos de escritura sin lector productivo: `Budget.approved_by/approved_at/closed_by/closed_at`, `BudgetLine.description`, `BudgetImportLine.description`, `BudgetImport.filename/rows_read/rows_inserted/errors_count`. Modelos activos, no tablas muertas; evidencia agregada al pase #1658 en https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568070631.
- Hallazgo cruzado de `CashForecast.periodicity` ya está cubierto y reproducido por #1258; no se abre duplicado. El grupo `CashForecast` aún requiere completar las invariantes de sus modelos y queda dentro de este mismo archivo.
- Inventario global inalterado: **27/245 auditados**, **1 en revisión**, **31 requieren revisión**, **186 pendientes**. `database/__init__.py` sigue `en revisión` (49/49 funciones AST; contratos/modelos pendientes). Próximo bloque contiguo en orden: `UserCompanyAccess`, `RecognizedDevice`, `OtpVerification`, `PasswordResetToken` (`:5747-5835`), con QA paralelo; después continuar los modelos restantes de esta declaración antes de cerrar el archivo.

### Revisión de contrato de `CashForecast` / `CashForecastEntry` (2026-11-01)

- Se cotejaron columnas `database/__init__.py:6002-6049` con escritores de `bancos/cash_forecast.py`, el servicio de matriz y el adaptador de importación. `company` y FY se validan al crear/cargar; `periodicity`, versión, estado, monto, moneda y fecha alimentan listados, cálculo y reportes; `CashForecastEntry.notes` sí se muestra en los templates.
- Hallazgos existentes, sin duplicar: #1258 cubre `periodicity` fuera de `weekly/monthly` que se guarda y cae en períodos semanales; ya contiene reproducción SQLite. #1501 cubre `estimated_date` fuera del FY, persistida pero ignorada por `_compute_manual_projections()`; ya contiene reproducción de handler. #950 cubre import/manual `Infinity` en `CashForecastEntry.amount`, con evidencia de persistencia SQLite; no se abrió issue.
- Metadatos sin lector: `approved_by/approved_at` solo se escriben al aprobar; `closed_by/closed_at` están declarados y la ruta de cierre no los escribe. Se agregaron al pase de limpieza #1658 en https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568082110. No se marca como muerto el modelo ni sus campos de negocio activos.
- Cobertura limitada a contrato de modelos y callers/lectores críticos dentro del bloque del archivo de base de datos; no reemplaza la auditoría completa de `bancos/cash_forecast.py`, importador y servicio cuando toque su componente. No se ejecutó otra reproducción, no se modificó código.
- El archivo sigue en revisión: **27/245** archivos completos, 1 en revisión, 31 requieren revisión, 186 pendientes. Próximos subbloques paralelos en el mismo archivo: seguridad (`UserCompanyAccess`, dispositivo, OTP, reset) y, después, approval; el bloque de Budget ya cerró.

### Revisión QA de modelos de alcance y autenticación (2026-11-01)

- Revisados `UserCompanyAccess`, `RecognizedDevice`, `OtpVerification` y `PasswordResetToken` (`database/__init__.py:5747-5835`) con rutas de administración, permisos, login OTP y recuperación. Se rastrearon unicidad/FKs, expiración, consumo, revocación y lectores por usuario.
- #1700 confirma que `usuario_companias()` borra todas las asignaciones previas antes de guardar; `_guard_sensitive_delete()` rechaza el borrado de `UserCompanyAccess` en Cloud. Reproducción propia con app/SQLite (`MODO_ESCRITORIO=False`, controles activos): commit falla con `ValueError`; en primera asignación sin filas anteriores, esa rama no borra y sí puede agregar.
- #1696 recibió reproducción adicional: código OTP incorrecto retorna `False`; el contador sube dentro de la sesión, pero `database.session.remove()` revierte el `flush` y el contador vuelve a cero. La ruta `verify_otp()` no hace commit en rama fallida. #1000 y #1696 cubren la misma carrera de consumo bajo concurrencia; se mantuvo un único issue, ampliando #1696 para el caso secuencial.
- Candidatos sin issue nuevo: la rama de reset para usuario inactivo marca `consumed` y retorna `None`, pero la ruta no hace commit; no validé si la reactivación posterior debe revivir el token. La generación concurrente de OTP/reset puede dejar varios activos por check-then-insert; no hubo repro PostgreSQL. Los bearer tokens (OTP y reset) se almacenan en claro; se registra como hardening/threat-model, no bug confirmado.
- `auth/device_verification.py::listar_dispositivos()` y `revocar_dispositivo()` son helpers sin callers; admin usa implementaciones de `admin/session_security_service.py`. Se agregó evidencia al dead-code umbrella #1658: https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568107876. Los modelos de dispositivo/token tienen consumidores activos.
- Issues relacionados sin duplicar: #1329 (tareas visibles tras revocación), #1028/#1444 (email con capitalización), #990 (GET no consume token; el código actual lo conserva), #1696/#1000 (OTP concurrente). Sin pruebas PG ni request HTTP completo para las conclusiones estáticas; las dos reproducciones locales mencionadas sí se ejecutaron en app SQLite.
- **Próximos bloques paralelos dentro del mismo archivo:** `BalanceConfirmation`/`BalanceConfirmationInvitation` (`:6149+`) y `ApprovalMatrix`/`ApprovalRequest`/`ApprovalAction` (`:6053-6148`). El inventario de archivos no cambia: 27/245 completos; `database/__init__.py` sigue en revisión con 49/49 funciones AST, pero modelos posteriores aún pendientes.

### Revisión QA de `ApprovalMatrix`, `ApprovalRequest`, `ApprovalAction` (2026-11-01)

- Bloque revisado en `database/__init__.py:6053-6148`; consumidores en `approval_engine.py`, administración, auditoría de aprobaciones e informe de control interno. `ApprovalAction` está protegido como evidencia; `ApprovalRequest` protege procedencia y transiciones; `ApprovalMatrix` es configuración sensible.
- Confirmados por issues vigentes, sin duplicar: #1565 (reglas solapadas pueden bajar el nivel requerido), #1566 (rechazo graba regla ajena al monto), #1017 (acción POST inválida tratada como rechazo) y #1553/#1593 (misma causa de solicitudes rechazadas + pendientes que disparan `MultipleResultsFound`; no abrir un tercero). La creación bloquea documento; approve bloquea solicitud. Carrera approve-vs-reject queda pendiente de repro PostgreSQL.
- Nuevo hallazgo #1701: matriz configurada como **Cualquiera** (`role_id/user_id` nulos) cuenta para `required_level` pero no aparece en `_get_user_rules()` para usuarios no administradores. Reproducción propia SQLite: `required_level=1`, `eligible_rules_for_non_admin=0`; no se ejecutó endpoint HTTP. Solicitud puede quedarse pendiente hasta intervención admin.
- No se marca como dead code el snapshot de `ApprovalAction` (regla/límite/monto/nivel): aunque el reporte actual solo lee algunas columnas, el conjunto preserva evidencia y #1566 depende de ellas. La moneda de `min_amount/max_amount` sigue sin criterio explícito; no se elevó a issue.
- Inventario global: 27/245 archivos completos; `database/__init__.py` continúa en revisión con 49/49 funciones AST y contrato de modelos restante. Próximos QA: `AuditTrail` y `BalanceConfirmation`/`BalanceConfirmationInvitation`, aún dentro del mismo archivo.

### Cierre de bloques paralelos de auditoría y confirmación de saldos (2026-11-01)

- QA read-only completó `AuditTrail` (`database/__init__.py:5518-5555`) y `BalanceConfirmation`/`BalanceConfirmationInvitation` (`:6149-6212`), siguiendo escritores, lectores, estados y rutas públicas/internas. El checkpoint permanece dentro del único archivo activo `database/__init__.py`; no se abrió otro componente.
- Reproducción propia SQLite/Desktop: un `UPDATE` ORM cambió y confirmó `AuditTrail.after_json` (`{"qty":1}` → `{"qty":77}`). Se amplió la misma causa append-only ya cubierta por `DELETE` en #1002; comentario [6568181265](https://github.com/cacao-accounting/cacao-accounting/issues/1002#issuecomment-6568181265). No se halló un caller de producto para ese UPDATE directo.
- El recorrido de `crear_confirmacion_form()` muestra que GET carga `Party` y expone el correo principal y correos de contactos activos sin validar acceso del usuario a una compañía del tercero (`contabilidad/balance_confirmation_bp.py:122-132,181-203`). Se agregó evidencia al issue de alcance ACL existente #1649, sin duplicado: [comentario 6568181795](https://github.com/cacao-accounting/cacao-accounting/issues/1649#issuecomment-6568181795).
- El GET público de enlace de confirmación puede reemplazar `confirmed`/`disputed` por `expired` después del vencimiento; reproducción de `_mark_expired()` en SQLite ya registrada en #1702. No se invocó el endpoint HTTP completo. La carrera de `failed_attempts` requiere reproducción PostgreSQL y queda pendiente, sin issue.
- Candidatos de código muerto del mismo modelo: `BalanceConfirmation.document_type`, timestamps no leídos y `BalanceConfirmationInvitation.expires_at`/`verified_at` sin consumidores encontrados; se mantienen para el pase existente #1658. `query_tools.audit.log_query_tool_event()` sin callers productivos y `audit_chain._CHAIN_FIELDS` sin referencias se agregaron a #1658: [comentario 6568181546](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568181546). No se clasifican snapshots retenidos como muertos solo por falta de vista.
- El límite de nombres/User-Agent frente a columnas `String(100/512)` puede fallar en PostgreSQL, pero falta una reproducción en Tier 1; permanece pendiente de validación. La posible colisión del número visible `CONF-{id[:8]}` está bajo revisión de QA antes de decidir si abrir issue.
- Estado verificable sin cambio: 27/245 archivos completos, 1 en revisión, 31 requieren revisión y 186 pendientes; 218 no están completos. `database/__init__.py` tiene 49/49 funciones AST revisadas, pero aún falta reconciliar el inventario contractual residual y sus listeners finales antes de cambiar al siguiente archivo. No se modificó código productivo ni se ejecutó la suite automatizada.
- **Próximo punto exacto:** reconciliar, en `cacao_accounting/database/__init__.py` al final de `BalanceConfirmationInvitation` y listeners `before_update`/`before_delete`, el inventario de clases ya cubiertas con el manifiesto y cerrar los candidatos verificados/no resueltos. Luego se decidirá el cierre del archivo; `database/helpers.py` permanece después de ese checkpoint.

### Reconciliación de cobertura real y revisión paralela por bloques (2026-11-01)

- Una comprobación independiente de la bitácora contra las declaraciones de clase detectó que el dato **49/49** solo acredita revisión funcional de funciones/métodos AST, no cobertura contractual del archivo. El archivo declara aproximadamente 120 clases; quedan rangos amplios sin evidencia contractual suficiente. `database/__init__.py` permanece **en revisión**; no se incrementa el total de archivos auditados.
- Se reordenó el trabajo sin cambiar el componente: tres revisiones read-only y no solapadas están cubriendo `database/__init__.py:120-1041` (bases, identidad, entidad/libros, series), `:1042-1773` (terceros e inventario) y `:1784-2996` (documentos de compras/ventas). La revisión principal cubrirá `:2997-4956` (bancos, pagos, AP/AR, flujo documental y GL), y después se reconciliarán los bloques ya anotados desde conciliaciones hasta confirmaciones. Los agentes no editarán código, bitácora ni issues; no se cambiará de archivo antes de completar esta cobertura.
- La colisión de referencia visible se confirmó generando dos ULID consecutivos con el entorno local (`01M6D476VBKD3RKJRQKE7FWC0H` y `01M6D476VBKD3RKJRQKE7FWC0J`): ambos producen `CONF-01M6D476` por `create_balance_confirmation()` (`contabilidad/balance_confirmation.py:479`). `BalanceConfirmation.document_no` solo tiene índice, sin unicidad (`database/__init__.py:6159`). La búsqueda de duplicados no halló issue equivalente; se creó #1703, severidad baja: [issue](https://github.com/cacao-accounting/cacao-accounting/issues/1703).
- Las confirmaciones de saldo y sus invitaciones no tienen guardas UPDATE/DELETE ni auditoría before/after en Desktop/Cloud. Se añadió a #759 como candidato a la clasificación por modelo, dejando explícita la decisión de si snapshot/respuesta externa forman evidencia append-only: [comentario 6568204841](https://github.com/cacao-accounting/cacao-accounting/issues/759#issuecomment-6568204841). Los metadatos sin lectores se añadieron al pase dead-code pre-alpha #1658: [comentario 6568205060](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568205060).
- También se añadieron la reproducción de UPDATE de `AuditTrail` en Desktop a #1002 ([comentario 6568181265](https://github.com/cacao-accounting/cacao-accounting/issues/1002#issuecomment-6568181265)), la divulgación de correos de terceros desde GET a #1649 ([comentario 6568181795](https://github.com/cacao-accounting/cacao-accounting/issues/1649#issuecomment-6568181795)) y los helpers de auditoría sin callers/alias muerto a #1658 ([comentario 6568181546](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568181546)).
- Permanecen pendientes de Tier 1 los límites de correo/nombre/User-Agent mayores que sus columnas `String(150/100/512)` y la concurrencia de `failed_attempts`; se requieren reproducción PostgreSQL antes de elevarlos. No se ejecutó la suite automatizada, no se modificó código productivo y los conteos globales siguen **27/245 auditados**, **1 en revisión**, **31 requieren revisión**, **186 pendientes**.
- **Siguiente archivo exacto no aplicable:** el componente actual aún no está cerrado. El siguiente bloque propio es `cacao_accounting/database/__init__.py::Bank` y modelos posteriores de pagos/AP-AR (`:2997-3695`); las otras revisiones continúan en rangos del mismo archivo.

### Revisión parcial de bancos, caja chica y pagos (2026-11-01)

- Se contrastaron las declaraciones `Bank`, `BankAccount`, `PettyCashAccount`, `PettyCashVoucher`, `PettyCashExpense`, `PettyCashReconciliation`, `PettyCashReplenishment` y `BankAccountNumberingConfig` con los servicios/rutas de bancos. Este bloque propio aún no cierra `PaymentEntry`, referencias de pago ni los subledgers AP/AR posteriores.
- Reproducción app/SQLite de #1088: cambiar `PettyCashAccount.account_id` a una cuenta `petty_cash` USD con `currency=None` conserva la moneda NIO y persiste el par incompatible. La ruta de edición convierte campo ausente/vacío a `None`; se agregó reproducción al issue existente #1088, sin duplicar #1264 (que requiere historia previa): [comentario 6568264839](https://github.com/cacao-accounting/cacao-accounting/issues/1088#issuecomment-6568264839).
- Reproducción SQLite del helper real de numeración: con una fila `BankAccountNumberingConfig(use_external_counter=False, external_counter_id=None)` y contador legacy en `BankAccount.default_external_counter_id`, `_resolve_payment_numbering()` devuelve el contador legacy. Se agregó como ruta alterna/precedencia rota al issue de limpieza pre-alpha #1658: [comentario 6568258460](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568258460). #1645 sigue siendo el problema distinto de CSRF que impide guardar desde la UI.
- Reproducción del flujo real `create_petty_cash_expense()` en SQLite: `Decimal("Infinity")` supera `amount <= 0`, llega al posting y lanza `decimal.InvalidOperation` en `posting_service.py:4380` antes de GL/commit. La ruta captura solo `ValueError`, por lo que no convierte el caso a validación controlada. Se agregó al issue existente de importes no finitos #1469, sin abrir duplicado; comentario [6568282650](https://github.com/cacao-accounting/cacao-accounting/issues/1469#issuecomment-6568282650). La probe separada de Infinity en `_build_payment_from_payload()` falló antes de persistir durante `quantize`; no se reporta como defecto confirmado.
- Issues conocidos contrastados: #1265 (setup elige cuenta inactiva), #1326 (dos fondos predeterminados bajo concurrencia), #1266/#1187/#1268 (doble liquidación/reembolso de vale); no se abrieron duplicados.
- Cobertura de este bloque sigue parcial. **Próximo símbolo exacto propio:** `PaymentEntry` y `PaymentReference` (`database/__init__.py:3278-3370`), y luego `ArApReconciliationPolicy`/`ARAPOpenItem`/ledgers (`:3371-3695`). No cambiar de archivo ni componente.

### Revisión QA de modelos de compras/ventas (1784-2996) (2026-11-01)

- QA revisó las 35 clases del rango: solicitudes/cotizaciones/adjudicaciones y pedidos/recepciones/facturas de compras; solicitudes/cotizaciones/pedidos/entregas/facturas de ventas y líneas relacionadas. Cotejó campos y constraints con escritores, lectores, validadores y flujos de posting. No confirmó campos o clases sin consumidores productivos en ese rango.
- Sin duplicar: #1429/#1481 UOM y adjudicación; #1433 unicidad de factura proveedor; #1435 pérdida de líneas de landed cost en parser; #1224 tipos de origen y moneda en nota de crédito; #1220/#1221/#1222 retornos y limpieza de allocations.
- Dos candidatos de concurrencia se mantienen **pendientes de validación PostgreSQL**, sin issue: submit simultáneo de una SalesOrder puede sumar reserva dos veces porque la verificación de `docstatus` ocurre antes del lock de `StockBin` y no se repite después; recepción/factura concurrentes pueden sobreconsumir cantidades de la línea fuente porque sus validadores leen antes del posting sin lock comparable al de O2C. #1139/#1689 son análogos de capacidad, no duplicados confirmados.
- El bloque `database/__init__.py:1784-2996` tiene revisión contractual QA; esto no cierra el archivo. Conteo global sigue 27/245 completos, 1 en revisión, 31 requieren revisión, 186 pendientes. No se modificó código ni se ejecutaron pruebas en el pase QA.
- **Siguiente foco propio:** completar `PaymentEntry` y `PaymentReference` (`database/__init__.py:3278-3370`), después `ArApReconciliationPolicy`, `ARAPOpenItem` y ambos ledgers (`:3371-3695`).

### Checkpoint de revisión paralela y modelos de pago (2026-11-02)

- Rama `estabilizacion`, HEAD `c62c3604646f65ce37100412edf2432a8f74cef6`; inventario sin cambio: 245 archivos productivos, 27 `auditado`, 1 `en revisión`, 31 `requiere revisión`, 186 `pendiente`. `database/__init__.py` permanece `en revisión`; no se suma al total completo.
- **Bloque QA `database/__init__.py:120-1041` cerrado en lectura contractual estática** (base/identidad/moneda/entidad/libros/períodos/cuentas/dimensiones/series/contadores). No hubo reproducción HTTP ni carreras. Hallazgos para consolidar: (a) rutas de unidad/proyecto/libro/series/contador con permiso de módulo pero sin scope ACL por compañía, solapamiento de causa con #1169; (b) unidades/proyectos pueden enlazar padres de otra entidad y propagar su jerarquía, relacionado pero no cubierto por el cierre API de #793; (c) falta unicidad/serialización al insertar `LedgerMappingRule`, pendiente de interleaving; (d) dos sesiones pueden hacer retroceder `ExternalCounter.last_used`, pendiente de concurrencia; (e) `Currency.default` permite segundo default; (f) varios candidatos de dead code/campos sin lector (detallados por el agente) aún requieren consolidar evidencia y decidir agrupación con #1658. No abrir nuevos issues de carreras sin repro Tier 1.
- **Bloque propio `PaymentEntry`/`PaymentReference` (`:3278-3368`) revisado a nivel de columnas, constraints, escritores, lectores, estados, moneda/compañía/libros y flujo de cancelación.** PaymentEntry está activo; `is_advance` tiene lector funcional en la confirmación de saldo pero el escritor bancario no lo asigna. Se creó #1704 y se actualizó a `severity-medium`: el flujo desde orden lleva `advance_mode=True`, pero `_create_payment_entry()` omite el flag y el default persiste `False`; sonda manual app+SQLite de la función real devolvió `is_advance=False` con saldo NIO 150. Duplicados consultados: #975, #1460 y #1197 cubren causas distintas.
- **Integridad append-only de referencia de pago:** en Desktop (`MODO_ESCRITORIO=True`) una sonda app+SQLite con pago posteado (`docstatus=1`, `is_advance=True`) insertó una `PaymentReference`, luego cambió la misma fila de `allocated_amount=10.0000` a `20.0000`; el commit fue aceptado porque `_enabled()` desactiva las guardas en Desktop. Repetida en Cloud (`MODO_ESCRITORIO=False`, `INTERNAL_CONTROLS_ENFORCE=True`), la modificación sí se bloqueó. El gap documentado en #759 es la falta de enforcement Desktop frente a la política append-only explícita, no un bypass Cloud de UPDATE. Evidencia y correcciones: [6568333446](https://github.com/cacao-accounting/cacao-accounting/issues/759#issuecomment-6568333446), [6568342274](https://github.com/cacao-accounting/cacao-accounting/issues/759#issuecomment-6568342274), [aclaración Cloud/Desktop](https://github.com/cacao-accounting/cacao-accounting/issues/759#issuecomment-6568363514). No se ensayó borrado.
- **Superficie de `PaymentReference` sin lectores:** la búsqueda de constructores, queries, serializadores, reportes e impresión no encontró consumidores productivos para `reference_date`, `payment_currency`, `payment_exchange_rate`, `base_allocated_amount`, `base_payment_amount`, `exchange_rate` y `notes`, aunque los constructores los asignan. Se agregaron al inventario pre-alpha #1658: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568336554). No se marca el modelo completo como muerto.
- Sin cambios productivos ni suite automatizada; las sondas fueron manuales y sobre SQLite en memoria. Mantener sin cambio los estados globales hasta terminar el contrato completo de este archivo.
- **Siguiente bloque exacto en paralelo:** `ArApReconciliationPolicy`, `ARAPOpenItem`, `ARAPLedgerEntry`, `ARAPLedgerBookEntry` (`:3371-3695`), agente read-only activo. Segundo bloque no solapado: modelos posteriores `:3696-4956`, en otra revisión read-only. Yo continuaré en ese orden dentro del mismo `database/__init__.py` y reconciliaré hallazgos antes de cambiar de archivo.

### Verificación funcional adicional de `is_advance` y aclaración Desktop/Cloud (2026-11-02)

- La omisión de `PaymentEntry.is_advance` tiene un efecto operativo además de la etiqueta de confirmación de saldos: las asignaciones posteriores de un anticipo posteado se guardan como nueva `PaymentReference`, pero la guarda solo admite la nueva línea si el padre tiene `is_advance=True` (`internal_control_service.py:466-494`). El flujo `/payment/new` desde orden envía `advance_mode=True`; `_create_payment_entry()` no lo asigna al modelo.
- Reproducción manual app+SQLite con `MODO_ESCRITORIO=False` e `INTERNAL_CONTROLS_ENFORCE=True`: invocar `_create_payment_reference_and_relation()` sobre un pago posteado que quedó `is_advance=False` fue rechazado en `flush()` con `ValueError` de documento posteado inmutable. Se agregó evidencia funcional a #1704: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1704#issuecomment-6568363280). El issue ya refleja severidad media por el bloqueo de aplicación posterior del anticipo.
- Aclaración de evidencia de `PaymentReference`: la sonda de UPDATE con padre `docstatus=1,is_advance=True` que se aceptó corría en `MODO_ESCRITORIO=True`, donde `_enabled()` desactiva las guardas. Al repetir en Cloud (`MODO_ESCRITORIO=False`, `INTERNAL_CONTROLS_ENFORCE=True`), la modificación de referencia existente sí se bloqueó. El gap documentado bajo #759 es por falta de enforcement append-only en Desktop según política explícita; no se afirma bypass de UPDATE Cloud. Comentario de corrección: [6568363514](https://github.com/cacao-accounting/cacao-accounting/issues/759#issuecomment-6568363514).
- #1705 documenta el vínculo cross-company de padres de unidad/proyecto encontrado por revisión estática de `Unit`/`Project` y rutas; #793 solo cubre la API de lectura/serialización de jerarquía. Se agregó a #1169 el alcance ACL restante de maestros contables, incluyendo libros, series y contadores: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1169#issuecomment-6568350008).


### Cierre del bloque de modelos AR/AP (`database/__init__.py:3371-3693`) (2026-11-02)

- QA terminó lectura contractual de `ArApReconciliationPolicy`, `ARAPOpenItem`, `ARAPLedgerEntry`/`document_balance()` y `ARAPLedgerBookEntry`; siguió escritores/lectores en el servicio AR/AP, allocations, conciliación GL, diarios y posting. El caché `ARAPOpenItem` es derivado/mutable por diseño; los movimientos y importes por libro son evidencia activa, con guardas UPDATE/DELETE. Writers revisados usan libros activos de la compañía; el endpoint de policy valida ACL. No se confirmó escritura cross-company.
- **Reversión de diario pierde identidad de línea económica:** la serialización de `duplicate_journal_as_reversal_draft()` no conserva `economic_line_id`; `_line_model()` no lo restaura y el subledger usa el ID nuevo de la línea como fallback (`journal_service.py:486-496,1002-1039,1107-1137`; `arap_ledger_service.py:1439-1452`). Se añadió como causa raíz adicional a #1107, sin duplicado: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1107#issuecomment-6568370687). Evidencia estática, falta repro de flujo HTTP/SQLite.
- Issues coincidentes verificados en código sin duplicar: #1145 (carrera de aplicaciones concurrentes, requiere PostgreSQL), #1140 (pago borrador sobreconsume al postear), #1305/#1103 (cancelación reabre cache de items), #1545 (tasa histórica vs fecha posterior; criterio contable pendiente), #759 (guardas append-only de entradas/valuaciones). No se abre issue por carrera sin reproducción Tier 1 ni por la política FX sin criterio.
- Candidatos de campos sin lectores en `ARAPLedgerEntry`/`ARAPLedgerBookEntry`: `fiscal_year_id`, `accounting_period_id`, ambos `is_cancelled`, `account_id`, `account_code` y `gl_entry_id` (este último se escribe en algunas aperturas, no se encontró lectura). Añadidos al pase dead-code pre-alpha #1658: [comentario](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6568375380). No se clasificaron como tablas muertas.
- El comentario #1107 cubre evidencia estática, no repro dinámica. La carrera #1145 queda en espera de PostgreSQL. El bloque modelo AR/AP sí está cerrado por QA; el archivo global `database/__init__.py` sigue `en revisión` porque quedan rangos posteriores y se debe reconciliar el inventario contractual.
- **Siguiente bloque exacto:** `database/__init__.py:3696-4956`, revisión read-only paralela en progreso. Después de integrarlo se avanzará de forma contigua al siguiente rango restante del mismo archivo; no cambiar de archivo todavía.

