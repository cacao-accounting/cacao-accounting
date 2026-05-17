# Fiscal Engine

The Fiscal Engine is responsible for calculating all taxes, withholdings, and fiscal charges.

## Calculation Logic

The engine follows a step-by-step process:
1. **Sort Rules**: Rules are sorted by their `order` property.
2. **Determine Base**: Depending on `base_mode`, the engine uses either the goods total or an accumulated subtotal.
3. **Apply Method**: Calculates amount based on `percentage`, `fixed`, or `quantity`.
4. **Rounding**: Applies the configured rounding policy (HALF_UP, Bankers, etc.).
5. **Tax Decomposition**: For taxes included in the price, the engine uses algebraic decomposition to solve for the net amount when multiple taxes apply to the same level.
6. **Update Accumulators**: If the rule `participates_in_next_base`, its result is added to the subtotal for subsequent rules.

## Cascading Taxes

Cascading is handled by using `base_mode: "accumulated"` and defining `include_concepts`.

**Example configuration for cascaded IVA:**
- Concept: `IVA`
- Base Mode: `accumulated`
- Include: `["goods", "DAI", "ISC"]`

## Accounting Treatment

Each result line is tagged with a treatment that guides the accounting mapper:
- `capitalizable_inventory_cost`: Added to inventory value.
- `separate_tax_account`: Recorded in a dedicated GL account (e.g., VAT).
- `withholding_payable`: Recorded as a liability at payment.
- `withholding_receivable`: Recorded as an asset at collection.
