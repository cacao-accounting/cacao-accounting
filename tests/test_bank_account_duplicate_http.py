# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1980: una cuenta bancaria duplicada no produce 500."""

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from cacao_accounting.database import (
    Bank,
    BankAccount,
    Currency,
    Entity,
    Modules,
    database,
)


@pytest.fixture(name="cuenta_bancaria")
def crear_cuenta_bancaria(app, request):
    """Banco y cuenta GL de la compañía cacao para el alta por ruta."""
    request.getfixturevalue("entorno_contable")
    sufijo = uuid4().hex[:5]
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one_or_none() is None:
            database.session.add(Modules(module="cash", default=False, enabled=True))
        if database.session.execute(database.select(Entity).filter_by(code="cacao")).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id=f"J{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                )
            )
        database.session.flush()
        banco = Bank(name=f"Banco {sufijo}", is_active=True)
        database.session.add(banco)
        database.session.commit()
        datos = {
            "bank_id": banco.id,
            "company": "cacao",
            "account_name": "Cuenta QA",
            "account_no": f"ACC-{sufijo}",
            "currency": "NIO",
        }
        yield datos
        cuenta = database.session.execute(
            database.select(BankAccount).filter_by(company=datos["company"], account_no=datos["account_no"])
        ).scalar_one_or_none()
        if cuenta is not None:
            database.session.delete(cuenta)
        database.session.flush()
        database.session.delete(banco)
        database.session.commit()


def test_cuenta_duplicada_no_produce_500(app, authenticated_client, cuenta_bancaria):
    """La segunda alta con el mismo número devuelve error controlado."""
    client = authenticated_client("admin")
    formulario = client.get("/cash_management/bank-account/new")
    csrf_token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', formulario.get_data(as_text=True))
    assert csrf_token is not None
    datos = {**cuenta_bancaria, "csrf_token": csrf_token.group(1)}

    primera = client.post("/cash_management/bank-account/new", data=datos)
    segunda = client.post("/cash_management/bank-account/new", data=datos)

    assert primera.status_code == 302, primera.get_data(as_text=True)
    assert segunda.status_code == 200
    assert "Ya existe una cuenta bancaria" in segunda.get_data(as_text=True)
    with app.app_context():
        cuentas = (
            database.session.execute(
                database.select(BankAccount).filter_by(
                    company=cuenta_bancaria["company"], account_no=cuenta_bancaria["account_no"]
                )
            )
            .scalars()
            .all()
        )
        assert len(cuentas) == 1
