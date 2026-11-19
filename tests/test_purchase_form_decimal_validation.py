# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2095: los formularios de compras rechazan decimales inválidos."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cacao_accounting.compras.services import _form_decimal


@pytest.mark.parametrize("value", ["abc", "NaN", "Infinity", "-Infinity"])
def test_decimal_invalido_se_convierte_en_validacion(app, value):
    """Sintaxis inválida o valores no finitos no escapan como InvalidOperation."""
    with app.test_request_context("/", method="POST", data={"qty_0": value}):
        with pytest.raises(ValueError, match="número"):
            _form_decimal("qty_0")


def test_decimal_valido_se_conserva(app):
    with app.test_request_context("/", method="POST", data={"qty_0": "12.5"}):
        assert _form_decimal("qty_0") == Decimal("12.5")
