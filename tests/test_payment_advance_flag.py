# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1704: el flujo de anticipo persiste PaymentEntry.is_advance."""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.bancos.services import PaymentPayload, _create_payment_entry


def _crear(advance_mode: bool | None):
    payload: PaymentPayload = {"party_type": "supplier", "party_id": "P-1", "party_name": "Proveedor"}
    if advance_mode is not None:
        payload["advance_mode"] = advance_mode
    return _create_payment_entry(
        payload=payload,
        payment_type="pay",
        company="cacao",
        bank_account_id=None,
        target_bank_account_id=None,
        amount=Decimal("100.00"),
        payment_currency="NIO",
        reference_date=None,
        mode_of_payment="transfer",
        paid_from_account_id=None,
        paid_to_account_id=None,
    )


def test_anticipo_marca_el_pago_como_advance():
    """El indicador que habilita referencias a órdenes queda persistido."""
    pago = _crear(True)

    assert pago.is_advance is True
    assert pago.unallocated_amount == Decimal("100.00")


def test_pago_normal_no_se_marca_como_anticipo():
    """Sin advance_mode el modelo conserva su valor por defecto."""
    assert _crear(None).is_advance is False
    assert _crear(False).is_advance is False
