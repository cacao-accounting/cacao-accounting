# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests for multiple included taxes."""

from decimal import Decimal
from datetime import date
from cacao_accounting.accounting_engine.common.context import (
    TaxRuleContext,
    CalculationContext,
    ItemContext,
    AccountingReferences,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine


def test_multiple_included_taxes():
    engine = FiscalEngine()

    # R1: 10% included
    r1 = TaxRuleContext(
        rule_id="R1",
        name="TAX1",
        concept="T1",
        tax_type="tax",
        calculation_method="percentage",
        rate=Decimal("10"),
        order=1,
        included_in_price=True,
    )
    # R2: 5% included (same level)
    r2 = TaxRuleContext(
        rule_id="R2",
        name="TAX2",
        concept="T2",
        tax_type="tax",
        calculation_method="percentage",
        rate=Decimal("5"),
        order=1,
        included_in_price=True,
    )

    # Total = 115.00
    # sum_rates = 15%
    # Net = 115 / 1.15 = 100.00
    # T1 = 100 * 0.10 = 10.00
    # T2 = 100 * 0.05 = 5.00

    ctx = CalculationContext(
        company_id="C1",
        document_type="invoice",
        event_type="confirm",
        transaction_direction="sales",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="customer",
        party_id="P1",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L1",
                item_id="I1",
                description="Item 1",
                quantity=Decimal("1"),
                unit_price=Decimal("115"),
                gross_amount=Decimal("115"),
                net_amount=Decimal("115"),
            )
        ],
        tax_rules=[r1, r2],
        references=AccountingReferences(),
    )

    result = engine.calculate(ctx)
    t1 = result.get_amount("T1")
    t2 = result.get_amount("T2")

    assert t1 == Decimal("10.0000")
    assert t2 == Decimal("5.0000")


def test_included_taxes_share_base_when_sequences_differ():
    """Included taxes with distinct sequences are extracted from their common base."""
    engine = FiscalEngine()
    fixed = TaxRuleContext(
        rule_id="FIXED",
        name="Timbre",
        concept="Timbre",
        tax_type="charge",
        calculation_method="fixed",
        amount=Decimal("10"),
        order=1,
        included_in_price=True,
    )
    vat = TaxRuleContext(
        rule_id="VAT",
        name="IVA",
        concept="IVA",
        tax_type="tax",
        calculation_method="percentage",
        rate=Decimal("15"),
        order=2,
        included_in_price=True,
    )
    ctx = CalculationContext(
        company_id="C1",
        document_type="invoice",
        event_type="confirm",
        transaction_direction="sales",
        transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1),
        party_type="customer",
        party_id="P1",
        currency="NIO",
        company_currency="NIO",
        items=[
            ItemContext(
                line_id="L1",
                item_id="I1",
                description="Item 1",
                quantity=Decimal("1"),
                unit_price=Decimal("125"),
                gross_amount=Decimal("125"),
                net_amount=Decimal("125"),
            )
        ],
        tax_rules=[fixed, vat],
        references=AccountingReferences(),
    )

    result = engine.calculate(ctx)

    assert result.get_amount("Timbre") == Decimal("10.0000")
    assert result.get_amount("IVA") == Decimal("15.0000")
    assert result.net_goods_total == Decimal("100.0000")
