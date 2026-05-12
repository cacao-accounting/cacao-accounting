CHECKLIST — Cacao Accounting (Data Framework)

---

## 🟥 1. CORE CONTABLE (bloque base — obligatorio primero)

* [ ] `account` (árbol contable)
* [ ] `gl_entry` (con `ledger_id`, `company_id`, multimoneda)
* [ ] `fiscal_year`
* [ ] `accounting_period` (con `is_closed`)
* [ ] Campos estándar en transacciones:

  * [ ] `docstatus`
  * [ ] `posting_date`
  * [ ] `document_date`
  * [ ] `company_id`

---

## 🟧 2. MULTI-COMPANY + PARTY SYSTEM

* [ ] `company`
* [ ] `party` (global)
* [ ] `company_party` (activación por compañía)
* [ ] `address`
* [ ] `contact`
* [ ] `party_address`
* [ ] `party_contact`

---

## 🟨 3. SERIES E IDENTIFICADORES

* [ ] `naming_series`
* [ ] `sequence`
* [ ] `series_sequence_map`
* [ ] resolución por `posting_date`
* [ ] prefijo por compañía
* [ ] soporte múltiples secuencias por serie
* [ ] `generated_identifier_log`

---

## 🟩 4. INVENTARIO (STRUCTURAL)

* [ ] `item`:

  * [ ] `type` (goods/service)
  * [ ] `is_stock_item`
  * [ ] `has_batch`
  * [ ] `has_serial_no`
  * [ ] `default_uom`
* [ ] `uom`
* [ ] `item_uom_conversion`
* [ ] `warehouse`
* [ ] `stock_entry`
* [ ] `stock_entry_item`
* [ ] `stock_ledger_entry`
* [ ] `stock_bin` (snapshot)

---

## 🟦 5. TRAZABILIDAD INVENTARIO

* [ ] `batch`
* [ ] `serial_number`
* [ ] reglas:

  * [ ] batch obligatorio si aplica
  * [ ] serial obligatorio si aplica
  * [ ] no modificar configuración después de uso

---

## 🟪 6. COMPRAS / VENTAS (STRUCTURAL)

* [ ] `purchase_order`
* [ ] `purchase_receipt`
* [ ] `purchase_invoice`
* [ ] `purchase_invoice_item`
* [ ] `sales_order`
* [ ] `delivery_note`
* [ ] `sales_invoice`
* [ ] `sales_invoice_item`

---

## 🟫 7. BANCOS

* [ ] `bank`
* [ ] `bank_account`
* [ ] `payment_entry`
* [ ] `payment_reference`
* [ ] `bank_transaction`

---

## ⬛ 8. ACCOUNT MAPPING (CRÍTICO)

* [ ] `item_account`
* [ ] `party_account`
* [ ] `company_default_account`

---

## 🟤 9. MULTIMONEDA (REAL)

* [ ] campos en TODAS las transacciones:

  * [ ] `transaction_currency`
  * [ ] `base_currency`
  * [ ] `exchange_rate`
* [ ] en `gl_entry`:

  * [ ] montos en moneda base
  * [ ] montos en moneda original

---

## ⚫ 10. MULTI-LEDGER

* [ ] `ledger`
* [ ] `ledger_id` en `gl_entry`
* [ ] generación de GL por cada libro
* [ ] regla: módulos operativos afectan todos los libros

---

## 🟥 11. GI / IR

* [ ] cuenta GR/IR por compañía
* [ ] flujo:

  * [ ] recepción → inventario vs GR/IR
  * [ ] factura → GR/IR vs AP
* [ ] `gr_ir_reconciliation` (opcional pero recomendado)

---

## 🟧 12. INVENTORY VALUATION

* [ ] `valuation_method` (FIFO / Moving Avg)
* [ ] (opcional) `stock_valuation_layer`

---

## 🟨 13. TAX STRUCTURE

* [ ] `tax`
* [ ] `tax_template`
* [ ] `tax_template_item`

---

## 🟩 14. PRICING

* [ ] `price_list`
* [ ] `item_price`

---

## 🟦 15. RECONCILIATION

* [ ] `reconciliation`
* [ ] `reconciliation_item`

---

## 🟪 16. REVALORIZACIÓN MONEDA

* [ ] `exchange_revaluation`
* [ ] `exchange_revaluation_item`

---

## 🟫 17. CIERRE CONTABLE

* [ ] `period_close_run`
* [ ] `period_close_check`

---

## ⬛ 18. DIMENSIONES CONTABLES

* [ ] `dimension_type`
* [ ] `dimension_value`
* [ ] `gl_entry_dimension`

---

## 🟤 19. REVERSIÓN CONTABLE

* [ ] `is_reversal`
* [ ] `reversal_of`

---

## ⚫ 20. AUDITORÍA

* [ ] `audit_log`
* [ ] before/after JSON

---

## ⚪ 21. COLABORACIÓN (MULTIUSER READY)

* [ ] `comment`
* [ ] `comment_mention`
* [ ] `assignment`
* [ ] `workflow`
* [ ] `workflow_state`
* [ ] `workflow_transition`
* [ ] `workflow_instance`
* [ ] `workflow_action_log`

---

## 📎 22. ARCHIVOS

* [ ] `file`
* [ ] `file_attachment`

---

## 🧠 23. PERFORMANCE / SNAPSHOTS

* [ ] `account_balance_snapshot`
* [ ] `stock_balance_snapshot`

---

# 🚀 ORDEN RECOMENDADO DE IMPLEMENTACIÓN

1. Core contable
2. Company + Party
3. Series
4. Inventory
5. GL + Multi-ledger + Multimoneda
6. Compras / Ventas
7. Bancos
8. Account mapping
9. GI/IR
10. Dimensiones + Tax + Pricing
11. Reconciliation
12. Cierre + Revalorización
13. Auditoría
14. Colaboración

---

# 🧭 LECTURA RÁPIDA (lo más crítico)

Si tuvieras que reducirlo a lo esencial:

👉 Sin esto, el sistema no funciona correctamente:

* GL (`gl_entry`)
* Multi-ledger
* Multimoneda real
* Series robustas
* Inventory + stock ledger
* Account mapping
* Party + company isolation
