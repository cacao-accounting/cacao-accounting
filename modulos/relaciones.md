# Flujo Documental y Relaciones (Estado Implementado)

Este documento resume solo lo que esta implementado actualmente en el sistema.

## Fuente de verdad

- Backend: `cacao_accounting/document_flow/registry.py`
  - `DOCUMENT_TYPES`: define contratos y acciones `Crear`.
  - `ALLOWED_FLOWS`: define pares origen -> destino permitidos.
- UI: panel dinamico `document_flow_trace`.
- No hay estrategia legacy activa de botones `Crear` hardcodeados en vistas detalle.

## Reglas operativas vigentes

- Las acciones visibles de `Crear` salen del backend (`create_actions`).
- Las relaciones validas se controlan por `ALLOWED_FLOWS`.
- Las notas/devoluciones que comparten modelo de factura se distinguen por `document_type`.
- Bancos soporta prefill por tipo documental (factura, nota credito/debito, orden).

## Matriz implementada (resumen)

## Compras

| Origen | Destinos habilitados |
|---|---|
| Solicitud de Compra (`purchase_request`) | Solicitud de Cotizacion (`purchase_quotation`), Orden de Compra (`purchase_order`) |
| Solicitud de Cotizacion (`purchase_quotation`) | Cotizacion de Proveedor (`supplier_quotation`), Orden de Compra (`purchase_order`) |
| Cotizacion de Proveedor (`supplier_quotation`) | Orden de Compra (`purchase_order`) |
| Orden de Compra (`purchase_order`) | Recepcion (`purchase_receipt`), Factura (`purchase_invoice`), Pago/Anticipo (`payment_entry`), Nota Credito (`purchase_credit_note`), Nota Debito (`purchase_debit_note`) |
| Recepcion (`purchase_receipt`) | Factura (`purchase_invoice`), Nota Credito (`purchase_credit_note`), Nota Debito (`purchase_debit_note`), Devolucion (`purchase_return`), Movimiento Inventario (`stock_entry`) |
| Factura de Compra (`purchase_invoice`) | Pago (`payment_entry`), Nota Credito (`purchase_credit_note`), Nota Debito (`purchase_debit_note`) |
| Nota Credito Compra (`purchase_credit_note`) | Reembolso (`payment_entry`) |
| Nota Debito Compra (`purchase_debit_note`) | Pago (`payment_entry`) |

## Ventas

| Origen | Destinos habilitados |
|---|---|
| Pedido de Venta (`sales_request`) | Cotizacion (`sales_quotation`), Orden de Venta (`sales_order`) |
| Cotizacion de Venta (`sales_quotation`) | Orden de Venta (`sales_order`) |
| Orden de Venta (`sales_order`) | Nota de Entrega (`delivery_note`), Factura (`sales_invoice`), Pago/Anticipo (`payment_entry`) |
| Nota de Entrega (`delivery_note`) | Factura (`sales_invoice`), Nota Credito (`sales_credit_note`), Nota Debito (`sales_debit_note`), Movimiento Inventario (`stock_entry`) |
| Factura de Venta (`sales_invoice`) | Pago (`payment_entry`), Nota Credito (`sales_credit_note`), Nota Debito (`sales_debit_note`) |
| Nota Credito Venta (`sales_credit_note`) | Reembolso (`payment_entry`) |
| Nota Debito Venta (`sales_debit_note`) | Cobro (`payment_entry`) |

## Inventario y Bancos

| Origen | Destinos habilitados |
|---|---|
| Movimiento de Inventario (`stock_entry`) | Reuso interno (`stock_entry`) |
| Pago (`payment_entry`) | Sin acciones de creacion downstream en matriz actual |
