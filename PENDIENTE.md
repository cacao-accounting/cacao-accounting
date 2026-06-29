# PENDIENTE - Cacao Accounting (Backlog Priorizado)

## Seguimiento 2026-06-29 (SonarCloud API - en curso)
- [x] Consultar la API publica de SonarCloud para enumerar issues abiertos del proyecto.
- [x] Confirmar el volumen de hallazgos activos antes de tocar hotspots de negocio.
- [x] Aplicar una primera limpieza de bajo riesgo en `journal_nuevo.html` y `cacaoaccounting.css`.
- [x] Cerrar un issue menor adicional en `imports/services/import_service.py`.
- [x] Cerrar un issue menor adicional en `bancos/templates/bancos/pago_nuevo.html`.
- [x] Cerrar un issue menor adicional en `contabilidad/templates/contabilidad/journal_nuevo.html`.
- [x] Cerrar un issue menor adicional en `bancos/__init__.py`.
- [x] Cerrar un issue menor adicional en `compras/__init__.py`.
- [x] Cerrar un issue menor adicional en `ventas/__init__.py`.
- [x] Cerrar un issue menor adicional en `version/__init__.py`.
- [x] Cerrar un issue menor adicional en `document_flow/service.py`.
- [x] Cerrar un issue menor adicional en `static/js/smart-select.js`.
- [x] Cerrar un issue menor adicional en `static/js/transaction-form.js`.
- [x] Cerrar un issue menor adicional en `bancos/templates/bancos/pago_nuevo.html`.
- [x] Cerrar un issue menor adicional en `contabilidad/templates/contabilidad/journal_nuevo.html`.
- [x] Cerrar un issue menor adicional en `static/js/smart-select.js` sobre manejo explicito de errores.
- [x] Cerrar un issue menor adicional en `static/js/transaction-form.js` sobre manejo explicito de errores.
- [x] Cerrar dos issues `Web:TableWithoutCaptionCheck` en `imports/templates/imports/index.html` y `detail.html`.
- [x] Cerrar un issue `javascript:S2004` en `static/js/smart-select.js` extrayendo la busqueda de opciones por valor normalizado.
- [ ] Seguir cerrando issues SonarCloud por prioridad, empezando por los de menor riesgo semantico y luego los de mayor complejidad tecnica.

## Seguimiento 2026-06-27 (Auditoria de pendientes - completado)
- [x] Contrastar los pendientes abiertos contra el codigo fuente antes de actualizar el backlog.
- [x] Marcar como completada la paridad funcional de formularios transaccionales para rutas `edit`/`duplicate` y transiciones de estado en POST.
- [x] Mantener abiertos los puntos que siguen parciales o pendientes: auditoria homogenea, filtros de listados, `LedgerMappingRule`, reportes legacy, drill-down/exportaciones universales y diagrama grafico de trazabilidad.

## Seguimiento 2026-06-27 (Filtros de listados - completado)
- [x] Agregar filtros GET `search` y `status` en listados transaccionales de Compras, Ventas y Bancos.
- [x] Agregar busqueda simple en listados maestros principales de terceros, bancos, cuentas bancarias y transacciones bancarias.
- [x] Conservar filtros al navegar paginacion y exponer controles Buscar/Limpiar en templates.
- [x] Cubrir busqueda y estado con prueba focal por modulo.

## Seguimiento 2026-06-18 (Refresh visual global - completado)
- [x] Aplicar mejora visual global sin tocar logica de negocio ni flujos transaccionales.
- [x] Modernizar navbar, sidebar, cards, grids de modulo, tablas, formularios y botones desde el CSS compartido.
- [x] Remover la franja superior de color en tarjetas de modulo para una apariencia mas sobria.
- [x] Mantener compatibilidad con tema claro/oscuro y responsive movil.
- [x] Validar render focal de vistas principales.

## Seguimiento 2026-06-18 (Actualizacion de contexto - completado)
- [x] Releer y consolidar el contexto del proyecto a partir de los documentos base de dominio y estado.
- [x] Sincronizar `SESSIONS.md` como bitacora cronologica de decisiones y hitos.
- [x] Refrescar `ESTADO_ACTUAL.md` para reflejar el contexto vigente del proyecto.
- [x] Mantener `PENDIENTE.md` como backlog priorizado sin introducir cambios funcionales.

## Seguimiento 2026-05-27 (Servicio reusable de impresion - completado)
- [x] Integrar via `merge --squash` la rama remota de impresion reutilizable y validacion QR.
- [x] Endurecer `PrintService` con registry obligatorio, sandbox Jinja2, `StrictUndefined`, resolucion compania/global y logging de intentos.
- [x] Normalizar contextos serializables en ingles y raices estables por tipo documental.
- [x] Agregar endpoints operativos de preview/PDF y endpoint publico de validacion QR.
- [x] Completar seeds/documentacion minima de formatos de impresion.
- [x] Validar pruebas focales de impresion/QR y calidad focal con Black, Ruff, Flake8 y Mypy.

## Seguimiento 2026-05-26 (Bandit - completado)
- [x] Remover literales de fallback de `SECRET_KEY` reportados por B105.
- [x] Reemplazar `assert` de runtime por validaciones explicitas en settlement y line import.
- [x] Ejecutar `bandit -r cacao_accounting` en verde sin skips nuevos.
- [x] Validar formato/lint focal y pruebas focales relacionadas.

## Seguimiento 2026-05-26 (Playwright E2E - completado)
- [x] Verificar Playwright/Chromium disponible en el `venv` local.
- [x] Mantener los tests Playwright marcados para omitirse si Playwright no esta disponible.
- [x] Agregar prueba Playwright focal para Smart Select de compania en comprobante contable.
- [x] Corregir el hidden `company` que podia quedar como `[object Object]` en navegador real.
- [x] Ajustar fixture E2E de comprobantes para sembrar moneda funcional activa y libros con moneda.
- [x] Validar suites Playwright y journal E2E en verde.

## Seguimiento 2026-05-26 (QA staged monedas/comprobante/maestros - completado)
- [x] Centralizar validaciones de monedas activas y bloqueo de desactivacion critica.
- [x] Corregir setup para activar/default la moneda funcional sin desactivar automaticamente monedas adicionales.
- [x] Validar compania existente/activa en comprobantes contables.
- [x] Corregir Smart Select para propagar hidden value, eventos `input/change` y estado `filled`.
- [x] Completar validaciones de monedas activas en comprobantes, libros y tasas de cambio.
- [x] Agregar soporte de padre para cuentas contables con filtro `is_group` y validaciones de ciclo/estado/entidad.
- [x] Agregar soporte de padre para centros de costo con filtro `is_group` y validaciones de ciclo/estado/entidad.
- [x] Guardar y mostrar moneda explicita del PPTO de proyectos.
- [x] Agregar pruebas focales de regresion para los issues QA cerrados.

## Seguimiento 2026-05-24 (UI responsive documental - completado)
- [x] Mover acciones de detalle a menu compacto en pantallas pequenas para documentos compartidos por Contabilidad, Bancos, Compras e Inventario/Almacen.
- [x] Convertir Historial del documento en panel colapsable cerrado por defecto.
- [x] Convertir Colaboracion en panel colapsable cerrado por defecto.
- [x] Alinear visualmente Historial, Colaboracion y Flujo documental con la misma tarjeta/cabecera colapsable.

## Seguimiento 2026-05-24 (Modo Desktop/Cloud sin migraciones - completado)
- [x] Centralizar deteccion desktop/cloud/single-entity en `runtime_mode.py`.
- [x] Mantener `config.MODO_ESCRITORIO` como alias compatible sin duplicar checks.
- [x] Bloquear usuarios adicionales en desktop y ocultar la accion de nuevo usuario.
- [x] Bloquear segunda entidad en desktop o con `CACAO_ACCOUNTING_FORCE_SINGLE_ENTITY=true`.
- [x] Agregar `DocumentTask` al ORM sin crear migracion Alembic.
- [x] Implementar comentarios y tareas cloud con validaciones de documento, permisos, usuario activo, estados y prioridades.
- [x] Exponer endpoints de comentarios, tareas, cambios de estado y `Mis tareas`.
- [x] Integrar panel colaborativo reusable en documentos con timeline visible inicial.
- [x] Registrar comentarios y acciones de tarea en `AuditTrail`.
- [x] Cubrir runtime, desktop, single-entity y flujo cloud con pruebas focales.

## Seguimiento 2026-05-24 (Dashboard Ejecutivo UI - completado)
- [x] Corregir la tarjeta de Inventario para que no ocupe ancho completo por una regla CSS basada en posicion.
- [x] Reemplazar reglas fragiles `nth-child` por clases semanticas de modulo en el dashboard.
- [x] Cubrir el render para evitar regresion del layout por posicion.

## Seguimiento 2026-05-24 (Acceso contable por libro - completado)
- [x] Integrar selectivamente la rama remota de limpieza multiledger sin traer cambios ajenos de reportes operativos.
- [x] Agregar matriz `UserBookAccess` para permisos granulares por libro contable.
- [x] Aplicar el filtro por libro solo al modulo de Contabilidad.
- [x] Mantener Bancos, Compras, Inventario y Ventas trabajando sobre todos los libros activos por defecto.
- [x] Filtrar libros disponibles en el selector de comprobantes contables segun permisos del usuario.
- [x] Asegurar que los reportes financieros contables usen un libro por defecto autorizado.
- [x] Cubrir con pruebas que un modulo operativo no se bloquee por parametros `ledger`.

## Seguimiento 2026-05-24 (Dashboard Ejecutivo - completado)
- [x] Validar acceso temporal usuario-compañía antes de devolver datos del dashboard.
- [x] Validar que el periodo contable pertenece a la compañía seleccionada.
- [x] Normalizar la respuesta del API en `sections` con visibilidad uniforme por módulo.
- [x] Ampliar métricas de Contabilidad, Bancos, Compras, Inventario y Ventas.
- [x] Renombrar el widget de inventario a **Menor existencia** usando `StockBin` mientras no exista stock mínimo formal.
- [x] Rediseñar `/app` con secciones ejecutivas, KPIs, widgets, acciones rápidas y estados vacíos.
- [x] Ampliar pruebas focales de seguridad, permisos, estados vacíos, métricas y render.

## Seguimiento 2026-05-24 (Mantenibilidad importacion/perfil - completado)
- [x] Refactorizar `validate_lines()` como orquestador y extraer validaciones a helpers privados.
- [x] Ampliar cobertura de importacion de lineas para doctype, compania, limites, tipos y datos maestros.
- [x] Refactorizar `profile()` separando render, actualizacion de perfil y cambio de contrasena.

## Seguimiento 2026-05-24 (Mantenibilidad motores fiscales/pagos - completado)
- [x] Refactorizar `_build_payment_context` para separar direccion del pago, montos de liquidacion, referencias contables y reglas fiscales.
- [x] Simplificar `_tax_rules_from_template` usando helpers y `match/case` para decisiones fiscales heredadas.
- [x] Refactorizar `RuleResolver.resolve` usando helpers y `match/case` para estrategias de merge.
- [x] Refactorizar `_calculate_share` de Landed Cost usando `match/case` por metodo de prorrateo.
- [x] Refactorizar `_map_settlement_event` para separar balance, banco, retenciones y ajustes de liquidacion.
- [x] Renombrar acumuladores `debits`/`credits` en mapper para evitar shadowing.

## Seguimiento 2026-05-24 (Flujo Documental Expandible - completado)
- [x] Registrar `journal_entry` dentro del árbol de flujo documental y mostrarlo en la vista de comprobante contable.
- [x] Crear relaciones contables desde líneas de journal con `internal_reference` / `internal_reference_id`.
- [x] Garantizar que `apply_advance_to_invoice` cree `PaymentReference` y `DocumentRelation`.
- [x] Eliminar la implementación inline duplicada de `documentFlowTree`.

## Seguimiento 2026-05-23 (Conciliaciones - completado)
- [x] Conciliacion masiva de facturas contra pagos (interfaz dedicada).
- [x] Implementar "Stock Reconciliation" para ajuste de valuacion (cantidad + valor objetivo).

## Seguimiento 2026-05-27 (Servicio reusable de impresion y QR - completado)
- [x] Integrar por `merge --squash` la rama remota de impresion reusable preservando `PENDIENTE.md`.
- [x] Consolidar modelos, registry, servicio, rutas, seeds, contextos Jinja, PDF y administracion de plantillas.
- [x] Implementar configuracion administrable de External Document Validation en `CacaoConfig`.
- [x] Renombrar semanticamente `company_id` a `company_code` en los modelos nuevos de impresion/validacion.
- [x] Endurecer QR: drafts no generan ni actualizan token, `segno` es dependencia explicita, estados tecnicos y view publica segura.
- [x] Ampliar documentos validables y calculo de `line_count` / `grand_total` por tablas reales.
- [x] Documentar configuracion QR, dependencia, estados y datos publicos permitidos.

## Seguimiento 2026-05-22 (Payment Entry - completado)
- [x] Acciones `Crear` en detalle de solicitud de compra (`purchase_request` → cotización de proveedor) — pre-existing gap en `ALLOWED_FLOWS`.
- [x] Acción `Crear Entrada de Almacén` desde recepción de compra — pre-existing gap en `ALLOWED_FLOWS`.

## Seguimiento 2026-05-21 (Matriz de relaciones operativas - completado)
- [x] Ejecutar implementación completa de la matriz definida en `modulos/relaciones.md` mediante `document_flow`, acciones dinámicas en trazabilidad y matriz vigente alineada al registro.
- [x] Completar expansión de `create_actions` y `ALLOWED_FLOWS` para los pares funcionales acordados y soportados por rutas actuales.
- [x] Completar backend de creación/prefill básico para acciones `Crear` soportadas, incluyendo notas débito/crédito, devoluciones, anticipos y pagos/reembolsos.
- [x] Añadir cobertura de pruebas para caminos de devolución y notas débito/crédito en Compras y Ventas.

## Seguimiento 2026-05-19 (MVP Fiscal)
- [ ] Ampliar cobertura de pruebas funcionales por documento del MVP fiscal (casos positivos/negativos por doctype).

## Seguimiento 2026-06-29 (Calidad documental)
- [x] Corregir el docstring de `_persist_bank_transaction` para cumplir `pydocstyle`/`D401`.
- [x] Validar `flake8` en la venv luego del ajuste.


## Administracion y Seguridad
- [ ] Activar `AuditLog` automatico para cambios en documentos operativos.

## Multi-Ledger y Revalorizacion
- [ ] Implementar `LedgerMappingRule` para diferencias automaticas entre libros.

## UI/UX y Reportes
- [x] Cerrar la fase final de paridad funcional en formularios transaccionales con pruebas adicionales por documento (incluyendo rutas `edit`/`duplicate` y transiciones de estado en POST).
- [ ] Evaluar y definir alcance de acciones equivalentes para registros maestros (cliente, proveedor, item, bodega, uom) sin forzar flujo documental donde no aplica.
- [x] Filtros de busqueda en listados de Compras, Ventas y Bancos.
- [x] Filtros de busqueda en listados de transacciones contables.
- [x] Reemplazar badges visuales hardcodeados de tarjetas de módulos por infraestructura semántica reusable en Python/Jinja.
- [ ] Migrar formularios operativos restantes al Smart Select Framework; el framework transaccional compartido de Compras, Ventas e Inventario ya inicializa correctamente sus selectores.
- [ ] Ampliar pruebas de interfaz para nuevos formularios bancarios (`pago_nuevo`, `nota_nueva`, `transferencia_nueva`) incluyendo escenarios multimoneda y contador externo.
- [ ] Implementar arbol grafico de trazabilidad (Diagrama de Flujo).
- [ ] Drill-down universal en el 100% de los reportes operativos.
- [ ] Exportacion consistente a Excel con formato financiero en todos los reportes.

## Motores de Cálculo y Contabilidad
- [ ] Añadir soporte transaccional persistido para documentos específicos de importación cuando exista un doctype dedicado para `import_landed_cost_confirmed`.

## Pendientes Generales
- [x] Implementar mas reportes operativos usando el nuevo framework.
- [ ] Seguir migrando formularios operativos al patron comun sin tocar todavia pagos bancarios ni documentos con origen complejo sin cobertura funcional suficiente.
- [ ] Ampliar cobertura de pruebas Playwright en el nuevo flujo estandarizado.
- [ ] Mejorar la estabilidad de los tests E2E en entornos de CI/Sandbox con latencia de red.
- [ ] Continuar la estandarizacion de reportes HTML siguiendo el patron de `financial_report.html`.
- [ ] Extender el uso de `smart-select` a dimensiones personalizadas si se requiere en el futuro.
- [ ] Integrar `audit_trail_service` en Bancos, Compras, Ventas, Inventario, Importaciones, Revalorización y Conciliaciones con timeline visible en cada detalle.
- [ ] Extender las mismas pruebas/contratos de Audit Trail a Bancos, Compras, Ventas, Inventario e Importaciones (acciones + timeline + append-only).
- [ ] Extender integración Audit Trail a documentos restantes de Compras/Ventas/Bancos/Inventario (órdenes, facturas, cotizaciones, notas) con render homogéneo de timeline en UI.
- [ ] Seguir reduciendo complejidad en flujos de Bancos donde todavía existan ramas largas, usando helpers pequeños y cobertura focal por cada refactor.
- [ ] Revisar si `issues.txt` debe regenerarse o depurarse, porque `_save_payment_references` ya quedó refactorizado y aparece como pendiente histórico.
