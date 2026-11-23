# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1946: reponer caja chica ofrece un selector de cuentas, no texto libre."""

from __future__ import annotations

from types import SimpleNamespace

from flask import render_template


def test_reposicion_aprobada_muestra_selectores_de_cuenta(app):
    """El formulario de reposición lista las cuentas accesibles de la compañía."""
    registro = SimpleNamespace(
        id="r1",
        document_no="REP-1",
        petty_cash_id="pc1",
        amount="100.00",
        transaction_currency="NIO",
        status="aprobado",
        company="cacao",
    )
    with app.test_request_context("/"):
        html = render_template(
            "bancos/caja_chica_reposicion_lista.html",
            registros=[registro],
            fondos={"pc1": ("Caja Principal", "cacao")},
            bank_accounts={"cacao": [("acc-1", "Banco Uno — 0001")]},
        )

    assert 'name="bank_account_id"' in html
    assert 'type="text"' not in html.split('name="bank_account_id"')[0].rsplit("<form", 1)[-1]
    assert 'value="acc-1"' in html
    assert "Banco Uno" in html
