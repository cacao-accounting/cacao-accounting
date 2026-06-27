# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Landed Cost Engine implementation."""

from __future__ import annotations
from decimal import Decimal
from typing import List, Dict, Any, Optional
from cacao_accounting.accounting_engine.common.context import (
    LandedCostResult,
    CostAllocation,
    AuditStep,
    ItemContext,
    FiscalLine,
)
from cacao_accounting.accounting_engine.common.rounding import RoundingManager


class LandedCostEngine:
    """Deterministic landed cost calculation engine."""

    def calculate(
        self,
        items: List[ItemContext],
        capitalizable_fiscal_lines: List[FiscalLine],
        capitalizable_charges: Optional[List[Dict[str, Any]]] = None,
        allocation_method: str = "by_value",
        rounding_policy: Optional[Dict[str, Any]] = None,
    ) -> LandedCostResult:
        """Calculate inventory cost allocations."""
        allocations: List[CostAllocation] = []
        audit_trail: List[AuditStep] = []
        rounding_manager = RoundingManager(rounding_policy or {"precision": 4})
        warnings: List[str] = []
        errors: List[str] = []

        base_goods_total = sum((item.net_amount for item in items), Decimal("0"))
        fiscal_costs = sum((line.amount for line in capitalizable_fiscal_lines), Decimal("0"))
        charge_costs = sum((_["amount"] for _ in (capitalizable_charges or [])), Decimal("0"))
        total_capitalizable = fiscal_costs + charge_costs

        if not items:
            return LandedCostResult(errors=["No items to allocate costs to."])

        total_qty = sum((item.quantity for item in items), Decimal("0"))
        total_weight = sum((item.weight * item.quantity for item in items), Decimal("0"))
        total_volume = sum((item.volume * item.quantity for item in items), Decimal("0"))
        total_count = Decimal(len(items))

        # We need to process rules one by one and update item costs to support 'by_current_value'
        item_costs = {item.line_id: item.net_amount for item in items}
        item_allocations: Dict[str, List[Dict[str, Any]]] = {item.line_id: [] for item in items}

        # Combine fiscal lines and charges for sequential processing
        all_rules: List[Dict[str, Any]] = []
        for line in capitalizable_fiscal_lines:
            all_rules.append(
                {
                    "type": "fiscal",
                    "line": line,
                    "amount": line.amount,
                    "concept": line.concept,
                    "method": line.allocation_method or allocation_method,
                }
            )
        for charge in capitalizable_charges or []:
            all_rules.append(
                {
                    "type": "charge",
                    "line": charge,
                    "amount": charge["amount"],
                    "concept": charge["concept"],
                    "method": charge.get("allocation_method") or allocation_method,
                }
            )

        step_counter = 1
        for rule in all_rules:
            rule_amount: Decimal = rule["amount"]
            method: str = rule["method"]

            # Calculate shares for this specific rule
            shares = {}
            total_current_value = sum(item_costs.values(), Decimal("0"))

            for item in items:
                shares[item.line_id] = self._calculate_share(
                    item,
                    items,
                    base_goods_total,
                    total_qty,
                    total_weight,
                    total_volume,
                    total_count,
                    method,
                    current_item_value=item_costs[item.line_id],
                    total_current_value=total_current_value,
                )

            audit_trail.append(
                AuditStep(
                    step=step_counter,
                    concept=rule["concept"],
                    formula=f"Allocation of {rule_amount} using {method}",
                    base_amount=rule_amount,
                    rate=Decimal("0"),
                    result=rule_amount,
                    reason=f"Distributed across {len(items)} items.",
                )
            )
            step_counter += 1

            # Allocate and update costs
            total_allocated_for_rule = Decimal("0")
            item_list = list(shares.keys())

            for i, item_id in enumerate(item_list):
                share = shares[item_id]
                allocated_amount = rounding_manager.round(rule_amount * share, context_key="inventory")

                # Check for residual on last item
                if i == len(item_list) - 1:
                    allocated_amount = rule_amount - total_allocated_for_rule

                total_allocated_for_rule += allocated_amount

                item_allocations[item_id].append(
                    {"concept": rule["concept"], "amount": allocated_amount, "source": rule["type"]}
                )
                item_costs[item_id] += allocated_amount

        for item in items:
            final_cost = item_costs[item.line_id]
            allocated_costs = item_allocations[item.line_id]
            unit_cost = (final_cost / item.quantity) if item.quantity > 0 else Decimal("0")

            allocations.append(
                CostAllocation(
                    item_line_id=item.line_id,
                    base_amount=item.net_amount,
                    allocated_costs=allocated_costs,
                    final_inventory_cost=final_cost,
                    unit_inventory_cost=rounding_manager.round(unit_cost, context_key="inventory"),
                )
            )

        inventory_value_total = sum((a.final_inventory_cost for a in allocations), Decimal("0"))
        return LandedCostResult(
            base_goods_total=base_goods_total,
            capitalizable_charges_total=total_capitalizable,
            inventory_value_total=inventory_value_total,
            allocations=allocations,
            audit_trail=audit_trail,
            warnings=warnings,
            errors=errors,
        )

    def _calculate_share(
        self,
        item: ItemContext,
        all_items: List[ItemContext],
        total_value: Decimal,
        total_qty: Decimal,
        total_weight: Decimal,
        total_volume: Decimal,
        total_count: Decimal,
        method: str,
        current_item_value: Optional[Decimal] = None,
        total_current_value: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate an item's proportional landed-cost share."""
        match method:
            case "by_value":
                return self._ratio(item.net_amount, total_value)
            case "by_current_value":
                return self._current_value_share(current_item_value, total_current_value)
            case "by_quantity":
                return self._ratio(item.quantity, total_qty)
            case "by_weight":
                return self._ratio(item.weight * item.quantity, total_weight)
            case "by_volume":
                return self._ratio(item.volume * item.quantity, total_volume)
            case "equal":
                return self._ratio(Decimal("1"), total_count)
            case _:
                return Decimal("0")

    def _current_value_share(
        self,
        current_item_value: Optional[Decimal],
        total_current_value: Optional[Decimal],
    ) -> Decimal:
        """Calculate a share based on the running item value."""
        if current_item_value is None or total_current_value is None:
            return Decimal("0")
        return self._ratio(current_item_value, total_current_value)

    def _ratio(self, numerator: Decimal, denominator: Decimal) -> Decimal:
        """Return a safe Decimal ratio."""
        return numerator / denominator if denominator > 0 else Decimal("0")
