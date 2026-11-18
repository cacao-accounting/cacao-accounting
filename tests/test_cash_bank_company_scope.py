# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1526/#1527: el maestro de bancos exige permiso y el listado acota compañía.

Crear un banco requiere ``cash.crear`` y el listado de transacciones bancarias
solo muestra movimientos de cuentas de compañías consultables. La compañía del
movimiento vive en su cuenta, así que el alcance se resuelve por ese vínculo.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    Currency,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

BANK_NEW_PATH = "/cash_management/bank/new"
TRANSACTION_LIST_PATH = "/cash_management/bank-transaction/list"


@pytest.fixture
def bank_company_scope_scenario():
    """Create bank accounts and transactions in two companies."""
    app = create_app(
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
    company_alpha = f"a{suffix}"
    company_beta = f"b{suffix}"
    reader_id = f"reader-{suffix}"
    creator_id = f"creator-{suffix}"
    denied_id = f"denied-{suffix}"
    admin_id = f"admin-{suffix}"
    alpha_description = f"MOV ALFA {suffix}"
    beta_description = f"MOV BETA {suffix}"
    bank_name = f"Banco Global {suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="cash", default=False, enabled=True),
                Entity(
                    code=company_alpha,
                    name="Alfa",
                    company_name=f"Compañía Alfa {suffix}",
                    tax_id=f"TAX-A-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=company_beta,
                    name="Beta",
                    company_name=f"Compañía Beta {suffix}",
                    tax_id=f"TAX-B-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
            ]
        )
        database.session.flush()
        bank = Bank(name=bank_name)
        database.session.add(bank)
        database.session.flush()
        alpha_account = BankAccount(bank_id=bank.id, company=company_alpha, account_name="Cuenta Alfa", account_no="A-1")
        beta_account = BankAccount(bank_id=bank.id, company=company_beta, account_name="Cuenta Beta", account_no="B-1")
        database.session.add_all(
            [
                alpha_account,
                beta_account,
                User(id=reader_id, user=reader_id, name="Lector Caja", password=b"unused", active=True, company=company_alpha),
                User(
                    id=creator_id, user=creator_id, name="Creador Caja", password=b"unused", active=True, company=company_alpha
                ),
                User(id=denied_id, user=denied_id, name="Sin Caja", password=b"unused", active=True, company=company_alpha),
                User(
                    id=admin_id,
                    user=admin_id,
                    name="Administrador",
                    password=b"unused",
                    active=True,
                    company=company_alpha,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                BankTransaction(
                    identity_key=f"ALPHA-{suffix}",
                    bank_account_id=alpha_account.id,
                    posting_date=date(2026, 11, 5),
                    deposit=10,
                    description=alpha_description,
                ),
                BankTransaction(
                    identity_key=f"BETA-{suffix}",
                    bank_account_id=beta_account.id,
                    posting_date=date(2026, 11, 6),
                    withdrawal=20,
                    description=beta_description,
                ),
            ]
        )

        module_id = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
        reader_role = Roles(name=f"cash-reader-{suffix}", note="Consulta de caja")
        creator_role = Roles(name=f"cash-creator-{suffix}", note="Alta de caja")
        database.session.add_all([reader_role, creator_role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=reader_role.id, module_id=module_id, access=True, view=True),
                RolesAccess(rol_id=creator_role.id, module_id=module_id, access=True, view=True, create=True),
                RolesUser(user_id=reader_id, role_id=reader_role.id, active=True),
                RolesUser(user_id=creator_id, role_id=creator_role.id, active=True),
                UserCompanyAccess(user_id=reader_id, company_code=company_alpha),
                UserCompanyAccess(user_id=creator_id, company_code=company_alpha),
                UserCompanyAccess(user_id=denied_id, company_code=company_alpha),
            ]
        )
        database.session.commit()
        ids = {
            "company_alpha": company_alpha,
            "company_beta": company_beta,
            "alpha_description": alpha_description,
            "beta_description": beta_description,
            "bank_name": bank_name,
            "reader_id": reader_id,
            "creator_id": creator_id,
            "denied_id": denied_id,
            "admin_id": admin_id,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _authenticated_client(app, user_id: str):
    """Authenticate an isolated test client as the requested seeded user."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _bank_count(app) -> int:
    """Return how many bank master rows exist."""
    with app.app_context():
        return int(database.session.execute(database.select(database.func.count(Bank.id))).scalar_one())


def test_bank_creation_rejects_users_without_cash_create_permission(bank_company_scope_scenario):
    """A user without cash permissions cannot create a bank master (#1526)."""
    app, ids = bank_company_scope_scenario
    before = _bank_count(app)
    client = _authenticated_client(app, ids["denied_id"])

    response = client.post(BANK_NEW_PATH, data={"name": "Banco No Autorizado"})

    assert response.status_code == 403
    assert _bank_count(app) == before


def test_bank_creation_persists_for_users_with_cash_create_permission(bank_company_scope_scenario):
    """The same route keeps working for a user granted cash.create."""
    app, ids = bank_company_scope_scenario
    client = _authenticated_client(app, ids["creator_id"])

    response = client.post(BANK_NEW_PATH, data={"name": "Banco Autorizado"})

    assert response.status_code == 302
    with app.app_context():
        assert (
            database.session.execute(database.select(Bank).filter_by(name="Banco Autorizado")).scalar_one_or_none() is not None
        )


def test_bank_transaction_list_only_shows_authorized_company_accounts(bank_company_scope_scenario):
    """Bank transactions are scoped through their bank account (#1527)."""
    app, ids = bank_company_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(TRANSACTION_LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_description"] in body
    assert ids["beta_description"] not in body


def test_bank_transaction_list_rejects_foreign_company_filter(bank_company_scope_scenario):
    """An explicit company filter outside the grant is refused."""
    app, ids = bank_company_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(f"{TRANSACTION_LIST_PATH}?company={ids['company_beta']}")

    assert response.status_code == 403
    assert ids["beta_description"] not in response.get_data(as_text=True)


def test_bank_transaction_list_requires_cash_permission(bank_company_scope_scenario):
    """A user without cash consultation permission cannot open the listing (#1320)."""
    app, ids = bank_company_scope_scenario
    client = _authenticated_client(app, ids["denied_id"])

    response = client.get(TRANSACTION_LIST_PATH)

    assert response.status_code == 403
    body = response.get_data(as_text=True)
    assert ids["alpha_description"] not in body
    assert ids["beta_description"] not in body


def test_bank_transaction_list_accepts_authorized_company_filter(bank_company_scope_scenario):
    """An authorized explicit company narrows the listing without widening it."""
    app, ids = bank_company_scope_scenario
    client = _authenticated_client(app, ids["reader_id"])

    response = client.get(f"{TRANSACTION_LIST_PATH}?company={ids['company_alpha']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_description"] in body
    assert ids["beta_description"] not in body


def test_bank_transaction_list_admin_keeps_global_scope(bank_company_scope_scenario):
    """An administrator keeps every company's transactions."""
    app, ids = bank_company_scope_scenario
    client = _authenticated_client(app, ids["admin_id"])

    response = client.get(TRANSACTION_LIST_PATH)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert ids["alpha_description"] in body
    assert ids["beta_description"] in body
