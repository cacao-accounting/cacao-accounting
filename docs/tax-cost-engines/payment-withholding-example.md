# Payments & Withholdings Example

This example demonstrates how the Settlement Engine handles partial payments and proportional withholdings.

## 1. Scenario

- **Document Total**: 1,000.00
- **Open Balance**: 1,000.00
- **Withholding Rule**: Income Tax (IR) 2% at Payment.
- **Full Withholding if paid in full**: 20.00

## 2. Case B: Partial Payment

- **Payment Amount**: 400.00
- **Settlement Step**:
  - Proportion: 40% (400 / 1000)
  - Withholding Base: 400.00
  - Withholding Amount: 8.00 (20.00 * 0.40)
  - **Cash to Pay**: 392.00
  - **New Balance**: 600.00
