# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2200: los importes visibles respetan la precisión de su moneda.

`Currency.decimals` es configurable; el formateador no debe fijar dos
decimales para todas las monedas ni ocultar fracciones configuradas.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from cacao_accounting import format_money_with_currency
from cacao_accounting.database import Currency, database


def test_money_uses_configured_currency_decimals(app):
    """Una moneda con cuatro decimales conserva la fracción visible."""
    suffix = uuid4().hex[:4].upper()
    code = f"D{suffix}"
    with app.app_context():
        database.session.add(Currency(code=code, name="Moneda precisa", decimals=4, active=True, default=False))
        database.session.commit()

        assert format_money_with_currency(Decimal("1.004"), code) == f"{code} 1.0040"
        assert format_money_with_currency(Decimal("1.004"), code).endswith("1.0040")


def test_money_without_currency_keeps_two_decimals(app):
    """El formato sin moneda conserva el contrato histórico."""
    with app.app_context():
        assert format_money_with_currency(Decimal("1.004"), "") == "1.00"
        assert format_money_with_currency(Decimal("1.004"), None) == "1.00"


def test_unknown_currency_falls_back_to_two_decimals(app):
    """Un código no configurado no rompe el renderizado."""
    with app.app_context():
        assert format_money_with_currency(Decimal("1.004"), "NO-EXISTE") == "NO-EXISTE 1.00"
