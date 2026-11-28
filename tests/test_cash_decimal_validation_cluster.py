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


def test_alta_de_caja_chica_con_monto_no_numerico_no_produce_500(app, authenticated_client, entorno_contable):
    """#1984: `float_amount=abc` se convierte en validación controlada."""
    from cacao_accounting.database import Accounts, PettyCashAccount, database

    with app.app_context():
        cuenta = Accounts(
            entity="cacao",
            code="PC-1984",
            name="Caja chica",
            classification="asset",
            account_type="petty_cash",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(cuenta)
        database.session.commit()
        cuenta_id = cuenta.id

    respuesta = authenticated_client("admin").post(
        "/cash_management/petty-cash/new",
        data={"name": "Fondo 1984", "account_id": cuenta_id, "currency": "NIO", "float_amount": "abc"},
    )

    assert respuesta.status_code != 500
    with app.app_context():
        fondos = database.session.execute(database.select(PettyCashAccount).filter_by(name="Fondo 1984")).scalars().all()
        assert fondos == []
