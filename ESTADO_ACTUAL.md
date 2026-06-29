# Estado Actual del Proyecto - 2026-06-27

- **SonarCloud / Validación de presupuesto (2026-06-29):** Se redujo la complejidad de `cacao_accounting/contabilidad/budget_service.py` separando la validación de cuenta, centro de costo, periodo, unidad de negocio, proyecto y unicidad.
  - `_validate_line_data()` ahora solo orquesta helpers pequeños y la semántica de alta/edición de líneas se mantiene sin cambios.
  - Se agregó una prueba focal que cubre cuenta agrupadora, centro de costo inválido, unidad de negocio inválida, proyecto inválido y duplicidad.
  - `black`, `ruff`, `flake8`, `mypy` focal y `tests/test_budget.py` quedaron en verde.

- **SonarCloud / Adaptador transaccional (2026-06-29):** Se redujo la complejidad de `cacao_accounting/imports/adapters/transaction_documents.py` separando el mapeo opcional de campos en helpers pequeños.
  - `_apply_optional_item_fields` ahora delega en helpers para montos base, tasas, campos configurados en cero y lote/serie, manteniendo el mismo comportamiento de importación.
  - Se agregó una prueba focal con un item mínimo en memoria para cubrir todas las ramas del mapeo opcional sin depender de base de datos.
  - `ruff`, `flake8`, `mypy` focal y la suite focal de imports/closure quedaron en verde.

- **SonarCloud / Importación de presupuesto (2026-06-29):** Se redujo la complejidad de `cacao_accounting/contabilidad/budget_import_service.py` separando el parseo ODS, la expansión de celdas repetidas y la validación por fila en helpers pequeños.
  - La lectura del archivo ahora delega en helpers para filas ODS, normalización de encabezados, conversión de celdas y validación de totales/periodos, manteniendo la semántica de importación.
  - Se extrajeron resolutores explícitos para cuentas, centros de costo, unidades de negocio y proyectos, lo que deja la validación más lineal y mantenible.
  - `ruff`, `flake8`, `mypy` focal y `tests/test_budget.py` quedaron en verde.

- **SonarCloud / Estado documental (2026-06-29):** Se redujo la complejidad de `cacao_accounting/document_flow/status.py` separando la resolución de `journal_entry`, los targets primarios y el mapeo de progreso en helpers pequeños.
  - La rama de `journal_entry` ahora se resuelve con un helper dedicado y la selección de progreso primario quedó lineal, sin cambiar la semántica de badges visibles.
  - Se agrego una prueba focal para `journal_entry` sin `docstatus` y la suite de flujo documental quedó en verde (`19 passed`).

- **SonarCloud / Persistencia fiscal (2026-06-29):** Se redujo la complejidad de `cacao_accounting/fiscal_persistence_service.py` separando la persistencia de resumen, líneas y snapshots de reglas en helpers pequeños.
  - `build_tax_rule_contexts_from_snapshot` ahora delega el mapeo de cada `DocumentTaxLine` a `TaxRuleContext` en un helper dedicado, manteniendo el contrato funcional.
  - `ruff`, `flake8`, `mypy` focal y `tests/test_tax_rules.py` quedaron en verde. `black` se dejó para el cierre en lote, conforme a la instrucción de la sesión.

- **SonarCloud / Presupuesto importación (2026-06-29):** Se cerro el issue `python:S1192` en `cacao_accounting/contabilidad/presupuesto.py` al consolidar `contabilidad/presupuestos/import.html` en `_TEMPLATE_PRESUPUESTO_IMPORTAR`.
  - La ruta de importación de presupuestos ahora reutiliza el mismo identificador de plantilla en GET, previsualización y confirmación.
  - Se agrego una prueba focal en `tests/test_budget.py` que autentica un cliente y verifica que la vista renderiza el template compartido.
  - `ruff`, `mypy` y la suite focal de presupuesto quedaron en verde; `flake8` mantiene avisos `CCR001` preexistentes en otras funciones del archivo.

- **SonarCloud / Ventas cliente (2026-06-29):** Se cerro el issue `python:S1192` en `cacao_accounting/ventas/__init__.py` al consolidar `ventas/cliente_nuevo.html` en la constante `VENTAS_CLIENTE_NUEVO_TEMPLATE`.
  - Las rutas de alta y edicion de clientes reutilizan ahora el mismo identificador de plantilla sin duplicar el literal.
  - `black --check`, `ruff check`, `mypy` focal y `tests/test_party_management.py` quedaron en verde; `flake8` mantiene avisos `CCR001` preexistentes en otras funciones del mismo archivo.

- **SonarCloud / Compras proveedor (2026-06-29):** Se cerro el issue `python:S1192` en `cacao_accounting/compras/__init__.py` al consolidar `compras/proveedor_nuevo.html` en la constante `COMPRAS_PROVEEDOR_NUEVO_TEMPLATE`.
  - Las rutas de alta y edicion de proveedores reutilizan ahora el mismo identificador de plantilla sin duplicar el literal.
  - `black --check`, `ruff check`, `mypy` focal y `tests/test_party_management.py` quedaron en verde; `flake8` mantiene avisos `CCR001` preexistentes en otras funciones del mismo archivo.

- **SonarCloud / Smart Select nesting (2026-06-29):** Se cerro un issue `javascript:S2004` en `cacao_accounting/static/js/smart-select.js`.
  - La busqueda de opciones por valor normalizado ahora pasa por `findOptionByNormalizedValue()`, evitando anidar `find()` dentro del callback del componente Alpine.
  - Se agrego una prueba JS focal para validar que el valor seleccionado recupera la etiqueta correcta desde `options`.
  - `npm test -- --grep smart-select`, `black --check tests/test_10_smart_select_js.py`, `ruff`, `mypy` y `tests/test_10_smart_select_js.py` quedaron en verde.

- **SonarCloud / Importaciones captions (2026-06-29):** Se cerraron dos issues `Web:TableWithoutCaptionCheck` en templates de importacion.
  - Las tablas de `cacao_accounting/imports/templates/imports/index.html` y `detail.html` ahora declaran `<caption>` antes de `<thead>`, que es la estructura esperada por accesibilidad y por el analizador.
  - Se agrego una prueba focal en `tests/imports/test_routes.py` para evitar regresiones en el orden del marcado.
  - `black --check`, `ruff`, `mypy` focal y `tests/imports/test_routes.py` quedaron en verde.

- **SonarCloud / Transaction Form errores (2026-06-29):** Se cerraron issues menores en `cacao_accounting/static/js/transaction-form.js`.
  - Los errores de preview fiscal y validacion de importacion ahora pasan por helpers explicitos con `console.warn` y estado UI consistente.
  - La suite JS del formulario transaccional quedo en verde (`13 passing`), incluyendo pruebas nuevas para ambos caminos de error.
  - `black` no aplica a archivos JavaScript en esta configuracion del proyecto.

- **SonarCloud / Smart Select errores (2026-06-29):** Se cerraron issues menores en `cacao_accounting/static/js/smart-select.js`.
  - Los errores de fetch ya no quedan capturados de forma muda; ahora pasan por `handleFetchError()` con `console.warn` y estado UI consistente.
  - La suite JS de `smart-select` quedo en verde (`16 passing`).
  - `black --check tests/test_10_smart_select_js.py` quedo en verde.

- **SonarCloud / Comprobante manual importador (2026-06-29):** Se cerro un issue menor en `cacao_accounting/contabilidad/templates/contabilidad/journal_nuevo.html`.
  - La carga de celdas importadas del comprobante manual ahora usa una condicion positiva sobre `cellValue` en lugar de una comparacion negada inline.
  - La vista general y la suite focal del formulario de comprobante quedaron en verde.
  - `black --check tests/test_09_journal_entry_form.py` quedo en verde.

- **SonarCloud / Pago nuevo (2026-06-29):** Se cerro un issue menor en `cacao_accounting/bancos/templates/bancos/pago_nuevo.html`.
  - El watcher de `mode_of_payment` ahora toma primero el caso positivo de cheque y deja el reseteo de contador/numero en `else`.
  - Se validaron el render del formulario nuevo y los dos comportamientos de negocio relevantes: transferencia sin chequera y cheque con contador default.
  - `black --check tests/test_payment_entry_improved.py` quedo en verde.

- **SonarCloud / Transaction Form (2026-06-29):** Se cerro un issue menor en `cacao_accounting/static/js/transaction-form.js`.
  - La resolucion de columnas importadas usa una condicion positiva (`foundIndex >= 0`) en lugar de la comparacion negada previa.
  - La suite JS del formulario transaccional paso completa (`11 passing`).
  - `ruff` no aplica a archivos JavaScript en esta configuracion del proyecto.

- **SonarCloud / Smart Select (2026-06-29):** Se cerro un issue menor en `cacao_accounting/static/js/smart-select.js`.
  - `handleSelectedValueChange()` ahora usa una condicion positiva en lugar de negar el valor normalizado.
  - La suite JS del componente `smart-select` paso completa (`16 passing`).
  - `ruff` no aplica a archivos JavaScript en esta configuracion del proyecto.

- **SonarCloud / Document Flow candidatos (2026-06-29):** Se cerro un issue menor en `cacao_accounting/document_flow/service.py`.
  - `_build_candidate_query()` elimino un branch duplicado y mantiene un unico filtro por `document_type` cuando el modelo lo soporta.
  - La prueba focal del endpoint de candidatos de referencia quedo en verde junto con Black, Ruff y Mypy focal.

- **SonarCloud / Versionado (2026-06-29):** Se cerro un issue menor en `cacao_accounting/version/__init__.py`.
  - La composicion de `VERSION` ahora usa `build_version()` en lugar de una condicion constante sobre `PRERELEASE`.
  - Se agregaron pruebas unitarias para prerelease, postrelease y version simple en `tests/test_00basicos.py`.
  - `ruff`, `mypy` y `tests/test_00basicos.py` quedaron en verde. `black --check` indico ambos archivos sin cambios antes de expirar por `timeout`.

- **SonarCloud / Ventas orden de venta (2026-06-29):** Se cerro un issue menor en `cacao_accounting/ventas/__init__.py`.
  - La resolucion del `initialSourceType` ahora vive en `_sales_order_initial_source_type()` con flujo explicito.
  - Se agrego una prueba focal en `tests/test_03webactions.py` para cubrir solicitud, cotizacion, vacio y precedencia.
  - `ruff`, `mypy` y la prueba focal quedaron en verde. `black --check` indico ambos archivos sin cambios antes de expirar por `timeout`.

- **SonarCloud / Compras factura de compra (2026-06-29):** Se cerro un issue menor en `cacao_accounting/compras/__init__.py`.
  - `_purchase_invoice_document_type()` ahora usa flujo explicito en lugar de ternario anidado para resolver `purchase_return`, `purchase_credit_note` o `purchase_invoice`.
  - Se agrego una prueba focal en `tests/test_03webactions.py` para cubrir la precedencia de origenes y el override explicito de `document_type`.
  - `ruff`, `mypy` y la prueba focal quedaron en verde. `black --check` indico que ambos archivos estaban sin cambios antes de expirar por `timeout`.

- **SonarCloud / Bancos validacion de tercero (2026-06-29):** Se cerro un issue menor en `cacao_accounting/bancos/__init__.py`.
  - `_validate_payment_party()` elimino un `if` anidado y ahora expresa la regla en una sola condicion.
  - La semantica funcional no cambia: pagos/cobros siguen exigiendo tercero y los tipos invalidos siguen rechazandose.
  - La prueba focal `tests/test_06transaction_closure.py::test_validate_payment_header_rejects_missing_party_for_payment_and_invalid_type` paso en verde con Black, Ruff y Mypy focal.

- **SonarCloud / Comprobante manual (2026-06-29):** Se cerraron issues menores en `cacao_accounting/contabilidad/templates/contabilidad/journal_nuevo.html`.
  - La deteccion de columnas importadas usa `Set.has()` en lugar de `includes()` sobre una lista derivada.
  - La normalizacion de lineas ahora usa `mergeJournalLine()` y elimina el fallback con objeto vacio en el spread.
  - `tests/test_01vistas.py::test_visit_views` y `tests/test_09_journal_entry_form.py` pasaron en verde.

- **SonarCloud / Bancos (2026-06-29):** Se cerro un issue menor en `cacao_accounting/bancos/templates/bancos/pago_nuevo.html`.
  - La clonacion de lineas para modales de referencias e impuestos ahora usa `cloneModalLine()` en lugar del patron con objeto vacio que Sonar marcaba.
  - El cambio no altera logica funcional del formulario de pagos.
  - `tests/test_fiscal_preview.py::test_forms_render_tax_charges_block` paso en verde.

- **SonarCloud / Importaciones (2026-06-29):** Se cerro un issue menor de SonarCloud en `cacao_accounting/imports/services/import_service.py`.
  - Se eliminaron reasignaciones de `batch` en helpers internos y se uso `current_batch` para hacer explicito el acceso al estado persistido.
  - El cambio es funcionalmente neutro y reduce ruido de analisis estatica.
  - La suite focal `tests/imports/test_service.py` paso en verde junto con Black, Ruff y Mypy focal.

- **Consulta SonarCloud (2026-06-29):** Se uso la API publica de SonarCloud para listar issues abiertos del proyecto y se confirmaron 113 hallazgos activos.
  - Se priorizaron avisos de bajo riesgo semantico para una primera limpieza: `journal_nuevo.html` y `cacaoaccounting.css`.
  - `journal_nuevo.html` dejo de usar el patron `this -> self` en la inicializacion del selector de compania y ahora delega en helpers de sincronizacion.
  - `cacaoaccounting.css` elimino una propiedad de borde redundante reportada por Sonar.
  - La vista focal `tests/test_01vistas.py::test_visit_views` paso en verde despues del ajuste.

- **Ajuste de calidad (2026-06-29):** Se corrigio el docstring de `_persist_bank_transaction` para cumplir `pydocstyle`/`D401`.
  - El cambio fue solo documental y no modifica logica de negocio.
  - `venv/bin/python -m flake8 cacao_accounting/` valida el arreglo en verde.

- **Auditoria de pendientes (2026-06-27):** Se contrastaron los puntos abiertos de `PENDIENTE.md` contra el codigo fuente antes de actualizar el backlog.
  - La paridad funcional de formularios transaccionales para rutas `edit`/`duplicate` y transiciones de estado en POST queda marcada como completada.
  - La verificacion se basa en rutas implementadas en Compras, Ventas e Inventario y cobertura en `tests/test_03webactions.py`.
  - Se mantienen abiertos los puntos que siguen parciales o no implementados completamente: auditoria homogenea, filtros de listados, `LedgerMappingRule`, reportes legacy fuera del framework, drill-down/exportaciones universales y diagrama grafico de trazabilidad.
  - No hubo cambios funcionales de codigo en esta iteracion.

- **Filtros de listados (2026-06-27):** Compras, Ventas y Bancos incorporan busqueda simple en sus listados principales.
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
  - Inventario incorpora Stock Reconciliation como documento de cantidad y valor objetivo, con snapshots auditables de cantidad/tasa/valor actual y diferencias.
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
  - `PaymentEntry` persiste moneda y `PaymentReference` conserva snapshot mínimo de auditoría: tipo lógico, documento visible, fecha, tercero, compañía, moneda, saldo posterior, tasa y diferencia.
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
- **Mapping Contable de Liquidaciones:** `AccountingMapper` ya distingue `payment_confirmed` y `collection_confirmed`, generando líneas pro-forma para tercero, banco/caja, retenciones y diferencia cambiaria.
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
