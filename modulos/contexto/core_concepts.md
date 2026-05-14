# Cacao Accounting - Core Concepts

## 1. Accounting Core & GL
- **GLEntry:** Single source of truth. Linked via `voucher_type` and `voucher_id`.
- **Multi-Ledger:** Every transaction impacts all active books (`Book`).
- **Multi-Currency:** Support for base and original currencies. `exchange_rate` mandatory.
- **Immutability:** No hard deletes. Corrections via reversal documents or adjust entries.
- **Posting Date:** Official accounting date (not creation date).

## 2. Analytical Dimensions
- **Structure:** `DimensionType`, `DimensionValue`, and `GLEntryDimension`.
- **Built-in:** `CostCenter`, `Unit`, and `Project` are first-class citizens in GL.
- **Flexibility:** Support for 0..N custom dimensions per GL entry.

## 3. Inventory Framework
- **Source of Truth:** `StockLedgerEntry` (existence and cost).
- **Performance:** `StockBin` (snapshot of current balance).
- **Valuation:** FIFO and Moving Average. `StockValuationLayer` tracks unit costs.
- **Immutable Flags:** Once used in transactions, `default_uom`, `has_batch`, and `has_serial_no` are immutable.
- **Service Items:** Items with `type="service"` never impact inventory.

## 4. Document Flow & Lifecycle
- **States:** 0 (Draft), 1 (Submitted), 2 (Cancelled).
- **Traceability:** `DocumentRelation` tracks upstream/downstream links.
- **Reference Pattern:** Generic `reference_type` + `reference_id` for transversal links (comments, files).
- **Correction Pattern:** Correction documents must reference origin. No direct mutation of history.

## 5. Multi-Company Isolation
- **Scoping:** Every transactional and master data record must have a `company` or `entity` field.
- **Isolation:** Joins and lookups must strictly filter by company to prevent leakage.
- **Activation:** Master data (Parties, Items) must be "activated" per company before use.

## 6. Series & Identifiers
- **Structure:** `NamingSeries` (logic) + `Sequence` (physical counter).
- **Resolution:** Tokens (`*YYYY*`, `*MM*`, etc.) resolved using `posting_date`.
- **Audit:** All generated IDs recorded in `GeneratedIdentifierLog`.

## 7. Account Mapping & Tax Structure
- **Mapping:** Resolution hierarchy: `ItemAccount` -> `PartyAccount` -> `CompanyDefaultAccount`.
- **Tax Engine:** Tax templates associated with documents and lines. Linked to GL via `account_id`.
- **Pricing:** `PriceList` and `ItemPrice` support multi-currency suggested pricing.

## 8. Third-Party Accounting (AR/AP)
- **Model:** AR/AP are projections of GL, not separate subledgers.
- **Linkage:** Require `party_type` and `party_id` for receivable/payable accounts.
- **Allocation:** Support for partial payments and many-to-many matching via `PaymentReference`.

## 9. Advanced Domains
- **Bridge Accounts:** Use for matching received goods vs. invoiced amounts (Purchase Reconciliation).
- **Revaluation:** Periodic adjustments for exchange rate fluctuations.
- **Period Close:** Formal checks and closing runs per `AccountingPeriod`.
- **Collaboration:** Support for comments, assignments, and file attachments via generic linking.
