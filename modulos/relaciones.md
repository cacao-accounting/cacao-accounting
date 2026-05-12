el sistema necesita cubrir todos los flujos documentales (upstream/downstream) y
no solo los “felices”. Aquí tienes una matriz exhaustiva por módulo, incluyendo:

Acciones tipo "Crear" (Make / Create)

Relaciones válidas

Consideraciones de auto-completado de líneas (“Actualizar Elementos”)



---

📊 CONTABILIDAD (Accounting)

Desde Factura de Venta

→ Pago (Payment Entry)

→ Nota de Crédito (Credit Note / Sales Invoice Return)

→ Asiento Contable (Journal Entry - ajuste)

→ Reconciliación


Desde Factura de Compra

→ Pago

→ Nota de Débito / Crédito proveedor

→ Asiento Contable


Desde Pago

→ Asiento Contable (write-off, diferencias)

→ Reconciliación contra facturas


Desde Asiento Contable

→ No suele generar documentos operativos, pero sí:

→ Reversión de asiento




---

🏦 BANCOS (Banking)

Desde Bank Transaction (extracto bancario)

→ Pago (Payment Entry)

→ Asiento Contable


Desde Pago

→ Conciliar con:

Factura de Venta

Factura de Compra



Desde Conciliación Bancaria

→ Ajustes (Journal Entry)



---

🛒 COMPRAS (Buying / Procure-to-Pay)

Desde Solicitud de Material (Material Request)

→ Solicitud de Cotización (RFQ)

→ Orden de Compra


Desde Solicitud de Cotización (RFQ)

→ Cotización de Proveedor (Supplier Quotation)


Desde Cotización de Proveedor

→ Orden de Compra


Desde Orden de Compra (PO)

→ Recibo de Compra (Purchase Receipt)

→ Factura de Compra (Purchase Invoice)

→ Subcontracting Receipt (si aplica)


Desde Recibo de Compra

→ Factura de Compra

→ Devolución de Compra


Desde Factura de Compra

→ Pago

→ Nota de Crédito (devolución financiera)


Desde Devolución de Compra

→ Nota de Crédito proveedor



---

💰 VENTAS (Selling / Order-to-Cash)

Desde Lead

→ Oportunidad


Desde Oportunidad

→ Cotización


Desde Cotización (Quotation)

→ Orden de Venta


Desde Orden de Venta (SO)

→ Nota de Entrega (Delivery Note)

→ Factura de Venta

→ Solicitud de Material (Make-to-Order)


Desde Nota de Entrega

→ Factura de Venta

→ Devolución de Entrega


Desde Factura de Venta

→ Pago

→ Nota de Crédito

→ Devolución (Sales Return)


Desde Devolución de Entrega

→ Nota de Crédito



---

📦 INVENTARIOS (Stock / Logistics)

Desde Item

→ Lista de Precios

→ Reglas de Reorden


Desde Material Request

→ Stock Entry (Transfer / Manufacture)

→ Orden de Compra


Desde Stock Entry

→ No suele generar, pero sí:

Ajustes

Reversión



Desde Delivery Note

→ Stock Ledger impact

→ Factura de Venta


Desde Purchase Receipt

→ Stock Ledger impact

→ Factura de Compra


Desde Batch / Serial

→ Movimientos de stock asociados



---

🔁 RELACIONES CRUZADAS IMPORTANTES

Estos son los que muchas implementaciones olvidan:

Orden de Venta → Factura (sin entrega) ✔️

Orden de Compra → Factura (sin recepción) ✔️

Entrega parcial → Facturación parcial ✔️

Recepción parcial → Facturación parcial ✔️

Pagos contra múltiples facturas ✔️

Un pago → múltiples facturas / viceversa ✔️



---

⚙️ “ACTUALIZAR ELEMENTOS” (AUTO-COMPLETAR LÍNEAS)

Esto no es opcional si quieres paridad con ERPNext. Debe aplicar en:

Documentos destino que reciben líneas:

Factura de Venta ← Orden de Venta / Entrega

Factura de Compra ← PO / Recepción

Nota de Entrega ← Orden de Venta

Recibo de Compra ← PO

Pago ← Facturas

Nota de Crédito ← Factura



---

🔧 Comportamiento esperado

1. Query param estándar

/sales-invoice?from_sales_order=SO-0001

2. Botón: "Actualizar Elementos"

Abre modal

Fetch API:


GET /api/sales-order/SO-0001

3. Modal permite:

Seleccionar líneas

Ver:

qty ordered

qty delivered

qty billed

qty pending


Editar cantidad a traer


4. Al confirmar:

Pobla tabla destino

Mantiene relación:

against_sales_order

so_detail_id




---

🔑 Reglas críticas

No duplicar líneas ya consumidas (control por qty pendiente)

Soportar parcialidades

Mantener trazabilidad (document flow)

Permitir múltiples documentos fuente (merge)



---

🧠 MODELO MENTAL (CLAVE PARA TU IMPLEMENTACIÓN)

Todo esto se resume en un patrón:

1. Documento fuente tiene:

items[]

qty

processed_qty


2. Documento destino:

referencia source_doc

referencia source_row


3. Motor:

pending_qty = qty - processed_qty


---

🚨 GAP TÍPICO EN IMPLEMENTACIONES (lo que te falta)

Seguramente te falta:

Crear desde Factura → Nota de Crédito

Crear desde Pago → Reconciliación

Crear desde Orden → Factura directa

Soporte de multi-source merge

Botón "Actualizar Elementos" reutilizable

Manejo de partial fulfillment 
