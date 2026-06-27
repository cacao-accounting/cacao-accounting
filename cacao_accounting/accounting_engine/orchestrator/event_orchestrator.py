# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Business Event Orchestrator."""

from __future__ import annotations
from decimal import Decimal
from typing import Any, Dict
from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    FiscalResult,
    FiscalLine,
    LandedCostResult,
    CostAllocation,
    SettlementLine,
    SettlementResult,
    AuditStep,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.accounting_engine.landed_cost.engine import LandedCostEngine
from cacao_accounting.accounting_engine.settlement.engine import SettlementEngine
from cacao_accounting.accounting_engine.snapshots.serializer import SnapshotSerializer
from cacao_accounting.accounting_engine.orchestrator.mapper import AccountingMapper


class BusinessEventOrchestrator:
    """Orchestrates calculation engines based on business events."""

    def __init__(self):
        """Initialize orchestrator."""
        self.fiscal_engine = FiscalEngine()
        self.landed_cost_engine = LandedCostEngine()
        self.settlement_engine = SettlementEngine()
        self.snapshot_serializer = SnapshotSerializer()
        self.mapper = AccountingMapper()

    def handle_event(self, context: CalculationContext) -> Dict[str, Any]:
        """Handle business events."""
        results = {
            "event_type": context.event_type,
            "document_type": context.document_type,
            "fiscal": None,
            "landed_cost": None,
            "settlement": None,
            "snapshot": None,
        }

        fiscal_result = self.fiscal_engine.calculate(context)
        results["fiscal"] = fiscal_result

        if self._should_run_landed_cost(context):
            capitalizable_lines = [
                line_item
                for line_item in fiscal_result.tax_lines
                if line_item.accounting_treatment == "capitalizable_inventory_cost"
            ]
            results["landed_cost"] = self.landed_cost_engine.calculate(
                items=context.items,
                capitalizable_fiscal_lines=capitalizable_lines,
                allocation_method=context.accounting_policy.get("allocation_method", "by_value"),
                rounding_policy=context.rounding_policy,
            )

        if self._should_run_settlement(context):
            withholding_rules = [
                rule_item
                for rule_item in context.tax_rules
                if rule_item.tax_type == "withholding"
                and rule_item.recognition_event in (context.event_type, "payment", "collection")
            ]
            settlement_amount = context.settlement_amount or Decimal("0")
            settlement_exchange_rate = context.references.get("settlement_exchange_rate", context.exchange_rate)
            results["settlement"] = self.settlement_engine.calculate(
                document_total=sum((item_item.net_amount for item_item in context.items), Decimal("0"))
                + fiscal_result.document_tax_total,
                open_balance=context.references.get("open_balance", Decimal("0")),
                settlement_amount=settlement_amount,
                withholding_rules=withholding_rules,
                rounding_policy=context.rounding_policy,
                transaction_direction=context.transaction_direction,
                document_currency=context.currency,
                company_currency=context.company_currency,
                document_exchange_rate=context.exchange_rate,
                settlement_exchange_rate=settlement_exchange_rate,
                actual_cash_amount=context.references.get("actual_cash_amount"),
                eligible_discount_amount=context.references.get("eligible_discount_amount"),
            )

        # 4. Generate Pro-forma Journal Entry
        results["proforma"] = self.mapper.map_to_proforma(
            context=context,
            fiscal=results["fiscal"],
            landed=results["landed_cost"],
            settlement=results["settlement"],
        )

        if "confirmed" in context.event_type:
            results["snapshot"] = self.snapshot_serializer.serialize(context, results)
        return results

    def _should_run_landed_cost(self, context: CalculationContext) -> bool:
        return (
            context.event_type in ("purchase_receipt_confirmed", "purchase_invoice_confirmed", "import_landed_cost_confirmed")
            or context.document_type == "purchase_receipt"
        )

    def _should_run_settlement(self, context: CalculationContext) -> bool:
        if context.event_type in ("payment_confirmed", "collection_confirmed"):
            return True
        return context.settlement_amount is not None and context.settlement_amount > 0

    def reverse_from_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a reversal result based on a confirmed snapshot.

        Negate all amounts for taxes, landed costs, and settlements.
        """
        reversal_results = {
            "event_type": "reversal",
            "document_type": snapshot["metadata"]["document_type"],
            "fiscal": None,
            "landed_cost": None,
            "settlement": None,
            "original_snapshot_id": snapshot["metadata"].get("snapshot_id"),
        }

        # 1. Reverse Fiscal
        if "fiscal" in snapshot["results"] and snapshot["results"]["fiscal"]:
            fiscal_data = snapshot["results"]["fiscal"]
            rev_lines = []
            for line_data in fiscal_data["tax_lines"]:
                # Convert back to Decimal if it was serialized as string
                rev_lines.append(
                    FiscalLine(
                        line_id=line_data["line_id"],
                        concept=line_data["concept"],
                        type=line_data["type"],
                        rate=Decimal(line_data["rate"]),
                        calculation_method=line_data["calculation_method"],
                        base_amount=-Decimal(line_data["base_amount"]),
                        amount=-Decimal(line_data["amount"]),
                        recognition_event="reversal",
                        accounting_treatment=line_data["accounting_treatment"],
                        affects_inventory=line_data["affects_inventory"],
                        affects_document_total=line_data["affects_document_total"],
                        included_in_price=line_data["included_in_price"],
                        source_rule_id=line_data["source_rule_id"],
                        applies_to_items=line_data["applies_to_items"],
                        depends_on=line_data["depends_on"],
                        participates_in_next_base=line_data["participates_in_next_base"],
                        allocation_method=line_data.get("allocation_method"),
                    )
                )

            reversal_results["fiscal"] = FiscalResult(
                document_tax_total=-Decimal(fiscal_data["document_tax_total"]),
                capitalizable_tax_total=-Decimal(fiscal_data["capitalizable_tax_total"]),
                separate_tax_total=-Decimal(fiscal_data["separate_tax_total"]),
                withholding_total=-Decimal(fiscal_data["withholding_total"]),
                tax_lines=rev_lines,
                audit_trail=[
                    AuditStep(
                        0,
                        "REVERSAL",
                        "Snapshot Reversal",
                        Decimal(0),
                        Decimal(0),
                        Decimal(0),
                        "Calculated by reversing original snapshot.",
                    )
                ],
            )

        # 2. Reverse Landed Cost
        if "landed_cost" in snapshot["results"] and snapshot["results"]["landed_cost"]:
            lc_data = snapshot["results"]["landed_cost"]
            rev_allocations = []
            for alloc_data in lc_data["allocations"]:
                rev_allocations.append(
                    CostAllocation(
                        item_line_id=alloc_data["item_line_id"],
                        base_amount=-Decimal(alloc_data["base_amount"]),
                        allocated_costs=[
                            {"concept": cost["concept"], "amount": -Decimal(cost["amount"]), "source": cost["source"]}
                            for cost in alloc_data["allocated_costs"]
                        ],
                        final_inventory_cost=-Decimal(alloc_data["final_inventory_cost"]),
                        unit_inventory_cost=-Decimal(alloc_data["unit_inventory_cost"]),
                    )
                )

            reversal_results["landed_cost"] = LandedCostResult(
                base_goods_total=-Decimal(lc_data["base_goods_total"]),
                capitalizable_charges_total=-Decimal(lc_data["capitalizable_charges_total"]),
                inventory_value_total=-Decimal(lc_data["inventory_value_total"]),
                allocations=rev_allocations,
            )

        if "settlement" in snapshot["results"] and snapshot["results"]["settlement"]:
            settlement_data = snapshot["results"]["settlement"]
            rev_settlement_lines = [
                SettlementLine(
                    line_id=line_data["line_id"],
                    concept=line_data["concept"],
                    type=line_data["type"],
                    base_amount=-Decimal(line_data["base_amount"]),
                    rate=Decimal(line_data["rate"]),
                    amount=-Decimal(line_data["amount"]),
                    recognition_event=line_data.get("recognition_event", ""),
                    accounting_treatment=line_data.get("accounting_treatment", ""),
                    account_id=line_data.get("account_id"),
                )
                for line_data in settlement_data["settlement_lines"]
            ]
            reversal_results["settlement"] = SettlementResult(
                gross_settlement_amount=-Decimal(settlement_data["gross_settlement_amount"]),
                cash_amount=-Decimal(settlement_data["cash_amount"]),
                withholding_amount=-Decimal(settlement_data["withholding_amount"]),
                payment_discount_amount=-Decimal(settlement_data["payment_discount_amount"]),
                exchange_difference=-Decimal(settlement_data["exchange_difference"]),
                unrealized_exchange_difference=-Decimal(settlement_data["unrealized_exchange_difference"]),
                remaining_balance=-Decimal(settlement_data["remaining_balance"]),
                settlement_lines=rev_settlement_lines,
                audit_trail=[
                    AuditStep(
                        0,
                        "REVERSAL",
                        "Snapshot Reversal",
                        Decimal(0),
                        Decimal(0),
                        Decimal(0),
                        "Settlement reversal created by negating original values.",
                    )
                ],
            )

        return reversal_results
