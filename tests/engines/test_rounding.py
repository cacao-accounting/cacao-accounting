# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tests for Rounding Manager."""

from decimal import Decimal
from cacao_accounting.accounting_engine.common.rounding import RoundingManager

def test_basic_rounding():
    rm = RoundingManager({"precision": 2, "mode": "HALF_UP"})
    assert rm.round(Decimal("10.555")) == Decimal("10.56")
    assert rm.round(Decimal("10.554")) == Decimal("10.55")

def test_bankers_rounding():
    rm = RoundingManager({"precision": 2, "mode": "HALF_EVEN"})
    # Rounds to nearest even number
    assert rm.round(Decimal("10.525")) == Decimal("10.52")
    assert rm.round(Decimal("10.535")) == Decimal("10.54")

def test_residual_distribution():
    rm = RoundingManager({"precision": 2})
    total = Decimal("100.00")
    # 100 / 3 = 33.3333...
    shares = [Decimal("33.3333"), Decimal("33.3333"), Decimal("33.3334")]
    distributed = rm.distribute_residual(total, shares)
    assert sum(distributed) == total
    assert distributed == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]

def test_rounding_overrides():
    policy = {
        "precision": 2,
        "overrides": {
            "inventory": {"precision": 4},
            "JPY": {"precision": 0}
        }
    }
    rm = RoundingManager(policy)

    assert rm.round(Decimal("10.12345")) == Decimal("10.12")
    assert rm.round(Decimal("10.12345"), context_key="inventory") == Decimal("10.1235")
    assert rm.round(Decimal("10.12345"), context_key="JPY") == Decimal("10")
