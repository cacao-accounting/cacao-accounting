# INFORME DE AUDITORÍA: MOTOR DE CÁLCULO DE IMPUESTOS Y CARGOS

**Fecha de la Auditoría:** Agosto 2026
**Auditor:** Jules, Consultor de Ingeniería de Software
**Área de Enfoque:** Motor de Cálculo Fiscal, Motor de Precios y Reglas de Impuestos

---

## 1. RESUMEN EJECUTIVO

Se ha realizado una auditoría exhaustiva, profunda y de nivel de código al motor de cálculo de impuestos y cargos de **Cacao Accounting**. El sistema cuenta con dos motores de cálculo distintos que conviven para diferentes propósitos:
1. **Motor de Impuestos Clásico (`calculate_taxes`):** Utilizado para plantillas de impuestos estáticas (`TaxTemplate`) asociadas a documentos u operaciones clásicas.
2. **Motor Fiscal Moderno (`FiscalEngine`):** Un motor declarativo, determinista y basado en grafos de dependencias (`TaxRuleContext`) diseñado para resolver y calcular impuestos en cascada complejos y dinámicos.

### Calificación de la Auditoría: **EXCELENTE CON OBSERVACIONES TÉCNICAS**
El diseño del nuevo `FiscalEngine` demuestra una gran rigurosidad de ingeniería matemática y contable (como ordenamiento topológico y descomposición de tasas incluidas concurrentes). Sin embargo, la coexistencia de ambos motores introduce discrepancias lógicas y de redondeo que deben documentarse y controlarse para garantizar la consistencia absoluta en reportes financieros y submayores.

---

## 2. ARQUITECTURA Y COMPONENTES DEL SISTEMA

El motor de impuestos se divide en las siguientes capas lógicas:

### Capa de Persistencia y Modelos (`cacao_accounting/database/`):
- `Tax`: Representa impuestos y cargos con sus tasas fijas o porcentuales y cuentas contables asociadas.
- `TaxTemplate` y `TaxTemplateItem`: Permiten agrupar impuestos secuencialmente para transacciones.
- `TaxRule`: Reglas fiscales configurables utilizadas por el nuevo motor de cálculo.
- `DocumentTaxSummary` y `DocumentTaxLine`: Snapshots persistidos que garantizan que el cálculo original de un documento permanezca inmutable ante modificaciones futuras de tasas.

### Capa de Servicios (`cacao_accounting/tax_pricing_service.py` y `tax_rule_service.py`):
- `calculate_taxes(document, template_id)`: Método clásico de plantillas.
- `build_tax_rule_contexts(...)`: Traduce reglas persistidas de la base de datos a contextos consumibles por el motor.

### Capa de Ejecución Fiscal (`cacao_accounting/accounting_engine/fiscal/`):
- `FiscalEngine`: Motor central de cálculo con ordenamiento por grafos, redondeo por pasos y descomposición de tasas incluidas.
- `RuleResolver`: Resuelve la prioridad y fusión de reglas (Ítems, Terceros, Transacciones, Compañías) mediante diferentes estrategias de combinación.

---

## 3. HALLAZGOS TÉCNICOS DETALLADOS

### Hallazgo A: Descomposición de Impuestos Incluidos (Incongruencia entre Motores)
- **Severidad:** ALTO (Riesgo de discrepancia en montos)
- **Descripción:**
  - El **Motor Fiscal Moderno (`FiscalEngine`)** maneja de forma correcta la descomposición matemática de impuestos incluidos en el precio (`included_in_price=True`), calculando el monto neto real a partir del precio bruto y deduciendo el impuesto proporcionalmente. Soporta múltiples impuestos incluidos de la misma secuencia sumando sus tasas antes de la división.
  - El **Motor Clásico (`calculate_taxes`)** calcula los impuestos incluidos como aditivos simples (`base_amount * rate / 100`) y simplemente acumula el resultado en un totalizador `inclusive_total`, sin alterar el monto neto ni realizar descomposición real del precio.
- **Impacto:** Si un documento usa el motor clásico y declara un impuesto incluido, la base imponible y el total calculado diferirán de los generados bajo el motor moderno.
- **Recomendación:** Se sugiere migrar progresivamente todas las operaciones transaccionales al `FiscalEngine` unificado y descontinuar el motor de plantillas clásico para evitar discrepancias.

### Hallazgo B: Redondeo por Pasos y Acumulación
- **Severidad:** MEDIO
- **Descripción:**
  - El motor clásico redondea cada línea de impuesto de forma independiente usando `amount.quantize(Decimal("0.0001"))` a 4 decimales.
  - `FiscalEngine` delega el redondeo al `RoundingManager` en cada paso del cálculo, redondeando a la precisión configurada de la moneda/política (usualmente 2 decimales para la presentación final).
- **Impacto:** En cascadas muy largas de impuestos con tasas acumuladas, la diferencia en el momento y la precisión de la cuantización puede producir diferencias marginales de céntimos en el total general.
- **Recomendación:** Asegurar que las pruebas unitarias validen siempre con políticas de redondeo estrictas de dos decimales para el total neto final visible al usuario.

### Hallazgo C: Prioridad de Resolución en el `RuleResolver`
- **Severidad:** MEDIO (Lógica de Precedencia)
- **Descripción:**
  - En `RuleResolver._rule_groups(...)`, los grupos de reglas se ordenan de menor a mayor prioridad: `[item_rules, party_rules, transaction_rules, company_rules]`.
  - Sin embargo, `RuleResolver._applicable_rules` recorre la lista en orden *invertido* (`reversed`), procesando primero las reglas de mayor prioridad (compañías) y de último las de menor prioridad (ítems).
  - Al aplicar la estrategia de fusión por defecto (`resolved_rules[rule.concept] = rule`), la regla evaluada al final (ítem) sobrescribe la regla evaluada al principio (compañía).
- **Impacto:** Esto significa que las reglas específicas de un artículo (ítem) toman precedencia y anulan las reglas globales de la compañía. Desde la perspectiva de especificidad contable esto es correcto (la regla específica de artículo debe primar sobre la genérica de compañía). Sin embargo, si la intención del diseño era que `company_rules` fuera la máxima restricción jerárquica inapelable, el orden actual funciona de forma inversa.
- **Recomendación:** Validar y documentar de forma explícita que las reglas de ítems deben sobrescribir las reglas de compañía por diseño de especificidad, o bien ajustar el orden si se requiere lo contrario.

### Hallazgo D: Blindaje contra Referencias Negativas
- **Severidad:** BAJO
- **Descripción:** En `calculate_taxes`, si el total del documento (`base_amount`) es menor a 0, el motor clásico aplica de forma defensiva la función absoluta `base_amount = abs(base_amount)`.
- **Impacto:** Si bien esto previene errores aritméticos al calcular tasas en documentos negativos (como notas de crédito de devolución), también silencia la naturaleza negativa del importe base del documento, lo que podría llevar a que se reporten impuestos con el signo cambiado si la lógica superior no maneja de forma explícita el signo de la devolución. En cambio, el `FiscalEngine` maneja el flujo de dirección y signo de forma determinista usando el contexto de la transacción.

### Hallazgo E: Aislamiento por Compañía (Multi-Company Isolation)
- **Severidad:** ALTO (Verificado como **OK/Seguro**)
- **Descripción:** Se ha verificado que la función `build_tax_rule_contexts` limita estrictamente las reglas mediante:
  `query = query.where(or_(TaxRule.company == company, TaxRule.company.is_(None)))`.
  Esto garantiza que las compañías solo recuperen sus propias reglas o las reglas globales del sistema, previniendo fugas accidentales de configuraciones fiscales entre distintas entidades legales.

---

## 4. SUGERENCIAS Y RECOMENDACIONES DE MEJORA

1. **Unificación de Motores:** Consolidar el cálculo de impuestos utilizando únicamente el `FiscalEngine` y su API asociada en todos los builders transaccionales de compras, ventas y tesorería.
2. **Ampliación de Pruebas de Redondeo:** Implementar pruebas que validen explícitamente escenarios de arrastre de decimales y redondeo monetario ante múltiples tasas concurrentes.
3. **Validación de Signos:** Eliminar los usos de `abs()` en montos base de impuestos y asegurar que las notas de crédito utilicen el signo y sentido transaccional para calcular importes proporcionales correctos.

---

## 5. INVENTARIO DE VERIFICACIÓN DE CALIDAD

Se ha diseñado e implementado una nueva suite de pruebas de auditoría (`tests/test_tax_engine_audit_cases.py`) para verificar formalmente las capacidades y límites del motor fiscal bajo escenarios extremos:
- **Descomposición Multitasa Incluida:** Verificación del algoritmo de reversión fiscal cuando coexisten múltiples impuestos incluidos al mismo nivel.
- **Cascada con Redondeo Estricto:** Verificación matemática de la consistencia de los deltas y acumulados con redondeo contable.
- **Manejo de Bases de Documento Vacías o de Cero:** Verificación de robustez aritmética.
- **Resolución de Prioridad de Reglas:** Verificación del comportamiento de especificidad del resolvedor de reglas.
