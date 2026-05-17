# PENDIENTE - Cacao Accounting (Backlog Priorizado)

## Seguimiento 2026-05-17
- [x] Integrar `pydocstyle` al flujo de calidad (local y CI) con convención `pep257`.
- [ ] Mantener cobertura de docstrings en nuevos cambios de `cacao_accounting`.

## Core y Posting
- [ ] Resolver politica formal de renumeracion de `document_no` tras cambios en borradores.
- [ ] Implementar soporte completo para `GLEntryDimension` (dimensiones personalizadas) en posting.

## AR/AP y Terceros
- [ ] Implementar modelo `PartyGroup` y su CRUD.
- [ ] Completar edicion/visualizacion por compania para Cliente y Proveedor en nuevo patron.
- [ ] Gestion de multiples direcciones y contactos para terceros.
- [ ] Conciliacion masiva de facturas contra pagos (interfaz dedicada).
- [ ] Buckets configurables por compania en reportes de Aging.

## Inventario y Valoracion
- [ ] Implementar "Stock Reconciliation" para ajuste de valuacion (actualmente solo cantidad).
- [ ] Prorrateo de cargos capitalizables (fletes/seguros) en `StockValuationLayer`.

## Administracion y Seguridad
- [ ] Matriz explicita de autorizacion Usuario-Compania/Libro.
- [ ] Implementar Workflow de aprobacion configurable (estados y transiciones).
- [ ] Activar `AuditLog` automatico para cambios en documentos operativos.

## Multi-Ledger y Revalorizacion
- [ ] Implementar `LedgerMappingRule` para diferencias automaticas entre libros.
- [ ] Implementar proceso de `ExchangeRevaluation` (revalorizacion cambiaria de cuentas monetarias).
- [ ] UI para gestion de `DimensionType` y `DimensionValue`.

## UI/UX y Reportes
- [ ] Cerrar la fase final de paridad funcional en formularios transaccionales con pruebas adicionales por documento (incluyendo rutas `edit`/`duplicate` y transiciones de estado en POST).
- [ ] Evaluar y definir alcance de acciones equivalentes para registros maestros (cliente, proveedor, item, bodega, uom) sin forzar flujo documental donde no aplica.
- [ ] Filtros de busqueda en listados de Compras, Ventas y Bancos.
- [ ] Migrar formularios operativos restantes al Smart Select Framework; el framework transaccional compartido de Compras, Ventas e Inventario ya inicializa correctamente sus selectores.
- [ ] Ampliar pruebas de interfaz para nuevos formularios bancarios (`pago_nuevo`, `nota_nueva`, `transferencia_nueva`) incluyendo escenarios multimoneda y contador externo.
- [ ] Implementar arbol grafico de trazabilidad (Diagrama de Flujo).
- [ ] Drill-down universal en el 100% de los reportes operativos.
- [ ] Exportacion consistente a Excel con formato financiero en todos los reportes.

## Motores de Cálculo y Contabilidad
- [x] Implementar el "Posting Builder" definitivo basado en las propuestas de `AccountingMapper`.
- [x] Evolucionar el motor de reglas hacia una implementación basada en Grafos de Dependencia (DAG) para cálculos complejos no secuenciales.
- [x] Integrar `TaxRule` al flujo transaccional para construir `CalculationContext` desde BD sin cargar reglas manualmente en pruebas.
- [x] Extender `SettlementEngine` para manejar descuentos por pronto pago y revaluaciones de moneda no realizadas.
- [ ] Añadir soporte transaccional persistido para documentos específicos de importación cuando exista un doctype dedicado para `import_landed_cost_confirmed`.
- [ ] Evaluar almacenamiento persistente del snapshot/fingerprint de cálculo en los documentos operativos para trazabilidad directa desde UI.

## Pendientes Generales
- [ ] Implementar mas reportes operativos usando el nuevo framework.
- [ ] Seguir migrando formularios operativos al patron comun sin tocar todavia pagos bancarios ni documentos con origen complejo sin cobertura funcional suficiente.
- [ ] Ampliar catalogos impositivos para otros paises.
- [ ] Webhooks para integracion con sistemas externos.
- [ ] Ampliar cobertura de pruebas Playwright en el nuevo flujo estandarizado.
- [ ] Mejorar la estabilidad de los tests E2E en entornos de CI/Sandbox con latencia de red.
- [ ] Continuar la estandarizacion de reportes HTML siguiendo el patron de `financial_report.html`.
- [ ] Extender el uso de `smart-select` a dimensiones personalizadas si se requiere en el futuro.
