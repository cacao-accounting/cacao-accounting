# SPDX-License-Identifier: Apache-2.0
"""#1883: listas de caja chica, vales y gastos identifican compa??a y fondo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

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
    PettyCashVoucher,
    User,
    database,
)

CONTRASENA = "caja-identidad-2026"


def _iniciar(client, app, user_id: str) -> None:
    with app.app_context():
        auth_version = database.session.get(User, user_id).auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True


@pytest.fixture
def multiempresa():
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
    sufijo = uuid4().hex[:6]
    user_id = f"caja-{sufijo}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="C?rdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="D?lar", decimals=2, active=True, default=False),
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
                    currency="USD",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id=user_id,
                    user=user_id,
                    name="Admin Caja",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Book(code="CACAO", name="Libro Cacao", entity="cacao", currency="NIO", status="activo", is_primary=True),
                Book(code="DELTA", name="Libro Delta", entity="delta", currency="USD", status="activo", is_primary=True),
            ]
        )
        database.session.flush()
        fondos = {}
        for company, currency in (("cacao", "NIO"), ("delta", "USD")):
            cuenta = Accounts(
                code=f"1.01.05.{company}",
                name=f"Caja {company}",
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
                name=f"Fondo {company}",
                currency=currency,
                float_amount=Decimal("100"),
                is_active=True,
                is_default=True,
            )
            database.session.add(fondo)
            database.session.flush()
            fondos[company] = fondo.id
            database.session.add(
                PettyCashVoucher(
                    company=company,
                    petty_cash_id=fondo.id,
                    voucher_no=f"V-{company}",
                    delivered_to=f"Persona {company}",
                    concept=f"Concepto {company}",
                    amount=Decimal("10"),
                    posting_date=date(2026, 11, 20),
                    voucher_status="entregado",
                    docstatus=0,
                    transaction_currency=currency,
                )
            )
            database.session.add(
                PettyCashExpense(
                    company=company,
                    petty_cash_id=fondo.id,
                    document_no=f"E-{company}",
                    beneficiary=f"Prov {company}",
                    concept=f"Gasto {company}",
                    expense_account_code="5.01.01.001",
                    amount=Decimal("5"),
                    posting_date=date(2026, 11, 20),
                    docstatus=1,
                    transaction_currency=currency,
                )
            )
        database.session.commit()
        ids = {"user": user_id, "fondos": fondos}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_lista_cajas_identifica_compania(multiempresa):
    app, ids = multiempresa
    client = app.test_client()
    _iniciar(client, app, ids["user"])
    resp = client.get("/cash_management/petty-cash/list")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Compa??a" in body or "Compa" in body
    assert "Fondo cacao" in body and "Fondo delta" in body
    assert "<td>cacao</td>" in body and "<td>delta</td>" in body
    assert "NIO" in body and "USD" in body


def test_lista_vales_identifica_compania_y_fondo(multiempresa):
    app, ids = multiempresa
    client = app.test_client()
    _iniciar(client, app, ids["user"])
    resp = client.get("/cash_management/petty-cash-voucher/list")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Fondo cacao (cacao)" in body and "Fondo delta (delta)" in body
    assert "<td>cacao</td>" in body and "<td>delta</td>" in body
    assert ids["fondos"]["cacao"] not in body and ids["fondos"]["delta"] not in body


def test_lista_gastos_identifica_fondo_con_compania(multiempresa):
    app, ids = multiempresa
    client = app.test_client()
    _iniciar(client, app, ids["user"])
    resp = client.get("/cash_management/petty-cash-expense/list")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Fondo cacao (cacao)" in body and "Fondo delta (delta)" in body
    assert ids["fondos"]["cacao"] not in body and ids["fondos"]["delta"] not in body
