# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 José Moreno Reyes

"""#1884: una conciliación de caja chica rechazada conserva los datos enviados."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, PettyCashAccount, PettyCashReconciliation, database

FECHA = date(2026, 5, 15)
URL_NUEVA = "/cash_management/petty-cash-reconciliation/new"
URL_EDITAR = "/cash_management/petty-cash-reconciliation/{id}/edit"


@pytest.fixture
def conciliacion_borrador(app, entorno_contable):
    """Crea un fondo y una conciliación en borrador para editar."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        account = Accounts(
            entity="cacao",
            code=f"PC{sufijo}",
            name="Caja chica",
            classification="asset",
            account_type="cash",
        )
        database.session.add(account)
        database.session.flush()
        fund = PettyCashAccount(
            company="cacao",
            account_id=account.id,
            name=f"Fondo {sufijo}",
            currency="NIO",
            float_amount=Decimal("100"),
        )
        database.session.add(fund)
        database.session.flush()
        reconciliation = PettyCashReconciliation(
            company="cacao",
            petty_cash_id=fund.id,
            reconciliation_date=FECHA,
            counted_cash=Decimal("10"),
            status="borrador",
        )
        database.session.add(reconciliation)
        database.session.commit()
        ids = {"fund": fund.id, "reconciliation": reconciliation.id, "account": account.id}
    yield ids
    with app.app_context():
        for model, value in (
            (PettyCashReconciliation, ids["reconciliation"]),
            (PettyCashAccount, ids["fund"]),
            (Accounts, ids["account"]),
        ):
            row = database.session.get(model, value)
            if row is not None:
                database.session.delete(row)
                database.session.flush()
        database.session.commit()


def test_edicion_rechazada_conserva_conteo_y_explicacion(app, authenticated_client, conciliacion_borrador):
    """El negativo rechazado vuelve al formulario, no al valor persistido."""
    client = authenticated_client("admin")

    response = client.post(
        URL_EDITAR.format(id=conciliacion_borrador["reconciliation"]),
        data={
            "reconciliation_date": "2026-05-20",
            "counted_cash": "-5",
            "explanation": "Conteo rechazado",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="-5"' in body
    assert 'value="2026-05-20"' in body
    assert "Conteo rechazado" in body
    with app.app_context():
        persistida = database.session.get(PettyCashReconciliation, conciliacion_borrador["reconciliation"])
        assert persistida.counted_cash == Decimal("10")
        assert persistida.reconciliation_date == FECHA


def test_alta_rechazada_conserva_compania_fondo_y_explicacion(app, authenticated_client, conciliacion_borrador):
    """Un alta inválida mantiene la selección enviada sin persistir la fila."""
    client = authenticated_client("admin")

    response = client.post(
        URL_NUEVA,
        data={
            "company": "cacao",
            "petty_cash_id": conciliacion_borrador["fund"],
            "reconciliation_date": "2026-05-20",
            "counted_cash": "-5",
            "explanation": "Alta rechazada",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="cacao"' in body
    assert f'value="{conciliacion_borrador["fund"]}" selected' in body
    assert 'value="2026-05-20"' in body
    assert "Alta rechazada" in body
    with app.app_context():
        total = database.session.execute(
            database.select(database.func.count()).select_from(PettyCashReconciliation)
        ).scalar_one()
        assert total == 1
