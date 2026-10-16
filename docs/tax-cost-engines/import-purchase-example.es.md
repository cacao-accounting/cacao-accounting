# Ejemplo de ciclo de importación y compra

Este ejemplo demuestra el flujo completo de una importación internacional, en el que intervienen tanto el Motor fiscal como el Motor de costo de importación.

## 1. Datos de entrada

- **Ítems**:
  - Ítem A: 10 unidades @ 100.00 = 1,000.00
- **Reglas configuradas**:
  1. DAI: 5% (Base: Bienes, Capitalizable)
  2. ISC: 3% (Base: Acumulada [Bienes, DAI], Capitalizable)
  3. IVA: 15% (Base: Acumulada [Bienes, DAI, ISC], Cuenta separada)

## 2. Paso del Motor fiscal

| Concepto | Base | Tasa | Monto | Tratamiento |
| :--- | :--- | :--- | :--- | :--- |
| **DAI** | 1,000.00 | 5% | 50.00 | Capitalizable |
| **ISC** | 1,050.00 | 3% | 31.50 | Capitalizable |
| **IVA** | 1,081.50 | 15% | 162.23 | Cuenta separada |

## 3. Paso del Motor de costo de importación

El motor recibe los 81.50 de impuestos capitalizables y los distribuye al Ítem A.

- **Asignación del Ítem A**:
  - Base: 1,000.00
  - Asignado: 81.50
  - Costo final: 1,081.50
  - Costo unitario: 108.15
