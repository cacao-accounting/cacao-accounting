# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1185: montos inválidos en caja chica devuelven validación, no 500."""

from __future__ import annotations

import pytest

from test_petty_cash_expense_required_fields import caja_gasto_centro_costo  # noqa: F401
from test_petty_cash_expense_required_fields import _iniciar, _postear_gasto
from cacao_accounting.database import ComprobanteContable, PettyCashExpense, database


@pytest.mark.parametrize("valor", ["abc", "NaN", "Infinity", "-Infinity"])
def test_gasto_con_monto_invalido_no_produce_500(caja_gasto_centro_costo, valor):  # noqa: F811
    """El parser convierte el error en validación y no persiste ni postea."""
    application, ids = caja_gasto_centro_costo
    client = application.test_client()
    _iniciar(client)

    response = _postear_gasto(client, ids, amount=valor)

    assert response.status_code == 200, response.get_data(as_text=True)
    cuerpo = response.get_data(as_text=True)
    assert "número" in cuerpo
    with application.app_context():
        assert database.session.execute(database.select(PettyCashExpense)).scalars().all() == []
        assert database.session.execute(database.select(ComprobanteContable)).scalars().all() == []


def test_gasto_con_monto_valido_sigue_funcionando(caja_gasto_centro_costo):  # noqa: F811
    """Control positivo: un monto finito conserva el flujo normal."""
    application, ids = caja_gasto_centro_costo
    client = application.test_client()
    _iniciar(client)

    response = _postear_gasto(client, ids, amount="25.00")

    assert response.status_code == 302, response.get_data(as_text=True)
