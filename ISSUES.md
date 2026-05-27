Plan de Corrección — Master Data Contable (Pre-R2R Gate)

Objetivo

Cerrar las inconsistencias funcionales y UX de los registros maestros de contabilidad antes de iniciar pruebas de registros transaccionales (R2R).

Este plan es accionable, verificable y auditable. Cada issue tiene:

problema

plan de corrección

criterios de aceptación

tests de regresión

definición objetiva de “completo”



---

Fase 1 — Entidades (bloqueante)

QA-MD-001 — Entidad no tiene estado activo/inactivo

Problema

Las entidades no tienen bandera booleana activo/inactivo.

Consecuencias:

- no puede deshabilitarse una compañía
- Smart Select no puede filtrar entidades operativas
- no existe lifecycle administrativo


---

Plan de corrección

Modelo

Agregar:

is_active: bool = True

Migración:

default = true
backfill de entidades existentes


---

Vista lista

Agregar columna:

Estado

Mostrar badge:

Activo
Inactivo


---

Vista editar entidad

Agregar control:

☑ Entidad activa

Reglas:

- editable por admin
- default true


---

Toggle rápido

Agregar acción:

Activar / Desactivar

en lista y detalle.


---

Reglas backend

No permitir:

- desactivar entidad usada por sesión actual si rompería acceso
- desactivar única entidad activa en desktop mode


---

Criterios de aceptación

[ ] Entidad tiene campo is_active.
[ ] Entidades existentes quedan activas.
[ ] Lista muestra estado.
[ ] Editar entidad permite activar/desactivar.
[ ] Acción rápida funciona.
[ ] Smart Select puede filtrar entidades activas.
[ ] Backend impide estados inconsistentes.


---

Tests requeridos

Modelo / servicio

test_entity_can_be_activated
test_entity_can_be_deactivated
test_existing_entities_default_to_active

UI/service

test_entity_list_shows_status
test_entity_edit_form_supports_active_flag

Regresión

test_desktop_mode_requires_single_active_entity


---

Definición de completo

Completo cuando:

✓ entidad tiene lifecycle activo/inactivo
✓ visible en UI
✓ editable
✓ protegido backend
✓ testeado


---

QA-MD-002 — Smart Select debe mostrar solo entidades activas

Problema

Los formularios permiten seleccionar entidades inactivas.


---

Plan de corrección

Agregar soporte transversal:

active_only=True

en:

smart_select.search_entities()

Default:

True

Override administrativo:

include_inactive=True

solo en pantallas administrativas.


---

Afectados

Cuenta contable
Centro costo
Libro
Proyecto
Período
Año fiscal
Comprobante contable


---

Criterios aceptación

[ ] Smart Select no muestra entidades inactivas.
[ ] Backend rechaza entidad inactiva enviada manualmente.
[ ] Admin puede ver todas si explicitly requested.


---

Tests

test_entity_search_select_returns_only_active_entities
test_entity_search_select_can_include_inactive_for_admin
test_backend_rejects_inactive_entity_submission


---

Completo

✓ selector filtrado
✓ backend protegido
✓ tests pasan


---

Fase 2 — Precarga correcta de formularios edit

(Bloqueante antes de R2R)


---

QA-MD-003 — Edit account no precarga datos

Route:

/accounting/account/<entity>/<code>/edit

Problema

No llena:

- entidad
- cuenta padre


---

Plan corrección

Garantizar que edit haga:

form.entity.data = account.entity_code
form.parent_account.data = account.parent_account_code

Smart Select debe cargar:

label actual + hidden value


---

Criterios aceptación

[ ] Código correcto
[ ] Nombre correcto
[ ] Entidad visible
[ ] Cuenta padre visible
[ ] Estado correcto
[ ] Tipo correcto
[ ] Clasificación correcta


---

Tests

test_account_edit_form_prefills_entity
test_account_edit_form_prefills_parent_account
test_account_edit_form_prefills_all_fields


---

Completo

✓ form edit refleja DB exactamente


---

QA-MD-004 — Edit cost center no precarga

Misma estrategia.

Criterios

[ ] entidad visible
[ ] padre visible
[ ] nombre correcto
[ ] estado correcto

Tests

test_cost_center_edit_prefills_entity
test_cost_center_edit_prefills_parent
test_cost_center_edit_prefills_fields


---

QA-MD-005 — Edit ledger no precarga

Route:

/accounting/book/edit/<code>


---

Criterios aceptación

[ ] código
[ ] nombre
[ ] entidad
[ ] moneda
[ ] estado


---

Tests

test_ledger_edit_prefills_entity
test_ledger_edit_prefills_currency
test_ledger_edit_prefills_state


---

QA-MD-006 — Edit project no precarga


---

Criterios

[ ] entidad visible
[ ] presupuesto correcto
[ ] moneda presupuesto visible
[ ] fechas correctas
[ ] estado correcto


---

Tests

test_project_edit_prefills_entity
test_project_edit_prefills_budget
test_project_edit_prefills_budget_currency
test_project_edit_prefills_dates


---

QA-MD-007 — Edit accounting period no precarga


---

Criterios

[ ] entidad correcta
[ ] nombre correcto
[ ] fechas correctas
[ ] estado correcto


---

Tests

test_accounting_period_edit_prefills_fields


---

QA-MD-008 — Edit fiscal year no precarga


---

Criterios

[ ] entidad
[ ] fechas
[ ] estado cerrado


---

Tests

test_fiscal_year_edit_prefills_fields


---

Definición transversal de completo (edit forms)

Completo cuando:

✓ el form refleja exactamente el registro persistido
✓ smart select muestra label correcto
✓ hidden input tiene value correcto
✓ save sin cambios no altera datos
✓ tests pasan


---

Fase 3 — Navegación administrativa


---

QA-MD-009 — Unidad de negocio detail sin botón editar

Plan

Agregar botón:

Editar

En:

/accounting/unit/<code>


---

Criterios

[ ] botón visible
[ ] navega correctamente


---

Test

test_unit_detail_shows_edit_action


---

QA-MD-010 — Currency detail sin editar

Mismo patrón.

Test

test_currency_detail_shows_edit_action


---

QA-MD-011 — Exchange rate detail sin editar

Test

test_exchange_rate_detail_shows_edit_action


---

Completo

✓ todos los details tienen CTA Editar visible


---

Fase 4 — Uniformidad de list views


---

QA-MD-012 — Look & feel inconsistente

Objetivo

Crear patrón único.


---

Requerimiento UI

Todas las listas maestras:

Breadcrumb
Título H1
Botón crear
Filtro búsqueda
Tabla uniforme
Estado badge
Columna acciones
Empty state
Paginación


---

Columna acciones mínima

Ver
Editar
Activar/Desactivar (si aplica)


---

Master views

Entidades
Cuentas
Centros costo
Unidad negocio
Libros
Proyectos
Monedas
Tasas cambio
Períodos
Años fiscales


---

Criterios aceptación

[ ] Todas tienen columna acciones.
[ ] Todas tienen CTA crear.
[ ] Todas tienen breadcrumbs.
[ ] Todas tienen empty state consistente.
[ ] Todas muestran estado cuando aplica.


---

Tests

Template tests

test_master_lists_render_actions_column
test_master_lists_render_primary_create_action
test_master_lists_render_breadcrumb

Snapshot/UI tests (si existen)

test_master_views_follow_standard_layout


---

Completo

✓ UX uniforme
✓ navegación consistente


---

Fase 5 — HTML titles


---

QA-MD-013 — Títulos HTML inconsistentes

Problema

Usuarios ERP trabajan con muchas pestañas.


---

Requerimiento

Todo template debe definir:

<title>

Patrón:

Cacao Accounting | Contabilidad | Entidades
Cacao Accounting | Contabilidad | Cuenta 11.01.001
Cacao Accounting | Contabilidad | Proyecto P0001


---

Convención

Lista:

Modulo | Lista

Detalle:

Modulo | Registro

Editar:

Modulo | Editar Registro

Crear:

Modulo | Nuevo Registro


---

Criterios aceptación

[ ] Todo template define title.
[ ] No existen titles vacíos.
[ ] Convención uniforme.


---

Tests

test_accounting_templates_define_title
test_accounting_templates_follow_title_convention


---

Completo

✓ navegación por tabs usable
✓ titles consistentes


---

Gate de cierre antes de R2R

No iniciar pruebas transaccionales hasta cumplir:

[ ] QA-MD-001 cerrado
[ ] QA-MD-002 cerrado
[ ] QA-MD-003 cerrado
[ ] QA-MD-004 cerrado
[ ] QA-MD-005 cerrado
[ ] QA-MD-006 cerrado
[ ] QA-MD-007 cerrado
[ ] QA-MD-008 cerrado
[ ] QA-MD-009 cerrado
[ ] QA-MD-010 cerrado
[ ] QA-MD-011 cerrado
[ ] QA-MD-012 cerrado
[ ] QA-MD-013 cerrado
[ ] Tests verdes

Estado objetivo

Cuando todo esto esté listo:

QA Status = MASTER DATA READY
R2R Testing = UNBLOCKED
