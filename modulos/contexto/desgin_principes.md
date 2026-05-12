PRINCIPIOS DE DISEÑO (no negociables)
1.1 Ledger como fuente de verdad
General Ledger (GL) = única fuente contable
Todo documento financiero debe terminar en GL
Nada “impacta balances” fuera del GL
1.2 Subledgers especializados
AR (Accounts Receivable)
AP (Accounts Payable)
Stock Ledger
Bank Ledger

Estos son derivados o paralelos, pero siempre reconciliables con GL.

1.3 Modelo basado en documentos + líneas

Patrón universal:

<Documento Header>
<Documento Line Items>

Ejemplo:

Sales Invoice + Sales Invoice Item
Journal Entry + Journal Entry Line
1.4 Tipificación por ENUM / flags (no tablas nuevas)

Ejemplo:

stock_entry.purpose
payment_entry.type
invoice.is_return

Esto evita explosión de tablas.

🧠 2. DOMINIOS (BOUNDARIES)
Core Domains:
Accounting Core
Party & Identity
Transactions Engine
Stock Engine
Banking Engine
Configuration
🗄️ 3. ESQUEMA BASE (NIVEL ESTRUCTURAL)
🔵 3.1 ACCOUNTING CORE
Tables
account
id
code
name
type (asset, liability, equity, income, expense)
parent_id
currency
is_group
gl_entry ⚠️ (CRÍTICO)
id
posting_date
account_id
debit
credit
party_type
party_id
voucher_type
voucher_id
company_id
currency
exchange_rate
fiscal_year
accounting_period
currency
exchange_rate
🟣 3.2 PARTY SYSTEM (compartido)
party
id
type (customer, supplier)
name
tax_id
address
contact
🟢 3.3 COMPRAS (AP)
purchase_invoice
id
supplier_id
posting_date
total
is_return
purchase_invoice_item
id
invoice_id
item_id
qty
rate
amount
purchase_order
purchase_receipt
🟡 3.4 VENTAS (AR)
sales_invoice
id
customer_id
posting_date
total
is_return
is_pos
sales_invoice_item
sales_order
delivery_note
🟤 3.5 INVENTARIO
Master
item
id
name
type (stock, service, asset)
warehouse
id
parent_id
Movimientos
stock_entry
id
purpose (issue, receipt, transfer, manufacture, repack)
posting_date
stock_entry_item
item_id
source_warehouse_id
target_warehouse_id
qty
valuation_rate
Ledger
stock_ledger_entry ⚠️
item_id
warehouse_id
qty_change
valuation_rate
voucher_type
voucher_id
🟠 3.6 BANCOS
bank
bank_account
id
account_id (GL link)
payment_entry
id
type (receive, pay, transfer)
party_id
amount
payment_reference
payment_id
reference_doctype
reference_id
allocated_amount
bank_transaction
id
bank_account_id
amount
reconciled
⚙️ 3.7 CONFIGURACIÓN
company
user
role
permission
number_series
tax_template
price_list
uom
🔗 4. RELACIONES CLAVE (CRÍTICAS)
Flujo ventas
Sales Order
   ↓
Delivery Note
   ↓
Sales Invoice
   ↓
GL Entry
   ↓
Payment Entry
Flujo compras
Purchase Order
   ↓
Purchase Receipt
   ↓
Purchase Invoice
   ↓
GL Entry
   ↓
Payment Entry
Flujo inventario
Stock Entry
   ↓
Stock Ledger Entry
   ↓
GL Entry (si es valuado)
⚠️ 5. DECISIONES ARQUITECTÓNICAS IMPORTANTES
5.1 No acoples lógica a tablas

Tu DB debe ser:

Declarativa
Neutral
Sin lógica de negocio dura
5.2 Usa “voucher pattern”

Todos los documentos financieros deben tener:

voucher_type
voucher_id

Esto permite:

Auditoría
Reversión
Trazabilidad completa
5.3 Soporte multi-moneda desde el día 1

Campos obligatorios:

base_amount
account_currency_amount
exchange_rate
5.4 Soft delete + docstatus
draft (0)
submitted (1)
cancelled (2)

Nunca borres transacciones contables.

🧪 6. CAPAS FUTURAS (que debes anticipar)

Aunque no las implementes aún:

Workflow engine
Tax engine
Pricing engine
Reconciliation engine
Reporting engine (materialized views)
🧩 7. ERRORES COMUNES A EVITAR

❌ Separar AR/AP del GL
❌ No usar ledger (solo totales en invoices)
❌ No versionar documentos
❌ No permitir reversión contable
❌ Mezclar inventario con contabilidad sin capa intermedia
