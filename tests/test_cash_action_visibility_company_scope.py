# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1981: las acciones visibles de caja respetan también la compañía.

El permiso de rol es global, pero el servidor exige acceso explícito a la
compañía. La interfaz no debe ofrecer altas ni acciones sobre registros de una
compañía que el usuario no puede operar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    Book,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashVoucher,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

LIST_PATHS = (
    "/cash_management/bank-account/list",
    "/cash_management/petty-cash/list",
    "/cash_management/petty-cash-voucher/list",
    "/cash_management/petty-cash-expense/list",
)
NEW_PATH = "/cash_management/bank-account/new"


@pytest.fixture
def companias_caja():
    """Dos compañías con registros de caja y dos creadores con distinto alcance."""
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
    suffix = uuid4().hex[:6]
    alpha = f"a{suffix}"
    beta = f"b{suffix}"
    sin_compania = f"sc{suffix}"
    con_alpha = f"ca{suffix}"

    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code=alpha,
                    name=f"Alfa {suffix}",
                    company_name=f"Alfa {suffix} SA",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=beta,
                    name=f"Beta {suffix}",
                    company_name=f"Beta {suffix} SA",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                Book(code=f"A{suffix}", name="Libro Alfa", entity=alpha, currency="NIO", status="activo"),
                Book(code=f"B{suffix}", name="Libro Beta", entity=beta, currency="NIO", status="activo"),
            ]
        )
        database.session.add_all(
            [
                User(id=sin_compania, user=sin_compania, name="Sin compañía", password=b"unused", active=True),
                User(id=con_alpha, user=con_alpha, name="Solo Alfa", password=b"unused", active=True),
            ]
        )
        database.session.flush()
        database.session.add_all([UserCompanyAccess(user_id=con_alpha, company_code=alpha)])
        role = Roles(name=f"cash-creator-{suffix}", note="Alta de caja")
        database.session.add(role)
        database.session.flush()
        modulo = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=role.id,
                    module_id=modulo,
                    access=True,
                    view=True,
                    create=True,
                    edit=True,
                    set_null=True,
                ),
                RolesUser(user_id=sin_compania, role_id=role.id, active=True),
                RolesUser(user_id=con_alpha, role_id=role.id, active=True),
            ]
        )
        banco = Bank(name=f"Banco {suffix}", swift_code=f"SW{suffix}")
        database.session.add(banco)
        database.session.flush()
        gl_banco_alpha = Accounts(
            entity=alpha,
            code=f"1{suffix}",
            name="Banco contable Alfa",
            group=False,
            active=True,
            enabled=True,
            account_type="bank",
        )
        gl_banco_beta = Accounts(
            entity=beta,
            code=f"2{suffix}",
            name="Banco contable Beta",
            group=False,
            active=True,
            enabled=True,
            account_type="bank",
        )
        gl_caja = Accounts(
            entity=beta,
            code=f"3{suffix}",
            name="Caja contable",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add_all([gl_banco_alpha, gl_banco_beta, gl_caja])
        database.session.flush()
        database.session.add(
            BankAccount(
                bank_id=banco.id,
                company=beta,
                account_name="Cuenta Beta",
                account_no=f"BETA-{suffix}",
                currency="NIO",
                gl_account_id=gl_banco_beta.id,
            )
        )
        fondo = PettyCashAccount(
            company=beta,
            account_id=gl_caja.id,
            name=f"Fondo Beta {suffix}",
            currency="NIO",
            float_amount=Decimal("500"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        database.session.add_all(
            [
                PettyCashVoucher(
                    company=beta,
                    petty_cash_id=fondo.id,
                    voucher_no=f"VALE-BETA-{suffix}",
                    voucher_status="entregado",
                    delivered_to="Empleado beta",
                    concept="Viáticos beta",
                    amount=Decimal("25"),
                    posting_date=date(2026, 11, 20),
                    transaction_currency="NIO",
                ),
                PettyCashExpense(
                    company=beta,
                    petty_cash_id=fondo.id,
                    document_no=f"GTO-BETA-{suffix}",
                    concept="Gasto beta",
                    expense_account_code="5.01.01.001",
                    amount=Decimal("10"),
                    posting_date=date(2026, 11, 20),
                    docstatus=1,
                    transaction_currency="NIO",
                ),
            ]
        )
        database.session.commit()
        ids = {
            "alpha": alpha,
            "beta": beta,
            "sin_compania": sin_compania,
            "con_alpha": con_alpha,
            "bank_id": banco.id,
            "gl_account_id": gl_banco_alpha.id,
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _cliente(application, user_id: str):
    """Devuelve un cliente autenticado como el usuario indicado."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _cuentas_creadas(application, number: str) -> int:
    """Cuenta las cuentas bancarias con el número indicado."""
    with application.app_context():
        return int(
            database.session.execute(
                database.select(database.func.count(BankAccount.id)).where(BankAccount.account_no == number)
            ).scalar_one()
        )


def test_sin_compania_no_ve_altas_ni_acciones(companias_caja):
    """Con permiso global pero sin compañía no se ofrecen acciones de escritura."""
    application, ids = companias_caja
    client = _cliente(application, ids["sin_compania"])

    for path in LIST_PATHS:
        response = client.get(path)
        assert response.status_code == 200
        cuerpo = response.get_data(as_text=True)
        assert "/cash_management/bank-account/new" not in cuerpo, path
        assert "/cash_management/petty-cash/new" not in cuerpo, path
        assert "/cash_management/petty-cash-voucher/new" not in cuerpo, path
        assert "/cash_management/petty-cash-expense/new" not in cuerpo, path
        assert "Liquidar" not in cuerpo, path
        assert "Anular" not in cuerpo, path

    assert client.get(NEW_PATH).status_code == 200
    assert client.get(f"{NEW_PATH}?company={ids['beta']}").status_code == 403


def test_con_compania_no_ofrece_acciones_de_otra_compania(companias_caja):
    """El usuario con acceso a Alfa no ve acciones sobre los registros de Beta."""
    application, ids = companias_caja
    client = _cliente(application, ids["con_alpha"])

    expected_links = {
        "/cash_management/bank-account/list": "/cash_management/bank-account/new",
        "/cash_management/petty-cash/list": "/cash_management/petty-cash/new",
        "/cash_management/petty-cash-voucher/list": "/cash_management/petty-cash-voucher/new",
        "/cash_management/petty-cash-expense/list": "/cash_management/petty-cash-expense/new",
    }
    for path, enlace in expected_links.items():
        response = client.get(path)
        assert response.status_code == 200
        assert enlace in response.get_data(as_text=True), path

    vales = client.get("/cash_management/petty-cash-voucher/list").get_data(as_text=True)
    assert "Liquidar" not in vales
    gastos = client.get("/cash_management/petty-cash-expense/list").get_data(as_text=True)
    assert "Anular" not in gastos


def test_alta_entre_companias_es_rechazada_en_get_y_post(companias_caja):
    """El guard de compañía cubre el GET con query y el POST con la cuenta nueva."""
    application, ids = companias_caja
    client = _cliente(application, ids["con_alpha"])
    payload = {
        "bank_id": ids["bank_id"],
        "company": ids["beta"],
        "account_name": "Cuenta no autorizada",
        "account_no": f"FORBIDDEN-{ids['beta']}",
        "currency": "NIO",
        "gl_account_id": ids["gl_account_id"],
    }
    numero = payload["account_no"]

    assert client.get(f"{NEW_PATH}?company={ids['beta']}").status_code == 403
    assert client.post(NEW_PATH, data=payload).status_code == 403
    assert _cuentas_creadas(application, numero) == 0


def test_alta_en_compania_autorizada_persiste(companias_caja):
    """El control positivo conserva la alta en la compañía permitida."""
    application, ids = companias_caja
    client = _cliente(application, ids["con_alpha"])
    payload = {
        "bank_id": ids["bank_id"],
        "company": ids["alpha"],
        "account_name": "Cuenta autorizada",
        "account_no": f"ALLOWED-{ids['alpha']}",
        "currency": "NIO",
        "gl_account_id": ids["gl_account_id"],
    }
    numero = payload["account_no"]

    assert client.get(f"{NEW_PATH}?company={ids['alpha']}").status_code == 200
    assert client.post(NEW_PATH, data=payload).status_code == 302
    assert _cuentas_creadas(application, numero) == 1
