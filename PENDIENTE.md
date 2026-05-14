# PENDIENTE — Cacao Accounting (Backlog Priorizado)

## Core y Posting
- [ ] Resolver política formal de renumeración de `document_no` tras cambios en borradores.
- [ ] Implementar soporte completo para `GLEntryDimension` (dimensiones personalizadas) en posting.

## AR/AP y Terceros
- [ ] Implementar modelo `PartyGroup` y su CRUD.
- [ ] Completar edición/visualización por compañía para Cliente y Proveedor en nuevo patrón.
- [ ] Gestión de múltiples direcciones y contactos para terceros.
- [ ] Conciliación masiva de facturas contra pagos (interfaz dedicada).
- [ ] Buckets configurables por compañía en reportes de Aging.

## Inventario y Valoración
- [ ] Implementar "Stock Reconciliation" para ajuste de valuación (actualmente solo cantidad).
- [ ] Prorrateo de cargos capitalizables (fletes/seguros) en `StockValuationLayer`.

## Administración y Seguridad
- [ ] Matriz explícita de autorización Usuario ↔ Compañía/Libro.
- [ ] Implementar Workflow de aprobación configurable (estados y transiciones).
- [ ] Activar `AuditLog` automático para cambios en documentos operativos.

## Multi-Ledger y Revalorización
- [ ] Implementar `LedgerMappingRule` para diferencias automáticas entre libros.
- [ ] Implementar proceso de `ExchangeRevaluation` (revalorización cambiaria de cuentas monetarias).
- [ ] UI para gestión de `DimensionType` y `DimensionValue`.

## UI/UX y Reportes
- [ ] Filtros de búsqueda en listados de Compras, Ventas y Bancos.
- [ ] Migrar formularios operativos restantes al Smart Select Framework.
- [ ] Implementar árbol gráfico de trazabilidad (Diagrama de Flujo).
- [ ] Drill-down universal en el 100% de los reportes operativos.
- [ ] Exportación consistente a Excel con formato financiero en todos los reportes.

## Nota de Integración (2026-05-14)
- [x] Integración selectiva desde `ia/main` completada: base documental de `1965ac44a352de5af34d604b81400a2bc8aed74a` y endpoints/prueba de salud desde `bef4029e25000512539a27164f8915cf3b4b2acc`.
- [ ] Verificar en CI la integración selectiva completa sobre `main`.
