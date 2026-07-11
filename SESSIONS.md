# SESSIONS - Historical Decisions & Milestones

## 2026-07-10 : Implementación de Límite de Intentos de Inicio de Sesión y Rate Limiting en API (CWE-307)
- **Petición del usuario:** No hay límite de intentos de inicio de sesión ni rate limiting en endpoints de la API, lo que posibilita ataques de fuerza bruta (CWE-307). Se sugiere usar `Flask-Limiter` con Redis para modo nube, pero de manera completamente opcional para respetar el modo escritorio como ciudadano de primer nivel. Adicionalmente se solicita proveer un archivo `docker-compose.yml` que defina tres servicios (`app`, `db`, `cache`).
- **Implementación:**
  - Se creó la biblioteca de control `cacao_accounting/limiter.py` que importa condicionalmente `flask_limiter`. Si no está instalada, hereda en una clase de respaldo `DummyLimiter` para que los decoradores `@limiter.limit` no arrojen errores de carga o ejecución.
  - Se implementó `init_limiter(app)` que desactiva el limitador si `is_desktop_mode()` retorna `True`. En modo nube, lo activa y configura con `RATELIMIT_STORAGE_URI` mapeado a `CACHE_REDIS_URL` o fallback a memoria.
  - Se registró el limitador en el factory de la aplicación `cacao_accounting/__init__.py`.
  - Se decoró la ruta `/login` en `cacao_accounting/auth/__init__.py` con `@limiter.limit("10 per minute")`.
  - Se decoraron las rutas de API en `cacao_accounting/api/__init__.py` con límites de `"60 per minute"` en los blueprints `api`, `line_import_bp` y `dashboard_api`.
  - Se añadió `limiter` como dependencia opcional en `pyproject.toml` (`Flask-Limiter[redis]>=3.8.0`).
  - Se editó el `Dockerfile` para requerir e instalar `Flask-Limiter[redis]` de forma nativa en la imagen final.
  - Se añadió `docker-compose.yml` con servicios `app`, `db` (PostgreSQL) y `cache` (Redis).
  - Se agregaron pruebas automatizadas exhaustivas en `tests/test_auth_limiter.py`.
- **Validación:** Black, Ruff, Flake8, Mypy y Pytest en verde con cero advertencias y todos los tests pasando con éxito.

## 2026-07-10 : Auditoría Senior DBA — Commits 4-10 (UniqueConstraints, CheckConstraints, Indexes, Optimistic Locking, Atomic Sequences)

### Commit 4: UniqueConstraints (`10a2bc1`)
- **Nuevas:** User.user (unique login), FiscalYear(entity,name), NamingSeries(entity_type,company,prefix_template), Workflow(entity_type,name), WorkflowState(workflow_id,name), WorkflowTransition(from_state_id,to_state_id,action_name).
- **Bug fix:** Roles.note eliminado `unique=True` (erróneo).
- **Redundantes eliminadas:** Modules, CompanyDefaultAccount, PurchaseMatchingConfig, SalesMatchingConfig (column-level `unique=True` ya cubría).

### Commit 5: CheckConstraints (`53a5bbc` → `7dd1391`)
- 37 CheckConstraints nuevas en 14 modelos de línea: `qty > 0`, `rate >= 0`, `amount >= 0`.
- Total en esquema: 38 (37 nuevas + 1 existente en GLEntry de debit_credit_integrity).
- **Fix (`7dd1391`):** Eliminados `ck_svl_qty_positive` (reversals necesitan qty negativa) y `ck_sei_qty_positive` (reconciliaciones con qty=0). Corregido constraint de naming_series de `(entity_type, company, prefix_template)` a `(entity_type, company, name)`.

### Commit 6+7: Index Optimization (`da55073`)
- 23 índices redundantes eliminados (single-column cubiertos por composites existentes).
- GLEntry: −6, DocumentRelation: −6, DocumentLineFlowState: −4, ReconciliationItem: −4, AuditTrail: −3.
- Total índices: 589 → 566.

### Commit 8: GLBase Refactor — CANCELADO
- GLBase usa naming incompatible con GLEntry (entity/company, account/account_id, etc.).
- Forzar herencia requeriría renombrar ~20 columnas (breaking migration). No seguro.

### Commit 9: Version Column (`8c043ad`)
- `version = Column(Integer, default=1)` agregado a `DocBase`.
- Cubre 15 modelos transaccionales (Purchase/Sales/Stock/Payment).
- Habilita optimistic locking en capa de aplicación.

### Commit 10: Atomic Sequences (`dae0c03`)
- `get_next_sequence_value()` usa `with_for_update()` para bloqueo pesimista.
- Previene asignaciones duplicadas bajo concurrencia en PostgreSQL/MySQL.
- SQLite: no-op (single-writer), pero semántica correcta.

## 2026-07-10 : FK Cascade Policies — ON DELETE/ON UPDATE para 444 foreign keys
- **Petición del usuario:** Auditoría Senior DBA de los modelos SQLAlchemy. Agregar reglas de integridad referencial explícitas a todas las FK.
- **Diagnostico:** ~444 restricciones FK en 136 tablas no tenían ON DELETE ni ON UPDATE definidos. SQLite los ignora por defecto, pero PostgreSQL y MySQL los aplican. Sin reglas, una eliminación de registro maestro podría crear filas huérfanas silenciosamente.
- **Implementacion:**
  - Se definieron constantes `FK_RESTRICT`, `FK_CASCADE`, `FK_SET_NULL` en `database/__init__.py` (~línea 67).
  - Se clasificaron todas las FKs en tres políticas:
    - **RESTRICT** (no permitir borrado padre): datos maestros (`entity`, `currency`, `accounts`, `parties`, `items`, `warehouses`, `users`, `books`, `tax_templates`, `print_templates`, `banks`).
    - **SET NULL** (nullificar FK al borrar padre): referencias opcionales (`naming_series`, `external_counter`, `fiscal_year`, `comprobante_contable`, `purchase_receipt`, `delivery_note`).
    - **CASCADE** (borrar hijos con padre): líneas de detalle (`purchase_order_item`, `sales_order_item`, `stock_entry_item`, `import_batch_error`, `budget_line`, `workflow_instance`, `comment`).
  - Circulares/auto-referentes (`fiscal_year`, `comprobante_contable`): SET NULL + `use_alter=True`.
  - Todas las FK: ON UPDATE CASCADE (propagación de cambios en PK).
- **Archivos modificados:**
  - `cacao_accounting/database/__init__.py`: ~360 FKs (modelos principales)
  - `cacao_accounting/imports/models.py`: 4 FKs (ImportBatch, ImportBatchError)
  - `cacao_accounting/printing/models.py`: 9 FKs (PrintTemplate, PrintTemplateVersion, PrintJobLog, PublicDocumentValidation)
- **Validación:** 444 FK constraints verificados vía DDL inspection (sqlite:///:memory:), 136 tablas creadas exitosamente.
- **Commit:** `dab2de9`

## 2026-07-10 : Optimización del Dockerfile
- **Petición del usuario:** Revisar y mejorar el Dockerfile del proyecto.
- **Problemas identificados:**
  - Imagen base desactualizada (`ubi9/ubi-minimal:9.4`).
  - Node.js/npm se instalaban y desinstalaban en la imagen final, dejando residuos y aumentando tamaño.
  - El contenedor ejecutaba como root (riesgo de seguridad).
  - `WORKDIR /app` estaba duplicado (líneas 11 y 31).
  - Múltiples llamadas a `microdnf install` separadas generaban capas innecesarias.
  - Sin `HEALTHCHECK` para orquestadores.
  - `npm install` instalaba `devDependencies` (mocha, chai, playwright) innecesarias en producción.
  - `ADD` con URL externa para tini es impredecible (sin cache de Docker).
- **Solución implementada:**
  - **Multi-stage build:** Etapa `frontend` con Node.js para instalar dependencias npm, la imagen final solo copia `node_modules`.
  - **Imagen base actualizada:** `ubi9/ubi-minimal:9.8-1782797275`.
  - **Usuario no-root:** `useradd -r -s /bin/false appuser` + `USER appuser` antes del ENTRYPOINT.
  - **WORKDIR eliminado duplicado:** Se mantiene solo después de instalar dependencias del sistema.
  - **Instalaciones consolidadas:** Una sola llamada a `microdnf install` para Python, pango, libxml2 y libxslt.
  - **HEALTHCHECK agregado:** Verifica `/health` en puerto 8080 cada 30 segundos.
  - **npm install --omit=dev:** No instala dependencias de desarrollo en producción.
  - **Tini:** Se mantiene descarga vía ADD por no estar en repos de RHEL.
  - **Python site-packages via multi-stage:** Las dependencias pip se compilan en una etapa `python-builder` dedicada y se copian via `--prefix=/install`, eliminando pip, headers de compilación y herramientas de build de la imagen final.

## 2026-07-10 : R2R-19 — Bloqueo de eliminación de maestros con historial transaccional activo
- **Petición del usuario:** El sistema permite eliminar registros maestros esenciales (Artículos, Almacenes, Proveedores, Clientes) del catálogo general aun cuando ya tienen un historial de transacciones registradas y contabilizadas (registros activos en `GLEntry`, `StockLedgerEntry`, etc.).
- **Plan de diseño e implementación:**
  - Se implementaron las funciones auxiliares `_warehouse_has_usage()` and `_party_has_usage()` en `cacao_accounting/database/__init__.py` para realizar escaneos eficientes de todas las tablas transaccionales (como diarios contables, diario de inventario, órdenes de compra/venta, facturas, etc.).
  - Se registraron escuchadores de eventos SQLAlchemy `before_delete` en los modelos `Item`, `Warehouse` y `Party` (clientes/proveedores) para interceptar cualquier intento de eliminación física a nivel de base de datos/ORM.
  - Al detectar historial transaccional o de stock activo, se lanza una excepción de integridad operativa `cacao_accounting.exceptions.IntegrityError` con un mensaje claro recomendando la inactivación o bloqueo del registro maestro.
  - Se agregaron pruebas automatizadas integrales en `tests/test_master_data_issues.py` para asegurar que el comportamiento de bloqueo funciona de forma robusta e infalible, y que los registros maestros limpios (sin historial) se puedan seguir eliminando con éxito.

## 2026-07-09 : ISSUES corregidos de acuerdo al archivo ISSUES.md

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
- **Diagnostico:** Ambos vistas compartian el patron `.ca-tree`, pero estaban montadas sobre una tarjeta demasiado amplia con toolbar dispersa, demasiado espacio en blanco y un arbol visualmente estrecho y poco tactil en pantallas pequenas.
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
- **Importador de lineas:** Los modales de importacion ya no devaluan `schema.columns` cuando el esquema aun es `null`, aceptan compania por `Entity.code` o `Entity.id` al validar y muestran errores visibles cuando falla la carga de esquema o la validacion.
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
- **Implementacion:** `CompanyParty` ahora guarda `default_tax_rule_id` and `default_price_list_id`. `party_settings` resuelve defaults, valida compania/tipo (`sales` vs `purchase`) y hace fallback a listas predeterminadas por compania. `search-select` incorpora `tax_rule` y `price_list`.
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
- **Implementacion:** Se agrego una capa de refresh in `cacao_accounting/static/css/cacaoaccounting.css` sobre el sistema visual existente, ajustando tokens, navbar, sidebar, contenido, tarjetas, cards de modulo, tablas, formularios, botones, alerts, dropdowns y modales.
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
- **Detalle:** `bancos/pago.html` adopta la estructura visual de `journal.html`, con tarjeta de cabecera, datos bancarios, referencias y asientos GL.
- **Verificación parcial:** `tests/test_payment_entry_improved.py` en verde (`37 passed`).

## 2026-05-22 (Cierre gaps Payment Entry: referencias, anticipos y candidatos)
- **Solicitud:** Implementar el plan para cerrar gaps detectados en `requerimiento.md` and `payment.md` sobre `payment_entry`.
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
- **Verificación:** Pruebas en verde tras cambios: `tests/test_05document_flow.py` (`14 passed`) and `tests/test_03webactions.py` (`19 passed`).

## 2026-05-21 (Inicio implementación matriz de relaciones: fase núcleo + UI dinámica)
- **Solicitud:** Iniciar implementación de brechas definidas en `modulos/relaciones.md` para acercar el flujo documental al resultado funcional esperado.
- **Implementación (fase inicial):** `document_flow` ahora serializa `create_actions` con URL navegable (`create_url`) y soporte de `query_params`; esto habilita acciones de creación dinámicas en el panel de trazabilidad.
- **Registro de flujos:** `registry.py` amplió acciones `Crear` en tipos existentes con rutas ya soportadas: Solicitud de Compra incorpora Solicitud de Cotización; Pedido de Venta incorpora Orden de Venta; se agregan acciones de Devolución y Nota de Débito/Crédito en Compra/Venta donde ya existe endpoint de factura con `document_type`.
- **UI:** `macros.document_flow_trace` ahora muestra sección **Acciones disponibles** con botones dinámicos derivados del resumen de flujo, reduciendo dependencia de botones hardcodeados en detalles.
- **Verificación:** Pruebas focales en verde tras cambios: `tests/test_05document_flow.py` (`9 passed`) and `tests/test_03webactions.py` (`19 passed`).

## 2026-05-21 (Importaciones: recuperación silenciosa sin lotes pendientes)
- **Solicitud:** Evitar el log de error `Error al recuperar lotes de importación` cuando no hay lotes pendientes o el esquema de importaciones aún no está inicializado.
- **Implementación:** `recover_crashed_batches()` ahora verifica que existan las tablas requeridas, retorna `0` cuando no hay lotes vencidos y solo hace `commit` si recupera lotes reales; el log de arranque usa formato correcto de Loguru.
- **Cobertura:** Se añadieron pruebas para arranque sin tablas, recuperación sin pendientes y marcado de un lote procesando vencido como fallido.
- **Ajuste UI:** Las plantillas de Importaciones usan el bloque `contenido` correcto de `base.html`; el índice muestra estado vacío acionable y el formulario de nuevo lote usa `smart-select` en orden Compañía → Tipo de registro → Serie/Secuencia filtrada por compañía y registro, con Libro Contable solo para comprobantes contables.
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
- **Verificación:** Pruebas focales en verde: `tests/test_tax_rules.py` + `tests/test_fiscal_preview.py` (`9 passed`) and `npm test -- --grep transaction-form` (`6 passing`).

## 2026-05-19 (Fix FIXME fiscal: preview canónico, cobros y FK nullable)
- **Solicitud:** Analizar `FIXME.md` y resolver los issues identificados sobre el MVP fiscal.
- **Preview fiscal:** `fiscal_preview_service.py` ahora recarga reglas canónicas persistidas antes de considerar líneas reenviadas por el cliente, conservando solo campos editables como cuenta/notas del preview previo.
- **Cobros:** `payment_entry` con `payment_type="receive"` resuelve un perfil fiscal de cobro con `applies_to="sales"` and `recognition_event="collection_confirmed"`.
- **UX transaccional:** `transaction-form.js` omite llamadas automáticas al preview fiscal para doctypes fuera de la matriz, evitando errores iniciales en cotizaciones y otros flujos no soportados.
- **Persistencia:** `fiscal_persistence_service.py` normaliza `account_id` vacío a `NULL` antes de guardar `DocumentTaxLine`.
- **Verificación:** Pruebas focales en verde: `tests/test_tax_rules.py` (`6 passed`) and `npm test -- --grep transaction-form` (`6 passing`).

## 2026-05-19 (Cierre review final: submit_document + robustez bancos)
- **Solicitud:** Resolver dos pendientes finales de review: confirmar/garantizar consumo del snapshot fiscal en `submit_document` y robustecer manejo transaccional/errores en `bancos_pago_nuevo`.
- **Implementación:** Se añadió prueba de integración en posting (`test_submit_sales_invoice_uses_persisted_fiscal_snapshot`) que valida GL generado desde snapshot persistido al ejecutar `submit_document`.
- **Robustez Bancos:** Se reforzó `bancos_pago_nuevo` para tratar también errores `ArithmeticError` dentro del mismo rollback; se añadió prueba (`test_payment_creation_rolls_back_when_fiscal_payload_is_invalid`) que confirma rollback completo cuando el payload fiscal es inválido.
- **Trazabilidad:** `PENDIENTE.md` y `ESTADO_ACTUAL.md` se actualizaron para marcar como completados persistencia fiscal real y consumo en posting.

## 2026-05-19 (Seguimiento review: faltantes fiscales de persistencia y posting)
- **Solicitud:** Atender comentario de revisión que señala brechas en la implementación fiscal MVP.
- **Resultado:** Se dejó explícito en `PENDIENTE.md` y `ESTADO_ACTUAL.md` que aún faltan dos frentes críticos: (1) persistencia fiscal real por documento con snapshot inmutable de reglas; (2) integración de ese payload persistido en el posting de `purchase_invoice`, `sales_invoice` y `payment_entry`.
- **Alcance de esta iteración:** Sin cambios funcionales en backend/UI; se actualizó la trazabilidad del estado para evitar ambigüedad entre preview visual y persistencia/contabilización final.

## 2026-05-19 (MVP fiscal: matriz + API preview + UX común con modal por línea)
- **Solicitud:** Ejecutar el plan MVP ampliado para Compras, Ventas, Inventario y Bancos, incorporando matriz fiscal por tipo documental, API unificada de preview y bloque UX común de `Impuestos y Cargos`.
- **Requisito UX confirmado:** Se mantiene el patrón visual alineado al framework transaccional existente, con capacidad de ampliar cada línea fiscal en modal para capturar información adicional.
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
- **Formato:** Se normalizo con Black `tests/test_e2e_modules.py` and `tests/test_uoms_full.py`.
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
- **Verificación completa:** Black, Ruff, Flake8, Mypy y Pytest ejecutados en `.venv` con resultado exitoso (`607 passed, 3 skipped`).

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
- **Detalle de documentos:** `detail_view_macros.detail_header` adopta el patron visual de `journal.html`: numero como titulo, tipo de documento debajo, estado junto al titulo, acciones a la derecha y datos en la misma tarjeta.
- **Comprobante manual:** `journal.html` ahora muestra `Comprobante manual` bajo el numero para igualar la estructura visual de los documentos operativos.
- **Solicitud de Compra:** En borrador muestra `Editar`, `Duplicar`, `Aprobar`, `Listado` y `Nuevo`; en aprobado mantiene `Crear` para Solicitud de Cotizacion y Orden de Compra.
- **Actualizar Elementos:** Orden de Compra y Solicitud de Cotizacion precargan origen `purchase_request` cuando se crean desde una Solicitud de Compra.
- **Backlog:** Se dejo pendiente completar la paridad de formatos y acciones específicas en el resto de Compras, Inventario y Ventas.
