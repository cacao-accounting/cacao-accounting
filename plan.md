# Plan accionable de estabilización

**Repositorio:** [cacao-accounting/cacao-accounting](https://github.com/cacao-accounting/cacao-accounting)
**Tracker maestro:** [#2248](https://github.com/cacao-accounting/cacao-accounting/issues/2248)
**Rama de trabajo:** `estabilizacion`, con seguimiento de la rama remota `origin/estabilizacion`.
**Corte de estado:** 15 de noviembre de 2026. Issues y subissues contrastados en GitHub.

## Alcance de ejecución

- El plan contiene la cola de issues abiertos con trabajo accionable. Los issues cerrados, trackers y agrupadores se usan como referencias de coordinación; no se asignan como tareas de implementación.
- `needs-work` significa implementación pendiente; `fix-proposed` significa que QA1 aprobó y falta la revisión independiente de QA2; `fix-confirmed` significa que QA2 aprobó y falta la aceptación final de QA3 expresamente autorizado o del administrador. Si una revisión encuentra una brecha, el issue vuelve a `needs-work` y reinicia el ciclo QA1 → QA2.
- Antes de intervenir y de entregar un lote, leer `feedback.md` y `review.md` si existen. Resolver las observaciones aplicables de QA1 y QA2 como parte del criterio de salida.
- Antes de atender un issue, leer su descripción y **todos sus comentarios**, con paginación completa, incluidos los del paraguas cuando establezcan el contrato compartido. Los comentarios son la bitácora de desarrollo: contienen decisiones, reproducciones, cambios existentes, rechazos de QA y limitaciones que pueden actualizar o sustituir el diagnóstico inicial. A estas alturas aportan más contexto de ejecución que la descripción original. Identificar las decisiones vigentes y los hallazgos aún aplicables antes de tocar código; no volver a decidir reglas ya aprobadas ni implementar a partir del título o de la descripción aislados. Si hay una contradicción real sin resolución posterior, presentar el caso concreto al responsable.
- Los cinco issues de interfaz que superan el límite de hijos de #1711 se incluyen por referencia: #2162, #2165, #2193, #2199 y #2201.

## Registro de avance

**Actualizado:** 19 de noviembre de 2026 (rama `estabilizacion`, sin push). Este registro documenta
implementación, evidencia local y commits; **no cambia etiquetas ni estados de GitHub**, que corresponden a
QA1, QA2, QA3 o al administrador.

| Lote / issue(s) | Estado local | Commit(s) | Evidencia |
|---|---|---|---|
| #1546 catálogos contables por compañía (proyectos, cuentas, centros de costo, unidades; ULID en cuentas/CC/proyectos/unidades) | Implementado con regresión | `1698c612`, `847617de`, `6a04dbdf`, `06058728`, `f4efb796`, `4a808042` | `tests/test_accounting_catalog_company_scope.py`, `tests/test_r2r_cost_center_hierarchy.py`, `tests/test_accounting_unit_detail_404.py` |
| #1541 detalle de artículo; #1418/#1542 edición multiempresa; #1181 proveedor predeterminado | Implementado con regresión | `b3e98f36`, `42786767`, `771d4e15` | `tests/test_item_detail_company_scope.py`, `tests/test_item_edit_company_scope.py` |
| #1173/#1416/#1176/#1543 listado y formulario de movimientos; #1175/#1540/#1417 lotes (cobertura) | Implementado con regresión | `04b2e32b`, `b4451169` | `tests/test_inventory_stock_entry_company_scope.py`, `tests/test_inventory_batch_company_scope.py` |
| #1526/#1527 bancos: permiso de alta y alcance por cuenta | Implementado con regresión | `ea3d7dfc` | `tests/test_cash_bank_company_scope.py` |
| #1320 listado de movimientos bancarios exige consulta de Caja | Implementado con regresión | `74db370b` | `tests/test_cash_bank_company_scope.py` |
| #1322 gastos de reposición de caja chica por alcance | Implementado con regresión | `d1979066` | `tests/test_petty_cash_fund_scope.py` |
| #1329 revocación de tareas y badge al perder compañía | Implementado con regresión | `ecac5587` | `tests/test_collaboration_task_company_revocation.py` |
| #1595 tareas ocultas al perder el permiso del documento | Implementado con regresión | `8badc192` | `tests/test_collaboration_task_company_revocation.py` |
| #1411 listas relacionadas con módulos alternativos | Implementado con regresión | `1a58f880` (scoping y filtro) / `4e18de70` | `tests/test_s2p_purchase_receipt_source_scope.py` |
| #1407 cada nodo del árbol documental por módulo | Implementado con regresión | `a43e6117` | `tests/test_document_tree_node_permissions.py` |
| #1410 líneas de entrega consultables desde Ventas | Implementado con regresión | `54bb39a1` | `tests/test_document_flow_delivery_note_lines.py` |
| #1388 relaciones O2C entre clientes distintos | Implementado con regresión | `872008d3` | `tests/test_o2c_line_relation_party_scope.py` |
| #1399 tercero seleccionado en importación de conciliaciones | Implementado con regresión | `1afff009` | `tests/test_payment_reconciliation_import_party_scope.py` |
| #1169 listado de cierres fiscales por compañía | Implementado con regresión | `a87db51f` | `tests/test_fiscal_year_closing_company_scope.py` |
| #1261 reglas de matching acotadas a su cuenta | Implementado con regresión | `f79c5da7` | `tests/test_bank_matching_rule_account_scope.py` |
| #1120 reporte de lotes aislado por compañía | Implementado con regresión | `b0d9003a` + `f995e0e0` | `tests/test_report_batch_company_evidence.py` |
| #1576 validar_solicitud en permisos calculados | Implementado con regresión | `353bee41` | `tests/test_permissions_validate_request.py` |
| #1515 fuentes documentales restringidas al módulo origen | Implementado con regresión | `9567dcdf` (prueba) | `tests/test_document_flow_read_access.py` |
| #1640 rol de ventas desactivado en edición de precios | Implementado con regresión | `13dddd6c` | `tests/test_sales_price_editor_active_role.py` |
| #1602 credenciales iniciales en el entrypoint del módulo | Implementado con regresión | `3821674c` | `tests/test_module_entrypoint_credentials.py` |
| #1130 libro de KPI validado contra su compañía | Implementado con regresión | `c4b36226` | `tests/test_kpi_snapshot_ledger_scope.py` |
| #1511 precargado de pagos acotado por compañía | Implementado con regresión | `147b367d` (prueba) | `tests/test_payment_preload_company_scope.py` |
| #1104 permiso de Caja en candidatos de conciliación | Implementado con regresión | `4d94544b` | `tests/test_payment_reconciliation_candidates_scope.py` |
| #1558 períodos de la portada acotados por compañía | Implementado con regresión | `26ab8aaf` (prueba) | `tests/test_home_company_periods_scope.py` |
| #2011 rol de ventas vigente en listas de precios | Implementado con regresión | `4b25e21f` | `tests/test_price_list_revoked_role.py` |
| #1433 factura duplicada validada con clave normalizada | Implementado con regresión | `c3d268ff` (fix/pruebas) | `tests/test_purchase_invoice_duplicate_scope.py` |
| QA2: nodos `journal_entry`, ledger del KPI y compañía de cuenta en matching | Implementado con regresión | `79e40e5f`, `5a2594b9`, `2ee07d67` | `tests/test_document_tree_node_permissions.py`, `tests/test_kpi_snapshot_ledger_scope.py`, `tests/test_bank_matching_rule_account_scope.py` |
| #1254 pendientes de compras ocultos en banca | Implementado con regresión | `274c1869` | `tests/test_query_tools_banking_purchase_scope.py` |
| #1354/#1355/#1110 revocación de credenciales y confirmaciones vencidas | Implementado con regresión | `de6f005c`, `6ebf42a5`, `9032d7a4` | `tests/test_token_requerido.py`, `tests/test_password_reset_revokes_sessions.py`, `tests/test_balance_confirmation_delivery_failures.py` |
| #1467 propiedad al cambiar estado de tareas | Implementado con regresión | `5848ee8e` (prueba) | `tests/test_task_status_authorization.py` |
| #1253 lotes visibles solo con evidencia de la compañía | Implementado con regresión | `b0d9003a`, `f995e0e0` | `tests/test_report_batch_company_evidence.py` |
| #997 alias fiscales de cobro/pago con acceso a compañía | Implementado con regresión | `43108a06` | `tests/test_fiscal_preview_company_scope.py` |
| #998 alias documentales con permiso y subtipo validados | Implementado con regresión | `4bc2dc7e` | `tests/test_document_alias_subtype_access.py` |
| #1357/#1283 retiro de código sin consumidores | Verificado por inspección y suite relacionada | `a93657fa`, `d1649c9a` | grep sin referencias; 41 passed |
| #1488 lote de importación ligado a su presupuesto | Implementado con regresión | `76d28dc8` | `tests/test_r2r_budget_import_owner_scope.py` |
| #1019 cierre de saldo ligado al documento autorizado | Implementado con regresión | `38fd869f` | `tests/test_document_flow_close_line_scope.py` |
| #911 compañía obligatoria en Cloud sin fallback | Implementado con regresión | `da5cb0c4` | `tests/test_report_company_required.py` |
| #1562 impresión de portal acotada a la compañía del usuario | Implementado con regresión | `5fbd7027` | `tests/test_portal_print_scope.py` |
| #1641 vigencia del rol admin en /info | Implementado con regresión | `62e6c02c` | `tests/test_dev_info_admin_role.py` |
| #1695 secretos de autenticación con HMAC y sin texto plano | Implementado con regresión | `e162b05c` | `tests/test_auth_secret_storage.py` |
| #1696 consumo atómico del OTP en concurrencia | Implementado con regresión | `474684ec` | `tests/test_otp_atomic_verification.py` |
| #2013 redondeo del lockout sin minuto extra | Implementado con regresión | `e9b32f49` | `tests/test_session_security_lockout_minutes.py` |
| #2060 insignia de aprobaciones acotada por compañía | Implementado con regresión | `29fe2836` | `tests/test_approval_count_scope.py` |
| #1466 cierre de flujo confirmado antes de responder | Implementado con regresión | `4078e439` | `tests/test_document_flow_close_persistence.py` |
| #1000 consumo atómico del OTP (coordinado con #1696) | Verificado con regresión concurrente | `474684ec` | `tests/test_otp_atomic_verification.py` |
| #1076 replay de idempotencia ligado a su factura | Implementado con regresión | `7e06776a` | `tests/test_purchase_reconciliation_idempotency_scope.py` |
| #925 cancelación monotónica del ledger | Implementado con regresión | `4af51ebf` | `tests/test_ledger_cancellation_monotonic.py` |
| #1002 inmutabilidad de la evidencia de auditoría en Desktop | Implementado con regresión | `39113652` | `tests/test_structural_integrity_guards.py` |
| #1294 retiro de la mutación de contador externo sin auditoría | Verificado por inspección | `2d9d8848` | grep sin referencias |
| #1669 claim atómico de la recuperación de importaciones | Implementado con regresión | `ba0e0252` | `tests/test_import_recovery_atomic_claim.py` |
| #1144 claves repetidas rechazadas en el plan AR/AP | Implementado con regresión | `0e3f790b` | `tests/test_arap_allocation_idempotency.py` |
| #950 rechazo de números no finitos en importaciones | Implementado con regresión | `135b3b5e` | `tests/test_import_non_finite_validation.py` |
| #1007/#1010 rechazo de valores fiscales no finitos | Implementado con regresión | `481470f7` | `tests/test_fiscal_non_finite_validation.py`, `tests/test_admin_tax_rule_form.py` |
| #1021/#1697 setup único y claves de configuración únicas | Implementado con regresión | `03dfc484` | `tests/test_setup_finalize_once.py`, `tests/test_config_key_uniqueness.py` |
| #1601 acciones de escritura en rutas de Contabilidad | Implementado con regresión | `6845ff63`, `719b89fb` | `tests/test_accounting_write_actions_required.py` |
| #1031 lote corrupto y recuperación con started_at nulo | Implementado con regresión | `4ac988a1` | `tests/test_import_corrupt_reader_recovery.py` |
| QA2 B-1: guards únicos instalados en bases existentes | Implementado con regresión | `43db7563` | `tests/test_schema_guards_existing_databases.py` |
| #1065 rechazo de archivos de importación sin filas | Implementado con regresión | `88964495` | `tests/test_import_empty_file_rejected.py` |
| #1033 celdas vacías normalizadas en extractos y pronósticos | Implementado con regresión | `0baa66b1` | `tests/test_import_empty_cells_normalized.py` |
| #1049 importación bloqueada en pronósticos no borrador | Implementado con regresión | `903cdf8b` | `tests/test_cash_forecast_import_status.py` |
| #1050 importación con montos positivos en pronósticos | Implementado con regresión | `63934c23` | `tests/test_cash_forecast_import_amount.py` |
| #1046 retiro del importador bancario sin ruta | Verificado por inspección | `a0d0f698` | grep sin referencias; suite de importaciones |
| #1052 campos requeridos solo con espacios rechazados | Implementado con regresión | `f24b6b6a` | `tests/test_import_required_whitespace.py` |
| #1055 fechas de Excel normalizadas antes de validar | Implementado con regresión | `70095718` | `tests/test_import_date_normalization.py` |
| #2252/#2253 ACL documental por módulo en query tools | Implementado con regresión y familias reales en `91247b48` | `9f9ad0f9`, `91247b48` | `tests/test_query_tools_document_acl.py` |
| #1051 identidad fiscal global normalizada y única | Implementado con regresión | `b4aac8b5` | `tests/test_party_tax_id_uniqueness.py` |
| #1048 grupo y clasificación en importación de terceros | Implementado con regresión | `acafcce7` | `tests/test_party_import_group_classification.py` |
| #2254/#2255 subtipo lógico en creación, listas y colaboración | Implementado con regresión | `de32b583` | `tests/test_document_subtype_creation_and_lists.py` |
| #1061 serial de artículo separado de la serie de numeración | Implementado con regresión | `d807ed6f` | `tests/test_import_template_serial_column.py` |
| #1064 tarifas negativas rechazadas en prevalidación | Implementado con regresión | `8fbe9f1d` | `tests/test_import_negative_rates.py` |
| Retornos QA2: ledger Core, tareas sin compañía, módulo activo y replay | Implementado con regresión | `c6eff9bf`, `3201a6a3`, `232d26c2`, `44f91ef2`, `e07b4fef` | `tests/test_ledger_cancellation_monotonic.py`, `tests/test_collaboration_task_company_revocation.py`, `tests/test_query_tools_document_acl.py`, `tests/test_party_tax_id_uniqueness.py`, `tests/test_purchase_reconciliation_idempotency_scope.py` |
| #1682/#2006/#1299 roles únicos, reemplazo serializado y preferencias inertes retiradas | Implementado con regresión | `8c4fdec4` | `tests/test_admin_user_roles_integrity.py`, `tests/test_company_party_preferences_cleanup.py` |
| QA2 B4/B8/B11/B14: 404 homogéneo, default fail-closed, subtipo en árbol y política fiscal completa | Implementado con regresión | `eaf2efdc`, `eaaf0daf`, `e257f00a`, `bf8615d3` | `tests/test_accounting_catalog_missing_404.py`, `tests/test_query_tools_banking_purchase_scope.py`, `tests/test_document_tree_subtype_scope.py`, `tests/test_fiscal_preview_company_scope.py` |
| #1572 filtros de tareas no amplían el alcance tras revocar | Implementado con regresión | `584253c4` | `tests/test_collaboration_task_company_revocation.py` |
| #1332 alta de recepción y líneas con permiso de Inventario | Implementado con regresión | `ba3a7f08` | `tests/test_s2p_purchase_receipt_source_scope.py` |
| #1524/#1525 terceros: permisos y alcance de listados/escrituras | Implementado con regresión | `1be22360` | `tests/test_party_management_company_scope.py` |
| #1282 contactos, direcciones y roles cruzados de terceros | Implementado con regresión | `ff54d165` | `tests/test_party_management_company_scope.py` |
| #1284 adjuntos de terceros por activación y permiso | Implementado con regresión | `9cd29cc2` | `tests/test_party_attachment_company_scope.py` |
| #1286 seguimiento de autorización de terceros (política común) | Coordinación cubierta con regresión | `f0ec7506` | `tests/test_party_read_company_scope.py`, `tests/test_party_management_company_scope.py` |
| #1280 configuración de terceros por compañía | Implementado con regresión | `039e582a` | `tests/test_party_management_company_scope.py` |
| #1590 reporte de lotes con evidencia de compañía | Implementado con regresión | `b0d9003a` | `tests/test_report_batch_company_evidence.py` |
| #1600/#1601 dashboard y permisos de acción contable | Implementado con regresión | `19610192` | `tests/test_dashboard_consult_permission.py`, `tests/test_accounting_action_permission.py` |
| #1301 imágenes de artículos | Implementado con regresión | `8fe99bdc` | `tests/test_item_image_permission.py` |
| #1338 compañías deshabilitadas en query tools | Implementado con regresión | `cbac6457` | `tests/test_query_tools_company_enabled.py` |
| #1327 permiso de módulo en catálogos del selector | Implementado con regresión | `dbaede68` | `tests/test_search_select_module_permission.py` |
| #2198 filtro `company` en el selector de compañías | Implementado con regresión | `0759a412` | `tests/test_search_select_company_filter.py` |
| #2110 resolución de período por unión de módulos | Implementado con contrato y regresión | `5053c95e` | `tests/test_delivery_note_period_picker_scope.py` |
| #1598 destinatarios de tareas por compañía/módulo | Implementado con regresión | `636a37b8` | `tests/test_collaboration_task_recipients_scope.py` |
| #1321 catálogo de usuarios por compañía | Implementado con regresión | `b649bbdf` | `tests/test_search_select_user_company_scope.py` |
| Aislamiento de pruebas (app context por prueba) | Implementado | `f5be9f90` | `tests/conftest.py`; suite completa estable |
| Rondas QA1: guardas de caja/inventario, ULID de compañía, filtro de usuarios, helper compartido y smoke Desktop | Implementado con regresión | `40a5579d`, `6e15ff8e`, `40a5579d`, `1a58f880`, `04cf0051`, `ded995a4` | `tests/test_cash_bank_company_scope.py`, `tests/test_inventory_stock_entry_company_scope.py`, `tests/test_search_select_*.py`, `tests/test_desktop_smoke_company_scope_routes.py` |
| QA2 P6: consumo concurrente de una línea documental serializado por origen y familia de destino | Implementado con regresión | `f4f2c7cd` | `tests/test_document_relation_concurrency.py`; tabla `document_flow_lock` creada en bases existentes |
| QA2 P7: `matched_qty` alineado con las asignaciones persistidas en 2-way/3-way | Implementado con regresión | `0082aa67` | `tests/test_purchase_reconciliation_matched_qty.py` |
| #1355 P3/P4: columna `auth_version` en bases existentes y revocación al cambiar clave desde administración | Implementado con regresión | `0489679e`, `5faa5547` | `tests/test_user_auth_version_schema.py`, `tests/test_admin_password_revokes_credentials.py`; `ALTER TABLE` cita `user` por dialecto |
| Observaciones QA2 N1/N3/N5/N6/N7/N8/N9/N13/N14/N20/N22 | Implementado con regresión | `4f564721`, `a62cd7bf`, `62835fd3`, `7672d253`, `d5905938`, `b3c6aacf`, `ec9cefba`, `c6b848a7`, `386c54cf`, `f3144011` | `tests/test_search_select_batch_company_scope.py`, `tests/test_collaboration_task_company_revocation.py`, `tests/test_o2c_line_relation_party_scope.py`, `tests/test_purchase_invoice_supplier_key_backfill.py`, `tests/test_document_flow_read_access.py`, `tests/test_document_type_legacy_rows.py`, `tests/test_import_recovery_atomic_claim.py` |
| QA2 N4: traducción de las cadenas nuevas y del mensaje de fecha del adaptador | Implementado con regresión | `fd0ab982` | `messages.po`/`messages.mo` compilados; `tests/test_import_date_normalization.py` |
| #2186 intentos de verificación externa reclamados de forma atómica | Implementado con regresión | `d106ed59` | `tests/test_balance_confirmation_attempts.py`; 10 reclamos concurrentes, solo 5 turnos |
| #2161 importes negativos rechazados en plantillas recurrentes | Implementado con regresión | `b7a06828` | `tests/test_recurring_template_negative_amounts.py` |
| #2153 cierre de sesión POST-only con CSRF | Verificado con regresión | `c3a6bdab`, `f64393ce` | `tests/test_logout_csrf.py`; GET 405, POST sin token 400, POST con token limpia sesión |
| #2171 líneas malformadas en `create-target` responden 400 | Implementado con regresión | `3ed9fd5b` | `tests/test_document_flow_read_access.py::test_create_target_rejects_malformed_lines` |
| #2173 conflicto concurrente al crear lotes | Implementado con regresión | `6a3a673e` | `tests/test_inventory_batch_creation_race.py` |
| #2181 numeración de pagos respeta la configuración por cuenta con campos vacíos | Implementado con regresión | `e7f895c2` | `tests/test_payment_numbering_config_empty_fields.py` |
| #2174 cuentas de bodega imputables | Verificado con regresión | `7bce4dd2` | `tests/test_warehouse_inventory_account_validation.py` |
| #2180 cuentas GL imputables en pagos y notas bancarias | Verificado con regresión | `de37f15f` | `tests/test_payment_gl_account_validation.py` |
| #2188 jerarquías concurrentes; #2161/N17 plantillas recurrentes negativas y numéricas | Implementado con regresión | `239c6e6d`, `1401aad7` | `tests/test_r2r_unit_hierarchy_concurrency.py` (PostgreSQL/MySQL), `tests/test_recurring_template_negative_amounts.py` |
| #2180 R1 cuenta por defecto imputable; #2181/N25 numeración de pagos; #1076/N26 clave cancelada | Implementado con regresión | `79ab88a8` | `tests/test_bank_note_gl_account_validation.py`, `tests/test_payment_numbering_config_empty_fields.py`, `tests/test_purchase_reconciliation_idempotency_scope.py` |
| i18n del adaptador transaccional; N24/N15/N18/N19 | Implementado con regresión | `9b6314b3` | `tests/test_import_*.py`, `tests/test_search_select_module_permission.py` |
| #2197 precisión de existencias en el dashboard | Implementado con regresión | `2ad71bda` | `cacao_accounting/static/test/dashboard.test.js`; suite JS 103 passing |
| N2/N11 badge de tareas por lote documental y alcance de destinatarios documentado | Implementado con regresión | `516049d2` | `tests/test_collaboration_task_company_revocation.py` |
| N24a/N24b defaults no escalares y orden de bloqueo documental | Implementado con regresión | `a9872ade` | `tests/test_document_type_legacy_rows.py`, `tests/test_document_relation_concurrency.py` |
| N12/N16/N21 fixture aislado, evidencia con `is_cancelled` y grupo vacío de centros de costo | Implementado con regresión | `63b58c7f` | `tests/test_delivery_note_period_picker_scope.py`, `tests/test_ledger_cancellation_monotonic.py`, `tests/test_r2r_cost_center_hierarchy.py` |
| N4 catálogo i18n regenerado, sin fuzzy ni msgstr vacíos | Implementado con regresión | `8df2209a` | `messages.po`/`messages.mo`; 25 cadenas nuevas y 75 fuzzy corregidas |
| #2172 importación bancaria concurrente sin duplicados | Implementado con regresión | `365f92ab` | `tests/test_bank_statement_import_concurrency.py` (PostgreSQL); lock por cuenta y detección bajo el mismo turno |
| #2200 precisión configurable de importes en servidor y formulario | Implementado con regresión | `6e377747` | `tests/test_currency_precision_formatting.py`, `transaction-form.test.js`; mapa de precisión por request y moneda transaccional |
| #2196 niveles expandidos del árbol financiero | Verificado con regresión | `ef321bb4` | `cacao_accounting/static/test/financial-report-tree.test.js`; tres niveles y estado de cada control |
| #2145/#2157/#2199 breadcrumb localizado, frecuencia traducida y enlace de chat | Implementado con regresión | `01b9b237` | `tests/test_ui_navigation_labels.py`, `tests/test_recurring_template_list_render.py`; lista y detalle muestran Mensual/Semanal/Diario |
| #2203/#2204 retiro de `transaction_form_js` y macros con consumidor | Implementado con regresión | `752486f1` | `tests/test_transaction_form_macros_consumers.py`; el resto de macros conserva consumidores reales |
| #2151 cierre fiscal con clasificaciones de catálogo en mayúscula | Implementado con regresión | `09b4b158` | `tests/test_fiscal_year_closing_classification_case.py`; `Income`, `Expense`, `Cost` y minúsculas |
| #2144 enlace de tipos de proveedor alineado con administración global | Implementado con regresión | `51f48cc1` | `tests/test_purchases_supplier_group_link.py`; usuario con `purchases.configurar` sin acceso admin |
| #2154 etiqueta del colapso de auditoría tras el toggle | Verificado con regresión | `caa97a12` | `tests/test_audit_timeline_collapse.py`; eventos `shown`/`hidden`, sin `onclick` inline |
| #2152 distinción alta/edición de series de numeración | Implementado con regresión | `8439df1c` | `tests/test_naming_series_edit_labels.py`; breadcrumb, encabezado y botón |
| #2149 fachada de contabilidad con `log_submit` y `__all__` | Implementado con regresión | `c4e77b56` | `tests/test_contabilidad_facade_compat.py`; import nombrado y wildcard |
| #2148 fuentes alineadas en devoluciones de recepción | Implementado con regresión | `df8fb6dd` | `tests/test_s2p_purchase_receipt_source_scope.py`; combinación incompatible 400 y fuente única al coincidir |
| #2143 snapshot de auditoría con totales y evidencia fiscal | Implementado con regresión | `f6fd5490` | `tests/test_purchase_audit_snapshot.py`; resumen y líneas fiscales antes/después |
| #2142 alcance combinado Compras/Inventario en período de OC | Verificado con regresión | `b7d4cc1d` | `tests/test_s2p_purchase_order_period_scope.py`; unión del selector, rango ambiguo 400 y consulta solo Beta |
| Limpieza de la serie creada por #2152 | Implementado con regresión | `d3af2aa2` | `tests/test_naming_series_edit_labels.py`; elimina la serie al terminar |

**Última suite completa:** Cloud **1061 passed, 96 skipped**; Desktop
(`CACAO_ACCOUNTING_DESKTOP=True`) **1055 passed, 102 skipped**; 0 fallos (HEAD `b7d4cc1d`).
La primera pasada Desktop tuvo fallos intermitentes en `test_sale_item_eligibility.py`
por estado de series; el archivo pasó aislado y la repetición completa quedó en verde.
La suite JavaScript quedó en 105 passing.

**Matriz de motores ejecutada localmente (HEAD `1401aad7`):**

- SQLite con `-m database --full --slow=True`: **84 passed, 7 skipped, 1060 deselected**.
- PostgreSQL + pg8000 sobre base temporal dedicada: **81 passed, 10 skipped, 1060 deselected**.
- PostgreSQL + psycopg2 sobre base temporal recreada: **81 passed, 10 skipped, 1060 deselected**.
- MySQL 8.0 + pymysql sobre base recreada: **79 passed, 12 skipped, 1060 deselected**.
  La primera ejecución detectó que #2188 seguía leyendo el snapshot previo bajo
  `REPEATABLE READ`; corregido en `1401aad7` y repetido en verde.
- Redis 7.2 + PostgreSQL, pruebas `-m cache`: **1 passed, 1150 deselected**.

La matriz local quedó completa. CI sigue siendo responsable de repetirla con las
versiones de Python y los servicios del workflow, y de las ramas de caché adicionales.
**Leyenda de estado:** ✅ implementado con regresión y confirmado por QA2; 🧪 implementado
localmente, GitHub `fix-proposed` (QA2 pendiente); ⚠️ implementado localmente pero GitHub
`needs-work` (reabierto o pendiente de revisión). El estado de GitHub es la fuente para el cierre.
Rondas ejecutadas tras el umbral de 50 commits desde `ded995a4`, que cubren #1254,
#1354/#1355/#1110, #1467, #1253, #997, #998, #1357/#1283, #1488, #1019, #911,
#1562, #1641, #1695, #1696, #2013, #2060, #1000, #1466, #1076, #925, #1002, #1294,
#1669, #1144, #950, #1601, #1778, #1031, #1065, #1033, #1049, #1050, #1052, #1055, #1061, #1064, #1048, #1046, #1021, #1697, #1682/#2006, #1299, #2252/#2253, #2254/#2255, #925, #1076 y los seguimientos QA2 B4/B8/B11/B14.
Black en verde en `cacao_accounting/` (alcance del workflow de lint); 4 archivos de prueba preexistentes
de `8f341b3e` requieren reformato de black fuera de ese alcance. Ruff, flake8, mypy y Bandit sin hallazgos bloqueantes. Complexipy reporta 2 funciones preexistentes > 20 (`_validate_manual_reversal_ledgers`, `_render_stock_reconciliation_edit_form`), ajenas a los cambios de Fase 1.
Pylint E/F: 35 avisos preexistentes fuera de los archivos modificados.
Ronda QA2: A1–A3, B1–B4, B8, B11 y B14 resueltos; B9 (backfill de clave heredada), B10 (nombre del guard) y B12 (filas legacy sin subtipo) quedaron resueltos en esta ronda. B5 (N+1 de destinatarios), B7 (fixture de entregas) y B15–B17 siguen como deuda no bloqueante.
La próxima ronda completa corresponde al siguiente umbral de 50 commits o antes de un push.
Black, ruff, flake8, pydocstyle, mypy y complexipy ≤ 20 aplicados a los archivos tocados.

**Controles pendientes:**

- La matriz local SQLite, PostgreSQL (pg8000/psycopg2), MySQL 8 y Redis 7 quedó ejecutada.
  CI debe repetirla con las versiones de Python y los servicios del workflow antes de un push;
  no se declara una ronda remota en verde.
- Los issues listados siguen OPEN/`needs-work` hasta que QA1 → QA2 revisen y el administrador o QA3 acepten el
  cierre. Este registro no sustituye esa revisión.

## Core funcional esperado

El core implementa los procesos empresariales estándar O2C, S2P, R2R, I2F y CTM de punta a punta, con comportamiento robusto, predecible, comprensible y auditable. Se espera que ventas y compras conserven sus documentos y relaciones de origen, que cobros y pagos apliquen y restituyan saldos por documento correctamente, que inventario mantenga cantidades y valoración por artículo, bodega y UOM —incluidos lote y serie cuando correspondan—, y que caja, bancos y conciliaciones reflejen los mismos hechos económicos que GL. El ledger financiero es la fuente única de verdad; AR/AP e inventario son extensiones reconciliables con él. Toda operación debe conservar atomicidad, evidencia append-only, cancelación monotónica, balance por libro y conversión explícita a la moneda de cada libro activo, bloqueando el registro cuando falte una tasa. Las anulaciones neutralizan el registro en su misma fecha y período; las reversiones conservan el efecto histórico y registran su corrección en otro período. R2R debe reportar esas operaciones con cortes y saldos reproducibles. Se aplican los procesos estándar de la industria y las decisiones documentadas del proyecto: no se reinventa su semántica ni se toman decisiones de negocio por iniciativa del implementador. Desktop, con SQLite y sin Redis, debe completar estos recorridos; Cloud agrega aislamiento multiempresa, roles y las capacidades adicionales definidas. Se conserva el monolito modular y el alcance contable; manufactura, nómina y activos fijos quedan fuera del core de este proyecto.

## Convención de lotes

Cada lote por agrupador corresponde a un cambio pequeño solo si sus hijos comparten consumidor y contrato. Si aparecen cambios independientes, dividir el lote en varios commits y dejar la lista exacta de issues cubierta por cada commit. Las referencias a un paraguas organizan el trabajo: no sustituyen el criterio de aceptación individual de sus hijos.

Antes de iniciar cada lote, leer todos los comentarios de sus issues, comprobar que continúen abiertos y que el comportamiento descrito siga presente en el código. Para cada fix, escribir o ampliar las pruebas funcionales y negativas mínimas necesarias, ejecutar los linters previos al commit y validar los motores afectados según la cadencia siguiente. Mantener el cambio por consumidor; usar `Refs: #n` en commits y no cerrar issues como consecuencia automática de un commit.

## Ritmo de desarrollo y controles

La prioridad operativa es avanzar rápido con fixes pequeños y verificables. **No es necesario ejecutar toda la suite para cada commit.** Seleccionar la menor cantidad de pruebas que demuestre el comportamiento corregido, los fallos realistas y las invariantes afectadas: empezar por casos o archivos concretos y agregar consumidores relacionados solo si el cambio o un fallo lo justifican. Conservar pruebas sustanciales y la cobertura exigida por AGENTS.md; evitar pruebas redundantes y repeticiones de controles ya aprobados sobre código que no cambió. Ejecutar desde `.venv` o `venv`; usar `pytest -n auto` cuando la selección tenga suficiente trabajo para aprovechar el paralelismo.

- **Antes de cada commit de código:** ejecutar las pruebas dirigidas del cambio y los linters exigidos por AGENTS.md, incluidos black, ruff, flake8, mypy, pylint y pydocstyle; comprobar complexipy en los archivos productivos editados. Aplicar los controles de seguridad, JavaScript e i18n pertinentes al cambio. Si el commit solo modifica Markdown, verificar el documento y su diff; no ejecutar tests ni linters de Python por ese cambio documental.
- **Cada 50 commits locales acumulados desde la última ronda completa satisfactoria:** detener la acumulación y ejecutar todos los controles de integración definidos en `.github/workflows/ci.yml` y los workflows que invoca. El umbral cuenta commits, no issues: un issue puede requerir varios commits y un fix puede cubrir varios issues. Registrar en la bitácora del issue o tracker el SHA validado y los resultados; contar desde ese SHA con `git rev-list --count <SHA-validado>..HEAD`. Reiniciar el contador únicamente cuando la ronda completa termine satisfactoriamente. Los commits de corrección también cuentan.
- **Pylint en cada ronda completa:** revisar todos los mensajes de error (`E`) y fatales (`F`), priorizando `E0602`, `E0601`, `E0606`, `E1101`, `E1102`, `E1120`, `E1121`, `E1123`, `E1131`, `E1136`, `E1111`, `E0401`, `E0611`, `E0702` y `E4702`; comparar con la línea base también `W0101`, `W0406`, `W0612` y `W1404`, corregir los defectos reales y documentar los falsos positivos, incluidos los de inferencia de ORM y frameworks.
- **Ronda completa:** reproducir la matriz vigente de `.github/workflows/python.yml`, `.github/workflows/lint.yml` y `.github/workflows/databases.yml`: suite Cloud en Python 3.12, 3.13 y 3.14, suite Desktop en Python 3.13, traducciones compiladas, cobertura, linters y Bandit, pruebas JavaScript, pruebas de base de datos SQLite/MySQL/PostgreSQL —PostgreSQL con psycopg2 y pg8000— y aislamiento de caché. Usar los comandos, variables, dependencias y preparación de bases indicados en esos workflows; ejecutarlos en entornos de prueba aislados. Los workflows son la fuente de la matriz vigente y no se modifican para eludir fallos.
- **Antes de un push autorizado a `origin/estabilizacion`:** exigir una ronda completa satisfactoria sobre el HEAD exacto que se enviará, aunque todavía no se hayan acumulado 50 commits. Reutilizar la ronda anterior si validó ese mismo SHA; si cambió el código, completar la validación del nuevo HEAD. Resolver las regresiones antes del push y revisar después el CI del PR asociado a `estabilizacion`: la configuración vigente de `ci.yml` ejecuta CI en los PR y en pushes a `main`/`development`, por lo que el push a `estabilizacion` por sí solo no garantiza un run. El objetivo de la ronda local es llegar al CI de GitHub en verde; confirmar el resultado remoto antes de considerar validada la integración.

SQLite y PostgreSQL son Tier 1: sus errores son bloqueantes. MySQL es Tier 2 y **también se prueba** en la ronda completa, además de las pruebas dirigidas cuando el fix afecta su compatibilidad; sus fallos se registran y corrigen según su impacto, sin convertirlo en un requisito de lanzamiento Tier 1. Si falta un motor, versión de Python o herramienta para reproducir la matriz, registrar el control pendiente y habilitar el entorno necesario; no declarar la ronda completa en verde con comprobaciones omitidas.

## Orden de ejecución

Tomar primero #1546, que corrige la lectura de catálogos contables entre compañías en Cloud. Después avanzar por las fases y dependencias siguientes, por flujo consumidor. #1658 se divide entre esos flujos; nunca se implementa como un cambio combinado. No se espera al cierre de una fase completa cuando el lote tenga sus propios prerrequisitos satisfechos.

Para elegir el siguiente lote, aplicar en orden: dependencia explícita del issue y sus comentarios; contrato productor de la tabla siguiente; riesgo confirmado de exposición entre compañías, pérdida de evidencia, atomicidad o desbalance; resto del flujo consumidor. Si varios issues describen el mismo defecto, usar la reproducción y el consumidor compartidos para un solo fix y validar por separado el criterio de cada issue. El número de issue no establece prioridad.

| Fase consumidora | Entrada exigida para el lote | Salida verificable antes de continuar un consumidor dependiente |
|---|---|---|
| 1 — Acceso | Actor, acción y alcance aprobados para la ruta afectada. | Matriz de acceso permitido/denegado por compañía, IDs ajenos y rutas alternativas; revocación efectiva cuando aplique. |
| 2 — Persistencia | Alcance de Fase 1 definido si la operación es multiempresa; identificar todos los escritores y el límite de transacción. | Commit/rollback completos, repetición y carrera realista sin evidencia duplicada, reactivada o perdida; semántica comprobada en SQLite y PostgreSQL. |
| 3 — Entrada | Guards de acceso de Fase 1 y unidad transaccional de Fase 2 disponibles para ese escritor. | La ruta y el servicio rechazan entradas inválidas sin mutación parcial; los formatos de importación conservan el mismo contrato. |
| 4 — Contabilidad | Acceso, persistencia y validación del escritor resueltos; identificar libro, moneda, período y estado documental. | GL balanceado por libro, tasa obligatoria, corte y anulación/reversión conforme a los contratos; fallo atómico si falta configuración. |
| 5 — Operación | Contratos de Fases 2–4 que use el recorrido satisfechos. | Recorrido origen → posteo → aplicación/movimiento → corrección; AR/AP e inventario reconciliables con GL por sus dimensiones pertinentes. |
| 6 — Reportes/UI | Fuente, corte y contrato de servidor estabilizados para ese consumidor. Seguridad y pantallas que bloquean el recorrido pueden adelantarse. | Reporte reconciliado, permisos y errores visibles correctos, filtros persistentes, precisión e i18n; solicitudes async obsoletas sin efecto. |

Cada entrega de implementación sigue este flujo: leer issue y todos sus comentarios → identificar consumidor y criterio propio → agregar regresión representativa → fix mínimo → pruebas dirigidas y linters previos al commit → commit acotado con `Refs: #n` y sign-off → QA1 → QA2. Aplicar la ronda completa cada 50 commits y antes del push según la cadencia definida arriba. QA1 y QA2 son revisiones estáticas independientes; si rechazan, corregir y reiniciar el ciclo. Registrar evidencia y decisiones en GitHub. El trabajo del lote termina en `fix-confirmed`; QA3 autorizado o el administrador decide `fixed` y cierre, o retorno a `needs-work`.

## Secuencia por fases y agrupadores

### Prioridad de ejecución

1. Atender primero los contratos que protegen integridad contable: transacciones, evidencia append-only, balanceo por libro, moneda/tasa, períodos y estados de anulación/reversión. Los prerrequisitos mínimos de acceso y persistencia se corrigen antes o en paralelo; no es necesario esperar el cierre de fases completas.
2. Sobre esos contratos, completar los recorridos verticales O2C/S2P/I2F/CTM y conciliar sus extensiones con GL.
3. Simplificar flujos redundantes y retirar código residual al lado de sus consumidores; no dejar esa deuda para el final si bloquea o confunde los recorridos.
4. Integrar únicamente funciones explícitas en los issues y justificadas por las decisiones documentadas. No introducir funcionalidades adicionales por iniciativa del lote. Diferir solo con motivo, impacto y limitación aceptada.


### Primer lote listo para implementación

- **Inicio:** ✅ #1546 implementado con regresión (`1698c612`, `847617de`, `6a04dbdf`, `06058728`, `f4efb796`, `4a808042`); coordinado con #1649/Fase 1. Corregir lecturas de catálogos contables de otra compañía en Cloud; usar la reproducción y los criterios de aceptación ya registrados en el issue. Cubrir usuario autorizado/ajeno, lectura por lista y detalle, y validar PostgreSQL y SQLite según el alcance documentado.
- Después, continuar con los lotes de las fases 1 y 2 que protegen autorización, aislamiento, atomicidad e integridad de evidencia. Avanzar por consumidor y dependencias concretas; no esperar a cerrar una fase completa.

### Ruta de ejecución de features de #1658

- **#1658 ya no es una puerta de decisión:** ejecutar sus hijos en cambios pequeños por consumidor. Integrar las funciones aprobadas, retirar código/rutas residuales tras verificar consumidores y diferir solo con motivo, impacto y limitación documentados.
- **Integrar o completar:** #1118, #1492, #1493, #1564, #1737, #1752, #1758, #1811, #1813, #1888, #1891, #1919, #1928, #1930, #1931, #1937, #1938, #1950, #1973, #1992, #2045, #2061, #2062, #2077, #2147.
- **Retirar residual:** #1162, #1882, #1899, #1909, #1915, #1916, #2071, #2079, #2203, #2204.
- **Retirar el flujo redundante:** #2093, completar la retirada del flujo residual de comparativos de órdenes de compra.
- **Limpieza técnica recomendada:** #2150, verificar que el commit/código referido no tenga consumidor o referencia vigente, retirar el residual y dejar explícito el contrato transaccional.
- Estos hijos se ejecutan en los lotes consumidores de fases 1–6; esta lista es un índice de ruta, no un commit combinado. Para cada retiro conservar evidencia breve de búsqueda de consumidores y pruebas de que el flujo restante funciona.

#### Sub-lotes ejecutables del agrupador #1658

| Sub-lote | Issues | Trabajo para un fix acotado |
|---|---|---|
| 1658-A · Recurrentes | #1492, #1493 | Validar balance por plantilla y aplicar la frecuencia aprobada en la creación/ejecución. |
| 1658-B · O2C/R2R | #1118, #1813, #1937, #2045 | Corregir exclusión de transferencias sin postear, requisito de entrega para 3-way, exportación PDF del mayor y consumo de origen desde orden; separar commits por consumidor si no comparten servicio. |
| 1658-C · Inventario | #1737, #1811, #1888, #1891 | Aplicar conversiones UOM, moneda requerida de conciliación, persistencia de detalle y contrato de ajustes solo positivos/negativos. |
| 1658-D · Costos de compra | #1752, #1758, #2147 | Completar edición/prorrateo de landed cost y enlace a detalle; separar el enlace de interfaz si es independiente del cálculo. |
| 1658-E · Portal y vistas de administración | #1564, #1919, #1928, #1930, #1931, #1938 | Completar paginación, revocar portal inactivo, renderizar administración, aplicar tamaño/orientación PDF, habilitar historial y vistas guardadas con RBAC. Dividir por consumidor; no combinar cambios de portal, PDF y reportes en un commit. |
| 1658-F · Seguridad de formularios y configuración | #1950, #1973, #1992, #2061, #2062, #2077 | CSRF, referencias inactivas, serie elegida, credenciales iniciales seguras, eliminación de cuentas predeterminadas y registro del pipeline de archivos. Separar por módulo/contrato. |
| 1658-G · Retiro de residuales | #1162, #1882, #1899, #1909, #1915, #1916, #2071, #2079, #2093, #2150, #2203, #2204 | Retirar constantes, plantillas/macros/helpers/modelos/aliases sin consumidor y el flujo redundante de comparativos; verificar referencias antes de cada retiro. #2150 incluye aclarar el contrato transaccional. No juntar limpiezas de módulos distintos en un solo commit. |

### Fase 1 — Acceso, aislamiento y seguridad

- **Lote 1 — Origen y autorización de documentos — #1649:** #1405, #1753, #1971, #2104, #2135, #2142.
- **Lote 2 — Permisos, acceso y reportes — #1649:** #1725, #1761, #1777, #1781, #1785, #1789, #1797, #1828, #1833, #1852, #1920, #1926, #1998, #2018, #2059, #2072, #2092.
- **Lote 3 — Listados y rutas adyacentes — #1649:** #1841, #1869, #1934, #2039, #2044, #2047, #2052, #2105.
- **Objetivo compartido:** aplicar el mismo alcance de compañía a rutas de lectura/escritura, IDs fuente y payloads; cubrir actor, acción, compañía propia/ajena y rutas alternativas. Standalone asociados: #2110, #2198.
- **Lote #1710 — [ROOT CAUSE][AUTH] Ciclo de vida de credenciales y mensajería: revocación, fail-safe e idempotencia:** #1732, #1762, #1917, #1948, #1958, #1965, #2023.
- **Lote #2209 — Consolidación causa-raíz: Sanitización/validación de salidas y recursos (XSS, SSRF, redirect):** #1923, #2131.
- **Lote #2231 — Consolidación causa-raíz: Invariante de operabilidad mínima (último admin/única entidad activa):** #1767, #1771.
- **Lote #2238 — Consolidación causa-raíz: Redacción de secretos en logs y evidencia:** #2178.

### Fase 2 — Persistencia y garantías transversales

- **Lotes por consumidor — #1653 (Consolidación causa-raíz: atomicidad/idempotencia en read-then-post):**
  - Concurrencia en inventario/documentos: #332, #1820, #1857, #1868, #1881, #1957, #2094, #2098, #2113, #2140, #2173.
  - Concurrencia financiera/bancaria: #1776, #1784, #2082, #2084, #2128, #2129, #2138, #2172.
  - Concurrencia auth/base/aprobaciones: #1680, #1730, #1910, #2076, #2186, #2187, #2188.
  - Contrato de importación/UI: #1678.
  - **Dependencia:** fijar atomicidad/idempotencia por motor; no asumir que locks equivalen en SQLite y PostgreSQL. Cada fix cubre commit/rollback, repetición y carrera realista.
- **Lote #1706 — [ROOT CAUSE][TRANSVERSAL] Extender garantías append-only e inmutabilidad a toda la evidencia:** #1733, #1751, #1865, #1877, #1987, #1997, #2078, #2119.
- **Lote #2208 — Consolidación causa-raíz: Contrato de evidencia de auditoría: escritura atómica, cobertura de campos y actor:** #1794, #1854, #1863, #2111, #2137, #2143, #2176.
- **Lote #2210 — Consolidación causa-raíz: Integridad referencial: FK desactivada y guards de uso/eliminación no replicados:** #1778, #1779, #2183, #2184.
- **Lote #2219 — Consolidación causa-raíz: Contrato de driver/base Tier-1 (portabilidad SQLite↔PostgreSQL y deploy):** #1731, #1738, #1851.
- **Lote #2220 — Consolidación causa-raíz: Idempotencia y guards de entorno en seed/bootstrap:** #1848, #2167, #2168.
- **Lote #2229 — Consolidación causa-raíz: Invalidación de caché al mutar datos maestros:** #1677, #1900.
- **Lote #2232 — Consolidación causa-raíz: Verificación de idempotencia por clave (mutable o sin comparar contenido):** #1815, #1836.
- **Lote #2234 — Consolidación causa-raíz: Contrato de migraciones de esquema sobre bases con datos:** #1849, #1898.

### Fase 3 — Entradas, maestros y contratos de API

- **Lote #1650 — Consolidación causa-raíz: coerción de Decimals en la frontera de entrada:** #1196, #1663, #1741, #1746, #1831, #1864, #1972, #1984, #2069, #2095, #2108, #2132, #2161.
- **Lote #1652 — Consolidación causa-raíz: contrato de lectura tabular en imports:** #1385, #1765.
- **Lote #1716 — [ROOT CAUSE][TRANSVERSAL] Guard de vigencia: is_active verificado al usar, no solo al crear:** #1823, #1839, #1927, #1979, #1982, #2002, #2006, #2075, #2124.
- **Lotes por dominio — #1717 ([ROOT CAUSE][VALIDACIÓN] Validación server-side de dominio en escrituras (formularios CRUD y enums)):**
  - Ventas/compras/documentos: #1520, #1760, #1947, #1978, #2056, #2116, #2136, #2171.
  - Maestros/admin/API: #1347, #1579, #1722, #1766, #1768, #1769, #1913, #1929, #1962, #1994, #1995, #2063.
  - Contabilidad/bancos/tesorería: #1083, #1088, #1742, #1914, #1922, #1933, #1974, #1980, #1983, #2130, #2139, #2180.
  - Inventario/UOM/cuentas: #1747, #1764, #1826, #1829, #2174.
  - **Salida:** rechazo consistente en ruta y servicio; pruebas con referencias inexistentes/ajenas, enums, estados y valores límite. No inferir reglas que el issue no define.
- **Lote #1718 — [ROOT CAUSE][IMPORTS] Paridad de validación y ciclo de vida de lotes de importación:** #1198, #1203, #1476, #1528, #1537, #1966, #2074.
- **Lote #2205 — Consolidación causa-raíz: Canonización de sentinelas de entrada (booleanos, 0/NULL, texto vacío):** #1483, #1555, #1556, #1720, #1723, #1806, #1924, #2066, #2070, #2181.
- **Lote #2207 — Consolidación causa-raíz: Traducción de errores de dominio/registros inexistentes a 400/404:** #1465, #1787, #2101, #2109, #2125, #2126.
- **Lote #2211 — Consolidación causa-raíz: Edición con reconstrucción de payload que descarta campos:** #1790, #1818, #1822, #1825, #1834, #2096, #2100, #2112.
- **Lote #2213 — Consolidación causa-raíz: Contratos de unicidad de negocio (scope, dimensiones, defaults):** #1340, #1681, #1687, #2169.
- **Lote #2214 — Consolidación causa-raíz: Parseo de líneas por índices contiguos descarta filas posteriores:** #1039, #1788, #1871.
- **Lote #2216 — Consolidación causa-raíz: Fallback silencioso ante entradas inválidas en lecturas/reportes:** #1350, #2192, #2194.
- **Lote #2217 — Consolidación causa-raíz: Resolución canónica de fechas/hora en UTC:** #1390, #1514, #1671.
- **Lote #2221 — Consolidación causa-raíz: Validación de dominio en parámetros de lectura:** #1866, #1904, #1969.
- **Lote #2226 — Consolidación causa-raíz: Mutación de configuración sin validar estados in-flight:** #1498, #1724.
- **Lote #2235 — Consolidación causa-raíz: Hidratación de cabecera en formularios con campos bloqueados:** #1874.

### Fase 4 — Invariantes contables y ciclo documental

- **Lote #1654 — Consolidación causa-raíz: lecturas de saldo sin filtro de libro (multilibro):** #2118 y standalone #1025.
- **Lote #1655 — Consolidación causa-raíz: resolver único de moneda y tasa histórica:** #1793, #1817, #1861, #1873, #1879, #1886, #1942, #2015, #2040, #2043, #2081, #2107, #2163, #2170.
- **Lote #1656 — Consolidación causa-raíz: invariantes del ciclo fiscal (año/período/cierre):** #1773, #1786, #1941, #1952, #1954, #1955, #2175, #2185.
- **Lote #1707 — [ROOT CAUSE][FISCAL] Contrato canónico del motor fiscal: una sola base para preview, persistencia y posteo:** #1745, #1757, #1911, #1943, #2020, #2058.
- **Lote #1708 — [ROOT CAUSE][TRANSVERSAL] Unificar máquina de estados documental: aprobaciones, anulaciones y transiciones:** #444, #1423, #1539, #1592, #1749, #1799, #1804, #1807, #1809, #1812, #1897.
- **Lote #1709 — [ROOT CAUSE][R2R] Contrato de cortes históricos: fecha efectiva as-of, reversas y saldo de apertura:** #1132, #1134, #1774, #1830, #1970, #2120, #2190.
- **Lote #2223 — Consolidación causa-raíz: Posteo sin guard de evidencia mínima (conjunto vacío o config faltante):** #1105, #1819.
- **Lote #2233 — Consolidación causa-raíz: Paridad de validación entre caminos paralelos de cálculo/posteo:** #1824, #1892.

### Fase 5 — Subledgers y flujos operativos

- **Lote #1651 — Consolidación causa-raíz: canonización de UOM y cantidad base entre flujos:** #841, #1810, #1847.
- **Lote #1657 — Consolidación causa-raíz: saldos derivados desincronizados en transiciones de documento:** #1264, #1559, #1728, #1770, #1872, #2099.
- **Lote #1713 — [ROOT CAUSE][TRANSVERSAL] Identidad de línea: DocumentRelation y consumo pendiente como única fuente de matching:** #1522, #1550, #1617, #1754, #1802, #1893, #1894, #1895, #2122, #2127.
- **Lote #1714 — [ROOT CAUSE][AR/AP] Contrato canónico de open items: subtipo, línea, dirección y corte:** #999, #1069, #1126, #1227, #2073, #2123.
- **Lote #1715 — [ROOT CAUSE][INVENTARIO] Contrato de valoración: rebuild no destructivo, costos capitalizados y capas en fecha:** #1726, #1727, #1759, #1858.
- **Lote #1719 — [ROOT CAUSE][DOCUMENT FLOW] Contrato del árbol documental: tipos de nodo, límites, búsqueda y cierre:** #1578, #1860.
- **Lote #2206 — Consolidación causa-raíz: Contrato de autoconciliación bancaria (reglas, filtros y ejecución):** #1080, #1081, #1470, #1504, #1508, #1509, #1644, #1721.
- **Lote #2215 — Consolidación causa-raíz: Contrato de alertas de reposición (umbral, predicado y faltante):** #1128, #1349, #1587.
- **Lote #2218 — Consolidación causa-raíz: Semántica de duplicación/copia de documentos:** #1618, #1798, #1821.
- **Lote #2224 — Consolidación causa-raíz: Método de observación de rotación de inventario:** #1129, #1246.
- **Lote #2225 — Consolidación causa-raíz: Vinculación física de crédito/devoluciones y facturas:** #1138, #1220.
- **Lote #2227 — Consolidación causa-raíz: Contrato de relaciones N:M documentadas (estado por vínculo, scalar_one):** #1551, #1734.
- **Lote #2230 — Consolidación causa-raíz: Invariantes de consistencia con origen/configuración validadas solo aguas abajo:** #1739, #1755.
- **Lote #2236 — Consolidación causa-raíz: Guard de stock negativo por lote:** #1876, #1878.

### Fase 6 — Reportes y experiencia de usuario

- **Lotes UI por subcontrato — #1711 ([ROOT CAUSE][FRONTEND] Contratos de interfaz: i18n, Alpine, endpoints y CSRF):**
  - seguridad: #1743, #1859, #1867, #1908, #1985, #2153.
  - traducción: #1740, #1782, #1814, #1838, #1843, #1885, #1907, #1912, #1918, #1932, #1953, #1963, #1964, #1968, #1996, #1999, #2007, #2022, #2054, #2065, #2067, #2145, #2154, #2157.
  - listas: #1792, #1935, #1936, #1939, #1975, #2042, #2050, #2055, #2144, #2152, #2160.
  - formularios y flujos: #1567, #1735, #1775, #1780, #1791, #1795, #1808, #1842, #1850, #1855, #1870, #1875, #1883, #1884, #1887, #1889, #1921, #1944, #1946, #1949, #1951, #1956, #1959, #1960, #1961, #1976, #1977, #1981, #1990, #1993, #2004, #2005, #2016, #2017, #2024, #2025, #2026, #2031, #2038, #2041, #2133.
  - Referencias fuera del tope de subissues: #2162 y #2201 (modales/formularios), #2165 y #2199 (onboarding/navegación), #2193 (traducciones). Añadirlas a los commits del componente correspondiente.
  - Separar commits por componente/flujo si no comparten plantilla o contrato. Corregir el backend antes de UI salvo que la pantalla bloquee el flujo o exponga datos.
- **Lote #1712 — [ROOT CAUSE][FRONTEND] Invalidación de respuestas async: request-id/snapshot en todos los flujos:** #1862, #2158.
- **Lote #2212 — Consolidación causa-raíz: Contrato de filtros de listado (persistencia al paginar y por doctype):** #2085, #2103, #2134, #2141.
- **Lote #2222 — Consolidación causa-raíz: Precisión/formato numérico derivado de Currency.decimals en frontend:** #2090, #2197, #2200.
- **Lote #2228 — Consolidación causa-raíz: Grano/clave de agregación en reportes y KPI:** #1619, #1620.
- **Lote #2237 — Consolidación causa-raíz: Plantillas compartidas con contexto por registro:** #2114, #2115.
- **Lote #2239 — Consolidación causa-raíz: Render del árbol jerárquico preserva el DOM del template:** #2196.

## Issues standalone: añadirlos al flujo consumidor

- **Seguridad y alcance por compañía:** #1546 (Fase 1/#1649), #2110, #2198.
- **Contabilidad, R2R y recurrentes:** #647, #1025, #1042, #1084, #1783, #1837, #2151, #2189, #2191, #1150, #1151, #1816, #2149.
- **O2C/S2P y documentos:** #1041, #1079, #2148, #1226, #1805, #1801.
- **Inventario y tesorería:** #1827, #1729, #1067, #1303, #1832, #2083.
- **Plataforma, UI, operación y documentación:** #1679, #1856, #2177, #2019, #1844, #1905, #2091, #2102, #1370, #1967, #2001, #2106, #1748, #1029, #2179.

## Issues accionables adicionales por fase

Ejecutar estas tareas junto con los lotes de la fase consumidora. La columna de coordinación indica el paraguas documentado en los vínculos o comentarios existentes; «Consumidor» identifica una tarea standalone de esa fase. #1658 coordina features distribuidas entre consumidores y no introduce una fase posterior. Los trackers y paraguas nunca se toman como fixes independientes aunque tengan `needs-work`.

### Fase 1 — Acceso, aislamiento y seguridad

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #911 | Consumidor | ✅ Implementado; regresión local en `da5cb0c4` (etiqueta sin cambio) | fix(reportes): exige company en cloud sin fallback y propaga la compania activa |
| #997 | #1649 | ✅ Implementado; regresión local en `43108a06` (etiqueta sin cambio) | API fiscal: validar compañía para aliases de cobro y pago |
| #998 | #1649 | ✅ Implementado; regresión local en `4bc2dc7e` (etiqueta sin cambio) | API: validar permisos en alias de notas documentales |
| #1019 | #1649 | ✅ Implementado; regresión local en `38fd869f` (etiqueta sin cambio) | API document-flow: la autorización cubre solo el documento de cabecera; las líneas y la compañía destino se escapan |
| #1021 | #1649 | ✅ Implementado; regresión local en `03dfc484` (etiqueta sin cambio) | Setup: el asistente solo requiere login; cualquier usuario autenticado cambia idioma/regional global y crea compañías |
| #1104 | #1649 | ✅ Implementado; regresión local en `4d94544b` (etiqueta sin cambio) | Exige permiso de Caja al listar candidatos de pago |
| #1110 | #1710 | ⚠️ Implementado; regresión local en `9032d7a4` + CAS concurrente en `cd818b30` (etiqueta sin cambio); GitHub: needs-work | fix: bloquea reenvíos de confirmación expirada |
| #1120 | #1649 | ✅ Implementado; regresión local en `f995e0e0` (etiqueta sin cambio) | fix: limita el reporte de lotes a la compañía |
| #1130 | #1649 | ✅ Implementado; regresión local en `c4b36226` (etiqueta sin cambio) | fix: valida libro de KPI contra su compañía |
| #1169 | #1649 | ✅ Implementado; regresión local en `a87db51f` (etiqueta sin cambio) | Aplica alcance de compañía al listado de cierres |
| #1173 | #1649 | ✅ Implementado; regresión local en `04b2e32b` (etiqueta sin cambio) | Filtra bodegas por acceso de compañía en inventario |
| #1175 | #1649 | ✅ Implementado; regresión local en `b4451169` + cobertura verificada (etiqueta sin cambio) | Limita lotes y movimientos al alcance de compañía |
| #1176 | #1649 | ✅ Implementado; regresión local en `04b2e32b` (etiqueta sin cambio) | Valida company explícita en listado de inventario |
| #1181 | #1649 | ✅ Implementado; regresión local en `771d4e15` (etiqueta sin cambio) | Restringe detalle de artículos a compañías autorizadas |
| #1253 | #1649 | ⚠️ Implementado; evidencia y regresión en `b0d9003a`, `f995e0e0` (etiqueta sin cambio); GitHub: needs-work | Define el alcance de lotes entre compañías |
| #1254 | #1649 | ✅ Implementado; regresión local en `274c1869` (etiqueta sin cambio) | Restringe pendientes de compras en consulta bancaria |
| #1261 | Consumidor | ✅ Implementado; regresión local en `f79c5da7` (etiqueta sin cambio) | Respeta alcance de cuenta en reglas bancarias |
| #1280 | #1649 | ✅ Implementado; regresión local en `039e582a` (etiqueta sin cambio) | Autoriza cambios de configuración de terceros por compañía |
| #1282 | #1649 | ✅ Implementado; regresión local en `ff54d165` (etiqueta sin cambio) | Protege la edición de contactos y roles de terceros |
| #1283 | #1658 | ⚠️ Helpers retirados en `d1649c9a`; sin referencias (etiqueta sin cambio); GitHub: needs-work | Elimina helpers de terceros sin llamadores |
| #1284 | #1649 | ✅ Implementado; regresión local en `9cd29cc2` (etiqueta sin cambio) | Aísla adjuntos de terceros entre compañías |
| #1286 | #1649 | ✅ Coordinación cubierta; regresión en `f0ec7506` (etiqueta sin cambio) | Seguimiento: autorización por compañía de terceros |
| #1299 | #1658 | ✅ Implementado; regresión local en `8c4fdec4` (etiqueta sin cambio) | Retira o integra preferencias CompanyParty sin consumidores |
| #1301 | #1649 | ✅ Implementado; regresión local en `8fe99bdc` (etiqueta sin cambio) | Exige alcance de compañía para imágenes globales de artículos |
| #1320 | #1649 | ✅ Implementado; regresión local en `74db370b` (etiqueta sin cambio) | Limita el listado de transacciones bancarias |
| #1321 | #1649 | ✅ Implementado; regresión local en `b649bbdf` (etiqueta sin cambio) | Limita el catálogo de usuarios por compañía |
| #1322 | #1649 | ✅ Implementado; regresión local en `d1979066` (etiqueta sin cambio) | Filtra gastos de reposición por compañía autorizada |
| #1327 | #1649 | ✅ Implementado; regresión local en `dbaede68` (etiqueta sin cambio) | Exige permiso de módulo en catálogos del selector |
| #1329 | #1649 | ⚠️ Implementado; compañía real del documento en `3593b5ad` (etiqueta sin cambio); GitHub: needs-work | Revoca tareas cuando se pierde acceso a la compañía |
| #1332 | #1649 | ✅ Implementado; regresión local en `ba3a7f08` (etiqueta sin cambio) | Alinea permisos de líneas en flujos de inventario |
| #1338 | #1649 | ✅ Implementado; regresión local en `cbac6457` (etiqueta sin cambio) | Rechaza compañías deshabilitadas en query tools |
| #1354 | #1710 | ⚠️ Implementado; regresión local en `de6f005c` (etiqueta sin cambio); GitHub: needs-work | [Seguridad] Rechaza tokens API de usuarios deshabilitados |
| #1355 | #1710 | ⚠️ Implementado; `auth_version` obligatoria en `2beff9e0` (etiqueta sin cambio); GitHub: needs-work | [Seguridad] Revoca accesos existentes al restablecer contraseña |
| #1357 | #1658 | ⚠️ Código retirado en `a93657fa`; `admin/services.py` sin `Blueprint` (etiqueta sin cambio); GitHub: needs-work | [Auditoría] Elimina el blueprint admin sin rutas |
| #1388 | #1649 | ✅ Implementado; regresión local en `872008d3` (etiqueta sin cambio) | Valida el cliente al crear relaciones O2C por línea |
| #1399 | #1649 | ✅ Implementado; regresión local en `1afff009` (etiqueta sin cambio) | Valida el tercero seleccionado en importación de pagos |
| #1407 | #1649 | ✅ Implementado; regresión local en `a43e6117` (etiqueta sin cambio) | Aplica permisos por módulo a cada nodo del árbol documental |
| #1410 | #1649 | ✅ Implementado; regresión local en `54bb39a1` (etiqueta sin cambio) | Permite consultar líneas de entrega desde ventas |
| #1411 | #1649 | ✅ Implementado; regresión local en `4e18de70` (etiqueta sin cambio) | Respeta acceso de inventario en lista de órdenes relacionadas |
| #1416 | #1649 | ✅ Implementado; regresión local en `04b2e32b` (etiqueta sin cambio) | El listado de movimientos filtra por compañías sin autorización |
| #1417 | #1649 | ✅ Implementado; regresión local en `b4451169` + cobertura verificada (etiqueta sin cambio) | Detalle de lote expone movimientos de otras compañías |
| #1418 | #1649 | ✅ Implementado; regresión local en `42786767` (etiqueta sin cambio) | Editar artículo permite borrar cuentas de otras compañías |
| #1433 | #1649 | ✅ Implementado; regresión local en `0b0b6d54` (etiqueta sin cambio) | Valida facturas duplicadas entre compañías |
| #1467 | #1649 | ✅ Implementado; regresión local en `5848ee8e` (etiqueta sin cambio) | Un usuario de solo lectura puede modificar tareas ajenas |
| #1488 | #1649 | ✅ Implementado; regresión local en `76d28dc8` (etiqueta sin cambio) | Vincula el lote de importación al presupuesto autorizado |
| #1511 | #1649 | ✅ Implementado; regresión local en `1b0ed7f4` (etiqueta sin cambio) | Restringir el precargado de pagos por compañía |
| #1515 | #1649 | ✅ Implementado; regresión local en `8aa8a94c` (etiqueta sin cambio) | Restringir fuentes documentales al módulo de origen |
| #1524 | #1649 | ✅ Implementado; regresión local en `1be22360` (etiqueta sin cambio) | Customer and supplier management bypass permissions |
| #1525 | #1649 | ✅ Implementado; regresión local en `1be22360` (etiqueta sin cambio) | Customer and supplier listings expose data without access checks |
| #1526 | #1649 | ✅ Implementado; regresión local en `ea3d7dfc` (etiqueta sin cambio) | Bank master creation bypasses cash permissions |
| #1527 | #1649 | ✅ Implementado; regresión local en `ea3d7dfc` (etiqueta sin cambio) | Bank transaction list omits company access filtering |
| #1540 | #1649 | ✅ Implementado; regresión local en `b4451169` + cobertura verificada (etiqueta sin cambio) | Lotes de inventario exponen datos sin permiso de compañía |
| #1541 | #1649 | ✅ Implementado; regresión local en `b3e98f36` (etiqueta sin cambio) | Detalle de artículo revela cuentas de otras compañías |
| #1542 | #1649 | ✅ Implementado; regresión local en `42786767` (etiqueta sin cambio) | Editar artículo borra cuentas de compañías omitidas |
| #1543 | #1649 | ✅ Implementado; regresión local en `04b2e32b` (etiqueta sin cambio) | Filtro de compañía expone movimientos de inventario |
| #1558 | #1649 | ✅ Implementado; regresión local en `7b7f1de0` (etiqueta sin cambio) | La portada expone períodos de compañías no autorizadas |
| #1562 | #1649 | ✅ Implementado; regresión local en `5fbd7027` (etiqueta sin cambio) | El portal puede imprimir documentos de otra compañía |
| #1572 | #1649 | ⚠️ Implementado; compañía real del documento en `3593b5ad` (etiqueta sin cambio); GitHub: needs-work | Filtra tareas por el acceso vigente al documento |
| #1576 | #1658 | ✅ Implementado; regresión local en `353bee41` (etiqueta sin cambio) | Incluye validar_solicitud en los permisos calculados |
| #1590 | #1649 | ✅ Implementado; regresión local en `b0d9003a` (etiqueta sin cambio) | Filtra lotes sin evidencia de la compañía en el reporte |
| #1595 | #1649 | ⚠️ Implementado; compañía real del documento en `3593b5ad` (etiqueta sin cambio); GitHub: needs-work | La bandeja de tareas muestra documentos tras revocar acceso |
| #1598 | #1649 | ✅ Implementado; regresión local en `636a37b8` (etiqueta sin cambio) | El selector de tareas expone usuarios ajenos a la compañía |
| #1600 | #1649 | ✅ Implementado; regresión local en `19610192` (etiqueta sin cambio) | El dashboard expone datos sin permiso de consulta |
| #1601 | #1649 | ⚠️ Implementado; regresión local en `19610192` (etiqueta sin cambio); GitHub: needs-work | Rutas contables permiten crear sin permiso de acción |
| #1602 | #1710 | ✅ Implementado; regresión local en `3821674c` (etiqueta sin cambio) | El inicio como módulo crea credenciales admin predeterminadas |
| #1640 | #1649 | ✅ Implementado; regresión local en `13dddd6c` (etiqueta sin cambio) | Ignora roles de ventas desactivados al editar precios |
| #1641 | #1710 | ✅ Implementado; regresión local en `62e6c02c` (etiqueta sin cambio) | El endpoint de desarrollo acepta roles admin inactivos |
| #1695 | #1710 | ✅ Implementado; regresión local en `e162b05c` (etiqueta sin cambio) | No guardes secretos de recuperación en texto plano |
| #1696 | #1710 | ✅ Implementado; regresión local en `474684ec` (etiqueta sin cambio) | Hace atómicos los intentos de verificación OTP |
| #2011 | Consumidor | ✅ Implementado; regresión local en `4b25e21f` (etiqueta sin cambio) | Price Lists: una asignación revocada conserva acceso |
| #2013 | Consumidor | ✅ Implementado; regresión local en `e9b32f49` (etiqueta sin cambio) | [LOW][Auth] Evita sumar un minuto extra al lockout |
| #2060 | Consumidor | ✅ Implementado; regresión local en `29fe2836` (etiqueta sin cambio) | [AUDIT][Auth] El contador de aprobaciones ignora el alcance de empresa |

### Fase 2 — Persistencia y garantías transversales

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #759 | #1706 | Implementación (`needs-work`) | HIGH: Extend append-only guarantees beyond GL and stock ledgers |
| #909 | Consumidor | Implementación (`needs-work`) | fix(search-select): ORDER BY invalido con DISTINCT en PostgreSQL |
| #923 | #1706 | Implementación (`needs-work`) | [HIGH][S2P][O2C][Append-only] DocumentRelation y conciliaciones permiten reescritura sin auditoría |
| #925 | #1706 | ⚠️ Implementado; regresión local en `4af51ebf` (etiqueta sin cambio); GitHub: needs-work | [MEDIUM][Append-only][Accounting] Impedir reactivar asientos mediante is_cancelled=False |
| #1000 | #1653 | ⚠️ Coordinado; cubierto por la regresión de #1696 en `474684ec` (etiqueta sin cambio); GitHub: needs-work | OTP: hacer atómico el consumo de códigos de un solo uso |
| #1002 | #1706 | ✅ Implementado; regresión local en `39113652` (etiqueta sin cambio) | Audit: impedir borrar la cadena en modo Desktop |
| #1076 | #1653 | ⚠️ Implementado; regresión local en `7e06776a` (etiqueta sin cambio); GitHub: needs-work | Validar factura al reproducir una clave de idempotencia |
| #1093 | #1653 | Implementación (`needs-work`) | Serializar la reposición concurrente de Caja Chica |
| #1094 | #1653 | Implementación (`needs-work`) | Reservar gastos de reposición bajo bloqueo |
| #1139 | #1653 | Implementación (`needs-work`) | fix: serializa asignaciones de factura a recepción |
| #1144 | #1653 | ✅ Implementado; regresión local en `0e3f790b` (etiqueta sin cambio) | fix: valida claves duplicadas en planes AR/AP |
| #1148 | #1653 | QA2 aprobó; QA3/administrador: `fixed` o retorno a `needs-work` | fix: crea reversos de diarios de forma atómica |
| #1160 | #1653 | Implementación (`needs-work`) | Evita revalorizaciones duplicadas concurrentes |
| #1177 | #1653 | Implementación (`needs-work`) | Revisa estado de serie al cancelar entradas |
| #1178 | #1653 | Implementación (`needs-work`) | Serializa la salida concurrente del mismo serial |
| #1187 | #1653 | Implementación (`needs-work`) | Serializa la liquidación concurrente de vales |
| #1266 | #1653 | Implementación (`needs-work`) | Evita liquidar dos veces un vale de caja |
| #1271 | #1653 | Implementación (`needs-work`) | Evita ajustes duplicados en conciliación de caja chica |
| #1294 | #1658 | ⚠️ Código retirado en `2d9d8848`; sin referencias (etiqueta sin cambio); GitHub: needs-work | Retira la mutación de contador externo sin auditoría |
| #1306 | #1653 | Implementación (`needs-work`) | Bloquea el serial antes de validar salidas concurrentes |
| #1318 | #1658 | Implementación (`needs-work`) | Integra o backfill bancario o elimina |
| #1319 | #1653 | Implementación (`needs-work`) | Evita duplicados en importaciones bancarias concurrentes |
| #1466 | #1653 | ✅ Implementado; regresión local en `4078e439` (etiqueta sin cambio) | API de cierre de flujo responde 200 sin persistir cambios |
| #1669 | #1653 | ✅ Implementado; regresión local en `ba0e0252` (etiqueta sin cambio) | [Imports] Recuperación duplica errores de timeout |
| #1682 | #1653 | ✅ Implementado; regresión local en `8c4fdec4` (etiqueta sin cambio) | [Audit][Auth] Evita roles duplicados por usuario |
| #1683 | #1658 | Implementación (`needs-work`) | [Audit][Database] Elimina columnas muertas de BaseTransaccion |
| #1684 | #1658 | Implementación (`needs-work`) | [Audit][Database] Retira aliases de compatibilidad sin uso |
| #1689 | #1653 | Implementación (`needs-work`) | Evita sobreasignar factura concurrentemente |
| #1697 | #1653 | ✅ Implementado; regresión local en `03dfc484` (etiqueta sin cambio) | Evita duplicar claves de configuración |
| #1853 | Consumidor | Implementación (`needs-work`) | [AUDIT][REFACTOR] Config mypy diverge: .mypy.ini sombreado por pyproject.toml |

### Fase 3 — Entradas, maestros y contratos de API

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #547 | #1652 | Implementación (`needs-work`) | [AUDIT][Importaciones] Acepta moneda inactiva |
| #950 | #1650 | ✅ Implementado; regresión local en `135b3b5e` (etiqueta sin cambio) | Importación: validar datos numéricos no finitos |
| #1007 | #1650 | ✅ Implementado; regresión local en `481470f7` (etiqueta sin cambio) | Fiscal: rechazar valores no finitos en líneas manuales |
| #1010 | #1650 | ✅ Implementado; regresión local en `481470f7` (etiqueta sin cambio) | TaxRule: rechazar tasas e importes no finitos |
| #1030 | #1652 | Implementación (`needs-work`) | Importación bancaria: '1.000' (miles europeos) se corrompe a 1.000 y '1,000' (miles americanos) se rechaza |
| #1031 | #1652 | ✅ Implementado; regresión local en `4ac988a1` (etiqueta sin cambio) | Importación: un lector que lanza excepción deja el lote zombi en estado 4 y la recuperación ignora started_at NULL |
| #1032 | #1652 | Implementación (`needs-work`) | Importación: la cancelación de un lote en ejecución queda sobrescrita (estado 8 se reescribe a 5/6) |
| #1033 | #1652 | ✅ Implementado; regresión local en `0baa66b1` (etiqueta sin cambio) | Importación: celdas XLSX/ODS vacías persisten el literal 'None' (descripción, referencia y moneda) en transacciones y pronósticos |
| #1046 | #1658 | ⚠️ Retirado en `a0d0f698`; sin referencias (etiqueta sin cambio); GitHub: needs-work | Extractos: retirar el importador CSV sin ruta productiva |
| #1048 | #1652 | 🧪 Implementado; regresión local en `acafcce7` (etiqueta sin cambio); GitHub: fix-proposed | Importación de terceros descarta grupo y clasificación |
| #1049 | #1652 | ✅ Implementado; regresión local en `903cdf8b` (etiqueta sin cambio) | Importación modifica pronósticos de caja aprobados |
| #1050 | #1652 | ✅ Implementado; regresión local en `63934c23` (etiqueta sin cambio) | Importación admite montos no positivos en pronósticos de caja |
| #1051 | #1652 | ⚠️ Implementado; clave legacy preservada en `ea8f3377` (etiqueta sin cambio); GitHub: needs-work | Importación de terceros duplica identidades ya registradas |
| #1052 | #1652 | ✅ Implementado; regresión local en `f24b6b6a` (etiqueta sin cambio) | Importación contable acepta campos requeridos en blanco |
| #1053 | #1652 | Implementación (`needs-work`) | Importación: preservar relaciones por línea origen |
| #1054 | #1652 | Implementación (`needs-work`) | Importación: validar campos de cabecera agrupados |
| #1055 | #1652 | ⚠️ Implementado; desbordamiento controlado en `b863f809` (etiqueta sin cambio); GitHub: needs-work | Importación: normalizar fechas Excel antes de validar |
| #1057 | #1652 | Implementación (`needs-work`) | Importación de órdenes: validar el tipo del proveedor |
| #1059 | #1652 | Implementación (`needs-work`) | Importación de órdenes: definir tratamiento de impuesto |
| #1060 | #1652 | Implementación (`needs-work`) | Importación de ventas: validar artículos habilitados |
| #1061 | #1652 | 🧪 Implementado localmente; GitHub fix-proposed (QA2 pendiente) | Importación transaccional: plantilla incluye columna prohibida |
| #1062 | #1658 | Implementación (`needs-work`) | Importación: lotes fallidos quedan sin recuperación |
| #1063 | #1652 | Implementación (`needs-work`) | Importación contable: validar cuenta padre |
| #1064 | #1652 | 🧪 Implementado localmente; GitHub fix-proposed (QA2 pendiente) | Importación transaccional: validar tarifas negativas |
| #1065 | #1652 | ✅ Implementado; regresión local en `88964495` (etiqueta sin cambio) | Importación: rechazar archivos sin filas de datos |
| #1072 | #1650 | Implementación (`needs-work`) | Rechazar factores UOM no finitos |
| #1087 | #1650 | Implementación (`needs-work`) | Normalizar precisión antes de detectar extractos repetidos |
| #1174 | #1650 | Implementación (`needs-work`) | Rechaza factores UOM no finitos |
| #1182 | #1717 | Implementación (`needs-work`) | Respeta validación al crear unidades de medida |
| #1183 | #1717 | Implementación (`needs-work`) | Respeta validación al crear bodegas |
| #1184 | #1717 | Implementación (`needs-work`) | Valida campos al crear unidades y proyectos contables |
| #1185 | #1650 | Implementación (`needs-work`) | Controla decimales inválidos en flujos de caja |
| #1197 | #1652 | Implementación (`needs-work`) | Comprobantes interpreta "false" como anticipo |
| #1199 | #1658 | Implementación (`needs-work`) | Eliminar adaptador de órdenes de compra sin uso productivo |
| #1200 | Consumidor | Implementación (`needs-work`) | Importación acepta archivos sin filas de datos |
| #1201 | Consumidor | Implementación (`needs-work`) | Lectores Excel no normalizan fechas de celdas |
| #1204 | #1718 | Implementación (`needs-work`) | Validador de conciliación acepta ajustes mayores al monto |
| #1205 | #1718 | Implementación (`needs-work`) | Validación de conciliación no acumula saldo entre líneas |
| #1206 | #1652 | Implementación (`needs-work`) | El lector XLSX materializa dimensiones antes de limitar filas |
| #1212 | #1717 | Implementación (`needs-work`) | Rechaza filas duplicadas por artículo y bodega en conciliación |
| #1225 | #1717 | Implementación (`needs-work`) | Rechaza tipos desconocidos en facturas de venta |
| #1262 | #1652 | Implementación (`needs-work`) | Unifica deteccion de duplicados bancarios |
| #1263 | #1650 | Implementación (`needs-work`) | Rechaza tolerancias negativas de matching |
| #1265 | #1716 | Implementación (`needs-work`) | Filtra cuentas inactivas en setup de caja chica |
| #1291 | #1652 | Implementación (`needs-work`) | Seguimiento: normalización de fechas Excel en importaciones |
| #1292 | #1650 | Implementación (`needs-work`) | Seguimiento: importes positivos en pronósticos importados |
| #1295 | #1652 | Implementación (`needs-work`) | Seguimiento: rechazo de importaciones sin filas de datos |
| #1296 | #1650 | Implementación (`needs-work`) | Seguimiento: rechazo de factores UOM no finitos |
| #1300 | #1716 | Implementación (`needs-work`) | Rechaza cuentas AR/AP no contabilizables |
| #1302 | #1716 | Implementación (`needs-work`) | Valida proveedor activo al aprobar factura de compra |
| #1339 | #1716 | Implementación (`needs-work`) | Impide agregar valores a dimensiones inactivas |
| #1342 | #1716 | Implementación (`needs-work`) | Valida cuenta bancaria al elegir plantilla de cheque |
| #1345 | #1652 | Implementación (`needs-work`) | ODS omite filas con number-rows-repeated |
| #1346 | #1652 | Implementación (`needs-work`) | Importación de maestros descarta filas agrupadas por document_ref |
| #1353 | #1658 | Implementación (`needs-work`) | [Auditoría] Define o elimina el filtro fiscal por categoría de artículo |
| #1358 | #1717 | Implementación (`needs-work`) | [Auditoría] Valida el tipo de grupo de terceros al guardarlo |
| #1362 | #1717 | Implementación (`needs-work`) | [Auditoría] Valida enums en configuración de matching |
| #1373 | #1652 | Implementación (`needs-work`) | Limita filas XLSX antes de materializar la hoja completa |
| #1374 | #1718 | Implementación (`needs-work`) | Rechaza fechas inválidas en la validación de asientos importados |
| #1383 | #1718 | Implementación (`needs-work`) | fix: conserva grupo al importar terceros |
| #1389 | #1652 | Implementación (`needs-work`) | Evita insertar dos veces líneas importadas |
| #1392 | #1652 | QA2 aprobó; QA3/administrador: `fixed` o retorno a `needs-work` | Limita la expansión de celdas en importaciones generales |
| #1393 | #1718 | Implementación (`needs-work`) | Permite corregir lotes con errores desde la interfaz |
| #1394 | #1718 | Implementación (`needs-work`) | Respeta la serie elegida al importar terceros |
| #1395 | #1718 | Implementación (`needs-work`) | Limita la cancelación de lotes al estado procesando |
| #1396 | #1652 | Implementación (`needs-work`) | Importación ODS omite filas repetidas |
| #1397 | #1718 | Implementación (`needs-work`) | Valida líneas importadas junto al comprobante existente |
| #1398 | #1718 | Implementación (`needs-work`) | Valida acumulados de pagos en importación de conciliaciones |
| #1400 | #1652 | Implementación (`needs-work`) | Rechaza ZIP que no sea XLSX en el importador de líneas |
| #1401 | #1652 | Implementación (`needs-work`) | Rechaza múltiples hojas de líneas en XLSX |
| #1403 | #1650 | Implementación (`needs-work`) | Rechaza ajustes de cambio negativos al conciliar pagos |
| #1419 | #1650 | Implementación (`needs-work`) | Líneas de inventario aceptan tarifas Infinity |
| #1435 | #1652 | Implementación (`needs-work`) | Importar artículos de landed cost pierde las líneas |
| #1439 | #1718 | Implementación (`needs-work`) | Importación de conciliaciones no acumula aplicaciones |
| #1446 | #1652 | Implementación (`needs-work`) | [API][Import] Cierra el workbook antes de borrar XLSX temporal |
| #1447 | #1718 | Implementación (`needs-work`) | [API][Cash] Importación no valida tipo de pago contra referencia |
| #1448 | #1652 | Implementación (`needs-work`) | [UI][Sales] La importación de cotización descarta el descuento |
| #1449 | #1652 | Implementación (`needs-work`) | [UI][Import] El pegado acepta encabezados duplicados |
| #1450 | #1652 | Implementación (`needs-work`) | [UI][I2F] La importación pierde bodegas por línea |
| #1451 | #1652 | Implementación (`needs-work`) | [UI][Import] Se descarta la descripción importada de las líneas |
| #1452 | #1652 | Implementación (`needs-work`) | [UI][O2C] La importación descarta la bodega de la línea |
| #1456 | #1718 | Implementación (`needs-work`) | Conciliación: importador rechaza reference_id del esquema |
| #1461 | #1650 | Implementación (`needs-work`) | Normaliza fecha antes de crear pagos destino |
| #1469 | #1650 | Implementación (`needs-work`) | [Cash] NaN provoca error 500 al conciliar pagos |
| #1471 | Consumidor | Implementación (`needs-work`) | [Cash] Fechas ambiguas del extracto se interpretan por orden fijo |
| #1472 | #1652 | Implementación (`needs-work`) | [Imports] XLSX rechaza fecha final del período abierto |
| #1475 | #1652 | Implementación (`needs-work`) | ODS: celdas combinadas desplazan datos de columna |
| #1477 | #1718 | Implementación (`needs-work`) | Importación transaccional acepta tercero de rol incorrecto |
| #1478 | #1718 | Implementación (`needs-work`) | Importación ignora encabezados distintos dentro del documento |
| #1479 | Consumidor | Implementación (`needs-work`) | Importación de líneas pierde valores con encabezados duplicados |
| #1489 | #1652 | Implementación (`needs-work`) | Acepta CSV de presupuesto con BOM UTF-8 |
| #1491 | Consumidor | Implementación (`needs-work`) | Evita validar importaciones de presupuesto vacías |
| #1500 | #1650 | Implementación (`needs-work`) | Rechaza montos no finitos en proyecciones manuales |
| #1505 | #1652 | Implementación (`needs-work`) | Rechaza importes negativos en columnas del extracto |
| #1506 | Consumidor | Implementación (`needs-work`) | Evita interpretar fechas ambiguas del extracto |
| #1507 | #1652 | Implementación (`needs-work`) | Detecta transacciones duplicadas dentro del mismo lote |
| #1510 | #1652 | Implementación (`needs-work`) | No deduzcas duplicados sin referencia bancaria |
| #1512 | #1650 | Implementación (`needs-work`) | Preservar decimales al serializar pagos en Alpine |
| #1519 | #1650 | Implementación (`needs-work`) | fix: conserva precisión al comparar ofertas |
| #1529 | #1652 | Implementación (`needs-work`) | Journal import validation accepts invalid dates |
| #1530 | #1652 | Implementación (`needs-work`) | Journal imports ignore dates that differ within a reference |
| #1531 | #1652 | Implementación (`needs-work`) | Transaction import templates reject their serial column |
| #1532 | #1718 | Implementación (`needs-work`) | Transaction imports accept parties with the wrong role |
| #1533 | #1652 | Implementación (`needs-work`) | Transaction imports ignore currency changes within a document |
| #1535 | #1652 | Implementación (`needs-work`) | Transaction imports ignore party changes within a document |
| #1536 | #1652 | Implementación (`needs-work`) | Importaciones omiten fechas distintas por documento |
| #1538 | #1716 | Implementación (`needs-work`) | Importación bancaria acepta cuentas inactivas |
| #1544 | #1650 | Implementación (`needs-work`) | Ventas y compras fallan con tarifas Infinity |
| #1568 | #1717 | Implementación (`needs-work`) | Matching acepta tipos y tolerancias fuera de rango |
| #1571 | #1650 | Implementación (`needs-work`) | Valida cantidades no finitas en precio del catálogo |
| #1603 | #1652 | Implementación (`needs-work`) | El importador XLSX deja archivos temporales abiertos |
| #1612 | #1650 | Implementación (`needs-work`) | La base cero de un cargo manual se sustituye por el subtotal |
| #1623 | #1652 | Implementación (`needs-work`) | Importación XLSX operativa acepta fórmulas con valores en caché |
| #1625 | #1652 | Implementación (`needs-work`) | Importadores ODS de presupuesto y tasas fallan con odfpy |
| #1626 | #1652 | Implementación (`needs-work`) | Importación de presupuesto rechaza CSV UTF-8 con BOM |
| #1627 | #1652 | Implementación (`needs-work`) | Importación de presupuesto valida un archivo vacío |
| #1628 | #1652 | Implementación (`needs-work`) | Importación agrupa filas con cabeceras incompatibles |
| #1629 | #1652 | Implementación (`needs-work`) | Valida series y cantidades al importar documentos de inventario |
| #1631 | #1652 | Implementación (`needs-work`) | Acepta CSV válidos de una columna en el fallback MIME |
| #1661 | #1718 | Implementación (`needs-work`) | Imports accepts unsupported record types and detail returns 500 |
| #1662 | #1652 | Implementación (`needs-work`) | CSV fallback accepts tabs that the reader cannot parse |
| #1668 | #1717 | Implementación (`needs-work`) | [Imports] Valida dominios del catálogo contable |
| #1670 | #1658 | Implementación (`needs-work`) | [Line Import] La columna description se descarta |
| #1672 | #1718 | Implementación (`needs-work`) | [Imports] Valida cuentas de comprobantes antes de ejecutarlos |
| #1674 | #1718 | Implementación (`needs-work`) | Importación acepta lotes vencidos en recepciones |
| #1675 | #1718 | Implementación (`needs-work`) | Importación falla con lote opcional en blanco |
| #1676 | #1718 | Implementación (`needs-work`) | [Imports] Normaliza moneda vacía en cuentas |
| #1688 | #1650 | Implementación (`needs-work`) | Rechaza tolerancias no finitas en reglas bancarias |
| #1835 | Consumidor | Implementación (`needs-work`) | [AUDIT][I2F] Editar conciliación de inventario borra las observaciones previas |
| #2009 | Consumidor | Implementación (`needs-work`) | Price Lists: respeta casillas de venta y vigencia |
| #2010 | Consumidor | Implementación (`needs-work`) | Price Lists: valida compañía y moneda antes de guardar |
| #2012 | Consumidor | Implementación (`needs-work`) | [MEDIUM][Admin] Evita resetear matching al editar |
| #2014 | Consumidor | Implementación (`needs-work`) | [MEDIUM][Admin] Define eliminación de reglas fiscales |

### Fase 4 — Invariantes contables y ciclo documental

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #546 | #1655 | Implementación (`needs-work`) | [AUDIT][R2R][Multimoneda] Las tasas de cambio históricas pueden editarse después de ser usadas |
| #758 | #1655 | Implementación (`needs-work`) | HIGH: Enforce complete source and destination currency data on every posting |
| #761 | #1708 | Implementación (`needs-work`) | MEDIUM: Apply cancellation and reversal period semantics consistently to all document types |
| #937 | #1658 | Implementación (`needs-work`) | GL: completar el flujo de comprobante manual |
| #961 | #1655 | Implementación (`needs-work`) | AR/AP acepta tasa unitaria sin conversión válida |
| #995 | #1707 | Implementación (`needs-work`) | Fiscal: aplicar exclusiones sin lista de inclusión |
| #996 | #1707 | Implementación (`needs-work`) | Compras: incluir líneas fiscales manuales en el total |
| #1004 | #1656 | Implementación (`needs-work`) | Numeración: fecha retroactiva colisiona al reiniciar serie |
| #1008 | #1707 | Implementación (`needs-work`) | Fiscal: impedir IDs duplicados en reglas manuales |
| #1009 | #1707 | Implementación (`needs-work`) | Fiscal: rechazar líneas manuales negativas en el preview |
| #1011 | #1707 | Implementación (`needs-work`) | Fiscal: no duplicar conceptos en bases acumuladas |
| #1015 | #1707 | Implementación (`needs-work`) | Impuestos: validar aplicabilidad al asignar una plantilla |
| #1016 | #1655 | Implementación (`needs-work`) | Ventas: no mezclar moneda de lista y factura |
| #1017 | #1708 | Implementación (`needs-work`) | Aprobaciones: validar la acción recibida en el POST |
| #1022 | #1708 | Implementación (`needs-work`) | Aprobaciones: doctypes válidos quedan sin rama de envío y quedan 'Approved' en borrador para siempre |
| #1023 | #1707 | Implementación (`needs-work`) | Fiscal: la persistencia de líneas de impuesto sobrescribe concept_amounts y el total no se reconstruye desde las líneas canónicas |
| #1024 | #1656 | Implementación (`needs-work`) | Series: allow_closing=True también desbloquea el año fiscal cerrado, contradiciendo la docstring |
| #1026 | #1707 | Implementación (`needs-work`) | Tax pricing: impuesto aditivo se calcula sobre el precio mostrado que ya contiene el impuesto incluido |
| #1027 | #1708 | Implementación (`needs-work`) | Retenciones: un certificado cancelado no se re-emite al re-publicar el pago y queda irrecuperable |
| #1035 | #1654 | Implementación (`needs-work`) | Caja chica: petty_cash_ledger_balance no filtra por libro y consolida el saldo duplicado |
| #1043 | #1708 | Implementación (`needs-work`) | Inventario: cancelar la origen queda bloqueado para siempre por capas de consumo ya revertidas |
| #1075 | #1709 | Implementación (`needs-work`) | Aplicar fecha de corte a conciliación S2P pendiente |
| #1078 | #1655 | Implementación (`needs-work`) | Comparar ofertas en moneda funcional al autorizar excepción |
| #1082 | #1708 | Implementación (`needs-work`) | Autorizar transición al cerrar ajuste bancario |
| #1085 | #1658 | Implementación (`needs-work`) | Retirar saldos legacy del pronóstico de caja |
| #1086 | #1709 | Implementación (`needs-work`) | Incluir reversiones en el flujo real de caja |
| #1091 | #1709 | Implementación (`needs-work`) | Reconstruir vales y gastos pendientes al corte histórico |
| #1114 | #1655 | Implementación (`needs-work`) | fix: alinea la moneda de conciliación del GL |
| #1115 | #1709 | Implementación (`needs-work`) | fix: acumula saldo previo en el Kardex |
| #1121 | #1655 | Implementación (`needs-work`) | fix: presenta saldos bancarios en una sola moneda |
| #1122 | #1709 | Implementación (`needs-work`) | fix: conserva saldos GL antes de anulación |
| #1123 | #1709 | Implementación (`needs-work`) | fix: conserva stock histórico antes de anulación |
| #1124 | #1709 | Implementación (`needs-work`) | fix: conserva facturas en reportes históricos |
| #1149 | #1658 | Implementación (`needs-work`) | fix: aplica la frecuencia de diarios recurrentes |
| #1153 | #1656 | Implementación (`needs-work`) | fix: evita cierres mensuales duplicados por período |
| #1154 | #1656 | Implementación (`needs-work`) | fix: bloquea la edición de períodos cerrados |
| #1155 | #1656 | Implementación (`needs-work`) | Impide rangos superpuestos en períodos contables |
| #1156 | Consumidor | Implementación (`needs-work`) | La reapertura activa períodos deshabilitados |
| #1157 | #1656 | Implementación (`needs-work`) | El cierre mensual revaloriza un período distinto |
| #1163 | #1654 | Implementación (`needs-work`) | Respeta los libros seleccionados en comprobantes |
| #1164 | #1655 | Implementación (`needs-work`) | Valida el balance de diarios con tasas por línea |
| #1165 | #1655 | Implementación (`needs-work`) | Rechaza monedas inactivas en líneas de diarios |
| #1166 | #1708 | Implementación (`needs-work`) | Permite contabilizar diarios tras aprobación |
| #1168 | #1709 | Implementación (`needs-work`) | Incluye reversiones del año en el cierre fiscal |
| #1170 | #1708 | Implementación (`needs-work`) | Integra el cierre fiscal con la aprobación Cloud |
| #1171 | #1656 | Implementación (`needs-work`) | Protege las fechas de años cerrados financieramente |
| #1172 | #1656 | Implementación (`needs-work`) | Impide años fiscales con rangos superpuestos |
| #1209 | #1708 | Implementación (`needs-work`) | Permite cancelar recibo tras anular consumo de inventario |
| #1210 | #1708 | Implementación (`needs-work`) | No bloquees cancelar factura por su propio costo capitalizado |
| #1211 | #1708 | Implementación (`needs-work`) | Valida costo de inventario consumido al cancelar landed cost |
| #1221 | #1708 | Implementación (`needs-work`) | Bloquea cancelar devolución física con nota de crédito activa |
| #1222 | #1708 | Implementación (`needs-work`) | Cancela asignaciones de notas de crédito sin recibo u orden |
| #1223 | #1655 | Implementación (`needs-work`) | Valida los enlaces de origen de notas de compra |
| #1224 | #1655 | Implementación (`needs-work`) | Valida los orígenes de las notas de venta |
| #1232 | #1708 | Implementación (`needs-work`) | Libera gastos de reposiciones canceladas |
| #1233 | #1655 | Implementación (`needs-work`) | Muestra proyecciones manuales sin tasa de cambio |
| #1234 | Consumidor | Implementación (`needs-work`) | Proyecta cobros y pagos según vencimiento |
| #1235 | #1655 | Implementación (`needs-work`) | Valida moneda en matriz de conciliación |
| #1236 | #1707 | Implementación (`needs-work`) | Incluye las cuentas fiscales configuradas en conciliación |
| #1237 | #1709 | Implementación (`needs-work`) | Aplica el rango de cuentas al presupuesto comparado |
| #1238 | #1709 | Implementación (`needs-work`) | Respeta límites parciales de período presupuestario |
| #1242 | #1709 | Implementación (`needs-work`) | Conserva reversiones de stock en su fecha efectiva |
| #1243 | #1654 | Implementación (`needs-work`) | Concilia AR/AP con la valoración del libro seleccionado |
| #1244 | #1654 | Implementación (`needs-work`) | Define valoración de inventario por libro en conciliación |
| #1245 | #1709 | Implementación (`needs-work`) | Incluye saldo inicial previo en el Kardex |
| #1248 | #1709 | Implementación (`needs-work`) | Rechaza períodos inválidos en reportes GL |
| #1249 | #1658 | Implementación (`needs-work`) | Evita mapeos EFE sin efecto en cuentas P&L |
| #1250 | #1658 | Implementación (`needs-work`) | Detecta cuentas de efectivo sin clasificar en el EFE |
| #1251 | #1655 | Implementación (`needs-work`) | Alinea moneda del saldo bancario reportado |
| #1252 | #1709 | Implementación (`needs-work`) | Separa conciliaciones bancarias de AR/AP en el reporte |
| #1257 | Consumidor | Implementación (`needs-work`) | Valida calendarios al comparar pronosticos de caja |
| #1259 | Consumidor | Implementación (`needs-work`) | Valida fechas de entradas del pronostico |
| #1260 | #1658 | Implementación (`needs-work`) | Elimina helper GL sin referencias |
| #1269 | #1654 | Implementación (`needs-work`) | Separa saldo de caja chica por libro |
| #1270 | #1655 | Implementación (`needs-work`) | Soporta reposición multimoneda de caja chica |
| #1273 | #1708 | Implementación (`needs-work`) | Impide cancelar un vale con gasto contabilizado activo |
| #1274 | #1707 | Implementación (`needs-work`) | Resta las reglas fiscales configuradas como descuento |
| #1275 | #1707 | Implementación (`needs-work`) | Conecta affects_settlement al cálculo de pago y cobro |
| #1276 | #1707 | Implementación (`needs-work`) | Alinea los flags de inventario de reglas fiscales |
| #1281 | #1655 | Implementación (`needs-work`) | Respeta la moneda de la lista al validar precios de venta |
| #1287 | #1656 | Implementación (`needs-work`) | Rechaza contabilizaciones fuera de un período |
| #1293 | #1656 | Implementación (`needs-work`) | Evita reutilizar números al retroceder la fecha de posting |
| #1297 | #1658 | Implementación (`needs-work`) | Aplica la plantilla fiscal configurada para el tercero |
| #1311 | #1656 | Implementación (`needs-work`) | Respeta la fecha de corte al calcular saldo FX |
| #1312 | #1656 | Implementación (`needs-work`) | Rechaza períodos deshabilitados en revaluación FX |
| #1314 | #1658 | Implementación (`needs-work`) | Elimina constante sin uso en revaluación cambiaria |
| #1315 | #1656 | Implementación (`needs-work`) | Lista cierres fiscales desde el modelo equivocado |
| #1317 | #1655 | Implementación (`needs-work`) | Permite conciliar la pata destino multimoneda |
| #1323 | #1655 | Implementación (`needs-work`) | Convierte la fecha antes de consultar la tasa del pago |
| #1324 | #1655 | Implementación (`needs-work`) | Evita asumir NIO sin moneda funcional |
| #1325 | #1655 | Implementación (`needs-work`) | Advierte flujos omitidos por falta de tipo de cambio |
| #1337 | #1658 | Implementación (`needs-work`) | Conecta las dimensiones analíticas con el ledger GL |
| #1341 | #1709 | Implementación (`needs-work`) | Incluye saldo inicial en balanza de query tools |
| #1348 | #1709 | Implementación (`needs-work`) | El saldo acumulado bancario omite el saldo anterior al rango |
| #1352 | #1658 | Implementación (`needs-work`) | [Auditoría] Integra o elimina la reversión de snapshots |
| #1359 | #1658 | Implementación (`needs-work`) | [Auditoría] Conecta las dimensiones analíticas adicionales con el GL |
| #1361 | #1658 | Implementación (`needs-work`) | [Auditoría] Retira el catálogo de tipos especiales sin consumidores |
| #1364 | #1708 | Implementación (`needs-work`) | [Auditoría] Restringe adjudicación a la ronda activa |
| #1365 | #1708 | Implementación (`needs-work`) | [Auditoría] Invalida comparativos al cancelar oferta seleccionada |
| #1367 | #1708 | Implementación (`needs-work`) | [Auditoría] Registra y valida excepción de abastecimiento |
| #1368 | Consumidor | Implementación (`needs-work`) | Seguimiento: conectar dimensiones analíticas con el ledger GL |
| #1372 | #1656 | Implementación (`needs-work`) | Preserva el inicio fiscal cuando solo se recibe una fecha |
| #1375 | #1708 | Implementación (`needs-work`) | Valida prerrequisitos de notas al aprobar documentos |
| #1377 | #1709 | Implementación (`needs-work`) | fix: incluye créditos abiertos en saldo por pagar |
| #1378 | #1655 | Implementación (`needs-work`) | fix: muestra la moneda correcta al relacionar pagos |
| #1380 | #1655 | Implementación (`needs-work`) | fix: actualiza tasas al cambiar la cuenta bancaria |
| #1381 | #1656 | Implementación (`needs-work`) | fix: bloquea imports en pronósticos aprobados |
| #1382 | #1655 | Implementación (`needs-work`) | fix: rechaza tasas cero numéricas al importar |
| #1386 | #1654 | Implementación (`needs-work`) | fix: respeta selección de libros en asientos |
| #1406 | #1654 | Implementación (`needs-work`) | Cierra saldos de documento con la misma regla de pendientes |
| #1422 | #1708 | Implementación (`needs-work`) | Rechaza justificaciones de adjudicación vacías |
| #1427 | #1655 | Implementación (`needs-work`) | Muestra la moneda en conciliación de compras |
| #1430 | #1708 | Implementación (`needs-work`) | Rechaza adjudicaciones sin líneas válidas |
| #1432 | #1708 | Implementación (`needs-work`) | Bloquea rondas tras el cierre manual |
| #1434 | #1709 | Implementación (`needs-work`) | Excluye órdenes completadas del dashboard |
| #1436 | #1707 | Implementación (`needs-work`) | Método fiscal por cantidad devuelve siempre cero |
| #1437 | #1707 | Implementación (`needs-work`) | Notas de crédito muestran preview fiscal de factura |
| #1438 | #1655 | Implementación (`needs-work`) | Preview de factura de compra usa NIO en vez de su moneda |
| #1440 | #1655 | Implementación (`needs-work`) | Saldo de pagos previos se duplica al prorratear |
| #1441 | #1707 | Implementación (`needs-work`) | Asiento fiscal omite impuestos sin cuenta configurada |
| #1460 | #1655 | Implementación (`needs-work`) | Prorratea mal el valor de anticipos multimoneda |
| #1490 | #1658 | Implementación (`needs-work`) | Guarda cambios de libro y año fiscal del presupuesto |
| #1499 | #1709 | Implementación (`needs-work`) | Incluye reversas de GL en el pronóstico real de caja |
| #1501 | #1656 | Implementación (`needs-work`) | Valida fechas de proyecciones dentro del año fiscal |
| #1502 | #1709 | Implementación (`needs-work`) | Permite conciliar reversas contabilizadas de otro período |
| #1503 | #1708 | Implementación (`needs-work`) | Reporta auto conciliación antes de aprobación requerida |
| #1513 | #1707 | Implementación (`needs-work`) | Descartar vistas previas fiscales obsoletas en pagos |
| #1523 | #1709 | Implementación (`needs-work`) | fix: respeta el corte histórico de conciliación |
| #1547 | #1709 | Implementación (`needs-work`) | Refleja notas aplicadas en confirmaciones de saldo |
| #1549 | #1707 | Implementación (`needs-work`) | Bloquea impuestos sin cuenta contable |
| #1553 | #1708 | Implementación (`needs-work`) | Evita fallos al consultar estados con historial de aprobaciones |
| #1560 | #1655 | Implementación (`needs-work`) | El saldo bancario se muestra en una moneda distinta |
| #1561 | #1709 | Implementación (`needs-work`) | Las gráficas agrupan meses de años distintos |
| #1565 | #1708 | Implementación (`needs-work`) | Un rango solapado permite aprobar con un nivel inferior |
| #1566 | #1708 | Implementación (`needs-work`) | El rechazo registra una regla ajena al monto |
| #1569 | #1655 | Implementación (`needs-work`) | El neteo de anticipos sobreestima el importe en otras monedas |
| #1577 | #1656 | Implementación (`needs-work`) | Evita reiniciar secuencias al volver a un periodo previo |
| #1580 | #1656 | Implementación (`needs-work`) | Valida el prefijo al registrar números externos |
| #1582 | #1709 | Implementación (`needs-work`) | Incluye reversiones en métricas analíticas GL |
| #1583 | #1709 | Implementación (`needs-work`) | Incluye reversas en el estado de flujo |
| #1584 | #1656 | Implementación (`needs-work`) | Rechaza meses inválidos en retenciones |
| #1586 | #1709 | Implementación (`needs-work`) | Conserva saldo inicial del Kardex |
| #1589 | #1709 | Implementación (`needs-work`) | Calcula saldo inicial en detalle bancario |
| #1593 | #1708 | Implementación (`needs-work`) | Consulta estado con varias solicitudes de aprobación |
| #1594 | #1655 | Implementación (`needs-work`) | Alinea motivo de excepción con recomendación por moneda |
| #1596 | #1709 | Implementación (`needs-work`) | La conciliación de caja chica no reconstruye el estado al corte |
| #1597 | #1655 | Implementación (`needs-work`) | El dashboard etiqueta saldo GL base con moneda bancaria |
| #1604 | #1655 | Implementación (`needs-work`) | Corrige pagos con moneda distinta a la factura |
| #1605 | #1708 | Implementación (`needs-work`) | Maneja estado inválido al crear órdenes del comparativo |
| #1606 | #1708 | Implementación (`needs-work`) | Mantiene abiertas solicitudes con órdenes parciales |
| #1607 | #1655 | Implementación (`needs-work`) | Muestra en moneda incorrecta los saldos bancarios del dashboard |
| #1613 | #1708 | Implementación (`needs-work`) | El estado de documento falla al conservar solicitudes de aprobación anteriores |
| #1621 | #1708 | Implementación (`needs-work`) | O2C: solicitud queda abierta tras convertirse en orden |
| #1634 | #1707 | Implementación (`needs-work`) | El motor fiscal aplica reglas de otros países |
| #1635 | #1707 | Implementación (`needs-work`) | Factura de venta acepta reglas fiscales incompatibles en el payload |
| #1636 | #1655 | Implementación (`needs-work`) | El reporte suma retenciones de monedas distintas |
| #1637 | #1707 | Implementación (`needs-work`) | Valida retenciones de pago con base del cliente |
| #1638 | #1708 | Implementación (`needs-work`) | El estado documental omite cancelaciones pendientes |
| #1642 | #1708 | Implementación (`needs-work`) | La aprobación de anulación no cancela costos de importación |
| #1673 | #1655 | Implementación (`needs-work`) | [Imports] Balancea comprobantes usando sus tasas por linea |
| #1685 | #1707 | Implementación (`needs-work`) | [Audit][Fiscal] Rechaza tipos de impuesto desconocidos |
| #1686 | #1707 | Implementación (`needs-work`) | [Audit][Fiscal] Consolida impuestos en un solo motor |
| #1698 | #1656 | Implementación (`needs-work`) | [AUDIT][R2R] Pasos del cierre reabren corridas cerradas |
| #1701 | #1708 | Implementación (`needs-work`) | [AUDIT][R2R] Regla Cualquiera no asigna aprobadores |
| #1702 | #1708 | Implementación (`needs-work`) | [AUDIT][R2R] GET sobrescribe confirmaciones respondidas |
| #1703 | #1656 | Implementación (`needs-work`) | [AUDIT][R2R] Colisión en número visible de confirmación |
| #1840 | Consumidor | Implementación (`needs-work`) | [AUDIT][R2R] El paquete accounting_engine no tiene suite de pruebas dedicada |
| #2008 | Consumidor | Implementación (`needs-work`) | Aprobaciones: rechazo no-op tras deshabilitar motor |

### Fase 5 — Subledgers y flujos operativos

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #651 | #1715 | Implementación (`needs-work`) | [MEDIO][INV] Reconstrucción de capas de valuación destructiva |
| #947 | #1651 | Implementación (`needs-work`) | Document Flow: cantidades pendientes mezclan UOM |
| #966 | #1651 | Implementación (`needs-work`) | Document status: unificar cantidades base |
| #975 | #1657 | Implementación (`needs-work`) | Document Flow: alinear resumen de pagos al saldo canónico |
| #1034 | #1651 | Implementación (`needs-work`) | Inventario: convert_item_qty permite factor cero o negativo en la dirección directa (la inversa sí lo rechaza) |
| #1036 | #1657 | Implementación (`needs-work`) | Caja chica: expected_cash duplica los gastos posteados y reporta faltante fantasma en cajas físicamente cuadradas |
| #1037 | #1651 | Implementación (`needs-work`) | Reportes por item: get_purchases_by_item/get_sales_by_item suman cantidades en UOMs transaccionales distintas |
| #1038 | #1651 | Implementación (`needs-work`) | Reportes de transferencias: la fila reporta qty_in_base_uom etiquetada con la UOM de transacción |
| #1040 | #1657 | Implementación (`needs-work`) | Ventas: cancelar factura con nota de entrega asociada omite revertir relaciones y refrescar caches derivados |
| #1068 | #1657 | Implementación (`needs-work`) | Conciliación automática ignora saldo bancario pendiente |
| #1073 | #1657 | Implementación (`needs-work`) | Reconstrucción deja bins sin ledger sin corregir |
| #1074 | #1658 | Implementación (`needs-work`) | Eliminar compatibilidad GR/IR sin consumidores |
| #1077 | #1651 | Implementación (`needs-work`) | Emparejar ofertas con su línea origen de RFQ |
| #1089 | #1657 | Implementación (`needs-work`) | Proteger el historial al cambiar cuenta de caja chica |
| #1099 | #1658 | Implementación (`needs-work`) | Retira la validación monetaria de pago sin uso |
| #1100 | #1658 | Implementación (`needs-work`) | Elimina helpers de pagos sin referencias |
| #1102 | #1657 | Implementación (`needs-work`) | No reduz saldo AR/AP por pagos en borrador |
| #1113 | #1714 | Implementación (`needs-work`) | fix: evita descontar dos veces notas aplicadas |
| #1116 | #1714 | Implementación (`needs-work`) | fix: calcula pagos en devoluciones con signo correcto |
| #1127 | #1657 | Implementación (`needs-work`) | fix: filtra documentos abiertos por saldo vigente |
| #1133 | #1715 | Implementación (`needs-work`) | fix: valida existencia de la capa en devoluciones S2P |
| #1135 | #1651 | Implementación (`needs-work`) | fix: compara cantidades de órdenes en UOM base |
| #1136 | #1651 | Implementación (`needs-work`) | fix: normaliza UOM omitida en conciliación S2P |
| #1137 | #1713 | Implementación (`needs-work`) | fix: permite devolver líneas repetidas de recepción |
| #1140 | #1657 | Implementación (`needs-work`) | fix: revalida saldo al contabilizar pagos |
| #1143 | #1657 | Implementación (`needs-work`) | fix: calcula remanente de reembolsos con signo correcto |
| #1146 | #1657 | Implementación (`needs-work`) | fix: conserva número documental al reconstruir AR/AP |
| #1147 | #1657 | Implementación (`needs-work`) | fix: respeta open item elegido al postear diarios |
| #1152 | #1657 | Implementación (`needs-work`) | fix: muestra aplicaciones recurrentes pendientes en cierre |
| #1161 | #1657 | Implementación (`needs-work`) | Evita revaluar saldos de factura ya reducidos por notas |
| #1179 | #1651 | Implementación (`needs-work`) | Test suite falla |
| #1180 | Consumidor | Implementación (`needs-work`) | Congela conversiones UOM de documentos abiertos |
| #1188 | Consumidor | Implementación (`needs-work`) | Valida fondos antes de registrar gastos de caja chica |
| #1194 | Consumidor | Implementación (`needs-work`) | Autoconciliación bancaria registra conciliaciones pendientes como aplicadas |
| #1207 | #1657 | Implementación (`needs-work`) | Confirmación de saldos muestra notas de crédito ya aplicadas |
| #1214 | #1715 | Implementación (`needs-work`) | Impide consumir capas de inventario con fecha futura |
| #1215 | #1658 | Implementación (`needs-work`) | Permite conciliar inventario controlado por lote o serial |
| #1216 | #1715 | Implementación (`needs-work`) | Incluye costos capitalizados de factura en devolución física |
| #1217 | #1715 | Implementación (`needs-work`) | Excluye landed costs anulados del costo de devolución |
| #1218 | #1715 | Implementación (`needs-work`) | Prorratea landed cost entre recibos parciales en devoluciones |
| #1219 | #1715 | Implementación (`needs-work`) | Evita duplicar costo capitalizado del recibo en devolución |
| #1228 | #1657 | Implementación (`needs-work`) | Recalcula estado bancario al cancelar pagos conciliados |
| #1230 | #1657 | Implementación (`needs-work`) | Recalcula caja chica al confirmar conciliación |
| #1239 | #1658 | Implementación (`needs-work`) | Integra el análisis semántico de stock negativo |
| #1255 | #1657 | Implementación (`needs-work`) | Calcula documentos abiertos desde su saldo real |
| #1272 | #1657 | QA2 aprobó; QA3/administrador: `fixed` o retorno a `needs-work` | Excluye líneas canceladas del saldo de caja chica |
| #1277 | #1658 | Implementación (`needs-work`) | Retira o integra el helper de precio sin uso |
| #1278 | #1658 | Implementación (`needs-work`) | Retira o integra la tolerancia de precio sin uso |
| #1279 | Consumidor | Implementación (`needs-work`) | Prioriza la UOM específica al resolver precios |
| #1298 | #1658 | Implementación (`needs-work`) | Conecta la lista de compra configurada al proveedor |
| #1304 | #1657 | Implementación (`needs-work`) | Elimina el fallback a referencias de pago sin relación |
| #1307 | #1651 | Implementación (`needs-work`) | Evalúa cambio de UOM base tras movimientos anulados |
| #1308 | #1658 | Implementación (`needs-work`) | Elimina import legado sin uso de company_currency |
| #1310 | #1657 | Implementación (`needs-work`) | Excluye pagos cancelados del valor en libros AR/AP |
| #1313 | #1657 | Implementación (`needs-work`) | Impide cancelar la revaluación desde journal genérico |
| #1316 | #1657 | Implementación (`needs-work`) | Revierte la conciliación al anular su asiento GL |
| #1333 | #1651 | Implementación (`needs-work`) | Revalida cantidades al duplicar órdenes de compra |
| #1334 | #1651 | Implementación (`needs-work`) | Bloquea cambio de UOM si hay cotizaciones históricas |
| #1335 | #1715 | Implementación (`needs-work`) | Reconstruye también bins sin movimientos de ledger |
| #1336 | #1715 | Implementación (`needs-work`) | Conserva la composición FIFO al reconstruir capas |
| #1351 | #1657 | Implementación (`needs-work`) | Conserva liquidaciones válidas en cortes previos a cancelar el pago |
| #1363 | #1657 | Implementación (`needs-work`) | [Auditoría] Normaliza eventos al reconstruir conciliación |
| #1379 | #1657 | Implementación (`needs-work`) | fix: limpia referencias al cambiar el tercero del pago |
| #1387 | #1657 | Implementación (`needs-work`) | Invalida los documentos fuente al cambiar el tercero |
| #1391 | #1657 | Implementación (`needs-work`) | Revalida capacidad fuente al aprobar documentos O2C |
| #1402 | #1657 | Implementación (`needs-work`) | Limpia conciliación al cambiar sus filtros |
| #1404 | #1657 | Implementación (`needs-work`) | Excluye referencias revertidas del saldo disponible del pago |
| #1408 | #1719 | Implementación (`needs-work`) | Usa el tipo lógico de referencias de pago en el árbol |
| #1412 | #1719 | Implementación (`needs-work`) | Muestra aviso de límite solo cuando haya más nodos |
| #1413 | #1715 | Implementación (`needs-work`) | Valida lotes con saldo posterior a la fecha del movimiento |
| #1414 | #1657 | Implementación (`needs-work`) | La reconstrucción deja bins sin movimientos intactos |
| #1415 | #1715 | Implementación (`needs-work`) | Rebuild de capas rompe referencias de costo capitalizable |
| #1420 | #1657 | Implementación (`needs-work`) | Limpiar un artículo conserva y reenvía la selección anterior |
| #1421 | #1657 | Implementación (`needs-work`) | Limpia lote y serie al cambiar artículo |
| #1424 | #1713 | Implementación (`needs-work`) | Resuelve notas de crédito por línea de origen |
| #1425 | #1713 | Implementación (`needs-work`) | Calcula tarifas solo con líneas pendientes |
| #1426 | #1713 | Implementación (`needs-work`) | Respeta la línea origen al asignar facturas |
| #1429 | #1651 | Implementación (`needs-work`) | Normaliza UOM al adjudicar ofertas |
| #1431 | #1713 | Implementación (`needs-work`) | Usa relaciones para alinear líneas de ofertas |
| #1458 | #1657 | Implementación (`needs-work`) | Pago destino: borrador reduce saldo cacheado de factura |
| #1459 | #1657 | Implementación (`needs-work`) | Cuenta en cero el remanente de reembolsos AR/AP |
| #1464 | #1719 | Implementación (`needs-work`) | La búsqueda documental omite resultados tras deduplicar GL |
| #1481 | #1651 | Implementación (`needs-work`) | Adjudicación mezcla cantidad y precio entre unidades |
| #1482 | #1713 | Implementación (`needs-work`) | Comparativo asigna cotización a línea RFQ equivocada |
| #1495 | #1714 | Implementación (`needs-work`) | Valida la dirección al aplicar anticipos |
| #1496 | #1713 | Implementación (`needs-work`) | Valida el tercero en relaciones documentales |
| #1497 | #1714 | Implementación (`needs-work`) | Rechaza tipos de pago no admitidos |
| #1516 | #1719 | Implementación (`needs-work`) | El flujo documental falla con 500 al apuntar a journal_entry |
| #1517 | #1719 | Implementación (`needs-work`) | El árbol documental acepta límites que provocan RecursionError |
| #1521 | #1713 | Implementación (`needs-work`) | fix: soporta devoluciones con artículos repetidos |
| #1545 | #1714 | Implementación (`needs-work`) | Revisar tasa histórica en aplicaciones posteriores AR/AP |
| #1552 | #1719 | Implementación (`needs-work`) | Valida el origen al cerrar saldos de flujo |
| #1570 | #1714 | Implementación (`needs-work`) | La nota de débito de ventas queda como abierta sin cobrar |
| #1573 | #1714 | Implementación (`needs-work`) | Respeta la línea al resolver referencias desde el ledger AR/AP |
| #1585 | #1714 | Implementación (`needs-work`) | Incluye devoluciones en reportes de CxP |
| #1599 | #1657 | Implementación (`needs-work`) | El dashboard cuenta órdenes completadas como abiertas |
| #1611 | #1651 | Implementación (`needs-work`) | Cambiar el artículo conserva requisitos de lote y serie anteriores |
| #1614 | #1714 | Implementación (`needs-work`) | Respeta el corte histórico al calcular saldo AR/AP |
| #1615 | #1719 | Implementación (`needs-work`) | Muestra el tipo lógico en el árbol de pagos |
| #1616 | #1714 | Implementación (`needs-work`) | Cuenta notas de débito sin factura origen en crédito |
| #1624 | #1651 | Implementación (`needs-work`) | Importación cambia la UOM sin convertir la cantidad |
| #1633 | #1719 | Implementación (`needs-work`) | El árbol documental anuncia nodos omitidos al llegar exactamente al límite |
| #1639 | #1651 | Implementación (`needs-work`) | El flujo genérico omite cantidad base en líneas destino |
| #1704 | #1657 | Implementación (`needs-work`) | No persiste anticipos bancarios y bloquea su aplicación |

### Fase 6 — Reportes y experiencia de usuario

| Issue | Coordinación | Acción y estado | Resultado requerido |
|---|---|---|---|
| #1071 | #1658 | QA2 aprobó; QA3/administrador: `fixed` o retorno a `needs-work` | Eliminar la ruta legacy del árbol documental |
| #1092 | #1658 | Implementación (`needs-work`) | Completar rutas enlazadas en lista de reposiciones |
| #1111 | #1711 | Implementación (`needs-work`) | fix: permite agregar correos en confirmación |
| #1112 | #1711 | Implementación (`needs-work`) | fix: muestra historial de confirmaciones por tercero |
| #1119 | #1658 | Implementación (`needs-work`) | refactor: elimina fallbacks gettext muertos y recursivos |
| #1125 | #1711 | Implementación (`needs-work`) | fix: conserva montos cero en relaciones documentales |
| #1131 | #1658 | Implementación (`needs-work`) | refactor: elimina fechas inertes en consultas de lotes |
| #1213 | #1712 | Implementación (`needs-work`) | Descarta snapshots tardíos en conciliación de inventario |
| #1285 | #1658 | Implementación (`needs-work`) | Elimina o conecta la ruta de carga de adjuntos sin uso |
| #1331 | #1658 | Implementación (`needs-work`) | Elimina o integra el flujo de adjuntos sin uso |
| #1428 | #1711 | Implementación (`needs-work`) | Corrige enlaces del panel de conciliación |
| #1453 | #1712 | Implementación (`needs-work`) | Diario: aceptar validación obsoleta al importar líneas |
| #1454 | #1712 | Implementación (`needs-work`) | Diario: respuesta XLSX reemplaza líneas pegadas después |
| #1455 | #1712 | Implementación (`needs-work`) | Conciliación: importación XLSX pisa líneas editadas |
| #1457 | #1712 | Implementación (`needs-work`) | Conciliación: mostrar candidatos de filtros anteriores |
| #1463 | #1711 | Implementación (`needs-work`) | Limpia selectores dependientes al editar una selección |
| #1480 | #1712 | Implementación (`needs-work`) | Validación tardía reemplaza filas nuevas del comprobante |
| #1484 | #1711 | Implementación (`needs-work`) | Corrige enlaces rotos del panel de conciliación |
| #1485 | #1711 | Implementación (`needs-work`) | Corrige acciones rotas en listas de Caja Chica |
| #1486 | #1711 | Implementación (`needs-work`) | Corrige endpoint de paginación de presupuestos |
| #1487 | #1711 | Implementación (`needs-work`) | Registra el filtro de moneda de presupuestos |
| #1518 | #1711 | Implementación (`needs-work`) | El árbol documental pierde colores de estado en inglés |
| #1554 | #1711 | Implementación (`needs-work`) | Conserva la búsqueda al editar una opción seleccionada |
| #1557 | #1711 | Implementación (`needs-work`) | La opción Costo promedio no se traduce al inglés |
| #1574 | #1711 | Implementación (`needs-work`) | Traduce las etiquetas del esquema de importación |
| #1575 | #1712 | Implementación (`needs-work`) | Descarta respuestas de validación obsoletas del importador |
| #1581 | #1658 | Implementación (`needs-work`) | Corrige módulos inexistentes en herramientas de consulta |
| #1591 | #1712 | Implementación (`needs-work`) | Ignora snapshots obsoletos en conciliación de inventario |
| #1609 | #1712 | Implementación (`needs-work`) | El dashboard conserva cifras tras fallar la consulta del periodo |
| #1610 | #1711 | Implementación (`needs-work`) | Smart select ejecuta onSelect aunque el campo esté bloqueado |
| #1622 | #1711 | Implementación (`needs-work`) | [UI] Badges del flujo documental pierden estilo en inglés |
| #1632 | #1711 | Implementación (`needs-work`) | Actualiza selectores dependientes al cambiar compañía |
| #1643 | #1711 | Implementación (`needs-work`) | Vista de permisos muestra dos acciones siempre denegadas |
| #1645 | #1711 | Implementación (`needs-work`) | El guardado AJAX de numeración bancaria falla por CSRF |
| #1646 | #1658 | Implementación (`needs-work`) | Editar caja chica ignora el nombre enviado |
| #1647 | #1658 | Implementación (`needs-work`) | Listas de caja chica usan endpoints inexistentes |
| #1648 | #1711 | Implementación (`needs-work`) | Importaciones: formularios POST fallan por CSRF |
| #1659 | #1711 | Implementación (`needs-work`) | Import wizard retains a naming series from the prior record type |
| #1666 | #1711 | Implementación (`needs-work`) | [UI][Import] Etiquetas de líneas no se traducen |
| #1667 | #1711 | Implementación (`needs-work`) | Smart Select conserva listeners tras desmontarse con x-if |

## Decisiones aprobadas: contratos de implementación

Estas decisiones se consideran resueltas según los comentarios de los issues y la matriz del responsable. No son bloqueos de triaje. El trabajo es implementar, probar y documentar su cumplimiento.

| Issue | Contrato de implementación | Lote relacionado |
|---|---|---|
| #1658 | Resolver por feature: integrar las funciones aprobadas, retirar código residual y diferir solo con justificación e impacto documentados. | Distribuir hijos entre las fases consumidoras 1–6 |
| #1340 | Unicidad por tipo, valor normalizado y compañía; precedencia del valor local. | #2213 |
| #2213 | Consolidar el contrato de unicidad para códigos y valores predeterminados con la regla aprobada en #1340. | Fase 3 |
| #1105 | Bloquear recepciones valorizadas si no pueden generar una contabilización válida. | #2223 |
| #1246 | Calcular rotación con promedio de inventario ponderado por tiempo. | #2224 |
| #1891 | Los ajustes de inventario admiten únicamente ajustes positivos y negativos. | #1658; validar junto al contrato de inventario |
| #1893 | Duplicar StockEntry de forma independiente, sin heredar relaciones económicas. | #1713 |
| #1895 | Al reutilizar líneas, preservar lote, serie y vencimiento. | #1713 |
| #1897 | Bloquear la duplicación mientras la cancelación está pendiente. | #1708 |
| #1915 | Retirar el catálogo ODS obsoleto después de verificar que no tenga consumidores. | #1658, retiro de residual |
| #1916 | Retirar el modelo residual WorkflowActionLog tras verificar referencias. | #1658, retiro de residual |
| #1919 | Revocar acceso al portal cuando el tercero está inactivo. | #1649 / #1716 |
| #1930 | Aplicar tamaño y orientación de página a la salida PDF. | #1658, impresión |
| #1931 | Completar el acceso al historial de versiones. | #1658, interfaz de administración |
| #1938 | Integrar vistas guardadas reutilizables y aplicar RBAC. | #1658, R2R/UI |
| #2093 | Completar la retirada del flujo residual de comparativos de órdenes de compra. | #1658, S2P |
| #2150 | Recomendación del responsable para el plan: retirar el commit/código inalcanzable tras comprobar referencias y aclarar el contrato transaccional. | #1658, limpieza técnica |
| #1955 | Los reportes de Kardex y bancos operan con períodos contables completos. | #1656 |

Si durante la implementación aparece una incompatibilidad real con estos contratos, registrar la evidencia y el caso concreto; no volver a poner estos issues en una fase genérica de decisión.

## Validación y cierre progresivo

- Para cada fix: pruebas reales orientadas a comportamiento; rollback, repetición, concurrencia, aislamiento de compañías, multilibro/moneda y reversión cuando correspondan.
- Tier 1 se valida en SQLite y PostgreSQL; MySQL Tier 2 también se prueba según la cadencia de integración. Desktop debe operar sin Redis. R2R consume fuentes conciliadas, no agregados sin grano definido.
- Antes de cada commit de código, ejecutar las pruebas mínimas pertinentes y los linters; cada 50 commits acumulados y antes del push, completar la ronda de workflows definida en «Ritmo de desarrollo y controles». Registrar comandos, SHA validado, resultados y bloqueos en GitHub. QA1 y QA2 revisan independientemente; conservar `needs-work` si falta cobertura o una observación sigue abierta. Solo QA3 expresamente autorizado o el administrador puede establecer `fixed`; no cerrar ni hacer push sin autorización expresa.
- La puerta Alpha de #2248 requiere recorridos O2C/S2P/I2F/CTM y R2R, migración de bases limpia/existente según modo, y limitaciones diferidas aceptadas con justificación e impacto.
