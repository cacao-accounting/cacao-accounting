# Prioridad y resolución de reglas

El sistema utiliza una estrategia de resolución jerárquica para determinar qué reglas de impuestos se aplican a una transacción.

## Niveles de prioridad

Las reglas se resuelven en el siguiente orden de especificidad (mayor prioridad primero):

1. **Ítem**: Reglas específicas asignadas a un perfil de producto o servicio.
2. **Parte**: Reglas específicas de un Cliente o Proveedor (p. ej., Cliente exento, Gran contribuyente).
3. **Transacción**: Reglas aplicadas a un tipo o plantilla de transacción específica.
4. **Compañía**: Reglas por defecto (fallback) para la entidad.

## Estrategias de fusión (merge)

Cuando múltiples reglas entran en conflicto o se solapan, el `merge_strategy` define el resultado:

| Estrategia | Descripción |
| :--- | :--- |
| `override` | Una regla de mayor prioridad reemplaza a las reglas de menor prioridad para el mismo concepto (p. ej., IVA). |
| `append` | Las reglas de mayor prioridad se agregan junto a las de menor prioridad. |
| `exclude` | Una regla de mayor prioridad elimina las reglas de ese concepto de los niveles inferiores (p. ej., un cliente exento excluye el IVA). |
| `replace_group` | Una regla de mayor prioridad reemplaza TODAS las reglas de los niveles inferiores. |
