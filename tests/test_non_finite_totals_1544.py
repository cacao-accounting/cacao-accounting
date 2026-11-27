# SPDX-License-Identifier: Apache-2.0
"""#1544: totales no finitos deben rechazarse antes de quantize."""

from __future__ import annotations

from decimal import Decimal

import pytest


def test_sales_totals_reject_infinity(app):
    with app.app_context():
        from cacao_accounting.ventas.services import _set_sales_document_totals

        class Doc:
            company = "cacao"
            posting_date = None
            transaction_currency = "NIO"
            base_currency = "NIO"
            exchange_rate = Decimal("1")

        with pytest.raises(ValueError):
            _set_sales_document_totals(Doc(), Decimal("Infinity"))


def test_purchase_totals_reject_infinity(app):
    with app.app_context():
        from cacao_accounting.compras.services import _set_purchase_document_totals

        class Doc:
            company = "cacao"
            posting_date = None
            transaction_currency = "NIO"
            base_currency = "NIO"
            exchange_rate = Decimal("1")

        with pytest.raises(ValueError):
            _set_purchase_document_totals(Doc(), Decimal("Infinity"))
