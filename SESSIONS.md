# SESSIONS - Historical Decisions & Milestones

## 2026-07-09 (S2P-01/O2C-09: Verificación de relaciones activas al cancelar documentos)
- **Solicitud:** Analizar issue #119 (S2P-01: Sin verificación de relaciones activas al cancelar documentos no financieros) y #145 (O2C-09: SalesQuotation cancel no verifica relaciones descendientes).
- **Diagnóstico:** Los issues son errores reales verificados. Solo `compras_orden_compra_cancel` (PO) y `ventas_orden_venta_cancel` (SO) llamaban a `has_active_source_relations()` antes de cancelar. Los demás handlers de cancelación en Compras (PR, SQ, PQ, Receipt) y Ventas (SR, SQ, DN, Invoice) permitían cancelar documentos con hijos activos, violando integridad referencial.
- **Implementación:**
  1. **Compras** — Se agregó `has_active_source_relations()` a:
     - `compras_solicitud_compra_cancel` (PurchaseRequest)
     - `compras_cotizacion_proveedor_cancel` (SupplierQuotation)
     - `compras_solicitud_cotizacion_cancel` (PurchaseQuotation)
     - `compras_recepcion_cancel` (PurchaseReceipt)
  2. **Ventas** — Se agregó `has_active_source_relations()` a:
     - `ventas_pedido_venta_cancel` (SalesRequest)
     - `ventas_cotizacion_cancel` (SalesQuotation)
     - `ventas_entrega_cancel` (DeliveryNote)
     - `ventas_factura_venta_cancel` (SalesInvoice)
  3. Cada handler ahora bloquea la cancelación con flash message descriptivo si hay hijos activos.
- **Pruebas:** Suite completa de cancelación pasó (31 tests). Patrón consistente con PO y SO existentes.
- **Cierre del issues:** #119 (S2P-01) cerrado, #145 (O2C-09) cerrado con comentario explicativo del fix completo en O2C.

## 2026-07-09 (S2P-09: Validación estricta cuando CompanyParty es None en _validate_supplier_invoice_flags)
- **Solicitud:** Ejecutar corrección del issue #138 (S2P-09): `_validate_supplier_invoice_flags` omitía validación cuando `CompanyParty` es None.
- **Implementación:** Se modificó `_validate_supplier_invoice_flags` en `cacao_accounting/compras/__init__.py:2846-2848` para lanzar `PostingError("No se encontró configuración de flags para el proveedor en la compañía.")` en lugar de retornar silenciosamente. Se agregó comentario con referencia al issue.
- **Cierre del issue:** #138 cerrado con comentario explicativo. Commit `13f77a4`.

## 2026-07-09 (O2C-22: Validación de almacén en validate_submit_prerequisites)
- **Solicitud:** Analizar issue #147 (O2C-22: validate_submit_prerequisites no valida almacén para ítems de stock) y corregir si es un error real.
- **Diagnóstico:** El issue es un error real verificado. La función `validate_submit_prerequisites` no validaba que ítems con `is_stock_item=True` tengan un almacén asignado antes de aprobar el documento. La validación de almacén solo ocurría después en `posting.py` durante la creación de `StockLedgerEntry`, causando errores después de la aprobación.
- **Implementación:**
  1. Se agregó parámetro `require_warehouse` a `validate_submit_prerequisites()` en `document_flow/validation.py`
  2. Cuando `require_warehouse=True`, valida que todas las líneas tengan `warehouse` asignado
  3. Se actualizaron handlers de submit:
     - Purchase Receipt: `require_warehouse=True` (siempre)
     - Delivery Note: `require_warehouse=True` (siempre)
     - Stock Entry: `require_warehouse=True` (siempre)
     - Sales Invoice: `require_warehouse=True` solo cuando `update_inventory=True`
  4. Se agregaron 4 tests en `tests/test_validation.py` para la validación de almacén
- **Pruebas:** Todos los tests pasaron (16 tests en test_validation.py). Black, ruff y mypy en verde.
- **Commits:** `e30c173` (fix(validation): add require_warehouse parameter to validate_submit_prerequisites)
- **Cierre del issue:** Issue #147 cerrado con comentario explicativo.

## 2026-07-09 (CAS-04: Corrección de conciliación bancaria al cancelar pago)
- **Solicitud:** Analizar issue #151 (CAS-04: Cancelación de pago no limpia enlace de conciliación bancaria) y corregir si es un error real.
- **Diagnóstico:** El issue es un error real verificado. Al cancelar un pago, el handler `bancos_pago_cancel` no reseteaba `is_reconciled` ni `payment_entry_id` en las `BankTransaction` vinculadas, dejando referencias huérfanas y estado de conciliación inconsistente.
- **Implementación:**
  1. Se agregó lógica en `bancos_pago_cancel` para buscar `BankTransaction` con `payment_entry_id` igual al pago cancelado
  2. Se resetea `is_reconciled = False` y `payment_entry_id = None` en cada transacción encontrada
  3. Se agregó comentario explicativo con referencia al issue CAS-04/#151 para prevenir falsos positivos futuros
- **Pruebas:** Todos los tests existentes de pagos y cancelación pasaron (51 tests). La corrección es consistente con el patrón de conciliación existente en `reconciliation_service.py`.
- **Cierre del issue:** Se cerrará con comentario explicativo indicando que el error fue corregido.

## 2026-07-09 (INV-05: Corrección de qty_in_base_uom en entradas de stock)
- **Solicitud:** Analizar issue #171 (INV-05: qty_in_base_uom no persiste al guardar entrada de stock) y corregir si es un error real.
- **Diagnóstico:** El issue es un error real. La función `_save_stock_entry_items` no calculaba `qty_in_base_uom` al crear líneas de `StockEntryItem`, mientras que `_save_stock_reconciliation_items` sí lo hacía correctamente usando `convert_item_qty`.
- **Implementación:** Se modificó `_save_stock_entry_items` para:
  1. Obtener la UOM base del item usando `_item_default_uom(item_code)`
  2. Si hay UOM y UOM base, convertir la cantidad usando `convert_item_qty`
  3. Asignar el resultado a `qty_in_base_uom` en el `StockEntryItem`
  4. Agregar comentario explicativo para evitar falsos positivos futuros
- **Pruebas:** Todos los tests existentes relacionados con stock_entry pasaron (10 tests). La corrección es consistente con la forma en que los tests ya creaban `StockEntryItem` con `qty_in_base_uom`.
- **Cierre del issue:** Se cerrará con comentario explicativo indicando que el error fue corregido.

## 2026-07-09 (Corrección de fallos en filtros del buscador asistido 'search-select' para terceros)
- **Solicitud:** Investigar y corregir los fallos en las pruebas automatizadas (específicamente la prueba E2E de autocompletado con múltiples fuentes: `test_transaction_form_multi_source_autofill`).
- **Diagnóstico:** El frontend enviaba el filtro `party_type` al buscar terceros vía `/api/search-select?doctype=party&q=Demo&company=cacao&party_type=customer`. Sin embargo, la especificación de búsqueda de `Party` (`party`, `customer`, `supplier`) en `cacao_accounting/search_select.py` sólo admitía el filtro `role`. Al recibir el parámetro desconocido `party_type`, el backend devolvía error HTTP 400 ("Filtros no permitidos: party_type"), lo que causaba que la búsqueda de Cliente Demo fallara y la prueba E2E fallara por timeout.
- **Implementación:**
  - Se modificaron las especificaciones de búsqueda para `party`, `customer` y `supplier` en `_SEARCH_SELECT_REGISTRY` en `cacao_accounting/search_select.py` para admitir `"party_type"` como un filtro válido, mapeándolo al campo de validación de rol de base de datos (`"role"`).
  - Se actualizó `_apply_request_filters` para capturar tanto `"role"` como `"party_type"` para los modelos de terceros (`Party`) y aplicar la lógica unificada de `_apply_role_filter`.
- **Pruebas:** Se verificaron con éxito la prueba E2E (`tests/test_e2e_transactional_ui.py`) y la prueba de conciliación (`tests/test_08_reconciliation_reports.py`).

## 2026-07-09 (Cierre de los 4 hallazgos reales pendientes de ISSUES.md)
- **Solicitud:** Preparar y ejecutar el plan para corregir los issues pendientes R2R-04, O2C-04, S2P-09 y S2P-07, con commits semánticos firmados (sign-off) como williamjmorenor@gmail.com.
- **Decisiones de diseño:**
  - **R2R-04:** El asistente de cierre ya ejecutaba recurrentes y revaluación pero no cerraba el período. Se agregó `finalizar_cierre_mensual` que fija `run_status="closed"`, `closed_by`, `closed_at` y `AccountingPeriod.is_closed=True`; Paso 3 expuesto en UI.
  - **S2P-09:** La infra de multimoneda ya existía (DocBase + `_lookup_exchange_rate`). Solo faltaba UI: se agregó smart_select de moneda en OC/Recepción/Factura de compra y el backend persistió `transaction_currency`/`exchange_rate` calculando `base_total`. `_purchase_exchange_rate` corregido para buscar la entidad por `code` (no `id`) y devolver tasa 1:1 como fallback seguro.
  - **O2C-04:** `sales_return` implementado como espejo de `purchase_return` (registry, flujos, ruta `/sales-invoice/return/new`, template, `DeliveryNote.is_return` en UI). El posting engine ya trata `is_return` igual a `sales_credit_note`, sin cambios en accounting_engine.
  - **S2P-07 (flag + neteo automático, según decisión del usuario):** Flag `apply_advances_automatically` en `CompanyDefaultAccount` + UI. Al aplicar anticipo a factura se genera un `ComprobanteContable` de neteo (Dr Payable / Cr Advance en compras; Dr Advance / Cr Receivable en ventas) y se postea vía `post_comprobante_contable`.
- **Pruebas agregadas:** `test_e2e_monthly_close_finalizes_and_closes_period` (R2R-04), `test_s2p09_purchase_order_foreign_currency_base_total` (S2P-09), `test_sales_return_*` (O2C-04), `test_s2p07_settle_advance_generates_netting_journal` (S2P-07).
- **Calidad:** Black, ruff, mypy en verde en archivos modificados. Nota: `test_purchase_happy_path` (test_e2e_modules) es preexistente y falla por flag de proveedor S2P-08, independiente de estos cambios.
- **Commits:** `4610fdd` (R2R-04), `bb2ac5d` (S2P-09), `b31ce72` (O2C-04), `3f72f1a` (S2P-07). ISSUES.md marcado con todos los hallazgos CORREGIDOS.

## 2026-07-08 (S2P-06 y O2C-05: validaciones pre-submit en 12 endpoints)
- **Solicitud:** Analizar ISSUES.md, identificar siguiente issue (S2P-06/O2C-05: validaciones pre-submit insuficientes) e implementar validación centralizada.
- **Diagnóstico:** 6 endpoints con cero validación (solo `docstatus != 0`) y 6 con validación solo en capa de posting. Ninguno validaba compañía, fecha, tercero ni existencia de líneas en el límite del submit.
- **Implementación:**
  - `document_flow/validation.py`: nueva función `validate_submit_prerequisites()` que valida compañía, fecha, tercero (supplier/customer), al menos una línea y qty > 0.
  - Aplicada en 12 endpoints de compras (6), ventas (5) e inventario (1).
  - Endpoints sin try/except previo ahora capturan `ValueError` y muestran flash `danger`.
  - `ventas_entrega_submit` e `inventario_entrada_submit` ampliaron captura a `ValueError`.
- **Pruebas:** 12 tests unitarios en `tests/test_validation.py` cubren todos los casos. 290 tests en verde (sin regresión).
- **Calidad:** Black, ruff, mypy, flake8 en verde.
- **Commits:** `b149b09` (código), `3fa36a6` (tests), `a774532` (fix fixture), `faf08a4` (ISSUES.md).

## 2026-07-08 (O2C-03: reserva de inventario en Orden de Venta)
- **Solicitud:** Analizar ISSUES.md, identificar el siguiente issue a atender (O2C-03) e implementar reserva de inventario al aprobar Orden de Venta.
- **Semántica:** `actual_qty` = stock físico, `reserved_qty` = comprometido en OV, `available_qty` = `actual_qty - reserved_qty`.
- **Implementación:**
  - `reserved_qty` cambió a non-nullable con default 0.
  - SO submit: valida `actual_qty - reserved_qty >= qty`, incrementa `reserved_qty`.
  - SO cancel: decrementa `reserved_qty`.
  - DN submit: libera reserva solo si tiene `sales_order_id`.
  - DN cancel: restaura reserva solo si tiene `sales_order_id`.
  - `_create_delivery_note_from_invoice` propaga `sales_order_id` para facturas con `update_inventory=True`.
  - `rebuild_stock_bins` preserva `reserved_qty` existente.
  - API `/api/inventory/stock-bin-snapshot` expone `reserved_qty`.
- **Pruebas:** 8 tests nuevos en `test_stock_reservation.py`, todos en verde.
- **Validación:** Black OK, flake8 OK, mypy OK. 36 tests existentes no regresionados.
- **Commits:** `7c6c85f`, `fc336fc`, `8868cec`, `35e220c`.

## 2026-07-08 (S2P-02 + S2P-05: sobre-facturación y crash 500)
- **Solicitud:** Analizar ISSUES.md, validar el siguiente issue pendiente y proponer plan de cierre.
- **Diagnóstico:** S2P-02 (sobre-facturación contra recepción) es real: no había validación submit-time de `consumed_qty <= receipt.qty`, y `_handle_purchase_invoice_edit_post` no limpiaba relaciones viejas (doble conteo). S2P-05 (crash 500) es real: `except PostingError` no capturaba `PurchaseReconciliationError` (hereda de `ValueError`).
- **Implementación:**
  - `_validate_invoice_quantities_against_receipt()`: itera `DocumentRelation` activas, consulta `consumed_qty_for_source(receipt, invoice)` y rechaza si excede `receipt_item.qty`.
  - `_handle_purchase_invoice_edit_post`: elimina `DocumentRelation` viejas antes de recrear ítems.
  - `compras_factura_compra_submit`: llama a la validación y captura `(PostingError, ValueError, DocumentFlowError)`.
- **Pruebas:** `test_invoice_submit_validates_against_receipt`, `test_invoice_edit_cleans_old_relations`, `test_invoice_submit_rejects_over_invoice` en `test_05document_flow.py`.
- **Validación:** 26/26 tests en verde, black OK, mypy OK.
- **Commits:** `f920176` (código), `f74b0f7` (ISSUES.md).

## 2026-07-03 (Inventario: cuenta de inventario unificada por almacen/compania)
- **Solicitud:** Alinear toda la contabilidad de inventario para que la cuenta se configure solo por `Almacen/Compañia` y no queden fallbacks globales en recepción, entrega ni cálculo contable.
- **Diagnostico:** `stock_entry` ya resolvia inventario desde `WarehouseCompanyAccount`, pero `post_purchase_receipt`, `post_delivery_note`, `document_builders` y `CompanyDefaultAccount.default_inventory` seguian manteniendo un camino alterno por compañía.
- **Implementacion:** Se introdujo un helper compartido para resolver la cuenta de inventario desde `warehouse + company`, `purchase_receipt` y `delivery_note` lo usan en posting y cálculo, y se eliminó `default_inventory` de `CompanyDefaultAccount`, `/settings/default-accounts` y de los mappings base de catálogo.
- **UI:** La ficha de bodega ahora muestra código y nombre de la cuenta configurada por compañía, y la ficha de item deja de insinuar una cuenta de inventario por item.
- **Validacion:** Las pruebas focales de posting, schema y configuración administrativa se ajustan para crear `WarehouseCompanyAccount` en lugar de `default_inventory`.

## 2026-07-03 (Inventario: valuacion global por compania en configuracion)
- **Solicitud:** Implementar una entrada administrativa para establecer el metodo de valuacion de inventarios, fuera del wizard inicial, como configuracion global de la compañia y con costo promedio por defecto.
- **Diagnostico:** El motor contable ya consumia `Entity.valuation_method`, pero no existia ninguna entrada en `/settings` para administrarlo ni una regla de bloqueo cuando la compañia ya habia operado inventario.
- **Implementacion:** Se agrego `/settings/inventory-valuation` dentro de `Administracion > Configuracion General`, con selector de compañia, selector de metodo (`Costo promedio`/`FIFO`) y persistencia directa sobre `Entity.valuation_method`.
- **Bloqueo de negocio:** El cambio queda bloqueado cuando la compañia ya tiene `StockLedgerEntry` o `StockValuationLayer`, evitando alterar la semantica de costo despues de operar inventario.
- **Mobile:** La pantalla usa un formulario admin simple, apilado en mobile, sin `smart-select` ni overlays.

## 2026-07-03 (Contabilidad: arboles de cuentas y centros de costo)
- **Solicitud:** Corregir el mismo patron visual del setup en el arbol de cuentas contables y el arbol de centros de costos, incluyendo comportamiento usable en dispositivos mobiles.
- **Diagnostico:** Ambas vistas compartian el patron `.ca-tree`, pero estaban montadas sobre una tarjeta demasiado amplia con toolbar dispersa, demasiado espacio en blanco y un arbol visualmente estrecho y poco tactil en pantallas pequenas.
- **Implementacion:** Se introdujo un layout comun para arboles maestros con toolbar responsive, contexto de entidad, panel de arbol con scroll controlado y ajustes compartidos de espaciado/hover/area tactil en `.ca-tree`.
- **Mobile:** Filtros y acciones se apilan a ancho completo, el panel del arbol conserva scroll horizontal cuando hace falta y los nodos ganan altura tactil para evitar errores de pulsacion.

## 2026-07-03 (Setup inicial: ajuste visual del wizard)
- **Solicitud:** Revisar la pantalla del wizard inicial porque la captura mostraba una composicion desbalanceada y poco cuidada visualmente.
- **Diagnostico:** El layout anterior se leia como una landing page: contenedor demasiado ancho, hero verde dominante, selector de idioma pequeno y aislado, stepper lateral pesado y acciones muy separadas.
- **Implementacion:** El wizard se compacto a un ancho operativo, el hero se redujo a una cabecera sobria, el stepper paso a una barra horizontal, el selector de idioma gano ancho coherente y la marca usa `static/media/brand.svg`.
- **Responsive:** En mobile el stepper se apila en filas legibles, el contenedor usa mejor el ancho disponible y los botones se mantienen accesibles sin dominar la pantalla.

## 2026-07-03 (Smart Select: overlay visible en tablas responsivas)
- **Solicitud:** Corregir el layout de los `smart-select` agregados en Articulo, Cliente y Proveedor porque al buscar las opciones quedaban atrapadas dentro del contenedor.
- **Diagnostico:** El problema se producia cuando el menu estaba dentro de `.table-responsive` u otros contenedores con overflow; el dropdown absoluto quedaba recortado aunque la busqueda y el endpoint funcionaran correctamente.
- **Implementacion:** `smart-select.js` ahora posiciona el menu abierto con coordenadas fijas de viewport, recalcula en scroll/resize y limpia estilos al cerrar; el CSS compartido eleva el `z-index` del menu sin cambiar contratos HTML ni payloads de formularios.
- **Mobile:** La posicion se limita contra `innerWidth`/`innerHeight`, abre hacia arriba si no hay espacio inferior y evita desbordes laterales en viewports angostos.
- **Validacion:** `tests/test_10_smart_select_js.py` paso en verde y `npm test` en `cacao_accounting/static` paso con 33 pruebas.

## 2026-07-03 (Reportes contables: anulaciones/reversas y reversión de comprobantes con fecha)
- **Solicitud:** Corregir los 5 reportes contables para que el filtro de anulaciones excluya también las reversas GL cuando no se desea ver anulaciones, y ajustar `Revertir comprobante` para pedir fecha y respetar la `naming_series` del comprobante origen.
- **Reportes contables:** `FinancialReportFilters` ahora separa explícitamente `include_cancellations` del `status`, y `_apply_gl_filters()` excluye `GLEntry.is_cancelled` e `GLEntry.is_reversal` por defecto en `account-movement`, `account-summary`, `trial-balance`, `balance-sheet` e `income-statement`.
- **UI de reportes:** El checkbox del patrón financiero ahora representa la semántica real del dataset (`Mostrar anulaciones y reversas`) y el estado mostrado en el resumen contextual deja de confundir reversas con movimientos contabilizados normales.
- **Detalle de movimiento:** Las filas GL reversadas se renderizan con `voucher_status = reversal`, manteniendo visibles las reversas solo cuando el usuario decide incluir anulaciones.
- **Reversión de comprobantes:** La acción `Revertir` en el detalle del comprobante abre un modal con fecha de reversión, recomendación de uso (`Anular` en el mismo período, `Revertir` en otro) y creación del borrador con la misma `naming_series_id` y la `posting_date` elegida.
- **Numeración:** El borrador de reversión sigue naciendo sin `document_no`, pero al asignar identificador usa la serie heredada y resuelve prefijos dinámicos (`YYYY`, `MM`) con la fecha de reversión.
- **Validación:** Se ampliaron pruebas de reportes, formularios de comprobante, cobertura de rutas y E2E para cubrir exclusión de anulados/reversas, fecha obligatoria de reversión, herencia de serie y numeración en otro mes.

## 2026-07-03 (Setup inicial, Smart Select en maestros, bodega por compania e importador de lineas)
- **Solicitud:** Corregir el setup inicial para respetar idioma, completar paises/monedas de America, bloquear el selector de catalogo al crear catalogo en cero y mejorar visualmente el wizard; estandarizar Cliente, Proveedor, Item y Bodega con `smart-select`; agregar configuracion de bodega por compania; corregir el error Alpine del importador de lineas.
- **Setup inicial:** Se centralizaron catalogos de idioma, paises de America y monedas reconciliadas con el seed; el wizard renderiza textos segun idioma seleccionado y el paso de catalogo deshabilita/limpia el selector cuando se elige crear desde cero.
- **Cliente/Proveedor:** La configuracion por compania ahora es una tabla dinamica con `smart-select`, permite agregar/remover companias y sincroniza el borrado de filas persistidas sin mantener soporte de formato legacy en el POST.
- **Item/Bodega:** Item usa `smart-select` para UOM en conversiones y para compania/centro de costo en configuracion contable. Bodega incorpora una tabla `warehouse_company_account` para definir cuenta de inventario por compania y el posting resuelve inventario desde esa configuracion.
- **Importador de lineas:** Los modales de importacion ya no evaluan `schema.columns` cuando el esquema aun es `null`, aceptan compania por `Entity.code` o `Entity.id` al validar y muestran errores visibles cuando falla la carga de esquema o la validacion.
- **Validacion:** Se agregaron/regeneraron pruebas focales de setup, terceros, bodega/stock reconciliation e inventario. Queda pendiente ejecutar la suite completa por costo de tiempo.

## 2026-07-02 (Inventario: cuenta de inventario solo en bodega, valuacion en entidad)
- **Solicitud:** Separar cuenta de inventario de ItemAccount y mover metodo de valuacion a Entity.
- **Cambios aplicados:**
  - `ItemAccount.inventory_account_id` removido del modelo y codigo; la cuenta de inventario solo existe en `Warehouse.inventory_account_id`.
  - `Item.valuation_method` removido; `Entity.valuation_method` agregado con default "moving_average" (Costo Promedio).
  - `posting.py`: `_warehouse_inventory_account_id()` retorna `None` (sin fallback a ItemAccount); stock entries usan cuenta de inventario de bodega.
  - `document_builders.py`: `_item_account_id()` remueve "inventory" del mapping de ItemAccount; en ese momento purchase receipts y delivery notes quedaron usando `CompanyDefaultAccount.default_inventory` como fallback temporal.
  - `datos/dev/__init__.py`: `cargar_bodegas()` asigna `inventory_account_id` a warehouses PRINCIPAL/SUCURSAL desde cuenta `11.03.001`.
- **Tests corregidos:** 9 fixtures de `ItemAccount` en `test_07posting_engine.py` y 1 en `test_08_reconciliation_reports.py` sin `inventory_account_id`; el fallback temporal de purchase receipts y delivery notes quedó cubierto por fixtures en `CompanyDefaultAccount`.
- **Validacion:** `test_07posting_engine.py` + `test_08_reconciliation_reports.py` en verde (73 tests); mypy sin errores.

## 2026-07-01 (Cliente/Proveedor: perfil basico y cumplimiento legal)
- **Solicitud:** Completar Cliente y Proveedor con los datos basicos que faltaban: nacional/extranjero, telefono y correo predeterminados, pagina web, direccion principal, tipo de persona natural/juridica y un bloque final de cumplimiento legal con datos de representación para notificacion formal.
- **Implementacion:** `Party` ahora guarda nacionalidad, tipo de persona, telefono/correo principales, pagina web, direccion principal y un paquete de datos legales de representacion/constitucion/notificacion.
- **UI:** Los formularios de Cliente y Proveedor agregan una seccion de `Datos básicos`, una seccion de direccion principal y un bloque final de `Cumplimiento legal`. Las fichas de detalle muestran esos mismos datos en cards separadas antes de la gestion de contactos/direcciones.
- **Validacion:** Se ampliaron las pruebas de terceros y del esquema para cubrir persistencia de los nuevos campos y render del detalle. La regresion focal paso en verde.

## 2026-07-01 (Cliente/Proveedor: simplificacion de clasificacion y visibilidad de contactos)
- **Solicitud:** Eliminar el campo libre `Clasificación` en Cliente y Proveedor, y hacer más visibles `Contactos` y `Direcciones` porque en la ficha no se apreciaban claramente.
- **Implementacion:** Los formularios de alta/edicion de Cliente y Proveedor ya no exponen ni envian `classification`; la clasificacion funcional queda representada por `party_group_id` (Tipo de Cliente / Tipo de Proveedor) y el backend deja de tomar ese valor desde POST.
- **Detalle del tercero:** Las fichas de Cliente y Proveedor ya no muestran `Clasificación` en el resumen superior. La seccion compartida agrega accesos visibles a `Configuracion por compañia`, `Contactos` y `Direcciones`, con contadores y anclas internas para navegar rápido.
- **Layout:** `Contactos` y `Direcciones` quedan primero en la ficha del tercero, dejando `Configuracion por compañia` después, para priorizar la gestion operativa que el usuario estaba buscando.
- **Validacion:** `tests/test_party_management.py` en verde (`3 passed`).

## 2026-07-01 (Cliente/Proveedor: cuentas, regla fiscal y lista de precio por compania)
- **Solicitud:** Completar Cliente y Proveedor con configuracion por compania para cuenta por cobrar/pagar predeterminada, regla fiscal predeterminada y lista de precio predeterminada, tomando como base las referencias visuales compartidas.
- **Correccion de fondo:** No se creo un maestro nuevo para precios; se reutilizo `PriceList` como concepto funcional de **Lista de Precio** y `ItemPrice` sigue como detalle de precios por item. La relacion por defecto del tercero se persiste en `CompanyParty`.
- **Implementacion:** `CompanyParty` ahora guarda `default_tax_rule_id` y `default_price_list_id`. `party_settings` resuelve defaults, valida compania/tipo (`sales` vs `purchase`) y hace fallback a listas predeterminadas por compania. `search-select` incorpora `tax_rule` y `price_list`.
- **Setup inicial:** El asistente crea listas de precio predeterminadas de venta y compra por compania, localizadas segun idioma (`ES`/`EN`) y marcadas como default.
- **UI:** Cliente y Proveedor muestran y editan por compania cuenta AR/AP, lista de precio, regla fiscal y plantilla fiscal; el detalle del tercero expone esos valores en la tabla de configuracion.
- **Validacion:** Pruebas focales de terceros, setup, search-select, esquema y vistas en verde.

## 2026-07-01 (Item: configuracion contable por compañia)
- **Solicitud:** Completar el formulario de Item con una tabla de cuenta predeterminada por empresa, porque los servicios y articulos no inventariables se registran directo al costo.
- **Implementacion:** El alta de item ahora incluye una tabla minima por compañia con cuenta de gasto y centro de costo; la configuracion se persiste en `ItemAccount` usando `expense_account_id` y `cost_center_code`.
- **Regla de negocio:** Si el item es `service` o `is_stock_item=False`, al menos una fila por compañia con cuenta de gasto y centro de costo predeterminados es obligatoria; si falta cualquiera de los dos, el guardado falla.
- **UI:** La vista detalle del item muestra la configuracion contable por compañia junto a las conversiones UOM.
- **Validacion:** Se agregaron pruebas para exigir cuenta de gasto y centro de costo en servicios/no inventariables y para persistir `ItemAccount` correctamente.

## 2026-07-01 (Maestro UOM e idioma de setup)
- **Solicitud:** Mejorar el item de inventario con un maestro de UOM, conversión contra una unidad predeterminada y un feed inicial de unidades de medida, respetando el idioma elegido en el setup.
- **Implementacion:** Se agrego soporte de UOM por item con unidad predeterminada, tabla de conversiones y bloqueo de cambio de la unidad base cuando el item ya tiene registros. El alta de item ahora valida la definicion contable minima para servicios y expone el detalle de conversiones en la vista.
- **Seed inicial:** El setup ahora carga un catalogo razonable de UOM localizados segun `idioma` (`ES`/`EN`), y el seed de desarrollo evita duplicados al reutilizar los mismos codigos.
- **Validacion:** Se agregaron pruebas para persistencia de conversiones, bloqueo de unidad base tras uso y verificacion del seed de UOM en ingles; la suite focal y la regresion de vistas/esquema quedaron en verde.

## 2026-06-30 (Análisis de cobertura de código y tests para servicios)
- **Solicitud:** Analizar la cobertura de código actual en Coveralls y mejorar los tests para aumentar cobertura.
- **Análisis:** El proyecto tiene 80.4% de cobertura (22,566 líneas relevantes, 18,144 cubiertas). Se identificaron módulos sin tests: `collaboration_service`, `party_settings`, `auth/forms`, `tax_pricing_service`, `module_badges`, etc.
- **Implementación:** Se crearon `tests/test_services_simple.py` con tests unitarios para:
  - Dataclasses de `tax_pricing_service` (TaxLineResult, TaxCalculationResult, PriceSuggestion, PriceToleranceResult)
  - Función `validate_price_tolerance` (lógica de validación de tolerancia)
  - Constantes de colaboración (TASK_STATUSES, TASK_PRIORITIES)
  - Excepción CollaborationError
  - Función `module_badge` (todos los casos de estado)
  - Helper `is_truthy` de runtime_mode
  - Dataclass PartyCompanySettings
- **Resultado:** 17 tests nuevos agregados, todos pasando. Commit: `test(coverage): add tests for tax_pricing_service and collaboration_service`
- **Nota:** Tests más complejos que requieren fixtures de base de datos completa (collaboration_service con cloud mode, party_settings con CompanyParty) requieren setup más elaborado y se dejaron para próximas iteraciones.

## 2026-06-27 (Filtros de busqueda en listados)
- **Solicitud:** Accionar un pendiente real del backlog: filtros de busqueda en listados de Compras, Ventas y Bancos.
- **Implementacion:** Se agrego `cacao_accounting/list_filters.py` para aplicar `search` y `status` de forma reusable, se conectaron rutas de listados en Compras, Ventas y Bancos, y se agrego el macro `list_filters` con preservacion de filtros en paginacion.
- **UI:** Los listados transaccionales muestran busqueda y estado; terceros, bancos, cuentas bancarias y transacciones bancarias muestran busqueda simple con acciones Buscar/Limpiar.
- **Cobertura:** `tests/test_03webactions.py` valida busqueda y estado en listados de los tres modulos.

## 2026-06-27 (Limpieza de navegacion lateral)
- **Solicitud:** Evitar que `/settings/modules` e `/imports/` aparezcan como modulos de primer nivel en la barra lateral para reducir sobrecarga visual.
- **Implementacion:** Se removieron los enlaces directos de Módulos e Importaciones desde `macros.barralateral()` y se dejo `Módulos` dentro de la pantalla de Settings. Importaciones se agrego a Settings con la misma condicion de modo cloud, modulo activo y permisos.
- **Cobertura:** Se agrego prueba focal para validar que ambos accesos esten en `/settings` y no en el sidebar principal.

## 2026-06-18 (Refresh visual global)
- **Solicitud:** Mejorar la parte visual de Cacao Accounting para que se vea mas fresca, profesional, moderna, util y atractiva.
- **Implementacion:** Se agrego una capa de refresh en `cacao_accounting/static/css/cacaoaccounting.css` sobre el sistema visual existente, ajustando tokens, navbar, sidebar, contenido, tarjetas, cards de modulo, tablas, formularios, botones, alerts, dropdowns y modales.
- **Ajuste posterior:** Se removio la franja de color superior en las tarjetas de modulo para mantener una estetica mas sobria y evitar competir visualmente con los indicadores de estado.
- **Criterio UI:** La mejora se mantuvo global y conservadora para impactar pantallas principales sin tocar la logica ni los templates funcionales; se respetaron radios moderados, layout denso y controles conocidos.
- **Verificacion:** `venv/bin/python -m pytest tests/test_01vistas.py::test_visit_views -q` paso en verde (`1 passed`).

## 2026-06-18 (Actualizacion de contexto del proyecto)
- **Solicitud:** Actualizar el contexto del proyecto leyendo los documentos base de dominio, estado y pendientes para dejar continuidad operativa entre sesiones.
- **Lectura de contexto:** Se revisaron `modulos/contexto/core_concepts.md`, `modulos/contabilidad.md`, `modulos/compras.md`, `modulos/ventas.md`, `modulos/inventario.md`, `modulos/setup.md`, `modulos/relaciones.md`, `ESTADO_ACTUAL.md` y `PENDIENTE.md`.
- **Hallazgo:** El proyecto ya tiene documentada la matriz implementada de flujo documental, los hitos recientes de conciliaciones, bancos, revalorizacion, impresiones reutilizables y controles de calidad.
- **Resultado:** Se dejo preparada una nueva base de contexto para la siguiente iteracion, con continuidad historica preservada en `SESSIONS.md` y estado/pending sincronizados.

## 2026-05-24 (Backlog: cierre documental de matriz operativa)
- **Solicitud:** Revisar `PENDIENTE.md` porque el bloque `Seguimiento 2026-05-21 (Matriz de relaciones operativas)` seguía abierto aunque la implementación parecía estar aplicada.
- **Verificación:** `SESSIONS.md`, `ESTADO_ACTUAL.md`, `modulos/relaciones.md` y `cacao_accounting/document_flow/registry.py` confirman que la matriz vigente está alineada con `DOCUMENT_TYPES`, `create_actions` y `ALLOWED_FLOWS`.
- **Resultado:** Se marcó el bloque como completado en `PENDIENTE.md`, manteniendo abiertos solo pendientes no relacionados con la matriz operativa.

## 2026-05-24 (Flujo Documental Expandible: cierre de faltantes)
- **Solicitud:** Implementar el plan para superar los faltantes detectados contra `requerimiento.md`: soporte de `journal_entry`, relaciones contables desde líneas de comprobante, garantía `PaymentReference -> DocumentRelation` en anticipos y limpieza de UI duplicada.
- **Implementación:** `journal_entry` queda registrado en `DOCUMENT_TYPES` y como destino contable permitido desde documentos operativos; el árbol resuelve fecha, moneda, total y estado para comprobantes manuales. La vista `journal.html` incluye `macros.document_flow_tree("journal_entry", registro)`.
- **Relaciones:** `submit_journal` sincroniza `DocumentRelation` desde líneas con `internal_reference`/`internal_reference_id`; `cancel_submitted_journal` revierte relaciones hacia el comprobante. `apply_advance_to_invoice` completa snapshots de `PaymentReference` y crea la relación factura -> pago.
- **UI y pruebas:** Se eliminó la macro inline `document_flow_tree_script`, dejando el componente estático como única fuente. Se agregaron pruebas para journal en API/UI, relaciones contables y anticipos con relación documental.
- **Validación:** `tests/test_document_flow_tree.py` + `tests/test_05document_flow.py` en verde (`37 passed`).

## 2026-05-23 (Compras/Ventas: accesos administrativos de terceros)
- **Solicitud:** La bitacora indicaba soporte para tipos de clientes/proveedores, contactos y direcciones, pero los accesos no estaban visibles en los menus administrativos de Compras y Ventas.
- **Implementacion UI:** `compras.html` agrega accesos a **Tipos de Proveedor** y **Contactos y Direcciones de Proveedores** dentro de Configuracion del Modulo; `ventas.html` agrega **Tipos de Cliente** y **Contactos y Direcciones de Clientes**.
- **Rutas reutilizadas:** Los tipos apuntan a `/settings/party-groups` filtrado por `supplier`/`customer`; contactos y direcciones apuntan a los listados de Proveedores/Clientes, donde se gestionan desde el detalle del tercero.
- **Cobertura:** Se agrego prueba focal en `tests/test_party_management.py` y se ampliaron expectativas de rutas estaticas para las pantallas principales de Compras y Ventas.

## 2026-05-23 (Payment Entry: opción visible de cálculo fiscal)
- **Solicitud:** En `/cash_management/payment/new`, agregar la opción de cálculo de impuestos porque el formulario de pagos no la exponía claramente.
- **Implementación UI:** `bancos/pago_nuevo.html` ahora muestra una sección explícita **Impuestos y Cargos**, abierta por defecto, con acciones para `Añadir impuesto/cargo` y `Recalcular`.
- **Detalle fiscal:** El modal fiscal permite editar líneas manuales con concepto, tipo, base, tasa, monto, método de cálculo, tratamiento contable, prorrateo, cuenta y observaciones; las líneas automáticas siguen viniendo de `/api/fiscal/preview`.
- **Cobertura:** `tests/test_fiscal_preview.py::test_forms_render_tax_charges_block` valida que el formulario de pagos renderice las acciones fiscales y el modal de cálculo.

## 2026-05-22 (Corrección UX de Payment Entry: header, tercero y cheque)
- **Solicitud:** Ajustar `/cash_management/payment/new` porque la app en 8080 mostraba errores de encabezado y luego alinear `pago.html` con el UX de `journal.html`.
- **Formulario nuevo:** El encabezado queda ordenado como Tipo de pago, Fecha, Compañía, Cuenta bancaria, Forma de pago, Secuencia y Moneda; todos los selectores principales usan `smart-select`.
- **Tercero:** Se separa en dos selectores explícitos: Tipo de tercero y Tercero filtrado por Cliente/Proveedor según la selección previa.
- **Cheques:** El contador externo solo aparece para `mode_of_payment=check`; el número de cheque es de solo lectura y se toma del contador, sin edición manual en el formulario.
- **Backend:** La moneda se toma de la cuenta bancaria, el tipo de cambio queda gestionado por backend/posting y los contadores externos se ignoran para pagos que no sean cheque.
- **Detalle:** `bancos/pago.html` adopta la estructura visual de `journal.html`, con tarjeta de cabecera, datos clave, referencias y asientos GL.
- **Verificación parcial:** `tests/test_payment_entry_improved.py` en verde (`37 passed`).

## 2026-05-22 (Cierre gaps Payment Entry: referencias, anticipos y candidatos)
- **Solicitud:** Implementar el plan para cerrar gaps detectados en `requerimiento.md` y `payment.md` sobre `payment_entry`.
- **Modelo:** `PaymentEntry` ahora conserva moneda y `PaymentReference` guarda snapshot mínimo para auditoría/conciliación futura: tipo lógico, documento visible, fecha, tercero, compañía, moneda, saldo posterior, tasa y diferencia.
- **Anticipos:** Los pagos creados desde Orden de Compra/Venta precargan referencia a la orden, crean `DocumentRelation` activa y se mantienen como pago abierto disponible para aplicación futura, sin reducir saldos AR/AP de facturas.
- **Carga manual:** Se agregó endpoint de candidatos de referencia para pagos, filtrado por compañía/tercero/tipo documental; `pago_nuevo.html` lo usa para cargar facturas, notas y órdenes compatibles.
- **Validaciones:** `pay`/`receive` exige tercero; notas crédito/débito validan dirección de pago/cobro; anulación conserva `PaymentReference` y revierte relaciones sin borrar historial funcional.
- **Verificación:** `tests/test_payment_entry_improved.py` (`31 passed`), `tests/test_06transaction_closure.py` + `tests/test_07posting_engine.py` (`40 passed`) y `tests/test_04database_schema.py` (`210 passed`).

## 2026-05-22 (Simplificacion de `modulos/relaciones.md`)
- **Solicitud:** Simplificar `modulos/relaciones.md` para reflejar solo los parches cubiertos por la implementacion actual.
- **Cambio aplicado:** Se reemplazo la propuesta extensa por una matriz resumida y operativa alineada al contrato real de `document_flow` (`DOCUMENT_TYPES` + `ALLOWED_FLOWS`).
- **Alineacion UI/Backend:** Se dejo explicito que las acciones `Crear` se gobiernan por `document_flow_trace` sin via legacy hardcodeada.
- **Resultado:** Documento mas corto, mantenible y sincronizado con el estado real del sistema.

## 2026-05-22 (Eliminacion de remanente legacy en acciones Crear)
- **Solicitud:** No dejar implementacion legacy tras la unificacion de acciones `Crear` basada en `document_flow`.
- **Limpieza final:** Se elimino la macro obsoleta `crear_dropdown` de `cacao_accounting/templates/macros.html` al no tener llamadas activas en templates.
- **Resultado:** Todas las acciones de creacion en detalles quedan centralizadas exclusivamente en `document_flow_trace` + `create_actions` del backend.
- **Verificacion:** Busqueda global en templates sin coincidencias de `crear_dropdown(` y sin errores de plantilla en `macros.html`.

## 2026-05-21 (Unificación UI `Crear` basada 100% en document_flow)
- **Solicitud:** Eliminar acciones `Crear` hardcodeadas en vistas de detalle para evitar divergencia UI/backend.
- **UI Compras/Ventas:** Se removieron dropdowns manuales `macros.crear_dropdown(...)` en detalles transaccionales de Solicitud/Cotización/Orden/Recepción/Factura, manteniendo workflow y navegación.
- **Estrategia unificada:** Las acciones de creación quedan centralizadas en `document_flow_trace`, consumiendo exclusivamente `create_actions` del backend.
- **Consistencia de notas:** Los detalles de factura/nota conservan trazabilidad dinámica por `registro.document_type`, evitando mezclar acciones entre factura normal y notas.
- **Verificación:** Regresión en verde: `tests/test_03webactions.py` + `tests/test_01vistas.py` (`20 passed`).

## 2026-05-21 (Expansión notas -> pago/reembolso + alineación matriz)
- **Solicitud:** Completar pares faltantes `credit/debit notes -> payment_entry`, con prefill operativo en Bancos y alinear documentación de `relaciones.md`.
- **Flujo documental:** `registry.py` agrega tipos documentales explícitos `purchase_credit_note`, `purchase_debit_note`, `sales_credit_note`, `sales_debit_note` con acciones de `Crear` hacia `payment_entry`.
- **Contrato de relaciones:** Se incorporan pares `purchase_credit_note -> payment_entry`, `purchase_debit_note -> payment_entry`, `sales_credit_note -> payment_entry`, `sales_debit_note -> payment_entry` en `ALLOWED_FLOWS`.
- **Bancos / Prefill:** `bancos_pago_nuevo` ahora acepta `from_purchase_credit_note`, `from_purchase_debit_note`, `from_sales_credit_note`, `from_sales_debit_note` y define `payment_type`/`party_type` según tipo de nota.
- **Trazabilidad:** Al registrar referencias de pago, `create_document_relation` usa `invoice.document_type` real (nota vs factura) para evitar pérdida semántica en flujo.
- **UI detalle:** Facturas/Notas de Compra y Venta ahora usan `registro.document_type` en `document_flow_trace` y muestran acciones de pago/reembolso consistentes por tipo documental.
- **Matriz funcional:** `modulos/relaciones.md` se actualiza para reflejar estado implementado y decisión de modelar devolución de venta operativa sobre `sales_credit_note`.
- **Verificación:** Pruebas en verde: `tests/test_05document_flow.py` (`17 passed`) y `tests/test_03webactions.py` (`19 passed`).

## 2026-05-21 (Expansión create_actions/ALLOWED_FLOWS: anticipos y notas desde recepción)
- **Solicitud:** Iniciar implementación de la expansión pendiente de pares en la matriz de `modulos/relaciones.md`.
- **Flujo documental:** `registry.py` incorpora acciones `Crear Pago` desde Orden de Compra y Orden de Venta, además de `Crear Nota de Crédito` y `Crear Nota de Débito` desde Recepción de Compra.
- **Contrato de relaciones:** Se agregaron pares `purchase_order -> payment_entry`, `sales_order -> payment_entry`, `purchase_receipt -> purchase_credit_note` y `purchase_receipt -> purchase_debit_note` en `ALLOWED_FLOWS`.
- **Backend Bancos:** `bancos_pago_nuevo` ahora acepta origen desde `from_purchase_order` y `from_sales_order` para prefill básico de pago/anticipo.
- **Cobertura:** `tests/test_05document_flow.py` amplía validaciones de acciones nuevas, URLs con `query_params` para notas desde recepción y presencia de pares nuevos en `is_allowed_flow`.
- **Verificación:** Pruebas en verde: `tests/test_05document_flow.py` (`16 passed`) y `tests/test_03webactions.py` (`19 passed`).

## 2026-05-21 (Hardening pre-merge de flujo documental)
- **Solicitud:** Atender observaciones antes de merge para alinear contrato `create_actions`, reglas de habilitación y consistencia entre UI y backend.
- **Implementación backend:** `document_flow/tracing.py` ahora serializa `model_target_type`, `enabled` y `condition`; además filtra acciones deshabilitadas (`enabled=False`) antes de exponerlas al panel dinámico.
- **Consistencia de flujos:** `document_flow/registry.py` amplía `ALLOWED_FLOWS` con pares lógicos para notas de débito/crédito y devoluciones en Compras y Ventas (Purchase Order/Receipt/Invoice y Delivery Note/Sales Invoice).
- **Cobertura:** `tests/test_05document_flow.py` incorpora validación de `create_url` + `query_params` para acciones derivadas y prueba explícita de exclusión de acciones deshabilitadas.
- **Verificación:** Pruebas en verde tras cambios: `tests/test_05document_flow.py` (`14 passed`) y `tests/test_03webactions.py` (`19 passed`).

## 2026-05-21 (Inicio implementación matriz de relaciones: fase núcleo + UI dinámica)
- **Solicitud:** Iniciar implementación de brechas definidas en `modulos/relaciones.md` para acercar el flujo documental al resultado funcional esperado.
- **Implementación (fase inicial):** `document_flow` ahora serializa `create_actions` con URL navegable (`create_url`) y soporte de `query_params`; esto habilita acciones de creación dinámicas en el panel de trazabilidad.
- **Registro de flujos:** `registry.py` amplió acciones `Crear` en tipos existentes con rutas ya soportadas: Solicitud de Compra incorpora Solicitud de Cotización; Pedido de Venta incorpora Orden de Venta; se agregan acciones de Devolución y Nota de Débito/Crédito en Compra/Venta donde ya existe endpoint de factura con `document_type`.
- **UI:** `macros.document_flow_trace` ahora muestra sección **Acciones disponibles** con botones dinámicos derivados del resumen de flujo, reduciendo dependencia de botones hardcodeados en detalles.
- **Verificación:** Pruebas focales en verde tras cambios: `tests/test_05document_flow.py` (`9 passed`) y `tests/test_03webactions.py` (`19 passed`).

## 2026-05-21 (Importaciones: recuperación silenciosa sin lotes pendientes)
- **Solicitud:** Evitar el log de error `Error al recuperar lotes de importación` cuando no hay lotes pendientes o el esquema de importaciones aún no está inicializado.
- **Implementación:** `recover_crashed_batches()` ahora verifica que existan las tablas requeridas, retorna `0` cuando no hay lotes vencidos y solo hace `commit` si recupera lotes reales; el log de arranque usa formato correcto de Loguru.
- **Cobertura:** Se añadieron pruebas para arranque sin tablas, recuperación sin pendientes y marcado de un lote procesando vencido como fallido.
- **Ajuste UI:** Las plantillas de Importaciones usan el bloque `contenido` correcto de `base.html`; el índice muestra estado vacío accionable y el formulario de nuevo lote usa `smart-select` en orden Compañía → Tipo de registro → Serie/Secuencia filtrada por compañía y registro, con Libro Contable solo para comprobantes contables.
- **Cobertura S2P/O2C:** El selector de tipo de registro ahora agrupa Source to Pay y Order to Cash, y el servicio incorpora adaptadores transaccionales para solicitudes, cotizaciones, órdenes, recepciones/entregas y facturas de compra/venta.
- **Comprobantes contables:** En importación, no seleccionar Libro Contable se interpreta como todos los libros activos de la compañía; si se selecciona uno, se importa solo para ese libro.
- **Importar líneas y Actualizar Elementos:** Source to Pay, Order to Cash e Inventario muestran `Importar líneas` para carga masiva de detalle. Los documentos derivados mantienen `Actualizar Elementos` desde fuentes reales con ítems abiertos de la misma compañía y tercero; Cotización de Proveedor usa el doctype real `purchase_quotation` para traer líneas desde Solicitud de Cotización.
- **Acciones operativas:** Todos los formularios transaccionales de Compras, Ventas e Inventario exponen ambas acciones: `Actualizar Elementos`, incluyendo registros existentes del mismo tipo documental con líneas abiertas, e `Importar líneas`.
- **Botones con iconos:** El macro transaccional agrega iconos a las acciones visibles principales, modales de actualización/importación, detalle de línea, impuestos y preferencias de columnas.
- **Comprobante contable manual:** El formulario de comprobantes mantiene `Importar líneas` mediante la API común de line import para cuentas/débitos/créditos, pero no muestra `Actualizar Elementos` porque sus líneas no son ítems ni se derivan de documentos operativos.

## 2026-05-21 (Contabilidad: sección propia para Presupuesto)
- **Solicitud:** Mover las entradas de administración de presupuestos y reporte Real versus Presupuesto fuera del bloque general de reportes del módulo de Contabilidad.
- **Implementación UI:** `contabilidad.html` ahora presenta una tarjeta independiente **Presupuesto** con `Administrar Presupuestos` y `Real versus Presupuesto`; la tarjeta **Reportes del Módulo** queda reservada para reportes contables generales.
- **Cobertura:** Se actualizó la ruta estática de `/accounting/` para verificar que la nueva sección y sus dos enlaces sigan renderizando.

## 2026-05-19 (UX fiscal: alta manual de impuestos/cargos)
- **Solicitud:** Resolver que el bloque `Impuestos y Cargos` no tenía acción para añadir nuevos impuestos/cargos, y revisar el pendiente de prorrateo capitalizable en inventario.
- **Implementación UI:** `transaction-form.js` y `transaction_form_macros.html` agregan acción `Añadir impuesto/cargo`, modal editable para líneas manuales, eliminación de líneas manuales y recálculo local de resumen.
- **Backend fiscal:** `fiscal_preview_service.py` conserva reglas canónicas persistidas y adjunta líneas manuales marcadas por el formulario, evitando duplicar líneas automáticas reenviadas.
- **Backlog inventario:** Se precisó que el motor `LandedCostEngine` ya calcula prorrateos, pero sigue pendiente persistir dichas asignaciones en `StockValuationLayer` dentro del flujo transaccional.
- **Verificación:** Pruebas focales en verde: `tests/test_tax_rules.py` + `tests/test_fiscal_preview.py` (`9 passed`) y `npm test -- --grep transaction-form` (`7 passing`).

## 2026-05-19 (Fix FIXME fiscal: preview canónico, cobros y FK nullable)
- **Solicitud:** Analizar `FIXME.md` y resolver los issues identificados sobre el MVP fiscal.
- **Preview fiscal:** `fiscal_preview_service.py` ahora recarga reglas canónicas persistidas antes de considerar líneas reenviadas por el cliente, conservando solo campos editables como cuenta/notas del preview previo.
- **Cobros:** `payment_entry` con `payment_type="receive"` resuelve un perfil fiscal de cobro con `applies_to="sales"` y `recognition_event="collection_confirmed"`.
- **UX transaccional:** `transaction-form.js` omite llamadas automáticas al preview fiscal para doctypes fuera de la matriz, evitando errores iniciales en cotizaciones y otros flujos no soportados.
- **Persistencia:** `fiscal_persistence_service.py` normaliza `account_id` vacío a `NULL` antes de guardar `DocumentTaxLine`.
- **Verificación:** Pruebas focales en verde: `tests/test_tax_rules.py` (`6 passed`) y `npm test -- --grep transaction-form` (`6 passing`).

## 2026-05-19 (Cierre review final: submit_document + robustez bancos)
- **Solicitud:** Resolver dos pendientes finales de review: confirmar/garantizar consumo del snapshot fiscal en `submit_document` y robustecer manejo transaccional/errores en `bancos_pago_nuevo`.
- **Implementación:** Se añadió prueba de integración en posting (`test_submit_sales_invoice_uses_persisted_fiscal_snapshot`) que valida GL generado desde snapshot persistido al ejecutar `submit_document`.
- **Robustez Bancos:** Se reforzó `bancos_pago_nuevo` para tratar también errores `ArithmeticError` dentro del mismo rollback; se añadió prueba (`test_payment_creation_rolls_back_when_fiscal_payload_is_invalid`) que confirma rollback completo cuando el payload fiscal es inválido.
- **Trazabilidad:** `PENDIENTE.md` y `ESTADO_ACTUAL.md` se actualizaron para marcar como completados persistencia fiscal real y consumo en posting.

## 2026-05-19 (Seguimiento review: faltantes fiscales de persistencia y posting)
- **Solicitud:** Atender comentario de revisión que señala brechas en la implementación fiscal MVP.
- **Resultado:** Se dejó explícito en `PENDIENTE.md` y `ESTADO_ACTUAL.md` que aún faltan dos frentes críticos: (1) persistencia fiscal real por documento con snapshot inmutable de reglas; (2) integración de ese payload persistido en el posting de `purchase_invoice`, `sales_invoice` y `payment_entry`.
- **Alcance de esta iteración:** Sin cambios funcionales en backend/UI; se actualizó trazabilidad del estado para evitar ambigüedad entre preview visual y persistencia/contabilización final.

## 2026-05-19 (MVP fiscal: matriz + API preview + UX común con modal por línea)
- **Solicitud:** Ejecutar el plan MVP ampliado para Compras, Ventas, Inventario y Bancos, incorporando matriz fiscal por tipo documental, API unificada de preview y bloque UX común de `Impuestos y Cargos`.
- **Requisito UX confirmado:** Se mantiene patrón visual alineado al framework transaccional existente, con capacidad de ampliar cada línea fiscal en modal para capturar información adicional.
- **Implementación core:** Se agregó `cacao_accounting/fiscal_preview_service.py` con matriz fiscal por documento y cálculo unificado usando `FiscalEngine` + `TaxRuleContext` persistidas.
- **API unificada:** Nuevo endpoint `POST /api/fiscal/preview` en `cacao_accounting/api/__init__.py` para que todos los formularios consulten el mismo preview.
- **UX común transaccional:** `transaction_form_macros.html` y `static/js/transaction-form.js` ahora incluyen bloque `Impuestos y Cargos`, resumen (`Subtotal/Impuestos/Total`) y modal por línea fiscal.
- **Bancos (alcance final):** Se integró el bloque únicamente en **Entrada de Pagos** (`bancos/pago_nuevo.html`). Nota de Débito, Nota de Crédito y Transferencia interna quedaron explícitamente fuera de este alcance por requerimiento.
- **Seguridad:** Se corrigió exposición de detalle de excepción en API de preview y se revalidó con `codeql_checker` (sin alertas).
- **Verificación:** Black, Ruff, Flake8, Mypy, pydocstyle, pytest (`--slow=True`) y CodeQL en verde para los cambios de la iteración.

## 2026-05-17 (AR/AP y terceros: tipos, edicion y contactos)
- **Solicitud:** Resolver pendientes de AR/AP y Terceros: `PartyGroup`, edicion/visualizacion por compania para Cliente/Proveedor y multiples direcciones/contactos, incluyendo Tipo de Cliente / Tipo de Proveedor.
- **Modelo y catalogo:** Se agrego `PartyGroup` global por `group_type` (`customer`/`supplier`) y `Party.party_group_id`, manteniendo `classification` como campo legacy sincronizado con el nombre del grupo.
- **UI y administracion:** Administracion incluye CRUD `/settings/party-groups`; Cliente y Proveedor tienen selector Smart Select de tipo, rutas de edicion y detalle enriquecido con configuracion por compania.
- **Contactos y direcciones:** Se exponen altas, edicion inline y desactivacion para multiples `Contact`/`Address` vinculados via `PartyContact` y `PartyAddress`, sin crear estructuras duplicadas.
- **Verificacion:** Pruebas focales de esquema, search-select, flujos de terceros, Mypy, Ruff, Flake8, Black, pydocstyle focal y render general de vistas quedaron en verde.

## 2026-05-17 (Exchange Revaluation NIIF multiledger)
- **Solicitud:** Finalizar la implementacion de revalorizacion de moneda contable segun `requerimiento.md` y marcar el pendiente de `ExchangeRevaluation` como completado.
- **Servicio:** Se agrego `ExchangeRevaluationService` para ejecutar runs auditables por compania/periodo, calcular diferencias incrementales contra el saldo ledger actual, omitir la moneda origen, registrar runs sin diferencias y anular revalorizaciones con reversos GL append-only.
- **Modelo y trazabilidad:** `ExchangeRevaluation`, `ExchangeRevaluationItem` y `GLEntry` conservan snapshots de saldos, tasas, ledger, documento, tercero, cuenta monetaria y `exchange_revaluation_run_id`.
- **UI y cierre mensual:** Contabilidad incluye listado, formulario minimo, detalle solo lectura y anulacion de revalorizaciones; el asistente de cierre mensual ejecuta el mismo servicio despues de recurrentes.
- **Verificacion:** Pruebas focales de servicio/rutas y regresion de esquema/cierre en verde; suite completa `pytest --slow=True` paso (`681 passed`). Black, Ruff, Flake8, Mypy focal y pydocstyle focal quedaron en verde.

## 2026-05-17 (Fix missing pydocstyle)
- **Solicitud:** Instalar `pydocstyle`, agregar docstrings faltantes en `cacao_accounting` y actualizar `AGENTS.md` con una regla breve de documentación.
- **Ajuste aplicado:** Se agregó `pydocstyle` a `development.txt`, se incorporó su ejecución en `.github/workflows/python-package.yml` y `run_test.sh`, y se añadió en `AGENTS.md` la instrucción explícita de documentar módulos/clases/funciones con docstrings.
- **Docstrings en `cacao_accounting`:** Verificación con `pydocstyle --convention=pep257` y análisis AST de elementos públicos (`TOTAL=0`) sin faltantes; no fue necesario modificar archivos Python del paquete.
- **Verificación:** `black`, `ruff`, `flake8`, `mypy`, `pytest` y `pydocstyle` en verde.

## 2026-05-17 (Cierre parcial de reglas fiscales, mapping contable y multimoneda)
- **Solicitud:** Completar la implementación iniciada de impuestos/gastos atendiendo los reviews, con prioridad en CRUD de reglas fiscales, mapping de cuentas contables y multimoneda.
- **Reglas fiscales:** Se agregó el modelo persistido `TaxRule`, el servicio `tax_rule_service.py` para crear/editar/eliminar/cargar reglas y la pantalla administrativa `/settings/tax-rules`.
- **Mapping contable:** `AccountingMapper` ahora diferencia eventos `payment_confirmed` y `collection_confirmed`, generando líneas pro-forma para tercero, banco/caja, retenciones y cuentas de ganancia/pérdida cambiaria.
- **Multimoneda:** `SettlementEngine` calcula diferencia cambiaria realizada y `JournalEntryLineProforma` conserva moneda documento/compañía, monto en ambas monedas y tipo de cambio usado.
- **Verificación:** Validación focal en `.venv` con `ruff`, `flake8`, `mypy` y `pytest` para `tests/engines/test_settlement_engine.py`, `tests/engines/test_mapper.py`, `tests/test_tax_rules.py` y `tests/test_04database_schema.py` (`205 passed` en la corrida combinada).

## 2026-05-17 (Motor fiscal/gastos listo para acoplarse a transacciones)
- **Solicitud:** Cerrar los pendientes del review para dejar el motor de impuestos y otros gastos listo para acoplarlo a transacciones reales.
- **Acoplamiento transaccional:** Se agregaron `document_builders.py` y `gl_posting_builder.py` para convertir `PurchaseReceipt`, `PurchaseInvoice`, `SalesInvoice` y `PaymentEntry` en `CalculationContext` y persistir el `JournalEntryProforma` resultante como `GLEntry` real dentro de `contabilidad/posting.py`.
- **Cobertura funcional:** El flujo de posting ahora usa el motor en recepciones, facturas de compra/venta, notas de crédito y pagos/cobros; también carga reglas `TaxRule` persistidas desde BD y mantiene compatibilidad con `TaxTemplate` como fallback cuando no hay reglas configuradas.
- **Fiscal DAG + settlement extendido:** `FiscalEngine` pasó a ordenar reglas por dependencias (DAG), `SettlementEngine` ahora calcula descuentos por pronto pago y revaluación no realizada, y `AccountingMapper` genera los offsets contables necesarios para diferencia cambiaria realizada/no realizada y descuentos de liquidación.
- **Verificación:** `black --check cacao_accounting/`, `ruff`, `flake8`, `mypy`, `pydocstyle` focal y `pytest -v -s --exitfirst --slow=True` completo en `.venv` quedaron en verde (`672 passed`).

## 2026-05-16 (Merge limpio rama remota de registros bancarios)
- **Solicitud:** Integrar `feat/banking-module-registers-16721791397278534001` sin perder funcionalidad local/remota y dejando el workflow de Python en verde.
- **Resolucion de conflictos:** Se conservaron versiones locales en archivos no relacionados (Compras/Ventas/Inventario/tests/macros) y se integraron cambios bancarios de la rama remota en rutas/templates de pagos, notas y transferencias.
- **Ajustes de compatibilidad:** En `bancos_pago_nuevo` se removio el uso de campos inexistentes en `PaymentEntry`, se mapearon cuentas GL para transferencias internas desde cuentas bancarias origen/destino y se mantuvo soporte de numeracion externa.
- **UI Bancos:** Se incorporaron `nota_nueva.html` y `transferencia_nueva.html`, se migro `pago_nuevo.html` al patron UI unificado con smart-select y se restauro el `data-test_info` requerido por tests de vistas.
- **Verificacion:** `black`, `ruff`, `flake8`, `mypy` y `pytest` completo pasaron (`618 passed, 5 skipped`), ademas de pruebas focalizadas de pagos/closure.

## 2026-05-16 (Moneda y formato numerico en documentos operativos)
- **Solicitud:** En comprobantes de Compras, Ventas e Inventario, mostrar la moneda del registro y aplicar formato monetario con codigo de moneda y separador de miles; las cantidades deben mostrarse con 4 decimales.
- **Ajuste aplicado:** Se agregaron helpers globales Jinja (`document_currency_code`, `format_money_with_currency`, `format_quantity`) para resolver moneda del documento, formatear importes como `NIO 1,000.00` y cantidades como `10.0000`.
- **Templates:** Los detalles de Solicitudes/Cotizaciones/Ordenes/Recepciones/Facturas de Compra, Solicitudes/Cotizaciones/Ordenes/Entregas/Facturas de Venta y Movimientos de Inventario ahora muestran `Moneda`, totales monetarios formateados y pasan el codigo de moneda a la tabla compartida de lineas.
- **Verificacion:** Render contra `cacaoaccounting.db` confirmado en Compra y Venta (`Moneda: NIO`, `Precio / Costo Unitario (NIO)`, `NIO 5.00`, cantidades a 4 decimales). Pruebas focalizadas `test_visit_views` y `test_transaction_forms_render_unified_grid_and_detail_text` pasaron (`2 passed`), con Ruff, Flake8 y Mypy en verde para `cacao_accounting/__init__.py`.

## 2026-05-16 (Mejora de moneda e importes en comprobante contable)
- **Solicitud:** Mostrar la moneda del comprobante contable con codigo (`NIO`) y formatear importes con separador de miles.
- **Confirmacion DB:** En `cacaoaccounting.db`, el comprobante `cacao-JOU-2026-05-00001` pertenece a `cacao`, la entidad usa moneda `NIO`, el libro `FISC` usa `NIO` y las lineas son `1000` / `-1000`.
- **Ajuste aplicado:** La vista de comprobante resuelve la compania por `Entity.code`, muestra solo el codigo de moneda y formatea `Debe`/`Haber` como `1,000.00` tanto en tabla como en detalle/modal.
- **Ajuste posterior:** Se agrego el codigo de moneda a los encabezados y celdas de `Debe`/`Haber`, mostrando valores como `NIO 1,000.00`.
- **Verificacion:** Render contra `cacaoaccounting.db` confirmado con `NIO` y `1,000.00`; `tests/test_01vistas.py::test_visit_views` paso (`1 passed`), con Ruff y Flake8 en verde para el modulo tocado.

## 2026-05-16 (Alineacion de leyenda en comprobante manual)
- **Solicitud:** Alinear la leyenda `Comprobante manual` del detalle del comprobante contable para que coincida con el patron visual de documentos operativos como Solicitud de Compra.
- **Ajuste aplicado:** `journal.html` agrupa el numero, estado y subtitulo en el mismo bloque de cabecera; la leyenda deja de quedar centrada por el layout flex de `.ca-card-header`.
- **Verificacion:** Render general de vistas validado con `tests/test_01vistas.py::test_visit_views` (`1 passed`).

## 2026-05-16 (Validacion completa CI y cobertura)
- **Solicitud:** Ejecutar pruebas unitarias completas con cobertura Python y JavaScript, asegurando que el workflow `.github/workflows/python-package.yml` pase correctamente y que la cobertura de Contabilidad, Compras, Inventario y Ventas sea adecuada.
- **Correccion aplicada:** Se activaron los terceros demo (`Cliente Demo SA` y `Proveedor Demo SA`) en `CompanyParty` para la compania `cacao`, de modo que los `smart-select` filtrados por compania encuentren clientes/proveedores en formularios transaccionales.
- **Pruebas E2E:** `tests/test_e2e_transactional_ui.py` se actualizo para seleccionar la compania demo real del seed y liberar la conexion SQLAlchemy antes de borrar la base temporal en Windows.
- **Formato:** Se normalizo con Black `tests/test_e2e_modules.py` y `tests/test_uoms_full.py`.
- **Verificacion:** `pytest` completo con cobertura paso (`623 passed`) con cobertura Python total de 83%. Mocha paso (`21 passing`) y cobertura JavaScript total fue 77%. Build/twine, flake8, ruff, mypy, black y `npm ci && npm test` quedaron en verde.

## 2026-05-15 (Inicio de implementación de paridad funcional en formularios transaccionales)
- **Compras:** Se implementaron rutas `edit` y `duplicate` para Solicitud de Cotización, Cotización de Proveedor, Orden de Compra, Recepción de Compra y Factura de Compra. También se completaron las rutas faltantes de `submit` y `cancel` para Solicitud de Cotización y Cotización de Proveedor.
- **Ventas:** Se implementaron rutas `edit` y `duplicate` para Pedido de Venta, Cotización, Orden de Venta, Nota de Entrega y Factura de Venta.
- **Inventario:** Se implementaron rutas `edit` y `duplicate` para Movimiento de Inventario (`stock-entry`).
- **Templates de detalle:** Se añadió visibilidad condicional de acciones `Editar` y `Duplicar` por estado (`docstatus`), manteniendo `Aprobar/Anular`, `Crear`, `Listado` y `Nuevo`.
- **Templates de captura:** Los formularios reutilizados para edición muestran ahora breadcrumb y títulos consistentes en modo `edit`.
- **Validación:** Pruebas web focalizadas ejecutadas con éxito en `tests/test_03webactions.py` (4 passed).

## 2026-05-16 (Reparación de Smart Select en formularios transaccionales)
- **Diagnóstico:** El modal compartido de detalle de línea se renderizaba con `modalLine = null`, provocando errores Alpine en expresiones `modalLine.*` y bloqueando los `smart-select` del framework transaccional.
- **Correcciones aplicadas:** `transaction_form_macros.html` ahora crea el contenido del modal con `x-if` cuando existe `modalLine`, pasa valores iniciales dinámicos a los selectores del modal y activa `loadOnFilterChange` para autoseleccionar la secuencia dependiente de compañía.
- **Cobertura:** Se agregó prueba JS para abrir/guardar detalle de línea con dimensiones existentes y prueba de render sobre `/buying/purchase-request/new` para validar `x-if`, valores iniciales dinámicos y `loadOnFilterChange`.
- **Ajuste posterior:** Se eliminó el `$dispatch('input')` de los hidden inputs porque convertía valores escalares en objetos Alpine (`[object Object]`). El hidden vuelve a ser la fuente de verdad para filtros, `naming_series` filtra por `company + entity_type`, e items/dimensiones consultan con compañía obligatoria.
- **UOM por item:** El selector de item ahora conserva el payload de la opción para llenar descripción, UOM predeterminada y UOMs permitidas. El selector UOM de la línea filtra por los códigos permitidos del item y ya no consulta todas las unidades globales.

## 2026-05-16 (Corrección de fallos de CI en smart-select.js)
- **Diagnóstico:** 7 tests JS fallando: 5 por `this.$watch is not a function` en entorno de pruebas sin Alpine, 1 por normalización de `el.value` objeto en selector-filter, 1 por arrays de filtros enviados como cadena unida en lugar de params separados.
- **Correcciones aplicadas en `cacao_accounting/static/js/smart-select.js`:**
  1. Guard `if (typeof this.$watch === 'function')` en `init()` para compatibilidad con entornos de test.
  2. `normalizeValue`: arrays ahora se preservan (no se unen con coma); selector-filter normaliza `el.value` objeto via `normalizeObjectValue`.
  3. `appendParam`: maneja arrays iterando y agregando cada elemento como param separado.
  4. `onFocus()`: preload en foco solo cuando `preloadOnFocus=true` (no cuando solo `preload=true`).
  5. `fetchOptions` y `preloadOptions`: usan `appendParam` para agregar filtros, habilitando multi-params.
- **Resultado:** 17/17 JS passing, 607/607 Python passing, CodeQL sin alertas.


- **Revisión de parche:** Se verificó que `72.patch` contiene los commits `4e8b192`, `3ea5f45` y `49a9081`, ya presentes en la rama.
- **Incorporación/ajuste mínimo:** Se aplicó formato Black en `tests/test_e2e_transactional_ui.py` para eliminar el único fallo de estilo pendiente.
- **Verificación completa:** Black, Ruff, Flake8, Mypy y Pytest ejecutados en `.venv` con resultado exitoso (`607 passed, 5 skipped`).

## Summary of Previous Milestones (May 2026)
- **Architecture:** Standardized on Python 3.12+, Flask, and Alpine.js. Implemented a clear separation between routes, services, and repositories.
- **Accounting Core:** `GLEntry` established as the single source of truth. Multi-ledger support via `Book` model and `ledger_id`. Real multi-currency support (base and original amounts).
- **Posting Engine:** Automated GL posting for Sales/Purchase Invoices, Payments, and Stock Entries. Implemented FIFO and Moving Average inventory valuation.
- **UI/UX Pattern:** Adopted the "Voucher Pattern" (Header + Items) for all transactional and master data forms.
- **Document Flow:** Implemented a transversal framework for document relations and traceability.
- **Series & Naming:** Centralized identifier generation with support for company prefixes and audit logs.
- **Smart Select Framework:** Implemented a controlled autocomplete framework for large catalogs (Accounts, Parties, Items, etc.).
- **Reporting:** Built a robust financial reporting framework with drill-down, saved views, and advanced XLSX export.
- **Master Data:** Migrated Items, Clients, Suppliers, Banks, and Accounts to the unified Voucher Pattern.
- **Setup & Quality:** Comprehensive initial setup wizard. Enforced quality controls via Black, Ruff, Flake8, Mypy, and Pytest.

---

## 2026-05-12 (Cierre del módulo de contabilidad: Comprobantes Recurrentes y Asistente de Cierre)
- **Comprobantes Recurrentes:** Framework completo para plantillas contables con validación de balance y estados operativos (`draft`, `approved`, `cancelled`, `completed`).
- **Asistente de Cierre Mensual:** Activado primer paso para filtrar y aplicar plantillas recurrentes por periodo contable.
- **Integración:** Facturas inicializan `outstanding_amount` y gran total al aprobarse.
- **UX:** Unificación de interfaz siguiendo el Voucher Pattern y adición de filtros de búsqueda.

## Sesión: 2026-05-11 - Mejora de UX y Consistencia en Módulo Contable
- **Rediseño:** Formularios de Cuentas y Entidades actualizados. Eliminación de campos redundantes y soporte `smart-select` para cuentas padre.
- **UX Uniforme:** Aplicado diseño de Journal Entry a Unidades, Libros, Proyectos, Monedas, Tasas de Cambio y Periodos.
- **Filtros:** Agregados filtros de búsqueda en todos los listados del módulo contable.

## 2026-05-12 (Consolidación y Limpieza de Backlog)
- **Auditoría:** Verificación de implementación de Valuación FIFO/MA, Saldo vivo dinámico y Comprobantes Recurrentes.
- **Documentación:** Sincronización de `FIXME.md`, `PENDIENTE.md` y `ESTADO_ACTUAL.md`.
- **Estabilidad:** Suite completa de pruebas pasando (578 tests).

## 2026-05-12 (fix reportes financieros: toggle de filtros avanzados)
- **Corrección:** Toggle Mostrar/Ocultar filtros avanzados usa JS local robusto. Persistencia del estado via input `advanced`.
- **Reordenamiento:** Checkboxes `Mostrar anulaciones` e `Incluir Registro de Cierre` movidos bajo `Cuenta contable`.

## 2026-05-12 (fix comprobante contable: parámetro isclosing)
- **Corrección:** `/accounting/journal/new?isclosing=true` ahora marca correctamente la etapa como `Cierre` por defecto.

## 2026-05-12 (ajuste UX de plantillas recurrentes)
- **Mejora:** Plantillas conservan `naming_series_id` y selección de libros.
- **Grilla:** Agregado modal de dimensiones contables por línea; eliminadas referencias específicas y campos de anticipo en plantillas.

## 2026-05-12 (rediseño del asistente de cierre mensual)
- **Registro:** `/period-close/monthly` convertido en listado/detalle de `PeriodCloseRun`.
- **Flujo:** Soporte step-by-step con registro de resultados en `PeriodCloseCheck`.

## 2026-05-12 (smart-select en nuevo cierre mensual)
- **UX:** Creación de cierre usa Smart Select para compañía y periodos contables abiertos filtrados.

## 2026-05-14 (Ampliación del seed de datos contables y multimoneda)
- **Seed Robusto:** Empresa 'cacao' con 3 libros (NIO, USD, EUR), tasas dinámicas, asientos iniciales reales, dimensiones analíticas y plantillas recurrentes.
- **Verificación:** Suite `tests/test_seed_accounting.py` valida integridad multimoneda y consistencia de reportes.

## 2026-05-14 (Implementación de Endpoints de Disponibilidad)
- **Endpoints:** `/health` (liveness) retorna 'ok'; `/ready` (readiness) verifica conexión DB (`SELECT 1`).

## 2026-05-14 (Integración selectiva desde ia/main)
- **Base documental:** Se consolidó la documentación desde `1965ac44a352de5af34d604b81400a2bc8aed74a`.
- **Código conservado de `bef4029e25000512539a27164f8915cf3b4b2acc`:** solo `/health`, `/ready` y `tests/test_health_checks.py`.

## 2026-05-14 (Estandarización UI/UX de Módulos Operativos y Flujo S2P)
- **Flujo S2P:** Finalizada la implementación del flujo Source to Pay con rutas de aprobación para Solicitudes, Cotizaciones y Órdenes de Compra.
- **Estandarización UI:** Creada librería `transaction-form.js` para manejo genérico de grillas transaccionales, similar a `smart-select.js`.
- **Refactorización Global:** Migrados todos los formularios de Compras, Ventas, Inventario y Bancos al patrón de diseño de Comprobantes Contables (Voucher Pattern).
- **Relaciones Documentales:** Implementado el patrón "Actualizar Elementos" para importar líneas desde documentos origen con trazabilidad completa.
- **Integridad:** Corregidos problemas de importación y dependencias de modelos; suite completa de 607 pruebas pasando satisfactoriamente.

## 2026-05-15 (Ajustes de PR #65 sobre formularios sensibles y pagos)
- **Bancos:** Se restauró `pago_nuevo.html` como formulario especializado por referencias; pagos ya no usan la misma grilla transaccional de Compras/Ventas/Inventario.
- **Facturas con documento origen:** `factura_compra_nuevo.html` y `factura_venta_nuevo.html` recuperaron campos ocultos y carga de líneas desde orden/recepción/entrega/factura según el origen.
- **Flujo documental:** Se limpiaron anotaciones `str | None | None` y se evitó recalcular `DocumentLineFlowState` para relaciones sin línea, manteniendo soporte factura → pago.
- **Validaciones de pago:** Se bloquearon referencias duplicadas o montos negativos y al cancelar un pago se revierten las relaciones documentales y se recalcula el saldo pendiente.
- **Verificación:** Validación amplia local completada con `build`, `flake8`, `ruff`, `mypy`, `pytest` y `smart-select`; resultado `606 passed, 3 skipped`.

## 2026-05-15 (Corrección UX del framework transaccional en Compras, Ventas e Inventario)
- **Framework unificado:** `transaction-form.js` ahora normaliza configuración legacy, impone las 6 columnas núcleo (código, descripción, UOM, cantidad, precio/costo unitario y total) y soporta detalle por línea en modal con dimensiones/trazabilidad.
- **Plantillas operativas:** Los formularios transaccionales de Compras, Ventas e Inventario migraron al macro compartido `transaction_form_macros.html` para replicar la UX del comprobante contable en documentos nuevos.
- **Detalle de documentos:** `detail_view_macros.html` y `macros.lineas_tabla_lectura` ahora renderizan una tabla interactiva con panel y modal de detalle por línea, alineada con `journal.html`.
- **Cobertura:** Se agregaron pruebas para el JS del framework transaccional y una validación web que comprueba el render del grid unificado y del detalle por línea.

## 2026-05-15 (Resolución de issues identificados en FIXME.md)
- **Correcciones Funcionales:** Se agregaron columnas predeterminadas para formularios de transacción nuevos. Se habilitó el flujo desde Solicitud de Compra hacia Orden de Compra.
- **Formularios Dinámicos:** La grilla transaccional ahora respeta las cantidades editadas manualmente en el modal al importar líneas origen.
- **Refactorización:** Simplificación de retornos en el servicio de conciliación de compras.
- **Calidad:** De-duplicación masiva de literales de cadena en todo el proyecto mediante la definición de constantes centralizadas. Suite completa de 609 pruebas aprobada.

## 2026-05-15 (Merge de `fix/resolve-fixme-issues-17130081935948712802` en main)
- **Conflictos resueltos:** Se preservaron tanto la UX unificada de `transaction-form.js` como las correcciones funcionales de FIXME, incluyendo la importación con cantidad editable desde documentos origen.
- **Documentación de estado:** `SESSIONS.md`, `ESTADO_ACTUAL.md` y `PENDIENTE.md` quedaron sincronizados con el estado integrado de la rama.
- **Verificación:** Se ejecutó la batería de calidad del proyecto antes y después de la integración para confirmar que no se perdió funcionalidad (`607 passed, 3 skipped` en pytest y `17 passing` en Mocha).

## 2026-05-15 (Estandarización UX y multi-merge en Compras, Ventas e Inventario)
- **Estandarización de Macros:** Se rediseñaron las macros de encabezado y grid en `transaction_form_macros.html` para imponer un layout uniforme (Breadcrumb -> Encabezado con Compañía/Secuencia/Moneda/Fecha -> Grid).
- **Smart-Select Integral:** Se implementó el uso consistente de `smart-select` en todos los campos de selección de los módulos de Compras, Ventas e Inventario, incluyendo cabeceras y detalles de línea (Ítems, Cuentas, Centros de Costo, etc.).
- **Funcionalidad de Multi-Merge:** Se implementó un flujo de "Actualizar Elementos" en dos pasos que permite seleccionar múltiples documentos fuente y fusionar sus líneas pendientes en una sola transacción.
- **Renombramiento de Rutas de Inventario:** Se migraron las rutas de `/stock-entry/adjustment-negative` a `/stock-entry/inventory-issue` para reflejar una semántica más genérica.
- **Calidad y Pruebas:** Se extendió la API de flujo documental para soportar filtrado por tercero y se añadieron pruebas E2E con Playwright para validar la nueva lógica de interfaz.

## 2026-05-16 (Paridad visual entre comprobante manual y documentos operativos)
- **Cabecera de detalle:** `detail_view_macros.detail_header` adopta el patron visual de `journal.html`: numero como titulo, tipo de documento debajo, estado junto al titulo, acciones a la derecha y datos en la misma tarjeta.
- **Comprobante manual:** `journal.html` ahora muestra `Comprobante manual` bajo el numero para igualar la estructura visual de los documentos operativos.
- **Solicitud de Compra:** En borrador muestra `Editar`, `Duplicar`, `Aprobar`, `Listado` y `Nuevo`; en aprobado mantiene `Crear` para Solicitud de Cotizacion y Orden de Compra.
- **Actualizar Elementos:** Orden de Compra y Solicitud de Cotizacion precargan origen `purchase_request` cuando se crean desde una Solicitud de Compra.
- **Backlog:** Se dejo pendiente completar la paridad de formatos y acciones especificas en el resto de Compras, Inventario y Ventas.

## 2026-05-16 (Verificación de patch E2E/ULID)
- **Solicitud:** Verificar que los cambios reportados para pruebas E2E de Compras/Ventas/Inventario, ajuste de valuación de inventario y migración de IDs a ULID estuvieran aplicados correctamente.
- **Ajuste aplicado:** Se corrigieron los campos `GLEntry.reversal_of` y `GLEntryDimension.gl_entry_id` a `String(26)` para alinear referencias con `gl_entry.id` ULID.
- **Pruebas E2E:** Se robusteció `tests/test_e2e_modules.py` para detectar errores reales vía `alert-danger` en lugar de buscar el literal `danger` en todo el HTML.
- **Verificación:** Suite completa `pytest` ejecutada con éxito (`618 passed, 5 skipped`).

## 2026-05-16 (Motores de Cálculo de Impuestos, Landed Cost y Liquidaciones)
- **Implementación de Motores:** Se crearon tres motores de cálculo independientes y determinísticos: Fiscal Engine, Landed Cost Engine y Settlement Engine en `cacao_accounting/accounting_engine/`.
- **Fiscal Engine:** Soporta impuestos en cascada, incluidos en precio, prioridades jerárquicas (Ítem > Tercero > Transacción) y detección de dependencias circulares.
- **Landed Cost Engine:** Implementa prorrateo secuencial por valor, cantidad, peso, volumen e igualitario, asegurando la capitalización correcta de costos accesorios al inventario.
- **Settlement Engine:** Gestiona retenciones proporcionales en pagos parciales y diferencias de cambio.
- **Auditabilidad y Snapshots:** Sistema de snapshots JSON inmutables para cada cálculo confirmado y generación automática de pistas de auditoría (Audit Trail) detallando fórmulas y bases de cálculo.
- **Documentación y Calidad:** Se crearon 12 manuales técnicos en `docs/tax-cost-engines/` y se validó el "Golden Test" de importación (Costo 1081.50, Total 1243.73).

## 2026-05-17 (Refinamiento Enterprise de Motores de Cálculo)
- **Precisión Financiera:** Se implementó el `RoundingManager` con soporte para múltiples políticas (HALF_UP, HALF_EVEN) y distribución de residuos para garantizar el balance matemático.
- **Mapeo Contable Pro-forma:** Creación del `AccountingMapper` que traduce resultados de cálculo en asientos contables equilibrados, incluyendo ajustes automáticos por redondeo.
- **Integridad de Snapshots:** Los snapshots JSON ahora incluyen un fingerprint SHA256 y versionado de motor para auditoría inmutable.
- **Resolución de Reglas Avanzada:** El `RuleResolver` ahora evalúa condiciones dinámicas como vigencia por fechas, moneda y jurisdicción geográfica.
- **Calidad de Código:** Tipado estático completo con Mypy y cumplimiento de Flake8/Ruff en todo el paquete `accounting_engine`.

## 2026-05-19 (Materialización de costos de importación en inventario)
- **Solicitud:** Atender el pendiente de prorrateo de cargos capitalizables para que el costo aterrizado se materialice dentro del flujo real de documentos, evitando sobrecargar una sola tabla.
- **Diseño aplicado:** Se agregó `LandedCostAllocation` como tabla dedicada de detalle y trazabilidad del prorrateo; `StockValuationLayer` conserva solo el efecto de valuación.
- **Recepción de compra:** Cuando los cargos de importación ya están disponibles al ingreso al almacén, `post_purchase_receipt` ejecuta el motor antes del stock ledger y crea la capa inicial con `final_inventory_cost`.
- **Factura de compra:** Cuando el costo capitalizable aparece después de una recepción ya contabilizada, `post_purchase_invoice` persiste el prorrateo y crea una capa de ajuste por valor (`qty = 0`) contra el inventario existente.
- **Pruebas:** Se agregó cobertura unitaria para una importación recibida con flete capitalizable prorrateado por valor, validando `LandedCostAllocation`, `StockValuationLayer` y `StockBin`.

## 2026-05-20 (Política definitiva para `document_no` en borradores)
- **Solicitud:** Formalizar que las secuencias y series deben llevar consecutivo riguroso; si una numeración fue emitida con datos incorrectos, el registro se anula y se crea uno nuevo.
- **Decisión:** `document_no` es irreversible una vez asignado, incluso en borradores. No se libera, no se reutiliza y no se renumera por cambios posteriores de fecha, compañía o serie.
- **Implementación:** `assign_document_identifier` ahora es idempotente para documentos ya numerados; retorna sin consumir secuencia ni alterar numeración interna/externa.
- **Prueba:** Se agregó cobertura para verificar que una factura en borrador conserva su `document_no` y no incrementa la secuencia al intentar reasignar tras cambiar la fecha.

## 2026-05-20 (Servicio Centralizado de Importación Tabular)
- **Solicitud:** Implementar un servicio centralizado para importar registros (Cuentas, Clientes, Proveedores, Comprobantes, Órdenes de Compra) desde CSV, XLS, XLSX y ODS, inhabilitándolo en modo escritorio.
- **Implementación Core:** Creado paquete `cacao_accounting.imports` con una arquitectura de Lectores (CSV, XLS vía xlrd, XLSX vía openpyxl, ODS vía odfpy) y Adaptadores por módulo.
- **Servicio y UI:** `ImportService` gestiona el ciclo de vida del lote (Pendiente -> Validado -> Procesando -> Completado). Se agregó UI web completa para carga, previsualización y ejecución de importaciones.
- **Seguridad:** Implementado el flag `MODO_ESCRITORIO` en `before_request` del blueprint y visibilidad de UI para cumplir con la restricción de inhabilitación en despliegues locales.
- **Resiliencia:** El procesamiento de documentos incluye rollbacks por registro para evitar estados corruptos del `database.session` y se integró un proceso de recuperación de lotes huérfanos al inicio de la aplicación.
- **Docker:** Actualizado `Dockerfile` con dependencias del sistema necesarias para el procesamiento de archivos.
- **Validación:** Creadas pruebas unitarias para lectores, rutas y servicios en `tests/imports/`. Se resolvieron fallos de linting D401 y se garantizó la compatibilidad con el esquema de base de datos actual.
- **Refinamiento Enterprise:**
  - Implementada normalización inmediata de datos a diccionarios para corregir bug crítico en agrupamiento.
  - Agregada validación de períodos contables abiertos en todo el pipeline de importación.
  - Implementada protección contra inyección de fórmulas en lectores de hojas de cálculo.
  - Mejorada la robustez de ejecución con bloqueos de base de datos (`with_for_update`) e hilos daemon.
  - Soporte para auto-detección de delimitadores en CSV y extracción de tipos avanzada en ODS.
  - Implementada generación de plantillas en formatos CSV, XLSX y ODS con descarga vía UI.

# 2026-07-03 (Reparación de layout en plantilla de comprobante recurrente)
- **Solicitud:** Corregir el layout roto de `/accounting/journal/recurring/new`, donde la cabecera del formulario y la tabla de asientos quedaban comprimidas en una sola línea.
- **Hallazgo:** El template `recurring_journal_nuevo.html` tenía los campos de cabecera incrustados dentro de `.ca-journal-toolbar` junto al botón `Cancelar`, usando clases `col-md-*` sin una grilla real, lo que rompía el flujo visual.
- **Implementación:** Se separó el toolbar del bloque de metadatos y se añadió una grilla explícita `ca-journal-header-grid` para `code`, `name`, `company`, `naming_series`, libros y fechas. La sección `Asientos contables` volvió a quedar debajo de la cabecera, con ancho normal.
- **Validación:** Se amplió la prueba de render HTML del formulario recurrente y se ejecutó junto al flujo E2E de plantilla recurrente (`2 passed`).

# 2026-07-03 (Reversión contable, anulación estricta y numeración mensual)
- **Solicitud:** Corregir el naming/numeración de reversión contable, endurecer la regla operativa para `Anular` y `Revertir`, y evitar que el listado de comprobantes muestre ULIDs como nombre visible cuando el borrador aún no tiene documento contable definitivo.
- **Hallazgo en desarrollo:** El comprobante `01KWK1HFDXZ3QPDM6BXDTM75GB` quedó con fecha `2026-08-01` pero referencia/numeración visible de julio, y la serie `BMO-JOU` estaba vinculada a una secuencia con política `yearly` aunque su prefijo usa `*YYYY*-*MM*`, lo que provocaba números como `...-00004` en agosto en lugar de reiniciar a `...-00001`.
- **Implementación:** La reversión ahora exige otro período contable, asigna número desde la fecha de reversión y conserva la serie del origen; los borradores de comprobante se renumeran si cambia `posting_date` o `naming_series_id`; la anulación solo se permite en la misma fecha del comprobante; y el listado usa un nombre visible amigable para borradores de reversión sin `document_no`.
- **Series dinámicas:** La política efectiva de reset de secuencia ahora sube a `monthly` cuando la serie usa tokens mensuales en el prefijo, incluso si la secuencia heredada estaba configurada como `yearly`. Las series nuevas con prefijo mensual también nacen con reset mensual.
- **Validación:** Pruebas focales en `tests/test_09_journal_entry_form.py`, `tests/test_e2e_journalentry.py`, `tests/test_11_contabilidad_coverage.py` y `tests/test_audit_trail_journal.py` quedaron en verde (`9 passed`).

# 2026-07-03 (Asistente de importación de líneas en comprobantes)
- **Solicitud:** Hacer más intuitivo el auxiliar de `Importar líneas` en comprobantes contables, agregando descarga de plantilla, carga local de XLSX y tolerancia real a encabezados en inglés o español sin depender del título exacto.
- **Implementación:** El modal de `journal_nuevo.html` ahora separa pegar/subir en pestañas, permite descargar una plantilla XLSX en navegador con `ExcelJS` y leer archivos locales sin enviar el archivo al servidor. El mapeo de columnas quedó normalizado sin acentos ni guiones bajos y con fallback por posición cuando no hay coincidencias de encabezado.
- **Esquemas compartidos:** `LineImportSchemaRegistry` expone aliases explícitos ES/EN para columnas de todos los doctypes soportados por line import, de modo que el asistente compartido y el comprobante manual acepten los mismos encabezados bilingües.
- **Validación:** Se agregaron pruebas de render del modal en comprobantes y pruebas API para aliases bilingües; la suite focal `tests/test_09_journal_entry_form.py` + `tests/test_line_import_api.py` quedó en verde (`48 passed`).

## 2026-05-23 (Conciliacion masiva AR/AP y Stock Reconciliation con valuacion)
- **Solicitud:** Implementar la conciliacion masiva de facturas contra pagos existentes y extender Stock Reconciliation para ajustar cantidad y valor.
- **AR/AP:** Se agrego `/cash_management/payment-reconciliation` y `/api/document-flow/payment-reconciliation-candidates`, con servicio que aplica pagos/cobros aprobados contra documentos abiertos, validando compania, tercero, direccion AR/AP, saldos y duplicados.
- **Persistencia AR/AP:** Cada aplicacion crea `PaymentReference`, `DocumentRelation` y `ReconciliationItem`, actualiza saldos pendientes y conserva compatibilidad con cancelaciones append-only.
- **Inventario:** `stock_reconciliation` ahora guarda snapshots de cantidad/tasa/valor actual y objetivo por linea, genera SLE/SVL y actualiza `StockBin` por diferencia de cantidad y/o valor.
- **Contabilidad:** La diferencia de valuacion se contabiliza balanceada contra la cuenta de inventario asignada a la bodega y una cuenta global de diferencia del documento, aplicando centro de costos, unidad de negocio y proyecto globales a todo el comprobante.
- **Validacion:** Pruebas focales nuevas cubren conciliacion AR/AP, render de pantallas, ajuste de valor de inventario, cuenta de bodega, dimensiones globales y cancelacion con reversos.

## 2026-06-27 (Badges semánticos de tarjetas de módulos)
- **Solicitud:** Confirmar y corregir la semántica de los badges de tarjetas de módulos, incluyendo Administración como módulo, para evitar colores hardcodeados como el badge beige/ámbar en Tasas de Cambio para usuarios administradores.
- **Implementación:** Se agregó `module_badge()` como helper Python disponible en Jinja y `module_status_badge` como macro reutilizable. Las tarjetas de Contabilidad, Compras, Ventas, Inventario, Bancos y Administración ahora calculan estado desde permisos y parámetros declarativos.
- **Decisión de diseño:** Verde indica acceso operativo correcto, gris sin acceso, azul pendientes reales de aprobación, beige solo visualización y rojo atención. Los estados antiguos de warning ya no se usan como sustituto de datos reales.
- **Validación:** Se agregaron pruebas unitarias de precedencia semántica y una prueba web que verifica que Tasas de Cambio se renderiza como `ok` para administrador.
- **Ajuste posterior:** Se extendió el buscador reusable de listados a comprobantes contables, comprobantes recurrentes y revalorizaciones cambiarias para cubrir transacciones de Contabilidad igual que Compras, Ventas y Bancos.

## 2026-06-28 (Refactor de persistencia de referencias de pago)
- **Solicitud:** Reducir la complejidad cognitiva de `_save_payment_references` en `cacao_accounting/bancos/__init__.py` y conservar la cobertura con pruebas unitarias.
- **Implementación:** Se extrajo la lectura de líneas desde el formulario, la resolución del documento referenciado, la validación de negocio por documento y la construcción de `PaymentReference` en helpers dedicados. La función principal quedó como orquestador lineal.
- **Validación:** Se ejecutó la suite focal de referencias de pago y cancelación, con `5 passed` en `tests/test_06transaction_closure.py`; también se corrió `ruff check` sobre el módulo modificado.

## 2026-06-29 (Refactor de hotspots Bancos y Compras)
- **Solicitud:** Refactorizar los métodos listados en `issues.txt` para bajar complejidad cognitiva, usar `match/case` donde aplique, mover lógica a helpers, preservar contratos, y validar con pruebas unitarias y herramientas de calidad.
- **Alcance acordado:** Se priorizaron solo los hotspots reales; `_save_payment_references` se trató como falso positivo histórico porque ya figuraba refactorizado en la bitácora.
- **Implementación:** Se simplificaron los handlers y servicios de Bancos con helpers de dispatch, validación y persistencia; `find_bank_reconciliation_candidates`, `reconcile_bank_items`, `import_bank_statement`, `bancos_pago_nuevo`, `_crear_nota_bancaria`, `_payment_source_rows` y `_validate_payment_header` quedaron menos anidados. En Compras, `compras_cotizacion_proveedor_nueva` y `compras_cotizacion_proveedor_editar` comparten ahora helpers de contexto y catálogos.
- **Validación:** Se ejecutaron `ruff`, `mypy` y pruebas focales de Bancos, Conciliación, Importación y Compras; el bloque relevante quedó en verde con `116 passed`.

## 2026-06-29 (Fix unit tests in CI workflows)
- **Solicitud:** Revisar y corregir fallos en las pruebas unitarias definidas en los workflows de GitHub.
- **Implementación:**
  - En `cacao_accounting/contabilidad/posting.py`: Se corrigió `_landed_cost_result_is_invalid` para que no trate una lista de errores vacía como un resultado inválido. Esto corrigió `test_purchase_receipt_lands_import_costs_into_initial_valuation_layers`.
  - En `cacao_accounting/reportes/services.py`: Se reescribió `_process_payment_entry` para manejar correctamente las transferencias internas en el reporte de movimientos bancarios y se corrigió el cálculo de totales en `get_bank_movement_detail`. Esto corrigió `test_get_bank_movement_detail_supports_bank_filter`.
  - En `tests/test_transaction_update_elements.py`: Se corrigió una regresión en las aserciones de etiquetas de UI que usaban constantes internas en lugar de los valores esperados.
- **Verificación:** Se ejecutó la suite completa de pruebas unitarias (`1015 passed`).

## 2026-07-03 (Códigos legibles para clientes, proveedores e items)
- **Solicitud:** Reemplazar los códigos ULID visibles en clientes, proveedores e items por códigos secuenciales legibles (CUSTM-00001, SUPLR-00001, ITEM-000001) usando el sistema de naming-series existente.
- **Diagnóstico:** `generate_party_code()` en `party_management.py` y `create_item_with_uoms()` en `inventario/service.py` llamaban a `generate_identifier()` sin `naming_series_id`/`sequence_id`, cayendo al fallback `full_identifier = entity_id` (ULID).
- **Implementación:**
  - `document_identifiers.py`: Se agregaron códigos `customer→CUSTM`, `supplier→SUPLR`, `item→ITEM` en `_default_entity_code()`. Nueva función `ensure_global_naming_series()` que crea series globales (`company=None`) con prefijo fijo, padding 5 (cliente/proveedor) o 6 (item), y `reset_policy="never"`. Nueva función `generate_entity_code()` como helper público que encapsula la resolución de naming-series + secuencia + generación.
  - `party_management.py`: `generate_party_code()` ahora usa `generate_entity_code()`.
  - `inventario/service.py`: `create_item_with_uoms()` ahora usa `generate_entity_code()` para items.
  - `setup/service.py`: Llama a `ensure_global_naming_series()` durante la creación de compañía.
  - `datos/dev/__init__.py`: Llama a `ensure_global_naming_series()` antes de crear datos demo.
- **Calidad:** Black, ruff, mypy en verde. 254 tests de cobertura contable + 874 tests generales pasan (fallo preexistente en `test_fiscal_year_closing_cycle`).
- **Commit:** `9b6f80d` — `feat: human-readable codes for customers, suppliers, and items`

## 2026-07-08 (CAS-02 y CAS-03: exchange_rate en pagos y bloqueo FOR UPDATE)
- **Solicitud:** Analizar 5 issues de prioridad alta (R2R-01, R2R-02, CAS-01, CAS-02, CAS-03) e implementar los reales.
- **Falsos positivos (3):** R2R-01 (period validation ya existe via _document_contexts), R2R-02 (balance check ya existe via _assert_entries_balance), CAS-01 (saldo bancario ya se deriva de GLEntry). Marcados como REQUIERE REVISION.
- **CAS-02 (implementado):** `_create_payment_entry` ya no hardcodea `exchange_rate=None`. Ahora recibe el rate resuelto desde `_lookup_exchange_rate()` cuando la moneda del pago difiere de la moneda base. `_update_payment_amounts` aplica el rate a `base_paid_amount`/`base_received_amount`.
- **CAS-03 (implementado):** `_load_payment_reference_document` y `_get_reference_document` ahora usan `with_for_update()` para bloquear la fila del documento antes de leer el saldo pendiente, previniendo condición TOCTOU.
- **Pruebas:** 3 tests nuevos, 1 existente ajustado. 337 tests en verde.
- **Calidad:** black, ruff, flake8 OK.
- **Commits:** `bb40f22` (CAS-02), `74079bf` (CAS-03), `61e15a4` (tests).
