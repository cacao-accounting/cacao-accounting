# QA1 — #1432 y hallazgo QA3 de #2140

## #1432 — `9a6230d8`

**Veredicto: rechazado; conservar `needs-work`.** La implementación serializa `open_negotiation_round()`, `create_purchase_quotation_award()` y `close_purchase_quotation_comparison()` con `lock_default_scope("purchase_quotation_award", rfq.id)`, y las tres consultan el estado terminal `closed`. Las rutas POST de ronda, adjudicación y cierre capturan `PurchaseSourcingError` y hacen rollback. El índice único se conserva; `_flush_award()` usa savepoint, traduce el conflicto de esa unicidad y vuelve a elevar otros `IntegrityError`. La cadena nueva está marcada con `_()` y tiene traducción inglesa.

Falta cobertura de regresión para dos contratos pedidos: no hay prueba de que llamar `close_purchase_quotation_comparison()` de nuevo tras el cierre falle sin crear otra fila, ni de que un `IntegrityError` ajeno a `uq_purchase_quotation_award_quotation` se propague en vez de convertirse a error de dominio. Las pruebas actuales cubren abrir ronda y adjudicar después del cierre por servicio/POST, y un conflicto real de la unique guard; no ejercitan esas dos ramas.

## #2140 — hallazgo QA3, alcance limitado

El commit incorpora el guard terminal que faltaba en el hallazgo QA3 de #2140 para apertura de ronda, adjudicación y cierre manual. No concluyo sobre los demás hallazgos del umbrella. La brecha de regresión de cierre repetido descrita arriba impide confirmar todavía el residual de #1432.

Revisión estática; no ejecuté pruebas ni linters.

---

# QA1 re-review — commits `9a6230d8` + `45e38f2b`

## #1432

**Veredicto: aprobado; mover a `fix-proposed`.** El guard de `closed` se aplica a abrir ronda, adjudicar y cerrar manualmente bajo el mismo lock. Las pruebas previas cubren servicio y POST para abrir ronda/adjudicar tras el cierre; `test_repeated_manual_close_preserves_the_single_close_record` ahora confirma que el segundo cierre no agrega ni reescribe el único award y conserva `authorization_reason`. `test_unrelated_integrity_error_is_not_translated_as_award_collision` provoca un NOT NULL real en `PurchaseQuotationAward.company` y comprueba que `IntegrityError` se propaga y el savepoint deja activa la sesión. `test_award_unique_collision_is_translated_to_closed_domain_error` cubre el conflicto real de la unique guard convertido a `PurchaseSourcingError`. El modelo conserva `uq_purchase_quotation_award_quotation`, la regresión concurrente existente sigue usando el mismo lock, y la nueva cadena está internacionalizada.

## #2140

El residual QA3 de #1432 queda cubierto por guardas y regresiones. Esta revisión no evalúa ni declara listos los demás hallazgos del umbrella; #2140 permanece `needs-work`.

Revisión estática; no ejecuté pruebas ni linters.

## QA2 estática independiente — #1432 / commits `9a6230d8` + `45e38f2b`

**Veredicto: aprobado; mover #1432 a `fix-confirmed`.** Leí el cuerpo y los seis comentarios completos de #1432, y el cuerpo y los nueve comentarios de #2140, incluido el residual QA3. Revisé de nuevo servicio, rutas, modelo, cambios y regresiones actuales, sin ejecutar pruebas ni linters.

`open_negotiation_round()`, `create_purchase_quotation_award()` y `close_purchase_quotation_comparison()` toman el mismo lock `purchase_quotation_award` por ID de RFQ y consultan los estados terminales `finalized`, `used` y `closed` antes de mutar rondas o insertar evidencia. Así el cierre manual bloquea tanto nueva ronda como adjudicación; el cierre repetido se rechaza antes de generar otro award o cambiar la razón guardada. El modelo conserva la unique constraint `uq_purchase_quotation_award_quotation` como defensa ante carreras/históricos. Las rutas POST de ronda y adjudicación capturan `PurchaseSourcingError`/`SQLAlchemyError`, hacen rollback y muestran el rechazo; regresiones autenticadas con admin confirman el mensaje y que siguen existiendo una sola evidencia `closed` y ninguna ronda nueva.

`_flush_award()` persiste el trabajo previo antes de abrir un savepoint para insertar el award. Solo traduce la constraint `uq_purchase_quotation_award_quotation` (diagnóstico PostgreSQL o mensaje específico de SQLite); otros `IntegrityError` se propagan. Las pruebas provocan el conflicto único real y una violación NOT NULL distinta dentro del savepoint, y comprueban que la sesión exterior sigue activa. El test de cierre repetido verifica que no se crea otra fila y que `authorization_reason` original no se reescribe. El test de concurrencia preexistente de #2140 confirma que una adjudicación concurrente espera el mismo lock y no crea un segundo award. La cadena de dominio se envuelve con `_()` y su traducción inglesa está en `messages.po`/`.mo`.

### Seguimiento acotado — #2140

El residual QA3 relacionado con cierre manual de #1432 queda cubierto por estos guards y pruebas. Esto no reevalúa ni promueve los demás hallazgos del umbrella #2140, que permanece abierto y `needs-work`.

### Revisión estática vigente — residual #1432 en #2140 (HEAD `45e38f2b`)

QA1 y QA2 aprueban el residual de cierre manual que QA3 devolvió. El diff local de `9a6230d8` y `45e38f2b` trata `closed` como terminal bajo el mismo lock de RFQ para abrir ronda, adjudicar y cerrar de nuevo; el cierre repetido preserva el registro y su justificación. `_flush_award()` traduce únicamente la colisión de la restricción única y deja propagar un `IntegrityError` ajeno. Las regresiones vigentes cubren servicio, POST, cierre repetido, ambos errores de integridad y concurrencia de awards. La inspección de `d5a12cbd`/`fde435c4` y los comentarios previos de QA2 mantiene aprobados los otros seis hallazgos del paraguas. No se ejecutaron pruebas/linters ni se modificó GitHub; no se cambió ninguna etiqueta. El estado queda para QA3 autorizado o administrador.

---

# Contexto de revisión recuperado — ronda #1658 y #1385

> Recuperación parcial reconstruida después de una sustitución accidental de las bitácoras locales. No reemplaza los comentarios de GitHub como fuente de verdad. La sección QA2 extensa perdida no está disponible en el filesystem.

## #1385 — cierre del hijo bancario

- Commit `b029e73d` agrega cobertura funcional CSV por `ImportService.validate()`/`execute()`: referencia informativa compartida con importes distintos, duplicado intra-lote y repetición entre lotes.
- QA1 independiente aprobó `b029e73d`: `row_N` es localizador inequívoco, referencia preservada como `reference_number`, alias `reference` aceptado por decisión expresa.
- QA2 independiente aprobó y comentó el issue. El cuerpo y los comentarios completos de #1385 y #1652 se revisaron. El issue sigue abierto; la etiqueta actual reportada por GitHub es `fixed`.

## #1658 — QA/estado local anterior (sujeto a revalidación de comentarios actuales)

La revisión local anterior registró QA1/QA2 aprobado para #1758, #1891, #1930, #1973, #1938, #2077 y #1915. También registró que #1891 y #1973 habían regresado a `needs-work` tras QA3 por falta de pruebas visibles en la rama remota, pese a tests en el árbol local. La consulta actual a GitHub muestra `needs-work` para los siete issues, por lo que esos veredictos históricos no deben usarse como estado vigente; revisar comentarios recientes de cada issue antes de retomar.

Evidencias de la ronda anterior conservadas en el contexto: #1758 cubría decimales landed cost; #1891 ajuste de stock genérico retirado y consulta de histórico; #1930 parámetros PDF y errores HTTP; #1973 retiro de cuatro argumentos `transaction_grid()`; #1938 vistas guardadas y rollback de colisión; #2077 regresiones del pipeline de adjuntos; #1915 retiro de `base.ods` y carga CSV. Tests dirigidos previos reportados pasaron, pero no se vuelven a atribuir como ejecución de esta ronda.

## Verificaciones de esta reanudación

- #1385: `tests/test_bank_transaction_identity_uniqueness.py` + `tests/imports/test_bank_statement_reference_grouping.py`: 10 passed, 1 skipped; Black/Ruff/Flake8/pydocstyle/Pylint/complexipy pasan.
- #1432: suite de autorización sourcing + concurrencia de awards + unique: 27 passed; Black/Ruff/Flake8/pydocstyle/Pylint/complexipy/Babel pasan.
- Mypy no pudo iniciar en `.venv`: `ModuleNotFoundError: pathspec.patterns.gitignore`; esta limitación del entorno queda pendiente de corregir antes de una aceptación con controles completos.
- Commits locales: `b029e73d`, `9a6230d8`, `45e38f2b`. No se hizo push ni se cerraron issues.

# QA local — #1652, diff sin commit (2026-11-21)

**Decisión: rechazado; necesita correcciones antes de QA1.** Revisión estática del diff local en `estabilizacion`; no ejecuté pruebas ni linters y no publiqué comentarios ni cambié etiquetas en GitHub.

## Hallazgos bloqueantes

1. **El contrato no cubre los lectores productivos paralelos señalados en la bitácora.** El diff adapta los cuatro readers de `cacao_accounting/imports/readers/`, pero deja intactos `contabilidad/budget_import_service.py`, `contabilidad/exchange_rate_import_service.py` y `api/line_import.py`. Los comentarios vigentes de #1652 identifican allí divergencia de BOM, expansión ODS, materialización XLS/XLSX y el `list(worksheet.iter_rows())` previo al límite de 500 filas (`api/line_import.py:319-338`). El criterio del issue dice seis lectores y las reproducciones de #1652 sitúan los fallos precisamente antes del límite o en lectores paralelos; por tanto, el contrato nuevo no cubre todavía el alcance documentado y persiste materialización excesiva en una ruta activa.

2. **La equivalencia multi-formato no valida una fecha Excel tipada en XLS.** `tests/imports/test_readers_contract.py:93-98` escribe `posting_date` como texto en BIFF2. En producción `XLSReader.read()` usa `ws.cell_value()` sin consultar `cell_type`/`datemode` (`cacao_accounting/imports/readers/xls_reader.py:43-46`), así que una fecha Excel con formato de fecha llega como serial numérico; `TabularBook.normalize_cell_value()` solo normaliza objetos `date`/`datetime` (`readers/base.py:20-23`) y la fixture pasa sin probar ese caso. Esto permite que CSV/XLS/ODS/XLSX sigan devolviendo valores distintos para los mismos datos lógicos, criterio central de #1652.

3. **Falta cobertura discriminante del límite previo a expansión en consumidores que no usan `ReadBudget`.** La batería nueva solo ejercita tablas de una fila; no comprueba el criterio de aplicar límites antes de expandir filas/celdas. Los comentarios vigentes reproducen expansiones ODS (`number-rows-repeated` y `number-columns-repeated`), y `api/line_import.py:325` materializa la hoja completa antes de comprobar 500 filas en `_canonical_xlsx_rows()`. El contrato/fixture común no protege esos caminos.

## Evidencia favorable, de alcance acotado

- En los cuatro readers de `imports/readers`, `TabularBook` centraliza BOM inicial de encabezado y coerción textual; los iteradores CSV/XLSX y el parser SAX ODS limitan antes de añadir cada fila. El servicio ya detecta `UNKNOWN_COLUMN` y duplicados.
- La compatibilidad `NormalizedTable = TabularBook` evita romper importadores/pruebas antiguos mientras sigan existiendo consumidores con el nombre previo.
- No se deriva aprobación del resultado de las pruebas ya reportado antes de esta revisión; por instrucción del rol QA, esta evaluación es estática.

**Acción requerida al implementador:** ampliar el contrato a los consumidores paralelos activos que #1652 ya enumera, convertir fecha XLS desde el valor tipado y agregar regresiones que fallen si el límite se aplica después de expandir/materializar. Después reiniciar QA1 → QA2. Sin cambios de estado, etiqueta, comentarios, commit ni push en esta revisión.

**Corroboración QA2 independiente del diff vigente:** confirma además que `JournalEntryAdapter.column_aliases` reasigna `reference` a `document_ref`, aunque la plantilla inglesa genera `reference` para la columna distinta `referencia`. Al canonizar una plantilla válida, `reference` y `document_reference` colisionan en `document_ref` y producen `DUPLICATE_COLUMN`; no hay regresión del adaptador inglés. QA1 y QA2 rechazan este cambio local. Se mantienen también los bloqueos de alcance y fechas/límites señalados arriba; sin cambios de código ni GitHub.

# QA local de reevaluación — #1765 (HEAD `45e38f2b`)

**Resultado: el hallazgo de cobertura citado por QA3 ya no se reproduce en el árbol actual.** Revisión estática; no ejecuté pruebas ni linters y no cambié etiquetas ni publiqué comentarios.

- El test que QA3 reportó ausente existe en `tests/test_exchange_rate_import_errors.py` y está incluido en el historial actual (`8e2fcc44`). Incluye prueba del parser con bytes UTF-8 inválidos y POST autenticado que comprueba respuesta 200, mensaje de validación y conteo de tasas sin cambios.
- `ExchangeRateImportService._parse_csv()` envuelve `UnicodeDecodeError` como `ExchangeRateImportError`; `importar_tasas_cambio()` captura ese error de dominio y vuelve a renderizar el formulario. El error ocurre durante el parseo antes de insertar tasas.
- Esta verificación estática resuelve solo el motivo de rechazo documentado por QA3 (#1765); no altera el estado del issue en GitHub ni sustituye una evaluación autorizada de cierre.

### Revisión estática de QA2 — #1765

QA2 confirma que el caso HTTP exigido por QA3 está versionado en `tests/test_exchange_rate_import_errors.py`: la ruta muestra el error de decodificación y verifica que el número de tasas persistidas no cambia. `ExchangeRateImportService._parse_csv()` convierte `UnicodeDecodeError` a `ExchangeRateImportError`, manejado por la ruta. No se ejecutaron pruebas/linters ni se modificó el estado remoto o la etiqueta.

### Corroboración independiente adicional — #1652

QA2 coincide con el rechazo y confirma además que `XLSXReader.read()` convierte cada fila a lista (`values = list(row)`) antes de llamar `budget.consume_row()` (`cacao_accounting/imports/readers/xlsx_reader.py:34-36`). Una fila ancha ya se materializó cuando se verifica el máximo de columnas/celdas; el presupuesto no satisface por sí solo el criterio de limitar antes de materializar. Mantener #1652 rechazado hasta que esta ruta y sus pruebas cubran el límite de forma efectiva.

# QA local de reevaluación — #998 (HEAD `45e38f2b`)

**Decisión: rechazado por cobertura funcional incompleta.** Revisión estática del issue y todos sus 12 comentarios, código y pruebas vigentes; no ejecuté pruebas/linters y no realicé escrituras en GitHub.

El fix de subtipo y permiso está presente en `api/__init__.py::_require_document_read_access` / `_require_document_send_access` y `document_flow/repository.py::document_matches_type`. Sin embargo, el último rechazo QA3 sigue vigente en alcance de pruebas: `tests/test_document_alias_subtype_access.py` solo llama `POST /api/document-flow/recalculate-status/...`; sus cinco casos no cubren `GET /api/documents/<alias>/<id>/email-info`, ni el listado/descarga de adjuntos con alias. La ruta de metadatos de correo está en `api/__init__.py:928-938`, y las rutas de referencia de adjuntos en `api/__init__.py:1175-1213`. Los tests de adjuntos existentes cubren otro contrato de referencia/autoridad, no el alias de nota con validación de subtipo.

Faltan regresiones de ventas y compras que acrediten al menos: alias válido y compañía autorizada, compañía ajena (403), subtipo incompatible (404), y denegación antes de devolver destinatario/metadatos o resolver/abrir el archivo adjunto. El fix no queda confirmado hasta cubrir esas superficies concretas. Este dictamen no altera el estado `needs-work` ni comenta el issue.

### Dictámenes independientes — #1652

QA1 y QA2 revisaron independientemente el mismo diff local y ambos rechazan el contrato incompleto. Coinciden en tres defectos: consumidores paralelos (presupuesto/tasas y API line-import) fuera del wiring, fixture XLS con fecha como texto que oculta la falta de conversión de serial de fecha, y comprobación XLSX de ancho después de materializar la fila. La revisión sigue siendo estática; no se ejecutaron controles ni hubo cambios en GitHub.

# QA local de reevaluación — #1021 (HEAD `45e38f2b`)

**Decisión: rechazado por regresión de autorización ausente en el árbol vigente.** Leí el issue y sus 11 comentarios completos; revisión estática, sin pruebas/linters ni escrituras en GitHub.

La ruta actual de `setup()` redirige cuando `SETUP_COMPLETE` ya está marcado y, antes de servir o procesar el asistente abierto, llama `_require_system_admin()` (`cacao_accounting/setup/__init__.py:49-62`). El helper de rol está en `admin/services.py`. Sin embargo, el rechazo QA3 más reciente (20 nov) exige evidencia committed de 403 para un usuario autenticado no administrador en GET y POST, y `tests/test_setup_access.py` no existe en HEAD. `tests/test_setup_finalize_once.py` cubre concurrencia de finalización, reintento, sesión corrupta y redirección tras completar; sus fixtures solo crean admin y no ejercitan el guard de autorización. Por tanto, el riesgo de acceso parece corregido en el código, pero el criterio de regresión que condiciona el reingreso a QA1/QA2 sigue incumplido.

Para reabrir revisión: restaurar una prueba HTTP con usuario autenticado sin rol admin que exija 403 en GET y POST y compruebe que idioma/configuración/compañías no mutan. No modificar estado ni etiqueta en GitHub.

# QA local de reevaluación — #1019 (HEAD `45e38f2b`)

**Decisión: rechazado por falta de regresiones HTTP de aislamiento que pide el QA3 más reciente.** Leí la descripción y los 14 comentarios completos; revisión estática sin tests/linters ni escrituras en GitHub.

El guard `api/__init__.py::_require_flow_target_access` valida destino y `_require_flow_source_lines_access` valida las líneas de `create-target`; `close-line` usa el guard de línea, y el servicio conserva su validación de pertenencia. Pero no existe `tests/test_document_flow_acl.py` en el árbol. La prueba de lectura `tests/test_document_flow_read_access.py` solo cubre `create-target` con línea nula (400, #2171), un mismatch de subtipo y consulta de líneas. Sí hay una prueba HTTP en `tests/test_document_flow_close_line_scope.py:187-204` que rechaza con 400 un `source_row_id` ajeno bajo cabecera propia, pero no comprueba que el saldo/evidencia quede intacto. No encontré cobertura HTTP para (a) destino en compañía no autorizada, (b) línea fuente ajena en `create-target` aunque la cabecera sea propia, ni (c) `close-document` ajeno sin filtrar/mutar datos. Esto coincide con el rechazo QA3 más reciente (20 nov), y el alto impacto multiempresa hace que las pruebas del servicio o de otros endpoints no sean sustituto suficiente.

Reingresar a QA cuando haya regresiones HTTP negativas y positivas para esos cuatro caminos, comprobando 403 y ausencia de creación o mutación. No publicar ni modificar estado/etiqueta.

### Dictámenes independientes — #1019

QA1 y QA2 coinciden en que el rechazo QA3 sigue pendiente. QA1 confirma que existe un caso HTTP parcial de `close-line` (400) sin aserción de no mutación; ambos no encontraron regresiones HTTP para destino extranjero, línea extranjera en `create-target` ni cierre de documento ajeno. Revisión estática, sin cambios en GitHub.

### Corroboración independiente — #1021

QA2 confirma el rechazo: `tests/test_setup_access.py` no existe y las pruebas de ruta que quedan usan solo admin (`test_setup_finalize_once.py` y `test_setup_company_errors.py`), por lo que no fijan 403 para no-admin en GET/POST.

### Dictámenes independientes — #998

QA1 y QA2 coinciden con el rechazo: los guards de correo y adjuntos validan subtipo/ACL, pero `test_document_alias_subtype_access.py` solo prueba `recalculate-status`; no existe regresión HTTP para `email-info` o lista/descarga de adjuntos con aliases de nota. Faltan control autorizado, compañía ajena y subtipo incompatible en dichas superficies.

# QA local de reevaluación — #1338 (HEAD `45e38f2b`)

**Decisión preliminar: rechazo QA3 confirmado por bypass de admin aún presente en el helper global.** Leí la descripción y los 12 comentarios completos; revisión estática sin pruebas/linters ni escrituras en GitHub.

La corrección `cbac6457` de `query_tools.permissions.validate_company_access()` y `query_tools.handlers.companies.list_companies()` está presente, y la prueba `tests/test_query_tools_company_enabled.py` cubre allowlist de service principal y listado allowlist/global. Sin embargo, el último comentario QA3 (#7030188900) reporta explícitamente un bypass hermano en `decorators.exige_acceso_compania()`. El código vigente sigue haciendo `if permisos.administrador: return` (`cacao_accounting/decorators.py:117-120`) antes de `permisos.tiene_acceso_compania(company)`, de modo que el admin no valida `Entity.enabled`. La prueba asociada de compañías query tools no cubre el decorador/RBAC web. El hallazgo del issue permanece y afecta rutas/servicios que usan ese guard; requiere rechazo fail-closed y prueba de regresión con admin más entidad inactiva antes de reingresar a QA.

### Dictámenes independientes — #1338

QA1 y QA2 confirman el bypass del último QA3: `exige_acceso_compania()` retorna ante `permisos.administrador` antes de comprobar acceso/estado activo. `Permisos.tiene_acceso_compania()` sí rechaza `Entity.enabled=False`, pero `test_query_tools_company_enabled.py` no recorre el helper/decorador con admin. Se requiere corregir el contrato del guard y fijarlo con regresión antes de reingresar a QA.

# QA local de reevaluación — #1181 (HEAD `45e38f2b`)

**Decisión preliminar: rechazo QA3 confirmado; el proveedor de vínculo inactivo aún se muestra.** Leí el issue y sus 15 comentarios completos; revisión estática, sin pruebas/linters ni escrituras en GitHub.

`CompanyParty` define `is_active` (`database/__init__.py:1320`), pero `_proveedor_predeterminado_visible()` filtra por tercero y compañías autorizadas, sin condición sobre `is_active` (`inventario/routes.py:562-568`). La fixture de `tests/test_item_detail_company_scope.py:149-150` crea los vínculos con el valor predeterminado (activo); los casos positivos/negativos existentes solo diferencian compañía ajena vs autorizada. Por ello, una relación inactiva dentro de una compañía autorizada sigue satisfaciendo `scalar_one_or_none()` y permite renderizar el proveedor, exactamente el defecto QA3 #7029752412. Añadir `CompanyParty.is_active.is_(True)` y regresión con vínculo inactivo en compañía propia; añadir además el control de vínculo activo solo ajeno para fijar ambas dimensiones.

### Corroboración QA1 — #1181

QA1 confirma el defecto exacto: vínculo autorizado inactivo sigue satisfaciendo el query y las pruebas solo usan vínculos activos; el rechazo QA3 permanece vigente. QA2 independiente queda pendiente.

# QA local estática — #1253 / #1120 (HEAD `45e38f2b`)

**Resultado: el criterio de aislamiento del reporte está satisfecho en el código y pruebas vigentes.** Leí la descripción/comentarios completos de #1253 y #1120, incluida la decisión de producto sobre evidencia. Sin pruebas/linters ni escrituras en GitHub.

La política aprobada es mostrar un lote solo si existe evidencia histórica de ese lote bajo la compañía consultada; conservar lote con evidencia anulada en cero; excluir lote ajeno o sin movimientos. `get_batch_report()` aplica `Batch.id IN (StockLedgerEntry.batch_id WHERE batch_id IS NOT NULL AND company == filters.company)` antes de enumerar filas. El cálculo del saldo usa el predicado compartido que excluye anulaciones y restringe tanto la compañía de ledger como la compañía de `Warehouse`; cuando el único movimiento está anulado, la evidencia inicial conserva el lote y el mapa de saldos queda vacío, produciendo cero. El filtro de compañía de la ruta pasa por `_resolve_company()`/`_exige_acceso_reporte_compania()` antes de invocar el servicio.

`tests/test_report_batch_company_evidence.py` verifica A con lote propio positivo, lote extranjero excluido, lote vacío excluido y evidencia solo anulada en cero; también verifica dirección inversa consultando B. Esto coincide con el criterio operativo de #1253 y con la aceptación QA3 de la misma política en #1120. No encontré discrepancia estática pendiente en este consumidor; la falta de motor PostgreSQL/MySQL en verificaciones previas está documentada, pero no cambia la lectura de este contrato SQL simple.

# QA local de reevaluación — #1301 (HEAD `45e38f2b`)

**Decisión preliminar: rechazo QA3 sigue pendiente por caso de usuario sin compañías asignadas no probado.** Leí el issue y sus ocho comentarios completos, incluida la decisión vigente; revisión estática sin pruebas/linters ni escrituras en GitHub.

La regla de producto está resuelta: la imagen es del maestro global; leer requiere `inventory.consultar`, y subir/borrar requiere `inventory.editar`, sin exigir compañía específica. `_require_inventory_image_access()` implementa exactamente permiso de módulo (`api/__init__.py:601-616`) y las tres rutas invocan el guard antes del servicio (`:1287-1335`). Sin embargo, todos los usuarios del fixture reciben una fila `UserCompanyAccess` (`tests/test_item_image_permission.py:114-116`), por lo que la suite no acredita el caso que QA3 #7029668982 dejó pendiente. Además, el test de editor solo manda el POST sin archivo y afirma `status_code != 403`; eso demuestra que supera el guard pero no que pueda subir/borrar la imagen sin compañía. Falta un usuario con permiso de módulo y cero compañías para lectura (imagen o 404 si no existe), y mutaciones reales que acrediten la política aprobada sin acceso de compañía, conservando los controles de permiso insuficiente.

### Dictámenes independientes — #1301

QA1 y QA2 confirman que el guard implementa la decisión de imagen global, pero el rechazo QA3 sigue pendiente: los tres usuarios actuales tienen `UserCompanyAccess`, así que no hay regresión que proteja permiso de módulo con cero compañías asignadas. Se rechaza la suficiencia de cobertura; no hay cambios remotos.

### Dictámenes independientes — #1181 y #1253

- **#1181:** QA1 y QA2 coinciden: falta `is_active` y no hay regresión del vínculo inactivo dentro de compañía autorizada; rechazo QA3 vigente.
- **#1253:** QA1 y QA2 coinciden en que el filtro de candidatos y la batería A/B/anulado/vacío cumplen el criterio aceptado por #1120. QA1 deja registrados dos bordes no probados: una fila ledger inconsistente `company != Warehouse.company` podría contar como evidencia candidata (aunque los saldos sí verifican ambas compañías y los postores ordinarios validan bodega-compañía); y el lote con evidencia anulada no se mantiene con filtro explícito de bodega. No se encontró que esos bordes contradigan la decisión de #1120 para los escenarios aceptados; conservarlos como observaciones para futuras pruebas de integridad/filtrado, no como cambio remoto.

# QA local de reevaluación — #1332 (HEAD `45e38f2b`)

**Resultado: no aprobable por conflicto de alcance funcional aún sin decisión del responsable.** Revisión estática; sin pruebas/linters, edición de código ni escrituras en GitHub.

La rama de recepción de compra satisface parcialmente el issue: `_document_read_access_modules("purchase_order")` acepta `purchases` e `inventory`, y `tests/test_s2p_purchase_receipt_source_scope.py` cubre líneas pendientes y creación de recepción por el usuario solo de Inventario. Para la rama de entrega, el mismo contrato no aplica: `sales_order` se resuelve únicamente a `sales`, por lo que `_require_document_read_access()` deniega líneas al usuario solo de Inventario. Además, `/api/document-flow/source-documents` filtra esa Orden de Venta antes de anunciarla; `tests/test_document_flow_read_access.py::test_source_picker_hides_sales_order_from_inventory_only_user` protege específicamente ese resultado.

Esto contradice el alcance solicitado por #1332 (consultar líneas de Orden de Venta al crear Nota de Entrega) con la regla aprobada y cerrada en #1515 (no revelar fuente de un módulo al que el usuario no tiene permiso). El comentario QA3 `7029581589` de #1332 señala la contradicción y pide decisión del responsable; el comentario QA3 `7030109308` de #1515 confirma el filtro de lista como aceptado. No hay una decisión posterior documentada en `plan.md`. No se debe escoger una regla ni cambiar el guard en QA: el responsable debe definir si Inventario obtiene lectura de esa Orden de Venta y, en ese caso, actualizar el contrato de lista, detalle/líneas y sus pruebas en conjunto. Hasta entonces, #1332 queda sin aprobación por conflicto funcional pendiente.

# QA local de revisión estática — #1354, #1357, #1433 y #2060 (HEAD `45e38f2b`)

No ejecuté pruebas ni linters, no edité código y no hice escrituras en GitHub. Leí el cuerpo y todos los comentarios actuales de cada issue; contrasté los hallazgos contra `plan.md`, el código y las regresiones vigentes.

## #1354 — credenciales de usuario inactivo: sin brecha estática encontrada

El token se rechaza si el usuario está inactivo, la fila ya no contiene el token, o `auth_version` no coincide (`api/__init__.py::_identity_for_api_token`). El loader Flask también exige `active=True` y valida la versión almacenada en sesión (`auth/__init__.py::cargar_sesion`). `tests/test_token_requerido.py` cubre solicitud API antes/después de deshabilitar directamente y por rutas administrativas, cookie de sesión existente, reactivación sin revivir el JWT/cookie, y emisión de credencial nueva. Esto cubre la ampliación de sesión del comentario #6531401692 y las pruebas son sustanciales respecto al ciclo de vida. Evaluación estática local favorable; no modifica el estado `needs-work` ni sustituye la autoridad de QA3.

## #1357 — blueprint muerto: retiro verificado estáticamente

`admin/services.py` solo contiene helpers/servicios y ya no declara el blueprint vacío. `admin/routes.py` mantiene `admin = Blueprint(...)` y la búsqueda recursiva en `cacao_accounting/` y `tests/` no encuentra `admin.services.admin`, `from ...admin.services import admin` ni otro consumidor de ese objeto. Permanecen importaciones de helpers concretos desde el módulo de servicios. El comentario del issue registra eliminación y pruebas del contrato conservado. No encontré un riesgo de referencia residual en el árbol local.

## #1433 — rechazo por grupo histórico duplicado con clave NULL

El comentario QA3 actual `7029470314` describe que `_ensure_purchase_invoice_supplier_key()` conserva en NULL los grupos históricos ambiguos; la búsqueda local confirma esa rama en `database/helpers.py`. Aunque `compras/services.py::_validate_duplicate_supplier_invoice()` usa correctamente la clave normalizada para filas no nulas, su query solo compara `supplier_invoice_key == supplier_invoice_no_cleaned`. Así, un documento activo histórico de ese grupo no participa del precheck ni del índice único, y una nueva factura puede ampliar el conflicto sin error de negocio. `tests/test_purchase_invoice_duplicate_scope.py` solo usa una factura histórica con clave `INV-1` poblada y no protege el caso nulo. Se mantiene el rechazo del QA3: comparar de forma segura la columna original normalizada para filas activas con clave nula, sin alterar esa evidencia, y cubrir el tercer alta antes de flush.

## #2060 — rechazo por divergencia entre badge y solicitudes aprobables

El comentario QA3 actual `7029139941` fija como criterio que el badge corresponda a solicitudes visibles en “Mis Aprobaciones Pendientes”. Localmente, `pending_approval_count()` solo filtra estados y compañías autorizadas; en cambio `admin/routes.py::pending_approvals()` omite cada solicitud cuando `_pending_approval_info()` recibe `None`, y ese helper invoca `ApprovalEngine.can_approve(document, current_user)`. Los tres casos de `tests/test_approval_count_scope.py` validan solo alcance de compañía y rol admin; no modelan solicitudes aprobables/no aprobables de la misma compañía. La brecha persiste y puede presentar un badge mayor que la lista accesible. Rechazar hasta que badge y listado compartan el mismo predicado o el responsable cambie explícitamente el contrato y se cubra con prueba diferenciadora.

### Dictámenes independientes QA1 / QA2

- **#1354:** ambos aprueban estáticamente: guard JWT, revocación/versionado y loader de sesión activa están cubiertos por las pruebas de desactivación, reactivación y credenciales antiguas.
- **#1357:** ambos aprueban el retiro: no queda blueprint ni referencia a `admin.services.admin`; `admin.routes.admin` y los helpers consumidores permanecen.
- **#1433:** ambos rechazan por el tercer alta contra grupo histórico duplicado con claves `NULL`; el test vigente solo cubre clave poblada. Hace falta precheck complementario sin reescritura de evidencia y regresión antes de flush.
- **#2060:** ambos rechazan por la diferencia entre el conteo por compañía/estado y elegibilidad `ApprovalEngine.can_approve()`; falta caso de dos solicitudes de una misma compañía con distinta elegibilidad.

No se ejecutaron pruebas/linters ni hubo cambios en GitHub. `plan.md` fue actualizado solo para reflejar esta evidencia estática local y mantener las etiquetas remotas intactas.

# QA local pos-QA3 — #1987 y #2078 (HEAD `45e38f2b`)

Revisión estática independiente; no ejecuté pruebas/linters, no modifiqué código y no escribí en GitHub. Consulté todos los comentarios actuales de ambos issues y verifiqué archivos en el árbol local, `origin/estabilizacion` y con `github_fetch_file(ref="estabilizacion")`.

## Evidencia que corrige el rechazo por archivo ausente

QA3 dijo que los archivos de prueba no estaban disponibles y devolvió ambos issues a `needs-work`. La evidencia actual contradice ese motivo: `origin/estabilizacion` contiene ambos archivos; el fetch de GitHub también devolvió sus contenidos para el ref `estabilizacion` (`tests/test_petty_cash_replenishment_append_only_link.py`, blob `9c79802c`; `tests/test_audit_chain_fail_closed.py`, blob `82eb5113`). Por tanto, el 404 de la revisión QA3 no es reproducible con la rama actual. Las etiquetas siguen intactas.

## #1987 — rechazo por upgrade de esquema incompleto

La asociación append-only satisface el criterio funcional y la prueba vigente cubre saldo/reconciliación, FK histórica legacy, fallo de inserción con rollback y reintento, escritura externa ORM/Core/texto, carrera de dos solicitudes y protección update/delete en Desktop/Cloud. Sin embargo, `PettyCashReplenishmentExpense` incorpora `petty_cash_replenishment_expense` (`database/__init__.py:3426-3444`) y no existe migración Alembic para crearla. El único baseline (`migrations/20260809_0001_baseline.py`) es no-op; `cacaoctl db migrate` solo ejecuta Alembic. `create_app()` llama helpers puntuales, pero no `create_all()` ni un ensure para esta tabla (`__init__.py:554-584`); `inicia_base_de_datos()` retorna ante un usuario existente antes de `create_all()` (`database/helpers.py:122-131`). En consecuencia, una base existente no obtiene la tabla y los SELECT/INSERT del nuevo servicio fallan.

Este es bloqueante para el objetivo Alpha: el criterio aprobado en #2248 exige migrar bases existentes en SQLite/PostgreSQL; el contrato arquitectónico #1898 establece Alembic como fuente única y requiere migración efectiva para toda tabla nueva. La excepción pre-alpha del comentario #2248 permite retirar código legacy al no haber instalaciones productivas, pero no exime la instalación sobre una base de datos existente. No encontré una postergación aceptada documentada. QA2 detectó la brecha y QA1 la confirmó tras contrastar esos contratos; ambos rechazan #1987 hasta que el esquema se integre con la política de migraciones.

Observación no bloqueante del fix: la carrera funcional del test se ejerce solo en SQLite. El código toma `FOR UPDATE` sobre los gastos y tiene unicidad por gasto; se debe validar PostgreSQL Tier 1 dentro del ciclo de verificación de persistencia/concurrencia. No es el hallazgo principal ni permite aprobar mientras la tabla no pueda actualizar una base existente.

## #2078 — cobertura del caso QA3 presente; QA1/QA2 aprueban alcance

`audit_chain.py::_validate_chain_head()` rechaza cabeza nula/inexistente, no única o con sucesora; cuando el puntero está nulo, `_legacy_chain_head()` reconstruye la topología y rechaza ciclos, raíces múltiples, ramas y filas huérfanas. Los writers ORM y Core llegan a `_pending_chain_tail()`/`_chain_head_after_lock()` antes de estampar. La regresión fabrica un ciclo de dos filas, prueba puntero anterior y nulo, y verifica que ambas filas, el conteo y el puntero no cambian tras fallar por ORM/Core. QA1 y QA2 aprueban independientemente el criterio del issue; el motivo de falta de prueba del QA3 quedó obsoleto por la presencia verificable del archivo.

Se conserva como hardening fuera del criterio: `_validate_chain_head()` no recorre toda la cadena cuando existe una cabeza terminal válida, por lo que una corrupción desconectada podría coexistir y no impedir append. No se toma como bloqueo del defecto específico “evidencia hasheada sin cabeza terminal” descrito en #2078.

## #1174 — QA1/QA2 rechazan: excepción de validación fuera del handler HTTP

Revisión estática independiente de QA1 y QA2 sobre HEAD `45e38f2b`; no se ejecutaron pruebas ni linters y no hubo cambios de código ni de GitHub. El parser y el servicio rechazan correctamente NaN/±Infinity antes de persistir y las conversiones verifican la finitud de los resultados ordinarios. Sin embargo, `_item_uom_rows_for_template()` invoca el parser que puede lanzar `InventoryServiceError` y no captura esa excepción. La ruta de alta lo llama antes del `try` de `routes.py:433-445`; la edición lo llama antes de `_process_item_edit()` (`routes.py:514-518`). El POST inválido puede acabar en HTTP 500 en vez de re-renderizar el formulario con un error controlado.

La prueba presente `tests/test_inventory_uom_factor_validation.py` valida parser/servicio y no ambas rutas HTTP. Se rechaza hasta manejar la excepción en ambas rutas/helper y agregar regresiones HTTP de alta y edición que comprueben respuesta controlada y ausencia de persistencia. QA2 añade revisar/normalizar `decimal.Overflow` con operandos finitos extremos si el contrato admite esos rangos. El `1e-10` finito que se cuantiza a cero por `Numeric(20,9)` corresponde al contrato de precisión #1650, no es motivo de rechazo de #1174.

## #1183 — QA1/QA2 aprueban corrección de validación de bodegas

Ambas revisiones estáticas independientes aprueban en HEAD `45e38f2b`; no se ejecutaron pruebas/linters ni hubo cambios en GitHub. La ruta `inventario_bodega_nuevo()` solo persiste después de `formulario.validate_on_submit()`, valida las filas de compañía y su autorización antes de crear bodega/configuración en la sesión. El `IntegrityError` de código duplicado hace rollback y solo se transforma en mensaje controlado para constraints conocidos; la fila original queda intacta.

`tests/test_inventory_master_duplicate_codes.py` cubre por HTTP: rechazo de campos vacíos sin persistencia, alta válida de la bodega junto a configuración de compañía, y duplicado controlado conservando el registro original. Observación no bloqueante de QA1: los tests usan cliente admin por defecto y no prueban ruta HTTP de usuario no-admin intentando compañía ajena; el guard de acceso sí está presente antes de escribir. La etiqueta `needs-work` permanece intacta por instrucción del usuario.

# QA local estática — #1683 y #1684 (HEAD `45e38f2b`)

Leí los cuerpos y comentarios completos de ambos issues y el contrato posterior de #1898/#2248. Revisión estática, doble QA independiente; no ejecuté pruebas ni linters y no hice escrituras en GitHub.

## #1683 — rechazo: actualización de esquema incompleta

El cambio `ab7cf4ab` retira del ORM las columnas muertas de `BaseTransaccion` y `tests/test_database_canonical_surface.py:17-23` comprueba la interfaz de un esquema recién creado. Sin embargo, no existe migración Alembic efectiva: `cacao_accounting/migrations/20260809_0001_baseline.py` es no-op. En una base existente, el mapeo nuevo deja de conocer las columnas, pero la base las conserva y `cacaoctl db migrate` no aplica el retiro. Aunque el comentario de implementación `6584531725` justificó omitir migración por pre-alpha, la decisión posterior aprobada en #1898 exige una migración efectiva para cambios de columnas; #2248 requiere verificar upgrades de bases existentes para Alpha. La excepción pre-alpha autoriza limpiar código legacy, no omitir ese contrato de esquema. QA1 y QA2 coinciden: no aprobar hasta integrar el retiro con Alembic y validar upgrade existente bajo la política vigente.

## #1684 — rechazo: tres synonyms de AR/AP siguen expuestos

La limpieza cubre los aliases originalmente identificados y tiene contrato para `Modulos`, `Unidad`, `Entity.is_active`, `ArApReconciliationPolicy.is_enabled`, nombres alternos del modelo de libro y clase `ARAPReconciliationPolicy`. Pero el comentario vigente `6668277830` amplía el issue: `ARAPLedgerEntry` conserva `amount`, `signed_amount` y `transaction_currency` como synonyms en `database/__init__.py:3753-3756`, sin callers productivos encontrados. `tests/test_database_canonical_surface.py:26-50` no verifica su ausencia. Esto deja expuesta la interfaz legacy que el issue busca retirar; QA1 y QA2 rechazan hasta quitar esos tres aliases y fijar su ausencia en la prueba de contrato.

# QA local estática — #1697 (HEAD `45e38f2b`)

Leí el issue y sus ocho comentarios actuales, además de la decisión posterior de #1898/#2248 sobre upgrades. QA1 y QA2 revisaron independientemente. No ejecuté pruebas ni linters y no hice escrituras en GitHub.

**Resultado: rechazo.** El upsert central `config_values.set_config_value()` cubre escritores que lo usan, pero no la creación inicial de la sal SMTP: `_get_or_create_password_salt()` (`messaging/email.py:58-71`) consulta con `scalar_one_or_none()`, genera una sal local y la inserta/flush directamente. Dos primeras llamadas concurrentes pueden leer ausencia; el perdedor falla por `uq_cacao_config_key` y no reintenta/relee la sal ganadora. `encrypt_smtp_pass()` no normaliza ese `IntegrityError`. `tests/test_config_key_uniqueness.py:47-88` prueba solo unicidad, upsert repetido y `set_setup_value`; no cubre carrera de inicialización SMTP ni que ambos callers usen la misma sal persistida. Esto confirma el último hallazgo QA3 `7029213721`.

También existe una incompatibilidad arquitectónica posterior: `_ensure_cacao_config_key_unique()` corre desde `create_app()` (`__init__.py:554-574`) y deduplica filas/crea el índice fuera de Alembic al arrancar. El contrato aprobado en #1898 (comentario `6716758622`) establece Alembic como fuente única de cambios de esquema, prohíbe que `serve` altere/repare esquemas y exige migración para cada índice/constraint en bases existentes; #2248 requiere validar esa ruta en SQLite/PostgreSQL. El único migration local, `20260809_0001_baseline.py`, es no-op. El test `test_schema_guards_existing_databases.py` cubre precisamente un helper de arranque que el contrato más reciente ya no permite como camino paralelo. Hace falta llevar el cambio de unicidad y la consolidación segura a migraciones versionadas, retirar el DDL/deduplicación de arranque y cubrir actualización existente según #1898, además de corregir la carrera SMTP.

Los otros writers revisados son coherentes con el alcance: `set_config_value()` usa upsert; `claim_setup_completion()` toma lock de alcance y traduce la colisión de clave a `SetupAlreadyComplete`. No compensan los dos defectos bloqueantes anteriores.

## #1184 — QA1/QA2 aprueban validación de altas contables

Revisión estática independiente de QA1 y QA2 en HEAD `45e38f2b`; no se ejecutaron pruebas/linters ni hubo cambios de código o GitHub. `nueva_unidad()` y `nuevo_proyecto()` persisten solo mediante `validate_on_submit()`. Así, unidad vacía no persiste y presupuesto `abc` no llega a convertirse en cero; el default a cero queda dentro de la ruta de un formulario válido. Las validaciones conservan entidad activa y padre de la misma entidad; capitalizable requiere cuenta conforme al guard del servicio.

`tests/test_accounting_master_form_validation.py` cubre unidad vacía, alta válida, presupuesto inválido sin proyecto y persistencia exacta de `123.45` con moneda funcional. `tests/test_r2r_hierarchy_company_scope.py` cubre que ambos tipos de altas rechazan padres de otra compañía. QA1/QA2 no encontraron defectos bloqueantes en el criterio de #1184. La etiqueta `needs-work` se deja intacta.

## #1266 — QA1/QA2 rechazan: falta exclusividad persistida del vale

Se leyeron el issue #1266 y sus tres comentarios, además del cuerpo y comentarios del paraguas #1653. Revisión estática doble sobre HEAD `45e38f2b`; no se ejecutaron pruebas/linters ni se modificó código o GitHub.

El fix ya protege el flujo de servicio: `create_petty_cash_expense()` reserva la escritura en SQLite y recarga el vale con `FOR UPDATE`/`populate_existing` antes de comprobar `voucher_status` y `expense_id`. El asiento se publica con `commit=False`; el `PettyCashExpense` se inserta y el vale se actualiza antes del commit común. El test de fault injection demuestra rollback de vale, subledger, journal y GL si falla el INSERT. `test_concurrent_voucher_liquidation_posts_one_expense` verifica que dos llamadas de servicio solo creen un gasto y un journal/GL.

Pero el criterio explícito del hijo requiere que la base de datos garantice que un vale no produzca más de un gasto. `PettyCashExpense.voucher_id` solo es nullable e indexado; no hay restricción única, ni migración Alembic para imponerla. Por lo tanto, otra ruta o escritor que no use el mismo lock aún puede persistir una segunda asociación. El baseline Alembic sigue no-op, de modo que la garantía tendría que incluir upgrade efectivo de bases existentes bajo el contrato posterior #1898/#2248. Además, el test de concurrencia usa el fixture SQLite; no demuestra el escenario en PostgreSQL Tier 1, como exige el enfoque de concurrencia actualizado de #1653. QA1/QA2 rechazan hasta agregar la garantía persistida/migración y cobertura PostgreSQL. La etiqueta `needs-work` queda intacta.

## #2076 — QA1/QA2 rechazan: falta la carrera aprobación/rechazo

Revisé el cuerpo y los seis comentarios actuales del issue en GitHub, y el código local de `ApprovalEngine.approve()`/`reject()` y `tests/test_approval_reject_lock.py` en HEAD `45e38f2b`. QA1 y QA2 revisaron independientemente; no ejecutaron pruebas ni linters y no hicieron cambios.

El fix comparte `_pending_request(..., lock=True)` entre aprobación y rechazo, y `reject()` revalida el estado bajo la transición antes de hacer flush. Sin embargo, la regresión cubre solamente dos llamadas secuenciales a `reject()` en una misma sesión: una queda en `Rejected`, la segunda falla y solo existe una `ApprovalAction`. No reproduce el interleaving central aprobado en el issue, aprobación y rechazo concurrentes en dos transacciones, ni demuestra exclusión con PostgreSQL, que sí aplica `FOR UPDATE`.

QA2 identificó además un riesgo para el flujo perdedor: si `approve()` espera a un rechazo y después `_pending_request()` ya no devuelve fila pendiente, el camino actual revisa solo solicitudes `Approved` y puede llamar `request_approval()`, que no considera `Rejected` en su búsqueda; podría crear otra solicitud y continuar la aprobación. Hace falta probar el interleaving solicitado en PostgreSQL, verificar un único estado/acción terminal y ausencia de side effects del perdedor, y resolver explícitamente cómo debe tratarse una solicitud rechazada durante esa carrera. Se mantiene `needs-work`; no se cambió la etiqueta.

## #2120 — QA1 rechaza edge fail-open; QA2 aprueba el escenario nominal

Leí el issue y sus cinco comentarios actuales, incluidos los hallazgos QA1 `7016722711`/`7018058618` y la actualización de implementación `7028587763`. Revisé en HEAD `45e38f2b` el código y pruebas relevantes. No ejecuté pruebas/linters ni realicé cambios de código o GitHub. QA2 confirma que el test real T2→T1 revierte corrida futura del mismo ejercicio y deja intactas la corrida de período cerrado y la de otro ejercicio; el filtro as-of también tiene prueba discriminante. QA2 aprueba esos escenarios.

QA1 rechaza por un edge adicional en la guarda del período: `_period_is_open_for_run()` captura `IdentifierConfigurationError` y retorna `True` (`exchange_revaluation_service.py:523-531`). El resolvedor (`document_identifiers.py:107-121`) lanza ese error tanto si no existe período como si una fecha pertenece a más de uno. Después, `_void_outstanding_run()` llama `void(..., _period_locked=True)`, lo que omite `_ensure_period_open()` (`exchange_revaluation_service.py:375-379`). Una corrida sin período resoluble o en una configuración ambigua puede, por tanto, recibir reverso GL sin guard de período. Además, el check de apertura no bloquea ni vuelve a comprobar la fila: un cierre concurrente puede ocurrir tras el SELECT y antes de la reversa. La discrepancia QA1/QA2 impide aprobar; mantener `needs-work` hasta que el tratamiento sea fail-closed y el período se revalide/bloquee transaccionalmente, con regresiones de ausencia/ambigüedad y cierre concurrente. Etiqueta intacta.

## #2065 — QA1/QA2 rechazan: la regresión no ata etiqueta a booleano

Leí cuerpo y seis comentarios actuales, incluida la objeción QA3 `7029108571`, y revisé plantillas y regresión vigente. QA1 y QA2 rechazan independientemente; no ejecutaron pruebas/linters ni modificaron código/GitHub.

El fix de producto en las plantillas sí presenta Activo/Inactivo según `rule.is_active`, y Sí/No según `is_buying`, `is_selling` e `is_default`, con cadenas traducibles. La nueva prueba evita contaminación de catálogos y renderiza Jinja real con modelos transitorios. Pero solo busca que las dos etiquetas aparezcan en la tabla y que no se vean `True`/`False`. Como usa filas con valores mixtos, invertir las ramas todavía produce ambos textos y satisface esas aserciones; la regresión no detecta que una fila activa muestre “Inactivo” o una celda false muestre “Sí”.

Mantener `needs-work` hasta que la prueba afirme cada fila/celda frente a sus booleanos concretos, conservando datos transitorios y render real. No se cambió la etiqueta.

## #2067 — QA1/QA2 discrepan del cierre fijo: falta matriz completa de tipos

Leí el cuerpo y los ocho comentarios actuales del issue, incluidos la objeción QA1 original de prueba fuente, su ratificación del render, la aprobación QA2, los dictámenes QA3 y el triage final `7030128979`. Revisé las plantillas y `tests/test_admin_label_tables_render.py` en HEAD `45e38f2b`. QA1 y QA2 independientes discrepan con que la cobertura satisfaga el criterio completo; no ejecutaron pruebas/linters ni modificaron GitHub.

Las plantillas actuales aplican correctamente `percentage → %` y `absolute → Absoluto` en compras para tolerancia de precio y cantidad, y en ventas para tolerancia de precio. El test conserva el render Jinja real y usa objetos transitorios, sin contaminación de catálogos. Las aserciones son discriminantes en los tres pares que prueban: compra precio=`percentage`, compra cantidad=`absolute`, venta precio=`absolute`.

Sin embargo, la matriz de tipos por consumidor/campo queda incompleta: ventas no prueba `percentage`; compras no prueba `absolute` en precio ni `percentage` en cantidad. Una regresión localizada en cualquiera de esas ramas puede pasar. Recomiendo dos tipos por cada campo mostrado (ambos tipos en compra precio, compra cantidad y venta precio), con assert importe+etiqueta por celda. Aunque el issue figura cerrado/fixed en GitHub, por instrucción no se cambió cierre ni etiqueta; esta nota solo registra el resultado QA local y la brecha de regresión.

## #1071 — QA1/QA2 rechazan por regresión del contrato ausente

Leí el cuerpo y los seis comentarios actuales, incluido el triage QA3 `7030188192`, y revisé el endpoint y pruebas actuales en HEAD `45e38f2b`. QA1/QA2 coinciden; no ejecutaron pruebas/linters ni cambiaron código/GitHub.

El retiro es correcto para pre-alpha: `/api/document-flow/tree` siempre invoca `build_document_flow_tree`; no hay lectura del parámetro `legacy`, ni import o función plana `document_flow_tree`. Las pruebas de árbol actuales verifican ACL y nodos permitidos, pero no comparan el resultado canónico con el de la misma solicitud que lleva `?legacy=1`; el test de subtipo llama el builder directamente y no ejerce el endpoint. La regresión del flag, eliminada con `tests/test_document_flow_acl.py`, no tiene equivalente. Se rechaza por cobertura contractual: afirmar con prueba HTTP que el parámetro ignorado devuelve el mismo árbol canónico, o fijar de forma explícita la respuesta si debe rechazarse. Se mantiene `needs-work` en GitHub, sin modificación.

## #2098 — QA1/QA2 rechazan: prueba secuencial no ejerce serialización

Leí cuerpo y seis comentarios del issue, incluido el último QA1 `7052972278`, y verifiqué el estado actual de la ruta directa, aprobación y pruebas en HEAD `45e38f2b`. Revisión estática doble; no se ejecutaron pruebas/linters ni hubo cambios de código/GitHub.

El mecanismo actual toma el lock determinístico de la OC y sus relaciones activas en `_lock_receipt_purchase_orders()`, y el validador también usa `FOR UPDATE` + `populate_existing` en la OC y líneas antes de consultar consumo. Tanto submit directo como aprobación final llaman el helper antes de validar, así que el fix de implementación está presente en ambos consumidores.

La prueba nueva `test_validacion_rechaza_recepciones_que_superan_la_ordenada` inserta/commitea ambas relaciones de 6 unidades y luego llama la validación secuencialmente; el exceso se detecta por los datos ya confirmados aunque se retiren todos los locks. Las otras regresiones verifican llamadas al helper, no exclusión ni lectura del consumo posterior al lock. No hay interleaving real de dos aprobaciones en PostgreSQL. QA1/QA2 rechazan porque la carrera es el defecto central: falta una regresión PostgreSQL con dos sesiones, OC por 10 y dos recepciones de 6, que pruebe un solo éxito y total aprobado ≤10, discriminante al retirar locks. Etiqueta `needs-work` sin cambios.

## #1301 — QA1/QA2 rechazan: falta probar principal sin compañías

Leí el issue y sus ocho comentarios actuales, incluido el acuerdo funcional `6712889146` y QA3 `7029668982`. QA1/QA2 revisaron independientemente el guard y `tests/test_item_image_permission.py` en HEAD `45e38f2b`; no ejecutaron pruebas/linters ni cambiaron código/GitHub.

La decisión funcional vigente es clara y el código la implementa: las imágenes pertenecen al artículo global; lectura exige `inventory.consultar`, mutaciones exigen `inventory.editar`, sin acceso a compañía. `_require_inventory_image_access()` solo comprueba esos permisos del módulo. Sin embargo, el fixture crea `UserCompanyAccess` para los tres roles en todas sus filas; ningún caso evalúa a un usuario con permiso de módulo y cero asignaciones. Las pruebas de acceso real/negado y 404 actual no verifican la condición que el responsable aprobó. Se rechaza hasta agregar lectores y editores sin `UserCompanyAccess` (GET/POST/DELETE según permiso) y conservar los rechazos por permisos insuficientes. Etiqueta `needs-work` intacta.
### #1299 — QA1 y QA2: rechazo por residuos de contrato

Revisión independiente del árbol actual (HEAD `45e38f2b`), sin ejecutar pruebas ni linters.

- `CompanyParty` en `cacao_accounting/database/__init__.py` ya no declara las ocho preferencias retiradas, y `PartyCompanySettingsParams`/su upsert no las reciben ni las guardan. El test `test_company_party_preferences_cleanup.py` cubre la ausencia en el modelo y parámetros.
- `document_flow/currency_resolver.py:110-115,174-179` mantiene `resolve_party_currency()` y la rama `source="party"`; el docstring de `resolve_transaction_currency()` todavía declara ese fallback. El caller productivo `ventas/services.py:321` pasa un `Party`; el modelo `Party` no contiene `default_currency` ni `currency`. Además, las fuentes de Document Flow tienen prioridad y retornan antes de esa rama. Es código inalcanzable y documentación que describe un comportamiento que el sistema no implementa.
- `tests/test_party_company_settings_validation.py:214-240,247-270` conserva asignaciones y asserts para `default_currency` y datos bancarios retirados. Atributos dinámicos sobre la instancia ORM no son columnas y no se persisten; estos tests pasan a representar incorrectamente el contrato y no deben ser la evidencia del retiro.
- No se halló cobertura directa de `resolve_transaction_currency` para fijar la precedencia vigente de moneda de origen, elección explícita del usuario y moneda funcional de compañía.

**Decisión QA1/QA2: rechazado.** Corregir la documentación y retirar la helper/rama muerta, reemplazar las pruebas de atributos retirados por pruebas del contrato vigente. Hallazgo alineado con QA3 #7029690077; issue/etiqueta de GitHub permanecen intactos por instrucción del usuario.
### #1689 — QA1/QA2 rechazan por carrera sin regresión discriminante

Revisión estática independiente de HEAD `45e38f2b`; no se ejecutaron pruebas/linters ni hubo cambios en código o GitHub.

El fix de serialización está presente: `allocate_purchase_invoice_receipt_lines()` adquiere el lock documental de la factura antes de `_allocate_invoice_lines()` (`compras/purchase_reconciliation_service.py:478-490`); después `_lock_invoice_items()` aplica `FOR UPDATE` antes de sumar allocations activas. El upsert de `DocumentFlowLock` coordina procesos que comparten PostgreSQL; SQLite obtiene serialización de escritor a nivel DB, que no acredita el contrato de PostgreSQL.

La regresión `test_concurrent_receipts_do_not_overallocate_invoice()` solo lanza dos tareas con `ThreadPoolExecutor` sobre SQLite, sin barrera/evento que las sincronice después de leer la capacidad. Solo afirma total `<= 10`; una ejecución secuencial también pasa sin los locks y la prueba puede no producir la carrera. QA1 y QA2 coinciden con el hallazgo QA1 de GitHub `7052878650`: el comportamiento del código parece correcto, pero el invariante concurrente no queda protegido por una prueba discriminante.

Requisito: dos sesiones PostgreSQL con pausa controlada tras lectura y antes de insertar, que demuestren serialización/remanente y fallen si se retiran ambos locks; documentar aparte SQLite. La etiqueta `needs-work` se conserva intacta.
### #1283 — QA1/QA2 rechazan por guard de retiro ausente

Leí el issue y sus cuatro comentarios. Revisión estática independiente en HEAD `45e38f2b`, sin pruebas/linters ni cambios en código/GitHub.

El código de `party_management.py` ya no declara `party_account_labels()` ni `build_party_code()`, y la búsqueda en el repositorio no encuentra sus nombres. `generate_party_code()` permanece con consumidores en adapters de clientes/proveedores, ventas y compras. No hay re-export público adicional.

La regresión que se añadió junto con la retirada en `d1649c9a` era parte de `tests/test_dead_code_inventory.py`, pero `0970476b` eliminó ese archivo y la prueba ya no existe en HEAD. QA1 y QA2 rechazan la cobertura del retiro: restablecer un guard de contrato para que los dos símbolos no reaparezcan y conservar evidencia de consumidores para el generador canónico. `needs-work` queda sin cambios en GitHub.
### #1046 — QA1/QA2 rechazan por residuo del flujo legacy

Leí el issue y sus cinco comentarios completos, además de la decisión pre-alpha aprobada en #2248. Revisión estática en HEAD `45e38f2b`; no ejecuté pruebas/linters ni modifiqué código o GitHub.

El parser principal `import_bank_statement()` fue retirado; `ImportService.ADAPTERS` registra `BankStatementAdapter`, con cobertura vigente de validación, precisión, persistencia, identidad y concurrencia. `statement_service.py` no debe eliminarse por completo: el adaptador consume `auto_reconcile_bank_transaction()` y las rutas usan `apply_bank_matching_rule()`.

Persisten `_decimal_value()` y `_parse_date()` en `statement_service.py` sin llamadas productivas; el test `tests/test_import_non_finite_validation.py` todavía importa `_decimal_value()` y valida ese parser residual, no el adapter activo. Además `/bank-statement/import` permanece como shim de redirección, el menú `bancos.html` apunta a él y `extracto_importar.html` sigue versionada sin caller de renderizado. Esto coincide con el residual explícito del comentario `6682010582`; la decisión #2248 elimina las rutas/capas legacy pre-alpha cuando el consumidor está identificado. QA1/QA2 rechazan hasta llevar el menú directamente a `imports.new`, retirar shim/plantilla/helpers/test antiguo y mantener los servicios de matching/autorreconciliación.
### #1031 — QA1/QA2 rechazan por preview corrupto sin manejar

Revisión estática independiente del árbol actual, incluyendo los cambios locales en lectores; sin ejecutar pruebas/linters ni modificar código/GitHub.

La recuperación de lote zombi sí está implementada: `validate()` captura excepciones del lector y registra `SYSTEM_ERROR`; el recovery incluye lotes con `started_at` nulo. Sin embargo, `ImportService.preview()` (`imports/services/import_service.py:359-383`) solo captura `ImportReadLimitError`; `reader.read()` puede propagar `KeyError`, `BadZipFile` u otra excepción del formato. La ruta `imports.routes.detail()` llama `preview()` para cualquier estado `>= 1`, incluso estado 7 con error persistido. Por tanto un archivo corrupto que ya falló validación todavía puede producir HTTP 500 al abrir su ficha, ocultando el error almacenado.

`tests/test_import_corrupt_reader_recovery.py` cubre validación y recovery, no el endpoint de detalle; las pruebas de preview existentes cubren límites de recursos, no archivos corruptos. Los cambios locales de readers/import service inspeccionados no cambian el manejo de excepciones en `preview()` ni añaden esa regresión. QA1 y QA2 confirman el retorno QA3 `7030187515`; requiere preview tolerante y prueba HTTP que muestre error de lote sin 500.
### #1032 — QA1/QA2 rechazan: estado procesando tras cancelación tardía

Leí el issue y los ocho comentarios completos. Revisión estática independiente del árbol actual; no ejecuté pruebas/linters ni modifiqué código o GitHub.

`_process_all_documents()` consulta cancelación al inicio de cada documento. `cancel()` persiste solo `cancel_requested=True`; si la petición llega después del último check, o no hay filas/documentos para procesar, se alcanza el finalizador con la bandera activa. `_finalize_execution()` vuelve a leer la fila y persiste contadores parciales y `completed_at`, pero retorna sin cambiar `import_status=4` a estado terminal `8` ni limpiar `started_at`. La UI conserva “procesando” hasta recovery. La cancelación detectada dentro del bucle sí pasa a 8, pero no resuelve esta ventana final. QA1 y QA2 confirman el hallazgo QA3 vigente.

No hay prueba de cancelación de importación en HEAD: `tests/test_import_batch_cancellation.py` no existe y la búsqueda no encuentra casos que ejerciten cancelación, finalizador o endpoint en esta superficie. Requerir transición terminal a 8 y regresiones para cancelación justo antes de finalizar y lote vacío, verificando contadores parciales y fecha terminal.
### #1030 — QA1/QA2 rechazan: blancos y agrupación mixta inválidos

Leí el issue y sus siete comentarios completos. Revisión estática del árbol actual; no ejecuté pruebas/linters ni modifiqué código/GitHub.

La lógica del fix base rechaza simétricamente 1.000 y 1,000, y conserva formas con decimales explícitos. Sin embargo, _optional_amount() comprueba None/cadena vacía antes de quitar espacios; un valor compuesto de espacios queda en cadena vacía y llega a coerce_decimal, que lo rechaza aunque el otro lado bancario tenga un monto válido. La rama de separadores mixtos borra globalmente el separador interpretado como miles sin validar agrupación; 12,34.56 queda en 1234.56 y 1.23,456 en 123.456. Ambos son defectos de interpretación con efecto financiero.

QA1 y QA2 confirman el rechazo QA3 6886283181. No hay pruebas actuales para estos casos; tests/test_bank_statement_import.py fue eliminado y la cobertura presente trata precisión/no finitos/celdas vacías exactas. Los cambios locales en el adaptador solo agregan un alias de columna, sin cambiar el parser. Se requiere normalizar blancos opcionales y validar gramática de grupos antes de eliminar separadores, con regresiones para ambas convenciones y agrupación mal formada.
### #1055 — QA1/QA2 rechazan: falta datemode y contrato XLS end-to-end

Leí el issue y sus doce comentarios completos. Revisión estática del árbol actual, incluyendo worktree local; no ejecuté pruebas/linters ni modifiqué código o GitHub.

El manejo de OverflowError en parse_import_date() se mantiene. Sin embargo, QA3 7029866045 señala un caso funcional adicional: XLSReader.read() copia ws.cell_value() sin leer wb.datemode ni convertir celdas fecha usando el workbook. TabularBook no transporta datemode y su normalización convierte seriales numéricos en texto; el parseador acepta seriales numéricos bajo época fija 1899-12-30, pero para strings intenta ISO. El sistema de fechas 1904 queda desfasado 1462 días y el cambio local puede impedir también parsear seriales 1900 del lector real.

QA1/QA2 rechazan la cobertura: test_import_date_normalization.py prueba el serial directamente contra el helper, mientras el nuevo archivo común XLS escribe una fecha literal como texto y no un serial de celda; no hay integración lector XLS → adaptador/validación con workbook.datemode 1904 y control 1900. Hay que conservar la época o normalizar celdas fecha dentro del lector, y verificar el período con la fecha ya convertida. La etiqueta de GitHub no se modificó.
### #1057 — QA1/QA2 rechazan: faltan guardas de proveedor

Leí el issue y su comentario completo. Revisión estática independiente; no ejecuté pruebas/linters ni cambié código o GitHub.

PurchaseOrderAdapter.validate_document() valida periodo, bodega, cantidades, UOM y moneda, pero no resuelve ni valida proveedor. En build_document(), la query filtra Party.id + is_supplier=True, sin is_active; si no encuentra fila se sigue construyendo PurchaseOrder con el supplier_id del payload y supplier_name=None. La FK solo acredita existencia, no el rol. Persistencia no vuelve a validar el proveedor. Por ello cliente con is_supplier=False, proveedor inactivo o identificador inexistente no queda rechazado como error de negocio antes de ejecutar, tal como exige el issue.

Las pruebas existentes del adaptador cubren importe negativo y decimales no finitos, no proveedor ausente/inactivo/cliente; no hay matriz positiva/negativa para esta regla. QA1/QA2 rechazan hasta validar en prevalidación y proteger la construcción/persistencia, con controles de proveedor válido y los tres casos inválidos. Etiqueta intacta.
### #1059 — QA1/QA2 rechazan: decisión de impuesto no conectada

Leí el issue y sus cinco comentarios, incluida la decisión funcional aprobada del responsable (comentario 6716234735). Revisión estática independiente; no ejecuté pruebas/linters ni hice cambios de código o GitHub.

La decisión ya fija la representación: impuesto es importe observado por línea; la fuente normativa es la plantilla fiscal aplicable a compañía/proveedor. Un observado sin plantilla o discrepante se rechaza antes de persistir; si se omite y existe plantilla, el adaptador calcula. Deben persistirse el total y datos necesarios para conservar el resultado.

El adapter sigue declarando la columna impuesto, pero validate_document() y build_document() no la usan. Las líneas se suman como cantidad × tarifa y grand_total permanece igual al subtotal; el adaptador no asigna PurchaseOrder.tax_total, no conserva plantilla aplicada y el modelo de línea carece de importe fiscal. No encontré pruebas que cubran las ramas de impuesto de importación. QA1/QA2 rechazan hasta implementar y cubrir el contrato aprobado; GitHub/etiqueta intactos.

### #1060 — QA1/QA2 rechazan: importaciones aceptan artículos no habilitados

Revisiones estáticas independientes en HEAD `45e38f2b`, tras leer el issue y sus seis comentarios completos. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

`TransactionDocumentAdapter._validate_document_row()` (`imports/adapters/transaction_documents.py:139-162`) valida conversión/UOM, bodega y lote, pero no exige `Item.is_active` ni comprueba el rol correspondiente al flujo (`is_sale_item`/`is_purchase_item`). Esto incluye adaptadores de documentos de venta y compra; `PurchaseOrderAdapter` también hereda la validación incompleta. Las rutas manuales de ventas y compras sí validan actividad y rol, de modo que la importación no mantiene paridad con la captura manual.

La prevalidación API (`api/line_import.py:665-685`) comprueba existencia de Item/UOM, pero no actividad ni elegibilidad por tipo de documento. En factura de compra, el servicio vigente sí verifica actividad y rol del Item (`compras/services.py:1216-1239`), pero no comprueba actividad de la UOM elegida o heredada; la conversión común tampoco la comprueba (`inventario/service.py:253-276,311`). El archivo histórico `purchase_invoice_draft_service.py` ya no existe en el árbol, por lo que se evaluó el call path actual.

QA1 y QA2 coinciden en el rechazo. Las pruebas disponibles cubren elegibilidad en rutas manuales, pero no adaptadores/prevalidación ni UOM inactiva o heredada. Se requieren regresiones de importación para Item inactivo y rol incorrecto en venta/compra, rechazo temprano sin documento persistido, UOM inactiva explícita y UOM de respaldo inactiva, además de controles positivos con referencias activas. GitHub conserva `needs-work`; no se cambiaron etiquetas ni se publicaron comentarios.

### #1062 — QA1/QA2 rechazan: recuperación sin checkpoint idempotente

Revisiones estáticas independientes en HEAD `45e38f2b`, tras leer los seis comentarios completos. El último comentario del responsable establece el contrato: conservar fuente/progreso confirmado, checkpoint por documento, reanudar solo documentos no persistidos, no reprocesar el archivo completo, y mostrar errores persistidos sin parsear una fuente ilegible. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

El worker confirma cada documento en `_process_document()` (`imports/services/import_service.py:444-458`) y guarda los contadores después, por separado (`:546-559,584-589`). `ImportBatch` no conserva checkpoint durable por documento (`imports/models.py:35-49`). Una caída entre ambos commits puede dejar una transacción persistida con contadores que no la reflejan; el comentario `6561838726` reproduce esta ventana. `recover_crashed_batches()` cambia el lote a estado 7 y agrega `SYSTEM_TIMEOUT`, pero no identifica ni guarda documentos ya confirmados (`imports/utils/recovery.py:22-53,56-80`). `execute()` solo acepta estado 3 y progreso cero, y `validate()`/`_claim_batch()` exigen también ausencia de `started_at`/contadores (`import_service.py:133-136,194-211,404-414`). No hay reanudación segura ni protección frente a duplicados append-only.

La ficha ofrece carga, validar y ejecutar solo para estados 0, 1 y 3 (`imports/templates/imports/detail.html:50-75`); un lote fallido no tiene acción. Además `routes.detail()` llama a `preview()` desde estado 1 (`imports/routes.py:207-216`) y `preview()` vuelve a parsear el archivo, capturando solo `ImportReadLimitError` (`import_service.py:359-384`). Un archivo corrupto puede devolver 500 e impedir que se vean los errores ya guardados, confirmado por el comentario `6669978955`.

El rollback antes de registrar el error fatal sí está presente en `_handle_execution_error()` (`import_service.py:613-624`); corrige esa ruta pero no agrega checkpoint ni reanudación. Los tests actuales cubren fallo de lectura y claim atómico (`tests/test_import_corrupt_reader_recovery.py:93-105`, `tests/test_import_recovery_atomic_claim.py:123-166`), no fallo tras commit parcial, reintento sin duplicados, ni ficha HTTP de archivo corrupto. QA1 y QA2 rechazan; GitHub conserva `needs-work` y no se cambiaron etiquetas.

### #1063 — QA1/QA2 rechazan: el importador persiste padres de cuenta inválidos

Revisiones estáticas independientes en HEAD `45e38f2b`; leí el issue y sus tres comentarios completos. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

`ChartOfAccountsAdapter` no implementa `validate_document()` y hereda el no-op de `BaseImportAdapter` (`imports/adapters/chart_of_accounts.py:14-18`, `imports/adapters/base.py:37-39`). `build_document()` copia `row.get("padre")` directamente y `persist_document()` solo agrega el modelo (`chart_of_accounts.py:17-37`). El valor vacío queda `""`, y referencias inexistentes, cuentas de detalle, inactivas o de otra entidad pueden persistirse; `Accounts.parent` es texto nullable sin FK (`database/__init__.py:678-693`).

El contrato del flujo manual ya está definido: padre opcional vacío equivale a `None`; de lo contrario resuelve dentro de la misma entidad y requiere cuenta existente, activa/habilitada y de grupo, además de impedir ciclos (`contabilidad/services.py:279-329`). El cargador de catálogos también normaliza vacío con `or None` (`contabilidad/ctas/__init__.py:54-78`), pero no es el adaptador CSV. El adaptador no prepara/resuelve padres del mismo archivo; el servicio agrupa/procesa filas individuales en el orden recibido (`imports/services/import_service.py:309-331,625-644`).

La única prueba dedicada del adapter cubre campos requeridos en blanco (`tests/test_import_required_whitespace.py:15-39`). `test_catalog_loading_transaction.py` cubre el cargador de setup, no esta ruta. Faltan regresiones para padre vacío, inexistente, inactivo, no-grupo, ajeno, ciclo, y padre incluido en el mismo archivo en orden previo/posterior; verificar rechazo sin persistencia y caso positivo. QA1 y QA2 rechazan; GitHub conserva `needs-work` sin cambios.

### #1087 — QA1/QA2 rechazan: valor bancario no se canonicaliza antes de identidad

Revisiones estáticas independientes en HEAD `45e38f2b`; leí el issue y sus dos comentarios completos, incluido el criterio explícito `6712801173`. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

El importador rechaza más de cuatro dígitos fraccionarios significativos: `_optional_amount()` llama `coerce_decimal(..., max_fractional_digits=4)` (`imports/adapters/bank_statement.py:83-84`). Eso resuelve el redondeo silencioso para valores como `1.23456`. Sin embargo, no cuantiza el resultado: `coerce_decimal()` devuelve el Decimal de entrada intacto (`numbers.py:41-46`), por lo que `123.456700` se acepta como Decimal con escala textual 6. El adapter usa ese mismo objeto al buscar duplicados y construir `BankTransaction` (`bank_statement.py:204-227`), y el listener construye `identity_key` con `str(deposit/withdrawal)` antes de que la columna `Numeric(20,4)` persista su representación a escala 4 (`database/__init__.py:4125,4150-4166`). No se cumple el contrato de normalizar una sola vez y alimentar con la misma representación identidad, búsqueda y persistencia.

`tests/test_bank_statement_precision_validation.py:83-113` cubre rechazo de exceso significativo y persistencia en escala 4, incluyendo ceros finales, pero solo con SQLite; no verifica identidad ni reimportación con representación equivalente. `tests/test_bank_transaction_identity_uniqueness.py:351-376` reimporta el mismo importe textual estándar, no equivalentes con escalas distintas. No encontré prueba PostgreSQL de este contrato; la fixture de precisión fuerza SQLite. QA1 y QA2 rechazan hasta cuantizar antes de identity/query/insert y cubrir rechazo, round-trip, reimportación equivalente con una sola transacción y ambos motores Tier 1.

### #1174 — QA1/QA2 rechazan: validación no finita escapa por HTTP y falta guard de escala

Revisiones estáticas independientes en HEAD `45e38f2b`; leí los nueve comentarios completos, incluido el caso adicional de factor representable menor que la escala `Numeric(20,9)`. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

El parser y servicio sí rechazan NaN e infinitos y el convertidor vuelve a validar factor/resultado (`inventario/service.py:241-283,899-937`). Aun así, el helper `_item_uom_rows_for_template()` llama `parse_item_uom_rows()` sin traducir errores (`inventario/services.py:403-408`); tanto alta como edición llaman el helper antes de sus `try` de manejo (`inventario/routes.py:429-445,514-518`). Por tanto el error controlado del servicio escapa de los POST HTTP de alta/edición como 500. `tests/test_inventory_uom_factor_validation.py:89-149` solo cubre parser/servicio/conversor y no prueba ambas rutas ni confirma no persistencia por HTTP.

Además, `validate_item_uom_rows()` acepta cualquier Decimal positivo finito sin comprobar representabilidad a escala de la columna (`service.py:917-937`). El factor `0.0000000001` cabe como entrada positiva pero `ItemUOMConversion.conversion_factor` es `Numeric(20,9)` (`database/__init__.py:1454`); el comentario `6643172155` documenta que se recupera como cero y luego no permite conversión. No hay test para ese borde. QA1/QA2 rechazan; corregir propagación HTTP en alta y edición, rechazar valores que colapsen según escala declarada y probar ambos caminos, persistencia ausente y un positivo representable.

### #1185 — QA1/QA2 rechazan por falta de regresiones HTTP en consumers

Revisiones estáticas independientes en HEAD `45e38f2b`; leí el issue y sus cuatro comentarios completos, incluida la reproducción más reciente de `counted_cash=abc` en la conciliación nueva. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

La corrección del parser compartido sí está presente: `bancos.services._form_decimal()` usa `coerce_decimal()` (`bancos/services.py:2106-2110`), que transforma `InvalidOperation` y entradas no finitas en `ValueError` (`numbers.py:31-36`). La revisión de todos los callers no encontró un escape de control actual: alta/edición de caja chica, vale, gasto y conciliación nueva convierten dentro de manejadores `ValueError` (`bancos/routes.py:1120-1135,1180-1192,1299-1320,1451-1469,1502-1514`); edición de conciliación también captura `InvalidOperation` (`:1535-1547`); aplicación de conciliación bancaria transforma los errores del parser por fila antes de invocar el servicio (`:587-617,630-636`).

La regresión HTTP actual `tests/test_cash_decimal_boundary_routes.py` cubre aplicación de conciliación bancaria y creación de caja chica (`:15-96`), pero no la evidencia más reciente de alta de conciliación de caja chica ni los otros campos/callers alcanzados: edición de caja chica, alta de vale, alta de gasto, edición de conciliación y referencias de pagos. QA1/QA2 rechazan por insuficiencia de pruebas sustanciales: añadir regresiones HTTP con valor malformado y sin mutación para cada consumer afectado, especialmente `counted_cash=abc` en alta. No se identifica bypass adicional en el código revisado. Etiqueta `needs-work` intacta.
### #1197 — QA1/QA2 rechazan: booleano de anticipo se interpreta por truthiness

Revisiones estáticas independientes en HEAD `45e38f2b`; leí los dos comentarios completos. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

`JournalEntryAdapter.build_document()` copia el valor de `is_advance` sin normalizar (`imports/adapters/journal_entry.py:152`) y `_normalize_line()` aún hace `bool(raw_line.get("is_advance"))` (`contabilidad/journal_service.py:912-944`), por lo que cadenas no vacías como `"false"`, `"0"`, `"no"` y `"off"` se convierten en `True`. `_optional_bool` existente no arregla este campo y no rechaza entradas desconocidas. El helper alimenta tanto servicio de comprobantes como otros consumers; la normalización debe vivir en el contrato compartido.

El campo no aparece en las columnas declaradas del adapter (`journal_entry.py:33-44`), así que la validación estructural de HEAD puede rechazar cabeceras desconocidas; no resuelve el bug en `_normalize_line` ni la petición de coerción explícita. El worktree actual también tiene un diff local que rechaza headers desconocidos; eso reduce la ruta del CSV con columna extra, pero no proporciona coerción booleana y no forma parte de HEAD. No hay tests funcionales que ejerciten `is_advance` importado; la búsqueda solo encontró su uso en fixtures no relacionados. QA1/QA2 rechazan: definir parse canónico para boolean y strings permitidas, rechazar desconocidos y cubrir false/true textual, booleanos reales y valor inválido a través del caller de importación y servicio. GitHub conserva `needs-work` sin cambios.

### #1200 — QA1/QA2 rechazan: falta guard de archivo vacío dentro del worker

Revisiones estáticas independientes en HEAD `45e38f2b`; leí el issue y sus cuatro comentarios completos. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

La validación ya rechaza un archivo sin filas con `NO_DATA_ROWS`, estado 7 y `started_at=None` (`imports/services/import_service.py:151-157,333-344`). `execute()` también tiene prelectura y rechaza un lote heredado de estado 3 si el archivo está vacío (`:416-424`). El test `tests/test_import_empty_file_rejected.py:95-120` cubre ambos caminos.

Sin embargo, `_execute_task()` vuelve a leer el archivo después del preflight y no verifica `table.rows` antes de normalizar/agrupación/finalización (`import_service.py:503-535,546-559,591-611`). Si la fuente desaparece o cambia entre ambas lecturas, el worker procesa cero documentos y `_finalize_execution()` puede marcar estado 5 con cero éxitos/errores. QA1 y QA2 coinciden: repetir la guarda dentro del worker y agregar una regresión que vacíe la fuente en esa frontera, asegurando estado fallido con error `NO_DATA_ROWS` y sin estado completado. No hay prueba HTTP de detalle, aunque estructuralmente la ficha renderiza errores persistidos. También se observa `total_rows` potencialmente obsoleto al revalidar un lote previo; revisar su reinicio junto a la transición vacía. GitHub conserva `needs-work`, sin cambios.

### #1199 — QA1/QA2 rechazan: adaptador redundante y pruebas siguen presentes

Revisiones estáticas independientes en HEAD `45e38f2b`; leí issue y tres comentarios completos, y busqué referencias de módulo y clase. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

El adaptador activo es el `PurchaseOrderAdapter` importado desde `transaction_documents.py` y registrado en `ImportService.ADAPTERS` (`imports/services/import_service.py:26-38,84-87`; clase activa `transaction_documents.py:501-518`). El archivo huérfano `imports/adapters/purchase_order.py` aún existe (`:30`) y lo importan tests `test_import_negative_rates.py:19,100-102` y `test_import_non_finite_validation.py:128-158`. No hay migración de esas pruebas al adaptador registrado, por lo que la cobertura actual puede pasar probando código que producción no ejecuta. QA1/QA2 confirman el hallazgo; aún no se ha aplicado el retiro.

El adapter antiguo declara `impuesto` (`purchase_order.py:33-46`) pero tampoco lo persiste; no usar su test/mapeo como soporte de la capacidad fiscal. El contrato de producto aprobado en #1059 (`6716234735`) requiere que el adapter activo procese impuesto observado por línea con plantilla fiscal, rechace discrepancias/sin plantilla, calcule cuando se omita y persista detalle/totales. La clase activa no añade esa columna o cálculo y la plantilla se genera con el adapter registrado (`imports/routes.py:390`). #1059 permanece pendiente; el retiro del duplicado debe ser un cambio separado y no declarar que preserva soporte fiscal inexistente. El destino de retirar el huérfano es correcto, pero issue no cumple criterio en este árbol.
### #1201 — QA1/QA2 rechazan: las fechas nativas XLS siguen sin normalizar

Revisiones estáticas independientes del worktree actual en `estabilizacion`, incluyendo los cambios locales a readers; leí el issue y sus nueve comentarios completos. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

La normalización local sí convierte `datetime` de XLSX a texto ISO en `imports/readers/base.py:20-23`, que los adaptadores convierten a fecha por `parse_import_date()`. La ruta XLS permanece rota: `XLSReader.read()` copia `ws.cell_value()` sin `cell_type` ni `wb.datemode` (`readers/xls_reader.py:43-47`); xlrd entrega serial de fecha como número y `TabularBook` lo convierte a texto (`base.py:24-31`). `parse_import_date()` interpreta serial solo si sigue siendo numérico; para texto intenta ISO/datetime y falla (`imports/utils/dates.py:32-50`). Además, el helper fija epoch 1899-12-30 y no retiene sistema 1904 (`dates.py:17`), con desplazamiento de fechas XLS en ese sistema.

La nueva prueba `tests/imports/test_readers_contract.py` cubre fecha XLSX nativa, pero el fixture XLS usa texto de fecha (`:83-101,114-125`); `tests/test_import_date_normalization.py` pasa serial numérico directo al helper (`:69-89`) y no prueba el lector ni la época. QA1 y QA2 rechazan: convertir celdas de fecha XLS con el datemode del libro (sin perder el contexto), y añadir fixtures de XLS nativo 1900/1904 desde lector hasta adaptador activo. GitHub conserva `needs-work`, sin cambios.
### #1204 — QA1/QA2 rechazan: prevalidación no aplica el límite de ajustes

Revisiones estáticas independientes en HEAD `45e38f2b`; leí el issue y sus dos comentarios completos. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

`api.line_import._validate_payment_reconciliation_amounts()` lee `allocated`, `discount` y `gain_loss`, pero calcula consumo con `max(allocated - discount - gain_loss, 0) * rate` y no valida que ajustes sumen menos que lo asignado (`api/line_import.py:1129-1148`). Si documento/pago conservan saldos suficientes, igualdad o exceso consume cero y puede no generar error. El servicio de aplicación sí rechaza `discount + gain_loss >= allocated` (`document_flow/payment.py:966-978`). Por tanto `/api/line-import/validate` puede aceptar una línea que apply rechaza.

QA1 y QA2 confirman que la discrepancia permanece en el árbol; la tolerancia de saldos `0.01` no corrige el límite funcional. Las pruebas encontradas cubren tipo de pago y alcance de terceros (`tests/test_payment_reconciliation_type_validation.py:16-72`, `test_payment_reconciliation_import_party_scope.py:123-147`), no igualdad/exceso ni paridad prevalidation/apply. Falta regresión para suma igual, suma mayor, suma menor válida y saldos suficientes, verificando que ambas rutas acuerden. GitHub conserva `needs-work`.
### #1205 — QA1/QA2 rechazan: prevalidación no acumula consumo por lote

Revisiones estáticas independientes en HEAD `45e38f2b`; leí issue y comentario completo. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

`validate_lines()` recorre cada fila y llama `_validate_import_row()` independientemente, sin pasar estado compartido entre filas (`api/line_import.py:409-422,525-544`). `_validate_payment_reconciliation_amounts()` consulta el saldo actual inicial del pago y documento cada vez (`:1129-1148`); no descuenta reservas previas. En cambio `apply_payment_reconciliation()` mantiene `payment_remaining`, lo inicializa por pago y lo decrementa según la línea aplicada (`document_flow/payment.py:909-914,1112-1152`); también rastrea claves procesadas para evitar repetir la misma asignación (`:966-982`). Así, saldo de pago 100 con dos líneas de 80 a documentos distintos puede aparecer válida en ambas filas del pre-validador y fallar al aplicar la segunda. El mismo documento repetido puede ser validado individualmente y rechazado luego por la aplicación.

Los tests de prevalidación encontrados cubren tipo de pago/alcance de tercero (`test_payment_reconciliation_type_validation.py`, `test_payment_reconciliation_import_party_scope.py`), no un lote de varias filas con pago o documento compartido. QA1 y QA2 rechazan: validar conjunto con acumuladores de pago/documento, siguiendo consumo y duplicate-key del flujo apply, y cubrir vía HTTP los casos multi línea suficiente/insuficiente y documento repetido, con paridad entre prevalidación y aplicación. GitHub conserva `needs-work`.
### #1206 — QA1/QA2 rechazan: endpoint de XLSX materializa sin límites

Revisiones estáticas independientes en el worktree actual; leí el issue y sus tres comentarios completos. No se ejecutaron pruebas/linters ni se modificó código o GitHub.

La ruta activa `/api/line-import/parse-xlsx` llama `_xlsx_rows()` (`api/line_import.py:341-364`). Esa función abre el libro en `read_only`, pero ejecuta `rows = list(worksheet.iter_rows())` antes de validar cualquier dimensión (`:319-338`). El tope de 100 columnas se revisa después de crear la lista (`:330-331`) y el de 500 filas después, durante `_canonical_xlsx_rows()` (`:303-315`). `_xlsx_archive_is_safe()` limita tamaño, ratio y entradas ZIP, pero no evita que una hoja pequeña declare dimensión inflada (`:202-218`).

El `XLSXReader` separado sí llama `reset_dimensions()` y consume con `ReadBudget` (`imports/readers/xlsx_reader.py:20-39`), pero el endpoint no utiliza ese lector. Las pruebas de recursos existentes cubren el lector general (`tests/imports/test_reader_resource_limits.py:130-142,242-261`), no `/parse-xlsx`, y no encontré test de la ruta contra dimensión inflada. QA1/QA2 rechazan: aplicar límites mientras se lee el endpoint (sin confiar en dimensiones declaradas) o usar el lector limitado compatible, y agregar regresión HTTP con XLSX reducido y dimensión inflada que pruebe respuesta controlada sin materialización excesiva. GitHub conserva `needs-work`.

### #1212 — QA1/QA2 rechazan: conciliación acepta filas de inventario duplicadas

Leí el issue y su comentario completo. Revisión estática independiente, sin ejecutar pruebas/linters ni modificar código o GitHub.

El alta guarda todas las líneas sin validar unicidad de `(artículo, bodega)` (`inventario/services.py:741-755`); la ruta POST no agrega guard (`inventario/routes.py:910-914`). Edición también reconstruye las líneas sin impedir duplicados (`services.py:1058` en adelante). El posting recorre las líneas sin orden ni guard de duplicado y actualiza snapshots secuencialmente (`posting_service.py:3081-3112`). `StockEntryItem` no tiene constraint única para la combinación y el formulario permite agregar la misma combinación varias veces (`database/__init__.py:1570`; `stock_reconciliation_nuevo.html:211`).

No encontré cobertura para duplicado exacto ni control positivo del mismo artículo en bodegas distintas. QA1 y QA2 rechazan: validar la clave de negocio al guardar y editar, proteger el posting ante evidencia duplicada preexistente y agregar pruebas que rechacen la repetición manteniendo permitida la distribución legítima por bodega. GitHub sigue `needs-work`; etiquetas y comentarios intactos.

### #1225 — QA1/QA2 rechazan: tipo documental no validado en factura de venta

Leí el issue y su comentario completo. Revisiones estáticas independientes; no ejecutaron pruebas/linters ni modificaron código o GitHub.

`_prepare_sales_invoice_creation()` acepta el valor POST sin validar (`ventas/services.py:2259-2285`) y `_build_sales_invoice_from_context()` lo persiste (`:2288-2305`). El modelo declara `String(50)` sin CHECK (`database/__init__.py:3071`). La aprobación (`ventas/routes.py:2493-2517,2546-2549`) usa validación genérica que no verifica subtipo (`document_flow/validation.py:214-256`); el posting despacha por clase ORM a `post_sales_invoice` (`contabilidad/posting_service.py:4946-4947`), que tampoco rechaza valores desconocidos (`:1237`). Por tanto, un tipo arbitrario puede quedar aprobado como factura regular y fuera de los listados tipados.

`test_document_subtype_creation_and_lists.py` cubre encabezados/filtros para subtipos válidos, pero no POST desconocido ni aprobación de un borrador desconocido. QA1 y QA2 rechazan: aplicar el mismo allowlist de los cuatro subtipos al crear y como defensa al aprobar, y verificar por HTTP los tipos válidos y el desconocido, sin persistencia ni GL ante rechazo. GitHub permanece `needs-work`; etiquetas y comentarios intactos.

### #1262 — QA1/QA2 rechazan: no se permiten cargos legítimos sin referencia

Leí issue y sus cuatro comentarios completos. Revisiones estáticas independientes en el worktree actual; no se ejecutaron pruebas/linters ni se modificó código o GitHub.

El importador directo ya no es consumidor productivo; `ImportService` usa `BankStatementAdapter`. El criterio funcional permanece incumplido en esa ruta: el adapter preconsulta igualdad de cuenta/fecha/referencia/monto (`imports/adapters/bank_statement.py:204-220`), y `BankTransaction` tiene UNIQUE `identity_key` (`database/__init__.py:4115-4117`) calculada a partir de cuenta, fecha, referencia normalizada a vacío e importes (`:4150-4159`). Por ello dos movimientos legítimos de la misma fecha/importe sin referencia colisionan tanto en el guard como en DB, aun con descripciones distintas. El guard de la restricción es útil para carreras y reimport con identidad estable, pero no distingue transacciones potencialmente legítimas sin referencia.

Los tests actuales afirman explícitamente rechazar el caso NULL versus cadena vacía (`test_bank_transaction_identity_uniqueness.py:189-227`) y duplicados intra-lote (`:327-349`); falta el test requerido que acepte dos movimientos sin referencia con misma fecha/importe. QA1/QA2 rechazan: cambiar la política de identidad persistida para que la fecha y el importe no deduzcan identidad cuando falta referencia, preservar idempotencia cuando exista identificador fiable y cubrir el flujo activo incluyendo dos movimientos idénticos legítimos. GitHub conserva `needs-work`; etiquetas y comentarios intactos.

### #1263 — QA1/QA2 rechazan: tolerancias bancarias sin validar

Leí issue y sus tres comentarios completos. Revisiones estáticas independientes; no se ejecutaron pruebas/linters ni se modificó código o GitHub.

El POST convierte `days_tolerance` con `int()` y `amount_tolerance` con `Decimal()` sin límite, finitud ni manejo de entrada inválida (`bancos/routes.py:697-721`). La plantilla mantiene campos texto (`bancos/templates/bancos/reglas_matching.html:10-11`). Los comentarios reproducen persistencia de negativos e `Infinity`, y HTTP 500 con `abc`. El modelo no añade constraints para estos rangos (`database/__init__.py:5007-5029`).

La ruta de lectura tampoco protege reglas heredadas: `_resolve_rule_tolerances()` convierte el importe a Decimal y elige el máximo sin comprobar valor finito/no negativo (`bancos/reconciliation_service.py:520-549`); `_candidate_tolerances()` retorna valores explícitos o resueltos sin validar (`:552-560`). Los días negativos se convierten silenciosamente en cero (`:711-712`), mientras Infinity puede hacer que cualquier diferencia finita pase el umbral y producir estado exacto (`:485-516`), habilitando la auto-conciliación. Los tests de reglas bancarias cubren alcance con valores válidos, no negativos/no finitos/malformados ni reglas inválidas heredadas. QA1/QA2 rechazan: validar la entrada antes de confirmar, transformar errores a respuesta controlada y validar también el contrato al resolver datos persistidos; cubrir límites finitos válidos, negativos, NaN/±Infinity, texto inválido y fallo seguro de reglas históricas. GitHub permanece `needs-work`, etiquetas y comentarios intactos.

### #1265 — QA1/QA2 rechazan: setup selecciona cuenta de caja chica no operable

Leí issue y sus dos comentarios completos. Revisiones estáticas independientes; sin pruebas/linters y sin modificar producto o GitHub.

`create_default_petty_cash()` elige la primera cuenta por código filtrando entidad, tipo y `group=False`, pero no `active`/`enabled` ni reutiliza `_validate_petty_cash_account()` (`bancos/services.py:622-635`, validación normal `:447-458`). Si no encuentra cuenta retorna `None`; `setup/service.py:128` ignora el resultado y no informa que no se creó el fondo. La ruta de uso posterior `_petty_cash_gl_account_code()` verifica existencia, pero no estado de la cuenta (`services.py:842-849`), por lo que una desactivación posterior tampoco falla temprano por el contrato de vigencia.

La única prueba de creación directa cubre cuenta activa y moneda (`tests/test_setup_petty_cash_currency.py:32-71`); las pruebas de setup concurrente solo cubren idempotencia. QA1 y QA2 rechazan: seleccionar solamente una cuenta que satisfaga el contrato normal, no crear/avisar observablemente si no hay candidata utilizable, y proteger el consumo de una cuenta luego inactiva; cubrir activa anterior/inactiva por código, deshabilitada, ausencia y vigencia al usar el fondo. GitHub conserva `needs-work`; etiqueta y comentarios intactos.

### #1271 — QA1/QA2 aprueban estáticamente: ajuste único de caja chica

Leí issue y sus cinco comentarios completos. Revisiones independientes; no se ejecutaron pruebas/linters ni se modificó código o GitHub. El comentario de QA previo que vio solo SQLite ya está superado por la cobertura actual.

`test_petty_cash_replenishment_approval.py` está marcado `pytestmark = pytest.mark.database` y `replenishment_app` conserva `DATABASE_URL` para motores externos (`:68,98-115`); `.github/workflows/databases.yml:51-70,72-92` ejecuta la marca en PostgreSQL con psycopg2 y pg8000. `test_concurrent_reconciliation_adjustment_posts_one_journal` crea dos sesiones/contextos y sincroniza ambas solicitudes (`:1136-1303`), exige un solo `posted`, puntero al diario enviado y dos líneas GL balanceadas. El fallo al guardar el enlace se prueba mediante trigger SQLite y valida rollback del diario/GL (`:1219-1254`).

La ruta bloquea y refresca la conciliación con `SELECT FOR UPDATE`/`populate_existing` (`bancos/services.py:1303-1318`), valida el puntero antes de crear, crea y envía diario con `commit=False`, actualiza puntero bajo condición `IS NULL` y confirma en conjunto; errores revierten (`:1366-1387,1390-1466`). El segundo concurrente obtiene conflicto explícito; la evidencia no queda duplicada. QA1 y QA2 aprueban estáticamente. La issue permanece `needs-work` en GitHub por autorización de etiquetas: no se cambió etiqueta; falta QA3/autorización final. Límite residual: el failpoint de rollback a nivel motor se cubre solo en SQLite; concurrencia real se incluye en las corridas Postgres.

### #1291 — QA1/QA2 rechazan: XLS nativo sigue fuera del contrato de fechas

Leí issue y sus dos comentarios completos. Revisiones estáticas independientes sobre el worktree actual, sin tests/linters ni cambios de producto/GitHub.

El contrato común convierte `datetime` tipado a ISO (`imports/readers/base.py:20-23,47-50`) y XLSX con openpyxl entrega esas fechas tipadas. El lector XLS sigue leyendo `ws.cell_value()` sin comprobar `cell_type` o preservar `wb.datemode` (`imports/readers/xls_reader.py:43-50`); el serial fecha se convierte en texto decimal por `TabularBook` (`base.py:24-31`). El parser de fechas usa época fija 1899-12-30 y no toma datemode (`imports/utils/dates.py:17,32-50`), así que los XLS nativos se rechazan o desvían en sistema 1904; serial 60 también se acepta aritméticamente como 1900-02-28 sin cubrir la fecha ficticia/ambigua de Excel.

`test_readers_contract.py` verifica XLSX nativo pero la fixture XLS contiene fecha ISO textual (`:35-41,83-101,104-125`); las pruebas helper directas no cubren seriales XLS desde reader, 1904, serial 60 o ambigüedad por formato (`test_import_date_normalization.py:69-89`). QA1 y QA2 rechazan: normalizar fechas XLS/XLSX nativas con el sistema de fechas del libro, conservar valores ya tipados y cubrir ambos sistemas y celdas inválidas hasta el consumidor. GitHub continúa `needs-work`, etiquetas y comentarios intactos.

### #1292 — QA1/QA2 rechazan por cobertura contractual pendiente

Leí issue y sus dos comentarios completos. Revisiones estáticas independientes; no se ejecutaron pruebas/linters ni se modificó código o GitHub.

La regla productiva está implementada para el camino habitual: `_finite_amount()` usa `coerce_decimal(..., positive=True, max_fractional_digits=4)` y se aplica en validación de fila, construcción y persistencia (`imports/adapters/cash_forecast_entry.py:17-20,45-58,91-112,131-134`). Construcción también normaliza Income/Expense (`:68-73`). Persistencia directa revalida monto y estado, pero no revalida explícitamente el tipo si recibe un documento construido manualmente (`:114-145`).

La cobertura no satisface el criterio añadido por el comentario. `test_cash_forecast_import_amount.py:101-141` prueba no positivos y número de hoja/espacios, todos como `Income`; `:144-186` prueba persistencia directa. El test no finito verifica NaN en validación e Infinity en build, sin -Infinity (`test_import_non_finite_validation.py:161-179`). `test_ctm_cash_forecast_import.py:95-145` prueba con adapter directo un ingreso válido y rollback por moneda inválida, no archivos CSV/XLSX ni la ruta ImportService ni un lote con monto inválido. El servicio valida el lote antes de ejecutar y no persiste si la prevalidación da error (`imports/services/import_service.py:514-523`); commit posterior es por documento (`:444-458`), por lo que la regresión debe probar ese contrato real sin asumir rollback global ante fallos tardíos. QA1 y QA2 rechazan por cobertura; falta verificar Income y Expense, formatos realistas, no finitos y no positivos por la ruta de importación, rollback/no persistencia del documento/lote al fallar la validación, y guard del tipo también en persistencia directa. GitHub conserva `needs-work`, etiqueta y comentarios intactos.

### #1295 — QA1/QA2 rechazan: el worker puede finalizar una segunda lectura vacía

Leí issue y sus cuatro comentarios completos. Revisiones estáticas independientes; no se ejecutaron pruebas/linters ni se modificó producto o GitHub.

La validación inicial detecta tabla sin filas luego de estructura y registra `NO_DATA_ROWS`/estado 7 (`imports/services/import_service.py:151-157,333-344`). `execute()` también falla ante archivo vacío en su primera lectura (`:404-424`). Pero el worker `_execute_task()` vuelve a leer la fuente y no verifica `table.rows` luego de esa segunda lectura (`:492-535`); si desaparece o se vacía entre preflight y worker, agrupa cero documentos y `_finalize_execution(..., 0, 0)` puede poner estado 5 completado (`:591-610`). Este es el mismo consumidor/cause-root que #1200; #1295 pide coordinar una corrección y no duplicarla.

`test_import_empty_file_rejected.py:95-120` solo usa CSV con encabezado; su prueba de ejecución sale en el preflight síncrono, no alcanza la relectura del worker. No hay regresión de fuente vaciada entre lecturas, archivo 0 bytes, control válido o contrato file-level para XLS/XLSX/ODS. QA1 y QA2 rechazan por el defecto de éxito vacío vigente, con brecha adicional en cobertura de formatos pedida por el triaje. Falta repetir guard en worker, error `NO_DATA_ROWS` accionable/estado no exitoso y test de carrera de lectura, más controles de formatos vacíos y una fila válida. GitHub `needs-work`; etiqueta y comentarios intactos.

### #1296 — QA1/QA2 rechazan: guardas de dominio no cubren las fronteras HTTP

Leí issue y sus cuatro comentarios completos. Revisiones estáticas independientes; no se ejecutaron pruebas/linters ni se modificó producto/GitHub.

El servicio aplica buena regla de dominio: `parse_item_uom_rows()` rechaza NaN/±Infinity (`inventario/service.py:899-914`); `validate_item_uom_rows()` rechaza factor no finito, cero/negativo (`:917-937`); alta y edición validan antes de persistir/reemplazar (`:721-726,950-953`); conversión revalida factores persistidos y resultado (`:241-283`). No encontré adaptador de importación que escriba conversiones UOM; las fronteras activas son formularios de alta/edición.

Pero ambos endpoints parsean antes de su handler: alta llama `_item_uom_rows_for_template()` (`inventario/routes.py:429-430`) antes del try de `:433-445`; edición lo hace antes de `_process_item_edit()` (`:514-518`). El helper invoca el parser (`inventario/services.py:403-408`), así que NaN/Infinity y decimal inválido escapan como HTTP 500 en vez de respuesta validada sin mutación. Los tests `test_inventory_uom_factor_validation.py:89-159` solo prueban helpers/servicios, no HTTP de alta/edición ni edición sin cambio persistido; faltan casos explícitos cero/negativo.

`ItemUOMConversion.conversion_factor` se guarda como `Numeric(20,9)` (`database/__init__.py:1454`), pero parser/validador aceptan positivos por debajo de la escala, p.ej. `1e-10`; en PostgreSQL puede redondearse a cero pese al requisito de factor estrictamente positivo. El `step` HTML 1e-9 no es guard servidor. QA1 y QA2 rechazan: contener errores en ambos formularios, probar HTTP/rollback y crear/editar finitos válidos y casos inválidos, y rechazar o canonizar importes no representables con la escala real de almacenamiento para evitar divergir entre motores. GitHub conserva `needs-work`; etiqueta/comentarios intactos.

### #1300 — QA1/QA2 rechazan: cuentas AR/AP inválidas pueden recibir posting

Leí issue y sus dos comentarios completos. Revisiones estáticas independientes; no se ejecutaron pruebas/linters ni se modificó producto/GitHub.

Configuración `party_settings._validate_account()` comprueba pertenencia a compañía, pero acepta tipo vacío y no valida hoja/active/enabled (`party_settings.py:444-455`). También el guard de asignación de cuentas por defecto comprueba tipo solo si existe, sin esos flags (`default_accounts.py:192-205`); el validator de consumo de GL tiene bypass de tipo vacío y no verifica entidad/estado/grupo (`:236-261`).

El posting legacy de factura de venta/compra resuelve cuenta AR/AP de PartyAccount o defaults y aplica `_require_account()`, que solo exige existencia (`contabilidad/posting_service.py:397-432,1247-1251,1341-1345`). `_require_company_account()` sí valida ownership, active/enabled/leaf, pero no se aplica a AR/AP. El motor contable hace la misma resolución en `_party_account_id()` (`accounting_engine/document_builders.py:1811-1824`) y luego solo requiere existencia (`:1876-1882`; `gl_posting_builder.py:69-98`). Sin un vínculo FK compuesto, un mapping heredado/incoherente puede apuntar a cuenta de otra compañía; ambos caminos pueden registrar GL con compañía documental y cuenta extranjera o no contabilizable.

Las pruebas de settings encontradas usan cuentas válidas y no cubren estos estados ni posting en ambos motores (`tests/test_party_company_settings_validation.py`). QA1/QA2 rechazan: imponer al guardar y al consumir una cuenta hoja, activa, habilitada, de compañía exacta y tipo explícito AR/AP esperado; aplicar defensa tanto al posting legacy como al motor para mappings/defaults heredados, y probar cada clase inválida sin GL. GitHub permanece `needs-work`; etiqueta y comentarios intactos.

### #1302 — QA1/QA2 rechazan: quedan bypasses en ciclo de vida S2P

Leí issue y sus siete comentarios completos. Revisiones estáticas independientes en el worktree vigente; no se ejecutaron pruebas/linters ni se modificó código o GitHub.

La ampliación histórica a PO sí está resuelta en el árbol: `_purchase_order_context()` y la edición usan `_validated_purchase_supplier()` (`compras/services.py:1551-1574,1682-1696`) y submit también (`compras/routes.py:2559-2560`); el helper exige Party existente/activo/rol proveedor y CompanyParty activa (`services.py:2477-2498`).

Los otros consumidores ampliados aún omiten parte o todo el contrato. Alta de PurchaseInvoice valida vínculo activo, pero no estado/rol del Party; edición llama flags que consultan CompanyParty sin `is_active`; submit hace lo mismo y prerequisitos genéricos solo exigen ID (`services.py:2444-2468,2874-2890,2995+`; `routes.py:3386-3415`). Alta de PurchaseReceipt comprueba CompanyParty activa pero no estado/rol del Party; edición persiste supplier/company enviados sin guard y submit no revalida vínculo (`services.py:1878-1893,1930-1948`; `routes.py:2991-3034`). SupplierQuotation no valida proveedor en alta/edición ni en submit; el prerequisito genérico solo verifica identificador (`services.py:401-449,552-585`; `routes.py:955-980`). Esto coincide con comentarios reproducidos en #1302 para receipt, factura, PO y quotation, pero no se asume vigente lo que quedó en HEAD antiguo: PO se verificó ya corregida.

No encontré regresiones para la transición de vínculo activo→inactivo durante borrador, para rol/estado del proveedor, ni para estos submits/ediciones. QA1/QA2 rechazan: usar guard canónico de existencia/rol/estado Party y CompanyParty activa en creación, edición y aprobación de invoice, receipt y SupplierQuotation; preservar la PO ya cubierta y probar rechazos sin postear. GitHub sigue `needs-work`, etiqueta y comentarios intactos.

### #1339 — QA1/QA2 rechazan: tipos inactivos aceptan valores y discovery los expone

Leí issue y sus siete comentarios completos. Revisiones estáticas independientes; no se ejecutaron pruebas/linters ni se modificó producto/GitHub.

`_add_dimension_value_from_request()` solo verifica que ID y valor no estén vacíos; inserta `DimensionValue(is_active=True)` y confirma sin cargar `DimensionType` ni verificar vigencia (`admin/routes.py:752-770`). El selector itera todos los tipos recibidos y la ruta pasa todos sin filtro activo (`admin/templates/admin/dimension_values.html:35-39`; `routes.py:786`). `query_tools.handlers.discovery.list_dimensions()` filtra tipo activo (`:250-260`), pero `search_dimension_values()` solo exige que el propio valor esté activo y compañía visible; no verifica el estado del tipo padre (`:274-300`). Así un tipo inactivo sigue aceptando altas y sus valores pueden buscarse por ID.

`DimensionValue.dimension_type_id` tiene FK RESTRICT (`database/__init__.py:4588-4600`), y el hook SQLite vigente activa foreign keys (`:60-74`); por ello no doy por probada la persistencia de huérfanos observada por un probe histórico con PRAGMA=0. Aun con FK activa, el endpoint no maneja el IntegrityError de un ID inexistente como validación controlada; la falla de tipo inactivo no depende de FK. No encontré test activo de la pantalla administrativa o del discovery de dimensiones; el `tests/test_dimensions_admin.py` referido no existe en checkout. QA1/QA2 rechazan: cargar y exigir tipo existente/activo antes de insertar; filtrar selector; hacer que búsqueda de valores no sirva tipos desactivados; cubrir inexistente, inactivo y acceso discovery a valor bajo padre inactivo. GitHub sigue `needs-work`; etiqueta y comentarios intactos.

### #1342 — QA1/QA2 rechazan: ID explícito ignora el alcance por cuenta

Leí issue y sus dos comentarios completos. Revisiones estáticas independientes; no se ejecutaron pruebas/linters ni se modificó producto/GitHub.

`render_preview_html()` y `render_pdf()` construyen contexto y pasan `bank_account_id` real del cheque a `resolve_template()` (`printing/service.py:131-137,189-195,350-355`). Sin embargo, con `template_id` explícito `resolve_template()` retorna antes por `_resolve_template_by_id()` (`:314-315`), que solo valida tipo documental, compañía y estado publicado; no compara `template.bank_account_id` con la cuenta del cheque (`:633-647`). Preview reenvía el mismo ID explícito a la URL PDF (`printing/routes.py:45-64`) y PDF acepta ID directamente (`:80-89`). Así un cheque de cuenta A puede utilizar plantilla asociada a cuenta B por URL. La resolución default sin ID sí prioriza cuenta y luego company/global genéricas (`service.py:334-348`).

No encontré regresiones para template explícito de otra cuenta en preview y PDF. `test_print_pdf_page_settings.py` sustituye el contexto/resolver para probar orientación/tamaño, no el alcance bancario; no existe `test_check_printing.py` en este checkout. QA1/QA2 rechazan: comparar el alcance de cuenta en plantilla explícita con la cuenta del documento y cubrir rechazo en ambos endpoints, además de permitir la plantilla de la misma cuenta y los scopes genéricos autorizados.

Hallazgo separado que requiere decisión de negocio: el formulario permite `company_code=NULL` junto a `bank_account_id` específico (`printing/admin_routes.py:97-100,345-360`; plantilla `:47-63`), pero el resolvedor default consulta global solo con `bank_account_id IS NULL` (`printing/service.py:649-665`). Esa combinación es aceptada pero inalcanzable mediante defaults. El comentario #1342 deja abierto si se prohíbe o se define una precedencia; no inferí ninguna semántica. GitHub conserva `needs-work`; etiqueta y comentarios intactos.

### #1345 — QA1/QA2 aprueban cobertura del contrato ODS

Leí el issue y sus dos comentarios. La aceptación pide que `ODSReader` devuelva todas las filas representadas por `number-rows-repeated`. `ods_reader.py` captura el repeat, rechaza encabezado repetido, consume el presupuesto de filas/celdas antes de expandir y agrega copias independientes de la fila. `tests/test_reader_resource_limits.py` crea un ODS real con repeat=2 y verifica dos filas separadas; también cubre exceso de límites, repeat inválido y encabezado repetido. QA1 y QA2 aprobaron independientemente la cobertura literal; la prueba end-to-end de ImportService sería mejora, no requisito bloqueante del issue. No se ejecutaron pruebas/linters ni se modificó producto/GitHub. La etiqueta permanece intacta.

### #1348 — revisión estática propia: saldo de apertura y separación por cuenta ausentes

Leí el issue, sus dos comentarios y los 15 comentarios del paraguas #1709. `get_bank_movement_detail()` fija el rango consultado y `_process_payment_entries()`/`_process_bank_transactions()` filtran al rango antes de armar filas (`reportes/services.py:2095-2112,1989-2034`). `_compute_running_balance()` empieza siempre en `Decimal("0")` y acumula una lista global sin clave de cuenta (`:2037-2042`). Por tanto no incluye saldo anterior y mezcla dos cuentas de la misma moneda cuando `bank_account_id` no se filtra. Existe `_compute_gl_balance(company, bank_account_id, as_of_date)` y `BankAccount.gl_account_id`/`GLEntry.bank_account_id` para el saldo por cuenta (`:2351-2361`, `database/__init__.py:3170-3203,4440+`), pero el detalle no lo consulta; además el helper filtra mediante `exclude_cancelled_gl_entries`, que excluye reversas sin fecha efectiva, riesgo explícitamente documentado en #1709. QA1/QA2 rechazan independientemente con los mismos hallazgos. No ejecuté pruebas/linters ni modifiqué producto/GitHub.

### #1346 — QA1/QA2 rechazan: falta repro funcional y hay colisión en alias inglés

Leí los seis comentarios de #1346 y los 16 de #1652, incluida la ADR aprobada de validación estricta. El código local ahora detecta encabezados fuera del esquema (`import_service.py:219-268`) y valida estructura tanto en validación como en worker antes de agrupar (`:145-157,503-515`); así, `document_ref` añadido a Customer/Vendor/Chart llega a `UNKNOWN_COLUMN` en lugar de la pérdida descrita. La decisión satisface la opción de rechazar columnas desconocidas. Aun así, no hay prueba de ImportService que reproduzca `document_ref,nombre` con dos filas y verifique estado/error/ausencia de persistencia o contadores; la única prueba `UNKNOWN_COLUMN` usa una fila sin encabezados que termina siendo interpretada como encabezado (`test_import_structure.py:110-125`). Tampoco hay cobertura funcional para Vendor/Chart ni referencias repetidas/vacías dentro de tipos documentales válidos.

QA2 detectó además colisión introducida en el diff: `JournalEntryAdapter` tiene la columna canónica `referencia`, traducida al inglés como `reference` (`column_labels.py:19`), pero el `column_aliases` agregado reasigna `reference` a `document_ref` (`journal_entry.py:45-54`). Una plantilla inglesa emite `document_reference` y `reference`, ambas terminan como `document_ref`; el validador luego ve duplicado y bloquea una plantilla válida. QA1 y QA2 rechazan independientemente. No ejecuté pruebas/linters ni modifiqué código o GitHub.

#### Reevaluación del diff local vigente

La validación nueva sí rechaza columnas desconocidas antes de `_group_by_reference()`, lo que previene el descarte reportado si `document_ref` se añade a Customer/Vendor/Chart. Pero la regresión editada solo cambia el caso de archivo sin encabezado (`test_import_structure.py:118-125`); no hay prueba integrada de las dos filas con `document_ref,nombre`, rechazo estructural, cero persistencia y contadores sin éxito. El alias conflictivo sigue en el árbol y rompe además el template inglés de comprobantes. QA1/QA2 mantienen #1346 rechazado; sin pruebas/linters ni cambios remotos.

QA2 revisó el diff actual independientemente y coincide: alta y worker revalidan el esquema antes de agrupar/persistir, pero el test actual falla también por `MISSING_COLUMN` y no discrimina el encabezado extra con requeridos válidos ni verifica Customer/Vendor/Chart y contadores. Confirma además la colisión inglesa `reference` → `document_ref`. Sin cambios remotos.

### #1352 — QA1/QA2 rechazan: helper huérfano y documentación divergente

Leí los seis comentarios de #1352, los 92 del paraguas #1658 (incluidos hallazgos #27/#66/#91 sobre helper, snapshots y alcance) y los cuatro de #2248. La decisión operativa focal más reciente, junto con la política pre-alpha de #2248, es retirar `reverse_from_snapshot()` si no hay consumidor de producción, preservando reversión efectiva/evidencia append-only y cualquier snapshot con uso real.

La búsqueda del símbolo en `cacao_accounting/`, `tests/` y documentación encuentra solo la definición `event_orchestrator.py:141`; el test aislado histórico ya no está en checkout. El helper sigue ocupando `:141-272`. `handle_event()` aún genera `results["snapshot"]` en memoria (`:110-112`), pero los consumidores de posting usan proforma y otros resultados, no guardan ese snapshot; `SnapshotSerializer` no crea `snapshot_id` (`snapshots/serializer.py:43-53`). Ambas docs de tax-cost-engines siguen afirmando que se guarda JSON al confirmar y se usa el snapshot para reversión (`auditability.es.md` y `.md`, líneas 7-12). QA1/QA2 rechazan por retiro pendiente y discrepancia documental no resuelta. No se deben retirar las reversiones GL/AR/AP reales ni snapshots fiscales de línea que sí tienen consumidores. No se ejecutaron pruebas/linters ni se modificó código/GitHub.

### #1353 — QA1/QA2 rechazan: categoría fiscal sigue inerte

Leí issue y sus cuatro comentarios; la última decisión funcional define `allowed_item_categories` opcional, evaluada por línea, para inventario/no inventario/servicios, desde el catálogo actual, sin coincidencia si falta categoría y complementaria a las condiciones fiscales existentes.

En el árbol solo existe `TaxRuleContext.allowed_item_categories` (`accounting_engine/common/context.py:63`). `Item.item_category_id` sí enlaza `ItemCategory` (`database/__init__.py:1383-1388,1494-1500`), pero `ItemContext` no modela categoría; `TaxRule` no persiste el filtro; `_apply_tax_rule_values()`/`_to_context()` y la UI administrativa no lo exponen. Builders productivos de líneas de compra/venta y preview omiten la categoría. `FiscalEngine.calculate()` procesa cada regla sobre el total del documento y `_build_fiscal_line()` asigna todos los items; no filtra por línea. `rg` no encuentra pruebas para `allowed_item_categories`. QA1/QA2 rechazan independientemente: faltan persistencia/configuración, propagación y evaluación por línea con cobertura de preview/posting y casos requeridos. No ejecuté pruebas/linters ni modifiqué código/GitHub.

### #1359 — QA1/QA2 rechazan: contrato de integración no implementado y schema retirado

Leí los siete comentarios de #1359, siete de #1340 y cuatro de #1368. La decisión funcional más reciente exige integrar dimensiones analíticas al GL desde documento/línea, validar compañía, tipo/valor/autorización y unicidad/precedencia de #1340, propagar a todos los libros, persistir inmutable por entrada GL, consultar/reportar con RBAC y conservar originales en reversión append-only.

En el checkout no existe `GLEntryDimension` ni `gl_entry_dimension`: el commit `0a7db7b2` retiró el modelo y agregó la migración `20261109_0004_drop_gl_entry_dimension.py` (#1841/#1649); `tests/test_dead_code_inventory.py` también registra su ausencia. La administración y discovery de `DimensionType`/`DimensionValue` siguen expuestos, pero el catálogo no llega a las líneas GL. `DimensionType` es global con unicidad solo por nombre; `DimensionValue` no tiene unicidad scoped/normalizada. Admin inserta valores sin el guard de duplicados y discovery devuelve valores globales+locales sin precedencia (contradice la decisión #1340 de local sobre global). No se halló captura de valores por línea, propagación, persistencia o lectura dinámica en reportes. Las pruebas de dimensiones existentes cubren cost_center/unit/project, no esta capacidad. QA1/QA2 rechazan. Para implementar la decisión actual hace falta restablecer el modelo/contrato de asociación con migración posterior que cree schema y actualizar el inventario de retiro; el commit de limpieza previo no sustituye la decisión funcional posterior. No ejecuté pruebas/linters ni modifiqué producto/GitHub.

### #1361 — QA1/QA2 aprueban estáticamente el retiro

Leí el issue y sus tres comentarios. `SPECIAL_ACCOUNT_TYPES` está retirado por `a93657fa`; una búsqueda del checkout no encuentra referencias en código/tests/docs. El diff elimina solo esa definición. `DEFAULT_ACCOUNT_DEFINITIONS`, `ACCOUNT_TYPE_ALLOWED_VOUCHERS`, `MANUAL_BLOCKED_ACCOUNT_TYPES` y `validate_gl_account_usage()` siguen intactos y tienen consumidores en posting normal y revaluación cambiaria (`default_accounts.py:110-141,236-261`; `posting_service.py:897`; `exchange_revaluation_service.py:915`). QA1/QA2 aprueban independientemente el retiro puro. Límite no bloqueante: no encontré prueba dedicada a la matriz de voucher/tipo, pero la eliminación no altera esa lógica; pruebas operativas existentes cubren validación de cuentas de pago/banco/inventario. No ejecuté tests/linters ni modifiqué código/GitHub. La etiqueta queda intacta.

### #1364 — QA1/QA2 rechazan: guard parcial sin regresiones y alta admite ronda inválida

Leí el issue y sus seis comentarios; el paraguas #1708 tiene 11 comentarios y su ADR confirma fail-closed para aprobaciones, sin decisión que debilite el contrato de ronda. En adjudicación, `submitted_supplier_quotations()` restringe ofertas a `current_negotiation_round().id` (`purchase_sourcing_service.py:185-197`); `_find_manual_override_items()` rechaza ID seleccionado fuera de esa lista y `create_purchase_quotation_award()` valida antes de `_flush_award` (`:285-329`). La ruta POST delega y hace rollback ante `PurchaseSourcingError` (`compras/routes.py:1485-1508`).

Pero no hay prueba de servicio ni POST que intente adjudicar oferta de ronda cerrada ni verifique que no se persista award. Tests actuales prueban cierre manual, no oferta antigua. Hallazgo adicional QA2: alta de cotización de proveedor con `from_rfq` convierte `negotiation_round_id` inexistente, ajeno, cerrado o ausente en `None` (`compras/services.py:410-418`) y sigue creando el borrador; submit (`routes.py:955-977`) no revalida ronda. Con una RFQ ya rodada, esto deja aprobar cotización huérfana de ronda en vez de rechazar mismatch/None exigido. No hay prueba de esa transición. QA1/QA2 rechazan por regresiones faltantes y guard incompleto de quote. No ejecuté pruebas/linters ni cambié producto/GitHub.

### #1365 — QA1/QA2 rechazan: cierre de solicitud cuenta selección obsoleta

Leí issue y sus cuatro comentarios; el criterio final exige mantener abierta la solicitud si la oferta seleccionada fue cancelada o deja de estar aprobada/vigente y cubrir comparativos `used`. `purchase_request_comparison_covered_item_ids()` cuenta cualquier línea seleccionada de comparativo `finalized`/`used` sin unir/verificar el `SupplierQuotation.docstatus` (`purchase_request_comparison_service.py:418-435`). `purchase_request_is_ready_to_close()` usa ese conjunto (`:502-521`), y GET/POST de cierre habilita/cierra si todas las líneas están cubiertas (`compras/routes.py:455,467-484`). `purchase_request_line_closure_reasons()` también registra razón de cierre sin comprobar vigencia (`service.py:467-494`). La generación de OC revalida oferta aprobada, pero no protege cierre de solicitud (`:559+`). QA1/QA2 rechazan; no encontré regresión del escenario finalizar → cancelar oferta sin relación activa → cerrar ni cobertura `used`. El comentario menciona adicionalmente que órdenes canceladas pueden seguir visibles como participantes (#2141), pero es superficie separada y no la mezclo en esta evaluación. No ejecuté pruebas/linters ni modifiqué producto/GitHub.

### #1367 — QA1/QA2 rechazan: motivo sin normalizar y sin evidencia persistida

Leí issue y sus tres comentarios; el criterio final exige mantener la política actual, quitar espacios antes de validar y persistir la razón junto al actor autorizador, con pruebas de válido, vacío/espacios, no autorizado y rollback.

`_purchase_order_context()` lee `comparison_exception_reason` crudo y `_validate_purchase_order_sourcing()` evalúa truthiness; un gerente puede enviar `"   "` y pasar la excepción (`compras/services.py:1399-1412,1551-1557`). `PurchaseOrder` no tiene campos del motivo ni autor, y `_create_purchase_order_from_request()` solo asigna `purchase_award_id` y guarda la orden/log estándar (`:1587-1598,1639+`). Pruebas de motivo/actor en `test_purchase_sourcing_authorization.py` son para adjudicaciones, no para excepción de creación de OC; no encontré prueba POST del caso issue ni rollback. QA1/QA2 rechazan. No ejecuté pruebas/linters ni modifiqué producto/GitHub.

### #1372 — QA1/QA2 rechazan: fecha fiscal parcial sigue descartándose

Leí el issue y sus dos comentarios; la reproducción SQLite confirma el fallback al año calendario. `SetupCompanyForm` permite inicio/fin opcionales independientemente y valida el rango solo si existen ambas (`setup/forms.py:68,100-109`). El servicio envía esos valores al repositorio (`setup/service.py:108-113`). `create_default_fiscal_year()` usa el rango aportado solo si ambas fechas son no nulas; si falta una, sustituye ambas por el año calendario de `reference_date` o del día actual (`setup/repository.py:304-320`). No hay rechazo del formulario ni aviso en setup. Pruebas encontradas usan ambos extremos y no cubren inicio o fin parcial por helper o HTTP. QA1/QA2 rechazan independientemente. No ejecuté pruebas/linters ni modifiqué código/GitHub.

### #1375 — QA1/QA2 rechazan: validación de notas sin regresión completa

Leí el issue y su comentario; también los 11 comentarios de #1708. El padre exige que cada tipo de documento cubra sus transiciones con regresiones, y la ADR reafirma aprobación fail-closed sin aprobar automáticamente por ausencia de matriz. No encontré decisión adicional que cambie la regla específica de notas.

El defecto original de salida temprana está corregido en HEAD: `item_models` contiene las cuatro notas (`approval_engine.py:659-675`), y el flujo pasa por validación de moneda, líneas/prerrequisitos y validadores de ventas/compra (`:697-718`). Sin embargo, `require_amount_nonzero` incluye notas de venta pero no `purchase_credit_note` ni `purchase_debit_note` (`:700-702`), por lo que una nota de compra con importe de línea cero no recibe el mismo guard final, aunque haya cantidad y tarifa válidas. No encontré prueba actual de aprobación para ninguno de los cuatro subtipos, ni de falta de líneas/moneda/reversión. Un test histórico en `d41cb51a` cubría una nota de débito de venta, pero el archivo fue eliminado por `0970476b clean`; no cuenta como regresión vigente.

`_validate_sales_submission()` solo llama `_validate_reversal_of()` cuando `reversal_of` viene informado (`approval_engine.py:568-583`), y el creador permite ese campo vacío (`ventas/services.py:2261-2285`). Esto queda documentado como punto de contrato a confirmar por producto antes de exigir una fuente; no lo convierto por inferencia en requisito. QA1/QA2 rechazan por la omisión de importe de compra y, principalmente, por falta de regresiones que acrediten las validaciones finales. No ejecuté pruebas/linters ni cambié código o GitHub; etiqueta `needs-work` intacta.

### #1377 — QA1/QA2 rechazan: KPI y tabla de AP aún excluyen créditos

Leí el issue y sus dos comentarios, incluida la ampliación a tabla `payables`, y los 15 comentarios de #1709. El paraguas confirma que los cortes/saldos deben tratar reversas por fecha efectiva; el criterio operativo específico de #1377 pide netear créditos abiertos en el KPI y mostrarlos en el detalle con signo económico.

`get_purchases_data()` continúa llamando `_sum_document_field(..., include_returns=False)` (`api/dashboard.py:327-333`), por lo que el helper filtra notas de crédito antes de aplicar el signo negativo (`:797-812`). `_payable_invoices()` también filtra `is_return=False` (`:617-627`), aunque `_purchase_invoice_payload()` ya serializa devoluciones con signo negativo (`:630-640`). Los queries limitan a `docstatus=1` y el detalle a saldo almacenado positivo; eso conserva el sentido de “abierto” según los saldos derivados actuales, pero no incluye los créditos para calcular el neto ni los presenta como fila. No encontré pruebas específicas de KPI/tabla de cuentas por pagar en `tests/`.

Con factura abierta 100 y crédito abierto 20, la ruta actual sigue mostrando KPI 100 y omite la nota; el resultado esperado es neto 80 y detalle con la nota por -20. QA1 y QA2 rechazan independientemente; no ejecuté pruebas/linters ni modifiqué código/GitHub. Etiqueta `needs-work` intacta.

### #1378 — QA1/QA2 rechazan: el árbol mezcla importe documental y del pago

Leí el issue y sus dos comentarios, incluida la extensión del total de referencias en `bancos/pago.html`, y los 17 comentarios de #1655. La asignación guarda `allocated_amount`/`currency` del documento y `payment_amount`/`payment_currency` del pago (`PaymentReference`); el criterio exige que importe y moneda correspondan en ambas direcciones del árbol.

En ambos sentidos `_append_payment_reference_nodes()` transmite `allocated_amount` como `applied_amount` (`document_flow/tree.py:690-725`). Cuando el nodo relacionado es `payment_entry`, su `currency` viene de `PaymentEntry` y el renderer etiqueta siempre `applied_amount` con `node.currency` (`document-flow-tree.js:128-129`); por ello factura 370 NIO + pago 3.70 USD se presenta como 370 USD desde factura. La dirección pago→factura sí necesita mantener allocated 370 NIO.

La extensión reportada también sigue: las filas de `pago.html` muestran allocated con `ref.currency`, pero el pie suma allocated y lo etiqueta con `registro.currency` (`:217,225`), mezclando moneda documental y del pago. No hallé pruebas que cubran árbol en ambas direcciones ni el total. QA1/QA2 rechazan independientemente; el árbol debe escoger/transportar monto+moneda según lado y el total del pago usar el monto de pago, con regresiones de multimoneda. No ejecuté pruebas/linters ni modifiqué código/GitHub; etiqueta `needs-work` intacta.

### #1380 — QA1/QA2 rechazan: cambio de cuenta conserva una tasa obsoleta

Leí el issue y sus dos comentarios, además del paraguas #1655. El caso reportado sigue activo: `applyBankAccount()` actualiza `header.currency` pero no invalida las tasas de `this.lines` (`pago_nuevo.html:218-230`). `normalizeReferenceAllocation()` conserva una `payment_exchange_rate` positiva y recalcula `payment_amount` usando esa tasa junto a la moneda nueva (`:252-270`); `prepareSubmit()` envía ambos (`:534-552`).

El backend vuelve a confiar en cualquier tasa positiva y deriva el monto de pago con ella; solo vuelve a resolverla si no es positiva (`bancos/services.py:2301-2309,2357-2374`). Por tanto cambiar una cuenta NIO por EUR puede persistir el monto con tasa NIO bajo la moneda EUR. Los tests contractuales existentes validan asignaciones con tasa recibida, no el cambio de cuenta después de cargar una referencia. QA1/QA2 rechazan independientemente. Invalidar/recalcular o exigir nueva tasa al cambiar moneda y cubrir valor mostrado/enviado/persistido; no ejecuté pruebas/linters ni modifiqué código/GitHub. Etiqueta `needs-work` intacta.

### #1381 — QA1/QA2 rechazan: guard de forecast no serializa frente a aprobación

Leí el issue y sus cinco comentarios y los 16 comentarios de #1656. El issue exige que el adaptador de importación rechace pronósticos no borrador, igual que alta manual; no hay comentario posterior que cambie ese contrato.

El guard secuencial está implementado en `validate_row()`, `validate_document()` y `persist_document()` (`cash_forecast_entry.py:45-52,75-89,114-130`). La regresión actual `test_cash_forecast_import_status.py:116-155` verifica borrador/aprobado y que un cambio secuencial del mismo objeto a Approved bloquee persistencia, pero no ejercita una segunda transacción. `_execute_task()` valida y persiste en la misma sesión (`import_service.py:518-557`); `persist_document()` llama `session.get()` y puede reutilizar la instancia Draft del identity map si otra sesión aprobó después del chequeo (`cash_forecast_entry.py:117`). La ruta de aprobación tampoco bloquea/serializa ese cambio (`cash_forecast.py:233-244`). Así, una importación concurrente podría agregar detalle tras aprobación pese al comentario del test que afirma cubrirlo. Tampoco vi casos Closed/Archived explícitos.

QA1/QA2 rechazan: hacer que aprobación e importación se serialicen mediante un guard transaccional efectivo en Tier 1 y probar el interleaving con dos sesiones (más estados Closed/Archived y rollback sin detalle), no solo mutar la instancia en memoria. No ejecuté tests/linters ni modifiqué producto/GitHub; etiqueta `needs-work` intacta.

### #1382 — QA1/QA2 rechazan: cero numérico se convierte en fallback de tasa

Leí el issue y sus tres comentarios. El comentario más reciente identifica explícitamente que `purchase_order` usa el adaptador genérico registrado por `ImportService`, no solo el archivo legacy; el paraguas #1655 no cambia el criterio operativo de distinguir celda vacía de cero explícito.

`ImportService.ADAPTERS["purchase_order"]` apunta a `PurchaseOrderAdapter` de `transaction_documents.py` (`import_service.py:83-87`). Este calcula `explicit_rate = first_row.get("tipo_cambio") or first_row.get("exchange_rate")` (`transaction_documents.py:352`): 0 numérico desaparece y puede activar fallback al origen o tasa histórica (`:358-365`), mientras que cadena `"0"` llega a `rate <= 0` y se rechaza (`:376-377`). El adaptador no registrado `imports/adapters/purchase_order.py` conserva igual omisión con `if raw_rate` (`:153-163`). Tests hallados cubren valores negativos/no finitos, pero no valor numérico cero frente a texto cero ni que se evite fallback histórico.

QA1/QA2 rechazan independientemente. Preservar valores explícitos al resolver aliases y rechazar cero antes de fallback; cubrir adaptador registrado con tasa histórica disponible, tipos numérico/texto y vacío/None legítimos. No ejecuté tests/linters ni modifiqué producto/GitHub; etiqueta `needs-work` intacta.

### #1386 — QA1/QA2 rechazan: falta prueba de selección de libro ajeno

Leí el issue y sus cinco comentarios; el último QA3 rechaza porque el test discriminante no estaba en el árbol entonces. El actual `tests/test_manual_journal_selected_books.py` sí existe, junto con el fix de `874d52ca`: prueba crear/editar/postear con un libro de dos activos y restringe los GL al seleccionado, omisión conserva todos los activos, libro inactivo se rechaza. El código valida ID/código contra `Book.entity == company` y estado activo (`journal_service.py:1173-1211`), persiste `book_codes` en creación/edición, y posting resuelve `_selected_books_for_journal()` antes de seleccionar contexts (`journal_service.py:1319-1327`; `posting_service.py:268-274,4603-4615`).

QA1 inicialmente aprobó al constatar prueba vigente; tras señalar QA2 la brecha del selector de otra compañía, QA1 retiró su aprobación. La única prueba específica de rechazo cubre libro inactivo de la misma compañía (`test_manual_journal_selected_books.py:80-93`); no existe regresión con libro activo de compañía ajena y garantía de que no se persista comprobante/GL. El filtro hace que la implementación aparente rechazarlo, pero el criterio exige libro activo y autorizado de esa compañía y `AGENTS.md` exige cobertura de aislamiento. Veredicto común final QA1/QA2: rechazar solo por esta brecha de cobertura, no por defecto del guard observado. Añadir test con ID/código de libro de otra compañía y ausencia de persistencia; luego repetir QA1→QA2. No ejecuté tests/linters ni cambié código/GitHub; etiqueta `needs-work` intacta.

### #1406 — verificación local confirma el cierre final QA3

Leí el issue y sus nueve comentarios; el último dictamen QA3 lo dejó `fixed`, y la consulta actual de GitHub muestra etiqueta `fixed`. Verifiqué independientemente el estado actual del árbol: `close_document_balances()` usa `pending_qty(..., exclude_draft_targets=True)` igual que el cierre por línea (`document_flow/service.py:901-923`). La regresión `test_close_document_ignores_draft_target_reservations` construye una relación activa de 10 unidades a una factura Draft y afirma que el cierre documental devuelve/cierra esas 10 unidades (`tests/test_document_flow_close_line_scope.py:241-273`). La extensión SalesRequest→SalesOrder en comentarios confirma el mismo mecanismo compartido. El test está presente en HEAD. No cambié la etiqueta `fixed`; no ejecuté pruebas/linters ni modifiqué producto/GitHub.

### #1427 — QA1/QA2 rechazan: falta moneda en conciliación de compras

Leí el issue y sus cinco comentarios; el primero amplía el alcance al panel, y el comentario más reciente confirma con GET que la vista de líneas sigue mostrando importes desnudos. El paraguas #1655 no reduce este contrato de interfaz: cada importe transaccional nominal debe identificar su moneda.

Los payloads de órdenes (`purchase_reconciliation_service.py:2048-2061`), facturas (`:2104-2116`) y resumen de recepciones (`:2152-2164`) no incluyen moneda transaccional. `PurchasePendingRow` expone pendientes sin moneda (`:118-129,1784-1802`). La plantilla muestra los totales/pending como floats sin código (`purchase_reconciliation.html:108,149,205-206,257`). El panel expone conciliaciones sin unidad monetaria y deja `matched_amount` crudo (`purchase_reconciliation_service.py:1802+`; `purchase_reconciliation_panel.html:139`); monedas coincidentes dentro de una conciliación no evitan mezclar diferentes conciliaciones del mismo proveedor/compañía. No hallé tests de render multimoneda para vistas de línea/panel.

QA1/QA2 rechazan independientemente. Propagar y mostrar moneda en órdenes, facturas, recepción resumen y detalle, pendientes por línea y panel; evitar sumar importes nominales de distintas monedas; probar NIO/USD con montos nominales iguales en cada superficie. No ejecuté tests/linters ni modifiqué producto/GitHub; etiqueta `needs-work` intacta.

### #1430 — QA1/QA2 rechazan: clave desconocida persiste award vacío

Leí el issue y sus tres comentarios. Los dos primeros confirman el repro de clave ajena con entidades reales; el comentario más reciente solo referencia el paraguas #1708 y no cambia la aceptación.

`validate_award_request()` rechaza solo `not selections` (`purchase_sourcing_service.py:259-264`). `_find_manual_override_items()` itera las líneas RFQ y mira `selections.get(item.id)` sin validar claves extra (`:285-304`), y `create_purchase_quotation_award()` vuelve a iterar las líneas reales (`:319-353`). El encabezado se guarda mediante `_flush_award()` antes de construir las líneas y el modelo default es `finalized`; para `{fake_line: fake_offer}`, ambas iteraciones omiten todo y se persiste una adjudicación terminal vacía. La oferta desconocida sí se rechaza si la clave es de una línea real porque no cubre la partida; vacío también falla. Falta prueba para clave ajena, oferta desconocida, selección parcial válida y ausencia de award al error.

QA1/QA2 rechazan independientemente. Validar que todas las claves pertenezcan a RFQ y que haya al menos una selección real/oferta válida antes de persistir encabezado; comprobar rollback, cero awards en inválidos y selección parcial válida. No ejecuté pruebas/linters ni modifiqué producto/GitHub; etiqueta `needs-work` intacta.

### #1432 — revisión estática local confirma los dictámenes aprobados

Leí el issue y sus diez comentarios; la última re-revisión de QA1 y la revisión QA2 aprueban `9a6230d8` + `45e38f2b`, después de que la primera QA1 hubiera rechazado brechas de prueba. El API aún muestra `needs-work`; no cambié esa etiqueta.

El servicio comparte `lock_default_scope("purchase_quotation_award", rfq_id)` entre abrir ronda, adjudicar y cerrar. `_terminal_award()` busca `TERMINAL_AWARD_STATUSES=("finalized", "used", "closed")`; los tres caminos lo consultan antes de mutar. Cierre repetido no inserta otra fila ni altera razón. `_flush_award()` usa savepoint y solo traduce el conflicto único de adjudicación; constraint NOT NULL ajena se propaga como `IntegrityError` y el test confirma sesión externa activa. Tests vigentes en `test_purchase_sourcing_authorization.py` cubren servicios de ronda/adjudicación después de cierre, cierre repetido, conflicto unique, IntegrityError ajeno y POSTs de ambas rutas. No hallé defecto estático pendiente contra el criterio del issue; el lock y constraint proveen protección de concurrencia documentada. Revisión estática, sin pruebas/linters ni cambios de código/GitHub.

### #1434 — QA1/QA2 rechazan: KPI cuenta órdenes cerradas/completadas

Leí el issue y sus dos comentarios; el reporte reproduce directamente `get_purchases_data()`. El padre #1709 no modifica el criterio operativo: el KPI “Órdenes abiertas” debe excluir los pedidos cerrados o sin cantidades pendientes.

`get_purchases_data()` aún calcula `open_orders` con `.filter_by(company=company, docstatus=1).count()` (`api/dashboard.py:334`), sin inspeccionar `PurchaseOrder.status` ni cantidades de líneas. `get_purchase_order_status_report()` ya calcula ordered/received/billed y estados por cantidades (`purchase_reconciliation_service.py:2005-2060`), pero no alimenta ese KPI ni excluye `status=closed`. No encontré prueba de `open_orders` que diferencie abiertas/partial, cerradas y cantidades completas. El repro de una orden `closed` con received=billed=ordered continúa contando 1.

QA1/QA2 rechazan independientemente. Alinear conteo al contrato de orden abierta, excluyendo estado cerrado y cantidades plenamente completadas, y probar partial/pending frente a completada/cerrada, incluidos estados inconsistentes. No ejecuté pruebas/linters ni modifiqué código/GitHub; etiqueta `needs-work` intacta.

### #1436 — QA1/QA2 aprueban rechazo explícito del método quantity

Leí el issue y sus tres comentarios. El segundo deja la semántica de “importe por unidad” sin decisión; el criterio de aceptación permite explícitamente rechazar la configuración si no es compatible, por lo que no se inventa cálculo.

`SUPPORTED_TAX_CALCULATION_METHODS` omite `quantity`; el formulario solo ofrece percentage/fixed/manual y `TaxRuleService` valida el enum antes de persistir (`accounting_engine/common/fiscal.py:10`, `admin/templates/admin/tax_rules.html:46-50`, `tax_rule_service.py:139-157,174`). El motor lanza error visible para método heredado no soportado y la integración de posting recoge `FiscalResult.errors` y falla; preview transmite errors al usuario (`engine.py:225-255`, `posting_service.py:920-925`, `fiscal_preview_service.py:277,324`). Persistencia canónica rechaza métodos no soportados antes de reemplazar snapshot (`fiscal_persistence_service.py:191,471-499`).

Pruebas actuales rechazan `quantity` por POST admin/alteración de enum, calculan una regla quantity sobre cantidad 3 y verifican error/ausencia de línea fiscal, canonical snapshot rechaza y la evidencia previa se conserva (`test_admin_tax_rule_form.py:83-155,246-283,286-344`). QA1/QA2 aprueban independientemente bajo la alternativa aprobada de rechazo. El cálculo unitario continúa intencionalmente no implementado; la regla queda no configurable y no genera cero silencioso. Revisión estática; no ejecuté tests/linters ni modifiqué código/GitHub. La etiqueta actual `needs-work` no se cambió.

### #1437 — QA1/QA2 rechazan: preview de notas de crédito sigue usando perfil de factura

Leí el issue y su comentario; este remite a #1707. Revisé los 14 comentarios del paraguas, cuyo criterio requiere reproducir cada hijo y agregar regresión a la batería fiscal, con paridad entre preview, persistencia y posteo.

En `transaction-form.js:775-802`, `documentType()` usa `config.documentType` solo si existe; de lo contrario deriva el sufijo de `formKey`, y `buildFiscalPayload()` manda ese valor. La configuración activa de ventas usa `formKey: sales.sales_invoice` (`ventas/routes.py:2218-2234`) y la de compras usa `purchases.purchase_invoice` (`compras/services.py:2269-2291`); ninguna aporta `documentType`. Los formularios sí tienen un campo oculto con el subtipo (`ventas/templates/ventas/factura_venta_nuevo.html:29`, compra `:30`), pero JS no lo lee. En consecuencia, el preview de ambas notas sigue mandando el tipo de factura.

La matriz `_FISCAL_MATRIX` de `fiscal_preview_service.py` no incluye perfiles `sales_credit_note` ni `purchase_credit_note`; por eso cambiar solo el payload al subtipo produciría error “Tipo documental no soportado”, no paridad. El posteo sí escoge `sales_credit_note_confirmed` y `purchase_credit_note_confirmed` (`accounting_engine/document_builders.py:486,564`). No encontré regresiones del payload/endpoint para preview de ambas notas; los tests de reglas por evento no ejercitan este contrato de formulario.

QA1 y QA2 rechazan independientemente. Corregir el tipo efectivo y resolver perfiles/eventos de las notas según la semántica aprobada; probar preview de compra/venta contra las reglas y totales usados al postear. Rechazo fundado en fallo funcional presente y ausencia de pruebas. No ejecuté pruebas/linters ni modifiqué código/GitHub; la etiqueta `needs-work` permanece intacta.

### #1438 — QA1/QA2 rechazan: preview de compra filtra reglas con moneda NIO

Leí el issue y su comentario, que remite a #1655; revisé los 17 comentarios del paraguas. El criterio del hijo exige usar moneda transaccional persistida, actualizar preview al cambiarla y demostrar la selección de regla restringida a USD frente a NIO.

El formulario de compra enlaza el selector solo a `header.transaction_currency` (`compras/templates/compras/factura_compra_nuevo.html:63-72`). `transaction-form.js` inicializa también `header.currency` como propiedad separada (`:356-368`), manda solo `currency: this.header.currency || ''` y omite `transaction_currency` en `buildFiscalPayload()` (`:790-800`). El watcher fiscal incluye `currency`, no `transaction_currency` (`:421-430`). Una factura nueva configura `formKey` y encabezado sin moneda genérica (`compras/services.py:2269-2291`); al no haber origen, la moneda se elige en el control transaccional. El servicio reemplaza moneda vacía por NIO (`fiscal_preview_service.py:239-255`) y el resolver filtra reglas por la moneda recibida (`tax_rule_service.py:61-76`). El posteo persiste/usa la moneda de transacción, divergente del preview.

Los tests de `transaction-form.js` comprueban refresco al cambiar `header.currency` y comportamiento de facturas genéricas, pero no este selector de compra, payload, regla USD/NIO o recálculo al cambio. QA1 y QA2 rechazan independientemente; usar la moneda transaccional canónica en payload y watcher, y cubrir el endpoint/reglas USD vs NIO y cambio de selección. Sin pruebas/linters ni modificación de código o GitHub; la etiqueta `needs-work` permanece intacta.

### #1440 — QA1/QA2 rechazan: el neto de varios pagos se duplica

Leí el issue y su comentario; este apunta a #1655. Los 17 comentarios del paraguas mantienen como causa la resolución/uso monetario y el requisito de regresión real por hijo.

`_prior_payment_document_net()` obtiene los pagos previos que referencian el documento y calcula bien los totales asignados para determinar cada proporción (`accounting_engine/document_builders.py:1607-1628`). Sin embargo, llama una sola vez `voucher_net("payment_entry", list(allocated_by_payment))`, cuyo callback suma con `voucher_id.in_(...)` sin `GROUP BY voucher_id` (`:1629`, `:1672-1685`), y reutiliza ese mismo escalar para cada pago en el ciclo (`:1631-1635`). Con pagos netos 40 y 30, ambos asignados completamente, cada proporción vale 1 y el resultado sigue siendo 140 en vez de 70. El carrying value alimenta liquidaciones y revaluación.

No encontré pruebas que invoquen `_prior_payment_document_net()`/`_document_carrying_value_in_ledger()` o verifiquen múltiples pagos y prorrateo previo. QA1 y QA2 rechazan independientemente. Calcular/obtener neto GL separado por voucher antes de prorratear; cubrir dos pagos 40/30, asignación parcial o del pago a más documentos y exclusión de pago cancelado. No ejecuté pruebas/linters ni modifiqué código/GitHub; `needs-work` permanece intacta.

### #1441 — QA1/QA2 rechazan: el mapper omite el impuesto que carece de cuenta

Leí el issue y su comentario, que remite a #1707; el paraguas exige fallo explícito para una línea contabilizable sin cuenta. `_map_fiscal_lines()` conserva el defecto: tras resolver cuenta explícita/predeterminada, hace `continue` si no existe (`accounting_engine/orchestrator/mapper.py:208-223`). Luego `_map_document_event()` incluye bienes/otras líneas y `_balance_against_party()` agrega el saldo AP/AR para balancearlas (`:45-73,470-480`). El resultado puede ser internamente balanceado aunque falte el impuesto; el guard de posting para línea sin cuenta no actúa porque el mapper ya omitió la línea.

No encontré pruebas que usen `AccountingMapper` o validen el contrato de impuesto contabilizable sin cuenta/default. QA1/QA2 rechazan independientemente. El mapper debe propagar error claro antes de que se rebalancee el documento; probar proforma y posting con impuesto excluido/incluido que debe contabilizarse y sin ambas cuentas, y confirmar ausencia de GL ante fallo. No ejecuté tests/linters ni cambié código/GitHub; `needs-work` intacta.

### #1465 — QA1/QA2 rechazan: el POST principal maneja el tipo, pero faltan regresiones y cierres siguen en 500

Leí el cuerpo y los seis comentarios del issue. El último QA documenta que el test `test_root_2207_not_found.py` citado no está en HEAD y deja el issue `needs-work`; el fix previo `44271087` captura `KeyError`/`ValueError` alrededor de `create-target`.

Confirmé que `api_document_flow_create_target()` ahora contiene la autorización y creación bajo un `try` que convierte `ValueError` a 400 (`api/__init__.py:1692-1705`). La búsqueda de tests no encontró cobertura HTTP equivalente para destino desconocido, tipo fuente desconocido ni ausencia de escrituras; la prueba actual del endpoint cubre solo líneas malformadas (`tests/test_document_flow_read_access.py:423-445`). La extensión planteada en comentarios también persiste: `close-line` ejecuta `_require_flow_company_access()` y `_require_source_item_access()` antes de su `try` (`api/__init__.py:1713-1729`), y `close-document` ejecuta la autorización antes de su `try` (`:1743-1754`). El registro/repository propaga `ValueError` para tipo no soportado; estos guards no lo traducen y pueden producir 500.

QA1 y QA2 rechazan independientemente. Agregar cobertura HTTP de tipo destino/fuente inválido y no persistencia en `create-target`, y traducir/encapsular errores de dominio para tipos fuentes inválidos en `close-line` y `close-document`, con pruebas HTTP sin mutación. Issue y etiquetas de GitHub sin cambios; no ejecuté tests/linters ni edité código.

### #1492 — QA1/QA2 aprueban estáticamente en el árbol local vigente

Leí los siete comentarios; el QA3 histórico devolvió a `needs-work` porque no halló en la rama remota el test que QA1/QA2 habían usado. En el HEAD local `45e38f2b`, `tests/test_recurring_template_frequency_and_balance.py` sí está versionado y presente.

`validate_template_balance()` rechaza importes inválidos/no finitos/negativos, línea con débito y crédito positivos simultáneos, línea cero, desbalance y menos de dos líneas (`contabilidad/recurring_journal_service.py:133-163`). El guard se usa al crear y vuelve a validar líneas persistidas al aprobar/aplicar (`:70-73,166-183,248-251`), antes de convertir cada línea al `value` signado. Las regresiones actuales prueban dual-positive/cero sin persistir, plantilla histórica inválida en aprobación y aplicación, y el comprobante real balanceado con valores +100/-100 (`test_recurring_template_frequency_and_balance.py:99-209`); casos negativos de ambos lados y persistencia ausente están en `test_recurring_template_negative_amounts.py:50-72`.

QA1 y QA2 aprobaron por separado la revisión estática del HEAD local. La brecha concreta que motivó QA3 histórico ya no está presente localmente. GitHub sigue `needs-work` y queda intacto conforme a la instrucción; no realicé tests, linters, comentarios ni cambios de etiqueta.

### #1493 — QA1/QA2 rechazan: no está probada la idempotencia por ocurrencia

Leí los siete comentarios. El responsable confirmó frecuencia mensual; la necesidad semanal se representa con varias plantillas mensuales independientes, no con ejecución semanal. El QA3 histórico objetó que no veía la suite en el remoto; el archivo sí está versionado en HEAD local `45e38f2b`.

El formulario ofrece solo `monthly` (`contabilidad/forms.py:386-393`); creación y aplicación normalizan/rechazan `weekly`/`daily` (`recurring_journal_service.py:62-73,224-227`). Las pruebas actuales rechazan esas frecuencias en creación, no aplican una fila histórica weekly y permiten dos plantillas distintas en fechas diferentes del mismo período (`test_recurring_template_frequency_and_balance.py:212-283`). El guard de reaplicación mira por template/company/book/FY/período y rechaza estados pending/applied (`recurring_journal_service.py:230-246`), pero ninguna prueba ejecuta dos veces la misma ocurrencia y verifica que no existan segunda aplicación ni segundo comprobante. El requisito fue explícito en el comentario de decisión: mantener idempotencia por ocurrencia. Adicionalmente, `approve_recurring_template()` no valida frequency; una fila legacy weekly puede pasar a Approved y fallar luego al aplicarse.

QA1 reconsideró y rechazó por falta de regresión de la ocurrencia repetida; QA2 rechazó independientemente por la misma brecha y señaló la transición Approved legacy weekly. Cubrir la misma plantilla dos veces mismo período/compañía/libro y probar que no se duplica evidencia; considerar también rechazar la frecuencia no soportada antes de aprobar. No ejecuté tests/linters ni cambié código/GitHub; `needs-work` intacta.

### #1564 — QA1 rechaza: ambos dashboards siguen truncando a 100 sin continuación

Leí el issue y sus tres comentarios, incluyendo reproducciones previas de 101 facturas aprobadas en dashboard de cliente y proveedor. Los filtros de compañía/tercero existentes acotan acceso, pero las consultas siguen truncadas sin exponer página siguiente.

`PORTAL_PAGE_SIZE=100` se aplica a las cuatro listas de cliente (facturas, órdenes, cotizaciones, entregas; `portal/__init__.py:31,83-97`) y las cinco de proveedor (facturas, notas, órdenes, cotizaciones, recepciones; `:216-235`). Los badges muestran `|length` sobre esa lista limitada en ambos templates (cliente `:16,55,94,133`; proveedor `:16,55,94,133,182`); no hay paginación, carga adicional ni total completo separado. No encontré regresión de dashboards/cardinality (>100).

QA1 y QA2 rechazan independientemente: los registros 101+ permanecen invisibles y el total exhibido es parcial. Implementar continuación/paginación por lista o carga explícita y enviar total real distinto del tamaño de página; cubrir datos >100 en los dos portales. Sin ejecutar pruebas/linters ni mutar archivos de producto/GitHub.

### #1737 — QA1/QA2 rechazan: UOM operativa persiste sin conversión

El issue no tiene comentarios adicionales. Su contrato requiere validar compra/venta al crear y editar: `purchase_uom`/`sale_uom` deben ser la unidad base o tener conversión del artículo antes de persistir.

`validate_item_uom_rows()` valida UOM base y filas de conversión, pero no contrasta con UOM operativas (`inventario/service.py:917-937`). `create_item_with_uoms()` llama esa validación y luego guarda `purchase_uom`/`sale_uom` directamente (`:950-982`). Update repite el patrón: valida filas pero `_aplica_campos_item()` asigna ambos campos sin guard (`:715-740,780-797`). Las choices de UI aseguran que una UOM exista en catálogo, no que tenga conversión por artículo. Pruebas actuales de factores UOM cubren valores inválidos del factor; las de edición I2F consumen una conversión que ya existe. No hay prueba de alta/edición con UOM operativa sin conversión y no-persistencia.

QA1 y QA2 rechazan independientemente. Validar ambos campos en un servicio compartido antes de mutación; permitir ausente/base y exigir fila por UOM distinta. Cubrir crear/editar con UOM válida sin factor y verificar que no cambia artículo ni conversiones. No ejecuté tests/linters ni modifiqué producto/GitHub; etiqueta `needs-work` intacta.

### #1752 — QA1/QA2 rechazan: enlace de edición de landed cost crea otro borrador

Leí el issue y su comentario, que solo agrega la referencia al paraguas #1658. La ruta y el consumidor confirman el defecto sin ambigüedad: el detalle muestra Editar para `docstatus == 0` y pasa `landed_cost_id` hacia `compras_import_landed_cost_nuevo` (`compras/templates/compras/import_landed_cost.html:23-29`). La ruta `/import-landed-cost/new` no lee ese argumento, configura el formulario de alta y en POST siempre llama `_create_import_landed_cost_from_request()` (`compras/routes.py:3535-3591`). El servicio construye un nuevo `ImportLandedCost`, guarda items/cargos y hace commit (`compras/services.py:3252-3354`); no hay servicio o ruta de actualización.

Las pruebas halladas solo cubren creación/formulario y enlace de listado; no prueban editar un borrador, no duplicarlo, permisos ni rechazo de documento no borrador. Al enviar el supuesto formulario de edición se crea otro costo y el original no cambia. QA1 y QA2 rechazan independientemente. Según el alcance aprobado de #1658 (completar edición), implementar actualización explícita con autorización por compañía/permiso, guard `docstatus=0` y persistencia consistente de cabecera, líneas, cargos y relación; no degradar el contrato a ocultar el botón. Agregar GET/POST que confirme el mismo ID y ausencia de duplicados/side effects. No ejecuté tests/linters ni cambié código/GitHub; etiqueta intacta.

### #1758 — QA1/QA2 rechazan en revisión fresca del HEAD local

Leí el cuerpo y los diez comentarios recientes. El comentario QA3 devolvió a `needs-work` por suite ausente en el remoto y decisión pendiente de peso/volumen. La prueba ahora está trackeada en el HEAD local `45e38f2b`; la decisión de producto está expresamente aprobada por el responsable en este hilo: mantener prorrateo por peso/volumen, dimensiones por línea, defaults de catálogo, persistencia histórica y validaciones. No la vuelvo a tratar como bloqueante.

La implementación actual parece enlazada: `_landed_cost_dimension()` usa valor/UOM por línea o defaults de `Item`, valida Decimal/UOM (`compras/services.py:3153-3172`); el guardado persiste dimensión/UOM por `ImportLandedCostItem` y rechaza unidades mixtas (`:3087-3150`); `_build_landed_cost_item_contexts()` lee dimensiones desde la fila histórica (`accounting_engine/document_builders.py:644-673`); el motor calcula peso/volumen por cantidad y falla ante base vacía. La suite tiene cálculo directo 40/60 y 20/80, test de persistencia con override/default parcial, base vacía, unidades mixtas y coerción de errores (`tests/test_landed_cost_weight_volume.py`).

La regresión no atraviesa el enlace del defecto original: el test de distribución construye `ItemContext` directamente (`:25-63`) y el test de persistencia solo lee las columnas guardadas (`:122-165`); ninguna llama el builder del contexto desde `ImportLandedCost` persistido. Por eso borrar `weight`/`volume` de `_build_landed_cost_item_contexts()` devolvería a cero el caso real y la suite todavía pasaría. Además, `Item` y `ImportLandedCostItem` contienen las cuatro columnas nuevas (`database/__init__.py:1401-1407,2737-2744`), pero la única migración Alembic actual es no-op (`migrations/20260809_0001_baseline.py`), sin upgrade incremental para bases existentes. Las bases ya inicializadas fallarán al leer/escribir esas columnas tras actualización.

QA1 y QA2 rechazan independientemente por integración sin regresión; QA1 señala también el bloqueo de esquema. Añadir integración que persista dimensiones, construya contexto real/postee y demuestre allocation con defaults/override, y migración de las cuatro columnas. No ejecuté pruebas/linters ni cambié código/GitHub. Etiqueta `needs-work` intacta; no reabrí la decisión de negocio aprobada.

### #1811 — QA1/QA2 rechazan: formulario normal de conciliación no puede enviar moneda

Leí el issue y su comentario. El comentario adicional histórico atribuye HTTP 500 al handler que retorna `None`; esa parte está desactualizada en el árbol actual porque la ruta re-renderiza el formulario tras respuesta `None`. No la cuento como defecto vigente.

La plantilla de conciliación (`inventario/stock_reconciliation_nuevo.html:17-20,36-119`) no contiene campo `transaction_currency`/`currency` ni usa el encabezado común; la configuración de la ruta tampoco inicializa moneda (`inventario/routes.py:897-909`). El handler ya consulta moneda funcional de compañía, pero exige además moneda transaccional explícita no vacía y falla antes de crear el `StockEntry` (`inventario/services.py:879-899`). La ruta retorna el formulario con el error flash y HTTP 200, no crea documento (`routes.py:910-927`). Así, el flujo estándar no permite registrar conciliación aunque se trate de moneda funcional.

Las pruebas positivas de conciliación observadas inyectan manualmente `transaction_currency=NIO` (`tests/test_stock_entry_dimensions.py:166-198`); no prueban el formulario y POST normales. QA1/QA2 rechazan independientemente. Exponer un selector requerido/default válido o derivar moneda transaccional desde la funcional de compañía de forma explícita; probar GET/POST real de creación y falta de moneda, incluyendo rollback/no persistencia. No ejecuté tests/linters ni cambié código/GitHub; etiqueta intacta.

### #1813 — QA1/QA2 rechazan: `matching_type=3-way` es evadible si require_sales_order=False

Leí el cuerpo y los cinco comentarios. Los comentarios describen el modo 3-way como Orden + Nota de Entrega + Factura y confirman el repro inicial; el issue sigue vinculado al lote #1658. El código ahora rechaza el caso más común (orden, sin entrega), pero queda un bypass con configuración contradictoria.

`_validate_3way_delivery_requirement()` se invoca solo dentro de ramas con source/order (`ventas/services.py:1894-1900,1908-1911,1917-1924`). Al final, si `config.require_sales_order` es falso, `_validate_sales_order_requirement()` retorna sin exigir ninguna fuente (`:1914-1915`), aunque `matching_type == "3-way"`. La configuración admin guarda matching type y checkbox de orden independientemente (`admin/routes.py:1274`, template `sales_matching_config.html:61-84`). El formulario podría, por tanto, guardar factura sin orden ni entrega bajo modo 3-way. La ruta de submit sí llama el validador antes de postear y revierte `ValueError` (`ventas/routes.py:2505-2523,2565-2568`).

El único test focal prueba 2-way con orden sin entrega y 3-way con `require_sales_order=True` sin entrega (`tests/test_3way_delivery_requirement.py:31-62`); no cubre 3-way con bandera false, un caso válido con orden+entrega enlazadas ni submit HTTP/ausencia de efectos contables. QA1/QA2 rechazan independientemente. Hacer que 3-way obligue orden y entrega (o rechazar config incoherente) y cubrir el bypass, una relación válida mismo flujo/líneas y POST de rechazo/aprobación sin GL o con GL correcto. No ejecuté pruebas/linters ni cambié código/GitHub; etiqueta intacta.

### #1888 — QA1/QA2 rechazan: el contrato aprobado no está integrado

Leí los cuatro comentarios del issue. El comentario final contiene decisión de producto aprobada: StockEntry integra dimensiones por línea (centro de costo/proyecto) según #1359 y observaciones; no permite cuenta arbitraria, no incorpora cargos fiscales y debe ocultar controles no soportados y rechazarlos en backend. No asumo reglas contables nuevas.

El formulario de movimiento usa `transaction_grid` genérico sin capabilities por documento (`inventario/templates/inventario/entrada_nuevo.html:55`; `routes.py:897-909`). El macro todavía muestra campos de cuenta/centro/unidad/proyecto/remarks en modal y hidden payloads de impuestos/cargos (`templates/transaction_form_macros.html:472-498,700-750`); `showPricing` queda true por default (`static/js/transaction-form.js:344`). `StockEntryItem` no tiene columnas para centro/proyecto/remarks (modelo `database/__init__.py:1567-1610` solo tiene cabecera de dimensiones/remarks); `_save_stock_entry_item()` ignora campos de línea y no rechaza payload fiscal/cuenta arbitraria (`inventario/services.py:599-636`). Readback usa filas del modelo, así que no puede recuperar esos valores. El posting de inventario propaga dimensiones de cabecera solamente (`contabilidad/posting_service.py:4869-4892`).

No encontré regresiones del contrato #1888. QA2 revisó independientemente y coincide: el test de edición cercano solo conserva en el render un POST rechazado; no demuestra persistencia/readback ni posting de dimensiones. Falta almacenamiento/readback de remarks/dimensiones, validar compañía y herencia/precedencia sin mutar cálculos, propagar dimensiones por línea a GL, acotar macro a campos soportados y rechazar payloads fiscales/cuentas no admitidas. Añadir pruebas multi-línea, autorización/intercompany, GL/libros/reversas y consumidores existentes del macro. No ejecuté pruebas/linters ni cambié código/GitHub; `needs-work` permanece intacto.

### #1891 — QA1/QA2 rechazan: duplicación vuelve a crear el ajuste genérico

Leí el issue y sus siete comentarios. La decisión funcional confirmada es admitir únicamente ajustes positivos y negativos, retirar nuevas altas genéricas y conservar consulta histórica. El test suite mencionado por el QA3 histórico sí está versionado localmente en HEAD `45e38f2b`; esa objeción quedó resuelta.

El alta directa y formulario excluyen `stock_adjustment`; el listado histórico filtra el propósito legado y no muestra botón de alta. Sin embargo, `entrada.html` ofrece **Editar** a todo borrador y **Duplicar** a cualquier documento en estado 0/1 (`inventario/templates/inventario/entrada.html:17-30`). `inventario_entrada_duplicar()` solo comprueba existencia, acceso y que no esté cancelado; copia `origen.purpose` directamente al nuevo `StockEntry` y hace commit, sin llamar `_validate_stock_entry_purpose()` ni excluir `LEGACY_STOCK_ENTRY_PURPOSES` (`inventario/routes.py:1031-1095`). Por tanto, duplicar el registro histórico genera un borrador nuevo `stock_adjustment`, eludiendo el retiro de alta genérica. La prueba `test_el_historial_generico_es_solo_lectura` verifica que la lista no tenga enlace `/adjustment/new`, pero no intenta duplicar por POST (`tests/test_stock_adjustment_contract.py:59-79`).

QA1 y QA2 rechazan independientemente por este bypass funcional. Bloquear la duplicación del propósito legado (y hacer solo lectura visible el borrador histórico, si esa es la conducta prevista); agregar prueba HTTP que intente duplicar un histórico, confirme respuesta 4xx y ausencia de nuevo `StockEntry`, y preserve lectura de historial/detalle. No ejecuté pruebas/linters ni modifiqué código/GitHub; etiqueta `needs-work` intacta.

### #1915 — QA1/QA2 aprueban retiro de `base.ods` en HEAD local

Leí el cuerpo y los ocho comentarios. El criterio aprobado por responsable (#2248) pide retirar el ODS si no hay consumidor ni uso manual documentado y el CSV es la fuente operativa; el comentario QA3 histórico alegó que la prueba integrada no estaba en `estabilizacion`, pero el HEAD local actual sí la contiene.

El commit `6fc5ee8e` es ancestro del HEAD `45e38f2b` y elimina únicamente `cacao_accounting/contabilidad/ctas/catalogos/base.ods`, junto con la prueba de flujo. La búsqueda completa de `base.ods` no encuentra consumidores, instrucciones de uso manual ni generadores en el repositorio; solo aparece una referencia histórica en esta bitácora. `MANIFEST.in` distribuye CSV/JSON, `ctas/__init__.py` define `base_es.csv`/`base_en.csv`, `setup/service.py` descubre solo CSV y el README documenta CSV como formato editable/operativo. La prueba versionada `tests/test_catalog_loading_transaction.py::test_alta_compania_carga_catalogo_csv_seleccionado` usa `finalize_setup(..., "base_es.csv")` y comprueba compañía/cuentas; la prueba compañera verifica rollback de carga.

QA1 y QA2 aprueban independientemente el cambio en el árbol local. La ausencia reportada por QA3 remoto no se reproduce en HEAD local; el uso manual/external no está documentado ni conocido en el historial revisado y el archivo tampoco se empaquetaba. Revisión estática, sin tests/linters ni cambios de producto/GitHub; etiqueta `needs-work` intacta.

### #1930 — QA1/QA2 aprueban estáticamente en HEAD local

Leí el cuerpo y los nueve comentarios. La decisión aprobada confirma que tamaño y orientación deben afectar la salida PDF; el QA3 histórico devolvió el cambio porque no encontró `tests/test_print_pdf_page_settings.py` en su snapshot remoto. En HEAD local `45e38f2b`, el archivo sí está versionado (`git ls-files`).

`PrintService.validate_template()` valida el tamaño/orientación y convierte `ValueError` en `TemplateValidationError` antes de persistir (`printing/service.py:233-248`). Alta y edición capturan esa excepción, revierten y re-renderizan el formulario (`printing/admin_routes.py:85-116,283-310`). `build_print_html()` coloca el `@page` configurado después del CSS de plantilla, y preview/PDF le pasan las settings guardadas. Las pruebas de servicio verifican precedence, defaults, inválidos, preview y PDF; los POSTs de alta/edición cubren b5/diagonal, respuesta HTTP controlada y configuración intacta (`tests/test_print_pdf_page_settings.py:28-139`).

QA1 y QA2 aprueban de forma independiente el árbol local; la ausencia reportada por QA3 no se reproduce localmente. Mejora no bloqueante sugerida por QA1: comprobar también orientación y número de versión sin cambios ante los POST inválidos; la validación se ejecuta antes de mutar ambos. Revisión estática; no ejecuté pruebas/linters ni modifiqué producto/GitHub. Etiqueta `needs-work` intacta.

### #1916 — QA1/QA2 rechazan: migración de retiro fuera de la cadena actual

Leí el cuerpo y ambos comentarios. El último comentario del responsable aprueba retirar el código residual `WorkflowActionLog` y referencias relacionadas bajo el criterio pre-alpha, sin integrar funcionalidad nueva. Esto elimina la objeción original de preservar datos de instalaciones productivas; no elimina el requisito de schema upgrade para bases ya existentes.

En HEAD `45e38f2b`, la búsqueda no encuentra las clases `Workflow`, `WorkflowState`, `WorkflowTransition`, `WorkflowInstance`, `WorkflowActionLog` ni sus strings de tabla; sin embargo, `database/__init__.py:105` conserva `WORKFLOW_STATE_ID` sin consumidores. `cacao_accounting/migrations/` solo contiene el baseline no-op `20260809_0001_baseline.py` y `script.py.mako`. El commit ancestro `6205ae9e` añadió una migración drop idempotente de las cinco tablas, pero `41c7af1e` la quitó del HEAD. Sin migración activa, `create_all` no elimina las tablas en esquemas existentes y `db migrate` no tiene operación para retirarlas. El plan Alpha exige manejar schema limpio/existente y el criterio de contrato Alembic requiere migraciones para bases con datos.

QA1 y QA2 rechazan independientemente: retirar la constante huérfana y conservar una migración de drop efectiva e idempotente integrada con el historial de migraciones vigente. No es necesario conservar filas legacy bajo la decisión pre-alpha. Revisión estática; no ejecuté pruebas/linters ni cambié código/GitHub; etiqueta `needs-work` intacta.

Revalidación #1916 con el comentario owner #6712656894: la decisión pre-alpha ya autoriza retirar los cinco modelos/tablas sin preservar datos, así que no queda abierta la pregunta histórica de producto. QA2 confirma que no hay consumidores, pero `WORKFLOW_STATE_ID` sigue huérfana y la migración drop del ancestro fue eliminada; HEAD solo tiene baseline no-op. `create_all` no elimina tablas existentes. El rechazo se mantiene por limpieza incompleta y upgrade sin migración efectiva. No ejecuté pruebas/linters ni cambié código/GitHub.

### #1938 — QA1 rechaza: vistas sin restauración completa ni migración

Leí el issue y sus 13 comentarios, incluida la ADR aprobada que exige servicio reutilizable, RBAC, aislamiento por compañía y permisos vigentes. QA3 histórico dijo que la prueba no estaba en la rama remota; el test sí está trackeado en HEAD `45e38f2b`, y la brecha de conflicto/rollback está atendida en `37354f19`.

La superficie de persistencia/autorización es correcta en lo revisado: el servicio consulta por reporte/compañía/usuario, comprueba `Permisos.reportes` y acceso vigente, y las rutas validan `FINANCIAL_REPORT_CODES`; la prueba cubre CRUD, aislamiento, permisos, corrupción y colisión con rollback. Sin embargo, el display JSON acepta `show_users` y `advanced` (`saved_views_service.py:41-42,96-115`) y el frontend captura ambos al guardar (`routes.py:388-397`), pero la carga solo restaura `visible_columns` y `group_by` (`helpers.py:453-477`). El cálculo de columnas y el estado de filtros avanzados leen `request.args` (`helpers.py:1274+`; `financial_report.html:52,75,89`), así que aplicar una vista no restaura esas preferencias. También falta migración Alembic para la tabla `saved_report_view`: el HEAD solo conserva baseline no-op; `create_all` solo resuelve bases nuevas.

QA1 rechaza por restauración incompleta y migración ausente. QA2 aprobó inicialmente al verificar RBAC, concurrencia y prueba de colisión, pero no abordó estas dos brechas; se le solicitó re-evaluarlas independientemente. Hasta obtener revisión coincidente, no hay aprobación QA1/QA2. Revisión estática; no ejecuté tests/linters ni cambié producto/GitHub; etiqueta `needs-work` intacta.

Actualización del veredicto de #1938: QA2 completó la reevaluación independiente, retiró su aprobación inicial y rechazó por las mismas brechas que QA1. El consenso final QA1/QA2 es rechazo; el comentario QA3 sobre la prueba ausente sí era stale: confirmé que `tests/test_saved_report_views.py` está trackeado localmente y que la rama `estabilizacion` lo sirve actualmente por GitHub. Esto no resuelve la restauración incompleta ni la migración ausente. En `inicia_base_de_datos()`, `usuarios_creados()` retorna antes de `database.create_all()` cuando la base ya contiene usuarios, por lo que la tabla nueva no se crea en una base existente y el baseline Alembic es no-op. Etiqueta sin cambios.

### #1973 — revisión discordante: QA1 aprueba, QA2 rechaza cobertura parcial

Leí el issue y sus seis comentarios. La tarea aprobada retira `source_label`, `items_disponibles`, `uoms_disponibles`, `warehouses_disponibles` de la firma de `transaction_grid()` y todos sus callers; `source_api_url` y `title` siguen vivos. La búsqueda estática sobre llamadas actuales confirma que los templates ya no pasan argumentos retirados. La prueba `tests/test_transaction_grid_contract.py` está trackeada en HEAD `45e38f2b`, corrige la evidencia 404 de QA3 e incluye firma, Jinja y smoke HTTP de tres módulos.

Brecha: `_argumentos_de_llamada()` usa un único `re.search` (`:27-31`) y `test_ningun_consumidor_envia_los_parametros_retirados()` valida solo la primera aparición por archivo (`:43-54`). Hay archivos con varias llamadas; un kwarg retirado reintroducido después de la primera podría no fallar el contrato. Los tres smoke paths no cubren todas las plantillas multi-call.

La revisión fresca QA1/QA2 rechaza por cobertura insuficiente. La prueba existe en la rama remota actual, así que la objeción QA3 de 404 está desactualizada; aun así, `_argumentos_de_llamada()` usa `.search()` y valida solo la primera invocación por archivo. Hay consumidores con ramas y varias llamadas; los smoke tests solo renderizan solicitud de venta, orden de compra y recepción de inventario. Una reintroducción de argumento inerte en la segunda o posterior llamada podría pasar. La inspección del código actual no encuentra argumentos retirados, pero la prueba no fija ese contrato para todos los callers. No ejecuté pruebas/linters ni modifiqué código/GitHub; `needs-work` intacta.

### #2077 — QA1 rechaza: falta migración de `File.sha256` y POST multipart integrado

Leí el issue y los nueve comentarios. El commit `0d19150d` sí conecta el pipeline al servicio activo y debe conservarse; el comentario QA3 de prueba ausente no aplica al HEAD local, donde `tests/test_attachment_service.py` está versionado. Las pruebas cubren firma/extensión/contenido/tamaño/archivos comprimidos, hash y almacenamiento, errores de stream, rollback/limpieza y reemplazo de imagen; el servicio conecta `upload_attachment()` con `validate_upload()`/`store_attachment()` y la ruta API delega a ese servicio.

QA1 detecta dos faltantes de aceptación: (1) no hay prueba multipart positiva que pase por la ruta `/api/attachments/<type>/<id>/upload`; las pruebas del pipeline llaman al servicio, mientras el test HTTP de scope solo valida permiso y recibe 400 por falta de archivo; (2) el campo `File.sha256` se añadió en `0d19150d` pero el HEAD solo tiene la migración baseline no-op y no crea esa columna en bases existentes. Esto puede hacer fallar el INSERT del upload tras actualizar una instalación existente. QA1 rechaza; QA2 está re-evaluando esos criterios. No ejecuté tests/linters ni modifiqué código/GitHub; etiqueta intacta.

Cierre de reevaluación #1973: QA1 reevalúa de forma independiente y cambia su dictamen a rechazo por la misma brecha de `re.search`/primera invocación; ahora QA1 y QA2 coinciden. Requisito mínimo: verificar cada invocación de cada template consumidor, incluidos argumentos multilínea, y conservar los smoke tests representativos. No hay cambios de código o GitHub.

Reevaluación independiente QA2 de #2077: rechazo por la misma brecha de esquema. Precisión: no es correcto decir que `create_app()` no toca el schema; sí intenta añadir `sha256`/índice con `_ensure_file_sha256_column()` (`__init__.py:577-579`, `database/helpers.py:937-964`), captura los fallos y los registra. Esa reparación de DDL al arrancar es la ruta paralela que #1898 prohíbe; hace falta migración Alembic efectiva y retirar el helper de startup. QA2 también confirma que no hay POST multipart positivo al endpoint activo; el test HTTP existente manda archivo vacío. QA1/QA2 coinciden en rechazo.

### #1118 — QA1/QA2 rechazan: no cubre cancelado ni el total solicitado

Leí el issue y los siete comentarios. El criterio más reciente distingue el seguimiento operativo de la evidencia contable: el reporte de traslados contabilizados debe usar solo `docstatus=1`; borradores/cancelados no deben tratarse ni sumarse como movimientos de inventario. El código actual filtra `StockEntry.docstatus == 1` y la salida mantiene status, así que el fix de producción parece alineado para el reporte. El consumidor query tool `inventory.get_transfers` delega en este servicio; no encontré un consumidor vigente `get_inventory_transfer_analysis` en el árbol.

`tests/test_inventory_transfers_report_scope.py` está trackeado y prueba draft (0) excluido y submitted (1) incluido, pero el owner pidió expresamente cobertura de los tres estados. No crea canceled (2) ni verifica `totals["qty"]` para confirmar que su cantidad quede fuera del acumulado. Si se regresara el filtro a `docstatus != 2`, esta prueba detectaría draft, pero no una regresión que incluya canceled con otro predicado ni fija el total.

QA1 y QA2 rechazan independientemente por regresión incompleta. Añadir movimiento cancelado de cantidad distinguible, aserción de que no aparece y total estrictamente por posteados, conservando draft/submitted. No ejecuté tests/linters ni modifiqué código/GitHub; etiqueta `needs-work` intacta.

### #2045 — QA1/QA2 rechazan: prueba no distingue el retiro de `from_order`

Leí el issue y sus dos comentarios. La decisión aprobada ordena retirar el parámetro legacy `from_order`, conservar la ruta de alta ordinaria y no inventar una conversión desde una orden. El código actual elimina la lectura/carga de `SalesOrder` y el contexto `orden_origen/from_order_id`; conserva únicamente los orígenes aprobados request/quotation y su guard de acceso. El cambio productivo parece correcto.

La regresión `tests/test_ventas_orden_nuevo_from_order.py` crea una orden propia, consulta `GET /sales/sales-order/new?from_order=<id>` y solo exige status 200. La versión previa también respondía 200 para una orden autorizada, por lo que el test pasa si se restaura la lectura/carga/contexto legacy. Tampoco encontré regresiones de request/quotation ajenas que acrediten el criterio del owner sobre permisos y aislamiento desde los orígenes soportados.

QA1 y QA2 rechazan independientemente por test no discriminante y cobertura de consumidores adyacentes insuficiente. Verificar explícitamente que la orden legacy no se carga ni expone en el render/transaction config; preservar y probar los orígenes request/quotation soportados, incluidos el rechazo de una fuente ajena y la ausencia de persistencia. No ejecuté pruebas/linters ni modifiqué código/GitHub; etiqueta `needs-work` intacta.

### #1937 — QA1/QA2 rechazan: no hay regresión que pruebe el PDF completo

Leí el cuerpo y los seis comentarios. La ruta actual incluye `pdf` en la reconsulta con `export_all=True, page=1` (`reportes/routes.py:249-266`); `get_account_movement_detail()` evita limit/offset para export_all (`reportes/services.py:2810-2824`) y el exportador PDF serializa las filas entregadas (`reportes/helpers.py:1136-1157`). El fix de ruta está presente.

El QA3 histórico reporta que `tests/test_account_movement_full_export.py` falta; el HEAD local confirma ausencia/no seguimiento y no encuentro otra prueba de PDF de movimiento con más de page_size. El test que agregó `320e3abb` era insuficiente incluso antes de ser retirado: usa reporte fake, stub del renderer y solo afirma que la segunda llamada recibe `export_all=True`; no observa 101+ filas reales ni contenido que llega al writer.

QA1 y QA2 rechazan independientemente por falta de prueba funcional discriminante. Reponer cobertura que genere más de 100 filas de ledger, pase por exportación PDF real (o capture las filas efectivas entregadas al writer) y afirme que incluye una fila posterior a page_size/todas las filas filtradas. No ejecuté pruebas/linters ni modifiqué código/GitHub; etiqueta `needs-work` intacta.

### #1919 — QA1/QA2 rechazan: el portal no revoca acceso por inactividad del tercero

La decisión del owner (#6712636413) exige que Party y CompanyParty estén activos al consultar documentos; desactivar cualquiera debe revocar nuevas consultas, incluidas las de documentos históricos, sin mutar esos documentos. `check_portal_access()` solo valida modo/rol/flags. Los dashboards y detalles de portal filtran compañía, tercero y docstatus, pero no revalidan actividad de Party/CompanyParty. QA2 confirmó un camino adicional: `PrintService._authorize_portal_document()` autoriza preview/PDF con compañía y `party_id`, sin revisar estados activos. `tests/test_portal_print_scope.py` cubre alcance compañía/tercero, no revocación por inactividad.

QA1 y QA2 rechazan independientemente. Añadir guard común de actividad y regresiones de lectura/listado/detalle/preview para Party inactiva y vínculo CompanyParty inactivo, preservando acceso activo y documentos históricos intactos. No ejecuté pruebas/linters ni cambié producto/GitHub; etiqueta intacta.

### #1931 — QA1/QA2 rechazan: el historial de versiones no es visible desde administración

La decisión del owner (#6666585771) confirma que el historial es una función que se debe mantener y completar. `PrintService.create_version()` persiste snapshots al editar, y `/admin/print-templates/<id>/versions` carga versiones descendentes. Sin embargo, la ruta renderiza `print_template_list.html` con `versions`, y esa plantilla no consume el dato ni ofrece enlace al historial; incluso la URL manual muestra la lista corriente sin snapshots. No encontré test positivo de listado/render del historial; la prueba existente de administración solo verifica denegación sin permisos.

QA1 y QA2 rechazan independientemente. Exponer un enlace y renderizar datos históricos pertinentes con autorización, más regresión de creación/listado/lectura y acceso denegado. No ejecuté pruebas/linters ni cambié producto/GitHub; etiqueta intacta.

### #1928 — QA1/QA2 rechazan: plantilla corregida, regresión positiva ausente

Leí el issue y sus siete comentarios. El arreglo de bloques de `f7cccfce` está presente en las tres plantillas: lista, formulario y configuración declaran `block contenido`, acorde con `base.html`. Sin embargo, la regresión citada históricamente (`test_lista_de_impresion_renderiza_y_traduce`) no existe en el checkout actual. `test_print_admin_fail_closed.py` prueba acceso positivo a la lista solo con HTTP 200, sin comprobar controles/texto del cuerpo; los demás casos son denegaciones. Tampoco encontré pruebas positivas de render para alta/edición y configuración. El último comentario del issue identifica esta brecha y deja `needs-work`.

QA1 y QA2 rechazan independientemente por no haber prueba funcional que prevenga el regreso de la UI vacía 200 para lista, formulario y configuración. Agregar regresión de render autenticada que afirme contenido visible en las tres vistas. No ejecuté pruebas/linters ni modifiqué producto/GitHub; etiqueta intacta.

La evidencia concreta de QA2 coincide: `test_con_rol_admin_las_plantillas_se_permiten` solo exige 200 para la lista; los tests de página PDF son POST inválidos que no verifican contenido renderizado y no hay prueba positiva de configuración. QA2 tampoco ejecutó pruebas/linters ni modificó producto/GitHub.

### #1564 — QA estática: paginación no implementada

Leí el issue y sus tres comentarios, incluida la evidencia HTTP de 101 facturas en cada dashboard. En el HEAD vigente, ambos dashboards mantienen `.limit(PORTAL_PAGE_SIZE)` (100) y no reciben parámetro de página; la búsqueda no encuentra navegación/continuación en el portal. El contrato pide exponer resultados posteriores y no representar el conteo de la página como total. QA rechaza: paginar todos los listados afectados o dar continuación explícita, y distinguir total de resultados de los mostrados. Sin pruebas/linters ni cambios en producto/GitHub; etiqueta intacta.

### #1950 — QA1/QA2 rechazan: tres formularios de configuración no envían CSRF

Los formularios POST en `external_document_validation.html:14-30`, `tax_templates.html:4-13` y `tax_template_items.html:4-13` carecen de `csrf_token()`/`hidden_tag()`. `CSRFProtect` se instala globalmente (`__init__.py:91-98`) y los tres handlers aceptan POST y persisten (`admin/routes.py:321-348,522-541,544-585`), así que la UI normal falla con 400 antes de llegar a guardar. `test_tax_template_sequence_validation.py` usa el fixture general con `WTF_CSRF_ENABLED=False`, y no hay regresiones CSRF positivas/negativas vigentes para las tres rutas.

QA1 y QA2 rechazan independientemente. Insertar token en cada formulario y cubrir cada GET/POST con CSRF activo: token válido persiste, ausente/inválido es rechazado; comprobar los tres contratos por separado. No ejecuté tests/linters ni modifiqué código/GitHub; etiqueta intacta.

Revalidación estática de la rama actual e historial completo del issue: los tres formularios siguen sin token, las rutas escriben, y el middleware global no tiene exención aplicable. QA2 confirma que la prueba de secuencia usa fixture con CSRF desactivado y que no hay control positivo/negativo de estos tres flujos bajo CSRF activo. El fallo no ha sido corregido; no ejecuté pruebas/linters ni modifiqué producto o GitHub.

Actualización de QA fresco para #1492: retiro la aprobación local previa. QA1 y QA2 inspeccionaron independientemente el test versionado y detectaron que las pruebas dual-positive no reproducen el defecto balanceado 150==150 del issue: los totales debit/credit quedan distintos y una validación solo agregada las rechazaría. La cobertura actual de importes negativos sí está en `tests/test_recurring_template_negative_amounts.py` y cubre ambos lados, así que corrijo esa afirmación preliminar de QA2. El hallazgo bloqueante común es que no hay regresión discriminante con ambos importes positivos en una línea y totales globales todavía iguales; agregar esa prueba en alta y/o historia antes de aprobar. El archivo señalado por QA3 está versionado en `HEAD 45e38f2b`, por lo que esa objeción histórica concreta era stale, pero no subsana el defecto de cobertura real. QA1/QA2 rechazan en re-revisión. Sin pruebas/linters ni cambios en producto/GitHub.

### #2093 — QA1/QA2 rechazan: permanece el flujo legacy de comparativos de órdenes

Leí el issue y sus tres comentarios. El commit `1f31d89e` eliminó el constructor sin caller, pero la decisión más reciente exige retirar también la lectura/operación de históricos `PurchaseOrderComparison` sin migración. En HEAD `45e38f2b` siguen los cuatro modelos/tablas (`database/__init__.py:2221-2301`), la ruta POST de rondas y la vista legacy prioritaria en `/request-for-quotation/comparison/<id>` (`compras/routes.py:1207-1235,1295-1393`), su servicio (`purchase_order_comparison_service.py`) y plantilla `comparativo_ordenes.html`. La prueba `test_purchase_order_comparison_alignment.py` importa el helper legacy. La interfaz/servicio activos de comparativos de solicitudes usan `PurchaseRequestComparison`, `purchase_request_comparison_service.py` y handlers separados (`routes.py:1021-1204`) y deben preservarse. `_purchase_order_comparison_open()` en `compras/services.py` usa el término comparison, pero resuelve awards de SupplierQuotation y se consume al crear órdenes; no lo atribuyo al modelo legacy sin evidencia adicional.

QA1 y QA2 rechazan independientemente: el residual sigue servido y almacenado. Retirar las clases legacy, rama/ruta/template/helpers/tests que solo los atienden y conservar/regresar el flujo de solicitudes. Agregar regresión que verifique que comparar por solicitud sigue funcionando y que el endpoint ya no expone el modelo legacy. No ejecuté pruebas/linters ni cambié código/GitHub; etiqueta intacta.

Revalidación con el comentario owner #6887529010: la retirada requerida incluye explícitamente lectura/operación de históricos sin migración. QA2 confirma que el lector genérico todavía resuelve primero `PurchaseOrderComparison`, y queda ruta POST de ronda, renderer/template y servicio legacy; la prueba de alineación conserva tres casos de ese modelo. El flujo activo `PurchaseRequestComparison` tiene modelo, writer, lista, borrador, negociación, finalización y órdenes separados y debe conservarse. Sin cambios de producto/GitHub.

### #1162 — QA1/QA2 rechazan: constante huérfana no fue retirada

Leí el issue y el comentario de vinculación con #1658. Una búsqueda completa del árbol encuentra `MONETARY_ACCOUNT_TYPES` solo en su definición (`contabilidad/exchange_revaluation_service.py:50`); no hay imports, consumidores ni pruebas que la usen. El servicio define sus candidatos mediante consultas/herramientas propias y no depende de esa constante. La revaluación que queda cubre cobro, pago y bancos; hay regresiones activas de posteo/tasas, anulación/rollback, concurrencia/re-ejecución y UI (`test_r2r_exchange_revaluation.py`, `test_exchange_revaluation_internal_controls.py`, `test_exchange_revaluation_missing_rate.py`, `test_exchange_revaluation_ui.py`).

QA1 y QA2 coinciden en que el retiro es seguro, pero rechazan el estado actual: la constante sigue en HEAD y no hay diff que la elimine. El fix acotado es borrar solo la definición, sin mover la regla ni cambiar selección de candidatos. No ejecuté pruebas/linters ni modifiqué producto/GitHub; etiqueta intacta.

### #1882 — QA1/QA2 rechazan: plantilla y ruta legacy de importación siguen enlazadas

Leí el issue y sus dos comentarios. La decisión vigente de #2248 indica retirar capas legacy, actualizar el dashboard para enlazar al asistente canónico y no conservar la redirección de compatibilidad por defecto. En HEAD siguen `bancos/templates/bancos/extracto_importar.html`, el endpoint `/bank-statement/import` que muestra flash y redirige a `imports.new` (`bancos/routes.py:673-682`) y el enlace del dashboard a ese endpoint (`bancos/templates/bancos.html:126`). El asistente compartido sí está enrutado en `/imports/new`; sus adaptadores mantienen cobertura de parseo/precisión/concurrencia (`tests/test_bank_statement_precision_validation.py`, `tests/test_bank_statement_import_concurrency.py`, `tests/imports/test_bank_statement_reference_grouping.py`). No hay regresión del enlace canónico ni de la eliminación del redirect/template.

QA1 y QA2 rechazan independientemente. Retirar plantilla y endpoint de compatibilidad, enlazar directamente a `imports.new` respetando permisos y conservar pruebas del importador compartido. Limpiar solo referencias de traducción verdaderamente exclusivas: `Importar Extracto Bancario` también aparece en el dashboard activo. No ejecuté pruebas/linters ni cambié producto/GitHub; etiqueta intacta.

Revalidación de #1882: el dashboard aún enlaza al redirect legacy, la ruta sigue registrada y la plantilla sigue en el árbol. QA2 confirma que `imports.new` ofrece `bank_statement`, mientras el adaptador/servicio compartido conserva consumidores y pruebas sustanciales; esos componentes activos no se deben retirar. Falta navegar directamente desde el dashboard al asistente y cubrir navegación/carga HTTP. Debe conservarse la traducción que usa el dashboard; limpiar solo cadenas exclusivas del template obsoleto. Sin cambios de producto/GitHub.

### #1899 — QA1/QA2 rechazan: tres hojas legacy siguen en el paquete


Leí el issue; no tiene comentarios. Búsqueda amplia en el repo no encuentra carga ni consumer de `dashboard.css`, `checkout.css` o `purecss-treeview.css`, y los selectores `.sidebar`, `ol.tree`/`li.file` no aparecen en markup vigente. El sidebar activo usa `ca-sidebar`; los árboles usan `ca-tree`/estilos en `cacaoaccounting.css`. `macros.html:31` carga el CSS activo y `public/validation_result.html:7` también lo carga explícitamente. `signin.css` sí es cargado por login, recuperación, reset y OTP; debe conservarse. Las tres hojas legacy permanecen en HEAD, y no hay test que verifique retiro/smoke visual.

QA1 y QA2 rechazan el estado actual por fix ausente; la búsqueda confirma que retirar solo esas tres hojas no requiere reemplazo. Mantener `signin.css` y estilos activos, y verificar las vistas restantes tras la eliminación. No ejecuté pruebas/linters ni modifiqué código/GitHub; etiqueta intacta.

QA2 fresca confirma que siguen presentes las tres hojas y que no tienen referencias de carga productivas ni consumidores actuales de sus selectores. Mantener `cacaoaccounting.css` y `signin.css`; al retirarlas, un smoke de layout y revisión visual deben asegurar que sidebar y árboles activos conservan su estilo. Issue #1899 no tiene comentarios ni decisiones adicionales. Sin cambios de producto/GitHub.

### #1909 — QA1/QA2 rechazan: campos `step` residuales siguen declarados

Leí el issue; no tiene comentarios. `SetupConfirmationForm` ya no existe y no tiene consumidor. No obstante, `SetupLanguageForm`, `SetupRegionalForm` y `SetupCompanyForm` siguen declarando `step = HiddenField(...)` (`setup/forms.py:33,42,77`). La ruta solo decide y actualiza el paso desde `session["setup_step"]` (`setup/__init__.py:84-138`); no lee `request.form["step"]`/`form.step.data`, y el template solo incluye `form.csrf_token`, no `form.step` (`setup.html:291`). La máquina de tres pasos y validación `validate_on_submit()` se mantienen. Hay tests del paso final, país y sesión corrupta, pero no recorrido HTTP completo de 1→2→3. QA2 nota además que las fixtures de setup desactivan CSRF; QA1 confirma que hay CSRF real en template.

QA1 y QA2 rechazan el HEAD actual: el retiro de los hidden fields aún no está hecho. Quitar solo las declaraciones `step`, conservar `session["setup_step"]` y CSRF; agregar cobertura de navegación de los tres pasos y validar sin token si se modifica/fortalece la ruta/form. No ejecuté pruebas/linters ni modifiqué producto/GitHub; etiqueta intacta.

Revisión fresca QA2 confirma que `SetupConfirmationForm` sí está retirado, pero los campos `step` continúan en los otros tres forms y no los consume ni la ruta ni la plantilla. Los tests actuales fuerzan directamente el paso 3 y deshabilitan CSRF, no recorren el wizard 1→2→3 con CSRF activo. Rechazo QA1/QA2; preservar `session["setup_step"]`, pantallas y token al retirar solo los campos muertos. Sin cambios de código/GitHub.

### #2071 — QA1/QA2 aprueban localmente el retiro de `_sum_query`

Leí el issue y su comentario de vínculo. `rg _sum_query` no encuentra símbolo ni referencia actual; `git log -S` ubica la eliminación en `d738bcdb`. El endpoint `/api/dashboard/data` y sus cinco secciones continúan activos, con cálculos específicos en lugar del helper genérico. Las pruebas funcionales actuales verifican permisos, KPI y agregaciones/resultados mensuales (`test_dashboard_consult_permission.py`, `test_dashboard_pending_vouchers_permission.py`, `test_dashboard_aggregation_identity.py`, `test_r2r_income_statement_cost_classification.py`). No hay consumidor del helper ni ruta/métrica dependiente de él.

QA1 y QA2 aprueban independientemente el retiro ya presente en HEAD. Revisión estática; no ejecuté tests/linters ni modifiqué código/GitHub. La etiqueta permanece intacta.

### #2079 — QA1/QA2 rechazan: alias de hashing sin consumidor permanece

Leí el issue y su comentario de vínculo con #1658. `_CHAIN_FIELDS = V1_FIELDS` sigue declarado (`audit_chain.py:61`), pero la búsqueda del repo no encuentra import/call/test/doc externo. El flujo usa `_hash_fields()` directamente: filas legacy sin versión siguen con `V1_FIELDS`; v2 incluye `id` en `_V2_FIELDS` (`:37-79,82-106`). `stamp` actual crea v2, mientras los docs de controles internos prometen verificar hashes v1 almacenados sin reescribir evidencia. El alias no forma parte de ese contrato.

QA1 y QA2 rechazan: el alias no se retiró. Se puede eliminar solo la asignación; mantener `V1_FIELDS`, `_V2_FIELDS` y la compatibilidad para filas legacy. La cobertura vigente de cadena nueva/topología no fija explícitamente selección/hash v1/v2, y el test histórico que lo hacía no está en HEAD; restaurar regresiones para preservar ambos formatos junto con la limpieza. No ejecuté tests/linters ni cambié código/GitHub; etiqueta intacta.

Revalidación fresca QA2: `_CHAIN_FIELDS` sigue siendo una asignación sin consumidor; `compute_payload_hash()` y la verificación usan `_hash_fields()` para conservar V1 en filas legacy y V2 en evidencia nueva. Las pruebas actuales no fijan explícitamente hash/verificación de fila v1 sin versión; mantener esa compatibilidad con regresión específica al retirar únicamente el alias. Sin cambios de producto/GitHub.

Corrección documental de #2071: en la revisión QA2 se mencionó `tests/test_dead_code_inventory.py`, pero ese archivo no existe en el HEAD actual (búsqueda de archivos confirmada). La aprobación de retiro de `_sum_query` se mantiene por búsqueda estática y cobertura funcional restante; retiro la afirmación de que un inventario de dead code versionado fija su ausencia.

### #2203 — fix-confirmed local: macro obsoleta retirada y cierre QA3 vigente

Leí el issue y sus cinco comentarios. GitHub refleja estado cerrado/`fixed` por QA3 autorizado; no cambié ese estado. En HEAD `45e38f2b`, `752486f1` es ancestro, `transaction_form_js` y `transactionFormConfig` no aparecen en código productivo, y `tests/test_transaction_form_macros_consumers.py` está versionado. La prueba estructural confirma que las macros restantes (`transaction_form_header`, `transaction_grid`, `logistics_section`, `smart_select`) tienen invocaciones y que el macro/global retirados no regresan. QA1/QA2/QA3 dejaron revisiones independientes; QA3 verificó HEAD y cierre. La limpieza está completada según expediente y estado vigente.

### #2204 — confirmado localmente: macros compartidas conservan consumidores

Leí el issue y sus cinco comentarios. La premisa original de que el archivo completo no tenía consumidores era un falso negativo de las importaciones Jinja con alias `tf_macros`; el código actual invoca `transaction_form_header`, `transaction_grid`, `logistics_section` y `smart_select` en ventas, compras, inventario y caja chica. `752486f1` elimina únicamente `transaction_form_js`; es ancestro de HEAD. La prueba `test_transaction_form_macros_consumers.py` está versionada y exige consumidor para cada macro. GitHub ya registra la revisión/cierre QA3 como `fixed`; solo verifiqué el estado, sin mutarlo.

### #2150 — fix confirmado y cierre QA3 localmente verificados

Leí los cinco comentarios. GitHub refleja issue cerrado/`fixed` tras QA3 autorizado. En HEAD, `5862eda3` es ancestro; `cargar_catalogos()` deja de consultar `session.in_transaction()`/hacer commit interno y documenta que el caller controla la transacción (`contabilidad/ctas/__init__.py:54-81`). `finalize_setup()` confirma o revierte compañía, catálogo y configuración como una sola operación (`setup/service.py:249-275`); el seed confirma explícitamente tras cargar (`datos/dev/__init__.py:143-152`). La prueba `test_catalog_loading_transaction.py` está versionada y exige transacción abierta, luego rollback sin cuentas residuales. QA1/QA2 y QA3 aprobaron; solo verificación estática, sin mutar GitHub.

### #2147 — fix confirmado/cierre QA3 localmente verificados

Leí los cinco comentarios. Issue cerrado/`fixed` por QA3; no cambié GitHub. En HEAD, `f51328f6` es ancestro y `import_landed_cost_lista.html:43-45` enlaza número/ID al detalle con `landed_cost_id=item.id`. La prueba HTTP `test_landed_cost_list_link.py::test_listado_de_costos_enlaza_al_detalle` está versionada y verifica el vínculo y número. QA1/QA2/QA3 aprobaron independientemente; la ruta de detalle mantiene su ACL.

### #1139 — QA1/QA2: falta regresión concurrente en PostgreSQL

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el cuerpo y los dos comentarios completos de #1139. El comentario de revisión más reciente recalca que dos recepciones distintas deben competir por la misma factura con dos transacciones PostgreSQL independientes.

La implementación tiene una serialización común plausible: `allocate_purchase_invoice_receipt_lines()` obtiene el lock transaccional de `DocumentFlowLock` para la factura, `_allocate_invoice_lines()` bloquea sus líneas con `FOR UPDATE` y vuelve a sumar allocations activas antes de insertar. El servicio hace `flush()` sin confirmar, por lo que el lock vive hasta el commit exterior. La escritura PostgreSQL `ON CONFLICT DO UPDATE` en `lock_document_flow_document()` serializa los llamadores sobre la misma clave.

La cobertura no demuestra ese contrato. `allocation_scenario` fuerza SQLite; la prueba con `ThreadPoolExecutor` usa el mismo fixture y no tiene barrera/interleaving determinista. Los casos restantes de cantidad son secuenciales. Falta una regresión de dos transacciones PostgreSQL independientes, con dos recepciones sobre una factura compartida, que fuerce el interleaving y confirme tras ambos commits que la suma activa no supera la cantidad facturada. QA1 y QA2 llegaron de forma independiente al mismo rechazo. No ejecuté pruebas ni linters; no se modificó código ni GitHub.

### #1177 — QA1/QA2: cancelación de serial conserva estado incorrecto

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el issue y sus cinco comentarios completos, además del issue #1539 y su decisión compartida de lifecycle. El comentario vigente del responsable establece que la reversa de una recepción cancelada no es una entrega: permite volver a recibir el serial solo si no existe una entrada activa, preservando unicidad y una sola ubicación. Otro comentario de #1177 documenta que cancelar transferencias serializadas también deja estado/ubicación dependientes del orden accidental de las filas.

En HEAD, `_create_stock_reversal()` actualiza cada serial como `outgoing=qty_change < 0`. Al cancelar una entrada positiva, la reversa negativa lo marca `delivered` y le quita la bodega; `_validate_incoming_serial()` rechaza después el serial existente salvo transferencia o devolución real. No hay consulta de entrada activa que permita la re-recepción válida. La transferencia produce movimientos de salida y entrada para el mismo serial; `_cancel_stock_movements_if_needed()` los lee sin `ORDER BY` y llama la mutación por cada reversa, así que la última fila sobrescribe el estado final. La unicidad de `SerialNumber.serial_no` no resuelve ese ciclo de vida.

No encontré pruebas específicas de recepción-cancelación-recepción ni de cancelación de transferencia serializada. QA1 y QA2 rechazaron independientemente. Hace falta representar el estado operativo a partir de movimientos efectivos, asegurar que cancelar una transferencia restaure el serial disponible en origen sin depender del orden, y cubrir re-recepción permitida, duplicado activo, devolución real y transferencia cancelada. No ejecuté pruebas ni linters; no se modificó código ni GitHub.

### #1178 — QA1/QA2: estado serial no serializa las salidas

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el cuerpo y los tres comentarios completos de #1178. El contrato vigente requiere que la transición del estado serial se serialice durante el posteo y que una unidad solo pueda salir una vez, incluso con dos transacciones concurrentes.

`_validate_serial()` lee `SerialNumber` sin `FOR UPDATE`; `_validate_outgoing_serial()` solo comprueba `serial_status` y `warehouse`. Después, `update_serial_state()` vuelve a leer y modifica el estado sin bloqueo ni transición condicional. El lock de `StockBin` no protege la identidad del serial. Dos transacciones PostgreSQL pueden observar `available`, ambas postear movimientos de salida y terminar con una sola fila de estado `delivered`; la unique de `SerialNumber.serial_no` no evita dos movimientos.

No encontré pruebas de posteo de inventario con serial ni una regresión concurrente de doble salida. QA1 y QA2 rechazaron independientemente. Falta adquirir un lock/revalidar el estado del serial dentro de la transacción de posteo y una prueba PostgreSQL con dos sesiones, donde una sola salida se confirme y la otra se rechace sin crear movimiento duplicado. No ejecuté pruebas ni linters; no se modificó código ni GitHub.

### #1294 — QA1/QA2: aprobado localmente en `45e38f2b`

Leí el issue y sus cuatro comentarios. QA3 lo devolvió previamente a `needs-work` porque el test de auditoría no estaba en la rama remota inspeccionada. En el HEAD local actual, `tests/test_external_counter_edit_audit.py` está trackeado (commit `f915edc5`), por lo que esa falta de archivo no se reproduce aquí.

`record_external_number_used` no aparece en el código ni en tests; la función fue retirada en `2d9d8848`, ancestro de HEAD. El archivo histórico `tests/test_dead_code_inventory.py` ya no está en HEAD, así que la ausencia se verificó mediante búsqueda estática, no por un guard ejecutable actual. La vía productiva de registro de números sigue en `_validate_and_register_external_number()`, que persiste `ExternalNumberUsage` y actualiza `last_used`. El ajuste manual restante exige motivo y crea `ExternalCounterAuditLog`. El test HTTP trackeado verifica que POST de edición no altere `last_used` ni cree auditoría, y que el ajuste dedicado sí persista before/after y motivo. QA1 y QA2 aprueban independientemente de forma estática. No ejecuté tests ni linters, no cambié código/GitHub y no moví etiquetas; falta QA3 para cualquier estado final.

### #1318 — QA1/QA2: retirada sin resolución de datos legacy

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el issue y sus dos comentarios completos. El helper `backfill_reconciliation_item_context()` fue retirado en `40453d45` y no quedan callers; eso satisface la limpieza del símbolo, pero no demuestra que el backfill sea innecesario para datos persistidos.

El modelo `ReconciliationItem` conserva columnas de contexto nullable y documenta que las asignaciones legacy sin contexto deben diagnosticarse y migrarse. El reporte todavía emite `reconciliation_item_missing_context` para partidas activas sin `currency`, y `test_report_reconciliation_company_scope.py` conserva ese escenario. Los fallbacks solo reconstruyen la cuenta/moneda si la `BankTransaction` fuente sigue existiendo; no hay backfill alternativo, comando migratorio ni evidencia de censo que confirme que no hay filas antiguas. QA1 y QA2 rechazaron independientemente: la aceptación exige demostrar que el modelo ya no requiere migración o dejar una vía de migración explícita/verificable. GitHub y etiquetas intactos; no ejecuté tests ni linters.

### #1683 — QA1/QA2: falta migración efectiva para esquema existente

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el issue y sus dos comentarios. El comentario de implementación sostiene que no se necesita migración por tratarse de pre-alpha, pero el contrato arquitectónico aprobado después en #1898 exige Alembic efectivo para toda modificación de columnas, también en instalaciones existentes.

El modelo `BaseTransaccion` ya no declara los cinco campos legacy, `MUTABLE_STATE` ya no incluye los aliases redundantes y `test_database_canonical_surface.py` fija el metadata ORM. Sin embargo, `cacao_accounting/migrations/20260809_0001_baseline.py` es la única migración y su `upgrade()` no modifica esquema. Una base existente conserva las columnas físicas tras este cambio; el test solo comprueba el modelo nuevo y no ejecuta upgrade sobre esquema previo. QA1 y QA2 rechazaron independientemente. Falta migración Alembic y prueba de upgrade que verifique retiro de columnas sin pérdida de datos, conforme a #1898. No ejecuté tests ni linters; sin cambios de código/GitHub.

### #1733 — QA1/QA2: aprobado localmente en `45e38f2b`

Leí el issue y sus cuatro comentarios. QA3 devolvió previamente el cambio a `needs-work` porque el test de regresión no estaba en la rama remota consultada; en HEAD local `45e38f2b`, `tests/test_external_counter_edit_audit.py` está trackeado y proviene de `f915edc5`.

La edición oculta `last_used` y `_update_counter_from_form()` ya no lo asigna; un POST manipulado con `last_used=999` conserva el valor 10, persiste un campo permitido y no crea auditoría. La ruta de ajuste dedicada exige `reason`, actualiza el contador y agrega `ExternalCounterAuditLog` en la misma sesión; el test verifica 10→42 con anterior/nuevo/razón. El incremento operativo de números sigue en `_validate_and_register_external_number()`, fuera de la mutación manual. QA1 y QA2 aprobaron de forma independiente y estática. No ejecuté tests ni linters, no cambié código/GitHub ni etiquetas; QA3 sigue pendiente.

### #1751 — QA1/QA2: aprobado localmente en `45e38f2b`

Leí el issue y sus cuatro comentarios. QA3 había devuelto el issue a `needs-work` porque el test no estaba disponible en la rama remota que consultó; `tests/test_import_landed_cost_creation_event.py` está trackeado en este HEAD local.

`_create_import_landed_cost_from_request()` llama a `log_create(registro)` antes del único `database.session.commit()`. `log_create()` solo agrega `AuditTrail` a la sesión, por lo que costo, líneas/cargos/relaciones y evento quedan en la misma transacción; ante fallo de commit no puede persistir uno sin el otro. La prueba hace POST real y luego consulta en un contexto/sesión separado que existe el costo y exactamente un evento `created` ligado al ID. QA1 y QA2 aprobaron independientemente y estáticamente. No ejecuté tests ni linters, no cambié código/GitHub ni etiquetas; queda aceptación QA3.

### #1306 — QA1/QA2: doble salida serial aún posible

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el cuerpo y sus tres comentarios. El criterio del issue pide serializar por identidad `(item_code, serial_no)` y volver a validar la disponibilidad dentro de la misma transacción de posting.

`_create_stock_movement()` y `_outgoing_stock_values()` validan el serial antes de consumir capas/bloquear el `StockBin`; el bloqueo posterior protege cantidad/valor agregado, no la fila del serial. `update_serial_state()` modifica luego `SerialNumber` sin lock ni compare-and-set. Por tanto, dos postings de documentos distintos aún pueden leer `available` y registrar dos salidas aunque haya stock físico sobrante. La unicidad de `SerialNumber.serial_no` solo protege que exista una fila; no impone una salida activa por serial.

No encontré regresiones funcionales o concurrentes de posteo con serial. QA1 y QA2 rechazaron independientemente. Hace falta una transición serializada por `(item_code, serial_no)` en el posting y una prueba multi-sesión que demuestre que la primera salida se confirma y la segunda falla sin movimiento duplicado, con stock restante. Comparte el mecanismo con #1178, pero mantiene criterio propio. No ejecuté pruebas ni linters; sin cambios de código/GitHub.

### #1093 — QA1/QA2 rechazan: falta regresión multi-sesión PostgreSQL del doble reembolso

Leí el cuerpo y los cinco comentarios. El último comentario del responsable (#6886805875) exige test PostgreSQL multi-sesión por ser Tier 1 Cloud. `replenish_petty_cash()` bloquea y refresca `PettyCashReplenishment`, exige `status == "aprobado"` y ausencia de `bank_debit_note_id`, crea/postea `PaymentEntry`, actualiza el vínculo y estado en la misma transacción (`bancos/services.py:1651-1720`). La revalidación después del lock parece serializar correctamente la solicitud.

La regresión `test_replenishment_waits_for_sqlite_writer_and_rechecks_committed_status()` usa `BEGIN IMMEDIATE` y salta para motores no SQLite (`test_petty_cash_replenishment_approval.py:1342-1385`). No hay cobertura equivalente con dos sesiones PostgreSQL que intente reembolsar la misma solicitud y verifique un solo PaymentEntry/nota, GL y vínculo. QA1 y QA2 rechazan independientemente por esta brecha Tier 1; se conserva `needs-work`. No ejecuté tests/linters ni modifiqué código/GitHub.

### #1094 — QA1/QA2 rechazan: reserva concurrente solo probada en SQLite

Leí el issue y sus seis comentarios. El último (#6886806689) exige regresión PostgreSQL multi-sesión para dos solicitudes que intentan reservar el mismo gasto. `create_petty_cash_replenishment()` toma locks `FOR UPDATE` en orden determinista, usa `populate_existing`, vuelve a validar compañía/fondo/posteo/reserva, y crea solicitud y asociaciones dentro de una transacción con rollback (`bancos/services.py:1541-1625`). `PettyCashReplenishmentExpense` impone unicidad por gasto (`database/__init__.py:3429-3430`), así que el código parece tener guardas adecuadas.

La regresión `test_concurrent_replenishments_reserve_one_posted_expense_once()` sí usa dos contextos/sesiones concurrentes, pero su fixture fija SQLite (`test_petty_cash_replenishment_append_only_link.py:37-48,294-335`); ahí `BEGIN IMMEDIATE`/bloqueo de escritor explica el resultado. No demuestra PostgreSQL `FOR UPDATE`. QA1 y QA2 rechazan independientemente por falta de evidencia Tier 1. Agregar prueba real con dos sesiones PostgreSQL, exactamente una solicitud/asociación, rechazo/rollback de la perdedora y ausencia de duplicado. No ejecuté tests/linters ni cambié código/GitHub.

### #2078 — QA1/QA2: aprobado localmente en `45e38f2b`

Leí el issue y sus cinco comentarios. QA3 había devuelto a `needs-work` porque no encontró `tests/test_audit_chain_fail_closed.py` en la rama remota consultada; el test está trackeado en HEAD local.

`_serialize_chain_head()` valida una cabeza almacenada como hash único y terminal; si el puntero es nulo, `_legacy_chain_head()` reconstruye la topología y falla cerrado ante cero/múltiples raíces, ciclos, ramas y filas huérfanas. Las rutas ORM (`chain_pending_rows`) y Core (`stamp_audit_values`) comparten esa validación antes de enlazar. La prueba crea un ciclo de dos filas con puntero nulo o obsoleto, recorre ORM y Core, y comprueba que la escritura falle sin cambiar el número de filas ni la cabeza. QA1 y QA2 aprobaron independientemente después de acordar que una raíz desconectada con puntero terminal válido es endurecimiento fuera del acceptance concreto de «cadena hasheada sin cabeza terminal». Revisión estática; no ejecuté tests ni linters ni cambié código/GitHub/etiquetas.

### #1987 — QA1/QA2: falta migración para la tabla de asociación

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el issue y sus seis comentarios. El criterio vigente pide una relación separada append-only, creada atómicamente con la reposición, sin modificar el gasto posteado. El test sí está trackeado en HEAD local, así que la objeción QA3 remota por archivo ausente ya no aplica.

El modelo `PettyCashReplenishmentExpense` usa tabla propia y unicidad por gasto; el servicio crea reposición y asociación en una transacción, y la suite existente cubre vínculo, saldo derivado, rollback/reintento, guards y concurrencia SQLite. Sin embargo, la tabla es un cambio de esquema sin migración: `cacao_accounting/migrations/` solo contiene el baseline cuyo `upgrade()` es no-op. Bases existentes no recibirán `petty_cash_replenishment_expense` al actualizar y fallarán al consultar o crear la asociación. El contrato aprobado en #1898 exige migración Alembic efectiva para toda tabla/constraint/FK nueva. QA1 y QA2 rechazan independientemente; falta migración y prueba de upgrade de base existente. No ejecuté tests ni linters ni modifiqué código/GitHub.

### #1877 — QA1/QA2: el test no recorre posting real y el permiso es amplio

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el issue y sus cuatro comentarios. La prueba se encuentra trackeada localmente, por lo que la objeción QA3 de archivo ausente en remoto no aplica al HEAD actual.

El guard verifica que la línea pertenezca a un documento posteado y autoriza mutarla si el parent está en `_POSTED_DOCUMENTS_IN_TRANSACTION`; el listener agrega el parent al permiso ante cualquier transición ORM de borrador a posteado. El test actual asigna `entry.docstatus = 1`, hace flush y muta campos, sin pasar por `submit_document()`/`post_stock_entry()` ni `approved_execution`; por eso prueba un camino más amplio que el posting autorizado y no reproduce la integración Cloud que falló. QA1 también observa que una transición ORM directa puede habilitar el permiso temporal. QA2 añade que no hay cobertura del nested savepoint ni de rollback. Vincular el allowance a una transacción de posting autorizada y agregar una prueba real de conciliación Cloud, más rechazo de edición después de commit y limpieza del permiso tras rollback. QA1/QA2 rechazan independientemente. No ejecuté tests ni linters ni modifiqué código/GitHub.

### #1865 — QA1/QA2: el guard también bloquea ediciones que preservan evidencia

**Veredicto: rechazado localmente; conservar `needs-work`.** Leí el issue y los siete comentarios completos. El criterio vigente (#6712664950) permite guardar una edición si conserva exactamente las relaciones activas y sus cantidades; pide rechazar cambios o eliminación de líneas vinculadas. El comentario posterior aclara que #1893 no modifica ese contrato.

`_delete_and_resave_stock_entry_items()` rechaza por la sola existencia de cualquier `DocumentRelation` cuyo destino sea el StockEntry, sin comparar estado, línea, cantidad ni payload. Como el handler actualiza primero la cabecera y siempre llama a ese helper, también revierte un POST de cabecera-only que conserva todas las relaciones. `tests/test_stock_entry_linked_edit.py` fija precisamente ese rechazo; `test_stock_entry_edit_relation_append_only.py` cubre cambio de cantidad/eliminación, pero no un caso positivo que mantenga vínculos intactos. Los archivos de prueba están trackeados localmente, por lo que la objeción QA3 por archivo ausente no aplica a este HEAD; la brecha funcional sí persiste. QA1/QA2 rechazan independientemente. Permitir edición que no altere líneas/vínculos, manteniendo rechazo/rollback para cambios o borrado de líneas vinculadas. No ejecuté tests ni linters ni modifiqué código/GitHub.

### #1794 — QA2 rechaza localmente: falta prueba de rollback atómico

Leí el issue, sus cuatro comentarios y el paraguas #2208. El fix local reordena `log_create(registro)` antes del único `database.session.commit()` en `_create_import_landed_cost_from_request()` (`compras/services.py:3348-3352`); `log_create()` solo agrega el evento a la sesión. `tests/test_import_landed_cost_creation_event.py` está trackeado y hace POST real, luego comprueba documento y un único `created` desde un contexto nuevo, así que distingue el defecto original.

QA1 y QA2 rechazan porque la aceptación del issue también exige que si falla una parte se reviertan ambas. No hay prueba del camino de fallo al insertar/confirmar auditoría que compruebe desde otra sesión que no persisten landed cost, líneas/cargos/enlace ni evento. Mismo orden transaccional sugiere rollback correcto, pero no fija esa garantía ante regresiones futuras. Cubrir el fallo atómico antes de aprobar. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #1854 — QA1/QA2 rechazan localmente: duplicación sin auditoría y copia estado

Leí el issue y los tres comentarios, incluida la decisión más reciente de #1893. `inventario_entrada_duplicar()` (`inventario/routes.py:1031-1096`) crea cabecera y líneas y confirma sin `log_create()` ni evento equivalente. La auditoría automática Cloud no cubre Desktop; el timeline consulta el nuevo ID. No encontré prueba específica de duplicación.

La decisión vigente requiere un borrador independiente con AuditTrail centralizado (actor, fecha y origen solo como referencia informativa), sin heredar relaciones, estado o evidencia contable, y sin GL/stock. La ruta copia además snapshots operativos de líneas (`valuation_rate`, cantidades/valores actuales/objetivo, diferencia, batch y serial). QA2 observa que ese payload puede heredar estado/evidencia del origen y debe revisarse contra el contrato, con prueba de que duplicar no postea ni comparte evidencia. QA1/QA2 rechazan por falta de evento y cobertura. QA1 confirma que Cloud tampoco deja la referencia informativa y que conteo/valuación/batch/serial copiados requieren revisar el contrato de no heredar evidencia de #1893. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### #1863 — QA1/QA2 rechazan localmente: snapshot de StockEntry incompleto

Leí el issue y sus dos comentarios. `_capture_stock_entry_state()` (`inventario/services.py:998-1011`) registra `purpose`, compañía, fecha, observaciones y snapshot de líneas. El handler modifica también bodegas, cuenta de ajuste, dimensiones, monedas y `total_amount`; `log_update()` compara únicamente las claves de esos mapas, por lo que los cambios omitidos no quedan en `before_json`, `after_json` ni `changes_json`. El snapshot completo de líneas cubre solo esa parte del requisito.

No encontré prueba de auditoría de edición de StockEntry que compruebe esos campos. QA1/QA2 rechazan independientemente; ampliar snapshot/pruebas de cabecera, total derivado y líneas. La observación del comentario sobre posible pérdida de valores al renderizar Alpine es un defecto relacionado separado, no evidencia para el hallazgo del snapshot. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2137 — QA1/QA2 rechazan localmente: snapshot y cobertura S2P incompletos

Leí el issue y los seis comentarios. El snapshot `PURCHASE_AUDIT_FIELDS` cubre varios campos de factura/orden y la prueba HTTP existente cambia supplier invoice number, plantilla, moneda/tasa y logística. Sin embargo, el campo mutable `landed_cost_estimates_json` está ausente; el snapshot tampoco incluye las relaciones `DocumentRelation` fuente. El fixture de la factura no tiene un enlace fuente real, por lo que no prueba su before/after. No hay casos de edición sin cambio ni rollback que verifiquen que documento, relaciones y AuditTrail quedan intactos.

QA1/QA2 rechazan según el último criterio del issue y paraguas #2208; el handler hace rollback en algunos errores, pero no hay regresión que fije esa garantía. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### #1779 — QA1/QA2 aprueban localmente

La ruta de edición del centro de costo carga y bloquea compañía/centro; si hay hijos, revierte la democión de `group` o el cambio de compañía antes de asignar/confirmar. `tests/test_r2r_cost_center_hierarchy.py::test_parent_hierarchy_changes_are_rejected_and_child_remains_editable` envía al padre sin checkbox, comprueba que `group`/compañía se conservan y luego edita el hijo. Hay además una prueba con dos transacciones PostgreSQL/MySQL para serializar reparentados y rechazar ciclos. QA1/QA2 aprueban independientemente. Sin cambios de código/GitHub/etiquetas y sin ejecutar pruebas/linters.

### #1784 — QA1/QA2 rechazan localmente: commit parcial y reintento bloqueado

`_process_group()` crea diarios por moneda, vincula la fuente al primero y llama `submit_journal()` sin `commit=False`; el default confirma cada envío. Si falla una moneda posterior, el rollback de `run_capitalization()` no revierte el primer commit ni el vínculo, y el reintento omite la fuente por `capitalized_by_id`. No encontré pruebas específicas del servicio, fallo multimoneda ni reintento. QA1/QA2 rechazan independientemente; el cambio requiere commit único por fuente y prueba de rollback/reintento. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### #1776 — QA1/QA2 rechazan localmente: aplicación recurrente pendiente no es recuperable

Leí el issue y sus cuatro comentarios completos. `apply_recurring_template()` confirma comprobante draft más `RecurringJournalApplication(status="pending")`, pero rechaza reenvíos si la aplicación existe como `pending` o `applied` (`recurring_journal_service.py:209-320`). El selector del wizard considera completadas solo las `applied`, así que el reintento vuelve a incluir una pending irrecuperable (`services.py:640-665`). Además, `_apply_recurring_templates()` cuenta la creación pending como éxito; `_record_check_result()` puede marcar `passed` con un `success_count` positivo aunque el diario aún no llegó a GL. Los errores no incluyen identificación de plantilla (`services.py:1148-1201`). Cancelar plantilla solo cambia su estado y confirma; no resuelve aplicaciones pending, y el diario asociado aún puede postearse (`recurring_journal_service.py:193-207`, `journal_service.py:271-289`).

Las pruebas existentes de recurrentes verifican balance/frecuencia, no fallo parcial, retry, pending cancelada ni check solo cuando todo está posteado. QA1/QA2 rechazan independientemente contra el criterio más reciente: recuperar/reconciliar pending sin duplicar evidencia, identificar plantilla fallida y marcar éxito solo cuando todas las aplicaciones completan. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2082 — QA1/QA2 rechazan: falta prueba real de concurrencia Tier 1

Releí el issue y los cuatro comentarios, incluida la devolución QA3 más reciente. El servicio toma `lock_default_scope` antes de buscar duplicado, mantiene `UNIQUE(company, petty_cash_id, reconciliation_date)` y traduce `IntegrityError` con rollback a `ValueError`; la ruta responde como validación. La implementación parece protegida.

La única prueba `test_petty_cash_reconciliation_race.py` reemplaza el lock por un wrapper y llama dos veces secuencialmente desde un mismo contexto/sesión. No produce carrera, no usa dos sesiones PostgreSQL, no verifica exactamente una fila concurrente, respuesta de dominio de la perdedora ni estado limpio tras conflicto. Como Tier 1/PostgreSQL y la carrera real son criterio explícito, QA1/QA2 rechazan independientemente. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2084 — QA1/QA2 rechazan: configuración bancaria conserva read-then-insert

Leí el issue y su comentario de vínculo con #1653. `_get_or_create_numbering_config()` consulta y agrega si no existe (`bancos/services.py:2050-2061`) sin lock, upsert ni retry. La restricción única `(bank_account_id, payment_type)` evita duplicar filas, pero una colisión llega como `IntegrityError`; `_save_numbering_configs()` confirma sin traducirla y la ruta solo captura `IdentifierConfigurationError` (`routes.py:1057-1063`), de modo que la solicitud perdedora puede acabar en 500. No encontré prueba de concurrencia para este modelo; `test_payment_numbering_config_empty_fields.py` cubre otro contrato. QA1/QA2 rechazan independientemente; serializar o releer ganador tras rollback y probar carrera con dos sesiones/ruta. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2128 — QA1/QA2 rechazan revalidación: dos contratos siguen sin prueba

Revisé el issue y sus cuatro comentarios, incluida la devolución más reciente de QA3. El código actual sí limita `respondent_user_agent` a 512 caracteres (`balance_confirmation_bp.py:879-900`), y `_handle_confirmation_creation()` confirma solo el éxito; captura excepciones con rollback/log interno y flash genérico sin revelar el detalle (`:254-295`). Pero la suite no prueba el límite del User-Agent en una respuesta pública ni una excepción durante la creación que verifique rollback y ausencia del texto interno en la respuesta. `test_balance_confirmation_attempts.py` cubre nombre largo, Unicode, cache, fecha nula, draft y límite concurrente; el archivo de delivery failures prueba envío de correo, no fallo de creación.

QA1/QA2 rechazan porque QA3 exigió esas regresiones HTTP para confirmar los dos contratos. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2129 — QA1/QA2 rechazan revalidación: tres contratos de bootstrap siguen abiertos

Revisé el issue y sus cinco comentarios, incluida la devolución QA3. `ensure_global_naming_series()` consulta solo la serie global `is_default=True`; una serie global activa no-default del mismo tipo/nombre no se recupera ni promueve y puede causar una colisión al insertar. `scalar_one_or_none()` lanza si existen múltiples defaults históricos; el lock/índice nuevo no normaliza esos datos. `ensure_default_naming_series_for_company()` delega a `_pick_naming_series()`, que devuelve una serie local activa no-default sin marcarla default y devuelve la global si solo existe global, incumpliendo default/serie por compañía.

Las pruebas actuales cubren bootstrap concurrente desde un esquema vacío, no los tres escenarios heredados del criterio QA3. QA1/QA2 rechazan independientemente; agregar regresiones y una normalización segura para estado histórico. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2186 — QA1/QA2 rechazan revalidación: control OTP concurrente solo probado en SQLite

Releí el issue y sus cuatro comentarios, incluida la devolución QA3. La implementación usa un `UPDATE` condicional (`failed_attempts < 5`) con incremento en SQL y decide el turno por `rowcount`; el endpoint respeta ese reclamo. La operación parece correcta por inspección.

La prueba concurrente ejecuta diez contextos/hilos y exige cinco turnos, pero el fixture fuerza `sqlite:///{tmp_path}/confirmation-attempts.sqlite`, no usa `DATABASE_URL` y no tiene marca `database`. Por eso el job PostgreSQL no corre la carrera contra PostgreSQL aunque corra la suite allí. Al ser control de seguridad concurrente y Tier 1, QA1/QA2 rechazan por falta de evidencia del motor. Agregar la variante con conexiones PostgreSQL independientes y mantener SQLite para Desktop. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2138 — QA1/QA2 rechazan revalidación: falta carrera PostgreSQL Tier 1

Revisé el issue y sus cinco comentarios. `create_ledger_mapping_rule()` toma `lock_default_scope` por identidad antes de validar/buscar/insertar, y la prueba SQLite con barrier verifica `created`/`rejected` y una sola regla activa. Pero `tests/test_ledger_mapping_rule_concurrency.py` fija SQLite en archivo y no está marcada `database`; no ejercita el upsert + `SELECT FOR UPDATE` PostgreSQL del lock. El modelo no tiene `UniqueConstraint` de respaldo en esa identidad, por lo que el control depende de ese mecanismo.

QA1/QA2 rechazan tras la devolución QA3: el criterio pide dos conexiones PostgreSQL, destinos distintos, un éxito/un conflicto y una regla activa. Mantener además la regresión SQLite Desktop. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2187 — QA1/QA2 rechazan revalidación: reset de contraseña solo concurrido en SQLite

Leí el issue y sus cuatro comentarios, incluida la devolución QA3. La emisión toma `_lock_secret_issuance` antes de consumir tokens previos e insertar el nuevo; el diseño parece serializar por usuario. La prueba con barrier verifica dos emisiones concurrentes y que solo un token queda válido, pero el fixture fija SQLite temporal y no tiene marca `database` ni usa `DATABASE_URL`; el job PostgreSQL no ejecuta la carrera sobre ese motor.

QA1/QA2 rechazan por falta de evidencia en Tier 1 para un control de autenticación Cloud. Agregar variante con conexiones PostgreSQL independientes; conservar SQLite Desktop. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2187 — QA1/QA2 rechazan revalidación: reset de contraseña solo concurrido en SQLite

Leí el issue y sus cuatro comentarios, incluida la devolución QA3. La emisión toma `_lock_secret_issuance` antes de consumir tokens previos e insertar el nuevo; el diseño parece serializar por usuario. La prueba con barrier verifica dos emisiones concurrentes y que solo un token queda válido, pero el fixture fija SQLite temporal y no tiene marca `database` ni usa `DATABASE_URL`; el job PostgreSQL no ejecuta la carrera sobre ese motor.

QA1/QA2 rechazan por falta de evidencia en Tier 1 para un control de autenticación Cloud. Agregar variante con conexiones PostgreSQL independientes; conservar SQLite Desktop. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2188 — QA1/QA2 rechazan re-revisión: el orden de locks permite deadlock

Leí el issue y sus cuatro comentarios, incluida la devolución QA3 por falta de QA2 sobre `1401aad7`. El cambio sí arregla lecturas obsoletas: `_fetch_hierarchy_node_locked()` usa `FOR UPDATE + populate_existing`; el test está marcado `database`, usa la URI configurada y se ejecuta para motores externos.

Residual bloqueante independiente: al editar, `check_hierarchy_cycle()` llama `_hierarchy_company_codes()` antes de `_lock_hierarchy_companies()`. La primera función bloquea el nodo origen; después se bloquea Entity; la caminata descendente/ascedente vuelve a bloquear nodos. Interleaving posible: T1 bloquea A y Entity, luego necesita bloquear C como ancestro; T2 ya bloqueó C y espera Entity. Se forma deadlock. Los writers Unit/Project no convierten `OperationalError`/deadlock de validación en conflicto controlado (`routes.py` y `services.py` capturan `ValueError`; `commit_hierarchy_change` solo captura `IntegrityError`). El test existente inicia T2 solo después de que T1 terminó la validación, por lo que fuerza el orden seguro y no cubre esa carrera.

QA1/QA2 rechazan independientemente. Adquirir anclas de compañía antes de nodos en orden determinista, revalidar compañía actual y agregar regresión Tier 1 que fuerce el interleaving inverso y descarte HTTP 500/deadlock no controlado. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #1730 — QA1/QA2 rechazan: seed de permisos no es idempotente

Leí el issue y su comentario de vínculo. `base_data()` ejecuta `cargar_permisos_predeterminados()` antes de crear el administrador. La función crea nuevos `RolesAccess` para cada rol/módulo y los confirma individualmente sin consultar/upsert; el modelo solo tiene índice no único `(rol_id, module_id)`. Si falla bootstrap después de commits parciales y se reintenta, las filas previas se duplican; los permisos se leen como conjunto de grants, así que duplicados persistentes también pueden conservar permisos antiguos al editar. No encontré test de retry/fallo parcial ni de una fila por clave lógica. QA1/QA2 rechazan independientemente; hacer seed idempotente y cubrir reintento tras fallo parcial. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### #1910 — QA1/QA2 rechazan localmente: el harness PostgreSQL citado no está en HEAD

Leí el issue y sus dos comentarios. Ambos describen que el harness `tests/test_concurrent_uniqueness.py` convierte una URL SQLAlchemy a `str(url)` y pierde el password en PostgreSQL, y que una copia temporal que renderiza `hide_password=False` pasó los tres escenarios de reembolso/reserva/anulación.

En el HEAD revisado no existe `tests/test_concurrent_uniqueness.py` ni referencias a `TestConcurrenciaPostgreSQL` o `_base_aislada_concurrencia` en `tests/`. Los tests cercanos de tax ID/email prueban contratos distintos, no la creación de bases aisladas ni las tres carreras. Por tanto no hay en HEAD una regresión para demostrar ni el arreglo de URL ni las carreras Tier 1. QA1/QA2 rechazan por falta de evidencia local. QA2 encontró que el fix histórico `57b7f358` corrige la URL, pero `0970476b` eliminó el harness y sus tres escenarios antes del HEAD actual. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #2076 — QA1/QA2 rechazan: approve obsoleto puede revivir tras rechazo

Leí el issue y sus siete comentarios, incluida la devolución QA3. `approve()` y `reject()` ahora cargan la solicitud pendiente con lock y `reject()` revalida su estado; esa parte serializa transiciones. Pero si `reject()` gana, un `approve()` concurrente que esperaba por el lock obtiene `req=None`; `approve()` solo busca solicitudes `Approved` y después llama `request_approval()`. Esa función ignora solicitudes `Rejected`, puede crear una nueva; el flujo `approve()` continúa y puede ejecutar posting/cancelación y sus efectos económicos. Una operación obsoleta puede por tanto revivir el documento después del rechazo.

`tests/test_approval_reject_lock.py` solo ejecuta dos rechazos secuenciales en una sesión y verifica una acción; no prueba approve-vs-reject, doble sesión PostgreSQL, que no aparezca una nueva solicitud ni ausencia de GL/stock/side effects del perdedor. QA1/QA2 rechazan independientemente. La ruta perdedora debe fallar sin reabrir; agregar carrera PostgreSQL con una transición/acción terminal y sin efectos del intento perdedor. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### #1680 — QA1/QA2 rechazan: el POST obsoleto de OC sobrescribe sin compare de versión

Leí el issue y su comentario de vínculo #1653. `DocBase.version` solo tiene default 1; no hay `version_id_col`, incremento ni comparación del valor observado por el formulario. `FormularioOrdenCompra` y la plantilla no envían versión. El endpoint recarga la OC por ID en POST, pero `_update_purchase_order_from_request()` confía en el payload del navegador, reemplaza todas las líneas y confirma sin comparar una versión esperada. Un formulario abierto antes del guardado de otra persona puede sobrescribir cabecera/líneas recientes aun cuando ORM recargue el objeto. El optimismo de mapper por sí solo tampoco resolvería el caso si el POST no envía la versión de lectura.

No encontré prueba de POST stale para OC; la cobertura de adjudicación es otro flujo. QA1/QA2 rechazan independientemente. Incluir versión leída en GET/form, comparar atómicamente en POST y ante conflicto preservar cabecera, líneas y relaciones. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### QA1/QA2 estática — #1732

**Veredicto: aprobado localmente por QA1 y QA2; GitHub intacto.** La prueba `test_editar_usuario_revoca_jwt_y_sesion_tras_reactivacion` (`tests/test_token_requerido.py:214-255`) usa login y POST HTTP reales de administrador para desactivar al usuario, comprueba la invalidación del JWT y de la cookie de sesión anterior, y confirma que reactivar no revive credenciales antiguas mientras un login nuevo sí funciona. Una segunda prueba cubre el toggle de administración para el JWT. Ambas rutas convergen en `_set_user_active()` y `revocar_credenciales_usuario()`; `cargar_sesion()` exige cuenta activa y versión coincidente, por lo que la revocación alcanza también las sesiones del portal. No encontré brecha bloqueante frente al último hallazgo QA3. No ejecuté pruebas/linters ni cambié código, etiquetas o GitHub.

### QA1/QA2 estática — #1917

**Veredicto: rechazado; falta una regresión funcional de la ruta OTP.** La implementación vigente ya conserva el objeto `Response` devuelto por `helpers.redireccion_despues_de_login()` y aplica `set_cookie()` sobre esa misma respuesta (`auth/__init__.py:229-242`), lo que corrige la doble envoltura descrita en el issue. Sin embargo, `rg` no encuentra una prueba del POST exitoso a `/auth/verify-otp`; `tests/test_session_security_fail_closed.py` solo cubre emisión/desafío, entrega fallida y dispositivo reconocido. La función sigue excluida de cobertura con `# pragma: no cover`, y no hay regresión que compruebe `Location` de destino, cookie de dispositivo y autenticación, ni la rama de destino predeterminado. QA1/QA2 rechazan localmente por la cobertura explícita pedida en el comentario más reciente. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### QA1/QA2 estática — #1948

**Veredicto: rechazado por cobertura retirada del HEAD; GitHub intacto.** `requirements.txt:6` fija `email-validator==2.3.0`, y `pyproject.toml` toma sus dependencias desde ese archivo, así que la solución funcional se distribuye. Pero `tests/test_email_validator_dependency.py`, agregado en `a91b72c0`, ya no está en el árbol de `45e38f2b` (se retiró en `0970476b`). Hay regresiones de rutas con emails válidos, pero no encontramos cobertura vigente para correo inválido rechazado por el formulario ni el campo opcional vacío. QA1/QA2 coinciden en que falta recuperar una prueba sustancial del contrato esperado antes de confirmar. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### QA1/QA2 estática — #1965

**Veredicto: rechazado por regresión retirada del HEAD; GitHub intacto.** `autenticar_usuario()` captura `InvalidHashError`, registra únicamente el ID del usuario y devuelve `None` (`auth/helpers.py:28-42`); el login responde como credenciales inválidas y no revela el hash. Sin embargo, `tests/test_invalid_password_hash.py` del commit `c71ddfd1` fue eliminado en `0970476b` y no hay una prueba equivalente de login con hash ilegible. QA1/QA2 rechazan independientemente porque falta la regresión HTTP para el caso preciso que antes daba 500; debe verificar respuesta controlada y que no autentique. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### QA1/QA2 estática — #2023

**Veredicto: rechazado localmente; GitHub intacto.** La ruta genera el nuevo token dentro de la transacción, envía correo y confirma solo si `enviar_token_recuperacion_email()` retorna éxito; si SMTP falla, ejecuta rollback y responde con el redirect/mensaje genérico compartido (`auth/__init__.py:251-286`). El rollback parece restaurar el token anterior y eliminar el nuevo. Pero las pruebas actuales de recuperación solo cubren envío exitoso y email ambiguo; falta el test HTTP de SMTP fallido que confirme mensaje genérico, token previo utilizable y ausencia del nuevo token. Además, si SMTP acepta el correo y el commit posterior falla, la ruta no captura el error y el token que contiene el enlace enviado puede revertirse; no existe cola durable de recuperación. QA1/QA2 rechazan por regresiones ausentes y este fallo post-envío sin solución durable. No ejecuté pruebas/linters ni cambié código/GitHub/etiquetas.

### QA1/QA2 estática — #1762

**Veredicto: rechazado por falta de regresión HTTP; GitHub intacto.** El fix funcional sí permanece: `verify_otp()` confirma la transacción cuando el código es incorrecto (`auth/__init__.py:241-242`), y `validar_otp()` incrementa de forma condicional atómica y consume el código en el límite (`device_verification.py:151-220`). Pero el test HTTP de intentos repetidos del commit `804c3669` no está en HEAD. Las pruebas vigentes llaman al helper directamente y algunas confirman desde la propia prueba, así que no detectarían la ausencia del commit en el endpoint. QA1/QA2 rechazan independientemente; hace falta POST real con sesión OTP y lectura del contador desde otro contexto después de cada solicitud, incluyendo consumo/rechazo en el límite. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### QA1/QA2 estática — #1958

**Veredicto: rechazado por falta de dos regresiones de contrato; GitHub intacto.** El flujo confirma cada fila `EmailQueue` como `pending` antes de SMTP y `deliver_email_queue_item()` intenta persistirla como `failed`/reintentable si falla el commit de resultado tras SMTP (`api/__init__.py:966-1000`, `messaging/email.py:284-298`). La prueba `test_uncertain_html_delivery_stays_retryable_after_commit_failure` inyecta el fallo únicamente en un reintento administrativo, no en el envío inicial. Los envíos iniciales vigentes cubren un destinatario; no encontramos prueba de varios destinatarios con un éxito y un fallo, estados independientes y respuesta parcial. QA1/QA2 rechazan independientemente: cubrir el commit fallido en envío inicial y la entrega parcial multi-destinatario, preservando evidencia durable y evitando reenvío ciego. No ejecuté pruebas/linters ni cambié código/GitHub/etiquetas.

### QA1/QA2 estática — #1923 (HEAD `45e38f2b`)

**Veredicto: aprobado localmente; GitHub/etiquetas intactos.** Aunque QA3 devolvió el issue porque el test no aparecía en `origin/estabilizacion`, el HEAD local contiene `dfdfdf41` y `tests/test_print_return_url.py`. `_safe_return_url()` descarta rutas que no empiezan con `/`, `//`, backslash literal, `%5c` sin distinción de mayúsculas, controles, esquema o authority (`printing/routes.py:123-134`), y la ruta de preview aplica el guard antes de entregar el valor al renderer. La regresión cubre rutas internas y las variantes externas/manipuladas que motivaron el caso. QA1/QA2 reevalúan independientemente y aprueban el HEAD local; QA2 observa que no hay caso separado de doble backslash literal, pero la guarda los rechaza por la misma condición y no es bloqueante. No ejecuté pruebas/linters ni cambié código/GitHub/etiquetas.

### QA1/QA2 estática — #1930 (HEAD `45e38f2b`)

**Veredicto: aprobado localmente; GitHub/etiquetas intactos.** El commit `3a81c9d2` convierte la validación de tamaño/orientación inválidos a `TemplateValidationError` (`printing/service.py:242-251`). Las rutas de alta y edición capturan el error, revierten y renderizan formulario; la edición valida antes de crear versión o mutar campos (`printing/admin_routes.py:85-119,283-309`). `tests/test_print_pdf_page_settings.py` está trackeado en HEAD y hace POST autenticado de alta/edición con tamaño y orientación inválidos; comprueba HTTP controlado, mensaje y que la plantilla conserve el tamaño. QA1/QA2 aprobaron independientemente. La devolución QA3 por test ausente en origin precede al test/restauración local presentes en este HEAD. No ejecuté pruebas/linters ni cambié código/GitHub/etiquetas.

### QA1/QA2 re-revisión estática — #1758 (HEAD `45e38f2b`)

**Veredicto: rechazado por una regresión de integración faltante; GitHub/etiquetas intactos.** La política funcional ya está aprobada por el responsable y no es un bloqueo. El código guarda peso/volumen/UOM por `ImportLandedCostItem`, usa defaults del catálogo y `_build_landed_cost_item_contexts()` copia las dimensiones persistidas a `ItemContext`, desde donde el motor calcula el prorrateo. Pero la suite prueba el motor con `ItemContext` armado a mano y prueba persistencia leyendo las filas por separado. No existe un test que conecte una línea persistida con el builder/contexto real de posting y verifique la asignación resultante. QA1/QA2 rechazan independientemente: si se quitara la propagación del builder, la cobertura actual seguiría pasando y el contrato histórico de consumo podría romperse sin aviso. Agregar una regresión representativa para peso y volumen por el camino persistido → contexto → cálculo/posting, sin mock del builder. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### QA1/QA2 re-revisión estática — #2077 (HEAD `45e38f2b`)

**Resultado actual: QA1/QA2 aprueban estáticamente; GitHub/etiquetas intactos.** La prueba restaurada `tests/test_attachment_service.py` está versionada y cubre validación por contenido, persistencia física/hash, rollback tras escritura, limpieza, reemplazo fallido y borrado pendiente auditado. La objeción anterior sobre falta de POST multipart positivo se reevalúa: la ruta HTTP activa delega directamente en `upload_attachment()`, y el test funcional fija el contrato del servicio compartido, incluyendo que invoque validación y almacenamiento; QA2 confirmó independientemente esa cadena y suficiencia para el alcance de #2077. La ausencia de migración Alembic para `File.sha256` y el DDL de arranque siguen registrados como contrato separado de #1898, no como bloqueo para el pipeline solicitado en #2077. No se ejecutaron pruebas/linters ni se modificó código/GitHub/etiquetas.

#### Revisión actual de la objeción QA3 (21-11-2026)

La objeción de QA3 de que `tests/test_attachment_service.py` no existe en `estabilizacion` ya no aplica al árbol remoto consultado: GitHub devuelve el archivo en esa rama con SHA `62b9cd92cd319bb857f701a0f8f191d41ca3d935`, igual al blob de HEAD local y de la referencia local `origin/estabilizacion`. El test remoto de flujo único invoca `upload_attachment()` y afirma una llamada a `validate_upload()` y `store_attachment()`; otros tests cubren contenido inválido, persistencia/hash, fallo de copia y rollback/limpieza.


QA2 revisó independientemente el flujo vigente y coincide en aprobación estática: el endpoint llama a `upload_attachment()`, y el servicio llama a `validate_upload()`/`store_attachment()`; los tests fijan los fallos y efectos persistidos solicitados. El POST HTTP positivo sería una mejora adicional de integración, pero no invalida las regresiones funcionales del pipeline ni la conexión observable en la ruta. Mantengo la migración `File.sha256` como deuda de #1898, no como bloqueo específico de #2077. El estado GitHub sigue `needs-work` porque no cambié etiquetas ni publiqué comentarios.

### QA1/QA2 re-revisión estática — #1891 (HEAD `45e38f2b`)

**Veredicto: rechazado; mantener consulta histórica sin recrear el flujo genérico. GitHub/etiquetas intactos.** La decisión vigente permite solo ajustes positivos/negativos y exige conservar el histórico. El alta normal excluye `stock_adjustment` de choices y del validador, pero la ruta `POST /stock-entry/<id>/duplicate` acepta cualquier origen salvo `docstatus == 2` y copia `origen.purpose` al borrador nuevo sin ejecutar la validación del propósito (`inventario/routes.py:1034-1057`). La fila histórica genérica aún puede recrear el tercer flujo por duplicación. `tests/test_stock_adjustment_contract.py` está en HEAD, pero cubre alta/consulta/posting y no ese bypass. QA1/QA2 rechazan independientemente; bloquear duplicación de propósito legacy (y fijar el contrato con regresión HTTP que compruebe que no se inserta fila), preservando vista/consulta del histórico. No ejecuté tests/linters ni cambié código/GitHub/etiquetas.

### QA1/QA2 re-revisión estática — #1938 (HEAD `45e38f2b`)

**Veredicto: rechazado; GitHub/etiquetas intactos.** Leí el historial completo del issue; la ADR posterior aprobó vistas guardadas con servicio reutilizable, RBAC, aislamiento por compañía y permisos vigentes. El servicio valida permiso de reportes/acceso actual a la compañía y limita cada lectura/escritura por usuario, compañía y reporte. La tabla/modelo, servicio, UI y prueba CRUD están en HEAD pese a la devolución QA3 por archivo ausente en origin.

Persisten dos brechas bloqueantes concordantes en QA1/QA2:

1. Se guardan `show_users` y `advanced` en `display_json` (`saved_views_service.py:42,96-115`), pero `restore_filters()` solo restaura `filters_json`; el render/plantilla sigue leyendo esas preferencias desde `request.args` (`reportes/helpers.py:1274,1430`, `financial_report.html:52,75,82-90`). Los enlaces de vista conservan los query args actuales y no aplican `view_display` para esos dos campos. La selección de vista no restaura esos ajustes y no hay regresión que lo detecte.
2. `SavedReportView` crea la tabla `saved_report_view`, pero `cacao_accounting/migrations/` solo tiene el baseline no-op y carece de migración efectiva. El contrato aprobado en #1898 exige migración Alembic para tablas nuevas y soporte de esquemas existentes; una base existente que no haya recibido create_all queda sin tabla.

Las pruebas presentes cubren filtros, columnas/agrupación, CRUD, acceso y colisión, pero no restauración de `show_users`/`advanced` ni upgrade de una base existente. QA1/QA2 rechazan independientemente. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

### QA1/QA2 re-revisión estática — #1973 (HEAD `45e38f2b`)

**Veredicto: rechazado por cobertura incompleta; GitHub/etiquetas intactos.** La firma actual de `transaction_grid()` conserva `source_api_url` y `title`, y búsquedas de las invocaciones actuales no encuentran los cuatro argumentos retirados. La prueba está trackeada pese a QA3 haberla encontrado ausente en origin. Pero `_argumentos_de_llamada()` usa `.search()` y la guarda inspecciona solo la primera llamada por archivo. Plantillas de Venta/Factura/Entrega y Recepción tienen varias llamadas; los render HTTP cubren plantillas de una sola invocación y compilar la macro no valida esos callsites. QA1/QA2 rechazan independientemente porque una regresión en la segunda o posteriores invocaciones pasaría. Cambiar la regresión a iterar todas las invocaciones de cada plantilla y conservar los parámetros funcionales. No ejecuté tests/linters ni modifiqué código/GitHub/etiquetas.

Revalidación en rama remota `estabilizacion`: `tests/test_transaction_grid_contract.py` sí existe actualmente (la ausencia citada por QA3 es stale). QA2 confirma de forma independiente que la brecha de `.search()` sigue vigente y que los smoke tests no cubren facturas con ramas múltiples. El rechazo QA1/QA2 actual se mantiene por cobertura, no por ausencia del archivo.

### QA1/QA2 independiente — #1916 (HEAD `45e38f2b`)

**Veredicto: rechazado; no hubo cambios en GitHub ni etiquetas.** La decisión más reciente del responsable en #1916 elimina el bloqueo histórico de producto: es código muerto pre-alpha y debe retirarse. El ORM ya no declara las cinco tablas ni se encontraron consumidores productivos activos. Sin embargo, queda la constante FK huérfana `WORKFLOW_STATE_ID` en `database/__init__.py:105`.

La brecha principal es el upgrade de bases existentes: la migración `20261109_0003_drop_workflow.py` del commit `6205ae9e` fue eliminada por `41c7af1e`; el árbol actual solo contiene el baseline Alembic no-op. `create_all()` no elimina tablas y `db migrate` no contiene una operación de retiro, por lo que instalaciones existentes pueden conservar las cinco tablas sin contrato de esquema ejecutable. La decisión pre-alpha autoriza descartar los datos, y #1898 ahora exige que los upgrades de esquema sean migraciones Alembic efectivas. QA1 y QA2 rechazaron independientemente; ambos recomiendan retirar la constante y restaurar/crear una migración efectiva sobre el chain vigente. No se ejecutaron pruebas ni linters.

### QA1/QA2 re-revisión estática — #1492 (HEAD `45e38f2b`)

**Veredicto: QA1/QA2 rechazan por falta de una regresión que discrimine la causa del issue; GitHub/etiquetas intactos.** El archivo de pruebas está versionado tanto en HEAD como en la rama remota `estabilizacion` (SHA `f7812500ead53df23d1e0b7abf15725e8b5a88be`), así que la objeción de QA3 de 404 está superada. La implementación parece correcta: `validate_template_balance()` protege la forma individual y suma agregada, y se reutiliza al crear, aprobar y aplicar (`recurring_journal_service.py:133-163,166-168,248-251`).

La regresión de alta actual usa una línea `(100,100)` y otra `(100,0)`, con totales agregados 200/100. Las variantes históricas ponen `(100,100)` y `(0,0)` sobre las líneas originales, con totales 100/100 pero una línea cero. Por tanto, quitando solo el guard de ambos lados positivos, los tests todavía rechazarían por otro invariante; ningún test reproduce el defecto original donde los totales globales también balancean (por ejemplo, líneas `(100,100)` y `(50,50)`). QA2 confirmó independientemente el mismo gap. Añadir regresión discriminante para creación y una plantilla histórica en aprobación o aplicación, verificando rechazo antes de persistir o generar diario. No ejecuté tests/linters.

La frecuencia mensual, el rechazo de frecuencias históricas no soportadas y las aplicaciones de plantillas distintas están cubiertas. Para #1493 permanece la brecha separada de reintentar una misma ocurrencia tras estado `reversed`/`failed`, registrada en la revisión de ese issue.

### QA1/QA2 re-revisión estática — #1493 (HEAD `45e38f2b`)

**Veredicto: rechazado por idempotencia incompleta; GitHub y etiquetas intactos.** La decisión aprobada está implementada: el formulario y servicio solo aceptan `monthly`, el servicio rechaza plantillas históricas `weekly`/`daily` al aplicar, y el test trackeado cubre esos casos. También cubre dos plantillas independientes en fechas distintas del mismo período, conforme al criterio de que una necesidad semanal se represente con cuatro plantillas mensuales.

Falta la regresión de reintentar la misma plantilla/ocurrencia. `apply_recurring_template()` busca la clave compañía/libro/plantilla/año/período, pero solo devuelve error de dominio para estados `pending` y `applied` (`recurring_journal_service.py:230-246`). Al cancelar/revertir un diario, `_reverse_recurring_application()` marca la aplicación `reversed` (`journal_service.py:383-388`); el retry atraviesa el guard y la unicidad `uq_recurring_application` (`database/__init__.py:4377-4383`) falla con `IntegrityError` al insertar, en vez de una respuesta controlada. `failed` sigue el mismo bypass si existe una fila heredada. La ruta de cierre maneja `RecurringJournalError`, no este error de integridad (`contabilidad/services.py:1165`). La prueba remota de frecuencia sí existe en `estabilizacion` con SHA `f7812500ead53df23d1e0b7abf15725e8b5a88be`; la objeción QA3 de 404 está superada, pero su caso de dos plantillas distintas no cubre reintentar la misma ocurrencia. QA2 confirmó independientemente el gap y el posible error 500. QA1/QA2 rechazan: fijar el contrato de retry para cualquier estado ya existente y probar que no deja journal/aplicación duplicados ni 500. No ejecuté tests/linters.

### QA1/QA2 re-revisión estática — #1564 (HEAD `45e38f2b`)

**Veredicto: QA1/QA2 rechazan; no se modificaron GitHub ni etiquetas.** La revisión del árbol actual confirma el hallazgo en los nueve listados: cuatro consultas de cliente y cinco de proveedor aplican `LIMIT 100` (`portal/__init__.py:70-98,197-236`) sin leer `page` ni exponer total/página siguiente. Los templates solo iteran esas filas y calculan cada badge con `|length` (`customer_dashboard.html:16,55,94,133`; `supplier_dashboard.html:16,55,94,133,182`). Así, resultados 101+ son inaccesibles y el badge presenta el tamaño de la primera tanda como total. Los comentarios del issue registran además GETs autenticados con 101 facturas y 100 enlaces/insignia en ambos dashboards (comments `6707457707`, `6707547057`). Búsqueda estática no encontró pruebas actuales de paginación/counts en estos dashboards; QA2 confirma independientemente los nueve LIMIT y la falta de navegación/total. Cubrir cada lista con páginas/conteos manteniendo filtros de compañía/tercero y documentos publicados. No ejecuté pruebas/linters.

### QA1/QA2 estática — #1737 (HEAD `45e38f2b`)

**Veredicto: QA1/QA2 rechazan; GitHub/etiquetas intactos.** Leí el issue vigente (sin comentarios adicionales). `validate_item_uom_rows()` valida UOM base, conversiones declaradas y factores finitos/positivos (`inventario/service.py:917-937`), pero no recibe ni contrasta `purchase_uom`/`sale_uom` con la unidad base y las conversiones del artículo. Alta y edición asignan esos campos directamente (`:953-982`, `:715-740,780-797`); los formularios admiten cualquier UOM del catálogo global (`inventario/routes.py:418-420,478-480`). Los consumidores convierten cantidades a UOM base y fallan cuando falta el factor de conversión (`service.py:253-276`, `ventas/services.py:1156`). QA2 confirma independientemente ausencia de validación y regresiones específicas; el barrido de tests tampoco encuentra casos de `purchase_uom`/`sale_uom` (solo pruebas de factores/configuración de conversión). Fijar que el campo operativo sea nulo, igual a la base o una conversión declarada para el artículo; validar antes de toda mutación y probar alta/edición con casos válidos e inválidos. No ejecuté tests/linters ni modifiqué código/GitHub.

### QA1/QA2 estática — #1752 (HEAD `45e38f2b`)

**Veredicto: rechazado; GitHub/etiquetas intactos.** El detalle ofrece «Editar» para `docstatus == 0` y envía `landed_cost_id` (`compras/templates/compras/import_landed_cost.html:24-28`), pero la ruta `/import-landed-cost/new` no lee ese ID (`routes.py:3535-3585`). Tanto GET como POST continúan el alta; el POST llama siempre `_create_import_landed_cost_from_request()`, que construye/añade/commitea un `ImportLandedCost` nuevo (`services.py:3252-3354`). La edición no carga/autoriza el mismo borrador ni comprueba estado, y un envío crea otro documento dejando intacto el original. No encontré prueba de GET/POST de edición; los tests vigentes cubren alta. QA1/QA2 rechazan independientemente: implementar actualización acotada con permiso/compañía, guard de borrador, líneas/cargos y evidencia del mismo ID sin duplicación, o retirar el botón si producto no admite edición. No ejecuté tests/linters.

### QA1/QA2 re-revisión estática — #1758 (HEAD `45e38f2b`)

**Veredicto: rechazado por dos brechas técnicas; GitHub/etiquetas intactos.** Se respeta la decisión directa del responsable de conservar y completar prorrateo por peso/volumen; la pregunta histórica sobre política de #2240 no es un bloqueo. La implementación persiste dimensiones por línea/unidad y defaults del catálogo, valida datos finitos/no negativos/UOM, rechaza mezcla de unidades (`compras/services.py:3108-3172`), y el builder pasa peso/volumen persistidos a `ItemContext` (`document_builders.py:644-673`).

1. **Falta prueba end-to-end del contrato dimensional.** `test_persiste_peso_y_volumen_por_linea` solo vuelve a leer las columnas persistidas (`tests/test_landed_cost_weight_volume.py:122-164`); la prueba de distribución alimenta `LandedCostEngine` con `ItemContext` armado a mano (`:40-63`). No existe caso que lea las líneas guardadas, ejecute el builder/context builder real y compruebe asignación del engine/posting. Si se rompe la propagación del builder, ninguna regresión cae.
2. **Falta migración para bases existentes.** Se añadieron `weight`, `weight_uom`, `volume`, `volume_uom` al modelo de artículo y al de línea de costo (`database/__init__.py:1401-1407,2737-2744`), pero `migrations/` solo tiene `20260809_0001_baseline.py` no-op. Una DB existente no recibe columnas con `create_all`; el contrato #1898 requiere migración Alembic efectiva.

QA1 y QA2 rechazan independientemente. Para completar: migrar los campos y añadir una regresión persisted line → builder real → distribución por peso y volumen. El test de issue sí está trackeado en HEAD; la devolución QA3 por ausencia en origin está obsoleta para la copia local. No ejecuté tests/linters.

### QA1/QA2 re-revisión estática — #1811 (HEAD `45e38f2b`)

**Veredicto: rechazado; GitHub/etiquetas intactos.** La descripción antigua de HTTP 500 ya no aplica: la ruta actual captura `ValueError`, revierte y vuelve a renderizar el formulario (`inventario/routes.py:910-927`; `services.py:918-920`). Pero persiste el bloqueo funcional: la ruta usa `stock_reconciliation_nuevo.html` para el alta normal y esa plantilla completa no tiene campo `transaction_currency` ni `currency` (`:17-20`, formulario y cabecera hasta líneas 193-207); el handler sigue exigiendo explícitamente una de esas monedas (`services.py:884-886`). Así, el POST servido por UI solo muestra error y no guarda la conciliación. Los tests de endpoint que hacen POST agregan `transaction_currency=NIO` manualmente; el caso de conciliación disponible es negativo por dimensiones ajenas y no es una creación HTTP válida desde el formulario. QA1/QA2 rechazan independientemente: exponer/proveer la moneda de forma explícita y cubrir POST real exitoso más omisión controlada sin persistencia parcial/500.

### QA1/QA2 re-revisión estática — #1813 (HEAD `45e38f2b`)

**Veredicto: rechazado; GitHub/etiquetas intactos.** El commit `94043df4` conecta el `matching_type` a un guard que exige `delivery_note_id` cuando el helper se ejecuta con factura ligada a una orden. El test nuevo conserva 2-way sin nota y rechaza 3-way con OV pero sin nota; sin embargo, llama directamente al helper.

Queda un bypass funcional: para `matching_type="3-way"` con `require_sales_order=False`, una factura sin OV ni nota llega al retorno temprano `if not config or not config.require_sales_order: return` (`ventas/services.py:1906-1915`), sin ejecutar `_validate_3way_delivery_requirement()`. También se puede llegar con Nota de Entrega sin una Orden de Venta vinculada: la validación de la nota no satisface por sí sola el conjunto de tres documentos. El endpoint productivo de submit llama a `_validate_sales_order_requirement()` (`ventas/routes.py:2518-2523`), así que el bypass puede aprobar una factura sin OV + Nota + Factura. El test actual invoca directamente el helper con OV y `require_sales_order=True` (`test_3way_delivery_requirement.py:47-62`), sin cubrir estos bypasses ni el POST de submit. QA2 confirma independientemente ambos casos; QA1/QA2 rechazan: 3-way debe imponer OV y Nota aunque el flag separado sea falso; cubrir submit HTTP, rollback/no posting y conservar 2-way. No ejecuté tests/linters.

### QA1/QA2 revisión local — #1888 (HEAD `45e38f2b`)

**Rechazado; sin cambiar GitHub ni etiquetas.** La lectura del issue y de todos sus comentarios confirma que la definición funcional ya no está pendiente: el comentario más reciente aprueba integrar centro de costo/proyecto y `remarks` por línea según #1359, retirar ambos payloads fiscales, impedir selección arbitraria de cuenta y rechazar en backend los campos funcionales no soportados. La decisión coordinada de #1359 también exige persistencia histórica, validación de compañía/estado/autorización, propagación a GL por todos los libros y consulta aislada con RBAC.

Evidencia local: `StockEntryItem` (`database/__init__.py:1567-1610`) no tiene columnas para centro de costo, proyecto ni remarks. `_save_stock_entry_item()` (`inventario/services.py:599-636`) crea la línea solo con artículo, almacenes, cantidad, UOM, costo, lote y serial; no consume los campos `cost_center_N`, `project_N` ni `remarks_N`. El render de edición (`inventario/services.py:1087-1125`) tampoco recupera ni inicializa esos valores. A la vez, `entrada_nuevo.html:55` invoca el macro genérico sin opciones para limitar campos, y `transaction_form_macros.html:470-498,820-823` envía cuenta, centro de costo, unidad, proyecto, remarks y payloads de impuestos; así, los campos no admitidos se descartan silenciosamente. La búsqueda en el writer confirma que no hay rechazo explícito de esos campos ni consumo de payload fiscal. El posteo de conciliación solo valida dimensiones de cabecera (`services.py:1032-1034`), no resuelve dimensiones por línea ni crea asociaciones de dimensión en GL.

Las pruebas existentes de inventario verifican UOM/edición y algunas cabeceras; `test_i2f_uom_editing.py` conserva campos de una petición rechazada al volver a renderizar, pero no valida que se guarden. No hay cobertura de persistencia/readback de remarks o dimensiones por línea, posting dimensional a GL, rechazo de controles fiscales/cuenta, aislamiento entre compañías/RBAC ni regresión de configuración del macro para otros consumidores. QA2 confirma de forma independiente que los guards y posting actuales solo usan dimensiones de cabecera, y que el macro sigue mostrando payloads fiscales y controles no admitidos. El defecto afecta consistencia de captura y trazabilidad y deja la interfaz aceptando datos que no sobreviven al documento. Para aprobar hace falta completar el contrato y las pruebas de aceptación, coordinando la asociación GL compartida con #1359; conservar cantidades, valores, cuentas, ledger de stock, reversiones y multilibro. No ejecuté pruebas ni linters, conforme al rol QA.

### QA1 re-revisión estática — #1891 (HEAD `45e38f2b`)

**Rechazado por una ruta alternativa de alta; sin cambios en GitHub ni etiquetas.** El archivo de regresión citado por QA3 sí existe localmente (`tests/test_stock_adjustment_contract.py`) y cubre formulario, guard de servicio, URLs de alta retiradas, lectura del histórico y posting positivo/negativo. Sin embargo, la cobertura omite el duplicado del documento histórico.

`inventario/routes.py:1031-1058` autoriza duplicar cualquier `StockEntry` salvo cancelado y asigna `purpose=origen.purpose` al borrador nuevo, sin comprobar `_validate_stock_entry_purpose()` ni que el propósito esté en `STOCK_ENTRY_PURPOSES`. Por tanto, al duplicar una fila histórica `stock_adjustment`, se crea un borrador nuevo con el propósito genérico que el formulario y el endpoint de alta rechazan. La ruta está expuesta como POST, el duplicado conserva líneas y luego queda disponible para submit; el endpoint de envío aún incluye `stock_adjustment` en sus excepciones para cantidad/tarifa y validación de solo valor (`routes.py:1117-1129`), reforzando que el documento puede continuar el flujo.

El criterio aprobado permite consultar el histórico, pero prohíbe crear ajustes genéricos. La ruta de duplicación transforma consulta histórica en nuevo documento operativo, así que es un bypass funcional bloqueante. Rechazar o redirigir explícitamente la duplicación de registros `stock_adjustment`, manteniendo la duplicación de propósitos vigentes y la lectura histórica; agregar una regresión HTTP que verifique que no se crea un borrador genérico ni evidencia derivada. Revisión estática sin ejecutar pruebas/linters.

QA2 terminó revisión independiente de #1888 y también **rechaza**. Confirmó que el macro siempre renderiza controles account/dimensiones/remarks y pricing fiscal, el JS incluye `stock_entry` en los tipos de preview fiscal y el writer/renderer no persisten las dimensiones o remarks por línea ni rechazan payloads. También verificó que los guards actuales solo cubren dimensiones de cabecera; no hay origen de dimensiones por línea para propagar a GL. Encontró que los tests cercanos de macros prueban consumidores/HTTP 200, no aceptación funcional/rechazo fiscal de StockEntry. Resultado QA1/QA2 concordante, local y sin cambios de etiquetas.

QA2 hizo una lectura independiente de #1891 y **coincide en el rechazo**. Confirmó que la prueba local está presente y cubre alta, histórico y posting positivo, pero no la duplicación. El botón de `inventario/templates/inventario/entrada.html:23-30` se presenta para movimientos activos/no cancelados; la ruta copia `purpose` y confirma el nuevo registro (`routes.py:1031-1094`), y el submit/posting aún permite `stock_adjustment` (`routes.py:1123-1128`, `contabilidad/posting_service.py:4783-4795`). Con ello una fila histórica puede duplicarse y contabilizarse como ajuste genérico. QA1/QA2 convergen; issue/labels sin cambios y sin ejecutar pruebas/linters.

### QA1 revisión estática local — #1992 (HEAD `45e38f2b`)

**Rechazado; sin cambios de GitHub/etiquetas.** Leí los cinco comentarios. El criterio funcional más reciente (#6712637888) ya cierra la política: una selección de serie activa válida debe honrarse; ausencia usa default; selección inválida, inactiva, de otra compañía o tipo debe rechazarse; no consumir el contador default silenciosamente. El alcance fue extendido en comentarios a los selectores de vale, gasto y reposición.

El formulario de vale presenta `naming_series`, pero `caja_chica_vale_nuevo()` no lo pasa en `routes.py:1300-1311`, aunque `create_petty_cash_voucher()` ya acepta el parámetro y lo usa (`services.py:720-766`). Gasto también muestra selector pero `_submit_petty_cash_expense_form()` no lo pasa (`routes.py:1452-1466`), y `create_petty_cash_expense()` no admite `naming_series_id`; asigna default explícito `None` (`services.py:932-947,1001-1007`). Reposición muestra selector (`caja_chica_reposicion_nueva.html:22-36`), pero ruta no lo envía (`routes.py:1680-1687`) y servicio no admite el parámetro, asignando default `None` (`services.py:1541-1549,1612-1618`). No encontré pruebas funcionales de series seleccionadas para estos tres consumidores; las pruebas de petty cash existentes cubren otros contratos.

Además, vale/gasto/reconciliación/replenishment tratan `IdentifierConfigurationError` como numeración opcional (`services.py:767-768`, `1008-1009`, `1249-1250`, `1619-1620`). Una selección explícita inválida debe ser rechazada según el criterio reciente; el `except` indiscriminado podría ocultar ese error (en vale incluso se asigna el ID en el modelo antes de la generación). Diferenciar error de configuración realmente opcional al resolver default de una selección explícita inválida, manteniendo rollback y sin consumir secuencias. Añadir POSTs HTTP válidos, ausentes y de series inactivas/ajenas/de tipo incorrecto en los tres formularios y verificar `naming_series_id`, número y contador correspondiente. No ejecuté pruebas ni linters.

QA2 hizo revisión independiente de #1992 y coincide en el rechazo. Confirmó que los tres formularios exponen selectors, pero sus rutas/servicios no propagan el ID y asignan el default; por tanto una elección válida se ignora y consume el contador equivocado. `document_identifiers._pick_naming_series()` valida activo, compañía y tipo solo si recibe el ID, condición que esos consumidores no satisfacen. También corroboró que las pruebas `test_petty_cash*` no cubren serie alternativa, selección inválida ni contadores y que los servicios silencian `IdentifierConfigurationError`. Consenso QA1/QA2 local; sin ejecución de pruebas, cambios de código ni mutaciones GitHub.

Revalidación QA2 fresca tras leer los cinco comentarios actuales: mantiene el rechazo. Confirmó que el vale no pasa `naming_series_id` y captura el error, y que gasto/reposición tampoco pasan selección y tragan `IdentifierConfigurationError`; no existen pruebas de selección válida, default solo por campo ausente, rechazo de serie inactiva/ajena/tipo incorrecto ni contador consumido. La decisión aprobada más reciente (#6712637888) define ese contrato; no queda duda de producto. Sin cambios locales de producto ni GitHub.

### QA1 revisión estática local — #2061 (HEAD `45e38f2b`)

**Rechazo por bypass funcional en Waitress; GitHub/etiquetas intactos.** `__main__.py:26-55` llama al resolver si no existen usuarios y detiene con `SystemExit(1)` ante `ValueError`. En cambio `server.py:34-54` llama al resolver solamente si falla la conexión. `verifica_coneccion_db()` (`database/helpers.py:47-59`) hace `database.session.execute(select(User))` y usa la existencia del objeto `Result` como booleano, sin consumir filas; con la tabla accesible pero vacía lo considera conexión exitosa. En ese caso Waitress inicia en `server.py:56-59` sin verificar credenciales ni usuario inicial y el guard nunca corre. Las pruebas `tests/test_module_entrypoint_credentials.py:45-79` solo ejercitan `__main__`; no hay regresión del camino Waitress ni del rechazo sin admin. El criterio reciente (#6711996661) exige proteger ambos entry points. Corregir la comprobación para distinguir esquema accesible de admin existente, aplicar el guard de bootstrap en ambos caminos y probar Waitress no-dev sin credenciales (sin crear usuario ni llamar `serve`) y desarrollo autorizado. No ejecuté pruebas/linters.

### QA1 revisión estática local — #2062 (HEAD `45e38f2b`)

**No aprobable: falta una decisión funcional.** El issue no tiene comentarios posteriores al vínculo con #1658 y el cuerpo deja abiertas tres alternativas de producto: operación de borrado auditada, inactivación/limpieza permitida, o retirar la acción. `cuentas_predeterminadas()` aún ejecuta `session.delete(config)` y `commit()` sin capturar el `ValueError` (`admin/routes.py:1380-1386`); `CompanyDefaultAccount` permanece en `SENSITIVE_MODELS` (`internal_control_service.py:125-140`) y `_guard_sensitive_delete()` rechaza eliminación sensible directa (`:623-629`). La acción sigue visible (`admin/default_accounts.html:143`). Sin elegir una de las alternativas, QA no puede aprobar ni recomendar una mutación: hacerlo violaría AGENTS.md (“No tomes decisiones de negocio”). Se mantiene anotado como alcance pendiente local; no alteré `needs-work` ni solicité cambios externos.

QA2 comprobó el bypass de #2061 independientemente y coincide en el rechazo funcional. `verifica_coneccion_db()` acepta un `Result` truthy sin comprobar si hay usuarios; así `server()` con conexión a una DB cuyo esquema existe pero `User` está vacía toma la rama positiva, nunca llama `resolver_credenciales_iniciales()` y arranca Waitress. QA2 confirma que el test existente solo cubre `__main__`; falta test de Waitress que demuestre rechazo no-dev y dev autorizado, además de corregir el guard operativo. Consenso QA1/QA2; GitHub/etiquetas intactos.

Revisión fresca del issue (#2061, cuatro comentarios) confirma que el criterio final (#6711996661) requiere aplicar el guard en ambos entrypoints. `__main__` está cubierto parcialmente por `test_module_entrypoint_credentials.py`; `server.server()` aún omite el guard si el chequeo de conexión acepta el objeto `Result`. QA2 coincide en que una base conectada y tabla `User` vacía puede arrancar Waitress sin credenciales validadas. Sin pruebas/linters ni cambios de producto/GitHub.

### QA1 re-revisión estática — #2060 (HEAD `45e38f2b`)

**Rechazado; sin cambios en GitHub ni etiquetas.** Revisé el issue y sus nueve comentarios, en particular el criterio owner (#6711946105) y el rechazo QA3 más reciente (#7029139941). El fix vigente en `pending_approval_count()` filtra compañías y estados (`__init__.py:418-438`), por lo que corrige el conteo cross-company original, pero no cuenta la misma colección que la bandeja del usuario.

`/admin/me/pending-approvals` carga estados que empiezan con `Pending`, y `_pending_approval_info()` descarta documentos que el usuario no puede aprobar (`admin/routes.py:1887-1895`, `admin/services.py:658-668`). Para documentos normales `ApprovalEngine.can_approve()` además aplica permiso del módulo del documento, política de aprobación independiente y regla/nivel aplicable (`approval_engine.py:409-434`). Los tipos de revisión de control tienen un guard distinto, `review_pending_info()` → `review_is_allowed()` (`control_review_service.py:270-273`). En cambio, el badge solo filtra `company_id` con `authorized_company_codes()` y dos estados exactos. Un usuario con acceso a una compañía pero sin permiso/regla de aprobar una solicitud de esa misma compañía recibe un conteo mayor que su bandeja. El texto de la bandeja la describe como documentos que coinciden con límites y roles (`pending_approvals.html:17-20`).

`tests/test_approval_count_scope.py:36-155` prueba dos compañías, usuario Alpha, usuario sin compañías y administrador global, pero no fija caso discriminante de dos requests de la misma compañía con una aprobable y otra no ni compara badge con la lista. QA3 ya exige esa paridad; QA1 coincide. Añadir cobertura con los mismos tipos/estados y documentar una sola regla compartida de visibilidad para badge y bandeja, manteniendo el aislamiento por compañía. Revisión estática, sin pruebas/linters.

QA2 revisó #2060 independientemente y coincide en rechazar. Añade la asimetría opuesta: `authorized_company_codes()` se invoca sin especificar módulo, así que usa `accounting`; una solicitud aprobable de ventas/compras/caja podría no aparecer en el badge si el usuario no tiene acceso accounting, aunque `can_approve()` le autorice por el módulo del documento. Las revisiones especiales aplican su guard de snapshot/módulo (`control_review_service.py:150-165,270-273`). El contador actual puede, por tanto, tanto sobrecontar solicitudes ocultas como omitir solicitudes aprobables de módulos operativos. La prueba actual no cubre compañía+permisos de módulo/regla ni visibilidad especial. QA1/QA2 coinciden; no hubo cambios externos.

### QA1 re-revisión estática local — #1433 (HEAD `45e38f2b`)

**Rechazado; sin cambios GitHub/etiquetas.** Leí los ocho comentarios, especialmente el QA3 vigente (#7029470314). El fix `c3d268ff` compara correctamente `supplier_invoice_key` con número normalizado para filas que sí tienen clave, pero `_ensure_purchase_invoice_supplier_key()` deja con clave NULL los grupos históricos activos duplicados para revisión manual (`tests/test_purchase_invoice_supplier_key_backfill.py:4-10,67-71,97-113`). En esos grupos, `_validate_duplicate_supplier_invoice()` (`compras/services.py:2516-2551`) busca únicamente `supplier_invoice_key == supplier_invoice_no.strip()` y filtra `docstatus != 2`; por ello no encuentra las filas históricas activas cuyo key es NULL.

La restricción `uq_purchase_invoice_supplier_number` tampoco detiene una tercera factura mientras su key sea NULL antes del listener/precheck, porque la base permite múltiples NULL únicos. El alta nueva con el mismo proveedor/número puede ampliar el grupo ambiguo y no devuelve `DUPLICATE_INVOICE`. La prueba actual `test_purchase_invoice_duplicate_scope.py:107-124` cubre espacios, compañía distinta y exclusión de propia factura con clave ya poblada; el test de backfill solo comprueba que los históricos duplicados quedan NULL. Ninguna combinación los conecta ni comprueba rechazo de un tercer alta. Corregir precheck para detectar facturas activas históricas con key NULL usando el número crudo normalizado, sin reescribir evidencia, y agregar una regresión de tercera alta antes de flush que verifique error controlado y ninguna mutación. No ejecuté pruebas/linters.

QA2 revisó #1433 independientemente y confirma el rechazo. Verificó el recorrido real del backfill (`database/helpers.py:1206-1224`), la semántica SQL de la clave única nullable (`database/__init__.py:2548-2562`) y que alta y edición invocan el mismo precheck (`compras/services.py:2891,3017-3021`). Dos filas históricas activas con key NULL quedan fuera del índice; la siguiente factura comparable recibe la clave poblada y puede entrar como tercer duplicado. QA1/QA2 concuerdan; no se ejecutaron pruebas ni se tocaron GitHub/etiquetas.

### Fase 1 / #1649 — QA1/QA2 #1405 rechazan por cobertura HTTP pendiente

El código actual ya permite que `payment_entry` omita el origen de cabecera; luego exige permiso `cash/crear` sobre la compañía destino y autoriza cada línea contra el tipo/documento/compañía fuente. El servicio vuelve a validar compañía, estado, tercero y tipo de pago. Sin embargo, `tests/test_payment_target_allocation_contract.py` llama `create_target_document()` directamente; no cubre la ruta original `POST /api/document-flow/create-target`. El único test HTTP de esa ruta manda una línea malformada y solo verifica rechazo 400. QA2 confirma esta brecha independientemente. Agregar regresión HTTP positiva con origen solo en línea y controles negativos de acceso de destino y fuente; comprobar estado, persistencia y ausencia de efectos ante rechazo. El issue/etiqueta `needs-work` no se modificó; no ejecuté pruebas/linters ni cambié producto/GitHub.

### Fase 1 / #1649 — QA1/QA2 #1753 rechazan por cobertura HTTP pendiente

El GET `/buying/import-landed-cost/new?from_invoice=...` ahora carga la factura y llama `_require_purchase_document_access(invoice_origen, "consultar")` antes del render (`compras/routes.py:3552-3558`). El guard rechaza compañía no verificable y exige acceso `purchases/consultar`; el formulario expone número/proveedor solo después. QA2 confirma que el fix está presente, pero no hay prueba HTTP de esta ruta: `test_import_landed_cost_creation_event.py` solo cubre el POST como admin, y la prueba `test_payment_preload_company_scope.py` corresponde a otra pantalla. El issue permanece `needs-work` por falta de regresión con factura ajena/sin permiso más control positivo autorizado que compruebe 403 y no exposición de metadatos. No ejecuté pruebas/linters ni cambié producto/GitHub/etiquetas.

### Fase 1 / #1649 — QA1/QA2 #1971 rechazan por cobertura HTTP incompleta

No se observa bypass en las rutas inspeccionadas: entrega desde orden/nota llama `_require_sales_document_access()` en `_load_delivery_note_sources()` antes de preparar metadatos (`ventas/routes.py:208-219`); orden desde solicitud/cotización verifica ambas fuentes antes de construir `transaction_config` (`ventas/routes.py:1123-1147`); cotización desde solicitud verifica antes del contexto (`ventas/routes.py:1453-1480`); y factura desde orden/nota/factura/devolución comprueba cada origen dentro de `_sales_invoice_sources_and_type()` antes de usarlo (`ventas/services.py:2202-2227`). El guard requiere consulta sobre la compañía origen (`ventas/services.py:806`).

La prueba HTTP vigente solo cubre origen extranjero para entrega desde orden y factura desde orden (`tests/test_document_flow_read_access.py:276-298`). No protege el caso original de cotización desde solicitud, las rutas de orden y factura con sus demás tipos de origen, ni las ramas de entrega desde nota; tampoco hay controles positivos HTTP que validen precarga autorizada en estas variantes. QA2 verificó de forma independiente que no hay bypass aparente y coincide en rechazar: la prioridad es una regresión HTTP negativa y positiva para cotización desde solicitud y luego las otras combinaciones reportadas. Issue y etiqueta permanecen intactos; no ejecuté pruebas/linters ni modifiqué producto o GitHub.

### Fase 1 / #1649 — QA1/QA2 #2135 rechazan regresión incompleta en edición

El validador actual enlaza adjudicación, fuente, proveedor y cobertura de líneas; `_update_purchase_order_from_request()` lo ejecuta antes de mutar relaciones o borrar líneas (`compras/services.py:1669-1680`). QA1/QA2 no encontraron un bypass aparente en esta lógica. La brecha está en la prueba: los negativos de línea no adjudicada y cantidad acumulada se ejercitan solo en el validador (`tests/test_purchase_order_award_validation.py:252-314`), no durante una edición. La edición con cambio de proveedor solo comprueba que quede algún ítem (`:390-411`), y la edición válida verifica adjudicación/comentario pero no los valores de línea persistidos (`:433-459`). Por tanto no queda fijado que una edición con línea sustituida o sobrecantidad se rechace preservando proveedor, líneas y cantidades existentes, ni que una edición válida persista la correspondencia exacta. QA2 coincide independientemente; el último QA3 también había señalado esta brecha. Mantener `needs-work` sin transición de GitHub. No ejecuté pruebas/linters ni modifiqué código/GitHub/etiquetas.

### Fase 1 / #1649 — QA1/QA2 #2142 rechazan cobertura del filtro de período

El fix se propaga correctamente: la ruta de órdenes de compra llama `_paginate_list(..., access_modules=("purchases", "inventory"))` (`compras/routes.py:346-354`); el helper aplica el filtro de período y picker con esa misma tupla (`compras/services.py:349-364`), y recepciones usan el helper común. `_period_company_for_query()` resuelve `company` explícito y el guard de lista valida acceso combinado antes de filtrar; ante período sin compañía y varias compañías autorizadas, `require_period_company()` devuelve 400.

La regresión actual (`tests/test_s2p_purchase_order_period_scope.py`) prueba el selector unido y el 400 ambiguo con helpers directos. Pero `test_consulta_se_limita_a_la_compania_autorizada_por_inventario` solo compila `_apply_company_scope()`; no ejercita `_apply_period_scope()` ni la ruta/listado. Por ello podría romperse la aplicación del filtro de período para Inventory y seguirían pasando las pruebas. QA2 coincide, y QA3 había señalado esta brecha en #7028674698. Añadir prueba del listado de OC con acceso a beta solo por Inventory, período válido de beta y resultados que incluyan OC beta y excluyan otra compañía/período; sería útil extender el mismo contrato a recepciones, cuya invocación es independiente. Mantener `needs-work`; sin cambios GitHub/etiquetas ni ejecución de pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 aprueban localmente #1725

El formulario/servicio ahora conserva preferencias de compras al editar configuración del rol cliente; `upsert_party_company_settings()` conserva la cuenta del rol opuesto, y `_delete_removed_company_settings()` preserva el vínculo y las cuentas compartidas si el Party sigue teniendo el otro rol (`party_settings.py:399-419,423-442,536-575`). La regresión HTTP `tests/test_s2p_dual_role_supplier_invoice.py:282-379` cubre edición y retiro de fila de cliente para tercero dual, persistencia de flags y cuentas AR/AP, creación de factura de compra después y actualización de proveedor que conserva cuenta AR. QA2 revisó independientemente el escenario, integración y fixture Tier 1 SQLite/PostgreSQL; no encontró hallazgos bloqueantes. QA1/QA2 aprueban localmente. La etiqueta GitHub sigue intacta; no publiqué comentario ni ejecuté pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 #1761 rechazan por regresión CSRF ausente

Las cuatro plantillas actuales incluyen el campo `csrf_token`: cierre fiscal, real vs. presupuesto, toggle de contador externo y alta/edición de plantilla de impresión. La prueba mencionada en comentarios históricos no está en HEAD. Las pruebas HTTP de impresión usan el fixture común con `WTF_CSRF_ENABLED=False` (`tests/conftest.py:150`), y `test_logout_csrf.py` cubre otra ruta. Por tanto no prueban que el token se renderice ni que, con CSRF activado, las cuatro rutas acepten formulario válido y rechacen POST sin token. QA2 confirma independientemente y el último comentario QA ya había regresado el issue a `needs-work`. Añadir regresión HTTP con protección activada en cada formulario y ruta. Mantener la etiqueta sin cambios; no publiqué comentarios ni ejecuté pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 #1777 rechazan exposición de correos globales

La vista ahora requiere `accounting/solicitar` y limita las compañías ofrecidas a aquellas autorizadas donde `CompanyParty` del tercero está activo (`balance_confirmation_bp.py:197-223,298-329`). Sin embargo, `_party_suggested_emails()` sigue cargando todos los `Contact` asociados al Party y añade su `primary_email` global, sin alcance de compañía (`:226-236`). El esquema no vincula `PartyContact` ni `Party.primary_email` a empresa (`database/__init__.py:1160-1234`), por lo que no existe base para asegurar que esos correos pertenecen al ámbito autorizado. Además, la ruta redirige si Party no existe antes de validar compañías, pero responde 403 si sí existe sin compañía permitida (`:304-319`), permitiendo distinguir IDs a quien tenga permiso de solicitar confirmaciones. QA2 coincide y no encontró regresión del GET. El criterio de aislamiento de correos requiere una decisión/modelo de datos para contactos globales; no se infiere política. Mantener `needs-work`, sin cambios GitHub/etiquetas, sin pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 #1781 rechazan cobertura de acciones incompleta

El guard `enforce_budget_company_access()` sí mapea explícitamente POST de approve/close/import/delete/edit a `autorizar`/`cerrar`/`importar`/`eliminar`/`editar` (`contabilidad/presupuesto.py:70-86`). QA1/QA2 no encontraron defecto en ese mapeo. Pero el criterio cubre roles segregados por acción para cada endpoint. La prueba HTTP vigente de importación (`tests/test_r2r_budget_import_owner_scope.py:236-250`) usa un usuario `import=True` sin create y demuestra que alcanza el handler; no hallé pruebas equivalentes con `create=False` para approve, close, delete-line ni edit. QA2 coincide con el último hallazgo QA3 (#6886586299). Mantener `needs-work` hasta probar las ramas restantes con cliente HTTP y estado/efecto controlado. Sin cambios GitHub/etiquetas, sin ejecución de pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 #1785 rechazan falta de regresión del estado del presupuesto

`get_real_vs_budget_report()` devuelve reporte vacío si el presupuesto no existe o `status != "approved"`, antes de consultar líneas/importes (`budget_report_service.py:61-69`). No encontré prueba que invoque el servicio o endpoint Real vs Presupuesto para ese contrato. QA2 confirma independientemente: falta tanto el negativo para `draft` como el control positivo para `approved`, señalados por QA3 en #6886587668. El filtro del selector en UI no protege IDs POST manipulados, por lo que el contrato servidor necesita ambas regresiones. Mantener `needs-work`; no hubo cambios GitHub/etiquetas ni ejecución de pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 #1789 rechazan falta de regresiones del mapeo EFE

El POST actualmente exige acción `editar`, rechaza `account_ids` vacío y compara el conjunto con todas las cuentas que muestra el formulario (`contabilidad/routes.py:4616-4628`). El servicio valida que cada ID pertenezca a la compañía y solo muta mappings incluidos, preservando los omitidos; una sección vacía explícita elimina su clasificación (`reportes/cash_flow.py:192-233`). Ese borrado explícito está previsto por el contrato y no debe confundirse con payload ausente/parcial.

No hay regresiones vigentes que cubran la ruta/servicio de configuración: `test_accounting_write_actions_required.py` solicita la ruta sin compañía para una denegación genérica, y `test_r2r_cash_flow_statement.py` prueba cálculo, no el guardado. QA2 coincide con QA3 (#6886589098): fijar rechazo de lector, POST vacío/parcial, ID de cuenta ajena con conservación del estado existente y actualización válida, tanto en ruta como en persistencia del servicio según corresponda. Mantener `needs-work`; sin cambios GitHub/etiquetas ni ejecución de pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 #1797 rechazan mapeo de acción y regresiones cross-company

El defecto estructural reportado está parcialmente corregido: el mismo `enforce_close_and_recurring_company_access` que vive en el blueprint no registrado de `services.py` se importa y conecta al blueprint `contabilidad` activo (`routes.py:346-351`). Sin embargo, el guard todavía aplica acciones incorrectas: todo POST de `/period-close/monthly/<identifier>/...` exige `autorizar` (`services.py:173-178`), incluso capitalización, cuyo handler exige `editar` (`routes.py:3238-3243`), y revalorización, cuyo handler exige `crear` (`:3404-3409`). En recurrentes, cualquier POST exige `autorizar`, pero cancelación exige `anular` (`services.py:179-182`, `routes.py:3142-3149`). Puede negar a usuarios con permiso funcional correcto.

Tampoco encontré prueba que compruebe el guard del blueprint registrado ni pruebas HTTP de registros beta/ajenos para cierre, recurrentes y revalorización; los tests actuales cubren otros contratos y referencias faltantes. QA2 coincide: corregir mapeo endpoint→acción y añadir pruebas discriminantes de usuario/compañía por rutas afectadas. Mantener `needs-work`; no ejecutar pruebas/linters ni cambiar producto/GitHub/etiquetas.

### Fase 1 / #1649 — QA1/QA2 #1828 rechazan bypass admin por parámetro explícito

El listado sin parámetro sí limita Cloud a `explicit_company_grants()` mediante `_authorized_companies()` (`compras/services.py:285-300`). Pero cuando el cliente envía `?company=beta`, `_apply_company_scope()` delega en `exige_acceso_compania_cualquiera()` (`:302-309`); esa función llama a `exige_acceso_compania()`, que retorna con acceso concedido antes de revisar asignaciones si `Permisos.administrador` es verdadero (`decorators.py:109-110`). Como la clasificación admin activa esa propiedad (`auth/permisos.py:168-178`), un admin Cloud sin grant explícito puede leer documentos de beta al especificar el parámetro, contradiciendo el criterio vigente de #6712615695.

Las pruebas de admin Cloud existentes cubren vistas/lecturas de Party (`tests/test_party_read_company_scope.py:429-504`), pero no los listados documentales S2P con `?company=`; tampoco hay regresiones de este bypass para PurchaseRequest, PurchaseQuotation, SupplierQuotation o PurchaseOrder. QA2 confirmó el bypass y la brecha. Mantener `needs-work`; el scope debe validar explícitamente el grant Cloud aun para company indicada y fijar rutas afectadas con pruebas. Sin cambios de código/GitHub/etiquetas ni ejecución de pruebas/linters.

### Fase 1 / #1649 — QA1/QA2 #1833 rechazan cobertura HTTP del flujo canónico

La superficie `contabilidad/gl` está retirada: no quedan enlaces ni referencias productivas a sus rutas, plantillas o JS; el único resultado de `/accounting/gl/...` es la prueba. La ruta canónica de listado permanece (`contabilidad/routes.py:2935`), la creación requiere `crear` (`:3632`) y el posteo requiere autorización sobre la compañía (`:3671`). `tests/test_gl_legacy_removed.py:75-91` verifica 404 de ambas rutas GL y 200 de `/journal/list` y `/journal/new`.

La regresión solo usa un administrador Cloud y GETs; no demuestra aislamiento por rol/compañía, creación por POST ni posteo HTTP. Las pruebas de servicio del comprobante no atraviesan esos contratos de ruta. QA2 coincide y aclara que la nota QA3 que decía faltaban incluso 404/GET está desactualizada respecto al test actual, pero el criterio owner #6712125451 pide además acceso, listado, creación y posteo con pruebas reales. Mantener `needs-work` hasta agregar rutas HTTP con users/company scopes representativos, alta persistida y aprobación/posting. No ejecuté pruebas/linters ni modifiqué producto/GitHub/etiquetas.

### Fase 1 / #1649 — QA1/QA2 #1852 rechazan cobertura del permiso `editar`

La vista ahora elige `action = "editar"` en POST antes de llamar a `exige_acceso_compania()` (`contabilidad/routes.py:4616-4618`), lo cual corrige el bypass funcional reportado. No hay regresión específica para esa guarda. La prueba genérica `test_accounting_write_actions_required.py` usa un lector con solo `access/view`, que carece de `configurar` y se rechaza antes del handler; su caso permitido usa todas las acciones pero no tiene compañía ni llega al guard de compañía. Por eso no demuestra que un usuario con `configurar`/consulta y grant de compañía, pero sin `editar`, sea rechazado antes de mutar, ni el control positivo con `editar`.

QA2 coincide; el mismo servicio/mapeo también tiene cobertura pendiente en #1789. Añadir prueba HTTP discriminante con compañía y roles reales y comprobar que un rechazo deja el mapping intacto más el POST válido. Mantener `needs-work`; no ejecutar pruebas/linters ni cambiar producto/GitHub/etiquetas.

### Fase 1 / #1649 — QA1/QA2 #1920 rechazan excepción admin y regresiones ausentes

Los predicados compartidos `User.is_portal_customer`/`is_portal_supplier` verifican Cloud, clasificación y asociaciones `party_id`/`company` (`database/__init__.py:358-373`). Tanto el redirect post-login como la página principal los usan (`auth/helpers.py:118-123`, `app/__init__.py:41-44`). Pero `check_portal_access()` conserva un bypass separado: después de bloquear Desktop, `_is_user_admin()` permite acceso directo al portal a cualquier admin sin exigir esos predicados (`portal/__init__.py:43-56`). Login y guard no comparten íntegramente el mismo contrato; además de la clasificación `admin`, el dashboard portal omite el filtro por tercero (`:66-80`, `:189-215`). QA2 lo identifica como discrepancia funcional frente al criterio vigente de compartir la regla. No se toma una decisión de producto sobre el alcance administrativo; mantener `needs-work` bajo el criterio aprobado.

La única suite portal en tests (`test_portal_print_scope.py`) cubre impresiones/alcance de documentos, no el login ni el guard de portal. No encontré pruebas de clasificación incompatible, asociaciones ausentes, supplier y Desktop que cubran redirect y acceso directo; QA2 confirma. Añadir regresión de flujo para esos casos y resolver explícitamente el bypass admin en consonancia con el predicado compartido antes de aprobar. No ejecutar pruebas/linters ni modificar producto/GitHub/etiquetas.

### Fase 1 / #1649 — QA1/QA2 #1926 rechazan falta de regresión de permisos UOM

La implementación actual se alinea con la decisión aprobada por el responsable (#6712892017): `/inventory/uom/list` y `/inventory/uom/<id>` exigen `inventory/consultar` (`inventario/routes.py:206-218,639-651`), y el alta `/inventory/uom/new` conserva `inventory/crear` (`:612-636`). No aparece una prueba HTTP de lectura UOM que distinga usuarios con y sin `inventory/consultar`; las pruebas relacionadas cubren factores, conversiones, edición y códigos duplicados, no la autorización del listado ni del detalle. QA2 confirmó por búsqueda independiente la misma brecha. El código parece correcto, pero no hay regresión para impedir que las rutas pierdan el guard. Mantener `needs-work` hasta cubrir denegación y acceso permitido en listado y detalle, con permisos representativos. Issue/etiqueta intactos; no publiqué comentarios ni ejecuté pruebas/linters, y no modifiqué producto.

### Fase 1 / #1649 — QA1/QA2 #1998 rechazan falta de regresión HTTP de privacidad

La ruta actual requiere `accounting/solicitar` y, antes de llamar a `_party_suggested_emails()` o renderizar el formulario, filtra las compañías del usuario por permiso `accounting/crear` y por una relación `CompanyParty` activa; sin compañías elegibles responde 403 (`balance_confirmation_bp.py:198-223,298-329`). Esto parece cerrar el disclosure descrito para un tercero ajeno o sin asociación activa. Sin embargo, `tests/test_accounting_write_actions_required.py` solo llama la URL sin `party_id`; su caso lector valida el decorador genérico, no el guard de asociación, y el positivo no demuestra que contactos se rendericen solo para compañía autorizada. No hay los tres casos de regresión solicitados: usuario sin RBAC, tercero de compañía ajena/no asociado y tercero asociado a compañía propia, verificando que el rechazo no expone nombre/correos. QA2 confirma implementación aparentemente alineada y brecha de cobertura. Mantener `needs-work`; issue/etiqueta intactos, sin comentarios GitHub, sin pruebas/linters ni modificaciones de producto.

### Fase 1 / #1649 — QA1/QA2 #2018 rechazan regla fiscal global con cuenta específica

La validación de referencias existe y evita cuenta inexistente o cuenta de otra compañía cuando `company` está informado (`tax_rule_service.py:91-105`); el CRUD también maneja `TaxRuleServiceError` y rollback, y el borrado convierte `IntegrityError` en respuesta controlada (`admin/routes.py:637-655,845-876`). Sin embargo, el chequeo de ownership está dentro de `if company`: un payload de regla global (`company=None`) con `account_id` de una entidad concreta pasa. `build_tax_rule_contexts(company=...)` incluye reglas globales (`tax_rule_service.py:64-80`), y el consumidor de retención configurada también admite regla global (`accounting_engine/document_builders.py:980-994`); `_append_tax_entries()` valida existencia de cuenta, no ownership de la compañía que contabiliza (`contabilidad/posting_service.py:1182`). Esto puede cruzar cuentas entre compañías al generar/postear impuestos. No encontré decisión aprobada que defina una cuenta específica en regla global como segura; el comentario vigente #6887062618 lo reporta expresamente como brecha. La cobertura presente de `test_admin_tax_rule_form.py` rechaza cuenta inexistente y cubre dominios/cálculo, pero no regla global con cuenta específica, referencias de compañía/moneda inválidas, consumo predeterminado cross-company ni borrado de regla referenciada. QA2 confirma el borde productivo y las pruebas ausentes. Mantener `needs-work`; corregir/definir el contrato de regla global con cuenta y cubrir referencia, consumo y borrado. Etiquetas y GitHub intactos; no ejecuté pruebas/linters ni modifiqué producto.

### Fase 1 / #1649 — QA1/QA2 #2059 rechazan por el residual compartido con #2060

Los comentarios de #2059 lo declaran duplicado de #2060 y remiten allí al fix y criterio único; leí también los comentarios completos de #2060. La insignia ahora limita el agregado a `authorized_company_codes()` y `tests/test_approval_count_scope.py` prueba compañía Alpha, sin compañías y administrador global. Pero el comentario QA3 más reciente (#7029139941) identifica brecha aún vigente: el listado `/admin/me/pending-approvals` filtra por `ApprovalEngine.can_approve(document, current_user)` y rechaza documentos inexistentes/no aprobables (`admin/services.py:658`), mientras el contador solo mira estado y compañía (`__init__.py:418-435`). La prueba actual inserta solicitudes sin documentos existentes y llama al contador directamente, por lo que no compara con las solicitudes que el usuario realmente ve. QA2 verifica igual de forma independiente. Mantener `needs-work` en la unidad duplicada; resolver el criterio y prueba compartidos en #2060, con solicitudes reales visibles y no visibles dentro de la misma compañía. No cambiar etiquetas ni comentar en GitHub; no ejecuté pruebas/linters ni modifiqué código.

### #2092 — fix local implementado; QA1/QA2 aprobados

El contador del badge ahora falla cerrado si el documento fuente no tiene `company`/`entity`, o si esa compañía no coincide con `DocumentTask.company`. La condición queda alineada con `_task_document_visible()` de la bandeja; la consulta conserva el filtro por usuario, estado, compañía autorizada y permiso de módulo. La prueba nueva crea un `DeliveryNote` válido pero sin compañía con tarea asociada a Alpha autorizada: la bandeja no lo muestra y el conteo queda en 1 por la tarea Alpha bien formada. QA1 y QA2 revisaron el diff local independientemente y aprobaron; QA2 observó que se valida la función del badge directamente, lo que cubre la llamada de la plantilla. Prueba dirigida: `8 passed`. Black, Ruff, Flake8, pydocstyle y complexipy pasaron. Mypy no pudo iniciar porque falta `pathspec.patterns.gitignore`; Pylint arroja advertencias previas del módulo, sin diagnóstico sobre las líneas editadas. No se hizo commit, push, cambio de etiquetas o comentario en GitHub.

### #1926 — regresión de permisos UOM agregada; QA1/QA2 aprobados

Sin modificar producto, agregué `tests/test_inventory_uom_read_permissions.py`: persiste una UOM global, un rol con acceso a inventory sin `view` y otro con consulta; verifica HTTP 403 para ambos endpoints de lectura al usuario no autorizado y HTTP 200 con el código/nombre para el lector autorizado. Esto cubre el vacío observado sin cambiar la decisión confirmada de mantener `inventory/crear` en el alta. QA1/QA2 aprueban estáticamente. Suite dirigida: `3 passed`; Black/Ruff/Flake8/pydocstyle pasaron. Nota de alcance no bloqueante de QA2: opciones UOM en formularios de alta/edición de artículo son datos necesarios en rutas de escritura y permanecen bajo su acción de escritura. No cambio etiquetas ni GitHub.

### #2060/#2059 — predicado de badge limitado por grants y compartido con bandeja; QA1/QA2 aprobados

El servicio `_pending_approval_company_codes()` primero limita candidatos a `UserCompanyAccess` unido a entidades habilitadas para usuarios normales; admin usa entidades habilitadas, acorde al bypass administrativo aprobado. No depende del módulo Accounting: la prueba incluye aprobador con solo Ventas y grant Beta, que conserva la solicitud visible de Beta. El resultado posterior se calcula con `_pending_approval_info()` compartido entre el badge y `/me/pending-approvals`, así que mantiene `ApprovalEngine.can_approve()` (módulo, compañía, independencia, reglas y monto) y `review_is_allowed()` para revisiones especiales. Las pruebas usan documentos reales y cubren Alpha dentro/fuera de rango, Beta ajena, revisión de configuración permitida/denegada, usuario sin grants y admin; `4 passed` en `test_approval_count_scope.py`. QA1/QA2 aprueban tras discutir rendimiento: el prefilter evita recorrer tenants ajenos para usuarios normales; el riesgo O(N) dentro del alcance vigente y en usuarios admin, cuyo alcance es global, queda como nota no bloqueante sin límite/paginación definida por el producto. Suite combinada con #2092: `12 passed`. Black/Ruff/Flake8/pydocstyle/complexipy pasaron; mypy no inicia por `pathspec.patterns.gitignore` ausente; Pylint conserva únicamente observaciones preexistentes. Sin commit, push, comentarios o cambios de etiqueta.
