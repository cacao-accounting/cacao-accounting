# Ejemplo de pagos y retenciones

Este ejemplo demuestra cómo el Motor de liquidación maneja pagos parciales y retenciones proporcionales.

## 1. Escenario

- **Total del documento**: 1,000.00
- **Saldo abierto**: 1,000.00
- **Regla de retención**: Impuesto sobre la Renta (IR) 2% al pago.
- **Retención completa si se paga en su totalidad**: 20.00

## 2. Caso B: Pago parcial

- **Monto del pago**: 400.00
- **Paso de liquidación**:
  - Proporción: 40% (400 / 1000)
  - Base de retención: 400.00
  - Monto de retención: 8.00 (20.00 * 0.40)
  - **Efectivo a pagar**: 392.00
  - **Nuevo saldo**: 600.00
