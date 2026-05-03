# Módulo: Inventario (Stock / Inventory)

## Rol en el sistema

Módulo operativo que controla la existencia física y la valoración de ítems.
Genera movimientos de inventario y actualiza el costo promedio o FIFO.
Se integra con Compras (entrance) y Ventas (exit).

---

## Principios de diseño

- El `StockLedgerEntry` es la única fuente de verdad de existencia y costo.
- No se eliminan `StockLedgerEntry`; se reversan.
- `StockBin` es un snapshot de saldo actual (cache para performance).
- `StockValuationLayer` registra el costo por unidad en cada movimiento.
- Soporte nativo para Lotes (`Batch`) y Números de Serie (`SerialNumber`).
- Los ítems tipo `service` nunca afectan inventario.

---

## Modelos disponibles en base de datos

| Modelo | Tabla | Descripción |
|---|---|---|
| `Item` | `item` | Ítem o servicio. |
| `UOM` | `uom` | Unidad de medida. |
| `ItemUOMConversion` | `item_uom_conversion` | Conversión de UOM por ítem. |
| `Warehouse` | `warehouse` | Almacén. Unique global en `code`. |
| `Batch` | `batch` | Lote de ítem inventariable. |
| `SerialNumber` | `serial_number` | Número de serie por ítem. |
| `StockEntry` | `stock_entry` | Movimiento de inventario. Header. |
| `StockEntryItem` | `stock_entry_item` | Líneas del movimiento. |
| `StockLedgerEntry` | `stock_ledger_entry` | Libro mayor de inventario. Auto-generado. |
| `StockBin` | `stock_bin` | Saldo actual por ítem+almacén (cache). |
| `StockValuationLayer` | `stock_valuation_layer` | Capa de valuación por movimiento. |
| `StockBalanceSnapshot` | `stock_balance_snapshot` | Snapshot histórico de saldo. |

---

## Clasificación de ítems

```
Item
├── type = service         → nunca afecta inventario
└── type = goods
    ├── is_stock_item = True   → afecta StockLedgerEntry y StockBin
    └── is_stock_item = False  → gasto directo, no afecta inventario
```

**Atributos adicionales del ítem:**
- `has_batch` — requiere lote en cada movimiento.
- `has_serial_no` — requiere número de serie en cada movimiento.
- `valuation_method` — FIFO o Moving Average. Inmutable una vez hay transacciones.
- `default_uom` — unidad de medida base. El ledger siempre usa la unidad base.

---

## UOM y Conversiones

- Conversiones definidas por ítem (`ItemUOMConversion`), no globales.
- El `StockLedgerEntry` siempre registra en unidad base.
- La conversión se aplica al ingresar un documento en unidad alternativa.

---

## Movimientos de Inventario (Stock Entry)

**Propósitos soportados:**

| Purpose | Descripción |
|---|---|
| `receipt` | Entrada de mercancía (sin PO). |
| `issue` | Salida de inventario (consumo, pérdida). |
| `transfer` | Traslado entre almacenes. |
| `manufacture` | Entrada por producción. |
| `repack` | Transformación de ítem. |
| `adjustment_positive` | Ajuste positivo por conteo físico o corrección. |
| `adjustment_negative` | Ajuste negativo por conteo físico, merma o corrección. |

**Flujo:**
```
StockEntry (submitted)
    → StockLedgerEntry (inmutable)
        → StockBin (actualizado)
        → StockValuationLayer (costo registrado)
        → GLEntry (cuenta de inventario ↔ contrapartida)
```

**Reversión:**
- No se eliminan. Se crea un `StockEntry` de reverso con `is_reversal=True` y `reversal_of`.

### Flujo no lineal y realista (con correcciones)

```
Movimiento de stock
   ├─→ Error de UOM
   │    └─→ reversión + movimiento corregido
   ├─→ Error de cantidad
   │    └─→ ajuste positivo o ajuste negativo
   ├─→ Error de almacén
   │    └─→ transferencia correctiva entre bodegas
   ├─→ Error de costo
   │    └─→ ajuste de valuación documentado
   ├─→ Devolución
   │    └─→ movimiento inverso con trazabilidad al origen
   └─→ Diferencia de conteo físico
    └─→ stock reconciliation con justificación
```

---

## Stock Ledger Entry

Generado automáticamente. Nunca se crea manualmente.

**Campos clave:**
- `item_code` — ítem.
- `warehouse` — almacén.
- `posting_date` — fecha contable.
- `actual_qty` — cantidad del movimiento (positiva = entrada, negativa = salida).
- `qty_after_transaction` — existencia acumulada después del movimiento.
- `incoming_rate` — costo unitario del ingreso.
- `valuation_rate` — tasa de valuación acumulada.
- `voucher_type` / `voucher_id` — referencia al documento origen.
- `batch_no`, `serial_no` — trazabilidad.

---

## Valuación de Inventario

### FIFO (First In First Out)
- Cada `StockValuationLayer` mantiene costo y cantidad de la capa.
- Las salidas consumen las capas más antiguas primero.
- El costo de cada salida puede variar.

### Moving Average
- El costo promedio se recalcula en cada entrada.
- Las salidas usan siempre el costo promedio vigente.

**Regla:** el método es inmutable una vez se registró la primera transacción del ítem.

### Impacto de impuestos y cargos en el costo

- El sistema debe soportar cargos/impuestos que:
    - se capitalizan al costo de inventario, o
    - se reconocen como gasto sin afectar costo del producto.
- Cuando se capitalizan, el sistema debe prorratear por regla definida (cantidad, peso/volumen, valor).
- Cuando no se capitalizan, no deben alterar `valuation_rate` ni `StockValuationLayer`.
- Todo ajuste de costo por cargos capitalizados debe ser auditable y reversible.

---

## Lotes (Batch)

- Controlado por `has_batch=True` en el ítem.
- Obligatorio en recepciones y salidas.
- `Batch` es inmutable después de uso.
- Campos relevantes: `expiry_date`, `manufacturing_date`.

---

## Números de Serie (SerialNumber)

- Controlado por `has_serial_no=True` en el ítem.
- Un `SerialNumber` existe por unidad física.
- Inmutable después de uso.
- `serial_status` — available, delivered, inactive.
- `warehouse` — almacén actual del serial.

---

## Almacenes (Warehouse)

- `code` es único globalmente (para soporte de FK desde `gl_entry` y otros módulos).
- Relación `company` + `code` también es única (constraint `uq_warehouse_code`).
- Soporte jerárquico: `parent_warehouse` + `is_group`.
- Almacenes grupo no tienen stock; son nodos de agrupación.

---

## Stock Reconciliation

**Propósito:**
- Cuadrar existencias físicas vs existencias en sistema.
- Ajustar diferencias de cantidad y/o valuación.

**Tipos:**
- Ajuste de cantidad.
- Ajuste de valuación.
- Ajuste positivo por sobrante físico.
- Ajuste negativo por faltante, merma o daño.

---

## Errores operativos y políticas de corrección

### Error de unidad de medida (UOM)

- Se corrige por reversión del movimiento incorrecto y nuevo movimiento correcto.
- Si hay impacto en compras/ventas, debe generarse documento de corrección encadenado.
- Toda corrección debe recalcular `StockValuationLayer`.

### Error de precio/costo

- Si el error proviene de compra, se corrige vía documento financiero en Compras.
- Si el error afecta valuación, se registra ajuste de valuación explícito.
- No se modifica en sitio el costo histórico de movimientos contabilizados.

### Auditabilidad obligatoria

- Todo ajuste requiere motivo obligatorio y referencia al documento origen.
- Debe registrarse usuario, fecha, tipo de error y diferencia de cantidad/valor.
- Lotes y seriales deben conservar trazabilidad completa antes y después del ajuste.

---

## Integraciones con otros módulos

| Módulo | Relación |
|---|---|
| Compras | `PurchaseReceipt` genera `StockLedgerEntry` (entrada). |
| Ventas | `DeliveryNote` genera `StockLedgerEntry` (salida). |
| Contabilidad | Todo movimiento de inventario genera `gl_entry`. |
| Compras/Contabilidad | Cargos capitalizables actualizan costo; no capitalizables se van a gasto. |

---

## Reportería requerida

| Reporte | Descripción |
|---|---|
| Stock Balance | Existencia actual por ítem+almacén. |
| Stock Ledger | Historial de movimientos por ítem. |
| Valoración de inventario | Costo total del inventario por almacén. |
| Movimientos por período | Entradas y salidas por fecha. |
| Ítems bajo mínimo | Ítems con existencia por debajo del mínimo definido. |
| Reporte de lotes | Lotes por estado y vencimiento. |
| Reporte de seriales | Seriales por estado y ubicación. |

---

## Casos que debe soportar

- Ítems con lote y serial simultáneamente.
- Traslados entre almacenes de distintas compañías.
- Devoluciones parciales a proveedor o de cliente.
- Ajustes positivos por sobrante físico.
- Ajustes negativos por faltante o deterioro.
- Corrección por UOM equivocada en movimientos de stock.
- Corrección por costo equivocado con impacto en valuación.
- Prorrateo de flete capitalizable sobre múltiples ítems en una recepción.
- Cargo no capitalizable (ej: gasto logístico) sin impacto en costo unitario.
- Ajuste de inventario por diferencia de conteo físico.
- Recalculo de valuación histórica reproducible.
- Existencia negativa temporal controlada (solo en modos permitidos).
