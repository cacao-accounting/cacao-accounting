---
applyTo: "**/*.py"
---

# Cacao Accounting Python Instructions
This document is aligned with the live schema defined in `cacao_accounting/database/__init__.py` and the identifier helpers in `cacao_accounting/database/helpers.py`.
When proposing or generating Python changes, prefer the existing contracts below over introducing alternate naming conventions.

## Schema Naming Contract (Current Codebase)

- Company scoping is currently represented mainly with `company` (string FK to `entity.code`), not `company_id`.
- Organizational ownership also uses `entity` in several core models (`Accounts`, `Book`, `FiscalYear`, etc.).
- For new transactional models, follow existing base contracts (`DocBase`, `BaseTransaccion`) instead of inventing parallel field sets.

## Base Classes and Required Columns

- `BaseTabla` provides shared metadata (`id`, `status`, `created`, `created_by`, `modified`, `modified_by`).
- `DocBase` is the transactional lifecycle base and must remain the reference for:
  - `docstatus` (0 draft, 1 submitted, 2 cancelled)
  - `posting_date`, `document_date`
  - `company`
  - `transaction_currency`, `base_currency`, `exchange_rate`
  - `is_reversal`, `reversal_of`
  - `voucher_type`, `voucher_id`
- `BaseTransaccion` is used for legacy/accounting docs and includes `entity`, `book`, `date`, `serie`, and sequence metadata.

## Non-Negotiable Accounting Rules

- Treat GL as the single source of accounting truth. Do not implement alternative balance sources outside GL.
- Use document patterns with header + items for transactional structures.
- Use voucher linkage consistently via `voucher_type` and `voucher_id` when referencing accounting impacts.
- Use generic cross-module references with `reference_type` and `reference_id` for transversal entities.

## Immutability and Lifecycle

- Never hard-delete accounting transactions. Use `docstatus` and reversal strategy.
- Reversal strategy is mandatory in transactional entities: `is_reversal` and `reversal_of`.
- Preserve temporal consistency: avoid mutating financial dates (`posting_date`, `allocation_date`) after posting.

## Multi-Company and Query Isolation

- Every transactional record must carry company scope (`company` and/or `entity` per current module pattern).
- Repositories and queries must enforce company isolation (filter by `company` or `entity` consistently in joins and lookups).
- Avoid designs that allow cross-company leakage by default.

## Multi-Ledger and Multi-Currency

- Support multiple ledgers natively. Use one business document that can generate multiple GL lines by `ledger_id`.
- Do not duplicate one journal/document per ledger.
- Do not restrict currency by party, account, customer, or supplier.
- Keep alignment with current ledger models: `Book` for ledger definitions and `GLEntry.ledger_id` for per-ledger posting.

## AR/AP and Third-Party Accounting

- AR/AP are projections of GL, not separate accounting ledgers.
- For receivable/payable accounts, require third-party linkage (`party_type`, `party_id`).
- Support partial allocations and many-to-many payment matching through reference tables.
- Keep balance logic time-aware: historical balances depend on dates of entries and allocations.

## GL and Stock Ledger Consistency

- `GLEntry` must keep voucher traceability with `voucher_type` and `voucher_id`.
- Keep per-entry company/date/ledger consistency (`company`, `posting_date`, `ledger_id`).
- `StockLedgerEntry` and `StockValuationLayer` must remain voucher-linked and company-scoped.

## Inventory, UOM, Batch, and Serial

- Respect item typing:
  - `service` must never be stock item.
  - stock ledger impacts only for stock-controlled goods.
- Store conversion factors per item (not globally).
- Persist stock ledger quantities in item base UOM.
- If `has_batch` is true, require batch in movements. If `has_serial_no` is true, require serial tracking.
- After item usage in transactions, treat structural flags (`default_uom`, `is_stock_item`, `has_batch`, `has_serial_no`) as immutable.

## Naming Series and Identifiers

- Use naming series + physical sequence separation.
- Resolve dynamic series tokens using `posting_date` (never `created_at`).
- Support multiple sequences per logical series when context requires it.
- Keep identifier generation auditable.
- Keep compatibility with helper contracts in `database/helpers.py`:
  - `resolve_naming_series_prefix`
  - `get_next_sequence_value`
  - `format_sequence_value`
  - `generate_identifier`
- Supported tokens are `*YYYY*`, `*YY*`, `*MMM*`, `*MM*`, `*DD*` and currently use Spanish month abbreviations in helper logic.

## Contacts, Addresses, and Reuse

- Model contacts and addresses as reusable entities linked through association tables.
- Avoid customer-only/supplier-only duplicate contact or address tables.
- Prefer soft deactivation (`is_active`) over deletion for records in use.

## Reconciliation, Audit, and Derived Data

- Reconciliation must support partial matching and remain traceable.
- Audit logs should be immutable and include before/after snapshots for critical entities.
- Snapshots/bins are derived optimization layers, never the source of truth.

## Advanced Domains (Already in Current Schema)

- GI/IR reconciliation models exist and must remain reconcilable by company and source docs.
- Exchange revaluation models exist and must generate adjustments without mutating origin transactions.
- Period close models exist (`PeriodCloseRun`, `PeriodCloseCheck`) and should enforce pre-close checks.
- Analytical dimensions are modeled through `DimensionType`, `DimensionValue`, and `GLEntryDimension`.
- Tax, pricing, account mapping, reconciliation, and snapshot models are already present; extend them without breaking their company-scoped design.

## Generic Linking Pattern

- For transversal features (comments, assignments, workflow instances, attachments, reconciliation references), use the existing generic pair `reference_type` + `reference_id`.
- Do not replace this pattern with per-module hard FK tables.

## Modeling Style

- Prefer enums/flags over creating many subtype tables when behavior differs by type.
- Keep domain logic out of route handlers; route -> service -> repository separation applies.
- Keep repository layer responsible for DB access and integrity-aware query composition.
