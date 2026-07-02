# Core Concepts

The system separates calculation responsibilities into three specialized engines coordinated by a central Orchestrator.

## The Three Engines

### 1. Fiscal Engine
Responsible for calculating all tax-related obligations.
- **Inputs**: Items, Tax Rules.
- **Calculates**: VAT (IVA), ISC, DAI, municipal taxes, and withholdings.
- **Key Feature**: Supports cascading taxes and taxes included in prices.

### 2. Landed Cost Engine
Responsible for calculating the actual inventoriable cost of items.
- **Inputs**: Items, Capitalizable Fiscal Results, Accessory Charges.
- **Calculates**: Unit cost after proration of freight, insurance, and duties.
- **Proration Methods**: By value, quantity, weight, volume, or equal distribution.

### 3. Settlement Engine
Responsible for resolving the financial liquidation of a document.
- **Inputs**: Document Total, Open Balance, Payment Amount, Withholding Rules.
- **Calculates**: Cash to be paid/received, withholdings at payment, and remaining balance.
- **Key Feature**: Handles proportional withholdings for partial payments.

## Business Event Orchestrator

The Orchestrator ties the engines to the system's business flow. When a document is confirmed (e.g., `purchase_invoice_confirmed`), the Orchestrator:
1. Builds the `CalculationContext`.
2. Resolves applicable Rules.
3. Invokes the Engines in sequence.
4. Generates an auditable **Snapshot**.
5. Passes results to Accounting and Inventory mappers.
