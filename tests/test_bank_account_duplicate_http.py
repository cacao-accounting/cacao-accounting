# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1980: una cuenta bancaria duplicada no produce 500."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    Currency,
    Entity,
    Modules,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def cuenta_bancaria(app):
    """Banco y cuenta GL de la compañía cacao para el alta por ruta."""
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
        cuenta_gl = Accounts(
            entity="cacao",
            code=f"11{sufijo}",
            name="Banco GL",
            classification="asset",
            account_type="bank",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add_all([banco, cuenta_gl])
        database.session.commit()
        yield {
            "bank_id": banco.id,
            "company": "cacao",
            "gl_account_id": cuenta_gl.id,
            "account_name": "Cuenta QA",
            "account_no": f"ACC-{sufijo}",
            "currency": "NIO",
        }


def _cliente(app):
    from cacao_accounting.auth import proteger_passwd

    sufijo = uuid4().hex[:5]
    with app.app_context():
        user_id = f"bancos-{sufijo}"
        database.session.add(
            User(
                id=user_id,
                user=user_id,
                name="Bancos",
                password=proteger_passwd("Clave-2026!"),
                active=True,
                classification="admin",
            )
        )
        database.session.add(UserCompanyAccess(user_id=user_id, company_code="cacao"))
        database.session.commit()
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def test_cuenta_duplicada_no_produce_500(app, cuenta_bancaria):
    """La segunda alta con el mismo número devuelve error controlado."""
    client = _cliente(app)

    primera = client.post("/cash_management/bank-account/new", data=cuenta_bancaria)
    segunda = client.post("/cash_management/bank-account/new", data=cuenta_bancaria)

    assert primera.status_code == 302
    assert segunda.status_code == 200
    assert "Ya existe una cuenta bancaria" in segunda.get_data(as_text=True)
    with app.app_context():
        cuentas = database.session.execute(database.select(BankAccount)).scalars().all()
        assert len(cuentas) == 1
