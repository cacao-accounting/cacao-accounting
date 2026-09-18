# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Landed Cost Engine implementation."""

from __future__ import annotations
from dataclasses import dataclass
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
from cacao_accounting.i18n import _

VALID_ALLOCATION_METHODS = frozenset({"by_value", "by_current_value", "by_quantity", "by_weight", "by_volume", "equal"})


@dataclass(frozen=True)
class _AllocationBases:
    """Distribution bases shared by every landed-cost rule."""

    value: Decimal
    qty: Decimal
    weight: Decimal
    volume: Decimal
    count: Decimal


@dataclass
class _AllocationState:
    """Running state while landed-cost rules are allocated sequentially."""

    item_costs: Dict[str, Decimal]
    item_allocations: Dict[str, List[Dict[str, Any]]]
    rounding_manager: RoundingManager
    audit_trail: List[AuditStep]


def validate_allocation_method(method: str) -> str:
    """Return a supported landed-cost allocation method or reject it.

    The allocation engine is a trust boundary for persisted documents and API
    callers, so unknown values must not silently turn into zero shares.
    """
    if method not in VALID_ALLOCATION_METHODS:
        raise ValueError(_("Método de prorrateo no soportado: %(method)s.") % {"method": method})
    return method


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
        rounding_manager = RoundingManager(rounding_policy or {"precision": 4})
        warnings: List[str] = []
        errors: List[str] = []

        base_goods_total = sum((item.net_amount for item in items), Decimal("0"))
        fiscal_costs = sum((line.amount for line in capitalizable_fiscal_lines), Decimal("0"))
        charge_costs = sum((_["amount"] for _ in (capitalizable_charges or [])), Decimal("0"))
        total_capitalizable = fiscal_costs + charge_costs

        if not items:
            return LandedCostResult(errors=["No items to allocate costs to."])

        validate_allocation_method(allocation_method)

        bases = _AllocationBases(
            value=base_goods_total,
            qty=sum((item.quantity for item in items), Decimal("0")),
            weight=sum((item.weight * item.quantity for item in items), Decimal("0")),
            volume=sum((item.volume * item.quantity for item in items), Decimal("0")),
            count=Decimal(len(items)),
        )
        state = _AllocationState(
            item_costs={item.line_id: item.net_amount for item in items},
            item_allocations={item.line_id: [] for item in items},
            rounding_manager=rounding_manager,
            audit_trail=[],
        )
        all_rules = self._build_allocation_rules(capitalizable_fiscal_lines, capitalizable_charges, allocation_method)
        for rule in all_rules:
            self._allocate_rule(rule, items, bases, state)

        allocations = self._finalize_allocations(items, state)
        inventory_value_total = sum((allocation.final_inventory_cost for allocation in allocations), Decimal("0"))
        return LandedCostResult(
            base_goods_total=base_goods_total,
            capitalizable_charges_total=total_capitalizable,
            inventory_value_total=inventory_value_total,
            allocations=allocations,
            audit_trail=state.audit_trail,
            warnings=warnings,
            errors=errors,
        )

    def _build_allocation_rules(
        self,
        fiscal_lines: List[FiscalLine],
        charges: Optional[List[Dict[str, Any]]],
        allocation_method: str,
    ) -> List[Dict[str, Any]]:
        """Combine fiscal lines and charges into sequential allocation rules."""
        all_rules: List[Dict[str, Any]] = []
        for line in fiscal_lines:
            all_rules.append(
                {
                    "type": "fiscal",
                    "line": line,
                    "amount": line.amount,
                    "concept": line.concept,
                    "source_rule_id": line.source_rule_id,
                    "tax_type": line.type,
                    "method": line.allocation_method or allocation_method,
                }
            )
        for charge in charges or []:
            all_rules.append(
                {
                    "type": "charge",
                    "line": charge,
                    "amount": charge["amount"],
                    "concept": charge["concept"],
                    "source_rule_id": charge.get("source_rule_id"),
                    "tax_type": charge.get("tax_type"),
                    "method": charge.get("allocation_method") or allocation_method,
                }
            )
        return all_rules

    def _allocate_rule(
        self,
        rule: Dict[str, Any],
        items: List[ItemContext],
        bases: _AllocationBases,
        state: _AllocationState,
    ) -> None:
        """Validate, record and distribute one allocation rule."""
        rule_amount: Decimal = rule["amount"]
        method = validate_allocation_method(rule["method"])
        total_current_value = sum(state.item_costs.values(), Decimal("0"))
        self._validate_allocation_basis(
            method=method,
            rule_amount=rule_amount,
            total_value=bases.value,
            total_current_value=total_current_value,
            total_qty=bases.qty,
            total_weight=bases.weight,
            total_volume=bases.volume,
            total_count=bases.count,
        )
        shares = {
            item.line_id: self._calculate_share(
                item,
                items,
                bases.value,
                bases.qty,
                bases.weight,
                bases.volume,
                bases.count,
                method,
                current_item_value=state.item_costs[item.line_id],
                total_current_value=total_current_value,
            )
            for item in items
        }
        state.audit_trail.append(
            AuditStep(
                step=len(state.audit_trail) + 1,
                concept=rule["concept"],
                formula=f"Allocation of {rule_amount} using {method}",
                base_amount=rule_amount,
                rate=Decimal("0"),
                result=rule_amount,
                reason=f"Distributed across {len(items)} items.",
            )
        )
        self._distribute_rule_amount(rule, shares, rule_amount, state)

    def _distribute_rule_amount(
        self,
        rule: Dict[str, Any],
        shares: Dict[str, Decimal],
        rule_amount: Decimal,
        state: _AllocationState,
    ) -> None:
        """Assign a rule amount to every item, absorbing the residual in the last one."""
        total_allocated_for_rule = Decimal("0")
        item_list = list(shares.keys())
        for index, item_id in enumerate(item_list):
            allocated_amount = state.rounding_manager.round(rule_amount * shares[item_id], context_key="inventory")
            if index == len(item_list) - 1:
                allocated_amount = rule_amount - total_allocated_for_rule
            total_allocated_for_rule += allocated_amount
            state.item_allocations[item_id].append(
                {
                    "concept": rule["concept"],
                    "amount": allocated_amount,
                    "source": rule["type"],
                    "source_rule_id": rule.get("source_rule_id"),
                    "tax_type": rule.get("tax_type"),
                }
            )
            state.item_costs[item_id] += allocated_amount

    def _finalize_allocations(
        self,
        items: List[ItemContext],
        state: _AllocationState,
    ) -> List[CostAllocation]:
        """Build the final cost allocation for every item."""
        allocations: List[CostAllocation] = []
        for item in items:
            final_cost = state.item_costs[item.line_id]
            unit_cost = (final_cost / item.quantity) if item.quantity > 0 else Decimal("0")
            allocations.append(
                CostAllocation(
                    item_line_id=item.line_id,
                    base_amount=item.net_amount,
                    allocated_costs=state.item_allocations[item.line_id],
                    final_inventory_cost=final_cost,
                    unit_inventory_cost=state.rounding_manager.round(unit_cost, context_key="inventory"),
                )
            )
        return allocations

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
                raise ValueError(_("Método de prorrateo no soportado: %(method)s.") % {"method": method})

    def _current_value_share(
        self,
        current_item_value: Optional[Decimal],
        total_current_value: Optional[Decimal],
    ) -> Decimal:
        """Calculate a share based on the running item value."""
        if current_item_value is None or total_current_value is None:
            return Decimal("0")
        return self._ratio(current_item_value, total_current_value)

    def _validate_allocation_basis(
        self,
        *,
        method: str,
        rule_amount: Decimal,
        total_value: Decimal,
        total_current_value: Decimal,
        total_qty: Decimal,
        total_weight: Decimal,
        total_volume: Decimal,
        total_count: Decimal,
    ) -> None:
        """Reject a non-zero allocation that lacks a positive distribution base.

        Without this guard all shares are zero and the rounding residual would
        assign the entire charge to the last line, which is not an accounting
        allocation method and makes inventory valuation depend on line order.
        """
        if rule_amount == 0:
            return
        bases = {
            "by_value": total_value,
            "by_current_value": total_current_value,
            "by_quantity": total_qty,
            "by_weight": total_weight,
            "by_volume": total_volume,
            "equal": total_count,
        }
        if bases[method] <= 0:
            raise ValueError(
                _("No existe una base positiva para prorratear el cargo mediante %(method)s.") % {"method": method}
            )

    def _ratio(self, numerator: Decimal, denominator: Decimal) -> Decimal:
        """Return a safe Decimal ratio."""
        return numerator / denominator if denominator > 0 else Decimal("0")
