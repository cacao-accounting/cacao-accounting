# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Comprehensive audit tests for the Fiscal and Tax Calculation Engine."""

from decimal import Decimal
from datetime import date
import pytest

from cacao_accounting.accounting_engine.common.context import (
    AccountingReferences,
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine
from cacao_accounting.accounting_engine.fiscal.resolver import RuleResolver
from cacao_accounting.accounting_engine.orchestrator.mapper import AccountingMapper


@pytest.fixture
def audit_context():
    """Returns a baseline CalculationContext for audit testing."""
    return CalculationContext(
        company_id="cacao",
        document_type="sales_invoice",
        event_type="sales_invoice_confirmed",
        transaction_direction="sales",
        transaction_date=date(2026, 8, 12),
        posting_date=date(2026, 8, 12),
        party_type="customer",
        party_id="CUST-001",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L-01",
                item_id="ITEM-01",
                description="Audited Good",
                quantity=Decimal("2"),
                unit_price=Decimal("500"),  # Total base = 1000.00
                gross_amount=Decimal("1000"),
                net_amount=Decimal("1000"),
            )
        ],
        tax_rules=[],
    )


def test_audit_multi_tax_inclusive_decomposition(audit_context):
    """Verify correct mathematically rigorous tax decomposition for compound inclusive taxes."""
    # Base Price = 1150 (inclusive of 10% TAX1 and 5% TAX2 at same level/order)
    # Total rate = 15%
    # Net = 1150 / 1.15 = 1000.00
    # TAX1 = 1000 * 0.10 = 100.00
    # TAX2 = 1000 * 0.05 = 50.00
    context = audit_context.__class__(
        **{
            **audit_context.__dict__,
            "items": [
                ItemContext(
                    line_id="L-01",
                    item_id="ITEM-01",
                    description="Included Compound",
                    quantity=Decimal("1"),
                    unit_price=Decimal("1150"),
                    gross_amount=Decimal("1150"),
                    net_amount=Decimal("1150"),
                )
            ],
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R-01",
                    name="TAX1",
                    concept="T1",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("10"),
                    order=1,
                    included_in_price=True,
                ),
                TaxRuleContext(
                    rule_id="R-02",
                    name="TAX2",
                    concept="T2",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("5"),
                    order=1,
                    included_in_price=True,
                ),
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert not result.errors
    assert result.get_amount("T1") == Decimal("100.00")
    assert result.get_amount("T2") == Decimal("50.00")
    assert all(line.base_amount == Decimal("1000.00") for line in result.tax_lines)
    assert result.net_goods_total == Decimal("1000.00")
    # Included taxes must not increase document total
    assert result.document_tax_total == Decimal("0.00")

    context = context.__class__(
        **{
            **context.__dict__,
            "references": AccountingReferences(
                goods_account="1401",
                party_account="2101",
                default_tax_accounts={"T1": "2102", "T2": "2103"},
            ),
        }
    )
    proforma = AccountingMapper().map_to_proforma(context, fiscal=result)
    assert proforma.is_balanced
    assert sum(line.debit for line in proforma.lines) == Decimal("1150.00")
    assert sum(line.credit for line in proforma.lines) == Decimal("1150.00")
    goods_lines = [line for line in proforma.lines if line.account_id == "1401"]
    assert len(goods_lines) == 1
    assert goods_lines[0].credit == Decimal("1000.00")


def test_audit_cascading_with_rounding_precision(audit_context):
    """Verify step-by-step rounding manager handles precision in cascading rules."""
    # Goods: 1000.00
    # Rule 1: 15.1234% on Goods = 151.234 => 151.23
    # Rule 2 (Accumulated): 5.5678% on Goods + T1
    # Base 2: 1000.00 + 151.23 = 1151.23
    # T2 (Raw): 1151.23 * 0.055678 = 64.0981... => rounded to 64.10
    context = audit_context.__class__(
        **{
            **audit_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R-01",
                    name="VAT High Precision",
                    concept="T1",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("15.1234"),
                    base_mode="goods",
                    order=1,
                    participates_in_next_base=True,
                ),
                TaxRuleContext(
                    rule_id="R-02",
                    name="Surcharge",
                    concept="T2",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("5.5678"),
                    base_mode="accumulated",
                    include_concepts=["goods", "T1"],
                    order=2,
                ),
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert not result.errors
    assert result.get_amount("T1") == Decimal("151.23")
    assert result.get_amount("T2") == Decimal("64.10")
    assert result.document_tax_total == Decimal("215.33")


def test_audit_zero_and_negative_base_amount(audit_context):
    """Ensure tax calculation behaves gracefully on extreme values (zero and negative bases)."""
    # Test zero base
    context_zero = audit_context.__class__(
        **{
            **audit_context.__dict__,
            "items": [
                ItemContext(
                    line_id="L-01",
                    item_id="ITEM-01",
                    description="Zero Value Good",
                    quantity=Decimal("0"),
                    unit_price=Decimal("0"),
                    gross_amount=Decimal("0"),
                    net_amount=Decimal("0"),
                )
            ],
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R-01",
                    name="IVA",
                    concept="IVA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("15"),
                    order=1,
                )
            ],
        }
    )

    engine = FiscalEngine()
    result_zero = engine.calculate(context_zero)
    assert not result_zero.errors
    assert result_zero.get_amount("IVA") == Decimal("0.00")
    assert result_zero.document_tax_total == Decimal("0.00")

    # Test negative base (returns / debit notes)
    context_neg = audit_context.__class__(
        **{
            **audit_context.__dict__,
            "items": [
                ItemContext(
                    line_id="L-01",
                    item_id="ITEM-01",
                    description="Returned Good",
                    quantity=Decimal("1"),
                    unit_price=Decimal("-100"),
                    gross_amount=Decimal("-100"),
                    net_amount=Decimal("-100"),
                )
            ],
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R-01",
                    name="IVA",
                    concept="IVA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("15"),
                    order=1,
                )
            ],
        }
    )

    result_neg = engine.calculate(context_neg)
    assert not result_neg.errors
    # FiscalEngine preserves negative signs on return lines
    assert result_neg.get_amount("IVA") == Decimal("-15.00")
    assert result_neg.document_tax_total == Decimal("-15.00")


def test_audit_rule_resolver_priority_and_overrides():
    """Verify resolver hierarchy where specific rules successfully override generic rules."""
    resolver = RuleResolver()

    # Rule A: Company-wide (concept "TAX", merge strategy "override", generic)
    company_rule = TaxRuleContext(
        rule_id="RULE-COMPANY",
        name="Company VAT",
        concept="TAX",
        tax_type="tax",
        calculation_method="percentage",
        rate=Decimal("15"),
        merge_strategy="override",
        order=1,
    )

    # Rule B: Item-specific (concept "TAX", override, highly specific)
    item_rule = TaxRuleContext(
        rule_id="RULE-ITEM",
        name="Item VAT Exempt",
        concept="TAX",
        tax_type="tax",
        calculation_method="percentage",
        rate=Decimal("0"),
        merge_strategy="override",
        order=1,
    )

    # Context is None, so rules always match.
    # Reversed list order: [company_rule] processed first, [item_rule] processed later
    # and overrides it.
    resolved = resolver.resolve(
        item_rules=[[item_rule]],
        party_rules=[],
        transaction_rules=[],
        company_rules=[company_rule],
    )

    assert len(resolved) == 1
    assert resolved[0].rule_id == "RULE-ITEM"
    assert resolved[0].rate == Decimal("0")
