# PENDIENTE - Cacao Accounting

## Auditoría Funcional / Verificación (2026-07-09) — Issues Verificados
- [ ] **S2P-01 [#119]:** Agregar `has_active_source_relations()` a cancel handlers de PR, SQ, PQ, Receipt.
- [ ] **S2P-02 [#120]:** Agregar `log_create()` a handlers de creación de PR, SQ, PO, PQ, PI.
- [ ] **S2P-03 [#140]:** Agregar `log_update()` a handlers de edición de PR, SQ, PO.
- [ ] **S2P-04 [#121]:** Validar cantidades contra PO en facturas directas sin recepción.
- [ ] **S2P-05 [#175]:** Agregar try/except en receipt edit handler para DocumentFlowError.
- [ ] **S2P-06 [#160]:** Agregar `supplier_name=supplier.name` en creación de Purchase Receipt.
- [ ] **S2P-07 [#122]:** Recalcular FX rate y montos base en edit handler de Purchase Invoice.
- [ ] **S2P-08 [#141]:** Copiar transaction_currency y computar FX en handlers de duplicado PO/Invoice.
- [ ] **S2P-09 [#138]:** Si CompanyParty es None, asumir configuración restrictiva (denegar factura sin OC).
- [ ] **S2P-10 [#161]:** Agregar `with_for_update()` en `_apply_payment_target_line`.
- [ ] **S2P-11 [#123]:** Reemplazar `except Exception` por captura específica + logging en `_purchase_exchange_rate`.
- [ ] **S2P-12 [#124]:** Verificar pagos activos antes de cancelar Invoice (compras y ventas).
- [ ] **S2P-13 [#142]:** Usar `dict.get()` o `try/except` en `get_document_type`.
- [ ] **S2P-14 [#162]:** Agregar `_audit()` en `create_document_relation`.
- [ ] **S2P-15 [#176]:** Completar propagación de caché transitiva al cancelar Receipt.
- [ ] **S2P-16 [#177]:** Preservar `supplier_invoice_no` existente en edit si form viene vacío.
- [ ] **S2P-17 [#178]:** Agregar validación fallback cuando no hay DocumentRelation explícito.
- [ ] **S2P-18 [#163]:** Validar existencia/is_active/company de almacén en Purchase Receipt.
- [ ] **S2P-19 [#179]:** Agregar `log_create` en `create_target_document` (API/bulk).
- [ ] **S2P-20 [#143]:** Verificar facturas activas antes de cancelar Recepción.
- [ ] **O2C-04 [#139]:** Hacer idempotente `_release_reservation_for_delivery_note` con flag de estado.
- [ ] **O2C-06 [#180]:** Mover validación de precio de edit a submit, o convertir en warnings.
- [ ] **O2C-07 [#125]:** Agregar `_release_reservation_for_delivery_note(dn)` en `_create_delivery_note_from_invoice`.
- [ ] **O2C-08 [#144]:** Agregar `_restore_reservation_for_delivery_note(dn)` en cancelación de Invoice con update_inventory.
- [ ] **O2C-09 [#145]:** Agregar `has_active_source_relations()` a cancel handler de SalesQuotation.
- [ ] **O2C-10 [#181]:** Agregar `except Exception` handler en `_handle_sales_order_new_post`.
- [ ] **O2C-11 [#146]:** Agregar `log_update()` a handlers de edición de SalesOrder y SalesRequest.
- [ ] **O2C-13 [#182]:** Validar `docstatus==1` del source en `create_document_relation`.
- [ ] **O2C-14 [#183]:** Agregar validación de rate > 0 y amount > 0 en `validate_submit_prerequisites`.
- [ ] **O2C-18 [#126]:** Validar `reversal_of` (existencia, docstatus, compañía, tercero) en NC/ND.
- [ ] **O2C-20 [#127]:** Agregar `with_for_update()` en reserva de stock para SalesOrder.
- [ ] **O2C-22 [#147]:** Agregar parámetro `require_warehouse` a `validate_submit_prerequisites`.
- [ ] **O2C-28 [#148]:** Agregar `default=0` a `delivered_qty`, `billed_qty`, `received_qty`.
- [ ] **R2R-03 [#128]:** Eliminar restricción de misma fecha en cancelación de comprobante. Validar solo período abierto.
- [ ] **R2R-05 [#129]:** Auto-aprobar voucher de cierre de año fiscal o agregar indicador de pendiente.
- [ ] **R2R-06 [#149]:** Agregar `log_create`, `log_submit`, `log_cancel` a ExchangeRevaluationService.
- [ ] **R2R-07 [#164]:** Agregar `log_update` en `finalizar_cierre_mensual`.
- [ ] **R2R-09 [#165]:** Agregar auditoría a `recurring_journal_service.py` (5 funciones).
- [ ] **R2R-10 [#184]:** Integrar control presupuestario en posting (futuro).
- [ ] **R2R-11 [#130]:** Agregar `_has_active_gl_entries` check en funciones `post_*` individuales.
- [ ] **R2R-12 [#131]:** Aplicar tolerancia `abs(diff) > Decimal("0.01")` en `_assert_entries_balance`.
- [ ] **R2R-13 [#185]:** Cambiar linking positional por matching explícito en revaluación.
- [ ] **R2R-14 [#132]:** Validar `check_status == "passed"` para todos los `PeriodCloseCheck` antes de cerrar período.
- [ ] **R2R-15 [#166]:** Agregar fallback a fecha más cercana en `_lookup_exchange_rate`.
- [ ] **R2R-16 [#167]:** Aplicar proporción al balance de revaluaciones activas.
- [ ] **CAS-01 [#150]:** Agregar `UniqueConstraint` en `PaymentReference` sobre `(payment_id, reference_type, reference_id)`.
- [ ] **CAS-02 [#169]:** Agregar `with_for_update()` en `reconcile_bank_items` para BankTransaction.
- [ ] **CAS-03 [#168]:** Agregar validación de moneda y FX en `_validate_payment_reference_document`.
- [ ] **CAS-04 [#151]:** Resetear `is_reconciled` y `payment_entry_id` en `BankTransaction` al cancelar pago.
- [ ] **CAS-06 [#152]:** Agregar `with_for_update()` en lectura de `PaymentEntry` durante reconciliación.
- [ ] **CAS-07 [#153]:** Agregar validación de tamaño máximo de lote en reconciliación.
- [ ] **CAS-10 [#133]:** Copiar lógica de `_build_payment_reference` al path masivo de pago.
- [ ] **CAS-13 [#134]:** Usar `allocated` en balance check en lugar de `consumed`, o validar que discount no exceda allocated.
- [ ] **CAS-14 [#135]:** Agregar check de `is_reconciled` en ruta de reconciliación "apply".
- [ ] **CAS-15 [#154]:** Invalidar caché de saldo pendiente al cancelar pagos.
- [ ] **INV-02 [#170]:** Incluir item_code y warehouse en mensaje de error de capas.
- [ ] **INV-03 [#156]:** Filtrar bodegas por compañía en compras y ventas.
- [ ] **INV-04 [#157]:** Re-lanzar error o flash warning en conversión UOM de reconciliación.
- [ ] **INV-05 [#171]:** Calcular `qty_in_base_uom` con `convert_item_qty` en `_save_stock_entry_items`.
- [ ] **INV-06 [#136]:** Derivar `qty_after` de `bin_row.actual_qty + qty_change` dentro de `_upsert_stock_bin`.
- [ ] **INV-07 [#158]:** Agregar método para reconstruir `StockValuationLayer` desde `StockLedgerEntry`.
- [ ] **INV-10 [#159]:** Considerar `reserved_qty` en movimientos manuales de inventario.
- [x] **INV-11 [#172]:** Incluir `line.item_code` en mensajes de error de valuación (Commit `64179e5`).
- [ ] **INV-25 [#137]:** Llamar `_consume_stock_valuation_layers` cuando `qty_change < 0` en reconciliación.

## Seguimiento 2026-07-08 (Cierre de hallazgos ISSUES.md)
- [x] **R2R-04:** Asistente de cierre mensual finaliza y marca `AccountingPeriod.is_closed=True` (Commit `4610fdd`).
- [x] **S2P-09:** Selector de moneda en UI de compras + `base_total` multimoneda (Commit `bb2ac5d`).
- [x] **O2C-04:** Tipo documental `sales_return` espejo de `purchase_return` + exposición de `DeliveryNote.is_return` (Commit `b31ce72`).
- [x] **S2P-07:** Neteo automático de anticipos contra factura con flag `apply_advances_automatically` (Commit `3f72f1a`).
- [x] Todos los 30 hallazgos de ISSUES.md corregidos o falsos positivos. No quedan pendientes del informe.

## Seguimiento 2026-07-03 (Codigos legibles para clientes, proveedores e items)
- [x] Reemplazar ULIDs visibles en clientes, proveedores e items por codigos secuenciales CUSTM-00001, SUPLR-00001, ITEM-000001.
- [x] Crear series globales de naming para customer/supplier/item con prefijo fijo y sin reinicio.
- [x] Modificar `generate_party_code()` y `create_item_with_uoms()` para usar `generate_entity_code()`.
- [x] Sembrar series globales durante setup inicial y seed de desarrollo.
- [ ] Migrar registros existentes con codigos ULID a codigos secuenciales (opcional, pendiente de priorizar).

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
