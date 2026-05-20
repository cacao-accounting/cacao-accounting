# PENDIENTE - Cacao Accounting (Backlog Priorizado)

## Seguimiento 2026-05-19 (MVP Fiscal)
- [x] Definir matriz fiscal/gastos por tipo documental para el alcance MVP.
- [x] Exponer API unificada `POST /api/fiscal/preview` para formularios transaccionales.
- [x] Integrar bloque UX común `Impuestos y Cargos` con modal por línea en Compras, Ventas e Inventario.
- [x] Integrar bloque en Bancos solo para `payment_entry` (entrada de pagos), según ajuste de alcance.
- [ ] Ampliar cobertura de pruebas funcionales por documento del MVP fiscal (casos positivos/negativos por doctype).
- [x] Implementar persistencia fiscal real por documento (`document_tax_line` / `document_tax_summary`) para `purchase_invoice`, `sales_invoice` y `payment_entry`.
- [x] Persistir snapshot inmutable de regla fiscal por línea (no recalcular histórico con reglas futuras) para trazabilidad y auditoría.
- [x] Integrar consumo del snapshot fiscal persistido en `submit_document` de `purchase_invoice`, `sales_invoice` y `payment_entry` para generar asientos/efectos contables desde datos confirmados.
- [x] Corregir regresiones de preview fiscal: reglas canónicas en recálculo, perfil de cobro para `receive`, guard UI para doctypes fuera de matriz y normalización de cuentas fiscales vacías.
- [x] Permitir añadir impuestos/cargos manuales desde el bloque transaccional y conservarlos junto a reglas fiscales canónicas.

## Core y Posting
- [x] Resolver politica formal de renumeracion de `document_no` tras cambios en borradores: la numeracion emitida se conserva; si fue incorrecta, se anula el registro y se crea uno nuevo.

## AR/AP y Terceros
- [x] Implementar modelo `PartyGroup` y su CRUD.
- [x] Completar edicion/visualizacion por compania para Cliente y Proveedor en nuevo patron.
- [x] Gestion de multiples direcciones y contactos para terceros.
- [ ] Conciliacion masiva de facturas contra pagos (interfaz dedicada).
- [ ] Buckets configurables por compania en reportes de Aging.

## Inventario y Valoracion
- [ ] Implementar "Stock Reconciliation" para ajuste de valuacion (actualmente solo cantidad).
- [x] Persistir el prorrateo de cargos capitalizables calculado por `LandedCostEngine` en una tabla dedicada y materializar su efecto en `StockValuationLayer` durante el flujo transaccional.
- [ ] Completar UI/documento dedicado para liquidaciones de importacion complejas cuando el costo aterrizado se confirme en un evento posterior a la recepcion.

## Administracion y Seguridad
- [ ] Matriz explicita de autorizacion Usuario-Compania/Libro.
- [ ] Implementar Workflow de aprobacion configurable (estados y transiciones).
- [ ] Activar `AuditLog` automatico para cambios en documentos operativos.

## Multi-Ledger y Revalorizacion
- [ ] Implementar `LedgerMappingRule` para diferencias automaticas entre libros.
- [x] Implementar proceso de `ExchangeRevaluation` (revalorizacion cambiaria de cuentas monetarias).

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

## Pendientes Generales
- [ ] Implementar mas reportes operativos usando el nuevo framework.
- [ ] Seguir migrando formularios operativos al patron comun sin tocar todavia pagos bancarios ni documentos con origen complejo sin cobertura funcional suficiente.
- [ ] Ampliar catalogos impositivos para otros paises.
- [ ] Webhooks para integracion con sistemas externos.
- [ ] Ampliar cobertura de pruebas Playwright en el nuevo flujo estandarizado.
- [ ] Mejorar la estabilidad de los tests E2E en entornos de CI/Sandbox con latencia de red.
- [ ] Continuar la estandarizacion de reportes HTML siguiendo el patron de `financial_report.html`.
- [ ] Extender el uso de `smart-select` a dimensiones personalizadas si se requiere en el futuro.
