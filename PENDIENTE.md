# PENDIENTE - Cacao Accounting (Backlog Priorizado)

## Seguimiento 2026-05-24 (Dashboard Ejecutivo - completado)
- [x] Validar acceso temporal usuario-compañía antes de devolver datos del dashboard.
- [x] Validar que el periodo contable pertenece a la compañía seleccionada.
- [x] Normalizar la respuesta del API en `sections` con visibilidad uniforme por módulo.
- [x] Ampliar métricas de Contabilidad, Bancos, Compras, Inventario y Ventas.
- [x] Renombrar el widget de inventario a **Menor existencia** usando `StockBin` mientras no exista stock mínimo formal.
- [x] Rediseñar `/app` con secciones ejecutivas, KPIs, widgets, acciones rápidas y estados vacíos.
- [x] Ampliar pruebas focales de seguridad, permisos, estados vacíos, métricas y render.

## Seguimiento 2026-05-24 (Mantenibilidad importacion/perfil - completado)
- [x] Refactorizar `validate_lines()` como orquestador y extraer validaciones a helpers privados.
- [x] Ampliar cobertura de importacion de lineas para doctype, compania, limites, tipos y datos maestros.
- [x] Refactorizar `profile()` separando render, actualizacion de perfil y cambio de contrasena.

## Seguimiento 2026-05-24 (Mantenibilidad motores fiscales/pagos - completado)
- [x] Refactorizar `_build_payment_context` para separar direccion del pago, montos de liquidacion, referencias contables y reglas fiscales.
- [x] Simplificar `_tax_rules_from_template` usando helpers y `match/case` para decisiones fiscales heredadas.
- [x] Refactorizar `RuleResolver.resolve` usando helpers y `match/case` para estrategias de merge.
- [x] Refactorizar `_calculate_share` de Landed Cost usando `match/case` por metodo de prorrateo.
- [x] Refactorizar `_map_settlement_event` para separar balance, banco, retenciones y ajustes de liquidacion.
- [x] Renombrar acumuladores `debits`/`credits` en mapper para evitar shadowing.

## Seguimiento 2026-05-24 (Flujo Documental Expandible - completado)
- [x] Registrar `journal_entry` dentro del árbol de flujo documental y mostrarlo en la vista de comprobante contable.
- [x] Crear relaciones contables desde líneas de journal con `internal_reference` / `internal_reference_id`.
- [x] Garantizar que `apply_advance_to_invoice` cree `PaymentReference` y `DocumentRelation`.
- [x] Eliminar la implementación inline duplicada de `documentFlowTree`.

## Seguimiento 2026-05-23 (Conciliaciones - completado)
- [x] Conciliacion masiva de facturas contra pagos (interfaz dedicada).
- [x] Implementar "Stock Reconciliation" para ajuste de valuacion (cantidad + valor objetivo).

## Seguimiento 2026-05-22 (Payment Entry - completado)
- [x] Acciones `Crear` en detalle de solicitud de compra (`purchase_request` → cotización de proveedor) — pre-existing gap en `ALLOWED_FLOWS`.
- [x] Acción `Crear Entrada de Almacén` desde recepción de compra — pre-existing gap en `ALLOWED_FLOWS`.

## Seguimiento 2026-05-21 (Matriz de relaciones operativas)
- [ ] Ejecutar implementación completa de la matriz definida en `modulos/relaciones.md` (en progreso: núcleo `document_flow` + acciones dinámicas en trazabilidad).
- [ ] Completar expansión de `create_actions` y `ALLOWED_FLOWS` para todos los pares funcionales acordados, priorizando faltantes reales por módulo.
- [ ] Completar backend de creación/prefill básico para nuevas acciones `Crear` aún no soportadas por rutas actuales.
- [ ] Añadir cobertura de pruebas para nuevos caminos de devolución y notas débito/crédito en Compras y Ventas.

## Seguimiento 2026-05-19 (MVP Fiscal)
- [ ] Ampliar cobertura de pruebas funcionales por documento del MVP fiscal (casos positivos/negativos por doctype).

## AR/AP y Terceros
- [ ] Buckets configurables por compania en reportes de Aging.

## Inventario y Valoracion
- [ ] Completar UI/documento dedicado para liquidaciones de importacion complejas cuando el costo aterrizado se confirme en un evento posterior a la recepcion.

## Administracion y Seguridad
- [ ] Matriz explicita de autorizacion Usuario-Compania/Libro.
- [ ] Implementar Workflow de aprobacion configurable (estados y transiciones).
- [ ] Activar `AuditLog` automatico para cambios en documentos operativos.

## Multi-Ledger y Revalorizacion
- [ ] Implementar `LedgerMappingRule` para diferencias automaticas entre libros.

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
- [ ] Añadir soporte transaccional persistido para documentos específicos de importación cuando exista un doctype dedicado para `import_landed_cost_confirmed`.

## Pendientes Generales
- [x] Implementar mas reportes operativos usando el nuevo framework.
- [ ] Seguir migrando formularios operativos al patron comun sin tocar todavia pagos bancarios ni documentos con origen complejo sin cobertura funcional suficiente.
- [ ] Ampliar catalogos impositivos para otros paises.
- [ ] Webhooks para integracion con sistemas externos.
- [ ] Ampliar cobertura de pruebas Playwright en el nuevo flujo estandarizado.
- [ ] Mejorar la estabilidad de los tests E2E en entornos de CI/Sandbox con latencia de red.
- [ ] Continuar la estandarizacion de reportes HTML siguiendo el patron de `financial_report.html`.
- [ ] Extender el uso de `smart-select` a dimensiones personalizadas si se requiere en el futuro.
