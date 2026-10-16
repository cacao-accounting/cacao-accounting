# Motor de costo de importación (Landed Cost)

El Motor de costo de importación calcula cómo se distribuyen los costos accesorios (flete, seguro, aranceles) entre los ítems de inventario.

## Entradas

- **Ítems**: Lista de productos que se están recibiendo.
- **Líneas capitalizables**: Impuestos o cargos del Motor fiscal marcados como `capitalizable_inventory_cost`.
- **Cargos externos**: Otros cargos manuales (p. ej., factura de flete) que deben prorratearse.

## Métodos de prorrateo

El motor soporta las siguientes estrategias de distribución:

| Método | Base de la cuota |
| :--- | :--- |
| `by_value` | (Monto neto del ítem) / (Monto neto total) |
| `by_quantity` | (Cantidad del ítem) / (Cantidad total) |
| `by_weight` | (Peso total del ítem) / (Peso total del envío) |
| `by_volume` | (Volumen total del ítem) / (Volumen total del envío) |
| `equal` | 1 / (Número de líneas de ítem) |
| `manual` | Usa montos específicos asignados manualmente por línea. |

## Salida del cálculo

El motor produce un `LandedCostResult` que incluye:
- **Asignación por ítem**:
    - Monto base original.
    - Lista de conceptos asignados y sus montos.
    - Costo capitalizable total final.
    - Costo unitario final (Total / Cantidad).
- **Pista de auditoría**: Explicación del cálculo de la cuota por ítem.

## Residuos de redondeo

La integridad financiera en los prorrateos exige que el total asignado coincida exactamente con el monto de origen. El motor garantiza esto asignando cualquier residuo fraccionario al último ítem de la asignación.
