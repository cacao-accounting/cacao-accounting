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

## Actualización incremental — 2026-05-14 (Ampliación del seed de datos de prueba)

- **Seed de datos robusto:** Se han ampliado los datos de prueba (`dev_data`) para incluir un escenario multimoneda completo para la empresa 'cacao'.
- **Libros Contables:** 'cacao' ahora cuenta con 3 libros: Local (NIO), Financiero (USD) y Gerencia (EUR).
- **Transacciones Reales:** El seed ya no solo inserta datos maestros, sino que ejecuta transacciones reales (asientos iniciales) a través del motor de posting para cada moneda y libro, asegurando que el ledger (`gl_entry`) esté poblado desde el inicio.
- **Tasas de Cambio:** Se generan tipos de cambio dinámicos para el día actual, permitiendo pruebas de conversión en tiempo real.
- **Dimensiones Analíticas:** Se agregaron unidades de negocio (Logística, Ventas), centros de costos (ADM, VTAS, OPS) y proyectos (Expansión) para permitir pruebas de reportes filtrados.
- **Plantillas Recurrentes:** Se incluye una plantilla de renta mensual aprobada y lista para ser aplicada en el asistente de cierre.
- **Verificación:** Todos los datos sembrados son validados por una suite de pruebas unitarias que también confirma que los reportes financieros (Balance, Resultados) son consistentes con la siembra.

## Actualización incremental — 2026-05-13 (inicio de Cliente y Proveedor con UX tipo comprobante)

- **Base funcional creada:** Cliente y Proveedor ya se están reestructurando con una cabecera de datos maestros y una tabla por compañía para activación y configuración operativa.
- **Configuración por compañía:** `CompanyParty` ahora soporta plantilla fiscal y banderas para permitir factura de compra sin OC / sin recibo; la lógica de guardado vive en `party_settings.py`.
- **Prefill de cuentas:** La cuenta por cobrar o por pagar se prellena desde `CompanyDefaultAccount` y se guarda en `PartyAccount` con validación de compañía y tipo de cuenta.
- **UX alineada:** Las plantillas de alta ya usan `smart-select` para compañía, cuentas y plantilla fiscal, siguiendo el patrón visual del comprobante contable.
- **Estado actual:** Es una primera entrega funcional; falta completar edición, listado detallado por compañía y el maestro formal de tipo de tercero si se decide separar la clasificación libre.

## Actualización incremental — 2026-05-13 (Maestros principales con UX tipo comprobante)

- **Maestros migrados:** Item, Cliente, Proveedor, Banco y Cuenta Bancaria usan formularios y vistas separadas alineadas al estilo del comprobante contable.
- **Smart Select aplicado:** Item selecciona UOM base con `smart-select`; Cliente y Proveedor seleccionan compañía para activación; Cuenta Bancaria selecciona banco, compañía, moneda y cuenta contable.
- **Cuenta bancaria contable:** La cuenta bancaria puede asociarse a una cuenta contable `account_type=bank`; el filtro es visual y también se valida en servidor antes de guardar `gl_account_id`.
- **Navegación de lectura:** Los listados de estos maestros enlazan al registro individual.
- **Sin sobreingeniería:** No se introdujeron macros nuevas ni un renderer compartido; cada plantilla se mantiene explícita por tipo de registro.

## Actualización incremental — 2026-05-12 (UX gradual de registros contables)

- **Alcance conservador:** Se mantuvieron plantillas HTML separadas por tipo de registro y no se agregaron macros nuevas para la UX de estos formularios.
- **Aprovechamiento de pantalla:** Los formularios y vistas de registros contables dejaron de tener `max-width` fijo; `/accounting/journal/<id>` también ocupa el ancho disponible.
- **Vistas de lectura agregadas:** Monedas, tasas de cambio, proyectos, años fiscales y períodos contables ahora tienen URL propia de visualización y sus listados enlazan a ella.
- **Tipos de cuenta completos:** `/accounting/account/new` expone todos los tipos de cuenta requeridos por el catálogo base y la configuración de cuentas por defecto.
- **Verificación focalizada:** Pasan rutas, vistas y formularios con `tests/test_routes_map.py`, `tests/test_01vistas.py` y `tests/test_02forms.py`.

## Actualización incremental — 2026-05-12 (Reportes financieros: filtros avanzados)

- **Motor identificado:** Los cinco reportes financieros usan el renderer común de `cacao_accounting/reportes/__init__.py` y la plantilla `financial_report.html`.
- **UX de filtros corregida:** El toggle Mostrar/Ocultar filtros avanzados ahora usa JavaScript local con estado inicial renderizado desde servidor y conserva `advanced=1|0` al aplicar filtros.
- **Filtros principales reordenados:** `Mostrar anulaciones` e `Incluir Registro de Cierre` quedan visibles debajo de `Cuenta contable` en todos los reportes financieros.
- **Comprobantes de cierre manuales:** `/accounting/journal/new?isclosing=true` precarga la Etapa de Cierre como `Cierre` en el selector del formulario.
- **Plantillas recurrentes alineadas al comprobante normal:** `/accounting/journal/recurring/new` permite serie por defecto, selección de libros con checkboxes y edición avanzada de dimensiones por línea sin asociar la plantilla a registros específicos.
- **Cierre mensual paso a paso:** `/accounting/period-close/monthly` ahora lista cierres mensuales, permite crear un cierre por periodo contable y continuar cada cierre desde una vista de pasos; el primer paso ejecuta comprobantes recurrentes y registra resultado en `PeriodCloseCheck`.
- **Smart Select en cierre mensual:** El formulario de nuevo cierre selecciona compañía con Smart Select y filtra periodos contables abiertos por compañía antes de crear el cierre.

## Actualización incremental — 2026-05-12 (Corrección de ciclo FK en recurrentes)

- **Esquema recurrente:** Corregida la advertencia de SQLAlchemy durante `drop_all()` en SQLite causada por la dependencia circular entre `comprobante_contable` y `recurring_journal_application`.
- **Trazabilidad conservada:** Se mantiene el vínculo bidireccional entre el comprobante contable generado y el registro de aplicación recurrente, marcando el ciclo explícitamente con `use_alter=True`.
- **Verificación:** `create_all()`/`drop_all()` pasa con `SAWarning` tratado como error y las pruebas de recurrentes continúan pasando.

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
