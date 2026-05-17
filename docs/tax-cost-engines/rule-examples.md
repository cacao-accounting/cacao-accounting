# Tax Rule Resolution Examples

This page provides examples of how the Rule Resolver handles different scenarios using priority and merge strategies.

## Scenario 1: Standard VAT Override

- **Company Rule**: VAT 15% (Level: Company)
- **Item Rule**: VAT 0% (Level: Item)
- **Result**: VAT 0%. (Reason: Item level higher priority than Company level).

## Scenario 2: Exempt Customer (Exclude Strategy)

- **Transaction Rule**: VAT 15% (Level: Transaction)
- **Party Rule**: VAT (Strategy: `exclude`) (Level: Party)
- **Result**: No VAT applied. (Reason: Party rule explicitly excludes the VAT concept).
