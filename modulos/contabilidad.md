# Módulo: Contabilidad (Accounting)
Rol: Núcleo central del sistema, implementa **Records to Reports (R2R)**.

## Principios de Diseño
- `gl_entry` es la única fuente de verdad financiera.
- Multi-ledger: Se genera un asiento por cada libro (`Book`) activo.
- Correcciones siempre vía reversión o ajuste; prohibido borrar.
- `posting_date` es la fecha oficial para efectos contables.

## Modelos Principales
- **Estructura:** `Entity`, `Book`, `FiscalYear`, `AccountingPeriod`.
- **Catálogo:** `Accounts`, `CostCenter`, `Unit`, `Project`.
- **Transaccional:** `ComprobanteContable` (JE), `GLEntry`.
- **Mapeo:** `ItemAccount`, `PartyAccount`, `CompanyDefaultAccount`.
- **Configuración:** `Currency`, `ExchangeRate`, `Tax`, `TaxTemplate`.

## Flujo Operativo
Transacción Operativa → `GLEntry` (por cada libro) → Revalorización → Cierre de Período → Reportes.
