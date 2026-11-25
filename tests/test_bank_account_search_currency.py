# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William JosǸ Moreno Reyes

"""#2040: el Smart Select de cuentas bancarias expone la moneda en primer nivel."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import cacao_accounting
from cacao_accounting.database import Bank, BankAccount, database


def test_search_select_de_banco_expone_currency_sin_extra(app, authenticated_client, entorno_contable):
    """El contrato que consumen nota y transferencia no anida la moneda en extra."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    numero = f"API-{sufijo}"
    with app.app_context():
        banco = Bank(name=f"Banco API {sufijo}")
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta API",
            account_no=numero,
            currency="USD",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        cuenta_id, banco_id = cuenta.id, banco.id

    try:
        respuesta = authenticated_client("admin").get(
            "/api/search-select",
            query_string={"doctype": "bank_account", "q": numero},
        )

        assert respuesta.status_code == 200, respuesta.get_json()
        resultados = respuesta.get_json()["results"]
        opcion = next(item for item in resultados if item["value"] == cuenta_id)
        assert opcion["currency"] == "USD"
        assert "extra" not in opcion
    finally:
        with app.app_context():
            database.session.execute(database.delete(BankAccount).where(BankAccount.id == cuenta_id))
            database.session.execute(database.delete(Bank).where(Bank.id == banco_id))
            database.session.commit()


def test_plantillas_de_ctm_consumen_la_moneda_del_evento():
    """Nota y transferencia leen event.detail.currency, no el legacy extra."""
    plantillas = Path(cacao_accounting.__file__).parent / "bancos" / "templates" / "bancos"
    for nombre in ("nota_nueva.html", "transferencia_nueva.html"):
        contenido = (plantillas / nombre).read_text(encoding="utf-8")
        assert "event.detail.currency" in contenido, nombre
        assert "extra.currency" not in contenido, nombre
