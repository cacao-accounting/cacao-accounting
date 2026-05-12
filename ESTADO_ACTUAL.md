Estado 2026-05-12 (Finalizado): Todos los issues listados han sido resueltos y verificados.
- Se ha unificado el UX en todo el módulo contable siguiendo el "Voucher Pattern".
- Se implementaron las funcionalidades de Comprobantes Recurrentes y Asistente de Cierre Mensual.
- Se agregaron filtros de búsqueda en las vistas de listado.
- Se limpiaron los formularios de Cuentas y Centros de Costos (eliminando campos redundantes).
- Se implementó la edición para Cuentas y Unidades de Negocio.
- Se habilitó `smartSelect` para Cuentas Padre filtrado por entidad y clasificación.
- Se aseguró la creación automática de Centro de Costos "MAIN" al crear una entidad.
- Se corrigieron errores de linting (E501) que bloqueaban el CI.

# ESTADO ACTUAL DEL PROYECTO

## Actualización incremental — 2026-05-12 (Cierre del módulo de contabilidad)

- **Comprobantes Recurrentes:** Implementado el framework completo para plantillas contables que no impactan el ledger al aprobarse, permitiendo su aplicación diferida. Incluye validación de balance y estados operativos (`draft`, `approved`, `cancelled`, `completed`).
- **Asistente de Cierre Mensual:** Activado el primer paso operativo del asistente, permitiendo filtrar y aplicar plantillas recurrentes aprobadas para un periodo contable específico.
- **Integración Contable:** Los comprobantes generados desde recurrentes quedan vinculados a su plantilla de origen y heredan el comportamiento de un comprobante manual.
- **Posting de Facturas:** Se aseguró que al aprobar una factura de compra o venta, se inicialice correctamente el saldo pendiente (`outstanding_amount`) y el gran total, permitiendo un seguimiento inmediato de AR/AP.
- **UX Uniforme:** Se unificó la interfaz de usuario en todo el módulo de Contabilidad siguiendo el patrón de diseño de "Comprobante Contable" (Voucher Pattern).
- **Filtros de Búsqueda:** Se agregaron filtros de búsqueda en todas las páginas de listado del módulo contable para facilitar la localización de registros.

## Núcleo de Posting y Valoración de Inventario

- **Valuación FIFO y Promedio Móvil:** Implementado el consumo real de capas de valoración (`StockValuationLayer`) en `posting.py`. Las salidas de inventario ahora calculan el costo real basándose en el método configurado para el ítem.
- **Cálculo Dinámico de Saldo Pendiente:** `compute_outstanding_amount` en `document_flow/service.py` calcula el saldo vivo de las facturas basándose en las referencias de pago reales en lugar de depender únicamente de un campo estático.
- **Pagos Multi-factura:** El formulario de pagos soporta la selección y aplicación de un pago a múltiples facturas pendientes, registrando correctamente las referencias de pago y actualizando los saldos.

---

## ¿Qué implementa el proyecto?

**Cacao Accounting** es un sistema contable de código abierto orientado a pequeñas y medianas empresas. Implementa los flujos de negocio centrales de contabilidad:

- **R2R (Record to Report):** captura de transacciones → mayor general → reportes.
- **S2P (Source to Pay):** solicitud de compra → orden → recepción → factura de proveedor → pago.
- **O2C (Order to Cash):** cotización → orden de venta → entrega → factura de cliente → cobro.
- **Inventario:** movimientos físicos (entradas, salidas, transferencias), valoración (FIFO / Promedio Móvil), lotes y series.

El sistema está diseñado con soporte nativo para:
- **Multi-compañía:** toda transacción tiene campo `company`.
- **Multi-ledger:** libros paralelos (Fiscal, NIIF, etc.).
- **Multimoneda real:** documentos en cualquier moneda, GL guarda moneda base y original.
- **Múltiples períodos contables** con apertura/cierre.
- **Series e identificadores** desacoplados y auditables.
- **Flujo documental trazable** (upstream/downstream entre documentos).

---

## ¿Dónde lo implementa?

| Capa | Ubicación | Descripción |
|---|---|---|
| Paquete principal | `cacao_accounting/` | Raíz de la aplicación Flask |
| Esquema de base de datos | `cacao_accounting/database/__init__.py` | Todos los modelos SQLAlchemy |
| Módulo Contabilidad | `cacao_accounting/contabilidad/` | Blueprint `contabilidad`, incluye Journal Entry, Recurrentes y Cierre |
| Módulo Compras | `cacao_accounting/compras/` | Blueprint `compras` (S2P) |
| Módulo Ventas | `cacao_accounting/ventas/` | Blueprint `ventas` (O2C) |
| Módulo Bancos | `cacao_accounting/bancos/` | Blueprint `bancos` (Tesorería y Reconciliación) |
| Módulo Inventario | `cacao_accounting/inventario/` | Blueprint `inventario` (Almacén y Valoración) |
| Posting contable | `cacao_accounting/contabilidad/posting.py` | Servicio de contabilización GL, AR/AP, bancos e inventario |
| Reportes | `cacao_accounting/reportes/` | Framework financiero y reportes operativos |

---

## Resumen de estado por módulo

| Módulo | Modelos DB | Rutas CRUD | Posting/Servicios | Reportes |
|---|---|---|---|---|
| Contabilidad | ✅ Completo | ✅ Unificado | ✅ JE Manual, Recurrentes | 🟡 Financieros MVP |
| Compras | ✅ Completo | 🟡 Parcial | ✅ Factura genera GL + Impuestos | 🟡 Operativos MVP |
| Ventas | ✅ Completo | 🟡 Parcial | ✅ Factura genera GL + Impuestos | 🟡 Operativos MVP |
| Bancos | ✅ Completo | 🟡 Parcial | ✅ Pagos y Reconciliación MVP | 🟡 Operativos MVP |
| Inventario | ✅ Completo | 🟡 Parcial | ✅ SLE/Bin/Valuation (FIFO/MA) | 🟡 Kardex MVP |
| Doc Flow | ✅ Completo | ✅ API completa | ✅ Relaciones activas | N/A |
