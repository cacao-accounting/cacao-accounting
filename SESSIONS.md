# SESSIONS — Bitácora de Decisiones de Diseño

> Este archivo documenta decisiones de diseño, arquitectura e invariantes contables que no deben romperse.
> Para detalles de implementación por sesión, consultar el historial de git.

## 2026-08-14 — Login independiente del tema global

### Petición

El login debe conservar el fondo claro aunque el selector de tema global esté
guardado en modo oscuro.

### Implementación

Se aumentó la especificidad de la regla clara en `auth/templates/login.html`
para que el selector global `[data-theme="dark"] body` no pueda cambiar el
fondo del login.

## 2026-08-14 — Contraste del dashboard en modo oscuro

### Petición

El dashboard ejecutivo debe conservar legibilidad cuando el selector de tema
esté en modo oscuro.

### Implementación

Los KPI ahora usan una superficie oscura y colores de texto explícitos en modo
oscuro. Chart.js recibe colores adaptativos para leyenda, ejes y cuadrículas,
evitando que sus valores por defecto queden ocultos sobre el fondo oscuro.

## 2026-08-14 — Contraste de vistas de detalle en modo oscuro

### Petición

Las vistas de documentos deben seguir siendo legibles en modo oscuro, en
particular sus acciones, metadatos y línea seleccionada.

### Implementación

Se ajustaron en el auxiliar compartido `cacaoaccounting.css` los botones
`outline-dark`, los textos secundarios, las etiquetas de metadatos y el
resaltado de líneas activas para usar colores legibles sobre superficies
oscuras.

## 2026-08-14 — Hidratar proveedor desde solicitud de cotización

Al crear una cotización de proveedor con `from_rfq`, el formulario ahora
recibe `party` y `party_label` desde la solicitud de cotización origen para
mostrar el proveedor seleccionado automáticamente.

Las solicitudes de compra y de cotización no muestran ni persisten precios;
los importes permanecen disponibles únicamente para cotizaciones de proveedor,
órdenes, recepciones y facturas.

El alta de cotizaciones de proveedor trata la ronda de negociación como
opcional: si el identificador enviado por un formulario obsoleto no existe,
no corresponde al RFQ o ya está cerrado, se descarta y la cotización se guarda
sin ronda asociada.

## 2026-08-14 — Excepción de adjudicación para administración y compras

### Petición

Un administrador o el Gerente de Compras debe poder cerrar una solicitud de
cotización con una sola oferta, siempre que registre una justificación.

### Implementación

La autorización de excepciones del comparativo reconoce tanto la clasificación
`admin` como el rol de Gerente de Compras. La validación del servidor y la
interfaz comparten esta regla; sin justificación, la adjudicación sigue siendo
rechazada y la autorización queda registrada en el comparativo.

El cierre manual independiente también está disponible para esos perfiles. El
cierre crea un registro `closed`, cierra la ronda activa y no habilita otra
acción de colocación de órdenes.

Las órdenes directas desde una cotización de proveedor se permiten como
borrador, pero muestran advertencia si el comparativo sigue abierto. Al crear
la orden se propaga la relación hasta la Solicitud de Compra; cuando la orden
aprobada cubre el 100%, la solicitud puede mostrar `Completado`.

El seed de desarrollo crea o recupera de forma idempotente la bodega
`PRINCIPAL`, asegura su configuración contable y la asigna como bodega
predeterminada a los artículos inventariables que aún no tienen una.

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
- `balance_confirmation_bp.py` centraliza la validación de respuestas públicas
  confirmadas o disputadas antes de persistir el resultado.
- `admin/__init__.py` separa el envío de prueba, persistencia y carga de la
  configuración SMTP del endpoint administrativo.
- `admin/__init__.py` extrae la validación de unicidad y reglas de usuarios de
  portal del endpoint de edición.
- `compras/__init__.py` separa la agrupación de adjudicaciones y la creación de
  líneas relacionadas al generar órdenes de compra.
- `compras/__init__.py` centraliza la resolución del contexto de órdenes de
  compra y conserva explícitamente el identificador del proveedor.
- `modulos/__init__.py` hace idempotente el registro de módulos estándar para
  evitar violaciones de unicidad cuando la inicialización se repite sobre una
  base PostgreSQL existente.
- `inventario/__init__.py` extrae la creación y conversión de una línea de
  movimiento para simplificar el iterador del formulario.
- `inventario/__init__.py` extrae la creación de líneas de conciliación y su
  snapshot de valuación del iterador del formulario.
- `contabilidad/posting.py` encapsula el efecto de cada capa de valuación para
  separar ajustes, compensaciones negativas y consumo de existencias.
- Corrección posterior: las capas con cantidad e importe de valuación ajustan
  su tasa y continúan siendo agregadas/consumidas; no se omite su efecto.
- `auth/roles.py` hace idempotentes la carga de roles predeterminados y las
  asignaciones usuario-rol, evitando colisiones UNIQUE al repetir seeds.
- `approval_engine.py` separa validaciones de ventas y compras de los
  prerrequisitos comunes de envío para reducir ramas en el motor de aprobación.

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

## 2026-08-15 — QA backend y correcciones de flujos de Compras/Configuración

### Peticiones y decisiones

- Se sincronizó `main` con `origin/main` mediante `git fetch` y `git pull --rebase`; se preservó el cambio local no relacionado de `.replit`.
- Se corrigieron los listados de Solicitud de Compra y Solicitud de Cotización para no mostrar la columna `Total`, manteniendo intactos los campos y cálculos de monto internos.
- Se cambió la configuración por compañía de Clientes y Proveedores para que se gestione dentro de la página de detalle mediante un formulario independiente. El formulario permite agregar compañías y editar cuentas, listas de precios, reglas fiscales y opciones operativas sin enviar el formulario general del tercero.
- Se permitió crear N Solicitudes de Cotización desde las mismas cantidades de una Solicitud de Compra. El flujo `purchase_request -> purchase_quotation` es paralelo; los flujos restrictivos posteriores hacia órdenes, recepciones y facturas mantienen el consumo de cantidades.
- Se confirmó que crear una RFQ no modifica el monto de la Solicitud de Compra. Las líneas de RFQ no tienen precio y las relaciones se registran con monto cero; el monto original de la solicitud se conserva.

### Commits semánticos firmados

- `7353503f fix(purchases): hide purchase request totals`
- `5e1842a4 fix(parties): add company settings action`
- `d0235412 fix(purchases): hide quotation request totals`
- `d6d0c784 refactor(admin): consolidate global configuration`
- `c07e84dd fix(parties): edit company settings in detail`
- `27b122b2 fix(document-flow): allow parallel purchase quotations`

### Validación

- `tests/test_party_management.py`: 4 passed.
- `tests/test_transaction_update_elements.py`: 13 passed.
- `tests/test_admin_blueprint.py`: 27 passed.
- `tests/test_e2e_modules.py::test_purchase_quotation_flow_requires_lines_and_inherits_currency`: 1 passed.
- Black pasó para los archivos Python modificados en esta etapa; la ejecución global aún reporta archivos históricos pendientes.
- Mypy y flake8 pasaron en la auditoría global; Ruff mantiene 27 hallazgos existentes principalmente en tests.
- Prettier reporta formato pendiente en plantillas Jinja existentes y no puede parsear `party_company_settings_form.html` por su atributo Alpine `x-data` multilínea; no se ejecutó un reformateo masivo.
- La base `cacaoaccounting.db` fue consultada en modo solo lectura. La solicitud `cacao-PREQ-2026-08-00002` tenía una RFQ activa por 200 unidades y quedó cubierta por la nueva regla de RFQs paralelas.

### Issues GitHub abiertos para revisión

- #409 Consolidación de configuración global.
- #410 Ubicación y comportamiento de anticipos automáticos.
- #411 Columna Total en Solicitudes de Compra.
- #419 Columna Total en Solicitudes de Cotización.
- #412 Configuración por compañía dentro del detalle de Clientes/Proveedores.
- #415 RFQs paralelas desde una Solicitud de Compra.
- #418 Operaciones destructivas de Contabilidad expuestas por GET.
- #413 ACL de administrador del sistema en usuarios, roles y módulos.
- #414 Aislamiento por compañía de `ImportBatch`.
- #416 Fallback MIME permisivo cuando `magic` no está disponible.
- #417 Validación de formas JSON en importación de líneas.

Todos permanecen abiertos para revisión posterior. `.replit` continúa fuera de los commits y conserva el cambio local del usuario.

## 2026-08-15 — Rediseño del comparativo visible en UI

### Petición y decisión de diseño

- Se confirmó que el comparativo no debe iniciar en Solicitudes de Cotización ni usar Cotizaciones de Proveedor.
- Se aplicó un cambio rompiente apropiado para desarrollo: `/buying/request-for-quotation/comparison` ahora lista Órdenes de Compra enviadas.
- El flujo visible es: seleccionar una Orden de Compra base, seleccionar las Órdenes de Compra que participarán como ofertas y crear una comparativa persistida.
- Las ofertas se restringen a órdenes de la misma compañía y que compartan el origen activo en una Solicitud de Compra. La orden base siempre participa.
- Se agregaron `PurchaseOrderComparison` y `PurchaseOrderComparisonOrder`, junto con la migración `20260815_0008_purchase_order_comparisons.py`.
- El comparativo resultante muestra las líneas y tarifas de las órdenes participantes; no crea nuevas órdenes ni consulta `SupplierQuotation`.
- La lógica histórica de rondas de negociación queda fuera de este flujo y continúa documentada en los issues #420 y #421, ambos abiertos.

### Validación

- `tests/test_purchase_sourcing.py`: 7 passed.
- `tests/test_03webactions.py tests/test_purchase_sourcing.py -k 'purchase_order_comparison or purchase_quotation_routes' --slow=True`: 2 passed.
- `tests/test_database_migrations.py`: 3 passed.
- Ruff, Black, `git diff --check` y Prettier para las plantillas nuevas: passed.
- Flake8 y mypy no están disponibles en el entorno actual; se conserva la validación global previa registrada arriba.

### Issues actualizados sin cerrar

- #420 recibió comentario con la UI y persistencia implementadas para comparar Órdenes de Compra.
- #421 recibió comentario indicando que las rondas legacy no se reutilizan en el nuevo comparativo y requieren el rediseño posterior propuesto.

### Despliegue local de desarrollo

- `cacaoctl db migrate` inicialmente reveló que `20260814_0007_balance_confirmation.py` usaba `DEFAULT 0` para un booleano en PostgreSQL. Se corrigió en `b4ed3999 fix(migrations): use portable boolean default` usando `sa.false()`.
- La migración se aplicó correctamente en la base de desarrollo y dejó `alembic_version = 20260815_0008`; las tablas `purchase_order_comparison` y `purchase_order_comparison_order` están disponibles para la UI.
- La corrida completa solicitada terminó con `188 failed, 1528 passed, 9 skipped`; los 188 fallos están concentrados en `tests/test_04database_schema.py` y corresponden a inconsistencias preexistentes del entorno de pruebas, no al comparativo nuevo.


## 2026-08-15 — Inicio del comparativo desde una Solicitud de Compra

### Petición

En `/buying/request-for-quotation/comparison` no era suficientemente visible la
acción para crear un nuevo comparativo de ofertas a partir de una Solicitud de
Compra aprobada.

### Plan e implementación

- Se agregó al registro documental de `purchase_request` la acción
  `Crear Comparativo de Ofertas`, enlazada al selector de órdenes relacionadas
  por Solicitud de Compra.
- El listado de comparativos ahora rotula su acción como `Crear comparativo`
  y mantiene la regla de mostrar únicamente solicitudes con Órdenes de Compra
  aprobadas relacionadas.
- La selección del pedido base y de las ofertas continúa validándose en el
  servidor; no se crean comparativos sin una Orden de Compra participante.
- Se añadió una prueba de regresión para la acción documental y su URL.
- Se añadió la ruta `/comparison/new` y el botón visible `Nueva comparativa` en el encabezado del bloque del listado para que el inicio del flujo sea explícito desde la pantalla solicitada.

## 2026-08-15 — Comparativo desde Cotizaciones de Proveedor

### Petición y decisión

El proceso correcto parte de una Solicitud de Compra abierta. De ella pueden
derivarse N Solicitudes de Cotización y cada una puede producir N Cotizaciones
de Proveedor. El comparativo debe seleccionar las ofertas asociadas a la
Solicitud de Compra original, sin conservar comparativos históricos basados en
Órdenes de Compra.

### Implementación

- La selección reúne ofertas por la cadena activa
  `purchase_request -> purchase_quotation -> supplier_quotation`, incluyendo
  también la relación directa `SupplierQuotation.purchase_quotation_id`.
- Se agregaron `PurchaseRequestComparison` y
  `PurchaseRequestComparisonOffer` para persistir únicamente la nueva
  comparación de ofertas.
- El selector dejó de pedir una Orden de Compra base y ahora permite elegir
  Cotizaciones de Proveedor asociadas a la Solicitud de Compra.
- La vista final compara proveedores, documentos, totales y líneas de las
  ofertas seleccionadas.
- La migración `20260815_0011_purchase_request_comparisons.py` crea el nuevo
  esquema sin backfill de los comparativos anteriores.
- Se confirmó en la base de datos la solicitud `cacao-PREQ-2026-08-00002`
  con las ofertas `cacao-SPQ-2026-08-00003` y `cacao-SPQ-2026-08-00002`.
- Se aplicó la migración en el entorno local y se validó por HTTP la creación
  del comparativo con ambas ofertas participantes.

## 2026-08-15 — Seguimiento de issues nuevos y correcciones de continuidad

### Petición

Se solicitó monitorear nuevos issues abiertos, aplicar los fixes sin cerrar
issues y comentar cada resultado para revisión posterior.

### Issues nuevos revisados

- #422: se aisló el libro contable por compañía tanto en la ruta de creación
  como en el adaptador de comprobantes, incluyendo permiso granular de libro.
  Fix: `35223058`.
- #423: la migración `0009` ahora reconstruye el origen desde relaciones
  activas y la vista conserva un camino explícito para comparativos legacy sin
  Solicitud de Compra reconstruible. Fix: `f6f42726`.
- #424: el comparativo empareja líneas por identidad comercial (artículo, UOM,
  conversión, bodega y descripción), con regresión para líneas invertidas.
  Fix: `f6f42726`.

### Monitoreo y calidad

- La consulta de issues abiertos confirmó #422, #423 y #424 como nuevos; los
  comentarios de fix se publicaron sin cambiar su estado.
- La migración de desarrollo quedó aplicada hasta `20260815_0010`.
- Validaciones focales posteriores: aislamiento de libros y emparejamiento de
  líneas — 3 passed; migraciones — 3 passed; sourcing y rondas — 10 passed;
  importaciones — 13 y 24 passed en sus suites de regresión previas.
- La corrida completa solicitada permanece ejecutándose en segundo plano en
  `/tmp/cacao-backend-qa-20260815-rounds.log`; su resultado final se añadirá
  cronológicamente en una entrada posterior.

## 2026-08-15 — Auditoría funcional y de flujo de negocio

### Petición

Se solicitó revisar el sistema archivo por archivo en busca de errores lógicos
o de flujo de negocio y documentar las observaciones mediante issues de GitHub.

### Alcance y método

- Se inspeccionó el estado real de `main`, incluyendo cambios locales no
  confirmados, `SESSIONS.md`, `ISSUES.md`, los 215 módulos Python, las vistas
  HTML/JS y los workflows de `.github/workflows`.
- Se contrastaron hallazgos contra los issues abiertos existentes para evitar
  duplicados. El seguimiento residual de permisos contables se añadió como
  comentario al issue #418.
- Se ejecutaron los tests focales de flujo documental, sourcing, importación y
  rutas: `102 passed, 5 warnings`.
- La corrida completa se lanzó en segundo plano en
  `/tmp/cacao-audit-full-20260815151534.log`; su resultado debe conservarse
  como evidencia de QA cuando termine.
- El `.venv` está incompleto: `flake8` y `pydocstyle` no están instalados, y
  `black`/`mypy` fallan al importar `pathspec.patterns.gitignore`. Estos son
  fallos del entorno, no veredictos sobre el código.

### Hallazgos confirmados abiertos en GitHub

- #422 — Importación de comprobantes permite seleccionar un libro de otra
  compañía. La ruta de lotes no valida `Book.entity == company_id` y el
  adapter conserva el libro cross-company.
- #423 — La migración `0009` vuelve inaccesibles los comparativos creados bajo
  `0008`: agrega `purchase_request_id` nullable sin backfill, mientras la vista
  actual responde 404 cuando falta.
- #424 — El comparativo empareja líneas repetidas por posición e ignora UOM,
  conversión, bodega y descripción; puede presentar la tarifa de otra línea.
- #425 — La ruta `/request-for-quotation/comparison/new` llama al helper no
  definido `_render_comparativo_ofertas_lista` y falla con `NameError`.
- #426 — Las APIs de líneas sin `target_type` llegan a
  `normalize_doctype(None)` y fallan con `AttributeError`/HTTP 500.

El issue #418 recibió seguimiento con el residuo de autorización: las rutas
de borrado de libros/unidades no verifican permiso de acción y las mutaciones
GET de entidad siguen sin restringirse a escritura/configuración.

### Decisiones de continuidad

Los próximos cambios deben corregir primero el aislamiento compañía-libro de
importaciones y el backfill de comparativos antes de ampliar rondas o UI. Toda
nueva ronda debe conservar una identidad de línea comercial estable y probar
UOM/conversión, y las operaciones de maestros contables deben usar POST,
CSRF, permiso de acción y ACL por compañía/libro.

## 2026-08-15 — Cierre de monitoreo de issues #425 y #426

### Petición

Se confirmó continuar con commits semánticos firmados y monitorear los nuevos
issues abiertos sin cerrarlos.

### Correcciones

- #425 quedó cubierto por `ccaf17f5` y `0e55ebc4`: la ruta Nueva comparativa
  delega a la vista existente y cuenta con prueba HTTP.
- #426 quedó corregido en `b1272635`: `get_source_items` acepta explícitamente
  `target_type=None`, no normaliza `None` y devuelve las líneas completas sin
  consumir cantidades de un destino inexistente.
- El residuo de permisos de #418 quedó corregido en `cc129a8a`; las rutas
  destructivas exigen la acción `eliminar`.

### Validación final

- `tests/test_05document_flow.py`: 31 passed.
- `tests/test_11_contabilidad_coverage.py tests/test_03webactions.py`: 284
  passed.
- Importaciones y sourcing focal: 30 passed; migraciones: 3 passed.
- Corrida completa en `/tmp/cacao-backend-qa-20260815-rounds.log`: 1532
  passed, 9 skipped, 188 failed. Los 188 fallos permanecen concentrados en
  `tests/test_04database_schema.py`, la inconsistencia preexistente del
  entorno documentada en esta bitácora.
- Todos los commits realizados en esta etapa tienen sign-off de
  `williamjmorenor@gmail.com`; todos los issues revisados permanecen abiertos.

## 2026-08-15 — Continuación de auditoría estática de lógica, cálculos y flujo

### Petición

Se indicó no ejecutar pruebas y continuar la revisión de errores de lógica,
cálculo y flujo de negocio.

### Alcance de esta etapa

- Se detuvo la corrida global de pytest iniciada previamente; terminó por
  señal `143` y no se usa como resultado de calidad de esta etapa.
- Se revisaron los cambios locales actuales del flujo de comparativos de
  Solicitud de Compra, RFQ y Cotización de Proveedor, además de los servicios
  de relaciones documentales y cálculo de importes.
- Se preservaron los cambios locales existentes. No se modificó código de
  aplicación ni se ejecutaron más pruebas.

### Hallazgos nuevos documentados

- #427: el comparativo nuevo toma las líneas de la primera cotización como
  universo; omite artículos presentes sólo en ofertas posteriores y puede
  distorsionar la cobertura de compra.
- #428: la creación de una Cotización de Proveedor desde una RFQ no valida que
  la compañía enviada coincida con la RFQ origen ni exige acceso/estado del
  origen antes de persistirla.
- #429: el flujo válido Solicitud de Compra → Cotización de Proveedor directa
  no es considerado por `supplier_quotations_for_request`, por lo que esas
  cotizaciones aprobadas no aparecen en el comparativo.
- Se comentó #424 porque el nuevo helper de cotizaciones también empareja por
  `item_code` y ocurrencia, ignorando UOM, conversión, bodega y descripción.
- Se amplió #299 porque `_line_amount` confía en el `amount` enviado por el
  cliente en Compras e Inventario en lugar de garantizar `qty × rate`.
- Se comentó #423 porque el handler compartido aborta antes de alcanzar el
  código histórico de `PurchaseOrderComparison`, dejando inaccesibles los
  comparativos antiguos aunque se reconstruya su Solicitud de Compra.
- #430: el comparativo vuelve a cargar cotizaciones por ID sin filtrar
  canceladas ni congelar sus importes, por lo que puede mostrar como vigente
  una oferta retirada.
- #431: la ruta POST de creación usa acceso de consulta y no exige permiso de
  acción `crear` para persistir el comparativo.

### Continuidad

Los siguientes cambios deben preservar simultáneamente los comparativos
históricos y los nuevos, usar como universo las líneas canónicas de la
Solicitud/RFQ, validar compañía/estado/permisos al crear documentos derivados,
resolver ambos caminos de sourcing (directo y vía RFQ), y calcular los
importes en servidor con una política explícita de redondeo.

## 2026-08-15 — Correcciones de continuidad para issues #427–#431

### Petición

Se solicitó monitorear nuevos issues de GitHub, aplicar fixes sin cerrar los
issues y trabajar con commits semánticos firmados por
`William José Moreno Reyes <williamjmorenor@gmail.com>`.

### Implementación

- #427: el comparativo ahora construye sus filas como la unión estable de las
  líneas de todas las ofertas participantes y muestra `Sin cobertura` cuando
  una oferta no contiene una línea.
- #428: la creación de Cotizaciones de Proveedor valida origen aprobado,
  acceso a compañía y encabezado inmutable de compañía/moneda.
- #429: el servicio del comparativo incluye cotizaciones trazables directamente
  desde la Solicitud de Compra, además de las relacionadas vía RFQ.
- #430: las ofertas cargadas en un comparativo deben seguir aprobadas y
  pertenecer a la compañía del comparativo; se excluyen canceladas y cross-company.
- #431: la creación POST del comparativo exige la acción `crear` por compañía;
  la consulta GET conserva `consultar`.

### Commits y validación

- `06590aff fix(purchases): allow supplier quotations without rounds`.
- `99c0b71f fix(purchases): complete supplier quotation comparison`.
- `ea975842 fix(purchases): enforce comparison lifecycle and access`.
- Todos incluyen el sign-off solicitado.
- `tests/test_purchase_request_comparison.py tests/test_purchase_sourcing.py`:
  13 passed.
- Ruff, Black y `git diff --check`: correctos.
- Se comentaron #427, #428, #429, #430 y #431; todos permanecen abiertos.

### Continuidad

No se cerraron issues. Permanecen cambios locales no relacionados en `.replit`,
`ISSUES.md`, `SESSIONS.md` y `tests/test_e2e_modules.py`; deben preservarse y
revisarse antes de cualquier commit posterior.

### Nota de continuidad

Durante esta misma etapa se incorporó también el commit firmado
`c1d8c425 fix(purchases): allow multiple supplier quotations per rfq`, que
ajusta el flujo documental y su prueba end-to-end. Se conserva como cambio
independiente del alcance #427–#431.

## 2026-08-15 — Corrección del flujo aprobado del comparativo (#420)

### Petición

Se reportó una regresión: al crear una comparativa, la Solicitud de Compra
desaparecía del listado; además, el punto de entrada había vuelto a exigir
Órdenes de Compra. Se confirmó nuevamente que el proceso aprobado es:

`Solicitud de Compra abierta/aprobada → N Solicitudes de Cotización → N Cotizaciones de Proveedor → Comparativo de Ofertas`.

### Implementación

- El listado `/buying/request-for-quotation/comparison` vuelve a partir de
  Solicitudes de Compra aprobadas, sin filtrarlas por Órdenes de Compra.
- Cada solicitud permanece en la lista después de crear el comparativo; la
  fila muestra `Pendiente` o `Comparativo creado` y enlaza al detalle vigente.
- La selección carga únicamente Cotizaciones de Proveedor aprobadas asociadas
  directamente a la Solicitud de Compra o a cualquiera de sus RFQ.
- La creación persiste `PurchaseRequestComparison` con las ofertas elegidas;
  no se reintroduce una Orden de Compra como requisito del comparativo.

### Validación y cierre

- `tests/test_purchase_request_comparison.py tests/test_transaction_update_elements.py`: 20 passed.
- `tests/test_database_migrations.py`: 3 passed.
- Se cerró el issue remoto #420 porque su propuesta de basar el proceso en
  Órdenes de Compra contradice el flujo aprobado confirmado en esta sesión.
