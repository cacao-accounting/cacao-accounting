# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Unit tests for the Fiscal Engine."""

import pytest
from decimal import Decimal
from datetime import date
from cacao_accounting.accounting_engine.common.context import (
    CalculationContext,
    ItemContext,
    TaxRuleContext,
)
from cacao_accounting.accounting_engine.fiscal.engine import FiscalEngine


@pytest.fixture
def base_context():
    return CalculationContext(
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
                item_id="ITEM-001",
                description="Test Item",
                quantity=Decimal("1"),
                unit_price=Decimal("1000"),
                gross_amount=Decimal("1000"),
                net_amount=Decimal("1000"),
            )
        ],
        tax_rules=[],
    )


def test_fiscal_engine_simple_tax(base_context):
    """Test a single simple percentage tax."""
    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R1",
                    name="VAT 15%",
                    concept="IVA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("15"),
                    base_mode="goods",
                    order=1,
                )
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert result.get_amount("IVA") == Decimal("150.00")
    assert result.document_tax_total == Decimal("150.00")


def test_fiscal_engine_multiple_taxes_no_cascade(base_context):
    """Test multiple taxes calculated on the same goods base."""
    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R1",
                    name="Tax A 10%",
                    concept="TAXA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("10"),
                    base_mode="goods",
                    order=1,
                ),
                TaxRuleContext(
                    rule_id="R2",
                    name="Tax B 5%",
                    concept="TAXB",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("5"),
                    base_mode="goods",
                    order=2,
                ),
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert result.get_amount("TAXA") == Decimal("100.00")
    assert result.get_amount("TAXB") == Decimal("50.00")
    assert result.document_tax_total == Decimal("150.00")


def test_fiscal_engine_fixed_amount(base_context):
    """Test a fixed amount tax/charge."""
    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R1",
                    name="Stamp Duty",
                    concept="STAMP",
                    tax_type="tax",
                    calculation_method="fixed",
                    amount=Decimal("25.50"),
                    order=1,
                )
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert result.get_amount("STAMP") == Decimal("25.50")
    assert result.document_tax_total == Decimal("25.50")


def test_fiscal_engine_withholding(base_context):
    """Test a withholding (deductive, doesn't affect document total the same way as taxes)."""
    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R1",
                    name="IR Withholding 2%",
                    concept="IR",
                    tax_type="withholding",
                    calculation_method="percentage",
                    rate=Decimal("2"),
                    base_mode="goods",
                    accounting_treatment="withholding_payable",
                    order=1,
                )
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert result.get_amount("IR") == Decimal("20.00")
    assert result.withholding_total == Decimal("20.00")
    # Withholdings shouldn't increase document total in this engine's convention (they decrease payment)
    assert result.document_tax_total == Decimal("0.00")


def test_fiscal_engine_cascading_complex(base_context):
    """Test complex cascading scenario."""
    # Goods: 1000
    # Tax A: 10% on Goods = 100 (Subtotal: 1100)
    # Tax B: 5% on Goods + Tax A = 55 (Subtotal: 1155)
    # Tax C: 1% on Tax A + Tax B = (100 + 55) * 0.01 = 1.55

    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R1",
                    name="A",
                    concept="TAXA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("10"),
                    base_mode="goods",
                    order=1,
                    participates_in_next_base=True,
                ),
                TaxRuleContext(
                    rule_id="R2",
                    name="B",
                    concept="TAXB",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("5"),
                    base_mode="accumulated",
                    include_concepts=["goods", "TAXA"],
                    order=2,
                    participates_in_next_base=True,
                ),
                TaxRuleContext(
                    rule_id="R3",
                    name="C",
                    concept="TAXC",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("1"),
                    base_mode="accumulated",
                    include_concepts=["TAXA", "TAXB"],
                    order=3,
                ),
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert result.get_amount("TAXA") == Decimal("100.00")
    assert result.get_amount("TAXB") == Decimal("55.00")
    assert result.get_amount("TAXC") == Decimal("1.55")
    assert result.document_tax_total == Decimal("156.55")


def test_fiscal_engine_tax_included_in_price(base_context):
    """Test tax extraction when included in price."""
    # Goods: 1150 (VAT 15% included)
    # Tax amount = 1150 * (15 / 115) = 150
    # Net amount = 1000

    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "items": [
                ItemContext(
                    line_id="L1",
                    item_id="I1",
                    description="A",
                    quantity=Decimal(1),
                    unit_price=Decimal(1150),
                    gross_amount=Decimal(1150),
                    net_amount=Decimal(1150),
                )
            ],
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R1",
                    name="IVA",
                    concept="IVA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("15"),
                    base_mode="goods",
                    included_in_price=True,
                    order=1,
                )
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert result.get_amount("IVA") == Decimal("150.00")
    # Included taxes shouldn't increase the document total
    assert result.document_tax_total == Decimal("0.00")


def test_fiscal_engine_circular_dependency(base_context):
    """Test that circular dependencies are detected."""
    # A depends on B, B depends on A
    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R1",
                    name="A",
                    concept="TAXA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("10"),
                    base_mode="accumulated",
                    include_concepts=["TAXB"],
                    order=1,
                ),
                TaxRuleContext(
                    rule_id="R2",
                    name="B",
                    concept="TAXB",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("5"),
                    base_mode="accumulated",
                    include_concepts=["TAXA"],
                    order=2,
                ),
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert "Circular dependency detected" in result.errors[0]


def test_fiscal_engine_orders_rules_by_dependency_graph(base_context):
    """Dependency order should take precedence over the manual order field."""
    context = base_context.__class__(
        **{
            **base_context.__dict__,
            "tax_rules": [
                TaxRuleContext(
                    rule_id="R2",
                    name="IVA",
                    concept="IVA",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("15"),
                    base_mode="accumulated",
                    include_concepts=["goods", "DAI"],
                    order=1,
                ),
                TaxRuleContext(
                    rule_id="R1",
                    name="DAI",
                    concept="DAI",
                    tax_type="tax",
                    calculation_method="percentage",
                    rate=Decimal("5"),
                    base_mode="goods",
                    order=99,
                    participates_in_next_base=True,
                ),
            ],
        }
    )

    engine = FiscalEngine()
    result = engine.calculate(context)

    assert not result.errors
    assert [line.concept for line in result.tax_lines] == ["DAI", "IVA"]
    assert result.get_amount("IVA") == Decimal("157.50")
