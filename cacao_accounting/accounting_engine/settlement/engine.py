# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Settlement Engine implementation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from cacao_accounting.accounting_engine.common.context import (
    AuditStep,
    SettlementLine,
    SettlementResult,
)
from cacao_accounting.accounting_engine.common.rounding import RoundingManager


class SettlementEngine:
    """Deterministic financial settlement engine."""

    def calculate(
        self,
        document_total: Decimal,
        open_balance: Decimal,
        settlement_amount: Decimal,
        withholding_rules: List[Any],
        is_partial: bool = False,
        rounding_policy: Optional[Dict[str, Any]] = None,
        transaction_direction: Optional[str] = None,
        document_currency: Optional[str] = None,
        company_currency: Optional[str] = None,
        document_exchange_rate: Optional[Decimal] = None,
        settlement_exchange_rate: Optional[Decimal] = None,
        actual_cash_amount: Optional[Decimal] = None,
        eligible_discount_amount: Optional[Decimal] = None,
    ) -> SettlementResult:
        """Calculate payments, collections and withholdings."""
        settlement_lines: list[SettlementLine] = []
        audit_trail: list[AuditStep] = []
        warnings: list[str] = []
        errors: list[str] = []

        if settlement_amount <= 0:
            return SettlementResult(errors=["Settlement amount must be greater than zero."])

        step_counter = 1
        withholding_total = Decimal("0")
        exchange_difference = Decimal("0")
        unrealized_exchange_difference = Decimal("0")
        payment_discount_amount = Decimal("0")
        rounding_manager = RoundingManager(rounding_policy)
        proportion = (settlement_amount / document_total) if document_total > 0 else Decimal("1")

        for rule in withholding_rules:
            full_base = document_total
            rule_base = rounding_manager.round(full_base * proportion, context_key="fiscal")
            amount = rounding_manager.round(rule_base * rule.rate / Decimal("100"), context_key="fiscal")

            line = SettlementLine(
                line_id=f"SETTLE-{step_counter:03}",
                concept=rule.concept,
                type="withholding",
                base_amount=rule_base,
                rate=rule.rate,
                amount=amount,
                recognition_event=rule.recognition_event,
                accounting_treatment=rule.accounting_treatment,
                account_id=getattr(rule, "account_id", None),
            )
            settlement_lines.append(line)
            withholding_total += amount
            audit_trail.append(
                AuditStep(
                    step=step_counter,
                    concept=rule.concept,
                    formula=f"({full_base} * {proportion}) * {rule.rate}%",
                    base_amount=rule_base,
                    rate=rule.rate,
                    result=amount,
                    reason=f"Proportional withholding for {proportion*100}% of document.",
                )
            )
            step_counter += 1

        requested_cash_amount = actual_cash_amount if actual_cash_amount is not None else settlement_amount - withholding_total
        gap_after_withholdings = settlement_amount - requested_cash_amount - withholding_total
        if eligible_discount_amount and gap_after_withholdings > 0:
            payment_discount_amount = min(gap_after_withholdings, eligible_discount_amount)
            settlement_lines.append(
                SettlementLine(
                    line_id=f"SETTLE-{step_counter:03}",
                    concept="payment_discount",
                    type="discount",
                    base_amount=settlement_amount,
                    rate=Decimal("0"),
                    amount=payment_discount_amount,
                    recognition_event="settlement",
                    accounting_treatment="payment_discount",
                )
            )
            audit_trail.append(
                AuditStep(
                    step=step_counter,
                    concept="payment_discount",
                    formula=f"min({gap_after_withholdings}, {eligible_discount_amount})",
                    base_amount=settlement_amount,
                    rate=Decimal("0"),
                    result=payment_discount_amount,
                    reason="Early payment discount applied to settlement.",
                )
            )
            step_counter += 1
        cash_amount = settlement_amount - withholding_total - payment_discount_amount
        if self._uses_foreign_currency(document_currency, company_currency):
            exchange_difference, carried_balance_company = self._calculate_exchange_difference(
                open_balance=open_balance,
                settlement_amount=settlement_amount,
                proportion=proportion,
                transaction_direction=transaction_direction,
                rounding_manager=rounding_manager,
                document_exchange_rate=document_exchange_rate,
                settlement_exchange_rate=settlement_exchange_rate,
            )
            remaining_balance = open_balance - carried_balance_company
            unrealized_exchange_difference = self._calculate_unrealized_exchange_difference(
                open_balance=open_balance,
                settlement_amount=settlement_amount,
                document_total=document_total,
                remaining_balance=remaining_balance,
                transaction_direction=transaction_direction,
                rounding_manager=rounding_manager,
                settlement_exchange_rate=settlement_exchange_rate,
            )
        else:
            remaining_balance = open_balance - settlement_amount
        return SettlementResult(
            gross_settlement_amount=settlement_amount,
            cash_amount=cash_amount,
            withholding_amount=withholding_total,
            payment_discount_amount=payment_discount_amount,
            exchange_difference=exchange_difference,
            unrealized_exchange_difference=unrealized_exchange_difference,
            remaining_balance=remaining_balance,
            settlement_lines=settlement_lines,
            audit_trail=audit_trail,
            warnings=warnings,
            errors=errors,
        )

    def _uses_foreign_currency(self, document_currency: Optional[str], company_currency: Optional[str]) -> bool:
        """Indica si la liquidacion requiere calculo cambiario."""
        return bool(document_currency and company_currency and document_currency != company_currency)

    def _calculate_exchange_difference(
        self,
        *,
        open_balance: Decimal,
        settlement_amount: Decimal,
        proportion: Decimal,
        transaction_direction: Optional[str],
        rounding_manager: RoundingManager,
        document_exchange_rate: Optional[Decimal],
        settlement_exchange_rate: Optional[Decimal],
    ) -> tuple[Decimal, Decimal]:
        """Calcula diferencia cambiaria realizada en moneda compañía."""
        del document_exchange_rate
        if settlement_exchange_rate in (None, Decimal("0")):
            return Decimal("0"), rounding_manager.round(open_balance * proportion, context_key="accounting")
        if settlement_exchange_rate is None:
            return Decimal("0"), rounding_manager.round(open_balance * proportion, context_key="accounting")
        applied_rate: Decimal = settlement_exchange_rate
        carried_balance_company = rounding_manager.round(open_balance * proportion, context_key="accounting")
        settlement_company_amount = rounding_manager.round(
            settlement_amount * applied_rate,
            context_key="accounting",
        )
        if transaction_direction == "sales":
            return settlement_company_amount - carried_balance_company, carried_balance_company
        return carried_balance_company - settlement_company_amount, carried_balance_company

    def _calculate_unrealized_exchange_difference(
        self,
        *,
        open_balance: Decimal,
        settlement_amount: Decimal,
        document_total: Decimal,
        remaining_balance: Decimal,
        transaction_direction: Optional[str],
        rounding_manager: RoundingManager,
        settlement_exchange_rate: Optional[Decimal],
    ) -> Decimal:
        """Calculate revaluation for the unpaid foreign-currency balance after a partial settlement."""
        if settlement_exchange_rate in (None, Decimal("0")) or document_total <= 0:
            return Decimal("0")
        if settlement_exchange_rate is None:
            return Decimal("0")
        remaining_transaction_balance = document_total - settlement_amount
        if remaining_transaction_balance <= 0 or remaining_balance <= 0:
            return Decimal("0")
        revalued_remaining_balance = rounding_manager.round(
            remaining_transaction_balance * settlement_exchange_rate,
            context_key="accounting",
        )
        if transaction_direction == "sales":
            return revalued_remaining_balance - remaining_balance
        return remaining_balance - revalued_remaining_balance
