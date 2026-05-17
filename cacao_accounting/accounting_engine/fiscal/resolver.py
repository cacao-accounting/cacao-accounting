# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tax rule resolver logic."""

from __future__ import annotations
from typing import List, Dict, Optional
from cacao_accounting.accounting_engine.common.context import (
    TaxRuleContext,
    CalculationContext,
)


class RuleResolver:
    """Resolves tax rules based on priority and merge strategies."""

    def resolve(
        self,
        item_rules: List[List[TaxRuleContext]],
        party_rules: List[TaxRuleContext],
        transaction_rules: List[TaxRuleContext],
        company_rules: List[TaxRuleContext],
        context: Optional[CalculationContext] = None,
    ) -> List[TaxRuleContext]:
        """Resolve tax rules."""
        groups = [
            ("item", [r for sublist in item_rules for r in sublist]),
            ("party", party_rules),
            ("transaction", transaction_rules),
            ("company", company_rules),
        ]
        resolved_rules: Dict[str, TaxRuleContext] = {}
        excluded_concepts: set[str] = set()

        for level, rules in reversed(groups):
            for rule in rules:
                if context and not self._matches_conditions(rule, context):
                    continue

                if rule.merge_strategy == "replace_group":
                    resolved_rules = {rule.concept: rule}
                    continue
                if rule.merge_strategy == "exclude":
                    excluded_concepts.add(rule.concept)
                    if rule.concept in resolved_rules:
                        del resolved_rules[rule.concept]
                    continue
                if rule.merge_strategy == "override":
                    resolved_rules[rule.concept] = rule
                    continue
                if rule.merge_strategy == "append":
                    key = f"{rule.concept}_{rule.rule_id}"
                    resolved_rules[key] = rule
                    continue
                resolved_rules[rule.concept] = rule

        final_rules = [r for k, r in resolved_rules.items() if r.concept not in excluded_concepts or r.level == "item"]
        return sorted(final_rules, key=lambda x: x.order)

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
