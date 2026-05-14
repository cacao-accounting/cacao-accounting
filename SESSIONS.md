# SESSIONS - Historical Decisions & Milestones

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
