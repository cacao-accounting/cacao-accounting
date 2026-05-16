# SESSIONS - Historical Decisions & Milestones

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
