Implementation Requirement (Ampliación)
Cacao Accounting — Third Party Accounting (Balances & Temporal Consistency)
1. 🎯 Objetivo (Extendido)

Además de asociar movimientos a terceros, el sistema debe:

Calcular el saldo por documento (invoice, payment, etc.)
Determinar el saldo total por tercero (cliente/proveedor)
Permitir consultar saldos en cualquier fecha pasada
Garantizar resultados consistentes y repetibles
2. 🧱 Principio Base

El saldo de un tercero NO se guarda como valor fijo.

Se define como:

✔ Suma de partidas abiertas (open items) derivadas del GL

3. 📄 Saldo por Documento
3.1 Campo requerido en documentos

En:

sales_invoice
purchase_invoice
(y cualquier documento con impacto AR/AP)

Debe existir:

outstanding_amount
base_outstanding_amount
3.2 Regla

El saldo de un documento =
monto original − monto conciliado (allocations)

4. 🔗 Modelo de Aplicación (Allocations)
Tabla: payment_reference (o equivalente)
id
payment_id
reference_type (invoice)
reference_id
allocated_amount
allocation_date
Reglas:
Soporta pagos parciales
Soporta múltiples pagos por factura
Soporta un pago aplicado a múltiples facturas
5. 📊 Saldo por Tercero
Definición:

Saldo del cliente/proveedor =
SUM(outstanding_amount de todas las partidas abiertas)

Alternativa equivalente:

SUM(GL con party_id) − SUM(aplicaciones)

6. 🕒 Consistencia Temporal (CRÍTICO)
6.1 Problema a resolver

Poder responder:

“¿Cuál era el saldo de este cliente el 31 de marzo?”

6.2 Requisito estructural

TODAS las entidades relevantes deben tener:

posting_date

Incluye:

invoices
payments
allocations
6.3 Regla clave

Las conciliaciones afectan el saldo a partir de su allocation_date

6.4 Implicación

Un pago aplicado en abril:

NO afecta saldo de marzo
SÍ afecta saldo de abril en adelante
7. 🧠 Modelo para Cálculo Histórico

El sistema debe permitir calcular:

Saldo a una fecha T:
SUM(GL hasta fecha T)
−
SUM(allocations hasta fecha T)
8. ⚠️ Reglas Críticas
8.1 Inmutabilidad temporal
No modificar posting_date
No modificar allocation_date después de registro
8.2 Orden lógico
Una asignación no puede tener fecha anterior al documento aplicado
8.3 Consistencia
El saldo nunca puede ser negativo (salvo créditos controlados)
9. 📦 Open Item Strategy

El sistema debe funcionar bajo modelo:

✔ Open Items (partidas abiertas)

Cada documento:

nace con saldo completo
se reduce mediante conciliaciones
10. 🚀 Estrategia de Implementación
10.1 Opción recomendada

NO confiar únicamente en campo persistido

✔ Usar:

campo outstanding_amount (cache)
cálculo dinámico (source of truth)
10.2 Validación
El valor persistido debe poder recalcularse siempre
11. 📊 Aging

Debe ser posible calcular:

buckets por antigüedad

Basado en:

posting_date
saldo pendiente
12. 🔄 Reversión

Si un documento es reversado:

sus allocations deben revertirse
su saldo vuelve a estado original
13. 🧪 Casos que debe soportar
Pago parcial
Sobrepago
Nota de crédito aplicada
Pago anticipado
Reversión de pago
Aplicaciones cruzadas
14. 🚫 Anti-Patrones Prohibidos

❌ Guardar saldo total en tabla de cliente
❌ No versionar allocations
❌ Modificar histórico
❌ Ignorar fechas en conciliación

15. 📌 Regla de Oro

El saldo es siempre una función del tiempo
