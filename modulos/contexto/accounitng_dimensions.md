DIMENSIONES CONTABLES (CRÍTICO)

Ahora mismo solo tienes cuentas (account) y compañía. Eso es insuficiente.

Necesitas soporte para dimensiones analíticas:

Ejemplos:
Centro de costo
Proyecto
Departamento
Sucursal
Estructura mínima:
dimension_type
dimension_value
gl_entry_dimension

📌 Regla:

Un gl_entry debe poder tener 0..N dimensiones

🧾 2. TAX ENGINE (aunque no implementes lógica aún)

Si no modelas impuestos desde ahora, después rompes invoices.

Necesitas:
tax
tax_category
tax_rule
tax_template
tax_template_item

📌 Incluso si no calculas:

Debes poder almacenar impuestos por línea y por documento

💲 3. PRICING (mínimo estructural)

Aunque no hagas lógica de precios:

price_list
item_price
price_list_currency

📌 Esto evita hardcodear precios en documentos

🧮 4. ACCOUNTING MAPPING (MUY IMPORTANTE)

Ahora mismo no definiste cómo se asignan cuentas.

Necesitas:

item_account
party_account
company_default_account

Ejemplo:

cuenta de ingreso por item
cuenta de gasto por item
cuenta por pagar proveedor

📌 Sin esto, no puedes generar GL correctamente

🏦 5. RECONCILIATION LAYER

Tienes pagos, pero no conciliación real.

Necesitas:
reconciliation
reconciliation_item

Para:

matching invoice ↔ payment
matching bank ↔ payment
📦 6. VALUACIÓN DE INVENTARIO

Tu modelo de stock está bien, pero falta:

Campo crítico:
valuation_method en item o company
FIFO
Moving Average
Tabla opcional futura:
stock_valuation_layer

📌 Si no lo contemplas ahora:

luego no podrás calcular costo de ventas correctamente

🔁 7. REVERSIÓN CONTABLE (fundamental)

Necesitas soporte estructural para:

reversals

Campos en documentos:

reversal_of
is_reversal

📌 Nunca deletes → siempre reversas

🧾 8. DOCUMENT LIFECYCLE

Ya tienes docstatus, pero falta formalizar:

Campos mínimos en TODAS las transacciones:

docstatus
posting_date
document_date
company_id
🔐 9. MULTI-COMPANY AISLATION (MUY IMPORTANTE)

Debes garantizar:

que datos de una compañía no contaminen otra
Reglas:
TODO lo transaccional tiene company_id
índices compuestos:
(company_id, identifier)
🧠 10. EVENTUAL CONSISTENCY / PROYECCIONES

Aunque no lo implementes:

Debes permitir:

materialized views
tablas de resumen

Ejemplo:

account_balance_snapshot
stock_balance_snapshot
📊 11. AUDITORÍA REAL (no solo timestamps)

Te falta:

audit_log

Con:

before/after
user
action
🧩 12. BLOQUEO DE PERÍODOS

Necesitas:

accounting_period
is_closed

📌 Regla futura:

no se puede postear en períodos cerrados

📦 13. STOCK BINNING (performance)

Para evitar recalcular siempre:

stock_bin
item_id
warehouse_id
actual_qty
⚠️ 14. EDGE CASES QUE DEBES SOPORTAR

Tu modelo debe poder manejar:

devoluciones parciales
pagos parciales
múltiples monedas en un mismo documento
descuentos por línea y globales
cargos adicionales (freight, insurance)
🧭 RESUMEN EJECUTIVO

Te faltan 4 capas clave:

🔴 Crítico (hazlo ya)
Dimensiones contables
Account mapping
Document lifecycle completo
Multi-company isolation
🟠 Muy importante
Tax structure
Reconciliation
Inventory valuation
🟡 Escalabilidad
Pricing
Audit log
Snapshots
