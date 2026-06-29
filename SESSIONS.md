# SESSIONS - Historical Decisions & Milestones

## 2026-06-29 (Fix pydocstyle en statement_service)
- **Solicitud:** Corregir el fallo de CI reportado por `flake8`/`pydocstyle` en `_persist_bank_transaction`.
- **Implementacion:** Se actualizo el docstring de `_persist_bank_transaction` en `cacao_accounting/bancos/statement_service.py` para usar modo imperativo en ingles y cumplir `D401`.
- **Verificacion:** `venv/bin/python -m flake8 cacao_accounting/` quedo en verde tras el cambio.

## 2026-06-27 (Auditoria de PENDIENTE.md contra codigo fuente)
- **Solicitud:** Revisar `PENDIENTE.md` porque parecia no estar actualizado y marcar como completados los puntos que realmente ya estuvieran implementados.
- **Verificacion:** Se contrastaron los pendientes abiertos contra rutas, servicios, templates y pruebas. La paridad de formularios transaccionales con `edit`/`duplicate` y transiciones POST ya esta implementada en Compras, Ventas e Inventario y cubierta por `tests/test_03webactions.py`.
- **Resultado:** Se marco ese pendiente como completado y se agrego un bloque de seguimiento en `PENDIENTE.md`. Se dejaron abiertos los puntos parciales o realmente pendientes: `AuditTrail` homogeneo, filtros de listados, `LedgerMappingRule`, reportes legacy, drill-down/exportaciones universales, diagrama grafico de trazabilidad y cobertura adicional bancaria/fiscal.
- **Alcance:** Solo documentacion de estado/backlog; sin cambios funcionales de codigo.

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
