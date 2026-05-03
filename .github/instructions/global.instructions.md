---
applyTo: "**/*.py"
---

Este resumen condensa los requisitos para que puedan usarse como contexto recurrente en cada iteración de un agente IA.

## Objetivo general

Construir un motor contable modular que soporte:
- General Ledger (`GLEntry`) como fuente única de verdad.
- Multi-compañía y aislamiento por `company`/`entity`.
- Multi-moneda real sin restricciones por party/cuanta.
- Multi-libro contable con `Book` + `GLEntry.ledger_id`.
- Documentos transaccionales basados en `DocBase` / `BaseTransaccion`.

## Principios clave

- Usa patrón documento + líneas para transacciones.
- Usa `voucher_type` y `voucher_id` para trazabilidad contable.
- Usa `reference_type` y `reference_id` para vínculos transversales.
- No elimines registros contables; usa `docstatus`, reversión y soft delete.
- No uses `created` para lógica contable; usa `posting_date`.
- Prefiere enums/flags sobre tablas separadas cuando el comportamiento cambia por tipo.

## Campos transaccionales obligatorios

- `docstatus` (0 draft, 1 submitted, 2 cancelled)
- `posting_date`
- `document_date`
- `company` y/o `entity` según el módulo
- `transaction_currency`, `base_currency`, `exchange_rate` para transacciones monetarias
- `is_reversal`, `reversal_of`
- `voucher_type`, `voucher_id`

## Reglas de multi-compañía y multi-libro

- Cada registro transaccional debe tener company scope.
- Las consultas deben filtrar por `company` o `entity` para evitar filtraje intercompañía.
- Un solo documento puede generar múltiples GL lines por libro activo.
- No dupliques un registro operativo por libro.

## Inventario y unidades de medida

- `item_type` y `is_stock_item` deben determinar si impacta inventario.
- `service` nunca puede ser stock item.
- Las conversiones de UOM son por ítem (`ItemUOMConversion`), no globales.
- El campo real de UOM base en `Item` es `default_uom`.
- `has_batch = true` exige lote; `has_serial_no = true` exige serial.
- Una vez usadas las configuraciones de ítem, son inmutables.

## Series e identificadores

- Usa `NamingSeries`, `Sequence` y `SeriesSequenceMap`.
- Resuelve tokens con `posting_date`, nunca `created`.
- Usa los helpers reales de `cacao_accounting/database/helpers.py`:
  - `resolve_naming_series_prefix`
  - `get_next_sequence_value`
  - `format_sequence_value`
  - `generate_identifier`
- Mantén la generación de identificadores auditable.

## Terceros, AR/AP y conciliación

- AR/AP son proyecciones del GL, no subledgers independientes.
- Requiere `party_type` y `party_id` en cuentas AR/AP y pagos.
- Soporta asignaciones parciales y pagos a múltiples facturas.
- Los saldos históricos dependen de fechas de posting y allocation.

## Transversalidad y colaboración

- Usa el patrón `reference_type` + `reference_id` para:
  - comentarios
  - archivos adjuntos
  - asignaciones
  - workflows
  - conciliaciones
- No crees tablas de comentarios o archivos por cada módulo.

## Dominios existentes en el esquema

Estos conceptos ya están presentes en el modelo actual y deben seguirse:
- `Book`, `GLEntry`, `DimensionType`, `DimensionValue`, `GLEntryDimension`
- `Tax`, `TaxTemplate`, `TaxTemplateItem`
- `PriceList`, `ItemPrice`
- `Reconciliation`, `ReconciliationItem`
- `ExchangeRevaluation`, `ExchangeRevaluationItem`
- `PeriodCloseRun`, `PeriodCloseCheck`

## Qué evitar

- No separar AR/AP del GL.
- No usar `company_id` cuando el esquema usa `company`/`entity`.
- No usar `created` o `created_at` como base para numeración o fechas contables; usa `posting_date`.
- No duplicar lógica contable en múltiples tablas.
- No implementar contabilidad fuera del GL.

## Referencias de `task/`

- `task/desgin_principes.md` → principios arquitectónicos y contables.
- `task/series.md` → series e identificadores.
- `task/uoms.md` → control de ítems, UOM, batch y serial.
- `task/third_party_accounting` → AR/AP, terceros y saldos.
- `task/checklist.md` → prioridades y dominio mínimo viable.
- `task/advanced_accounting.md` → GI/IR, revalorización, cierre y multi-ledger.
- `task/accouting_estructure.md` → dimensiones, pricing, mappings, reconciliación.

---

Usa este documento como contexto principal cuando un agente necesite entender rápidamente las reglas de negocio y las expectativas de arquitectura del proyecto.