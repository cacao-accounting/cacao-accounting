
Tras revisar en detalle el diff aportado de la arquitectura de motores de cálculo (FiscalEngine, LandedCostEngine, SettlementEngine, RoundingManager, etc.), se observa una base técnica muy sólida de diseño determinístico, orientado a objetos e inmutable mediante dataclasses.
Sin embargo, para cerrar formalmente la implementación y resolver los puntos listados en PENDIENTE.md, te sugiero priorizar las siguientes mejoras estructuradas en cuatro pilares (Precisión, Extensibilidad, Flujo y Errores):
### 1. Mejoras en RoundingManager y Distribución Financiera
En rounding.py, el método distribute_residual contiene una lógica de ajuste directo sobre el elemento mayor (max(shares)):
```python
idx = shares.index(max(shares))
rounded_shares[idx] += diff

```
 * **Riesgo:** Si existen valores idénticos compartiendo el máximo, .index() siempre seleccionará el primero, sesgando los redondeos sistemáticamente en listas repetitivas. Además, en transacciones comerciales, ajustar la línea de mayor valor no siempre es la regla de negocio esperada.
 * **Sugerencia:** Modifica el método para absorber el residuo centavo a centavo (o según la precisión mínima) distribuyéndolo secuencialmente entre los elementos de forma ponderada o circular, o bien mantén una lista interna de elementos ya ajustados en ejecuciones en cascada para no sobrecargar de forma sistemática la misma línea del documento.
### 2. Robustez y Descomposición del Impuesto Incluido en el FiscalEngine
En engine.py, la lógica de descomposición para múltiples impuestos incluidos en el precio realiza una suma simple de tasas utilizando el campo order:
```python
sum_included_rates = sum(
    (r.rate for r in (all_rules or []) if r.included_in_price and r.order == rule.order), Decimal("0")
)

```
 * **Deficiencia:** Si un modelo fiscal posee dos impuestos incluidos en el precio en cascada (donde la base de uno incluye al otro), pero están mapeados en diferentes niveles de order, la fórmula fallará al subestimar o sobreestimar sum_included_rates.
 * **Sugerencia:** La descomposición de impuestos incluidos concurrentes debe calcularse de manera simultánea resolviendo un sistema de ecuaciones lineales simple o agrupando recursivamente las tasas asociadas que afecten a la misma base real de mercancía, sin restringir rígidamente a que compartan el mismo order.
### 3. Transición hacia Grafos de Dependencia (DAG)
El archivo PENDIENTE.md ya identifica la necesidad de evolucionar a un DAG. Actualmente, usas una validación de ciclo basada en un DFS profundo (_has_circular_dependency) y un ordenamiento plano secuencial con sorted(..., key=lambda x: x.order).
 * **Mejora para Cierre:** Sustituye el ordenamiento plano por un **Ordenamiento Topológico** genuino utilizando las listas include_concepts y depends_on. Esto permitirá prescindir del campo manual order (el cual es propenso a errores humanos de configuración en sistemas multi-jurisdiccionales complejos) y automatizará de forma nativa la secuencia exacta en la que el FiscalEngine debe procesar las bases acumuladas.
### 4. Coherencia y Límites en LandedCostEngine
En landed_cost/engine.py, el prorrateo de costos accesorios se ejecuta al final de la iteración mediante un ajuste del último elemento para absorber residuos:
```python
if i == len(item_list) - 1:
    allocated_amount = rule_amount - total_allocated_for_rule

```
 * **Deficiencia:** No hay validaciones previas para evitar divisiones por cero si un lote entero de ítems tiene cantidades, pesos o volúmenes en cero (por ejemplo, errores de entrada de datos donde total_qty o total_weight resulta 0). Adicionalmente, el residuo se calcula sobre el final de la lista plana de ítems y no utilizando el método financiero unificado de distribute_residual que ya construiste en el RoundingManager.
 * **Sugerencia:** 1. Utiliza rounding_manager.distribute_residual para repartir los montos de la regla entre las líneas en lugar del parche if i == len(item_list) - 1.
   2. Lanza advertencias (warnings.append(...)) o errores controlados explícitos si el método de distribución seleccionado (como by_weight) se ejecuta sobre ítems que carecen de dicha métrica en sus propiedades, evitando que el costo capitalizable se desvanezca o genere un ZeroDivisionError.
### 5. Consolidación de Errores y Mensajes de Auditoría
Dentro del bucle principal de FiscalEngine, se captura una excepción genérica:
```python
except Exception as e:
    errors.append(f"Error calculating rule {rule.name}: {str(e)}")

```
 * **Sugerencia:** Dado que se trata de un core contable enterprise, evita silenciar excepciones críticas de código (como AttributeError o TypeError internos). Captura únicamente excepciones de lógica de negocio (por ejemplo, InvalidRuleParameter) e incluye el line_id o el item_id afectado en el mensaje para facilitar el rastreo en producción cuando se use el motor a través del BusinessEventOrchestrator.
### Siguientes pasos recomendados para el "Merge":
 1. **Implementar el Posting Builder:** Vincula el AccountingMapper con los modelos persistidos de SQLAlchemy en posting.py (los cuales ya usan ULID de 26 caracteres) para transformar el JournalEntryProforma en registros contables definitivos de la base de datos.
 2. **Ampliar SettlementEngine:** Añade el soporte para descuentos por pronto pago y revaluaciones de tipo de cambio por saldos pendientes (completando los requerimientos de multi-moneda de CalculationContext).
