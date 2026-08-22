"""Regression coverage for purchase-return matching boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from cacao_accounting.contabilidad.posting_service import _record_purchase_reconciliation


def test_purchase_return_is_excluded_from_positive_auto_matching() -> None:
    """Returns must not consume a receipt or order's positive pending quantity."""
    purchase_return = SimpleNamespace(id="RETURN-1", company="cacao", is_return=True)

    with patch("cacao_accounting.compras.purchase_reconciliation_service.get_matching_config") as matching_config:
        _record_purchase_reconciliation(purchase_return, matched_amount=10)

    matching_config.assert_not_called()
