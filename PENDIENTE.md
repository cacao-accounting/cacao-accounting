# PENDIENTE — Cacao Accounting

Este documento registra lo que queda pendiente tras la consolidación de mayo de 2026. Se han priorizado las funcionalidades de colaboración, auditoría y seguridad avanzada.

---

## Correcciones Técnicas Resueltas
- [x] Migrar los maestros principales Item, Cliente, Proveedor, Banco y Cuenta Bancaria al estilo visual del comprobante contable.
- [x] Usar `smart-select` en los maestros principales donde hay relaciones: UOM, compañía, banco, moneda y cuenta contable.
- [x] Permitir y validar asociación de Cuenta Bancaria con cuenta contable de tipo `bank`.
- [x] Alinear gradualmente formularios y vistas de registros maestros contables con el estilo del comprobante, manteniendo plantillas separadas y sin macros nuevas.
- [x] Agregar URLs de visualización para monedas, tasas de cambio, proyectos, años fiscales y períodos contables.
- [x] Ampliar tipos de cuenta en `/accounting/account/new` para cubrir el catálogo base y la configuración de cuentas por defecto.
- [x] Resolver advertencia `SAWarning` por ciclo FK entre `comprobante_contable` y `recurring_journal_application` durante `drop_all()` en SQLite.
- [x] Corregir toggle Mostrar/Ocultar filtros avanzados en los cinco reportes financieros y reubicar los checkboxes principales bajo `Cuenta contable`.
- [x] Alinear formulario de plantillas recurrentes con comprobante normal: serie por defecto, libros por checkbox y modal de dimensiones sin referencias específicas.
- [x] Rediseñar asistente de cierre mensual como registro step-by-step con lista de cierres, creación por periodo y paso inicial de comprobantes recurrentes.
- [x] Usar Smart Select en nuevo cierre mensual para compañía y periodos contables abiertos filtrados por compañía.

- [x] Ampliar el seed inicial de datos de prueba para cubrir escenarios multimoneda (NIO, USD, EUR).
- [x] Incluir transacciones reales (JEs) y plantillas recurrentes en el proceso de siembra de datos.
- [x] Dinamizar fechas de registros y tasas de cambio según el mes de ejecución.
- [x] Agregar unidades de negocio, centros de costos y proyectos adicionales al seed.

---

## Posting Contable y Core
- [ ] Resolver política formal de renumeración de `document_no` cuando un borrador cambia de serie/fecha tras haber sido numerado.
- [ ] Implementar soporte completo para `GLEntryDimension` (dimensiones personalizadas) en el motor de posting.

---

## Cuentas por Cobrar / Cuentas por Pagar (AR/AP)
- [ ] Mejorar UX de exportación de Aging y permitir buckets configurables por compañía.
- [ ] Implementar conciliación masiva de facturas contra pagos desde una interfaz dedicada (actualmente es 1 a N desde el pago).

---

## Documentos de Corrección
- [ ] Reforzar validaciones E2E para flujos de devolución complejos (ej. devolución parcial de mercancía con factura ya pagada).
- [ ] Trazabilidad bidireccional visualmente mejorada en el árbol de flujo para reversiones.

---

## Proveedor y Cliente
- [ ] Implementar modelo `PartyGroup` y su CRUD.
- [ ] Completar edición y visualización por compañía para Cliente y Proveedor en el nuevo patrón de comprobante.
- [ ] Añadir gestión de múltiples direcciones/contactos.
- [ ] Evaluar si la clasificación libre debe convertirse en un maestro formal de tipo de tercero.

---

## Inventario
- [ ] Implementar "Stock Reconciliation" para ajuste de valuación (actualmente solo soporta ajuste de cantidad/conciliación física).
- [ ] Prorrateo de cargos capitalizables (fletes/seguros) hacia el costo de entrada en `StockValuationLayer`.

---

## Multi-Ledger y Dimensiones
- [ ] Implementar `LedgerMappingRule` para diferencias automáticas entre libros.
- [ ] UI para gestión de `DimensionType` y `DimensionValue`.
- [ ] Reporte de saldos por dimensiones analíticas.

---

## Tesorería y Revalorización
- [ ] Implementar proceso de `ExchangeRevaluation` (revalorización cambiaria de cuentas monetarias).
- [ ] Automatización de ajustes por diferencial cambiario en pagos de facturas multimoneda.

---

## Administración y Seguridad
- [ ] Endurecer autorización por compañía/libro con matriz explícita usuario↔compañía/libro.
- [ ] Implementar Workflow de aprobación configurable (definición de estados y transiciones).
- [ ] Activar registro automático de `AuditLog` para cambios en documentos operativos (actualmente solo en flujo documental).

---

## UI y UX (Pendiente Transversal)
- [ ] Añadir filtros de búsqueda en listados de Compras, Ventas y Bancos (completado solo en Contabilidad).
- [ ] Migrar todos los formularios operativos restantes al Smart Select Framework.
- [ ] Implementar el árbol gráfico de trazabilidad (Diagrama de Flujo).

---

## Reportes
- [ ] Drill-down universal completo en todos los reportes operativos.
- [ ] Exportación consistente a Excel con formato financiero en el 100% de los reportes.
- [ ] Añadir pruebas E2E de UI para expand/collapse jerárquico.
