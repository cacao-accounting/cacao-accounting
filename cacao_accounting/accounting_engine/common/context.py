# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Common data structures for the accounting engines."""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, List, Optional, Dict
from datetime import date


@dataclass(frozen=True)
class ItemContext:
    """Context for an individual item line."""

    line_id: str
    item_id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    gross_amount: Decimal
    discount_amount: Decimal = Decimal("0")
    net_amount: Decimal = Decimal("0")
    item_type: str = "inventory"  # inventory, service
    uom: str = "unit"
    weight: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    tax_profile_id: Optional[str] = None
    cost_center_id: Optional[str] = None
    warehouse_id: Optional[str] = None


@dataclass(frozen=True)
class TaxRuleContext:
    """Context for a tax or charge rule."""

    rule_id: str
    name: str
    concept: str
    tax_type: str  # tax, charge, withholding, deduction
    calculation_method: str  # percentage, fixed, manual, quantity
    rate: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    base_mode: str = "goods"  # goods, accumulated
    include_concepts: List[str] = field(default_factory=list)
    exclude_concepts: List[str] = field(default_factory=list)
    participates_in_next_base: bool = False
    order: int = 0
    accounting_treatment: str = "separate_tax_account"
    recognition_event: str = "invoice"
    affects_inventory: bool = False
    affects_document_total: bool = True
    included_in_price: bool = False
    merge_strategy: str = "override"  # override, append, exclude, replace_group
    level: str = "transaction"  # item, party, transaction, company
    allocation_method: Optional[str] = None  # by_value, by_quantity, by_weight, by_volume, equal, manual
    # Dynamic conditions
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    allowed_currencies: List[str] = field(default_factory=list)
    allowed_party_categories: List[str] = field(default_factory=list)
    allowed_item_categories: List[str] = field(default_factory=list)
    country: Optional[str] = None
    account_id: Optional[str] = None


@dataclass(frozen=True)
class AccountingReferences:
    """Structured references for accounting mapping."""

    party_account: Optional[str] = None
    goods_account: Optional[str] = None
    cash_account: Optional[str] = None
    expense_account: Optional[str] = None
    income_account: Optional[str] = None
    open_balance: Decimal = Decimal("0")
    party_category: Optional[str] = None
    country: Optional[str] = None
    default_tax_accounts: Dict[str, str] = field(default_factory=dict)
    custom_references: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Compatibility helper for dictionary-like access."""
        if hasattr(self, key):
            return getattr(self, key)
        if key.startswith("default_") and key.endswith("_account"):
            concept = key.replace("default_", "").replace("_account", "")
            return self.default_tax_accounts.get(concept, default)
        return self.custom_references.get(key, default)


@dataclass(frozen=True)
class CalculationContext:
    """Global context for all engine calculations."""

    company_id: str
    document_type: str
    event_type: str
    transaction_direction: str  # purchase, sales
    transaction_date: date
    posting_date: date
    party_type: str  # supplier, customer
    party_id: str
    currency: str
    company_currency: str
    exchange_rate: Decimal = Decimal("1")
    fiscal_exchange_rate: Decimal = Decimal("1")
    price_includes_tax: bool = False
    items: List[ItemContext] = field(default_factory=list)
    tax_rules: List[TaxRuleContext] = field(default_factory=list)
    rounding_policy: Dict[str, Any] = field(default_factory=dict)
    accounting_policy: Dict[str, Any] = field(default_factory=dict)
    references: AccountingReferences = field(default_factory=AccountingReferences)
    settlement_amount: Optional[Decimal] = None


@dataclass(frozen=True)
class AuditStep:
    """An individual step in the calculation audit trail."""

    step: int
    concept: str
    formula: str
    base_amount: Decimal
    rate: Decimal
    result: Decimal
    reason: str


@dataclass(frozen=True)
class FiscalLine:
    """A calculated tax or charge line."""

    line_id: str
    concept: str
    type: str
    rate: Decimal
    calculation_method: str
    base_amount: Decimal
    amount: Decimal
    recognition_event: str
    accounting_treatment: str
    affects_inventory: bool
    affects_document_total: bool
    included_in_price: bool
    source_rule_id: str
    applies_to_items: List[str]
    depends_on: List[str]
    participates_in_next_base: bool
    allocation_method: Optional[str] = None
    account_id: Optional[str] = None


@dataclass(frozen=True)
class FiscalResult:
    """Result from the Fiscal Engine."""

    engine: str = "fiscal"
    document_tax_total: Decimal = Decimal("0")
    capitalizable_tax_total: Decimal = Decimal("0")
    separate_tax_total: Decimal = Decimal("0")
    withholding_total: Decimal = Decimal("0")
    tax_lines: List[FiscalLine] = field(default_factory=list)
    audit_trail: List[AuditStep] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def get_amount(self, concept: str) -> Decimal:
        """Get tax amount for a concept."""
        return sum((line.amount for line in self.tax_lines if line.concept == concept), Decimal("0"))


@dataclass(frozen=True)
class CostAllocation:
    """Allocation of costs to a specific item."""

    item_line_id: str
    base_amount: Decimal
    allocated_costs: List[Dict[str, Any]]
    final_inventory_cost: Decimal
    unit_inventory_cost: Decimal

    @property
    def allocated_total(self) -> Decimal:
        """Get total allocated cost."""
        return sum((_["amount"] for _ in self.allocated_costs), Decimal("0"))


@dataclass(frozen=True)
class LandedCostResult:
    """Result from the Landed Cost Engine."""

    engine: str = "landed_cost"
    base_goods_total: Decimal = Decimal("0")
    capitalizable_charges_total: Decimal = Decimal("0")
    inventory_value_total: Decimal = Decimal("0")
    allocations: List[CostAllocation] = field(default_factory=list)
    audit_trail: List[AuditStep] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def get_allocation(self, item_line_id: str) -> Optional[CostAllocation]:
        """Get allocation for an item."""
        for allocation in self.allocations:
            if allocation.item_line_id == item_line_id:
                return allocation
        return None


@dataclass(frozen=True)
class SettlementLine:
    """A calculated financial settlement line."""

    line_id: str
    concept: str
    type: str
    base_amount: Decimal
    rate: Decimal
    amount: Decimal
    recognition_event: str
    accounting_treatment: str
    account_id: Optional[str] = None


@dataclass(frozen=True)
class JournalEntryLineProforma:
    """Pro-forma journal entry line."""

    account_id: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    transaction_currency: Optional[str] = None
    company_currency: Optional[str] = None
    amount_transaction_currency: Decimal = Decimal("0")
    amount_company_currency: Decimal = Decimal("0")
    exchange_rate_used: Decimal = Decimal("1")
    exchange_rate_source: str = "document"
    description: str = ""
    cost_center_id: Optional[str] = None
    project_id: Optional[str] = None
    party_id: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None


@dataclass(frozen=True)
class JournalEntryProforma:
    """Pro-forma journal entry."""

    lines: List[JournalEntryLineProforma] = field(default_factory=list)
    memo: str = ""

    @property
    def is_balanced(self) -> bool:
        """Check if entry is balanced."""
        total_debits = sum((line.debit for line in self.lines), Decimal("0"))
        total_credits = sum((line.credit for line in self.lines), Decimal("0"))
        return total_debits == total_credits


@dataclass(frozen=True)
class SettlementResult:
    """Result from the Settlement Engine."""

    engine: str = "settlement"
    gross_settlement_amount: Decimal = Decimal("0")
    cash_amount: Decimal = Decimal("0")
    withholding_amount: Decimal = Decimal("0")
    payment_discount_amount: Decimal = Decimal("0")
    exchange_difference: Decimal = Decimal("0")
    unrealized_exchange_difference: Decimal = Decimal("0")
    remaining_balance: Decimal = Decimal("0")
    settlement_lines: List[SettlementLine] = field(default_factory=list)
    audit_trail: List[AuditStep] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
