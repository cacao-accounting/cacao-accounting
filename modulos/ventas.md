# Módulo: Ventas (Selling / Sales)
Rol: Gestión del flujo **Order to Cash (O2C)**.

## Principios de Diseño
- Patrón Header + Items obligatorio.
- Entrega y Facturación son eventos separados e independientes.
- El saldo AR es una proyección del GL (Open Items model).
- Soporte nativo para multimoneda real.

## Modelos Principales
- **Terceros:** `Party` (customer), `CompanyParty` (activación).
- **Documentos:** `SalesOrder`, `DeliveryNote`, `SalesInvoice`.
- **Maestros:** `TaxTemplate`, `PriceList`, `ItemPrice`.

## Flujo Operativo
Cotización → Orden de Venta (SO) → Nota de Entrega (Delivery) → Factura (Invoice) → Devolucion → Nota de Debito / Credito → Pago.

### Flujo configurable

- Permitir Factura sin Orden de Venta.
- Permtir Factura sin Recepción.
