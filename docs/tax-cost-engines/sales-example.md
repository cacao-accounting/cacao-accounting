# Sales & Tax Calculation Example

This example shows a standard domestic sale with VAT and a municipal tax.

## 1. Input Data

- **Items**:
  - Laptop: 1 unit @ 1,200.00
  - Mouse: 1 unit @ 25.00
  - **Subtotal**: 1,225.00
- **Configured Rules**:
  1. Municipal Tax: 1% (Base: Goods, Non-capitalizable)
  2. IVA: 15% (Base: Goods, Non-capitalizable)

## 2. Fiscal Engine Step

| Concept | Base | Rate | Amount |
| :--- | :--- | :--- | :--- |
| **Municipal Tax** | 1,225.00 | 1% | 12.25 |
| **IVA** | 1,225.00 | 15% | 183.75 |
