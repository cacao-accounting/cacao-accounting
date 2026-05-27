# Referencia de Contexto Jinja

Los formatos de impresion reciben diccionarios serializables. No se exponen objetos
SQLAlchemy, `request`, `session`, `config`, `g` ni modelos internos.

## Raices comunes

- `company`: datos publicos de la compania emisora.
- `audit`: usuario y fecha de impresion.
- `validation`: estado de validacion publica y QR opcional.

## Raices por documento

- `journal_entry`: comprobante contable.
- `invoice`: factura de venta o compra, segun `document_type`.
- `purchase_order`: orden de compra.
- `payment`: comprobante de pago.
- `receipt`: nota de entrega o recepcion imprimible.
- `adjustment`: movimiento de inventario.
- `quote`: cotizacion.

## Lineas

Las colecciones de lineas usan campos estables en ingles:

```jinja
{% for item in invoice.items %}
  {{ item.item_code }}
  {{ item.description }}
  {{ item.quantity }}
  {{ item.unit_price }}
  {{ item.line_total }}
{% endfor %}
```

## Validacion QR

```jinja
{% if validation.enabled and validation.qr_data_uri %}
  <img src="{{ validation.qr_data_uri }}" alt="Document validation QR">
{% endif %}
```
