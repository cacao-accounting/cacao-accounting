# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Business Event Orchestrator."""

from __future__ import annotations
from decimal import Decimal
from typing import Any, Dict
from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.accounting_engine.landed_cost.engine import LandedCostEngine
from cacao_accounting.accounting_engine.settlement.engine import SettlementEngine, SettlementOptions
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
            already_capitalized = set(context.references.get("already_capitalized_components", []))
            is_invoice = context.event_type in ("purchase_invoice_confirmed", "purchase_credit_note_confirmed")
            capitalizable_lines = [
                line_item
                for line_item in fiscal_result.tax_lines
                if line_item.accounting_treatment == "capitalizable_inventory_cost"
                and (
                    not is_invoice
                    or (
                        line_item.type == "tax"
                        and f"rule:{line_item.source_rule_id}" not in already_capitalized
                        and f"concept:{line_item.concept}" not in already_capitalized
                    )
                )
            ]
            results["landed_cost"] = self.landed_cost_engine.calculate(
                items=context.items,
                capitalizable_fiscal_lines=capitalizable_lines,
                allocation_method=context.accounting_policy.get("allocation_method", "by_value"),
                rounding_policy=context.rounding_policy,
            )

        if self._should_run_settlement(context):
            recognition_events = self._settlement_recognition_events(context.event_type, context.transaction_direction)
            withholding_rules = [
                rule_item
                for rule_item in context.tax_rules
                if rule_item.tax_type == "withholding" and rule_item.recognition_event in recognition_events
            ]
            settlement_amount = context.settlement_amount or Decimal("0")
            settlement_exchange_rate = context.references.get("settlement_exchange_rate", context.exchange_rate)
            results["settlement"] = self.settlement_engine.calculate(
                document_total=sum((item_item.net_amount for item_item in context.items), Decimal("0"))
                + fiscal_result.document_tax_total,
                open_balance=context.references.get("open_balance", Decimal("0")),
                settlement_amount=settlement_amount,
                withholding_rules=withholding_rules,
                options=SettlementOptions(
                    rounding_policy=context.rounding_policy,
                    transaction_direction=context.transaction_direction,
                    document_currency=context.currency,
                    company_currency=context.company_currency,
                    document_exchange_rate=context.exchange_rate,
                    settlement_exchange_rate=settlement_exchange_rate,
                    actual_cash_amount=context.references.get("actual_cash_amount"),
                    eligible_discount_amount=context.references.get("eligible_discount_amount"),
                    explicit_exchange_difference=context.references.get("explicit_exchange_difference", Decimal("0")),
                ),
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
        if context.event_type in ("payment_confirmed", "collection_confirmed", "refund_confirmed"):
            return True
        return context.settlement_amount is not None and context.settlement_amount > 0

    @staticmethod
    def _settlement_recognition_events(event_type: str, transaction_direction: str) -> set[str]:
        """Return the exact and legacy recognition events valid for a settlement."""
        aliases = {
            "payment_confirmed": {"payment_confirmed", "payment"},
            "collection_confirmed": {"collection_confirmed", "collection"},
            # Refunds inherit the legacy alias of their cash direction: a
            # customer refund is an outgoing payment, while a supplier refund
            # is an incoming collection.
            "refund_confirmed": {
                "refund_confirmed",
                "payment" if transaction_direction == "sales" else "collection",
            },
        }
        return aliases.get(event_type, {event_type})
