# ISSUES — Registro de Deuda Técnica

> Este archivo documenta problemas de deuda técnica identificados en el código fuente.
> Cada issue incluye módulo afectado, severidad, descripción y propuesta de resolución.
> Cuando la API de GitHub esté disponible, estos issues se crearán remotamente.

---

## Tabla de contenidos

1. [REF-001 — compras/\_\_init\_\_.py: God Module S2P (5,426 líneas)](#ref-001)
2. [REF-002 — database/\_\_init\_\_.py: 158 modelos en un solo archivo (5,186 líneas)](#ref-002)
3. [REF-003 — contabilidad/\_\_init\_\_.py: God Module R2R (4,259 líneas)](#ref-003)
4. [REF-004 — ventas/\_\_init\_\_.py: God Module O2C (3,677 líneas)](#ref-004)
5. [REF-005 — contabilidad/posting.py: Motor de posting monolítico (3,425 líneas)](#ref-005)
6. [REF-006 — reportes/services.py: Servicios de reportes concentrados (2,908 líneas)](#ref-006)
7. [REF-007 — bancos/\_\_init\_\_.py: God Module de Bancos (2,439 líneas)](#ref-007)
8. [REF-008 — reportes/\_\_init\_\_.py: Rutas de reportes concentradas (1,601 líneas)](#ref-008)
9. [REF-009 — inventario/\_\_init\_\_.py: God Module de Inventario (1,551 líneas)](#ref-009)
10. [REF-010 — admin/\_\_init\_\_.py: God Module de Admin (1,534 líneas)](#ref-010)

---

<a id="ref-001"></a>
## REF-001 — `cacao_accounting/compras/__init__.py`: God Module del ciclo S2P

- **Módulo**: Compras (S2P — Source to Pay)
- **Archivo**: `cacao_accounting/compras/__init__.py`
- **Líneas**: 5,426
- **Funciones/rutas**: 174
- **Severidad**: Alta
- **Etiqueta**: `refactoring`, `architecture`, `maintainability`

### Problema

El archivo concentra **todas** las rutas, lógica de negocio, validación, procesamiento de formularios y orquestación del ciclo completo de compras en un solo módulo. Las responsabilidades incluyen:

- CRUD de Purchase Request (solicitud de compra)
- CRUD de Supplier Quotation (cotización de proveedor)
- CRUD de Purchase Quotation (cotización de compra)
- CRUD de Purchase Order (orden de compra)
- CRUD de Purchase Receipt (recepción de compra)
- CRUD de Purchase Invoice (factura de compra)
- Flujo de comparativo de ofertas (RFQ comparison)
- Validación de cantidades contra órdenes/recepciones
- Límites de crédito de proveedor
- Notas de crédito/débito de compra
- Gestión de landed cost (costos de importación)
- Configuración de tolerancias de conciliación
- Carga de catálogos repetida en cada ruta
- Helpers de logística, series, paginación

**Problemas concretos**:
- Merge conflicts frecuentes al trabajar múltiples desarrolladores en el mismo archivo
- Imposibilidad de hacer testing unitario aislado por subdominio
- Duplicación de carga de catálogos (`_supplier_quotation_catalogs`, `_purchase_order_catalogs`, etc.)
- Funciones helper genéricas (`_paginate_list`, `_parse_date`, `_series_choices`) mezcladas con lógica de negocio
- El archivo supera el límite de revisión cómoda de cualquier IDE o tooling

### Propuesta de descomposición

```
compras/
├── __init__.py                    # Blueprint registration + landing (~50 líneas)
├── routes/
│   ├── purchase_request.py        # CRUD + lifecycle de solicitud de compra
│   ├── supplier_quotation.py      # CRUD + lifecycle de cotización proveedor
│   ├── purchase_quotation.py      # CRUD + lifecycle de cotización de compra
│   ├── purchase_order.py          # CRUD + lifecycle de orden de compra
│   ├── purchase_receipt.py        # CRUD + lifecycle de recepción de compra
│   ├── purchase_invoice.py        # CRUD + lifecycle de factura de compra
│   ├── comparison.py              # Flujo de comparativo de ofertas
│   ├── landed_cost.py             # Costos de importación
│   └── purchase_notes.py          # Notas de crédito/débito
├── services/
│   ├── validation.py              # Validación de cantidades, tolerancias, límites
│   ├── catalogs.py                # Carga de catálogos (empresa, series, items)
│   └── reconciliation_config.py   # Configuración de tolerancias
└── helpers.py                     # Helpers genéricos (paginate, parse_date, etc.)
```

### Dependencias afectadas

- `document_flow/service.py` — importa tipos de `compras`
- `contabilidad/posting.py` — posting de PurchaseInvoice, PurchaseReceipt
- `accounting_engine/document_builders.py` — construye contextos desde documentos de compra
- `reportes/services.py` — reportes de compras por proveedor/artículo
- `tests/test_s2p_*.py` — tests del ciclo S2P

### Esfuerzo estimado

**Alto** — Requiere extraer 174 funciones en 9+ submódulos, actualizar todos los imports, y verificar que las rutas Flask mantengan los mismos URLs.

---

<a id="ref-002"></a>
## REF-002 — `cacao_accounting/database/__init__.py`: 158 modelos en un solo archivo

- **Módulo**: Core (base de datos)
- **Archivo**: `cacao_accounting/database/__init__.py`
- **Líneas**: 5,186
- **Clases**: 158 (modelos SQLAlchemy)
- **Severidad**: Alta
- **Etiqueta**: `refactoring`, `architecture`, `database`

### Problema

El archivo define **todos** los modelos de SQLAlchemy del sistema en un solo archivo. Los 158 modelos cubren:

- Estructura contable (Entity, Book, Accounts, FiscalYear, AccountingPeriod)
- Documentos de compra (PurchaseRequest → PurchaseInvoice, 18+ modelos)
- Documentos de venta (SalesRequest → SalesInvoice, 12+ modelos)
- Inventario (Item, Warehouse, StockEntry, StockBin, StockValuationLayer, etc.)
- Bancos (Bank, BankAccount, PaymentEntry, BankTransaction, Reconciliation)
- Contabilidad (ComprobanteContable, GLEntry, Budget, ExchangeRevaluation)
- Impuestos (Tax, TaxTemplate, TaxRule, DocumentTaxSummary)
- Aprobaciones (ApprovalMatrix, ApprovalRequest, ApprovalAction)
- Workflow (Workflow, WorkflowState, WorkflowTransition, WorkflowInstance)
- Auditoría (AuditLog, AuditTrail, Comment, Assignment)
- Portal (BalanceConfirmation, BalanceConfirmationInvitation)
- Forecast (CashForecast, CashForecastEntry)
- Y muchos más...

**Problemas concretos**:
- Cualquier cambio en un modelo obliga a recargar todo el archivo
- Imposible identificar qué modelos pertenecen a qué módulo por ubicación
- Las relaciones entre modelos cruzan todo el archivo sin organización
- Las migraciones de Alembic (aunque vacías) futuras serán difíciles de mantener
- El archivo no carga en la mayoría de IDEs de forma eficiente

### Propuesta de descomposición

```
database/
├── __init__.py              # Importa todos los modelos para backwards compatibility
├── base.py                  # BaseTabla, BaseTransaccion, DocBase, GLBase
├── party.py                 # Party, PartyAccount, Address, Contact
├── accounting/
│   ├── entity.py            # Entity, Book
│   ├── accounts.py          # Accounts, CompanyDefaultAccount
│   ├── fiscal.py            # FiscalYear, AccountingPeriod
│   ├── journal.py           # ComprobanteContable, ComprobanteContableDetalle
│   ├── gl.py                # GLEntry, GLEntryDimension
│   ├── dimensions.py        # DimensionType, DimensionValue
│   └── budget.py            # Budget, BudgetLine, BudgetImport
├── purchasing/
│   ├── request.py           # PurchaseRequest, PurchaseRequestItem
│   ├── quotation.py         # PurchaseQuotation, SupplierQuotation
│   ├── order.py             # PurchaseOrder, PurchaseOrderItem
│   ├── receipt.py           # PurchaseReceipt, PurchaseReceiptItem
│   ├── invoice.py           # PurchaseInvoice, PurchaseInvoiceItem
│   ├── reconciliation.py    # PurchaseReconciliation, PurchaseReconciliationItem
│   ├── landed_cost.py       # ImportLandedCost, ImportLandedCostItem
│   ├── comparison.py        # PurchaseRequestComparison
│   └── matching.py          # PurchaseMatchingConfig, PurchaseEconomicEvent
├── sales/
│   ├── request.py           # SalesRequest, SalesRequestItem
│   ├── quotation.py         # SalesQuotation, SalesQuotationItem
│   ├── order.py             # SalesOrder, SalesOrderItem
│   ├── delivery.py          # DeliveryNote, DeliveryNoteItem
│   ├── invoice.py           # SalesInvoice, SalesInvoiceItem
│   └── matching.py          # SalesMatchingConfig
├── inventory/
│   ├── item.py              # Item, ItemUOMConversion, ItemCategory, ItemAccount, ItemPrice
│   ├── uom.py               # UOM
│   ├── warehouse.py         # Warehouse, WarehouseCompanyAccount
│   ├── stock.py             # StockEntry, StockEntryItem, StockLedgerEntry, StockBin
│   ├── valuation.py         # StockValuationLayer, LandedCostAllocation
│   ├── batch.py             # Batch, SerialNumber
│   └── snapshot.py          # StockBalanceSnapshot
├── banking/
│   ├── bank.py              # Bank, BankAccount, BankAccountNumberingConfig
│   ├── payment.py           # PaymentEntry, PaymentReference
│   ├── transaction.py       # BankTransaction
│   ├── reconciliation.py    # Reconciliation, ReconciliationItem, BankMatchingRule
│   └── forecast.py          # CashForecast, CashForecastEntry
├── taxes/
│   ├── tax.py               # Tax, TaxTemplate, TaxTemplateItem
│   ├── tax_rule.py          # TaxRule
│   └── document_tax.py      # DocumentTaxSummary, DocumentTaxLine
├── documents/
│   ├── relation.py          # DocumentRelation, DocumentLineFlowState
│   └── naming.py            # NamingSeries, Sequence, ExternalCounter
├── approval.py              # ApprovalMatrix, ApprovalRequest, ApprovalAction
├── workflow.py              # Workflow, WorkflowState, WorkflowTransition, WorkflowInstance
├── audit.py                 # AuditLog, AuditTrail, Comment, CommentMention
├── email.py                 # EmailQueue
├── file.py                  # File, FileAttachment
├── task.py                  # DocumentTask
├── snapshot.py              # AccountBalanceSnapshot
├── revaluation.py           # ExchangeRevaluation, ExchangeRevaluationItem
├── period_close.py          # PeriodCloseRun, PeriodCloseCheck
├── balance_confirmation.py  # BalanceConfirmation, BalanceConfirmationInvitation
└── config.py                # PriceList, PurchaseMatchingConfig, SalesMatchingConfig
```

### Dependencias afectadas

- Todos los módulos de la aplicación importan desde `database`
- El `__init__.py` de compatibilidad mantendría los imports existentes sin cambios

### Esfuerzo estimado

**Alto** — 158 clases a distribuir en ~30 subarchivos. Requiere cuidado con imports circulares y el `__init__.py` de compatibilidad.

---

<a id="ref-003"></a>
## REF-003 — `cacao_accounting/contabilidad/__init__.py`: God Module del ciclo R2R

- **Módulo**: Contabilidad (R2R — Record to Report)
- **Archivo**: `cacao_accounting/contabilidad/__init__.py`
- **Líneas**: 4,259
- **Funciones/rutas**: 221
- **Severidad**: Alta
- **Etiqueta**: `refactoring`, `architecture`, `maintainability`

### Problema

Concentra **todas** las rutas y lógica del módulo contable:

- CRUD de Monedas (currency)
- CRUD de Entidades (entity)
- CRUD de Libros contables (book)
- CRUD de Plan de cuentas (accounts) con jerarquía
- CRUD de Centros de costo (cost center)
- CRUD de Unidades de negocio (unit)
- CRUD de Proyectos (project)
- CRUD de Años fiscales (fiscal year)
- CRUD de Períodos contables (accounting period)
- CRUD de Tipos de cambio (exchange rate)
- CRUD de Comprobantes contables (journal entry)
- Lifecycle de comprobantes (draft → submit → cancel → reverse)
- Cierre de año fiscal
- Revaluación de divisas
- Asientos recurrentes (recurring journals)
- Confirmación de saldos
- Presupuestos
- Configuración de cuentas por defecto
- Validación de períodos

**Problemas concretos**:
- 221 funciones en un solo archivo — imposible de navegar
- Mezcla de CRUD administrativo con lógica contable compleja
- El lifecycle de comprobantes contables (submit/cancel/reverse) es crítico y no debería competir con CRUD de monedas
- La validación de períodos y la lógica de cierre de año fiscal están entrelazadas con rutas HTTP

### Propuesta de descomposición

```
contabilidad/
├── __init__.py                    # Blueprint registration + landing (~50 líneas)
├── routes/
│   ├── currency.py                # CRUD de monedas
│   ├── entity.py                  # CRUD de entidades
│   ├── book.py                    # CRUD de libros contables
│   ├── accounts.py                # CRUD de plan de cuentas
│   ├── cost_center.py             # CRUD de centros de costo
│   ├── unit.py                    # CRUD de unidades de negocio
│   ├── project.py                 # CRUD de proyectos
│   ├── fiscal_year.py             # CRUD de años fiscales
│   ├── period.py                  # CRUD de períodos contables
│   ├── exchange_rate.py           # CRUD de tipos de cambio
│   ├── journal.py                 # CRUD + lifecycle de comprobantes
│   └── budget.py                  # CRUD de presupuestos
├── services/
│   ├── journal_service.py         # (ya existe) lifecycle de comprobantes
│   ├── fiscal_year_closing.py     # (ya existe) cierre de año fiscal
│   ├── exchange_revaluation.py    # (ya existe) revaluación de divisas
│   ├── recurring_journal.py       # (ya existe) asientos recurrentes
│   ├── balance_confirmation.py    # (ya existe) confirmación de saldos
│   ├── budget_service.py          # (ya existe) servicio de presupuestos
│   └── period_validation.py       # Validación de períodos (extraer de posting.py)
└── helpers.py                     # Helpers (_company_label, _validate_*, etc.)
```

### Dependencias afectadas

- `contabilidad/posting.py` — importa tipos desde `contabilidad`
- `reportes/__init__.py` — rutas de reportes contables
- `document_flow/payment.py` — posting de pagos
- Tests de contabilidad

### Esfuerzo estimado

**Alto** — 221 funciones a distribuir en 12+ submódulos de rutas. La lógica de servicios ya está parcialmente extraída.

---

<a id="ref-004"></a>
## REF-004 — `cacao_accounting/ventas/__init__.py`: God Module del ciclo O2C

- **Módulo**: Ventas (O2C — Order to Cash)
- **Archivo**: `cacao_accounting/ventas/__init__.py`
- **Líneas**: 3,677
- **Funciones/rutas**: 174
- **Severidad**: Alta
- **Etiqueta**: `refactoring`, `architecture`, `maintainability`

### Problema

Concentra **todas** las rutas y lógica del ciclo de ventas:

- CRUD de Solicitud de venta (Sales Request)
- CRUD de Cotización de venta (Sales Quotation)
- CRUD de Orden de venta (Sales Order)
- CRUD de Nota de entrega (Delivery Note)
- CRUD de Factura de venta (Sales Invoice)
- CRUD de Clientes (Customer)
- Reserva de stock en órdenes de venta
- Liberación de reserva en notas de entrega
- Validación de límites de crédito
- Notas de crédito/débito de venta
- Devoluciones
- Configuración de tolerancias de conciliación de ventas
- Portal de cliente
- Helpers de logística, series, paginación

**Problemas concretos**:
- La reserva de stock (`_validate_and_reserve_stock_for_sales_order`, `_release_reservation_for_delivery_note`) está en el módulo de ventas pero debería estar en un servicio de inventario
- La validación de crédito de cliente está entrelazada con la creación de órdenes
- Duplicación de helpers (`_parse_date`, `_series_choices`, `_paginate_list`) idénticos a los de `compras`
- 174 funciones en un solo archivo

### Propuesta de descomposición

```
ventas/
├── __init__.py                    # Blueprint registration + landing (~50 líneas)
├── routes/
│   ├── sales_request.py           # CRUD de solicitud de venta
│   ├── sales_quotation.py         # CRUD de cotización de venta
│   ├── sales_order.py             # CRUD de orden de venta
│   ├── delivery_note.py           # CRUD de nota de entrega
│   ├── sales_invoice.py           # CRUD de factura de venta
│   ├── customer.py                # CRUD de clientes
│   ├── sales_notes.py             # Notas de crédito/débito
│   └── returns.py                 # Devoluciones
├── services/
│   ├── stock_reservation.py       # Reserva/liberación de stock
│   ├── credit_validation.py       # Validación de límites de crédito
│   ├── delivery_validation.py     # Validación de cantidades contra OV
│   └── reconciliation_config.py   # Configuración de tolerancias
└── helpers.py                     # Helpers genéricos (shared with compras?)
```

### Dependencias afectadas

- `inventario/__init__.py` — reserva de stock
- `contabilidad/posting.py` — posting de SalesInvoice, DeliveryNote
- `accounting_engine/document_builders.py` — contextos desde documentos de venta
- `reportes/services.py` — reportes de ventas
- `portal/` — dashboard de cliente
- Tests de O2C

### Esfuerzo estimado

**Alto** — 174 funciones, con lógica de reserva de stock que cruza módulos.

---

<a id="ref-005"></a>
## REF-005 — `cacao_accounting/contabilidad/posting.py`: Motor de posting monolítico

- **Módulo**: Contabilidad (core posting engine)
- **Archivo**: `cacao_accounting/contabilidad/posting.py`
- **Líneas**: 3,425
- **Funciones**: ~150
- **Severidad**: Alta
- **Etiqueta**: `refactoring`, `architecture`, `testing`

### Problema

El archivo es el **corazón del sistema contable** — toda publicación al libro mayor (GL) pasa por aquí. Concentra:

- Posting de SalesInvoice (`post_sales_invoice`)
- Posting de PurchaseInvoice (`post_purchase_invoice`)
- Posting de PurchaseReceipt (`post_purchase_receipt`)
- Posting de DeliveryNote (`post_delivery_note`)
- Posting de PaymentEntry (`post_payment_entry`)
- Posting de BankTransaction (`post_bank_transaction`)
- Posting de StockEntry (`post_stock_entry`)
- Posting de ComprobanteContable (`post_comprobante_contable`)
- Posting de ImportLandedCost (`post_import_landed_cost`)
- Creación de stock ledger entries
- Creación de stock bin upserts
- Consumo de capas de valoración (FIFO/moving average)
- Manejo de stock negativo
- Reversión de movimientos de stock
- Validación de dimensiones
- Cálculo de tasas de cambio por libro
- Creación de asientos de diferencia cambiaria
- Reconciliación de.purchase receipt con factura
- Lifecycle completo: `submit_document` → `post_document_to_gl` → `cancel_document`

**Problemas concretos**:
- Un cambio en el posting de ventas puede romper el posting de compras sin detección
- El consumo de capas de valoración (líneas 1680-1815) está acoplado al posting GL
- `_upsert_stock_bin` (linea 1903) es lógica de inventario, no de posting
- `_create_stock_movement` (linea 2134) es lógica de inventario
- Las funciones de reversión de stock (`_create_stock_reversal`, `_validate_stock_reversal_capacity`) están en posting pero afectan inventario
- Las 150 funciones hacen imposible el testing aislado por tipo de documento

### Propuesta de descomposting

```
contabilidad/
├── posting/
│   ├── __init__.py              # submit_document, cancel_document, post_document_to_gl
│   ├── base.py                  # LedgerContext, helpers comunes, exchange rate resolution
│   ├── sales.py                 # post_sales_invoice, post_delivery_note
│   ├── purchasing.py            # post_purchase_invoice, post_purchase_receipt, post_import_landed_cost
│   ├── payments.py              # post_payment_entry, post_bank_transaction
│   ├── inventory.py             # post_stock_entry, _create_stock_ledger, _upsert_stock_bin
│   ├── journal.py               # post_comprobante_contable
│   ├── valuation.py             # FIFO, moving average, layer consumption
│   ├── reversal.py              # cancel_document, _create_gl_reversals, _cancel_stock_movements
│   └── reconciliation.py        # purchase reconciliation posting
```

### Dependencias afectadas

- Todos los módulos de rutas llaman `submit_document` / `cancel_document`
- `accounting_engine/` — posting alternativo vía engine
- Tests del posting engine (4,430 líneas)

### Esfuerzo estimado

**Alto** — 3,425 líneas de lógica crítica que requiere separación cuidadosa para no romper invariantes contables.

---

<a id="ref-006"></a>
## REF-006 — `cacao_accounting/reportes/services.py`: Servicios de reportes concentrados

- **Módulo**: Reportes (servicios de negocio)
- **Archivo**: `cacao_accounting/reportes/services.py`
- **Líneas**: 2,908
- **Funciones**: ~107
- **Severidad**: Media
- **Etiqueta**: `refactoring`, `maintainability`

### Problema

Concentra **todos** los servicios de generación de reportes en un solo archivo:

- Reportes financieros: Trial Balance, Income Statement, Balance Sheet, Cash Flow
- Reportes de subledger: AR/AP Aging, Maturity Schedule
- Reportes de inventario: Kardex, Existencia, Valoración, Stock Balance, Lotes, Seriados
- Reportes bancarios: Movimientos, Saldos, No conciliados, Reconciliación
- Reportes de compras: Por proveedor, Por artículo
- Reportes de ventas: Por cliente, Por artículo, Margen bruto
- Reportes de presupuesto: Varianza presupuestaria
- Filtros por tipo: SubledgerFilters, AgingFilters, KardexFilters, BankingFilters, etc.
- Funciones de formateo y enriquecimiento de datos

**Problemas concretos**:
- 107 funciones de reportes en un solo archivo
- Los filtros de reportes están definidos como clases al inicio del archivo
- No hay separación por dominio (financiero vs inventario vs bancario)
- Las funciones helper de formateo están mezcladas con la lógica de negocio

### Propuesta de descomposición

```
reportes/
├── services/
│   ├── __init__.py              # Re-exports para backwards compatibility
│   ├── filters.py               # SubledgerFilters, AgingFilters, KardexFilters, etc.
│   ├── financial.py             # Trial Balance, Income Statement, Balance Sheet
│   ├── subledger.py             # AR/AP Aging, Maturity Schedule, Account Movement
│   ├── inventory.py             # Kardex, Existencia, Valoración, Lotes, Seriados
│   ├── banking.py               # Bank Movement, Balance Summary, Reconciliation
│   ├── purchasing.py            # Purchases by Supplier/Item
│   ├── sales.py                 # Sales by Customer/Item, Gross Margin
│   ├── budget.py                # Budget Variance
│   └── helpers.py               # Formateo, paginación, enriquecimiento
```

### Dependencias afectadas

- `reportes/__init__.py` — importa servicios
- `api/__init__.py` — endpoints JSON de reportes
- Tests de reportes

### Esfuerzo estimado

**Medio** — Funciones independientes sin acoplamiento cruzado significativo.

---

<a id="ref-007"></a>
## REF-007 — `cacao_accounting/bancos/__init__.py`: God Module de Bancos

- **Módulo**: Bancos (Treasury)
- **Archivo**: `cacao_accounting/bancos/__init__.py`
- **Líneas**: 2,439
- **Funciones/rutas**: 131
- **Severidad**: Media
- **Etiqueta**: `refactoring`, `architecture`

### Problema

Concentra todas las rutas y lógica del módulo de bancos/tesorería:

- CRUD de Bancos (Bank)
- CRUD de Cuentas bancarias (BankAccount)
- CRUD de Pagos (PaymentEntry) — pay, receive, transfer, debit_note, credit_note
- Conciliación bancaria (manual y automática)
- Importación de extractos bancarios
- Reglas de matching
- Cash forecast (pronóstico de flujo de caja)
- Configuración de numeración por cuenta bancaria
- Validación de duplicados
- Resolución de cuentas GL

**Problemas concretos**:
- La creación de pagos (`_create_payment_entry`, `_save_payment_references`, `_finalize_and_commit_payment`) es lógica de negocio compleja mezclada con rutas HTTP
- La conciliación bancaria tiene su propio servicio (`reconciliation_service.py`) pero la orquestación está en `__init__.py`
- El cash forecast tiene su propio servicio (`cash_forecast_service.py`) pero las rutas están en `__init__.py`
- `_form_decimal` no maneja formato locale (coma como separador de miles)

### Propuesta de descomposición

```
bancos/
├── __init__.py                    # Blueprint registration + landing (~50 líneas)
├── routes/
│   ├── bank.py                    # CRUD de bancos
│   ├── bank_account.py            # CRUD de cuentas bancarias
│   ├── payment.py                 # CRUD de pagos (create/submit/cancel)
│   ├── reconciliation.py          # Rutas de conciliación
│   ├── statement.py               # Importación de extractos
│   ├── matching_rules.py          # Reglas de matching
│   └── cash_forecast.py           # Rutas de pronóstico
├── services/
│   ├── payment_service.py         # Lógica de creación/validación de pagos
│   ├── reconciliation_service.py  # (ya existe)
│   ├── statement_service.py       # (ya existe)
│   └── cash_forecast_service.py   # (ya existe)
└── helpers.py                     # Helpers (_form_decimal, _paginate_list, etc.)
```

### Dependencias afectadas

- `contabilidad/posting.py` — posting de PaymentEntry
- `document_flow/payment.py` — reconciliación de pagos
- `reportes/services.py` — reportes bancarios
- Tests de bancos

### Esfuerzo estimado

**Medio** — Los servicios ya están parcialmente extraídos; queda mover rutas y lógica de orquestación.

---

<a id="ref-008"></a>
## REF-008 — `cacao_accounting/reportes/__init__.py`: Rutas de reportes concentradas

- **Módulo**: Reportes (rutas HTTP)
- **Archivo**: `cacao_accounting/reportes/__init__.py`
- **Líneas**: 1,601
- **Funciones/rutas**: 111
- **Severidad**: Media
- **Etiqueta**: `refactoring`, `maintainability`

### Problema

Concentra todas las rutas HTTP de reportes en un solo archivo:

- Rutas de reportes financieros (trial balance, income statement, balance sheet)
- Rutas de reportes de subledger (aging, maturity)
- Rutas de reportes de inventario (kardex, existencia, valoración)
- Rutas de reportes bancarios (movimientos, saldos)
- Rutas de reportes de compras/ventas
- Rutas de reportes de presupuesto
- Exportación CSV/XLSX
- Vistas guardadas (saved views)
- Drill-down de documentos
- Formateo de columnas y celdas

**Problemas concretos**:
- 111 funciones de rutas en un solo archivo
- Cada grupo de reportes compite por espacio
- Las funciones helper de formateo (`_format_cell`, `_column_label`) están al inicio del archivo

### Propuesta de descomposición

```
reportes/
├── __init__.py                    # Blueprint registration (~30 líneas)
├── routes/
│   ├── financial.py               # Trial Balance, Income Statement, Balance Sheet
│   ├── subledger.py               # AR/AP Aging, Maturity, Account Movement
│   ├── inventory.py               # Kardex, Existencia, Valoración
│   ├── banking.py                 # Bank Movement, Balance Summary
│   ├── purchasing.py              # Purchases by Supplier/Item
│   ├── sales.py                   # Sales by Customer/Item, Gross Margin
│   ├── budget.py                  # Budget Variance
│   ├── export.py                  # CSV/XLSX export
│   └── views.py                   # Saved views management
├── services/                      # (ver REF-006)
└── helpers.py                     # Formateo de columnas, celdas, contextos
```

### Dependencias afectadas

- `api/__init__.py` — endpoints JSON
- Templates HTML de reportes

### Esfuerzo estimado

**Medio** — 111 funciones de rutas a distribuir en 9 submódulos.

---

<a id="ref-009"></a>
## REF-009 — `cacao_accounting/inventario/__init__.py`: God Module de Inventario

- **Módulo**: Inventario
- **Archivo**: `cacao_accounting/inventario/__init__.py`
- **Líneas**: 1,551
- **Funciones/rutas**: 102
- **Severidad**: Baja
- **Etiqueta**: `refactoring`, `maintainability`

### Problema

Concentra todas las rutas del módulo de inventario:

- CRUD de Artículos (Item)
- CRUD de Unidades de medida (UOM)
- CRUD de Bodegas (Warehouse)
- CRUD de Stock Entries (material receipt, material issue, transfer, adjustment, reconciliation)
- Configuración de valoración FIFO/moving average
- Listas filtradas por tipo de movimiento
- Validación de almacenes
- Resolución de propósitos de movimiento

**Problemas concretos**:
- 102 funciones en un archivo (justo sobre el umbral)
- Las rutas de stock entry manejan 7+ tipos de movimiento con lógica condicional extensa
- `_save_stock_entry_items` no tiene límite de líneas (riesgo de abuso)
- `_line_rate` tiene lógica redundante (condiciones inalcanzables)

### Propuesta de descomposición

```
inventario/
├── __init__.py                    # Blueprint registration + landing (~50 líneas)
├── routes/
│   ├── item.py                    # CRUD de artículos
│   ├── uom.py                     # CRUD de unidades de medida
│   ├── warehouse.py               # CRUD de bodegas
│   ├── stock_entry.py             # CRUD de movimientos de inventario
│   └── reconciliation.py          # Conciliación de inventario
├── services/
│   ├── service.py                 # (ya existe) lógica de negocio
│   └── valuation_settings.py      # (ya existe) configuración de valoración
└── helpers.py                     # Helpers (_parse_date, _series_choices, etc.)
```

### Dependencias afectadas

- `ventas/__init__.py` — reserva de stock
- `compras/__init__.py` — recepciones de compra
- `contabilidad/posting.py` — posting de StockEntry
- Tests de inventario

### Esfuerzo estimado

**Bajo** — Archivo relativamente pequeño, descomposición clara.

---

<a id="ref-010"></a>
## REF-010 — `cacao_accounting/admin/__init__.py`: God Module de Admin

- **Módulo**: Admin (configuración del sistema)
- **Archivo**: `cacao_accounting/admin/__init__.py`
- **Líneas**: 1,534
- **Funciones/rutas**: 96
- **Severidad**: Baja
- **Etiqueta**: `refactoring`, `maintainability`

### Problema

Concentra todas las rutas de administración del sistema:

- Configuración de módulos (enable/disable)
- Configuración de validación de documentos externos
- Configuración de email (settings, test, log)
- Configuración de valoración de inventario
- Configuración de impuestos (taxes, tax templates)
- Configuración de secuencias de numeración
- Configuración de contadores externos
- Configuración de tolerancias de conciliación (purchase/sales matching)
- Gestión de usuarios y roles
- Configuración de libros contables por empresa
- Configuración de cuentas por defecto por empresa
- Configuración de aprobaciones
- Configuración de workflows
- Configuración de importaciones
- Logs de auditoría
- Gestión de archivos

**Problemas concretos**:
- 96 funciones de configuración en un solo archivo
- Cada subdominio de configuración es independiente
- La configuración de email (con test de envío) no debería estar junto con la configuración de impuestos

### Propuesta de descomposición

```
admin/
├── __init__.py                    # Blueprint registration + landing (~50 líneas)
├── routes/
│   ├── modules.py                 # Enable/disable de módulos
│   ├── email.py                   # Configuración de email
│   ├── taxes.py                   # Impuestos y plantillas
│   ├── numbering.py               # Secuencias y contadores
│   ├── matching.py                # Tolerancias de conciliación
│   ├── users.py                   # Usuarios y roles
│   ├── books.py                   # Libros contables por empresa
│   ├── accounts.py                # Cuentas por defecto
│   ├── approvals.py               # Matriz de aprobaciones
│   ├── workflows.py               # Configuración de workflows
│   ├── imports.py                 # Configuración de importaciones
│   ├── valuation.py               # Valoración de inventario
│   └── audit.py                   # Logs de auditoría
└── helpers.py                     # Helpers (_require_system_admin, etc.)
```

### Dependencias afectadas

- `auth/roles.py` — definición de roles
- `approval_engine.py` — configuración de aprobaciones
- Templates HTML de admin

### Esfuerzo estimado

**Bajo** — Archivo relativamente pequeño, descomposición clara por subdominio.

---

## Resumen de impacto

| Issue | Archivo | Líneas | Submódulos | Esfuerzo |
|-------|---------|--------|------------|----------|
| REF-001 | compras/\_\_init\_\_.py | 5,426 | 12 | Alto |
| REF-002 | database/\_\_init\_\_.py | 5,186 | 30+ | Alto |
| REF-003 | contabilidad/\_\_init\_\_.py | 4,259 | 15 | Alto |
| REF-004 | ventas/\_\_init\_\_.py | 3,677 | 10 | Alto |
| REF-005 | contabilidad/posting.py | 3,425 | 10 | Alto |
| REF-006 | reportes/services.py | 2,908 | 10 | Medio |
| REF-007 | bancos/\_\_init\_\_.py | 2,439 | 9 | Medio |
| REF-008 | reportes/\_\_init\_\_.py | 1,601 | 9 | Medio |
| REF-009 | inventario/\_\_init\_\_.py | 1,551 | 5 | Bajo |
| REF-010 | admin/\_\_init\_\_.py | 1,534 | 13 | Bajo |

**Total de líneas a refactorizar**: 32,066
**Total de archivos a crear**: ~120 submódulos

### Orden de refactorización recomendado

1. **database/\_\_init\_\_.py** (REF-002) — Es la base; todos los módulos dependen de él. El `__init__.py` de compatibilidad permite migración incremental.
2. **contabilidad/posting.py** (REF-005) — Core del sistema contable. Separar por tipo de documento reduce riesgo de regresión.
3. **compras/\_\_init\_\_.py** (REF-001) — El más grande. Extraer servicios y helpers primero, luego rutas.
4. **ventas/\_\_init\_\_.py** (REF-004) — Similar a compras, pero con acoplamiento a inventario.
5. **contabilidad/\_\_init\_\_.py** (REF-003) — CRUDs son independientes; extraer primero.
6. **reportes/services.py** (REF-006) — Servicios independientes, bajo riesgo.
7. **bancos/\_\_init\_\_.py** (REF-007) — Servicios ya parcialmente extraídos.
8. **reportes/\_\_init\_\_.py** (REF-008) — Rutas straightforward.
9. **inventario/\_\_init\_\_.py** (REF-009) — Archivo pequeño, baja prioridad.
10. **admin/\_\_init\_\_.py** (REF-010) — Archivo pequeño, baja prioridad.
