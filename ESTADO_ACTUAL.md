# Estado Actual del Proyecto - 2026-07-10

- **R2R-19 — Bloqueo de eliminación de maestros con historial transaccional activo (2026-07-10):**
  - Se agregaron helpers de verificación `_warehouse_has_usage()` y `_party_has_usage()` en `cacao_accounting/database/__init__.py`.
  - Se registraron escuchadores de eventos de SQLAlchemy `@event.listens_for(..., "before_delete")` para los modelos `Item`, `Warehouse`, y `Party`.
  - Si un usuario o proceso intenta eliminar físicamente un artículo, bodega, cliente o proveedor que cuente con transacciones activas (ej. `GLEntry`, `StockLedgerEntry`, etc.), el sistema lanza una excepción de integridad operativa `IntegrityError` detallando la situación y recomendando su inactivación.
  - Se añadieron pruebas unitarias exhaustivas que confirman este comportamiento de bloqueo y que permiten la eliminación de maestros limpios sin historial.

- **Codigos legibles para terceros e items (2026-07-03):** Clientes, proveedores e items ahora usan codigos secuenciales legibles en lugar de ULIDs.
  - `generate_party_code()` y `create_item_with_uoms()` resuelven la naming series global antes de generar el identificador.
  - Las series globales `CUSTM-`, `SUPLR-`, `ITEM-` se crean automaticamente durante el setup y el seed de desarrollo.
  - Padding: 5 para clientes/proveedores (CUSTM-00001), 6 para items (ITEM-000001), sin reinicio de secuencia.
  - Commit: `9b6f80d`

- **Inventario / cuenta contable por almacen+compañia (2026-07-03):** La cuenta de inventario ya quedó alineada a una sola fuente de verdad.
  - `WarehouseCompanyAccount` define la cuenta de inventario por `warehouse_code + company`.
  - `stock_entry`, `purchase_receipt` y `delivery_note` resuelven inventario desde la bodega de la línea o del movimiento.
  - `CompanyDefaultAccount` ya no expone ni usa `default_inventory`.
  - La ficha de bodega muestra la cuenta configurada con código y nombre; la ficha de item ya no sugiere cuenta de inventario por item.

- **Inventario / valuacion global por compañia (2026-07-03):** Ya existe una entrada administrativa dedicada para definir el metodo de valuacion por compañia.
  - `/settings` muestra el acceso `Valuación de inventarios` dentro de `Configuración General`.
  - La pantalla `/settings/inventory-valuation` permite seleccionar compañia y guardar `Costo promedio` o `FIFO`.
  - La persistencia se realiza sobre `Entity.valuation_method`, manteniendo `moving_average` como default funcional.
  - Si la compañia ya tiene `StockLedgerEntry` o `StockValuationLayer`, el cambio queda bloqueado en UI y backend.

- **Contabilidad / arboles maestros responsive (2026-07-03):** Los listados de Catalogo de Cuentas y Centros de Costos ahora comparten una presentacion mas util y consistente.
  - Ambos usan un toolbar comun con selector de entidad, actualizacion y acciones de expandir/colapsar.
  - El arbol se renderiza dentro de un panel con mejor legibilidad, menos espacio muerto y scroll controlado para codigos largos.
  - En mobile los controles se apilan y los nodos del arbol aumentan su area tactil sin cambiar la logica Alpine ni los enlaces existentes.

- **Setup inicial / ajuste visual del wizard (2026-07-03):** La pantalla inicial del setup ya usa una composicion mas compacta y operativa.
  - El contenedor principal reduce el ancho maximo y elimina el aspecto de hero sobredimensionado.
  - La cabecera usa la marca real desde `static/media/brand.svg`.
  - El stepper queda como barra horizontal compacta y el selector de idioma ya no queda perdido dentro de una tarjeta pequena.
  - En mobile el stepper y las acciones se ajustan al ancho disponible sin romper el flujo.

- **Smart Select / overlay en formularios maestros (2026-07-03):** Los menues de busqueda ya no quedan recortados dentro de tablas responsivas.
  - `smart-select.js` posiciona el menu abierto con `position: fixed` and coordenadas calculadas desde el campo visible.
  - La posicion se recalcula en scroll/resize, se limpia al cerrar y se ajusta al viewport para mobile.
  - Aplica al patron compartido usado en Articulo, Cliente y Proveedor sin cambiar endpoints, nombres de campos ni payloads de formulario.
  - La cobertura JS valida posicion inferior, apertura superior por falta de espacio y clamp lateral en viewport movil.

- **Reportes contables / anulaciones y reversas (2026-07-03):** Los 5 reportes contables principales ya comparten una regla única de visibilidad sobre `GLEntry`.
  - `account-movement`, `account-summary`, `trial-balance`, `balance-sheet` e `income-statement` excluyen por defecto tanto `is_cancelled=True` como `is_reversal=True`.
  - Al activar el checkbox de anulaciones, el dataset vuelve a incluir movimientos anulados y reversas GL, sin depender del módulo origen del comprobante.
  - La semántica aplica igual a comprobantes manuales y a postings originados desde Compras, Ventas, Bancos e Inventario porque el filtro opera directamente en GL.
  - El detalle de movimiento ya distingue reversas con estado visible propio en la fila (`Reversión`).

- **Comprobante contable / revertir con fecha (2026-07-03):** La reversión manual ya no se dispara con POST ciego.
  - La vista detalle abre un modal para capturar `Fecha de reversión`.
  - El borrador de reversión hereda la `naming_series_id` del comprobante origen y usa la fecha seleccionada como `posting_date`.
  - La recomendación en UI diferencia el caso de mismo período (`Anular`) contra período distinto (`Revertir`).
  - La asignación posterior del `document_no` usa la misma serie y resuelve el prefijo dinámico con la nueva fecha, evitando numeraciones fuera de período.

- **Setup inicial / idioma, region y catalogo contable (2026-07-03):** El wizard inicial ya respeta el idioma seleccionado desde la primera pantalla.
  - Los textos del setup se renderizan desde un catalogo ES/EN centralizado.
  - El paso regional lista paises soberanos de America y solo permite monedas activas existentes en el seed/base.
  - Al seleccionar "Crear catalogo contable en cero", el selector de catalogo origen queda deshabilitado y se limpia.
  - La pantalla adopta una composicion visual renovada con hero, stepper y tarjetas.

- **Terceros / configuracion por compania editable (2026-07-03):** Cliente y Proveedor ya no quedan fijos a una sola compania.
  - La tabla por compania permite agregar y remover filas con `smart-select`.
  - El POST usa un unico formato repetible; no se mantiene fallback al formato viejo.
  - Las filas removidas se eliminan de `CompanyParty` y `PartyAccount` para evitar configuraciones fantasma.

- **Inventario / Item y Bodega con Smart Select (2026-07-03):** Los formularios maestros de inventario quedan alieandos al framework de seleccion.
  - Item usa `smart-select` para UOM en conversiones y para compania/cuenta/centro de costo en configuracion contable.
  - Bodega incorpora configuracion por compania con cuenta de inventario mediante `warehouse_company_account`.
  - El posting de stock reconciliation resuelve la cuenta de inventario por bodega+compania sin fallback legacy en `Warehouse`.

- **Importador de lineas / Alpine (2026-07-03):** Los modales de importacion ya no fallan si el esquema aun no ha cargado.
  - Las iteraciones de columnas usan una lista segura cuando `importModal.schema` es `null`.
  - La correccion aplica al macro transaccional compartido y al formulario de comprobante contable.
  - La validacion acepta compania por codigo o id para alinearse con `smart-select`.
  - Los errores de carga de esquema y validacion se muestran dentro del modal en lugar de fallar silenciosamente.

- **Inventario / cuenta de inventario solo en bodega (2026-07-02):** La cuenta de inventario se configura unicamente a nivel de bodega.
  - `ItemAccount.inventory_account_id` removido del modelo, dataclass, validacion y templates.
  - `Warehouse.inventory_account_id` es la unica fuente de la cuenta de inventario para stock entries.
  - Stock entries resuelven la cuenta via `_warehouse_inventory_account_id()` sin fallback a ItemAccount.
  - Test fixtures actualizados para no usar `inventory_account_id` en ItemAccount.

- **Inventario / valuacion a nivel de entidad (2026-07-02):** El metodo de valuacion de inventario ahora es un atributo de la entidad.
  - `Item.valuation_method` removido; `Entity.valuation_method` agregado con default "moving_average".
  - `posting.py` usa `_valuation_method_for_company()` que consulta `Entity.valuation_method` primero.
  - Servicios de inventario y formularios de item actualizados para no exponer el campo.
  - Seed de desarrollo y tests corregidos.

- **Cliente/Proveedor / perfil basico y cumplimiento legal (2026-07-01):** Los terceros ya incluyen los campos basicos y legales que faltaban.
  - `Party` guarda nacionalidad, tipo de persona, telefono y correo principales, pagina web y direccion principal.
  - El formulario agrega un bloque de cumplimiento legal con representante, documento, cargo, fechas y datos de notificacion.
  - La ficha de detalle muestra las secciones de datos basicos y cumplimiento legal antes de contactos/direcciones.

- **Cliente/Proveedor / simplificacion de clasificación (2026-07-01):** La UI de terceros ya no expone el campo libre `Clasificación`.
  - Cliente y Proveedor usan `Tipo de Cliente` / `Tipo de Proveedor` como fuente funcional de clasificación.
  - Los handlers de creación ya no toman `classification` desde el formulario; el valor legacy sigue sincronizado internamente desde `party_group_id` por compatibilidad.
  - El resumen superior de la ficha de Cliente/Proveedor ya no muestra `Clasificación`.

- **Cliente/Proveedor / visibilidad de contactos y direcciones (2026-07-01):** La ficha del tercero hace más evidentes las secciones operativas compartidas.
  - Se agregó una franja de navegación con accesos rápidos a `Configuración por compañía`, `Contactos` y `Direcciones`.
  - `Contactos` y `Direcciones` quedaron priorizados antes de la configuración por compañía dentro del detalle.
  - Cada acceso rápido muestra contador y ancla interna para ubicar rápidamente la tabla correspondiente.

- **Cliente/Proveedor por compañia (2026-07-01):** Los terceros ya soportan configuracion ampliada por compañia para cuentas, fiscalidad y precios.
  - `CompanyParty` ahora persiste regla fiscal predeterminada y lista de precio predeterminada.
  - Cliente valida listas de precio de venta; Proveedor valida listas de precio de compra.
  - `PriceList` queda consolidado como maestro funcional de listas de precio; `ItemPrice` sigue siendo el detalle por item.
  - El setup inicial crea listas de precio de venta y compra predeterminadas por compañia y las localiza por idioma de instalacion.
  - Las pantallas de Cliente y Proveedor ya muestran cuenta AR/AP, lista de precio, regla fiscal y plantilla fiscal dentro de la configuracion por compañia.
  - `search-select` ya expone `price_list` and `tax_rule`.

- **Item / configuracion contable por compañia (2026-07-01):** El formulario de item ya soporta cuentas predeterminadas por empresa.
  - El alta de item muestra una tabla por compañia con cuenta de gasto y centro de costo.
  - La configuracion se persiste en `ItemAccount`.
  - Si el item es servicio o no inventariable, la cuenta de gasto y el centro de costo por compañia son obligatorios y el guardado falla si falta cualquiera.
  - El detalle del item ya muestra la configuracion contable por compañia.

- **Maestro UOM e idioma de setup (2026-07-01):** El item de inventario ya maneja un maestro de UOM con conversiones contra una unidad predeterminada.
  - Cada item puede definir una unidad base y varias UOM adicionales con su factor de conversión hacia esa base.
  - Si el item ya tiene registros de uso, la unidad predeterminada queda bloqueada y no puede modificarse.
  - El alta de item valida la configuración contable mínima para servicios antes de permitir guardar.
  - El seed inicial de UOM respeta el idioma seleccionado en setup y carga nombres localizados para `ES` o `EN`.
  - El catálogo de desarrollo evita duplicados al reaprovechar los mismos códigos de UOM.
  - Verificación focal y regresiones relacionadas en verde.

- **Cobertura de código (2026-06-30):** Análisis de cobertura en Coveralls muestra 80.4% (22,566 líneas relevantes, 18,144 cubiertas).
  - Se identificaron módulos sin tests dedicados: `collaboration_service`, `party_settings`, `auth/forms`, `tax_pricing_service`, `module_badges`.
  - Se agregaron 17 tests unitarios en `tests/test_services_simple.py` cubriendo dataclasses, constantes y funciones de validación.
  - Commit: `test(coverage): add tests for tax_pricing_service and collaboration_service`

- **Filtros de listados (2026-06-27):** Compras, Ventas y Bancos de busqueda simple en sus listados principales.
  - Los listados transaccionales aceptan `search` y `status` por GET; `status` mapea borrador, contabilizado y cancelado a `docstatus`.
  - Los listados maestros principales de terceros, bancos, cuentas bancarias y transacciones bancarias aceptan `search`.
  - La paginacion conserva `search`/`status`, y los templates muestran controles Buscar/Limpiar con el macro comun `list_filters`.
  - Cobertura focal agregada en `tests/test_03webactions.py`.

- **Navegacion lateral (2026-06-27):** La barra lateral queda reservada para modulos operativos principales.
  - `Módulos` ya no aparece como entrada principal del sidebar; se mantiene dentro de Administración/Settings.
  - `Importaciones` ya no aparece como entrada principal del sidebar; se muestra dentro de Settings cuando el modo cloud y permisos lo permiten.
  - Se agrego prueba focal para proteger que ambos accesos vivan dentro de Settings y no como elementos primarios.

- **Refresh visual global (2026-06-18):** La aplicacion incorpora una capa moderna sobre el design system existente.
  - `cacao_accounting/static/css/cacaoaccounting.css` redefine tokens visuales y mejora navbar, sidebar, cards, grids de modulo, tablas, formularios, botones y superficies comunes.
  - Las pantallas de modulos ganan mas jerarquia visual: hover mas claro, iconos en contenedores suaves, mejor ritmo de lista y tarjetas sobrias sin franja decorativa superior.
  - El cambio es CSS-only y no modifica flujos, rutas ni templates funcionales.
  - Verificacion focal de render: `tests/test_01vistas.py::test_visit_views` en verde.

- **Actualización de contexto (2026-06-18):** Se releyeron los documentos base del dominio y se confirmó que la documentación operativa ya cubre el núcleo funcional del proyecto.
  - `modulos/contexto/core_concepts.md` fija las reglas de contabilidad, inventario, flujo documental y multi-compañía.
  - `modulos/contabilidad.md`, `modulos/compras.md`, `modulos/ventas.md`, `modulos/inventario.md`, `modulos/setup.md` y `modulos/relaciones.md` describen el alcance vigente.
  - `SESSIONS.md` queda como bitacora cronologica para continuidad por etapas.
  - `PENDIENTE.md` sigue siendo la fuente de backlog priorizado.

- **Backlog / Matriz de relaciones operativas (2026-05-24):** Se revisó el bloque pendiente del 2026-05-21 contra la implementación real y se confirmó que ya estaba cerrado.
  - `modulos/relaciones.md` documenta solo la matriz vigente implementada.
  - `cacao_accounting/document_flow/registry.py` contiene los `DOCUMENT_TYPES`, `create_actions` y `ALLOWED_FLOWS` correspondientes.
  - `SESSIONS.md` y este estado ya registraban las fases de implementación, hardening, prefill y pruebas de notas/devoluciones.
  - `PENDIENTE.md` fue actualizado para marcar ese bloque como completado.

- **Flujo Documental Expandible / Cierre de faltantes (2026-05-24):** El árbol recursivo de flujo documental queda extendido a Contabilidad y anticipos.
  - `journal_entry` se registra como tipo documental trazable y la vista de comprobante contable muestra la sección colapsable `Flujo documental`.
  - Las líneas de comprobante con `internal_reference` e `internal_reference_id` generan `DocumentRelation` desde el documento operativo hacia el comprobante contable al contabilizar.
  - La anulación de comprobantes revierte relaciones documentales hacia `journal_entry` conservando historial.
  - `apply_advance_to_invoice` completa el snapshot de `PaymentReference` y crea su `DocumentRelation` formal hacia `payment_entry`.
  - Se removió la implementación inline duplicada del componente Alpine, dejando `static/js/document-flow-tree.js` como única fuente del árbol.
  - Validación focal: `tests/test_document_flow_tree.py` + `tests/test_05document_flow.py` en verde (`37 passed`).

- **Conciliacion AR/AP masiva y Stock Reconciliation con valuacion (2026-05-23):** Se implementaron los dos pendientes prioritarios de conciliacion.
  - Caja y Bancos expone `/cash_management/payment-reconciliation` para aplicar pagos/cobros aprobados existentes contra facturas abiertas AR/AP sin crear pagos nuevos.
  - El servicio valida compania, tercero, direccion AR/AP, saldos disponibles, documentos aprobados y duplicados; persiste `PaymentReference`, `DocumentRelation` y `ReconciliationItem` manteniendo historial append-only.
  - Inventario incorpora Stock Reconciliation como documento de cantidad y valor objetivo, con snapshots de cantidad/tasa/valor actual y diferencias.
  - La valuacion crea `StockLedgerEntry`, `StockValuationLayer` incluso con `qty=0` para ajustes solo de valor, actualiza `StockBin` y genera GL balanceado por diferencia de valor.
  - El asiento de conciliacion usa la cuenta de inventario asignada globalmente a la bodega; la contrapartida y dimensiones globales del documento (cuenta de diferencia, centro de costos, unidad de negocio y proyecto) balancean el comprobante.
  - Las cancelaciones conservan trazabilidad append-only con reversos GL y movimientos inversos de inventario.

- **Compras/Ventas / Accesos administrativos de terceros (2026-05-23):** Las pantallas principales de los modulos ahora muestran los accesos de administracion de terceros ya soportados.
  - Compras expone **Tipos de Proveedor** y **Contactos y Direcciones de Proveedores** en Configuracion del Modulo.
  - Ventas expone **Tipos de Cliente** y **Contactos y Direcciones de Clientes** en Configuracion del Modulo.
  - Los tipos reutilizan `/settings/party-groups` filtrado por tipo de tercero; contactos/direcciones se gestionan desde el detalle de Cliente/Proveedor.

- **Payment Entry / Impuestos y Cargos visibles (2026-05-23):** El formulario `/cash_management/payment/new` vuelve a exponer el cálculo fiscal de forma explícita.
  - La sección **Impuestos y Cargos** aparece abierta por defecto y deja de estar escondida bajo "Deducciones o Pérdida".
  - La UI incluye acciones visibles para `Añadir impuesto/cargo` y `Recalcular`, reutilizando el endpoint fiscal `/api/fiscal/preview`.
  - Las líneas manuales permiten capturar método de cálculo, base, tasa, monto, tratamiento contable, prorrateo, cuenta contable y observaciones.
  - Se mantiene la persistencia existente de `tax_lines` y `tax_summary` en `payment_entry`.

- **Payment Entry / UX de formulario y detalle (2026-05-22):** El formulario `/cash_management/payment/new` queda alineado al flujo operativo solicitado.
  - Encabezado ordenado: Tipo de pago, Fecha, Compañía, Cuenta bancaria, Forma de pago, Secuencia y Moneda.
  - Compañía, Cuenta bancaria, Forma de pago, Secuencia, Tipo de tercero y Tercero usan `smart-select`; el tercero se filtra por Cliente/Proveedor según el selector previo.
  - La moneda se deriva de la cuenta bancaria y el tipo de cambio no se edita en UI; queda bajo control backend/posting para libros activos.
  - El contador externo y número de cheque solo se muestran para cheques; el número de cheque es no editable y proviene del contador configurado.
  - El backend ignora contadores externos en pagos que no son cheque y no acepta número externo manual para cheques.
  - `bancos/pago.html` adopta un layout tipo `journal.html`, con cabecera, datos bancarios, referencias y asientos contables.

- **Payment Entry / Implementación completa (2026-05-22):** Se completó la implementación de `payment_entry` según `requerimiento.md` y `payment.md`.
  - `pago.html` (vista de detalle) ahora muestra tabla de referencias aplicadas (tipo, documento, total, saldo previo, aplicado, descuento) y tabla de asientos contables GL.
  - Se añadió campo `Cuenta Bancaria` y `Referencia` en el encabezado del detalle.
  - La sección de referencias del formulario `pago_nuevo.html` se titula "Referencias del Pago" para consistencia con tests.
  - `PaymentEntry` persiste moneda y `PaymentReference` conserva snapshot mínimo de auditoría: tipo de relación, documento visible, fecha, tercero, compañía, moneda, saldo posterior, tasa y diferencia.
  - Anticipos desde Orden de Compra/Orden de Venta precargan línea de referencia, crean `DocumentRelation` activa y permanecen como pago abierto disponible para aplicación futura.
  - El formulario de pagos carga candidatos manuales desde `/api/document-flow/payment-reference-candidates`, filtrados por compañía, tercero y tipo documental.
  - Los pagos/cobros `pay`/`receive` requieren tercero explícito, y las notas crédito/débito validan dirección de pago/cobro según semántica del documento.
  - La anulación conserva `PaymentReference`, revierte relaciones documentales y recalcula saldos sin borrar historial funcional.
  - El handler `bancos_pago_nuevo` ahora captura excepciones `HTTPException` (incluye `Conflict` por mismatch de compañía/tercero) y las muestra como flash `danger`.
  - Cobertura de pruebas ampliada: snapshots de referencia, endpoint de candidatos, prefill desde órdenes, anticipos abiertos, bloqueo por documento borrador/cancelado, mismatch de compañía/tercero y verificación de vista de detalle.
  - Corregido test de cierre `test_06transaction_closure` para usar la API actual de `_save_payment_references` (retorna dict con `allocated`/`discount`/`gain_loss`).

- **Documentacion de relaciones (2026-05-22):** `modulos/relaciones.md` fue simplificado para reflejar unicamente flujos implementados y vigentes en `document_flow`.
- **Criterio de consistencia:** La matriz funcional documentada ahora se mantiene alineada a `DOCUMENT_TYPES` + `ALLOWED_FLOWS` y a acciones dinamicas en UI.

- **Legacy eliminado (2026-05-22):** Se removio la macro legacy `crear_dropdown` de `cacao_accounting/templates/macros.html`; no quedan referencias activas en templates.
- **Estrategia final de creacion:** Las acciones `Crear` en detalles operativos quedan 100% gobernadas por `document_flow_trace` y `create_actions` del backend.

- **UI / Unificación de acciones Crear (2026-05-21):** Las vistas de detalle transaccionales de Compras y Ventas ya no mantienen dropdowns `Crear` hardcodeados; la creación se rige por `document_flow_trace` y `create_actions` del backend.
- **Consistencia UI/Backend:** Se eliminó duplicidad de reglas en templates, reduciendo riesgo de desalineación entre botones visibles y `ALLOWED_FLOWS`.
- **Validación de vistas:** Regresión `tests/test_03webactions.py` + `tests/test_01vistas.py` en verde (`20 passed`).

- **Flujo Documental / Notas hacia Bancos (2026-05-21):** Se implementaron pares `purchase_credit_note`, `purchase_debit_note`, `sales_credit_note`, `sales_debit_note` hacia `payment_entry` con acciones `Crear` dedicadas.
- **Bancos / Prefill por tipo de nota:** `bancos_pago_nuevo` soporta parámetros `from_*_credit_note` y `from_*_debit_note`, resolviendo `payment_type`/`party_type` según semántica de reembolso o cobro/pago.
- **Trazabilidad semántica:** Las relaciones de pago usan el `document_type` real de la nota (no solo `purchase_invoice`/`sales_invoice`) al persistir `DocumentRelation`.
- **UI / Panel de flujo:** Los detalles de factura/nota en Compras y Ventas usan `registro.document_type` para consultar flujo y acciones correctas por tipo documental.
- **Matriz funcional:** `modulos/relaciones.md` quedó alineado con esta expansión y documenta que la devolución de venta operativa se canaliza con `sales_credit_note`.
- **Validación técnica:** `tests/test_05document_flow.py` (`17 passed`) y `tests/test_03webactions.py` (`19 passed`) en verde tras los cambios.

- **Flujo Documental / Expansión (2026-05-21):** Se habilitó `Crear Pago` desde Orden de Compra y Orden de Venta en acciones dinámicas de trazabilidad.
- **Flujo Documental / Compras:** Recepción de Compra ahora expone también `Crear Nota de Crédito` y `Crear Nota de Débito` (además de devolución/factura) con `query_params` de tipo documental.
- **Consistencia de matriz:** `ALLOWED_FLOWS` agrega pares de anticipos desde órdenes y notas desde recepción para mantener alineación UI/backend.
- **Bancos / Prefill:** `bancos_pago_nuevo` acepta origen desde `from_purchase_order` y `from_sales_order`, precargando contexto básico del tercero y compañía.
- **Validación técnica:** `tests/test_05document_flow.py` (`16 passed`) y `tests/test_03webactions.py` (`19 passed`) en verde tras la expansión.

- **Flujo Documental / Hardening pre-merge (2026-05-21):** `document_flow_summary` ahora expone `model_target_type`, `enabled` y `condition` en cada acción, y filtra acciones deshabilitadas para evitar divergencias UI/backend.
- **Flujo Documental / Consistencia de pares:** `ALLOWED_FLOWS` incluye pares lógicos para notas de débito/crédito y devoluciones en compras/ventas alineados con acciones dinámicas expuestas.
- **Contrato de URLs dinámicas:** Se validó construcción de `create_url` con `query_params` para notas y devoluciones derivadas de facturas/entregas/recepciones.
- **Validación técnica:** `tests/test_05document_flow.py` (`14 passed`) y `tests/test_03webactions.py` (`19 passed`) en verde después de los ajustes.

- **Flujo Documental / Implementación en curso (2026-05-21):** Se inició la ejecución de la nueva matriz de relaciones; `document_flow` ya entrega `create_actions` con URL resoluble y parámetros de query para tipos documentales derivados.
- **Flujo Documental / Registro:** Se ampliaron acciones `Crear` en `registry.py` para relaciones ya soportadas por rutas existentes (incluyendo devolución y notas débito/crédito sobre facturas de compra/venta, además de acciones adicionales en solicitudes/pedidos).
- **UI / Trazabilidad:** El panel `Flujo documental` muestra ahora una sección dinámica **Acciones disponibles** con botones de creación navegables, derivadas del backend y no únicamente de plantillas hardcodeadas.
- **Validación técnica:** Pruebas focales de flujo y acciones web en verde (`tests/test_05document_flow.py`, `tests/test_03webactions.py`).

- **Importaciones / Recuperación:** El arranque de Flask ya no registra error cuando no existen tablas de importación o no hay lotes en proceso vencidos; la recuperación solo marca como fallidos lotes reales atascados por más de cuatro horas.
- **Importaciones / UI:** El módulo lateral de Importaciones renderiza contenido en `base.html`, muestra un estado vacío cuando no hay lotes y usa `smart-select` en orden Compañía → Tipo de registro → Serie/Secuencia filtrada; el Libro Contable solo aparece para comprobantes contables.
- **Importaciones / Flujos Operativos:** El módulo permite crear lotes para documentos del flujo Source to Pay y Order to Cash: solicitudes, cotizaciones, órdenes, recepciones/entregas y facturas de compra/venta.
- **Importaciones / Comprobantes Contables:** Cuando no se selecciona Libro Contable, la importación usa todos los libros activos de la compañía; seleccionar uno restringe el lote a ese libro.
- **Transaccionales / Líneas:** Source to Pay, Order to Cash e Inventario ofrecen `Importar líneas` para carga masiva. Los documentos derivados conservan `Actualizar Elementos` desde documentos origen reales con ítems abiertos de la misma compañía y tercero.
- **Transaccionales / Acciones:** Todos los registros de Compras, Ventas e Inventario muestran `Actualizar Elementos` e `Importar líneas`; `Actualizar Elementos` incluye registros existentes del mismo tipo documental cuando aplica.
- **Transaccionales / Iconografía:** El macro compartido agrega iconos a los botones visibles de cabecera, grilla, modales, importación, impuestos y preferencias.
- **Comprobante Contable / Líneas:** El comprobante manual ofrece `Importar líneas` para cuentas/débitos/créditos y no muestra `Actualizar Elementos`, ya que no maneja ítems ni documentos origen.
- **Contabilidad / Presupuesto:** La pantalla principal de Contabilidad muestra una sección independiente **Presupuesto** para `Administrar Presupuestos` y `Real versus Presupuesto`, separada de los reportes contables generales.
- **Politica de numeracion documental:** `document_no` es irreversible una vez emitido. Los borradores conservan su numero aunque cambien fecha, compania o serie; si se genero una numeracion incorrecta, el registro debe anularse y crearse uno nuevo para preservar consecutivos rigurosos y trazabilidad sin huecos por eliminacion fisica.
- **MVP Fiscal (preview unificado):** Implementada matriz de comportamiento fiscal/gastos por tipo documental en `fiscal_preview_service.py`, con resolución por doctype y evento de reconocimiento.
- **API Fiscal Unificada:** Disponible `POST /api/fiscal/preview` para cálculo/preview común consumible por formularios transaccionales.
- **Preview fiscal canónico:** Los recálculos de preview priorizan reglas persistidas de `TaxRule` para conservar cascadas, dependencias y orden; las líneas reenviadas por el cliente ya no sustituyen reglas configuradas.
- **Impuestos/cargos manuales:** El bloque transaccional permite añadir líneas fiscales manuales desde la UI; el backend las adjunta a las reglas canónicas sin duplicar líneas automáticas reenviadas por el cliente.
- **Cobros bancarios:** `payment_entry` de tipo `receive` usa perfil de cobro (`sales` / `collection_confirmed`) para alinear preview, snapshot persistido y posting.
- **Guard UI fiscal:** El framework transaccional omite auto-preview para doctypes fuera de matriz fiscal, evitando errores visuales en flujos como cotizaciones.
- **UX Común “Impuestos y Cargos”:** Integrado en el framework transaccional compartido (Compras, Ventas, Inventario) con resumen de totales y modal de detalle por línea fiscal.
- **Bancos (alcance ajustado por requerimiento):** El bloque fiscal quedó activo solo en **Entrada de Pagos**; Nota de Crédito, Nota de Débito y Transferencia no requieren estos campos en esta fase.
- **Seguridad y calidad:** Corregida exposición de errores internos en API de preview; `codeql_checker` sin alertas, checks de calidad en verde para los cambios.
- **Persistencia fiscal real:** Implementada para `purchase_invoice`, `sales_invoice` y `payment_entry` mediante `document_tax_summary` y `document_tax_line`, incluyendo snapshot inmutable por línea.
- **Persistencia fiscal robusta:** Las cuentas fiscales vacías se guardan como `NULL` en `DocumentTaxLine.account_id`, evitando violaciones de FK cuando el usuario no selecciona cuenta.
- **Contabilización fiscal histórica:** `submit_document` para `purchase_invoice`, `sales_invoice` y `payment_entry` consume primero el snapshot fiscal persistido antes de cualquier fallback dinámico.

- **AR/AP y Terceros:** Implementado `PartyGroup` como catalogo global de tipos de cliente/proveedor y `Party.party_group_id` con sincronizacion hacia `classification` para compatibilidad.
- **Clientes y Proveedores:** Los maestros permiten crear/editar/ver tipo de tercero, estado global y configuracion por compania (`CompanyParty`, `PartyAccount`, plantilla fiscal y flags de compra).
- **Contactos y Direcciones:** Detalles de Cliente y Proveedor permiten gestionar multiples contactos y direcciones con alta, edicion inline y desactivacion, usando `Contact`, `Address`, `PartyContact` y `PartyAddress`.
- **Search Select:** Agregados doctypes `party_group`, `customer_group` y `supplier_group` para seleccionar Tipo de Cliente / Tipo de Proveedor desde formularios.
- **Validacion terceros:** Pruebas focales de esquema, search-select, rutas de terceros y render general de vistas en verde; Black, Ruff, Flake8, Mypy y pydocstyle focal pasan.

- **Revalorizacion cambiaria NIIF:** Implementado `ExchangeRevaluationService` para runs auditables multiledger, calculo incremental por documento/cuenta bancaria, omision de moneda origen, ejecuciones sin diferencias y anulacion con reversos GL.
- **Trazabilidad de revalorizacion:** `ExchangeRevaluation`, `ExchangeRevaluationItem` y `GLEntry.exchange_revaluation_run_id` guardan snapshot de tasas, saldos, documento fuente, tercero, cuenta, ledger y linea GL.
- **UI y cierre mensual:** Contabilidad cuenta con listado, formulario, detalle solo lectura y anulacion de revalorizaciones; el asistente de cierre mensual ejecuta la revalorizacion despues de comprobantes recurrentes.
- **Validacion revalorizacion:** Suite completa `pytest --slow=True` en verde (`681 passed`); Black, Ruff, Flake8, Mypy focal y pydocstyle focal tambien pasan.

- **Calidad Python (docstrings):** `pydocstyle` queda integrado al flujo de desarrollo y CI (`development.txt`, `run_test.sh` y workflow `python-package.yml`) con convención `pep257`.
- **Regla de documentación:** `AGENTS.md` ahora exige documentación adecuada mediante docstrings en módulos, clases y funciones.
- **Estado de `cacao_accounting`:** No se detectan docstrings faltantes (pydocstyle y validación AST sin hallazgos).

- **Merge Bancos remoto:** Integrada la rama `feat/banking-module-registers-16721791397278534001` con resolucion manual de conflictos, conservando funcionalidad existente en modulos no bancarios.
- **Bancos UX/Flujo:** Pagos, notas de debito/credito y transferencias internas ahora comparten formularios unificados con smart-select y payload JSON para captura rapida.
- **Compatibilidad de posting bancario:** Transferencias internas convierten cuentas bancarias origen/destino a cuentas GL (`paid_from_account_id`/`paid_to_account_id`) antes del posteo.
- **Documentos Operativos:** Detalles de Compras, Ventas e Inventario muestran moneda del registro, totales y lineas con codigo de moneda (`NIO 1,000.00`) y cantidades con 4 decimales (`10.0000`).
- **Comprobante Contable:** La moneda se muestra como codigo (`NIO`) y los importes `Debe`/`Haber` usan separador de miles con codigo de moneda (`NIO 1,000.00`) en tabla, panel y modal de detalle.
- **Comprobante Manual:** La leyenda `Comprobante manual` queda alineada bajo el numero del comprobante, igualando la cabecera de documentos operativos.
- **Validacion CI y Cobertura:** Workflow local equivalente en `venv` queda verde: build/twine, flake8, ruff, mypy, black, pytest completo con cobertura (`623 passed`, 83% total Python), `npm ci && npm test` (`21 passing`) y cobertura JavaScript con c8 (77% total).
- **Datos Demo de Terceros:** `Cliente Demo SA` y `Proveedor Demo SA` ahora se activan en `CompanyParty` para `cacao`, habilitando `smart-select` de clientes/proveedores filtrado por compania en Compras y Ventas.

- **Correccion UI Transaccional:** El modal compartido de detalle de linea inicializa sus `smart-select` solo cuando existe `modalLine`, conserva valores existentes y la secuencia se recarga automaticamente al cambiar compania.
- **Smart Select en Grids:** Los formularios transaccionales usan hidden inputs escalares como fuente de verdad; items filtran por compania y cargan descripcion, UOM predeterminada y UOMs permitidas.
- **Cabecera de Detalle:** Solicitud de Compra usa la misma estructura visual del comprobante manual: documento como titulo, tipo bajo el titulo, estado junto al numero, acciones a la derecha y datos dentro de la misma tarjeta.
- **Comprobante Manual:** El comprobante contable muestra `Comprobante manual` debajo del numero para mantener paridad visual con los documentos operativos.
- **Contabilidad / Plantillas recurrentes:** La pantalla de nueva plantilla recurrente volvió a separar toolbar, cabecera y tabla de asientos. El layout ya no colapsa todos los campos en una sola fila.

- **Contabilidad / Reversión y Anulación:** `Revertir` ahora solo permite fechas en otro período contable; `Anular` solo permite anular comprobantes con fecha igual al día del comprobante.
- **Contabilidad / Naming Series mensual:** Los comprobantes manuales renumeran borradores cuando cambia fecha o serie, y las secuencias asociadas a prefijos con `*MM*` o `*MMM*` resetean por mes aunque provengan de configuración heredada con política anual.
- **Contabilidad / Listado de comprobantes:** El listado ya no depende del ULID como texto visible para borradores de reversión sin número definitivo; muestra un nombre amigable basado en el contexto contable del comprobante.

- **Contabilidad / Importar líneas en comprobantes:** El comprobante manual ya ofrece un asistente más usable para `Importar líneas`, con pestañas para pegar o subir XLSX, descarga local de plantilla y previsualización antes de validar/inserar.
- **Importación tabular / Encabezados bilingües:** El mapeo de columnas de line import ahora tolera encabezados en español o inglés, ignora acentos/guiones bajos y puede caer por posición cuando el título no coincide, tanto en el asistente compartido como en el formulario manual de comprobantes.

- **Acciones en Borrador:** Solicitud de Compra en borrador muestra `Editar`, `Duplicar`, `Aprobar`, `Listado` y `Nuevo`; `Crear` permanece reservado para documentos aprobados.
- **Paridad Funcional Transaccional:** Compras, Ventas e Inventario incorporan rutas y acciones de `Editar` y `Duplicar` en documentos transaccionales, con edición restringida a borrador y duplicado disponible en borrador/aprobado.
- **Compras RFQ/SQ:** Se habilitaron rutas faltantes de `submit` y `cancel` para Solicitud de Cotización y Cotización de Proveedor; los botones del detalle ya no apuntan a endpoints inexistentes.
- **Actualizar Elementos:** Orden de Compra y Solicitud de Cotizacion pueden entrar desde Solicitud de Compra con origen precargado para traer lineas pendientes.
- **Framework Transaccional:** Estandarizado con soporte para `smart-select` en todos los niveles y layout uniforme.
- **Flujo Documental:** Soporta fusion de multiples fuentes con filtrado por Tercero y Compania.
- **Modulos Operativos:** Compras, Ventas e Inventario usan macros compartidas y ya tienen paridad de acciones en transaccionales; pendiente de consolidar cobertura y revisar casos limite en documentos maestros/no transaccionales.
- **Rutas de Inventario:** Renombradas a `inventory-issue` para mayor claridad semantica.
- **Pruebas:** Cobertura de mas de 600 tests unitarios/integracion y suite E2E Playwright basica para UI transaccional.
- **Verificación patch E2E/ULID:** Confirmado ajuste en `posting.py` para crear `StockBin` faltante y proteger `valuation_rate` con divisor `actual_qty > 0`. Se alinearon FKs de GL (`reversal_of`, `gl_entry_id`) a ULID de 26 caracteres y la suite de pruebas quedó en verde (`618 passed, 5 skipped`).
- **Motores de Cálculo Centralizados:** Implementada la nueva arquitectura de motores Fiscal, Landed Cost y Settlement. Los cálculos son determinísticos, auditables y configurables vía reglas sin código hardcodeado para impuestos específicos.
- **Golden Test de Importación:** Validado exitosamente el caso de referencia (DAI 5%, ISC 3%, IVA 15%) con costos de inventario y totales de factura exactos.
- **Audit Trail y Snapshots:** El sistema genera una explicación detallada de cada cálculo y persiste snapshots JSON con integridad SHA256 para trazabilidad histórica y reversiones precisas.
- **Infraestructura Contable Desacoplada:** Los motores Fiscal, Landed Cost y Settlement son ahora ciudadanos de primera clase, con soporte para redondeo avanzado, mapeo contable pro-forma y resolución dinámica de reglas.
- **Reglas Fiscales Persistidas:** Existe el modelo `TaxRule`, con servicio `tax_rule_service.py` para CRUD y conversión a `TaxRuleContext`, además de una pantalla administrativa en `/settings/tax-rules`.
- **Mapping Contable de Liquidaciones:** `AccountingMapper` ya distingue `payment_confirmed` and `collection_confirmed`, generando líneas pro-forma para tercero, banco/caja, retenciones y diferencia cambiaria.
- **Multimoneda en Proforma:** `JournalEntryLineProforma` ahora transporta moneda de transacción, moneda compañía, monto dual y tipo de cambio usado; `SettlementEngine` calcula diferencia cambiaria realizada para pagos/cobros.
- **Motor listo para transacciones:** `contabilidad/posting.py` ya puede usar el motor fiscal/gastos para `PurchaseReceipt`, `PurchaseInvoice`, `SalesInvoice` y `PaymentEntry` mediante builders de contexto y un posting builder que persiste `JournalEntryProforma` como `GLEntry`.
- **TaxRule en flujo real:** El acoplamiento transaccional carga `TaxRule` desde BD por evento (`purchase_invoice_confirmed`, `sales_invoice_confirmed`, `payment_confirmed`, `collection_confirmed`, notas de crédito, etc.) y mantiene fallback a `TaxTemplate` para no romper documentos existentes.
- **DAG + settlement ampliado:** `FiscalEngine` resuelve dependencias entre reglas vía ordenamiento topológico; `SettlementEngine` soporta descuentos por pronto pago y revaluación no realizada; `AccountingMapper` genera el offset del control AR/AP para la revaluación no realizada.
- **Landed Cost transaccional:** `LandedCostEngine` calcula prorrateo de cargos capitalizables y el flujo real de recepción de compra materializa el costo aterrizado en la capa inicial de `StockValuationLayer` cuando los cargos ya son conocidos al ingreso. Para costos posteriores, la factura de compra puede persistir una capa de ajuste por valor sin cambiar cantidad.
- **Trazabilidad de importación:** Se agregó `LandedCostAllocation` como tabla dedicada de prorrateo para no sobrecargar `StockValuationLayer`; cada asignación guarda línea documental, ítem, almacén, base, monto asignado, costo final y referencia opcional a la capa de valuación.
- **Cobertura de eventos revisados:** El flujo real quedó cubierto para recepciones de compra, facturas de compra/venta, pagos/cobros y notas de crédito; el evento `import_landed_cost_confirmed` sigue disponible en motores/orquestador para casos de importación calculada.
- **Validación actual:** En `.venv`, `black --check cacao_accounting/`, `ruff`, `flake8`, `mypy`, `pydocstyle` focal y `pytest -v -s --exitfirst --slow=True` completo están en verde (`672 passed`).

- **Servicio Centralizado de Importación:** Implementado framework de importación tabular en `cacao_accounting/imports` con soporte para CSV (con auto-detección de delimitador), XLS, XLSX y ODS (extracción robusta de tipos). Permite carga masiva de Catálogo de Cuentas, Clientes, Proveedores, Comprobantes Contables y Órdenes de Compra.
- **Control de Modo Escritorio:** El servicio de importación cuenta con guardias de seguridad que bloquean el acceso y la ejecución si `MODO_ESCRITORIO` está habilitado, tanto en rutas backend como en UI.
- **Procesamiento de Grado Enterprise:**
  - Soporta validación estructural/negocio, previsualización de datos y ejecución asíncrona (daemon threads).
  - Garantiza la integridad vía rollbacks automáticos por documento y bloqueos de concurrencia (`with_for_update`).
  - Validación de períodos contables cerrados y protección contra inyección de fórmulas en archivos.
  - Generación de plantillas en formatos CSV, XLSX y ODS.

- **Badges Semánticos de Módulos:** Las tarjetas de Contabilidad, Compras, Ventas, Inventario, Bancos y Administración usan `module_badge()` y la macro `module_status_badge` para calcular estados semánticos: verde `ok`, gris `no_access`, azul `pending_approval`, beige `view_only` y rojo `attention`.
- **Accesibilidad de Badges:** Los badges de módulo exponen `title`, `aria-label`, `data-status` y texto oculto para lectores de pantalla; los colores ya no son la única fuente de significado.
- **Contabilidad / Buscador de Transacciones:** Los listados de comprobantes contables (`/accounting/journal/list`), comprobantes recurrentes (`/accounting/journal/recurring`) y revalorizaciones cambiarias (`/accounting/exchange-revaluation`) usan el mismo filtro reusable de búsqueda que los listados operativos de Compras, Ventas y Bancos.

- **Bancos / Referencias de pago:** `_save_payment_references` quedó descompuesta en helpers para lectura de formulario, carga de documento, validación de negocio y construcción de `PaymentReference`. La lógica funcional se mantuvo y la suite focal de referencias de pago quedó en verde (`5 passed`).
- **Bancos / Hotspots de complejidad:** `bancos_pago_nuevo`, `_crear_nota_bancaria`, `_payment_source_rows`, `_validate_payment_header`, `find_bank_reconciliation_candidates`, `reconcile_bank_items` e `import_bank_statement` fueron refactorizados con helpers y `match/case` en los puntos de dispatch. Las pruebas focales de Bancos, Conciliación e Importación quedaron en verde (`116 passed`).
- **Compras / Cotización de proveedor:** `compras_cotizacion_proveedor_nueva` y `compras_cotizacion_proveedor_editar` comparten helpers de catálogo, fuentes y configuración transaccional para reducir duplicación sin alterar el contrato de la vista.

- **O2C-03: Reserva de inventario en Orden de Venta (2026-07-08):** Se implementó reserva de inventario al aprobar Orden de Venta y liberación al cancelar OV o al aprobar Nota de Entrega vinculada.
  - `StockBin.reserved_qty` es ahora non-nullable con default 0.
  - SO submit valida `actual_qty - reserved_qty >= qty`, rechaza si insuficiente.
  - SO cancel libera la reserva (`reserved_qty -= qty`).
  - DN submit libera reserva si tiene `sales_order_id`.
  - DN cancel restaura reserva si tiene `sales_order_id`.
  - `_create_delivery_note_from_invoice` propaga `sales_order_id`.
  - `rebuild_stock_bins` preserva `reserved_qty`.
  - API `stock-bin-snapshot` expone `reserved_qty`.
  - 8 tests nuevos en `test_stock_reservation.py`.
  - Commits: `7c6c85f`, `fc336fc`, `8868cec`, `35e220c`.

- **S2P-02 y S2P-05 corregidos (2026-07-08):** Se implementó prevención de sobre-facturación contra recepción (3-way match) y manejo amigable de `PurchaseReconciliationError`.
  - `_validate_invoice_quantities_against_receipt()` rechaza submit si `consumed_qty > receipt.qty`.
  - `_handle_purchase_invoice_edit_post` limpia relaciones viejas para evitar doble conteo en ediciones.
  - `compras_factura_compra_submit` captura `(PostingError, ValueError, DocumentFlowError)` en lugar de solo `PostingError`.
  - Commit: `f920176`

- **S2P-06 y O2C-05 corregidos (2026-07-08):** Se implementaron validaciones pre-submit para los 12 endpoints transaccionales.
  - Nueva funcion `validate_submit_prerequisites()` en `document_flow/validation.py` que valida compania, fecha, tercero, lineas y cantidades.
  - 6 endpoints de compras, 5 de ventas y 1 de inventario ahora tienen validacion en el limite del submit.
  - Endpoints sin manejo de error previo ahora capturan `ValueError` con flash message.
  - `ventas_entrega_submit` e `inventario_entrada_submit` ampliaron captura a `(PostingError, ValueError)`.
  - 12 tests unitarios en `tests/test_validation.py`.
  - Commits: `b149b09`, `3fa36a6`, `a774532`, `faf08a4`.

- **CAS-02 corregido (2026-07-08):** Se implementó auto-poblado de exchange_rate en pagos.
  - `_create_payment_entry` acepta parámetro `exchange_rate` en lugar de hardcodear `None`.
  - `_build_payment_from_payload` resuelve rate vía `_lookup_exchange_rate()` cuando difiere la moneda.
  - `_update_payment_amounts` aplica exchange_rate a montos base.
  - Commits: `bb40f22`, `61e15a4`.

- **CAS-03 corregido (2026-07-08):** Se implementó bloqueo FOR UPDATE en lectura de saldo pendiente.
  - `_load_payment_reference_document` en bancos usa `with_for_update()`.
  - `_get_reference_document` en document_flow/service.py usa `with_for_update()`.
  - Commits: `74079bf`, `61e15a4`.

- **R2R-01, R2R-02, CAS-01 marcados como REQUIERE REVISION:** Verificados como falsos positivos.
  - R2R-01: `validate_accounting_period` ya se llama desde `_document_contexts()` en todos los postings.
  - R2R-02: `_assert_entries_balance()` en `_add_entries()` ya verifica balance antes de persistir.
  - CAS-01: El balance bancario ya se deriva de GLEntry en dashboard, reportes y revaluación.

## 2026-07-10 (Rediseño de la CLI cacaoctl)
- **Estado:** Completado. `cacaoctl` ya no expone la identidad de Flask: usa `prog_name="cacaoctl"`, banner propio y ayuda agrupada por categorías.
- **Comandos disponibles:** `db init|reset|clean|seed`, `run`, `serve`, `shell`, `routes`, `version`, `status`, `config`.
- **Nuevos:** `status` and `config` (diagnóstico); confirmaciones en `db reset`/`db clean` con `--force`; colores en la salida; opciones `--env/--verbose/--quiet/--version`.
- **Nota:** `ventas/__init__.py` tenía un error de sintaxis preexistente que impedía importar la app; se corrigió la indentación del `except` en `ventas_factura_venta_nuevo`.
