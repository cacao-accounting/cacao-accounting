# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1946: reponer caja chica ofrece un selector de cuentas, no texto libre."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from flask import render_template

from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    Entity,
    PettyCashAccount,
    PettyCashReplenishment,
    database,
)


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


def test_lista_http_solo_ofrece_cuentas_activas_de_la_compania(app, authenticated_client, entorno_contable):
    """El selector real se construye con la compañía del registro y cuentas activas."""
    sufijo = uuid4().hex[:6]
    with app.app_context():
        cuenta_contable = database.session.execute(
            database.select(Accounts).filter_by(entity="cacao", code="1101")
        ).scalar_one()
        banco = Bank(name=f"Banco {sufijo}", is_active=True)
        otra = Entity(
            code=f"o{sufijo}",
            name="Otra",
            company_name=f"Otra {sufijo}",
            tax_id=f"J-{sufijo}",
            currency="NIO",
            enabled=True,
        )
        database.session.add_all([banco, otra])
        database.session.flush()
        activa = BankAccount(
            bank_id=banco.id,
            company="cacao",
            account_name=f"Cuenta activa {sufijo}",
            account_no=f"A-{sufijo}",
            currency="NIO",
            is_active=True,
        )
        inactiva = BankAccount(
            bank_id=banco.id,
            company="cacao",
            account_name=f"Cuenta inactiva {sufijo}",
            account_no=f"I-{sufijo}",
            currency="NIO",
            is_active=False,
        )
        ajena = BankAccount(
            bank_id=banco.id,
            company=otra.code,
            account_name=f"Cuenta ajena {sufijo}",
            account_no=f"B-{sufijo}",
            currency="NIO",
            is_active=True,
        )
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta_contable.id,
            name=f"Fondo {sufijo}",
            currency="NIO",
            float_amount=Decimal("100"),
        )
        database.session.add_all([activa, inactiva, ajena, fondo])
        database.session.flush()
        reposicion = PettyCashReplenishment(
            petty_cash_id=fondo.id,
            request_date=date(2026, 5, 15),
            company="cacao",
            amount=Decimal("50"),
            status="aprobado",
        )
        database.session.add(reposicion)
        database.session.commit()
        ids = {
            "activa": activa.id,
            "inactiva": inactiva.id,
            "ajena": ajena.id,
            "fondo": fondo.id,
            "reposicion": reposicion.id,
            "banco": banco.id,
            "otra": otra.code,
        }

    try:
        response = authenticated_client("admin").get("/cash_management/petty-cash-replenishment/list")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert f'value="{ids["activa"]}"' in html
        assert f"Cuenta activa {sufijo}" in html
        assert f'value="{ids["inactiva"]}"' not in html
        assert f'value="{ids["ajena"]}"' not in html
    finally:
        with app.app_context():
            for model, value in (
                (PettyCashReplenishment, ids["reposicion"]),
                (PettyCashAccount, ids["fondo"]),
                (BankAccount, ids["activa"]),
                (BankAccount, ids["inactiva"]),
                (BankAccount, ids["ajena"]),
                (Bank, ids["banco"]),
            ):
                fila = database.session.get(model, value)
                if fila is not None:
                    database.session.delete(fila)
                    database.session.flush()
            otra = database.session.execute(database.select(Entity).filter_by(code=ids["otra"])).scalar_one_or_none()
            if otra is not None:
                database.session.delete(otra)
            database.session.commit()
