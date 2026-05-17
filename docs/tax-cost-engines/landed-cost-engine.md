# Landed Cost Engine

The Landed Cost Engine calculates how accessory costs (freight, insurance, duties) are distributed among inventory items.

## Inputs

- **Items**: List of products being received.
- **Capitalizable Lines**: Taxes or charges from the Fiscal Engine marked as `capitalizable_inventory_cost`.
- **External Charges**: Other manual charges (e.g., freight invoice) to be prorated.

## Proration Methods

The engine supports the following distribution strategies:

| Method | Basis for Share |
| :--- | :--- |
| `by_value` | (Item Net Amount) / (Total Net Amount) |
| `by_quantity` | (Item Quantity) / (Total Quantity) |
| `by_weight` | (Item Total Weight) / (Total Shipment Weight) |
| `by_volume` | (Item Total Volume) / (Total Shipment Volume) |
| `equal` | 1 / (Number of Item Lines) |
| `manual` | Uses specific amounts assigned manually per line. |

## Calculation Output

The engine produces a `LandedCostResult` which includes:
- **Allocation per Item**:
    - Original Base Amount.
    - List of allocated concepts and their amounts.
    - Final total inventoriable cost.
    - Final unit cost (Total / Quantity).
- **Audit Trail**: Explanation of the share calculation per item.

## Rounding Residuals

Financial integrity in prorations requires that the total allocated matches the source amount exactly. The engine ensures this by assigning any fractional residual to the last item in the allocation.
