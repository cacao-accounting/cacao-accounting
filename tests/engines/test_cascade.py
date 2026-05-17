# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests for non-cascading taxes."""

from decimal import Decimal
from datetime import date
from cacao_accounting.accounting_engine.common.context import TaxRuleContext, CalculationContext, ItemContext, AccountingReferences
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine

def test_non_cascading_tax():
    engine = FiscalEngine()

    # R1 does not participate in next base
    r1 = TaxRuleContext(
        rule_id="R1", name="DAI", concept="DAI",
        tax_type="tax", calculation_method="percentage",
        rate=Decimal("10"), order=1, participates_in_next_base=False
    )
    # R2 calculates on accumulated, including DAI
    r2 = TaxRuleContext(
        rule_id="R2", name="IVA", concept="IVA",
        tax_type="tax", calculation_method="percentage",
        rate=Decimal("15"), order=2, base_mode="accumulated",
        include_concepts=["goods", "DAI"]
    )

    ctx = CalculationContext(
        company_id="C1", document_type="invoice", event_type="confirm",
        transaction_direction="sales", transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1), party_type="customer", party_id="P1",
        currency="NIO", company_currency="NIO",
        items=[ItemContext(line_id="L1", item_id="I1", description="Item 1",
                           quantity=Decimal("1"), unit_price=Decimal("100"),
                           gross_amount=Decimal("100"), net_amount=Decimal("100"))],
        tax_rules=[r1, r2],
        references=AccountingReferences()
    )

    result = engine.calculate(ctx)
    dai = result.get_amount("DAI")
    iva = result.get_amount("IVA")

    assert dai == Decimal("10.0000")
    # IVA should be on 100 (goods) only, because DAI did not participate
    assert iva == Decimal("15.0000")

def test_cascading_tax():
    engine = FiscalEngine()

    # R1 participates in next base
    r1 = TaxRuleContext(
        rule_id="R1", name="DAI", concept="DAI",
        tax_type="tax", calculation_method="percentage",
        rate=Decimal("10"), order=1, participates_in_next_base=True
    )
    # R2 calculates on accumulated, including DAI
    r2 = TaxRuleContext(
        rule_id="R2", name="IVA", concept="IVA",
        tax_type="tax", calculation_method="percentage",
        rate=Decimal("15"), order=2, base_mode="accumulated",
        include_concepts=["goods", "DAI"]
    )

    ctx = CalculationContext(
        company_id="C1", document_type="invoice", event_type="confirm",
        transaction_direction="sales", transaction_date=date(2025, 6, 1),
        posting_date=date(2025, 6, 1), party_type="customer", party_id="P1",
        currency="NIO", company_currency="NIO",
        items=[ItemContext(line_id="L1", item_id="I1", description="Item 1",
                           quantity=Decimal("1"), unit_price=Decimal("100"),
                           gross_amount=Decimal("100"), net_amount=Decimal("100"))],
        tax_rules=[r1, r2],
        references=AccountingReferences()
    )

    result = engine.calculate(ctx)
    dai = result.get_amount("DAI")
    iva = result.get_amount("IVA")

    assert dai == Decimal("10.0000")
    # IVA should be on 110 (goods + DAI)
    assert iva == Decimal("16.5000")
