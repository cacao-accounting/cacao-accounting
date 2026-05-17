# Import & Purchase Lifecycle Example

This example demonstrates the full flow of an international import, involving both Fiscal and Landed Cost engines.

## 1. Input Data

- **Items**:
  - Item A: 10 units @ 100.00 = 1,000.00
- **Configured Rules**:
  1. DAI: 5% (Base: Goods, Capitalizable)
  2. ISC: 3% (Base: Accumulated [Goods, DAI], Capitalizable)
  3. IVA: 15% (Base: Accumulated [Goods, DAI, ISC], Separate Account)

## 2. Fiscal Engine Step

| Concept | Base | Rate | Amount | Treatment |
| :--- | :--- | :--- | :--- | :--- |
| **DAI** | 1,000.00 | 5% | 50.00 | Capitalizable |
| **ISC** | 1,050.00 | 3% | 31.50 | Capitalizable |
| **IVA** | 1,081.50 | 15% | 162.23 | Separate Account |

## 3. Landed Cost Engine Step

The engine receives the 81.50 of capitalizable taxes and distributes them to Item A.

- **Item A Allocation**:
  - Base: 1,000.00
  - Allocated: 81.50
  - Final Cost: 1,081.50
  - Unit Cost: 108.15
