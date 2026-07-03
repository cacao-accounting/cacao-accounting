# PENDIENTE - Cacao Accounting

## Seguimiento 2026-07-03 (Cuenta de inventario por almacen/compania)
- [x] Alinear purchase receipts y delivery notes para usar solo `WarehouseCompanyAccount` y eliminar el fallback global `default_inventory`.

## Seguimiento 2026-07-03 (Valuacion de inventarios)
- [x] Agregar una entrada en configuracion global para administrar el metodo de valuacion por compañia fuera del wizard inicial.

## Seguimiento 2026-07-03 (Arboles contables)
- [x] Ajustar el patron visual compartido del arbol de cuentas contables y del arbol de centros de costos, con comportamiento usable en mobile.

## Seguimiento 2026-07-03 (Setup inicial)
- [x] Ajustar visualmente el wizard inicial para reducir el hero sobredimensionado, compactar el stepper y usar marca desde `static/media`.

## Seguimiento 2026-07-03 (Smart Select)
- [x] Corregir el overlay de resultados de `smart-select` dentro de tablas responsivas en Articulo, Cliente y Proveedor.

## Seguimiento 2026-05-19 (MVP Fiscal)
- [ ] Ampliar cobertura de pruebas funcionales por documento del MVP fiscal (casos positivos/negativos por doctype).

## Administracion y Seguridad
- [ ] Activar `AuditLog` automatico para cambios en documentos operativos.

## Multi-Ledger y Revalorizacion
- [ ] Implementar `LedgerMappingRule` para diferencias automaticas entre libros.

## UI/UX y Reportes
- [ ] Seguir afinando el bloque legal de Cliente y Proveedor si en el futuro se requieren campos adicionales de notificación o representación por jurisdicción.
- [ ] Agregar edicion del item para mantener y ajustar la configuracion contable por compañia despues de la creacion, respetando bloqueos de negocio donde aplique.
- [ ] Evaluar y definir alcance de acciones equivalentes para registros maestros (cliente, proveedor, item, bodega, uom) sin forzar flujo documental donde no aplica.
- [ ] Auditar formularios maestros restantes para detectar selectores que todavia deban migrarse al Smart Select Framework despues de Cliente, Proveedor, Item y Bodega.
- [ ] Ampliar pruebas de interfaz para nuevos formularios bancarios (`pago_nuevo`, `nota_nueva`, `transferencia_nueva`) incluyendo escenarios multimoneda y contador externo.
- [ ] Extender el mismo flujo intuitivo de importación local de XLSX y plantilla descargable a cualquier formulario legacy que todavía conserve un modal de importación propio fuera del asistente compartido.
- [ ] Evaluar si el filtro avanzado `Estado` en reportes contables debe desdoblarse para distinguir explícitamente `Cancelado` versus `Reversión`, ahora que el dataset ya soporta ambas clases GL por separado.
- [ ] Evaluar si el detalle del comprobante también debe ocultar el ULID como nombre visible cuando un borrador de reversión todavía no tiene numeración definitiva, para mantener la misma regla visual del listado.
- [ ] Implementar arbol grafico de trazabilidad (Diagrama de Flujo).
- [ ] Drill-down universal en el 100% de los reportes operativos.
- [ ] Exportacion consistente a Excel con formato financiero en todos los reportes.
- [ ] Revisar si la plantilla recurrente debe compartir aún más markup/base CSS con `journal_nuevo.html` para evitar divergencias futuras de layout.

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
