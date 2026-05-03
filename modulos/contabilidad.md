# Módulo: Contabilidad (Accounting)

## Rol en el sistema

Módulo central del sistema. Todos los módulos operativos convergen aquí.
Es la implementación del flujo **Records to Reports (R2R)**.

---

## Principios de diseño

- `gl_entry` es la única fuente de verdad financiera.
- Cada transacción genera una `gl_entry` por cada libro activo (`book`).
- No se eliminan registros contables; se reversan.
- `posting_date` es la fecha contable oficial, nunca `created`.
- Soporte nativo multi-ledger, multi-moneda y multi-compañía.
- Correcciones siempre por documentos aditivos (notas, ajustes, reversión), nunca por edición destructiva.

---

## Modelos disponibles en base de datos

| Modelo | Tabla | Descripción |
|---|---|---|
| `Entity` | `entity` | Compañía contable. Toda transacción tiene `company`. |
| `Accounts` | `accounts` | Catálogo de cuentas por entidad. |
| `Book` | `book` | Libro contable (Fiscal, NIIF, etc.). |
| `FiscalYear` | `fiscal_year` | Año fiscal por entidad. |
| `AccountingPeriod` | `accounting_period` | Período contable con soporte de cierre. |
| `CostCenter` | `cost_center` | Dimensión analítica por entidad. |
| `Unit` | `unit` | Unidad de negocio / sucursal. |
| `Project` | `project` | Proyecto como dimensión analítica. |
| `ComprobanteContable` | `comprobante_contable` | Asiento contable manual (Journal Entry). |
| `ComprobanteContableDetalle` | `comprobante_contable_detalle` | Líneas del comprobante. |
| `GLEntry` | `gl_entry` | Registro del mayor general, auto-generado. |
| `GLEntryDimension` | `gl_entry_dimension` | Dimensiones adicionales por asiento. |
| `DimensionType` | `dimension_type` | Tipos de dimensión personalizables. |
| `DimensionValue` | `dimension_value` | Valores por dimensión. |
| `LedgerMappingRule` | `ledger_mapping_rule` | Reglas entre libros contables. |
| `ExchangeRate` | `exchange_rate` | Tasas de cambio históricas. |
| `ExchangeRevaluation` | `exchange_revaluation` | Revalorización de moneda extranjera. |
| `ExchangeRevaluationItem` | `exchange_revaluation_item` | Detalle por cuenta/moneda revalorizada. |
| `PeriodCloseRun` | `period_close_run` | Proceso de cierre de período. |
| `PeriodCloseCheck` | `period_close_check` | Verificaciones de cierre. |
| `ItemAccount` | `item_account` | Mapeo de cuentas por ítem. |
| `PartyAccount` | `party_account` | Mapeo de cuentas por tercero. |
| `CompanyDefaultAccount` | `company_default_account` | Cuentas por defecto de compañía. |
| `Tax` | `tax` | Definición de impuesto. |
| `TaxTemplate` | `tax_template` | Plantilla de impuestos por documento. |
| `TaxTemplateItem` | `tax_template_item` | Líneas de impuesto en plantilla. |
| `AccountBalanceSnapshot` | `account_balance_snapshot` | Snapshot de saldos para performance. |

---

## Documentos del módulo

### Journal Entry (Comprobante Contable)

**Tipos soportados:**
- Asiento estándar
- Apertura
- Nota de crédito contable
- Nota de débito contable
- Contra asiento
- Ajuste
- Reversión

**Ciclo de vida:**
```
Draft → Submitted → Cancelled (vía reversión)
```

**Reglas:**
- Debe balancear por libro: `SUM(debit) == SUM(credit)`.
- Un documento puede generar múltiples `gl_entry` (una por libro activo).
- Si hay error posterior a contabilización, se corrige con ajuste o reversión.

---

### GL Entry

Generado automáticamente. Nunca se crea manualmente desde UI.

**Campos clave:**
- `posting_date`, `company`, `ledger_id`
- `account_id`, `account_code`
- `debit`, `credit` (moneda base)
- `debit_in_account_currency`, `credit_in_account_currency` (moneda original)
- `exchange_rate`
- `voucher_type`, `voucher_id`
- `party_type`, `party_id`
- `cost_center_code`, `unit_code`, `project_code`

**Reglas de corrección:**
- Ninguna corrección edita una `gl_entry` existente.
- Toda corrección crea nuevas `gl_entry` enlazadas al origen.
- El sistema debe reconstruir saldos históricos en cualquier fecha.

---

## Flujos de negocio cubiertos

### R2R — flujo base

```
Transacción operativa
    → GL Entry (por cada libro activo)
        → Revalorización
            → Cierre de período
                → Estados financieros
```

### R2R realista (no lineal con correcciones)

```
Transacción operativa
   ├─→ contabilización inicial
   ├─→ detección de error (precio/UOM/impuesto/cuenta)
   │    ├─→ nota de crédito / nota de débito
   │    ├─→ reversión y recreación
   │    └─→ ajuste manual controlado
   ├─→ conciliación (AR/AP/Bancos/GI-IR)
   ├─→ revalorización por moneda
   └─→ cierre de período con validaciones
```

---

## Anticipos (totales y parciales)

### Anticipos de cliente

- Se registran antes o durante el ciclo de venta.
- Pueden cubrir total o parcial de una factura futura.
- Se registran inicialmente como pasivo (anticipo de cliente).
- Se aplican contra factura por `PaymentReference` y `allocation_date`.

### Anticipos a proveedor

- Se registran antes o durante el ciclo de compra.
- Pueden cubrir total o parcial de una factura futura.
- Se registran inicialmente como activo (anticipo a proveedor).
- Se aplican contra factura por `PaymentReference` y `allocation_date`.

### Reglas contables de anticipos

- La aplicación de anticipo reduce `outstanding_amount` del documento objetivo.
- Si hay remanente, queda saldo a favor del tercero para aplicación futura.
- Debe soportar aplicación de un anticipo a múltiples facturas y viceversa.
- Debe conservar trazabilidad temporal: el efecto inicia en `allocation_date`.

---

## Dimensiones analíticas

Dos capas:

1. Primer nivel en `gl_entry`: `cost_center_code`, `unit_code`, `project_code`.
2. Extensión dinámica vía `gl_entry_dimension`.

---

## Multi-Ledger

- `Book` define libros paralelos (Fiscal, NIIF, etc.).
- `LedgerMappingRule` define diferencias por libro.
- Toda transacción impacta todos los libros activos.

---

## Multimoneda

- `gl_entry` guarda moneda base y moneda original.
- `ExchangeRate` guarda tipo de cambio histórico.
- `ExchangeRevaluation` genera ajustes sin alterar transacciones base.

---

## Impuestos, otros costos y otros gastos

- Los impuestos/cargos de documentos operativos deben soportar:
    - monto fijo,
    - porcentaje,
    - aditivo (suma),
    - deductivo (resta).
- Cada línea de impuesto/cargo debe definir cuenta contable y naturaleza (impuesto/costo/gasto).
- Debe existir trazabilidad de la base de cálculo y del signo aplicado.

### Capitalización vs gasto

- Para compras e inventario, cada cargo debe indicar si:
    - se capitaliza al costo de inventario, o
    - se reconoce como gasto del período.
- Cargos capitalizados incrementan costo de inventario y COGS futuro.
- Cargos no capitalizados se registran en cuenta de gasto sin alterar costo del producto.

### Regla de prorrateo

- Si un cargo se capitaliza, debe prorratearse entre líneas por regla configurable (cantidad, peso/volumen, valor).
- El prorrateo debe ser consistente entre documento operativo, inventario y GL.

---

## Cierre de período

`PeriodCloseRun` ejecuta checks (`PeriodCloseCheck`):
- GL balanceado.
- AR/AP conciliado.
- GI/IR conciliado.
- Revaluaciones aplicadas.
- Inventario consistente.

**Regla:** no se contabiliza en período cerrado (`is_closed=True`).

**Excepción controlada:**
- Error detectado tras cierre: corregir en siguiente período abierto o reapertura autorizada con bitácora.

---

## Auditabilidad y control interno

- Toda corrección debe registrar usuario, fecha, motivo y documento origen.
- Toda corrección debe tener trazabilidad bidireccional.
- Debe existir evidencia de aprobación para ajustes sensibles.
- Prohibido alterar histórico sin documento de corrección.

---

## Matriz de contabilización

Reglas generales de uso:

- Esta matriz se aplica por cada `ledger_id` activo.
- Toda contabilización usa `posting_date` del documento.
- En multimoneda, el GL guarda moneda base y moneda original.
- Los nombres de cuenta son conceptuales; la cuenta real se resuelve por `ItemAccount`, `PartyAccount` y `CompanyDefaultAccount`.

| Escenario | Débito | Crédito | Regla de negocio |
|---|---|---|---|
| Venta facturada estándar | Cuentas por cobrar (AR) | Ingreso de ventas | Impuestos y descuentos se calculan en líneas separadas. |
| Impuesto de venta aditivo (fijo o %) | Cuentas por cobrar (AR) | Impuesto por pagar / trasladado | Suma al total de factura. |
| Impuesto/cargo de venta deductivo | Descuento/cargo deductivo (según naturaleza) | Cuentas por cobrar (AR) | Resta al total de factura. |
| Flete cobrado al cliente | Cuentas por cobrar (AR) | Ingreso por flete/recuperación | Puede ir en la misma factura o ajuste separado. |
| Nota de crédito de venta | Devoluciones y descuentos sobre ventas / impuesto correspondiente | Cuentas por cobrar (AR) | Reduce ingreso y saldo del cliente. |
| Nota de débito de venta | Cuentas por cobrar (AR) | Ingreso adicional / impuesto correspondiente | Incrementa saldo del cliente. |
| Cobro de factura (pago final) | Banco/Caja | Cuentas por cobrar (AR) | Aplicación total o parcial por `PaymentReference`. |
| Anticipo de cliente recibido | Banco/Caja | Anticipo de cliente (pasivo) | No impacta ingreso hasta facturar/aplicar. |
| Aplicación de anticipo de cliente a factura | Anticipo de cliente (pasivo) | Cuentas por cobrar (AR) | Reduce `outstanding_amount` desde `allocation_date`. |
| Compra facturada estándar (no inventariable) | Gasto/consumo + impuesto acreditable | Cuentas por pagar (AP) | Si aplica GI/IR, se compensa en líneas separadas. |
| Compra de inventario facturada | Inventario + impuesto acreditable | Cuentas por pagar (AP) | Costo inicial según precio del documento. |
| Impuesto de compra aditivo (fijo o %) | Inventario o gasto/impuesto acreditable | Cuentas por pagar (AP) | Suma al total según configuración fiscal. |
| Impuesto/cargo de compra deductivo | Cuentas por pagar (AP) | Descuento/cargo deductivo (según naturaleza) | Resta al total de factura. |
| Flete/costo capitalizable en compra | Inventario (prorrateado por regla) | Cuentas por pagar (AP) / Proveedor de servicio | Incrementa costo del producto y valuación. |
| Flete/gasto no capitalizable | Gasto logístico/flete | Cuentas por pagar (AP) / Proveedor de servicio | No modifica costo unitario del inventario. |
| Nota de crédito de proveedor | Cuentas por pagar (AP) | Inventario/gasto/impuesto según origen | Reduce saldo AP y revierte impacto económico. |
| Nota de débito de proveedor | Inventario/gasto/impuesto según origen | Cuentas por pagar (AP) | Incrementa saldo AP por ajustes posteriores. |
| Pago a proveedor (pago final) | Cuentas por pagar (AP) | Banco/Caja | Aplicación total o parcial por `PaymentReference`. |
| Anticipo a proveedor entregado | Anticipo a proveedor (activo) | Banco/Caja | No impacta gasto/inventario hasta aplicar. |
| Aplicación de anticipo a proveedor | Cuentas por pagar (AP) | Anticipo a proveedor (activo) | Reduce `outstanding_amount` desde `allocation_date`. |
| Recepción de inventario con GI/IR | Inventario | GI/IR | Separación entre recepción e invoice. |
| Factura de proveedor con GI/IR | GI/IR | Cuentas por pagar (AP) | Debe limpiar GI/IR al conciliar. |
| Entrega de inventario (COGS) | Costo de ventas (COGS) | Inventario | Costo según `StockValuationLayer` (FIFO/Moving Average). |
| Ajuste inventario positivo | Inventario | Cuenta de ajuste de inventario (ganancia) | Diferencia de conteo a favor. |
| Ajuste inventario negativo | Cuenta de ajuste de inventario (pérdida) | Inventario | Faltante, merma o daño. |
| Revalorización cambiaria con pérdida | Pérdida por diferencia cambiaria | Cuenta de activo/pasivo revaluada | Ajuste al cierre o fecha de corte. |
| Revalorización cambiaria con ganancia | Cuenta de activo/pasivo revaluada | Ganancia por diferencia cambiaria | Ajuste al cierre o fecha de corte. |
| Reversión de documento contabilizado | Cuentas del asiento inverso | Cuentas del asiento original | No elimina histórico; crea asiento espejo. |

### Reglas específicas para impuestos y cargos

- Cálculo fijo: monto absoluto por línea o por documento.
- Cálculo porcentual: base configurable (neto de línea, neto documento, base previa).
- Comportamiento aditivo: incrementa total del documento.
- Comportamiento deductivo: reduce total del documento.
- Todo impuesto/cargo requiere cuenta contable obligatoria.
- En compras, todo cargo debe indicar `capitalizable=True/False`.

### Reglas de prorrateo para cargos capitalizables

- Por cantidad: distribución proporcional a unidades.
- Por valor: distribución proporcional al neto de cada línea.
- Por peso/volumen: distribución logística para fletes y seguro.
- El método seleccionado debe guardarse en el documento para auditoría y recalculo.

### Reglas de validación de la matriz

- Cada evento debe balancear en cada libro (`debit == credit`).
- La matriz debe respetar períodos abiertos/cerrados.
- No se permiten asientos directos que rompan trazabilidad de documento origen.

---

## Reportería requerida

| Reporte | Descripción |
|---|---|
| Balance General | Por compañía, libro, fecha y moneda. |
| Estado de Resultados | Por compañía, libro y período. |
| Mayor General | Por cuenta y tercero. |
| Libro Diario | Asientos cronológicos. |
| Balanza de Comprobación | Saldos por cuenta. |
| Aging AR/AP | Saldos por antigüedad de terceros. |
| Saldos por dimensión | cost_center, unit, project. |
| Revalorización | Diferencias cambiarias históricas. |
| Anticipos de clientes/proveedores | Aplicado, pendiente y remanente. |

---

## Restricciones no negociables

- No borrar `gl_entry`.
- No usar `created` para lógica financiera.
- No acoplar módulos externos al GL sin voucher pattern.
- No restringir moneda por entidad, tercero o cuenta.
- No corregir errores editando documentos contabilizados; usar ajuste, nota o reversión.
