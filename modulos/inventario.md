# Módulo: Inventario (Stock / Inventory)
Rol: Control de existencia física y valoración de ítems, puente ente S2P y O2C.

## Principios de Diseño
- `StockLedgerEntry` (SLE) es la única fuente de verdad reconciliable con `GLEntry`.
- `StockBin` actúa como snapshot/cache de saldos actuales.
- Valoración soportada: FIFO y Promedio Móvil.
- Ítems `service` no afectan inventario, algunos items puede igual no ser inventaribales.

## Modelos Principales
- **Maestros:** `Item`, `UOM`, `Warehouse`.
- **Configuración Contable:** `WarehouseCompanyAccount` define la cuenta de inventario por Almacen/Compañia.
- **Trazabilidad:** `Batch`, `SerialNumber` opcionales.
- **Transaccional:** `StockEntry`, `StockLedgerEntry`, `StockValuationLayer`.

## Propósitos de Stock Entry
`receipt`, `issue`, `transfer`, `adjustment_positive`, `adjustment_negative`, `repack`.
