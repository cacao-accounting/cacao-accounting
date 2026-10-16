# Ejemplo de cálculo de ventas e impuestos

Este ejemplo muestra una venta nacional estándar con IVA y un impuesto municipal.

## 1. Datos de entrada

- **Ítems**:
  - Laptop: 1 unidad @ 1,200.00
  - Mouse: 1 unidad @ 25.00
  - **Subtotal**: 1,225.00
- **Reglas configuradas**:
  1. Impuesto municipal: 1% (Base: Bienes, No capitalizable)
  2. IVA: 15% (Base: Bienes, No capitalizable)

## 2. Paso del Motor fiscal

| Concepto | Base | Tasa | Monto |
| :--- | :--- | :--- | :--- |
| **Impuesto municipal** | 1,225.00 | 1% | 12.25 |
| **IVA** | 1,225.00 | 15% | 183.75 |
