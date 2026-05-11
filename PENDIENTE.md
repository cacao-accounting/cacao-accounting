# PENDIENTE — Cacao Accounting

## Actualizacion incremental - 2026-05-11 (menu cierre mensual)

- [x] Implementar la logica completa de `Comprobante Recurrente`: modelos `RecurringJournalTemplate`/lineas, estados, aprobacion sin GL, cancelacion con motivo e historial.
- [x] Implementar `RecurringJournalApplication` con restriccion unica por compania, ledger, plantilla, fiscal year y periodo.
- [x] Implementar la aplicacion real desde el `Asistente de Cierre Mensual`, generando comprobantes contables reales y marcandolos como recurrentes.

## Actualizacion incremental - 2026-05-11 (FIXME reportes y cierre)

- Sin nuevos pendientes derivados de esta iteracion.
- Quedan cerrados los issues actuales de `FIXME.md` relacionados con acceso a comprobantes de cierre, filtros de reportes financieros, busqueda de tercero, agrupacion por comprobante, prefill de libro/periodo y cobertura E2E focalizada de reportes.

## Actualización incremental — 2026-05-10

- Sin nuevos pendientes derivados de esta iteración.
- Se resolvió la compatibilidad de reportes financieros con clasificaciones de cuentas en plural (`Ingresos`/`Gastos`) en el cálculo de resultados.

**Fecha de análisis:** 2026-05-06
**Base:** definición de módulos en `modulos/` y estado actual del código.

Este documento registra todo lo que está pendiente de implementar para cumplir la especificación completa de los módulos del sistema.

---

## 🔴 BLOQUE 1 — Posting Contable (Core crítico)

El servicio `cacao_accounting/contabilidad/posting.py` ya contabiliza documentos operativos principales: facturas de venta, facturas de compra, pagos y `StockEntry`. La prioridad cambia de “crear posting desde cero” a completar los escenarios faltantes: impuestos, COGS desde entregas, recibos directos, Journal Entry manual, reglas avanzadas y reportes.

### 1.1 Contabilización de Factura de Venta (`SalesInvoice`)
- [x] Al hacer submit, generar `GLEntry` por cada libro activo (`Book`):
  - Débito: Cuentas por cobrar (AR) — `PartyAccount` del cliente.
  - Crédito: Ingreso de ventas — cuenta de ingreso del ítem.
- [x] Líneas de impuesto: según `TaxTemplate` aplicada, con fallback a cuenta predeterminada de ventas si el impuesto no define cuenta.
- [ ] Costo de ventas (COGS) si el ítem es inventariable y se entrega/factura.
- [x] Respetar `posting_date` y período abierto.
- [x] Registrar `voucher_type` y `voucher_id` en cada `GLEntry`.
- [ ] Calcular `outstanding_amount` inicial de forma centralizada al submit.
- [x] Guardar moneda base/original y `exchange_rate` cuando el documento lo provee.
- [x] Generar reverso contable append-only al cancelar.

### 1.2 Contabilización de Factura de Compra (`PurchaseInvoice`)
- [x] Al hacer submit, generar `GLEntry` por cada libro activo:
  - Débito: gasto, inventario o impuesto acreditable según tipo de ítem.
  - Crédito: Cuentas por pagar (AP) — `PartyAccount` del proveedor.
  - Si hay recepción previa: descarga cuenta puente de conciliación de compras.
- [x] Separar impuestos acreditables en cuentas fiscales predeterminadas cuando el impuesto no define cuenta específica.
- [ ] Calcular `outstanding_amount` inicial de forma centralizada al submit.
- [x] Soportar multimoneda cuando el documento trae moneda/tasa.
- [x] Generar reverso contable append-only al cancelar.

### 1.3 Contabilización de Pago (`PaymentEntry`)
- [x] Al hacer submit, generar `GLEntry`:
  - Cobro: Débito banco/caja, Crédito AR.
  - Pago: Débito AP, Crédito banco/caja.
  - Transferencia interna: Débito cuenta destino, Crédito cuenta origen.
- [x] Separar operativamente transferencias internas de pagos/cobros en listados y flujo de registro.
- [x] Procesar `PaymentReference` y reducir `outstanding_amount` en documentos aplicados al crear pagos desde factura.
- [x] Calcular `allocation_date` para cada referencia.
- [x] Usar cuenta explícita o fallback `BankAccount.gl_account_id`.
- [ ] Recalcular referencias y outstanding desde GL/allocations como fuente dinámica.

### 1.4 Contabilización de Nota de Entrega / Recepción de Mercancía (Inventario)
- [x] Al hacer submit de `DeliveryNote`: generar `StockLedgerEntry` (salida) + `GLEntry` de COGS.
- [x] Al hacer submit de `PurchaseReceipt`: generar `StockLedgerEntry` (entrada) + `GLEntry` contra cuenta puente de conciliación de compras.
- [x] Actualizar `StockBin` (saldo actual) tras cada movimiento.
- [x] Registrar `StockValuationLayer` con costo según método (FIFO / Moving Average).
- [x] Validar reversión de notas de entrega y recepciones con `is_return` y reversos append-only.
- [x] Añadir pruebas de reversión contable y stock para `PurchaseReceipt` y `DeliveryNote`.

### 1.5 Contabilización de Entrada de Almacén (`StockEntry`)
- [x] Al hacer submit: generar `StockLedgerEntry` según propósito (material_receipt, material_issue, material_transfer).
- [x] Actualizar `StockBin`.
- [x] Generar `GLEntry` con cuenta de inventario vs contrapartida según propósito.
- [x] Registrar `StockValuationLayer`.
- [x] Soportar ajustes de inventario/reconciliación física con cuenta predeterminada de ajuste.
- [ ] Implementar FIFO y Moving Average reales para consumo de capas.

### 1.6 Comprobante Contable Manual (Journal Entry)
- [x] Implementar servicio/repository de captura en `contabilidad/` dejando `contabilidad/gl/` como legacy.
- [x] Validar balance (`SUM(debit) == SUM(credit)`) y líneas de un solo lado antes de guardar borrador.
- [x] Guardar borrador desde `/accounting/journal/new` en `ComprobanteContable` y `ComprobanteContableDetalle` sin generar `GLEntry`.
- [x] Agregar acción separada `/accounting/journal/<id>/submit` para generar `GLEntry` desde el motor existente.
- [x] Persistir configuración de columnas por usuario en backend para el formulario de Journal Entry.
- [x] Generar `GLEntry` por cada línea y por cada libro activo desde una acción de submit; el comprobante manual puede limitarse a uno o varios libros activos.
- [x] Permitir en `/accounting/journal/new` seleccionar libros activos con checkboxes preseleccionados y tratar “todos marcados” como afectar todos los libros activos.
- [x] Permitir editar borradores del comprobante manual para cambiar libros y líneas antes del submit.
- [x] Exigir centro de costo en líneas de cuentas de gasto.
- [x] Forzar moneda única por comprobante y bloquear mezcla de monedas en líneas.
- [x] Migrar moneda de cabecera a SmartSelect (`doctype=currency`) en el formulario de comprobante manual.
- [x] Simplificar modal de línea: sin moneda de línea y sin cuenta bancaria.
- [x] Persistir `is_advance` del modal avanzado y mantener compatibilidad backend para `bank_account` vía payload/API legado.
- [x] Añadir prueba E2E basada en cliente Flask (GET/POST) para verificar creación de borrador (`tests/test_e2e_journalentry.py`).
- [ ] Soportar tipos: estándar, apertura, nota de crédito, nota de débito, contra asiento, ajuste, reversión.
- [ ] Completar edición de borradores y lista operacional; `/gl/new` y `/gl/list` quedan como legacy hasta retiro.
- [x] Añadir cobertura HTTP del selector multi-book y del endpoint de libros activos del comprobante manual.
- [~] Resolver formalmente el comportamiento de `document_no` cuando un borrador cambia de serie antes de contabilizar.
- [x] Diferir numeración en `Duplicar`/`Revertir`: crear borradores sin `document_no` y asignar identificador al primer guardado de edición (con fallback en submit).
- [x] Permitir contabilización manual con cuentas de caja/banco en `Journal Entry` y mostrar errores de submit mediante flash global.
- [ ] Implementar selector de documentos abiertos dependiente de compañía / tipo de tercero / tercero / tipo documental.
- [x] Completar estados operativos visibles del comprobante (cancelado, reversado, cierre) y sus restricciones.

---

## 🟠 BLOQUE 2 — Cuentas por Cobrar / Cuentas por Pagar (AR/AP)

### 2.1 Saldo pendiente (`outstanding_amount`)
- [x] Implementar cálculo dinámico de `outstanding_amount` para `SalesInvoice` y `PurchaseInvoice`.
- [x] Fórmula: `outstanding_amount = total_amount - SUM(allocated_amount de PaymentReference)`.
- [x] El campo persistido es cache; el cálculo dinámico es la fuente de verdad.
- [x] Consistencia temporal: filtrar por `posting_date` y `allocation_date`.

### 2.2 Aplicación de pagos a facturas
- [ ] Permitir desde el formulario de pago seleccionar una o varias facturas pendientes del mismo tercero.
- [ ] Registrar `PaymentReference` con `allocated_amount` y `allocation_date`.
- [ ] Actualizar `outstanding_amount` en las facturas aplicadas.
- [ ] Soportar pago parcial (un pago → una factura parcial).
- [ ] Soportar pago multiple (un pago → múltiples facturas).
- [ ] Soportar aplicación cruzada (múltiples pagos → una factura).

### 2.3 Anticipos (totales y parciales)
- [ ] Registrar anticipo de cliente como pasivo (cuenta de anticipo de cliente).
- [ ] Registrar anticipo a proveedor como activo (cuenta de anticipo a proveedor).
- [ ] Aplicar anticipo contra factura mediante `PaymentReference` con `allocation_date`.
- [ ] Soportar aplicación parcial: el remanente queda como saldo a favor.
- [ ] Aplicar un anticipo a múltiples facturas del mismo tercero.
- [x] Configuración de cuentas contables de anticipos por compañía en `CompanyDefaultAccount`.

### 2.4 Aging AR/AP
- [x] Implementar cálculo de aging por buckets (0-30, 31-60, 61-90, +90 días) basado en `posting_date`.
- [x] Reproducible históricamente: calcular aging para cualquier fecha pasada.
- [x] Vista MVP de aging por cliente (AR) y por proveedor (AP).
- [ ] Mejorar UX/exportación y permitir buckets configurables por compañía.

---

## 🟠 BLOQUE 3 — Documentos de Corrección

### 3.1 Nota de Crédito de Venta (Sales Credit Note)
- [ ] Verificar y reforzar la creación de nota de crédito de venta con `is_return=True` y `reversal_of` a factura origen.
- [ ] Generar GL inverso al de la factura original.
- [ ] Reducir `outstanding_amount` de la factura referenciada.
- [ ] Validar que la lista de notas de crédito muestre correctamente el origen y el estado del documento.

### 3.2 Nota de Débito de Venta (Sales Debit Note)
- [ ] Verificar la creación de nota de débito de venta y su asociación a la factura origen.
- [ ] Generar GL adicional al de la factura original.
- [ ] Incrementar `outstanding_amount` de la factura referenciada.

### 3.3 Devolución de Venta (Sales Return)
- [ ] Implementar retorno de mercancía: `DeliveryNote` con `is_return=True`.
- [ ] Revertir `StockLedgerEntry` y `StockValuationLayer`.
- [ ] Generar `SalesInvoice` de crédito asociada.

### 3.4 Nota de Crédito de Compra (Purchase Credit Note)
- [ ] Ruta de creación desde factura de proveedor.
- [ ] `PurchaseInvoice` con `is_return=True` o vía nota de crédito de proveedor.
- [ ] Revertir impacto GL y ajustar `outstanding_amount` AP.

### 3.5 Nota de Débito de Compra (Purchase Debit Note)
- [ ] Ruta de creación desde factura de proveedor.
- [ ] Incrementar `outstanding_amount` AP.

### 3.6 Devolución de Compra (Purchase Return)
- [ ] `PurchaseReceipt` con `is_return=True`.
- [ ] Revertir `StockLedgerEntry`.
- [ ] Generar nota de crédito de proveedor asociada.

### 3.7 Reversión de Comprobante Contable
- [x] Servicio de reversión para documentos operativos contabilizados.
- [x] Poblar `reversal_of` y `is_reversal` en las entradas GL reversadas.
- [ ] Trazabilidad bidireccional visible entre asiento original y reverso.
- [x] Aplicar el mismo patrón al comprobante contable manual.

---

## 🟠 BLOQUE 4 — Proveedor y Cliente (formularios completos)

### 4.1 Formulario de Proveedor
- [ ] Validar y mejorar `proveedor_nuevo.html` tras la documentación de FIXME; el flujo actual es operativo pero requiere controles adicionales.
- [ ] Campos requeridos: razón social, identificación fiscal, moneda, condiciones de pago, cuentas AP.
- [ ] Gestión de direcciones (`Address`) y contactos (`Contact`) vinculados (`PartyAddress`, `PartyContact`).
- [ ] Activación en compañía (`CompanyParty`).

### 4.2 Formulario de Cliente
- [ ] Completar `cliente_nuevo.html` con campos equivalentes al proveedor.
- [ ] Gestión de direcciones y contactos.
- [ ] Activación en compañía.

### 4.3 Grupos de Clientes y Proveedores
- [ ] Implementar modelo `PartyGroup` para agrupar terceros.
- [ ] CRUD de grupos en la interfaz.

---

## 🟡 BLOQUE 5 — Inventario (Servicios de Valoración)

### 5.1 StockLedgerEntry automático
- [x] Generar `StockLedgerEntry` al submit de `StockEntry`.
- [x] Generar `StockLedgerEntry` al submit directo de `PurchaseReceipt` y `DeliveryNote`.
- [x] Campos base: `item_code`, `warehouse`, `posting_date`, `qty_change`, `qty_after_transaction`, `valuation_rate`, `voucher_type`, `voucher_id`.
- [x] Política de reversión con SLE inverso append-only implementada para `StockEntry`, `PurchaseReceipt` y `DeliveryNote`.
- [ ] Ampliar pruebas de reversión para validar `is_return`, stock negativo y ajustes de bin.

### 5.2 StockBin (cache de saldo actual)
- [x] Actualizar `StockBin` en cada `StockLedgerEntry` generado por `StockEntry`.
- [x] Campo: `actual_qty`, `valuation_rate`, `stock_value`.
- [x] Servicio de recalculo de `StockBin` desde `StockLedgerEntry`.

### 5.3 StockValuationLayer (costo por capa)
- [x] Crear `StockValuationLayer` básico desde `StockEntry`.
- [ ] Implementar método FIFO: crear capa con `qty` y `incoming_rate` en cada entrada; consumir capas más antiguas en salidas.
- [ ] Implementar método Moving Average: recalcular costo promedio en cada entrada; usar promedio vigente en salidas.
- [ ] Método de valuación inmutable una vez hay transacciones en el ítem.

### 5.4 Lotes (Batch)
- [x] Requerir selección de lote en recepciones/salidas cuando `item.has_batch = True`.
- [x] Validar existencia del lote antes de movimiento.
- [x] Reporte de lotes por estado y vencimiento MVP.

### 5.5 Números de Serie (SerialNumber)
- [x] Requerir selección de serial en recepciones/salidas cuando `item.has_serial_no = True`.
- [x] Actualizar `serial_status` y `warehouse` en cada movimiento.
- [x] Reporte de seriales por estado y ubicación MVP.

### 5.6 Stock Reconciliation
- [x] UI MVP de conciliación física de inventario sobre `StockEntry`.
- [ ] Tipos: ajuste de cantidad, ajuste de valuación.
- [x] Generar `StockLedgerEntry` de ajuste positivo/negativo.

### 5.7 Conversiones de UOM
- [x] Aplicar `ItemUOMConversion` al ingresar cantidad en unidad alternativa.
- [x] `StockLedgerEntry` siempre en unidad base.

---

## 🟡 BLOQUE 6 — Conciliación de Compras

- [x] Definir cuenta puente configurable por compañía en `CompanyDefaultAccount`.
- [x] Al submit de `StockEntry` material_receipt: acreditar cuenta puente cuando el flujo contable la requiere.
- [x] Al submit directo de `PurchaseReceipt`: acreditar cuenta puente (no AP).
- [x] Al submit de `PurchaseInvoice` con recepción previa: debitar cuenta puente, acreditar AP.
- [x] Implementar UI y servicio de `PurchaseReconciliation` por líneas.
- [x] Soportar matching 3-way con recepción y factura.
- [x] Soportar matching 2-way con orden de compra y factura sin recepción, sin reutilizar referencias de recepción.
- [x] Evaluar matching por agregados de producto/UOM antes de crear detalles de conciliación.
- [x] Registrar disputas (`MATCH_FAILED`) sin consumir cantidades disponibles.
- [x] Auto-conciliar facturas PO-only desde posting cuando la compañía está configurada en 2-way.
- [x] Cancelar conciliaciones 2-way y 3-way al anular la factura, liberando cantidades.
- [x] Permitir posting operativo de recepción sin cuenta puente cuando `bridge_account_required=False`.
- [x] Reporte de conciliación de compras pendiente por proveedor/ítem/documento.
- [ ] Definir cuenta de ajuste y flujo contable para diferencias de precio conciliación de compras.

---

## 🟡 BLOQUE 6.1 — Catálogo base y cuentas predeterminadas

- [x] `base_es.csv` incluye columna `account_type` en inglés y conserva compatibilidad de importación con cabeceras en español.
- [x] Cada catálogo ofrecido por el setup debe tener mapping JSON compañero; `base_es.csv` se acompaña por `base_es.json` y `base_en.csv` se acompaña por `base_en.json`.
- [x] El setup inicial aplica el mapping JSON y crea `CompanyDefaultAccount` completo al seleccionar un catálogo predefinido.
- [x] CRUD administrativo `/settings/default-accounts` para crear, editar y eliminar cuentas predeterminadas por compañía.
- [x] `/settings/default-accounts` usa Smart Select para buscar cuentas por código/nombre, sin renderizar todo el catálogo y filtrando por compañía + tipos compatibles.
- [x] `Accounts.account_type` tiene enforcement estricto en posting: cuentas sin tipo permiten afectación libre; cuentas tipadas se restringen por origen/módulo.
- [x] `CompanyDefaultAccount` cubre las cuentas actuales requeridas por bancos, compras, ventas, inventario, impuestos, anticipos, diferidos, redondeo, diferencias cambiarias, resultado del período y resultados acumulados.
- [ ] Crear migración formal para instalaciones existentes cuando el proyecto adopte un flujo de migraciones.

## 🟡 BLOQUE 6.2 — Smart Select Framework

- [x] Backend genérico `/api/search-select` con registry explícito de doctypes permitidos y filtros validados.
- [x] Frontend Alpine.js reutilizable en `static/js/smart-select.js` para búsqueda, loading, errores, limpieza, valor inicial y filtros dinámicos.
- [x] Instrucción permanente `.github/instructions/search-select-fields.instructions.md` para migraciones futuras.
- [x] Registry extendido para el formulario GL con `company`, `book`, `cost_center`, `unit`, `project` y `party`.
- [x] API `/api/form-preferences/<form_key>/<view_key>` para layouts persistidos por usuario.
- [ ] Migrar progresivamente selects de catálogos grandes/contextuales en compras, ventas, bancos, inventario y GL.
- [ ] Añadir cobertura específica por cada formulario migrado para confirmar filtros de compañía, permisos y valores guardados.

## 🟡 BLOQUE 6.3 — Smoke Test de Rutas

- [x] Crear `tests/test_routes_map.py` usando el `url_map` real de Flask para visitar rutas GET estáticas construibles.
- [x] Detectar automáticamente rutas que renderizan 404/5xx por enlaces o endpoints rotos en vistas/templates.
- [ ] Extender la cobertura a rutas dinámicas con parámetros mínimos por módulo.
- [ ] Definir whitelist explícita para endpoints API cuyo 400/404 sin query params es comportamiento esperado y no error de routing.

---

## 🟡 BLOQUE 7 — Impuestos y Cargos

### 7.1 UI de Gestión de Impuestos
- [x] CRUD MVP de `Tax` (definición de impuesto/cargo: nombre, tasa, cuenta contable, tipo).
- [x] CRUD MVP de `TaxTemplate` (plantilla: nombre, tipo buying/selling).
- [x] CRUD MVP de `TaxTemplateItem` (líneas: impuesto, tipo cálculo, comportamiento).

### 7.2 Aplicación en Documentos
- [x] Al postear factura, aplicar `TaxTemplate` seleccionada y calcular monto de cada línea de impuesto.
- [x] Soportar cálculo fijo (monto absoluto) y porcentual.
- [x] Soportar comportamiento aditivo (suma al total) y deductivo (resta del total).
- [x] Base de cálculo configurable MVP: neto documento y base previa.

### 7.3 Cargos Adicionales (Flete, Seguro, Aduana)
- [x] Campo `capitalizable` en definición de cargo/impuesto.
- [ ] Si capitalizable: prorratear costo entre ítems según regla (por cantidad, por valor, por peso/volumen).
- [x] Si no capitalizable: registrar como gasto/ingreso/impuesto en cuenta contable definida.
- [ ] Actualizar `StockValuationLayer` para ítems inventariables capitalizables.

---

## 🟡 BLOQUE 8 — Precios

### 8.1 UI de Listas de Precios
- [x] CRUD MVP de `PriceList` (nombre, tipo buying/selling, moneda, activa).
- [x] CRUD MVP de `ItemPrice` (ítem, precio, fecha inicio/fin de vigencia).

### 8.2 Sugerencia de Precio en Documentos
- [x] Servicio `get_item_price` para sugerir precio desde `ItemPrice` activo.
- [ ] El precio sugerido es editable en el documento.
- [ ] Tolerancia de precio por rol y tipo de documento.
- [ ] Documentos con precios fuera de tolerancia requieren aprobación por workflow.

---

## 🟡 BLOQUE 9 — Multi-Ledger

- [x] Implementar lógica de posting multi-libro para facturas, pagos y `StockEntry`: genera `GLEntry` por cada `Book` activo de la compañía.
- [ ] Implementar `LedgerMappingRule`: diferencias de cuenta/monto entre libros.
- [ ] UI para gestión de reglas de mapeo entre libros.
- [ ] Reporte de Mayor General por libro.

---

## 🟡 BLOQUE 10 — Dimensiones Analíticas

- [ ] UI de `DimensionType` (lista, nuevo, activar/inactivar).
- [ ] UI de `DimensionValue` (lista y CRUD por tipo).
- [ ] Captura de dimensiones en formularios de documentos operativos.
- [ ] Generación de `GLEntryDimension` al contabilizar.
- [ ] Reporte de saldos por dimensión (cost_center, unit, project, dimensiones personalizadas).

---

## 🟡 BLOQUE 11 — Revalorización Cambiaria

- [ ] UI para ejecutar `ExchangeRevaluation` por compañía y fecha.
- [ ] Seleccionar cuentas en moneda extranjera a revalorizar.
- [ ] Calcular diferencia entre tipo de cambio original y actual.
- [ ] Generar `GLEntry` de pérdida/ganancia cambiaria.
- [ ] Registrar `ExchangeRevaluationItem` con detalle por cuenta.
- [ ] Reporte de diferencias cambiarias históricas.

---

## 🟡 BLOQUE 12 — Cierre de Período

- [ ] UI de ejecución de `PeriodCloseRun` para un período contable.
- [ ] Implementar checks (`PeriodCloseCheck`):
  - [ ] GL balanceado en el período.
  - [ ] AR/AP conciliado.
  - [ ] GI/IR conciliado.
  - [ ] Revaluaciones aplicadas.
  - [ ] Inventario consistente.
- [ ] Marcar `AccountingPeriod.is_closed = True` al completar cierre.
- [ ] Validar en todos los endpoints de posting que el período esté abierto.
- [ ] Control de reapertura autorizada con bitácora.

---

## 🟡 BLOQUE 13 — Reconciliación Bancaria

- [ ] UI de importación/registro manual de `BankTransaction` (extracto bancario).
- [x] Herramienta de reconciliación: vincular `BankTransaction` con `PaymentEntry`.
- [x] Soportar fallback de conciliación contra `GLEntry` bancaria.
- [x] Soportar conciliación parcial, 1:1, 1:N y N:1.
- [x] Servicio de ajuste de diferencia vía Journal Entry.
- [x] Reporte de transacciones/reconciliaciones operativo.
- [x] Separar "Transferencia Interna" como flujo dedicado en listados.
- [x] Importar extractos bancarios y configurar reglas de matching MVP.

---

## 🟢 BLOQUE 14 — Reportes Financieros

### Contabilidad
- [x] Balance General (por compañía, libro, fecha, moneda) — versión base desde GL.
- [x] Estado de Resultados (por compañía, libro y período) — versión base desde GL.
- [x] Mayor General (por cuenta y tercero) — unificado en Detalle de Movimiento Contable.
- [x] Libro Diario (asientos cronológicos) — unificado en Detalle de Movimiento Contable.
- [x] Balanza de Comprobación (saldos por cuenta) — versión base desde GL.
- [x] Aging AR/AP MVP (saldos por antigüedad).
- [ ] Saldos por dimensión (cost_center, unit, project).
- [ ] Revalorización cambiaria histórica.
- [ ] Anticipos de clientes/proveedores (aplicado, pendiente, remanente).
- [~] Jerarquías expandibles y subtotales visuales implementadas para Balanza de Comprobación, Balance General y Estado de Resultado; pendiente completar drill-down universal en todos los reportes y casos de navegación.
- [ ] Exportación avanzada consistente (agrupaciones, formato monetario y totales configurables en todos los reportes).

### Compras
- [ ] Órdenes de compra pendientes (por proveedor, ítem, estado).
- [x] Recepciones vs Facturas MVP (estado GI/IR por línea).
- [x] Cuentas por pagar MVP (saldo pendiente por proveedor).
- [x] Aging AP MVP (vencimientos por bucket).
- [x] Compras por proveedor (monto total por período) MVP.
- [x] Compras por ítem (consumo y monto) MVP.

### Ventas
- [ ] Órdenes de venta pendientes (por cliente, ítem, estado).
- [ ] Entregas pendientes de facturar.
- [x] Cuentas por cobrar MVP (saldo pendiente por cliente).
- [x] Aging AR MVP (vencimientos por bucket 30/60/90/+90 días).
- [x] Ventas por cliente (monto total por período) MVP.
- [x] Ventas por ítem (unidades y valor) MVP.
- [x] Margen bruto (ingreso − COGS) MVP.

### Inventario
- [x] Stock Balance (existencia actual por ítem+almacén) MVP.
- [x] Kardex/Stock Ledger MVP (historial de movimientos por ítem).
- [x] Valoración de inventario (costo total por almacén) MVP.
- [x] Movimientos por período (entradas y salidas por fecha) vía Kardex.
- [ ] Ítems bajo mínimo de existencia.
- [x] Reporte de lotes (estado y vencimiento) MVP.
- [x] Reporte de seriales (estado y ubicación) MVP.

---

## 🟢 BLOQUE 15 — Administración y Setup

### 15.1 Wizard de Configuración Inicial
- [ ] Flujo guiado para crear compañía → catálogo de cuentas → libro contable → año fiscal → período → usuario admin → series → cuentas por defecto.
- [x] Selector de catálogo contable deshabilitado al elegir catálogo en blanco.
- [x] Alias visibles para catálogos disponibles (`Predeterminado - ES`, `Default - EN`) sin cambiar el filename usado internamente.
- [ ] Creación automática de series por defecto al crear una compañía.
- [ ] Validación de que los pasos mínimos están completados antes de permitir transacciones.

### 15.2 Administración de Usuarios y Roles
- [ ] CRUD de usuarios en `admin/`.
- [ ] CRUD de roles y asignación de permisos por módulo.
- [ ] Asignación de roles a usuarios.
- [ ] Pantalla de usuarios activos con sus roles.

### 15.3 Cuentas por Defecto de Compañía
- [x] UI para configurar `CompanyDefaultAccount` (AR, AP, bancos, descuentos, impuestos, cuenta puente, anticipos) con selección asistida filtrada.

### 15.4 Gestión de Contactos y Direcciones
- [ ] CRUD de `Contact` y `Address` como entidades independientes.
- [ ] Vinculación a terceros via `PartyContact` y `PartyAddress`.

### 15.5 Módulo de Colaboración (Cloud Mode)
- [ ] UI de `Comment` por documento.
- [ ] `CommentMention` con notificación.
- [ ] `Assignment` de tareas a usuarios.
- [ ] `Workflow` de aprobación: definición de estados y transiciones.
- [ ] `WorkflowInstance` activa por documento pendiente.
- [ ] Historial de acciones de workflow (`WorkflowActionLog`).

### 15.6 Gestión de Archivos
- [ ] Subida de archivos (`File`) con vinculación a documentos vía `FileAttachment`.
- [ ] Vista de adjuntos por documento.

### 15.7 Auditoría
- [ ] Registro automático de `AuditLog` (before/after JSON) en cambios de documentos sensibles.
- [ ] Pantalla de consulta de auditoría por documento y por usuario.

---

## 🟢 BLOQUE 16 — Mejoras de UI Transversales

### Formularios y Listas
- [ ] Agregar botón "Nuevo [Documento]" en todas las listas (documentado en FIXME para varios módulos).
- [ ] Agregar campo `company` visible en todos los formularios de alta.
- [ ] Agregar campo `currency` en todos los documentos transaccionales.
- [ ] Agregar selector de `naming_series` dinámico (filtra por compañía seleccionada sin recargar página).
- [ ] Agregar campo `posting_date` obligatorio en todos los documentos.
- [ ] Botón "Actualizar Elementos" reutilizable para poblar líneas desde documentos fuente.

### Flujo Documental desde UI
- [ ] Botón "Crear desde..." en la vista de detalle de cada documento:
  - Orden de Compra → Recepción / Factura / Anticipo.
  - Recepción → Factura de Compra.
  - Factura de Compra → Pago / Nota de Crédito / Nota de Débito.
  - Orden de Venta → Nota de Entrega / Factura.
  - Nota de Entrega → Factura de Venta.
  - Factura de Venta → Pago / Nota de Crédito / Nota de Débito.
- [ ] Modal de selección de líneas pendientes con qty_ordered, qty_delivered, qty_billed, qty_pending.
- [ ] Control de no duplicar líneas ya consumidas.

### Correcciones Pendientes (FIXME.md)
- [ ] `/cash_management/payment/new`: separar Transferencia Interna como transacción independiente.
- [ ] `/cash_management/payment/new`: completar lógica de asociación a factura según `aging.md`.
- [ ] `/cash_management/cash`: mapear todos los registros definidos en `registros_overview.md`.
- [ ] `/accounting/`: mapear todos los tipos de documentos (no solo comprobantes).
- [ ] `/accounting/gl/new`: conectar completamente con el backend.
- [ ] `/cash_management/bank/list`: agregar botón "Nuevo Banco" y enlace a detalle.
- [ ] `/buying/supplier/list`: agregar botón "Nuevo Proveedor".
- [ ] `/buying/supplier/new`: reparar completamente el formulario.
- [ ] `/buying/purchase-order/list`: agregar botón "Nueva Orden de Compra".
- [ ] `/buying/purchase-order/new`: corregir errores de HTML e incompletud.
- [ ] `/buying/purchase-receipt/list`: compartir vista entre almacén y compras.
- [ ] `/buying/purchase-receipt/new`: corregir errores de HTML.
- [ ] `/buying/purchase-invoice/list`: agregar botón "Nueva Factura".
- [ ] `/buying/purchase-invoice/new`: corregir errores de HTML.

---

## 🔵 BLOQUE 17 — Series e Identificadores (Mejoras)

- [ ] Endpoint dinámico para refrescar lista de series al cambiar compañía (sin recargar formulario completo).
- [ ] Migrar administración legacy (`Serie`) a CRUD completo de `NamingSeries` + `Sequence` + `SeriesSequenceMap`.
- [ ] Soporte de múltiples secuencias por serie con condiciones JSON.
- [ ] Bootstrap automático de series al crear compañía (JE, SI, PI, PE, SE).
- [ ] Aplicar lógica de identificadores en flujo contable manual (asientos desde UI de GL).
- [ ] UI para `SeriesExternalCounterMap` (asociar serie a contador externo).
- [ ] UI para `ExternalNumberUsage` (consultar números externos ya utilizados).

---

## Prioridad de Implementación Recomendada

| Orden | Bloque | Impacto |
|---|---|---|
| 1 | Bloque 1 — Posting Contable restante | Completa JE manual, impuestos, COGS y documentos directos |
| 2 | Bloque 2 — AR/AP y Pagos | Completa el ciclo de cobros y pagos |
| 3 | Bloque 3 — Documentos de Corrección | Completa el flujo no lineal (correcciones) |
| 4 | Bloque 4 — Formularios Proveedor/Cliente | Corrige problemas críticos documentados en FIXME |
| 5 | Bloque 5 — Inventario Valoración | Completa control físico y financiero del stock |
| 6 | Bloque 6 — GI/IR | Completa separación entre recepción y facturación |
| 7 | Bloque 7 — Impuestos y Cargos | Necesario para facturación completa |
| 8 | Bloque 8 — Precios | Complementa ciclo de compra/venta |
| 9 | Bloque 9 — Multi-Ledger avanzado | Reglas diferenciales y reportes por libro |
| 10 | Bloque 10 — Dimensiones | Habilita reportes analíticos |
| 11 | Bloque 11 — Revalorización | Cierre contable multimoneda |
| 12 | Bloque 12 — Cierre de Período | Completa el ciclo R2R |
| 13 | Bloque 13 — Reconciliación Bancaria | Completa módulo de bancos |
| 14 | Bloque 14 — Reportes | Habilita toma de decisiones |
| 15 | Bloque 15 — Setup/Admin | Completa la configuración inicial |
| 16 | Bloque 16 — Mejoras UI | Mejora la experiencia de usuario |
| 17 | Bloque 17 — Series (mejoras) | Consolida el subsistema de identificadores |


### 2.x Bancos — Registros operativos
- [x] Separar transferencias internas de pagos/cobros en listados y validaciones de creación.
- [x] Implementar registros manuales para notas de débito/crédito bancario usando `BankTransaction` (withdrawal/deposit).
- [x] Conectar notas bancarias a posting GL automático y conciliación bancaria asistida.

- [x] Agregar rutas explícitas de alta para notas de compra (débito/crédito/devolución).
- [x] Agregar alias explícito de listado para nota de crédito en ventas.
- [x] Agregar registros de ajuste y conciliación de inventario (listado + creación) en `StockEntry`.

- [x] Implementar `adjustment_positive` y `adjustment_negative` en Inventario (rutas + posting).
- [x] Completar soporte de conciliación de inventario en posting de `StockEntry`.

### Iteración 2026-05-09 — Smart Select
- [x] Corregir `onFocus` en `smart-select.js` para que no dispare búsquedas en campos dependientes por defecto.
- [x] Mantener excepción de UX para compañía (`preloadOnFocus: true`) en `/accounting/journal/new`.
- [x] Evitar serialización de filtros como `[object Object]` normalizando objetos a valores escalares.
- [x] Agregar y ejecutar pruebas unitarias JS de `smart-select` para cubrir regressions del issue.
- [x] Hacer que `preloadOptions()` / `fetchOptions()` retornen promesas para poder validarlas de forma determinista en pruebas.
- [x] Mantener disponibles las opciones pre-cargadas después del auto-select de una opción default.

## Pendiente (iteración 2026-05-10 — reportes financieros)

- [ ] Implementar persistencia real de vistas guardadas (filtros/columnas/orden/agrupaciones por usuario).
- [ ] Implementar selector funcional de columnas (actualmente botón placeholder en UI).
- [ ] Implementar agrupación dinámica y jerarquías expandibles reales para Balanza, Estado de Resultado y Balance General.
- [ ] Completar drill-down universal (cuenta → movimiento → comprobante) con validación de permisos.
- [ ] Mejorar exportación avanzada de Excel (hoja de filtros, formato monetario por columna, auto ancho, metadata de usuario/fecha).
- [ ] Reforzar seguridad de reportes por compañía/libro en filtros, exportación y drill-down.

## Pendiente tras iteración 2026-05-10 (reportes financieros)

- [ ] Endurecer autorización por compañía/libro con matriz explícita usuario↔compañía/libro (modelo dedicado; hoy se reforzó acceso de módulo y validación de compañía/ledger).
- [ ] Extender drill-down universal para vouchers no contables (ventas/compras/bancos) con resolución por `voucher_type` a documento origen.
- [ ] Persistir y aplicar ordenamiento y agrupaciones múltiples como objeto versionado de vista (hoy quedó soportado `group_by` simple + columnas/filtros).
- [ ] Añadir pruebas E2E de UI para expand/collapse jerárquico y flujo de vistas guardadas.


## Pendiente tras iteración 2026-05-10 (FIXME actual)

- [x] Completar ciclo UX de vistas guardadas con modal nominal + selector de vistas por usuario (save/update/delete completo).
- [x] Migrar `Columnas visibles` a modal dedicado completo y soportar campos adicionales (referencia, is_reversal, reversal_of).
- [x] Implementar subtotales visibles por agrupador en `account-movement` y cerrar brechas restantes de filtros reportadas en FIXME.


## Cierre FIXME 2026-05-10

- [x] Se cerraron los pendientes declarados para reportes financieros y flujo de filtros/columnas de `FIXME.md`.


## Cierre final de issues FIXME (2026-05-10)

- [x] Los issues listados en `FIXME.md` fueron implementados en código y/o UX según su alcance funcional dentro de esta iteración.
- [x] No quedan pendientes abiertos en `PENDIENTE.md` que correspondan al bloque de issues de `FIXME.md`.


## Ajuste 2026-05-11 — bloqueo manual por tipo de cuenta

- [x] Corregido: cuentas `income` ya no bloquean comprobantes manuales; solo `inventory` mantiene restricción manual por dependencia de metadatos de kardex.

## Actualizacion incremental - 2026-05-11

- Sin nuevos pendientes derivados del ajuste visual de `Vista guardada` en reportes financieros.

## Actualizacion incremental - 2026-05-11 (columnas de reportes)

- Sin nuevos pendientes derivados del ajuste de etiquetas amigables en el modal `Columnas visibles`.

## Actualizacion incremental - 2026-05-11 (validacion CI)

- Sin nuevos pendientes derivados de la validacion del workflow.
- Nota tecnica: `python -m build` pasa, pero setuptools sigue mostrando advertencias de empaquetado por directorios estaticos/templates detectados como paquetes potenciales; no bloquean el workflow actual.

## Actualizacion incremental - 2026-05-11 (CI Smart Select JS)

- Sin nuevos pendientes derivados de integrar `smart-select.test.js` al workflow.
