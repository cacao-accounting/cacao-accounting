# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1990: la lista de gastos de caja chica identifica compañía y fondo.

La vista puede reunir gastos de varias compañías autorizadas. Cada fila debe
mostrar la compañía y el nombre del fondo, no solo el ULID técnico, para que
dos gastos de entidades o fondos distintos no resulten indistinguibles.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashExpense,
    User,
    database,
)

CONTRASENA = "gastos-identidad-2026"


def _iniciar(client, app, user_id: str) -> None:
    """Abre la sesión del administrador sembrado."""
    with app.app_context():
        auth_version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True


@pytest.fixture
def gastos_multiempresa():
    """Dos compañías con un fondo y un gasto cada una, visibles por el admin."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    user_id = "admin-gastos"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="delta",
                    name="Delta",
                    company_name="Delta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id=user_id,
                    user=user_id,
                    name="Administrador de Gastos",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Book(code="CACAO", name="Libro Cacao", entity="cacao", currency="NIO", status="activo"),
                Book(code="DELTA", name="Libro Delta", entity="delta", currency="NIO", status="activo"),
            ]
        )
        database.session.flush()
        fondos: dict[str, PettyCashAccount] = {}
        for company in ("cacao", "delta"):
            cuenta = Accounts(
                code="1.01.05.001",
                name=f"Caja Chica {company}",
                entity=company,
                group=False,
                active=True,
                enabled=True,
                account_type="petty_cash",
            )
            database.session.add(cuenta)
            database.session.flush()
            fondo = PettyCashAccount(
                company=company,
                account_id=cuenta.id,
                name=f"Fondo Operativo {company}",
                currency="NIO",
                float_amount=Decimal("500"),
                is_default=True,
                is_active=True,
            )
            database.session.add(fondo)
            database.session.flush()
            fondos[company] = fondo
            database.session.add(
                PettyCashExpense(
                    company=company,
                    petty_cash_id=fondo.id,
                    concept=f"Suministro {company}",
                    expense_account_code="5.01.01.001",
                    amount=Decimal("10"),
                    posting_date=date(2026, 11, 20),
                    docstatus=1,
                    document_no=f"GTO-{company}",
                    transaction_currency="NIO",
                )
            )
        database.session.commit()
        ids = {"user": user_id, "fondos": {code: fondo.id for code, fondo in fondos.items()}}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_la_lista_de_gastos_identifica_compania_y_fondo(gastos_multiempresa):
    """El administrador distingue gastos de dos compañías y fondos distintos."""
    application, ids = gastos_multiempresa
    client = application.test_client()
    _iniciar(client, application, ids["user"])

    response = client.get("/cash_management/petty-cash-expense/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Compañía" in cuerpo and "Fondo" in cuerpo
    assert "Suministro cacao" in cuerpo and "Suministro delta" in cuerpo
    assert "Fondo Operativo cacao" in cuerpo and "Fondo Operativo delta" in cuerpo
    for codigo in ("cacao", "delta"):
        assert f"<td>{codigo}</td>" in cuerpo
        assert ids["fondos"][codigo] not in cuerpo
