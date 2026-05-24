# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tax rule resolver logic."""

from __future__ import annotations

from typing import Optional

from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    TaxRuleContext,
)


class RuleResolver:
    """Resolves tax rules based on priority and merge strategies."""

    def resolve(
        self,
        item_rules: list[list[TaxRuleContext]],
        party_rules: list[TaxRuleContext],
        transaction_rules: list[TaxRuleContext],
        company_rules: list[TaxRuleContext],
        context: Optional[CalculationContext] = None,
    ) -> list[TaxRuleContext]:
        """Resolve tax rules."""
        resolved_rules: dict[str, TaxRuleContext] = {}
        excluded_concepts: set[str] = set()

        for rule in self._applicable_rules(item_rules, party_rules, transaction_rules, company_rules, context):
            self._apply_merge_strategy(rule, resolved_rules, excluded_concepts)

        final_rules = self._final_rules(resolved_rules, excluded_concepts)
        return sorted(final_rules, key=lambda x: x.order)

    def _applicable_rules(
        self,
        item_rules: list[list[TaxRuleContext]],
        party_rules: list[TaxRuleContext],
        transaction_rules: list[TaxRuleContext],
        company_rules: list[TaxRuleContext],
        context: Optional[CalculationContext],
    ) -> list[TaxRuleContext]:
        """Return matching rules ordered from generic to specific."""
        rules: list[TaxRuleContext] = []
        for group in reversed(self._rule_groups(item_rules, party_rules, transaction_rules, company_rules)):
            rules.extend(rule for rule in group if self._rule_matches_context(rule, context))
        return rules

    def _rule_groups(
        self,
        item_rules: list[list[TaxRuleContext]],
        party_rules: list[TaxRuleContext],
        transaction_rules: list[TaxRuleContext],
        company_rules: list[TaxRuleContext],
    ) -> list[list[TaxRuleContext]]:
        """Return tax rules grouped by increasing priority level."""
        return [
            [rule for sublist in item_rules for rule in sublist],
            party_rules,
            transaction_rules,
            company_rules,
        ]

    def _rule_matches_context(
        self,
        rule: TaxRuleContext,
        context: Optional[CalculationContext],
    ) -> bool:
        """Return whether a rule can be applied to the calculation context."""
        return context is None or self._matches_conditions(rule, context)

    def _apply_merge_strategy(
        self,
        rule: TaxRuleContext,
        resolved_rules: dict[str, TaxRuleContext],
        excluded_concepts: set[str],
    ) -> None:
        """Apply one rule to the accumulated result according to its merge strategy."""
        match rule.merge_strategy:
            case "replace_group":
                resolved_rules.clear()
                resolved_rules[rule.concept] = rule
            case "exclude":
                excluded_concepts.add(rule.concept)
                resolved_rules.pop(rule.concept, None)
            case "append":
                resolved_rules[f"{rule.concept}_{rule.rule_id}"] = rule
            case "override":
                resolved_rules[rule.concept] = rule
            case _:
                resolved_rules[rule.concept] = rule

    def _final_rules(
        self,
        resolved_rules: dict[str, TaxRuleContext],
        excluded_concepts: set[str],
    ) -> list[TaxRuleContext]:
        """Remove excluded non-item rules from the accumulated result."""
        return [rule for rule in resolved_rules.values() if rule.concept not in excluded_concepts or rule.level == "item"]

    def _matches_conditions(self, rule: TaxRuleContext, context: CalculationContext) -> bool:
        """Check if rule matches the calculation context."""
        # Date validity
        if rule.valid_from and context.transaction_date < rule.valid_from:
            return False
        if rule.valid_to and context.transaction_date > rule.valid_to:
            return False

        # Currency
        if rule.allowed_currencies and context.currency not in rule.allowed_currencies:
            return False

        # Party category (if provided in references)
        party_category = context.references.get("party_category")
        if rule.allowed_party_categories and party_category not in rule.allowed_party_categories:
            return False

        # Country
        if rule.country and context.references.get("country") != rule.country:
            return False

        return True
