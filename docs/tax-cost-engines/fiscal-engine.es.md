# Motor fiscal

El Motor fiscal es responsable de calcular todos los impuestos, retenciones y cargos fiscales.

## Lógica de cálculo

El motor sigue un proceso paso a paso:
1. **Ordenar reglas**: Las reglas se ordenan por su propiedad `order`.
2. **Determinar la base**: Según `base_mode`, el motor utiliza el total de bienes o un subtotal acumulado.
3. **Aplicar método**: Calcula el monto según `percentage`, `fixed` o `quantity`.
4. **Redondeo**: Aplica la política de redondeo configurada (HALF_UP, Bankers, etc.).
5. **Descomposición de impuestos**: Para los impuestos incluidos en el precio, el motor usa descomposición algebraica para resolver el monto neto cuando múltiples impuestos aplican al mismo nivel.
6. **Actualizar acumuladores**: Si la regla `participates_in_next_base`, su resultado se suma al subtotal para las reglas siguientes.

## Impuestos en cascada

La cascada se maneja usando `base_mode: "accumulated"` y definiendo `include_concepts`.

**Ejemplo de configuración para IVA en cascada:**
- Concepto: `IVA`
- Base Mode: `accumulated`
- Include: `["goods", "DAI", "ISC"]`

## Tratamiento contable

Cada línea de resultado se etiqueta con un tratamiento que guía al mapper contable:
- `capitalizable_inventory_cost`: Se suma al valor del inventario.
- `separate_tax_account`: Se registra en una cuenta contable (GL) dedicada (p. ej., IVA).
- `withholding_payable`: Se registra como pasivo al momento del pago.
- `withholding_receivable`: Se registra como activo al momento del cobro.
