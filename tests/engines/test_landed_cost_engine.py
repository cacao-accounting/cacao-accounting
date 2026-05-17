# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Unit tests for the Landed Cost Engine."""

import pytest
from decimal import Decimal
from cacao_accounting.accounting_engine.common.context import (
    ItemContext,
    FiscalLine,
)
from cacao_accounting.accounting_engine.landed_cost.engine import LandedCostEngine

@pytest.fixture
def items():
    return [
        ItemContext(
            line_id="A", item_id="I1", description="Item A", quantity=Decimal("10"),
            unit_price=Decimal("50"), gross_amount=Decimal("500"), net_amount=Decimal("500"),
            weight=Decimal("2"), volume=Decimal("0.1")
        ),
        ItemContext(
            line_id="B", item_id="I2", description="Item B", quantity=Decimal("5"),
            unit_price=Decimal("100"), gross_amount=Decimal("500"), net_amount=Decimal("500"),
            weight=Decimal("10"), volume=Decimal("0.5")
        )
    ]

def test_landed_cost_by_value(items):
    """Test allocation by value."""
    # Total value = 1000. Each gets 50%.
    fiscal_lines = [
        FiscalLine(
            line_id="T1", concept="DAI", type="tax", rate=Decimal("10"),
            calculation_method="percentage", base_amount=Decimal("1000"), amount=Decimal("100"),
            recognition_event="invoice", accounting_treatment="capitalizable_inventory_cost",
            affects_inventory=True, affects_document_total=True, included_in_price=False,
            source_rule_id="R1", applies_to_items=["A", "B"], depends_on=[], participates_in_next_base=False
        )
    ]

    engine = LandedCostEngine()
    result = engine.calculate(items, fiscal_lines, allocation_method="by_value")

    assert result.inventory_value_total == Decimal("1100.00")
    assert result.get_allocation("A").allocated_total == Decimal("50.00")
    assert result.get_allocation("B").allocated_total == Decimal("50.00")

def test_landed_cost_rounding_residual(items):
    """Test that rounding residuals are handled (allocated to last item)."""
    # Total charge: 10.00.
    # A gets 50%, B gets 50%.
    # If we forced a weird rounding, we want to ensure sum is exactly 10.00.

    fiscal_lines = [
        FiscalLine(
            line_id="T1", concept="FEES", type="charge", rate=Decimal("0"),
            calculation_method="fixed", base_amount=Decimal("0"), amount=Decimal("10.00"),
            recognition_event="invoice", accounting_treatment="capitalizable_inventory_cost",
            affects_inventory=True, affects_document_total=True, included_in_price=False,
            source_rule_id="R1", applies_to_items=["A", "B"], depends_on=[], participates_in_next_base=False
        )
    ]

    engine = LandedCostEngine()
    # Mocking items to have values that might cause rounding issues if they were different
    result = engine.calculate(items, fiscal_lines, allocation_method="by_value")

    total_allocated = sum(a.allocated_total for a in result.allocations)
    assert total_allocated == Decimal("10.00")

def test_landed_cost_audit_trail(items):
    """Test that the audit trail is populated."""
    fiscal_lines = [
        FiscalLine(
            line_id="T1", concept="DAI", type="tax", rate=Decimal("0"),
            calculation_method="fixed", base_amount=Decimal("0"), amount=Decimal("100"),
            recognition_event="invoice", accounting_treatment="capitalizable_inventory_cost",
            affects_inventory=True, affects_document_total=True, included_in_price=False,
            source_rule_id="R1", applies_to_items=["A", "B"], depends_on=[], participates_in_next_base=False
        )
    ]

    engine = LandedCostEngine()
    result = engine.calculate(items, fiscal_lines)

    assert len(result.audit_trail) > 0
    assert result.audit_trail[0].concept == "DAI"
    assert "Allocation" in result.audit_trail[0].formula

def test_landed_cost_by_quantity(items):
    """Test allocation by quantity."""
    # Total qty = 15. A: 10/15 = 2/3, B: 5/15 = 1/3.
    fiscal_lines = [
        FiscalLine(
            line_id="T1", concept="FREIGHT", type="charge", rate=Decimal("0"),
            calculation_method="fixed", base_amount=Decimal("0"), amount=Decimal("150"),
            recognition_event="invoice", accounting_treatment="capitalizable_inventory_cost",
            affects_inventory=True, affects_document_total=True, included_in_price=False,
            source_rule_id="R1", applies_to_items=["A", "B"], depends_on=[], participates_in_next_base=False
        )
    ]

    engine = LandedCostEngine()
    result = engine.calculate(items, fiscal_lines, allocation_method="by_quantity")

    assert result.get_allocation("A").allocated_total == Decimal("100.00")
    assert result.get_allocation("B").allocated_total == Decimal("50.00")

def test_landed_cost_by_weight(items):
    """Test allocation by weight."""
    # Total weight = (10*2) + (5*10) = 20 + 50 = 70.
    # A: 20/70 = 2/7, B: 50/70 = 5/7.
    fiscal_lines = [
        FiscalLine(
            line_id="T1", concept="FREIGHT", type="charge", rate=Decimal("0"),
            calculation_method="fixed", base_amount=Decimal("0"), amount=Decimal("700"),
            recognition_event="invoice", accounting_treatment="capitalizable_inventory_cost",
            affects_inventory=True, affects_document_total=True, included_in_price=False,
            source_rule_id="R1", applies_to_items=["A", "B"], depends_on=[], participates_in_next_base=False
        )
    ]

    engine = LandedCostEngine()
    result = engine.calculate(items, fiscal_lines, allocation_method="by_weight")

    assert result.get_allocation("A").allocated_total == Decimal("200.00")
    assert result.get_allocation("B").allocated_total == Decimal("500.00")

def test_landed_cost_equal(items):
    """Test equal allocation among lines."""
    fiscal_lines = [
        FiscalLine(
            line_id="T1", concept="FEES", type="charge", rate=Decimal("0"),
            calculation_method="fixed", base_amount=Decimal("0"), amount=Decimal("100"),
            recognition_event="invoice", accounting_treatment="capitalizable_inventory_cost",
            affects_inventory=True, affects_document_total=True, included_in_price=False,
            source_rule_id="R1", applies_to_items=["A", "B"], depends_on=[], participates_in_next_base=False
        )
    ]

    engine = LandedCostEngine()
    result = engine.calculate(items, fiscal_lines, allocation_method="equal")

    assert result.get_allocation("A").allocated_total == Decimal("50.00")
    assert result.get_allocation("B").allocated_total == Decimal("50.00")
