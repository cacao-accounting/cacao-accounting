# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos\u00e9 Moreno Reyes

"""#1892: validaci\u00f3n pre-submit exige bodega efectiva seg\u00fan prop\u00f3sito."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cacao_accounting.document_flow import validate_submit_prerequisites


def _entry(purpose: str):
    return SimpleNamespace(
        document_type="stock_entry",
        purpose=purpose,
        company="cacao",
        posting_date="2026-05-15",
        transaction_currency="NIO",
        base_currency="NIO",
        document_no="SE-TEST",
    )


def _item(*, source=None, target=None, qty=1, rate=10, is_stock_item=True):
    return SimpleNamespace(
        item_code="ITEM-1",
        qty=qty,
        rate=rate,
        amount=qty * rate,
        source_warehouse=source,
        target_warehouse=target,
        warehouse=None,
        is_stock_item=is_stock_item,
    )


@pytest.mark.parametrize("purpose", ["material_receipt", "adjustment_positive"])
def test_inflow_requiere_bodega_destino(purpose):
    with pytest.raises(ValueError, match="bodega de destino"):
        validate_submit_prerequisites(
            _entry(purpose),
            items=[_item(source="WH-A", target=None)],
            require_party=False,
            require_warehouse=True,
            require_rate_positive=False,
        )


@pytest.mark.parametrize("purpose", ["material_issue", "adjustment_negative"])
def test_outflow_requiere_bodega_origen(purpose):
    with pytest.raises(ValueError, match="bodega de origen"):
        validate_submit_prerequisites(
            _entry(purpose),
            items=[_item(source=None, target="WH-B")],
            require_party=False,
            require_warehouse=True,
            require_rate_positive=False,
        )


def test_transfer_requiere_ambas_bodegas():
    with pytest.raises(ValueError, match="bodega de destino"):
        validate_submit_prerequisites(
            _entry("material_transfer"),
            items=[_item(source="WH-A", target=None)],
            require_party=False,
            require_warehouse=True,
            require_rate_positive=True,
        )


def test_transfer_rechaza_la_misma_bodega():
    """#1892: una transferencia con origen igual al destino no pasa la guarda."""
    with pytest.raises(ValueError, match="distintas"):
        validate_submit_prerequisites(
            _entry("material_transfer"),
            items=[_item(source="WH-A", target="WH-A")],
            require_party=False,
            require_warehouse=True,
            require_rate_positive=True,
        )


def test_inflow_con_destino_pasa():
    validate_submit_prerequisites(
        _entry("material_receipt"),
        items=[_item(target="WH-B")],
        require_party=False,
        require_warehouse=True,
        require_rate_positive=True,
    )


def test_item_no_stock_no_requiere_bodega():
    validate_submit_prerequisites(
        _entry("material_receipt"),
        items=[_item(target=None, is_stock_item=False)],
        require_party=False,
        require_warehouse=True,
        require_rate_positive=True,
        warehouse_for_stock_items_only=True,
    )
