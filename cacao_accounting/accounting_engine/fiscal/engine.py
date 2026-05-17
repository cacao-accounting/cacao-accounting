# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Fiscal Engine implementation."""

from __future__ import annotations
from decimal import Decimal
from heapq import heappop, heappush
from typing import Dict, Optional

from cacao_accounting.accounting_engine.common.context import (
    AuditStep,
    CalculationContext,
    FiscalLine,
    FiscalResult,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.common.rounding import RoundingManager


class FiscalEngine:
    """Deterministic fiscal calculation engine."""

    def calculate(self, context: CalculationContext) -> FiscalResult:
        """Calculate taxes based on the provided context."""
        tax_lines: list[FiscalLine] = []
        audit_trail: list[AuditStep] = []
        rounding_manager = RoundingManager(context.rounding_policy)
        warnings: list[str] = []
        errors: list[str] = []

        sorted_rules = self._order_rules(context.tax_rules)
        if sorted_rules is None:
            return FiscalResult(errors=["Circular dependency detected in tax rules."])

        # Basic goods total
        goods_total = sum((item.net_amount for item in context.items), Decimal("0"))

        # Concept amounts for cascading
        concept_amounts: Dict[str, Decimal] = {"goods": goods_total}

        step_counter = 1

        for rule in sorted_rules:
            try:
                base_amount = self._calculate_base(rule, concept_amounts, goods_total)
                amount = self._calculate_amount(rule, base_amount, sorted_rules)

                # Use rounding manager
                amount = rounding_manager.round(amount, context_key="fiscal")

                # Update concept amounts for next rules
                if rule.participates_in_next_base:
                    if rule.concept not in concept_amounts:
                        concept_amounts[rule.concept] = Decimal("0")
                    concept_amounts[rule.concept] += amount

                line = FiscalLine(
                    line_id=f"TAX-{step_counter:03}",
                    concept=rule.concept,
                    type=rule.tax_type,
                    rate=rule.rate,
                    calculation_method=rule.calculation_method,
                    base_amount=base_amount,
                    amount=amount,
                    recognition_event=rule.recognition_event,
                    accounting_treatment=rule.accounting_treatment,
                    affects_inventory=rule.affects_inventory,
                    affects_document_total=rule.affects_document_total,
                    included_in_price=rule.included_in_price,
                    source_rule_id=rule.rule_id,
                    applies_to_items=[item.line_id for item in context.items],
                    depends_on=rule.include_concepts,
                    participates_in_next_base=rule.participates_in_next_base,
                    allocation_method=rule.allocation_method,
                    account_id=rule.account_id,
                )
                tax_lines.append(line)

                formula = self._get_formula(rule, base_amount)
                audit_trail.append(
                    AuditStep(
                        step=step_counter,
                        concept=rule.concept,
                        formula=formula,
                        base_amount=base_amount,
                        rate=rule.rate,
                        result=amount,
                        reason=f"{rule.concept} calculated using {rule.calculation_method} on {rule.base_mode} base.",
                    )
                )

                step_counter += 1
            except (ArithmeticError, ValueError) as exc:
                errors.append(f"Error calculating rule {rule.name}: {str(exc)}")

        # Consolidate totals
        doc_tax_total = sum(
            (
                line_item.amount
                for line_item in tax_lines
                if line_item.affects_document_total and not line_item.included_in_price and line_item.type != "withholding"
            ),
            Decimal("0"),
        )
        capitalizable_total = sum(
            (line_item.amount for line_item in tax_lines if line_item.accounting_treatment == "capitalizable_inventory_cost"),
            Decimal("0"),
        )
        separate_tax_total = sum(
            (line_item.amount for line_item in tax_lines if line_item.accounting_treatment == "separate_tax_account"),
            Decimal("0"),
        )
        withholding_total = sum((line_item.amount for line_item in tax_lines if line_item.type == "withholding"), Decimal("0"))

        return FiscalResult(
            document_tax_total=doc_tax_total,
            capitalizable_tax_total=capitalizable_total,
            separate_tax_total=separate_tax_total,
            withholding_total=withholding_total,
            tax_lines=tax_lines,
            audit_trail=audit_trail,
            warnings=warnings,
            errors=errors,
        )

    def _order_rules(self, rules: list[TaxRuleContext]) -> list[TaxRuleContext] | None:
        """Return rules ordered by dependency graph and configured order."""
        if not rules:
            return []
        concept_to_rule_ids = {
            rule.rule_id: {
                candidate.rule_id
                for candidate in rules
                if candidate.concept in set(rule.include_concepts + rule.exclude_concepts)
                and candidate.rule_id != rule.rule_id
            }
            for rule in rules
        }
        indegree = {rule.rule_id: len(concept_to_rule_ids[rule.rule_id]) for rule in rules}
        reverse_graph: dict[str, list[str]] = {rule.rule_id: [] for rule in rules}
        rule_map = {rule.rule_id: rule for rule in rules}
        for rule_id, dependencies in concept_to_rule_ids.items():
            for dependency in dependencies:
                reverse_graph.setdefault(dependency, []).append(rule_id)
        queue: list[tuple[int, str, str]] = []
        for rule in rules:
            if indegree[rule.rule_id] == 0:
                heappush(queue, (rule.order, rule.concept, rule.rule_id))
        ordered: list[TaxRuleContext] = []
        while queue:
            _, _, rule_id = heappop(queue)
            ordered.append(rule_map[rule_id])
            for dependent_id in reverse_graph.get(rule_id, []):
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    dependent = rule_map[dependent_id]
                    heappush(queue, (dependent.order, dependent.concept, dependent_id))
        if len(ordered) != len(rules):
            return None
        return ordered

    def _calculate_base(self, rule: TaxRuleContext, concept_amounts: Dict[str, Decimal], goods_total: Decimal) -> Decimal:
        if rule.base_mode == "goods":
            return goods_total
        if rule.base_mode == "accumulated":
            base = Decimal("0")
            if not rule.include_concepts:
                return goods_total
            for concept in rule.include_concepts:
                base += concept_amounts.get(concept, Decimal("0"))
            for concept in rule.exclude_concepts:
                base -= concept_amounts.get(concept, Decimal("0"))
            return base
        return goods_total

    def _calculate_amount(
        self, rule: TaxRuleContext, base_amount: Decimal, all_rules: Optional[list[TaxRuleContext]] = None
    ) -> Decimal:
        if rule.calculation_method == "percentage":
            if rule.included_in_price:
                # Tax Decomposition for multiple included taxes
                # Total = Net * (1 + sum(rates_included))
                # Tax_i = Net * rate_i
                # Tax_i = (Total / (1 + sum(rates_included))) * rate_i
                sum_included_rates = sum(
                    (r.rate for r in (all_rules or []) if r.included_in_price and r.order == rule.order), Decimal("0")
                )
                if not all_rules:  # Fallback for single rule
                    sum_included_rates = rule.rate

                net_amount = base_amount / (Decimal("1") + (sum_included_rates / Decimal("100")))
                return net_amount * rule.rate / Decimal("100")
            return base_amount * rule.rate / Decimal("100")
        if rule.calculation_method == "fixed":
            return rule.amount
        if rule.calculation_method == "manual":
            return rule.amount
        return Decimal("0")

    def _get_formula(self, rule: TaxRuleContext, base_amount: Decimal) -> str:
        if rule.calculation_method == "percentage":
            return f"{base_amount} * {rule.rate}%"
        if rule.calculation_method == "fixed":
            return f"{rule.amount} (fixed)"
        return "manual"
