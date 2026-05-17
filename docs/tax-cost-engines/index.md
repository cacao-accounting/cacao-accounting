# Tax and Cost Calculation Engines

Welcome to the documentation for the Cacao Accounting Tax, Landed Cost, and Settlement Engines.

This module provides a centralized, deterministic, and auditable architecture for handling all financial calculations associated with business transactions.

## Documentation Map

- **[Core Concepts](concepts.md)**: Introduction to the three-engine architecture.
- **[Fiscal Engine](fiscal-engine.md)**: Details on tax and withholding calculations.
- **[Landed Cost Engine](landed-cost-engine.md)**: Inventory valuation and cost proration.
- **[Settlement Engine](settlement-engine.md)**: Financial liquidations and payments.
- **[Rule Priority & Resolution](rule-priority.md)**: How the system decides which rules apply.
- **[Auditability & Snapshots](auditability.md)**: How we ensure every calculation is explainable.
- **[Testing Strategy](testing.md)**: How to verify the engines and new rules.

## Practical Examples

- [Tax Rule Resolution Examples](rule-examples.md)
- [Import & Purchase Lifecycle Example](import-purchase-example.md)
- [Sales & Tax Calculation Example](sales-example.md)
- [Payments & Withholdings Example](payment-withholding-example.md)

## Design Principles

1. **Deterministic**: Given the same input (context), the output is always the same.
2. **Pure Functions**: Engines do not access the database or modify state directly.
3. **Auditability**: Every step of the calculation is recorded in an audit trail.
4. **Explainability**: The system can explain exactly how it reached a result.
5. **Configurability**: No taxes are hardcoded; all behavior is driven by rules.
