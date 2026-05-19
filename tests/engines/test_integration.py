# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Integration tests for the Orchestrator, Resolver and Snapshots."""

import pytest
from decimal import Decimal
from datetime import date
from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.resolver import RuleResolver
from cacao_accounting.accounting_engine.orchestrator.event_orchestrator import BusinessEventOrchestrator


def test_rule_resolver_priority():
    """Test that rules are resolved with correct priority."""
    resolver = RuleResolver()

    company_rules = [
        TaxRuleContext(
            rule_id="C1",
            name="C VAT",
            concept="IVA",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("15"),
            level="company",
            order=1,
        )
    ]
    transaction_rules = [
        TaxRuleContext(
            rule_id="T1",
            name="T VAT",
            concept="IVA",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("10"),
            level="transaction",
            order=1,
        )
    ]
    party_rules = [
        TaxRuleContext(
            rule_id="P1",
            name="P VAT",
            concept="IVA",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("5"),
            level="party",
            order=1,
        )
    ]
    item_rules = [
        [
            TaxRuleContext(
                rule_id="I1",
                name="I VAT",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("0"),
                level="item",
                order=1,
            )
        ]
    ]

    # Item should win
    resolved = resolver.resolve(item_rules, party_rules, transaction_rules, company_rules)
    assert len(resolved) == 1
    assert resolved[0].rate == Decimal("0")
    assert resolved[0].level == "item"

    # Party should win if item rules empty
    resolved = resolver.resolve([], party_rules, transaction_rules, company_rules)
    assert resolved[0].rate == Decimal("5")
    assert resolved[0].level == "party"


def test_orchestrator_confirmed_event_creates_snapshot():
    """Test that confirmed events trigger snapshot creation."""
    orchestrator = BusinessEventOrchestrator()

    context = CalculationContext(
        company_id="COM-001",
        document_type="purchase_invoice",
        event_type="purchase_invoice_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="supplier",
        party_id="SUP-001",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L001",
                item_id="I1",
                description="Item",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("100"),
                net_amount=Decimal("100"),
            )
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="R1",
                name="V",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                order=1,
            )
        ],
    )

    results = orchestrator.handle_event(context)

    assert results["fiscal"] is not None
    assert results["snapshot"] is not None
    assert results["snapshot"]["metadata"]["event_type"] == "purchase_invoice_confirmed"
    # Verify serializable
    assert "context" in results["snapshot"]
    assert "results" in results["snapshot"]


def test_orchestrator_skips_landed_cost_on_sales():
    """Test that Landed Cost is not run for sales events by default."""
    orchestrator = BusinessEventOrchestrator()

    context = CalculationContext(
        company_id="COM-001",
        document_type="sales_invoice",
        event_type="sales_invoice_confirmed",
        transaction_direction="sales",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="customer",
        party_id="CUS-001",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L001",
                item_id="I1",
                description="Item",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                gross_amount=Decimal("100"),
                net_amount=Decimal("100"),
            )
        ],
        tax_rules=[],
    )

    results = orchestrator.handle_event(context)
    assert results["landed_cost"] is None


def test_orchestrator_reversal_from_snapshot():
    """Test reversal logic using a snapshot."""
    orchestrator = BusinessEventOrchestrator()

    # 1. Create a "confirmed" result (with snapshot)
    context = CalculationContext(
        company_id="COM-001",
        document_type="purchase_invoice",
        event_type="purchase_invoice_confirmed",
        transaction_direction="purchase",
        transaction_date=date(2026, 5, 16),
        posting_date=date(2026, 5, 16),
        party_type="supplier",
        party_id="SUP-001",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L1",
                item_id="I1",
                description="A",
                quantity=Decimal(1),
                unit_price=Decimal(100),
                gross_amount=Decimal(100),
                net_amount=Decimal(100),
            )
        ],
        tax_rules=[
            TaxRuleContext(
                rule_id="R1",
                name="V",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                order=1,
                accounting_treatment="separate_tax_account",
            )
        ],
    )

    original_results = orchestrator.handle_event(context)
    snapshot = original_results["snapshot"]

    # 2. Reverse it
    reversal = orchestrator.reverse_from_snapshot(snapshot)

    assert reversal["event_type"] == "reversal"
    assert reversal["fiscal"].get_amount("IVA") == Decimal("-15.00")
    assert reversal["fiscal"].document_tax_total == Decimal("-15.00")
