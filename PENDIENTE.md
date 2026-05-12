# PENDIENTE — Cacao Accounting

Este documento registra lo que queda pendiente tras la consolidación de mayo de 2026. Se han priorizado las funcionalidades de colaboración, auditoría y seguridad avanzada.

---

## Posting Contable y Core
- [ ] Resolver política formal de renumeración de `document_no` cuando un borrador cambia de serie/fecha tras haber sido numerado.
- [ ] Implementar soporte completo para `GLEntryDimension` (dimensiones personalizadas) en el motor de posting.

---

## Cuentas por Cobrar / Cuentas por Pagar (AR/AP)
- [ ] Mejorar UX de exportación de Aging y permitir buckets configurables por compañía.
- [ ] Implementar conciliación masiva de facturas contra pagos desde una interfaz dedicada (actualmente es 1 a N desde el pago).

---

## Documentos de Corrección
- [ ] Reforzar validaciones E2E para flujos de devolución complejos (ej. devolución parcial de mercancía con factura ya pagada).
- [ ] Trazabilidad bidireccional visualmente mejorada en el árbol de flujo para reversiones.

---

## Proveedor y Cliente
- [ ] Implementar modelo `PartyGroup` y su CRUD.
- [ ] Migrar formularios de Proveedor y Cliente al "Voucher Pattern" y añadir gestión de múltiples direcciones/contactos.

---

## Inventario
- [ ] Implementar "Stock Reconciliation" para ajuste de valuación (actualmente solo soporta ajuste de cantidad/conciliación física).
- [ ] Prorrateo de cargos capitalizables (fletes/seguros) hacia el costo de entrada en `StockValuationLayer`.

---

## Multi-Ledger y Dimensiones
- [ ] Implementar `LedgerMappingRule` para diferencias automáticas entre libros.
- [ ] UI para gestión de `DimensionType` y `DimensionValue`.
- [ ] Reporte de saldos por dimensiones analíticas.

---

## Tesorería y Revalorización
- [ ] Implementar proceso de `ExchangeRevaluation` (revalorización cambiaria de cuentas monetarias).
- [ ] Automatización de ajustes por diferencial cambiario en pagos de facturas multimoneda.

---

## Administración y Seguridad
- [ ] Endurecer autorización por compañía/libro con matriz explícita usuario↔compañía/libro.
- [ ] Implementar Workflow de aprobación configurable (definición de estados y transiciones).
- [ ] Activar registro automático de `AuditLog` para cambios en documentos operativos (actualmente solo en flujo documental).

---

## UI y UX (Pendiente Transversal)
- [ ] Añadir filtros de búsqueda en listados de Compras, Ventas y Bancos (completado solo en Contabilidad).
- [ ] Migrar todos los formularios operativos restantes al Smart Select Framework.
- [ ] Implementar el árbol gráfico de trazabilidad (Diagrama de Flujo).

---

## Reportes
- [ ] Drill-down universal completo en todos los reportes operativos.
- [ ] Exportación consistente a Excel con formato financiero en el 100% de los reportes.
- [ ] Añadir pruebas E2E de UI para expand/collapse jerárquico.
