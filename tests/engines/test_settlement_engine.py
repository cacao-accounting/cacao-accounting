# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Unit tests for the Settlement Engine."""

from decimal import Decimal
from dataclasses import dataclass
from typing import Optional

from cacao_accounting.accounting_engine.settlement.engine import SettlementEngine


@dataclass
class MockRule:
    concept: str
    rate: Decimal
    recognition_event: str
    accounting_treatment: str
    account_id: Optional[str] = None


def test_settlement_full_payment():
    """Test full payment of a document with one withholding."""
    rules = [MockRule("IR", Decimal("2"), "payment", "withholding_payable")]

    engine = SettlementEngine()
    # Doc Total: 1000, Open Balance: 1000, Payment: 1000
    result = engine.calculate(Decimal("1000"), Decimal("1000"), Decimal("1000"), rules)

    assert result.gross_settlement_amount == Decimal("1000")
    assert result.withholding_amount == Decimal("20.00")
    assert result.cash_amount == Decimal("980.00")
    assert result.remaining_balance == Decimal("0.00")


def test_settlement_partial_payment():
    """Test partial payment with proportional withholding."""
    rules = [MockRule("IR", Decimal("2"), "payment", "withholding_payable")]

    engine = SettlementEngine()
    # Doc Total: 1000, Open Balance: 1000, Payment: 400 (40%)
    result = engine.calculate(Decimal("1000"), Decimal("1000"), Decimal("400"), rules)

    assert result.gross_settlement_amount == Decimal("400")
    # 2% of 400 is 8.00
    assert result.withholding_amount == Decimal("8.00")
    assert result.cash_amount == Decimal("392.00")
    assert result.remaining_balance == Decimal("600.00")


def test_settlement_multiple_withholdings():
    """Test payment with multiple withholdings."""
    rules = [
        MockRule("IR", Decimal("2"), "payment", "withholding_payable"),
        MockRule("ALC", Decimal("1"), "payment", "withholding_payable"),
    ]

    engine = SettlementEngine()
    result = engine.calculate(Decimal("1000"), Decimal("1000"), Decimal("1000"), rules)

    assert result.withholding_amount == Decimal("30.00")  # 20 + 10
    assert result.cash_amount == Decimal("970.00")


def test_settlement_purchase_exchange_loss():
    """A supplier payment in foreign currency should compute realized exchange loss."""
    engine = SettlementEngine()

    result = engine.calculate(
        Decimal("100"),
        Decimal("3650"),
        Decimal("100"),
        [],
        transaction_direction="purchase",
        document_currency="USD",
        company_currency="NIO",
        document_exchange_rate=Decimal("36.5"),
        settlement_exchange_rate=Decimal("36.8"),
    )

    assert result.exchange_difference == Decimal("-30.00")
    assert result.remaining_balance == Decimal("0.00")


def test_settlement_collection_exchange_gain():
    """A customer collection in foreign currency should compute realized exchange gain."""
    engine = SettlementEngine()

    result = engine.calculate(
        Decimal("100"),
        Decimal("3650"),
        Decimal("100"),
        [],
        transaction_direction="sales",
        document_currency="USD",
        company_currency="NIO",
        document_exchange_rate=Decimal("36.5"),
        settlement_exchange_rate=Decimal("36.8"),
    )

    assert result.exchange_difference == Decimal("30.00")
    assert result.remaining_balance == Decimal("0.00")


def test_settlement_applies_early_payment_discount_against_cash_gap():
    """The engine should recognize an eligible discount when gross settlement exceeds cash plus withholdings."""
    engine = SettlementEngine()

    result = engine.calculate(
        Decimal("100"),
        Decimal("3650"),
        Decimal("100"),
        [],
        transaction_direction="purchase",
        document_currency="USD",
        company_currency="NIO",
        document_exchange_rate=Decimal("36.5"),
        settlement_exchange_rate=Decimal("36.5"),
        actual_cash_amount=Decimal("98"),
        eligible_discount_amount=Decimal("2"),
    )

    assert result.cash_amount == Decimal("98")
    assert result.payment_discount_amount == Decimal("2")
    assert any(line.type == "discount" and line.amount == Decimal("2") for line in result.settlement_lines)


def test_settlement_partial_payment_calculates_unrealized_exchange_difference():
    """A partial foreign-currency settlement should revalue the unpaid balance."""
    engine = SettlementEngine()

    result = engine.calculate(
        Decimal("100"),
        Decimal("3650"),
        Decimal("40"),
        [],
        transaction_direction="sales",
        document_currency="USD",
        company_currency="NIO",
        document_exchange_rate=Decimal("36.5"),
        settlement_exchange_rate=Decimal("36.8"),
    )

    assert result.exchange_difference == Decimal("12.00")
    assert result.remaining_balance == Decimal("2190.00")
    assert result.unrealized_exchange_difference == Decimal("18.00")


def test_settlement_discount_partial_gap_maintains_invariant():
    """When the eligible discount is smaller than the cash gap, cash_amount must adjust to keep the components balanced."""
    engine = SettlementEngine()
    rules = [MockRule("IR", Decimal("5"), "payment", "withholding_payable")]

    result = engine.calculate(
        document_total=Decimal("100"),
        open_balance=Decimal("100"),
        settlement_amount=Decimal("100"),
        withholding_rules=rules,
        actual_cash_amount=Decimal("90"),
        eligible_discount_amount=Decimal("3"),
    )

    assert result.cash_amount == Decimal("92")
    assert result.withholding_amount == Decimal("5")
    assert result.payment_discount_amount == Decimal("3")
    assert result.cash_amount + result.withholding_amount + result.payment_discount_amount == result.gross_settlement_amount
