# Cola de trabajo pendiente — reconstruida desde la revisión disponible

> La bitácora local anterior fue sustituida accidentalmente durante QA. Esta cola recupera los pendientes que se habían leído en esta sesión; no pretende reproducir literalmente la copia perdida. Los veredictos y evidencias comprobables se conservan en `review.md` y en GitHub.

## Avance de esta reanudación

- **#1385 — implementado y QA1/QA2 aprobado.** `b029e73d`; CSV end-to-end para referencias compartidas, duplicado intra-lote y repetición entre lotes. `row_N` aceptado como localizador inequívoco. Issue abierto; GitHub muestra `fixed`.
- **#1432 — implementado y QA1/QA2 aprobado.** `9a6230d8` + `45e38f2b`; cierre terminal, bloqueo de rondas/adjudicaciones, mapeo de colisión única, i18n y regresiones adicionales. Issue abierto en `fix-confirmed`.
- **#2140 — sin cambios de estado/etiqueta.** QA1 y QA2 aprueban localmente el residual QA3 derivado de #1432; los seis hallazgos previos del paraguas conservan su QA2 aprobado. El estado `needs-work` permanece para la decisión de QA3/autorizado; no se publicó comentario.
- **#1652 — sigue `needs-work`.** #1385 y #1765 son fixes hijos acotados; falta el contrato común tabular y su batería multi-formato.
- **#2092 — fix local implementado y QA1/QA2 aprobado.** El contador falla cerrado si el documento fuente carece de compañía o no coincide con la de la tarea; prueba dirigida: 8 passed. Black, Ruff, Flake8, pydocstyle y complexipy pasaron; mypy no pudo iniciar por dependencia `pathspec` rota y Pylint reportó advertencias previas del módulo. Sin commit ni cambios GitHub.
- **#1926 — regresión de permisos implementada y QA1/QA2 aprobada.** UOM global real: usuario con acceso sin consulta recibe 403 en listado/detalle; lector autorizado recibe 200 y contenido en ambas rutas. Prueba dirigida: 3 passed. Sin cambio de etiqueta.
- **#2060/#2059 — predicado del badge unificado con la bandeja y QA1/QA2 aprobada.** Preselección por compañías activas explícitamente asignadas (o entidades habilitadas para admin), independiente del permiso de Accounting; filtro final shared `can_approve`/reviews. Pruebas dirigidas: 4 del contador y 8 de colaboración, 12 passed. Riesgo no bloqueante: costo crece con pendientes en las compañías del usuario.

## Cierre del árbol de trabajo (2026-11-21)

- **#1652 — contrato tabular común committed en `ef0cd81d`.** `TabularBook` normaliza encabezados/celdas y BOM; los cuatro lectores comparten la representación; `tests/imports/test_readers_contract.py` construye archivos reales CSV/XLS/XLSX/ODS. Quedan fuera de este commit los consumidores paralelos, las fechas tipadas XLS con `datemode` y el límite previo a materializar XLSX.
- **#1346 — committed en `d294d139`.** Las columnas fuera del esquema se rechazan antes de agrupar y las etiquetas localizadas prevalecen sobre aliases. Regresiones: CSV maestro `document_ref,nombre` sin filas persistidas, plantilla inglesa de comprobantes sin `DUPLICATE_COLUMN`, aliases legacy vigentes. Pruebas dirigidas: `14 passed, 1 skipped`.
- **#2018 — committed en `41e3d615`.** Regla global sin cuenta específica, cuenta fiscal de la compañía en posteo, retención ajena ignorada y eliminación en uso controlada. Traducción inglesa compilada en `.mo`. `tests/test_admin_tax_rule_form.py`: `20 passed`.
- **#1998/#1926 — committed en `2725af0e`.** Regresiones HTTP de privacidad de confirmaciones y de lectura UOM por permiso; conciliación aislada por compañía. `42 passed` en la selección de alcance.
- **#2059/#2060 — committed en `30859cd2`; #2092 — committed en `8885d843`.** Predicado único badge/bandeja y tarea sin compañía oculta en bandeja y contador.
- **Estado:** commits locales sin push, sin cierre de issues y sin cambios de etiqueta. Siguiente paso: QA1 → QA2 sobre el lote. `mypy` sigue sin iniciar por `pathspec.patterns.gitignore` ausente; Black, Ruff, Flake8, pydocstyle y complexipy pasan en los archivos tocados.

## Cola de implementación y revisión

### #1649 — alcance de compañía/ACL por endpoint y payload

- Agregar matriz `tests/test_company_scope_matrix.py` con usuarios de dos compañías y un escenario por endpoint/doctype.
- Corregir #1700 (revocación de alcance) y #1705 (`parent_id` global); auditar catálogos contables y `query_tools` sin filtro.
- Reconciliar los hijos en `needs-work` y ejecutar QA1 → QA2 integral.

### #1652 — contrato tabular común de importación

- Mantener el paraguas `needs-work`: la ADR aprobó validación estricta, rechazo de esquemas/contenido desconocido y límites de recursos.
- Implementar `TabularBook` en `imports/readers/`, migrar los seis lectores y aplicar límites antes de materializar/expandir filas.
- Añadir `tests/imports/test_readers_contract.py` con fixtures equivalentes CSV/XLS/XLSX/ODS y verificar los hijos operativos.

### #1653 — atomicidad e idempotencia en read-then-post

- Crear `tests/test_concurrent_uniqueness.py` con escenarios reales SQLite/PostgreSQL.
- Completar el patrón de bloqueo, transición condicional e idempotencia para caja chica, revaluación y AR/AP; falta `with_for_update` en `cancel_petty_cash_expense`.
- Documentar el contrato por motor y la composición transaccional. Cada cambio debe probar rollback, repetición y carrera realista.

### #1689 — sobreasignación concurrente de factura

- Sustituir la prueba no determinista por dos sesiones sincronizadas: pausar T1 tras `_allocated_invoice_qty()` y antes del insert, ejecutar T2 y demostrar que la suma no supera la cantidad facturada.
- Verificar que retirar `_lock_invoice_items()` y el lock documental hace fallar la regresión; ejecutar en PostgreSQL Tier 1 y documentar SQLite.

### #1706 — evidencia append-only e inmutable

- Resolver las decisiones de contrato pendientes de #759 (adjuntos, snapshots y transiciones derivadas).
- Completar matriz Modelo × UPDATE/DELETE para ORM/Core/SQL textual en Desktop y Cloud; revisar brechas en StockEntry, tax summary, ExternalCounterAuditLog y purga física.
- Integrar PR #1660 solo con cobertura verde y doble QA.

### #1710 — ciclo de vida de credenciales y mensajería

- Conciliar el paraguas con sus hijos; cerrar trabajo de #1443, #1354 y #1442 y los siete hijos operativos.
- Comprobar revocación JWT, fail-closed ante SMTP ausente e idempotencia; QA1 → QA2 sobre el contrato completo.

### #1767 y #1771 — operabilidad mínima

- #1767: bloquear admins activos en orden determinista antes de la fila objetivo; rollback y error de dominio ante deadlock; cubrir concurrencia PostgreSQL y endpoints autenticados de toggle, clasificación y roles.
- #1771: regresión HTTP Desktop al eliminar la única entidad; conservar `enabled=True` si se inactiva; traducir al inglés las dos cadenas de rechazo y probar que el guard precede cualquier borrado.

### #1813, #1820 — O2C

- #1813: mover el requisito 3-way de Nota de Entrega a servicio compartido para envío directo y ApprovalEngine; evaluar `require_sales_order=False` conforme a criterios del issue y cubrir rechazo sin entrega.
- #1820: regresión de aprobación con órdenes A/B del mismo ítem/bodega; cancelar A cerrada/liberada no debe modificar la reserva vigente de B.

### #1864, #1881 — inventario

- #1864: validar signo de líneas dinámicas según propósito antes de flush y traducir `IntegrityError` a error de validación con rollback; cubrir valores negativos y cero permitido por HTTP.
- #1881: intercalación determinista de dos sesiones para valuación, demostrando que cada lock es necesario; ejecutar PostgreSQL Tier 1 y valorar `populate_existing=True`.

### #1937, #1957, #2012 — reportes, adjuntos y administración

- #1937: exportar PDF completo con más filas que `page_size` mediante ruta real y afirmar 102/102.
- #1957: cubrir fallo en segundo commit durante reemplazo de imagen, cero vínculos/archivos huérfanos y preservación de `Item.image_path`.
- #2012: restaurar pruebas de hidratación de matching de compras/ventas; GET existente y POST sin cambios no deben resetear la política.

### #2045, #2098 — O2C/S2P

- #2045: verificar ausencia de `from_order` residual en hidden/`initialHeader`/`transaction_config`; cubrir alta ordinaria desde request/quotation con compañía ajena.
- #2098: carrera de dos sesiones sincronizadas sobre una OC; la segunda recepción debe esperar y rechazar o limitar a saldo disponible; centralizar lock dentro del validador para vínculos por DocumentRelation.

### #2131 — validación de salida/plantillas

- Corregir hallazgos #3–#6 de `feedback.md` original: tipo de recurso en `validation.py`, conversión de fecha en snippets, unicidad atómica compuesta y tratamiento de `company_code=NULL`.
- Añadir regresiones por hallazgo, incluido bypass Jinja, y confirmar #1/#2 con el commit anotado en el issue. QA1 → QA2 por hallazgo.

### #2140 — comparativos de solicitudes

- El residual QA3 de cierre manual compartido con #1432 ya tiene fix QA1/QA2. Mantener #2140 pendiente de revisión propia del umbrella y demás criterios que el responsable juzgue dentro de su alcance.

### #2209 — sanitización/validación de salidas y recursos

- Completar #2131 y la revisión QA2 de #1923; verificar #1344, #1563 y #1664 con regresión vigente en HEAD, no eliminada en cambios posteriores.

## Observaciones de seguimiento recuperadas

- #759: completar traducciones de ocho cadenas de evidencia y consolidar inventario de modelos; `database/economic_policy.py` no existe en HEAD.
- #925: restaurar parametrización `[False, 0]` de reactivación ORM de GL/ARAP.
- #1118: probar explícitamente una fila `docstatus=2` además de estados 0/1.
- #1243: documentar el comportamiento fail-closed si cambia luego la moneda del libro.
- #1765: evaluar normalización de excepciones de openpyxl/xlrd/odf para archivos corruptos XLS/ODS.
- #1831: confirmar convención de signo de `gain_loss` y considerar validador común con `document_flow/payment.py`.

## Deuda transversal de traducciones

Verificar en `messages.po` y compilar `.mo` las cadenas nuevas marcadas con `_()` anotadas en la revisión anterior: validadores landed cost, inventario, plantillas de validación externa, Nota de Entrega 3-way, reposición autorizada y las ocho cadenas de #759.


## Feedback QA local — brechas verificadas en HEAD `45e38f2b`

No se publicaron estos hallazgos en GitHub ni se cambiaron etiquetas/estados. Las revisiones son estáticas.

### #1652 — contrato tabular

- Unificar también los consumidores paralelos activos documentados en comentarios: `api/line_import.py`, `contabilidad/budget_import_service.py` y `contabilidad/exchange_rate_import_service.py`; el fix actual solo conecta `ImportService` con los cuatro readers comunes y no limita la expansión anterior a `list(worksheet.iter_rows())` en line-import.
- Corregir y probar fechas tipadas XLS: `XLSReader` usa `cell_value()` sin `cell_type`/`datemode`; la fixture actual pone fecha XLS como texto y oculta el serial Excel.
- Hacer que el control de ancho/celdas se ejecute antes de materializar cada fila XLSX (hoy `values = list(row)` precede a `budget.consume_row()`) y cubrir ancho/fila excedidos, ODS repetido y los lectores paralelos. El fixture multi-formato de una fila no acredita el límite previo a expansión.
- Resolver el alias `reference` del `JournalEntryAdapter`: la traducción inglesa ya lo usa para el campo distinto `referencia`, pero el nuevo alias lo redirige a `document_ref`; ambas columnas colisionan y la plantilla inglesa válida se rechaza como duplicada. QA2 confirma este bloqueo.

### #998 — alias documentales y ACL

- El código de subtipo/permiso está presente, pero el último QA3 pidió regresiones HTTP para `email-info` y adjuntos con alias; los cinco tests actuales solo ejercitan `recalculate-status`.
- Añadir casos de alias de venta y compra, acceso propio permitido, compañía ajena 403, subtipo incorrecto 404, y confirmar que no se devuelve correo/metadatos ni se resuelve/abre un adjunto cuando se deniega.

### #1021 — setup

- El guard de admin y el sellado se ven en el código, pero falta `tests/test_setup_access.py` o equivalente. Las pruebas de finalización actuales solo usan admin.
- Restaurar regresión HTTP con usuario autenticado sin rol admin: GET y POST `/setup/` deben responder 403 y dejar sin cambios configuración global y compañías.

### #1019 — ACL de document-flow

- Los guards actuales de destino, líneas y cierre están en código, pero falta una prueba de endpoint con usuario autenticado multiempresa (el archivo previo `tests/test_document_flow_acl.py` ya no existe).
- Cubrir destino ajeno, línea fuente ajena con cabecera propia y cierre de documento ajeno; verificar 403 y cero creación/mutación. Ya existe un test HTTP de `close-line` (400 ante fila de otro documento), pero debe afirmar también que no se mutó saldo/evidencia. Los tests de servicio, lectura, subtipo o entrada malformada no acreditan los otros guards HTTP señalados por QA3.

### #1338 — bypass global de compañías inactivas

- Se conserva el fix query-tools, pero `decorators.exige_acceso_compania()` todavía retorna cuando `permisos.administrador` es verdadero antes de comprobar `permisos.tiene_acceso_compania(company)` (`decorators.py:117-120`). El último QA3 reprodujo que un admin pasa con `Entity.enabled=False`.
- Corregir el guard para que el privilegio admin no habilite una compañía desactivada y agregar regresión con admin, compañía inactiva y rutas/helpers consumidores. La cobertura actual de `test_query_tools_company_enabled.py` solo verifica query-tools y no protege este decorador.

### #1181 — vínculo de proveedor inactivo

- `CompanyParty.is_active` existe, pero `_proveedor_predeterminado_visible()` no lo filtra; la regresión actual deja ambos vínculos activos por default. Un vínculo inactivo en compañía autorizada sigue mostrando el proveedor.
- Añadir `CompanyParty.is_active.is_(True)` y una prueba de detalle con vínculo inactivo autorizado (debe ocultar el nombre), conservando control positivo activo propio y negativo activo solo ajeno.

### #1301 — recurso global sin alcance de compañía

- La decisión vigente se refleja en el guard: imágenes globales, lectura `inventory.consultar`, mutación `inventory.editar`, sin compañía específica.
- QA3 dejó pendiente probar un usuario con permiso de módulo y ninguna fila `UserCompanyAccess`. El fixture actual asigna compañía a los tres usuarios; el test editor usa POST sin archivo y solo comprueba `!=403`.
- Añadir control sin grants: lectura autorizada (o 404 por archivo ausente), y carga/borrado reales autorizados; mantener rechazos de roles con permisos insuficientes.

### #1332 — alcance de lectura de líneas para flujos de inventario

- La rama de Compra está cubierta: `purchase_order` admite módulos `purchases`/`inventory`, y hay pruebas de líneas pendientes y POST de recepción con usuario solo de Inventario.
- La rama Orden de Venta → Nota de Entrega no está implementada: `sales_order` solo resuelve al módulo `sales`; el selector también oculta esa fuente a usuario solo de Inventario. Las pruebas de `#1332` no cubren ese caso.
- Existe una contradicción funcional explícita con `#1515`: su decisión QA3 aprobada prohíbe exponer documentos fuente de módulos sin permiso y la prueba `test_source_picker_hides_sales_order_from_inventory_only_user` fija ese resultado. El comentario QA3 más reciente de `#1332` pide precisamente resolver ese conflicto con el responsable.
- No inferir una regla de negocio para resolverlo. Mantener #1332 sin aprobación hasta que el responsable decida si Inventario puede leer la Orden de Venta fuente de una entrega y se alineen selector, detalle/líneas y cobertura con #1515.

### #1354 — revocación de credenciales de usuario inactivo

- En el árbol actual, el guard JWT comprueba `User.active`, `User.token` y `auth_version`; el loader de sesión carga solo usuarios activos y compara también la versión de sesión.
- `tests/test_token_requerido.py` cubre llamada API autenticada antes/después de desactivar, cambio por admin y por formulario de edición, invalidación de cookie de navegador y rechazo de token tras reactivación. No hallé brecha estática frente al comentario de sesión.

### #1357 — blueprint admin sin rutas

- `admin/services.py` ya no declara un `Blueprint`; la búsqueda de referencias no encuentra `admin.services.admin` ni importación del blueprint desde ese servicio. `admin/routes.py` conserva el blueprint operativo y sus funciones importadas desde servicios.
- La evidencia de eliminación es una búsqueda estática de referencias en `cacao_accounting/` y `tests/`; no encontré consumidor residual.

### #1433 — colisiones con claves históricas nulas

- El fix compara correctamente `supplier_invoice_key` para filas con clave ya poblada, pero el comentario QA3 vigente señala grupos históricos duplicados dejados intencionalmente con `supplier_invoice_key=NULL` por `_ensure_purchase_invoice_supplier_key()`.
- El precheck actual consulta solo la clave normalizada, por lo que permite un nuevo alta que coincide con el número normalizado de esas filas históricas activas. Falta cubrir el fallback de clave nula sin reescribir evidencia heredada y probar rechazo antes del flush.

### #2060 — alcance de la insignia de aprobaciones

- El filtro de compañía y los casos Alpha/sin compañías/admin están presentes. El comentario QA3 más reciente identifica otro desajuste: `pending_approval_count()` cuenta todas las solicitudes de la compañía, mientras `/admin/me/pending-approvals` solo incluye las que `ApprovalEngine.can_approve()` autoriza para el usuario.
- Falta una regresión con dos solicitudes en la misma compañía (una aprobable y otra no) y una definición explícita si el badge debe seguir las filas visibles de la lista. No aprobar mientras ese criterio no esté satisfecho o resuelto por el responsable.

### #1987 — asociación append-only de gastos de caja chica

- QA3 rechazó porque el test no estaba visible; la verificación actual de `origin/estabilizacion` y lectura directa del archivo GitHub confirman que `tests/test_petty_cash_replenishment_append_only_link.py` está presente junto a `5f0e03ab`.
- QA1 y QA2 confirman la cobertura funcional de asociación, conciliación, rollback/reintento, reserva concurrente, compatibilidad legacy y guards ORM/Core/SQL.
- Persiste un bloqueo de esquema: `PettyCashReplenishmentExpense` agrega una tabla nueva, pero el baseline Alembic es no-op, `create_app()` no la crea, y `db init`/`inicia_base_de_datos()` retornan antes de `create_all()` cuando ya existe un usuario. El servicio falla al consultar o insertar en una base existente sin esa tabla.
- El contrato aprobado de #1898 exige que todo cambio de esquema tenga migración Alembic efectiva para bases existentes; #2248 requiere validar upgrades sobre bases existentes SQLite y PostgreSQL. No hay limitación aceptada documentada para este issue. Rechazar hasta que el cambio se integre con el contrato de migraciones.

### #2078 — escritura sobre cadena de auditoría sin cabeza terminal

- QA3 indicó que la prueba faltaba, pero `tests/test_audit_chain_fail_closed.py` está en HEAD y en `origin/estabilizacion`; la lectura directa de la ruta GitHub también la devuelve.
- QA1 y QA2 aprueban el criterio del issue: ante ciclo con puntero viejo o nulo, los paths ORM y Core fallan cerrado y la regresión confirma que no se altera la evidencia ni el puntero.
- Límite fuera del caso reportado: una topología corrupta desconectada que coexista con una cabeza válida puede no detectarse al anexar. Se documenta como hardening futuro, no como bloqueo de este issue.

### #1683 — columnas muertas de BaseTransaccion

- El modelo y `MUTABLE_STATE` ya no exponen las cinco columnas legacy; la prueba de contrato cubre ese resultado para un esquema nuevo.
- Falta la migración Alembic para quitar columnas de bases existentes. La decisión posterior de #1898/#2248 establece Alembic como mecanismo único de evolución y exige upgrades efectivos de bases existentes; la excepción pre-alpha para retirar código legacy no cubre esta omisión de esquema.

### #1684 — aliases ORM de compatibilidad

- La limpieza de aliases originalmente listados y la ruta `Modules` están implementadas, pero el comentario `6668277830` reportó tres synonyms adicionales sin consumidores en `ARAPLedgerEntry`.
- Siguen declarados `amount`, `signed_amount` y `transaction_currency` (`database/__init__.py:3753-3756`); no aparecen callers productivos, y `tests/test_database_canonical_surface.py` no afirma su ausencia. Retirar los tres y extender la prueba contractual.

### #1697 — unicidad/atomicidad de configuración

- `set_config_value()` usa upsert nativo y el helper de unicidad está presente, pero `messaging/email.py::_get_or_create_password_salt()` conserva SELECT → sal aleatoria → INSERT/flush directo. Dos primeras llamadas concurrentes pueden colisionar en el índice único y el perdedor no relee la sal persistida; la prueba de configuración no cubre ese caso.
- QA3 `7029213721`, QA1 y QA2 coinciden en la regresión SMTP pendiente: la inicialización debe ser atómica y ambos callers deben obtener la misma sal persistida sin error.
- Además `_ensure_cacao_config_key_unique()` se invoca desde `create_app()` y cambia el esquema/deduplica filas en el arranque. La decisión posterior de #1898/#2248 establece Alembic como autoridad única, prohíbe alterar el esquema al ejecutar `serve` y exige migraciones efectivas para existentes. El baseline es no-op y no hay migración específica; mover el cambio de unicidad al contrato Alembic y retirar la ruta de mutación del arranque.

### #1174 — validación de factores UOM no finitos

- QA1 y QA2 rechazan de forma independiente en HEAD `45e38f2b`. `parse_item_uom_rows()` y `validate_item_uom_rows()` rechazan NaN/±Infinity en el servicio, pero el preparador `_item_uom_rows_for_template()` también parsea y puede lanzar `InventoryServiceError` sin capturar.
- En alta, `/item/new` llama `_item_uom_rows_for_template(request.form)` antes del `try` que captura `InventoryServiceError`/`ValueError` (`cacao_accounting/inventario/routes.py:429-445`). En edición, `/item/<item_id>/edit` llama el mismo helper antes de `_process_item_edit()` (`routes.py:514-518`). Por eso factores no finitos pueden escapar como error HTTP 500 antes del manejo de validación.
- `tests/test_inventory_uom_factor_validation.py` cubre parser y servicio, pero no las respuestas HTTP de alta/edición ni la ausencia de persistencia mediante esas rutas. Corregir la propagación y agregar pruebas funcionales HTTP de ambas rutas con NaN e Infinity; verificar que el usuario vuelve al formulario con error controlado y que no se crea/actualiza el artículo ni sus conversiones.
- QA2 señala además normalizar `decimal.Overflow` de operaciones con operandos finitos extremos y agregar una regresión discriminante, si esos rangos son aceptados por el contrato. Confirmar ese alcance al implementar; no desplaza el bloqueo HTTP observado por ambos QA.
- El factor finito `1e-10`, cuantizado a cero por `Numeric(20,9)`, es un problema distinto de precisión/representabilidad y permanece bajo #1650; ambos QA excluyen ese comentario del rechazo específico de #1174.

### #1183 — cierre de revisión estática local

- QA1 y QA2 aprueban la corrección en HEAD `45e38f2b`: la ruta ya no fuerza guardado en cada POST, valida compañías antes de persistir y devuelve error controlado ante código duplicado.
- Pruebas HTTP ya existentes cubren campos vacíos, alta válida con configuración y duplicado sin alterar la fila original. No se ejecutaron pruebas durante la revisión estática.
- Mejora no bloqueante sugerida por QA1: agregar un caso HTTP con usuario no-admin y compañía ajena; la ruta llama el guard de autorización antes de escribir. No cambiar etiqueta en GitHub.

### #1184 — QA1/QA2 aprueban la validación de altas

- En HEAD `45e38f2b`, ambas rutas persisten solo con `validate_on_submit()`. Los POST con unidad vacía o presupuesto `abc` no llegan al guardado; presupuesto válido `123.45` se almacena exacto.
- Pruebas locales existentes cubren esos rechazos y altas válidas. Pruebas existentes de jerarquía rechazan padres de otra compañía para unidades y proyectos. QA1/QA2 no hallaron defectos bloqueantes.
- No se ejecutaron pruebas/linters durante esta revisión estática. Dejar intacta la etiqueta de GitHub.

### #1266 — QA1/QA2 rechazan por garantía de base de datos incompleta

- El lock de fila y el rollback GL/subledger están implementados en el servicio. Hay prueba concurrente de SQLite y fault injection que comprueba rollback integral tras fallar el INSERT del gasto.
- Falta el requisito de aceptación explícito de exclusividad persistida: `PettyCashExpense.voucher_id` no tiene constraint unique (solo índice nullable), así que un consumidor que omita el servicio puede enlazar dos gastos al mismo vale. No hay migración Alembic efectiva para añadir esa garantía a bases existentes.
- Falta demostrar la carrera del mismo flujo en PostgreSQL Tier 1; el test actual es SQLite. QA1 y QA2 rechazan por estas brechas. No ejecutar pruebas desde QA ni cambiar etiquetas.

### #2076 — QA1/QA2 rechazan por escenario de concurrencia incompleto

- El código bloquea y revalida el estado al rechazar. La única regresión dedicada hace dos rechazos secuenciales en una sesión; no ejerce aprobación frente a rechazo concurrentes en dos transacciones ni verifica side effects del perdedor.
- Se mantiene el hallazgo QA3 vigente. Debe probarse la carrera en PostgreSQL y asegurar un solo terminal/evidencia sin que el flujo perdedor reabra o vuelva a aprobar el documento.
- QA2 observa que `approve()` puede no hallar solicitud pendiente tras un rechazo y llamar a `request_approval()`, que ignora solicitudes rechazadas al buscar existentes. Definir/codificar el comportamiento de esa carrera antes de aprobar.
- No se ejecutaron pruebas/linters; no tocar etiquetas de GitHub.

### #2065 — QA1/QA2 confirman el bloqueo de QA3

- El código de plantilla muestra correctamente las etiquetas localizadas para cada flag y los tests renderizan Jinja real con objetos transitorios, sin insertar en catálogos compartidos.
- La prueba solo exige que aparezcan ambas etiquetas en la tabla. No vincula cada fila/celda con su flag: si se invierte `is_active` o una rama de `PriceList`, ambas palabras aún aparecen y la regresión pasa.
- Fortalecer asserts por fila y columna manteniendo aislamiento/render real. QA1/QA2 rechazan; etiqueta intacta.

### #2067 — QA1/QA2 registran brecha de matriz de cobertura

- El mapeo de las plantillas es correcto y las regresiones usan render real sin persistir datos.
- Los tests cubren compra-precio percentage, compra-cantidad absolute y venta-precio absolute; faltan las otras ramas por campo, en particular percentage en ventas.
- Fortalecer render para probar ambos tipos y etiqueta+importe por campo de compra precio, compra cantidad y venta precio. La issue sigue cerrada/fixed en GitHub; QA local no modifica etiqueta ni cierre.

### #1071 — QA1/QA2 confirman brecha contractual

- Se retiró correctamente `document_flow_tree` y el parámetro `legacy` no altera la ruta actual; el endpoint llama el builder recursivo canónico.
- Las pruebas presentes cubren ACL/nodos y el builder, pero no el GET de `/api/document-flow/tree` comparado con el mismo GET más `?legacy=1`. Falta fijar que no reaparece un esquema alterno (o definir que el parámetro se rechaza).
- QA1/QA2 rechazan hasta esa regresión HTTP. Etiqueta `needs-work` intacta.

### #2098 — QA1/QA2 rechazan: falta evidencia de la carrera real

- Los locks están presentes en submit directo y aprobación: se bloquea OC/líneas antes de consultar consumo.
- La prueba 6+6 crea y confirma ambas relaciones antes de validar secuencialmente. Demuestra rechazo de exceso, pero pasa igual sin los locks; no reproduce TOCTOU.
- Las otras regresiones comprueban invocación del helper, no exclusión/efecto. Agregar interleaving PostgreSQL de dos aprobaciones contra OC de 10 y probar que solo una gana, total aprobado ≤10; verificar que la prueba falle al quitar locks. No cambiar etiqueta.

### #1301 — QA1/QA2 rechazan: regresión no cubre recurso global

- Código del guard coincide con la decisión responsable: imagen global; lectura requiere consultar, mutaciones requieren editar; sin requisito de acceso a compañía.
- El fixture asigna `UserCompanyAccess` a todos los roles. Falta cubrir un viewer y editor con permiso de módulo y cero compañías asignadas, incluyendo lectura y mutaciones autorizadas; conservar los casos que rechazan permisos insuficientes.
- QA1/QA2 confirman QA3; no cambiar etiqueta.

### #2120 — QA1 rechaza por guarda de período fail-open

- La cobertura nueva sí cubre T2→T1, corridas cerradas y ejercicios distintos; QA2 aprueba esa parte.
- QA1 verificó que `_period_is_open_for_run()` convierte `IdentifierConfigurationError` en `True`, aunque el error representa período inexistente o ambiguo. El caller después usa `void(..., _period_locked=True)`, omitiendo la guarda regular de período. Puede generar reversos GL sin un período válido/resuelto.
- El check tampoco bloquea ni revalida el período abierto frente a un cierre concurrente. Falta manejar ambos casos con una guarda fail-closed/lock transaccional y regresiones. Sin consenso QA, no aprobar ni cambiar etiqueta.
### #1299 — QA1/QA2 rechazan: retirada incompleta de moneda obsoleta

- Se retiraron las ocho preferencias del modelo `CompanyParty` y de los parámetros de escritura. El criterio de retirada pre-alpha está aprobado en el historial (#2248).
- Sigue `resolve_party_currency()` y la rama `source="party"` en `document_flow/currency_resolver.py`; su único consumidor, Ventas, pasa un `Party` sin atributos de moneda y además el camino de fuentes Document Flow retorna antes. Los docstrings todavía prometen esa precedencia inexistente.
- `tests/test_party_company_settings_validation.py` aún asigna y comprueba `default_currency` y campos `default_bank_*` ya retirados. Son asignaciones Python no mapeadas que se conservan en la misma instancia de sesión; no prueban persistencia y dan una señal falsa sobre el contrato del modelo.
- Retirar la helper/precedencia muerta y actualizar los docstrings al contrato real. Sustituir los asserts heredados por pruebas funcionales de la precedencia activa: moneda explícita de origen, elección del usuario y moneda funcional de compañía. Conservar pruebas de los campos aún válidos por tercero.
- QA1 y QA2 independientes rechazan. El hallazgo coincide con el retorno QA3 #7029690077. GitHub sigue en `needs-work`; no se cambió etiqueta ni se publicó comentario.
### #1283 — retiro correcto, falta regresión de ausencia

- La búsqueda completa no encuentra `party_account_labels` ni `build_party_code`; `generate_party_code` permanece y tiene callers activos en ventas, compras e importadores.
- `d1649c9a` eliminó los helpers e incluyó ambos nombres en `tests/test_dead_code_inventory.py`; ese archivo fue borrado por `0970476b`, por lo que HEAD no conserva la protección de contrato.
- QA1/QA2 rechazan hasta restablecer un test que compruebe la ausencia de ambos símbolos, manteniendo las pruebas/callers del generador canónico. GitHub sigue intacto.
### #1046 — importador retirado parcialmente

- `import_bank_statement()` y su parser principal ya no están; `ImportService` registra `BankStatementAdapter`, que cuenta con cobertura funcional. `statement_service.py` sigue teniendo consumidores legítimos para matching y autorreconciliación; no retirar el módulo completo.
- Persisten `_decimal_value()` y `_parse_date()` sin callers productivos. `tests/test_import_non_finite_validation.py` todavía importa `_decimal_value()` y prueba el parser retirado, duplicando el contrato del adaptador.
- El menú sigue apuntando a `/bank-statement/import`, que solo redirige al asistente común; `extracto_importar.html` sigue en árbol sin render caller. A la luz del criterio pre-alpha aprobado #2248, el menú debe ir directo a `imports.new` y el shim/plantilla/helpers/test legacy retirarse.
- QA1/QA2 rechazan hasta completar esa limpieza y conservar los servicios activos de conciliación. No se cambió estado ni etiqueta en GitHub.
### #1031 — validación y recovery corregidos; preview sigue fallando

- `validate()` convierte excepciones del lector en estado 7 con error `SYSTEM_ERROR`; `recover_crashed_batches()` contempla `started_at IS NULL`. Esos criterios se mantienen cubiertos por `test_import_corrupt_reader_recovery.py`.
- `ImportService.preview()` todavía captura únicamente `ImportReadLimitError`; `KeyError`, `BadZipFile` u otros errores de lector se propagan. `imports.routes.detail()` intenta generar preview para todo estado `>=1`, también el lote inválido que ya tiene un error persistido, y puede terminar HTTP 500 en vez de mostrar ese error.
- QA1/QA2 confirman el QA3 `7030187515`. Falta manejar el error del lector en preview y una regresión HTTP de detalle para XLSX corrupto. No modificar etiquetas.
### #1032 — carrera de cancelación en la ventana terminal

- La cancelación dentro del bucle escribe estado 8 y el finalizador preserva ese estado; ese caso no cubre la carrera más reciente.
- `cancel()` solo guarda `cancel_requested=True`. Si la solicitud llega después de la última comprobación, o un lote vacío no ejecuta ninguna comprobación, `_finalize_execution()` actualiza contadores y `completed_at` pero retorna dejando `import_status=4` y `started_at` poblado. La UI seguirá mostrando el lote como procesando hasta recovery.
- El test histórico `test_import_batch_cancellation.py` no está en HEAD, y no encontré prueba actual de cancelación de importación.
- QA1/QA2 confirman QA3; exigir transición terminal a 8 y regresiones para solicitud posterior al último check y lote vacío. No se cambió etiqueta.
### #1030 — parser bancario aún acepta importes mal formados

- El criterio original de simetría ya rechaza 1.000 y 1,000, y preserva las formas explícitas inequívocas.
- Sigue el borde del comentario QA3 6886283181: un campo opcional compuesto solo de espacios se transforma en vacío después de la comprobación de ausencia y llega a coerce_decimal, invalidando una fila que tiene monto válido en el otro lado.
- Los separadores mixtos se eliminan globalmente sin validar agrupación: 12,34.56 se interpreta como 1234.56; 1.23,456 como 123.456. Esto altera silenciosamente el valor.
- QA1/QA2 rechazan. La regresión histórica test_bank_statement_import.py no está en HEAD; las pruebas presentes cubren precisión y no finitos, no estos casos. El diff local actual solo agrega alias de columna y no corrige el parser.
### #1055 — normalización XLS incompleta en el árbol actual

- El arreglo de overflow de seriales está presente, pero el último QA3 7029866045 identifica que XLSReader descarta wb.datemode y parse_import_date fija la época 1899-12-30; libros XLS con sistema 1904 quedan desplazados 1462 días.
- El cambio local del lector devuelve celdas crudas en TabularBook y este normaliza números a texto. El parseador posterior acepta serial numérico, pero cadenas se interpretan como ISO; el serial real XLS puede fallar además de perder la época.
- QA1/QA2 rechazan. La cobertura de fechas pasa serial numérico directo al helper (1900), y el workbook XLS sintético usa fecha textual; falta fixture XLS con fecha serial real en sistemas 1900 y 1904 y verificar el valor que entra a validación de período.
### #1057 — proveedor de orden de compra no validado

- PurchaseOrderAdapter.validate_document() valida fecha, bodega, cantidad y tasa, pero no consulta la columna proveedor.
- build_document() busca por Party.id e is_supplier=True, pero omite is_active; si no encuentra tercero conserva supplier_id recibido y supplier_name=None. La validación de persistencia no vuelve a comprobarlo.
- QA1/QA2 rechazan. Faltan pruebas para cliente sin rol proveedor, proveedor inactivo, ID inexistente y control positivo; los fallos deben ser errores de fila/documento antes de ejecutar, sin PO persistida.
### #1059 — contrato fiscal aprobado, implementación ausente

- El responsable ya aprobó en comentario 6716234735: impuesto es el importe observado por línea; calcular desde plantilla aplicable compañía/proveedor, rechazar sin plantilla o con diferencia; si no se informa observado, calcular desde plantilla; persistir resultado fiscal de la orden.
- El adaptador aún incluye la columna impuesto pero no la lee en validate_document() ni build_document(); suma qty×precio y deja grand_total igual al subtotal. Aunque PurchaseOrder tiene tax_total, el adaptador no lo asigna y PurchaseOrderItem no guarda impuesto por línea/plantilla.
- QA1/QA2 rechazan. Falta conectar contrato completo y regresiones de observado coincidente/diferente, sin plantilla, omitido con plantilla y persistencia.

### #1060 — importaciones no validan artículo/UOM habilitados

- `TransactionDocumentAdapter._validate_document_row()` (`cacao_accounting/imports/adapters/transaction_documents.py:139-162`) no verifica `Item.is_active` ni el rol de compra/venta configurado por `entity_type`; la carencia alcanza adaptadores transaccionales y `PurchaseOrderAdapter`.
- `api/line_import.py:665-685` solo verifica existencia de artículo y UOM. No bloquea artículo inactivo, rol incorrecto o UOM inactiva.
- Factura de compra vigente sí valida actividad/rol del artículo (`compras/services.py:1216-1239`), pero puede usar UOM elegida o predeterminada sin guard de actividad; conversión compartida (`inventario/service.py:253-276,311`) tampoco revisa `UOM.is_active`.
- Falta cobertura funcional para artículos inactivos/rol equivocado por flujo, UOM inactiva explícita y heredada, rechazo sin persistencia y controles positivos con referencias activas.
- QA1/QA2 rechazan en HEAD `45e38f2b`. No se ejecutaron pruebas/linters durante QA estático; GitHub y sus etiquetas permanecen intactos.

### #1062 — recuperación no idempotente tras fallo parcial

- El contrato del comentario 6712445750 requiere preservar archivo/progreso confirmado, checkpoint por documento, reanudar solo pendientes y mostrar errores guardados sin releer archivo ilegible.
- `_process_document()` confirma el documento antes de que `_update_batch_progress()` guarde contadores; no hay checkpoint por documento en `ImportBatch`. La caída entre commits permite persistencia sin progreso medible y reprocesar el archivo podría duplicar evidencia.
- Recovery cambia a estado 7 pero no permite reanudar; el servicio solo ejecuta estado 3 con contadores vacíos. La pantalla de estado 7 no ofrece acciones.
- `detail()` vuelve a parsear la fuente y `preview()` solo captura límites de lectura; archivo corrupto puede producir 500 ocultando el error persistido. El rollback de `_handle_execution_error()` sí está corregido, pero no resuelve esta causa.
- Faltan regresiones de fallo entre commit y checkpoint, reanudación/repetición sin duplicados, fallo previo al primer commit y acceso HTTP a ficha con fuente corrupta. QA1/QA2 rechazan en HEAD `45e38f2b`; GitHub y etiquetas intactos.

### #1063 — padres de cuenta sin validación en importación

- `ChartOfAccountsAdapter` hereda `validate_document()` no-op y asigna `padre` directamente a `Accounts.parent`; no resuelve referencia ni valida entidad, existencia, actividad/habilitación o grupo.
- El valor opcional vacío queda `""`, aunque manual y catalog loader normalizan raíz a `None`. `Accounts.parent` no tiene FK.
- No hay resolución anticipada de padres incluidos en el mismo archivo ni prevención de ciclo en el adaptador.
- Tests actuales solo verifican campos requeridos y no cubren jerarquías. Añadir padre vacío/inexistente/inactivo/no-grupo/otra compañía/ciclo, padre intraarchivo anterior y posterior y éxito válido; comprobar cero persistencia en rechazos.
- QA1/QA2 rechazan en HEAD `45e38f2b`; GitHub y etiquetas `needs-work` intactos.

### #1087 — precisión no canónica en identidad bancaria

- Ya se rechazan fracciones con más de cuatro dígitos significativos. Pero `_optional_amount()` retorna Decimal original sin cuantizar; `123.456700` se acepta con escala textual 6 aunque columna `Numeric(20,4)` guarde `123.4567`.
- El listener de identidad calcula SHA de `str(Decimal)` antes de persistir; búsqueda de duplicado y `identity_key` reciben valor no canonicalizado. Falta que un valor normalizado a escala 4 alimente las tres operaciones.
- La prueba existente cubre rechazo >4 y guardado de 4 decimales/ceros finales en SQLite, pero no identity key, reimport equivalente, ni PostgreSQL.
- QA1/QA2 rechazan. Añadir canonicalización y regresiones portables a Tier 1 para rechazo, valor exacto y reimportación de formas numéricamente equivalentes. GitHub/etiquetas intactos.

### #1174 — error HTTP no controlado y factor positivo no representable

- Parser, servicio y conversor ya rechazan NaN/Inf, pero el helper de render llama al parser antes del try de manejo en alta y edición. Un POST con valor no finito puede responder 500; no hay regresión HTTP para ninguna ruta.
- El servicio admite `1e-10`; `Numeric(20,9)` puede persistirlo como cero, dejando conversión inutilizable. No existe guard de escala ni prueba de este caso.
- QA1/QA2 rechazan. Manejar el error antes del render en ambos POST, validar representabilidad de la escala y cubrir respuesta controlada/no persistencia, borde inferior y valor positivo representable. GitHub/etiqueta `needs-work` intactos.

### #1185 — cobertura HTTP insuficiente para decimales inválidos

- `_form_decimal()` ya usa `coerce_decimal()`, y el parser compartido convierte entradas inválidas/no finitas en `ValueError`. Revisé los callers principales: todos muestran/canalizan el error; no encontré bypass de producción.
- Pruebas HTTP actuales solo cubren conciliación bancaria y alta de caja chica. Falta el caso documentado `counted_cash=abc` en alta de conciliación, además de regresiones para edición de caja chica, vale, gasto, edición de conciliación y referencias de pagos con verificación de cero mutación.
- QA1/QA2 rechazan por cobertura insuficiente en HEAD `45e38f2b`; GitHub/etiqueta `needs-work` intactos.

### #1197 — `is_advance` usa conversión truthy

- `JournalEntryAdapter` copia `is_advance` crudo; `_normalize_line()` usa `bool(value)`, que convierte `"false"`, `"0"`, `"no"` y `"off"` en verdadero.
- El worktree tiene un diff que rechaza headers extra, pero no normaliza el booleano solicitado ni corrige el helper compartido. No considerar que soporte una columna `is_advance` sea equivalente a parseo explícito.
- No hay regresiones funcionales del campo. QA1/QA2 rechazan; cubrir booleanos/string permitidas y desconocidos desde import y consumer central. GitHub/etiquetas intactos.

### #1200 — worker todavía puede completar cero filas

- `validate()` y prelectura de `execute()` rechazan tablas vacías y las pruebas cubren esos dos controles.
- `_execute_task()` vuelve a leer la fuente y no repite el guard antes de iterar; una fuente vaciada entre lecturas puede finalizar como completada con cero documentos.
- QA1/QA2 rechazan. Agregar guard y regresión del worker para la carrera entre preflight y segunda lectura; comprobar estado terminal fallido, error accionable y no cero-completado. Revisar `total_rows` obsoleto al revalidar. GitHub/etiquetas intactos.

### #1199 — adaptador de órdenes duplicado no retirado

- La clase activa se registra desde `transaction_documents.py`; el archivo `adapters/purchase_order.py` no tiene callers productivos y sigue consumido por dos tests directos que no prueban el flujo activo.
- No hay diff local que retire el archivo o migre esos tests al consumer registrado.
- El adapter huérfano declara `impuesto` pero no lo persiste. #1059 ya aprobó por separado integración fiscal del adapter activo; sigue pendiente y no debe confundirse con retirar el código duplicado.
- QA1/QA2 rechazan; retirar archivo/tests obsoletos y conservar cobertura real del adapter activo. GitHub/etiquetas intactos.
### #1201 — seriales de fecha XLS se convierten en texto

- `TabularBook` local normaliza `datetime` XLSX a ISO, pero XLS sigue copiando valores sin celda tipo fecha ni `wb.datemode`. Un serial pasa a string y `parse_import_date` solo convierte seriales numéricos; se rechaza.
- La época está fija en 1899-12-30 y no contempla workbook 1904.
- Fixture nueva de XLS usa fecha textual; helper test pasa serial directo y no valida lector→adaptador ni datemode. QA1/QA2 rechazan; añadir XLS nativo 1900/1904 end-to-end y completar conversión. GitHub/etiquetas intactos.
### #1204 — pre-validador omite el límite combinado

- `_validate_payment_reconciliation_amounts()` calcula consumo con tope inferior cero, pero no rechaza `discount + gain_loss >= allocated`.
- El servicio apply sí bloquea suma igual o superior, por lo que la ruta API puede reportar fila válida que apply rechaza, aunque haya saldos suficientes.
- QA1/QA2 rechazan. Añadir pruebas de suma igual, superior y válida con paridad entre prevalidación y aplicación. GitHub/etiquetas intactos.
### #1205 — validación ignora consumo acumulado entre líneas

- Endpoint valida cada fila contra saldos iniciales, sin reservas/acumuladores por pago o documento.
- Apply descuenta `payment_remaining` por línea y rechaza duplicados de clave; dos filas 80 para un saldo 100 pueden superar prevalidación y fallar en aplicación.
- No hay tests HTTP multi-fila con pago/documento compartido. QA1/QA2 rechazan; acumular consumo con reglas compatibles con apply y cubrir saldos, repetición, orden y paridad. GitHub/etiquetas intactos.
### #1206 — endpoint parse-xlsx materializa antes de acotar

- `/api/line-import/parse-xlsx` usa `_xlsx_rows()`, que materializa todas las filas antes de revisar límite de 100 columnas o 500 líneas. El preflight ZIP no limita dimensión XML inflada.
- El `XLSXReader` separado sí limita incrementalmente, pero el endpoint no lo consume. No hay test HTTP para dimensión inflada; pruebas existentes son del lector distinto.
- QA1/QA2 rechazan. Aplicar límites antes/durante iteración en consumer activo y cubrir vía HTTP una hoja pequeña con dimensión inflada. GitHub/etiquetas intactos.

### #1212 — filas duplicadas en conciliación de inventario

- El alta (`inventario/services.py:741-755`) y la edición (`:1058` en adelante) no rechazan combinaciones repetidas de artículo y bodega; la ruta POST tampoco valida duplicados (`inventario/routes.py:910-914`).
- El posting recorre las líneas sin guard (`posting_service.py:3081-3112`); `StockEntryItem` no garantiza unicidad de `(artículo, bodega)` y el formulario permite duplicarlas.
- Añadir validación en creación/edición y defensa al postear evidencia heredada duplicada. Cubrir duplicado exacto y mismo artículo en bodegas diferentes. QA1/QA2 rechazan; no se ejecutaron tests ni se modificó el producto/GitHub.

### #1225 — allowlist de tipo documental de factura de venta

- `_prepare_sales_invoice_creation()` no valida el campo POST; `_build_sales_invoice_from_context()` persiste cualquier valor. El modelo no declara CHECK de tipo.
- La aprobación usa guardas genéricas y `post_sales_invoice()` no valida el subtipo. Un valor desconocido puede aprobarse/contabilizarse como factura regular y desaparecer de listados por tipo.
- Las pruebas existentes ejercitan subtipos conocidos en helpers/filtros, no la creación HTTP ni aprobación de un tipo desconocido. QA1/QA2 rechazan: validar los cuatro tipos permitidos antes de guardar y al aprobar; cubrir POST válido/desconocido y asegurar ausencia de persistencia/GL en el rechazo. Sin cambios locales a producto o GitHub.

### #1262 — movimientos bancarios sin referencia

- El consumidor activo es `BankStatementAdapter`; el importador directo del issue ya no tiene consumidores productivos. El adapter y el guard de DB rechazan las mismas cuentas/fechas/importes con referencia vacía.
- La UNIQUE `identity_key` concatena cuenta, fecha, referencia vacía e importes, por lo que impide dos cargos legítimos indistinguibles en esos campos. El test NULL contra `""` y el de importación repetida afirman este rechazo actual.
- QA1/QA2 rechazan: fecha+importe no bastan como identidad en ausencia de referencia. Rediseñar esa identidad manteniendo idempotencia con una referencia fiable y cubrir aceptación de movimientos legítimos iguales en el importador activo.

### #1263 — límites de tolerancias de matching

- El POST persiste días/importe sin exigir no negatividad ni finitud; `Infinity` puede convertir diferencias arbitrarias en candidatos `exact` y disparar auto conciliación. `abc` provoca HTTP 500.
- La resolución de reglas guardadas tampoco valida el contrato; días negativos se truncan silenciosamente a cero, importe negativo no encuentra candidatos e Infinity amplía sin límite.
- QA1/QA2 rechazan. Validar entradas y reglas heredadas/resueltas, devolver error controlado y probar negativo, NaN, ±Infinity, texto malformado y valores válidos dentro del flujo de matching.

### #1265 — cuenta GL operable en setup de caja chica

- Setup elige la primera cuenta `petty_cash` no agrupadora por código, sin filtrar `active`/`enabled` ni llamar a `_validate_petty_cash_account()`. Puede crear un fondo asociado a cuenta que el posting no acepta.
- Sin cuenta elegible retorna `None`, pero `setup/service.py` ignora ese resultado. El helper que usa el fondo tampoco revisa vigencia al obtener código GL.
- QA1/QA2 rechazan. Aplicar el contrato normal al seleccionar cuenta; hacer observable la ausencia de cuenta utilizable y validar estado al usar una cuenta que pudo desactivarse. Cubrir estas transiciones.

### #1291 — fecha nativa XLS

- XLSX estilizado normaliza a ISO; `XLSReader` no consulta `cell_type` ni `wb.datemode`, deja seriales como texto y el parser aplica época fija 1899-12-30.
- No se valida el sistema 1904; serial 60 puede interpretarse silenciosamente aunque representa la fecha ficticia de Excel. La fixture XLS usa texto y helper tests no cubren reader→adapter.
- QA1/QA2 rechazan. Normalizar según el workbook, preservar fechas tipadas y probar XLS/XLSX nativo con sistemas 1900/1904, serial inválido/ambiguo y consumo real.

### #1292 — cobertura de importes de pronóstico

- La implementación normal aplica `coerce_decimal(positive=True)` en validar, construir y persistir. Pero persistencia directa no vuelve a validar `type`.
- Las pruebas de importe usan siempre `Income` y métodos del adapter; no incluyen archivo CSV/XLSX ni ejecución de ImportService/lote. `NaN` e `Infinity` están cubiertos parcialmente; falta `-Infinity`, Expense y rollback/no persistencia del lote por importe inválido.
- QA1/QA2 rechazan por cobertura del contrato. Cubrir formatos reales, ambos tipos, límites y flujo de rollback con evidencia que no deje entradas parciales.

### #1295 — archivos de importación sin filas

- `validate()` y el primer preflight de `execute()` rechazan tablas vacías; `_execute_task()` relee la ruta sin repetir el guard. Si la fuente queda vacía en esa frontera, procesa cero documentos y puede marcar estado completado.
- El test actual solo cubre CSV con encabezado y ejecución vacía que se detiene antes del worker; no prueba la segunda lectura, archivo 0 bytes, otros formatos ni una fila válida.
- QA1/QA2 rechazan. Corregir la guarda del worker coordinada con #1200 y cubrir estado fallido/NO_DATA_ROWS en relectura vacía, además del contrato de formatos solicitado.

### #1296 — factor UOM finito y representable

- El servicio rechaza no finitos, cero y negativos, y revalida al convertir factores ya almacenados; no encontré adaptador de importación UOM activo.
- Alta y edición parsean las filas para re-render antes de entrar a handlers de errores, así que NaN/Infinity/valor malformado puede responder 500 en vez de re-render controlado sin mutación.
- `Numeric(20,9)` permite que un `1e-10` positivo pase y termine como cero tras persistencia. HTML `step` no reemplaza una guarda server-side portable.
- QA1/QA2 rechazan: cubrir HTTP alta/edición y rollback, casos válidos/inválidos, y límites de representación de la escala persistida.

### #1300 — elegibilidad de cuentas AR/AP

- `_validate_account()` valida compañía, pero permite tipo vacío y no comprueba grupo/estado. El validador de cuentas por defecto y el de consumo GL comparten bypass similares.
- Posting de factura legacy resuelve PartyAccount/default y usa guard de existencia; el guard estricto `_require_company_account` no se usa para AR/AP. Accounting engine también resuelve y solo exige existencia. Una asignación heredada puede apuntar a cuenta de otra compañía o no operable.
- QA1/QA2 rechazan. Exigir tipo receivable/payable explícito, ownership, hoja, active/enabled al configurar y en ambos posting paths; cubrir mappings/defaults heredados y confirmar cero GL al rechazar.

### #1302 — vigencia del proveedor en S2P

- Purchase Order ya usa `_validated_purchase_supplier()` en alta, edición y aprobación; ese helper exige Party activo, rol supplier y CompanyParty activa.
- Purchase Invoice solo valida CompanyParty activo al crear; edición y submit consultan configuración sin `is_active` y no vuelven a comprobar rol/estado Party. Purchase Receipt crea con membership, pero sin rol/estado; edición persiste sin guard y submit no revalida. SupplierQuotation carece de guard equivalente en alta/edición/aprobación.
- QA1/QA2 rechazan. Aplicar el guard canónico a todos los puntos ampliados de ciclo de vida, sin retirar la cobertura de PO, y comprobar transición a membresía inactiva/Party inactivo antes de submit/edición y ausencia de GL.

### #1339 — alta y consulta de valores de dimensiones

- El endpoint solo valida campos no vacíos y guarda un valor activo sin cargar/verificar `DimensionType.is_active`. El selector muestra tipos activos e inactivos.
- `list_dimensions` filtra tipos activos, pero `dimension_values.search` no verifica vigencia del tipo padre; valores bajo una dimensión desactivada siguen siendo consultables por ID.
- FK RESTRICT existe y SQLite actual habilita foreign keys: el probe histórico con PRAGMA 0 no demuestra huérfanos en la configuración vigente. El handler aún carece de error controlado para ID inexistente.
- QA1/QA2 rechazan. Agregar guards/selector y cobertura para ID inexistente, tipo inactivo y consulta del valor bajo tipo inactivo.

### #1342 — scope bancario de plantillas de cheque

- Preview y PDF pasan la cuenta del cheque al resolver, pero selección explícita por `template_id` retorna antes y solo valida tipo/compañía/publicación; permite plantilla asignada a otra cuenta.
- Default sin ID sí prioriza la cuenta; no hay pruebas para incompatibilidad explícita en ambos endpoints.
- El editor permite `Global + bank_account_id`, pero defaults globales solo buscan plantillas sin cuenta. El comentario lo deja como decisión pendiente entre prohibir o definir resolución; no asumir política.
- QA1/QA2 rechazan por el bypass explícito; validar account scope y probar cheque de misma cuenta, cuenta distinta y plantilla genérica en preview/PDF.

### #1348 — detalle bancario no reconstruye la apertura ni separa cuentas

- `get_bank_movement_detail()` filtra `PaymentEntry` y `BankTransaction` al período; `_compute_running_balance()` empieza en cero y solo acumula esas filas. La reproducción 100 anterior +20−5 devuelve 20 y 15, no 120 y 115.
- Sin `bank_account_id`, movimientos de varias cuentas quedan en un solo acumulador; cuentas distintas en la misma moneda se combinan sin sentido como saldo individual. El primer comentario pide acumuladores separados por cuenta.
- El posible helper GL de apertura filtra a través de `exclude_cancelled_gl_entries()`, que descarta toda reversa sin tomar en cuenta su fecha efectiva. #1709 documenta que esto distorsiona cortes históricos. Alinear apertura/reversiones a ese contrato, sin mezclar filas de extracto sin conciliar con saldo GL.
- La prueba vigente hallada en `tests/test_spreadsheet_export_sanitization.py` verifica salida/escape, no saldo inicial, corte previo, cuentas múltiples ni reversas. QA1/QA2 rechazan independientemente; etiqueta GitHub `needs-work` sin cambios.

### #1346 — regresión propuesta sin cobertura suficiente; colisión de alias

- El cambio local rechaza columnas desconocidas antes de `group_by_reference`, lo cual satisface la decisión aprobada en #1652. Sin embargo, no existe una prueba ImportService que reproduzca un CSV maestro con `document_ref,nombre` repetido y compruebe rechazo, contadores y ausencia de clientes/proveedores/cuentas persistidas. El único caso `UNKNOWN_COLUMN` es ODS sin fila de encabezado; no cubre los datos del issue ni los tres adaptadores.
- El alias añadido `reference -> document_ref` colisiona con la etiqueta inglesa de la columna canónica `referencia` de JournalEntry. La plantilla en inglés puede normalizar `document_reference` y `reference` ambas a `document_ref`, provocando `DUPLICATE_COLUMN` y bloqueo del formato válido.
- QA1/QA2 rechazan. Agregar regresiones funcionales por consumidor y corregir el mapeo conservando aliases reales y etiquetas localizadas. Etiqueta GitHub `needs-work` intacta.

### #1352 — retirar el helper huérfano y alinear contrato documental

- El helper `BusinessEventOrchestrator.reverse_from_snapshot()` sigue definido (`event_orchestrator.py:141-272`) y no tiene caller productivo, prueba vigente ni referencia documental exacta. El test aislado histórico ya no existe.
- `handle_event()` produce `results["snapshot"]` solo en memoria; posting no lo persiste ni lo consume y serializer no asigna `snapshot_id`. En contraste, documentación ES/EN promete Snapshot JSON persistido y usado para reversión. La última decisión de #1352/#2248 permite retirar el helper sin caller, pero exige aclarar esta discrepancia.
- QA1/QA2 rechazan. Retirar solo este helper huérfano y actualizar el contrato documental para distinguirlo de la reversión GL/AR/AP append-only y snapshots fiscales con consumidores; preservar esas rutas activas. GitHub `needs-work` y etiqueta intactos.

### #1353 — condición fiscal por categoría aprobada, aún no implementada

- Decisión funcional aprobada: filtro opcional por categoría por línea para goods/services, reusando `ItemCategory`; artículo sin categoría no coincide con regla restringida; preservar los demás predicados fiscales.
- `allowed_item_categories` existe solo en contexto puro. `TaxRule`/formulario/API no persisten/configuran el filtro; `_to_context()` no lo lee; `ItemContext` y builders/preview no propagan `Item.item_category_id`; `FiscalEngine` aplica reglas globalmente a todas las líneas.
- No hay tests de categorías. QA1/QA2 rechazan. Implementar contrato end-to-end y cubrir categorías permitidas/no permitidas/ausentes, reglas no restringidas, inventario/no inventario/servicio y paridad preview/posting. GitHub `needs-work`, etiqueta intacta.

### #1359 — capacidad aprobada para integrar; checkout la retiró y no la conecta

- Decisión vigente (#1359/#1368): integrar captura y validación por línea, posting a todos los libros, asociación inmutable por GL entry, consulta/reportes, aislamiento/RBAC y reversión append-only. Usar unicidad/precedencia #1340 (local prevalece sobre global; no mutar referencias históricas).
- En HEAD no existe `GLEntryDimension`/`gl_entry_dimension`; commit `0a7db7b2` la retiró y añade migración drop; el test de dead-code inventory afirma ausencia. La UI/discovery `DimensionType`/`DimensionValue` sigue activa sin conexión al ledger.
- El catálogo no cumple #1340: sin unicidad backend/DB normalizada scoped y discovery expone global/local duplicados sin precedencia. No hay tests de asociaciones dinámicas GL; existentes prueban dimensiones estándar.
- QA1/QA2 rechazan. La integración aprobada requiere reintroducir el contrato de persistencia con migración, conectar el ciclo end-to-end, alinear admin/discovery con #1340 y reemplazar el assert de retiro por pruebas funcionales. No inferir que quitar el modelo satisface el issue. GitHub `needs-work`, etiqueta intacta.

### #1364 — guard de award existe, pero queda sin pruebas y alta deja pasar ronda inválida

- Award: oferta anterior queda fuera de `submitted_supplier_quotations()`; `_find_manual_override_items()` la rechaza antes de persistir y POST hace rollback. Falta prueba de servicio y endpoint con oferta vieja y afirmación de cero awards persistidos.
- SupplierQuotation desde RFQ: `_create_supplier_quotation_from_request()` convierte `negotiation_round_id` inválido, cerrado, ajeno o ausente a `None` y sigue creando draft; submit no compara contra la ronda actual. Al tener rondas la RFQ, el issue exige rechazar ID que no corresponda, incluida ronda nula.
- QA1/QA2 rechazan. Cubrir ronda previa/manipulada, quote no relacionada y fallo sin persistencia/submit, manteniendo el guard del award. GitHub `needs-work`, etiqueta intacta.

### #1365 — el cierre admite ofertas seleccionadas obsoletas

- `purchase_request_comparison_covered_item_ids()` marca cubiertas líneas selected de comparativos finalized/used solo porque tienen `selected_supplier_quotation_id`; no valida que la cotización exista, pertenezca al comparativo/compañía ni siga aprobada (`docstatus=1`).
- Vista y POST consumen el conjunto y pueden cerrar la solicitud tras cancelar la oferta seleccionada. Generación posterior de OC sí valida, pero ocurre tarde. Razón de cierre también considera selección histórica válida.
- QA1/QA2 rechazan. Añadir una guard común de vigencia al cierre para finalized/used, mantener abierta solicitud y cubrir cancelar oferta sin orden activa antes de cerrar, además de comparación usada. GitHub `needs-work`, etiqueta intacta.

### #1367 — excepción de OC permite texto de espacios y no deja traza

- `_validate_purchase_order_sourcing()` usa truthiness sin `strip()`: gerente puede pasar `comparison_exception_reason="   "` cuando la política exige comparativo. El texto no se normaliza al extraer del form.
- La orden solo persiste `purchase_award_id`; PurchaseOrder no almacena razón ni actor autorizador, ni queda ese dato en log de creación. Pruebas existentes de `reason/authorized_by` cubren adjudicación, no esta excepción sin comparativo.
- QA1/QA2 rechazan. Requerir motivo normalizado no vacío, permiso de gerente, persistir motivo+actor append-only/trazable y cubrir POST de gerente/no gerente/válido/vacío/espacios y rollback sin orden/evidencia parcial. GitHub `needs-work`, etiqueta intacta.

### #1372 — fecha parcial se acepta y reemplaza en silencio

- Form permite `inicio_anio_fiscal`/`fin_anio_fiscal` independientes y solo compara orden si los dos existen. Servicio pasa esos valores. Repositorio usa los valores solo si ambos vienen; de lo contrario crea año calendario de referencia/hoy, descartando la fecha elegida.
- Sin tests de fecha parcial por función ni por asistente HTTP. QA1/QA2 rechazan. Validar partial range explícitamente (rechazar con error controlado o preservar según contrato fiscal aprobado) antes de crear compañía; probar inicio solo, fin solo, rango completo, y ausencia de persistencia ante invalidación. GitHub `needs-work`, etiqueta intacta.

### #1375 — faltan regresiones para las validaciones de notas al aprobar

- El `return` temprano del issue está corregido: ventas y compras incluyen crédito/débito en `item_models`, llegan al contrato de moneda y a `validate_submit_prerequisites()`, y luego a sus validadores de dominio (`approval_engine.py:659-718`).
- El conjunto `require_amount_nonzero` incluye las notas de venta pero omite `purchase_credit_note` y `purchase_debit_note` (`approval_engine.py:700-702`). Alinear la validación final al contrato de las notas, sin afectar tipos restantes.
- El árbol actual no contiene pruebas de aprobación final para los cuatro subtipos ni casos de líneas vacías, moneda inválida, origen/reversión o que el fallo impida dejar la solicitud aprobada y el documento borrador. El test histórico de una nota de débito se eliminó en `0970476b clean`; no proporciona cobertura actual.
- El código de venta solo valida el origen si `reversal_of` tiene valor. La creación también permite omitirlo (`ventas/services.py:2261-2285`). Confirmar el contrato aprobado para nota sin factura fuente; no imponer su obligatoriedad sin decisión funcional explícita. En compra el validador sí recibe la cadena vacía y falla al resolver fuente.
- QA1 y QA2 rechazan independientemente. Agregar pruebas funcionales que demuestren el guard final de los cuatro tipos, incluyendo importe no nulo de compra, validación de moneda, línea ausente y reversión inválida; verificar rollback y estado de ApprovalRequest/documento. GitHub `needs-work`, etiqueta intacta; no ejecuté pruebas/linters ni cambié código/GitHub.

### #1377 — KPI y detalle AP omiten devoluciones/créditos abiertos

- `get_purchases_data()` conserva `include_returns=False` al sumar `outstanding`; el helper excluye `is_return=True` antes de sumar aunque ya tiene signo negativo para retorno (`api/dashboard.py:327-333,797-812`).
- `_payable_invoices()` excluye expresamente `is_return=True` (`api/dashboard.py:617-627`). El payload ya serializa el crédito/devolución como negativo (`:630-640`), pero esa ruta es inaccesible.
- Con factura aprobada abierta de 100 y nota aprobada abierta de 20, el KPI esperado es 80 y la tabla debe incluir la nota a -20. Hoy devuelve 100 y no presenta la nota. No hay regresión específica de dashboard KPI/detalle. Los filtros actuales de `docstatus=1` y saldo positivo deben mantenerse para no mezclar borradores o saldos cerrados; probar también el cierre/anulación del crédito.
- QA1/QA2 rechazan independientemente. Incluir créditos abiertos en KPI y tabla con signo coherente; añadir regresión de conciliación, cerrados y anulados. GitHub `needs-work`, etiqueta intacta; no ejecuté tests/linters ni modifiqué código/GitHub.

### #1378 — el árbol y el pie mezclan monedas de asignación y pago

- `PaymentReference.allocated_amount`/`currency` están en moneda del documento; `payment_amount`/`payment_currency` son el lado pago. Las dos orientaciones del árbol pasan `allocated_amount` como `applied_amount` (`document_flow/tree.py:690-725`). Al nodo `payment_entry` se le asigna moneda del pago, y el renderer etiqueta siempre con `node.currency` (`document-flow-tree.js:128-129`); desde la factura, eso exhibe amount documental bajo código de pago. Desde el pago a factura, allocated/currency documental sí es la combinación correcta.
- El comentario del issue amplía el mismo defecto al total de `bancos/pago.html`: filas usan allocated + `ref.currency`, pero el pie suma allocated y le pone `registro.currency` (`:217,225`).
- No encontré regresiones de importes/monedas para árbol en ambas direcciones ni para el pie. Separar y transportar el importe y moneda propios del nodo/relación; pie en moneda del pago usando los valores de ese lado. Probar 370 NIO ↔ 3.70 USD, ambas orientaciones, además de pagos de misma moneda.
- QA1 y QA2 rechazan independientemente. GitHub `needs-work`, etiqueta intacta; no ejecuté pruebas/linters ni modifiqué código/GitHub.

### #1380 — cambiar la cuenta no invalida tasa de las referencias

- `applyBankAccount()` actualiza cuenta y `header.currency` pero deja intacta `payment_exchange_rate` de cada línea (`bancos/templates/bancos/pago_nuevo.html:218-230`). La normalización conserva tasa positiva y recalcula `payment_amount` con moneda nueva y tasa vieja (`:252-270`); `prepareSubmit()` serializa ambos (`:534-552`).
- `_payment_reference_amount_context()` confía en la tasa positiva que envió UI y persiste el monto resultante, solo recalculando tasa si no es positiva (`bancos/services.py:2301-2309,2357-2374`). El caso de cuenta NIO→EUR todavía puede enviar/persistir valor incorrecto en EUR.
- Pruebas de asignación multimoneda existentes no cubren cambio de cuenta tras cargar línea. Invalidar/recalcular tasas o requerir tasa nueva al cambiar moneda, y comprobar UI, payload, persistencia y rollback/error si falta tasa. QA1/QA2 rechazan. GitHub `needs-work`, etiqueta intacta; sin pruebas/linters ni cambios de producto/GitHub.

### #1381 — la revalidación Draft aún permite carrera con aprobación

- Guard `forecast.status == "Draft"` ya presente en `validate_row()`, `validate_document()` y `persist_document()` (`cash_forecast_entry.py:45-52,75-89,114-130`); resuelve el bypass secuencial del issue.
- ImportService valida y persiste en la misma sesión (`imports/services/import_service.py:518-557`). `session.get()` al persistir puede devolver instancia Draft cacheada; si otra sesión aprobó después de validación, el estado obsoleto no se refresca. `cash_forecast_approve()` no comparte lock (`bancos/cash_forecast.py:233-244`). El detalle puede insertarse tras transición a Approved.
- `test_cash_forecast_import_status.py:116-155` cambia el estado en la misma sesión, sin carrera real; también cubre Draft/Approved, pero no Closed/Archived expresamente.
- QA1/QA2 rechazan. Serializar la transición con importación usando mecanismo efectivo SQLite/PostgreSQL y agregar prueba con sesiones/interleaving concurrentes, estados no Draft y rollback de entradas. GitHub `needs-work`, etiqueta intacta; no ejecuté tests/linters ni modifiqué código/GitHub.

### #1382 — el cero numérico cae al fallback de tasa histórica

- El adaptador `purchase_order` activo está registrado desde `transaction_documents.py`; `explicit_rate = tipo_cambio or exchange_rate` borra el cero numérico (`:352`) y recurre a tasa del origen/histórica (`:358-365`). La cadena `"0"` llega a la validación positiva y falla (`:376-377`).
- El helper legacy `imports/adapters/purchase_order.py` hace `if raw_rate` y conserva igual el bypass (`:153-163`), aunque no está registrado.
- No encontré regresión del adaptador activo que compare `0`, `"0"`, `None`/vacío con un lookup histórico disponible. Las pruebas vistas de tasas negativas/no finitas no prueban esta coerción.
- QA1/QA2 rechazan. No permitir fallback ante tasa explícita no positiva; conservar fallback solo para celda ausente/vacía; probar tipo de dato numérico de XLS/XLSX en el adaptador registrado y la ruta legacy si se mantiene. GitHub `needs-work`, etiqueta intacta; sin pruebas/linters ni cambio de producto/GitHub.

### #1386 — falta regresión de selector de libro de otra compañía

- Fix presente en `874d52ca` y test específico actual existe (`test_manual_journal_selected_books.py`): crear/editar/postear conserva una selección única; selector ausente usa todos los activos; libro inactivo se rechaza. El código filtra ID/código por `Book.entity == company` y `status == activo`; posting usa selector persistido.
- La cobertura no comprueba que un libro activo de otra compañía, enviado por ID o código, sea rechazado antes de persistir journal/GL. El issue define selector válido como activo y autorizado de esa compañía; `AGENTS.md` pide aislamiento intercompany probado. No se aprecia bypass en el guard actual, pero la regresión contractual falta.
- QA1 retiró aprobación inicial tras la objeción; QA1/QA2 coinciden en rechazo por este faltante de test. Añadir test cross-company sin persistencia y reiniciar QA. GitHub `needs-work`, etiqueta intacta; no ejecuté pruebas/linters ni modifiqué producto/GitHub.

### #1427 — conciliación de compras mezcla importes nominales sin moneda

- `get_purchase_reconciliation_orders`/filas PO, facturas no vinculadas y resumen de recepciones no llevan `transaction_currency` (`purchase_reconciliation_service.py:2048-2061,2104-2116,2152-2164`). `PurchasePendingRow` también omite moneda en el detalle (`:118-129,1784-1802`). Las plantillas muestran `grand_total`/`pending_amount` como floats sin código (`purchase_reconciliation.html:108,149,205-206,257`).
- Comentario #1427 amplía al panel: `get_purchase_reconciliation_panel_groups()` pasa modelos sin currency y el template presenta `matched_amount` crudo (`purchase_reconciliation_panel.html:139`). Aunque cada conciliación exige monedas iguales internamente, el panel agrupa transacciones de una empresa que pueden tener distintas monedas.
- No encontré regresión de vista/template con NIO/USD de mismo importe nominal para órdenes, factura sin recepción, resumen/detalle de pendientes ni panel. Propagar moneda apropiada por documento/línea; presentar por importe transaccional y unidad; no agregar valores nominales de monedas distintas. QA1/QA2 rechazan. GitHub `needs-work`, etiqueta intacta; no ejecuté pruebas/linters ni modifiqué código/GitHub.

### #1430 — una clave de línea ajena permite award finalized vacío

- `validate_award_request()` solo exige dict truthy. `_find_manual_override_items()` y creación iteran IDs reales RFQ sin comprobar que claves del payload pertenezcan a esas IDs (`purchase_sourcing_service.py:259-304,319-353`). Payload `{fake_line: fake_offer}` pasa; `_flush_award()` inserta el encabezado terminal antes de agregar líneas, el loop no agrega ninguna.
- Selección vacía sí se rechaza. Oferta desconocida con línea real falla en lookup/cobertura. Pero no hay pruebas de claves ajenas, oferta desconocida, partial válida o ninguna fila de award en caso inválido.
- QA1/QA2 rechazan. Validar claves ⊆ líneas RFQ y selección válida antes del insert; cubrir rollback y que no sobreviva award finalized vacío. GitHub `needs-work`, etiqueta intacta; sin pruebas/linters ni modificación de producto/GitHub.

### #1434 — KPI de órdenes abiertas cuenta documentos cerrados/completados

- `get_purchases_data()` cuenta toda `PurchaseOrder(company=..., docstatus=1)` como `open_orders` (`api/dashboard.py:334`), sin condición por `status` ni saldo de cantidades pendientes.
- El reporte conciliatorio ya calcula `ordered_qty`, `received_qty`, `billed_qty` y estados (`purchase_reconciliation_service.py:2021-2046`), pero no se usa en el KPI. No hay prueba focal para `open_orders`.
- Una orden `closed` completamente recibida/facturada sigue contando abierta. Alinear conteo a definición vigente de cierre/saldos; cubrir pending/partial, completamente recibido/facturado y closed incluso con quantities incompletas. QA1/QA2 rechazan. GitHub `needs-work`, etiqueta intacta; no ejecuté pruebas/linters ni cambié producto/GitHub.

### #1437 — bloqueante: las notas de crédito aún no tienen contrato de preview fiscal

- El formulario envía `document_type=sales_credit_note` o `purchase_credit_note`, pero las configuraciones activas no pasan `documentType` y JS deriva el tipo de `formKey`; el preview calcula como factura (`transaction-form.js:775-802`, `ventas/routes.py:2218-2234`, `compras/services.py:2269-2291`).
- El campo oculto con el subtipo no es la fuente del payload del preview. Tampoco hay perfiles `sales_credit_note`/`purchase_credit_note` en `_FISCAL_MATRIX`; conectar solo el subtipo desde navegador resultaría en rechazo de tipo (`fiscal_preview_service.py:58-...,231-235`).
- Posting usa eventos `sales_credit_note_confirmed` y `purchase_credit_note_confirmed` (`accounting_engine/document_builders.py:486,564`); el preview debe resolver los mismos eventos y reglas y mantener coherencia del cálculo.
- Agregar regresiones funcionales para ambas notas, verificando tipo enviado, evento/reglas y total contra el cálculo de posting; si algún subtipo no es soportado por decisión, mostrar rechazo explícito y no presentar preview de factura.
- QA1/QA2 rechazan independientemente. Etiqueta GitHub `needs-work` intacta; sin comentario, edición de código, pruebas ni linters.

### #1438 — bloqueante: el preview de compras no sigue la moneda transaccional

- El selector enlaza `header.transaction_currency`, pero `buildFiscalPayload()` manda `header.currency`, vacío en factura nueva, sin alias ni `transaction_currency` (`compras/templates/compras/factura_compra_nuevo.html:63-72`, `transaction-form.js:356-368,790-800`). El preview reemplaza vacío con NIO y consulta reglas con esa moneda (`fiscal_preview_service.py:239-255`, `tax_rule_service.py:61-76`).
- El watcher tampoco escucha `header.transaction_currency` (`transaction-form.js:421-430`), por lo que elegir/cambiar USD no obliga a recalcular.
- Usar la misma moneda que se persiste; al cambiarla actualizar preview y filtrar por regla. Agregar regresión de compra USD con regla solo USD, NIO excluyéndola, y cambio USD→NIO/viceversa con payload/resumen actualizado.
- QA1/QA2 rechazan independientemente. Etiqueta `needs-work` intacta; sin cambios en código ni GitHub, sin ejecutar pruebas/linters.

### #1440 — bloqueante: el neto GL agregado se vuelve a sumar por pago

- `_prior_payment_document_net()` agrega una sola vez el neto de todos los IDs (`document_builders.py:1629`). `_voucher_net()` devuelve un escalar de `SUM(debit-credit)` sobre `voucher_id.in_(...)` sin agrupar por voucher (`:1672-1685`). El ciclo multiplica ese agregado por la proporción de cada pago (`:1631-1635`): 40 y 30 asignados completos generan 140, no 70.
- Ese carrying value participa en liquidación y revaluación; la diferencia distorsiona saldos monetarios posteriores.
- Obtener neto GL por voucher y prorratear solo ese pago; cubrir dos pagos con netos diferentes, pagos parcialmente aplicados a documentos, pago compartido por varios documentos y voucher cancelado.
- QA1/QA2 rechazan independientemente. Etiqueta `needs-work` intacta; sin código/GitHub ni ejecución de pruebas/linters.

### #1441 — bloqueante: el mapper borra impuestos antes del guard de posting

- `_map_fiscal_lines()` sigue haciendo `continue` si no resuelve cuenta fiscal (`accounting_engine/orchestrator/mapper.py:217-223`). El asiento luego se balancea contra AR/AP usando líneas restantes (`:46-73,470-480`), ocultando la omisión; el guard de posting para líneas sin cuenta no alcanza una línea ya descartada.
- El paraguas #1707 exige rechazo explícito para un impuesto contabilizable sin cuenta. No hay cobertura de mapper/proforma/posting para este caso.
- Lanzar un error de dominio antes de formar un proforma contabilizable. Agregar casos con impuesto de compra/venta contabilizable sin cuenta explícita y sin default, verificar que falla y no persisten GL; conservar el caso con cuenta existente.
- QA1/QA2 rechazan independientemente. GitHub `needs-work` intacto; no hubo cambios de código, pruebas, linters ni GitHub.

### #1465 — bloqueante: falta cobertura del fix y hay rutas de cierre con 500

- El commit previo añadió captura `KeyError`/`ValueError` a `create-target` (`api/__init__.py:1692-1705`), pero el test citado por QA fue retirado y no hay regresión HTTP actual que compruebe 400 + ausencia de escritura para tipo destino o fuente inválido.
- En `close-line`, `_require_flow_company_access()` y `_require_source_item_access()` se ejecutan antes del `try` (`:1713-1729`); en `close-document`, la autorización también está fuera (`:1743-1754`). `get_document_type()` propaga `ValueError`, así que una fuente desconocida puede responder 500.
- Traducir entradas inválidas consistentemente en las rutas, y probar create-target destino/fuente, close-line/close-document fuente inválida, status HTTP y que no se cree/cambie ninguna relación o documento.
- QA1/QA2 rechazan. GitHub `needs-work` intacto; sin cambios de etiqueta/comentarios/código ni ejecución de pruebas/linters.

### #1493 — bloqueante: falta probar no duplicar una aplicación mensual

- El criterio decidido por el responsable exige idempotencia por ocurrencia. El servicio busca existente por plantilla/compañía/libro/año/período y evita repetir estados pending/applied (`recurring_journal_service.py:230-246`), pero no hay prueba que aplique dos veces la misma plantilla a ese mismo período y verifique un único registro y un único diario. La prueba actual usa dos plantillas distintas.
- Añadir regresión de reintento sobre misma ocurrencia, incluyendo ausencia de segundo comprobante/líneas. Revisar también frecuencia de fila histórica en el paso de aprobación: creación y aplicación sí rechazan weekly/daily, aprobación no valida ese campo.
- QA1/QA2 rechazan por brecha contractual; el test que QA3 histórico no halló sí existe ahora en HEAD, pero no cubre el reintento. `needs-work` intacto, sin cambios de código/GitHub ni ejecución de checks.

### #1564 — bloqueante: portal de cliente/proveedor oculta documentos 101+

- Los nueve listados tienen `.limit(PORTAL_PAGE_SIZE)` (100); plantillas muestran `|length` como total sin link de continuación ni total sin límite (`portal/__init__.py:31,83-97,216-235`; templates customer `:16,55,94,133`, supplier `:16,55,94,133,182`).
- La reproducción de 101 documentos por portal en comentarios continúa sin fix ni pruebas de cardinalidad para ambos portales.
- Implementar paginación/carga adicional por categoría o mecanismo equivalente; presentar total real y contar con pruebas >100 para ambos roles y los listados afectados.
- QA1/QA2 rechazan independientemente. No se ejecutaron pruebas/linters ni se modificó código/GitHub; etiquetas intactas.

### #1737 — bloqueante: los UOM de compra/venta no exigen conversión por artículo

- `validate_item_uom_rows()` valida unidad base y rows, pero no las UOM operativas (`inventario/service.py:917-937`). Alta/edición guardan `purchase_uom` y `sale_uom` sin compararlas con default/factores (`:950-982,715-797`). Una opción de catálogo existente sin fila por artículo deja configuración que falla cuando los consumidores convierten cantidades.
- No hay prueba de alta/edición de esta relación. Añadir guard de servicio antes de cambiar modelo/conversiones; probar UOM ausente/base válida, conversión presente y conversión ausente en ambas rutas, con rechazo y sin mutación parcial.
- QA1/QA2 rechazan independientemente. GitHub `needs-work` intacto; sin código/GitHub ni ejecutar pruebas/linters.

### #1752 — bloqueante: “Editar” landed cost navega a creación

- El enlace pasa `landed_cost_id` al endpoint `/import-landed-cost/new`, pero esa ruta ignora el parámetro, no carga el documento y siempre POSTea al helper creador (`compras/templates/compras/import_landed_cost.html:23-29`, `compras/routes.py:3535-3591`). El helper genera nuevo ID y commitea nueva cabecera, líneas/cargos y relación (`compras/services.py:3252-3354`).
- El borrador original queda sin cambios y el submit puede crear un duplicado. No hay ruta/service ni pruebas de edición.
- Implementar edición con permiso/compañía y condición `docstatus=0`, conservando el ID y actualizando evidencia de borrador consistente; o retirar el link si no hay contrato de edición. Cubrir GET/POST, cabecera, líneas y cargos, permisos/estado y no creación duplicada.
- QA1/QA2 rechazan independientemente. GitHub `needs-work` intacto; sin código/GitHub ni ejecutar pruebas/linters.

### #1758 — bloqueantes: probar el builder y migrar dimensiones en bases existentes

- La regla de negocio de `by_weight`/`by_volume` sí está aprobada: dimensiones por línea, defaults del catálogo, persistencia histórica y validación. No reabrirla como consulta.
- El test del engine crea `ItemContext` a mano y el test de persistencia solo comprueba columnas guardadas. Ningún caso pasa por `_build_landed_cost_item_contexts()` desde `ImportLandedCost` persistido; la regresión raíz (builder pierde dimensiones) volvería y la suite pasaría. Añadir flujo integración desde persistencia hasta allocation/posting y comprobar shares con default y override.
- Se añadieron columnas `weight`, `weight_uom`, `volume`, `volume_uom` a `Item` e `ImportLandedCostItem`, pero solo existe la migración baseline vacía. Añadir migración incremental de upgrade/downgrade comprobada para bases existentes.
- QA1/QA2 rechazan. GitHub `needs-work` intacto; sin comentario/cambio de etiqueta, tests/linters ni modificaciones de producto.

### #1811 — bloqueante: el formulario no suministra la moneda exigida al guardar

- `stock_reconciliation_nuevo.html` no incluye `transaction_currency`/`currency`; la configuración tampoco provee default. `_handle_stock_entry_new_post()` exige campo explícito aunque resolvió moneda funcional de compañía, falla antes de insertar y hace rollback (`inventario/services.py:879-899`). El usuario normal recibe formulario re-renderizado con flash (HTTP 200), no conciliación. El comentario histórico del 500 por retorno None ya no aplica porque la ruta continúa el render (`routes.py:910-927`).
- Los tests de POST que llegan a la conciliación inyectan moneda manualmente en lugar de reproducir el formulario; falta integración positiva.
- Mostrar y enviar moneda transaccional explícita válida o derivarla explícitamente de moneda funcional; probar flujo de navegador/POST, ausencia/error de moneda sin persistencia y alta exitosa/reconciliación.
- QA1/QA2 rechazan. Etiqueta GitHub `needs-work` intacta; sin mutaciones ni pruebas/linters.

### #1813 — bloqueante: configuración 3-way permite aprobar sin orden ni entrega

- `_validate_3way_delivery_requirement()` se evalúa solo tras encontrar orden/documento origen. Si `matching_type=3-way`, `require_sales_order=False` y no hay origen, `_validate_sales_order_requirement()` retorna temprano (`ventas/services.py:1914-1915`) y permite la factura. El checkbox es independiente en admin; 3-way significa OV+entrega+factura.
- Test actual solo cubre 2-way con orden sin entrega y 3-way+`require_sales_order=True` sin entrega; no cubre el bypass, vínculo válido orden/entrega ni submit HTTP/efectos de posting.
- Obligar orden y entrega cuando el matching type es 3-way o rechazar la combinación incoherente al guardar. Cubrir config con flag false/no links, caso válido mismo flujo/líneas, entrega ajena/mismatch y submit HTTP con rollback o GL correcto.
- QA1/QA2 rechazan independientemente. GitHub `needs-work` intacto; no ejecuté pruebas/linters ni cambié código/GitHub.

### #1888 — bloqueante: contrato aprobado de StockEntry sigue descartándose

- Decisión aprobada en issue: persistir/recuperar `cost_center`, `project` y observaciones por línea; no dejar cuenta arbitraria en modal; eliminar payloads fiscales de StockEntry y rechazarlos por backend. GL debe heredar y propagar dimensiones por línea según #1359 sin alterar importe/cantidad.
- Formulario usa macro genérico sin capabilities; todavía presenta modal account/cost-center/unit/project/remarks y serializa `tax_lines_payload`/`tax_summary_payload`. `StockEntryItem` no tiene campos de dimension/remarks; writer ignora valores y no rechaza las entradas; readback y posting usan solo filas/cabecera de modelo. La dimensión por línea nunca llega a GL.
- Implementar campos persistidos, migración, validación company scope/herencia/precedencia, edición y readback. Exponer solo controles soportados mediante config de macro; quitar fiscal payload y rechazar impuestos/cuenta arbitraria backend.
- Añadir regresiones funcionales multi-línea y reread, dimensión distinta por línea hasta GL/libros/reversas, invalid cross-company y campos no soportados; verificar regresión de otros consumidores del macro compartido.
- QA1 rechaza; QA2 coincide independientemente. `needs-work` intacta, sin ejecución de pruebas/linters ni cambios de producto/GitHub.

### #1891 — bloqueante: duplicación crea nuevos ajustes genéricos legados

- Aunque formulario, validador de alta y rutas nuevas excluyen `stock_adjustment`, el detalle histórico ofrece **Duplicar** para todo documento docstatus 0/1 (`inventario/templates/inventario/entrada.html:17-30`).
- `inventario_entrada_duplicar()` no valida el propósito y copia `origen.purpose` al nuevo borrador antes del commit (`inventario/routes.py:1031-1095`). El endpoint reintroduce así el tercer tipo de ajuste genérico.
- Bloquear la duplicación de propósitos legacy y evitar que un borrador legacy parezca editable si debe ser solo lectura. Añadir regresión POST que compruebe 4xx y ninguna fila nueva; mantener acceso de consulta histórica.
- QA1 y QA2 rechazan independientemente. QA3 histórico buscaba un test no trackeado, pero `tests/test_stock_adjustment_contract.py` sí está versionado en el HEAD local; el bypass actual no está cubierto por ese archivo. GitHub/etiqueta `needs-work` intactos; sin código, pruebas/linters, comentarios o cambios de etiqueta.

### #1916 — bloqueante: retiro de modelos workflow no actualiza esquemas existentes

- La búsqueda del HEAD no encuentra las cinco clases ni sus nombres de tabla, pero conserva `WORKFLOW_STATE_ID = "workflow_state.id"` en `database/__init__.py:105` sin consumidores.
- El HEAD solo contiene `20260809_0001_baseline.py`, cuyo `upgrade()` es no-op; el commit histórico `6205ae9e` añadió `20261109_0003_drop_workflow.py`, pero `41c7af1e` lo eliminó. El `create_all` vigente no borra las tablas de esquemas ya creados, por lo que una base existente conserva las cinco tablas legacy.
- La decisión aprobada pre-alpha permite descartar filas legacy sin exigir retención productiva; aun así, el issue requiere migración segura y la puerta Alpha/contrato de esquema pide actualizar bases existentes. Retirar constante huérfana y entregar una migración efectiva/idempotente integrada en la cadena activa para eliminar las tablas retiradas.
- QA1 y QA2 rechazan independientemente. No ejecuté pruebas/linters ni modifiqué código/GitHub; `needs-work` intacta.

### #1938 — bloqueantes: preferencias visibles no se restauran y no hay migración incremental

- La vista guarda `show_users` y `advanced` en `display_json` (`saved_views_service.py:41-42,96-115`), pero `_preferred_columns_from_view()`/`_preferred_group_by_from_view()` solo leen columnas y agrupación (`reportes/helpers.py:453-477`). `_compute_display_columns()` y el template obtienen `show_users`/`advanced` directamente de `request.args` (`helpers.py:1274+`; `financial_report.html:52,75,89`); seleccionar una vista no restaura esas preferencias guardadas.
- `SavedReportView` es modelo nuevo pero no existe migración para bases existentes; en el árbol solo queda el baseline Alembic no-op. La creación de tabla por `create_all` cubre DB nueva, no upgrade de DB existente, contrario al contrato de esquema vigente.
- QA1 rechaza; QA2 reevalúa y retira su aprobación inicial, rechazando independientemente por ambas brechas. El reporte de QA3 remoto sobre archivo de pruebas ausente es stale porque el test sí está trackeado en HEAD. GitHub/etiqueta `needs-work` intactos; sin tests/linters ni cambios de producto/GitHub.

### #1973 — pendiente por revisión discordante de cobertura

- El diff actual elimina los cuatro parámetros sin uso y los callers actuales no los pasan. Sin embargo, `test_ningun_consumidor_envia_los_parametros_retirados()` usa `re.search` y solo inspecciona la primera llamada de cada archivo; los kwargs reintroducidos en invocaciones posteriores de templates con múltiples llamadas no harían fallar la prueba. Los smoke routes cubren solo tres plantillas representativas.
- QA1 aprueba por búsqueda estática completa y la prueba existente; QA2 rechaza porque la regresión no guarda el contrato para todos los callers. Revisión independiente QA1 pendiente sobre si esta brecha es bloqueante bajo el requisito de regresión del contrato. Hasta consenso, no aprobar. GitHub/etiqueta intactos; sin pruebas ni cambios de producto.

### #2077 — pendientes de esquema y de prueba de ruta activa

- El servicio usa un único pipeline y las regresiones de servicio cubren validación, SHA-256/almacenamiento, errores durante lectura/copia, rollback y limpieza. QA3 histórico buscó un test que sí está trackeado en HEAD.
- Falta una migración incremental para la nueva columna `File.sha256`; Alembic en el árbol es solo baseline no-op. `create_app()` sí intenta alterar columna/índice mediante `_ensure_file_sha256_column()` (`__init__.py:577-579`, helper `database/helpers.py:937-964`), pero absorbe errores y el DDL de arranque contradice la decisión aprobada #1898 de usar Alembic como autoridad única. En falla puede dejar DB sin columna y uploads fallidos. Añadir migración efectiva y retirar la ruta de reparación de arranque.
- Falta cobertura multipart positiva por la ruta API activa: la suite llama el servicio directamente y el test HTTP de scope envía POST sin archivo. QA1 y QA2 rechazan independientemente; la migración es bloqueante y el HTTP positivo es una brecha adicional para demostrar el consumidor activo. GitHub/etiqueta needs-work intactos; no se ejecutaron tests/linters ni se modificó código.

Actualización #1973: QA1 reevalúa el hallazgo y cambia a rechazo. Existe consenso QA1/QA2: la prueba debe iterar todas las invocaciones/callers para detectar cualquier argumento residual, no solo el primer callsite de cada archivo. Etiqueta sin cambios.

Precisión adicional #2077: QA2 confirma que el startup sí intenta reparar `File.sha256` mediante DDL directo que absorbe errores, en contradicción con #1898; no afirmar que no hay intento de migración. El fix esperado es Alembic versionado como fuente única y sin alteración de esquema al arrancar.

### #1118 — QA1/QA2 rechazan: falta el tercer estado y el total

- El filtro de producción `docstatus == 1` es correcto para el reporte contable. La prueba vigente crea borrador y posteado, no un cancelado; tampoco fija que el total solo incluya el movimiento posteado. La decisión #6712901363 exige cubrir draft/submitted/cancelled y alinear filas/totales.
- QA1/QA2 rechazan por cobertura: agregar caso cancelled con cantidad distinguible, verificar exclusión de filas y total, y conservar casos existentes. El análisis `get_inventory_transfer_analysis` del reporte histórico no se encuentra como consumidor en HEAD; no inventar su reintroducción.

### #2045 — QA1/QA2 rechazan: test no discrimina consulta legacy

- El retiro de `from_order` en ruta/contexto estático se ve correcto y deja las fuentes soportadas intactas. El test `test_alta_orden_ignora_from_order_legacy` solo afirma HTTP 200, que también era la respuesta previa para una orden autorizada; no detecta que se reintroduzca query/carga/contexto de orden.
- Cubrir una señal que falle si se restaura la carga/exposición legacy, además de proteger alta desde request/quotation con compañía/permisos autorizados y ajenos conforme al criterio owner. QA1/QA2 rechazan independientemente; GitHub `needs-work` y etiquetas intactas, sin tests/linters ni cambios de producto.

### #1937 — QA1/QA2 rechazan: el PDF puede truncarse sin regresión que lo detecte

- La ruta actual reconsulta con `export_all=True, page=1` para PDF/CSV/XLSX; el servicio desactiva el límite en ese modo y el writer usa sus filas.
- `tests/test_account_movement_full_export.py` no está en HEAD. El test histórico agregado en `320e3abb` solo mockeaba reporte y renderer para verificar el flag, sin 101+ filas ni afirmar el contenido exportado; no acreditaba el resultado observado.
- QA1/QA2 rechazan independientemente. Agregar prueba funcional >100 GLEntry que confirme PDF completo tras `page_size`. No se ejecutaron pruebas/linters ni se tocaron producto/GitHub; `needs-work` intacta.

### #1919 — QA1/QA2: acceso de portal no se revoca al desactivar tercero/vínculo

Hallazgo: `check_portal_access()`, rutas de listado/detalle y `PrintService._authorize_portal_document()` no comprueban `Party.is_active` y `CompanyParty.is_active`. El acceso a documentos históricos sigue disponible después de desactivar el tercero o su asociación. Agregar autorización compartida y pruebas para ambos estados en listados, detalles y preview/PDF; validar que los documentos históricos no cambian. Revisión estática QA1/QA2 coincidente; sin cambios en producto o GitHub.

### #1931 — QA1/QA2: ruta de historial no presenta las versiones

Hallazgo: la ruta consulta `PrintTemplateVersion`, pero `print_template_list.html` ignora `versions` y no enlaza a la ruta; historial no descubrible ni visible. El owner confirmó que el historial debe completarse. Añadir enlace/UI con campos históricos relevantes y regresión positiva de creación/lectura, manteniendo RBAC. Revisión estática QA1/QA2 coincidente; sin cambios en producto o GitHub.

### #1928 — QA1/QA2: no hay regresión positiva de render

Las tres plantillas ahora usan `block contenido`, pero el test de render citado históricamente no está en HEAD. El control positivo actual solo afirma HTTP 200 en la lista; no comprueba su contenido y no cubre formulario ni configuración. Agregar pruebas autenticadas que detecten cuerpo vacío en lista, alta/edición y settings. Sin cambios en producto/GitHub.

### #1564 — QA: falta paginación/continuación en dashboards de portal

Ambos dashboards aún limitan consultas a 100 y el HTML no ofrece continuación ni distingue total de resultados. La evidencia previa confirma pérdida de filas en ambos portales con 101 documentos. Implementar paginación o carga progresiva en todos los grupos afectados y contadores de total correctos; probar límite/página siguiente y aislamiento de tercero/compañía. Sin cambios en producto/GitHub.

### #1950 — hallazgo estático: los tres formularios siguen sin CSRF

En HEAD `45e38f2b`, `external_document_validation.html`, `tax_templates.html` y `tax_template_items.html` conservan `<form method="post">` sin `csrf_token()`/`hidden_tag()`. `CSRFProtect` está registrado globalmente; las tres rutas POST siguen implementadas, por lo que el navegador no puede completar esos cambios con protección activa. La evidencia histórica HTTP del issue también reprodujo 400 sin token y éxito con token válido. QA1/QA2 independiente pendiente; no ejecutar pruebas/linters ni cambiar producto/GitHub.
Actualización #1950: QA1 y QA2 completaron la revisión independiente y coinciden en rechazo. Los tests existentes de líneas usan `WTF_CSRF_ENABLED=False`; cubrir POST válido/ inválido con protección activa en los tres formularios y verificar persistencia para el token válido. GitHub sin cambios.

### #1492 — re-revisión QA1/QA2: casos dual-positive no conservan balance agregado

El archivo de regresión sí está trackeado en HEAD, pese al 404 reportado por QA3. Sin embargo, los tests de alta y de plantilla histórica que ponen débito/crédito positivos en una línea también dejan los totales generales desbalanceados; una regresión que solo compruebe agregados seguiría rechazándolos y las pruebas pasarían aunque se retirara la validación por línea. Agregar un caso como el del issue, con una línea dual-positive y una segunda que mantenga débito total == crédito total, y probar que se rechaza antes de persistir o crear comprobante. La prueba de negativos sí existe en `test_recurring_template_negative_amounts.py`. QA1/QA2 rechazan en revisión fresca; GitHub y etiquetas sin cambios.

### #2093 — QA1/QA2: comparativos legacy de órdenes siguen accesibles

El constructor fue retirado, pero siguen los cuatro modelos/tablas `PurchaseOrderComparison*`, el branch legacy y POST de rondas en la ruta compartida, el renderer/template, helpers y `test_purchase_order_comparison_alignment.py`. La última decisión del issue pide retirar este flujo de históricos sin migración. El flujo autorizado de comparación desde PurchaseRequest está separado (`PurchaseRequestComparison`, rutas/servicio propios) y debe mantenerse. Retirar únicamente el branch legacy y sus símbolos/tests; comprobar que la comparación por solicitud y sus negociaciones siguen operativas. QA1/QA2 rechazan. GitHub sin cambios.

### #1162 — QA1/QA2: retiro seguro, pero aún no implementado

`MONETARY_ACCOUNT_TYPES` continúa en `exchange_revaluation_service.py:50`; búsqueda del árbol no encuentra consumidor. La selección actual de partidas no depende de ella, y hay pruebas del flujo de revaluación restante (posteo/tasas, anulación/rollback, concurrencia y UI). Ambos revisores confirman que basta retirar la definición sin alterar servicio. El issue sigue incompleto hasta que el símbolo desaparezca. No hubo cambios de código/GitHub.

### #1882 — QA1/QA2: redirect y plantilla legacy siguen en uso desde dashboard

El asistente `/imports/new` está activo y probado, pero `extracto_importar.html` permanece, el endpoint `/bank-statement/import` sigue redirigiendo y el dashboard todavía lo enlaza. La decisión del responsable dice adaptar el enlace al asistente canónico y no asumir compatibilidad. Retirar plantilla y ruta, cambiar link a `imports.new`, conservar cobertura de importación bancaria y permisos; eliminar traducciones solo si los msgid son exclusivos (el encabezado de importación se usa en el dashboard). QA1/QA2 rechazan; GitHub intacto.

### #1899 — QA1/QA2: CSS legacy sin consumidores sigue en el paquete

`dashboard.css`, `checkout.css` y `purecss-treeview.css` siguen versionados, aunque no hay cargas ni consumidores de sus selectores. La UI usa `cacaoaccounting.css` con clases `ca-sidebar`/`ca-tree`. Conservar `signin.css`, que sí se carga en login/forgot/reset/OTP. El fix es borrar solo las tres hojas obsoletas y hacer un smoke del estilo activo. QA1/QA2 rechazan por ausencia del retiro; GitHub intacto.

### #1909 — QA1/QA2: campos `step` ocultos permanecen en forms

`SetupConfirmationForm` ya no existe, pero los tres formularios activos conservan `step = HiddenField(...)`; ningún route/template los lee o renderiza. El wizard sigue gobernado por `session["setup_step"]`, mantiene tres pasos y muestra CSRF. Retirar únicamente esos campos y preservar flujo y token. La cobertura actual prueba paso 3/sesión corrupta, no recorrido HTTP 1→2→3; las fixtures desactivan CSRF. QA1/QA2 rechazan por retiro pendiente. Sin cambios de producto/GitHub.

### #2071 — QA1/QA2 aprueban localmente el retiro

`_sum_query` fue eliminado en `d738bcdb` y no tiene referencias vigentes. El dashboard sigue operativo con agregaciones específicas; el inventario de dead code y pruebas de endpoint, permisos y KPI cubren la superficie restante. QA1/QA2 aprueban estáticamente. GitHub sin cambios de comentarios/etiquetas.

### #2079 — QA1/QA2: alias de campos v1 continúa sin consumidor

`_CHAIN_FIELDS = V1_FIELDS` todavía existe, pero no tiene consumidores. `_hash_fields()` usa `V1_FIELDS` para filas legacy y `_V2_FIELDS` con `id` para hashes actuales; el alias puede eliminarse sin cambiar ese contrato. QA1/QA2 rechazan por retiro ausente. Antes de confirmar, preservar mediante regresiones los formatos legacy v1 y actual v2, pues el test histórico ya no está en HEAD y los checks vigentes se centran en cadena nueva/topología. No hubo cambios en código/GitHub.

### #2203 — fix confirmado/cierre QA3 verificado

`transaction_form_js`/`transactionFormConfig` están ausentes desde `752486f1` (ancestro de HEAD); test estructural de consumidores está versionado. Leídos los cinco comentarios: QA1/QA2 aprobaron y QA3 autorizó `fixed` y cierre. No toqué GitHub.

### #1093 — QA1/QA2: falta la carrera de reembolso en PostgreSQL

El servicio bloquea y vuelve a leer la solicitud antes de crear el PaymentEntry, enlazarlo y marcarla reembolsada dentro de una sola transacción. La única prueba de doble reembolso fuerza el escritor SQLite con `BEGIN IMMEDIATE` y se omite en otros motores. El criterio más reciente exige una regresión real multi-sesión PostgreSQL: dos intentos para la misma reposición, exactamente un pago/nota contabilizado y un pointer, sin segundo efecto GL. QA1/QA2 rechazan hasta esa cobertura Tier 1. GitHub sin cambios.

### #1094 — QA1/QA2: reserva del mismo gasto carece de prueba PostgreSQL

`create_petty_cash_replenishment()` bloquea IDs ordenados con `FOR UPDATE`/`populate_existing`, revalida disponibilidad y confirma solicitud+asociaciones en una transacción; hay unicidad por gasto. La prueba concurrente actual usa fixture SQLite y puede pasar por `BEGIN IMMEDIATE`; no prueba la garantía Cloud del lock PostgreSQL. El comentario owner final exige dos sesiones PostgreSQL, una sola solicitud/asociación y no-persistencia/rollback de la perdedora. QA1/QA2 rechazan hasta esa regresión Tier 1; GitHub intacto.

### #1139 — QA1/QA2: falta regresión concurrente en PostgreSQL

El servicio obtiene un lock transaccional común de la factura (`DocumentFlowLock`), bloquea las líneas con `FOR UPDATE` y vuelve a calcular allocations antes de insertar. Sin embargo, `tests/test_purchase_invoice_receipt_allocation.py` fija SQLite y su prueba con `ThreadPoolExecutor` no fuerza el interleaving. El criterio del issue exige dos transacciones PostgreSQL independientes sobre recepciones distintas y una misma factura. Agregar esa regresión y comprobar tras ambos commits que el total activo no exceda la cantidad facturada. QA1/QA2 rechazan hasta cubrir PostgreSQL Tier 1. Sin cambios en código ni GitHub; no ejecuté pruebas ni linters.

### #1177 — QA1/QA2: cancelación de serial conserva estado incorrecto

Decisión vigente compartida con #1539: cancelar una recepción no equivale a entregar el serial. Debe quedar sin entrada activa, permitirse una recepción nueva si no hay otra entrada activa, y preservarse unicidad global y una sola ubicación. La salida comercial y devolución real conservan sus transiciones.

El código actual aplica `delivered` a la reversa negativa de una recepción; el reingreso normal rechaza el serial que solo tiene esa recepción anulada. Al cancelar una transferencia serializada, las dos reversas mutan la misma fila y el query no establece orden, por lo que el estado/warehouse puede terminar incorrecto. No hay pruebas específicas de estos recorridos. Corregir la derivación del estado desde evidencia activa y agregar pruebas de cancelación/re-recepción, serial activo duplicado, devolución y cancelación de transferencia con resultado independiente del orden de filas. QA1/QA2 rechazan. Sin cambios en código/GitHub; no ejecuté pruebas ni linters.

### #1178 — QA1/QA2: estado serial no serializa las salidas

`_validate_serial()` lee el estado del serial con SELECT ordinario, y `update_serial_state()` vuelve a leer y mutar sin `FOR UPDATE` ni compare-and-set. El lock de `StockBin` no serializa el serial. Dos sesiones pueden validar `available` y postear dos salidas; la unique del número protege solo la fila `SerialNumber`, no los movimientos. No hay regresión server-side de doble salida. Agregar lock/revalidación dentro de la transacción y prueba PostgreSQL multi-sesión con una salida exitosa, una rechazada y ausencia de salida duplicada. QA1/QA2 rechazan; sin cambios de código/GitHub, sin tests ni linters ejecutados.

### #1294 — QA1/QA2 aprueban localmente en `45e38f2b`

`record_external_number_used` está retirado desde `2d9d8848` y no tiene referencias según búsqueda estática. El histórico `tests/test_dead_code_inventory.py` no existe en el HEAD actual. La ruta productiva de registro conserva `ExternalNumberUsage` y `last_used`; el ajuste explícito exige razón y escribe auditoría. El test HTTP trackeado `tests/test_external_counter_edit_audit.py` cubre la edición que intenta modificar `last_used` y la operación auditada. Esto resuelve localmente la falta de test operativo que señaló QA3; GitHub permanece intacto, sin cambio de etiqueta. QA1/QA2 aprueban localmente; pendiente QA3.

### #1318 — QA1/QA2: retirada sin resolución de datos legacy

El helper `backfill_reconciliation_item_context()` y sus callers ya no están en el árbol. Sin embargo, `ReconciliationItem` aún declara las columnas legacy nullable para conservar datos previos y ordena migrar los registros sin contexto; el reporte y su prueba siguen detectando esos registros. Los fallbacks solo reconstruyen contexto mientras la transacción bancaria fuente exista, y no hay migración/comando alternativo ni prueba de que el almacén esté libre de filas antiguas. Antes de aprobar el retiro, documentar soporte/censo de datos o restaurar un backfill operativo. QA1/QA2 rechazan; GitHub intacto, sin cambios de código ni pruebas ejecutadas.

### #1683 — QA1/QA2: falta migración para esquema existente

La retirada de los cinco campos en `BaseTransaccion` y de `canceled`/`canceled_by` en `MUTABLE_STATE` está implementada, con una prueba de metadata ORM. Pero el único archivo Alembic actual es el baseline no-op; un esquema ya existente conserva físicamente esas columnas. El ADR posterior de #1898 exige una migración Alembic efectiva para cambios de columnas y pruebas sobre base existente, por encima del comentario previo que proponía omitirla por pre-alpha. Falta migración y prueba de upgrade. QA1/QA2 rechazan; GitHub intacto, sin cambios de código ni pruebas ejecutadas.

### #1733 — QA1/QA2 aprueban localmente en `45e38f2b`

La objeción de QA3 sobre test ausente no se reproduce en el HEAD local: `tests/test_external_counter_edit_audit.py` está trackeado. La prueba verifica que la edición POST no cambie `last_used` aunque se envíe un valor manipulado y que el ajuste separado sí cambie el valor junto con su auditoría. El formulario oculta el campo y el servicio no lo aplica. QA1/QA2 aprobaron de forma independiente; la etiqueta y GitHub permanecen intactos. La aceptación QA3 queda pendiente.

### #1751 — QA1/QA2 aprueban localmente en `45e38f2b`

La objeción QA3 de que faltaba la prueba en la rama remota no se reproduce en el HEAD local: `tests/test_import_landed_cost_creation_event.py` está trackeado. El servicio registra AuditTrail antes del único commit; el test hace POST real y consulta desde un contexto separado tanto el costo como exactamente un evento `created`. Rechazos anteriores dentro de la ruta revierten la sesión y el evento no se separa del documento. QA1/QA2 aprueban localmente; sin cambios de código/GitHub ni etiquetas y sin ejecutar tests/linters. Pendiente QA3.

### #1306 — QA1/QA2: doble salida serial aún posible

Los dos caminos de salida validan `SerialNumber` sin lock y solo después consumen con bloqueo de `StockBin`; luego actualizan el serial sin revalidarlo. Dos documentos concurrentes pueden usar el mismo serial aunque quede cantidad en la bodega. La clave única de `serial_no` no garantiza un único movimiento. Agregar transición protegida por `(item_code, serial_no)` en la transacción de posting y regresión de dos sesiones con una salida exitosa y la otra rechazada, sin duplicar ledger. QA1/QA2 rechazan; GitHub intacto, no ejecuté pruebas/linters ni cambié código.

### #1865 — QA1/QA2: el guard bloquea también cambios permitidos

El contrato vigente permite guardar si las relaciones activas y cantidades se conservan exactamente, y exige rechazar cambios o eliminación de líneas vinculadas. El código rechaza cualquier edición si hay una relación, incluida una modificación de solo cabecera; el test trackeado `test_stock_entry_linked_edit.py` espera ese rechazo. Agregar caso positivo de cabecera-only/vínculos intactos y conservar rollback para cambios de cantidad o eliminación de líneas relacionadas. QA1/QA2 rechazan; GitHub intacto, sin código ni pruebas ejecutadas.

### #1877 — QA1/QA2: falta validar posting autorizado real en Cloud

El test actual está trackeado en HEAD, pero simula un cambio ORM `docstatus=1` y updates de línea; no ejecuta `submit_document()`/`post_stock_entry()` ni sus savepoints. El listener concede autorización temporal ante cualquier transición draft→posted, en vez de exigir el posting autorizado, de modo que el test también revela un posible bypass del guard. No cubre rollback del nested savepoint. Vincular el permiso al posting autorizado y probar conciliación Cloud real, rollback y bloqueo posterior a commit. QA1/QA2 rechazan; sin cambios de código/GitHub ni tests ejecutados.

### #1987 — QA1/QA2: asociación append-only presente, migración ausente

La relación `PettyCashReplenishmentExpense` y su unicidad por gasto sí están implementadas, con pruebas de atomicidad/rollback/reintento y lectura del saldo. La tabla nueva carece de migración Alembic; el baseline es no-op, por lo que bases existentes no recibirán su esquema. Según el contrato aprobado #1898, agregar migración efectiva y prueba de upgrade de base existente. QA1/QA2 rechazan; el test está en HEAD local y no hubo cambios en GitHub.

### #2078 — QA1/QA2 aprueban localmente en `45e38f2b`

El test `tests/test_audit_chain_fail_closed.py` está trackeado en HEAD. La escritura ORM/Core rechaza el ciclo con puntero nulo o stale y no altera filas ni cabeza; la objeción QA3 por archivo remoto ausente no aplica al árbol local. QA1 reconsideró el caso adicional de raíz desconectada con cabeza terminal válida como endurecimiento fuera del criterio del issue; ambos revisores aprueban. GitHub y etiqueta intactos, sin tests/linters ejecutados.

### #1794 — falta regresión de atomicidad ante fallo

QA2 confirma que `log_create()` está antes del commit y la prueba HTTP existente consulta el landed cost y el evento en otro contexto. Aun así, esa prueba solo cubre éxito; no inyecta fallo de auditoría/commit y no prueba rollback del documento, sus líneas/cargos/enlace y el evento. El criterio del issue dice que si una parte falla ambas se revierten. Agregar un caso de fallo realista que compruebe desde una sesión nueva que no queda evidencia parcial; QA1 también rechaza; mantener la cobertura de rollback pendiente.

### #1854 — falta AuditTrail al duplicar StockEntry

QA1/QA2 rechazan: el endpoint duplica y confirma sin evento `created`, por lo que Desktop no muestra el evento en el timeline. No hay test específico. La decisión de #1893 también pide que origen sea una referencia informativa y que el duplicado no herede relaciones, estado ni evidencia contable, ni cree GL/stock. La ruta copia campos operativos/snapshot (cantidades y valores actuales/objetivo, diferencia, batch y serial); verificar y fijar el contrato al implementar.

### #1863 — faltan campos mutables en el snapshot de auditoría de StockEntry

QA1/QA2 rechazan: el snapshot registra propósito, compañía, fecha, observaciones y líneas, pero el handler modifica bodegas, cuenta de ajuste, dimensiones, monedas y total derivado. `log_update()` solo compara claves suministradas, así que esas ediciones no dejan before/after ni `changes_json`. Agregar cobertura de cambios de cabecera y total. La posible pérdida de valores iniciales por Alpine se mantiene como observación relacionada, separada del contrato del snapshot.

### #2137 — cobertura aún incompleta tras corrección de QA3

QA1/QA2 rechazan: aunque el test de auditoría existe en HEAD, no cubre enlaces de origen, no-cambio ni rollback. El snapshot omite `landed_cost_estimates_json` y no registra `DocumentRelation`; la factura de prueba no está enlazada a una fuente. Agregar los campos y escenarios del contrato, y comprobar que errores de guardado dejan documento, relaciones y AuditTrail intactos.

### #1779 — QA1/QA2 aprueban localmente

El guard rechaza retirar `group` mientras hay hijos y conserva la editabilidad del hijo; también impide cambiar compañía con hijos. Prueba HTTP verifica el estado preservado y edición del hijo; test de transacciones cubre serialización de cambios jerárquicos. QA1/QA2 coinciden en que el guard y la cobertura satisfacen el criterio. GitHub/etiquetas intactos.

### #1784 — la capitalización multimoneda sigue sin atomicidad

QA2 confirma que `submit_journal()` conserva su default `commit=True` en cada diario; si falla un diario posterior, ya se confirmó el anterior, los drafts generados y el vínculo de la fuente. El reintento salta esa fuente por `capitalized_by_id`. No hay regresiones de fallo multimoneda/reintento. Hacer una sola transacción por fuente, asociar toda la evidencia de forma coherente y verificar rollback completo + retry tras corregir tasa. QA1/QA2 rechazan independientemente.

### #1776 — pending persistente bloquea reintentos y puede dar check falso

QA1/QA2 rechazan. La primera aplicación se confirma como diario draft + application pending; al reintentar, el servicio la rechaza como duplicada y el wizard la incluye otra vez porque solo excluye `applied`. La ruta puede marcar el paso `passed` antes del posting del diario; los errores no identifican qué plantilla corregir. Cancelar plantilla no resuelve la application pending y el diario aún puede postearse. Hace falta recuperación idempotente de la evidencia ya creada, regla explícita para cancelación con pending, identificar plantilla fallida y que el check solo pase cuando todas hayan llegado al estado requerido. No hay pruebas del ciclo parcial/retry/cancelación.

### #2082 — falta regresión concurrente PostgreSQL

QA1/QA2 rechazan tras la devolución de QA3. El servicio tiene lock por caja/fecha, unique persistida y rollback/traducción de `IntegrityError`, pero la prueba actual es secuencial y comparte una sesión; no activa la carrera ni la defensa de unicidad. Agregar dos transacciones PostgreSQL reales que compitan por la misma caja/fecha, con una sola fila final, error controlado/no 500 para la perdedora y ausencia de estado parcial. QA2 coincide independientemente.

### #2084 — colisión de creación de numeración bancaria sin manejo controlado

QA1/QA2 rechazan. `_get_or_create_numbering_config()` hace read-then-add sin serialización; la restricción única conserva integridad, pero el endpoint no captura `IntegrityError`, así que una solicitud concurrente puede terminar en 500. Implementar bloqueo/upsert o rollback + lectura del registro ganador y respuesta controlada, cubriendo dos sesiones y la ruta HTTP.

### #2128 — faltan pruebas del límite User-Agent y error de creación

QA1/QA2 reevalúan y rechazan tras QA3. El código recorta User-Agent a 512 y hace rollback/mensaje genérico ante excepción en creación, pero no hay pruebas que envíen User-Agent largo y comprueben persistencia acotada, ni que provoquen fallo de creación y comprueben rollback + ausencia del detalle crudo en HTTP. Las pruebas de fallo SMTP cubren delivery, no creación. 
### #2129 — siguen abiertos tres casos de idempotencia/default

QA1/QA2 reevalúan y rechazan tras QA3: una serie global no-default existente no se recupera y puede colisionar; varios defaults legacy hacen fallar `scalar_one_or_none`; una serie local no-default se devuelve sin promover default ni crear la serie local requerida. La cobertura de bootstrap parte de esquema vacío y no reproduce estos estados heredados. Agregar pruebas por cada caso y manejar de forma segura los datos existentes.

### #2186 — concurrencia OTP no validada en PostgreSQL

QA1/QA2 rechazan tras QA3: la prueba de diez reclamos concurrentes está fijada a SQLite en archivo y no corre en job marcado `database`; no valida PostgreSQL aunque CI ejecute otras pruebas contra ese motor. El CAS SQL parece correcto, pero para el control de seguridad Tier 1 falta la misma carrera con conexiones PostgreSQL independientes que confirme exactamente cinco reclamaciones y el contador final.

### #2138 — la serialización del mapeo multilibro solo se prueba en SQLite

QA1/QA2 rechazan tras QA3. El servicio usa lock_default_scope y la prueba SQLite concurrente es discriminante, pero no verifica PostgreSQL Tier 1 donde el helper usa upsert + `FOR UPDATE`; la tabla no tiene unicidad de respaldo para esa identidad. Agregar variante `database` con dos conexiones PostgreSQL, destinos distintos, una sola creación/conflicto y exactamente una regla activa; conservar SQLite.

### #2187 — falta prueba PostgreSQL del lock de emisión de reset

QA1/QA2 rechazan tras QA3. El lock por usuario y la regresión de dos hilos parecen correctos, pero el test fuerza SQLite y no está marcado `database`; no demuestra el upsert/lock PostgreSQL de Cloud. Agregar el mismo interleaving con sesiones PostgreSQL separadas y mantener cobertura SQLite.

### #2187 — falta prueba PostgreSQL del lock de emisión de reset

QA1/QA2 rechazan tras QA3. El lock por usuario y la regresión de dos hilos parecen correctos, pero el test fuerza SQLite y no está marcado `database`; no demuestra el upsert/lock PostgreSQL de Cloud. Agregar el mismo interleaving con sesiones PostgreSQL separadas y mantener cobertura SQLite.

### #2188 — orden de locks puede producir deadlock en jerarquías

QA1/QA2 rechazan. El helper bloquea primero el nodo editado (`_hierarchy_company_codes`) y después la compañía; la caminata de validación bloquea otros nodos. Dos writers de la misma jerarquía pueden retener nodos distintos y esperar entre sí por Entity/nodo, provocando deadlock/`OperationalError` que los handlers no traducen a error controlado. La prueba actual inicia la segunda transacción después de la validación completa de la primera y no reproduce el interleaving. Reordenar globalmente: resolver anclas sin lock, bloquear compañías en orden, luego bloquear/recargar nodos y revalidar compañía; probar interleaving concurrente PostgreSQL con resultado controlado. `1401aad7` sí corrige snapshots MySQL RR, pero no este orden.

### #1730 — seed de RolesAccess duplica filas en bootstrap reintentado

QA1/QA2 rechazan. `cargar_permisos_predeterminados()` confirma cada permiso nuevo sin consultar la clave rol+módulo; la tabla solo tiene índice no único. Si se produce error después de commits parciales, `base_data()` se reintenta y duplica permisos. Implementar upsert/idempotencia y probar fallo parcial + retry con permisos/filas estables.

### #1910 — pruebas PostgreSQL desaparecidas del HEAD

QA1/QA2 rechazan: el archivo y fixture citados por issue/comentarios no existen en HEAD, ni aparece `TestConcurrenciaPostgreSQL`. El arreglo histórico de URL es ancestro, pero el reset `0970476b` eliminó las pruebas equivalentes. Los comentarios reportan fallo original de `str(URL)` redacted y una copia temporal que pasó tres escenarios, pero esa evidencia no está en la rama local. Restaurar harness funcional que preserve credenciales de forma segura y ejecute las tres carreras sobre PostgreSQL.

### #2076 — approve concurrente puede reabrir una solicitud rechazada

QA1/QA2 rechazan. Aunque approve/reject bloquean la fila, al perder el lock una aprobación puede no hallar pending y crear una nueva solicitud porque las rechazadas no cuentan como existentes; luego continúa y puede postear. Test actual solo verifica dos rechazos secuenciales. Corregir la rama de aprobación obsoleta para no recrear/reabrir y probar PostgreSQL approve-vs-reject: un estado/acción final, ninguna solicitud nueva ni GL/stock/side effects del perdedor.

### #1680 — falta comparación de versión observada por el formulario de OC

QA1/QA2 rechazan. `DocBase.version` no se incrementa ni se configura como versionado ORM; el form no envía versión. El POST recarga la orden por ID y luego aplica payload antiguo, reemplazando header y todas las líneas. Agregar token expected-version desde render hasta POST con compare atómico; el conflict debe preservar el estado reciente sin mutar relaciones, con prueba HTTP de dos lecturas/guardados.

### #1917 — falta regresión de éxito para verificar destino OTP

El código actual ya devuelve directamente el `Response` de `redireccion_despues_de_login()` y agrega la cookie de dispositivo a esa respuesta, corrigiendo la doble envoltura descrita. QA1/QA2 rechazan localmente porque no existe prueba HTTP de POST OTP exitoso que compruebe `Location`, cookie y estado autenticado; tampoco se cubre el destino predeterminado. Añadir ambos casos con OTP real del fixture o aislando únicamente generación/verificación, como pide el issue. Sin cambios de código ni GitHub.

### #1948 — la regresión del validador fue retirada del HEAD

La dependencia funcional sí está fijada en `requirements.txt` y se incluye vía `pyproject.toml`. QA1/QA2 rechazan porque `tests/test_email_validator_dependency.py` se eliminó en `0970476b`; no queda regresión de formato inválido y campo opcional vacío. Reponer casos representativos de validación del formulario/ruta con email válido, inválido y vacío opcional.

### #1965 — la regresión HTTP de hash corrupto fue retirada

`autenticar_usuario()` captura `InvalidHashError`, registra el ID y devuelve `None`; el login no revela el detalle. QA1/QA2 rechazan porque `tests/test_invalid_password_hash.py` se eliminó en `0970476b` y no hay caso equivalente con hash ilegible. Reponer la regresión HTTP que verifica respuesta controlada, sin sesión autenticada ni exposición del error.

### #2023 — recuperación sin cobertura de fallo SMTP ni commit posterior al envío

El rollback del envío fallido parece preservar el token anterior y descartar el recién generado; el mensaje sigue siendo genérico. QA1/QA2 rechazan porque no hay regresión HTTP de SMTP fallido con estado de tokens y respuesta. Además, SMTP puede aceptar el enlace y luego fallar el commit, dejando el token enviado no persistido e inaccesible. Añadir estado de correo/token durable o mecanismo recuperable equivalente y pruebas de éxito, fallo SMTP y fallo del commit posterior sin enumeración de usuarios.

### #1762 — persistencia HTTP de intentos sin regresión vigente

El endpoint ya confirma en la rama de código incorrecto y el helper consume el OTP al límite. QA1/QA2 rechazan porque el test HTTP histórico fue eliminado en `0970476b`; los tests actuales llaman el helper y confirman por sí mismos, sin cubrir la persistencia tras teardown del endpoint. Reponer prueba de POST repetido que revise el estado durable entre requests, consumo al límite y rechazo posterior.

### #1958 — faltan pruebas de commit fallido en entrega inicial y envío parcial

El código persiste `pending` antes de SMTP por destinatario y tiene fallback a estado `failed` si falla el commit del resultado. QA1/QA2 rechazan porque la prueba de commit fallido ejercita solo retry administrativo; no verifica fallo tras SMTP en el envío inicial. No hay regresión multi-destinatario con un mensaje aceptado y otro fallido ni estados independientes/respuesta parcial. Agregar ambas regresiones sobre el flujo inicial.

### #1758 — falta probar la propagación histórica hacia el posting

La decisión de producto sobre prorratear por peso/volumen ya está aprobada. La implementación almacena las dimensiones por línea y las copia desde filas persistidas a `ItemContext`; el engine calcula la asignación. QA1/QA2 rechazan porque los tests separan cálculo con `ItemContext` manual de persistencia, sin verificar que el builder real propague las dimensiones históricas al posting. Añadir regresión integrada por el consumidor real que pruebe la distribución derivada de líneas persistidas para peso y volumen.

### #2077 — falta regresión multipart positiva del consumidor HTTP activo

QA1 aprueba las pruebas restauradas del servicio: validación de contenido, almacenamiento/hash, rollback/limpieza, reemplazo y borrado pendiente auditado. QA2 rechaza por falta de POST multipart válido a `/api/attachments/<type>/<id>/upload`; el test del pipeline invoca `upload_attachment()` directamente, así una regresión del endpoint que no lo conecte puede pasar. Agregar una prueba HTTP positiva del consumidor activo y conservar las pruebas de rollback/cleanup. QA2 observó también que la migración de `File.sha256` pertenece al contrato de #1898: no confundir esa dependencia con la cobertura específica de #2077.

### #1891 — duplicar historial legacy recrea ajuste genérico

La decisión aprobada es solo ajustes positivos/negativos con histórico consultable. Aunque el alta normal rechaza `stock_adjustment`, `POST /stock-entry/<id>/duplicate` copia sin validación el propósito del registro histórico a un nuevo draft. El test de contrato actual no cubre este endpoint. QA1/QA2 rechazan independientemente; denegar duplicación para `stock_adjustment` legacy y agregar regresión HTTP con ninguna fila nueva, preservando el detalle histórico.

### #1938 — preferencias de vista sin restauración y tabla sin migración

QA1/QA2 rechazan tras revisión independiente. RBAC/aislamiento por usuario-compañía-reporte están presentes y el test CRUD local está trackeado. Pero `show_users` y `advanced` se guardan en `display_json` y al cargar vista nunca se aplican; renderer/plantilla consultan los query args actuales. Los tests no fijan ese comportamiento. Además, `saved_report_view` carece de migración Alembic efectiva pese al contrato #1898; bases existentes no inicializadas con create_all carecen de la tabla. Integrar esas preferencias en el estado efectivo del reporte y añadir regresiones de restauración; crear migración versionada con verificación de upgrade existente.

### #1973 — la prueba solo inspecciona una llamada por plantilla

El código actual está limpio: `transaction_grid` conserva `source_api_url` y `title`, y los callsites no pasan los cuatro args retirados. QA1/QA2 rechazan porque `_argumentos_de_llamada()` usa `.search()` y el test revisa solo la primera llamada en cada template; varios templates invocan la macro 2–4 veces y no están entre los render HTTP de humo. Una reintroducción del argumento en llamada posterior no haría fallar las pruebas. Iterar cada match/invocación y cubrir templates con varias llamadas.

### #1916 — falta completar retiro de esquema

QA1 y QA2 rechazan independientemente en HEAD `45e38f2b`. El retiro de modelos/consumidores ya está aplicado y la decisión pre-alpha permite eliminar estos datos; `WORKFLOW_STATE_ID` sigue como constante huérfana. Falta una migración Alembic activa que retire las tablas de workflow de bases existentes: `20261109_0003_drop_workflow.py` fue eliminada por `41c7af1e` y el baseline actual es no-op. Conforme al contrato aprobado en #1898, quitar la constante y entregar migración efectiva para las cinco tablas, con precondiciones/orden dependencial; después validar upgrade real y repetición en Tier 1. No cambiar etiquetas ni ejecutar tests/linters durante esta revisión estática.

### #1492 — cubrir también el guard de balance agregado

El test restaurado sí está presente localmente y el caso de aprobación legacy con ambas líneas debit/credit preserva totales iguales, así que distingue el guard por línea que motivó el issue. QA1 aprueba; QA2 rechaza porque no existe una regresión con lados válidos por línea y suma debit/credit desigual. El caso de creación dual-positive también viola la suma global; el caso de aplicación legacy termina con suma desigual. Si se quitara el guard agregado actual, ninguna prueba fija ese contrato de que una plantilla y su diario sean posteables/balanceados. Agregar un caso desbalanceado con líneas de un solo lado tanto en creación como en revalidación persistida según corresponda; reiniciar QA1 → QA2. QA3 reportó que el archivo no estaba en origin, pero sí está trackeado en HEAD local. Sin tests/linters en esta revisión estática.

### #1493 — idempotencia no contempla aplicaciones revertidas

QA1/QA2 rechazan independientemente en HEAD `45e38f2b`. Frecuencia mensual exclusiva, rechazo de frecuencias heredadas y aplicaciones de varias plantillas por período están implementados y probados. Falta repetir la misma ocurrencia. El guard en `apply_recurring_template()` bloquea `pending`/`applied`, pero `journal_service._reverse_recurring_application()` cambia a `reversed`; el retry pasa el guard e intenta crear otra fila con la misma clave única, propagando `IntegrityError` (el cierre solo captura `RecurringJournalError`). `failed` heredado tiene el mismo camino. Cubrir reintento y definir una respuesta controlada para todo registro existente de esa ocurrencia, incluida reversión, sin journal o aplicación duplicados. GitHub/etiquetas sin cambios; revisión estática, sin tests/linters.

### #1564 — los dashboards aún recortan los nueve listados

QA1/QA2 rechazan en HEAD `45e38f2b`. Cliente limita 4 listas y proveedor 5 a 100 filas, sin `page`, continuidad ni total aparte; las plantillas iteran esa única tanda y `|length` alimenta los badges. Los documentos 101+ quedan inaccesibles y el conteo es engañoso. No hay regresiones actuales de ambos dashboards. Añadir paginación navegable y conteos completos para cada lista, preservando el scope de compañía/tercero y solo documentos publicados; probar ambas vistas con más de 100 elementos y navegar desde la página 1 a la siguiente. GitHub/etiquetas intactos; QA estático, sin tests/linters.

### #1737 — alta y edición aceptan UOM operativa no convertible

QA1/QA2 rechazan independientemente en HEAD `45e38f2b`. `validate_item_uom_rows()` solo valida UOM base y filas adicionales. `create_item_with_uoms()` y `update_item_with_uoms()` escriben `purchase_uom`/`sale_uom` sin exigir que correspondan a la UOM base o a una conversión del artículo. Una selección válida del catálogo global puede quedar guardada y luego fallar al convertir cantidades de compras/ventas. Las pruebas actuales cubren factores, no esa relación ni no-mutación en creación/edición. Agregar validación compartida antes de persistir y regresiones de unidad base, conversiones válidas e inválidas para ambos campos y ambos caminos. GitHub/etiquetas intactos; no tests/linters en QA.

### #1752 — el botón Editar sigue creando un documento nuevo

QA1/QA2 rechazan independientemente en HEAD `45e38f2b`. El botón pasa `landed_cost_id`, pero la ruta new ignora el parámetro y procesa el POST por `_create_import_landed_cost_from_request()`, que siempre añade/commitea otro costo. No hay GET/POST de edición ni prueba que fije la identidad. Implementar el update del mismo draft con scope/ACL y `docstatus` correcto, actualizando cabecera/líneas/cargos bajo la unidad transaccional, o retirar el enlace si no está soportado. Agregar regresión HTTP que compruebe que el ID se conserva y no se crea otra fila. GitHub/etiquetas intactos; sin tests/linters en esta revisión.

### #1758 — respetar regla aprobada; faltan migración y prueba integrada

La decisión de producto de mantener prorrateo por peso/volumen está aprobada y no se reabre. QA1/QA2 rechazan por dos asuntos técnicos: (1) prueba de persistencia y prueba de motor usan caminos aislados; falta recuperar dimensiones guardadas desde landed-cost lines, construir el contexto con el builder real y verificar la asignación por peso/volumen; (2) `Item` y `ImportLandedCostItem` agregan cuatro campos dimensionales, pero no existe migración Alembic efectiva en el árbol actual, necesaria para bases existentes según #1898. Código de validación, persistencia y propagación actual parece correcto. No tratar ausencia del test en origin como cierta: está trackeado en HEAD local. GitHub/etiquetas intactos; revisión sin tests/linters.

### #1811 — creación por formulario sigue sin poder enviar moneda

QA1/QA2 rechazan localmente. El informe histórico de 500 está superado: ahora la ruta revierte y re-renderiza formulario con error controlado. La causa original persiste: la plantilla activa de conciliación no contiene `currency`/`transaction_currency`, pero servicio lo exige, así que el flujo normal nunca persiste una conciliación. Los tests de ruta introducen `transaction_currency=NIO` directamente; no prueban el formulario servido. Agregar selección/provisión explícita y validada de moneda, prueba HTTP de creación exitosa del formulario y caso de moneda ausente con error controlado y cero mutación. GitHub/etiquetas intactos; QA estático sin tests/linters.

### #1813 — bypass 3-way cuando `require_sales_order=False`

QA1/QA2 rechazan independientemente la implementación local `94043df4` en HEAD `45e38f2b`. La regla se ejecuta si factura ya tiene una orden; en 3-way con `require_sales_order=False`, factura sin OV/DN cae por retorno temprano y pasa sin referencias. El submit real llama al helper, así que puede aprobar factura incompleta. La regresión actual llama helper directamente con factura enlazada a OV y cubre DN faltante, pero no flag falso/sin fuentes ni endpoint HTTP. Hacer que `matching_type=3-way` exija ambas referencias con independencia de ese flag y agregar POST de submit que no postee ni cree GL al faltar OV/DN; mantener semántica 2-way. GitHub/etiquetas intactos, sin tests/linters QA.

### #1888 — campos editables del detalle siguen sin contrato persistente

La decisión funcional nueva cierra la antigua duda de alcance: integrar centro de costo/proyecto por línea y `remarks` bajo #1359; ocultar/rechazar cuenta arbitraria; retirar UI/payload fiscal y rechazar payloads no soportados. QA1 local rechaza en HEAD `45e38f2b` porque el contrato no está implementado: `StockEntryItem` carece de columnas, el writer no lee dimensiones/notas, el renderer de edición no las recupera y el macro activo aún emite campos genéricos de cuenta/dimensiones/remarks e impuestos. Por tanto, el flujo descarta silenciosamente entradas y no alcanza el comportamiento aprobado.

Completar persistencia y readback por línea con validación de compañía/estado/RBAC conforme al contrato común; propagar las dimensiones a los GL correspondientes en todos los libros y exponer la consulta sin duplicar importes. Configurar el macro por consumidor: en StockEntry no mostrar cuenta ni controles fiscales, ni serializar payloads fiscales; rechazar en servidor campos no soportados. Cubrir varias líneas, dimensiones distintas, herencia/precedencia según #1359/#1340, aislamiento, posting/reversión, no mutación de cantidades/importes y compatibilidad de los otros consumidores del macro. Sin pruebas/linters en revisión QA; issue y etiquetas sin cambios.

### #1891 — duplicar el histórico reabre creación genérica

La decisión aprobada conserva solo ajustes positivos/negativos y la consulta de registros genéricos antiguos. Aunque `tests/test_stock_adjustment_contract.py` está presente en HEAD local (la observación QA3 de ausencia en GitHub está desactualizada para este árbol), QA1 rechaza por un bypass no cubierto: `inventario/routes.py:1031-1058` duplica cualquier documento no cancelado y copia sin validar `origen.purpose`. Duplicar `stock_adjustment` genera un borrador genérico nuevo; el endpoint de submit todavía tiene ramas que admiten ese propósito (`routes.py:1117-1129`). Esto convierte una vista histórica en creación y posting de un propósito retirado.

Bloquear duplicación de `stock_adjustment` en ruta/servicio con respuesta controlada; conservar la consulta histórica y duplicación de propósitos vigentes. Agregar prueba funcional que cree fila histórica, intente duplicarla por HTTP y confirme que no aparece borrador ni asiento adicional. El test actual cubre altas directas e historial pero no esta ruta alternativa. Sin pruebas/linters en revisión QA; GitHub y etiquetas intactos.

QA2 revisó #1888 de forma independiente y coincide con el rechazo: además de las columnas/writer/renderer ausentes, `transaction_form_macros.html` presenta siempre controles genéricos y pricing fiscal, y `transaction-form.js` clasifica `stock_entry` para preview fiscal. Los guards y posting actuales solo tienen dimensiones de cabecera, no datos de detalle que propagar a GL. Los tests de macros existentes verifican presencia de consumidores y respuesta HTTP, no persistencia/rechazo funcional del contrato de #1888. Sin cambios en issue/etiquetas.

QA2 revisó #1891 independientemente y confirma el mismo bypass. El botón de duplicado se ofrece a documentos no cancelados; la ruta copia el propósito y commitea el borrador, mientras submit y posting aún manejan `stock_adjustment`. No es un mero defecto de consulta ni una prueba ausente: puede originar nuevo efecto de inventario/GL contrario a la decisión de solo ajustes positivos/negativos. Bloquear duplicación genérica y cubrirla por HTTP. QA1/QA2 concuerdan; no se tocaron GitHub/etiquetas.

### #1992 — los selectores de serie de caja chica no llegan al identificador

La decisión reciente ya exige honrar la serie válida en vale/gasto/reposición, usar default solo si no se elige ninguna y rechazar selección inválida/inactiva/ajena/de otro tipo. QA1 local rechaza: la ruta del vale no pasa `naming_series` aunque el servicio acepta `naming_series_id`; la ruta de gasto no lo pasa y su servicio no expone parámetro; reposición tiene selector pero ni ruta ni servicio lo reciben. Los tres asignan el default con `naming_series_id=None`. No hay pruebas funcionales de esa selección para los tres flujos.

Hallazgo límite: los servicios capturan `IdentifierConfigurationError` de forma genérica como numeración opcional. Bajo el contrato explícito, una selección inválida no debe terminar en documento sin número/serie; separar ausencia opcional de selección inválida y asegurar rollback sin consumir el contador equivocado. Añadir cobertura HTTP por vale, gasto y reposición para selección válida, omitida y series inactivas/de otra compañía/tipo, comprobando identidad de serie, número y contadores. Revisión estática; no tocar GitHub ni etiquetas.

QA2 revisó #1992 por separado y confirma el rechazo: vale, gasto y reposición ignoran la serie visible, usan default y consumen su contador; el guard del helper no ayuda mientras los consumidores no pasan el ID. También confirma que los errores explícitos de configuración se silencian y no hay cobertura para estados inválidos/contador. QA1/QA2 concordantes; issue/etiquetas intactos.

### #2061 — falta regresión del entry point Waitress

El criterio aprobado (#6711996661) pide ambos entry points, no-dev sin creación de admin y desarrollo autorizado. El código actual invoca el resolver en `__main__.py:45` y `server.py:43`; la cobertura versionada `test_module_entrypoint_credentials.py` solo ejercita `inicializar_si_hace_falta()` de `__main__` y no prueba `server.server()` ni que Waitress no arranque en rechazo. QA1 rechaza por falta de cobertura explícita del segundo flujo y del modo dev desde el entrypoint; agregar pruebas sin abrir sockets/parcheando el servicio, con assertion sobre no creación de usuario/serve en no-dev y arranque autorizado en dev. Sin tests/linters en QA.

### #2062 — decidir comportamiento antes de corregir

El DELETE de `/settings/default-accounts` aún llama `session.delete()` y commit sin manejo del guard; `CompanyDefaultAccount` está en `SENSITIVE_MODELS`, donde `_guard_sensitive_delete()` rechaza borrado directo. La acción UI sigue visible. El propio issue requiere decidir entre borrado auditado, inactivar/limpiar mediante operación permitida o retirar la acción; no hay decisión aprobada en sus comentarios recientes. Conforme a AGENTS, no inferir política de negocio desde QA. Dejar alcance pendiente hasta decisión explícita, sin cambiar etiquetas.

Corrección de análisis #2061 tras contrastar `verifica_coneccion_db()`: no es solo cobertura faltante. La función ejecuta `select(User)` y decide que DB está disponible por la truthiness del objeto `Result`, sin comprobar filas (`database/helpers.py:47-59`). Con esquema conectado pero sin usuarios, `server()` omite el resolver en su rama positiva y arranca Waitress; el guard solo se ejecuta si falla conexión (`server.py:34-59`). QA1/QA2 rechazan. Hacer que el guard de credenciales/admin aplique antes de servir Waitress y diferenciar conectividad de presencia de usuario; cubrir DB accesible sin usuarios, rechazo no-dev sin bootstrap/serve y desarrollo explícito autorizado.

### #2060 — badge de compañía aún cuenta solicitudes no aprobables

El filtro por `authorized_company_codes()` corrige el cross-company, pero no satisface el criterio vigente de solicitudes visibles para el usuario. El listado carga pendientes y `_pending_approval_info()` aplica `ApprovalEngine.can_approve()`; este también revisa permiso del módulo, independencia y regla/nivel. Las operaciones especiales usan `review_is_allowed()`. `pending_approval_count()` solo cuenta dos estados por compañía, sin esos guards, por lo que puede incluir solicitudes de la propia compañía que la lista oculta. La prueba actual fija solo compañía propia/ajena/sin compañías/admin; QA3 marcó explícitamente el caso faltante.

QA1 rechaza la re-revisión local. Cubrir dos solicitudes en la misma compañía, una visible/aprobable y otra no, y asegurar paridad exacta del badge con la bandeja para permisos normales y revisiones especiales, manteniendo company scope. Sin pruebas/linters ni cambios de GitHub.

QA2 confirma el rechazo independiente y precisa ambos errores: además de contar solicitudes same-company que fallan `can_approve`, el badge usa el alcance de `accounting` por defecto y puede omitir solicitudes válidas para un aprobador con permisos del módulo O2C/S2P/CTM pero sin accounting. `REVIEW_TYPES` también usa `review_is_allowed`/permiso por módulo. Compartir o equivaler la predicate del inbox es necesario; solo filtrar por compañía no alcanza. QA1/QA2 concordantes; etiquetas intactas.

### #1433 — el precheck deja ampliar grupos históricos ambiguos

QA1 re-rechaza en HEAD `45e38f2b`, coincidiendo con el QA3 vigente. El backfill conserva `supplier_invoice_key=NULL` cuando hay facturas activas históricas duplicadas. El precheck solo busca la clave normalizada poblada; por eso no detecta esas filas activas heredadas y un alta nueva del mismo proveedor/número puede crear un tercer registro del mismo número. El índice único tampoco bloquea el caso, pues sus claves continúan `NULL`.

Mantener la evidencia histórica sin alterarla, pero consultar también números activos legados con key NULL comparando su `supplier_invoice_no.strip()` con el valor entrante. Añadir un caso integrado con dos duplicados históricos NULL y un tercer intento; verificar `DUPLICATE_INVOICE` antes de insertar y no alterar las filas heredadas. Las pruebas existentes cubren por separado la key normalizada y el backfill, no este escenario combinado. Revisión estática sin tests/linters; GitHub/etiquetas intactos.

QA2 confirma por separado que alta y edición usan el mismo guard incompleto. SQL permite múltiples NULL en la clave única; el nuevo registro será el primero con clave poblada y no colisiona con las dos filas legacy NULL, por lo que el tercer duplicado realmente persiste. QA1/QA2 independientes rechazan. Ampliar la cobertura del fallback de key NULL para alta y edición, incluido proveedor global entre compañías; conservar filas históricas sin mutación.
