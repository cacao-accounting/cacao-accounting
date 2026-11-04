## Cola vigente de auditoría — únicamente elementos pendientes (2026-11-04)

Esta tabla es la vista de continuidad al reanudar; conserva el historial y hallazgos anteriores. Incluye solo rutas sin cierre completo, deduplicadas por archivo y tomadas de la última fila vigente del manifiesto.

Rama `estabilizacion`, HEAD de código auditado `73fcbd3feab0f7c56bdbd082c4b7422a41ce473f`; **473 archivos pendientes de cierre** de 557 rutas únicas. La lista tiene 287 parciales, 186 pendientes, 0 deltas por revalidar y 2 pendientes de criterio (#1888, #1889). Las 84 rutas restantes tienen cierre documentado; nuevas expresiones de estado de cancelación reabrieron dos plantillas.

| Archivo | Funcion/Clase | estatus |
|---|---|---|
| `cacao_accounting/database/__init__.py` | `StockLedgerEntry` listeners de inmutabilidad/tombstone, `StockBin` y `StockValuationLayer` revalidados independientemente; `Batch`, `SerialNumber`, `StockEntry`, `StockEntryItem`, constraints/FK/índices y callers cotejados parcialmente; FKs de `batch_id` solo prueban existencia, no `Batch.item_code == line.item_code` (#1754); `StockEntryItem.amount >= 0` sin qty/base CHECK ni unique por item+bodega; SVL sin link FK a SLE ni guarda inmutable; header delete→FK cascade y guards Desktop #759; StockBin UNIQUE(item,warehouse), first-insert race #332; company↔Warehouse alignment queda solo en callers; resto de modelos/DDL/consumidores y writers pendientes | Parcial |
| `cacao_accounting/database/helpers.py` | ensure helpers SQLite verificados; bootstrap parcial confirmado y reintento falso positivo por usuario ya creado (#1848); PostgreSQL/MySQL, contrato de upgrade y resto pendientes | Parcial |
| `cacao_accounting/__init__.py` | `get_balance_confirmations_history` consumers omit company (#1796); resto de app factory pendiente | Parcial |
| `cacao_accounting/__main__.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/api/__init__.py` | colaboración, correo, guards y contrato de respuesta parcial cotejados; otros endpoints pendientes | Parcial |
| `cacao_accounting/api/dashboard.py` | revisado de principio a fin el contrato del endpoint y consultas (checkpoint 2026-11-03); sin hallazgo confirmado, pendiente callers/revisores cruzados | Parcial |
| `cacao_accounting/api/templates/empy.html` | revisado en checkpoint 2026-11-03: archivo vacío sin callers, candidata a retirar en #1658 | Parcial |
| `cacao_accounting/approval_engine.py` | lectores de RolesUser y filtro active revisados; `request_cancellation`, `_resolve_doctype`, `_finalize_approval`, `_execute_cancel`, `_validate_final_cancellation`, `_validate_purchase_submission`, `_cancel_posted_document` cotejados parcialmente; revalidación independiente confirma rama aceptada `cancel_stock_entry` no revierte relación/cache (#1872), y retorno `None` de solicitud se ignora (#1728); notas omitidas por executor, misma causa que #1642; callers y demás tipos pendientes | Parcial |
| `cacao_accounting/approval_policy.py` | module_access/module_rank/authorized cotejados con permisos por rol | Parcial |
| `cacao_accounting/attachment_service.py` | upload/list/get/delete y ciclo de imágenes cotejados; alcance global Party #1284, imagen de artículo #1376 y helpers heredados sin caller #1658; restantes callers/estados pendientes | Parcial |
| `cacao_accounting/audit_chain.py` | cadena v1/v2, verificador/topología, orden de filas pendientes y lock PostgreSQL reconciliados con hash vigente; límites restantes de DB privilege/Tier 2/concurrencia pendientes | Parcial |
| `cacao_accounting/audit_trail_service.py` | `_log`/`log_create` y S2P #1794 previos; `log_update`/`get_document_timeline` cotejados para StockEntry; timeline filtra AuditTrail por tipo/ID y la duplicación Desktop #1854 carece de inserción; snapshot de edición selectivo pendiente; otras acciones/contratos pendientes | Parcial |
| `cacao_accounting/cache.py` | class DummyCache (métodos: __init__, init_app, get, set, delete); _crear_cache(); _redis_cache_is_enabled(); _generation_key(); _build_user_cache_key(); user_scoped_cache(); invalidate_cache(); init_cache() | Pendiente |
| `cacao_accounting/cli.py` | `db_init` retorna éxito al hallar usuario aunque falte el seed tras fallo parcial (#1848); otros comandos CLI pendientes | Parcial |
| `cacao_accounting/collaboration_service.py` | 24/24 funciones del servicio cotejadas; consumidores y delta de hash pendiente | Parcial |
| `cacao_accounting/company_context.py` | acceso/compañías autorizadas cotejados en flujos asociados; callers restantes pendientes | Parcial |
| `cacao_accounting/config.py` | URI PostgreSQL y driver psycopg2 verificados, revisión integral pendiente | Parcial |
| `cacao_accounting/control_review_service.py` | evidencia en histórico | Parcial |
| `cacao_accounting/decorators.py` | semántica de acceso por módulo y guard de compañía inspeccionados | Parcial |
| `cacao_accounting/document_authorship.py` | revisado en checkpoint 2026-11-03 con scope Cloud; pendiente llamadas del resto de reportes | Parcial |
| `cacao_accounting/document_flow/context.py` | 3/3 helpers revisados; callers O2C/S2P cotejados parcialmente, ACL y consumidores restantes pendientes | Parcial |
| `cacao_accounting/document_flow/currency_resolver.py` | 8/8 funciones revisadas; rutas de alta, conversión de factura y validadores de posting cotejados parcialmente; causas/configuración restantes pendientes | Parcial |
| `cacao_accounting/document_flow/payment.py` | saldo histórico y cache revisados | Parcial |
| `cacao_accounting/document_flow/registry.py` | 20 specs, acciones, 69 flows y 5 helpers cotejados; líneas snapshot/UOM #1847; DeliveryNote→StockEntry permitido y StockEntry→StockEntry reuse permitido; PurchaseReceipt→StockEntry anunciado pero no permitido (criterio); pares purpose de reuso no acotados, decisión pendiente; contratos consumidores pendientes | Parcial |
| `cacao_accounting/document_flow/repository.py` | consumo y cachés revisados; destinos `docstatus=2` se excluyen al recalcular consumo; estado cacheado puede conservarse en rama aprobación StockEntry anulada (#1872); concurrencia de consumo agregado/cierre sin bloqueo y resto pendientes | Parcial |
| `cacao_accounting/document_flow/service.py` | relación/disponibilidad/compañía y estados; writer no bloquea la línea fuente; `source_qty_in_base_uom` consume snapshot afectable por cambio UOM (#1847); cancelación aprobada conserva estado de relación/cache visible (#1872); candidato carrera entre creación de relación y cancelación directa StockEntry (#1872, sin repro); candidato S2P concurrente y resto pendientes | Parcial |
| `cacao_accounting/document_flow/tracing.py` | 3/3 funciones revisadas; tipo inválido depende de #1225, permisos/URLs destino pendientes | Parcial |
| `cacao_accounting/document_flow/tree.py` | 22 funciones revisadas; fuga de metadatos por ACL solo de raíz vinculada a #1515/#1649; árbol muestra vínculo activo de StockEntry anulado vía ApprovalEngine (#1872); límites configurables sin clamp pendientes | Parcial |
| `cacao_accounting/document_flow/validation.py` | 11/11 funciones revisadas; callers y enforcement completo siguen pendientes | Parcial |
| `cacao_accounting/document_identifiers.py` | evidencia en histórico | Parcial |
| `cacao_accounting/exceptions/__init__.py` | clases de excepción y `flash_error()` revisados; helper solo flashea y retorna `None`; varios callers todavía pendientes de contrato de retorno | Parcial |
| `cacao_accounting/exceptions/mensajes.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/fiscal_persistence_service.py` | checkpoint 2026-11-03: 36 funciones revisadas; contrato alta/edición→snapshot→posting/AP/GL cotejado; bordes de payload, modelo y consumidores globales pendientes | Parcial |
| `cacao_accounting/fiscal_preview_service.py` | `fiscal_preview()`/currency fallback y filtro de reglas por moneda cotejados con API/JS/#1438; demás parsers/funciones pendientes | Parcial |
| `cacao_accounting/i18n.py` | class _Stringifiable (métodos: __str__); _get_locale(); _get_timezone() | Pendiente |
| `cacao_accounting/internal_control_service.py` | guards de ApprovalRequest/ledger AR/AP previos; `_audit_insert`/`_write_event` cotejados como listener para DocBase activo solo con `_enabled()` (Cloud; Desktop lo desactiva), factor #1854; `_guard_line` y guards de financial children/Core/raw SQL se omiten en Desktop (#759); en Cloud ese guard bloquea cambios internos de la línea al postear conciliación StockEntry (#1877); otras tablas/guards restantes | Parcial |
| `cacao_accounting/internal_control_sql.py` | uso de `raw_sql_mutates_protected_table()` para impedir mutación textual de ApprovalAction y otras tablas de evidencia cotejado; lexer restante pendiente | Parcial |
| `cacao_accounting/ledger_queries.py` | predicado de stock excluye original cancelado, su voucher y contra is_reversal; coherente con cancelación intra-período comprobada; otros consumidores pendientes | Parcial |
| `cacao_accounting/limiter.py` | revisado en checkpoint 2026-11-03; pendiente decoradores aplicados en blueprints | Parcial |
| `cacao_accounting/list_filters.py` | `apply_list_filters`, filtros de periodo y contexto del selector cotejados para listado de facturas de compra; otros consumidores/limites pendientes | Parcial |
| `cacao_accounting/logistics.py` | revisado en checkpoint 2026-11-03; pendiente revision completa del rest de rutas de proveedores/docs | Parcial |
| `cacao_accounting/logs.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/matching_config_service.py` | valores de compra cotejados con aprobaciones y consumidor 2-way/3-way; normalización/enums, replay y consumidores restantes pendientes | Parcial |
| `cacao_accounting/num2words.py` | revisado en checkpoint 2026-11-03; pendiente Caller de impresión y cotizaciones, nota sobre default `es` | Parcial |
| `cacao_accounting/party_management.py` | checkpoint 2026-11-03: perfil, contactos/direcciones y permisos; consumers restantes pendientes | Parcial |
| `cacao_accounting/party_settings.py` | checkpoint 2026-11-03: round-trip de configuración y alcance GET/POST | Parcial |
| `cacao_accounting/search_select.py` | Batch usa id como value y filtros item_code/activo; el modelo sin company no recibe filtro de alcance; selector y consumidores restantes pendientes (#1175/#1649) | Parcial |
| `cacao_accounting/server.py` | server() | Pendiente |
| `cacao_accounting/static/js/dashboard.js` | initDashboardModule, buildFallbackConfig, dashboardConfig, dashboard, money | Pendiente |
| `cacao_accounting/static/js/document-flow-tree.js` | helpers de escape/render, estados de carga/saldo y payload del árbol cotejados; no tacha vínculo `active` aunque destino StockEntry esté anulado (#1872); formato/lifecycle/casos nulos pendientes | Parcial |
| `cacao_accounting/static/js/smart-select.js` | item_category (#1850) y propagación id para selección Batch cotejadas; resto de funciones/callers pendiente | Parcial |
| `cacao_accounting/static/js/sw.js` | Módulo JS: eventos, listeners y llamadas API pendientes | Pendiente |
| `cacao_accounting/static/js/transaction-form.js` | `transactionForm` rows/prepareSubmit y carga fuente cotejados parcialmente; permite huecos por fila vacía que el parser StockEntry trunca (#1871); validación UI de batch/serial no sustituye qty/estado del servidor; factura #1438; otros doctypes/handlers pendientes | Parcial |
| `cacao_accounting/tax_pricing_service.py` | checkpoint 2026-11-03: cálculo de taxes por plantilla cotejado para S2P; precio ItemPrice y tolerancia de venta pendientes | Parcial |
| `cacao_accounting/tax_rule_service.py` | 15/15 funciones inspeccionadas con rutas, TaxRuleContext/FiscalEngine y snapshots; consumidores y validaciones de frontera restantes pendientes | Parcial |
| `cacao_accounting/templates/400.html` | Jinja/HTML dinámico (8 expresiones/controles) | Pendiente |
| `cacao_accounting/templates/403.html` | Jinja/HTML dinámico (8 expresiones/controles) | Pendiente |
| `cacao_accounting/templates/404.html` | Jinja/HTML dinámico (8 expresiones/controles) | Pendiente |
| `cacao_accounting/templates/base.html` | blocks test, contenido | Pendiente |
| `cacao_accounting/templates/detail_view_macros.html` | `detail_lines_table`/modal revisados para StockEntry: destino de transferencia, descripción `item_name`, trazabilidad por línea y etiqueta batch visibles incompletos (#1810/#1889); Jinja autoescape y render JS con `textContent`; otros callers pendientes | Parcial |
| `cacao_accounting/templates/document_flow_related_list.html` | herencia/enlaces/specs, null fallbacks y guards de contenido condicional cotejados; macro status y productor pendiente | Parcial |
| `cacao_accounting/templates/macros.html` | `lineas_tabla_lectura` cotejada como wrapper de detalle StockEntry; modal correo/colaboración previos; restantes macros/consumidores pendientes | Parcial |
| `cacao_accounting/templates/party_company_settings_form.html` | checkpoint 2026-11-03: campos Alpine, payload y compañía | Parcial |
| `cacao_accounting/templates/party_detail_sections.html` | checkpoint 2026-11-03: formularios de contactos/direcciones | Parcial |
| `cacao_accounting/templates/party_legal_fields.html` | checkpoint 2026-11-03: campos legales cotejados con WTForms/apply_party_profile | Parcial |
| `cacao_accounting/templates/party_profile_fields.html` | checkpoint 2026-11-03: campos de perfil cotejados con WTForms/apply_party_profile | Parcial |
| `cacao_accounting/templates/public/confirm_balance_status.html` | blocks contenido | Pendiente |
| `cacao_accounting/templates/public/confirm_balance_success.html` | blocks contenido | Pendiente |
| `cacao_accounting/templates/public/confirm_balance_verify.html` | blocks contenido | Pendiente |
| `cacao_accounting/templates/public/confirm_balance_view.html` | blocks contenido; Alpine (5 directivas) | Pendiente |
| `cacao_accounting/templates/public/validation_result.html` | Jinja/HTML dinámico (33 expresiones/controles) | Pendiente |
| `cacao_accounting/templates/smart_select_field.html` | evidencia en histórico | Parcial |
| `cacao_accounting/templates/tasks/my.html` | permisos, filtros, estados y etiquetas visibles cotejados; demás plantillas/callers pendientes | Parcial |
| `cacao_accounting/templates/transaction_form_macros.html` | picker Batch/Serial, x-model y sincronización hidden cotejados; inputs rate/amount usan restricciones cliente, no validación server-side (#1864); XSS reflejado desde `source_id` query en StockEntry (#1867); revisión parcial del macro StockEntry confirmó controles de detalle/cargos enviados pero ignorados por el POST (#1888, criterio pendiente); #1871/#1788 cubren huecos de filas; otros callers/macros pendientes | Parcial |
| `cacao_accounting/translations/en/LC_MESSAGES/messages.po` | msgid/msgstr y contexto de traducción | Pendiente |
| `cacao_accounting/version/__init__.py` | build_version() | Pendiente |
| `cacao_accounting/withholding_service.py` | _decimal(); create_withholding_certificate(); cancel_withholding_certificate(); withholding_certificate_lines() | Pendiente |
| `cacao_accounting/admin/__init__.py` | __getattr__(); __dir__() | Pendiente |
| `cacao_accounting/admin/navigation.py` | class ConfigurationLink; class ConfigurationSection | Pendiente |
| `cacao_accounting/admin/routes.py` | correo, sesión y acciones de aprobación cotejadas; settings de valuación cotejado: company query inválida puede terminar en 500 (#1866); restantes endpoints/settings pendientes | Parcial |
| `cacao_accounting/admin/services.py` | configuración SMTP y acciones de aprobación cotejadas; servicios restantes pendientes | Parcial |
| `cacao_accounting/admin/session_security_service.py` | revalidado junto a dispositivo/OTP; resto de configuración de sesión pendiente | Parcial |
| `cacao_accounting/admin/templates/admin.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/approval_matrix.html` | compañía, configuración y tabla de reglas, condición de rol/usuario, CSRF y escape cotejados; motor/callers pendientes | Parcial |
| `cacao_accounting/admin/templates/admin/budget_control_config.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/default_accounts.html` | Jinja/Alpine, filtros Smart Select, CSRF y contrato de guardado cotejados; resto del flujo compartido pendiente | Parcial |
| `cacao_accounting/admin/templates/admin/dimension_values.html` | checkpoint dimensión analítica 2026-11-03 | Parcial |
| `cacao_accounting/admin/templates/admin/email_log.html` | estados, acciones, escape y CSRF cotejados; contratos restantes de administración pendientes | Parcial |
| `cacao_accounting/admin/templates/admin/email_settings.html` | campos SMTP, contraseña, estados y CSRF cotejados; integración completa pendiente | Parcial |
| `cacao_accounting/admin/templates/admin/external_document_validation.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/item_prices.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/ledger_mapping_rules.html` | checkpoint dependiente ledger mapping 2026-11-03 | Parcial |
| `cacao_accounting/admin/templates/admin/modulos.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/party_groups.html` | checkpoint 2026-11-03: catálogo de grupos y cambio de tipo (#1724) | Parcial |
| `cacao_accounting/admin/templates/admin/pending_approvals.html` | filas, payload de revisión, URLs, comentarios, acciones POST y CSRF cotejados; control de tipos especiales y componentes compartidos pendientes | Parcial |
| `cacao_accounting/admin/templates/admin/price_lists.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/purchase_reconciliation_config.html` | CSRF, campos, default visual y tabla de configuración inspeccionados; selección/edición y contrato de config pendientes | Parcial |
| `cacao_accounting/admin/templates/admin/purchase_sourcing_config.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/rol_form.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/rol_permisos.html` | formulario de permisos, csrf y valores de módulo revisados | Parcial |
| `cacao_accounting/admin/templates/admin/roles.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/sales_matching_config.html` | semántica visual 2-way/3-way, campos, CSRF y listado cotejados con ruta/servicio; #1813 | Parcial |
| `cacao_accounting/admin/templates/admin/session_security.html` | acciones y guardas visibles cotejadas con el servicio; integración restante pendiente | Parcial |
| `cacao_accounting/admin/templates/admin/system_language.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/tax_rules.html` | campos/enums, CSRF, creación/edición/eliminación cotejados con servicio/motor; #1010/#1436 | Parcial |
| `cacao_accounting/admin/templates/admin/tax_template_items.html` | selección activa/campos cotejados con ruta/motor; CSRF #1648, ruta legacy #1686 | Parcial |
| `cacao_accounting/admin/templates/admin/tax_templates.html` | formulario/listado cotejados con ruta; POST sin token CSRF relacionado con #1648 | Parcial |
| `cacao_accounting/admin/templates/admin/taxes.html` | campos/enums y CSRF cotejados con ruta/cálculo; #1685 | Parcial |
| `cacao_accounting/admin/templates/admin/usuario_companias.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/usuario_form.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/usuario_password.html` | blocks contenido | Pendiente |
| `cacao_accounting/admin/templates/admin/usuario_roles.html` | checkboxes, CSRF WTForms y script setAllRoles cotejados | Parcial |
| `cacao_accounting/admin/templates/admin/usuarios.html` | blocks contenido | Pendiente |
| `cacao_accounting/app/__init__.py` | evidencia en histórico | Parcial |
| `cacao_accounting/app/templates/app.html` | blocks contenido; Alpine (18 directivas) | Pendiente |
| `cacao_accounting/app/templates/development.html` | Jinja/HTML dinámico (35 expresiones/controles) | Pendiente |
| `cacao_accounting/auth/__init__.py` | login, dispositivo/OTP y recuperación cotejados parcialmente; demás rutas pendientes | Parcial |
| `cacao_accounting/auth/account_throttling.py` | evidencia en histórico | Parcial |
| `cacao_accounting/auth/device_verification.py` | validación OTP/dispositivo y estados de token cotejados; resto de autenticación pendiente | Parcial |
| `cacao_accounting/auth/forms.py` | evidencia en histórico | Parcial |
| `cacao_accounting/auth/helpers.py` | `redireccion_despues_de_login()` consulta `SETUP_COMPLETE` y redirige solo ante valor explícito `False`; ausencia del marcador cae a inicio; resto de helpers pendiente | Parcial |
| `cacao_accounting/auth/permisos.py` | guards de compañía y colaboración cotejados; matriz completa de permisos pendiente | Parcial |
| `cacao_accounting/auth/roles.py` | evidencia en histórico | Parcial |
| `cacao_accounting/auth/templates/forgot_password.html` | formulario/token cotejado con recuperación; flujos completos y expiración pendientes | Parcial |
| `cacao_accounting/auth/templates/login.html` | Jinja/HTML dinámico (27 expresiones/controles) | Pendiente |
| `cacao_accounting/auth/templates/profile.html` | blocks contenido | Pendiente |
| `cacao_accounting/auth/templates/reset_password.html` | formulario y token cotejados con servicio; límites y contratos restantes pendientes | Parcial |
| `cacao_accounting/auth/templates/test_roles.html` | blocks contenido | Pendiente |
| `cacao_accounting/auth/templates/verify_otp.html` | formulario OTP y estados visibles cotejados; flujo integral pendiente | Parcial |
| `cacao_accounting/datos/__init__.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/datos/base/__init__.py` | orden de roles/permisos/admin/monedas cotejado; commits por etapas posibilitan setup parcial (#1848); otros datos base pendientes | Parcial |
| `cacao_accounting/datos/dev/__init__.py` | caller demo_entidad cotejado | Parcial |
| `cacao_accounting/datos/dev/data.py` | fixtures Entity cotejados | Parcial |
| `cacao_accounting/modulos/__init__.py` | descubrimiento, registro/sincronización y estado enabled revisados | Parcial |
| `cacao_accounting/printing/templates/admin/print_template_form.html` | blocks content | Pendiente |
| `cacao_accounting/printing/templates/admin/print_template_list.html` | blocks content | Pendiente |
| `cacao_accounting/printing/templates/admin/print_validation_settings.html` | blocks content | Pendiente |
| `cacao_accounting/setup/__init__.py` | guard `is_setup_complete`, guardas login/admin y pasos POST cotejados con el marcador; flujos restantes del asistente pendientes | Parcial |
| `cacao_accounting/setup/catalogs.py` | class CountryOption; normalize_language(); setup_texts(); entity_type_choices(); country_choices(); country_currency_map(); country_timezone_map(); timezone_choices(); catalog_choices(); setup_template_context() | Pendiente |
| `cacao_accounting/setup/forms.py` | validación WTForms de idioma/región/compañía y opciones de catálogo cotejadas con la ruta; reglas de dominio y casos restantes pendientes | Parcial |
| `cacao_accounting/setup/repository.py` | `get_setup_value`/`set_setup_value` y persistencia key/value del marcador cotejadas; resto de operaciones de entidad/periodo pendiente | Parcial |
| `cacao_accounting/setup/service.py` | `mark_setup_complete` y `finalize_setup` guardan marcador al final del flujo en la transacción; resto de setup/creación de compañía pendiente | Parcial |
| `cacao_accounting/setup/templates/setup.html` | pasos, errores, CSRF, mapas `tojson`, listeners de país/moneda/zona, idioma y catálogo revisados; contratos completos con backend y recursos compartidos pendientes | Parcial |
| `cacao_accounting/templates/admin/balance_confirmation_detail.html` | blocks contenido | Pendiente |
| `cacao_accounting/templates/admin/balance_confirmation_new.html` | blocks contenido; Alpine (4 directivas) | Pendiente |
| `cacao_accounting/templates/setup/setup.html` | plantilla informativa heredada y traducciones cotejadas; búsqueda no encontró caller productivo, relación con la ruta Blueprint pendiente de resolver | Parcial |
| `cacao_accounting/accounting_engine/common/context.py` | ItemContext dimensions/defaults revisados como dependencia de LandedCostEngine; otros contratos pendientes | Parcial |
| `cacao_accounting/accounting_engine/common/rounding.py` | round, precisión/política y residual revisados para LandedCostEngine; otros consumidores pendientes | Parcial |
| `cacao_accounting/accounting_engine/document_builders.py` | `_build_import_landed_cost_context`/`_build_landed_cost_item_contexts` cotejados; dimensions omitidas #1758 y amount transaccional hacia inventario #1793; otros builders pendientes | Parcial |
| `cacao_accounting/accounting_engine/fiscal/engine.py` | class FiscalEngine (métodos: calculate, _build_fiscal_line, _consolidate_fiscal_result, _order_rules, _dependency_map, _calculate_base, _calculate_amount, _included_rules_with_same_base, _get_formula) | Pendiente |
| `cacao_accounting/accounting_engine/fiscal/resolver.py` | class RuleResolver (métodos: resolve, _applicable_rules, _rule_groups, _rule_matches_context, _apply_merge_strategy, _final_rules, _matches_conditions) | Pendiente |
| `cacao_accounting/accounting_engine/gl_posting_builder.py` | post_proforma_to_gl(); _persistence_context(); _gl_entry_from_line(); _bank_account_id_for_line(); _proforma_for_ledger(); _is_balanced(); _calculation_context_for_ledger(); _payment_open_balance_in_ledger(); _reference_carrying_in_ledger(); _reference_balance_in_ledger() | Pendiente |
| `cacao_accounting/accounting_engine/orchestrator/event_orchestrator.py` | llamada LandedCostEngine y propagación de resultado/error verificadas; otros eventos y contratos pendientes | Parcial |
| `cacao_accounting/accounting_engine/orchestrator/mapper.py` | class AccountingMapper (métodos: map_to_proforma, _map_document_event, _map_settlement_event, _build_settlement_balance_line, _map_cash_line, _map_settlement_tax_lines, _map_settlement_adjustment_lines, _settlement_balance_side, _settlement_cash_side, _settlement_tax_side, _map_fiscal_lines, _build_party_line, _build_exchange_difference_line, _build_unrealized_exchange_difference_line, _build_unrealized_party_offset_line, _build_payment_discount_line, _build_line, _finalize_proforma, _map_explicit_account_lines, _requires_party_balance, _balance_against_party, _resolve_goods_account, _resolve_cash_account, _resolve_tax_account, _document_exchange_rate, _settlement_exchange_rate) | Pendiente |
| `cacao_accounting/accounting_engine/settlement/engine.py` | class SettlementOptions; class SettlementEngine (métodos: calculate, _uses_foreign_currency, _calculate_exchange_difference, _calculate_unrealized_exchange_difference) | Pendiente |
| `cacao_accounting/accounting_engine/snapshots/serializer.py` | class EngineJSONEncoder (métodos: default); class SnapshotSerializer (métodos: serialize, to_json) | Pendiente |
| `cacao_accounting/contabilidad/__init__.py` | __getattr__(); __dir__() | Pendiente |
| `cacao_accounting/contabilidad/arap_allocation.py` | class AllocationError; class AllocationCurrencyError; class AllocationOverpaymentError; class AllocationIdempotencyError; _decimal(); class ARAPOpenItem (métodos: __post_init__, from_model); class AllocationRequest; class AllocationLine; class AllocationPlan (métodos: allocated_source_amount, remaining_source_amount, is_full); class OpenItemResolver (métodos: __init__, _key, from_ledger, from_models, add, resolve, all, consume, snapshot, restore); list_open_items(); list_cached_open_items(); resolve_open_item(); class AllocationPlanner (métodos: __init__, plan, _rate); class AllocationExecutor (métodos: __init__, execute); plan_allocation(); apply_allocation() | Pendiente |
| `cacao_accounting/contabilidad/arap_gl_reconciliation.py` | class ARAPGLReconciliationError (métodos: __init__); class ARAPGLReconciliationKey; class ARAPGLReconciliationLine (métodos: is_balanced); class ARAPGLReconciliationResult (métodos: differences, is_balanced, blocked, message); _decimal(); resolve_arap_gl_policy(); compare_arap_gl_totals(); _subledger_totals(); _gl_entry_matrix_value(); _gl_totals(); reconcile_arap_to_gl(); enforce_arap_gl_policy(); reconcile_companies_arap_to_gl() | Pendiente |
| `cacao_accounting/contabilidad/arap_ledger_service.py` | apertura AR/AP y multilibro cotejados; `_add_book_entry` guarda signo débito/crédito coherente con monto firmado; resto pendiente | Parcial |
| `cacao_accounting/contabilidad/auxiliares.py` | obtener_lista_entidades_por_id_razonsocial(); _lista_entidades_cacheada(); obtener_catalogo_base(); obtener_catalogo_centros_costo_base(); obtener_catalogo(); obtener_centros_costos(); obtener_entidades(); obtener_entidad(); obtener_arbol_cuentas(); obtener_arbol_ccostos(); obtener_arbol_unidades(); obtener_arbol_proyectos(); build_tree_data(); obtener_lista_monedas(); obtener_lista_monedas_activas() | Pendiente |
| `cacao_accounting/contabilidad/balance_confirmation.py` | _utcnow(); build_cancellation_map(); is_cancelled_before_cutoff(); _payment_cancelled_at_cutoff(); _reference_active_at_cutoff(); compute_payment_unallocated_amount_at_date(); compute_applied_credit_document_amount(); _document_type_label(); _invoice_is_credit(); _invoice_item(); _invoice_open_items(); _payment_open_items(); get_open_documents_at_cutoff(); prepare_invitation_token(); compute_snapshot_hash(); verify_snapshot_hash(); create_balance_confirmation() | Pendiente |
| `cacao_accounting/contabilidad/balance_confirmation_bp.py` | _utcnow(); _as_utc(); _mark_expired(); check_desktop_mode(); _confirmation_companies(); _party_suggested_emails(); _handle_confirmation_creation(); crear_confirmacion_form(); ver_confirmacion(); enviar_confirmacion(); reenviar_confirmacion(); cancelar_confirmacion(); public_confirm_balance(); public_confirm_balance_verify(); _validated_public_response(); public_confirm_balance_respond() | Pendiente |
| `cacao_accounting/contabilidad/budget_import_service.py` | staging, validación e inserción cotejados para #1699; resto del servicio pendiente | Parcial |
| `cacao_accounting/contabilidad/budget_report_service.py` | agregaciones/dimensiones y filtros; rango cuenta omitido (#1237); acepta budget draft (#1785) | Parcial |
| `cacao_accounting/contabilidad/budget_service.py` | unicidad/dimensiones y totales cotejados para #1699; resto del servicio pendiente | Parcial |
| `cacao_accounting/contabilidad/ctas/__init__.py` | _value(); _is_group(); cargar_catalogos() | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/base_en.csv` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/base_en.json` | Claves: catalog, default_accounts | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/base_es.csv` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/base_es.json` | Claves: catalog, default_accounts | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/ifrs_smes_en.csv` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/ifrs_smes_en.json` | Claves: catalog, default_accounts | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/niif_pymes_es.csv` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/niif_pymes_es.json` | Claves: catalog, default_accounts | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/us_gaap.csv` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `cacao_accounting/contabilidad/ctas/catalogos/us_gaap.json` | Claves: catalog, default_accounts | Pendiente |
| `cacao_accounting/contabilidad/currency_guard.py` | reglas de activación/desactivación y moneda predeterminada revisadas | Parcial |
| `cacao_accounting/contabilidad/default_accounts.py` | delta revalidado con SHA vigente; 13/13 funciones inspeccionadas; consumidores y criterio de cuentas inactivas pendientes | Parcial |
| `cacao_accounting/contabilidad/exchange_rate_import_service.py` | validación, importación, duplicados y savepoint revisados; parsers/casos límite pendientes | Parcial |
| `cacao_accounting/contabilidad/exchange_revaluation_service.py` | run/void/period lock y caller de cierre mensual cotejados en HEAD actual; resto de métodos pendiente | Parcial |
| `cacao_accounting/contabilidad/fiscal_year_closing.py` | cálculo, multilibro, guards, reversa y referencias de cierre cotejadas; consumidores posteriores pendientes | Parcial |
| `cacao_accounting/contabilidad/forms.py` | además FormularioLibro/FiscalYear/AccountingPeriod y validación de fechas cotejados | Parcial |
| `cacao_accounting/contabilidad/gl/__init__.py` | gl_list(); gl_new() | Pendiente |
| `cacao_accounting/contabilidad/gl/static/gl.js` | update_form_from_entity, add_new_gl_line, delete_gl_line | Pendiente |
| `cacao_accounting/contabilidad/gl/templates/gl_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/gl/templates/gl_new.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/journal_repository.py` | add_journal(); get_journal(); list_journals(); list_journal_lines(); replace_journal_lines() | Pendiente |
| `cacao_accounting/contabilidad/journal_service.py` | evidencia en histórico | Parcial |
| `cacao_accounting/contabilidad/ledger_mapping_service.py` | validación de compañía/dirección y aplicación por libro cotejadas; dependencia de Book edit pendiente | Parcial |
| `cacao_accounting/contabilidad/posting_service.py` | writers receipt/issue/transfer/reconciliation y GL cotejados parcialmente; AR/AP no-op válido para StockEntry y transfer same-account `entries=[]`; conciliación con 2 SVL `-3/-6` y `0/-2` vs SLE `-3/-8` al cancelar distorsiona FIFO aunque bin vuelva 5/10, ampliado #1858; fan-out GL por línea/libro cotejado por dos revisores, sin discrepancia monetaria nueva; Unit/Project de otra compañía pueden llegar a GL en StockEntry no-reconciliation (#1890); líneas repetidas/transfer y matching línea↔SLE↔SVL #1858; amount-only #1878/#1879; batch cruzado #1754; límites #761/#1857/#1868/#1876/#1211/#444 | Parcial |
| `cacao_accounting/contabilidad/presupuesto.py` | CRUD/líneas/aprobación/cierre/import/reporte; draft validación servidor ausente (#1785) | Parcial |
| `cacao_accounting/contabilidad/project_capitalization_service.py` | elegibilidad, grouping, transacción por voucher y concurrencia de capitalización cotejados parcialmente | Parcial |
| `cacao_accounting/contabilidad/recurring_journal_service.py` | apply_recurring_template y validación de compañía/vigencia/duplicados cotejados; resto pendiente | Parcial |
| `cacao_accounting/contabilidad/routes.py` | además CRUD Book, ciclo fiscal y handlers del cierre mensual cotejados; accesos, transiciones y #1698/#1773/#1814; resto del módulo pendiente | Parcial |
| `cacao_accounting/contabilidad/services.py` | además flujo de cierre/reapertura y checks mensuales cotejados; taxonomía append-only de PeriodCloseCheck pendiente de criterio (#759); otras funciones pendientes | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/book.html` | detalle, estado primario y delete CSRF revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/book_crear.html` | form, smartSelect y validación de contexto revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/book_lista.html` | filtro, estados y acciones revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/centro-costo.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/centro-costo_crear.html` | blocks contenido; Alpine (10 directivas) | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/centro-costo_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/cuenta.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/cuenta_crear.html` | blocks contenido; Alpine (10 directivas) | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/cuenta_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad.html` | actions, estado y CSRF de delete revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad_crear.html` | campos create y formulario CSRF revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad_editar.html` | campos edit, CSRF y acción POST revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/entidad_lista.html` | listado, filtro y links mutadores revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/exchange_revaluation.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/exchange_revaluation_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/exchange_revaluation_nueva.html` | blocks contenido; Alpine (27 directivas) | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_ajuste.html` | POST con CSRF y campos de ajuste revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_auditoria.html` | tabla y expresiones de variación revisadas | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_lista.html` | toggle sin CSRF reproducido HTTP (#1648) | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_nuevo.html` | campos del formulario revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year.html` | detalle, flags de cierre y navegación cotejados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_closing_lista.html` | exposición de lista/entidades cotejada contra #1169 | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_closing_nuevo.html` | selector JS, relación company/FY y POST sin token reproducido (#1761) | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_crear.html` | CSRF, campos, x-data smartSelect y límites de cliente cotejados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/fiscal_year_lista.html` | búsqueda, loop, permisos visibles, POST delete CSRF cotejados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/journal.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/journal_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/journal_nuevo.html` | evidencia en histórico | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/moneda.html` | estado, datos y acciones visibles revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/moneda_crear.html` | CSRF, campos y marca predeterminada revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/moneda_lista.html` | filtros, indicadores y toggle CSRF revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/monthly_close_assistant.html` | formularios CSRF, dos smartSelect dependientes y pasos/checks cotejados; estados/tipos sin localización confirmados en #1814 | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/naming_series_lista.html` | acciones cotejadas con handlers y permisos parciales | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/naming_series_nueva.html` | formulario inspeccionado, expresiones restantes pendientes | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/periodo.html` | estado operacional/contable y enlaces de detalle cotejados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/periodo_crear.html` | CSRF, selector company/fiscal year, campos y panel de reapertura cotejados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/periodo_lista.html` | filtros, estados operativos/contables, acciones POST CSRF cotejados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/detail.html` | estados, controles por permiso, tablas de líneas/totales y acciones CSRF cotejados con rutas | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/form.html` | formulario/CSRF y smartSelect de año/libro dependientes de compañía cotejados; placeholder Jinja literal reproducido (#1780) | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/import.html` | dos fases/CSRF; CSV vacío deja lote validated pero la UI vuelve a carga y no expone import_id (#1491) | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/line_form.html` | choices de dimensiones, validación server-side y token CSRF cotejados con ruta/servicio | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/list.html` | búsqueda, paginación, estado y links de acciones cotejados con ruta; guards servidor necesarios | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/presupuestos/real_vs_budget.html` | filtros/smartSelect cotejados; POST reportes y status=approved como contrato cliente, render falla (#1782) | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/proyecto.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/proyecto_crear.html` | blocks contenido; Alpine (7 directivas) | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/proyecto_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/recurring_journal_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/recurring_journal_nuevo.html` | blocks contenido; Alpine (55 directivas) | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/recurring_journal_ver.html` | blocks contenido | Pendiente |
| `cacao_accounting/contabilidad/templates/contabilidad/tc.html` | vista/datos visibles revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/tc_crear.html` | CSRF, campos y validación visible revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/tc_importar.html` | contrato de encabezados, formatos y CSRF revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/tc_lista.html` | paginación, búsqueda y acciones revisadas | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/tree_macros.html` | toolbar, eventos tree-toggle y render recursivo revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/unidad.html` | contexto de unidad, padre/ruta y acciones revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/unidad_crear.html` | smartSelect y selector parent revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad/unidad_lista.html` | macro recursivo y toolbar revisados | Parcial |
| `cacao_accounting/contabilidad/templates/contabilidad_cash_flow_config.html` | formulario GET/POST, `account_ids`, valores dinámicos, CSRF y autorización cotejados con ruta y #1789 | Parcial |
| `cacao_accounting/inventario/routes.py` | listados StockEntry, alta/detalle/edición/duplicación/submit/cancel parciales; `inventario_entrada()` consulta solo `StockEntryItem` sin join Item/Batch ni `DocumentRelation` por línea (#1810/#1889); alta bodega: permisos/scope y criterios #1736/#1739; amount-only #1878; IntegrityError dinámico #1864; cancelación #1728/#1872; posting Cloud #1877, #1876/#761/#1811/#332/#1857; editores #1865/#1810/#1871/#1870; UOM #1747/#1182/#1183/#1736; Batch scope #1175; demás handlers pendientes | Parcial |
| `cacao_accounting/inventario/service.py` | UOM/categoría (#1847/#1850), Batch y validación serial/qty/estado/bodega cotejados; `validate_batch_serial()` omite un `batch_id` suministrado si el item no controla lote/vencimiento, permite SKU cruzado en StockEntry (#1754); retornos O2C/S2P y criterio sobre lote fuente también bajo #1754; factor UOM `1e-10` persiste cero por escala #1174/#1650, conversiones #1174/#1737; candidatos de rango Item/default supplier; carrera de lote duplicado puede dejar IntegrityError sin capturar en POST (sin repro); carreras #1178/#1306/#1653, cancelaciones #444/#1539/#1177; rebuild SVL pierde batch/consumed_layers y borra capas (#651/#1336/#1715), único caller `rebuild_stock_bins()` sin caller productivo hallado; resto helpers/callers pendientes | Parcial |
| `cacao_accounting/inventario/services.py` | alta/edición StockEntry, UOM, relaciones, compañía/bodega, reconciliación/snapshots cotejados; `_save_stock_entry_item()` copia batch del POST sin validar la pareja con artículo, en combinación con guard condicional de `validate_batch_serial()` permite SKU cruzado (#1754); POST acepta Unit/Project sin ownership por compañía (#1890); edición genérica borra dimensiones de cabecera omitidas, extensión comentada en #1863. Resto: `_form_decimal`/CHECK amount #1864; amount-only con batch #1878 (criterio); filas vacías #1871; renderer #1810; title #1838/#1870; duplicados #1857; snapshot #1863/#207; relation delete #1865; lote/serial #1215; UOM #841; pares de reuso siguen criterio; demás helpers pendientes | Parcial |
| `cacao_accounting/inventario/templates/inventario/articulo.html` | Jinja dinámico/escape, estado, links, campos Item, categorías (#1850), UOM, cuentas visibles, bodega filtrada, Party global y formas de imagen Cloud cotejados; `registro.item_type` muestra `goods/service` sin gettext (#1838); exposición de detalle/proveedor sin ACL `consultar`, botones que muestran 403 y alcance imagen en revisión (#1181/#1376); resto del contexto/caller pendiente | Parcial |
| `cacao_accounting/inventario/templates/inventario/entrada.html` | reabierta: el detalle pasa `docstatus` crudo a `detail_header`, así una solicitud de cancelación aprobable sigue mostrando «presentado» y la acción «Anular» (#1803/#1728); el árbol tras aprobación aceptada sigue bajo #1872 | Parcial |
| `cacao_accounting/inventario/templates/inventario/entrada_lista.html` | reabierta: usa `document_status_for`, que no encuentra `cancel_<doctype>` y omite «Anulación Pendiente» (#1803); otros hallazgos del listado #1838/#1861 y cero oculto siguen registrados | Parcial |
| `cacao_accounting/inventario/templates/inventario/entrada_nuevo.html` | alta cotejada; reabierta por contrato de edición: el contexto no precarga moneda/bodegas y la plantilla omite dimensiones de cabecera; la edición con líneas sigue bloqueada antes del render por #1810; pérdida potencial estática relacionada con #1863/#1890 | Parcial |
| `cacao_accounting/inventario/templates/inventario/stock_reconciliation_nuevo.html` | alta/snapshot cotejados; reabierta por edición: smart_select recibe initialValue vacío y su x-effect pisa company/cuenta/dimensiones preconfigurados; requiere volver a elegir company/serie y al guardar se pueden limpiar cuenta/dimensiones (#1835, comentario); límites estáticos sin ejecución de navegador | Parcial |
| `cacao_accounting/inventario/valuation_settings.py` | las 7 funciones y callers admin/posting revisados; choices moving_average/FIFO, validación y compañía inexistente; actividad incluye SLE/SVL aunque estén cancelados (conserva evidencia append-only); label dinámico «Costo promedio» sin msgid inglés (#1838); guard de cambio vs posting carece lock/CAS, candidato concurrente en #1881 (sin reproducción PG); revisar bootstrap/importadores y estrategia Tier 1 | Parcial |
| `cacao_accounting/compras/forms.py` | Party.name/#1722 y FormularioImportLandedCost/choices/defaults cotejados; handlers no usan validate_on_submit, guards del writer revisados | Parcial |
| `cacao_accounting/compras/purchase_invoice_draft_service.py` | 19 métodos revisados; no hay caller productivo/tests actuales (#1366); mode/source, finite values, active item, account company-scope, replay-payload equivalence y commit=False boundary requieren validación | Parcial |
| `cacao_accounting/compras/purchase_order_comparison_service.py` | claves, ocurrencias, rounds y origen cotejados; creador sin caller/ruta/registro detectado, posible código muerto por confirmar | Parcial |
| `cacao_accounting/compras/purchase_reconciliation_service.py` | 2-way/3-way totals, locks, replay y cancelación cotejados; asignación de devolución por artículo/cantidad no coteja batch de la recepción fuente (#1754); diferencia de índice MySQL revalidada sin issue (la misma invoice cancelada no admite retry normal); pending/as-of/reportes y resto pendiente (#1134/#1135/#1689) | Parcial |
| `cacao_accounting/compras/purchase_request_comparison_service.py` | recomendaciones, autorización, cobertura/cierre y generación de OC desde adjudicación cotejados; locks/idempotencia y resto pendientes | Parcial |
| `cacao_accounting/compras/purchase_sourcing_service.py` | rondas, participantes, adjudicación y cierre manual cotejados; UOM #1429/#1481; race/locks y resto pendiente | Parcial |
| `cacao_accounting/compras/routes.py` | writer/GET/edición/submit/cancel/duplicado/listas notas; #1438/#758/#1753/#1790/#1792/#1795; auth fuente GET y #1223 origen relacionado; devolución de recepción permite batch ajeno al artículo: `validate_batch_serial_draft()` solo exige presencia antes del writer (#1754); PO/solicitudes/RFQ/comparativo/tercero pendientes (#1302/#1496/#1532) | Parcial |
| `cacao_accounting/compras/services.py` | writer/edición factura y landed cost (moneda/base/rate/auditoría), persistencia serial de recibos/facturas y retornos cotejados; retorno persiste batch posteado sin cotejar propiedad artículo (causa junto a #1754); snapshot de Solicitud #1847; demás validadores pendientes | Parcial |
| `cacao_accounting/compras/templates/compras.html` | enlaces/badges cotejados con endpoints; ACL de cada destino pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/comparativo_ofertas.html` | estados, líneas, ofertas, CSRF y guards POST cotejados; cobertura/concurrencia pendientes | Parcial |
| `cacao_accounting/compras/templates/compras/comparativo_ofertas_lista.html` | tabla/estados/acciones/paginación cotejados con lista filtrada por compañía; destino de selección y demás estados pendientes | Parcial |
| `cacao_accounting/compras/templates/compras/comparativo_ordenes.html` | rondas, participantes, líneas y estados cotejados con acceso/POST; creación y alcance histórico sin cerrar | Parcial |
| `cacao_accounting/compras/templates/compras/comparativo_ordenes_seleccionar.html` | selección HTML/CSRF cotejada con ACL y validación de participantes; cambio de docstatus concurrente pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/comparativo_solicitud.html` | presentación de líneas/ofertas, controles por estado y POST para crear órdenes cotejados; resto pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/cotizacion_proveedor.html` | acciones por docstatus, CSRF, print/create, timeline y componentes compartidos cotejados; resto pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/cotizacion_proveedor_lista.html` | total nominal sin moneda (#1869); expresiones y callers restantes pendientes | Parcial |
| `cacao_accounting/compras/templates/compras/cotizacion_proveedor_nueva.html` | from_request/from_rfq, ronda, smart-select y source_api_url cotejados; criterios de tercero #1302/#1496/#1532; resto pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/factura_compra.html` | estados/acciones/moneda/líneas cotejados con rutas y macro compartida; resto pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/factura_compra_devolucion_lista.html` | nota debit/credit: estado/paginación incorrectos (#1792), CTA de alta sin origen requerido (#1795), total sin moneda; resto pendiente; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/compras/templates/compras/factura_compra_lista.html` | filtros/estado/paginacion y enlace a detalle cotejados con ruta; total no identifica moneda y combinacion de filtros queda pendiente de criterio; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/compras/templates/compras/factura_compra_nuevo.html` | x-data, ramas de origen/grid, preview #1438, CTA sin origen #1795 y selector credit_note_type sin selected en edición (#1790) cotejados; resto pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/import_landed_cost.html` | detalle, botones por estado y macros de documento cotejados con GET/transiciones; moneda de importes y macros compartidos pendientes | Parcial |
| `cacao_accounting/compras/templates/compras/import_landed_cost_lista.html` | filtros, paginación y navegación cotejados con listado por compañía; total sin moneda queda para dedupe transversal; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/compras/templates/compras/import_landed_cost_nuevo.html` | Alpine transactionForm, grilla de líneas de factura, cargos dinámicos, CSRF y origen cotejados; interfaz restante pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/orden_compra.html` | permisos de lectura, botones por docstatus, moneda/logística, líneas y macros flujo/adjuntos/auditoría cotejados; contrato compartido pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/orden_compra_lista.html` | filtros de estado/periodo, lista por compañía, enlaces y paginación cotejados; total sin moneda queda para dedupe transversal; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/compras/templates/compras/orden_compra_nuevo.html` | contexto `transactionForm`, smart-selects y `transaction_grid` cotejados con configuración de compra; resto de presentación pendiente | Parcial |
| `cacao_accounting/compras/templates/compras/proveedor.html` | contexto Party y detalle; llamada de historial sin company ligada a #1796 | Parcial |
| `cacao_accounting/compras/templates/compras/proveedor_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/compras/templates/compras/proveedor_nuevo.html` | checkpoint 2026-11-03: selector Alpine de grupo y alta Party | Parcial |
| `cacao_accounting/compras/templates/compras/purchase_reconciliation.html` | tabs 2-way/3-way, filtros de compañía, columnas y valores de service cotejados; formato de moneda y presentación integral pendientes | Parcial |
| `cacao_accounting/compras/templates/compras/purchase_reconciliation_panel.html` | grupos/estados y colapso inspeccionados; dos enlaces fallan al generar URL (hallazgo) | Parcial |
| `cacao_accounting/compras/templates/compras/recepcion.html` | status, acciones, moneda, líneas, document flow, adjuntos y timeline cotejados con GET; macros compartidos pendientes | Parcial |
| `cacao_accounting/compras/templates/compras/recepcion_lista.html` | normal/devoluciones, ACL de creación UI, status, filtros y paginación cotejados; Total crudo comparte patrón de moneda; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/compras/templates/compras/recepcion_nuevo.html` | `from_order` API, `from_receipt` retorno, formulario proveedor/bodega y grid cotejados; datos/líneas de devolución no se hidratan | Parcial |
| `cacao_accounting/compras/templates/compras/solicitud_compra.html` | blocks contenido | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_compra_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_compra_nueva.html` | header, CSRF y grid sin source cotejados con alta/edición; detalle y resto pendientes | Parcial |
| `cacao_accounting/compras/templates/compras/solicitud_cotizacion.html` | blocks contenido | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_cotizacion_lista.html` | blocks contenido | Pendiente |
| `cacao_accounting/compras/templates/compras/solicitud_cotizacion_nuevo.html` | `from_request`, selector Party y `transaction_grid` con source API revisados; vista y estados restantes pendientes | Parcial |
| `cacao_accounting/static/js/purchase-sourcing.js` | listener de selección y requisito visual de justificación cotejados con validación del servidor; resto S2P pendiente | Parcial |
| `cacao_accounting/ventas/routes.py` | alta/edición Party #1524, visibilidad detalle #1525, acciones de contacto/dirección #1282/#1649 y transiciones O2C revisadas | Parcial |
| `cacao_accounting/ventas/services.py` | escritores Party y contratos O2C, persistencia serial en DeliveryNote/SalesInvoice y retornos cotejados; líneas SalesRequest/Quotation #1847; #1722/#1524; validadores pendientes | Parcial |
| `cacao_accounting/ventas/templates/ventas.html` | revisión previa de página, navegación/badges y endpoints en checkpoint de entrada O2C | Parcial |
| `cacao_accounting/ventas/templates/ventas/cliente.html` | detalle Jinja, historial sin company #1796 y panel de adjuntos global compartido #1284; demás expresiones pendientes | Parcial |
| `cacao_accounting/ventas/templates/ventas/cliente_lista.html` | Jinja/list_filters/paginación y consulta `CompanyParty` por compañías autorizadas cotejadas | Parcial |
| `cacao_accounting/ventas/templates/ventas/cliente_nuevo.html` | checkpoint 2026-11-03: selector Alpine de grupo y alta Party | Parcial |
| `cacao_accounting/ventas/templates/ventas/cotizacion.html` | detalle Jinja y `_require_sales_document_access` cotejados en checkpoint de entrada O2C | Parcial |
| `cacao_accounting/ventas/templates/ventas/cotizacion_lista.html` | listado/`_paginate_list` y patrón total sin moneda cotejados en checkpoint de entrada O2C; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/ventas/templates/ventas/cotizacion_nuevo.html` | rama desde solicitud, payload Alpine y contrato de alta revisados; guard de origen GET y dependencias compartidas pendientes | Parcial |
| `cacao_accounting/ventas/templates/ventas/entrega.html` | detalle de remisión, moneda y ruta de consulta cotejados en checkpoint de entrada O2C | Parcial |
| `cacao_accounting/ventas/templates/ventas/entrega_lista.html` | listado/`_paginate_list` y total crudo sin moneda cotejados en checkpoint de entrada O2C; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/ventas/templates/ventas/entrega_nuevo.html` | ramas origen/devolución y contrato de alta revisados; ACL dual y validación de bodega/retorno pendientes | Parcial |
| `cacao_accounting/ventas/templates/ventas/factura_venta.html` | detalle fiscal, importes con moneda y ruta cotejados en checkpoint de entrada O2C | Parcial |
| `cacao_accounting/ventas/templates/ventas/factura_venta_devolucion_lista.html` | endpoints/filters; #1792 por paginación y tipo para helper de estado, evidencia agregada al issue; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/ventas/templates/ventas/factura_venta_lista.html` | listado/`_paginate_list` y total crudo sin moneda cotejados en checkpoint de entrada O2C; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/ventas/templates/ventas/factura_venta_nuevo.html` | ramas origen/tipo, CSRF, Alpine y contratos de alta/previsualización cotejados; permisos de origen GET y dependencias compartidas pendientes | Parcial |
| `cacao_accounting/ventas/templates/ventas/orden_venta.html` | detalle de orden, importes con moneda y ruta cotejados en checkpoint de entrada O2C | Parcial |
| `cacao_accounting/ventas/templates/ventas/orden_venta_lista.html` | listado/`_paginate_list` y total crudo sin moneda cotejados en checkpoint de entrada O2C; total nominal sin moneda en lista (#1869) | Parcial |
| `cacao_accounting/ventas/templates/ventas/orden_venta_nuevo.html` | ramas de origen, configuración Alpine y contrato de alta cotejados; validación de macros/JS compartidos y guards de origen sigue pendiente | Parcial |
| `cacao_accounting/ventas/templates/ventas/solicitud_venta.html` | detalle de pedido de venta, moneda y guard de consulta cotejados en checkpoint de entrada O2C | Parcial |
| `cacao_accounting/ventas/templates/ventas/solicitud_venta_lista.html` | listado/`_paginate_list` y total crudo sin moneda cotejados en checkpoint de entrada O2C | Parcial |
| `cacao_accounting/ventas/templates/ventas/solicitud_venta_nuevo.html` | contrato de creación y líneas revisado; protección por compañía, catálogo y controles compartidos pendientes de cierre | Parcial |
| `cacao_accounting/bancos/__init__.py` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/cash_forecast.py` | 20/20 funciones de ruta/helper revalidadas en 2026-11-03; caller de importación y estados revisados, CTM transversal pendiente | Parcial |
| `cacao_accounting/bancos/cash_forecast_service.py` | 20/20 funciones de servicio revisadas en 2026-11-03; cálculo y contratos financieros cotejados, CTM transversal pendiente | Parcial |
| `cacao_accounting/bancos/forms.py` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/reconciliation_service.py` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/routes.py` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/services.py` | helper de numeración, cancelación de pagos y delta de locks de caja chica cotejados; #1290 conserva una ventana entre draft commit y vínculo idempotente; resto pendiente | Parcial |
| `cacao_accounting/bancos/statement_service.py` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos.html` | blocks contenido | Pendiente |
| `cacao_accounting/bancos/templates/bancos/banco.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/banco_cuenta.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/banco_cuenta_lista.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/banco_cuenta_nuevo.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/banco_lista.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/banco_nuevo.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/caja_chica.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/caja_chica_gasto_nuevo.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/caja_chica_nuevo.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/caja_chica_reposicion_nueva.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/caja_chica_vale_nuevo.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_comparar.html` | selección/estados/tabla/escape cotejados en 2026-11-03; callers de layout y CTM restantes pendientes | Parcial |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_detalle.html` | estado, acciones/CSRF, matriz y detalle manual cotejados en 2026-11-03; macros/layout y CTM restantes pendientes | Parcial |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_entradas.html` | expresiones de compañía, pronóstico, filas y acciones cotejadas en 2026-11-03; layout y CTM restantes pendientes | Parcial |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_lista.html` | filtros, loops y presentación de estados cotejados en 2026-11-03; layout y CTM restantes pendientes | Parcial |
| `cacao_accounting/bancos/templates/bancos/cash_forecast_nuevo.html` | formulario y valores de compañía/FY/periodicidad cotejados en 2026-11-03; layout y CTM restantes pendientes | Parcial |
| `cacao_accounting/bancos/templates/bancos/conciliacion_facturas_pagos.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/nota_nueva.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/pago.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/pago_lista.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/pago_nuevo.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/transaccion_lista.html` | evidencia en histórico | Parcial |
| `cacao_accounting/bancos/templates/bancos/transferencia_nueva.html` | evidencia en histórico | Parcial |
| `cacao_accounting/messaging/__init__.py` | revisado completo en batch 7 (checkpoint 2026-11-03): solo docstring | Parcial |
| `cacao_accounting/messaging/email.py` | envío, reintento, configuración y destinatarios cotejados; atomicidad/semántica externa pendiente | Parcial |
| `cacao_accounting/portal/__init__.py` | _is_user_admin(); check_portal_access(); customer_dashboard(); customer_invoice(); customer_order(); customer_quotation(); customer_delivery(); supplier_dashboard(); supplier_invoice(); supplier_order(); supplier_quotation(); supplier_receipt() | Pendiente |
| `cacao_accounting/portal/templates/portal/base_portal.html` | blocks contenido | Pendiente |
| `cacao_accounting/portal/templates/portal/customer_dashboard.html` | blocks contenido | Pendiente |
| `cacao_accounting/portal/templates/portal/delivery_detail.html` | blocks contenido | Pendiente |
| `cacao_accounting/portal/templates/portal/invoice_detail.html` | blocks contenido | Pendiente |
| `cacao_accounting/portal/templates/portal/order_detail.html` | blocks contenido | Pendiente |
| `cacao_accounting/portal/templates/portal/quotation_detail.html` | blocks contenido | Pendiente |
| `cacao_accounting/portal/templates/portal/receipt_detail.html` | blocks contenido | Pendiente |
| `cacao_accounting/portal/templates/portal/supplier_dashboard.html` | blocks contenido | Pendiente |
| `cacao_accounting/printing/admin_routes.py` | batch 7: CRUD/plan y set-default; #1845 _is_print_admin fail-open | Parcial |
| `cacao_accounting/printing/context.py` | batch 7: builders 24 tipos + samples; mis options sin consumidores | Parcial |
| `cacao_accounting/printing/exceptions.py` | batch 7: sin hallazgo | Parcial |
| `cacao_accounting/printing/models.py` | batch 7: PrintTemplate/Version/JobLog/PublicDocumentValidation; PrintTemplateVersion sin unique (template_id, version) | Parcial |
| `cacao_accounting/printing/registry.py` | batch 7: 24 tipos con guard de módulo; #1844 sample builder de compra usa el de venta | Parcial |
| `cacao_accounting/printing/seed.py` | batch 7: seeds system_default_*, label no escapada en la plantilla base (candidato relativo: sin repro) | Parcial |
| `cacao_accounting/printing/service.py` | batch 7: Jinja SandboxedEnvironment; autorización por document.company + party (#1562 y ya registrado) + exige_acceso_compania | Parcial |
| `cacao_accounting/printing/settings.py` | batch 7: config en CacaoConfig; fail-open default True con endpoint público | Parcial |
| `cacao_accounting/printing/snippets.py` | batch 7: 3 snippets inline; sin hallazgo | Parcial |
| `cacao_accounting/printing/validation.py` | batch 7: tokens URL-safe, hash canónico, estados; sin hallazgo | Parcial |
| `cacao_accounting/printing/validators.py` | batch 7: blacklist regex <script> y expresiones inline (sin sanitizador HTML completo — decisión de slug del equipo) | Parcial |
| `cacao_accounting/query_tools/__init__.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/audit.py` | _serialize_value(); serialize_parameters(); log_query_tool_event() | Pendiente |
| `cacao_accounting/query_tools/bootstrap.py` | load_query_tools() | Pendiente |
| `cacao_accounting/query_tools/context.py` | class QueryContext | Pendiente |
| `cacao_accounting/query_tools/decorators.py` | class QueryTool; _validate_read_only(); query_tool() | Pendiente |
| `cacao_accounting/query_tools/errors.py` | class ErrorCode; class QueryToolError (métodos: __str__, to_dict) | Pendiente |
| `cacao_accounting/query_tools/handlers/accounting.py` | list_accounting_periods(); search_accounts(); get_trial_balance(); get_general_ledger() | Pendiente |
| `cacao_accounting/query_tools/handlers/advanced.py` | inventory.get_transfers y accounting.get_budget_variance, permisos/payload revisados | Parcial |
| `cacao_accounting/query_tools/handlers/aging.py` | class AgingQuery; get_aging_result(); _load_aging_report(); _load_documents(); _paginated_result(); _document_model(); _aging_item() | Pendiente |
| `cacao_accounting/query_tools/handlers/analytics.py` | _date(); _json(); _validate(); _envelope(); get_kpi_snapshot_tool(); compare_periods_tool(); get_trend_tool(); get_concentration_tool() | Pendiente |
| `cacao_accounting/query_tools/handlers/audit_trail.py` | get_document_timeline_handler(); get_user_activity_summary() | Pendiente |
| `cacao_accounting/query_tools/handlers/banking.py` | _get_gl_balances(); get_banking_accounts(); get_banking_transactions() | Pendiente |
| `cacao_accounting/query_tools/handlers/companies.py` | list_companies() | Pendiente |
| `cacao_accounting/query_tools/handlers/configuration.py` | _is_admin(); list_admin_configuration() | Pendiente |
| `cacao_accounting/query_tools/handlers/discovery.py` | checkpoint dimensión analítica 2026-11-03 | Parcial |
| `cacao_accounting/query_tools/handlers/documents.py` | get_document_flow(); get_related_documents(); _document_context(); get_document_details_handler(); get_document_lines_handler(); get_document_status_handler() | Pendiente |
| `cacao_accounting/query_tools/handlers/operational.py` | _parse_date(); _decimal(); _with_provenance(); _payment_items(); search_payments(); get_unapplied_payments(); get_payment_applications(); search_document_relations(); search_audit_events(); get_revaluations() | Pendiente |
| `cacao_accounting/query_tools/handlers/payables.py` | get_payables_aging(); get_payables_open_documents() | Pendiente |
| `cacao_accounting/query_tools/handlers/receivables.py` | get_receivables_aging(); get_receivables_open_documents() | Pendiente |
| `cacao_accounting/query_tools/handlers/treasury.py` | _json(); _verify_forecast(); list_cash_forecasts(); get_cash_forecast(); compare_cash_forecasts(); get_maturity_schedule_handler() | Pendiente |
| `cacao_accounting/query_tools/pagination.py` | class PaginatedResult (métodos: total_pages, has_next_page, to_dict); paginate() | Pendiente |
| `cacao_accounting/query_tools/permissions.py` | scope accounting reports y fail-closed compañía verificados para #1783 | Parcial |
| `cacao_accounting/query_tools/registry.py` | class Registry (métodos: __init__, register, get, list_tools, get_tools_for_permissions, _tool_to_schema, get_count); _serialize_schema() | Pendiente |
| `cacao_accounting/query_tools/schemas/accounting.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/schemas/audit_trail.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/schemas/banking.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/schemas/common.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/schemas/companies.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/schemas/documents.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/schemas/payables.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/query_tools/schemas/receivables.py` | Módulo Python: constantes, listeners o declaraciones pendientes | Pendiente |
| `cacao_accounting/reportes/__init__.py` | __getattr__(); __dir__() | Pendiente |
| `cacao_accounting/reportes/analytics.py` | _decimal(); _percentage(); _invoice_base_amount(); _invoice_total(); _convert_to_ledger_currency(); _gl_totals(); metric_value(); _document_base_factor(); _stock_movement_balances(); _historical_inventory_value(); get_kpi_snapshot(); compare_periods(); get_trend(); get_concentration(); _share_percentage(); _concentration_totals(); _concentration_invoice_query(); _concentration_item_query() | Pendiente |
| `cacao_accounting/reportes/cash_flow.py` | 4/13 funciones de clasificación y persistencia de mapeos cotejadas con modelo/ruta; cálculo y estado del EFE pendientes | Parcial |
| `cacao_accounting/reportes/documentos.py` | _decimal(); _status(); _resolve(); get_document_details(); get_document_lines(); get_document_status() | Pendiente |
| `cacao_accounting/reportes/helpers.py` | evidencia en histórico | Parcial |
| `cacao_accounting/reportes/internal_control.py` | class InternalControlFilters; control_report_access(); _date_bounds(); _evidence_query(); get_internal_control_report() | Pendiente |
| `cacao_accounting/reportes/periods.py` | class PeriodRange (métodos: single_period, label); list_periods_for_company(); current_period_for_company(); period_ids_in_range(); resolve_period(); resolve_period_range(); reject_manual_date_overrides(); _safe_date() | Pendiente |
| `cacao_accounting/reportes/routes.py` | evidencia en histórico; ruta /reports/serials cotejada con filtros operativos y get_serial_report, resto de permisos/contratos pendiente | Parcial |
| `cacao_accounting/reportes/semantic.py` | _decimal(); _signed(); _base_amount(); _document_base_factor(); _document_base_amount(); _document_base_outstanding_amount(); _company_currency_map(); _bounded(); get_sales_analysis(); get_purchase_analysis(); get_receivables_analysis(); get_payables_analysis(); get_settlement_analysis(); get_document_relations(); get_audit_events(); _report_items(); get_inventory_slow_moving_analysis(); get_inventory_negative_analysis(); get_inventory_turnover_analysis(); get_inventory_transfer_analysis() | Pendiente |
| `cacao_accounting/reportes/services.py` | #1664/#1783/#1134; get_batch_report (#1590) y get_serial_report cotejados; serial report basa ubicación actual en warehouse y omite entregados sin bodega; semántica restante pendiente | Parcial |
| `cacao_accounting/reportes/templates/reportes/cash_flow_blocked.html` | blocks contenido | Pendiente |
| `cacao_accounting/reportes/templates/reportes/financial_report.html` | blocks contenido; Alpine (4 directivas) | Pendiente |
| `cacao_accounting/reportes/templates/reportes/internal_control.html` | blocks contenido | Pendiente |
| `cacao_accounting/reportes/templates/reportes/operational_report.html` | evidencia en histórico | Parcial |
| `cacao_accounting/reportes/templates/reportes/report_macros.html` | macros period_range_field | Pendiente |
| `cacao_accounting/reportes/templates/reportes/report_pdf.html` | Jinja/HTML dinámico (26 expresiones/controles) | Pendiente |
| `cacao_accounting/reportes/templates/reportes/report_table.html` | blocks contenido | Pendiente |
| `.coveragerc` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `.dockerignore` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `.git-blame-ignore-revs` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `.github/FUNDING.yml` | Claves/secciones: github, patreon, open_collective, ko_fi, tidelift, community_bridge, liberapay, issuehunt, otechie, custom | Pendiente |
| `.github/workflows/ci.yml` | evidencia en histórico | Parcial |
| `.github/workflows/databases.yml` | evidencia en histórico | Parcial |
| `.github/workflows/lint.yml` | evidencia en histórico | Parcial |
| `.github/workflows/publish.yml` | Claves/secciones: name, on, workflow_run, workflows, types, branches, jobs, pypi-publish, if, runs-on, environment, url, permissions, id-token, steps, uses, with, python-version, node-version, run, continue-on-error | Pendiente |
| `.github/workflows/python.yml` | evidencia en histórico | Parcial |
| `.gitignore` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `.mypy.ini` | Claves/secciones: ignore_missing_imports, show_error_codes | Pendiente |
| `.pydocstyle` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `.replit` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `Dockerfile` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `MANIFEST.in` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `babel.cfg` | Claves/secciones: keywords, extensions | Pendiente |
| `cacao_accounting/misc/ejemplos/cacao-accounting.unit` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `cacao_accounting/misc/ejemplos/nginx.conf` | Claves de configuración pendientes | Pendiente |
| `cacao_accounting/static/manifest.json` | Claves: name, short_name, start_url, display, background_color, theme_color, orientation, scope, icons | Pendiente |
| `cacao_accounting/static/package-lock.json` | Claves: name, version, lockfileVersion, requires, packages | Pendiente |
| `cacao_accounting/static/package.json` | Claves: name, version, description, main, scripts, repository, author, license, bugs, homepage, dependencies, devDependencies, overrides | Pendiente |
| `codecov.yml` | Claves/secciones: fixes | Pendiente |
| `development.txt` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `docker-compose.yml` | Claves/secciones: services, app, build, context, dockerfile, ports, environment, depends_on, db, condition, cache, image, volumes, healthcheck, test, interval, timeout, retries, postgres_data, redis_data | Pendiente |
| `docker-entry-point.sh` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `docs.txt` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `docs/examples/cacao-accounting.service` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `docs/oci_files/Caddyfile` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `docs/oci_files/mysql.sh` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `docs/oci_files/psql.sh` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `docs/theme_override_home/home.html` | blocks tabs, content, footer | Pendiente |
| `docs/theme_override_home/main.html` | blocks libs, announce, footer, social | Pendiente |
| `mkdocs.yml` | Claves/secciones: site_name, theme, name, custom_dir, language, favicon, logo, palette, primary, accent, icon, repo, features, repo_url, repo_name, copyright, nav, plugins, docs_structure, languages, default, build, extra, social, link, markdown_extensions, alternate_style, emoji_index, emoji_generator | Pendiente |
| `pyproject.toml` | Claves/secciones: name, description, readme, requires-python, authors, license, keywords, classifiers, dynamic, extra-formats, cloud, cacaoctl, include-package-data, dependencies, version, where, include, exclude, namespaces, requires, build-backend, line-length, target-version, extend-exclude, select, ignore, max-line-length, extend-ignore, disable, python_version, ignore_missing_imports, follow_imports, disable_error_code, addopts, markers, norecursedirs | Pendiente |
| `replit.nix` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `requirements.txt` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `run.py` | caller de setup trata User existente como indicador de bootstrap completo (#1848); resto de launcher pendiente | Parcial |
| `scripts/run_server.sh` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `scripts/run_test.sh` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `scripts/run_tests_by_file.sh` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `scripts/update_translations.sh` | Lógica ejecutable/dinámica según superficie inventariada | Pendiente |
| `setup.cfg` | Claves/secciones: max-line-length, extend-ignore, exclude, license_files | Pendiente |
| `cacao_accounting/migrations/20261015_0001_audit_hash_version.py` | upgrade idempotente y downgrade reproducido; al quitar `hash_version`, el lector anterior v1 no puede validar filas v2; criterio de soporte rollback pendiente, relacionado pero no duplicado de #926 | Parcial |
