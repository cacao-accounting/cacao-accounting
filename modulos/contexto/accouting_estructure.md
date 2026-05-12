Implementation Requirement
Cacao Accounting — Core Gaps Completion (Data Framework)
1. 🎯 Objetivo

Extender el framework de base de datos existente para cubrir capacidades críticas faltantes que garanticen:

Integridad contable completa
Clasificación analítica
Escalabilidad multi-compañía
Soporte para escenarios reales de negocio
Preparación para lógica futura sin rediseño
2. 📊 Dimensiones Contables (Analytical Dimensions)
2.1 Objetivo

Permitir clasificar movimientos contables más allá de la cuenta.

2.2 Modelo
dimension_type
id
name (cost_center, project, department, etc.)
is_active
dimension_value
id
dimension_type_id
value
company_id (nullable)
gl_entry_dimension
id
gl_entry_id
dimension_type_id
dimension_value_id
2.3 Reglas
Un gl_entry puede tener múltiples dimensiones
Las dimensiones pueden ser globales o por compañía
No se permite eliminar dimensiones en uso
3. 🧾 Tax Structure (Estructura de Impuestos)
3.1 Objetivo

Soportar impuestos sin implementar lógica de cálculo aún.

3.2 Modelo
tax
id
name
rate
type (percentage, fixed)
account_id
tax_template
id
name
company_id
tax_template_item
id
tax_template_id
tax_id
sequence
is_inclusive
3.3 Reglas
Los impuestos deben poder asociarse a:
documentos
líneas
No se permite eliminar impuestos en uso
4. 💲 Pricing (Estructura de Precios)
4.1 Modelo
price_list
id
name
currency
company_id (nullable)
item_price
id
item_id
price_list_id
price
uom_id
4.2 Reglas
Un ítem puede tener múltiples precios
Soporte multi-moneda obligatorio
5. 🧮 Account Mapping
5.1 Objetivo

Determinar cómo se asignan cuentas contables.

5.2 Modelo
item_account
id
item_id
company_id
income_account_id
expense_account_id
inventory_account_id
party_account
id
party_id
company_id
receivable_account_id
payable_account_id
company_default_account
id
company_id
default_receivable
default_payable
default_cash
default_bank
5.3 Reglas
Resolución jerárquica:
item_account
party_account
company_default
6. 🔗 Reconciliation Layer
6.1 Modelo
reconciliation
id
company_id
date
type (bank, AR, AP)
reconciliation_item
id
reconciliation_id
reference_type
reference_id
amount
6.2 Reglas
Permitir matching parcial
No duplicar conciliaciones
7. 📦 Inventory Valuation
7.1 Modelo
Campo en item o company
valuation_method
FIFO
MOVING_AVERAGE
(Futuro) stock_valuation_layer
id
item_id
qty
value
source_voucher
7.2 Reglas
Método definido antes de transacciones
No modificable después
8. 🔁 Reversión Contable
8.1 Campos requeridos

En todas las tablas transaccionales:

is_reversal (boolean)
reversal_of (FK nullable)
8.2 Reglas
No eliminar registros
Toda corrección se hace vía reversión
9. 📄 Document Lifecycle
9.1 Campos obligatorios

En TODAS las transacciones:

docstatus
posting_date
document_date
company_id
9.2 Estados
0 → Draft
1 → Submitted
2 → Cancelled
10. 🔐 Multi-Company Isolation
10.1 Reglas
Todo registro transaccional debe incluir company_id
Índices compuestos obligatorios:
(company_id, id)
(company_id, series)
10.2 Restricción
No permitir joins sin company_id
11. 📊 Snapshots & Performance
11.1 Modelo
account_balance_snapshot
account_id
company_id
balance
stock_balance_snapshot
item_id
warehouse_id
qty
11.2 Reglas
Son derivados (no fuente de verdad)
Recalculables
12. 📜 Auditoría
12.1 Modelo
audit_log
id
entity_type
entity_id
action (insert, update, delete)
before_data (JSON)
after_data (JSON)
user_id
timestamp
12.2 Reglas
Obligatorio para tablas críticas
Inmutable
13. 🔒 Accounting Period Control
13.1 Modelo
accounting_period
id
fiscal_year_id
start_date
end_date
is_closed
13.2 Regla
No permitir registros en períodos cerrados
14. 📦 Stock Binning
14.1 Modelo
stock_bin
item_id
warehouse_id
company_id
actual_qty
14.2 Reglas
Derivado del ledger
Optimización de lectura
15. ⚠️ Casos que el modelo debe soportar
Pagos parciales
Facturas parciales
Devoluciones parciales
Multi-moneda por documento
Descuentos por línea
Cargos adicionales
16. 🚀 Criterio de Éxito

El sistema será exitoso si:

No requiere rediseño estructural para casos reales
Permite implementar lógica contable completa
Mantiene consistencia entre todos los subledgers
Soporta multi-compañía sin colisiones
