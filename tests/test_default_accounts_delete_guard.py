# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2062: el borrado de cuentas predeterminadas no produce 500.

`CompanyDefaultAccount` es un modelo sensible; el guard ORM rechaza su borrado.
La ruta debe presentar ese rechazo como error controlado y conservar la
configuración, en lugar de terminar en HTTP 500.
"""

from __future__ import annotations


import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyDefaultAccount,
    Currency,
    Entity,
    Modules,
    Roles,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)


@pytest.fixture
def default_accounts_scenario():
    """Admin con acceso y una configuración de cuentas por defecto."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "INTERNAL_CONTROLS_ENFORCE": True,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
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
                User(
                    id="admin",
                    user="admin",
                    name="Admin",
                    password=b"x",
                    classification="admin",
                    active=True,
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="admin", company_code="cacao"))
        rol = Roles(name="admin", note="admin")
        database.session.add(rol)
        database.session.flush()
        database.session.add(RolesUser(user_id="admin", role_id=rol.id, active=True))
        database.session.add(CompanyDefaultAccount(company="cacao", default_cash=None))
        database.session.commit()
    yield app
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _client(application):
    client = application.test_client()
    with application.app_context():
        version = database.session.get(User, "admin").auth_version
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_auth_version"] = version
        session["_fresh"] = True
    return client


def test_delete_de_cuentas_predeterminadas_no_produce_500(default_accounts_scenario):
    """El POST delete responde con redirección y conserva la configuración."""
    application = default_accounts_scenario
    response = _client(application).post(
        "/settings/default-accounts",
        data={"action": "delete", "company": "cacao"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 200), response.get_data(as_text=True)
    with application.app_context():
        config = database.session.execute(
            database.select(CompanyDefaultAccount).filter_by(company="cacao")
        ).scalar_one_or_none()
        assert config is not None
