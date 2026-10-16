# Ejemplos de resolución de reglas de impuestos

Esta página proporciona ejemplos de cómo el Resolutor de reglas maneja distintos escenarios usando las estrategias de prioridad y fusión.

## Escenario 1: Reemplazo estándar de IVA

- **Regla de compañía**: IVA 15% (Nivel: Compañía)
- **Regla de ítem**: IVA 0% (Nivel: Ítem)
- **Resultado**: IVA 0%. (Razón: el nivel de Ítem tiene mayor prioridad que el nivel de Compañía).

## Escenario 2: Cliente exento (estrategia Exclude)

- **Regla de transacción**: IVA 15% (Nivel: Transacción)
- **Regla de parte**: IVA (Estrategia: `exclude`) (Nivel: Parte)
- **Resultado**: No se aplica IVA. (Razón: la regla de Parte excluye explícitamente el concepto de IVA).
