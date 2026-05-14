---
applyTo: "**/*.py"
---
# Accounting Python Rules

- **Schema:** Use `company` (not `company_id`) and `entity` for scoping.
- **Bases:** Follow `DocBase` (transactional) or `BaseTransaccion` (legacy/accounting).
- **Core:** GL is the single source of truth. Use `voucher_type`/`voucher_id` for links.
- **Immutability:** No hard deletes. Use `docstatus` and reversals (`is_reversal`, `reversal_of`).
- **Isolation:** Every query must strictly filter by `company` or `entity`.
- **Ledger:** Support multiple books via `GLEntry.ledger_id`. Módulos affect all active books.
- **AR/AP:** Projections of GL. Require `party_type` and `party_id`. Support partial allocations.
- **Inventory:** `StockLedgerEntry` and `StockValuationLayer` linked to vouchers. Item flags (`default_uom`, `is_stock_item`, etc.) are immutable after first use.
- **Naming:** Use `generate_identifier` and physical sequences. Tokens resolved via `posting_date`.
- **Advanced:** Analytical dimensions (`DimensionValue`), GI/IR (Purchase Reconciliation), and Period Close checks are mandatory.
- **Pattern:** Route -> Service -> Repository. Generic linking via `reference_type` + `reference_id`.
