# SESSIONS — Continuidad de Desarrollo

> Este archivo documenta decisiones de diseño, arquitectura y hitos clave del proyecto.
> Para detalles de implementación por sesión, consultar el historial de git.

---

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
- Subcomandos: `db init|reset|clean|seed`, `run`, `serve`, `shell`, `routes`, `version`, `status`, `config`.
- Confirmaciones interactivas para operaciones destructivas, `--force` para omitir.
- Alembic importado pero no activado (`init_app` comentado, sin migration files).

---

## Hitos Principales (orden cronológico inverso)

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
