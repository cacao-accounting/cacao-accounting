# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1483: un importe de línea igual a cero es un valor válido."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.compras.purchase_reconciliation_service import _line_amount
from cacao_accounting.database import PurchaseReceiptItem


def _line(amount: Decimal | None, qty: Decimal = Decimal("2"), rate: Decimal = Decimal("10")) -> PurchaseReceiptItem:
    """Construye una línea de recepción con el importe persistido indicado."""
    return PurchaseReceiptItem(qty_in_base_uom=qty, amount=amount, rate=rate)


def test_importe_cero_se_conserva_en_lugar_de_recalcularlo(app):
    """Una línea bonificada conserva su importe cero."""
    del app
    assert _line_amount(_line(Decimal("0"))) == Decimal("0")


def test_importe_ausente_se_calcula_con_cantidad_y_tarifa(app):
    """Solo la ausencia del importe activa el cálculo derivado."""
    del app
    assert _line_amount(_line(None)) == Decimal("20")
