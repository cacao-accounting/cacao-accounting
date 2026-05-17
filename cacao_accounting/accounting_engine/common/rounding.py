# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Rounding management for accounting engines."""

from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_CEILING, ROUND_FLOOR
from typing import Dict, Any, Optional


class RoundingManager:
    """Handles rounding policies and execution."""

    MODES = {
        "HALF_UP": ROUND_HALF_UP,
        "HALF_EVEN": ROUND_HALF_EVEN,
        "CEILING": ROUND_CEILING,
        "FLOOR": ROUND_FLOOR,
    }

    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        """Initialize with a rounding policy."""
        self.policy = policy or {}
        self.default_mode = self.MODES.get(self.policy.get("mode", "HALF_UP"), ROUND_HALF_UP)
        self.default_precision = self.policy.get("precision", 2)
        self.quantizer = Decimal("1." + "0" * self.default_precision) if self.default_precision > 0 else Decimal("1")

    def round(
        self, value: Decimal, precision: Optional[int] = None, mode: Optional[str] = None, context_key: Optional[str] = None
    ) -> Decimal:
        """Round a decimal value based on policy."""
        # Check for context-specific overrides (e.g. 'inventory', 'fiscal', 'NIO')
        context_policy: Dict[str, Any] = self.policy.get("overrides", {}).get(context_key, {}) if context_key else {}

        target_mode = self.MODES.get(str(mode or context_policy.get("mode")), self.default_mode)
        target_precision = precision if precision is not None else context_policy.get("precision", self.default_precision)

        quantizer = Decimal("1." + "0" * target_precision) if target_precision > 0 else Decimal("1")

        return value.quantize(quantizer, rounding=target_mode)

    def distribute_residual(self, total: Decimal, shares: list[Decimal]) -> list[Decimal]:
        """Distribute a total amount among shares, ensuring the sum matches exactly."""
        if not shares:
            return []

        rounded_shares = [self.round(s) for s in shares]
        current_sum = sum(rounded_shares)
        diff = total - current_sum

        if diff == 0:
            return rounded_shares

        # Adjust the largest share to absorb the rounding difference
        # This is a simple but effective strategy for accounting
        idx = shares.index(max(shares))
        rounded_shares[idx] += diff
        return rounded_shares
