# Motor de liquidación

El Motor de liquidación gestiona la liquidación financiera de documentos, calculando el movimiento real de efectivo y las retenciones.

## Responsabilidades

1. **Calcular retenciones**: Determina los impuestos que se retendrán al momento del pago o cobro.
2. **Pagos parciales**: Calcula correctamente las retenciones proporcionales cuando solo se paga una parte del saldo del documento.
3. **Diferencias financieras**: Rastrea diferencias de tipo de cambio y pequeñas variaciones de redondeo.
4. **Seguimiento de saldo**: Calcula el saldo abierto restante después de la liquidación.

## Lógica de retención proporcional

Para pagos parciales, el motor usa la siguiente fórmula:
`Proportion = (Payment Amount) / (Document Total)`
`Withholding = (Full Withholding for Document) * Proportion`

Esto asegura que las retenciones se apliquen de forma justa a lo largo de múltiples pagos de la misma factura.
