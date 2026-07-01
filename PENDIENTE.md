# PENDIENTE - Cacao Accounting

## Seguimiento 2026-05-19 (MVP Fiscal)
- [ ] Ampliar cobertura de pruebas funcionales por documento del MVP fiscal (casos positivos/negativos por doctype).

## Administracion y Seguridad
- [ ] Activar `AuditLog` automatico para cambios en documentos operativos.

## Multi-Ledger y Revalorizacion
- [ ] Implementar `LedgerMappingRule` para diferencias automaticas entre libros.

## UI/UX y Reportes
- [ ] Completar la segunda iteracion visual de Cliente y Proveedor para acercar mas la disposicion por secciones a las referencias, manteniendo la funcionalidad ya implementada de cuenta AR/AP, lista de precio y regla fiscal por compañia.
- [ ] Evaluar y definir alcance de acciones equivalentes para registros maestros (cliente, proveedor, item, bodega, uom) sin forzar flujo documental donde no aplica.
- [ ] Migrar formularios operativos restantes al Smart Select Framework; el framework transaccional compartido de Compras, Ventas e Inventario ya inicializa correctamente sus selectores.
- [ ] Ampliar pruebas de interfaz para nuevos formularios bancarios (`pago_nuevo`, `nota_nueva`, `transferencia_nueva`) incluyendo escenarios multimoneda y contador externo.
- [ ] Implementar arbol grafico de trazabilidad (Diagrama de Flujo).
- [ ] Drill-down universal en el 100% de los reportes operativos.
- [ ] Exportacion consistente a Excel con formato financiero en todos los reportes.

## Motores de Cálculo y Contabilidad
- [ ] Añadir soporte transaccional persistido para documentos específicos de importación cuando exista un doctype dedicado para `import_landed_cost_confirmed`.

## Pendientes Generales
- [ ] Seguir migrando formularios operativos al patron comun sin tocar todavia pagos bancarios ni documentos con origen complejo sin cobertura funcional suficiente.
- [ ] Ampliar cobertura de pruebas Playwright en el nuevo flujo estandarizado.
- [ ] Mejorar la estabilidad de los tests E2E en entornos de CI/Sandbox con latencia de red.
- [ ] Continuar la estandarizacion de reportes HTML siguiendo el patron de `financial_report.html`.
- [ ] Extender el uso de `smart-select` a dimensiones personalizadas si se requiere en el futuro.
- [ ] Integrar `audit_trail_service` en Bancos, Compras, Ventas, Inventario, Importaciones, Revalorización y Conciliaciones con timeline visible en cada detalle.
- [ ] Extender las mismas pruebas/contratos de Audit Trail a Bancos, Compras, Ventas, Inventario e Importaciones (acciones + timeline + append-only).
- [ ] Extender integración Audit Trail a documentos restantes de Compras/Ventas/Bancos/Inventario (órdenes, facturas, cotizaciones, notas) con render homogéneo de timeline en UI.
- [ ] Seguir reduciendo complejidad en flujos de Bancos donde todavía existan ramas largas, usando helpers pequeños y cobertura focal por cada refactor.
- [ ] Revisar si `issues.txt` debe regenerarse o depurarse, porque `_save_payment_references` ya quedó refactorizado y aparece como pendiente histórico.
