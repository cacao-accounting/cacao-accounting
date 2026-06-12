# Settlement Engine

The Settlement Engine handles the financial liquidation of documents, calculating actual cash movement and withholdings.

## Responsibilities

1. **Calculate Withholdings**: Determines taxes to be retained at the moment of payment or collection.
2. **Partial Payments**: Correctly calculates proportional withholdings when only a part of the document balance is being paid.
3. **Financial Differences**: Tracks exchange rate differences and small rounding variances.
4. **Balance Tracking**: Calculates the remaining open balance after the settlement.

## Proportional Withholding Logic

For partial payments, the engine uses the following formula:
`Proportion = (Payment Amount) / (Document Total)`
`Withholding = (Full Withholding for Document) * Proportion`

This ensures that withholdings are applied fairly across multiple payments for the same invoice.
