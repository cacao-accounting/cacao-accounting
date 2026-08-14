# SESSIONS — Bitácora de Decisiones de Diseño

> Este archivo documenta decisiones de diseño, arquitectura e invariantes contables que no deben romperse.
> Para detalles de implementación por sesión, consultar el historial de git.

## 2026-08-14 — Refactors SonarCloud sobre origin/main

### Petición y base

Se actualizó `origin/main` y se dejó el trabajo sobre el checkout limpio
`b3d375707706ea1f35679828ad9728b7d65b4635`. El stash de la rama anterior se
conservó sin restaurarlo. SonarCloud reportó 57 issues abiertos: 38
`python:S3776`, 12 `python:S3358`, 4 `python:S5655`, y un issue de cada regla
JavaScript `S2004`, `S3358` y `S3776`.

### Implementación

- `0cef598e`: se eliminaron condicionales ternarios anidados en reportes y
  constructores de pagos mediante resolución explícita de importes/eventos.
- `08ef4777`: se aplanó la sincronización de líneas del formulario
  transaccional y se eliminó el ternario anidado de campos bloqueados.
- `38bc54a2`: se extrajo la resolución de cuentas de anticipo y textos de
  posting de pagos.
- `0869cb77`: se aplanó la selección de tipos de documento origen en los
  formularios de ventas y compras.
- `2ce8ece8`: se hicieron explícitos los caminos de aborto y la ausencia de
  reglas fiscales para que Mypy valide el flujo completo.
- `e1963fae`: se aisló el parseo de componentes capitalizables y la
  re-clasificación de facturas two-way posteriores a la recepción.
- `0e841c0f`: se separó la autorización del comparativo de compras de la
  selección de líneas.
- `caf20dda`: se separaron las reglas de especificación de pagos.
- `87dd1079`: se dividió la agregación del reporte de concentración por
  dimensión.
- `a7cd1f7f`: se separaron los handlers de cancelación del motor de
  aprobaciones.
- `65190a26`: se separó la resolución de montos de pagos y entradas GL en
  conciliación bancaria.
- `6c4e63fb`: se aisló la conversión multimoneda de líneas GL del constructor
  de entradas contables.
- `c188fc40`: se unificaron los parámetros de débito/crédito de comprobantes
  manuales para eliminar ramas duplicadas al construir líneas GL.
- Trabajo actual: `balance_confirmation.py` separa la construcción de partidas
  de facturas y pagos en helpers reutilizables, conservando el corte, las
  anulaciones y los signos de notas de crédito.
- `reportes/services.py` separa la acumulación cronológica y la construcción de
  filas de rotación de inventario, sin alterar el stock inicial ni el cálculo
  de salidas.
- `balance_confirmation.py` aísla la vigencia de cancelaciones y relaciones de
  pago al corte para simplificar el cálculo de saldos no aplicados.
- `reportes/services.py` separa los diagnósticos de transacciones bancarias,
  pagos sin extracto y relaciones huérfanas en builders independientes.
- `balance_confirmation.py` extrae la clasificación y serialización de partidas
  de facturas, y reutiliza la regla de cancelación de pagos al corte.
- `balance_confirmation_bp.py` separa la preparación del formulario y el flujo
  POST de creación para mantener el endpoint enfocado en la presentación.

Black, Ruff y Flake8 pasan en los archivos modificados; los tests focales de
reportes y JavaScript se ejecutan en segundo plano con salida persistida en
`/tmp/sonar-main-reports-test-1786744716.log`.

La validación global actual también pasa pydocstyle y Mypy sobre 212 módulos.
El build y `twine check` pasan usando artefactos aislados en
`/tmp/cacao-build-1786745104`.

---

## 1. Invariantes Contables Fundamentales

### GLEntry como fuente única de verdad
- `GLEntry` es la única fuente de verdad para saldos contables. Bancos, AP, AR e inventario son capas reconciliables contra ella.

### Anulación vs Reversión (append-only)
- **Anulación**: corrige dentro del período original. Solo se permite mientras el período esté abierto. Genera un contrasiento con la misma fecha contable. Los reportes ordinarios ocultan el asiento original y su contrasiento. El usuario puede incluirlos para auditoría.
- **Reversión**: corrige en un período posterior. El comprobante original permanece vivo en el período anterior y un nuevo comprobante invertido permanece vivo en el período actual; ambos deben aparecer en reportes históricos y "as of".
- Las cancelaciones marcan `is_cancelled=True`; nunca se eliminan registros originales.
- `StockLedgerEntry` no posee `is_reversal`. Al cancelar una recepción, el movimiento original se marca cancelado y se agrega un contramovimiento con el mismo `(company, voucher_type, voucher_id)`. Los reportes deben excluir el grupo completo.

### Multi-ledger y multi-moneda
- El sistema es multilibro y multimoneda real: las capas operativas postean atómicamente en todos los libros activos, conservando moneda original, moneda funcional y tasa histórica. Solo Contabilidad puede seleccionar libros.
- Una única tasa del documento se conserva históricamente solo para el libro cuya moneda coincide con la base documental; para cada libro secundario se busca independientemente la tasa entre moneda de transacción y moneda funcional del libro.
- La persistencia GL toma el monto original de la proforma como fuente para convertir cada libro. Las líneas de diferencia cambiaria que existen solo en moneda base preservan su importe en el libro base y se convierten explícitamente para libros secundarios.
- `GLEntryParams` transporta la tasa calculada por línea para distinguir tasas de documento y liquidación en pagos.
- La resolución de moneda usa `Entity.code`, no la clave primaria interna.
- Los importes de revaluación se expresan en moneda base de la entidad; el detalle conserva los importes de todos los libros.

### Impuestos y costos
- Un impuesto normal se contabiliza con la factura y forma parte de cuentas por pagar y del monto liquidado al proveedor, salvo retenciones.
- Un impuesto marcado como `capitalizable_inventory_cost` se reconoce una sola vez en la recepción; la factura conserva el impuesto sin volver a aumentar el valor del inventario.
- Los landed costs pertenecen al flujo de recepción/valoración de inventario; no se incorporan a la factura ni participan en la deduplicación de impuestos.
- La interfaz compartida deriva `affects_inventory` exclusivamente del tratamiento contable y muestra una explicación cuando el impuesto es capitalizable.
- El flujo de factura identifica impuestos capitalizables ya reconocidos en la recepción mediante `source_rule_id` y evita la doble capitalización.
- La identidad de tipo se guarda en el detalle de asignación para que cargos y landed costs no se confundan con impuestos.
- El filtro de no duplicación se limita a eventos de confirmación de factura; los eventos de recepción e importación continúan procesando todos sus cargos capitalizables.

### Numeración e identidad
- `document_no` es irreversible una vez emitido: no se reutiliza, no se renumera, no se libera.
- Las series de numeración usan códigos legibles (`CUSTM-`, `SUPLR-`, `ITEM-`, `ILC`, etc.) via naming-series globales.
- `naming_series` permanece editable; si sigue vacío, se consulta y aplica la serie predeterminada después de una espera diferida, sin sobrescribir una selección manual.
- El reset de secuencia sube a `monthly` cuando el prefijo usa tokens `*MM*`/`*MMM*`.
- Secuencias atómicas con `with_for_update()` en `get_next_sequence_value()`.

### Compañía y moneda en flujos documentales
- En cualquier document flow, compañía y moneda se heredan del origen y no se pueden editar.
- La moneda efectiva usa `transaction_currency` y, cuando está vacía, la moneda configurada en la compañía.

---

## 2. Arquitectura y Patrones de Diseño

### Stack
- Python 3.12+, Flask, Alpine.js, SQLAlchemy, PostgreSQL (prod) / SQLite (dev/tests).
- Multi-stage Docker build: Caddy (HTTP/reverse proxy) → Waitress (WSGI) → Flask.
- CLI: `cacaoctl` (Click-based, identidad propia sin Flask).

### Contabilidad
- Multi-ledger: modelo `Book` con `is_primary`. Cada `GLEntry` lleva `ledger_id`. El posting engine genera entries paralelos por cada libro activo de la compañía.
- Políticas de integridad: 444 FKs con ON DELETE RESTRICT/CASCADE/SET_NULL + ON UPDATE CASCADE definidas en `database/__init__.py`.
- `DocBase.version` para optimistic locking en 15 modelos transaccionales.

### Posting Engine
- `_document_contexts()` crea un `LedgerContext` por libro activo.
- `_assert_entries_balance()` valida balance por libro y por moneda de transacción.
- `_active_books()` resuelve libros activos de la compañía.
- Motor fiscal: `FiscalEngine` (DAG topológico), `SettlementEngine`, `AccountingMapper`.
- Motor landed cost: `LandedCostEngine` con prorrateo por valor/cantidad/peso/volumen.
- Snapshots SHA256 para trazabilidad inmutable de cada cálculo.

### Flujo Documental
- `DOCUMENT_TYPES` en `registry.py`: 19 tipos transaccionales registrados.
- `ALLOWED_FLOWS`: pares de transiciones permitidas entre tipos.
- `create_actions`: acciones de creación dinámicas por tipo documental.
- `DocumentRelation` persiste relaciones entre documentos para trazabilidad.
- Los borradores conservan su `document_no` aunque cambien fecha/compañía/serie.
- Los documentos operativos de inventario sin moneda explícita clonan su valor base en todos los libros. El contexto contable reconoce esos importes como moneda base de la entidad y los convierte a la moneda funcional de cada libro.

### Nombres de variables de flujo documental
- `flow_source_type` (lógico, ej. `purchase_credit_note`).
- `model_type` (físico SQLAlchemy, ej. `purchase_invoice`).
- `document_id` (identificador).
- Las columnas DB no cambian; solo variables Python.
- Módulos: `payment.py` para lógica de pagos/conciliación AR/AP; `service.py` para relaciones documentales y creación de documentos; `registry.py` para tipos/flows permitidos.

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
- Revalorización: `ExchangeRevaluationService` multiledger, cálculo incremental por documento/cuenta.
- Las reservas se calculan en UOM base.
- `StockBin` no elimina reservas al cruzar stock cero o negativo; la reserva se libera solo mediante cancelación/entrega explícita.
- `get_inventory_turnover` reconstruye el stock cronológicamente desde el ledger ordenado por fecha, creación e identificador.

### Maestros
- Códigos legibles: `CUSTM-00001`, `SUPLR-00001`, `ITEM-000001` via naming-series globales.
- `PartyGroup` como catálogo global de tipos de cliente/proveedor.
- Configuración por compañía: `CompanyParty` (AR/AP, tax rule, price list), `PartyAccount`, `ItemAccount`.
- Contactos y direcciones: `Contact`, `Address`, `PartyContact`, `PartyAddress`.
- Bloqueo de eliminación: `before_delete` en SQLAlchemy para Item/Warehouse/Party con historial transaccional.

### Seguridad
- SEC-001 a SEC-011 resueltos (credenciales, JWT, CSRF, CSP, rate limiting, open redirect, etc.).
- `Flask-Limiter` (opcional): modo nube usa Redis, modo escritorio usa `DummyLimiter`.
- JWT tokens en caché (DummyCache o Redis) con timeout 8h, no en atributo volátil de User.
- Audit Trail: servicio centralizado en `audit_trail_service.py` (create/update/submit/cancel/reverse/reject).
- No se confía en `company` enviado por el cliente; siempre se deriva del contexto de autenticación/permiso.

### Reportes
- `financial_report.html`: patrón base para reportes financieros (account-movement, account-summary, trial-balance, balance-sheet, income-statement).
- `operational_report.html`: variante para subledger/kardex/banking/inventory.
- Drill-down: account_code → account-movement, document_no → detalle comprobante.
- Exportación XLSX/CSV con openpyxl. Hoja de filtros separada.
- Cancelados/reversas: `GLEntry.is_cancelled` e `is_reversal` excluidos por defecto; checkbox `show_cancellations` para incluirlos.
- Los agregados por cliente, proveedor y artículo solo consideran facturas posteadas (`docstatus=1`).
- Los importes se suman en moneda base (`base_grand_total`, `base_total`, `base_amount`), con compatibilidad para registros antiguos sin valores base.
- Las devoluciones reducen tanto el importe como la cantidad del agregado correspondiente (signo negativo).
- AR/AP y el cronograma de vencimientos expresan importes en moneda base al factor histórico del documento, conservando la moneda original en cada fila.
- La búsqueda de un comprobante usa únicamente el valor visible generado por la naming series (`GLEntry.document_no`), mediante un campo de texto libre. El usuario no debe buscar por `naming_series_id`, ULID o `voucher_id`.

### CLI
- Click-based con `CacaoGroup` propio. `prog_name="cacaoctl"`.
- Subcomandos: `db init|migrate|reset|clean|seed`, `run`, `serve`, `shell`, `routes`, `version`, `status`, `config`.
- `db init` y `db migrate` son idempotentas.
- `db init` usa `usuarios_creados()` como criterio de base ya lista.

---

## 3. Decisiones de Diseño Clave

1. **Append-only**: Cancelaciones y reversas crean entradas nuevas (con `is_cancelled=True`), nunca eliminan originales.
2. **UniqueConstraints**: `StockLedgerEntry`/`StockValuationLayer` NO deben tener UniqueConstraint en `(voucher_type, voucher_id, item_code, warehouse)` porque multi-line documents, reversiones y landed cost crean duplicados legítimos.
3. **LedgerMappingRule**: modelo existe como schema-only sin lógica de negocio implementada.
4. **AuditLog legacy**: superseded por `AuditTrail` (`audit_trail_service.py`). El antiguo `AuditLog` solo se usa en `document_flow/service.py` para relaciones.
5. **Smart Select**: migración completada al 100% (excepto `<select>` de enum/choice).
6. **Reportes**: `financial_report.html` es el patrón superset; `operational_report.html` es la variante simplificada.
7. **Docker**: Internet → Caddy:80 → Waitress:8080 → Flask. Caddy maneja static + compresión + proxy.
8. **Document Flow naming**: `flow_source_type` (lógico), `model_type` (físico), `document_id` (identificador). DB columns sin cambios, solo variables Python.
9. **Document Flow modules**: `payment.py` para lógica de pagos/conciliación AR/AP; `service.py` para relaciones documentales y creación de documentos; `registry.py` para tipos/flows permitidos.

---

## 4. Controles de Aislamiento y Conciliación

### Fiscal Year Closing
- El cálculo de cierre se ejecuta por cada libro activo; cada línea queda dirigida explícitamente a ese libro. La contrapartida de utilidades acumuladas también se calcula independientemente por libro.
- `create_fiscal_year_closing_voucher` y `submit_journal` bloquean la fila `FiscalYear` con `with_for_update` durante la transacción para prevenir doble cierre concurrente.
- Los flags `is_closing` e `is_fiscal_year_closing` no deben aceptarse desde payload manual sin autorización.
- El cierre exige resultados actuales para comprobantes recurrentes, revaluación cambiaria y capitalización de proyectos.

### Conciliación bancaria
- Los targets `gl_entry` deben usar la cuenta GL de la cuenta bancaria origen/destino.
- Las reversas preservan `bank_account_id` del asiento original.
- El matching de candidatos exige compatibilidad entre moneda de cuenta bancaria, moneda funcional, moneda de pago y `GLEntry.account_currency`.
- La conciliación rechaza fechas anteriores a aplicaciones existentes.
- La conciliación rechaza fechas de liquidación anteriores a aplicaciones previas.
- La cancelación de pagos marca sus `ReconciliationItem` como `cancelled`, conserva el audit trail y deja de consumir saldo conciliable.
- `_payment_order_allocated` suma anticipos solo de `PaymentEntry` aprobados (`docstatus == 1`).
- El adaptador de extractos valida que la cuenta bancaria pertenezca a la compañía del lote.
- Las filas con depósito y retiro simultáneos se rechazan.
- La base de datos tiene un constraint único sobre `BankTransaction` con hash de identidad para evitar duplicados.

### Credit Notes y exposición O2C
- Las notas de crédito reducen el saldo de la factura origen. La relación se persiste como `DocumentRelation`.
- La cancelación revierte el `target_type` real.
- La exposición de crédito incluye el saldo no facturado de órdenes de venta aprobadas.
- `_compute_outstanding_amount` combina referencias modernas y legacy.
- El límite de crédito incluye facturas aprobadas y OV aprobadas, evitando doble conteo.
- `_validate_reversal_of` limita el monto de la NC/DN contra el saldo de la factura origen.

### Matching S2P
- La diferencia de precio del matching 2-way/3-way se acumula como diferencia unitaria por cantidad conciliada.
- `matched_qty` y `matched_amount` se limitan a lo realmente recibido/ordenado.
- La recepción rechaza una orden cuyo proveedor no coincide.
- `supplier_invoice_no` derivado por listener respaldado por constraint único `(supplier_id, supplier_invoice_key)` para impedir duplicados concurrentes.

### Inventario
- Las reservas de órdenes de venta y sus liberaciones se calculan en UOM base.
- La liberación/restauración de una nota de entrega usa la bodega que originó la reserva.
- El posting de movimientos de stock valida en servidor que cada bodega exista, esté activa y pertenezca a la compañía del documento.
- Cancelar una recepción ya consumida puede crear stock negativo; se valida previamente proyectando el efecto de todas las reversas.
- Las transferencias aplican el mismo fallback de costo que las salidas para artículos con `allow_negative_stock=True`.
- `StockEntry` requiere conservar su mensaje específico `no permite stock negativo`.
- `StockEntry` de tipo `stock_adjustment` postea como débito a inventario (positive adjustment).
- Las conciliaciones de inventario recalculan cantidad y valor de ajuste contra el `StockBin` bloqueado durante el posting.
- Las conciliaciones validan el período contable antes del retorno temprano.
- Los formularios rechazan UOM ausentes o conversiones inválidas.
- `get_inventory_valuation` reconstruye al corte a partir de los deltas de `StockValuationLayer`.
- `_valuation_queue` mantiene un déficit de cantidad para compensar capas positivas posteriores.

---

## 5. UI/UX y Flujos Transaccionales

- El formulario transaccional usa el patrón "Voucher Pattern" (Header + Items) unificado para todos los formularios.
- `transaction_form_macros.html` + `transaction-form.js`: componente compartido con smart-select, grid, modal de detalle y bloque fiscal.
- `smart-select.js`: componente Alpine.js con `position: fixed`, filtrado server-side, autocompletado, soporte multi-filtros.
- Smart Select admite selección bloqueada y carga diferida de la serie default.
- Los formularios transaccionales bloquean compañía/moneda cuando tienen `initialSourceType`, sincronizan las líneas Alpine con sus inputs hidden antes del POST y esperan la hidratación AJAX del origen.
- Compras, Ventas e Inventario rechazan persistir documentos sin líneas.
- La carga asíncrona de líneas debe finalizar antes de permitir guardar.
- La interfaz compartida deriva `affects_inventory` exclusivamente del tratamiento contable.
- El menú "Crear" en la barra principal de 12 vistas de detalle reúne acciones de creación dinámicas.
- Las opciones de tipo documental se resuelven desde `DOCUMENT_TYPES` y conservan sus URLs y parámetros de origen.
- La búsqueda de un comprobante usa `GLEntry.document_no` (naming series visible), no IDs internos.
- El árbol de flujo documental se puede consultar en borradores.
- Los asientos de cierre de años anteriores se preservan e incluyen como utilidades retenidas.
- Se excluyen los asientos de cierre del período actual cuando `include_closing=False`.
- La selección de gastos reconoce normalizada `expense`, `gasto` y `gastos`, sin depender de mayúsculas.

---

## 6. Migraciones y Esquema

- `db init` es idempotente (exit 0 si la DB ya existe).
- La fuente única del esquema es `create_all`; `cacaoctl db migrate` es un no-op idempotente.
- `db init` usa `usuarios_creados()` como criterio de base ya lista.
- El reset de secuencia sube a `monthly` cuando el prefijo usa tokens `*MM*`/`*MMM*`.
- Las pruebas de esquema usan `DATABASE_URL` para validar el motor seleccionado.

---

## 7. Importación y Desktop

- Framework tabular: CSV (auto-detección delimitador), XLS, XLSX, ODS.
- Adaptadores por módulo: chart_of_accounts, customer, vendor, journal_entry, purchase_order, transaction_documents.
- Procesamiento asíncrono con daemon threads, rollbacks por documento, `with_for_update()`.
- Modo escritorio bloquea acceso. Generación de plantillas CSV/XLSX/ODS.
- Los importes de importación se normalizan a `Decimal`; se rechazan valores no finitos y filas con depósito y retiro simultáneos.
