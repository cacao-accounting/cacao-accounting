# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1972: los montos no finitos de formularios bancarios se rechazan."""

from __future__ import annotations

import pytest

from cacao_accounting.bancos.services import _form_decimal


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity", "nan", "inf"])
def test_form_decimal_rechaza_no_finitos(app, valor):
    """`NaN`/`Infinity` no llegan a comparaciones de saldo ni al GL."""
    with app.test_request_context("/", method="POST", data={"monto": valor}):
        with pytest.raises(ValueError):
            _form_decimal("monto")


def test_form_decimal_acepta_valor_finito(app):
    """Un importe normal se convierte sin pérdida."""
    with app.test_request_context("/", method="POST", data={"monto": "123.45"}):
        assert str(_form_decimal("monto")) == "123.45"
