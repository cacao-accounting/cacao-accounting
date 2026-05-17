# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Accounting Mapper implementation."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    FiscalResult,
    JournalEntryLineProforma,
    JournalEntryProforma,
    LandedCostResult,
    SettlementResult,
)


class AccountingMapper:
    """Maps economic results from engines to pro-forma journal entries."""

    def map_to_proforma(
        self,
        context: CalculationContext,
        fiscal: Optional[FiscalResult] = None,
        landed: Optional[LandedCostResult] = None,
        settlement: Optional[SettlementResult] = None,
    ) -> JournalEntryProforma:
        """Create a pro-forma journal entry from engine results."""
        del landed
        if settlement and context.event_type in {"payment_confirmed", "collection_confirmed"}:
            lines = self._map_settlement_event(context, settlement)
        else:
            lines = self._map_document_event(context, fiscal, settlement)
        return self._finalize_proforma(context, lines)

    def _map_document_event(
        self,
        context: CalculationContext,
        fiscal: Optional[FiscalResult],
        settlement: Optional[SettlementResult],
    ) -> list[JournalEntryLineProforma]:
        """Map invoice-like events such as purchase or sales confirmations."""
        explicit_lines = self._map_explicit_account_lines(context)
        lines = list(explicit_lines)
        lines.extend(self._map_fiscal_lines(context, fiscal))
        if not explicit_lines:
            total_goods = sum((item.net_amount for item in context.items), Decimal("0"))
            goods_account = self._resolve_goods_account(context)
            if total_goods > 0 and goods_account:
                side = "debit" if context.transaction_direction == "purchase" else "credit"
                lines.append(
                    self._build_line(
                        context,
                        goods_account,
                        total_goods,
                        side=side,
                        description=f"Base Goods - {context.document_type}",
                        exchange_rate=self._document_exchange_rate(context),
                    )
                )
        if self._requires_party_balance(context):
            lines.extend(self._balance_against_party(context, lines))
        elif settlement and settlement.gross_settlement_amount > 0:
            lines.append(
                self._build_party_line(
                    context,
                    amount=settlement.gross_settlement_amount,
                    side="credit" if context.transaction_direction == "purchase" else "debit",
                    description=f"Party Balance - {context.document_type}",
                    exchange_rate=self._document_exchange_rate(context),
                )
            )
        return lines

    def _map_settlement_event(
        self,
        context: CalculationContext,
        settlement: SettlementResult,
    ) -> list[JournalEntryLineProforma]:
        """Map payment and collection events."""
        lines = [
            self._build_party_line(
                context,
                amount=settlement.gross_settlement_amount,
                side="debit" if context.transaction_direction == "purchase" else "credit",
                description=f"Settlement - {context.document_type}",
                exchange_rate=self._document_exchange_rate(context),
            )
        ]
        cash_account = self._resolve_cash_account(context)
        if cash_account and settlement.cash_amount > 0:
            side = "credit" if context.transaction_direction == "purchase" else "debit"
            lines.append(
                self._build_line(
                    context,
                    cash_account,
                    settlement.cash_amount,
                    side=side,
                    description=f"Cash/Bank - {context.document_type}",
                    exchange_rate=self._settlement_exchange_rate(context),
                    exchange_rate_source="settlement",
                )
            )
        for withholding_line in settlement.settlement_lines:
            account_id = self._resolve_tax_account(context, withholding_line.account_id)
            if not account_id or withholding_line.amount <= 0:
                continue
            side = "credit" if context.transaction_direction == "purchase" else "debit"
            lines.append(
                self._build_line(
                    context,
                    account_id,
                    withholding_line.amount,
                    side=side,
                    description=f"{withholding_line.concept} - {context.document_type}",
                    exchange_rate=self._settlement_exchange_rate(context),
                    exchange_rate_source="settlement",
                    party_id=context.party_id,
                )
            )
        exchange_difference = settlement.exchange_difference
        if exchange_difference != 0:
            lines.append(self._build_exchange_difference_line(context, exchange_difference))
        if settlement.payment_discount_amount > 0:
            lines.append(self._build_payment_discount_line(context, settlement.payment_discount_amount))
        if settlement.unrealized_exchange_difference != 0:
            lines.append(self._build_unrealized_exchange_difference_line(context, settlement.unrealized_exchange_difference))
            lines.append(self._build_unrealized_party_offset_line(context, settlement.unrealized_exchange_difference))
        return lines

    def _map_fiscal_lines(
        self,
        context: CalculationContext,
        fiscal: Optional[FiscalResult],
    ) -> list[JournalEntryLineProforma]:
        """Map fiscal lines for invoice-like events."""
        if not fiscal:
            return []
        lines: list[JournalEntryLineProforma] = []
        for fiscal_line in fiscal.tax_lines:
            if not fiscal_line.affects_document_total:
                continue
            account_id = self._resolve_tax_account(context, fiscal_line.account_id, concept=fiscal_line.concept)
            if not account_id:
                continue
            is_debit = (context.transaction_direction == "purchase" and fiscal_line.type != "withholding") or (
                context.transaction_direction == "sales" and fiscal_line.type == "withholding"
            )
            side = "debit" if is_debit else "credit"
            lines.append(
                self._build_line(
                    context,
                    account_id,
                    fiscal_line.amount,
                    side=side,
                    description=f"{fiscal_line.concept} - {context.document_type}",
                    party_id=context.party_id if fiscal_line.type == "withholding" else None,
                    exchange_rate=self._document_exchange_rate(context),
                )
            )
        return lines

    def _build_party_line(
        self,
        context: CalculationContext,
        *,
        amount: Decimal,
        side: str,
        description: str,
        exchange_rate: Decimal,
    ) -> JournalEntryLineProforma:
        """Build a pro-forma line against the counterparty account."""
        party_account = context.references.get("party_account")
        if not party_account:
            return self._build_line(
                context,
                "",
                Decimal("0"),
                side=side,
                description=description,
                exchange_rate=exchange_rate,
                party_id=context.party_id,
            )
        return self._build_line(
            context,
            party_account,
            amount,
            side=side,
            description=description,
            exchange_rate=exchange_rate,
            party_id=context.party_id,
        )

    def _build_exchange_difference_line(
        self,
        context: CalculationContext,
        exchange_difference: Decimal,
    ) -> JournalEntryLineProforma:
        """Build the realized exchange gain/loss line in company currency."""
        side = "credit" if exchange_difference > 0 else "debit"
        account_id = (
            context.references.get("exchange_gain_account_id")
            if exchange_difference > 0
            else context.references.get("exchange_loss_account_id")
        )
        return self._build_line(
            context,
            account_id or "",
            abs(exchange_difference),
            side=side,
            description=f"Exchange Difference - {context.document_type}",
            exchange_rate=self._settlement_exchange_rate(context),
            exchange_rate_source="settlement",
            transaction_amount=Decimal("0"),
            amount_is_company_currency=True,
        )

    def _build_unrealized_exchange_difference_line(
        self,
        context: CalculationContext,
        exchange_difference: Decimal,
    ) -> JournalEntryLineProforma:
        """Build the unrealized exchange revaluation line in company currency."""
        side = "credit" if exchange_difference > 0 else "debit"
        account_id = (
            context.references.get("unrealized_exchange_gain_account_id")
            if exchange_difference > 0
            else context.references.get("unrealized_exchange_loss_account_id")
        )
        return self._build_line(
            context,
            account_id or "",
            abs(exchange_difference),
            side=side,
            description=f"Unrealized Exchange Difference - {context.document_type}",
            exchange_rate=self._settlement_exchange_rate(context),
            exchange_rate_source="settlement",
            transaction_amount=Decimal("0"),
            amount_is_company_currency=True,
        )

    def _build_unrealized_party_offset_line(
        self,
        context: CalculationContext,
        exchange_difference: Decimal,
    ) -> JournalEntryLineProforma:
        """Build the control-account offset required for unrealized revaluation."""
        side = "debit" if exchange_difference > 0 else "credit"
        return self._build_line(
            context,
            context.references.get("party_account") or "",
            abs(exchange_difference),
            side=side,
            description=f"Unrealized Exchange Offset - {context.document_type}",
            exchange_rate=self._settlement_exchange_rate(context),
            exchange_rate_source="settlement",
            party_id=context.party_id,
            transaction_amount=Decimal("0"),
            amount_is_company_currency=True,
        )

    def _build_payment_discount_line(
        self,
        context: CalculationContext,
        payment_discount_amount: Decimal,
    ) -> JournalEntryLineProforma:
        """Build the payment discount line in company currency."""
        side = "credit" if context.transaction_direction == "purchase" else "debit"
        account_id = context.references.get("payment_discount_account_id")
        return self._build_line(
            context,
            account_id or "",
            payment_discount_amount,
            side=side,
            description=f"Payment Discount - {context.document_type}",
            exchange_rate=self._settlement_exchange_rate(context),
            exchange_rate_source="settlement",
        )

    def _build_line(
        self,
        context: CalculationContext,
        account_id: str,
        amount: Decimal,
        *,
        side: str,
        description: str,
        exchange_rate: Decimal,
        exchange_rate_source: str = "document",
        party_id: str | None = None,
        transaction_amount: Decimal | None = None,
        amount_is_company_currency: bool = False,
    ) -> JournalEntryLineProforma:
        """Create a multi-currency pro-forma line."""
        transaction_value = amount if transaction_amount is None else transaction_amount
        company_amount = amount if amount_is_company_currency else transaction_value * exchange_rate
        debit = company_amount if side == "debit" else Decimal("0")
        credit = company_amount if side == "credit" else Decimal("0")
        return JournalEntryLineProforma(
            account_id=account_id,
            debit=debit,
            credit=credit,
            transaction_currency=context.currency,
            company_currency=context.company_currency,
            amount_transaction_currency=transaction_value,
            amount_company_currency=company_amount,
            exchange_rate_used=exchange_rate,
            exchange_rate_source=exchange_rate_source,
            description=description,
            party_id=party_id,
        )

    def _finalize_proforma(
        self,
        context: CalculationContext,
        lines: list[JournalEntryLineProforma],
    ) -> JournalEntryProforma:
        """Ensure the pro-forma entry is balanced."""
        proforma = JournalEntryProforma(lines=lines, memo=f"Pro-forma for {context.document_type}")
        if proforma.is_balanced or not lines:
            return proforma
        debits = sum((line.debit for line in lines), Decimal("0"))
        credits = sum((line.credit for line in lines), Decimal("0"))
        diff = debits - credits
        rounding_account = context.references.get("default_rounding_account_id")
        if rounding_account:
            lines.append(
                self._build_line(
                    context,
                    rounding_account,
                    abs(diff),
                    side="credit" if diff > 0 else "debit",
                    description=f"Rounding Difference - {context.document_type}",
                    exchange_rate=self._document_exchange_rate(context),
                )
            )
            return JournalEntryProforma(lines=lines, memo=f"Pro-forma for {context.document_type}")
        return JournalEntryProforma(lines=lines, memo=f"Pro-forma for {context.document_type}")

    def _map_explicit_account_lines(self, context: CalculationContext) -> list[JournalEntryLineProforma]:
        """Map pre-resolved account lines provided by the transactional builders."""
        raw_lines = context.references.custom_references.get("account_lines", [])
        mapped: list[JournalEntryLineProforma] = []
        for raw_line in raw_lines:
            amount = Decimal(str(raw_line.get("amount", "0")))
            if amount <= 0:
                continue
            mapped.append(
                self._build_line(
                    context,
                    str(raw_line.get("account_id", "")),
                    amount,
                    side=str(raw_line.get("side", "debit")),
                    description=str(raw_line.get("description", context.document_type)),
                    exchange_rate=self._document_exchange_rate(context),
                    party_id=raw_line.get("party_id"),
                )
            )
        return mapped

    def _requires_party_balance(self, context: CalculationContext) -> bool:
        """Return whether the document event should be balanced against AR/AP."""
        return context.event_type in {
            "purchase_invoice_confirmed",
            "sales_invoice_confirmed",
            "purchase_credit_note_confirmed",
            "sales_credit_note_confirmed",
        }

    def _balance_against_party(
        self,
        context: CalculationContext,
        lines: list[JournalEntryLineProforma],
    ) -> list[JournalEntryLineProforma]:
        """Balance invoice-like events against the party control account."""
        debits = sum((line.debit for line in lines), Decimal("0"))
        credits = sum((line.credit for line in lines), Decimal("0"))
        if debits == credits:
            return []
        side = "credit" if debits > credits else "debit"
        amount = abs(debits - credits)
        return [
            self._build_party_line(
                context,
                amount=(
                    amount / self._document_exchange_rate(context)
                    if context.currency != context.company_currency and self._document_exchange_rate(context) != 0
                    else amount
                ),
                side=side,
                description=f"Party Balance - {context.document_type}",
                exchange_rate=self._document_exchange_rate(context),
            )
        ]

    def _resolve_goods_account(self, context: CalculationContext) -> Optional[str]:
        """Resolve the goods account with sensible fallbacks."""
        if context.references.goods_account:
            return context.references.goods_account
        key = "default_inventory_account_id" if context.transaction_direction == "purchase" else "default_income_account_id"
        return context.references.get(key)

    def _resolve_cash_account(self, context: CalculationContext) -> Optional[str]:
        """Resolve the cash/bank account."""
        return (
            context.references.cash_account
            or context.references.get("default_bank_account_id")
            or context.references.get("default_cash_account_id")
        )

    def _resolve_tax_account(
        self,
        context: CalculationContext,
        explicit_account_id: Optional[str],
        *,
        concept: str | None = None,
    ) -> Optional[str]:
        """Resolve a tax/withholding account using explicit or default mappings."""
        if explicit_account_id:
            return explicit_account_id
        if concept:
            mapped = context.references.get(f"default_{concept}_account")
            if mapped:
                return mapped
        default_key = (
            "default_purchase_tax_account_id"
            if context.transaction_direction == "purchase"
            else "default_sales_tax_account_id"
        )
        return context.references.get(default_key)

    def _document_exchange_rate(self, context: CalculationContext) -> Decimal:
        """Resolve the accounting exchange rate for document mapping."""
        if context.currency == context.company_currency:
            return Decimal("1")
        return context.exchange_rate or Decimal("1")

    def _settlement_exchange_rate(self, context: CalculationContext) -> Decimal:
        """Resolve the settlement exchange rate for cash events."""
        if context.currency == context.company_currency:
            return Decimal("1")
        return context.references.get("settlement_exchange_rate", context.exchange_rate) or Decimal("1")
