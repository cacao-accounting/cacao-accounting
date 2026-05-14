# Módulo: Compras (Buying / Purchasing)
Rol: Gestión del flujo **Source to Pay (S2P)**.

## Principios de Diseño
- Patrón Header + Items obligatorio.
- Recepción e Invoice son eventos separados.
- Uso de cuenta puente (Bridge) para conciliación de mercancía vs. factura.
- Impacto contable automático en GL.

## Modelos Principales
- **Terceros:** `Party` (supplier), `CompanyParty` (activación).
- **Documentos:** `PurchaseOrder`, `PurchaseReceipt`, `PurchaseInvoice`.
- **Conciliación:** `PurchaseReconciliation`.
- **Maestros:** `TaxTemplate`, `PriceList`, `ItemPrice`.

## Flujo Operativo
Solicitud (Material Request) → RFQ → Cotización Proveedor → Orden de Compra (PO) → Recepción (Receipt) → Factura (Invoice) → Pago.
