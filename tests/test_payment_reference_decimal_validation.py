# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1831: validación de importes decimales en referencias bancarias."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting.bancos.services import _validate_payment_reference_line


def _line(**overrides):
    """Construye una referencia de factura con importes explícitos."""
    return {
        "reference_type": "sales_invoice",
        "reference_id": "invoice-1",
        "allocated_amount": "100.00",
        "discount_amount": "0",
        "gain_loss_amount": "0",
        **overrides,
    }


def test_payment_reference_rejects_negative_discount_before_building_evidence():
    """Un descuento negativo no puede aumentar el efectivo consumido."""
    processed: set[tuple[str, str]] = set()

    with pytest.raises(ValueError, match="descuento.*negativo"):
        _validate_payment_reference_line(
            payment=SimpleNamespace(),
            line=_line(discount_amount="-50"),
            allow_order_references=False,
            processed_keys=processed,
        )

    assert processed == set()


def test_payment_reference_keeps_valid_signed_exchange_difference():
    """La diferencia de cambio conserva el signo permitido por el flujo actual."""
    result = _validate_payment_reference_line(
        payment=SimpleNamespace(),
        line=_line(discount_amount="10", gain_loss_amount="-5"),
        allow_order_references=False,
        processed_keys=set(),
    )

    assert result[-2:] == (Decimal("100.00"), Decimal("100.00"))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "abc"])
def test_payment_reference_rejects_invalid_allocated_amount(value):
    """Una asignación no finita o no numérica se vuelve error controlado."""
    with pytest.raises(ValueError):
        _validate_payment_reference_line(
            payment=SimpleNamespace(),
            line=_line(allocated_amount=value),
            allow_order_references=False,
            processed_keys=set(),
        )
