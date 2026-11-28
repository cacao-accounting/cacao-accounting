# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Stock approval rejects non-finite rates that bypass numeric comparisons."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting.document_flow.validation import validate_submit_prerequisites


@pytest.mark.parametrize("rate", [Decimal("Infinity"), Decimal("-Infinity"), Decimal("NaN")])
def test_stock_submit_prerequisites_reject_non_finite_rates(rate):
    """Persisted or legacy non-finite rates cannot pass stock approval checks."""
    entry = SimpleNamespace(company="cacao", posting_date="2026-05-15")
    line = SimpleNamespace(qty=Decimal("1"), rate=rate)

    with pytest.raises(ValueError, match="tarifa.*finito"):
        validate_submit_prerequisites(
            entry,
            items=[line],
            require_party=False,
            require_warehouse=False,
        )
