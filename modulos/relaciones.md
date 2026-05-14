# Flujo Documental y Relaciones
Este módulo define la trazabilidad transversal entre documentos.

## Acciones de Creación (Make/Create)
- **Ventas:** SO → Delivery → Invoice → Payment → Credit Note.
- **Compras:** PO → Receipt → Invoice → Payment → Debit/Credit Note.
- **Inventario:** Receipt → Stock Entry; Delivery → Stock Entry.

Registros de los modulos de Compras, Ventas, Inventario y Bancos deben incluir in boton "Crear" que permita al usuario crear transacciones relacionadas
al registro actual siguiendo el flujo logico de operación, ejemplos:

Solicitud de Compra permite Crear Solicitud de Cotización.
Solicitud de Cotización permite crear presupuesto de Proveedor.
Multiples Presupuestos de Proveedor se pueden unir en un comparativo de ofertas.
Comparativo de Oferta, Oferta de Proveedor o Solicitud de Compra Permiten Crear Orden de Compra.
Orden de Compra permite Crear Recibo en Almacen, Factura, Nota de Debito, Nota de Credito o Devolucion
etc, etc, etc, etc,

## Patrón "Actualizar Elementos"
Mecanismo para tirar líneas de documentos fuente hacia destinos:
- Factura ← Orden / Entrega / Recepción.
- Pago ← Facturas (múltiples).
- Nota de Crédito ← Factura.

## Reglas de Oro
- Mantener `pending_qty = qty - processed_qty`.
- No duplicar líneas consumidas.
- Trazabilidad bidireccional vía `DocumentRelation`.

El usuario debe poder generar un nuevo registro, aplicar filtros y obtener lineas de otros registros preexistentes que cumplan con los filtros aplicados.
