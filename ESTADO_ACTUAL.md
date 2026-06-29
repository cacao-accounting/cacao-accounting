# Estado Actual del Proyecto - 2026-06-27

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
