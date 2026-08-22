# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Unit tests for purchase-reconciliation allocation helpers."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting.compras import purchase_reconciliation_service as service


@pytest.mark.parametrize("order_mode", [False, True])
def test_available_line_slices_distributes_invoice_across_source_lines(monkeypatch, order_mode):
    """An invoice group consumes each compatible line instead of only the first."""
    lines = [SimpleNamespace(id="first", qty=Decimal("5")), SimpleNamespace(id="second", qty=Decimal("5"))]
    monkeypatch.setattr(service, "_line_qty", lambda line: line.qty)
    monkeypatch.setattr(service, "_matched_qty_for_receipt_item", lambda _line_id: Decimal("0"))
    monkeypatch.setattr(service, "_matched_qty_for_order_item", lambda _line_id: Decimal("0"))

    slices = service._available_line_slices(lines, Decimal("8"), order_mode=order_mode)

    assert [(line.id, qty) for line, qty in slices] == [("first", Decimal("5")), ("second", Decimal("3"))]
